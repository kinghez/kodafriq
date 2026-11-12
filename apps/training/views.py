import uuid
import json
import csv
from decimal import Decimal
from django.urls import reverse
from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Q, F, Sum, Count
from django.db.models.functions import TruncDate
from django.db import transaction
from django.http import JsonResponse, HttpResponse

from apps.accounts.models import User, CandidateProfile
from apps.skills.models import Skill, SkillCategory
from apps.dashboard.models import Notification, send_notification
from apps.scoring.services import calculate_candidate_score
from apps.billing.models import PaymentGatewayConfig

from .models import (
    TrainingProgram, ProgramModule, TrainingEnrolment, ModuleProgress,
    CertificateTemplateConfig, TrainingMaterial, TrainingCoupon,
    CouponRedemption, ModuleQuizQuestion, ModuleQuizOption, ModuleQuizAttempt,
    TrainingPayment
)


def convert_to_ghs(amount, currency):
    """Converts course tuition into Ghana Cedis (GHS) for Paystack Ghana Mobile Money/Card rail."""
    rate_map = {
        'GHS': Decimal('1.00'),
        'USD': Decimal('15.50'),
        'EUR': Decimal('16.80'),
        'GBP': Decimal('19.60'),
    }
    rate = rate_map.get(str(currency or 'USD').upper(), Decimal('15.50'))
    return (Decimal(str(amount or '0.00')) * rate).quantize(Decimal('0.01'))


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
        return TrainingProgram.objects.filter(is_active=True).prefetch_related('modules', 'skills_covered', 'creator')

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

        gateway_cfg = PaymentGatewayConfig.get_active()
        amount_ghs = convert_to_ghs(program.price, program.currency) if program.is_paid else Decimal('0.00')

        context.update({
            'enrolment': enrolment,
            'modules': modules,
            'skills': program.skills_covered.all(),
            'gateway_cfg': gateway_cfg,
            'paystack_enabled': gateway_cfg.paystack_enabled,
            'flutterwave_enabled': gateway_cfg.flutterwave_enabled,
            'flutterwave_public_key': gateway_cfg.get_flutterwave_public_key(),
            'paystack_public_key': gateway_cfg.get_paystack_public_key(),
            'amount_ghs': amount_ghs,
            'amount_kobo': int(amount_ghs * Decimal('100.00')),
        })
        return context


class ValidateCouponView(LoginRequiredMixin, View):
    """
    AJAX endpoint to validate promotional coupon codes in real-time.
    """
    def post(self, request, pk, *args, **kwargs):
        program = get_object_or_404(TrainingProgram, pk=pk, is_active=True)
        code = request.POST.get('code', '').strip().upper()
        if not code:
            return JsonResponse({'valid': False, 'message': 'Please enter a coupon promo code.'})

        coupon = TrainingCoupon.objects.filter(code=code).first()
        if not coupon:
            return JsonResponse({'valid': False, 'message': f"Promotional code '{code}' is not valid or unrecognized."})

        profile = getattr(request.user, 'candidate_profile', None)
        is_valid, msg, discount_amount, final_price = coupon.validate_for_candidate(program, profile)

        if not is_valid:
            return JsonResponse({'valid': False, 'message': msg})

        is_free_after_discount = (final_price <= Decimal('0.00'))
        final_price_ghs = convert_to_ghs(final_price, program.currency)
        return JsonResponse({
            'valid': True,
            'code': coupon.code,
            'message': f"Promotional code '{coupon.code}' applied successfully!",
            'discount_type': coupon.discount_type,
            'discount_value': str(coupon.discount_value),
            'discount_amount': f"{discount_amount:.2f}",
            'final_price': f"{final_price:.2f}",
            'final_price_ghs': f"{final_price_ghs:.2f}",
            'currency': program.currency,
            'is_100_percent_free': is_free_after_discount
        })


class TrainingCheckoutInitiateView(LoginRequiredMixin, View):
    """
    Prepares a paid course enrollment transaction and returns gateway configurations
    for Paystack or Flutterwave.
    """
    def post(self, request, pk):
        program = get_object_or_404(TrainingProgram, pk=pk, is_active=True)
        user = request.user

        if user.role != User.Role.CANDIDATE:
            return JsonResponse({'status': 'error', 'message': 'Only registered candidates can enroll.'}, status=403)

        profile, _ = CandidateProfile.objects.get_or_create(user=user)
        if TrainingEnrolment.objects.filter(candidate=profile, program=program).exists():
            return JsonResponse({'status': 'error', 'message': 'You are already enrolled in this program.'}, status=400)

        # Parse request payload
        try:
            if request.content_type == 'application/json':
                payload = json.loads(request.body.decode('utf-8'))
            else:
                payload = request.POST.dict()
        except Exception:
            payload = {}

        coupon_code = payload.get('coupon_code', '').strip().upper()
        gateway = payload.get('gateway', 'FLUTTERWAVE').upper()
        if gateway not in ['FLUTTERWAVE', 'PAYSTACK']:
            gateway = 'FLUTTERWAVE'

        gross_price = program.price if program.is_paid else Decimal('0.00')
        discount_amount = Decimal('0.00')
        final_price = gross_price
        coupon_obj = None

        if coupon_code:
            coupon = TrainingCoupon.objects.filter(code=coupon_code).first()
            if not coupon:
                return JsonResponse({'status': 'error', 'message': f"Promotional code '{coupon_code}' is invalid."}, status=400)
            is_valid, err_msg, disc, fin = coupon.validate_for_candidate(program, profile)
            if not is_valid:
                return JsonResponse({'status': 'error', 'message': err_msg}, status=400)
            coupon_obj = coupon
            discount_amount = disc
            final_price = fin

        # 100% Free / Fully Discounted enrollment
        if final_price <= Decimal('0.00'):
            with transaction.atomic():
                enrolment = TrainingEnrolment.objects.create(
                    candidate=profile,
                    program=program,
                    status=TrainingEnrolment.EnrolmentStatus.IN_PROGRESS,
                    amount_paid=Decimal('0.00'),
                    coupon_used=coupon_obj
                )
                if coupon_obj:
                    TrainingCoupon.objects.filter(id=coupon_obj.id).update(times_redeemed=F('times_redeemed') + 1)
                    coupon_obj.refresh_from_db()
                    CouponRedemption.objects.create(
                        coupon=coupon_obj,
                        candidate=profile,
                        program=program,
                        enrolment=enrolment,
                        original_price=gross_price,
                        discount_amount=discount_amount,
                        final_price_paid=Decimal('0.00')
                    )

                for mod in program.modules.all():
                    ModuleProgress.objects.get_or_create(enrolment=enrolment, module=mod)

                payment_ref = f"KODA-FREE-{uuid.uuid4().hex[:8].upper()}"
                TrainingPayment.objects.create(
                    payment_ref=payment_ref,
                    program=program,
                    candidate=profile,
                    enrolment=enrolment,
                    creator=program.creator,
                    coupon=coupon_obj,
                    gross_amount=gross_price,
                    discount_amount=discount_amount,
                    net_amount_paid=Decimal('0.00'),
                    currency=program.currency,
                    creator_share_percent=program.creator_share_percentage,
                    creator_earnings=Decimal('0.00'),
                    platform_fee=Decimal('0.00'),
                    creator_payout_status=TrainingPayment.CreatorPayoutStatus.NOT_APPLICABLE,
                    gateway=TrainingPayment.Gateway.COUPON_FREE if coupon_obj else TrainingPayment.Gateway.MANUAL,
                    status=TrainingPayment.PaymentStatus.SUCCESSFUL,
                    settled_at=timezone.now(),
                    ip_address=request.META.get('REMOTE_ADDR')
                )

            messages.success(request, f"🎉 100% discount applied! You are enrolled in {program.title}.")
            return JsonResponse({
                'status': 'success',
                'is_free': True,
                'redirect_url': reverse('training:learn', kwargs={'enrolment_id': enrolment.id})
            })

        # Initiate Paid Gateway Transaction
        gateway_cfg = PaymentGatewayConfig.get_active()
        if not gateway_cfg.paystack_enabled and not gateway_cfg.flutterwave_enabled:
            return JsonResponse({
                'status': 'error',
                'message': 'No payment gateway is currently enabled on Kodafriq. Please contact support.'
            }, status=400)

        if gateway == 'PAYSTACK' and not gateway_cfg.paystack_enabled:
            return JsonResponse({
                'status': 'error',
                'message': 'Paystack payment rail is currently disabled.'
            }, status=400)

        if gateway == 'FLUTTERWAVE' and not gateway_cfg.flutterwave_enabled:
            return JsonResponse({
                'status': 'error',
                'message': 'Flutterwave payment rail is currently disabled.'
            }, status=400)

        payment_ref = f"KODA-TRN-{timezone.now().year}-{uuid.uuid4().hex[:8].upper()}"
        amount_ghs = convert_to_ghs(final_price, program.currency)
        amount_kobo = int(amount_ghs * Decimal('100.00'))

        payment = TrainingPayment.objects.create(
            payment_ref=payment_ref,
            program=program,
            candidate=profile,
            creator=program.creator,
            coupon=coupon_obj,
            gross_amount=gross_price,
            discount_amount=discount_amount,
            net_amount_paid=final_price,
            currency=program.currency,
            creator_share_percent=program.creator_share_percentage,
            gateway=gateway,
            status=TrainingPayment.PaymentStatus.PENDING,
            raw_response={'charged_ghs_equivalent': str(amount_ghs)} if gateway == 'PAYSTACK' else {},
            ip_address=request.META.get('REMOTE_ADDR')
        )

        customer_name = profile.full_name or user.get_full_name() or user.username
        customer_email = user.email

        return JsonResponse({
            'status': 'success',
            'is_free': False,
            'payment_ref': payment_ref,
            'amount': float(final_price),
            'amount_ghs': float(amount_ghs),
            'amount_kobo': amount_kobo,
            'currency': program.currency,
            'paystack_currency': 'GHS',
            'gateway': gateway,
            'customer_name': customer_name,
            'customer_email': customer_email,
            'program_title': program.title,
            'flutterwave_public_key': gateway_cfg.get_flutterwave_public_key(),
            'paystack_public_key': gateway_cfg.get_paystack_public_key(),
        })


class TrainingCheckoutVerifyView(LoginRequiredMixin, View):
    """
    Verifies transaction from Paystack or Flutterwave and activates course enrollment.
    """
    def post(self, request, pk):
        program = get_object_or_404(TrainingProgram, pk=pk, is_active=True)
        user = request.user
        profile = getattr(user, 'candidate_profile', None)
        if not profile:
            return JsonResponse({'status': 'error', 'message': 'Candidate profile not found.'}, status=403)

        try:
            if request.content_type == 'application/json':
                payload = json.loads(request.body.decode('utf-8'))
            else:
                payload = request.POST.dict()
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Invalid payload.'}, status=400)

        payment_ref = payload.get('payment_ref', '').strip()
        gateway = payload.get('gateway', 'FLUTTERWAVE').upper()
        transaction_id = payload.get('transaction_id') or payload.get('reference') or payload.get('flw_ref') or payment_ref

        payment = TrainingPayment.objects.filter(
            payment_ref=payment_ref,
            candidate=profile,
            program=program
        ).first()

        if not payment:
            return JsonResponse({'status': 'error', 'message': 'Payment transaction reference not found.'}, status=404)

        if payment.status == TrainingPayment.PaymentStatus.SUCCESSFUL:
            enr_id = payment.enrolment_id or TrainingEnrolment.objects.filter(candidate=profile, program=program).values_list('id', flat=True).first()
            return JsonResponse({
                'status': 'success',
                'message': 'Payment already verified!',
                'redirect_url': reverse('training:learn', kwargs={'enrolment_id': enr_id})
            })

        verified = False
        gateway_data = {}

        if gateway == 'PAYSTACK':
            from apps.billing.services.paystack_ghana import PaystackGhanaService
            pstk = PaystackGhanaService()
            verified, gateway_data = pstk.verify_transaction(transaction_id)
        else:
            from apps.billing.services.flutterwave import FlutterwaveService
            flw = FlutterwaveService()
            verified, gateway_data = flw.verify_transaction(transaction_id)

        if not verified:
            err = gateway_data if isinstance(gateway_data, str) else "Payment gateway could not verify transaction."
            payment.status = TrainingPayment.PaymentStatus.FAILED
            payment.raw_response = {"error": err}
            payment.save()
            return JsonResponse({'status': 'error', 'message': err}, status=400)

        # Mark Payment Successful & Activate Course Enrollment
        with transaction.atomic():
            enrolment, _ = TrainingEnrolment.objects.get_or_create(
                candidate=profile,
                program=program,
                defaults={
                    'status': TrainingEnrolment.EnrolmentStatus.IN_PROGRESS,
                    'amount_paid': payment.net_amount_paid,
                    'coupon_used': payment.coupon,
                    'payment_reference': payment_ref
                }
            )

            # Mark Payment Successful with Creator & Platform calculations
            payment.enrolment = enrolment
            payment.mark_successful(gateway_ref=transaction_id, raw_data=gateway_data)

            # Record coupon redemption if coupon was used
            if payment.coupon:
                TrainingCoupon.objects.filter(id=payment.coupon.id).update(times_redeemed=F('times_redeemed') + 1)
                CouponRedemption.objects.create(
                    coupon=payment.coupon,
                    candidate=profile,
                    program=program,
                    enrolment=enrolment,
                    original_price=payment.gross_amount,
                    discount_amount=payment.discount_amount,
                    final_price_paid=payment.net_amount_paid
                )

            # Initialize module progress
            for mod in program.modules.all():
                ModuleProgress.objects.get_or_create(enrolment=enrolment, module=mod)

        # Notify Student
        send_notification(
            recipient=user,
            title="Course Tuition Confirmed!",
            message=f"Your payment of {payment.currency} {payment.net_amount_paid:.2f} for '{program.title}' was confirmed. You now have full access to the classroom.",
            notification_type=Notification.NotificationType.SYSTEM,
            link=reverse('training:learn', kwargs={'enrolment_id': enrolment.id})
        )

        # Notify Course Creator (if assigned)
        if program.creator:
            send_notification(
                recipient=program.creator,
                title="New Paid Student Enrollment!",
                message=f"{profile.full_name} enrolled in your course '{program.title}'. Creator earnings of ${payment.creator_earnings:.2f} credited to your ledger.",
                notification_type=Notification.NotificationType.SYSTEM,
                link='/admin/training/trainingpayment/'
            )

        messages.success(request, f"🎉 Payment confirmed! Welcome to '{program.title}'. Begin your clinical training.")
        return JsonResponse({
            'status': 'success',
            'message': 'Payment confirmed successfully!',
            'redirect_url': reverse('training:learn', kwargs={'enrolment_id': enrolment.id})
        })


class TrainingEnrollView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        program = get_object_or_404(TrainingProgram, pk=pk, is_active=True)
        user = request.user

        if user.role != User.Role.CANDIDATE:
            messages.warning(request, "Only registered healthcare candidates can enroll in accredited programs.")
            return redirect('training:detail', pk=program.pk)

        profile, _ = CandidateProfile.objects.get_or_create(user=user)

        # Check existing enrolment
        existing = TrainingEnrolment.objects.filter(candidate=profile, program=program).first()
        if existing:
            messages.info(request, f"You are already enrolled in {program.title}.")
            return redirect('training:learn', enrolment_id=existing.id)

        coupon_code = request.POST.get('coupon_code', '').strip().upper()
        amount_to_pay = program.price if program.is_paid else Decimal('0.00')
        coupon_obj = None

        if program.is_paid:
            if coupon_code:
                coupon = TrainingCoupon.objects.filter(code=coupon_code).first()
                if not coupon:
                    messages.error(request, f"Coupon code '{coupon_code}' is invalid or unrecognized.")
                    return redirect('training:detail', pk=program.pk)

                is_valid, err_msg, discount, final_price = coupon.validate_for_candidate(program, profile)
                if not is_valid:
                    messages.error(request, err_msg)
                    return redirect('training:detail', pk=program.pk)

                coupon_obj = coupon
                amount_to_pay = final_price
            else:
                messages.error(request, f"This is a paid training program ({program.formatted_price}). Please choose a payment method below or enter a coupon code.")
                return redirect('training:detail', pk=program.pk)

        # If amount to pay is 0.00 (either free course or 100% coupon discount)
        if amount_to_pay <= Decimal('0.00'):
            with transaction.atomic():
                enrolment = TrainingEnrolment.objects.create(
                    candidate=profile,
                    program=program,
                    status=TrainingEnrolment.EnrolmentStatus.IN_PROGRESS,
                    amount_paid=Decimal('0.00'),
                    coupon_used=coupon_obj
                )

                if coupon_obj:
                    # Increment atomic redemption counter
                    TrainingCoupon.objects.filter(id=coupon_obj.id).update(times_redeemed=F('times_redeemed') + 1)
                    coupon_obj.refresh_from_db()
                    CouponRedemption.objects.create(
                        coupon=coupon_obj,
                        candidate=profile,
                        program=program,
                        enrolment=enrolment,
                        original_price=program.price,
                        discount_amount=program.price - amount_to_pay,
                        final_price_paid=amount_to_pay
                    )

                # Initialize module progress records for all program modules
                for mod in program.modules.all():
                    ModuleProgress.objects.get_or_create(enrolment=enrolment, module=mod)

                payment_ref = f"KODA-FREE-{uuid.uuid4().hex[:8].upper()}"
                TrainingPayment.objects.create(
                    payment_ref=payment_ref,
                    program=program,
                    candidate=profile,
                    enrolment=enrolment,
                    creator=program.creator,
                    coupon=coupon_obj,
                    gross_amount=program.price if program.is_paid else Decimal('0.00'),
                    discount_amount=program.price if program.is_paid else Decimal('0.00'),
                    net_amount_paid=Decimal('0.00'),
                    currency=program.currency,
                    creator_share_percent=program.creator_share_percentage,
                    creator_earnings=Decimal('0.00'),
                    platform_fee=Decimal('0.00'),
                    creator_payout_status=TrainingPayment.CreatorPayoutStatus.NOT_APPLICABLE,
                    gateway=TrainingPayment.Gateway.COUPON_FREE if coupon_obj else TrainingPayment.Gateway.MANUAL,
                    status=TrainingPayment.PaymentStatus.SUCCESSFUL,
                    settled_at=timezone.now(),
                    ip_address=request.META.get('REMOTE_ADDR')
                )

            if coupon_obj:
                messages.success(request, f"🎉 Promotional code '{coupon_obj.code}' applied! 100% discount granted. Welcome to {program.title}!")
            else:
                messages.success(request, f"Enrolled in {program.title}! Begin your clinical training.")
            return redirect('training:learn', enrolment_id=enrolment.id)

        messages.warning(request, f"Tuition payment required ({program.currency} {amount_to_pay:.2f}). Please select Paystack or Flutterwave below.")
        return redirect('training:detail', pk=program.pk)


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

        module_materials = list(current_module.materials.all().order_by('order')) if current_module else []
        program_materials = list(enrolment.program.materials.filter(module__isnull=True).order_by('order'))

        # Module Quiz Data
        quiz_questions = []
        latest_attempt = None
        if current_module and current_module.requires_quiz:
            quiz_questions = list(current_module.quiz_questions.prefetch_related('options').order_by('order'))
            latest_attempt = ModuleQuizAttempt.objects.filter(enrolment=enrolment, module=current_module).order_by('-attempted_at').first()

        context = {
            'enrolment': enrolment,
            'program': enrolment.program,
            'modules': modules,
            'current_module': current_module,
            'current_progress': current_progress,
            'prev_module': prev_module,
            'next_module': next_module,
            'module_materials': module_materials,
            'program_materials': program_materials,
            'quiz_questions': quiz_questions,
            'latest_attempt': latest_attempt,
            'is_course_completed': (enrolment.status == TrainingEnrolment.EnrolmentStatus.COMPLETED),
        }
        return render(request, self.template_name, context)


class ModuleQuizSubmitView(LoginRequiredMixin, View):
    def post(self, request, enrolment_id, module_id, *args, **kwargs):
        profile = getattr(request.user, 'candidate_profile', None)
        if not profile:
            return redirect('training:index')

        enrolment = get_object_or_404(TrainingEnrolment, id=enrolment_id, candidate=profile)
        module = get_object_or_404(ProgramModule, id=module_id, program=enrolment.program)

        questions = list(module.quiz_questions.prefetch_related('options').all())
        if not questions:
            messages.info(request, "This module does not contain any quiz questions.")
            return redirect(f"/training/enrolment/{enrolment.id}/learn/?module={module.id}")

        total_questions = len(questions)
        correct_count = 0

        for q in questions:
            selected_option_id = request.POST.get(f"question_{q.id}")
            if selected_option_id:
                try:
                    opt = q.options.filter(id=int(selected_option_id)).first()
                    if opt and opt.is_correct:
                        correct_count += 1
                except (ValueError, TypeError):
                    pass

        score_pct = Decimal(str(round((correct_count / total_questions) * 100, 2)))
        passed = (score_pct >= Decimal(str(module.quiz_pass_percentage)))

        # Record attempt
        ModuleQuizAttempt.objects.create(
            enrolment=enrolment,
            module=module,
            score_percentage=score_pct,
            total_questions=total_questions,
            correct_answers=correct_count,
            passed=passed
        )

        mp, _ = ModuleProgress.objects.get_or_create(enrolment=enrolment, module=module)
        mp.quiz_score = score_pct

        if passed:
            mp.quiz_passed = True
            mp.is_completed = True
            if not mp.completed_at:
                mp.completed_at = timezone.now()
            mp.save()

            messages.success(
                request,
                f"🎉 Outstanding! You passed the {module.title} Knowledge Check with {score_pct}% ({correct_count}/{total_questions} correct). Required: {module.quiz_pass_percentage}%."
            )

            # Check if all modules are complete
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

                    # Recalculate verified score
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
                        f"🎓 Extraordinary Achievement! You completed all curriculum modules in '{enrolment.program.title}' and earned your accredited Kodafriq Certificate!"
                    )
                    return redirect('training:certificate', certificate_id=enrolment.certificate_id)

            # Find next incomplete module
            next_incomplete = enrolment.module_progresses.filter(is_completed=False).select_related('module').order_by('module__order').first()
            if next_incomplete:
                return redirect(f"/training/enrolment/{enrolment.id}/learn/?module={next_incomplete.module.id}")

            return redirect(f"/training/enrolment/{enrolment.id}/learn/?module={module.id}")
        else:
            mp.quiz_passed = False
            mp.save()
            messages.warning(
                request,
                f"Quiz Score: {score_pct}% ({correct_count}/{total_questions} correct). You need at least {module.quiz_pass_percentage}% to pass. Please review the clinical guidelines and retake the quiz."
            )
            return redirect(f"/training/enrolment/{enrolment.id}/learn/?module={module.id}")


class ModuleCompleteView(LoginRequiredMixin, View):
    def post(self, request, enrolment_id, module_id, *args, **kwargs):
        profile = getattr(request.user, 'candidate_profile', None)
        if not profile:
            return redirect('training:index')

        enrolment = get_object_or_404(TrainingEnrolment, id=enrolment_id, candidate=profile)
        module = get_object_or_404(ProgramModule, id=module_id, program=enrolment.program)
        mp, _ = ModuleProgress.objects.get_or_create(enrolment=enrolment, module=module)

        # Check if quiz gate is active
        if module.requires_quiz and not mp.quiz_passed:
            messages.warning(
                request,
                f"Module '{module.title}' requires passing the Knowledge Check quiz (minimum {module.quiz_pass_percentage}%) before advancing."
            )
            return redirect(f"/training/enrolment/{enrolment.id}/learn/?module={module.id}")

        mp.is_completed = True
        if not mp.completed_at:
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
                    f"Outstanding Achievement! You have completed '{enrolment.program.title}' and earned your accredited Kodafriq Certificate!"
                )
                return redirect('training:certificate', certificate_id=enrolment.certificate_id)

        next_incomplete = enrolment.module_progresses.filter(is_completed=False).select_related('module').order_by('module__order').first()
        if next_incomplete:
            return redirect(f"/training/enrolment/{enrolment.id}/learn/?module={next_incomplete.module.id}")

        return redirect('training:learn', enrolment_id=enrolment.id)


def _get_filtered_training_payments(request):
    """
    Shared filter helper for training revenue analytics and CSV exports.
    Supports filtering by course, staff creator, payment status, and date range.
    """
    payments = TrainingPayment.objects.select_related(
        'program', 'candidate', 'candidate__user', 'creator', 'coupon'
    ).order_by('-created_at')

    course_id = request.GET.get('course', '').strip()
    creator_id = request.GET.get('creator', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    if course_id.isdigit():
        payments = payments.filter(program_id=int(course_id))
    if creator_id.isdigit():
        payments = payments.filter(creator_id=int(creator_id))
    if status_filter in [c[0] for c in TrainingPayment.PaymentStatus.choices]:
        payments = payments.filter(status=status_filter)

    parsed_from = parse_date(date_from) if date_from else None
    parsed_to = parse_date(date_to) if date_to else None
    if parsed_from:
        payments = payments.filter(created_at__date__gte=parsed_from)
    if parsed_to:
        payments = payments.filter(created_at__date__lte=parsed_to)

    filter_state = {
        'course': course_id,
        'creator': creator_id,
        'status': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'has_filters': any([course_id, creator_id, status_filter, date_from, date_to]),
    }
    return payments, filter_state


class StaffTrainingRevenueAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    Staff / Superuser Executive Revenue & Course Creator Payout Ledger.
    Displays course sales, daily breakdowns, Kodafriq platform retention,
    creator earnings split, and pending vs. settled creator disbursements.
    """
    template_name = 'training/admin_revenue_analytics.html'

    def test_func(self):
        user = self.request.user
        return bool(user.is_authenticated and getattr(user, 'is_kodafriq_staff', False))

    def handle_no_permission(self):
        messages.error(self.request, "Access restricted to Kodafriq Management & Financial Administrators.")
        return redirect('dashboard:staff')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        payments, filter_state = _get_filtered_training_payments(self.request)
        successful_payments = payments.filter(status=TrainingPayment.PaymentStatus.SUCCESSFUL)

        # KPI Stats (respecting active filters)
        total_gross = successful_payments.aggregate(s=Sum('net_amount_paid'))['s'] or Decimal('0.00')
        total_creator_earnings = successful_payments.aggregate(s=Sum('creator_earnings'))['s'] or Decimal('0.00')
        total_platform_fee = successful_payments.aggregate(s=Sum('platform_fee'))['s'] or Decimal('0.00')

        pending_creator_payout = successful_payments.filter(
            creator_payout_status=TrainingPayment.CreatorPayoutStatus.PENDING
        ).aggregate(s=Sum('creator_earnings'))['s'] or Decimal('0.00')

        settled_creator_payout = successful_payments.filter(
            creator_payout_status=TrainingPayment.CreatorPayoutStatus.PAID
        ).aggregate(s=Sum('creator_earnings'))['s'] or Decimal('0.00')

        total_paid_enrollments = successful_payments.filter(net_amount_paid__gt=0).count()
        total_free_enrollments = successful_payments.filter(net_amount_paid=0).count()

        # Daily Breakdown by Course & Date
        daily_breakdown = (
            successful_payments
            .annotate(pay_date=TruncDate('created_at'))
            .values(
                'pay_date',
                'program__id',
                'program__title',
                'currency',
                'creator__first_name',
                'creator__last_name',
                'creator__email',
            )
            .annotate(
                tx_count=Count('id'),
                daily_gross=Sum('net_amount_paid'),
                daily_creator_cut=Sum('creator_earnings'),
                daily_platform_fee=Sum('platform_fee'),
            )
            .order_by('-pay_date', 'program__title')[:30]
        )

        # Course-by-Course Breakdown (respecting date filters if provided)
        courses = TrainingProgram.objects.select_related('creator').all()
        course_breakdown = []
        for c in courses:
            c_payments = successful_payments.filter(program=c)
            if filter_state['course'] and str(c.id) != filter_state['course']:
                continue
            gross = c_payments.aggregate(s=Sum('net_amount_paid'))['s'] or Decimal('0.00')
            creator_cut = c_payments.aggregate(s=Sum('creator_earnings'))['s'] or Decimal('0.00')
            pending = c_payments.filter(creator_payout_status=TrainingPayment.CreatorPayoutStatus.PENDING).aggregate(s=Sum('creator_earnings'))['s'] or Decimal('0.00')
            paid_enr = c_payments.filter(net_amount_paid__gt=0).count()
            free_enr = c_payments.filter(net_amount_paid=0).count()
            course_breakdown.append({
                'program': c,
                'creator': c.creator,
                'paid_enrollments': paid_enr,
                'free_enrollments': free_enr,
                'gross_revenue': gross,
                'creator_earnings': creator_cut,
                'pending_payout': pending,
            })

        # Creator Payout Rollup
        creators = User.objects.filter(
            Q(created_training_programs__isnull=False) | Q(training_creator_earnings__isnull=False)
        ).distinct()
        creator_summary = []
        for cr in creators:
            if filter_state['creator'] and str(cr.id) != filter_state['creator']:
                continue
            cr_payments = successful_payments.filter(creator=cr)
            earned = cr_payments.aggregate(s=Sum('creator_earnings'))['s'] or Decimal('0.00')
            pending = cr_payments.filter(creator_payout_status=TrainingPayment.CreatorPayoutStatus.PENDING).aggregate(s=Sum('creator_earnings'))['s'] or Decimal('0.00')
            settled = cr_payments.filter(creator_payout_status=TrainingPayment.CreatorPayoutStatus.PAID).aggregate(s=Sum('creator_earnings'))['s'] or Decimal('0.00')
            creator_summary.append({
                'creator': cr,
                'courses_count': cr.created_training_programs.count(),
                'total_earned': earned,
                'pending_payout': pending,
                'settled_payout': settled,
            })

        context.update({
            'kpis': {
                'total_gross': f"{total_gross:.2f}",
                'total_platform_fee': f"{total_platform_fee:.2f}",
                'total_creator_earnings': f"{total_creator_earnings:.2f}",
                'pending_creator_payout': f"{pending_creator_payout:.2f}",
                'settled_creator_payout': f"{settled_creator_payout:.2f}",
                'total_paid_enrollments': total_paid_enrollments,
                'total_free_enrollments': total_free_enrollments,
            },
            'daily_breakdown': daily_breakdown,
            'course_breakdown': course_breakdown,
            'creator_summary': creator_summary,
            'recent_payments': payments[:50],
            'all_courses': courses,
            'all_creators': creators,
            'filters': filter_state,
            'export_querystring': self.request.META.get('QUERY_STRING', ''),
        })
        return context


class StaffTrainingRevenueExportView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Exports clean CSV audit ledger of course tuition payments and creator earnings.
    """
    def test_func(self):
        user = self.request.user
        return bool(user.is_authenticated and getattr(user, 'is_kodafriq_staff', False))

    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="kodafriq_training_revenue_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Payment Ref', 'Date (UTC)', 'Course Title', 'Candidate Name', 'Candidate Email',
            'Creator Name', 'Creator Email', 'Gross Price', 'Discount', 'Net Paid',
            'Currency', 'Creator Share %', 'Creator Earnings', 'Platform Fee',
            'Gateway', 'Gateway Ref', 'Payment Status', 'Creator Payout Status', 'Creator Paid Date'
        ])

        payments, _ = _get_filtered_training_payments(request)

        for p in payments:
            cand_user = p.candidate.user if p.candidate else None
            creator_name = p.creator.get_full_name() if p.creator else 'Unassigned'
            creator_email = p.creator.email if p.creator else '—'
            writer.writerow([
                p.payment_ref,
                p.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                p.program.title if p.program else '',
                p.candidate.full_name if p.candidate else '',
                cand_user.email if cand_user else '',
                creator_name,
                creator_email,
                p.gross_amount,
                p.discount_amount,
                p.net_amount_paid,
                p.currency,
                f"{p.creator_share_percent}%",
                p.creator_earnings,
                p.platform_fee,
                p.gateway,
                p.gateway_reference,
                p.status,
                p.creator_payout_status,
                p.creator_paid_at.strftime('%Y-%m-%d %H:%M') if p.creator_paid_at else ''
            ])

        return response


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
