from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('broadcast/', views.AdminBroadcastCenterView.as_view(), name='admin_broadcast'),
    path('broadcast/<int:pk>/', views.AdminBroadcastDetailView.as_view(), name='broadcast_detail'),
    path('api/audience-estimate/', views.AdminAudienceEstimateApiView.as_view(), name='audience_estimate'),
]
