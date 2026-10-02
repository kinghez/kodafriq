from django.contrib.auth.models import Permission
from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.accounts.models import EmployerProfile, CandidateProfile
from apps.employers.models import Job
from apps.billing.models import ContractInvoice
from apps.dashboard.models import Notification, AuditLog
from .models import Contract, Timesheet, TimesheetEntry, Milestone, DisputeCase

User = get_user_model()


class ContractsMonitizationTests(TestCase):
    def setUp(self):
        # Create Employer User & Profile
        self.employer_user = User.objects.create_user(
            username='hosp_admin',
            email='admin@metrohospital.org',
            password='testpassword123',
            role=User.Role.EMPLOYER
        )
        self.employer_profile, _ = EmployerProfile.objects.get_or_create(
            user=self.employer_user,
            defaults={'company_name': "Metro Health System", 'website': "https://metrohealth.org"}
        )
        self.employer_profile.company_name = "Metro Health System"
        self.employer_profile.website = "https://metrohealth.org"
        self.employer_profile.save()

        # Create Candidate User & Profile
        self.candidate_user = User.objects.create_user(
            username='talent_jane',
            email='jane@kodafriq.org',
            password='testpassword123',
            role=User.Role.CANDIDATE
        )
        self.candidate_profile, _ = CandidateProfile.objects.get_or_create(
            user=self.candidate_user,
            defaults={'headline': "Inpatient Medical Coder | CCS", 'phone': "+233241234567"}
        )
        self.candidate_profile.headline = "Inpatient Medical Coder | CCS"
        self.candidate_profile.phone = "+233241234567"
        self.candidate_profile.save()

        # Create Job
        self.job = Job.objects.create(
            employer=self.employer_profile,
            title="Inpatient DRG Coder"
        )

    def test_contract_creation_and_rate_calculations(self):
        """
        Verify:
        Candidate net rate: $7.00/hr
        Kodafriq platform markup: 10%
        Employer billed rate: $7.70/hr
        Platform fee per hour: $0.70/hr
        """
        contract = Contract.objects.create(
            employer=self.employer_profile,
            candidate=self.candidate_profile,
            job=self.job,
            title="Inpatient DRG Coder Contract",
            contract_type=Contract.ContractType.HOURLY,
            rate_per_hour=Decimal('7.00'),
            kodafriq_fee_percent=Decimal('10.00'),
            weekly_hour_limit=40
        )
        self.assertTrue(contract.contract_ref.startswith('KD-'))
        self.assertEqual(contract.billed_rate_per_hour, Decimal('7.70'))
        self.assertEqual(contract.platform_fee_per_hour, Decimal('0.70'))

    def test_timesheet_weekly_logging_and_totals(self):
        """
        Test generating 7 daily entries and calculating gross compensation,
        10% platform fee, and employer billed total.
        """
        contract = Contract.objects.create(
            employer=self.employer_profile,
            candidate=self.candidate_profile,
            title="Clinical Coder Contract",
            contract_type=Contract.ContractType.HOURLY,
            rate_per_hour=Decimal('10.00'),
            kodafriq_fee_percent=Decimal('10.00'),
            status=Contract.Status.ACTIVE
        )
        timesheet = contract.get_or_create_current_timesheet()
        self.assertEqual(timesheet.entries.count(), 7)

        # Candidate logs 8 hours on Mon, Tue, Wed, Thu, Fri (40 hours total)
        for entry in timesheet.entries.all()[:5]:
            entry.hours_worked = Decimal('8.00')
            entry.charts_coded_count = 25
            entry.work_description = "Coded 25 inpatient charts"
            entry.save()

        self.assertEqual(timesheet.total_hours, Decimal('40.00'))
        self.assertEqual(timesheet.total_charts_coded, 125)
        # Talent compensation = 40 * $10.00 = $400.00
        self.assertEqual(timesheet.talent_gross_earnings, Decimal('400.00'))
        # Kodafriq 10% fee = $40.00
        self.assertEqual(timesheet.kodafriq_fee, Decimal('40.00'))
        # Employer total charge = $440.00
        self.assertEqual(timesheet.total_employer_charge, Decimal('440.00'))

    def test_milestone_calculations(self):
        """
        Test milestone deliverable and 10% markup calculation.
        """
        contract = Contract.objects.create(
            employer=self.employer_profile,
            candidate=self.candidate_profile,
            title="Bulk Chart Audit",
            contract_type=Contract.ContractType.MILESTONE,
            total_milestone_amount=Decimal('500.00'),
            kodafriq_fee_percent=Decimal('10.00'),
            status=Contract.Status.ACTIVE
        )
        milestone = Milestone.objects.create(
            contract=contract,
            title="Batch 1: 500 Outpatient Charts Audited",
            amount=Decimal('500.00'),
            order=1
        )
        self.assertEqual(milestone.kodafriq_fee, Decimal('50.00'))
        self.assertEqual(milestone.total_employer_charge, Decimal('550.00'))

    def test_contract_views_render(self):
        # 1. Test Contract List for Employer
        self.client.login(username="hosp_admin", password="testpassword123")
        res = self.client.get("/contracts/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Healthcare Contracts")

        # 2. Test Contract Create View
        res_create = self.client.get("/contracts/new/")
        self.assertEqual(res_create.status_code, 200)
        self.assertContains(res_create, "Issue Healthcare Engagement Offer")

        # 3. Create active contract
        contract = Contract.objects.create(
            employer=self.employer_profile,
            candidate=self.candidate_profile,
            title="Telehealth Specialist",
            contract_type=Contract.ContractType.HOURLY,
            rate_per_hour=Decimal("12.00"),
            status=Contract.Status.ACTIVE
        )
        timesheet = contract.get_or_create_current_timesheet()

        # 4. Test Contract Detail View
        res_detail = self.client.get(f"/contracts/{contract.pk}/")
        self.assertEqual(res_detail.status_code, 200)
        self.assertContains(res_detail, contract.contract_ref)

        # 5. Test Employer Timesheet Review View
        res_review = self.client.get(f"/contracts/timesheet/{timesheet.pk}/review/")
        self.assertEqual(res_review.status_code, 200)
        self.assertContains(res_review, "Review Timesheet")

        # 6. Test Candidate Timesheet Log View
        self.client.logout()
        self.client.login(username="talent_jane", password="testpassword123")
        res_log = self.client.get(f"/contracts/timesheet/{timesheet.pk}/log/")
        self.assertEqual(res_log.status_code, 200)
        self.assertContains(res_log, "Timesheet Log")


class DisputeMediationTests(TestCase):
    def setUp(self):
        # Staff user
        self.staff_user = User.objects.create_user(
            username='staff_officer',
            email='moderator@kodafriq.com',
            password='testpassword123',
            role=User.Role.STAFF,
            is_staff=True
        )
        perm_disputes = Permission.objects.get(content_type__app_label='dashboard', codename='access_disputes')
        self.staff_user.user_permissions.add(perm_disputes)

        # Employer user & profile
        self.employer_user = User.objects.create_user(
            username='apex_health',
            email='director@apexhealth.org',
            password='testpassword123',
            role=User.Role.EMPLOYER
        )
        self.employer_profile, _ = EmployerProfile.objects.get_or_create(
            user=self.employer_user,
            defaults={'company_name': "Apex Health Systems"}
        )

        # Candidate user & profile
        self.candidate_user = User.objects.create_user(
            username='kofi_mensah',
            email='kofi@kodafriq.org',
            password='testpassword123',
            role=User.Role.CANDIDATE
        )
        self.candidate_profile, _ = CandidateProfile.objects.get_or_create(
            user=self.candidate_user,
            defaults={'headline': "Lead Outpatient Coding Auditor"}
        )

        # Contract
        self.contract = Contract.objects.create(
            employer=self.employer_profile,
            candidate=self.candidate_profile,
            title="Outpatient Facility Coder",
            contract_type=Contract.ContractType.HOURLY,
            rate_per_hour=Decimal('25.00'),
            kodafriq_fee_percent=Decimal('10.00'),
            status=Contract.Status.ACTIVE
        )

        # Timesheet
        self.timesheet = self.contract.get_or_create_current_timesheet()
        for entry in self.timesheet.entries.all()[:5]:
            entry.hours_worked = Decimal('8.00')
            entry.charts_coded_count = 20
            entry.work_description = "Reviewed outpatient emergency room encounters."
            entry.save()
        self.timesheet.status = Timesheet.Status.DISPUTED
        self.timesheet.save()

        # Dispute Case
        self.dispute = DisputeCase.objects.create(
            contract=self.contract,
            timesheet=self.timesheet,
            raised_by=self.employer_user,
            reason="Facility compliance officer noted that 8 encounters were logged without clinical discharge documentation.",
            status=DisputeCase.Status.OPEN
        )

    def test_dispute_rbac_access_control(self):
        # 1. Candidate access should be forbidden (403)
        self.client.login(username='kofi_mensah', password='testpassword123')
        res_cand = self.client.get('/contracts/disputes/')
        self.assertEqual(res_cand.status_code, 403)

        # 2. Employer access should be forbidden (403)
        self.client.logout()
        self.client.login(username='apex_health', password='testpassword123')
        res_emp = self.client.get('/contracts/disputes/')
        self.assertEqual(res_emp.status_code, 403)

        # 3. Staff access allowed (200)
        self.client.logout()
        self.client.login(username='staff_officer', password='testpassword123')
        res_staff = self.client.get('/contracts/disputes/')
        self.assertEqual(res_staff.status_code, 200)
        self.assertContains(res_staff, "Dispute Mediation Center")
        self.assertContains(res_staff, "Outpatient Facility")

    def test_dispute_detail_view(self):
        self.client.login(username='staff_officer', password='testpassword123')
        res = self.client.get(f'/contracts/disputes/{self.dispute.pk}/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Disputing Party Official Statement")
        self.assertContains(res, "Flagged Timesheet Clinical Audit Log")
        self.assertContains(res, "Enforce Adjudication")

    def test_adjudicate_favor_candidate(self):
        self.client.login(username='staff_officer', password='testpassword123')
        res = self.client.post(
            f'/contracts/disputes/{self.dispute.pk}/adjudicate/',
            {
                'decision': 'FAVOR_CANDIDATE',
                'mediator_notes': 'Clinical audit confirmed physician notes were present in supplementary EHR archive. Approving full 40 hours.'
            },
            follow=True
        )
        self.assertEqual(res.status_code, 200)

        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, DisputeCase.Status.RESOLVED)
        self.assertIn("Ruled in Favor of Candidate", self.dispute.resolution_notes)

        self.timesheet.refresh_from_db()
        self.assertEqual(self.timesheet.status, Timesheet.Status.APPROVED)

        # Invoice should exist
        inv = ContractInvoice.objects.filter(contract=self.contract, timesheet=self.timesheet).first()
        self.assertIsNotNone(inv)
        self.assertEqual(inv.talent_earnings, Decimal('1000.00'))  # 40 hrs * $25.00

        # AuditLog entry created
        audit = AuditLog.objects.filter(target_id=str(self.dispute.id)).first()
        self.assertIsNotNone(audit)

    def test_adjudicate_favor_employer(self):
        self.client.login(username='staff_officer', password='testpassword123')
        res = self.client.post(
            f'/contracts/disputes/{self.dispute.pk}/adjudicate/',
            {
                'decision': 'FAVOR_EMPLOYER',
                'mediator_notes': 'Candidate admitted incomplete charts were erroneously logged. Voiding payment obligation.'
            },
            follow=True
        )
        self.assertEqual(res.status_code, 200)

        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, DisputeCase.Status.RESOLVED)
        self.assertIn("Ruled in Favor of Employer", self.dispute.resolution_notes)

        self.timesheet.refresh_from_db()
        self.assertEqual(self.timesheet.status, Timesheet.Status.DRAFT)

    def test_adjudicate_compromise(self):
        self.client.login(username='staff_officer', password='testpassword123')
        res = self.client.post(
            f'/contracts/disputes/{self.dispute.pk}/adjudicate/',
            {
                'decision': 'COMPROMISE',
                'adjusted_hours': '32.00',
                'mediator_notes': 'Mediated compromise: Deducted 8 disputed hours, compensated 32 hours verified.'
            },
            follow=True
        )
        self.assertEqual(res.status_code, 200)

        self.dispute.refresh_from_db()
        self.assertEqual(self.dispute.status, DisputeCase.Status.RESOLVED)
        self.assertIn("Mediated Compromise", self.dispute.resolution_notes)

        self.timesheet.refresh_from_db()
        self.assertEqual(self.timesheet.status, Timesheet.Status.APPROVED)
        self.assertIn("32.00 hrs", self.timesheet.employer_review_notes)

        # Invoice should reflect adjusted earnings: 32 hrs * $25.00 = $800.00
        inv = ContractInvoice.objects.filter(contract=self.contract, timesheet=self.timesheet).first()
        self.assertIsNotNone(inv)
        self.assertEqual(inv.talent_earnings, Decimal('800.00'))
