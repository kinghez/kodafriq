from django.contrib import admin
from .models import ScoreWeightConfig, ScoreLog

@admin.register(ScoreWeightConfig)
class ScoreWeightConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'assessment_weight', 'work_performance_weight', 'training_weight', 'professional_experience_weight', 'readiness_weight', 'is_active', 'updated_at')

@admin.register(ScoreLog)
class ScoreLogAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'final_score', 'calculated_at')
