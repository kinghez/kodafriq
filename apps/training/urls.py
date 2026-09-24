from django.urls import path
from . import views

app_name = 'training'

urlpatterns = [
    path('', views.TrainingProgramListView.as_view(), name='index'),
    path('<int:pk>/', views.TrainingProgramDetailView.as_view(), name='detail'),
    path('<int:pk>/enroll/', views.TrainingEnrollView.as_view(), name='enroll'),
    path('enrolment/<int:enrolment_id>/learn/', views.TrainingLearnView.as_view(), name='learn'),
    path('enrolment/<int:enrolment_id>/module/<int:module_id>/complete/', views.ModuleCompleteView.as_view(), name='module_complete'),
    path('certificate/preview/', views.AdminCertificatePreviewView.as_view(), name='certificate_preview_global'),
    path('certificate/preview/program/<int:program_id>/', views.AdminCertificatePreviewView.as_view(), name='certificate_preview_program'),
    path('certificate/preview/enrolment/<int:enrolment_id>/', views.AdminCertificatePreviewView.as_view(), name='certificate_preview_enrolment'),
    path('certificate/preview/print/', views.AdminCertificatePrintPreviewView.as_view(), name='certificate_preview_print'),
    path('certificate/<str:certificate_id>/print/', views.TrainingCertificatePrintView.as_view(), name='certificate_print'),
    path('certificate/<str:certificate_id>/', views.TrainingCertificateView.as_view(), name='certificate'),
]
