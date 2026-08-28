# Entropy Frontend Handover

## Current state

The frontend now follows the backend handoff structure. Templates live under `templates/bunkloop/` and shared assets live under `static/css/` and `static/js/`.

## Templates

- `templates/bunkloop/base.html`: shared mobile-first page shell.
- `templates/bunkloop/signup.html`: required student profile fields and conditional hostel field.
- `templates/bunkloop/item_form.html`: category, camera-first photos, sell/rent, price, condition, and description.
- `templates/bunkloop/home.html`: browse cards with image, category, price, condition, and listing type.
- `static/css/app.css`: shared responsive design system.
- `static/js/item_form.js`: hostel validation, sell/rent label, four-photo limit, and previews.

## Expected URL names

Wire these names in the backend, or update the `{% url %}` calls when the URL design is final:

- `marketplace:home`
- `listings:create`, `listings:detail`, `listings:mine`
- `messaging:inbox`, `messaging:chat`
- `profiles:me`

## Backend handoff checklist

- Configure `TEMPLATES[0]['DIRS']` to include `BASE_DIR / 'templates'`.
- Add the `bunkloop` URL namespace with `home`, `item_create`, `item_detail`, and `profile` names, or update the `{% url %}` tags.
- Configure `TEMPLATES[0]['DIRS']` to include `BASE_DIR / 'templates'`.
- Configure static files so `static/css/app.css` and `static/js/item_form.js` resolve.
- Pass a `listings` queryset to `home.html`; it expects `item.images.first`, `title`, `price`, `category`, `listing_type`, `condition`, and `created_at`.
- Bind signup and item form fields to the backend forms while preserving the field names in the templates.
- Serve uploaded media for listing images.
- Enforce hostel validation server-side as well as in the browser.

## MVP behavior to preserve

The primary demo path is: publish a listing, find it through browse/search, open details, chat with the owner, reserve it, then mark it sold or rented. Payments and delivery remain offline.
