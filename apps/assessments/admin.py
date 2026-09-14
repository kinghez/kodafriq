from django.contrib import admin
from .models import Assessment, Question, AnswerChoice, AssessmentAttempt, CandidateResponse

class AnswerChoiceInline(admin.TabularInline):
    model = AnswerChoice
    extra = 4

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('order', 'prompt', 'assessment', 'points')
    list_filter = ('assessment',)
    inlines = [AnswerChoiceInline]

@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'duration_minutes', 'pass_mark_percentage', 'is_active')
    list_filter = ('category', 'is_active')

@admin.register(AssessmentAttempt)
class AssessmentAttemptAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'assessment', 'score_percentage', 'passed', 'status', 'started_at')
    list_filter = ('passed', 'status')
