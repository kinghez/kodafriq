from django.urls import path
from . import views
from . import views_messaging

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
    
    # Admin Command Center & Analytics (Phase 9)
    path('staff/analytics/', views.AdminAnalyticsView.as_view(), name='staff_analytics'),
    path('staff/audit-logs/', views.StaffAuditLogView.as_view(), name='staff_audit_logs'),
    path('staff/visitors/', views.StaffVisitorAnalyticsView.as_view(), name='staff_visitors'),
    path('staff/users/<int:pk>/toggle-suspension/', views.StaffUserToggleSuspensionView.as_view(), name='staff_toggle_suspension'),
    path('staff/export/<str:dataset>/', views.AdminExportDataView.as_view(), name='staff_export'),
    path('admin-dashboard/', views.StaffDashboardView.as_view(), name='admin_dashboard'),
    path('admin-dashboard/analytics/', views.AdminAnalyticsView.as_view(), name='admin_analytics'),
    
    # Notifications Hub
    path('notifications/', views.NotificationsListView.as_view(), name='notifications'),
    path('notifications/mark-read/<int:notification_id>/', views.MarkNotificationReadView.as_view(), name='notification_mark_read'),
    path('notifications/mark-all-read/', views.MarkAllNotificationsReadView.as_view(), name='notifications_mark_all_read'),

    # Settings Suite (Employers & Professionals)
    path('settings/', views.DashboardSettingsView.as_view(), name='settings'),

    # Support Ticket Submission
    path('support/ticket/', views.ContactSupportView.as_view(), name='contact_support'),

    # Direct Messaging Suite
    path('messages/', views_messaging.ConversationInboxView.as_view(), name='messages_inbox'),
    path('messages/<int:pk>/', views_messaging.ConversationInboxView.as_view(), name='messages_thread'),
    path('messages/start/<int:candidate_id>/', views_messaging.StartConversationView.as_view(), name='start_conversation'),
    path('messages/<int:pk>/reply/', views_messaging.SendMessageView.as_view(), name='send_message'),
    path('messages/<int:pk>/close/', views_messaging.CloseConversationView.as_view(), name='close_conversation'),
    path('messages/<int:pk>/reopen/', views_messaging.ReopenConversationView.as_view(), name='reopen_conversation'),
]
