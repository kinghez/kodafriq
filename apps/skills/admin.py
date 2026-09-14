from django.contrib import admin
from .models import SkillCategory, Skill, CandidateSkill

@admin.register(SkillCategory)
class SkillCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'code_standard', 'category', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'code_standard')

@admin.register(CandidateSkill)
class CandidateSkillAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'skill', 'status', 'proficiency', 'verified_by', 'verified_at')
    list_filter = ('status', 'proficiency')
    search_fields = ('candidate__user__username', 'skill__name')
