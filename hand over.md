# Entropy Frontend Handover

## Current state

The `templates/` folder contains a Django-compatible Notion-inspired MVP shell. All templates are kept directly in this one folder. It assumes named URL namespaces and can be connected to Django views without changing the markup.

## Templates

- `base.html`: shared navigation, top bar, responsive layout, and design tokens.
- `home.html`: marketplace feed, category filters, sort control, and listing cards.
- `detail.html`: listing facts, seller identity, chat action, and report action.
- `form.html`: create listing form with image upload, sell/rent, condition, price, and pickup fields.
- `mine.html`: owner listing management and status display.
- `inbox.html`: conversation list and listing-linked chat room.
- `profile.html`: profile and verified-community identity.
- `reports.html`: reported-listing moderation table.
- `auth.html`: login and signup base template.
- `../static/entropy.css`: shared stylesheet and responsive rules.

## Expected URL names

Wire these names in the backend, or update the `{% url %}` calls when the URL design is final:

- `marketplace:home`
- `listings:create`, `listings:detail`, `listings:mine`
- `messaging:inbox`, `messaging:chat`
- `profiles:me`

## Backend handoff checklist

- Configure `TEMPLATES[0]['DIRS']` to include `BASE_DIR / 'templates'`.
- Add the URL namespaces listed above.
- Replace hard-coded demo listing data with context querysets.
- Serve uploaded media and provide `listing.images` for the gallery.
- Add authenticated user context to the sidebar and profile.
- Enforce ownership for listing edits, deletes, and status changes.
- Add POST handling and validation to the listing form and chat composer.
- Add a unique constraint for `(listing_id, buyer_id, seller_id)` conversations.
- Exclude `sold`, `rented`, and `closed` listings from available results.
- Connect report actions to the moderation workflow.

## MVP behavior to preserve

The primary demo path is: publish a listing, find it through browse/search, open details, chat with the owner, reserve it, then mark it sold or rented. Payments and delivery remain offline.
