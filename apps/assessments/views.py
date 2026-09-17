from apps.dashboard.models import Notification, send_notification
import decimal
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.db import models

from apps.accounts.models import CandidateProfile
from apps.skills.models import SkillCategory, Skill, CandidateSkill
from apps.assessments.models import Assessment, Question, AnswerChoice, AssessmentAttempt, CandidateResponse
from apps.scoring.services import calculate_candidate_score


class AssessmentListView(LoginRequiredMixin, TemplateView):
    template_name = 'assessments/assessment_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile, _ = CandidateProfile.objects.get_or_create(user=user)

        category_id = self.request.GET.get('category')
        assessments_qs = Assessment.objects.filter(is_active=True).select_related('category', 'primary_skill').prefetch_related('questions')

        if category_id:
            assessments_qs = assessments_qs.filter(category_id=category_id)

        # Attach candidate's best attempt to each assessment
        assessment_cards = []
        for a in assessments_qs:
            attempts = profile.assessment_attempts.filter(assessment=a).order_by('-score_percentage', '-completed_at')
            best_attempt = attempts.first()
            has_passed = attempts.filter(passed=True).exists()
            assessment_cards.append({
                'assessment': a,
                'question_count': a.questions.count(),
                'best_attempt': best_attempt,
                'has_passed': has_passed,
                'total_attempts': attempts.count(),
            })

        # Overall Stats
        all_attempts = profile.assessment_attempts.filter(status='COMPLETED')
        total_completed = all_attempts.count()
        passed_count = all_attempts.filter(passed=True).values('assessment').distinct().count()
        avg_score = all_attempts.aggregate(models.Avg('score_percentage'))['score_percentage__avg'] or 0

        context.update({
            'profile': profile,
            'assessment_cards': assessment_cards,
            'categories': SkillCategory.objects.all(),
            'selected_category': int(category_id) if category_id and category_id.isdigit() else None,
            'total_completed': total_completed,
            'passed_count': passed_count,
            'avg_score': round(avg_score, 1),
            'verified_score': profile.kodafriq_verified_score,
        })
        return context


class AssessmentDetailView(LoginRequiredMixin, DetailView):
    model = Assessment
    template_name = 'assessments/assessment_detail.html'
    context_object_name = 'assessment'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = CandidateProfile.objects.get_or_create(user=self.request.user)
        attempts = profile.assessment_attempts.filter(assessment=self.object).order_by('-completed_at')
        best_attempt = attempts.order_by('-score_percentage').first()
        has_passed = attempts.filter(passed=True).exists()
        in_progress_attempt = attempts.filter(status=AssessmentAttempt.AttemptStatus.IN_PROGRESS).first()

        context.update({
            'profile': profile,
            'attempts': attempts[:5],
            'best_attempt': best_attempt,
            'has_passed': has_passed,
            'in_progress_attempt': in_progress_attempt,
            'question_count': self.object.questions.count(),
        })
        return context


class AssessmentStartView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        assessment = get_object_or_404(Assessment, pk=pk, is_active=True)

        # Check for existing IN_PROGRESS attempt
        attempt = profile.assessment_attempts.filter(
            assessment=assessment,
            status=AssessmentAttempt.AttemptStatus.IN_PROGRESS
        ).order_by('-started_at').first()

        now = timezone.now()
        if attempt:
            # Check if timed out
            deadline = attempt.started_at + timedelta(minutes=assessment.duration_minutes)
            if now > deadline:
                attempt.status = AssessmentAttempt.AttemptStatus.TIMED_OUT
                attempt.completed_at = deadline
                attempt.save(update_fields=['status', 'completed_at'])
                attempt = None

        if not attempt:
            attempt = AssessmentAttempt.objects.create(
                candidate=profile,
                assessment=assessment,
                status=AssessmentAttempt.AttemptStatus.IN_PROGRESS,
                total_questions=assessment.questions.count(),
                started_at=now
            )

        return redirect('assessments:runner', attempt_id=attempt.id)


class AssessmentRunnerView(LoginRequiredMixin, View):
    template_name = 'assessments/assessment_runner.html'

    def get(self, request, attempt_id, *args, **kwargs):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        attempt = get_object_or_404(
            AssessmentAttempt.objects.select_related('assessment', 'assessment__category'),
            id=attempt_id,
            candidate=profile
        )

        if attempt.status != AssessmentAttempt.AttemptStatus.IN_PROGRESS:
            return redirect('assessments:results', attempt_id=attempt.id)

        # Compute remaining time in seconds
        now = timezone.now()
        deadline = attempt.started_at + timedelta(minutes=attempt.assessment.duration_minutes)
        remaining_seconds = max(0, int((deadline - now).total_seconds()))

        if remaining_seconds <= 0:
            # Auto-submit if timed out
            return redirect('assessments:submit', attempt_id=attempt.id)

        questions = attempt.assessment.questions.prefetch_related('choices').order_by('order', 'id')
        
        # Load existing responses if candidate refreshed
        existing_responses = {
            r.question_id: r.selected_choice_id 
            for r in attempt.responses.all()
        }

        context = {
            'attempt': attempt,
            'assessment': attempt.assessment,
            'questions': questions,
            'remaining_seconds': remaining_seconds,
            'duration_minutes': attempt.assessment.duration_minutes,
            'existing_responses': existing_responses,
        }
        return render(request, self.template_name, context)


class AssessmentSubmitView(LoginRequiredMixin, View):
    def post(self, request, attempt_id, *args, **kwargs):
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        attempt = get_object_or_404(AssessmentAttempt, id=attempt_id, candidate=profile)

        if attempt.status != AssessmentAttempt.AttemptStatus.IN_PROGRESS:
            return redirect('assessments:results', attempt_id=attempt.id)

        questions = attempt.assessment.questions.prefetch_related('choices')
        total_questions = questions.count()
        correct_count = 0

        # Record candidate responses and grade
        for q in questions:
            choice_id = request.POST.get(f'question_{q.id}')
            selected_choice = None
            is_correct = False

            if choice_id:
                try:
                    selected_choice = q.choices.get(id=choice_id)
                    is_correct = selected_choice.is_correct
                except AnswerChoice.DoesNotExist:
                    pass

            if is_correct:
                correct_count += 1

            CandidateResponse.objects.update_or_create(
                attempt=attempt,
                question=q,
                defaults={
                    'selected_choice': selected_choice,
                    'is_correct': is_correct
                }
            )

        # Calculate final percentage
        score_pct = Decimal('0.00')
        if total_questions > 0:
            score_pct = Decimal(str(round((correct_count / total_questions) * 100, 2)))

        passed = score_pct >= attempt.assessment.pass_mark_percentage

        attempt.status = AssessmentAttempt.AttemptStatus.COMPLETED
        attempt.total_questions = total_questions
        attempt.correct_answers = correct_count
        attempt.score_percentage = score_pct
        attempt.passed = passed
        attempt.completed_at = timezone.now()
        attempt.save()

        # Automatic 3-Tier Skill Promotion to ASSESSED
        if passed and attempt.assessment.primary_skill:
            skill = attempt.assessment.primary_skill
            cand_skill, _ = CandidateSkill.objects.get_or_create(
                candidate=profile,
                skill=skill,
                defaults={'proficiency': CandidateSkill.ProficiencyLevel.INTERMEDIATE}
            )
            cand_skill.status = CandidateSkill.VerificationStatus.ASSESSED
            cand_skill.verification_feedback = f"Passed {attempt.assessment.title} with {score_pct}%"
            cand_skill.verified_at = timezone.now()
            cand_skill.save()

        # Recalculate dynamic Kodafriq Verified Score
        calculate_candidate_score(profile)

        if passed:
            send_notification(
                recipient=request.user,
                title="Assessment Passed & Skill Verified",
                message=f"Outstanding! You scored {score_pct}% and passed {attempt.assessment.title}! Your verified score has been boosted.",
                notification_type=Notification.NotificationType.ASSESSMENT,
                link=f"/assessments/attempt/{attempt.id}/results/"
            )
            messages.success(
                request,
                f"Outstanding! You scored {score_pct}% and passed the {attempt.assessment.title}! "
                f"Your skill has been elevated to Tier 2 (Assessed) and your Verified Score has increased."
            )
        else:
            messages.info(
                request,
                f"Assessment completed with a score of {score_pct}%. "
                f"The passing mark is {attempt.assessment.pass_mark_percentage}%. You may review the clinical rationales and retake the test."
            )

        return redirect('assessments:results', attempt_id=attempt.id)


class AssessmentResultView(LoginRequiredMixin, DetailView):
    model = AssessmentAttempt
    template_name = 'assessments/assessment_results.html'
    context_object_name = 'attempt'
    pk_url_kwarg = 'attempt_id'

    def get_queryset(self):
        profile, _ = CandidateProfile.objects.get_or_create(user=self.request.user)
        return AssessmentAttempt.objects.filter(candidate=profile).select_related('assessment', 'assessment__category')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        attempt = self.object
        profile = attempt.candidate

        # Load responses with question and selected choice details
        responses = attempt.responses.select_related('question', 'selected_choice').prefetch_related('question__choices').order_by('question__order', 'question__id')

        context.update({
            'profile': profile,
            'assessment': attempt.assessment,
            'responses': responses,
            'verified_score': profile.kodafriq_verified_score,
        })
        return context
