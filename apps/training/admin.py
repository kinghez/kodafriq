from django.contrib import admin
from .models import TrainingProgram, TrainingEnrolment

@admin.register(TrainingProgram)
class TrainingProgramAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'duration_weeks', 'start_date', 'is_active')
    list_filter = ('is_active',)

@admin.register(TrainingEnrolment)
class TrainingEnrolmentAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'program', 'status', 'attendance_rate', 'certificate_id', 'enrolled_at')
    list_filter = ('status',)
