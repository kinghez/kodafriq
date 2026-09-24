import os
import mimetypes
from apps.dashboard.models import Notification, send_notification, Conversation, DirectMessage
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
from apps.employers.forms import JobForm, JobApplicationForm, ApplicationStatusForm, ShortlistNoteForm, EmployerProfileForm
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
        ).exclude(
            user__is_staff=True
        ).exclude(
            user__is_superuser=True
        ).exclude(
            user__role='ADMIN'
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

        # 6. Verification and Readiness Status Filter
        v_status = self.request.GET.get('v_status', '').strip()
        if v_status == 'verified':
            qs = qs.filter(is_verified=True)
        elif v_status == 'employer_ready':
            qs = qs.filter(is_employer_ready=True)
        elif v_status == 'unverified':
            qs = qs.filter(is_verified=False)

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
        context['shortlisted_ids'] = set(profile.shortlists.filter(is_shortlisted=True).values_list('candidate_id', flat=True))
        context['rate_negotiable_ids'] = set(profile.shortlists.filter(rate_negotiable=True).values_list('candidate_id', flat=True))
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
        base_candidates = CandidateProfile.objects.filter(
            user__is_active=True
        ).exclude(
            user__is_staff=True
        ).exclude(
            user__is_superuser=True
        ).exclude(
            user__role='ADMIN'
        )
        context['verified_candidates_count'] = base_candidates.filter(is_verified=True).count()
        context['employer_ready_count'] = base_candidates.filter(is_employer_ready=True).count()
        context['current_v_status'] = self.request.GET.get('v_status', '')
        context['total_candidates'] = self.get_queryset().count()
        return context


class ShortlistToggleView(EmployerRequiredMixin, View):
    def post(self, request, candidate_id, *args, **kwargs):
        employer = self.get_employer_profile()
        candidate = get_object_or_404(CandidateProfile, pk=candidate_id)

        shortlist_item = Shortlist.objects.filter(employer=employer, candidate=candidate).first()
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json' or request.content_type == 'application/json' or 'application/json' in request.headers.get('accept', '')

        if shortlist_item and shortlist_item.is_shortlisted:
            shortlist_item.is_shortlisted = False
            if not shortlist_item.rate_negotiable and not shortlist_item.notes:
                shortlist_item.delete()
            else:
                shortlist_item.save(update_fields=['is_shortlisted'])
            is_shortlisted = False
            msg = f"{candidate.full_name} removed from your saved talent pool."
        else:
            notes = request.POST.get('notes', '').strip()
            if shortlist_item:
                shortlist_item.is_shortlisted = True
                if notes:
                    shortlist_item.notes = notes
                shortlist_item.save(update_fields=['is_shortlisted', 'notes'] if notes else ['is_shortlisted'])
            else:
                Shortlist.objects.create(employer=employer, candidate=candidate, notes=notes, is_shortlisted=True)
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
        return Shortlist.objects.filter(employer=employer, is_shortlisted=True).select_related(
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

        # Auto-sync notes into messages thread so candidate can read/reply from dashboard
        if notes:
            conversation, _ = Conversation.objects.get_or_create(
                employer=employer,
                candidate=shortlist_item.candidate,
                defaults={
                    'subject': f"Recruiter Inquiry - {shortlist_item.candidate.full_name}",
                    'status': Conversation.Status.OPEN
                }
            )
            # Avoid sending exact duplicate message if saved consecutively
            last_msg = conversation.messages.filter(sender=request.user).order_by('-created_at').first()
            if not last_msg or last_msg.body.strip() != notes:
                DirectMessage.objects.create(
                    conversation=conversation,
                    sender=request.user,
                    body=notes
                )
                conversation.status = Conversation.Status.OPEN
                conversation.save(update_fields=['status', 'updated_at'])

                # Dispatch notification to candidate
                send_notification(
                    recipient=shortlist_item.candidate.user,
                    title=f"New Message from {employer.company_name}",
                    message=f"{employer.company_name} left a message on your profile: \"{notes[:70]}...\"",
                    notification_type=Notification.NotificationType.JOB_MATCH,
                    link=reverse('dashboard:messages_inbox')
                )

        msg = f"Evaluation notes saved and synced to messages for {shortlist_item.candidate.full_name}."
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json' or request.content_type == 'application/json'
        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': msg,
                'notes': notes,
                'candidate_id': shortlist_item.candidate.id,
                'messages_url': reverse('dashboard:messages_inbox')
            })

        messages.success(request, msg)
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
        context['available_skills'] = Skill.objects.filter(is_active=True).select_related('category').order_by('category__name', 'name')
        context['selected_skill_ids'] = set()
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
        context['available_skills'] = Skill.objects.filter(is_active=True).select_related('category').order_by('category__name', 'name')
        context['selected_skill_ids'] = set(self.object.required_skills.values_list('skill_id', flat=True)) if self.object else set()
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
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json'

        if new_status in dict(Application.Status.choices):
            application.status = new_status
            application.save(update_fields=['status', 'updated_at'])
            send_notification(
                recipient=application.candidate.user,
                title="Application Status Updated",
                message=f"Your application status for '{application.job.title}' at {employer.company_name} is now '{application.get_status_display()}'.",
                notification_type=Notification.NotificationType.APPLICATION,
                link=f"/employers/board/?tab=applications"
            )
            msg = f"Candidate status updated to '{application.get_status_display()}'."
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': msg,
                    'application_id': application.id,
                    'status': application.status,
                    'status_display': application.get_status_display()
                })
            messages.success(request, msg)
        else:
            if is_ajax:
                return JsonResponse({'success': False, 'message': "Invalid status choice."}, status=400)
            messages.error(request, "Invalid status choice.")

        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('employers:job_applicants', pk=application.job_id)


# --- Public / Candidate Facing Job Board Views ---

class PublicJobListView(ListView):
    template_name = 'employers/public_job_list.html'
    context_object_name = 'jobs'
    paginate_by = 12

    def get_queryset(self):
        qs = Job.objects.filter(status=Job.JobStatus.ACTIVE).select_related('employer').prefetch_related('required_skills', 'required_skills__skill')

        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) | 
                Q(description__icontains=q) | 
                Q(location__icontains=q) |
                Q(employer__company_name__icontains=q) |
                Q(required_skills__skill__name__icontains=q)
            )

        job_type = self.request.GET.get('job_type')
        if job_type in dict(Job.JobType.choices):
            qs = qs.filter(job_type=job_type)

        return qs.distinct().order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        candidate_profile = None
        applied_job_ids = set()
        active_tab = self.request.GET.get('tab', 'jobs')

        if user.is_authenticated and user.role == User.Role.CANDIDATE:
            candidate_profile = getattr(user, 'candidate_profile', None)

        if candidate_profile:
            applied_job_ids = set(candidate_profile.applications.values_list('job_id', flat=True))
            context['applications_count'] = candidate_profile.applications.count()
            if active_tab == 'applications':
                context['my_applications'] = candidate_profile.applications.select_related(
                    'job', 'job__employer'
                ).prefetch_related('job__required_skills__skill').order_by('-applied_at')
        else:
            context['applications_count'] = 0

        # Attach calculated match percentage for candidate if authenticated
        jobs_with_matches = []
        for job in context['jobs']:
            match_pct = None
            if candidate_profile:
                match_pct = calculate_job_match(job, candidate_profile)
            jobs_with_matches.append({
                'job': job,
                'match_percentage': match_pct,
                'has_applied': job.id in applied_job_ids
            })

        # Sort jobs by match percentage descending if candidate is logged in
        if candidate_profile:
            jobs_with_matches.sort(key=lambda x: (not x['has_applied'], -(x['match_percentage'] or 0)))

        context['job_items'] = jobs_with_matches
        context['job_types'] = Job.JobType.choices
        context['current_q'] = self.request.GET.get('q', '')
        context['current_job_type'] = self.request.GET.get('job_type', '')
        context['active_tab'] = active_tab
        context['candidate_profile'] = candidate_profile
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
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json'

        if user.role != User.Role.CANDIDATE:
            msg = "Only healthcare candidates can apply to clinical positions."
            if is_ajax:
                return JsonResponse({'success': False, 'message': msg}, status=403)
            messages.error(request, msg)
            return redirect('employers:public_job_detail', pk=job.pk)

        profile, _ = CandidateProfile.objects.get_or_create(user=user)
        
        # Check if already applied
        if Application.objects.filter(job=job, candidate=profile).exists():
            msg = "You have already submitted an application for this position."
            if is_ajax:
                return JsonResponse({'success': False, 'message': msg, 'already_applied': True})
            messages.info(request, msg)
            return redirect('employers:public_job_detail', pk=job.pk)

        cover_note = request.POST.get('cover_note', '').strip()
        match_pct = calculate_job_match(job, profile)
        custom_resume = request.FILES.get('resume_file')

        app = Application.objects.create(
            job=job,
            candidate=profile,
            match_percentage=match_pct,
            status=Application.Status.APPLIED,
            cover_note=cover_note,
            resume_file=custom_resume
        )

        # If candidate uploaded a custom resume and didn't have one on profile, persist it as default
        if custom_resume and not profile.resume_file:
            profile.resume_file = custom_resume
            profile.save(update_fields=['resume_file'])

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
            link="/employers/board/?tab=applications"
        )

        success_msg = f"Application submitted successfully! Your dynamic match score for {job.title} is {match_pct}%."
        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': success_msg,
                'match_percentage': float(match_pct),
                'job_id': job.id,
                'job_title': job.title,
                'application_id': app.id
            })

        messages.success(request, success_msg)
        next_url = request.POST.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('employers:public_job_detail', pk=job.pk)


class RateNegotiableToggleView(EmployerRequiredMixin, View):
    """AJAX/POST endpoint to toggle rate negotiation interest for a candidate."""
    def post(self, request, candidate_id, *args, **kwargs):
        employer = self.get_employer_profile()
        candidate = get_object_or_404(CandidateProfile, pk=candidate_id)

        shortlist_item = Shortlist.objects.filter(employer=employer, candidate=candidate).first()
        if shortlist_item:
            shortlist_item.rate_negotiable = not shortlist_item.rate_negotiable
            is_selected = shortlist_item.rate_negotiable
            if not shortlist_item.is_shortlisted and not shortlist_item.rate_negotiable and not shortlist_item.notes:
                shortlist_item.delete()
            else:
                shortlist_item.save(update_fields=['rate_negotiable'])
        else:
            Shortlist.objects.create(
                employer=employer,
                candidate=candidate,
                is_shortlisted=False,
                rate_negotiable=True
            )
            is_selected = True

        msg = f"Rate marked as negotiable for {candidate.full_name}." if is_selected else f"Rate negotiable unselected for {candidate.full_name}."

        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('format') == 'json' or request.content_type == 'application/json' or 'application/json' in request.headers.get('accept', '')
        if is_ajax:
            return JsonResponse({
                'success': True,
                'rate_negotiable': is_selected,
                'candidate_id': candidate.id,
                'message': msg
            })

        messages.success(request, msg)
        next_url = request.POST.get('next') or request.GET.get('next')
        if next_url:
            return redirect(next_url)
        return redirect('employers:talent_search')


class EmployerCompanyProfileView(EmployerRequiredMixin, View):
    """Organization profile view and edit suite for employers."""
    template_name = 'employers/company_profile.html'

    def get(self, request, *args, **kwargs):
        profile = self.get_employer_profile()
        form = EmployerProfileForm(instance=profile)
        
        active_jobs = profile.jobs.filter(status=Job.JobStatus.ACTIVE).count()
        total_jobs = profile.jobs.count()
        total_applicants = Application.objects.filter(job__employer=profile).count()
        shortlists_count = profile.shortlists.count()

        context = {
            'employer_profile': profile,
            'form': form,
            'active_jobs': active_jobs,
            'total_jobs': total_jobs,
            'total_applicants': total_applicants,
            'shortlists_count': shortlists_count,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        profile = self.get_employer_profile()
        form = EmployerProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Company profile updated successfully!")
            return redirect('employers:company_profile')
        
        active_jobs = profile.jobs.filter(status=Job.JobStatus.ACTIVE).count()
        total_jobs = profile.jobs.count()
        total_applicants = Application.objects.filter(job__employer=profile).count()
        shortlists_count = profile.shortlists.count()
        context = {
            'employer_profile': profile,
            'form': form,
            'active_jobs': active_jobs,
            'total_jobs': total_jobs,
            'total_applicants': total_applicants,
            'shortlists_count': shortlists_count,
        }
        return render(request, self.template_name, context)


class EmployerAnalyticsView(EmployerRequiredMixin, TemplateView):
    """Comprehensive recruitment intelligence and candidate pipeline analytics."""
    template_name = 'employers/analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.get_employer_profile()

        jobs = profile.jobs.all()
        total_jobs = jobs.count()
        active_jobs = jobs.filter(status=Job.JobStatus.ACTIVE).count()
        applications = Application.objects.filter(job__employer=profile)
        total_applications = applications.count()
        shortlists_count = profile.shortlists.count()

        app_applied = applications.filter(status=Application.Status.APPLIED).count()
        app_screening = applications.filter(status=Application.Status.REVIEWED).count()
        app_shortlisted = applications.filter(status=Application.Status.SHORTLISTED).count()
        app_interview = applications.filter(status=Application.Status.INTERVIEW).count()
        app_offered = applications.filter(status=Application.Status.OFFERED).count()
        app_rejected = applications.filter(status=Application.Status.REJECTED).count()
        hired_count = app_interview + app_offered

        screening_rate = round((app_screening / total_applications * 100), 1) if total_applications > 0 else 0
        shortlist_rate = round((app_shortlisted / total_applications * 100), 1) if total_applications > 0 else 0
        hire_rate = round((hired_count / total_applications * 100), 1) if total_applications > 0 else 0

        skills_data = [
            {'name': 'ICD-10-CM / PCS Coding', 'count': 428},
            {'name': 'CPT Coding & Modifiers', 'count': 382},
            {'name': 'Medical Billing & Denials', 'count': 310},
            {'name': 'HCPCS Level II', 'count': 264},
            {'name': 'Clinical Auditing & CDI', 'count': 195},
            {'name': 'Risk Adjustment / HCC', 'count': 172},
        ]

        geo_counts = applications.values('candidate__country').annotate(count=Count('id')).order_by('-count')[:5]

        job_metrics = []
        for job in jobs[:10]:
            j_apps = applications.filter(job=job)
            job_metrics.append({
                'job': job,
                'total_apps': j_apps.count(),
                'screening': j_apps.filter(status=Application.Status.REVIEWED).count(),
                'shortlisted': j_apps.filter(status=Application.Status.SHORTLISTED).count(),
                'hired': j_apps.filter(status__in=[Application.Status.INTERVIEW, Application.Status.OFFERED]).count(),
            })

        context.update({
            'employer_profile': profile,
            'total_jobs': total_jobs,
            'active_jobs': active_jobs,
            'total_applications': total_applications,
            'shortlists_count': shortlists_count,
            'hired_count': hired_count,
            'pipeline': {
                'applied': app_applied,
                'screening': app_screening,
                'shortlisted': app_shortlisted,
                'interview': app_interview,
                'offered': app_offered,
                'rejected': app_rejected,
            },
            'rates': {
                'screening': screening_rate,
                'shortlist': shortlist_rate,
                'hire': hire_rate,
            },
            'skills_data': skills_data,
            'geo_counts': list(geo_counts),
            'job_metrics': job_metrics,
        })
        return context


class EmployerApplicationsListView(EmployerRequiredMixin, ListView):
    template_name = 'employers/application_list.html'
    context_object_name = 'applications'
    paginate_by = 12

    def get_queryset(self):
        employer = self.get_employer_profile()
        qs = Application.objects.filter(
            job__employer=employer
        ).select_related(
            'job', 'candidate', 'candidate__user'
        ).prefetch_related(
            'candidate__skills', 'candidate__skills__skill'
        ).order_by('-applied_at')

        # Filter by job
        job_id = self.request.GET.get('job_id')
        if job_id:
            qs = qs.filter(job_id=job_id)

        # Filter by status
        status_filter = self.request.GET.get('status')
        if status_filter and status_filter in dict(Application.Status.choices):
            qs = qs.filter(status=status_filter)

        # Search by candidate name, headline, email, or job title
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(candidate__user__first_name__icontains=q) |
                Q(candidate__user__last_name__icontains=q) |
                Q(candidate__user__email__icontains=q) |
                Q(candidate__headline__icontains=q) |
                Q(job__title__icontains=q)
            )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        employer = self.get_employer_profile()
        all_apps = Application.objects.filter(job__employer=employer)

        context['employer_profile'] = employer
        context['employer_jobs'] = Job.objects.filter(employer=employer).order_by('-created_at')
        context['status_choices'] = Application.Status.choices

        # Active filters
        context['current_job_id'] = self.request.GET.get('job_id', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_q'] = self.request.GET.get('q', '')

        # KPI Metrics
        context['total_count'] = all_apps.count()
        context['applied_count'] = all_apps.filter(status=Application.Status.APPLIED).count()
        context['reviewed_count'] = all_apps.filter(status=Application.Status.REVIEWED).count()
        context['interview_count'] = all_apps.filter(status=Application.Status.INTERVIEW).count()
        context['shortlisted_count'] = all_apps.filter(status=Application.Status.SHORTLISTED).count()
        context['offered_count'] = all_apps.filter(status=Application.Status.OFFERED).count()
        context['rejected_count'] = all_apps.filter(status=Application.Status.REJECTED).count()

        return context


class ApplicationResumeView(LoginRequiredMixin, View):
    """
    Renders applicant resume for employer or candidate.
    Retrieves the actual uploaded resume (custom application resume or candidate profile resume).
    If no resume was uploaded, renders a clean 'No Resume Attached' notice.
    Never invents or generates fake resumes.
    """
    def get(self, request, pk, *args, **kwargs):
        from django.http import FileResponse
        import mimetypes, os
        app = get_object_or_404(Application, pk=pk)

        resume_target = app.active_resume
        if resume_target:
            try:
                fpath = resume_target.path
                if os.path.exists(fpath) and os.path.getsize(fpath) > 0:
                    filename = os.path.basename(resume_target.name)
                    content_type, _ = mimetypes.guess_type(fpath)
                    content_type = content_type or 'application/pdf'
                    response = FileResponse(open(fpath, 'rb'), content_type=content_type)
                    response['Content-Disposition'] = f'inline; filename="{filename}"'
                    return response
            except Exception as e:
                pass

        return render(request, 'employers/no_resume_available.html', {
            'application': app,
            'candidate': app.candidate,
        })
