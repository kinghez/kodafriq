from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User, CandidateProfile
from apps.billing.models import PaymentGatewayConfig
from .models import (
    TrainingProgram, ProgramModule, TrainingEnrolment,
    TrainingCoupon, CouponRedemption, TrainingPayment
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
