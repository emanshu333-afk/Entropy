from django.urls import path

from . import api_views

urlpatterns = [
    path('chat/conversations/', api_views.ConversationListCreateAPIView.as_view(), name='api_conversation_list_create'),
    path('chat/conversations/<str:pk>/', api_views.ConversationDetailAPIView.as_view(), name='api_conversation_detail'),
    path('chat/conversations/<str:pk>/messages/', api_views.MessageListAPIView.as_view(), name='api_conversation_messages'),
    path('chat/conversations/<str:pk>/read/', api_views.MarkReadAPIView.as_view(), name='api_conversation_read'),
]
