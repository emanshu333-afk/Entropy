"""Service layer for messaging — keeps business logic out of views/consumers (plan §31)."""
import uuid
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone

from django.conf import settings

from .models import Conversation, ConversationMember, Message

# Env-driven limits (was hard-coded 5000, 100, 30)
MAX_TEXT_LENGTH = getattr(settings, 'CHAT_MAX_MESSAGE_LENGTH', 5000)


def get_or_create_listing_conversation(buyer, seller, item):
    """
    Reuse existing conversation for buyer+seller+listing, else create.
    Enforces: buyer != seller, same university, listing exists.
    Uses transaction.atomic() to avoid duplicate under concurrent requests (plan §32).
    """
    if buyer.pk == seller.pk:
        raise ValidationError("You cannot message yourself.")
    # University isolation (§6)
    if buyer.university_id and seller.university_id and buyer.university_id != seller.university_id:
        raise ValidationError("You can only message sellers from your university.")
    if not item:
        raise ValidationError("Listing not found.")
    # Also enforce listing's university matches buyer's university if listing has university via seller
    # For MVP, item's university via registration_id should match buyer's university
    try:
        listing_uni = item.registration_id.university_id if hasattr(item, 'registration_id') else None
        if listing_uni and buyer.university_id and listing_uni != buyer.university_id:
            raise ValidationError("Listing not in your university.")
    except Exception:
        pass

    with transaction.atomic():
        # Try to find existing
        conversation = Conversation.objects.filter(item=item, buyer=buyer, seller=seller).first()
        if conversation:
            # Ensure university/listing filled if missing (backfill)
            if not conversation.university_id:
                conversation.university = seller.university if seller.university_id else buyer.university
                conversation.save(update_fields=['university'])
            if not conversation.listing_id:
                conversation.listing_id = item.pk
                conversation.save(update_fields=['listing'])
            # Ensure members
            for user in (buyer, seller):
                ConversationMember.objects.get_or_create(conversation=conversation, user=user)
            return conversation, False

        # Create new conversation
        # Use get_or_create with unique_together to handle race
        conversation, created = Conversation.objects.get_or_create(
            item=item,
            buyer=buyer,
            defaults={
                'seller': seller,
                'university': seller.university if seller.university_id else buyer.university,
                'listing': item,
            }
        )
        # If created via get_or_create race, ensure listing/university
        if created:
            # Already has defaults, but ensure save triggers auto-fill if needed
            pass
        else:
            # Another thread created it concurrently, ensure members
            pass
        # Ensure membership rows
        for user in (buyer, seller):
            ConversationMember.objects.get_or_create(conversation=conversation, user=user)
        return conversation, created


def ensure_conversation_member(conversation, user):
    """Ensure user is member, else raise PermissionDenied."""
    if not ConversationMember.objects.filter(conversation=conversation, user=user).exists():
        # Fallback to legacy buyer/seller check for old conversations
        if user.pk not in (conversation.buyer_id, conversation.seller_id):
            raise PermissionDenied("You are not a member of this conversation.")
        # Auto-create membership for legacy data
        ConversationMember.objects.get_or_create(conversation=conversation, user=user)
    return True


def get_user_conversations(user):
    """Return conversations for user ordered by most recent activity (plan §9)."""
    from django.db.models import Q
    return Conversation.objects.filter(Q(buyer=user) | Q(seller=user) | Q(memberships__user=user)).distinct().select_related('item', 'buyer', 'seller', 'university').prefetch_related('messages', 'memberships').order_by('-updated_at')


def get_conversation_messages(conversation, limit=50, before_id=None):
    """Paginated message history (plan §10). Ordered DESC limit."""
    from django.conf import settings as _s
    max_limit = getattr(_s, 'CHAT_PAGINATION_MAX_LIMIT', 100)
    limit = max(1, min(limit, max_limit))
    qs = Message.objects.filter(conversation=conversation, deleted_at__isnull=True).select_related('sender').order_by('-created_at')
    if before_id:
        try:
            before_msg = Message.objects.get(pk=before_id, conversation=conversation)
            qs = qs.filter(created_at__lt=before_msg.created_at)
        except Message.DoesNotExist:
            pass
    # Return latest `limit` in chronological order for rendering
    messages = list(qs[:limit][::-1])
    return messages


def create_message(conversation, sender, content, message_type='text', media_url=''):
    """Validate and persist message (plan §15)."""
    from django.conf import settings as _s
    max_len = getattr(_s, 'CHAT_MAX_MESSAGE_LENGTH', 5000)
    content = (content or '').strip()
    if not content and message_type == 'text':
        raise ValidationError("Message cannot be empty.")
    if len(content) > max_len:
        raise ValidationError(f"Message too long (max {max_len} chars).")
    # Membership check
    ensure_conversation_member(conversation, sender)
    # University isolation
    if conversation.university_id and sender.university_id and conversation.university_id != sender.university_id:
        raise ValidationError("University isolation: conversation not in your university.")
    # Create
    msg = Message.objects.create(
        conversation=conversation,
        sender=sender,
        content=content,
        body=content,  # compat
        message_type=message_type,
        media_url=media_url,
    )
    # Touch conversation updated_at
    conversation.save(update_fields=['updated_at'])
    return msg


def mark_conversation_read(conversation, user, message_id=None):
    """Update ConversationMember.last_read_message (plan §17)."""
    try:
        member = ConversationMember.objects.get(conversation=conversation, user=user)
    except ConversationMember.DoesNotExist:
        # Legacy fallback
        ensure_conversation_member(conversation, user)
        member = ConversationMember.objects.get(conversation=conversation, user=user)
    if message_id:
        try:
            msg = Message.objects.get(pk=message_id, conversation=conversation)
            member.last_read_message = msg
        except Message.DoesNotExist:
            # Mark latest
            latest = Message.objects.filter(conversation=conversation).order_by('-created_at').first()
            if latest:
                member.last_read_message = latest
    else:
        latest = Message.objects.filter(conversation=conversation).order_by('-created_at').first()
        if latest:
            member.last_read_message = latest
    member.save(update_fields=['last_read_message'])
    # Also mark messages as read for legacy is_read field
    Message.objects.filter(conversation=conversation).exclude(sender=user).filter(is_read=False).update(is_read=True)
    return member


def get_unread_count(conversation, user):
    """Unread based on last_read_message (plan §18) fallback to is_read."""
    try:
        member = ConversationMember.objects.get(conversation=conversation, user=user)
        if member.last_read_message_id:
            return Message.objects.filter(conversation=conversation, created_at__gt=member.last_read_message.created_at).exclude(sender=user).filter(deleted_at__isnull=True).count()
    except ConversationMember.DoesNotExist:
        pass
    # Fallback
    return Message.objects.filter(conversation=conversation, is_read=False).exclude(sender=user).filter(deleted_at__isnull=True).count()

