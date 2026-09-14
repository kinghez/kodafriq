from django.contrib import admin
from .models import Job, JobRequiredSkill, Application, Shortlist

class JobRequiredSkillInline(admin.TabularInline):
    model = JobRequiredSkill
    extra = 2

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('title', 'employer', 'job_type', 'min_years_experience', 'min_score_required', 'status', 'created_at')
    list_filter = ('status', 'job_type')
    inlines = [JobRequiredSkillInline]

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'job', 'match_percentage', 'status', 'applied_at')
    list_filter = ('status',)

admin.site.register(Shortlist)
