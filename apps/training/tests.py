from decimal import Decimal
import io
import os
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User, CandidateProfile
from apps.billing.models import PaymentGatewayConfig
from .models import (
    TrainingProgram, ProgramModule, ModuleLesson, LessonProgress, TrainingEnrolment,
    TrainingCoupon, CouponRedemption, TrainingPayment, TrainingMaterial
)


class TrainingPaymentAndAnalyticsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_creator = User.objects.create_user(
            username='creator_staff',
            email='creator@kodafriq.com',
            password='Password123!',
            first_name='Eugenia',
            last_name='Skep',
            role=User.Role.STAFF,
        )
        self.admin_user = User.objects.create_user(
            username='admin_user',
            email='admin@kodafriq.com',
            password='Password123!',
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        self.candidate_user = User.objects.create_user(
            username='candidate1',
            email='candidate@kodafriq.com',
            password='Password123!',
            first_name='Kwame',
            last_name='Mensah',
            role=User.Role.CANDIDATE,
        )
        self.candidate_profile, _ = CandidateProfile.objects.get_or_create(
            user=self.candidate_user,
        )

        self.gateway_cfg = PaymentGatewayConfig.objects.create(
            paystack_enabled=True,
            paystack_mode=PaymentGatewayConfig.Mode.TEST,
            flutterwave_enabled=True,
            flutterwave_mode=PaymentGatewayConfig.Mode.TEST,
            is_active=True,
        )

        self.paid_program = TrainingProgram.objects.create(
            title='Intermediate IT Skills for Remote Work',
            description='Essential IT skills training',
            creator=self.staff_creator,
            creator_share_percentage=Decimal('70.00'),
            is_free=False,
            price=Decimal('40.00'),
            currency='USD',
            is_active=True,
        )
        self.module1 = ProgramModule.objects.create(
            program=self.paid_program,
            title='Computers & Operating Systems',
            order=1,
            content='<p>Module content</p>',
        )

    def test_paid_course_flutterwave_checkout_and_creator_split(self):
        self.client.force_login(self.candidate_user)

        detail_resp = self.client.get(reverse('training:detail', kwargs={'pk': self.paid_program.pk}))
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, '<span class="kf-payable-amount">$40.00</span>')
        self.assertContains(detail_resp, '<span id="kf-paystack-ghs">620.00</span>')

        init_resp = self.client.post(
            reverse('training:checkout_initiate', kwargs={'pk': self.paid_program.pk}),
            data={'gateway': 'FLUTTERWAVE'},
            content_type='application/json',
        )
        self.assertEqual(init_resp.status_code, 200)
        init_data = init_resp.json()
        self.assertEqual(init_data['status'], 'success')
        self.assertFalse(init_data['is_free'])
        self.assertEqual(init_data['amount'], 40.0)
        self.assertEqual(init_data['currency'], 'USD')

        payment_ref = init_data['payment_ref']
        verify_resp = self.client.post(
            reverse('training:checkout_verify', kwargs={'pk': self.paid_program.pk}),
            data={
                'gateway': 'FLUTTERWAVE',
                'payment_ref': payment_ref,
                'transaction_id': f'FLW-{payment_ref}',
            },
            content_type='application/json',
        )
        self.assertEqual(verify_resp.status_code, 200)
        verify_data = verify_resp.json()
        self.assertEqual(verify_data['status'], 'success')

        payment = TrainingPayment.objects.get(payment_ref=payment_ref)
        self.assertEqual(payment.status, TrainingPayment.PaymentStatus.SUCCESSFUL)
        self.assertEqual(payment.net_amount_paid, Decimal('40.00'))
        self.assertEqual(payment.creator_earnings, Decimal('28.00'))
        self.assertEqual(payment.platform_fee, Decimal('12.00'))
        self.assertEqual(payment.creator_payout_status, TrainingPayment.CreatorPayoutStatus.PENDING)
        self.assertEqual(payment.creator, self.staff_creator)
        self.assertTrue(
            TrainingEnrolment.objects.filter(candidate=self.candidate_profile, program=self.paid_program).exists()
        )

    def test_paystack_ghs_conversion_with_50_percent_coupon(self):
        coupon = TrainingCoupon.objects.create(
            code='HALF50',
            discount_type=TrainingCoupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('50.00'),
            max_redemptions=10,
            is_active=True,
        )
        self.client.force_login(self.candidate_user)

        val_resp = self.client.post(
            reverse('training:validate_coupon', kwargs={'pk': self.paid_program.pk}),
            data={'code': 'HALF50'},
        )
        self.assertEqual(val_resp.status_code, 200)
        val_data = val_resp.json()
        self.assertTrue(val_data['valid'])
        self.assertEqual(val_data['final_price'], '20.00')
        self.assertEqual(val_data['final_price_ghs'], '310.00')

        init_resp = self.client.post(
            reverse('training:checkout_initiate', kwargs={'pk': self.paid_program.pk}),
            data={'gateway': 'PAYSTACK', 'coupon_code': 'HALF50'},
            content_type='application/json',
        )
        self.assertEqual(init_resp.status_code, 200)
        init_data = init_resp.json()
        self.assertEqual(init_data['amount'], 20.0)
        self.assertEqual(init_data['amount_ghs'], 310.0)
        self.assertEqual(init_data['amount_kobo'], 31000)
        self.assertEqual(init_data['paystack_currency'], 'GHS')

        verify_resp = self.client.post(
            reverse('training:checkout_verify', kwargs={'pk': self.paid_program.pk}),
            data={
                'gateway': 'PAYSTACK',
                'payment_ref': init_data['payment_ref'],
                'transaction_id': init_data['payment_ref'],
            },
            content_type='application/json',
        )
        self.assertEqual(verify_resp.status_code, 200)

        payment = TrainingPayment.objects.get(payment_ref=init_data['payment_ref'])
        self.assertEqual(payment.gross_amount, Decimal('40.00'))
        self.assertEqual(payment.discount_amount, Decimal('20.00'))
        self.assertEqual(payment.net_amount_paid, Decimal('20.00'))
        self.assertEqual(payment.creator_earnings, Decimal('14.00'))
        self.assertEqual(payment.platform_fee, Decimal('6.00'))

        coupon.refresh_from_db()
        self.assertEqual(coupon.times_redeemed, 1)
        self.assertEqual(CouponRedemption.objects.count(), 1)

    def test_100_percent_coupon_free_checkout(self):
        TrainingCoupon.objects.create(
            code='FIRST50',
            discount_type=TrainingCoupon.DiscountType.PERCENTAGE,
            discount_value=Decimal('100.00'),
            max_redemptions=50,
            is_active=True,
        )
        self.client.force_login(self.candidate_user)

        init_resp = self.client.post(
            reverse('training:checkout_initiate', kwargs={'pk': self.paid_program.pk}),
            data={'gateway': 'PAYSTACK', 'coupon_code': 'FIRST50'},
            content_type='application/json',
        )
        self.assertEqual(init_resp.status_code, 200)
        init_data = init_resp.json()
        self.assertTrue(init_data['is_free'])

        payment = TrainingPayment.objects.get(candidate=self.candidate_profile, program=self.paid_program)
        self.assertEqual(payment.gateway, TrainingPayment.Gateway.COUPON_FREE)
        self.assertEqual(payment.net_amount_paid, Decimal('0.00'))
        self.assertEqual(payment.creator_payout_status, TrainingPayment.CreatorPayoutStatus.NOT_APPLICABLE)

    def test_disabled_gateway_rejected(self):
        self.gateway_cfg.paystack_enabled = False
        self.gateway_cfg.save()
        self.client.force_login(self.candidate_user)

        resp = self.client.post(
            reverse('training:checkout_initiate', kwargs={'pk': self.paid_program.pk}),
            data={'gateway': 'PAYSTACK'},
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_staff_revenue_analytics_and_csv_export(self):
        enrolment = TrainingEnrolment.objects.create(
            candidate=self.candidate_profile,
            program=self.paid_program,
            amount_paid=Decimal('40.00'),
        )
        payment = TrainingPayment.objects.create(
            payment_ref='KODA-TRN-TEST-001',
            program=self.paid_program,
            candidate=self.candidate_profile,
            enrolment=enrolment,
            creator=self.staff_creator,
            gross_amount=Decimal('40.00'),
            net_amount_paid=Decimal('40.00'),
            currency='USD',
            creator_share_percent=Decimal('70.00'),
            gateway=TrainingPayment.Gateway.FLUTTERWAVE,
        )
        payment.mark_successful(gateway_ref='FLW-TEST-99')

        # Candidate should not access staff analytics
        self.client.force_login(self.candidate_user)
        cand_resp = self.client.get(reverse('training:staff_revenue_analytics'))
        self.assertEqual(cand_resp.status_code, 302)

        # Staff creator / Admin can access analytics with filters and export CSV
        self.client.force_login(self.staff_creator)
        analytics_resp = self.client.get(
            reverse('training:staff_revenue_analytics'),
            {'course': self.paid_program.id, 'creator': self.staff_creator.id, 'status': 'SUCCESSFUL'},
        )
        self.assertEqual(analytics_resp.status_code, 200)
        self.assertContains(analytics_resp, 'KODA-TRN-TEST-001')
        self.assertContains(analytics_resp, 'Eugenia Skep')
        self.assertContains(analytics_resp, '$28.00')

        export_resp = self.client.get(
            reverse('training:staff_revenue_export'),
            {'course': self.paid_program.id},
        )
        self.assertEqual(export_resp.status_code, 200)
        self.assertEqual(export_resp['Content-Type'], 'text/csv')
        csv_body = export_resp.content.decode('utf-8')
        self.assertIn('KODA-TRN-TEST-001', csv_body)
        self.assertIn('28.00', csv_body)
        self.assertIn('12.00', csv_body)

        # Admin changelist & creator payout disbursement action
        self.client.force_login(self.admin_user)
        admin_list_resp = self.client.get(reverse('admin:training_trainingpayment_changelist'))
        self.assertEqual(admin_list_resp.status_code, 200)
        self.assertContains(admin_list_resp, 'KODA-TRN-TEST-001')

        action_resp = self.client.post(
            reverse('admin:training_trainingpayment_changelist'),
            {'action': 'mark_disbursed_to_creator', '_selected_action': [str(payment.id)]},
        )
        self.assertEqual(action_resp.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.creator_payout_status, TrainingPayment.CreatorPayoutStatus.PAID)
        self.assertIsNotNone(payment.creator_paid_at)


class TrainingCareerWizeLMSAndMediaTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(
            username='admin_lms',
            email='admin_lms@kodafriq.com',
            password='Password123!',
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        self.candidate_user = User.objects.create_user(
            username='learner_cand',
            email='learner@kodafriq.com',
            password='Password123!',
            first_name='Abena',
            last_name='Boateng',
            role=User.Role.CANDIDATE,
        )
        self.candidate_profile = CandidateProfile.objects.filter(user=self.candidate_user).first()
        if not self.candidate_profile:
            self.candidate_profile = CandidateProfile.objects.create(user=self.candidate_user)

        self.program = TrainingProgram.objects.create(
            title='Clinical Pathology & ICD Coding',
            description='Medical training curriculum',
            is_free=True,
            price=Decimal('0.00'),
            is_active=True,
        )
        self.module = ProgramModule.objects.create(
            program=self.program,
            title='Skeletal Diseases & Diagnosis',
            order=1,
            content='<p>Module overview</p>',
        )
        self.lesson_reading = ModuleLesson.objects.create(
            module=self.module,
            order=1,
            title='Diseases of the Skeletal System',
            lesson_type=ModuleLesson.LessonType.CONTENT,
            content='<p class="kf-img-left">Fractures get all the glory...</p>',
        )
        self.lesson_matching = ModuleLesson.objects.create(
            module=self.module,
            order=2,
            title='Terminology L-O: Skeletal Diseases Matching',
            lesson_type=ModuleLesson.LessonType.MATCHING_QUIZ,
            matching_title='Matching',
            matching_instructions='Drag and drop the answers to the correct questions.',
            matching_pairs=[
                {'question': 'Tumor derived from blood cells', 'answer': 'Multiple myeloma'},
                {'question': 'Benign lesion in bone', 'answer': 'Osteoid osteoma'},
            ],
        )
        self.enrolment = TrainingEnrolment.objects.create(
            candidate=self.candidate_profile,
            program=self.program,
            status=TrainingEnrolment.EnrolmentStatus.IN_PROGRESS,
        )

    def test_admin_media_upload_endpoint(self):
        self.client.force_login(self.admin_user)
        dummy_file = SimpleUploadedFile("sample_scan.png", b"\x89PNG\r\n\x1a\n\x00\x00", content_type="image/png")
        resp = self.client.post(
            reverse('training:admin_upload_media'),
            {'file': dummy_file},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('location', data)
        self.assertIn('sample_scan.png', data['location'])

    def test_unauthorized_user_cannot_upload_media(self):
        self.client.force_login(self.candidate_user)
        dummy_file = SimpleUploadedFile("test.png", b"test", content_type="image/png")
        resp = self.client.post(
            reverse('training:admin_upload_media'),
            {'file': dummy_file},
        )
        self.assertEqual(resp.status_code, 403)

    def test_careerwize_learn_view_pagination_and_outline(self):
        self.client.force_login(self.candidate_user)
        learn_url = reverse('training:learn', kwargs={'enrolment_id': self.enrolment.id})
        resp = self.client.get(learn_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Kodafriq Academy')
        self.assertContains(resp, 'Diseases of the Skeletal System')
        self.assertContains(resp, 'Page')
        self.assertContains(resp, 'Outline')

    def test_interactive_matching_quiz_submission(self):
        self.client.force_login(self.candidate_user)
        submit_url = reverse(
            'training:lesson_matching_submit',
            kwargs={'enrolment_id': self.enrolment.id, 'lesson_id': self.lesson_matching.id}
        )

        # 1. Partial/Wrong Submission
        wrong_payload = {
            'pairs': [
                {'question': 'Tumor derived from blood cells', 'answer': 'Osteoid osteoma'},
                {'question': 'Benign lesion in bone', 'answer': 'Multiple myeloma'},
            ]
        }
        resp = self.client.post(submit_url, data=wrong_payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['all_correct'])
        self.assertEqual(data['score'], 0)

        # 2. Perfect Submission
        correct_payload = {
            'pairs': [
                {'question': 'Tumor derived from blood cells', 'answer': 'Multiple myeloma'},
                {'question': 'Benign lesion in bone', 'answer': 'Osteoid osteoma'},
            ]
        }
        resp = self.client.post(submit_url, data=correct_payload, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['all_correct'])
        self.assertEqual(data['score'], 2)

        # Verify LessonProgress updated
        lp = LessonProgress.objects.filter(enrolment=self.enrolment, lesson=self.lesson_matching).first()
        self.assertIsNotNone(lp)
        self.assertTrue(lp.is_completed)
        self.assertTrue(lp.matching_completed)

    def test_lesson_complete_view(self):
        self.client.force_login(self.candidate_user)
        complete_url = reverse(
            'training:lesson_complete',
            kwargs={'enrolment_id': self.enrolment.id, 'lesson_id': self.lesson_reading.id}
        )
        resp = self.client.post(complete_url)
        self.assertEqual(resp.status_code, 302)
        lp = LessonProgress.objects.filter(enrolment=self.enrolment, lesson=self.lesson_reading).first()
        self.assertIsNotNone(lp)
        self.assertTrue(lp.is_completed)

    def test_lesson_quiz_questions_sync_and_submission(self):
        # Create a dedicated QUIZ lesson with quiz_questions_data
        quiz_lesson = ModuleLesson.objects.create(
            module=self.module,
            order=4,
            title="Knowledge Check Quiz",
            lesson_type=ModuleLesson.LessonType.QUIZ,
            quiz_questions_data=[
                {
                    'prompt': 'Which is part of clinical care?',
                    'explanation': 'Diagnosing is direct clinical care.',
                    'options': [
                        {'text': 'Submitting insurance claims', 'is_correct': False},
                        {'text': 'Diagnosing and treating patients', 'is_correct': True},
                        {'text': 'Recording payments', 'is_correct': False},
                    ]
                }
            ]
        )

        # Verify sync created ModuleQuizQuestion & ModuleQuizOption
        self.assertEqual(quiz_lesson.quiz_questions.count(), 1)
        q = quiz_lesson.quiz_questions.first()
        self.assertEqual(q.prompt, 'Which is part of clinical care?')
        self.assertEqual(q.options.count(), 3)
        correct_opt = q.options.filter(is_correct=True).first()
        self.assertEqual(correct_opt.text, 'Diagnosing and treating patients')

        # Test submitting quiz answer via quiz_submit
        self.client.force_login(self.candidate_user)
        submit_url = reverse(
            'training:quiz_submit',
            kwargs={'enrolment_id': self.enrolment.id, 'module_id': self.module.id}
        )
        resp = self.client.post(submit_url, data={
            'lesson_id': quiz_lesson.id,
            f'question_{q.id}': correct_opt.id
        })
        self.assertEqual(resp.status_code, 302)

        # Verify LessonProgress is now completed
        lp = LessonProgress.objects.filter(enrolment=self.enrolment, lesson=quiz_lesson).first()
        self.assertIsNotNone(lp)
        self.assertTrue(lp.is_completed)

    def test_matching_lesson_renders_cleanly_without_500_error(self):
        """
        Verify that a lesson with matching pairs configured as {question, answer}
        renders without template VariableDoesNotExist error (500 Server Error).
        """
        self.client.force_login(self.candidate_user)
        matching_lesson = ModuleLesson.objects.create(
            module=self.module,
            order=5,
            title="Healthcare Provider Matching",
            lesson_type=ModuleLesson.LessonType.MATCHING_QUIZ,
            matching_title="Matching",
            matching_instructions="<h3>Match the Healthcare Provider</h3><p>Match each provider.</p>",
            matching_pairs=[
                {"question": "Physician practice", "answer": "Laboratory tests and medical imagi"},
                {"question": "Diagnostic centre", "answer": "Specialist medical care"},
            ],
        )

        learn_url = reverse('training:learn', kwargs={'enrolment_id': self.enrolment.id})
        resp = self.client.get(f"{learn_url}?lesson={matching_lesson.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Healthcare Provider Matching")
        self.assertContains(resp, "Physician practice")
        self.assertContains(resp, "Diagnostic centre")
        self.assertContains(resp, "Specialist medical care")

    def test_quiz_submission_feedback_ajax_indicators(self):
        """
        Verify that submitting quiz answers returns detailed per-question indicators
        (selected option, is_correct, correct answer, explanation).
        """
        quiz_lesson = ModuleLesson.objects.create(
            module=self.module,
            order=6,
            title="Knowledge Check",
            lesson_type=ModuleLesson.LessonType.QUIZ,
            quiz_questions_data=[
                {
                    'prompt': 'Which is part of clinical care?',
                    'explanation': 'Diagnosing is clinical.',
                    'options': [
                        {'text': 'Submitting insurance claims', 'is_correct': False},
                        {'text': 'Diagnosing and treating patients', 'is_correct': True},
                    ]
                },
                {
                    'prompt': 'What is medical billing concerned with?',
                    'explanation': 'Billing manages payments.',
                    'options': [
                        {'text': 'Treating patients', 'is_correct': False},
                        {'text': 'Requesting and managing payment', 'is_correct': True},
                    ]
                }
            ]
        )

        questions = list(quiz_lesson.quiz_questions.prefetch_related('options').order_by('order'))
        q1 = questions[0]
        q2 = questions[1]
        q1_wrong = q1.options.filter(is_correct=False).first()
        q2_correct = q2.options.filter(is_correct=True).first()

        self.client.force_login(self.candidate_user)
        submit_url = reverse(
            'training:quiz_submit',
            kwargs={'enrolment_id': self.enrolment.id, 'module_id': self.module.id}
        )
        resp = self.client.post(
            submit_url,
            data={
                'lesson_id': quiz_lesson.id,
                f'question_{q1.id}': q1_wrong.id,
                f'question_{q2.id}': q2_correct.id,
                'ajax': '1',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['total_questions'], 2)
        self.assertEqual(data['correct_count'], 1)
        self.assertEqual(data['score_percentage'], 50.0)

        # Inspect question feedback
        q1_fb = next(q for q in data['questions'] if q['question_id'] == q1.id)
        self.assertFalse(q1_fb['is_correct'])
        self.assertEqual(q1_fb['selected_option_id'], q1_wrong.id)
        self.assertEqual(q1_fb['correct_option_text'], 'Diagnosing and treating patients')
        self.assertEqual(q1_fb['explanation'], 'Diagnosing is clinical.')

        q2_fb = next(q for q in data['questions'] if q['question_id'] == q2.id)
        self.assertTrue(q2_fb['is_correct'])
        self.assertEqual(q2_fb['selected_option_id'], q2_correct.id)

    def test_quiz_lesson_type_suppresses_duplicate_content(self):
        """
        Verify that when a lesson is QUIZ type, lingering reading content is not displayed.
        """
        self.client.force_login(self.candidate_user)
        quiz_lesson = ModuleLesson.objects.create(
            module=self.module,
            order=7,
            title="Lesson 1 Knowledge Check",
            lesson_type=ModuleLesson.LessonType.QUIZ,
            content="<p>Old duplicate question text in database</p>",
            quiz_questions_data=[
                {
                    'prompt': 'Test Question 1?',
                    'options': [
                        {'text': 'Option A', 'is_correct': True},
                        {'text': 'Option B', 'is_correct': False},
                    ]
                }
            ]
        )

        learn_url = reverse('training:learn', kwargs={'enrolment_id': self.enrolment.id})
        resp = self.client.get(f"{learn_url}?lesson={quiz_lesson.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Old duplicate question text in database")
        self.assertContains(resp, "Test Question 1?")
        self.assertContains(resp, "Option A")

    def test_audio_reads_term_and_definition_and_lesson_jump_exists(self):
        """
        Verify audio button passes both term and definition, and lesson quick-jump dropdown renders.
        """
        self.client.force_login(self.candidate_user)
        term_lesson = ModuleLesson.objects.create(
            module=self.module,
            order=8,
            title="Clinical Terms Audio Lesson",
            lesson_type=ModuleLesson.LessonType.TERMINOLOGY,
            terms_data=[
                {"term": "Chronic", "definition": "A condition that lasts a long time and needs ongoing care"}
            ],
        )

        learn_url = reverse('training:learn', kwargs={'enrolment_id': self.enrolment.id})
        resp = self.client.get(f"{learn_url}?lesson={term_lesson.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-term="Chronic"')
        self.assertContains(resp, 'data-definition="A condition that lasts a long time and needs ongoing care"')
        self.assertContains(resp, 'onclick="speakTermFromButton(this)"')
        self.assertContains(resp, 'id="lessonQuickJump"')
        self.assertContains(resp, "Clinical Terms Audio Lesson")

    def test_quiz_grade_persists_in_database_across_sessions(self):
        """
        Verify that a submitted quiz attempt persists its grade & feedback in the DB
        so returning to the quiz in a fresh session still shows the saved grade and feedback.
        """
        quiz_lesson = ModuleLesson.objects.create(
            module=self.module,
            order=9,
            title="Persistent Grade Knowledge Check",
            lesson_type=ModuleLesson.LessonType.QUIZ,
            quiz_questions_data=[
                {
                    'prompt': 'Persistent Q1?',
                    'explanation': 'Q1 explanation.',
                    'options': [
                        {'text': 'Right Choice', 'is_correct': True},
                        {'text': 'Wrong Choice', 'is_correct': False},
                    ]
                }
            ]
        )
        q = quiz_lesson.quiz_questions.first()
        right_opt = q.options.filter(is_correct=True).first()

        self.client.force_login(self.candidate_user)
        submit_url = reverse(
            'training:quiz_submit',
            kwargs={'enrolment_id': self.enrolment.id, 'module_id': self.module.id}
        )
        resp = self.client.post(
            submit_url,
            data={'lesson_id': quiz_lesson.id, f'question_{q.id}': right_opt.id, 'ajax': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json',
        )
        self.assertEqual(resp.status_code, 200)

        # Simulate user logging out / returning in a brand-new session
        self.client.logout()
        self.client.force_login(self.candidate_user)

        learn_url = reverse('training:learn', kwargs={'enrolment_id': self.enrolment.id})
        revisit_resp = self.client.get(f"{learn_url}?lesson={quiz_lesson.id}")
        self.assertEqual(revisit_resp.status_code, 200)
        self.assertContains(revisit_resp, 'id="quizFeedbackData"')
        self.assertContains(revisit_resp, '"score_percentage": 100.0')
        self.assertContains(revisit_resp, 'Right Choice')

    def test_rendered_inline_javascript_has_no_syntax_errors(self):
        """
        Ensure rendered inline <script> on matching, terminology, and quiz pages
        passes Node.js syntax checking so icons, audio, drag-and-drop, and quiz JS always execute.
        """
        import re
        import shutil
        import subprocess
        import tempfile

        node_bin = shutil.which('node')
        if not node_bin:
            self.skipTest("node binary not available")

        self.client.force_login(self.candidate_user)
        learn_url = reverse('training:learn', kwargs={'enrolment_id': self.enrolment.id})
        for qs in ['', f'?lesson={self.lesson_matching.id}']:
            resp = self.client.get(f"{learn_url}{qs}")
            self.assertEqual(resp.status_code, 200)
            html = resp.content.decode('utf-8')
            scripts = re.findall(r'<script>(.*?)</script>', html, flags=re.DOTALL)
            self.assertTrue(scripts, "Expected inline <script> block on learn page")
            for idx, js_code in enumerate(scripts):
                with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as tmp:
                    tmp.write(js_code)
                    tmp_path = tmp.name
                try:
                    proc = subprocess.run([node_bin, '--check', tmp_path], capture_output=True, text=True)
                    self.assertEqual(proc.returncode, 0, f"JS syntax error in script #{idx} ({qs}): {proc.stderr}")
                finally:
                    os.unlink(tmp_path)

    def test_matching_success_and_incomplete_modals_rendered(self):
        """
        Ensure branded matching achievement and incomplete modals are present in the HTML
        with proper styling classes and navigation actions.
        """
        # Create a subsequent lesson so next_page is populated
        ModuleLesson.objects.create(
            module=self.module,
            order=self.lesson_matching.order + 1,
            title="Next Step Lesson",
            lesson_type=ModuleLesson.LessonType.CONTENT,
            content="Follow-up clinical reading content.",
        )

        self.client.force_login(self.candidate_user)
        learn_url = reverse('training:learn', kwargs={'enrolment_id': self.enrolment.id})
        resp = self.client.get(f"{learn_url}?lesson={self.lesson_matching.id}")
        self.assertEqual(resp.status_code, 200)

        # Modals exist
        self.assertContains(resp, 'id="matchingSuccessModal"')
        self.assertContains(resp, 'id="matchingIncompleteModal"')
        self.assertContains(resp, 'cw-modal-achievement')
        self.assertContains(resp, 'Knowledge Check Passed')
        self.assertContains(resp, 'Review Answers')
        self.assertContains(resp, 'id="btnMatchingNextLesson"')

        # JS functions exist
        self.assertContains(resp, 'openMatchingSuccessModal')
        self.assertContains(resp, 'closeMatchingSuccessModal')
        self.assertContains(resp, 'openMatchingIncompleteModal')
        self.assertContains(resp, 'closeMatchingIncompleteModal')
        self.assertContains(resp, 'confirmMatchingSubmission')

    def test_module_materials_hidden_without_uploaded_files(self):
        """
        Ensure 'Module Video & Downloads' does NOT appear unless an actual video or
        downloadable file has been uploaded by the creator/owner, and stays hidden on quizzes.
        """
        content_lesson = ModuleLesson.objects.create(
            module=self.module,
            order=90,
            title="Clinical Claims Flow",
            lesson_type=ModuleLesson.LessonType.CONTENT,
            content="<p>Structured clinical billing workflow overview.</p>",
        )
        self.client.force_login(self.candidate_user)
        learn_url = reverse('training:learn', kwargs={'enrolment_id': self.enrolment.id})

        # 1. No materials at all -> section must not render
        resp_empty = self.client.get(f"{learn_url}?lesson={content_lesson.id}")
        self.assertEqual(resp_empty.status_code, 200)
        self.assertNotContains(resp_empty, 'Module Video')

        # 2. Only external VIDEO_EMBED / empty file row -> section must still stay hidden
        embed_stub = TrainingMaterial.objects.create(
            program=self.enrolment.program,
            module=self.module,
            title="Placeholder YouTube Video",
            material_type='VIDEO_EMBED',
            external_url='https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            is_downloadable=True,
            order=1,
        )
        resp_stub = self.client.get(f"{learn_url}?lesson={content_lesson.id}")
        self.assertEqual(resp_stub.status_code, 200)
        self.assertNotContains(resp_stub, 'Module Video')
        embed_stub.delete()

        # 3. Actual uploaded downloadable document -> shows on content lesson, hidden on quiz
        uploaded_pdf = SimpleUploadedFile(
            'clinical_study_guide.pdf',
            b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF',
            content_type='application/pdf',
        )
        doc_mat = TrainingMaterial.objects.create(
            program=self.enrolment.program,
            module=self.module,
            title="Clinical Study Guide",
            material_type='DOCUMENT',
            file=uploaded_pdf,
            is_downloadable=True,
            order=2,
        )
        try:
            resp_doc = self.client.get(f"{learn_url}?lesson={content_lesson.id}")
            self.assertEqual(resp_doc.status_code, 200)
            self.assertContains(resp_doc, 'Module Video')
            self.assertContains(resp_doc, 'Download: Clinical Study Guide (.PDF)')

            resp_quiz = self.client.get(f"{learn_url}?lesson={self.lesson_matching.id}")
            self.assertEqual(resp_quiz.status_code, 200)
            self.assertNotContains(resp_quiz, 'Module Video')
        finally:
            if doc_mat.file:
                doc_mat.file.delete(save=False)
            doc_mat.delete()

    def test_training_pages_render_mobile_responsive_layout(self):
        """
        Verify candidate training catalog, program detail, and LMS player templates render
        HTTP 200 with mobile-responsive layout classes and controls intact.
        """
        self.client.force_login(self.candidate_user)

        list_resp = self.client.get(reverse('training:index'))
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, 'kf-tl-wrap')
        self.assertContains(list_resp, 'kf-tl-pillars-grid')

        detail_resp = self.client.get(reverse('training:detail', kwargs={'pk': self.enrolment.program.pk}))
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, 'kf-td-page')
        self.assertContains(detail_resp, 'kf-td-module-row')

        learn_resp = self.client.get(reverse('training:learn', kwargs={'enrolment_id': self.enrolment.id}))
        self.assertEqual(learn_resp.status_code, 200)
        self.assertContains(learn_resp, 'cw-mobile-header-nav')
        self.assertContains(learn_resp, 'cw-mobile-nav')


