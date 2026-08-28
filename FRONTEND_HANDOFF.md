# Frontend Handoff Book

## MVP goal
Build a simple, fast marketplace flow for students to list and browse second-hand items.

## Core screens
1. Student signup/profile screen
   - full name
   - registration ID
   - university dropdown
   - profile image selection
   - contact number
   - student type selection
   - hostel dropdown only when hosteler is selected
   - email
   - gender

2. Item posting form
   - item category dropdown
   - item photos (camera-first, up to 4 images)
   - price input
   - listing type selector: Selling / Renting
   - item condition dropdown
   - optional item description

3. Browse marketplace
   - cards for items with photo, category, price, condition, and listing type
   - filter chips for category and listing type

## Item condition options
Use these exact values from the backend:
- New
- Like New
- Good
- Fair
- Needs Repair

## Form behavior requirements
- If the listing type is Selling, show the price as a sale price.
- If the listing type is Renting, show the rental amount and duration context if needed.
- Allow upload from live camera first; fallback to gallery upload is okay if needed.
- Limit to 4 images per item.
- Validate that hosteler users must select a hostel.

## Recommended UI structure
### Item form fields
- category: select
- photos: file input or camera capture widget, max 4
- price: number input
- listing type: radio or segmented buttons with Selling / Renting
- condition: select
- description: textarea (optional but recommended)

### Suggested component hierarchy
- Page shell
- Top nav bar
- Student profile card
- Listing form card
- Photo upload widget
- Condition select
- Sell/Rent switch
- Submit button

## Design direction
- Clean, mobile-first layout
- Warm neutral theme with campus/student-friendly feel
- Large tap targets for mobile users
- Use clear radio buttons for Selling vs Renting
- Use image cards with upload count indicator

## Acceptance criteria for MVP
- User can sign up with required student fields
- User can create a listing with category, price, selling/renting choice, condition, and photos
- User can attach up to 4 images
- Hosteler users must choose hostel
- Listing is visible in a simple browse view

## Suggested file structure
- templates/bunkloop/base.html
- templates/bunkloop/item_form.html
- static/css/app.css
- static/js/item_form.js

## Frontend handoff checklist
- [ ] Student signup form is implemented
- [ ] Hostel field is conditionally shown
- [ ] Item form matches backend model fields
- [ ] Camera upload widget supports up to 4 images
- [ ] Selling / Renting toggle is implemented
- [ ] Condition dropdown matches backend choices
- [ ] Browsing cards show price + condition + category
- [ ] Mobile responsiveness is tested
