from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.KodafriqLoginView.as_view(), name='login'),
    path('logout/', views.KodafriqLogoutView.as_view(), name='logout'),
    path('register/', views.RoleSelectionView.as_view(), name='role_select'),
    path('register/talent/', views.TalentRegistrationView.as_view(), name='register_talent'),
    path('register/employer/', views.EmployerRegistrationView.as_view(), name='register_employer'),
    path('api/geo/', views.GeoDetectionAPIView.as_view(), name='api_geo'),
    path('suspended/', views.SuspendedAccountView.as_view(), name='suspended'),
]
