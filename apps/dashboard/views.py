from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse
from django.http import Http404

from apps.accounts.models import User, CandidateProfile, EmployerProfile, WorkExperience, CandidateCertification
from apps.accounts.forms import CandidateProfileEditForm, WorkExperienceForm, CandidateCertificationForm
from apps.skills.models import CandidateSkill, Skill
from apps.skills.forms import CandidateSkillAddForm
from apps.scoring.services import calculate_candidate_score


class RoleDashboardRouterView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        user = request.user
        if user.is_kodafriq_staff:
            return redirect('dashboard:staff')
        elif user.is_employer:
            return redirect('dashboard:employer')
        else:
            return redirect('dashboard:candidate')


class CandidateDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/candidate_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile, _ = CandidateProfile.objects.get_or_create(user=user)
        
        # Calculate dynamic profile completion and verified score
        score_data = calculate_candidate_score(profile)
        
        completion_fields = [
            bool(user.first_name and user.last_name),
            bool(user.email),
            bool(profile.headline),
            bool(profile.phone),
            bool(profile.location),
            bool(profile.years_of_experience > 0),
            bool(profile.bio),
            bool(profile.resume_file),
            bool(profile.certifications.exists()),
            bool(profile.skills.exists()),
        ]
        completion_pct = int((sum(completion_fields) / len(completion_fields)) * 100)

        context['profile'] = profile
        context['completion_pct'] = max(completion_pct, 20)
        context['verified_score'] = profile.kodafriq_verified_score
        context['score_breakdown'] = score_data
        context['certifications'] = profile.certifications.all()[:4]
        context['work_experiences'] = profile.work_experiences.order_by('-start_date')[:3]
        context['skills'] = profile.skills.select_related('skill', 'skill__category')[:6]
        context['verified_skills_count'] = profile.skills.filter(status__in=['ASSESSED', 'KODAFRIQ_VERIFIED']).count()
        context['total_skills_count'] = profile.skills.count()
        return context


class CandidateProfileEditView(LoginRequiredMixin, View):
    template_name = 'dashboard/candidate_profile_edit.html'

    def get(self, request, *args, **kwargs):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        score_data = calculate_candidate_score(profile)

        context = {
            'profile': profile,
            'profile_form': CandidateProfileEditForm(instance=profile),
            'experience_form': WorkExperienceForm(),
            'certification_form': CandidateCertificationForm(),
            'skill_form': CandidateSkillAddForm(candidate=profile),
            'work_experiences': profile.work_experiences.order_by('-start_date'),
            'certifications': profile.certifications.order_by('-issue_date'),
            'skills': profile.skills.select_related('skill', 'skill__category'),
            'score_data': score_data,
            'verified_score': profile.kodafriq_verified_score,
            'completion_pct': int((sum([
                bool(request.user.first_name and request.user.last_name),
                bool(profile.headline),
                bool(profile.phone),
                bool(profile.location),
                bool(profile.years_of_experience > 0),
                bool(profile.bio),
                bool(profile.profile_photo),
                bool(profile.resume_file),
                bool(profile.certifications.exists()),
                bool(profile.skills.exists()),
            ]) / 10) * 100),
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        form = CandidateProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            calculate_candidate_score(profile)
            messages.success(request, "Your professional profile details have been successfully updated!")
            return redirect('dashboard:candidate_profile_edit')
        
        # If invalid, re-render with errors
        score_data = calculate_candidate_score(profile)
        context = {
            'profile': profile,
            'profile_form': form,
            'experience_form': WorkExperienceForm(),
            'certification_form': CandidateCertificationForm(),
            'skill_form': CandidateSkillAddForm(candidate=profile),
            'work_experiences': profile.work_experiences.order_by('-start_date'),
            'certifications': profile.certifications.order_by('-issue_date'),
            'skills': profile.skills.select_related('skill', 'skill__category'),
            'score_data': score_data,
            'verified_score': profile.kodafriq_verified_score,
            'active_tab': 'general',
        }
        return render(request, self.template_name, context)


class WorkExperienceCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        form = WorkExperienceForm(request.POST)
        if form.is_valid():
            exp = form.save(commit=False)
            exp.candidate = profile
            exp.save()
            calculate_candidate_score(profile)
            messages.success(request, f"Clinical experience at {exp.organization_name} added!")
        else:
            messages.error(request, "Could not add work experience. Please check the entered dates and details.")
        return redirect('dashboard:candidate_profile_edit')


class WorkExperienceDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        profile = get_object_or_404(CandidateProfile, user=request.user)
        exp = get_object_or_404(WorkExperience, pk=pk, candidate=profile)
        org_name = exp.organization_name
        exp.delete()
        calculate_candidate_score(profile)
        messages.success(request, f"Work experience at {org_name} removed.")
        return redirect('dashboard:candidate_profile_edit')


class CertificationCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        form = CandidateCertificationForm(request.POST, request.FILES)
        if form.is_valid():
            cert = form.save(commit=False)
            cert.candidate = profile
            cert.save()
            calculate_candidate_score(profile)
            messages.success(request, f"Certification '{cert.certification_name}' added successfully! Submitted for verification.")
        else:
            messages.error(request, "Could not add certification. Please check the entered credential details.")
        return redirect('dashboard:candidate_profile_edit')


class CertificationDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        profile = get_object_or_404(CandidateProfile, user=request.user)
        cert = get_object_or_404(CandidateCertification, pk=pk, candidate=profile)
        name = cert.certification_name
        cert.delete()
        calculate_candidate_score(profile)
        messages.success(request, f"Certification '{name}' removed.")
        return redirect('dashboard:candidate_profile_edit')


class CandidateSkillAddView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        form = CandidateSkillAddForm(request.POST, request.FILES, candidate=profile)
        if form.is_valid():
            skill_instance = form.save(commit=False)
            skill_instance.candidate = profile
            skill_instance.status = CandidateSkill.VerificationStatus.SELF_REPORTED
            skill_instance.save()
            calculate_candidate_score(profile)
            messages.success(request, f"Skill '{skill_instance.skill.name}' added to your portfolio!")
        else:
            messages.error(request, "Could not add skill. Please select a valid skill from the healthcare catalog.")
        return redirect('dashboard:candidate_profile_edit')


class CandidateSkillDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        profile = get_object_or_404(CandidateProfile, user=request.user)
        candidate_skill = get_object_or_404(CandidateSkill, pk=pk, candidate=profile)
        name = candidate_skill.skill.name
        candidate_skill.delete()
        calculate_candidate_score(profile)
        messages.success(request, f"Skill '{name}' removed from your portfolio.")
        return redirect('dashboard:candidate_profile_edit')


class PublicTalentCardView(TemplateView):
    template_name = 'dashboard/talent_card_public.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pk = self.kwargs.get('pk')
        if pk:
            profile = get_object_or_404(CandidateProfile, pk=pk)
        elif self.request.user.is_authenticated and hasattr(self.request.user, 'candidate_profile'):
            profile = self.request.user.candidate_profile
        else:
            raise Http404("Talent card not found.")
            
        context['profile'] = profile
        context['score_data'] = calculate_candidate_score(profile)
        context['skills'] = profile.skills.select_related('skill', 'skill__category')
        context['certifications'] = profile.certifications.all()
        context['experiences'] = profile.work_experiences.order_by('-start_date')
        return context


class EmployerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/employer_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile, _ = EmployerProfile.objects.get_or_create(
            user=user,
            defaults={'company_name': f"{user.get_full_name() or user.username} Healthcare"}
        )
        from apps.employers.models import Job, Application, Shortlist
        context['profile'] = profile
        context['total_candidates'] = CandidateProfile.objects.count()
        context['verified_candidates'] = CandidateProfile.objects.filter(is_employer_ready=True).count()
        context['active_jobs_count'] = profile.jobs.filter(status=Job.JobStatus.ACTIVE).count()
        context['total_jobs_count'] = profile.jobs.count()
        context['total_applications'] = Application.objects.filter(job__employer=profile).count()
        context['shortlisted_count'] = profile.shortlists.count()
        context['recent_candidates'] = CandidateProfile.objects.filter(is_employer_ready=True).order_by('-kodafriq_verified_score')[:4]
        context['recent_applications'] = Application.objects.filter(
            job__employer=profile
        ).select_related('candidate', 'candidate__user', 'job').order_by('-applied_at')[:5]
        context['recent_shortlists'] = profile.shortlists.select_related(
            'candidate', 'candidate__user'
        ).order_by('-created_at')[:4]
        return context


class StaffDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'dashboard/staff_dashboard.html'

    def test_func(self):
        return self.request.user.is_kodafriq_staff

    def handle_no_permission(self):
        return redirect('dashboard:index')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_candidates'] = User.objects.filter(role=User.Role.CANDIDATE).count()
        context['total_employers'] = User.objects.filter(role=User.Role.EMPLOYER).count()
        context['total_staff'] = User.objects.filter(role__in=[User.Role.STAFF, User.Role.ADMIN]).count()
        context['pending_employers'] = EmployerProfile.objects.filter(approval_status=EmployerProfile.ApprovalStatus.PENDING).count()
        context['recent_users'] = User.objects.order_by('-created_at')[:8]
        return context


from django.http import JsonResponse
from django.views import View
from .models import Notification

class NotificationsListView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/notifications.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        notifications_qs = user.notifications.all()

        filter_type = self.request.GET.get('type', 'all')
        if filter_type == 'unread':
            notifications_qs = notifications_qs.filter(is_read=False)
        elif filter_type == 'certificate':
            notifications_qs = notifications_qs.filter(notification_type=Notification.NotificationType.CERTIFICATE)
        elif filter_type == 'assessment':
            notifications_qs = notifications_qs.filter(notification_type=Notification.NotificationType.ASSESSMENT)
        elif filter_type == 'application':
            notifications_qs = notifications_qs.filter(notification_type=Notification.NotificationType.APPLICATION)
        elif filter_type == 'score':
            notifications_qs = notifications_qs.filter(notification_type=Notification.NotificationType.SCORE_BOOST)

        context['notifications'] = notifications_qs
        context['current_filter'] = filter_type
        context['total_count'] = user.notifications.count()
        context['unread_count'] = user.notifications.filter(is_read=False).count()
        context['cert_count'] = user.notifications.filter(notification_type=Notification.NotificationType.CERTIFICATE).count()
        context['assess_count'] = user.notifications.filter(notification_type=Notification.NotificationType.ASSESSMENT).count()
        context['app_count'] = user.notifications.filter(notification_type=Notification.NotificationType.APPLICATION).count()
        return context


class MarkNotificationReadView(LoginRequiredMixin, View):
    def post(self, request, notification_id):
        notif = get_object_or_404(Notification, id=notification_id, recipient=request.user)
        notif.is_read = True
        notif.save(update_fields=['is_read'])
        
        unread_count = request.user.notifications.filter(is_read=False).count()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            return JsonResponse({'status': 'ok', 'unread_count': unread_count})
        
        if notif.link:
            return redirect(notif.link)
        return redirect('dashboard:notifications')


class MarkAllNotificationsReadView(LoginRequiredMixin, View):
    def post(self, request):
        request.user.notifications.filter(is_read=False).update(is_read=True)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
            return JsonResponse({'status': 'ok', 'unread_count': 0})
        return redirect('dashboard:notifications')
