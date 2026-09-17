from django.urls import path
from . import views

app_name = 'employers'

urlpatterns = [
    # Talent Discovery Engine
    path('talents/', views.TalentSearchView.as_view(), name='talent_search'),
    
    # Shortlist & Talent Pools
    path('shortlist/', views.ShortlistListView.as_view(), name='shortlist'),
    path('shortlist/<int:candidate_id>/toggle/', views.ShortlistToggleView.as_view(), name='shortlist_toggle'),
    path('shortlist/<int:pk>/note/', views.ShortlistNoteUpdateView.as_view(), name='shortlist_note_update'),
    
    # Employer Job Management
    path('jobs/', views.JobListView.as_view(), name='job_list'),
    path('jobs/create/', views.JobCreateView.as_view(), name='job_create'),
    path('jobs/<int:pk>/edit/', views.JobUpdateView.as_view(), name='job_edit'),
    path('jobs/<int:pk>/applicants/', views.JobApplicantListView.as_view(), name='job_applicants'),
    path('applications/<int:application_id>/status/', views.ApplicantStatusUpdateView.as_view(), name='applicant_status_update'),

    # Public / Candidate Job Board
    path('board/', views.PublicJobListView.as_view(), name='public_job_list'),
    path('board/<int:pk>/', views.PublicJobDetailView.as_view(), name='public_job_detail'),
    path('board/<int:pk>/apply/', views.JobApplyView.as_view(), name='job_apply'),
]
