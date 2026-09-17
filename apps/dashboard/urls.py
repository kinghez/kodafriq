from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.RoleDashboardRouterView.as_view(), name='index'),
    path('candidate/', views.CandidateDashboardView.as_view(), name='candidate'),
    path('candidate/profile/', views.CandidateProfileEditView.as_view(), name='candidate_profile_edit'),
    
    # Work Experience CRUD
    path('candidate/experience/add/', views.WorkExperienceCreateView.as_view(), name='experience_add'),
    path('candidate/experience/<int:pk>/delete/', views.WorkExperienceDeleteView.as_view(), name='experience_delete'),
    
    # Certifications CRUD
    path('candidate/certification/add/', views.CertificationCreateView.as_view(), name='certification_add'),
    path('candidate/certification/<int:pk>/delete/', views.CertificationDeleteView.as_view(), name='certification_delete'),
    
    # Skills Management
    path('candidate/skill/add/', views.CandidateSkillAddView.as_view(), name='skill_add'),
    path('candidate/skill/<int:pk>/delete/', views.CandidateSkillDeleteView.as_view(), name='skill_delete'),
    
    # Public Verified Talent Card
    path('talent/card/', views.PublicTalentCardView.as_view(), name='talent_card_me'),
    path('talent/card/<int:pk>/', views.PublicTalentCardView.as_view(), name='talent_card_public'),
    
    # Other Role Dashboards
    path('employer/', views.EmployerDashboardView.as_view(), name='employer'),
    path('staff/', views.StaffDashboardView.as_view(), name='staff'),
]
