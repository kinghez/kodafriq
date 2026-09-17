from django.urls import path
from . import views

app_name = 'assessments'

urlpatterns = [
    path('', views.AssessmentListView.as_view(), name='index'),
    path('<int:pk>/', views.AssessmentDetailView.as_view(), name='detail'),
    path('<int:pk>/start/', views.AssessmentStartView.as_view(), name='start'),
    path('attempt/<int:attempt_id>/', views.AssessmentRunnerView.as_view(), name='runner'),
    path('attempt/<int:attempt_id>/submit/', views.AssessmentSubmitView.as_view(), name='submit'),
    path('attempt/<int:attempt_id>/results/', views.AssessmentResultView.as_view(), name='results'),
]
