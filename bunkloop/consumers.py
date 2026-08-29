import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ValidationError, PermissionDenied

class ChatConsumer(AsyncWebsocketConsumer):
    """
    Thin WebSocket consumer per plan §30.
    - Auth via AuthMiddlewareStack
    - Membership check (§13)
    - Group per conversation (§14)
    - Validate, save to Postgres, broadcast via Redis
    """

    async def connect(self):
        user = self.scope.get("user")
        if not user or user.is_anonymous:
            await self.close(code=4401)
            return

        self.conversation_id = self.scope["url_route"]["kwargs"].get("conversation_id")
        # Resolve conversation (support int pk or uuid)
        self.conversation = await self.get_conversation()
        if not self.conversation:
            await self.close(code=4404)
            return

        # Authorization: must be member (§13)
        is_member = await self.is_member(user, self.conversation)
        if not is_member:
            # Also check university isolation
            await self.close(code=4403)
            return

        # Also check university isolation
        if self.conversation.university_id and user.university_id and self.conversation.university_id != user.university_id:
            await self.close(code=4403)
            return

        self.group_name = f"chat_{self.conversation.pk}"  # per §14, use pk (or uuid)
        # If uuid exists, use it for group to match plan's UUID group name
        try:
            if self.conversation.uuid:
                self.group_name = f"chat_{self.conversation.uuid}"
        except Exception:
            pass

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Optional presence (§20) — could set presence key in Redis here

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            try:
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
            except Exception:
                pass

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            return
        try:
            data = json.loads(text_data)
        except Exception:
            await self.send(text_data=json.dumps({"error": "Invalid JSON"}))
            return

        msg_type = data.get("type", "message.send")
        if msg_type == "message.send":
            content = data.get("content", "") or data.get("body", "")
            message_type = data.get("message_type", "text")
            await self.handle_message_send(content, message_type)
        elif msg_type == "message.read":
            message_id = data.get("message_id")
            await self.handle_message_read(message_id)
        elif msg_type in ("typing.start", "typing.stop"):
            # Typing indicators (§21) — just relay via Redis, not persisted
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "typing_event",
                    "typing_type": msg_type,
                    "user_id": self.scope["user"].id,
                    "username": self.scope["user"].username,
                }
            )
        else:
            await self.send(text_data=json.dumps({"error": f"Unknown type {msg_type}"}))

    async def handle_message_send(self, content, message_type="text"):
        user = self.scope["user"]
        # Validation (§23)
        content = (content or "").strip()
        if not content and message_type == "text":
            await self.send(text_data=json.dumps({"error": "Message cannot be empty", "type": "error"}))
            return
        if len(content) > 5000:
            await self.send(text_data=json.dumps({"error": "Message too long (max 5000)", "type": "error"}))
            return
        # Rate limiting (§22) — simple in-memory via cache; for MVP use cache
        allowed = await self.check_rate_limit(user)
        if not allowed:
            await self.send(text_data=json.dumps({"error": "Rate limit exceeded. Slow down.", "type": "error"}))
            return

        # Save to Postgres via service
        try:
            message = await self.create_message_db(content, message_type)
        except (ValidationError, PermissionDenied) as e:
            await self.send(text_data=json.dumps({"error": str(e), "type": "error"}))
            return
        except Exception as e:
            await self.send(text_data=json.dumps({"error": f"Failed to save: {e}", "type": "error"}))
            return

        # Broadcast (plan §15) — must be saved first
        payload = {
            "type": "message.new",
            "message": {
                "id": message["id"],
                "conversation_id": str(message["conversation_id"]),
                "sender_id": message["sender_id"],
                "sender_name": message["sender_name"],
                "sender_registration_id": message["sender_registration_id"],
                "message_type": message["message_type"],
                "content": message["content"],
                "created_at": message["created_at"],
            }
        }
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat_message",
                "payload": payload,
            }
        )
        # Also echo to sender as confirmation (group_send will also deliver to sender, but ensure)
        # No need to send separately; group includes sender

    async def chat_message(self, event):
        payload = event.get("payload")
        if payload:
            await self.send(text_data=json.dumps(payload))

    async def typing_event(self, event):
        await self.send(text_data=json.dumps({
            "type": event.get("typing_type"),
            "user_id": event.get("user_id"),
            "username": event.get("username"),
        }))

    async def handle_message_read(self, message_id):
        user = self.scope["user"]
        try:
            await self.mark_read_db(message_id)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "read_event",
                    "payload": {
                        "type": "message.read",
                        "user_id": user.id,
                        "message_id": message_id,
                    }
                }
            )
        except Exception as e:
            await self.send(text_data=json.dumps({"error": str(e), "type": "error"}))

    async def read_event(self, event):
        payload = event.get("payload")
        if payload:
            await self.send(text_data=json.dumps(payload))

    @database_sync_to_async
    def get_conversation(self):
        from .models import Conversation
        import uuid as _uuid
        cid = self.conversation_id
        # Try integer pk first
        try:
            # If cid is digit, try pk
            if str(cid).isdigit():
                return Conversation.objects.select_related('university').get(pk=int(cid))
        except Conversation.DoesNotExist:
            pass
        except Exception:
            pass
        # Try UUID
        try:
            uid = _uuid.UUID(str(cid))
            return Conversation.objects.select_related('university').get(uuid=uid)
        except Exception:
            pass
        # Fallback try pk as string
        try:
            return Conversation.objects.select_related('university').get(pk=cid)
        except Exception:
            return None

    @database_sync_to_async
    def is_member(self, user, conversation):
        from .models import ConversationMember
        # Check membership table first
        if ConversationMember.objects.filter(conversation=conversation, user=user).exists():
            return True
        # Fallback legacy buyer/seller
        return user.pk in (conversation.buyer_id, conversation.seller_id)

    @database_sync_to_async
    def create_message_db(self, content, message_type):
        from .services import create_message
        user = self.scope["user"]
        # Need to get conversation fresh (already have self.conversation)
        # Use sync version; self.conversation was fetched in async context, need to refetch for sync
        from .models import Conversation
        conv = Conversation.objects.get(pk=self.conversation.pk)
        msg = create_message(conversation=conv, sender=user, content=content, message_type=message_type)
        return {
            "id": msg.pk,
            "conversation_id": conv.pk,  # also expose uuid if exists
            "sender_id": msg.sender_id,
            "sender_name": msg.sender.full_name or msg.sender.username,
            "sender_registration_id": getattr(msg.sender, 'registration_id', ''),
            "message_type": msg.message_type,
            "content": msg.content or msg.body,
            "created_at": msg.created_at.isoformat(),
        }

    @database_sync_to_async
    def mark_read_db(self, message_id):
        from .services import mark_conversation_read
        from .models import Conversation
        conv = Conversation.objects.get(pk=self.conversation.pk)
        user = self.scope["user"]
        mark_conversation_read(conv, user, message_id)

    @database_sync_to_async
    def check_rate_limit(self, user):
        # MVP: 30/min for normal, 10/min for new? Use simple cache with Redis if available, else allow
        try:
            from django.core.cache import cache
            key = f"chat_rate:user:{user.id}"
            # Use fixed window: increment and expire 60s
            count = cache.get(key, 0)
            if count >= 30:
                return False
            # Use add to handle race
            if count == 0:
                cache.set(key, 1, 60)
            else:
                cache.incr(key)
            return True
        except Exception:
            # If cache not available (e.g., no Redis), allow
            return True
