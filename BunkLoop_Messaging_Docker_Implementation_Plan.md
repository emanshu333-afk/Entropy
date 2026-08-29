# BunkLoop Messaging System — Docker-Aware Implementation Plan for Coding Agent

## 1. Objective

Implement a scalable real-time messaging system for **BunkLoop**, a university-focused campus marketplace.

Expected future scale:

- ~20,000 students per university
- ~4–5 universities initially
- ~80,000–100,000 registered users total
- Messaging is primarily **buyer ↔ seller**
- Most conversations should be linked to a marketplace listing
- Architecture must work for the hackathon MVP but remain extensible for production

The system should prioritize:

1. Correctness
2. Security
3. Simple implementation
4. Horizontal scalability later
5. Low unnecessary complexity

Do **not** attempt WhatsApp-level architecture for the MVP.

---

# 2. Recommended Technology Stack

Use:

- **Django** — main backend
- **Django REST Framework** — REST APIs
- **Django Channels** — WebSocket support
- **PostgreSQL** — persistent source of truth
- **Redis** — Channels layer, real-time communication, presence, rate limiting, cache
- **Daphne or Uvicorn** — ASGI server
- **Nginx** — reverse proxy in deployment
- **Object storage** — future media/file storage

Suggested future object storage:

- Cloudflare R2
- AWS S3
- Google Cloud Storage

Do not store image/video binaries directly inside PostgreSQL.

---

# 3. Architectural Principle

The messaging architecture should be:

```text
Frontend
   │
   ├──── REST API ────────────────┐
   │                              │
   └──── WebSocket ────────┐      │
                           │      │
                     Django / DRF
                     Django Channels
                           │
                ┌──────────┴──────────┐
                │                     │
           PostgreSQL               Redis
        source of truth         realtime/cache
```

Critical rule:

> PostgreSQL is the durable source of truth. Redis is temporary infrastructure.

If Redis is flushed or restarted, messages must still exist.

---

# 4. Core Messaging Model

Implement these models.

## University

Use the project's existing University model if one already exists.

Conceptually:

```python
class University(models.Model):
    id = ...
    name = ...
```

Every user should belong to a university.

---

## Conversation

Recommended fields:

```python
class Conversation(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    university = models.ForeignKey(
        University,
        on_delete=models.CASCADE,
        related_name="conversations"
    )

    listing = models.ForeignKey(
        "marketplace.Listing",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversations"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

For the MVP, conversations are one-to-one.

Do not add group chat unless already required elsewhere.

---

## ConversationMember

Use a membership table instead of hard-coding `buyer` and `seller` onto Conversation.

```python
class ConversationMember(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="memberships"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation_memberships"
    )

    last_read_message = models.ForeignKey(
        "Message",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+"
    )

    muted = models.BooleanField(default=False)

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="unique_conversation_member"
            )
        ]
```

Benefits:

- Cleaner authorization
- Easy future group-chat support
- Efficient read receipts
- No separate read-status row per message

---

## Message

Recommended structure:

```python
class Message(models.Model):

    class MessageType(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        SYSTEM = "system", "System"

    id = models.BigAutoField(primary_key=True)

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_messages"
    )

    message_type = models.CharField(
        max_length=20,
        choices=MessageType.choices,
        default=MessageType.TEXT
    )

    content = models.TextField(blank=True)

    media_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    edited_at = models.DateTimeField(null=True, blank=True)

    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["conversation", "-created_at"]
            ),
            models.Index(
                fields=["sender", "-created_at"]
            ),
        ]
```

For the MVP, text messages are enough.

---

# 5. Conversation Creation Rules

Messaging should normally start from a marketplace listing.

Example flow:

```text
Listing page
     ↓
Message Seller
     ↓
Backend checks:
- buyer != seller
- same university
- listing exists
- listing is active
     ↓
Find existing conversation
OR
Create conversation
     ↓
Return conversation UUID
```

Avoid creating duplicate conversations for the same:

```text
buyer + seller + listing
```

The backend should reuse an existing conversation when possible.

Recommended service:

```python
get_or_create_listing_conversation(
    buyer,
    seller,
    listing
)
```

---

# 6. University Isolation

BunkLoop is campus-based.

Unless requirements change, enforce:

```python
sender.university_id == recipient.university_id
```

and:

```python
conversation.university_id == request.user.university_id
```

Do not trust a university ID supplied by the frontend.

Always derive the university from authenticated server-side user data.

---

# 7. REST API Endpoints

Suggested endpoints:

```text
POST /api/chat/conversations/
GET  /api/chat/conversations/
GET  /api/chat/conversations/<uuid>/
GET  /api/chat/conversations/<uuid>/messages/
POST /api/chat/conversations/<uuid>/read/
```

Optional:

```text
DELETE /api/chat/messages/<id>/
PATCH  /api/chat/messages/<id>/
```

Not necessary for first MVP.

---

# 8. Create Conversation API

Example request:

```json
{
  "listing_id": 153
}
```

The seller should be determined from the listing.

Do not let the client freely specify arbitrary seller IDs unless general DMs are intentionally supported.

Backend should:

1. Authenticate user
2. Fetch listing
3. Confirm listing belongs to the same university
4. Confirm current user is not listing owner
5. Check for an existing conversation
6. Create if needed
7. Add both ConversationMember rows
8. Return conversation

---

# 9. Conversation List API

Return:

```json
[
  {
    "id": "uuid",
    "listing": {
      "id": 153,
      "title": "Casio fx-991EX",
      "price": 700
    },
    "other_user": {
      "id": 441,
      "name": "Student Name"
    },
    "last_message": {
      "id": 9192,
      "content": "Can you do 650?",
      "created_at": "..."
    },
    "unread_count": 2
  }
]
```

Order conversations by most recent message/activity.

---

# 10. Message History API

Use pagination.

Do not return the entire chat history at once.

Recommended:

```text
GET /api/chat/conversations/<uuid>/messages/?limit=50&before=<message_id>
```

or cursor pagination through DRF.

Default page:

```text
50 messages
```

Query pattern:

```sql
SELECT *
FROM message
WHERE conversation_id = ?
ORDER BY created_at DESC
LIMIT 50;
```

Ensure the compound database index exists.

---

# 11. WebSocket Endpoint

Recommended endpoint:

```text
ws/chat/<conversation_uuid>/
```

Example:

```text
wss://api.bunkloop.com/ws/chat/2b3ef8c9-.../
```

Create a Channels consumer.

Possible file:

```text
chat/
├── consumers.py
├── routing.py
├── models.py
├── serializers.py
├── views.py
├── urls.py
├── services.py
└── permissions.py
```

---

# 12. WebSocket Authentication

The connection MUST authenticate the logged-in user.

If using Django session authentication, use:

```python
AuthMiddlewareStack
```

If the project uses JWT authentication, implement an appropriate WebSocket JWT middleware.

Do not allow anonymous chat connections.

---

# 13. WebSocket Authorization

Knowing the conversation UUID must never grant access.

When a WebSocket connects:

```python
conversation = await get_conversation(...)
```

then verify:

```python
ConversationMember.objects.filter(
    conversation=conversation,
    user=self.scope["user"]
).exists()
```

If false:

```text
close connection
```

Recommended close code:

```text
4403
```

for forbidden access.

Apply equivalent authorization to every REST chat endpoint.

---

# 14. Channels Group Structure

Use one group per conversation.

Example:

```python
group_name = f"chat_{conversation.id}"
```

On connect:

```python
await self.channel_layer.group_add(
    group_name,
    self.channel_name
)
```

On disconnect:

```python
await self.channel_layer.group_discard(
    group_name,
    self.channel_name
)
```

---

# 15. Message Send Flow

Client sends:

```json
{
  "type": "message.send",
  "content": "Is this still available?"
}
```

Server must:

1. Validate authenticated user
2. Validate conversation membership
3. Validate content
4. Rate-limit sender
5. Save message to PostgreSQL
6. Broadcast saved message through Channels/Redis
7. Return the persisted message ID and timestamp

Flow:

```text
Sender
   ↓
WebSocket
   ↓
Channels Consumer
   ↓
Validation
   ↓
PostgreSQL INSERT
   ↓
Redis / Channel Layer
   ↓
Conversation group
   ↓
Recipient
```

Never broadcast an unsaved message as if it were successfully persisted.

---

# 16. Standard WebSocket Events

Use predictable event names.

MVP:

```text
message.send
message.new
message.read
```

Later:

```text
message.edit
message.delete
typing.start
typing.stop
presence.online
presence.offline
```

Example server response:

```json
{
  "type": "message.new",
  "message": {
    "id": 128991,
    "conversation_id": "uuid",
    "sender_id": 6121,
    "message_type": "text",
    "content": "Is this still available?",
    "created_at": "2026-08-29T21:40:00+05:30"
  }
}
```

---

# 17. Read Receipts

Do not create a `MessageReadReceipt` row for every message.

For one-to-one chat, store:

```text
ConversationMember.last_read_message_id
```

When a user opens or reads through the latest message:

```text
POST /api/chat/conversations/<uuid>/read/
```

or WebSocket:

```json
{
  "type": "message.read",
  "message_id": 128991
}
```

Backend updates:

```python
membership.last_read_message = message
```

Then optionally broadcast:

```json
{
  "type": "message.read",
  "user_id": 123,
  "message_id": 128991
}
```

---

# 18. Unread Counts

Source of truth:

```text
last_read_message_id
```

Initially, calculate unread counts in PostgreSQL.

Example logic:

```text
messages after last_read_message
AND sender != current_user
```

Do not prematurely create a complicated unread-count service.

At higher scale, Redis may cache values such as:

```text
unread:user:123:conversation:abc
```

but Redis must remain only a cache.

---

# 19. Redis Responsibilities

Redis should handle:

- Django Channels channel layer
- WebSocket fan-out
- Presence
- Typing state
- Rate limiting
- Temporary unread count cache
- Short-lived locks if needed

Redis should NOT permanently store:

- Message history
- Conversation history
- User account data

---

# 20. Presence System

Presence is optional for the MVP.

If implemented:

```text
presence:user:<id> = timestamp
```

with an expiration/TTL.

Example:

```text
TTL = 60–120 seconds
```

Client heartbeat can refresh it.

Do not store permanent "online" booleans in PostgreSQL.

---

# 21. Typing Indicators

Skip typing indicators until core messaging works.

If later implemented:

Client sends:

```json
{
  "type": "typing.start"
}
```

and:

```json
{
  "type": "typing.stop"
}
```

These should:

- travel only through Redis/Channels
- not be saved to PostgreSQL
- expire automatically

---

# 22. Rate Limiting

Messaging requires spam protection.

Suggested MVP limits:

```text
New accounts:
10 messages/minute

Normal accounts:
30 messages/minute
```

Implement using Redis.

Possible key:

```text
chat_rate:user:<user_id>
```

Use fixed-window or token-bucket logic.

Never rely only on frontend throttling.

---

# 23. Message Validation

At minimum:

```text
MAX_TEXT_LENGTH = 2000–5000 chars
```

Reject:

- empty text messages
- oversized messages
- malformed payloads
- unauthorized conversation access

Escape/render text safely on the frontend.

Do not treat user message content as HTML.

---

# 24. Blocking and Reporting

Recommended production features:

```text
BlockUser
Report
```

Blocking should prevent:

- creating a new conversation
- sending messages
- optionally viewing profile/contact details

These are more valuable for marketplace safety than reactions, stickers, or group chats.

For the hackathon, these can remain future work unless already required.

---

# 25. Media Messages

Do not implement media until text messaging works reliably.

Future flow:

```text
Client
  ↓
Upload endpoint
  ↓
Object storage
  ↓
Receive media URL
  ↓
Send WebSocket message containing URL
  ↓
Store only metadata/URL in PostgreSQL
```

Example:

```json
{
  "type": "message.send",
  "message_type": "image",
  "media_url": "https://cdn.example.com/..."
}
```

Add upload validation for:

- MIME type
- file size
- extension
- malicious content

---

# 26. Notifications

Later architecture:

```text
New message
    ↓
Is recipient connected?
    ├── Yes → WebSocket delivery
    └── No  → notification service
                  ↓
                 FCM
```

Possible notification:

```text
A student messaged you about "Casio fx-991EX"
"Can you do ₹650?"
```

For MVP, in-app WebSocket messaging is sufficient.

---

# 27. Django Channels Configuration

Install:

```bash
pip install channels channels-redis
```

Optionally:

```bash
pip install daphne
```

Settings example:

```python
INSTALLED_APPS = [
    "daphne",
    "channels",
    ...
]

ASGI_APPLICATION = "config.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}
```

Use environment variables instead of hard-coded production credentials.

---

# 28. ASGI Configuration

Example:

```python
import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

import chat.routing

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,

    "websocket": AuthMiddlewareStack(
        URLRouter(
            chat.routing.websocket_urlpatterns
        )
    ),
})
```

Adapt project module names as required.

---

# 29. Routing

Example:

```python
from django.urls import re_path

from .consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/chat/(?P<conversation_id>[0-9a-f-]+)/$",
        ChatConsumer.as_asgi(),
    ),
]
```

---

# 30. Consumer Responsibilities

Keep the WebSocket consumer thin.

It should mainly handle:

```text
connect
disconnect
receive event
validate event
call service
broadcast result
```

Business logic such as saving messages should live in services.

Recommended:

```python
message = await create_message(
    conversation=conversation,
    sender=user,
    content=content,
)
```

Avoid putting all database/business logic directly into a massive `consumers.py`.

---

# 31. Suggested Service Layer

Possible functions:

```python
get_user_conversation(...)
ensure_conversation_member(...)
get_or_create_listing_conversation(...)
create_message(...)
mark_conversation_read(...)
get_conversation_messages(...)
get_user_conversations(...)
```

This allows both REST APIs and WebSockets to reuse the same logic.

---

# 32. Transactions

Conversation creation should be atomic.

Use:

```python
transaction.atomic()
```

to avoid duplicate conversations/members under concurrent requests.

Where possible, add database-level uniqueness constraints instead of relying only on application logic.

---

# 33. Database Query Efficiency

Always avoid N+1 query problems.

Use:

```python
select_related(...)
prefetch_related(...)
```

for:

- listing
- sender
- memberships
- university

Example conversation list should not perform separate queries for every user's listing/user/message.

Use Django Debug Toolbar during development if available.

---

# 34. Pagination

Never send thousands of messages to the frontend.

Use cursor pagination.

Initial load:

```text
latest 50 messages
```

Scrolling upward:

```text
previous 50
```

Cursor-based pagination is preferred over high-offset pagination.

---

# 35. IDs

Prefer:

- UUID for Conversation
- integer/big integer for Message

Reason:

Conversation IDs are user-visible in URLs and WebSocket routes.

Message IDs benefit from sequential ordering and efficient database indexes.

UUID does NOT replace authorization.

---

# 36. Deployment Architecture

Future production setup:

```text
                         Internet
                            │
                            ▼
                         Nginx
                            │
              ┌─────────────┴──────────────┐
              │                            │
           HTTP/API                    WebSocket
              │                            │
              ▼                            ▼
       Django API workers          ASGI/Channels workers
              │                            │
              └────────────┬───────────────┘
                           │
                  ┌────────┴────────┐
                  │                 │
             PostgreSQL          Redis
                  │
                  ▼
            Object Storage
```

Multiple ASGI workers can be added later:

```text
ASGI Worker 1
ASGI Worker 2
ASGI Worker 3
ASGI Worker 4
       │
       └──── shared Redis channel layer
```

No architecture rewrite should be necessary merely because WebSocket workers increase.

---

# 37. Expected Scale

Potential platform:

```text
5 universities
× 20,000 students
= 100,000 users
```

Example usage:

```text
20,000 daily active users
5,000 simultaneous online users
1,000 actively chatting
```

This architecture is appropriate for that scale when properly deployed and indexed.

Do not introduce Kafka, Cassandra, dedicated message brokers, or microservices unless real production metrics justify them.

---

# 38. Future PostgreSQL Scaling

Do not partition the Message table during the hackathon.

Possible future optimizations:

1. Better indexes
2. Query tuning
3. Read replicas
4. Connection pooling
5. PostgreSQL partitioning
6. Message archival
7. Dedicated messaging service

Only adopt these when needed.

---

# 39. Security Requirements

The coding agent must ensure:

- authenticated WebSockets
- conversation membership checks
- university isolation
- no arbitrary cross-campus messages
- server-side authorization for every REST endpoint
- server-side authorization for every WebSocket connection
- rate limits
- maximum message sizes
- no raw user HTML rendering
- secure production WebSockets (`wss://`)
- secrets stored in environment variables

Never trust:

```text
user_id
university_id
seller_id
conversation membership
```

provided by the frontend without server-side verification.

---

# 40. MVP Scope

Implement now:

```text
✓ Conversation model
✓ ConversationMember model
✓ Message model
✓ Listing-linked conversations
✓ Create/open conversation
✓ Conversation list
✓ Message history
✓ WebSocket connection
✓ Send text message
✓ Receive text message instantly
✓ Read state
✓ Authorization
✓ PostgreSQL persistence
✓ Redis channel layer
```

Do NOT prioritize:

```text
✗ Group chat
✗ Calls
✗ Video calls
✗ Voice notes
✗ Message reactions
✗ GIFs
✗ Stickers
✗ Forwarding
✗ End-to-end encryption
✗ Complex presence
✗ Kafka
✗ Microservices
```

---

# 41. Suggested Implementation Order

## Phase 1 — Models

Implement:

```text
Conversation
ConversationMember
Message
```

Run migrations.

---

## Phase 2 — REST APIs

Implement:

```text
Create conversation
List conversations
Fetch conversation
Fetch paginated messages
Mark as read
```

Test permissions thoroughly.

---

## Phase 3 — Redis

Install/start Redis.

Configure:

```text
channels_redis
```

Confirm Django can connect.

---

## Phase 4 — WebSocket

Create:

```text
routing.py
consumers.py
ASGI configuration
```

Test connecting to a conversation.

---

## Phase 5 — Real-Time Send

Implement:

```text
client message.send
↓
backend validation
↓
database save
↓
group_send
↓
message.new
```

Test between two browsers/accounts.

---

## Phase 6 — Frontend

Frontend should:

1. Fetch initial message history through REST
2. Open WebSocket
3. Append incoming `message.new`
4. Send new messages over WebSocket
5. Reconnect on network interruption
6. Avoid inserting duplicate messages

---

## Phase 7 — Read State

When chat is viewed:

```text
mark latest visible message as read
```

Update membership.

Broadcast optional read event.

---

## Phase 8 — Hardening

Add:

```text
rate limiting
input validation
error handling
authorization tests
database indexes
```

---

# 42. Frontend Connection Strategy

When user opens chat:

```text
GET message history
↓
Render existing messages
↓
Connect WebSocket
↓
Listen for message.new
```

Do not depend solely on WebSockets for historical messages.

REST handles history.

WebSocket handles real-time changes.

---

# 43. Reconnection Strategy

Browser/mobile networks disconnect.

Frontend must automatically reconnect.

Recommended:

```text
1 second
2 seconds
4 seconds
8 seconds
...
```

with maximum backoff.

After reconnect:

```text
fetch messages newer than last known message
```

This prevents lost UI updates while disconnected.

Messages remain safe because PostgreSQL is authoritative.

---

# 44. Duplicate Message Prevention

The frontend should de-duplicate using server message IDs.

Future improvement:

Client generates:

```text
client_message_id = UUID
```

and server stores it with a uniqueness constraint per sender.

This supports retry-safe sending.

Not mandatory for first MVP, but recommended before serious production traffic.

---

# 45. Important Marketplace UX

Every listing-created conversation should retain listing context.

Chat header could show:

```text
Casio fx-991EX
₹700

Seller: Student Name
```

This is much more useful than generic direct messaging.

If the listing is deleted/sold, keep the conversation but show listing state:

```text
Sold
Removed
Unavailable
```

Do not delete conversation history automatically when a listing becomes inactive.

---

# 46. Recommended App Structure

Suggested:

```text
backend/
├── config/
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py
│
├── users/
├── universities/
├── marketplace/
│
└── chat/
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── consumers.py
    ├── models.py
    ├── permissions.py
    ├── routing.py
    ├── serializers.py
    ├── services.py
    ├── urls.py
    ├── views.py
    ├── tests/
    │   ├── test_models.py
    │   ├── test_permissions.py
    │   ├── test_api.py
    │   └── test_websockets.py
    └── migrations/
```

Adapt to the existing codebase rather than blindly restructuring the whole project.

---

# 47. Testing Requirements

At minimum test:

### Authorization

```text
✓ Member can open conversation
✓ Non-member cannot open conversation
✓ Cross-university user cannot access conversation
✓ Anonymous user cannot access conversation
```

### Messages

```text
✓ Valid message saves
✓ Empty message rejected
✓ Oversized message rejected
✓ User cannot send into another conversation
```

### Conversation creation

```text
✓ Buyer can message seller
✓ Seller cannot message themselves through own listing
✓ Duplicate listing conversation is reused
✓ Cross-university listing access rejected
```

### WebSockets

```text
✓ Authorized connection succeeds
✓ Unauthorized connection closes
✓ Sent message persists
✓ Both clients receive broadcast
```

---

# 48. Definition of Done for Hackathon

Messaging MVP is done when:

1. Two authenticated users exist
2. User A opens User B's listing
3. User A clicks **Message Seller**
4. Conversation is created/reused
5. Both users can open the chat
6. User A sends a message
7. User B receives it without refreshing
8. Refreshing either page still shows message history
9. Unauthorized users cannot access the conversation
10. Messages are stored in PostgreSQL
11. Redis is used only for real-time infrastructure
12. Basic read state works

Anything beyond this is secondary.

---

# 49. Critical Rules for the Coding Agent

1. **Inspect the existing Django models before changing architecture.**
2. Reuse existing User, University, and Listing models.
3. Do not duplicate existing abstractions.
4. Avoid unnecessary dependencies.
5. PostgreSQL is the source of truth.
6. Redis is transient.
7. Every message operation requires authorization.
8. Never trust user or university IDs from the frontend.
9. Use pagination.
10. Use database indexes.
11. Keep WebSocket consumers thin.
12. Put business logic in services.
13. Build text messaging first.
14. Do not add Kafka or microservices.
15. Do not sacrifice the existing marketplace functionality while adding chat.
16. Write migrations safely.
17. Add tests for permissions.
18. Prefer maintainable code over hacky demo-only code.

---



---

# Dockerization Requirements

This project is being containerized. The messaging implementation must therefore be designed so that Django, PostgreSQL, Redis, and the ASGI server work correctly both:

- on a developer laptop
- inside Docker Compose
- on another teammate's machine
- on a hackathon presentation machine
- in a future production deployment

Do not assume that `localhost` always points to PostgreSQL or Redis.

Inside Docker, `localhost` means **the current container**.

Use Docker service names for communication between containers.

Example:

```text
web container
    ↓
postgres:5432
redis:6379
```

NOT:

```text
localhost:5432
localhost:6379
```

---

# Recommended Docker Architecture

For the MVP, use Docker Compose with these services:

```text
┌──────────────────────────────┐
│          frontend            │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│         Django/ASGI          │
│      Daphne or Uvicorn       │
└───────┬──────────────┬───────┘
        │              │
        ▼              ▼
┌──────────────┐  ┌──────────────┐
│ PostgreSQL   │  │    Redis     │
│  postgres    │  │    redis     │
└──────────────┘  └──────────────┘
```

Do not split REST and WebSocket servers into separate containers for the hackathon unless the existing architecture already does that.

A single Django ASGI container is simpler and sufficient.

---

# Important ASGI Requirement

Because BunkLoop messaging uses Django Channels/WebSockets, the backend container must run an **ASGI server**.

Do not run production-style messaging using:

```bash
python manage.py runserver
```

as the long-term Docker entrypoint.

Prefer:

```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

or:

```bash
uvicorn config.asgi:application --host 0.0.0.0 --port 8000
```

If the project already uses Gunicorn for standard HTTP, do not blindly replace the deployment architecture without checking what is already configured.

For a simple hackathon setup, running the entire Django app under Daphne/Uvicorn is acceptable.

---

# Bind to 0.0.0.0

Inside Docker, the backend server must bind to:

```text
0.0.0.0
```

NOT:

```text
127.0.0.1
```

Correct:

```bash
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

Incorrect:

```bash
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

Binding to `127.0.0.1` inside the container will prevent access from outside that container.

---

# Docker Compose Example

Adapt service names and paths to the existing project.

Do not overwrite a working Compose file without inspecting it first.

Example:

```yaml
services:
  web:
    build:
      context: .
    command: >
      sh -c "
      python manage.py migrate &&
      daphne -b 0.0.0.0 -p 8000 config.asgi:application
      "
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"
        ]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  postgres_data:
  redis_data:
```

For a hackathon, Redis persistence is not required for message safety because PostgreSQL stores messages.

However, a Redis volume can still be useful for preserving cache/state during container recreation.

---

# Environment Variables

Do not hard-code Docker hostnames, credentials, ports, secrets, or URLs.

Use `.env`.

Recommended values:

```env
DEBUG=True

DJANGO_SECRET_KEY=change-me

POSTGRES_DB=bunkloop
POSTGRES_USER=bunkloop
POSTGRES_PASSWORD=change-me
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379

ALLOWED_HOSTS=localhost,127.0.0.1,192.168.137.1
```

For Docker Compose, `POSTGRES_HOST` should normally equal the PostgreSQL service name:

```text
postgres
```

and:

```text
REDIS_HOST=redis
```

Do not use:

```text
POSTGRES_HOST=localhost
REDIS_HOST=localhost
```

inside the Django container.

---

# Django Database Configuration

Recommended:

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST", "postgres"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
    }
}
```

The coding agent should reuse any existing settings/config library if the project already uses:

```text
django-environ
python-decouple
dj-database-url
```

Do not introduce a second configuration system unnecessarily.

---

# Redis / Channel Layer Configuration

Docker-aware Channels configuration:

```python
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                (REDIS_HOST, REDIS_PORT)
            ],
        },
    },
}
```

Alternatively use:

```env
REDIS_URL=redis://redis:6379/0
```

Then:

```python
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}
```

Using `REDIS_URL` is often cleaner.

---

# Dockerfile Requirements

The Dockerfile must install the Python packages needed for real-time messaging.

At minimum:

```text
Django
djangorestframework
channels
channels-redis
daphne OR uvicorn
psycopg / psycopg2
```

Example:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD [
  "daphne",
  "-b",
  "0.0.0.0",
  "-p",
  "8000",
  "config.asgi:application"
]
```

Adapt Python version and project module name to the actual project.

Do not assume the project is named `config`.

---

# Requirements File

Ensure the real-time dependencies are included in whichever dependency manager the project uses.

For `requirements.txt`:

```text
channels
channels-redis
daphne
```

or Uvicorn if preferred.

If the project uses Poetry, uv, Pipenv, or another tool, modify that instead of adding an unrelated `requirements.txt`.

---

# Do Not Bake .env Into Docker Image

Do not:

```dockerfile
COPY .env /app/.env
```

for production-oriented builds.

The Compose file should inject environment variables at runtime:

```yaml
env_file:
  - .env
```

Also ensure `.env` is listed in:

```text
.gitignore
```

Example safe file to commit:

```text
.env.example
```

---

# .env.example

Create or update:

```env
DEBUG=True

DJANGO_SECRET_KEY=replace-this

POSTGRES_DB=bunkloop
POSTGRES_USER=bunkloop
POSTGRES_PASSWORD=replace-this
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379

ALLOWED_HOSTS=localhost,127.0.0.1
```

Never commit real passwords or secret keys.

---

# Docker Networking

Docker Compose automatically creates a network and provides DNS based on service names.

Therefore:

```text
web → postgres
web → redis
```

works without manually assigning container IP addresses.

Do not hard-code Docker container IPs because they can change.

---

# Host Machine vs Container Addressing

Understand the difference:

From the **host machine**:

```text
Django:
http://localhost:8000
```

From the **Django container**:

```text
PostgreSQL:
postgres:5432

Redis:
redis:6379
```

From another device on the same Wi-Fi/hotspot:

```text
http://<HOST_LAN_IP>:8000
```

Example:

```text
http://192.168.137.1:8000
```

provided the host OS, firewall, Docker port mapping, and hotspot allow it.

---

# Important LAN Demo Configuration

Because the project may be demonstrated across multiple devices on the same hotspot/network, the coding agent must account for LAN access.

Docker Compose should expose:

```yaml
ports:
  - "8000:8000"
```

The ASGI server must bind to:

```text
0.0.0.0
```

Django `ALLOWED_HOSTS` should include:

```text
localhost
127.0.0.1
host machine LAN IP
```

For temporary hackathon testing only, this can be:

```python
ALLOWED_HOSTS = ["*"]
```

but this should not be kept for real production deployment.

---

# CSRF Trusted Origins for LAN Development

If Django forms, admin, session authentication, or CSRF-protected frontend requests are being accessed through a LAN IP, add the relevant origins.

Example:

```python
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://192.168.137.1:8000",
]
```

If the frontend runs separately, include its actual origin instead.

Do not randomly disable CSRF globally to make development easier.

---

# CORS

If the frontend and Django backend run on different origins, configure CORS deliberately.

Example:

```text
frontend:
http://192.168.137.1:3000

backend:
http://192.168.137.1:8000
```

Then configure `django-cors-headers` if already part of the project or needed.

Do not use:

```text
CORS_ALLOW_ALL_ORIGINS=True
```

in production.

Temporary hackathon usage may be acceptable only when clearly marked as development configuration.

---

# WebSocket URL Handling

Do not hard-code:

```javascript
ws://localhost:8000
```

because that fails on another student's phone/laptop.

The frontend should derive the hostname dynamically.

Example:

```javascript
const protocol =
  window.location.protocol === "https:"
    ? "wss"
    : "ws";

const socket = new WebSocket(
  `${protocol}://${window.location.host}/ws/chat/${conversationId}/`
);
```

If frontend and backend use different ports/hosts, use an environment variable:

```env
VITE_WS_BASE_URL=ws://192.168.137.1:8000
```

or equivalent framework configuration.

The coding agent should inspect the frontend stack first.

---

# Reverse Proxy and WebSockets

If Nginx is later placed in front of Django, WebSocket upgrade headers are required.

Example:

```nginx
location /ws/ {
    proxy_pass http://web:8000;

    proxy_http_version 1.1;

    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

Normal HTTP:

```nginx
location / {
    proxy_pass http://web:8000;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

Missing upgrade headers commonly causes WebSockets to fail while normal Django pages continue working.

---

# HTTP vs HTTPS

During LAN hackathon development:

```text
http://
ws://
```

is acceptable.

Production should use:

```text
https://
wss://
```

If the frontend is loaded over HTTPS, browsers will generally block insecure:

```text
ws://
```

Use:

```text
wss://
```

in production.

---

# Container Startup Ordering

`depends_on` by itself does not always mean that PostgreSQL is fully ready to accept connections.

Use health checks where possible.

Example:

```yaml
depends_on:
  postgres:
    condition: service_healthy
  redis:
    condition: service_healthy
```

Still write startup logic defensively.

Do not rely on arbitrary:

```bash
sleep 10
```

unless absolutely necessary for a temporary hackathon fix.

---

# Database Migrations in Docker

The agent must ensure migrations are applied.

Possible hackathon command:

```yaml
command: >
  sh -c "
  python manage.py migrate &&
  daphne -b 0.0.0.0 -p 8000 config.asgi:application
  "
```

For a serious production deployment, migrations are better run as a separate release/deployment step to avoid multiple replicas simultaneously trying to migrate.

For the current MVP, automatic migration at startup is acceptable if there is only one backend container.

---

# Persistent PostgreSQL Data

Use a Docker volume:

```yaml
volumes:
  postgres_data:
```

and:

```yaml
postgres:
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

Without a volume, recreating the PostgreSQL container could destroy marketplace and chat data.

This is critical.

---

# Redis Data Durability

Messages must not depend on Redis persistence.

Redis may be completely emptied and the messaging history should still load correctly from PostgreSQL.

This should be testable:

```text
1. Send messages
2. Restart/flush Redis
3. Open conversation
4. History must still exist
```

Temporary things may disappear:

```text
typing state
presence
cached unread count
WebSocket subscriptions
```

That is acceptable.

---

# Development Volume Mounts

For development:

```yaml
web:
  volumes:
    - .:/app
```

is useful because code updates become available without rebuilding every time.

For production, source-code bind mounts are usually not desired.

The coding agent should distinguish:

```text
docker-compose.yml
docker-compose.dev.yml
docker-compose.prod.yml
```

only if the existing project complexity warrants it.

Do not create multiple Compose files merely for architectural aesthetics during a hackathon.

---

# Static Files

If Django serves admin/static assets, the Dockerized deployment must account for them.

Potential future flow:

```bash
python manage.py collectstatic --noinput
```

with either:

- WhiteNoise
- Nginx static serving
- CDN/object storage

This is not directly part of chat, but the agent should avoid breaking existing static handling.

---

# Media Files

If BunkLoop currently uses local filesystem uploads:

```text
/media/
```

inside Docker, they can disappear when containers are recreated unless a volume is mounted.

For temporary development:

```yaml
volumes:
  media_data:
```

Eventually move chat/listing images to object storage.

Do not rely on ephemeral container filesystem storage for persistent user uploads.

---

# Docker Health Checks

Add basic checks where practical.

PostgreSQL:

```yaml
healthcheck:
  test:
    [
      "CMD-SHELL",
      "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"
    ]
```

Redis:

```yaml
healthcheck:
  test: ["CMD", "redis-cli", "ping"]
```

Backend health endpoint can later be:

```text
GET /health/
```

returning:

```json
{
  "status": "ok"
}
```

A deeper health check may verify PostgreSQL and Redis separately.

---

# Graceful WebSocket Failure

The frontend must handle Redis/backend/container restarts.

Expected behavior:

```text
WebSocket disconnects
        ↓
UI shows temporary reconnect state
        ↓
frontend reconnects
        ↓
fetch messages newer than last known message
        ↓
normal operation resumes
```

Do not assume WebSocket connections stay alive forever.

This is especially important during hackathon development because containers will be restarted frequently.

---

# Docker Restart Policies

For a local hackathon setup, optional:

```yaml
restart: unless-stopped
```

for:

```text
web
postgres
redis
```

This is useful but not mandatory.

Do not use restart loops to hide an application crash.

---

# Logging

Docker logs must be useful.

Ensure Python logs go to stdout/stderr rather than only to files inside containers.

Useful command:

```bash
docker compose logs -f web
```

Also:

```bash
docker compose logs -f redis
docker compose logs -f postgres
```

The coding agent should preserve enough logging to diagnose:

```text
database connection failures
Redis failures
WebSocket authorization failures
WebSocket disconnects
message save errors
```

Do not log user message contents unnecessarily in production.

---

# Docker Debugging Commands

Useful during development:

```bash
docker compose ps
```

```bash
docker compose logs -f
```

```bash
docker compose logs -f web
```

```bash
docker compose exec web python manage.py shell
```

```bash
docker compose exec web python manage.py migrate
```

```bash
docker compose exec web python manage.py showmigrations
```

```bash
docker compose exec redis redis-cli ping
```

Expected:

```text
PONG
```

PostgreSQL check:

```bash
docker compose exec postgres pg_isready
```

---

# Docker-Specific Testing Checklist

Before calling messaging complete, test:

```text
✓ docker compose up --build works on a clean machine
✓ PostgreSQL becomes healthy
✓ Redis becomes healthy
✓ Django connects using Docker service names
✓ migrations run successfully
✓ normal HTTP page/API works
✓ WebSocket connection succeeds
✓ messages are received in real time
✓ messages survive Redis restart
✓ messages survive Django container restart
✓ messages survive PostgreSQL container restart
✓ PostgreSQL data survives container recreation
✓ unauthorized WebSocket access still fails
✓ another device on the same network can load the app
✓ another device can establish WebSocket connection
```

---

# Clean-Machine Requirement

Because the hackathon requires the project to run on different machines, the repo should allow a teammate/judge to do approximately:

```bash
git clone <repo>
cd <repo>
cp .env.example .env
docker compose up --build
```

with minimal additional setup.

Document any required initialization.

Avoid undocumented dependencies such as:

```text
Redis installed manually on host
PostgreSQL installed manually on host
local Python packages outside Docker
hard-coded absolute Windows paths
hard-coded developer IP addresses
hard-coded database passwords
```

The point of Docker is that these dependencies should be reproducible.

---

# Windows / Linux Compatibility

Avoid Docker configuration that depends on one developer's absolute path.

Bad:

```yaml
volumes:
  - C:\Users\SomeUser\Desktop\bunkloop:/app
```

Prefer:

```yaml
volumes:
  - .:/app
```

Also use LF-compatible scripts where possible.

If using shell entrypoint scripts:

```text
entrypoint.sh
```

ensure they work inside the Linux container.

Windows CRLF line endings can cause errors such as:

```text
/bin/sh^M: bad interpreter
```

Configure Git/editor accordingly if shell scripts are added.

---

# Do Not Use Host Network Mode

Avoid:

```yaml
network_mode: host
```

for this project unless there is a very specific reason.

It behaves differently across operating systems and makes portability worse.

Use normal Compose port mappings instead.

---

# Secrets and Git

Ensure `.gitignore` includes:

```text
.env
.env.local
*.pem
*.key
```

Do commit:

```text
.env.example
```

Do not commit:

```text
actual Django secret key
PostgreSQL production password
Redis cloud credentials
API keys
payment credentials
```

---

# Special Instruction for the Coding Agent

Before modifying Docker files:

1. Inspect the existing:
   - `Dockerfile`
   - `docker-compose.yml`
   - `.env`
   - `.env.example`
   - `requirements.txt` / dependency manager
   - Django settings
   - `asgi.py`

2. Preserve existing working services.

3. Add Redis only if it does not already exist.

4. Reuse the existing PostgreSQL service.

5. Do not create a second database container.

6. Do not create duplicate environment variables under different names unless necessary.

7. Make Django use the actual Compose service names.

8. Ensure the backend binds to `0.0.0.0`.

9. Ensure port `8000` is exposed/mapped if that is the project's selected port.

10. Ensure WebSocket routes pass through the same exposed backend.

11. Do not replace the project's frontend Docker setup unless messaging requires a specific change.

12. Make changes incrementally and verify `docker compose up --build` after each major step.

---

# Recommended Docker Implementation Order

## Docker Phase 1 — Inspect Existing Setup

Determine:

```text
existing services
service names
backend container name
PostgreSQL service name
current startup command
current exposed ports
environment configuration style
```

Do not assume names such as `web`, `postgres`, or `redis`.

---

## Docker Phase 2 — Add Redis

If absent:

```yaml
redis:
  image: redis:7-alpine
```

Configure a health check.

---

## Docker Phase 3 — Add Python Dependencies

Install:

```text
channels
channels-redis
daphne OR uvicorn
```

Rebuild image:

```bash
docker compose build
```

---

## Docker Phase 4 — Configure Channels

Use the Redis Compose hostname.

Example:

```text
redis://redis:6379/0
```

---

## Docker Phase 5 — Switch to ASGI

Ensure container startup launches:

```text
config.asgi:application
```

through Daphne or Uvicorn.

Verify normal REST APIs still work.

---

## Docker Phase 6 — Test WebSockets

Open two browser sessions and verify:

```text
browser A
    ↓
containerized Django
    ↓
containerized Redis
    ↓
browser B
```

---

## Docker Phase 7 — LAN Test

From another device:

```text
http://HOST_LAN_IP:8000
```

Verify:

```text
page load
login
REST API
WebSocket connection
message send
message receive
```

---

# Final Docker-Aware Architecture

```text
                    Device / Browser
                           │
              HTTP + WebSocket
                           │
                           ▼
                   Host machine :8000
                           │
                    Docker mapping
                           │
                           ▼
                ┌────────────────────┐
                │ Django ASGI        │
                │ Daphne / Uvicorn   │
                └───────┬────────────┘
                        │
              Docker Compose network
                 ┌──────┴──────┐
                 ▼             ▼
           ┌──────────┐   ┌──────────┐
           │ postgres │   │  redis   │
           │  :5432   │   │  :6379  │
           └──────────┘   └──────────┘
                 │
         persistent volume
```

The implementation must remain portable.

A fresh machine should not need locally installed PostgreSQL or Redis.

Docker Compose should provide the runtime dependencies required for the messaging system.



# 50. Final Target Architecture

```text
                         BUNKLOOP

                 ┌─────────────────────┐
                 │      Frontend       │
                 └──────────┬──────────┘
                            │
                  ┌─────────┴─────────┐
                  │                   │
                REST              WebSocket
                  │                   │
                  ▼                   ▼
             Django DRF       Django Channels
                  │                   │
                  └─────────┬─────────┘
                            │
                  ┌─────────┴─────────┐
                  │                   │
             PostgreSQL            Redis
           Durable storage    Realtime/cache
                  │
                  ▼
            Object Storage
              (future)
```

The goal is not to build the most sophisticated messaging system possible.

The goal is to build a **secure, maintainable marketplace messaging system that works now and can scale to roughly 100,000 students without requiring a rewrite**.
