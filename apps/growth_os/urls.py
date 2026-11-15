from django.urls import path
from . import views

app_name = 'growth_os'

urlpatterns = [
    path('', views.GrowthOSDashboardView.as_view(), name='dashboard'),
    path('discovery/', views.EmployerDiscoveryHubView.as_view(), name='discovery_hub'),
    path('discovery/import/', views.DiscoveryLeadImportView.as_view(), name='discovery_import'),
    path('leads/', views.EmployerLeadListView.as_view(), name='lead_list'),
    path('leads/add/', views.EmployerLeadCreateView.as_view(), name='lead_create'),
    path('leads/import/', views.EmployerLeadCSVImportView.as_view(), name='lead_import_csv'),
    path('leads/import/sample-csv/', views.DownloadSampleCSVView.as_view(), name='download_sample_csv'),
    path('leads/<uuid:pk>/', views.EmployerLeadDetailView.as_view(), name='lead_detail'),
    path('leads/<uuid:pk>/edit/', views.EmployerLeadUpdateView.as_view(), name='lead_edit'),
    path('leads/<uuid:pk>/scan-careers/', views.LeadScanCareersView.as_view(), name='lead_scan_careers'),
    path('leads/<uuid:pk>/recalculate/', views.EmployerLeadRecalculateScoresView.as_view(), name='lead_recalculate'),
    path('leads/<uuid:lead_id>/contacts/add/', views.LeadContactCreateView.as_view(), name='contact_create'),
    path('contacts/<uuid:pk>/delete/', views.LeadContactDeleteView.as_view(), name='contact_delete'),
    path('leads/<uuid:lead_id>/vacancies/add/', views.HiringSignalCreateView.as_view(), name='vacancy_create'),
    path('vacancies/<uuid:pk>/toggle/', views.HiringSignalToggleView.as_view(), name='vacancy_toggle'),
    path('leads/<uuid:lead_id>/activities/add/', views.CRMActivityCreateView.as_view(), name='activity_create'),
    path('leads/<uuid:lead_id>/opportunity/update/', views.CRMOpportunityUpdateView.as_view(), name='opportunity_update'),
    path('matches/<uuid:pk>/toggle-shortlist/', views.LeadReverseMatchToggleShortlistView.as_view(), name='match_toggle_shortlist'),

    # Phase 3: AI Outreach Generation, Review Queue, and Public Shortlist
    path('outreach/', views.OutreachQueueView.as_view(), name='outreach_queue'),
    path('leads/<uuid:lead_id>/outreach/generate/', views.OutreachGenerateView.as_view(), name='outreach_generate'),
    path('outreach/<uuid:pk>/approve/', views.OutreachApproveSendView.as_view(), name='outreach_approve'),
    path('outreach/<uuid:pk>/reject/', views.OutreachRejectView.as_view(), name='outreach_reject'),
    path('outreach/<uuid:pk>/reply/', views.OutreachRecordReplyView.as_view(), name='outreach_reply'),
    path('shortlist/<uuid:pk>/', views.PublicCandidateShortlistView.as_view(), name='public_shortlist'),
    path('shortlist/<uuid:pk>/inquire/', views.PublicShortlistInquireView.as_view(), name='public_shortlist_inquire'),
]

