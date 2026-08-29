from django.urls import path

from . import views

app_name = 'bunkloop'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile, name='profile'),
    path('logout/', views.logout_view, name='logout'),
    path('my-items/', views.my_items, name='my_items'),
    path('items/new/', views.item_create, name='item_create'),
    path('items/<int:pk>/', views.item_detail, name='item_detail'),
]
