from rest_framework import serializers

from .models import Conversation, ConversationMember, Message, Item


class ItemBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ['id', 'title', 'price']


class UserBriefSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    registration_id = serializers.CharField()


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    # Expose both body and content for compat
    content = serializers.CharField()

    class Meta:
        model = Message
        fields = ['id', 'conversation', 'sender', 'message_type', 'content', 'body', 'media_url', 'created_at', 'edited_at', 'deleted_at']
        read_only_fields = ['id', 'created_at', 'sender']

    def get_sender(self, obj):
        user = obj.sender
        return {
            'id': user.id,
            'name': user.full_name or user.username,
            'registration_id': getattr(user, 'registration_id', ''),
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Ensure content/body sync
        if not data.get('content') and data.get('body'):
            data['content'] = data['body']
        return data


class ConversationSerializer(serializers.ModelSerializer):
    listing = ItemBriefSerializer(source='item', read_only=True)
    # Also expose 'item' as alias
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    university = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'uuid', 'university', 'listing', 'item', 'other_user', 'last_message', 'unread_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']

    def get_university(self, obj):
        if obj.university:
            return {'id': obj.university.id, 'name': obj.university.name}
        return None

    def get_other_user(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or request.user.is_anonymous:
            return None
        user = request.user
        # Determine other user
        try:
            # Prefer membership, but fallback to buyer/seller
            if obj.buyer_id == user.pk:
                other = obj.seller
            elif obj.seller_id == user.pk:
                other = obj.buyer
            else:
                # Check membership
                other_mem = obj.memberships.exclude(user=user).first()
                other = other_mem.user if other_mem else None
            if other:
                return {
                    'id': other.id,
                    'name': other.full_name or other.username,
                    'registration_id': getattr(other, 'registration_id', ''),
                }
        except Exception:
            pass
        return None

    def get_last_message(self, obj):
        try:
            last = obj.messages.filter(deleted_at__isnull=True).order_by('-created_at').first()
            if last:
                return MessageSerializer(last).data
        except Exception:
            pass
        return None

    def get_unread_count(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or request.user.is_anonymous:
            return 0
        try:
            from .services import get_unread_count
            return get_unread_count(obj, request.user)
        except Exception:
            try:
                return obj.messages.filter(is_read=False).exclude(sender=request.user).filter(deleted_at__isnull=True).count()
            except Exception:
                return 0
