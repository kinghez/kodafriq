from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.accounts.models import EmployerProfile, CandidateProfile
from apps.employers.models import Job
from .models import Contract, Timesheet, TimesheetEntry, Milestone

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
