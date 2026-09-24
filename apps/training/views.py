from django.urls import reverse
from apps.dashboard.models import Notification, send_notification
import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q

from apps.accounts.models import User, CandidateProfile
from apps.skills.models import Skill, SkillCategory
from apps.training.models import TrainingProgram, ProgramModule, TrainingEnrolment, ModuleProgress, CertificateTemplateConfig
from apps.scoring.services import calculate_candidate_score


class TrainingProgramListView(ListView):
    model = TrainingProgram
    template_name = 'training/program_list.html'
    context_object_name = 'programs'

    def get_queryset(self):
        qs = TrainingProgram.objects.filter(is_active=True).prefetch_related('modules', 'skills_covered')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(instructor__icontains=q))

        skill_id = self.request.GET.get('skill')
        if skill_id:
            qs = qs.filter(skills_covered__id=skill_id)

        return list(qs.order_by('id'))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        programs = context['programs']
        completed_count = 0
        in_progress_count = 0

        if user.is_authenticated and user.role == User.Role.CANDIDATE:
            profile = getattr(user, 'candidate_profile', None)
            if profile:
                user_enrolments = TrainingEnrolment.objects.filter(
                    candidate=profile
                ).select_related('program').prefetch_related('module_progresses')
                enrolments_map = {e.program_id: e for e in user_enrolments}

                for p in programs:
                    enr = enrolments_map.get(p.id)
                    p.user_enrolment = enr
                    if enr:
                        if enr.status == TrainingEnrolment.EnrolmentStatus.COMPLETED:
                            completed_count += 1
                        elif enr.status == TrainingEnrolment.EnrolmentStatus.IN_PROGRESS:
                            in_progress_count += 1
            else:
                for p in programs:
                    p.user_enrolment = None
        else:
            for p in programs:
                p.user_enrolment = None

        context.update({
            'completed_count': completed_count,
            'in_progress_count': in_progress_count,
            'skills': Skill.objects.filter(training_programs__isnull=False).distinct(),
            'current_q': self.request.GET.get('q', ''),
            'current_skill': self.request.GET.get('skill', ''),
        })
        return context


class TrainingProgramDetailView(DetailView):
    model = TrainingProgram
    template_name = 'training/program_detail.html'
    context_object_name = 'program'

    def get_queryset(self):
        return TrainingProgram.objects.filter(is_active=True).prefetch_related('modules', 'skills_covered')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        program = self.object
        user = self.request.user
        enrolment = None

        if user.is_authenticated and user.role == User.Role.CANDIDATE:
            profile = getattr(user, 'candidate_profile', None)
            if profile:
                enrolment = TrainingEnrolment.objects.filter(
                    candidate=profile, program=program
                ).prefetch_related('module_progresses').first()

        modules = list(program.modules.all().order_by('order'))
        if enrolment:
            progress_map = {mp.module_id: mp.is_completed for mp in enrolment.module_progresses.all()}
            for m in modules:
                m.is_completed = progress_map.get(m.id, False)

        context.update({
            'enrolment': enrolment,
            'modules': modules,
            'skills': program.skills_covered.all(),
        })
        return context


class TrainingEnrollView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        program = get_object_or_404(TrainingProgram, pk=pk, is_active=True)
        user = request.user

        if user.role != User.Role.CANDIDATE:
            messages.warning(request, "Only healthcare candidates can enroll in accredited clinical programs.")
            return redirect('training:detail', pk=program.pk)

        profile, _ = CandidateProfile.objects.get_or_create(user=user)
        enrolment, created = TrainingEnrolment.objects.get_or_create(
            candidate=profile,
            program=program,
            defaults={'status': TrainingEnrolment.EnrolmentStatus.IN_PROGRESS}
        )

        # Initialize module progress records for all program modules
        modules = program.modules.all()
        for mod in modules:
            ModuleProgress.objects.get_or_create(enrolment=enrolment, module=mod)

        if created:
            messages.success(request, f"Enrolled in {program.title}! Begin your clinical training.")
        return redirect('training:learn', enrolment_id=enrolment.id)


class TrainingLearnView(LoginRequiredMixin, View):
    template_name = 'training/program_learn.html'

    def get(self, request, enrolment_id, *args, **kwargs):
        profile = getattr(request.user, 'candidate_profile', None)
        if not profile:
            return redirect('training:index')

        enrolment = get_object_or_404(
            TrainingEnrolment.objects.select_related('program').prefetch_related('program__modules', 'module_progresses'),
            id=enrolment_id,
            candidate=profile
        )

        modules = list(enrolment.program.modules.all().order_by('order'))
        if not modules:
            messages.info(request, "No modules currently published for this program.")
            return redirect('training:detail', pk=enrolment.program.id)

        progress_map = {mp.module_id: mp for mp in enrolment.module_progresses.all()}
        for m in modules:
            m.user_progress = progress_map.get(m.id)

        # Select requested module or first incomplete module
        module_id = request.GET.get('module')
        current_module = None

        if module_id:
            try:
                mod_pk = int(module_id)
                current_module = next((m for m in modules if m.id == mod_pk), None)
            except ValueError:
                pass

        if not current_module:
            for m in modules:
                mp = progress_map.get(m.id)
                if not mp or not mp.is_completed:
                    current_module = m
                    break
            if not current_module:
                current_module = modules[0]

        current_progress = progress_map.get(current_module.id)

        # Determine next and previous modules
        current_idx = modules.index(current_module)
        prev_module = modules[current_idx - 1] if current_idx > 0 else None
        next_module = modules[current_idx + 1] if current_idx < len(modules) - 1 else None

        context = {
            'enrolment': enrolment,
            'program': enrolment.program,
            'modules': modules,
            'current_module': current_module,
            'current_progress': current_progress,
            'prev_module': prev_module,
            'next_module': next_module,
        }
        return render(request, self.template_name, context)


class ModuleCompleteView(LoginRequiredMixin, View):
    def post(self, request, enrolment_id, module_id, *args, **kwargs):
        profile = getattr(request.user, 'candidate_profile', None)
        if not profile:
            return redirect('training:index')

        enrolment = get_object_or_404(TrainingEnrolment, id=enrolment_id, candidate=profile)
        module = get_object_or_404(ProgramModule, id=module_id, program=enrolment.program)

        mp, _ = ModuleProgress.objects.get_or_create(enrolment=enrolment, module=module)
        mp.is_completed = True
        mp.completed_at = timezone.now()
        mp.save()

        # Check if all program modules are now complete
        total_modules = enrolment.program.modules.count()
        completed_modules = enrolment.module_progresses.filter(is_completed=True).count()

        if completed_modules >= total_modules and total_modules > 0:
            if enrolment.status != TrainingEnrolment.EnrolmentStatus.COMPLETED:
                enrolment.status = TrainingEnrolment.EnrolmentStatus.COMPLETED
                if not enrolment.certificate_id:
                    year = timezone.now().year
                    enrolment.certificate_id = f"KODA-TRN-{year}-{uuid.uuid4().hex[:8].upper()}"
                enrolment.completed_at = timezone.now()
                enrolment.save()

                # Recalculate candidate's verified score (15% training weight!)
                calculate_candidate_score(profile)

                send_notification(
                    recipient=request.user,
                    title="Accredited Certificate Earned!",
                    message=f"Congratulations! You completed '{enrolment.program.title}' and earned Certificate {enrolment.certificate_id}. Your Verified Score has been boosted!",
                    notification_type=Notification.NotificationType.CERTIFICATE,
                    link=f"/training/certificate/{enrolment.certificate_id}/"
                )

                messages.success(
                    request,
                    f"Outstanding Achievement! You have completed '{enrolment.program.title}' and earned your accredited Kodafriq Certificate! "
                    f"Your Kodafriq Verified Score has been boosted."
                )
                return redirect('training:certificate', certificate_id=enrolment.certificate_id)

        # Redirect to next incomplete module if available
        next_incomplete = enrolment.module_progresses.filter(is_completed=False).select_related('module').order_by('module__order').first()
        if next_incomplete:
            return redirect(f"/training/enrolment/{enrolment.id}/learn/?module={next_incomplete.module.id}")

        return redirect('training:learn', enrolment_id=enrolment.id)


class AdminCertificatePreviewView(LoginRequiredMixin, View):
    template_name = 'training/certificate.html'

    def dispatch(self, request, *args, **kwargs):
        user = request.user
        if not (user.is_authenticated and (user.is_staff or getattr(user, 'role', None) == 'ADMIN' or getattr(user, 'is_kodafriq_staff', False))):
            messages.error(request, "Access restricted to Kodafriq Clinical Administrators.")
            return redirect('training:index')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, program_id=None, enrolment_id=None, *args, **kwargs):
        cert_config = CertificateTemplateConfig.get_solo()
        from types import SimpleNamespace

        if enrolment_id:
            enrolment = get_object_or_404(
                TrainingEnrolment.objects.select_related('program', 'candidate', 'candidate__user').prefetch_related('program__skills_covered'),
                id=enrolment_id
            )
            is_preview = enrolment.status != TrainingEnrolment.EnrolmentStatus.COMPLETED
            if not enrolment.certificate_id:
                enrolment.certificate_id = f"KODA-TRN-PREVIEW-{timezone.now().year}"
            if not enrolment.completed_at:
                enrolment.completed_at = timezone.now()

            context = {
                'enrolment': enrolment,
                'program': enrolment.program,
                'candidate': enrolment.candidate,
                'cert_config': cert_config,
                'is_preview': is_preview,
                'skills': enrolment.program.skills_covered.all(),
                'return_url': '/admin/training/certificatetemplateconfig/',
                'return_label': 'Return to Template Config',
            }
            return render(request, self.template_name, context)

        # Global or Program-specific preview
        if program_id:
            program = get_object_or_404(
                TrainingProgram.objects.prefetch_related('skills_covered', 'modules'),
                id=program_id
            )
        else:
            program = TrainingProgram.objects.prefetch_related('skills_covered').first()
            if not program:
                class MockSkills:
                    def all(self):
                        return [
                            SimpleNamespace(name="ICD-10-CM Coding"),
                            SimpleNamespace(name="MS-DRG Auditing"),
                            SimpleNamespace(name="Clinical Documentation Improvement")
                        ]
                program = SimpleNamespace(
                    id=None,
                    title="Advanced Inpatient ICD-10-CM & MS-DRG Clinical Optimization",
                    instructor=cert_config.signatory_name,
                    instructor_title=cert_config.signatory_title,
                    certificate_subtitle=cert_config.certificate_title,
                    accreditation_statement=cert_config.accreditation_subtitle,
                    skills_covered=MockSkills()
                )

        mock_candidate = getattr(request.user, 'candidate_profile', None)
        if not mock_candidate:
            class MockCandidate:
                full_name = request.user.get_full_name() or "Solomon Itie"
                id = None
            candidate_obj = MockCandidate()
        else:
            candidate_obj = mock_candidate

        enrolment_obj = SimpleNamespace(
            certificate_id=f"KODA-TRN-2026-C562CAF4",
            completed_at=timezone.now(),
            candidate=candidate_obj,
            program=program
        )
        skills = program.skills_covered.all() if hasattr(program, 'skills_covered') else []

        context = {
            'enrolment': enrolment_obj,
            'program': program,
            'candidate': candidate_obj,
            'cert_config': cert_config,
            'is_preview': True,
            'skills': skills,
            'return_url': '/admin/training/certificatetemplateconfig/',
            'return_label': 'Return to Template Config',
        }
        return render(request, self.template_name, context)


class TrainingCertificateView(DetailView):
    model = TrainingEnrolment
    template_name = 'training/certificate.html'
    context_object_name = 'enrolment'
    slug_field = 'certificate_id'
    slug_url_kwarg = 'certificate_id'

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and (user.is_staff or getattr(user, 'role', None) == 'ADMIN' or getattr(user, 'is_kodafriq_staff', False)):
            return TrainingEnrolment.objects.select_related('program', 'candidate', 'candidate__user').prefetch_related('program__skills_covered')
        return TrainingEnrolment.objects.filter(
            status=TrainingEnrolment.EnrolmentStatus.COMPLETED
        ).select_related('program', 'candidate', 'candidate__user').prefetch_related('program__skills_covered')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enrolment = self.object
        context['candidate'] = enrolment.candidate
        context['program'] = enrolment.program
        context['cert_config'] = CertificateTemplateConfig.get_solo()
        context['verified_score'] = enrolment.candidate.kodafriq_verified_score

        # Smart Return Navigation
        return_to = self.request.GET.get('return_to')
        candidate_id = self.request.GET.get('candidate_id')
        user = self.request.user
        is_employer = user.is_authenticated and (getattr(user, 'role', None) == 'EMPLOYER' or hasattr(user, 'employer_profile'))
        
        if return_to == 'talent_card' or (is_employer and enrolment and enrolment.candidate):
            cand_id = candidate_id or (enrolment.candidate.id if enrolment.candidate else None)
            if cand_id:
                context['return_url'] = reverse('dashboard:talent_card_public', kwargs={'pk': cand_id})
                context['return_label'] = "Back to Candidate Talent Card"
        elif return_to == 'applications':
            context['return_url'] = reverse('employers:application_list')
            context['return_label'] = "Back to Applications"
        elif return_to == 'talent_search':
            context['return_url'] = reverse('employers:talent_search')
            context['return_label'] = "Back to Candidates"
        elif user.is_authenticated:
            context['return_url'] = reverse('training:index')
            context['return_label'] = "Back to Training Programs"
        else:
            context['return_url'] = reverse('core:home')
            context['return_label'] = "Return to Kodafriq Home"

        return context


class TrainingCertificatePrintView(TrainingCertificateView):
    template_name = 'training/certificate_standalone_print.html'


class AdminCertificatePrintPreviewView(AdminCertificatePreviewView):
    template_name = 'training/certificate_standalone_print.html'
