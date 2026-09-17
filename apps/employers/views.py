from apps.dashboard.models import Notification, send_notification
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.db.models import Q, Count, Avg

from apps.accounts.models import User, CandidateProfile, EmployerProfile
from apps.skills.models import Skill, CandidateSkill, SkillCategory
from apps.employers.models import Job, JobRequiredSkill, Application, Shortlist
from apps.employers.forms import JobForm, JobApplicationForm, ApplicationStatusForm, ShortlistNoteForm
from apps.employers.services import calculate_job_match


class EmployerRequiredMixin(LoginRequiredMixin):
    """Ensures user has an Employer or Staff role."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in [User.Role.EMPLOYER, User.Role.STAFF, User.Role.ADMIN]:
            messages.warning(request, "This area is restricted to healthcare employers and partners.")
            return redirect('dashboard:index')
        return super().dispatch(request, *args, **kwargs)

    def get_employer_profile(self):
        profile, _ = EmployerProfile.objects.get_or_create(
            user=self.request.user,
            defaults={'company_name': f"{self.request.user.get_full_name() or self.request.user.username} Healthcare"}
        )
        return profile


class TalentSearchView(EmployerRequiredMixin, ListView):
    template_name = 'employers/talent_search.html'
    context_object_name = 'candidates'
    paginate_by = 12

    def get_queryset(self):
        qs = CandidateProfile.objects.filter(
            user__is_active=True
        ).select_related('user').prefetch_related('skills', 'skills__skill', 'certifications', 'work_experiences')

        # 1. Text Search
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(user__first_name__icontains=q) |
                Q(user__last_name__icontains=q) |
                Q(headline__icontains=q) |
                Q(bio__icontains=q) |
                Q(location__icontains=q)
            )

        # 2. Min Kodafriq Verified Score
        min_score = self.request.GET.get('min_score')
        if min_score:
            try:
                score_val = float(min_score)
                qs = qs.filter(kodafriq_verified_score__gte=score_val)
            except ValueError:
                pass

        # 3. Clinical Skill & Verification Tier Filter
        skill_id = self.request.GET.get('skill_id')
        tier = self.request.GET.get('tier', '').strip()
        if skill_id:
            skill_filter = Q(skills__skill_id=skill_id)
            if tier in [CandidateSkill.VerificationStatus.ASSESSED, CandidateSkill.VerificationStatus.KODAFRIQ_VERIFIED]:
                skill_filter &= Q(skills__status=tier)
            elif tier == 'ASSESSED_OR_HIGHER':
                skill_filter &= Q(skills__status__in=[
                    CandidateSkill.VerificationStatus.ASSESSED,
                    CandidateSkill.VerificationStatus.KODAFRIQ_VERIFIED
                ])
            qs = qs.filter(skill_filter)

        # 4. Minimum Experience Years
        min_exp = self.request.GET.get('min_exp')
        if min_exp:
            try:
                exp_val = int(min_exp)
                qs = qs.filter(years_of_experience__gte=exp_val)
            except ValueError:
                pass

        # 5. Location
        location = self.request.GET.get('location', '').strip()
        if location:
            qs = qs.filter(location__icontains=location)

        # 6. Sorting
        sort_by = self.request.GET.get('sort', '-kodafriq_verified_score')
        if sort_by in ['-kodafriq_verified_score', 'kodafriq_verified_score', '-years_of_experience', 'hourly_rate', '-created_at']:
            qs = qs.order_by(sort_by)
        else:
            qs = qs.order_by('-kodafriq_verified_score')

        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.get_employer_profile()
        context['employer_profile'] = profile
        context['shortlisted_ids'] = set(profile.shortlists.values_list('candidate_id', flat=True))
        context['skills'] = Skill.objects.filter(is_active=True).order_by('category__name', 'name')
        context['skill_categories'] = SkillCategory.objects.all()
        
        # Preserve active filter parameters
        context['current_q'] = self.request.GET.get('q', '')
        context['current_min_score'] = self.request.GET.get('min_score', '')
        context['current_skill_id'] = self.request.GET.get('skill_id', '')
        context['current_tier'] = self.request.GET.get('tier', '')
        context['current_min_exp'] = self.request.GET.get('min_exp', '')
        context['current_location'] = self.request.GET.get('location', '')
        context['current_sort'] = self.request.GET.get('sort', '-kodafriq_verified_score')
        context['total_candidates'] = self.get_queryset().count()
        return context


class ShortlistToggleView(EmployerRequiredMixin, View):
    def post(self, request, candidate_id, *args, **kwargs):
        employer = self.get_employer_profile()
        candidate = get_object_or_404(CandidateProfile, pk=candidate_id)

        shortlist_item = Shortlist.objects.filter(employer=employer, candidate=candidate).first()
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json'

        if shortlist_item:
            shortlist_item.delete()
            is_shortlisted = False
            msg = f"{candidate.full_name} removed from your saved talent pool."
        else:
            notes = request.POST.get('notes', '').strip()
            Shortlist.objects.create(employer=employer, candidate=candidate, notes=notes)
            is_shortlisted = True
            msg = f"{candidate.full_name} added to your shortlisted talent pool!"

        if is_ajax:
            return JsonResponse({
                'success': True,
                'is_shortlisted': is_shortlisted,
                'message': msg,
                'candidate_id': candidate.id,
            })

        messages.success(request, msg)
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('employers:shortlist')


class ShortlistListView(EmployerRequiredMixin, ListView):
    template_name = 'employers/shortlist_list.html'
    context_object_name = 'shortlist_items'

    def get_queryset(self):
        employer = self.get_employer_profile()
        return Shortlist.objects.filter(employer=employer).select_related(
            'candidate', 'candidate__user'
        ).prefetch_related('candidate__skills', 'candidate__skills__skill').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employer_profile'] = self.get_employer_profile()
        return context


class ShortlistNoteUpdateView(EmployerRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        employer = self.get_employer_profile()
        shortlist_item = get_object_or_404(Shortlist, pk=pk, employer=employer)
        notes = request.POST.get('notes', '').strip()
        shortlist_item.notes = notes
        shortlist_item.save(update_fields=['notes'])
        messages.success(request, "Evaluation notes saved.")
        return redirect('employers:shortlist')


class JobListView(EmployerRequiredMixin, ListView):
    template_name = 'employers/job_list.html'
    context_object_name = 'jobs'

    def get_queryset(self):
        employer = self.get_employer_profile()
        return Job.objects.filter(employer=employer).annotate(
            applicant_count=Count('applications')
        ).prefetch_related('required_skills', 'required_skills__skill').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employer = self.get_employer_profile()
        context['employer_profile'] = employer
        context['active_jobs_count'] = employer.jobs.filter(status=Job.JobStatus.ACTIVE).count()
        context['total_applicants_count'] = Application.objects.filter(job__employer=employer).count()
        return context


class JobCreateView(EmployerRequiredMixin, CreateView):
    model = Job
    form_class = JobForm
    template_name = 'employers/job_form.html'
    success_url = reverse_lazy('employers:job_list')

    def form_valid(self, form):
        form.instance.employer = self.get_employer_profile()
        messages.success(self.request, "Clinical job requisition created successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employer_profile'] = self.get_employer_profile()
        context['is_edit'] = False
        return context


class JobUpdateView(EmployerRequiredMixin, UpdateView):
    model = Job
    form_class = JobForm
    template_name = 'employers/job_form.html'
    success_url = reverse_lazy('employers:job_list')

    def get_queryset(self):
        return Job.objects.filter(employer=self.get_employer_profile())

    def form_valid(self, form):
        messages.success(self.request, "Job requisition updated successfully.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employer_profile'] = self.get_employer_profile()
        context['is_edit'] = True
        return context


class JobApplicantListView(EmployerRequiredMixin, DetailView):
    model = Job
    template_name = 'employers/job_applicants.html'
    context_object_name = 'job'

    def get_queryset(self):
        return Job.objects.filter(employer=self.get_employer_profile())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.object
        applications = job.applications.select_related(
            'candidate', 'candidate__user'
        ).prefetch_related('candidate__skills', 'candidate__skills__skill').order_by('-match_percentage', '-applied_at')

        # Filter by status if requested
        status_filter = self.request.GET.get('status')
        if status_filter and status_filter in dict(Application.Status.choices):
            applications = applications.filter(status=status_filter)

        context['applications'] = applications
        context['current_status'] = status_filter
        context['status_choices'] = Application.Status.choices
        context['employer_profile'] = self.get_employer_profile()
        return context


class ApplicantStatusUpdateView(EmployerRequiredMixin, View):
    def post(self, request, application_id, *args, **kwargs):
        employer = self.get_employer_profile()
        application = get_object_or_404(Application, id=application_id, job__employer=employer)
        new_status = request.POST.get('status')

        if new_status in dict(Application.Status.choices):
            application.status = new_status
            application.save(update_fields=['status', 'updated_at'])
            send_notification(
                recipient=application.candidate.user,
                title="Application Status Updated",
                message=f"Your application status for '{application.job.title}' at {employer.company_name} is now '{application.get_status_display()}'.",
                notification_type=Notification.NotificationType.APPLICATION,
                link=f"/employers/board/{application.job.id}/"
            )
            messages.success(request, f"Candidate status updated to '{application.get_status_display()}'.")
        else:
            messages.error(request, "Invalid status choice.")

        return redirect('employers:job_applicants', pk=application.job_id)


# --- Public / Candidate Facing Job Board Views ---

class PublicJobListView(ListView):
    template_name = 'employers/public_job_list.html'
    context_object_name = 'jobs'
    paginate_by = 10

    def get_queryset(self):
        qs = Job.objects.filter(status=Job.JobStatus.ACTIVE).select_related('employer').prefetch_related('required_skills', 'required_skills__skill')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(employer__company_name__icontains=q))

        job_type = self.request.GET.get('job_type')
        if job_type in dict(Job.JobType.choices):
            qs = qs.filter(job_type=job_type)

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        candidate_profile = None

        if user.is_authenticated and user.role == User.Role.CANDIDATE:
            candidate_profile = getattr(user, 'candidate_profile', None)

        # Attach calculated match percentage for candidate if authenticated
        jobs_with_matches = []
        applied_job_ids = set()
        if candidate_profile:
            applied_job_ids = set(candidate_profile.applications.values_list('job_id', flat=True))

        for job in context['jobs']:
            match_pct = None
            if candidate_profile:
                match_pct = calculate_job_match(job, candidate_profile)
            jobs_with_matches.append({
                'job': job,
                'match_percentage': match_pct,
                'has_applied': job.id in applied_job_ids
            })

        context['job_items'] = jobs_with_matches
        context['job_types'] = Job.JobType.choices
        context['current_q'] = self.request.GET.get('q', '')
        context['current_job_type'] = self.request.GET.get('job_type', '')
        return context


class PublicJobDetailView(DetailView):
    model = Job
    template_name = 'employers/public_job_detail.html'
    context_object_name = 'job'

    def get_queryset(self):
        return Job.objects.filter(status=Job.JobStatus.ACTIVE).select_related('employer').prefetch_related('required_skills', 'required_skills__skill')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        job = self.object
        user = self.request.user
        candidate_profile = None
        has_applied = False
        match_percentage = None

        if user.is_authenticated and user.role == User.Role.CANDIDATE:
            candidate_profile = getattr(user, 'candidate_profile', None)
            if candidate_profile:
                has_applied = job.applications.filter(candidate=candidate_profile).exists()
                match_percentage = calculate_job_match(job, candidate_profile)

        context['candidate_profile'] = candidate_profile
        context['has_applied'] = has_applied
        context['match_percentage'] = match_percentage
        context['application_form'] = JobApplicationForm()
        return context


class JobApplyView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        job = get_object_or_404(Job, pk=pk, status=Job.JobStatus.ACTIVE)
        user = request.user

        if user.role != User.Role.CANDIDATE:
            messages.error(request, "Only healthcare candidates can apply to clinical positions.")
            return redirect('employers:public_job_detail', pk=job.pk)

        profile, _ = CandidateProfile.objects.get_or_create(user=user)
        
        # Check if already applied
        if Application.objects.filter(job=job, candidate=profile).exists():
            messages.info(request, "You have already submitted an application for this position.")
            return redirect('employers:public_job_detail', pk=job.pk)

        cover_note = request.POST.get('cover_note', '').strip()
        match_pct = calculate_job_match(job, profile)

        Application.objects.create(
            job=job,
            candidate=profile,
            match_percentage=match_pct,
            status=Application.Status.APPLIED,
            cover_note=cover_note
        )

        send_notification(
            recipient=job.employer.user,
            title="New Clinical Candidate Application",
            message=f"{profile.full_name} applied for {job.title} with a match score of {match_pct}%.",
            notification_type=Notification.NotificationType.APPLICATION,
            link=f"/employers/jobs/{job.id}/applicants/"
        )
        send_notification(
            recipient=user,
            title="Application Submitted",
            message=f"Your application for '{job.title}' at {job.employer.company_name} was received (Match Score: {match_pct}%).",
            notification_type=Notification.NotificationType.APPLICATION,
            link=f"/employers/board/{job.id}/"
        )

        messages.success(
            request,
            f"Application submitted successfully! Your dynamic match score for {job.title} is {match_pct}%."
        )
        return redirect('employers:public_job_detail', pk=job.pk)
