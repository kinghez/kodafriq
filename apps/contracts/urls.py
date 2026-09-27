from django.urls import path
from . import views

app_name = 'contracts'

urlpatterns = [
    path('', views.ContractListView.as_view(), name='contract_list'),
    path('new/', views.ContractCreateView.as_view(), name='contract_create'),
    path('<uuid:pk>/', views.ContractDetailView.as_view(), name='contract_detail'),
    path('<uuid:pk>/action/', views.ContractActionView.as_view(), name='contract_action'),
    path('timesheet/<uuid:pk>/log/', views.CandidateTimesheetLogView.as_view(), name='candidate_timesheet_log'),
    path('timesheet/<uuid:pk>/review/', views.EmployerTimesheetReviewView.as_view(), name='employer_timesheet_review'),
    path('milestone/<uuid:pk>/submit/', views.MilestoneSubmitView.as_view(), name='milestone_submit'),
    path('milestone/<uuid:pk>/approve/', views.MilestoneApproveView.as_view(), name='milestone_approve'),
]
