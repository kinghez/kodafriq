from django.contrib.auth.models import Permission
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.accounts.models import EmployerProfile, CandidateProfile
from apps.employers.models import Job
from apps.contracts.models import Contract, Timesheet, Milestone
from apps.billing.models import PlatformFeeConfig, PaymentGatewayConfig, CandidatePayoutProfile, ContractInvoice, PaymentTransaction
from apps.billing.services.invoicing import (
    generate_invoice_for_timesheet,
    generate_invoice_for_milestone,
    get_candidate_ledger_summary,
    get_next_payout_date
)

User = get_user_model()


class BillingAndEarningsLedgerTests(TestCase):
    def setUp(self):
        # 1. Employer Setup
        self.employer_user = User.objects.create_user(
            username='hospital_cf_exec',
            email='cfo@metrohealth.org',
            password='testpassword123',
            role=User.Role.EMPLOYER
        )
        self.employer_profile, _ = EmployerProfile.objects.get_or_create(
            user=self.employer_user,
            defaults={'company_name': "Metro Health System"}
        )
        self.employer_profile.company_name = "Metro Health System"
        self.employer_profile.save()

        # 2. Candidate Setup
        self.candidate_user = User.objects.create_user(
            username='coder_esther',
            email='esther@kodafriq.org',
            password='testpassword123',
            role=User.Role.CANDIDATE
        )
        self.candidate_profile, _ = CandidateProfile.objects.get_or_create(
            user=self.candidate_user,
            defaults={'headline': "Certified Inpatient Coder | CCS"}
        )

        # 3. Contract Setup (Hourly: $17.50/hr net to talent)
        self.contract = Contract.objects.create(
            employer=self.employer_profile,
            candidate=self.candidate_profile,
            title="Inpatient Clinical Coding",
            contract_type=Contract.ContractType.HOURLY,
            rate_per_hour=Decimal('17.50'),
            kodafriq_fee_percent=Decimal('10.00'),
            weekly_hour_limit=40,
            status=Contract.Status.ACTIVE
        )

        # 4. Timesheet Setup (40 hours logged = $700.00 net talent)
        self.timesheet = self.contract.get_or_create_current_timesheet()
        for entry in self.timesheet.entries.all()[:5]:
            entry.hours_worked = Decimal('8.00')
            entry.charts_coded_count = 20
            entry.work_description = "Coded inpatient charts"
            entry.save()
        self.timesheet.status = Timesheet.Status.APPROVED
        self.timesheet.save()

    def test_invoice_generation_math(self):
        """
        Tests the 10% platform fee and pass-through gateway fee calculation:
        - Talent Net: 40 hrs @ $17.50 = $700.00
        - Kodafriq Fee: 10% of $700.00 = $70.00
        - Subtotal: $770.00
        - Pass-through Processing Fee: 2.9% of $770 + $0.30 = $22.63
        - Gross Billed: $792.63
        """
        invoice = generate_invoice_for_timesheet(self.timesheet)
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.talent_earnings, Decimal('700.00'))
        self.assertEqual(invoice.kodafriq_fee, Decimal('70.00'))
        self.assertEqual(invoice.processing_fee, Decimal('22.63'))
        self.assertEqual(invoice.gross_amount, Decimal('792.63'))
        self.assertEqual(invoice.payment_status, ContractInvoice.PaymentStatus.ISSUED)
        self.assertEqual(invoice.payout_status, ContractInvoice.PayoutStatus.PENDING)

    def test_candidate_ledger_states_lifecycle(self):
        """
        Tests the 3 core states of the Candidate Earnings Ledger:
        1. When invoice is ISSUED:
           - pending_earnings = $700.00
           - available_earnings = $0.00
           - lifetime_paid = $0.00
        2. When invoice is SETTLED by employer:
           - pending_earnings = $0.00
           - available_earnings = $700.00 (queued for Friday)
           - next_payout_amount = $700.00
        3. When invoice is DISBURSED to talent:
           - available_earnings = $0.00
           - lifetime_paid = $700.00
        """
        invoice = generate_invoice_for_timesheet(self.timesheet)

        # State 1: Awaiting Employer Payment
        ledger1 = get_candidate_ledger_summary(self.candidate_profile)
        self.assertEqual(ledger1['pending'], Decimal('700.00'))
        self.assertEqual(ledger1['available'], Decimal('0.00'))
        self.assertEqual(ledger1['lifetime_paid'], Decimal('0.00'))

        # State 2: Employer Pays Invoice -> Funds become Available & Queued for Friday
        invoice.mark_settled(gateway_charge_ref="flw_tx_849204128")
        self.assertEqual(invoice.payment_status, ContractInvoice.PaymentStatus.SETTLED)
        self.assertEqual(invoice.payout_status, ContractInvoice.PayoutStatus.QUEUED)
        self.assertEqual(self.timesheet.status, Timesheet.Status.PAID)

        ledger2 = get_candidate_ledger_summary(self.candidate_profile)
        self.assertEqual(ledger2['pending'], Decimal('0.00'))
        self.assertEqual(ledger2['available'], Decimal('700.00'))
        self.assertEqual(ledger2['next_payout_amount'], Decimal('700.00'))
        self.assertEqual(ledger2['lifetime_paid'], Decimal('0.00'))

        # State 3: Friday Payout Run executes disbursement
        invoice.mark_disbursed(gateway_payout_ref="pstk_trf_9921045")
        self.assertEqual(invoice.payout_status, ContractInvoice.PayoutStatus.COMPLETED)

        ledger3 = get_candidate_ledger_summary(self.candidate_profile)
        self.assertEqual(ledger3['available'], Decimal('0.00'))
        self.assertEqual(ledger3['lifetime_paid'], Decimal('700.00'))

    def test_payout_profile_momo_and_bank(self):
        """
        Verify Mobile Money destination masking and verification state.
        """
        profile = CandidatePayoutProfile.objects.create(
            candidate=self.candidate_profile,
            payout_method=CandidatePayoutProfile.PayoutMethod.PAYSTACK_MOMO,
            momo_network=CandidatePayoutProfile.MoMoNetwork.MTN,
            momo_phone_number="+233241234567",
            momo_account_name="Esther Mensah",
            is_verified=True
        )
        self.assertTrue(profile.is_configured)
        self.assertIn("MTN Mobile Money", profile.masked_destination)
        self.assertIn("67", profile.masked_destination)

    def test_billing_views(self):
        """
        Verify candidate earnings ledger and employer invoice views render successfully.
        """
        invoice = generate_invoice_for_timesheet(self.timesheet)

        # 1. Candidate accesses Earnings Ledger
        self.client.login(username='coder_esther', password='testpassword123')
        res_ledger = self.client.get('/billing/earnings/')
        self.assertEqual(res_ledger.status_code, 200)
        self.assertContains(res_ledger, "KODAFRIQ EARNINGS LEDGER")
        self.assertContains(res_ledger, "$700.00")

        # 2. Candidate accesses Payout Settings
        res_payout = self.client.get('/billing/payout-settings/')
        self.assertEqual(res_payout.status_code, 200)

        # 3. Employer accesses Invoice List & Detail
        self.client.logout()
        self.client.login(username='hospital_cf_exec', password='testpassword123')

        res_inv_list = self.client.get('/billing/invoices/')
        self.assertEqual(res_inv_list.status_code, 200)
        self.assertContains(res_inv_list, invoice.invoice_ref)

        res_inv_detail = self.client.get(f'/billing/invoices/{invoice.pk}/')
        self.assertEqual(res_inv_detail.status_code, 200)
        self.assertContains(res_inv_detail, "$792.63")

        # 4. Employer completes one-click settlement
        res_pay = self.client.post(f'/billing/invoices/{invoice.pk}/pay/')
        self.assertEqual(res_pay.status_code, 302)

        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_status, ContractInvoice.PaymentStatus.SETTLED)
        self.assertEqual(invoice.payout_status, ContractInvoice.PayoutStatus.QUEUED)
        self.assertTrue(PaymentTransaction.objects.filter(invoice=invoice).exists())

    def test_invoice_and_statement_pdf_generation(self):
        """
        Verify employer invoice PDF and candidate earnings statement PDF generate valid application/pdf streams.
        """
        invoice = generate_invoice_for_timesheet(self.timesheet)

        # 1. Employer downloads Invoice PDF
        self.client.login(username='hospital_cf_exec', password='testpassword123')
        res_inv_pdf = self.client.get(f'/billing/invoices/{invoice.pk}/pdf/')
        self.assertEqual(res_inv_pdf.status_code, 200)
        self.assertEqual(res_inv_pdf['Content-Type'], 'application/pdf')
        self.assertTrue(len(res_inv_pdf.getvalue()) > 500)

        # 2. Candidate downloads Earnings Statement PDF
        self.client.logout()
        self.client.login(username='coder_esther', password='testpassword123')
        res_stmt_pdf = self.client.get('/billing/earnings/statement/pdf/')
        self.assertEqual(res_stmt_pdf.status_code, 200)
        self.assertEqual(res_stmt_pdf['Content-Type'], 'application/pdf')
        self.assertTrue(len(res_stmt_pdf.getvalue()) > 500)

        # 3. Unauthorized user cannot access other invoices
        self.client.logout()
        other_user = User.objects.create_user(username='other_random', email='other@test.org', password='testpassword123')
        self.client.login(username='other_random', password='testpassword123')
        res_denied = self.client.get(f'/billing/invoices/{invoice.pk}/pdf/')
        self.assertEqual(res_denied.status_code, 403)



class PaymentGatewayConfigTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='admin_billing',
            email='billing@kodafriq.com',
            password='testpassword123',
            is_staff=True,
            is_superuser=True
        )

    def test_payment_gateway_config_and_service_precedence(self):
        """
        Tests that Paystack & Flutterwave services dynamically read from the active database
        PaymentGatewayConfig model when keys are inserted by Staff in Admin.
        """
        # 1. Create active configuration with custom API keys
        cfg = PaymentGatewayConfig.objects.create(
            paystack_enabled=True,
            paystack_mode=PaymentGatewayConfig.Mode.LIVE,
            paystack_public_key='pk_live_custom_paystack_key_123',
            paystack_secret_key='sk_live_custom_paystack_sec_456',
            flutterwave_enabled=True,
            flutterwave_mode=PaymentGatewayConfig.Mode.LIVE,
            flutterwave_public_key='FLWPUBK-custom_flw_key_789',
            flutterwave_secret_key='FLWSECK-custom_flw_sec_012',
            flutterwave_secret_hash='custom_webhook_hash_345',
            is_active=True
        )

        from apps.billing.services.paystack_ghana import PaystackGhanaService
        from apps.billing.services.flutterwave import FlutterwaveService

        pstk = PaystackGhanaService()
        flw = FlutterwaveService()

        self.assertEqual(pstk.secret_key, 'sk_live_custom_paystack_sec_456')
        self.assertEqual(flw.secret_key, 'FLWSECK-custom_flw_sec_012')
        self.assertEqual(flw.secret_hash, 'custom_webhook_hash_345')

        # 2. Test single active configuration constraint
        cfg2 = PaymentGatewayConfig.objects.create(
            paystack_mode=PaymentGatewayConfig.Mode.TEST,
            paystack_secret_key='sk_test_secondary_key',
            is_active=True
        )
        cfg.refresh_from_db()
        self.assertFalse(cfg.is_active)
        self.assertTrue(cfg2.is_active)

        # 3. Test Admin interface accessibility for superuser/staff
        self.client.login(username='admin_billing', password='testpassword123')
        res_list = self.client.get('/admin/billing/paymentgatewayconfig/')
        self.assertEqual(res_list.status_code, 200)
        self.assertContains(res_list, "Payment Gateway API Configurations")

        res_change = self.client.get(f'/admin/billing/paymentgatewayconfig/{cfg2.pk}/change/')
        self.assertEqual(res_change.status_code, 200)
        self.assertContains(res_change, "Paystack API Configuration")
        self.assertContains(res_change, "Flutterwave API Configuration")
        self.assertContains(res_change, "Webhook Integration Guide")



class InteractiveCheckoutTests(TestCase):
    def setUp(self):
        self.employer_user = User.objects.create_user(
            username='health_employer',
            email='cfo@healthfacility.org',
            password='testpassword123',
            role=User.Role.EMPLOYER
        )
        self.employer_profile, _ = EmployerProfile.objects.get_or_create(
            user=self.employer_user,
            defaults={'company_name': 'National Health Clinic'}
        )
        self.employer_profile.company_name = 'National Health Clinic'
        self.employer_profile.save()

        self.candidate_user = User.objects.create_user(
            username='coder_kwame',
            email='kwame@kodafriq.org',
            password='testpassword123',
            role=User.Role.CANDIDATE
        )
        self.candidate_profile, _ = CandidateProfile.objects.get_or_create(
            user=self.candidate_user,
            defaults={'headline': 'Clinical Coding Auditor'}
        )

        self.contract = Contract.objects.create(
            employer=self.employer_profile,
            candidate=self.candidate_profile,
            title='Inpatient Coding Audit',
            contract_type=Contract.ContractType.HOURLY,
            rate_per_hour=Decimal('20.00'),
            kodafriq_fee_percent=Decimal('10.00'),
            status=Contract.Status.ACTIVE
        )

        self.timesheet = self.contract.get_or_create_current_timesheet()
        for entry in self.timesheet.entries.all()[:5]:
            entry.hours_worked = Decimal('8.00')
            entry.charts_coded_count = 25
            entry.work_description = 'Inpatient medical chart audit.'
            entry.save()
        self.timesheet.status = Timesheet.Status.APPROVED
        self.timesheet.save()

        self.invoice = generate_invoice_for_timesheet(self.timesheet)

    def test_checkout_ui_render_and_verification(self):
        # 1. Employer views invoice with interactive multi-rail checkout
        self.client.login(username='health_employer', password='testpassword123')
        res = self.client.get(f'/billing/invoices/{self.invoice.pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "SECURE ESCROW CHECKOUT")
        self.assertContains(res, "International Card")
        self.assertContains(res, "Mobile Money (GHS)")
        self.assertContains(res, "Direct 1-Click")

        # 2. Verify payment via Flutterwave checkout callback
        import json
        res_flw = self.client.post(
            f'/billing/invoices/{self.invoice.pk}/verify-payment/',
            data=json.dumps({
                'gateway': 'FLUTTERWAVE',
                'transaction_id': 'flw_unit_test_tx_12345'
            }),
            content_type='application/json'
        )
        self.assertEqual(res_flw.status_code, 200)
        self.assertEqual(res_flw.json()['status'], 'success')

        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.payment_status, ContractInvoice.PaymentStatus.SETTLED)
        self.assertEqual(self.invoice.payout_status, ContractInvoice.PayoutStatus.QUEUED)
        self.assertEqual(self.invoice.gateway_provider, ContractInvoice.GatewayProvider.FLUTTERWAVE)



class ScheduledAutomationEngineTests(TestCase):
    """
    Automated Unit and Integration Tests for Option 3: Scheduled Automation Engine.
    - Weekly Timesheet Lock Engine (Sunday 23:59 Cron / Staff Hub)
    - Friday Batch Payout Disbursement Engine (Friday 09:00 Cron / Staff Hub)
    - Staff Automation Hub UI & Permissions
    - Django Management Commands
    """
    def setUp(self):
        self.client = Client()

        # 1. Staff User
        self.staff_user = User.objects.create_user(
            username='ops_officer',
            email='ops@kodafriq.com',
            password='testpassword123',
            role=User.Role.ADMIN,
            is_staff=True
        )
        perm_auto = Permission.objects.get(content_type__app_label='dashboard', codename='access_automation')
        perm_pay = Permission.objects.get(content_type__app_label='dashboard', codename='access_payments')
        self.staff_user.user_permissions.add(perm_auto, perm_pay)

        # 2. Employer Setup
        self.employer_user = User.objects.create_user(
            username='korle_bu_cfo',
            email='cfo@korlebu.gov.gh',
            password='testpassword123',
            role=User.Role.EMPLOYER
        )
        self.employer_profile, _ = EmployerProfile.objects.get_or_create(
            user=self.employer_user,
            defaults={'company_name': "Korle Bu Premier Hospital"}
        )

        # 3. Candidate 1 (Paystack MoMo)
        self.candidate1_user = User.objects.create_user(
            username='talent_kofi',
            email='kofi@kodafriq.com',
            first_name='Kofi',
            last_name='Mensah',
            password='testpassword123',
            role=User.Role.CANDIDATE
        )
        self.candidate1_profile, _ = CandidateProfile.objects.get_or_create(
            user=self.candidate1_user,
            defaults={'headline': "Lead Outpatient HIM Specialist"}
        )
        self.payout_profile1, _ = CandidatePayoutProfile.objects.get_or_create(
            candidate=self.candidate1_profile,
            defaults={
                'payout_method': CandidatePayoutProfile.PayoutMethod.PAYSTACK_MOMO,
                'momo_network': CandidatePayoutProfile.MoMoNetwork.MTN,
                'momo_phone_number': '0244123456',
                'momo_account_name': 'Kofi Mensah',
                'is_verified': True
            }
        )

        # 4. Candidate 2 (No payout destination configured)
        self.candidate2_user = User.objects.create_user(
            username='talent_yaa',
            email='yaa@kodafriq.com',
            password='testpassword123',
            role=User.Role.CANDIDATE
        )
        self.candidate2_profile, _ = CandidateProfile.objects.get_or_create(
            user=self.candidate2_user,
            defaults={'headline': "Pediatric Clinical Coder"}
        )

        # 5. Contract 1 (Hourly, Active)
        self.contract1 = Contract.objects.create(
            employer=self.employer_profile,
            candidate=self.candidate1_profile,
            title="Outpatient Clinic Coding",
            contract_type=Contract.ContractType.HOURLY,
            rate_per_hour=Decimal('20.00'),
            kodafriq_fee_percent=Decimal('10.00'),
            status=Contract.Status.ACTIVE
        )

        # Pre-populate draft timesheet with 30 hours for Contract 1
        today = timezone.localdate()
        self.timesheet1 = self.contract1.get_or_create_current_timesheet(target_date=today)
        for entry in self.timesheet1.entries.all()[:3]:
            entry.hours_worked = Decimal('10.00')
            entry.charts_coded_count = 35
            entry.save()

    def test_weekly_timesheet_lock_dry_run_vs_live(self):
        from apps.billing.services.automation import lock_closing_timesheets

        # 1. Dry run execution
        dry_result = lock_closing_timesheets(as_of_date=self.timesheet1.week_end_date, dry_run=True, force=True)
        self.assertTrue(dry_result['success'])
        self.assertTrue(dry_result['is_dry_run'])
        self.assertEqual(dry_result['timesheets_locked'], 1)
        self.assertEqual(Decimal(str(dry_result['total_hours'])), Decimal('30.00'))

        # Verify no database mutation occurred
        self.timesheet1.refresh_from_db()
        self.assertEqual(self.timesheet1.status, Timesheet.Status.DRAFT)
        self.assertFalse(ContractInvoice.objects.filter(timesheet=self.timesheet1).exists())

        # 2. Live execution
        live_result = lock_closing_timesheets(as_of_date=self.timesheet1.week_end_date, dry_run=False, actor=self.staff_user, force=True)
        self.assertTrue(live_result['success'])
        self.assertFalse(live_result['is_dry_run'])
        self.assertEqual(live_result['timesheets_locked'], 1)

        # Verify timesheet transitioned to SUBMITTED
        self.timesheet1.refresh_from_db()
        self.assertEqual(self.timesheet1.status, Timesheet.Status.SUBMITTED)
        self.assertIsNotNone(self.timesheet1.submitted_at)

        # Verify Invoice was created in ISSUED status
        invoice = ContractInvoice.objects.get(timesheet=self.timesheet1)
        self.assertEqual(invoice.payment_status, ContractInvoice.PaymentStatus.ISSUED)
        self.assertEqual(invoice.talent_earnings, Decimal('600.00')) # 30 hrs * $20

        # Verify next week timesheet was initialized with 7 entries
        next_mon = self.timesheet1.week_end_date + timedelta(days=1)
        next_ts = Timesheet.objects.filter(contract=self.contract1, week_start_date=next_mon).first()
        self.assertIsNotNone(next_ts)
        self.assertEqual(next_ts.entries.count(), 7)

    def test_friday_payout_engine_settled_disbursement(self):
        from apps.billing.services.automation import execute_friday_payout_run

        # Lock timesheet and issue invoice
        self.timesheet1.status = Timesheet.Status.APPROVED
        self.timesheet1.save()
        invoice = generate_invoice_for_timesheet(self.timesheet1)
        
        # Employer settles invoice
        invoice.mark_settled(gateway_charge_ref="flw_test_settle_8899")
        self.assertEqual(invoice.payout_status, ContractInvoice.PayoutStatus.QUEUED)

        # Create another queued invoice for Candidate 2 (who has NO configured payout method)
        contract2 = Contract.objects.create(
            employer=self.employer_profile,
            candidate=self.candidate2_profile,
            title="Pediatric Coding",
            contract_type=Contract.ContractType.HOURLY,
            rate_per_hour=Decimal('15.00'),
            status=Contract.Status.ACTIVE
        )
        ts2 = contract2.get_or_create_current_timesheet()
        for e in ts2.entries.all()[:2]:
            e.hours_worked = Decimal('8.00')
            e.save()
        ts2.status = Timesheet.Status.APPROVED
        ts2.save()
        invoice2 = generate_invoice_for_timesheet(ts2)
        invoice2.mark_settled(gateway_charge_ref="flw_test_settle_9900")

        # 1. Dry run payout execution
        dry_payout = execute_friday_payout_run(dry_run=True, force=True)
        self.assertTrue(dry_payout['success'])
        self.assertEqual(dry_payout['candidates_paid'], 1)
        self.assertEqual(dry_payout['candidates_skipped'], 1) # Candidate 2 skipped

        # Verify invoices remain QUEUED in dry run
        invoice.refresh_from_db()
        self.assertEqual(invoice.payout_status, ContractInvoice.PayoutStatus.QUEUED)

        # 2. Live payout execution
        live_payout = execute_friday_payout_run(dry_run=False, actor=self.staff_user, force=True)
        self.assertTrue(live_payout['success'])
        self.assertEqual(live_payout['candidates_paid'], 1)
        self.assertEqual(live_payout['candidates_skipped'], 1)

        # Candidate 1 invoice must be COMPLETED
        invoice.refresh_from_db()
        self.assertEqual(invoice.payout_status, ContractInvoice.PayoutStatus.COMPLETED)
        self.assertIsNotNone(invoice.disbursed_at)

        # Verify PaymentTransaction (PAYOUT) record created
        tx = PaymentTransaction.objects.filter(invoice=invoice, transaction_type=PaymentTransaction.TransactionType.PAYOUT).first()
        self.assertIsNotNone(tx)
        self.assertEqual(tx.status, PaymentTransaction.Status.SUCCESS)

        # Candidate 2 invoice remains QUEUED / on hold
        invoice2.refresh_from_db()
        self.assertEqual(invoice2.payout_status, ContractInvoice.PayoutStatus.QUEUED)

    def test_staff_automation_hub_ui_and_permissions(self):
        import json
        url = '/billing/automation/'

        # 1. Anonymous user redirected to login
        res_anon = self.client.get(url)
        self.assertEqual(res_anon.status_code, 302)

        # 2. Candidate user blocked
        self.client.login(username='talent_kofi', password='testpassword123')
        res_candidate = self.client.get(url)
        self.assertEqual(res_candidate.status_code, 302)

        # 3. Staff user access granted
        self.client.login(username='ops_officer', password='testpassword123')
        res_staff = self.client.get(url)
        self.assertEqual(res_staff.status_code, 200)
        self.assertContains(res_staff, "Scheduled Automation Engine &amp; Payout Cron")
        self.assertContains(res_staff, "Engine 1: Weekly Timesheet Lock")
        self.assertContains(res_staff, "Engine 2: Friday Batch Payout")
        self.assertContains(res_staff, "59 23 * * 0")
        self.assertContains(res_staff, "0 9 * * 5")

        # 4. Trigger lock engine via AJAX POST
        res_ajax_lock = self.client.post(
            url,
            data={'action': 'lock_timesheets', 'dry_run': '1', 'force': '1'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            HTTP_ACCEPT='application/json'
        )
        self.assertEqual(res_ajax_lock.status_code, 200)
        data_lock = res_ajax_lock.json()
        self.assertEqual(data_lock['status'], 'success')
        self.assertTrue(data_lock['result']['is_dry_run'])

    def test_cli_management_commands(self):
        from django.core.management import call_command
        import io

        out_lock = io.StringIO()
        call_command('lock_weekly_timesheets', dry_run=True, force=True, stdout=out_lock)
        self.assertIn("Starting Weekly Timesheet Lock Engine", out_lock.getvalue())
        self.assertIn("DRY RUN COMPLETE", out_lock.getvalue())

        out_payout = io.StringIO()
        call_command('execute_friday_payouts', dry_run=True, force=True, stdout=out_payout)
        self.assertIn("Starting Friday Batch Payout Engine", out_payout.getvalue())
        self.assertIn("DRY RUN COMPLETE", out_payout.getvalue())


    def test_payments_overview_hub_access_and_filters(self):
        url = '/billing/payments/'

        # 1. Anonymous user blocked
        res_anon = self.client.get(url)
        self.assertEqual(res_anon.status_code, 302)

        # 2. Candidate blocked
        self.client.login(username='talent_kofi', password='testpassword123')
        res_candidate = self.client.get(url)
        self.assertEqual(res_candidate.status_code, 302)

        # 3. Staff user access granted
        self.client.login(username='ops_officer', password='testpassword123')
        res_staff = self.client.get(url)
        self.assertEqual(res_staff.status_code, 200)
        self.assertContains(res_staff, "Platform Payments &amp; Payouts Command Center")
        self.assertContains(res_staff, "All Cashflows")
        self.assertContains(res_staff, "Employer Charges (Inflow)")
        self.assertContains(res_staff, "Talent Payouts (Outflow)")
        self.assertContains(res_staff, "Platform 10% Revenue")

        # 4. Filter by flow: employers
        res_emp_flow = self.client.get(url + '?flow=employers')
        self.assertEqual(res_emp_flow.status_code, 200)

        # 5. Filter by flow: candidates
        res_cand_flow = self.client.get(url + '?flow=candidates')
        self.assertEqual(res_cand_flow.status_code, 200)

        # 6. Filter by individual user (Candidate Kofi)
        res_user_filter = self.client.get(f"{url}?user_id={self.candidate1_user.id}")
        self.assertEqual(res_user_filter.status_code, 200)
        self.assertContains(res_user_filter, "Kofi Mensah")
        self.assertContains(res_user_filter, "Healthcare Professional / Talent")

        # 7. CSV Export
        res_csv = self.client.get(url + '?export=csv')
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv['Content-Type'], 'text/csv')
        self.assertIn("Invoice Ref,Date Created", res_csv.content.decode('utf-8'))
