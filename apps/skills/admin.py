from django.contrib import admin
from django.utils import timezone
from .models import SkillCategory, Skill, CandidateSkill
from apps.dashboard.models import log_staff_action, send_notification, Notification
from apps.scoring.services import calculate_candidate_score

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

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data:
            if obj.status in [CandidateSkill.VerificationStatus.KODAFRIQ_VERIFIED, CandidateSkill.VerificationStatus.ASSESSED]:
                obj.verified_by = request.user
                obj.verified_at = timezone.now()
            elif obj.status == CandidateSkill.VerificationStatus.SELF_REPORTED:
                obj.verified_by = None
                obj.verified_at = None

            super().save_model(request, obj, form, change)

            log_staff_action(
                actor=request.user,
                action=f"Skill Verification: {obj.skill.name} -> {obj.get_status_display()}",
                action_category='VERIFICATION',
                target_user=obj.candidate.user,
                target_entity="CandidateSkill",
                target_id=str(obj.pk) if obj.pk else "",
                details=f"Admin {request.user.username} updated status of skill '{obj.skill.name}' to {obj.status}.",
                request=request
            )
            calculate_candidate_score(obj.candidate)
            send_notification(
                recipient=obj.candidate.user,
                title="Skill Verification Update",
                message=f"Your clinical skill '{obj.skill.name}' was verified as '{obj.get_status_display()}'.",
                notification_type=Notification.NotificationType.SCORE_BOOST
            )
        else:
            super().save_model(request, obj, form, change)
