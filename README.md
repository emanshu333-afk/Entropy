# Bunkloop – PG Sharing Marketplace

## Overview
This project is a Django-based campus marketplace for students to list, browse, and buy or rent items within the same university community. The app currently supports user sign-up, profile creation, item posting, item browsing, and item detail viewing.
## Database used
We have implemented the use of postgres sql to manage the project at large scale across campuses, .env.example file has been provided where the required values can be filled and a migration can be run to test the project on another machine with new data.

## What is already done (2026-08-29)
- Student registration and login flow with university and hostel-based profiles — **ProgrammingError fixed** (`identity_photo`/`email_verified` schema sync + closed-file OTP fix)
- Profile image selection and hostel validation rules
- Item listing creation with title, category, price, listing type, condition, and photo upload support (max 4)
- Marketplace home screen showing listings filtered by the logged-in user’s university
- Personal “My items” view for the seller
- Item detail page with item metadata, seller contact, gallery, and **Message Seller / Buy-Rent Now** actions
- Selling/renting listing types with price handling
- Postgres integration + **Dockerized** (`Dockerfile` + `docker-compose.yml` with postgres:16, gunicorn, WhiteNoise, `/health/` probe)
- **Buyer-seller messaging** — `Conversation`/`Message` models, `/messages/` list & `/messages/<id>/` thread, unread counts, participant-only guard
- **Order & checkout** — `Order` model (`pending→paid→confirmed→shipped→delivered→completed` + `cancelled`), mock payment (`succeeded`) ready for Razorpay/Stripe via env, `/orders/` & `/orders/<id>/` with role-restricted status updates
- Health check `GET /health/` for container probes; prod-ready settings (`DJANGO_DEBUG`, `SECURE_*`, email/payment env)
- Tests: 9/9 passing (postgres & sqlite)

## What is pending / being polished
- Frontend polish: CSS animations, toast/spinner UX
- Real payment webhook verification (replace mock `succeeded` with Razorpay/Stripe signature)
- Production S3/media storage + SSL + cloud deploy
- Security hardening: rate limiting, CAPTCHA, CSP
- Advanced: 2FA, social login, password reset
