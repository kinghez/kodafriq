from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.RoleDashboardRouterView.as_view(), name='index'),
    path('candidate/', views.CandidateDashboardView.as_view(), name='candidate'),
    path('employer/', views.EmployerDashboardView.as_view(), name='employer'),
    path('staff/', views.StaffDashboardView.as_view(), name='staff'),
]
