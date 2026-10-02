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
    
    # Email Verification
    path('verify-email/resend/', views.ResendVerificationEmailView.as_view(), name='resend_verification'),
    path('verify-email/<str:uidb64>/<str:token>/', views.EmailVerificationView.as_view(), name='verify_email'),

    # Password Reset Workflow
    path('password-reset/', views.KodafriqPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.KodafriqPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', views.KodafriqPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset-complete/', views.KodafriqPasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
