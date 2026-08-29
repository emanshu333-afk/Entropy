# Bunkloop – PG Sharing Marketplace

## Overview
This project is a Django-based campus marketplace for students to list, browse, and buy or rent items within the same university community. The app currently supports user sign-up, profile creation, item posting, item browsing, and item detail viewing.
## Database used
We have implemented the use of postgres sql to manage the project at large scale across campuses, .env.example file has been provided where the required values can be filled and a migration can be run to test the project on another machine with new data.

## What is already done
- Student registration and login flow with university and hostel-based profiles
- Profile image selection and hostel validation rules
- Item listing creation with title, category, price, listing type, condition, and photo upload support
- Marketplace home screen showing listings filtered by the logged-in user’s university
- Personal “My items” view for the seller
- Item detail page with item metadata, seller contact, and gallery images
- Selling/renting listing types with price handling built into the form
- integration with postgres
## What is pending / being added
- improve sign up/ sign in front UI/UX
- also improve the other over all UI/UX 
- Buyer-seller messaging and a basic payment/checkout flow for selling items
- Real payment integration with a live gateway such as Razorpay or Stripe
- Complete buyer-to-seller messaging system with persistent chat history and notifications
- Checkout flow tied to a payment record and order status tracking
- Seller confirmation or delivery status flow after payment
- prepare the project for deployment using docker
- Production deployment and environment configuration
