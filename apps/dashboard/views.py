from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse

from apps.accounts.models import User, CandidateProfile, EmployerProfile

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
        
        # Calculate dynamic profile completion percentage
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
        ]
        completion_pct = int((sum(completion_fields) / len(completion_fields)) * 100)

        context['profile'] = profile
        context['completion_pct'] = max(completion_pct, 25) # minimum 25% for newly registered
        context['verified_score'] = profile.kodafriq_verified_score
        context['certifications'] = profile.certifications.all()[:4]
        context['work_experiences'] = profile.work_experiences.all()[:3]
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
        context['profile'] = profile
        context['total_candidates'] = CandidateProfile.objects.count()
        context['verified_candidates'] = CandidateProfile.objects.filter(is_employer_ready=True).count()
        context['recent_candidates'] = CandidateProfile.objects.order_by('-created_at')[:4]
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
