from django.urls import path

from . import api_views
from . import auth_otp_views

urlpatterns = [
    path('chat/conversations/', api_views.ConversationListCreateAPIView.as_view(), name='api_conversation_list_create'),
    path('chat/conversations/<str:pk>/', api_views.ConversationDetailAPIView.as_view(), name='api_conversation_detail'),
    path('chat/conversations/<str:pk>/messages/', api_views.MessageListAPIView.as_view(), name='api_conversation_messages'),
    path('chat/conversations/<str:pk>/read/', api_views.MarkReadAPIView.as_view(), name='api_conversation_read'),
    # Auth OTP — per BunkLoop_SendOTP_Email_Integration_Guide.md §14
    path('auth/send-email-otp/', auth_otp_views.send_otp_view, name='api_send_email_otp'),
    path('auth/verify-email-otp/', auth_otp_views.verify_otp_view, name='api_verify_email_otp'),
]
