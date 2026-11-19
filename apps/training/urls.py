from django.urls import path
from . import views

app_name = 'training'

urlpatterns = [
    path('', views.TrainingProgramListView.as_view(), name='index'),
    path('<int:pk>/', views.TrainingProgramDetailView.as_view(), name='detail'),
    path('<int:pk>/enroll/', views.TrainingEnrollView.as_view(), name='enroll'),
    path('<int:pk>/checkout/initiate/', views.TrainingCheckoutInitiateView.as_view(), name='checkout_initiate'),
    path('<int:pk>/checkout/verify/', views.TrainingCheckoutVerifyView.as_view(), name='checkout_verify'),
    path('<int:pk>/coupon/validate/', views.ValidateCouponView.as_view(), name='validate_coupon'),
    path('analytics/revenue/', views.StaffTrainingRevenueAnalyticsView.as_view(), name='staff_revenue_analytics'),
    path('analytics/revenue/export/', views.StaffTrainingRevenueExportView.as_view(), name='staff_revenue_export'),
    path('admin/upload-media/', views.AdminMediaUploadView.as_view(), name='admin_upload_media'),
    path('enrolment/<int:enrolment_id>/learn/', views.TrainingLearnView.as_view(), name='learn'),
    path('enrolment/<int:enrolment_id>/lesson/<int:lesson_id>/matching/submit/', views.InteractiveMatchingSubmitView.as_view(), name='lesson_matching_submit'),
    path('enrolment/<int:enrolment_id>/lesson/<int:lesson_id>/complete/', views.LessonCompleteView.as_view(), name='lesson_complete'),
    path('enrolment/<int:enrolment_id>/module/<int:module_id>/complete/', views.ModuleCompleteView.as_view(), name='module_complete'),
    path('enrolment/<int:enrolment_id>/module/<int:module_id>/quiz/submit/', views.ModuleQuizSubmitView.as_view(), name='quiz_submit'),
    path('certificate/preview/', views.AdminCertificatePreviewView.as_view(), name='certificate_preview_global'),
    path('certificate/preview/program/<int:program_id>/', views.AdminCertificatePreviewView.as_view(), name='certificate_preview_program'),
    path('certificate/preview/enrolment/<int:enrolment_id>/', views.AdminCertificatePreviewView.as_view(), name='certificate_preview_enrolment'),
    path('certificate/preview/print/', views.AdminCertificatePrintPreviewView.as_view(), name='certificate_preview_print'),
    path('certificate/<str:certificate_id>/print/', views.TrainingCertificatePrintView.as_view(), name='certificate_print'),
    path('certificate/<str:certificate_id>/', views.TrainingCertificateView.as_view(), name='certificate'),
]
