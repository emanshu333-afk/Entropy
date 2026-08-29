# Bunkloop Implementation Plan

## Status
This document is a planning-only blueprint for the next implementation phase. It does not change application code or database state yet. The goal is to define the exact backlog, architecture, sequence, and quality gates to move the project from its current MVP state to a production-ready student marketplace.

## Current project baseline
The application already supports:
- Student sign-up and login
- Profile creation with university, hostel, gender, and image handling
- Item listing creation with title, category, price, condition, listing type, and media upload
- University-scoped marketplace browsing and seller dashboard
- Item detail page and user-specific item management

The remaining work is concentrated in four priority areas:
1. User experience and interface refinement
2. Buyer-seller communication and order lifecycle
3. Secure payment and checkout flow
4. Deployment readiness and production configuration

## Updated requirements from review
The following requirements are now part of the approved scope and must be reflected in the implementation sequence:
- Add sufficient spacing between icons and key interface elements to improve readability and usability.
- Redesign the login and sign-up experience as a dynamic, interactive page with smoother transitions and better flow.
- Add student email verification before account creation is allowed.
- Validate that the email domain is a real, active student or university domain before proceeding.
- Check that the email address appears to be a valid mailbox, not a disposable or invalid address.
- Send a one-time password (OTP) to the verified student email.
- Only complete account creation after OTP verification succeeds.
- Require a real camera-captured profile photo during registration/unique ID verification.
- Ensure the uploaded photo is taken from a live camera device rather than a gallery upload.
- Add a verification step to ensure the submitted photo and registration details align with the student's provided information.
- Document the photo verification as a trust layer for registration and identity validation.

These requirements are not optional and should be treated as part of the product security and onboarding process.

---

## Implementation strategy
The work will be executed in a controlled sequence so each major feature is validated before we move to the next one. This reduces churn and prevents the app from reaching a half-finished commerce state.

### Phase 0: Planning and dependency lock
- Confirm the final product scope and feature priority order.
- Lock the data model for chat, orders, payments, and delivery status.
- Decide the payment provider and environment configuration strategy.
- Define the testing and deployment checklist before code changes begin.

### Phase 1: UX/UI improvement for the MVP
- Improve landing flows, authentication screens, profile screens, and item forms.
- Add clearer spacing between icons, fields, and action buttons across the app.
- Redesign the login and sign-up screens as a dynamic page experience with stronger visual hierarchy and smoother motion states.
- Standardize spacing, typography, card layouts, and mobile-first interactions.
- Ensure seller and buyer actions are visually obvious and easy to complete.
- Align the frontend with the actual backend data model and validation rules.

### Phase 2: Identity, email verification, and onboarding security
- Add domain validation for student and university email addresses before sending OTPs.
- Integrate a real mailbox validation step to reduce fake, disposable, or mistyped addresses.
- Implement a 6-digit OTP delivery flow through email.
- Restrict account creation to successfully verified email ownership.
- Add registration photo capture using the device camera instead of allowing only file uploads from the gallery.
- Store the captured identity image and perform a verification check against the student profile details.
- Add proper error messaging and retry logic for failed or expired verification attempts.

### Phase 3: Messaging system
- Add private conversations between buyer and seller.
- Store persistent messages per listing and user pair.
- Add unread counts or basic notification status.
- Integrate communication into the item detail and order flow.

### Phase 4: Payments and checkout
- Add checkout flow for item purchase or rental request.
- Create order records linked to user, item, price, payment status, and order lifecycle.
- Add payment gateway integration through Razorpay or Stripe.
- Secure the payment callback and status handling logic.

### Phase 5: Order lifecycle and seller confirmation
- Add order state transitions: pending, paid, confirmed, shipped/delivered, completed, cancelled.
- Allow the seller to confirm bookings or deliveries.
- Add buyer visibility into payment and delivery status.
- Ensure status changes are auditable and queryable.

### Phase 6: Deployment preparation
- Add Docker support for the app and database.
- Use environment variables for production secrets and settings.
- Prepare the project for cloud deployment and external storage.
- Add health checks, server configuration, and production-ready settings.

### Phase 7: Quality assurance, security, and launch hardening
- Validate all flows using end-to-end testing.
- Run security checks around authentication, file uploads, and payment callbacks.
- Validate responsiveness and edge cases for buyer, seller, and admin use.
- Perform final deployment smoke tests.

---

## Planned feature breakdown

### 1) Frontend UX and UI overhaul
#### Objective
Improve the visual quality and usability of the app so it feels like a polished campus marketplace rather than a basic functional prototype.

#### Scope
- Refine signup and login pages
- Improve profile creation and hostel conditional UI
- Improve home marketplace cards and filters
- Improve item posting form layout and validation messaging
- Improve item detail view and contact flow
- Ensure responsive experience on mobile devices
- Add stronger spacing between icons, cards, sections, and form controls to improve comfort and readability
- Convert login and signup screens into a more dynamic page flow with better interactivity and clearer transitions

#### Proposed implementation details
- Update the templates in the existing Django template structure.
- Rework styling in the CSS layer to create cleaner spacing, hierarchy, and mobile responsiveness.
- Enhance the JavaScript layer for dynamic field behavior, especially hostel visibility, auth page transitions, and upload interactions.
- Ensure forms match the backend fields exactly and use clear instructional text.
- Use accessible spacing patterns for icon-only elements and action rows to avoid visual clutter.

#### Files likely involved
- templates/bunkloop/*.html
- static/css/app.css
- static/js/item_form.js
- bunkloop/forms.py

#### Acceptance criteria
- Auth and profile flows look consistent and mobile friendly
- Users can complete sign-up and listing creation with less friction
- Conditional hostel logic remains clear and reliable
- All key actions are easy to discover and complete on a phone
- Icons and fields have sufficient spacing and visual breathing room
- Login and registration experience feels dynamic and refined rather than static

---

### 2) Student identity verification and onboarding security
#### Objective
Prevent fake registrations and verify the identity and student email before allowing the account to become active.

#### Scope
- Student email verification before creating an account
- Real-domain validation for institutional email addresses
- Actual mailbox existence checks for the provided email
- OTP verification through email
- Camera-based profile authenticity capture during registration
- Verification that the registration photo aligns with the student's personal details

#### Proposed implementation details
- Add a pre-registration step that validates the email domain and syntax.
- Use a backend service or external verification provider to confirm the email domain is legitimate and the mailbox is not disposable or unreachable.
- Send a one-time code to the email address and block account creation until OTP validation succeeds.
- Require camera capture on the registration page for the identity photo.
- Store the captured image, validate it as a live capture, and keep it linked to the student's profile.
- Add a clear consent and verification flow explaining that identity information is used for trust and safety checks.

#### Files likely involved
- bunkloop/models.py
- bunkloop/forms.py
- bunkloop/views.py
- bunkloop/urls.py
- templates/bunkloop/signup.html
- templates/bunkloop/login.html
- settings and environment configuration

#### Acceptance criteria
- A user cannot complete registration without a valid student email and verified OTP
- Invalid or disposable domains are blocked before account creation completes
- Real camera capture is required for identity verification during onboarding
- The registration process includes a trustworthy identity check before the account is marked active

---

### 3) Buyer-seller messaging system
#### Objective
Enable direct user communication around a listing before or after purchase.

#### Scope
- Conversations between a buyer and the seller
- Message history stored in the database
- Listing-linked chat threads
- Basic notification state for unread messages

#### Proposed data model
Add new models for:
- Conversation / chat thread
- Message
- Message delivery status
- Optional notification record

Suggested relationships:
- One conversation belongs to one listing
- One conversation has multiple participants
- One conversation contains many messages
- Each message belongs to one sender and one conversation

#### Proposed implementation details
- Create app-level models to persist conversations and message content.
- Add views for creating or opening a conversation and sending a message.
- Add templates for chat UI and message list.
- Add endpoints for fetching chat history and showing latest messages.
- Use Django authentication to restrict conversations to participants only.

#### Files likely involved
- bunkloop/models.py
- bunkloop/views.py
- bunkloop/urls.py
- templates/bunkloop/*.html

#### Acceptance criteria
- Buyer can open a chat from a listing
- Seller can reply and view a persistent history
- Only participants can access the thread
- Message timestamps and history are stored reliably

---

### 4) Payment and checkout flow
#### Objective
Support real buying or renting transactions with a formal checkout process.

#### Scope
- Add cart or checkout flow for a single item purchase
- Create an order record for each transaction
- Link order to the item and the buyer
- Integrate with a live payment provider such as Razorpay or Stripe
- Handle payment callbacks, order confirmation, and failure states

#### Proposed data model
Add models for:
- Order
- Order item
- Payment
- Payment status
- Order status history or lifecycle state

Suggested workflow:
- Buyer clicks Buy / Rent Now
- Order is created with pending status
- Redirect to payment provider
- Payment callback updates payment status and order status
- Seller receives confirmation and can update delivery or fulfillment state

#### Proposed implementation details
- Add a checkout view and success/cancel callback endpoints.
- Use environment variables for API keys and public/private keys.
- Implement signature verification and secure callback handling.
- Store payment metadata for auditability.
- Add order detail pages for both buyer and seller.

#### Files likely involved
- bunkloop/models.py
- bunkloop/views.py
- bunkloop/urls.py
- settings and environment config
- templates/bunkloop/*.html

#### Acceptance criteria
- Buyer can complete a validated checkout flow
- Payment status is persisted and visible to the user
- Orders are linked to the relevant listing and seller
- Failed or cancelled payments do not create a misleading successful order

---

### 5) Seller confirmation and order tracking
#### Objective
Move the app beyond checkout and into a complete transaction lifecycle.

#### Scope
- Seller confirms order or product availability
- Delivery or handoff status is recorded
- User tracks order progress from pending to completed
- Cancellation and dispute state handling is possible

#### Proposed workflow
- Order created
- Payment confirmed
- Seller marks item as confirmed / prepared
- Delivery or collection status is updated
- Buyer receives confirmation and can mark completion
- Completed orders remain visible in purchase history

#### Proposed implementation details
- Add order status enum or choices
- Add seller-side actions in templates and views
- Restrict status updates to authorized user roles
- Add transaction history and timestamps

#### Acceptance criteria
- Order lifecycle is visible to both parties
- Seller can confirm and update fulfillment state
- The app keeps a clean historical record of the transaction

---

### 6) Deployment readiness and infrastructure
#### Objective
Prepare the application for actual hosting and production deployment.

#### Scope
- Dockerize the project
- Use PostgreSQL in a production-safe configuration
- Move secrets to environment variables
- Add deployment-ready settings and media handling
- Prepare server startup and static asset configuration

#### Proposed strategy
- Use Docker and docker-compose or equivalent setup
- Configure PostgreSQL for production instead of relying on SQLite for live use
- Add environment template files with secure placeholders
- Define static and media collection for production hosting
- Prepare for deployment on a managed host or container platform

#### Files likely involved
- Dockerfile
- docker-compose.yml
- requirements.txt
- entropy/settings.py
- .env.example
- deployment documentation

#### Acceptance criteria
- Project can be built using containerized setup
- Production settings can be configured without editing code files directly
- Database and secret configuration are externalized
- Application bootstraps cleanly in a non-local environment

---

## Supporting tasks and quality gates

### Security and validation
- Validate all forms and permissions
- Protect payment callback endpoints
- Restrict user access to their own listings and conversations
- Sanitize file uploads and server-side validation

### Testing plan
- Unit tests for models and validation rules
- Form tests for hostel validation and item creation
- View tests for university-scoped listings and authentication
- Integration tests for checkout and messaging workflow
- Browser smoke tests for the important user journeys

### Analytics and observability
- Add basic logging for critical actions such as purchase, payment result, and chat activity
- Track failed or delayed orders for support overhead
- Monitor deployment health and error logs after launch

---

## Recommended delivery order
1. Frontend cleanup and mobile UX improvements
2. Student identity verification, domain validation, OTP flow, and camera-based registration checks
3. Messaging flow and database models
4. Payment and order creation flow
5. Seller confirmation and order tracking
6. Docker and production deployment configuration
7. Final QA, security review, and launch pass

This sequence keeps the project stable: first UX and trust onboarding, then communication, then financial transaction flow, then deployment. It ensures each layer is built and validated before the app becomes more complex.

---

## Risk considerations
- Payment integration can create operational and security risks if implemented too early.
- Messaging and orders should be scoped carefully to avoid poor data design.
- Deployment work should happen only after the app logic is stable and verified.
- Overbuilding before validation can delay deployment; the roadmap should remain modular.

## Final implementation principle
The app should evolve from a working campus MVP into a reliable marketplace with strong trust signals, transparent order states, and production-safe deployment. The next milestone should be to complete the UX refresh and then add the messaging and payment systems in a structured, testable order.
