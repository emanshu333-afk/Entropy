from django.db.models import Q

def nav_counts(request):
    # Guard for error pages / requests without session (e.g., 404 via RequestFactory)
    if not hasattr(request, 'session'):
        return {}
    try:
        reg_id = request.session.get('user_registration_id')
    except Exception:
        return {}
    if not reg_id:
        return {}
    try:
        from .models import Conversation, Message, Order, User
        user = User.objects.filter(registration_id=reg_id).first()
        if not user:
            return {}
        unread = Message.objects.filter(
            conversation__in=Conversation.objects.filter(Q(buyer=user) | Q(seller=user)),
            is_read=False
        ).exclude(sender=user).count()
        pending = Order.objects.filter(
            Q(buyer=user, status__in=['paid','confirmed','shipped','delivered']) |
            Q(seller=user, status__in=['paid','confirmed','shipped'])
        ).count()
        return {'nav_unread_count': unread, 'nav_pending_orders': pending}
    except Exception:
        return {}
