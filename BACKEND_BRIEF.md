# Bunkloop Backend — Brief Overview (UTF-8)

> Django 5.2.17 + PostgreSQL (prod) / SQLite (dev) + Redis (Channels) + Daphne + DRF + WhiteNoise

> **PDF-ready with infographics** — all diagrams below use Mermaid (supported by GitHub, VS Code, md-to-pdf, etc.). Export this `.md` to PDF via `md-to-pdf`, `pandoc`, or VS Code “Markdown PDF”.

```mermaid
%% System at a glance — infographic for PDF cover
graph TB
    A[Student Browser<br/>JS: auth_otp.js, chat.js] --> B[Nginx / Daphne<br/>0.0.0.0:8000]
    B --> C[Django + DRF<br/>bunkloop/views, api_views, serializers]
    B --> D[Channels<br/>ChatConsumer<br/>ws/chat/<id>/]
    C --> E[(PostgreSQL<br/>source of truth<br/>User, Item, Conversation, Message, Order)]
    D --> F[(Redis<br/>channel layer, cache<br/>OTP challenge, rate limit)]
    C --> G[sendotp.email<br/>Bearer otp_email_key]
    style A fill:#fff0eb,stroke:#e75b43
    style E fill:#d9eee3,stroke:#1a6b46
    style F fill:#dce9f2,stroke:#252522
```

## 1. Project Layout
```
Entropy_temp/
├── entropy/                 # Django project (settings, urls, wsgi, asgi)
│   ├── settings.py          # 12-factor env-driven (DEBUG, SECRET_KEY, DB, REDIS, EMAIL, OTP, CHAT)
│   ├── urls.py              # /health/, /api/, /, /admin/
│   └── asgi.py              # ProtocolTypeRouter {http: Django, websocket: AuthMiddlewareStack(URLRouter(chat))}
├── bunkloop/                # Main app
│   ├── models.py            # University, ProfileImage, Hostel, User, Item, ItemImage, Conversation, ConversationMember, Message, Order
│   ├── forms.py             # UserProfileForm, ItemForm, validate_student_email (University.domains + .edu/.ac. + MX)
│   ├── views.py             # auth, home, item, conversation, order, university, health, terms
│   ├── services.py          # get_or_create_listing_conversation, create_message, mark_read, get_unread_count (atomic, university isolation)
│   ├── email_otp.py         # sendotp.email service (Bearer otp_email_key, never stored OTP, challenge_id in cache)
│   ├── auth_otp_views.py    # POST /api/auth/send-email-otp/, POST /verify-email-otp/ (cache challenge, session verified_signup_email)
│   ├── api_views.py         # DRF chat REST (CursorPagination -updated_at/-created_at)
│   ├── serializers.py       # Conversation/Message/Item brief
│   ├── consumers.py         # ChatConsumer (AuthMiddlewareStack, membership 4403, group chat_<uuid>, rate-limit 30/min, Redis)
│   ├── routing.py           # ws/chat/<id>/
│   ├── context_processors.py# nav_unread_count / nav_pending_orders
│   ├── admin.py             # University (domains_text), User, Item etc.
│   └── migrations/          # 0001_initial + 0007_ensure_identity + 0008_conversation/order + 0009_university_domains + 0010_seed + 0011_member/listing
├── templates/bunkloop/      # base, home, login, signup, verify_email, profile, item_*, conversations, orders, universities, terms, 404
├── static/css/ + js/        # app.css + per-page UTF-8 (pages/*.css/js), chat.js, auth_otp.js, cookie_banner.js
├── Dockerfile               # python:3.12-slim, daphne -b 0.0.0.0 -p 8000
├── docker-compose.yml       # postgres:16 + redis:7 + web (migrate + collectstatic + daphne)
└── manage.py, requirements.txt, .env.example
```

## 2. Core Models

```mermaid
erDiagram
    University ||--o{ Hostel : has
    University ||--o{ User : enrolls
    University ||--o{ Conversation : isolates
    User ||--o{ Item : lists
    User ||--o{ Conversation : buys
    User ||--o{ Conversation : sells
    Item ||--o{ ItemImage : has
    Item ||--o{ Conversation : listing
    Conversation ||--o{ ConversationMember : has
    Conversation ||--o{ Message : contains
    User ||--o{ Message : sends
    User ||--o{ ConversationMember : joins
    Item ||--o{ Order : ordered
    User ||--o{ Order : buys
    User ||--o{ Order : sells

    University {
        string name PK
        json domains
    }
    User {
        string full_name
        string registration_id UK
        string email UK
        bool email_verified
    }
    Item {
        string title
        decimal price
        string listing_type
    }
    Conversation {
        int id PK
        uuid uuid UK
        int university_FK
    }
    Message {
        int id PK
        string message_type
        text content
    }
```

- **University** `name, domains:JSONField[list]` — `is_domain_allowed()` (exact/subdomain), `get_domains_display()`, `clean()` normalizes.
- **User** `AbstractUser` + `full_name, registration_id (unique, to_field for Item), university(FK), profile_image, contact_number, student_type, hostel(FK), email(unique), gender, identity_photo, email_verified`. `clean()` enforces hosteler→hostel.
- **Item** `title, description, registration_id(FK User.to_field), category(FK), price, listing_type, condition, created_at`; **ItemImage** `item(FK), image` (max 4, `full_clean` in `save`).
- **Conversation** `uuid(UUID, null), university(FK), item(FK), listing(FK SET_NULL), buyer/seller(FK User), created/updated_at` (unique_together `item+buyer`); `save()` auto-fills `university/listing`.
- **ConversationMember** `conversation(FK), user(FK), last_read_message(FK Message), muted, joined_at` + `UniqueConstraint(conversation,user)`.
- **Message** `conversation(FK), sender(FK), body/content, message_type(TEXT/IMAGE/SYSTEM), media_url, created_at, edited_at, deleted_at, is_read` + indexes `(conversation,-created_at)`, `(sender,-created_at)`.
- **Order** `item(FK PROTECT), buyer/seller(FK), amount, listing_type, status(pending→paid→confirmed→shipped→delivered→completed/cancelled), payment_status, payment_reference, provider, timestamps`.

| Entity | Key Fields | Relations | Notes |
|---|---|---|---|
| University | `domains` JSON list | 1—N Hostel, User, Conversation | `thapar.edu` allowlist |
| User | `registration_id` unique | N—1 University | `to_field` for Item |
| Item | `price, listing_type` | N—1 Category, 1—N Images | Max 4 images |
| Conversation | `uuid, university` | N—1 Item, 1—N Members/Messages | `item+buyer` unique |
| Message | `content, message_type` | N—1 Conversation | Indexed |
| Order | `status, payment_status` | N—1 Item | `pending→completed` |

## 3. Auth & OTP

```mermaid
sequenceDiagram
    participant U as Student Browser<br/>signup.html + auth_otp.js
    participant D as Django<br/>/api/auth/*
    participant S as sendotp.email<br/>Bearer otp_email_key
    participant C as Cache (Redis)<br/>email_otp:signup:<email>
    participant DB as PostgreSQL<br/>User

    U->>D: POST /api/auth/send-email-otp/ {email}
    D->>D: validate_student_email (denied, academic, MX, University.domains)
    D->>S: POST /v1/send {email, purpose:signup}
    S-->>D: {ok:true, id:otp_..., expiresAt}
    D->>C: SET email_otp:signup:<email> {challenge_id, expires_at} 600s
    D-->>U: 200 {success:true, message:"Verification code sent."}
    U->>U: Show OTP input (link stays same)
    U->>D: POST /api/auth/verify-email-otp/ {email, code}
    D->>C: GET challenge_id
    D->>S: POST /v1/verify {email, id, code}
    S-->>D: {valid:true}
    D->>D: session["verified_signup_email"]=email
    D-->>U: 200 {verified:true}
    U->>D: POST /signup/ (full form, email==verified)
    D->>DB: CREATE User (email_verified=True)
    D-->>U: 302 /login/
```

- **Signup** `UserProfileForm` validates `email` via `validate_student_email` (denied list env `ALLOWED_EMAIL_DENIED_DOMAINS`, academic suffixes `ALLOWED_ACADEMIC_SUFFIXES`, University `domains` allowlist, `dns MX`), `university.domains` strict check in `clean()`, `identity_photo` (Pillow).
- **OTP** `email_otp.py: send_email_otp() / verify_email_otp()` → `POST https://api.sendotp.email/v1/send|verify` with `Authorization: Bearer $otp_email_key` (never frontend, never logged). Fallback to local random `6`-digit (`OTP_LENGTH`) when `otp_email_key` missing or `test` in argv (fast, <10s tests). Challenge `{id}` stored in `cache` (`email_otp:signup:<email>`, 600s `OTP_TTL_SECONDS`, Redis or LocMem), **never OTP code**. Verification sets `session["verified_signup_email"]`; signup checks it before `User` creation (`email_verified=True`). Resend cooldown `429` handled.
- **API** `POST /api/auth/send-email-otp/ {email}` → `{success, expires_at, retry_after}`; `POST /verify-email-otp/ {email,code}` → `{verified, message}` + session.

| Step | WSGI Sends | JS Breaks Down | HTML Update |
|---|---|---|---|
| Send | `200 {success:true}` | `data.message` → `setStatus` | `Verify` input shown, no URL change |
| Verify | `200 {verified:true}` | `data.verified` → `emailInput.readOnly=true` | `Complete registration` enabled |
| Fail | `400 {error, reason}` | `data.reason` → `wrong_code` mapping | Inline `form-errors` |

## 4. Views & URLs
- `require_login` (session `user_registration_id`) guards `profile, home, my_items, item_create, item_detail, item_delete, conversation_*, order_*, university_list`.
- `login_view`/`signup` redirect `GET` when already authed (`signup` allows no-university to complete profile, breaks loop), `POST` flushes for account switch (tests). `verify_email` handles both `OTP_STORE` (fallback) and `cache` (`sendotp`).
- `home` filters `Q(title|description|category__name icontains q)` + `category`, annotates `nav_unread_count/nav_pending_orders`; `item_delete` (owner only, `orders.exists()` → `PROTECT` error).
- `conversation_list/detail, start_conversation` use `services` (atomic, university isolation, `ConversationMember` auto-create). `order_create` mock `succeeded` + `MOCK-{pk}-…`, `order_update_status` role-restricted transitions.
- `health_check` (`/health/`) `SELECT 1` → `{"status":"ok"}`.
- `terms_view` (`/terms/`, `/tnd/`), `university_list`, `custom_404` (`handler404`).

## 5. Messaging (Real-time)

```mermaid
sequenceDiagram
    participant A as Buyer Browser<br/>chat.js
    participant W as Django Channels<br/>ChatConsumer ws/chat/<id>/
    participant P as PostgreSQL<br/>Message
    participant R as Redis<br/>chat_<uuid>

    A->>W: WebSocket connect (AuthMiddlewareStack, 4401/4403)
    W->>W: is_member? university?
    W->>R: group_add chat_<uuid>
    A->>W: {"type":"message.send","content":"Hi"}
    W->>W: validate empty/5000, rate 30/min
    W->>P: INSERT Message (content, body, message_type)
    P-->>W: id, created_at
    W->>R: group_send message.new
    R-->>A: message.new (buyer)
    R-->>B as Seller Browser: message.new
    A->>W: typing.start (Redis only, not DB)
    Note over W,R: Link stays /messages/<id>/ — JSON via WSGI, JS appends bubble
```

- **REST** `/api/chat/conversations/ (POST {listing_id})`, `GET /api/chat/conversations/`, `GET /api/chat/conversations/<uuid|pk>/`, `GET .../messages/?limit=50&before=<id>`, `POST .../read/` — DRF `SessionAuthentication`, `IsAuthenticated`, `CursorPagination` (`-updated_at/-created_at`), university isolation via services.
- **WebSocket** `ws/chat/<id>/` `ChatConsumer` (`AuthMiddlewareStack`, membership `4403`, university check, `group_add f"chat_{uuid|pk}"`, `receive` `message.send` → `validate (empty/5000) → rate limit 30/min via cache → create_message → group_send message.new`, `typing` relay, `message.read`). Frontend `chat.js` fetches history via `GET .../messages/` (WSI JSON, JS breaks down, no `pushState` — link stays `/messages/<id>/`), sends via `WS` (fallback `POST .../messages/` via `fetch`), dedup by `data-message-id`, reconnect backoff 1/2/4/8s.
- **Services** keep consumer thin; `transaction.atomic()` prevents duplicate conversations.

```mermaid
graph LR
    subgraph REST [REST - History]
        A1[GET /api/.../messages/?limit=50] --> B1[Postgres<br/>indexed]
        B1 --> C1[JSON<br/>id, content, sender]
        C1 --> D1[JS: appendMessage<br/>no URL change]
    end
    subgraph WS [WebSocket - Live]
        A2[message.send<br/>JSON] --> B2[Validate + Insert]
        B2 --> C2[Redis group_send]
        C2 --> D2[message.new<br/>JS breaks down]
    end
```

## 6. Settings & Env (12-factor, no hard-code)
- `SECRET_KEY` fail-closed when `!DEBUG`, `ALLOWED_HOSTS` `*` in `DEBUG` + dynamic LAN IP via `8.8.8.8` trick (env `LAN_DISCOVERY_IP`), `CSRF_TRUSTED_ORIGINS` env, `TIME_ZONE='Asia/Kolkata'` (was `UTC`), `USE_TZ=True`.
- `DB` `DB_ENGINE/NAME/USER/PASSWORD/HOST/PORT` → `postgres` (prod) / `sqlite` (dev) + `TEST` `test_bunkloop_db`/` :memory:`; `REDIS_HOST/PORT/URL` → `channels_redis` (Docker `redis`, dev `127.0.0.1` → `InMemory` if no Redis/test), `CACHES` `RedisCache`/`LocMem`.
- `EMAIL_BACKEND` `console` (dev) / SMTP env, `DEFAULT_FROM_EMAIL` env, `OTP_*`, `CHAT_*`, `ALLOWED_EMAIL_*` all env-driven with safe defaults.
- `STATIC_URL/MEDIA_URL`, `WhiteNoise`, `daphne` in `INSTALLED_APPS` first, `ASGI_APPLICATION`.

## 7. Frontend
- `base.html` (`meta charset utf-8`, `topbar` with Messages/Orders badges via `context_processors`, `progress-bar` + `cookie-banner` (`localStorage` Accept → 1yr, Ask later → session, only on `/`)).
- `home.html` toolbar `GET ?q=&category=` (preserves `q`), `filter-chips` `overflow-x:auto` hidden bar but scroll, `listing-grid` responsive 3→2→1.
- `item_detail.html` (Contact Seller card + `Message Seller`/`Buy` only for non-owner, `Remove` for owner).
- `conversation_detail.html` (chat-card, status, `Load older` via JS `?before` without URL change).

## 8. Docker & Deploy

```mermaid
graph TB
    Internet --> Nginx
    Nginx --> Daphne[Daphne 0.0.0.0:8000<br/>entropy.asgi]
    Daphne --> Django[Django + DRF]
    Django --> PG[(PostgreSQL<br/>postgres:16)]
    Django --> RD[(Redis<br/>redis:7)]
    Daphne --> RD
    Django --> S3[(S3/R2<br/>future media)]

    subgraph Docker
        Daphne
        PG
        RD
    end
    style Daphne fill:#fff0eb,stroke:#e75b43
```

- `Dockerfile` `python:3.12-slim` `pip install -r requirements.txt` `collectstatic` `CMD ["daphne","-b","0.0.0.0","-p","8000","entropy.asgi:application"]` `HEALTHCHECK /health/`.
- `docker-compose.yml` `postgres:16-alpine` + `redis:7-alpine` + `web` (`depends_on healthy`, `env_file/.env` `otp_email_key`, `REDIS_HOST=redis`, `DB_HOST=db`, `daphne`).
- Run: `python manage.py runserver 0.0.0.0:8000` (or `docker compose up --build`), peer at `http://192.168.137.36:8000/` (or `LAN_IP:8000`), health `curl http://.../health/`.

| Service | Image | Env Must |
|---|---|---|
| `web` | `bunkloop` (Daphne) | `DJANGO_SECRET_KEY`, `DB_PASSWORD`, `otp_email_key` |
| `db` | `postgres:16-alpine` | `DB_PASSWORD` |
| `redis` | `redis:7-alpine` | — |
```

## 9. Tests
- `bunkloop/tests.py` 9 tests: profile, item limits, routes, signup reject gmail, signup OTP → verify (fallback), messaging start/isolated, order lifecycle `pending→paid→confirmed→shipped→delivered→completed`, health.
- OTP mocked via `patch('bunkloop.email_otp.requests.post')` or `test` fallback (no network), `chat` mocked not needed (InMemory).
- Run: `python manage.py test bunkloop.tests` or `USE_INMEMORY_CHANNEL_LAYER=1`.

— Brief end —
