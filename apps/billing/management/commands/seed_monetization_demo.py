import uuid
from datetime import date, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.accounts.models import CandidateProfile, EmployerProfile
from apps.employers.models import Job
from apps.contracts.models import Contract, Timesheet, TimesheetEntry, Milestone, DisputeCase
from apps.billing.models import (
    PlatformFeeConfig,
    PaymentGatewayConfig,
    CandidatePayoutProfile,
    ContractInvoice,
    PaymentTransaction
)
from apps.dashboard.models import send_notification, Notification

User = get_user_model()


class Command(BaseCommand):
    help = "Seed realistic healthcare contracts, approved timesheets, settled invoices, and ledger records for demo."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== SEEDING KODAFRIQ MONETIZATION & CONTRACTS DEMO DATA ==="))

        # 1. Platform Fee Config
        fee_config = PlatformFeeConfig.objects.first()
        if not fee_config:
            fee_config = PlatformFeeConfig.objects.create()
        fee_config.fee_percent = Decimal('10.00')
        fee_config.gateway_processing_fee_percent = Decimal('2.90')
        fee_config.gateway_flat_fee = Decimal('0.30')
        fee_config.is_active = True
        fee_config.save()
        self.stdout.write(self.style.SUCCESS("✓ Platform Fee Config confirmed (10% platform, 2.9% + $0.30 gateway)"))

        # 1b. Payment Gateway Configuration (Paystack & Flutterwave API)
        gateway_cfg = PaymentGatewayConfig.objects.filter(is_active=True).first()
        if not gateway_cfg:
            gateway_cfg = PaymentGatewayConfig.objects.create(
                paystack_enabled=True,
                paystack_mode=PaymentGatewayConfig.Mode.TEST,
                paystack_public_key='pk_test_kodafriq_demo_key',
                paystack_secret_key='sk_test_kodafriq_demo_secret',
                flutterwave_enabled=True,
                flutterwave_mode=PaymentGatewayConfig.Mode.TEST,
                flutterwave_public_key='FLWPUBK_TEST-kodafriq_demo_key',
                flutterwave_secret_key='FLWSECK_TEST-kodafriq_demo_secret',
                flutterwave_secret_hash='kodafriq_webhook_hash',
                is_active=True
            )
        self.stdout.write(self.style.SUCCESS("✓ Payment Gateway API Config confirmed (Paystack & Flutterwave sandbox ready in Admin)"))

        # 2. Key Demo Users
        # Candidate 1: Ama Boateng (Senior Clinical Coder)
        ama_user, _ = User.objects.get_or_create(
            username='ama_boateng',
            defaults={
                'email': 'ama.boateng@clinical.org',
                'first_name': 'Ama',
                'last_name': 'Boateng',
                'role': User.Role.CANDIDATE
            }
        )
        if not ama_user.check_password('Kodafriq2026!'):
            ama_user.set_password('Kodafriq2026!')
            ama_user.save()
        ama_cand, _ = CandidateProfile.objects.get_or_create(
            user=ama_user,
            defaults={
                'headline': 'Senior Inpatient Clinical Coder (ICD-10-CM/PCS & DRG)',
                'years_of_experience': 6,
                'hourly_rate': Decimal('32.00'),
                'is_employer_ready': True,
                'kodafriq_verified_score': Decimal('94.5'),
                'availability_status': 'AVAILABLE'
            }
        )

        # Candidate 2: Solomon Itie (RCM & Denial Specialist)
        solo_user, _ = User.objects.get_or_create(
            username='solo',
            defaults={
                'email': 'solomonitie@gmail.com',
                'first_name': 'Solomon',
                'last_name': 'Itie',
                'role': User.Role.CANDIDATE
            }
        )
        if not solo_user.check_password('Kodafriq2026!'):
            solo_user.set_password('Kodafriq2026!')
            solo_user.save()
        solo_cand, _ = CandidateProfile.objects.get_or_create(
            user=solo_user,
            defaults={
                'headline': 'Revenue Cycle & Denial Management Specialist (CPC, CPB)',
                'years_of_experience': 4,
                'hourly_rate': Decimal('28.00'),
                'is_employer_ready': True,
                'kodafriq_verified_score': Decimal('88.0'),
                'availability_status': 'AVAILABLE'
            }
        )

        # Candidate 3: kinghez (Emergency Dept Coder)
        kinghez_user = User.objects.filter(username='kinghez').first()
        if not kinghez_user:
            kinghez_user = User.objects.create(
                username='kinghez',
                email='kinghez10@gmail.com',
                first_name='Hezekiah',
                last_name='King',
                role=User.Role.CANDIDATE
            )
            kinghez_user.set_password('Kodafriq2026!')
            kinghez_user.save()
        kinghez_cand, _ = CandidateProfile.objects.get_or_create(
            user=kinghez_user,
            defaults={
                'headline': 'Emergency Medicine HIM Specialist & Outpatient Coder',
                'years_of_experience': 3,
                'hourly_rate': Decimal('26.00'),
                'is_employer_ready': True,
                'kodafriq_verified_score': Decimal('86.0'),
                'availability_status': 'AVAILABLE'
            }
        )

        # Employer 1: Accra Premier / Dr. Kwabena Asante
        emp1_user, _ = User.objects.get_or_create(
            username='accra_premier',
            defaults={
                'email': 'hr@accrapremier.org',
                'first_name': 'Dr. Kwabena',
                'last_name': 'Asante',
                'role': User.Role.EMPLOYER
            }
        )
        if not emp1_user.check_password('Kodafriq2026!'):
            emp1_user.set_password('Kodafriq2026!')
            emp1_user.save()
        emp1_profile, _ = EmployerProfile.objects.get_or_create(
            user=emp1_user,
            defaults={
                'company_name': 'Hicov Healthcare Systems Ltd',
                'company_type': 'HOSPITAL',
                'location': 'Accra, Ghana / Global Health Division',
                'is_verified': True
            }
        )

        # Employer 2: Covtech / Hezekiah Itie
        emp2_user, _ = User.objects.get_or_create(
            username='covtech',
            defaults={
                'email': 'hi@hicovtech.com',
                'first_name': 'Hezekiah',
                'last_name': 'Itie',
                'role': User.Role.EMPLOYER
            }
        )
        if not emp2_user.check_password('Kodafriq2026!'):
            emp2_user.set_password('Kodafriq2026!')
            emp2_user.save()
        emp2_profile, _ = EmployerProfile.objects.get_or_create(
            user=emp2_user,
            defaults={
                'company_name': 'Covtech Health Partners',
                'company_type': 'BILLING_COMPANY',
                'location': 'Greater Accra, Ghana',
                'is_verified': True
            }
        )

        self.stdout.write(self.style.SUCCESS("✓ Key Candidate & Employer Profiles verified."))

        # 3. Payout Profiles
        # Ama: Flutterwave Bank Transfer
        payout_ama, _ = CandidatePayoutProfile.objects.get_or_create(
            candidate=ama_cand,
            defaults={
                'payout_method': CandidatePayoutProfile.PayoutMethod.FLUTTERWAVE_BANK,
                'bank_name': 'Ecobank Ghana Ltd',
                'account_number': '1441002938475',
                'account_name': 'Ama Serwaa Boateng',
                'currency': 'GHS',
                'bank_country': 'Ghana',
                'is_verified': True
            }
        )

        # Solo: Paystack Mobile Money (MTN)
        payout_solo, _ = CandidatePayoutProfile.objects.get_or_create(
            candidate=solo_cand,
            defaults={
                'payout_method': CandidatePayoutProfile.PayoutMethod.PAYSTACK_MOMO,
                'momo_network': CandidatePayoutProfile.MoMoNetwork.MTN,
                'momo_phone_number': '0244123890',
                'momo_account_name': 'Solomon Itie',
                'is_verified': True
            }
        )

        # Kinghez: Paystack Mobile Money (MTN)
        payout_kinghez, _ = CandidatePayoutProfile.objects.get_or_create(
            candidate=kinghez_cand,
            defaults={
                'payout_method': CandidatePayoutProfile.PayoutMethod.PAYSTACK_MOMO,
                'momo_network': CandidatePayoutProfile.MoMoNetwork.MTN,
                'momo_phone_number': '0555987654',
                'momo_account_name': 'Hezekiah King',
                'is_verified': True
            }
        )
        self.stdout.write(self.style.SUCCESS("✓ Candidate Payout Profiles configured (Bank & MoMo)."))

        # 4. Job Posts
        job_inpatient, _ = Job.objects.get_or_create(
            employer=emp1_profile,
            title='Senior Inpatient Clinical Coder (ICD-10 / DRG)',
            defaults={
                'description': 'High-volume inpatient coding for tertiary health system. Remote position.',
                'job_type': Job.JobType.CONTRACT,
                'status': Job.JobStatus.ACTIVE
            }
        )

        job_rcm, _ = Job.objects.get_or_create(
            employer=emp2_profile,
            title='Revenue Cycle & Denial Management Specialist',
            defaults={
                'description': 'Root cause denial audits and appeal pack creation for commercial US payers.',
                'job_type': Job.JobType.CONTRACT,
                'status': Job.JobStatus.ACTIVE
            }
        )

        # 5. CONTRACT 1: Hourly, Active, Multi-Week (Ama Boateng & Accra Premier)
        c1, created = Contract.objects.get_or_create(
            employer=emp1_profile,
            candidate=ama_cand,
            title='Senior Inpatient Clinical Coder (ICD-10 / DRG)',
            defaults={
                'job': job_inpatient,
                'contract_type': Contract.ContractType.HOURLY,
                'status': Contract.Status.ACTIVE,
                'rate_per_hour': Decimal('32.00'),
                'kodafriq_fee_percent': Decimal('10.00'),
                'weekly_hour_limit': 40,
                'start_date': date.today() - timedelta(days=21),
                'scope_of_work': (
                    "Abstract and assign ICD-10-CM diagnosis codes and ICD-10-PCS procedure codes "
                    "for acute inpatient discharges. Verify MS-DRG grouping, APR-DRG risk of mortality, "
                    "and severity of illness. Target productivity: 3.5 - 4 charts per hour at >=95% accuracy."
                )
            }
        )
        if not created and c1.status != Contract.Status.ACTIVE:
            c1.status = Contract.Status.ACTIVE
            c1.save()

        # Date calculations for past 3 Monday-aligned weeks
        today = date.today()
        curr_monday = today - timedelta(days=today.weekday())
        week1_monday = curr_monday - timedelta(days=14)
        week2_monday = curr_monday - timedelta(days=7)
        week3_monday = curr_monday

        # --- WEEK 1: SETTLED & PAID OUT ---
        ts1, _ = Timesheet.objects.get_or_create(
            contract=c1,
            week_start_date=week1_monday,
            defaults={
                'week_end_date': week1_monday + timedelta(days=6),
                'status': Timesheet.Status.APPROVED,
                'submitted_at': timezone.now() - timedelta(days=9),
                'reviewed_at': timezone.now() - timedelta(days=8),
                'employer_review_notes': 'Exceptional DRG accuracy. All 146 inpatient charts verified with zero coding queries.'
            }
        )
        if ts1.entries.count() == 0:
            for day_idx in range(5):
                d = week1_monday + timedelta(days=day_idx)
                TimesheetEntry.objects.create(
                    timesheet=ts1,
                    date=d,
                    hours_worked=Decimal('7.70'),
                    charts_coded_count=29,
                    work_description="Inpatient coding: Cardiology & Orthopedic surgery charts on EHR (Epic/Cerner). Assigned ICD-10-PCS."
                )

        # Invoice for Week 1: Settled & Completed
        inv1, _ = ContractInvoice.objects.get_or_create(
            contract=c1,
            timesheet=ts1,
            defaults={
                'invoice_ref': f"INV-{week1_monday.strftime('%Y%m%d')}-001",
                'billing_period_start': week1_monday,
                'billing_period_end': week1_monday + timedelta(days=6),
                'talent_earnings': Decimal('1232.00'),  # 38.5 * $32
                'kodafriq_fee': Decimal('123.20'),     # 10%
                'processing_fee': Decimal('40.00'),
                'gross_amount': Decimal('1395.20'),
                'payment_status': ContractInvoice.PaymentStatus.SETTLED,
                'payout_status': ContractInvoice.PayoutStatus.COMPLETED,
                'gateway_provider': ContractInvoice.GatewayProvider.FLUTTERWAVE,
                'gateway_charge_ref': f"FLW-CHG-{uuid.uuid4().hex[:10].upper()}",
                'gateway_payout_ref': f"FLW-DISB-{uuid.uuid4().hex[:10].upper()}",
                'settled_at': timezone.now() - timedelta(days=7),
                'due_date': week1_monday + timedelta(days=10)
            }
        )

        PaymentTransaction.objects.get_or_create(
            reference=inv1.gateway_charge_ref,
            defaults={
                'invoice': inv1,
                'gateway': PaymentTransaction.Gateway.FLUTTERWAVE,
                'transaction_type': PaymentTransaction.TransactionType.CHARGE,
                'amount': inv1.gross_amount,
                'currency': 'USD',
                'status': PaymentTransaction.Status.SUCCESS,
                'raw_payload': {'event': 'charge.completed', 'status': 'successful', 'amount': float(inv1.gross_amount)}
            }
        )

        PaymentTransaction.objects.get_or_create(
            reference=inv1.gateway_payout_ref,
            defaults={
                'invoice': inv1,
                'gateway': PaymentTransaction.Gateway.FLUTTERWAVE,
                'transaction_type': PaymentTransaction.TransactionType.PAYOUT,
                'amount': inv1.talent_earnings,
                'currency': 'GHS',
                'status': PaymentTransaction.Status.SUCCESS,
                'raw_payload': {'event': 'transfer.success', 'recipient_bank': 'Ecobank Ghana', 'amount_ghs': float(inv1.talent_earnings * Decimal('15.5'))}
            }
        )

        # --- WEEK 2: SETTLED & QUEUED FOR FRIDAY PAYOUT ---
        # (This provides the LIVE "Available Balance: $1,280.00" on Ama's dashboard!)
        ts2, _ = Timesheet.objects.get_or_create(
            contract=c1,
            week_start_date=week2_monday,
            defaults={
                'week_end_date': week2_monday + timedelta(days=6),
                'status': Timesheet.Status.APPROVED,
                'submitted_at': timezone.now() - timedelta(days=2),
                'reviewed_at': timezone.now() - timedelta(days=1),
                'employer_review_notes': 'Weekly quota met ahead of schedule. Released for upcoming Friday payroll run.'
            }
        )
        if ts2.entries.count() == 0:
            for day_idx in range(5):
                d = week2_monday + timedelta(days=day_idx)
                TimesheetEntry.objects.create(
                    timesheet=ts2,
                    date=d,
                    hours_worked=Decimal('8.00'),
                    charts_coded_count=31,
                    work_description="Inpatient coding: Critical Care ICU & Neurological surgical encounters. Secondary CC/MCC validation."
                )

        inv2, _ = ContractInvoice.objects.get_or_create(
            contract=c1,
            timesheet=ts2,
            defaults={
                'invoice_ref': f"INV-{week2_monday.strftime('%Y%m%d')}-002",
                'billing_period_start': week2_monday,
                'billing_period_end': week2_monday + timedelta(days=6),
                'talent_earnings': Decimal('1280.00'),  # 40 * $32
                'kodafriq_fee': Decimal('128.00'),     # 10%
                'processing_fee': Decimal('41.50'),
                'gross_amount': Decimal('1449.50'),
                'payment_status': ContractInvoice.PaymentStatus.SETTLED,
                'payout_status': ContractInvoice.PayoutStatus.QUEUED,
                'gateway_provider': ContractInvoice.GatewayProvider.FLUTTERWAVE,
                'gateway_charge_ref': f"FLW-CHG-{uuid.uuid4().hex[:10].upper()}",
                'settled_at': timezone.now() - timedelta(hours=18),
                'due_date': week2_monday + timedelta(days=10)
            }
        )

        # --- WEEK 3: CURRENT WEEK IN PROGRESS (SUBMITTED / PENDING REVIEW) ---
        # (Provides the "Pending Review: $720.00" on Ama's dashboard!)
        ts3, _ = Timesheet.objects.get_or_create(
            contract=c1,
            week_start_date=week3_monday,
            defaults={
                'week_end_date': week3_monday + timedelta(days=6),
                'status': Timesheet.Status.SUBMITTED,
                'submitted_at': timezone.now() - timedelta(hours=4),
            }
        )
        if ts3.entries.count() == 0:
            for day_idx in range(3):
                d = week3_monday + timedelta(days=day_idx)
                TimesheetEntry.objects.create(
                    timesheet=ts3,
                    date=d,
                    hours_worked=Decimal('7.50'),
                    charts_coded_count=28,
                    work_description="Active coding: General internal medicine & oncology encounters. Pending physician query resolution."
                )

        # Invoice for Week 3: ISSUED (Payment Pending from Employer)
        # Enables employer (accra_premier) to test interactive checkout on /billing/invoices/!
        inv3, _ = ContractInvoice.objects.get_or_create(
            contract=c1,
            timesheet=ts3,
            defaults={
                'invoice_ref': f"INV-{week3_monday.strftime('%Y%m%d')}-003",
                'billing_period_start': week3_monday,
                'billing_period_end': week3_monday + timedelta(days=6),
                'talent_earnings': Decimal('720.00'),  # 22.5 hrs * $32
                'kodafriq_fee': Decimal('72.00'),     # 10%
                'processing_fee': Decimal('23.27'),   # (792 * 2.9%) + 0.30
                'gross_amount': Decimal('815.27'),
                'payment_status': ContractInvoice.PaymentStatus.ISSUED,
                'payout_status': ContractInvoice.PayoutStatus.PENDING,
                'due_date': week3_monday + timedelta(days=10)
            }
        )

        self.stdout.write(self.style.SUCCESS("✓ Contract 1 (Hourly: Ama Boateng) seeded with 3-week full financial ledger."))

        # 6. CONTRACT 2: Milestone-Based Project (Solomon Itie & Covtech)
        c2, created2 = Contract.objects.get_or_create(
            employer=emp2_profile,
            candidate=solo_cand,
            title='Comprehensive RCM & Denial Remediation Audit',
            defaults={
                'job': job_rcm,
                'contract_type': Contract.ContractType.MILESTONE,
                'status': Contract.Status.ACTIVE,
                'rate_per_hour': Decimal('0.00'),
                'kodafriq_fee_percent': Decimal('10.00'),
                'total_milestone_amount': Decimal('2800.00'),
                'start_date': date.today() - timedelta(days=14),
                'scope_of_work': (
                    "Conduct in-depth root-cause analysis on $1.4M in commercial payer denials (Aetna, BCBS, UnitedHealthcare). "
                    "Draft appeal playbooks, correct CPT/HCPCS modifier bundling issues, and lead 2 remediation workshops."
                )
            }
        )

        # Milestone 1: Approved & Paid Out ($900.00)
        m1, _ = Milestone.objects.get_or_create(
            contract=c2,
            order=1,
            defaults={
                'title': 'Milestone 1: 90-Day Payer Denial Root-Cause Audit Report',
                'description': 'Deliverable: Comprehensive audit matrix categorizing 450 denials by CARC/RARC codes with financial impact.',
                'amount': Decimal('900.00'),
                'status': Milestone.Status.APPROVED,
                'submission_notes': 'Audit completed. Identified 3 high-volume modifier -59 omissions recovering $142,000 in clean claims.',
                'submitted_at': timezone.now() - timedelta(days=6),
                'approved_at': timezone.now() - timedelta(days=5),
                'employer_feedback': 'Approved. Clean analysis with actionable recoveries.'
            }
        )

        inv_m1, _ = ContractInvoice.objects.get_or_create(
            contract=c2,
            milestone=m1,
            defaults={
                'invoice_ref': f"INV-MILE-001-{uuid.uuid4().hex[:6].upper()}",
                'billing_period_start': date.today() - timedelta(days=14),
                'billing_period_end': date.today() - timedelta(days=5),
                'talent_earnings': Decimal('900.00'),
                'kodafriq_fee': Decimal('90.00'),
                'processing_fee': Decimal('29.00'),
                'gross_amount': Decimal('1019.00'),
                'payment_status': ContractInvoice.PaymentStatus.SETTLED,
                'payout_status': ContractInvoice.PayoutStatus.COMPLETED,
                'gateway_provider': ContractInvoice.GatewayProvider.PAYSTACK,
                'gateway_charge_ref': f"PSTK-CHG-{uuid.uuid4().hex[:10].upper()}",
                'gateway_payout_ref': f"PSTK-TRF-{uuid.uuid4().hex[:10].upper()}",
                'settled_at': timezone.now() - timedelta(days=5),
                'due_date': date.today() - timedelta(days=5)
            }
        )

        # Milestone 2: Deliverable Submitted, Under Review ($1,100.00)
        m2, _ = Milestone.objects.get_or_create(
            contract=c2,
            order=2,
            defaults={
                'title': 'Milestone 2: EHR Template Optimization & Payer Appeal Playbook',
                'description': 'Deliverable: 15 customized appeal template letters and EHR coding scrubbing rule sets.',
                'amount': Decimal('1100.00'),
                'status': Milestone.Status.SUBMITTED,
                'submission_notes': 'All 15 appeal templates uploaded and verified against 2026 CMS NCCI edits. Ready for employer review.',
                'submitted_at': timezone.now() - timedelta(hours=12)
            }
        )

        # Milestone 3: Pending ($800.00)
        m3, _ = Milestone.objects.get_or_create(
            contract=c2,
            order=3,
            defaults={
                'title': 'Milestone 3: Clinical Staff Training & Clean Claim Assurance Walkthrough',
                'description': 'Deliverable: 2 interactive 90-minute live training sessions for billing team.',
                'amount': Decimal('800.00'),
                'status': Milestone.Status.PENDING
            }
        )

        self.stdout.write(self.style.SUCCESS("✓ Contract 2 (Milestone: Solomon Itie) seeded with deliverables & payment."))

        # 7. CONTRACT 3: Pending Offer (kinghez & Accra Premier)
        # Enables the user to test the "Accept / Decline Contract" workflow live!
        c3, created3 = Contract.objects.get_or_create(
            employer=emp1_profile,
            candidate=kinghez_cand,
            title='Emergency Medicine HIM & Level 5 Coding Specialist',
            defaults={
                'job': job_inpatient,
                'contract_type': Contract.ContractType.HOURLY,
                'status': Contract.Status.PENDING,
                'rate_per_hour': Decimal('26.00'),
                'kodafriq_fee_percent': Decimal('10.00'),
                'weekly_hour_limit': 35,
                'start_date': date.today() + timedelta(days=3),
                'scope_of_work': (
                    "Review and code Level 1 through Level 5 Emergency Department charts. "
                    "Assign appropriate E/M levels, CPT procedure codes (lacerations, bedside ultrasounds, "
                    "intubations), and primary ICD-10-CM diagnosis codes."
                )
            }
        )
        self.stdout.write(self.style.SUCCESS("✓ Contract 3 (Pending Offer for 'kinghez') seeded for live acceptance testing."))

        # 8. Dispute Mediation Center Demo Records
        # Open Dispute: Flagged Timesheet on Contract 1
        ts_dispute_mon = week1_monday - timedelta(days=7)
        ts_disputed, _ = Timesheet.objects.get_or_create(
            contract=c1,
            week_start_date=ts_dispute_mon,
            defaults={
                'week_end_date': ts_dispute_mon + timedelta(days=6),
                'status': Timesheet.Status.DISPUTED,
                'submitted_at': timezone.now() - timedelta(days=12),
                'reviewed_at': timezone.now() - timedelta(days=10),
                'employer_review_notes': "Flagged for arbitration: 12 inpatient encounters coded under secondary hypertension lack secondary CC/MCC clinical indicators."
            }
        )
        if ts_disputed.entries.count() == 0:
            for day_idx in range(5):
                d = ts_dispute_mon + timedelta(days=day_idx)
                TimesheetEntry.objects.create(
                    timesheet=ts_disputed,
                    date=d,
                    hours_worked=Decimal('7.20'),
                    charts_coded_count=26,
                    work_description="Inpatient chart abstraction: General cardiology & pulmonary inpatient discharges."
                )

        d_open, _ = DisputeCase.objects.get_or_create(
            contract=c1,
            timesheet=ts_disputed,
            defaults={
                'raised_by': emp1_user,
                'reason': "Employer internal HIM audit supervisor identified 12 inpatient charts coded with secondary CC/MCC diagnoses that were not clinically substantiated in physician progress notes. Requesting timecard audit reconciliation of 6.0 hours ($192.00) before authorizing payment release.",
                'status': DisputeCase.Status.OPEN
            }
        )

        # Resolved Dispute: Historical Milestone on Contract 2
        d_resolved, _ = DisputeCase.objects.get_or_create(
            contract=c2,
            milestone=m1,
            defaults={
                'raised_by': emp2_user,
                'reason': "Initial denial audit spreadsheet was missing CARC/RARC remittance reason code mappings for Aetna and UnitedHealthcare claim lines.",
                'status': DisputeCase.Status.RESOLVED,
                'resolution_notes': "[Adjudication: Ruled in Favor of Candidate] Kodafriq Staff clinical review verified candidate subsequently uploaded comprehensive Appendix B containing full 2026 CARC remittance crosswalks recovering $142,000. Deliverable approved and $900.00 payment released.",
                'resolved_at': timezone.now() - timedelta(days=4)
            }
        )

        self.stdout.write(self.style.SUCCESS("✓ Dispute Mediation Center demo cases seeded (1 Open in Mediation, 1 Resolved)."))

        # 8. Demo In-App Notifications
        send_notification(
            recipient=ama_user,
            title="Timesheet Approved ($1,280.00)",
            message="Dr. Kwabena Asante approved your 40.0 hours timesheet. Your payout of $1,280.00 is queued for this Friday's payout run.",
            notification_type=Notification.NotificationType.SYSTEM
        )
        send_notification(
            recipient=solo_user,
            title="Milestone 1 Payment Disbursed ($900.00)",
            message="Payment for 'Milestone 1: 90-Day Payer Denial Root-Cause Audit' has been transferred to your MTN Mobile Money wallet.",
            notification_type=Notification.NotificationType.SYSTEM
        )
        send_notification(
            recipient=kinghez_user,
            title="New Formal Contract Offer Received",
            message="Hicov Healthcare Systems Ltd has extended a formal hourly contract offer: Emergency Medicine HIM Specialist at $26.00/hr.",
            notification_type=Notification.NotificationType.SYSTEM
        )

        self.stdout.write(self.style.SUCCESS("\n=== DEMO DATA SEEDED SUCCESSFULLY ==="))
        self.stdout.write(
            "Test Accounts & Scenarios Ready to Demo:\n"
            "--------------------------------------------------------------------------------\n"
            "1. Candidate: Ama Boateng (username: ama_boateng / password: Kodafriq2026!)\n"
            "   - Available Balance: $1,280.00 (Settled, queued for Friday payout)\n"
            "   - Under Review: $720.00 (Week 3 timesheet submitted)\n"
            "   - Paid to Date: $1,232.00 (Week 1 disbursed via Flutterwave to Ecobank)\n"
            "   - Ledger URL: /billing/ledger/\n"
            "   - Payout Settings: /billing/payout/settings/\n\n"
            "2. Candidate: Solomon Itie (username: solo / password: Kodafriq2026!)\n"
            "   - Active Milestone Contract ($2,800 total)\n"
            "   - Milestone 1 Paid ($900 via Paystack MoMo)\n"
            "   - Milestone 2 In Review ($1,100)\n"
            "   - Milestone 3 Pending ($800)\n\n"
            "3. Candidate: Hezekiah King (username: kinghez / password: Kodafriq2026!)\n"
            "   - Pending Contract Offer from Accra Premier ($26.00/hr)\n"
            "   - Test 'Accept Offer' / 'Decline Offer' directly at /contracts/\n\n"
            "4. Employer: Accra Premier (username: accra_premier / password: Kodafriq2026!)\n"
            "   - Active Contracts & Invoices\n"
            "   - Timesheet review & settlement at /billing/invoices/\n"
            "--------------------------------------------------------------------------------\n"
        )
