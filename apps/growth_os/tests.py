import os
import tempfile
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import CandidateProfile
from apps.growth_os.models import (
    EmployerLead, LeadContact, HiringSignal, TalentReverseMatch,
    CRMOpportunity, CRMActivity, normalize_company_domain
)
from apps.growth_os.services.matcher import compute_lead_reverse_matches
from apps.growth_os.services.intent import calculate_lead_intent_score
from apps.growth_os.services.scraper import extract_skills_from_text, inspect_lead_career_page
from apps.growth_os.services.discovery import (
    search_healthcare_employers, import_discovered_lead, import_leads_from_csv
)

User = get_user_model()


class GrowthOSModelTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff_growth',
            email='staff@kodafriq.com',
            password='testpassword123',
            role=User.Role.STAFF
        )

    def test_domain_normalization(self):
        """Tests robust domain cleaning for deduplication."""
        self.assertEqual(normalize_company_domain('https://www.optum.com/en-us/careers'), 'optum.com')
        self.assertEqual(normalize_company_domain('http://ensemblehp.com?ref=google'), 'ensemblehp.com')
        self.assertEqual(normalize_company_domain('WWW.ConiferHealth.COM/'), 'coniferhealth.com')
        self.assertEqual(normalize_company_domain(''), '')

    def test_employer_lead_creation_and_auto_domain(self):
        """Lead saves normalized domain and website automatically."""
        lead = EmployerLead.objects.create(
            company_name='Optum Revenue Solutions',
            website='https://www.optum.com/services/rcm',
            assigned_staff=self.staff_user
        )
        self.assertEqual(lead.domain, 'optum.com')
        self.assertEqual(lead.priority_tier, 4)  # 0 intent, 0 fit -> Tier 4

    def test_intent_score_calculation(self):
        """Tests dynamic multi-variable Hiring Intent Score formula."""
        lead = EmployerLead.objects.create(
            company_name='MedCare Billing Group',
            domain='medcarebilling.com',
            careers_url='https://medcarebilling.com/careers'
        )
        # Base with careers url = 10 pts
        self.assertEqual(lead.recalculate_intent_score(), 10)

        # Add 3 vacancies (+30 pts)
        HiringSignal.objects.create(lead=lead, job_title='Medical Biller 1', days_open=10)
        HiringSignal.objects.create(lead=lead, job_title='Medical Biller 2', days_open=15)
        HiringSignal.objects.create(lead=lead, job_title='Senior Coder', days_open=35, is_persistent=True)  # +30 pts persistent!

        # Add verified contact (+20 pts)
        LeadContact.objects.create(
            lead=lead,
            full_name='Dr. Lisa Ray',
            email='lisa@medcarebilling.com',
            verification_status=LeadContact.VerificationStatus.VERIFIED_VALID,
            is_primary=True
        )

        # Expected score: 10 (careers) + 30 (3 vac) + 30 (persistent) + 20 (verified contact) = 90
        score = lead.recalculate_intent_score()
        self.assertEqual(score, 90)

    def test_priority_tier_quadrants(self):
        """Verifies priority tier quadrants based on Intent and Talent Fit combinations."""
        lead = EmployerLead.objects.create(company_name='Test Lead', domain='testquad.com')

        # Tier 1: High Intent (>=60) + High Fit (>=60)
        lead.hiring_intent_score = 80
        lead.talent_fit_score = 75
        self.assertEqual(lead.priority_tier, 1)

        # Tier 2: High Intent (>=60) + Low Fit (<60)
        lead.hiring_intent_score = 70
        lead.talent_fit_score = 45
        self.assertEqual(lead.priority_tier, 2)

        # Tier 3: Low Intent (<60) + High Fit (>=60)
        lead.hiring_intent_score = 30
        lead.talent_fit_score = 85
        self.assertEqual(lead.priority_tier, 3)

        # Tier 4: Low Intent (<60) + Low Fit (<60)
        lead.hiring_intent_score = 20
        lead.talent_fit_score = 30
        self.assertEqual(lead.priority_tier, 4)

    def test_primary_contact_uniqueness(self):
        """Marking a contact as primary unsets previous primary."""
        lead = EmployerLead.objects.create(company_name='Alpha RCM', domain='alpharcm.com')
        c1 = LeadContact.objects.create(lead=lead, full_name='Alice Smith', is_primary=True)
        self.assertTrue(c1.is_primary)

        c2 = LeadContact.objects.create(lead=lead, full_name='Bob Jones', is_primary=True)
        c1.refresh_from_db()
        self.assertFalse(c1.is_primary)
        self.assertTrue(c2.is_primary)

    def test_reverse_talent_matching_service(self):
        """Tests reverse candidate matching against employer vacancies."""
        lead = EmployerLead.objects.create(
            company_name='Ensemble Health Partners',
            domain='ensemblehp.com',
            industry_vertical=EmployerLead.IndustryVertical.RCM_SERVICES
        )
        HiringSignal.objects.create(
            lead=lead,
            job_title='Inpatient Medical Coder',
            role_category=HiringSignal.RoleCategory.MEDICAL_CODER,
            extracted_skills=['ICD-10', 'DRG', 'CPT']
        )

        cand_user = User.objects.create_user(
            username='talent_coder',
            email='coder@talent.com',
            password='testpassword123',
            first_name='Kofi',
            last_name='Mensah',
            role=User.Role.CANDIDATE
        )
        cand_profile, _ = CandidateProfile.objects.get_or_create(
            user=cand_user,
            defaults={
                'headline': 'Certified Inpatient Medical Coder | CCS, CPC',
                'is_verified': True,
                'is_employer_ready': True,
                'years_of_experience': 4,
                'availability_status': CandidateProfile.Availability.IMMEDIATE
            }
        )

        fit_score = compute_lead_reverse_matches(lead)
        lead.refresh_from_db()

        self.assertGreaterEqual(fit_score, 50)
        self.assertEqual(lead.talent_fit_score, fit_score)
        self.assertTrue(TalentReverseMatch.objects.filter(lead=lead, candidate=cand_profile).exists())


class GrowthOSPhase2DiscoveryTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='bd_scout',
            email='bd_scout@kodafriq.com',
            password='Password123!',
            role=User.Role.STAFF
        )

    def test_search_healthcare_employers_catalog(self):
        """Tests search discovery returning normalized results."""
        results = search_healthcare_employers('billing Texas', limit=5)
        self.assertGreater(len(results), 0)
        first = results[0]
        self.assertIn('company_name', first)
        self.assertIn('domain', first)
        self.assertIn('website', first)

    def test_import_discovered_lead(self):
        """Tests ingesting a discovered organization and deduplication."""
        data = {
            'company_name': 'Apex Revenue Management',
            'domain': 'apexrcm.com',
            'website': 'https://apexrcm.com',
            'careers_url': 'https://apexrcm.com/careers',
            'city': 'Atlanta, GA',
            'country': 'United States',
            'industry_vertical': EmployerLead.IndustryVertical.RCM_SERVICES,
            'snippet': 'Specialty clinic revenue cycle management.'
        }
        lead, created = import_discovered_lead(data, assigned_staff=self.staff_user)
        self.assertTrue(created)
        self.assertEqual(lead.domain, 'apexrcm.com')
        self.assertEqual(lead.assigned_staff, self.staff_user)
        self.assertTrue(hasattr(lead, 'crm_opportunity'))

        # Second import returns same lead
        lead2, created2 = import_discovered_lead(data, assigned_staff=self.staff_user)
        self.assertFalse(created2)
        self.assertEqual(lead.id, lead2.id)

    def test_csv_bulk_import_service(self):
        """Tests bulk CSV ingestion pipeline with multiple rows, aliased headers, and contacts."""
        csv_data = (
            "Company,Website,Careers_URL,City,Vertical,Contact Name,Contact Email,Contact Title\n"
            "Baystate Billing,https://baystatebilling.com,https://baystatebilling.com/jobs,Boston MA,MEDICAL_BILLING,Rachel Green,rachel@baystatebilling.com,VP Operations\n"
            "Lone Star Coding,lonestarcoding.com,,Houston TX,MEDICAL_CODING,Hank Hill,hank@lonestar.com,Billing Director\n"
            ",invalid-no-company.com,,,,,,\n"
        )
        results = import_leads_from_csv(csv_data, assigned_staff=self.staff_user)
        self.assertEqual(results['total'], 3)
        self.assertEqual(results['created'], 2)
        self.assertEqual(results['skipped'], 1)

        # Verify lead and contact were created
        lead = EmployerLead.objects.get(domain='baystatebilling.com')
        self.assertEqual(lead.company_name, 'Baystate Billing')
        self.assertEqual(lead.city, 'Boston MA')
        self.assertEqual(lead.contacts.count(), 1)
        self.assertEqual(lead.contacts.first().full_name, 'Rachel Green')

    def test_skill_extraction_from_text(self):
        """Tests regex extraction of healthcare coding and billing competencies."""
        sample_text = (
            "We are seeking an Inpatient Medical Coder with strong proficiency in ICD-10-CM and CPT coding. "
            "Experience with Epic EHR, DRG assignment, and AHIMA CCS certification preferred."
        )
        skills = extract_skills_from_text(sample_text)
        self.assertIn('ICD-10-CM', skills)
        self.assertIn('CPT', skills)
        self.assertIn('Epic', skills)
        self.assertIn('DRG', skills)
        self.assertIn('CCS', skills)

    def test_career_scraper_offline_html(self):
        """Tests career page inspector against mock HTML response."""
        lead = EmployerLead.objects.create(
            company_name='Premier Health Billing',
            domain='premierhealthbilling.com',
            website='https://premierhealthbilling.com',
            careers_url='https://premierhealthbilling.com/careers'
        )

        mock_html = """
        <html>
            <body>
                <h1>Current Career Opportunities</h1>
                <div class="job-list">
                    <h3>Senior Inpatient Medical Coder</h3>
                    <p>Requires 3+ years experience with ICD-10 and DRG auditing.</p>
                    <a href="/jobs/inpatient-coder">Apply Now</a>

                    <h3>Accounts Receivable & Denial Specialist</h3>
                    <p>Manage payer appeals and claim re-submissions.</p>
                    <a href="/jobs/ar-specialist">Apply Now</a>
                </div>
            </body>
        </html>
        """
        with patch('requests.get') as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = mock_html
            mock_get.return_value = mock_resp

            result = inspect_lead_career_page(lead)
            self.assertTrue(result['success'])
            self.assertEqual(result['vacancies_detected'], 2)
            self.assertTrue(lead.vacancies.filter(job_title__icontains='Medical Coder').exists())
            self.assertTrue(lead.vacancies.filter(job_title__icontains='Receivable').exists())

    def test_management_commands_execution(self):
        """Tests run_lead_discovery and scan_hiring_intent management commands."""
        # Test run_lead_discovery
        call_command('run_lead_discovery', query='medical billing', limit=2)
        self.assertGreater(EmployerLead.objects.count(), 0)

        # Test scan_hiring_intent
        call_command('scan_hiring_intent', rescore_all=True)

        # Test import_leads_csv with temp file
        with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False) as f:
            f.write("company_name,domain,city\nMetro Billing,metrobilling.com,Chicago IL\n")
            temp_path = f.name

        try:
            call_command('import_leads_csv', temp_path)
            self.assertTrue(EmployerLead.objects.filter(domain='metrobilling.com').exists())
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class GrowthOSViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username='staff_rep',
            email='staff_rep@kodafriq.com',
            password='Password123!',
            role=User.Role.STAFF
        )
        self.regular_candidate = User.objects.create_user(
            username='cand_user',
            email='cand@test.com',
            password='Password123!',
            role=User.Role.CANDIDATE
        )
        self.lead = EmployerLead.objects.create(
            company_name='GeBBS Healthcare Solutions',
            domain='gebbs.com',
            industry_vertical=EmployerLead.IndustryVertical.HEALTHCARE_BPO,
            assigned_staff=self.staff_user,
            hiring_intent_score=75,
            talent_fit_score=80
        )

    def test_anonymous_access_denied(self):
        """Anonymous user is redirected to login for GrowthOS views."""
        response = self.client.get(reverse('growth_os:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_candidate_access_restricted(self):
        """Non-staff user (candidate) is forbidden / redirected with error."""
        self.client.login(username='cand_user', password='Password123!')
        response = self.client.get(reverse('growth_os:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/dashboard/staff/', response.url)

    def test_staff_dashboard_view_success(self):
        """Staff user can access GrowthOS dashboard successfully."""
        self.client.login(username='staff_rep', password='Password123!')
        response = self.client.get(reverse('growth_os:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'GrowthOS Acquisition Engine')
        self.assertContains(response, 'GeBBS Healthcare Solutions')
        self.assertContains(response, 'Tier 1')

    def test_staff_lead_directory_view(self):
        """Staff user can view and filter leads list."""
        self.client.login(username='staff_rep', password='Password123!')
        response = self.client.get(reverse('growth_os:lead_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'GeBBS Healthcare Solutions')
        self.assertContains(response, 'gebbs.com')

    def test_staff_lead_detail_view(self):
        """Staff user can view full lead dossier."""
        self.client.login(username='staff_rep', password='Password123!')
        response = self.client.get(reverse('growth_os:lead_detail', args=[self.lead.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'GeBBS Healthcare Solutions')
        self.assertContains(response, 'Hiring Intent Score')
        self.assertContains(response, 'Kodafriq Talent Fit')

    def test_discovery_hub_view(self):
        """Staff can access discovery console and execute searches."""
        self.client.login(username='staff_rep', password='Password123!')
        res = self.client.get(reverse('growth_os:discovery_hub'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Multi-Source Employer Discovery Engine')

        # Run query
        res_q = self.client.get(reverse('growth_os:discovery_hub') + '?q=billing')
        self.assertEqual(res_q.status_code, 200)
        self.assertContains(res_q, 'Discovered')

    def test_discovery_single_import_action(self):
        """Staff can import a discovered organization via POST."""
        self.client.login(username='staff_rep', password='Password123!')
        data = {
            'company_name': 'Dallas Medical Billing Group',
            'domain': 'dallasmedbilling.com',
            'website': 'https://dallasmedbilling.com',
            'city': 'Dallas, TX',
            'country': 'United States',
            'industry_vertical': EmployerLead.IndustryVertical.MEDICAL_BILLING
        }
        res = self.client.post(reverse('growth_os:discovery_import'), data=data)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(EmployerLead.objects.filter(domain='dallasmedbilling.com').exists())

    def test_csv_import_views(self):
        """Staff can access CSV import page and download sample template."""
        self.client.login(username='staff_rep', password='Password123!')

        # Download sample template
        res_sample = self.client.get(reverse('growth_os:download_sample_csv'))
        self.assertEqual(res_sample.status_code, 200)
        self.assertEqual(res_sample['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="kodafriq_growth_os_leads_template.csv"', res_sample['Content-Disposition'])

        # Upload CSV
        csv_file = SimpleUploadedFile(
            "test_leads.csv",
            b"company_name,domain,city\nAustin Coding Partners,austincoding.com,Austin TX\n",
            content_type="text/csv"
        )
        res_upload = self.client.post(reverse('growth_os:lead_import_csv'), {'csv_file': csv_file})
        self.assertEqual(res_upload.status_code, 200)
        self.assertContains(res_upload, 'CSV Import Finished')
        self.assertTrue(EmployerLead.objects.filter(domain='austincoding.com').exists())

    def test_scan_careers_action(self):
        """Staff can trigger web scan for a lead."""
        self.client.login(username='staff_rep', password='Password123!')
        with patch('apps.growth_os.views.inspect_lead_career_page') as mock_scan:
            mock_scan.return_value = {
                'success': True,
                'vacancies_detected': 3,
                'new_vacancies_added': 2,
                'intent_score': 85,
                'fit_score': 90
            }
            res = self.client.post(reverse('growth_os:lead_scan_careers', args=[self.lead.id]))
            self.assertEqual(res.status_code, 302)
            mock_scan.assert_called_once_with(self.lead)
