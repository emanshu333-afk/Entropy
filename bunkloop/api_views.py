"""REST APIs for chat per plan §7-10."""
from rest_framework import generics, permissions, status
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied

from .models import Conversation, Message, Item
from .serializers import ConversationSerializer, MessageSerializer
from .services import (
    get_or_create_listing_conversation,
    get_user_conversations,
    get_conversation_messages,
    mark_conversation_read,
)


class ConversationCursorPagination(CursorPagination):
    ordering = '-updated_at'
    page_size = 50


class MessageCursorPagination(CursorPagination):
    ordering = '-created_at'
    page_size = 50


class ConversationListCreateAPIView(generics.ListCreateAPIView):
    """
    GET /api/chat/conversations/  — list
    POST /api/chat/conversations/ — create {listing_id}
    """
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ConversationCursorPagination
    ordering = '-updated_at'
    ordering_fields = ['updated_at', 'created_at']

    def get_queryset(self):
        return get_user_conversations(self.request.user)

    def create(self, request, *args, **kwargs):
        listing_id = request.data.get('listing_id') or request.data.get('item_id') or request.data.get('listing') or request.data.get('item')
        if not listing_id:
            return Response({"error": "listing_id required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            listing = Item.objects.select_related('registration_id', 'registration_id__university').get(pk=listing_id)
        except Item.DoesNotExist:
            return Response({"error": "Listing not found"}, status=status.HTTP_404_NOT_FOUND)
        seller = listing.registration_id
        buyer = request.user
        try:
            conversation, created = get_or_create_listing_conversation(buyer=buyer, seller=seller, item=listing)
        except ValidationError as e:
            return Response({"error": str(e.message) if hasattr(e, 'message') else str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = self.get_serializer(conversation)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ConversationDetailAPIView(generics.RetrieveAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        return get_user_conversations(self.request.user)

    def get_object(self):
        # Support both pk and uuid
        lookup = self.kwargs.get(self.lookup_field)
        # Try to find via get_user_conversations
        qs = self.get_queryset()
        # Try integer pk
        try:
            if str(lookup).isdigit():
                obj = qs.filter(pk=int(lookup)).first()
                if obj:
                    return obj
        except Exception:
            pass
        # Try uuid
        try:
            import uuid as _uuid
            uid = _uuid.UUID(str(lookup))
            obj = qs.filter(uuid=uid).first()
            if obj:
                return obj
        except Exception:
            pass
        # Fallback 404
        return super().get_object()


class MessageListAPIView(generics.ListCreateAPIView):
    """
    GET /api/chat/conversations/<uuid|pk>/messages/?limit=50&before=<id>
    POST /api/chat/conversations/<uuid|pk>/messages/ {content} — REST fallback when WebSocket not available
    """
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        conversation_id = self.kwargs.get('conversation_pk') or self.kwargs.get('pk')
        # Resolve conversation via user's conversations
        conversation = self._get_conversation(conversation_id)
        if not conversation:
            return Message.objects.none()
        # Check membership
        from .services import ensure_conversation_member
        try:
            ensure_conversation_member(conversation, self.request.user)
        except Exception:
            return Message.objects.none()
        # University isolation
        if conversation.university_id and self.request.user.university_id and conversation.university_id != self.request.user.university_id:
            return Message.objects.none()
        limit = self.request.query_params.get('limit', '50')
        before = self.request.query_params.get('before')
        try:
            limit = int(limit)
            limit = max(1, min(limit, 100))
        except Exception:
            limit = 50
        # Use service for pagination
        messages = get_conversation_messages(conversation, limit=limit, before_id=before)
        # Return queryset-like (list) — but DRF expects queryset, so we return filtered queryset for pagination
        # For simplicity, return the list via custom response in list()
        # Instead, handle in list()
        return Message.objects.filter(pk__in=[m.pk for m in messages]).select_related('sender').order_by('created_at')

    def _get_conversation(self, lookup):
        from .models import Conversation
        qs = get_user_conversations(self.request.user)
        try:
            if str(lookup).isdigit():
                obj = qs.filter(pk=int(lookup)).first()
                if obj:
                    return obj
        except Exception:
            pass
        try:
            import uuid as _uuid
            uid = _uuid.UUID(str(lookup))
            obj = qs.filter(uuid=uid).first()
            if obj:
                return obj
        except Exception:
            pass
        try:
            return qs.filter(pk=lookup).first()
        except Exception:
            return None

    def list(self, request, *args, **kwargs):
        # Override to use service pagination and return in correct order
        conversation_id = self.kwargs.get('conversation_pk') or self.kwargs.get('pk')
        conversation = self._get_conversation(conversation_id)
        if not conversation:
            return Response({"error": "Conversation not found or access denied"}, status=status.HTTP_404_NOT_FOUND)
        limit = request.query_params.get('limit', '50')
        before = request.query_params.get('before')
        try:
            limit = int(limit)
            limit = max(1, min(limit, 100))
        except Exception:
            limit = 50
        messages = get_conversation_messages(conversation, limit=limit, before_id=before)
        serializer = self.get_serializer(messages, many=True)
        return Response(serializer.data)


class MarkReadAPIView(APIView):
    """
    POST /api/chat/conversations/<uuid>/read/  {message_id}
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        # Find conversation
        from .models import Conversation
        qs = get_user_conversations(request.user)
        conversation = None
        try:
            if str(pk).isdigit():
                conversation = qs.filter(pk=int(pk)).first()
            if not conversation:
                import uuid as _uuid
                uid = _uuid.UUID(str(pk))
                conversation = qs.filter(uuid=uid).first()
        except Exception:
            pass
        if not conversation:
            try:
                conversation = qs.get(pk=pk)
            except Exception:
                return Response({"error": "Conversation not found"}, status=status.HTTP_404_NOT_FOUND)
        message_id = request.data.get('message_id')
        try:
            mark_conversation_read(conversation, request.user, message_id)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"status": "ok"})
