from django.urls import path

from . import views

app_name = 'bunkloop'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup, name='signup'),
    path('verify-email/', views.verify_email, name='verify_email'),
    path('profile/', views.profile, name='profile'),
    path('logout/', views.logout_view, name='logout'),
    path('my-items/', views.my_items, name='my_items'),
    path('items/new/', views.item_create, name='item_create'),
    path('items/<int:pk>/', views.item_detail, name='item_detail'),
    path('items/<int:pk>/delete/', views.item_delete, name='item_delete'),
    path('items/<int:pk>/contact/', views.start_conversation, name='start_conversation'),
    path('items/<int:pk>/checkout/', views.order_create, name='order_create'),
    path('messages/', views.conversation_list, name='conversation_list'),
    path('messages/<int:pk>/', views.conversation_detail, name='conversation_detail'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/update/', views.order_update_status, name='order_update_status'),
    path('universities/', views.university_list, name='university_list'),
]
