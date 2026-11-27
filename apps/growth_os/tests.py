import os
import tempfile
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import CandidateProfile, EmployerProfile
from apps.contracts.models import Contract
from apps.growth_os.models import (
    EmployerLead, LeadContact, HiringSignal, TalentReverseMatch,
    CRMOpportunity, CRMActivity, OutreachMessage, GrowthAutomationLog,
    normalize_company_domain
)
from apps.growth_os.services.matcher import compute_lead_reverse_matches
from apps.growth_os.services.intent import calculate_lead_intent_score
from apps.growth_os.services.scraper import extract_skills_from_text, inspect_lead_career_page
from apps.growth_os.services.discovery import (
    search_healthcare_employers, import_discovered_lead, import_leads_from_csv
)
from apps.growth_os.services.automation import (
    poll_and_age_vacancies, apply_hiring_intent_decay,
    archive_dormant_leads, sync_candidate_availability_to_growth,
    generate_weekly_bd_digest, send_weekly_bd_digest_email
)
from apps.growth_os.services.connectors import (
    search_all_connectors, CONNECTOR_REGISTRY,
    LinkedInJobsConnector, IndeedJobsConnector
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

    def test_hiring_intent_view(self):
        """Staff can access Employer Hiring Intent Detection Engine console."""
        self.client.login(username='staff_rep', password='Password123!')
        res = self.client.get(reverse('growth_os:hiring_intent'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Employer Hiring Intent Detection')
        self.assertContains(res, 'Total Employers Monitored')
        self.assertContains(res, 'With Hiring Signals')
        self.assertContains(res, 'High-Intent Employers')
        self.assertContains(res, 'Ready for Outreach')
        self.assertContains(res, 'Top Hiring Signals')
        self.assertContains(res, 'By Industry')
        self.assertContains(res, 'Employers with Hiring Intent')

    def test_lead_sourcing_view(self):
        """Staff can access Automated Employer Lead Sourcing console, export CSV, toggle sources, and run sourcing."""
        self.client.login(username='staff_rep', password='Password123!')
        res = self.client.get(reverse('growth_os:lead_sourcing'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Automated Employer Lead Sourcing')
        self.assertContains(res, 'New Leads Found')
        self.assertContains(res, 'Qualified Leads')
        self.assertContains(res, 'High-Priority Leads')
        self.assertContains(res, 'Last Scan Duration')
        self.assertContains(res, 'Sourcing Sources')
        self.assertContains(res, 'Lead Sourcing Performance')
        self.assertContains(res, 'Lead Categories')
        self.assertContains(res, 'Discovered Employers')
        self.assertContains(res, 'Go to Outreach')
        # Live DB lead created in setUp is rendered
        self.assertContains(res, 'GeBBS Healthcare Solutions')

        # Range switching (30d / 90d)
        res_30 = self.client.get(reverse('growth_os:lead_sourcing') + '?range=30d&sort=location')
        self.assertEqual(res_30.status_code, 200)

        # Live CSV Export
        res_csv = self.client.get(reverse('growth_os:lead_sourcing') + '?export=csv')
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv['Content-Type'], 'text/csv')
        self.assertContains(res_csv, 'GeBBS Healthcare Solutions')

        # AJAX source toggle
        res_toggle = self.client.post(
            reverse('growth_os:lead_sourcing'),
            data='{"action": "toggle_source", "source_key": "GOOGLE_SEARCH", "enabled": false}',
            content_type='application/json'
        )
        self.assertEqual(res_toggle.status_code, 200)
        self.assertFalse(res_toggle.json()['enabled'])

        # Run sourcing scan POST
        res_run = self.client.post(reverse('growth_os:lead_sourcing'), data={
            'action': 'run_sourcing',
            'query': 'medical billing',
            'country': 'United States',
            'source_key': 'ALL',
        })
        self.assertEqual(res_run.status_code, 302)
        self.assertGreater(EmployerLead.objects.count(), 1)

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


class GrowthOSPhase3OutreachTests(TestCase):
    """
    Test suite for Phase 3: Reverse Matching, AI-Powered Multi-Sector Outreach
    Generation (Steps 1-3 Cadence), Staff Approval Queue, and Public Talent Dossiers.
    """
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff_growth_rep',
            email='growth_rep@kodafriq.com',
            password='Password123!',
            role=User.Role.STAFF
        )

        cand_user = User.objects.create_user(
            username='candidate_jane',
            email='jane@kodafriq.com',
            password='Password123!',
            role=User.Role.CANDIDATE
        )
        self.cand_profile, _ = CandidateProfile.objects.get_or_create(user=cand_user)
        self.cand_profile.headline = 'Senior Inpatient Coder & Auditor (CPC, CCS)'
        self.cand_profile.years_of_experience = 6
        self.cand_profile.is_verified = True
        self.cand_profile.is_employer_ready = True
        self.cand_profile.kodafriq_verified_score = 94
        self.cand_profile.save()

        # 1. Healthcare Lead
        self.health_lead = EmployerLead.objects.create(
            company_name='HealthFirst Solutions',
            domain='healthfirst.org',
            industry_vertical=EmployerLead.IndustryVertical.RCM_SERVICES,
            hiring_intent_score=85,
            talent_fit_score=90,
            assigned_staff=self.staff_user
        )
        self.health_match = TalentReverseMatch.objects.create(
            lead=self.health_lead,
            candidate=self.cand_profile,
            match_score=95,
            matched_skills=['Inpatient Coding', 'ICD-10-CM', 'DRG'],
            is_shortlisted=True
        )
        self.health_contact = LeadContact.objects.create(
            lead=self.health_lead,
            full_name='Sarah Connor',
            email='sarah@healthfirst.org',
            job_title='VP of Revenue Cycle',
            is_primary=True
        )
        self.health_signal = HiringSignal.objects.create(
            lead=self.health_lead,
            job_title='Inpatient Medical Coder',
            is_active=True
        )

        # 2. IT Lead
        self.it_lead = EmployerLead.objects.create(
            company_name='CloudNova Technologies',
            domain='cloudnova.io',
            industry_vertical=EmployerLead.IndustryVertical.IT_SOFTWARE_DEV,
            hiring_intent_score=80,
            talent_fit_score=85,
            assigned_staff=self.staff_user
        )
        self.it_contact = LeadContact.objects.create(
            lead=self.it_lead,
            full_name='Alex Chen',
            email='alex@cloudnova.io',
            job_title='Engineering Director',
            is_primary=True
        )
        self.it_signal = HiringSignal.objects.create(
            lead=self.it_lead,
            job_title='Senior Python & Cloud Engineer',
            is_active=True
        )

        # 3. Finance Lead
        self.fin_lead = EmployerLead.objects.create(
            company_name='Apex Capital Advisory',
            domain='apexcap.com',
            industry_vertical=EmployerLead.IndustryVertical.FINANCE_ACCOUNTING,
            hiring_intent_score=50,
            talent_fit_score=50,
            assigned_staff=self.staff_user
        )
        self.fin_contact = LeadContact.objects.create(
            lead=self.fin_lead,
            full_name='David Morgan',
            email='david@apexcap.com',
            job_title='Chief Financial Officer',
            is_primary=True
        )

    def test_outreach_pitch_generator_sectors_and_steps(self):
        """Verifies multi-sector AI pitch generation across Email & LinkedIn cadences (Steps 1, 2, 3)."""
        from apps.growth_os.services.outreach_generator import generate_outreach_pitch

        # 1. Healthcare Step 1 Email
        health_msg = generate_outreach_pitch(
            lead=self.health_lead,
            contact=self.health_contact,
            channel=OutreachMessage.Channel.EMAIL,
            sequence_step=1
        )
        self.assertEqual(health_msg.status, OutreachMessage.Status.DRAFT_PENDING_APPROVAL)
        self.assertEqual(health_msg.sequence_step, 1)
        self.assertIn("Sarah", health_msg.body_text)
        self.assertIn("HealthFirst Solutions", health_msg.body_text)
        self.assertIn("/growth-os/shortlist/", health_msg.body_text)
        self.assertIn("Inpatient Medical Coder", health_msg.body_text)

        # 2. IT Step 1 LinkedIn
        it_msg = generate_outreach_pitch(
            lead=self.it_lead,
            contact=self.it_contact,
            channel=OutreachMessage.Channel.LINKEDIN,
            sequence_step=1
        )
        self.assertEqual(it_msg.channel, OutreachMessage.Channel.LINKEDIN)
        self.assertIn("Alex", it_msg.body_text)
        self.assertIn("Senior Python & Cloud Engineer", it_msg.body_text)
        self.assertIn("/growth-os/shortlist/", it_msg.body_text)

        # 3. IT Step 2 Follow-Up Email (Value-Add & Trial)
        it_msg_step2 = generate_outreach_pitch(
            lead=self.it_lead,
            contact=self.it_contact,
            channel=OutreachMessage.Channel.EMAIL,
            sequence_step=2
        )
        self.assertEqual(it_msg_step2.sequence_step, 2)
        self.assertIn("Two-Week Risk-Free Trial", it_msg_step2.body_text)

        # 4. Finance Step 3 Break-Up Email
        fin_msg_step3 = generate_outreach_pitch(
            lead=self.fin_lead,
            contact=self.fin_contact,
            channel=OutreachMessage.Channel.EMAIL,
            sequence_step=3
        )
        self.assertEqual(fin_msg_step3.sequence_step, 3)
        self.assertIn("Closing the loop", fin_msg_step3.subject)
        self.assertIn("close your file", fin_msg_step3.body_text)

    def test_outreach_queue_view(self):
        """Staff can view and filter outreach messages in the approval queue."""
        from apps.growth_os.services.outreach_generator import generate_outreach_pitch

        # Create a sample message
        generate_outreach_pitch(lead=self.health_lead, contact=self.health_contact, channel='EMAIL', sequence_step=1)

        # Anonymous cannot access
        res_anon = self.client.get(reverse('growth_os:outreach_queue'))
        self.assertEqual(res_anon.status_code, 302)

        # Authenticated staff can access
        self.client.login(username='staff_growth_rep', password='Password123!')
        res = self.client.get(reverse('growth_os:outreach_queue'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'HealthFirst Solutions')
        self.assertContains(res, 'Sarah Connor')
        self.assertContains(res, 'Pending Review')

        # Filter by sent
        res_sent = self.client.get(reverse('growth_os:outreach_queue') + '?status=SENT')
        self.assertEqual(res_sent.status_code, 200)

    def test_outreach_generate_view_post(self):
        """Staff can trigger AI pitch generation via POST."""
        self.client.login(username='staff_growth_rep', password='Password123!')
        data = {
            'channel': 'EMAIL',
            'sequence_step': '1',
            'contact_id': str(self.it_contact.id)
        }
        res = self.client.post(reverse('growth_os:outreach_generate', args=[self.it_lead.id]), data=data)
        self.assertEqual(res.status_code, 302)
        self.assertTrue(OutreachMessage.objects.filter(lead=self.it_lead, sequence_step=1).exists())

    def test_outreach_approve_and_send(self):
        """Staff approval marks outreach as SENT, advances CRM pipeline, and logs activity."""
        self.client.login(username='staff_growth_rep', password='Password123!')
        from apps.growth_os.services.outreach_generator import generate_outreach_pitch

        msg = generate_outreach_pitch(lead=self.health_lead, contact=self.health_contact, channel='EMAIL', sequence_step=1)
        self.assertEqual(msg.status, OutreachMessage.Status.DRAFT_PENDING_APPROVAL)

        approve_data = {
            'subject': 'Updated Custom Subject Line',
            'body_text': 'Polished email body text.'
        }
        res = self.client.post(reverse('growth_os:outreach_approve', args=[msg.id]), data=approve_data)
        self.assertEqual(res.status_code, 302)

        msg.refresh_from_db()
        self.assertEqual(msg.status, OutreachMessage.Status.SENT)
        self.assertEqual(msg.subject, 'Updated Custom Subject Line')
        self.assertIsNotNone(msg.sent_at)

        # Opportunity stage should advance
        opp = CRMOpportunity.objects.get(lead=self.health_lead)
        self.assertEqual(opp.stage, CRMOpportunity.Stage.STAGE_5_OUTREACH_SENT)

        # CRM activity logged
        self.assertTrue(CRMActivity.objects.filter(lead=self.health_lead, activity_type=CRMActivity.ActivityType.EMAIL_SENT).exists())

    def test_outreach_reject(self):
        """Staff can reject/archive draft outreach message."""
        self.client.login(username='staff_growth_rep', password='Password123!')
        from apps.growth_os.services.outreach_generator import generate_outreach_pitch

        msg = generate_outreach_pitch(lead=self.health_lead, contact=self.health_contact, channel='EMAIL', sequence_step=1)
        res = self.client.post(reverse('growth_os:outreach_reject', args=[msg.id]))
        self.assertEqual(res.status_code, 302)

        msg.refresh_from_db()
        self.assertEqual(msg.status, OutreachMessage.Status.REJECTED)

    def test_outreach_record_reply(self):
        """Staff can log incoming prospect reply, which advances pipeline to STAGE_6_REPLY_RECEIVED."""
        self.client.login(username='staff_growth_rep', password='Password123!')
        from apps.growth_os.services.outreach_generator import generate_outreach_pitch

        msg = generate_outreach_pitch(lead=self.health_lead, contact=self.health_contact, channel='EMAIL', sequence_step=1)
        msg.status = OutreachMessage.Status.SENT
        msg.save()

        reply_data = {
            'sentiment': 'positive',
            'reply_notes': 'Prospect replied wanting a discovery call this Thursday.'
        }
        res = self.client.post(reverse('growth_os:outreach_reply', args=[msg.id]), data=reply_data)
        self.assertEqual(res.status_code, 302)

        msg.refresh_from_db()
        self.assertEqual(msg.status, OutreachMessage.Status.REPLIED)
        self.assertIn('discovery call this Thursday', msg.reply_notes)

        opp = CRMOpportunity.objects.get(lead=self.health_lead)
        self.assertEqual(opp.stage, CRMOpportunity.Stage.STAGE_6_REPLY_RECEIVED)

    def test_public_candidate_shortlist_dossier_anonymous(self):
        """Prospective employers can view their unguessable candidate shortlist link WITHOUT logging in."""
        res = self.client.get(reverse('growth_os:public_shortlist', args=[self.health_lead.id]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'HealthFirst Solutions')
        self.assertContains(res, 'Pre-Vetted Specialists Ready to Accelerate')
        self.assertContains(res, '14-Day Zero-Risk Trial')
        self.assertContains(res, 'Candidate #KF-')

    def test_public_shortlist_inquiry_submission(self):
        """Prospective employer submits interview request from the public shortlist page."""
        inquiry_data = {
            'full_name': 'Marcus Vance',
            'work_email': 'm.vance@healthfirst.org',
            'phone': '+1 555-019-2834',
            'requested_roles': 'Inpatient Coder #KF-842',
            'message': 'We are looking to interview this candidate for our inpatient backlog immediately.'
        }
        res = self.client.post(reverse('growth_os:public_shortlist_inquire', args=[self.health_lead.id]), data=inquiry_data)
        self.assertEqual(res.status_code, 302)

        # Contact created or updated
        contact = LeadContact.objects.filter(lead=self.health_lead, email='m.vance@healthfirst.org').first()
        self.assertIsNotNone(contact)
        self.assertEqual(contact.full_name, 'Marcus Vance')

        # Opportunity stage advanced to STAGE_6_REPLY_RECEIVED
        opp = CRMOpportunity.objects.get(lead=self.health_lead)
        self.assertEqual(opp.stage, CRMOpportunity.Stage.STAGE_6_REPLY_RECEIVED)

        # CRM activity logged
        act = CRMActivity.objects.filter(lead=self.health_lead, activity_type=CRMActivity.ActivityType.NOTE).first()
        self.assertIsNotNone(act)
        self.assertIn("Marcus Vance", act.summary)


class Phase4KanbanAndConversionTests(TestCase):
    """
    Automated tests for Phase 4:
    - 10-Stage Interactive Kanban Pipeline
    - AJAX Drag-and-Drop Stage Transitions & Audit Activity Logging
    - 1-Click Conversion: EmployerLead -> EmployerProfile + User + Contract
    - Executive KPI Metrics & Follow-Up Reminders
    """
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff_bd_lead',
            email='bd@kodafriq.com',
            password='testpassword123',
            role=User.Role.STAFF
        )
        self.candidate_user = User.objects.create_user(
            username='cand_billing_star',
            email='star@kodafriq.com',
            password='testpassword123',
            role=User.Role.CANDIDATE
        )
        self.candidate = CandidateProfile.objects.get(user=self.candidate_user)
        self.candidate.headline = "Senior Medical Coder | CPC, CCS"
        self.candidate.years_of_experience = 5
        self.candidate.is_employer_ready = True
        self.candidate.save()

        # Healthcare Lead
        self.health_lead = EmployerLead.objects.create(
            company_name='Apex Health Partners',
            domain='apexhealth.com',
            website='https://apexhealth.com',
            industry_vertical=EmployerLead.IndustryVertical.MEDICAL_BILLING,
            hiring_intent_score=85,
            talent_fit_score=90,
            assigned_staff=self.staff_user
        )
        self.health_contact = LeadContact.objects.create(
            lead=self.health_lead,
            full_name='Dr. Evelyn Hayes',
            job_title='VP Revenue Cycle',
            email='evelyn@apexhealth.com',
            phone='+1 555-223-9900',
            is_primary=True
        )
        self.health_opp = CRMOpportunity.objects.create(
            lead=self.health_lead,
            stage=CRMOpportunity.Stage.STAGE_1_DISCOVERED,
            estimated_monthly_deal_value=Decimal('4500.00'),
            target_roles_count=2,
            win_probability_percent=10
        )

        # Reverse match
        self.match = TalentReverseMatch.objects.create(
            lead=self.health_lead,
            candidate=self.candidate,
            match_score=Decimal('92.00'),
            is_shortlisted=True
        )

        self.client = Client()
        self.client.login(username='staff_bd_lead', password='testpassword123')

    def test_crm_stage_transition_logic(self):
        """Tests transitioning pipeline stages updates probabilities, logs activity and syncs lead status."""
        from apps.growth_os.services.crm_service import transition_opportunity_stage

        # Transition to Stage 7: Meeting Scheduled
        transition_opportunity_stage(
            opportunity=self.health_opp,
            new_stage=CRMOpportunity.Stage.STAGE_7_MEETING_SCHEDULED,
            performed_by=self.staff_user,
            notes="Discovery meeting confirmed for Tuesday 2 PM EST."
        )

        self.health_opp.refresh_from_db()
        self.assertEqual(self.health_opp.stage, CRMOpportunity.Stage.STAGE_7_MEETING_SCHEDULED)
        self.assertEqual(self.health_opp.win_probability_percent, 75)

        self.health_lead.refresh_from_db()
        self.assertEqual(self.health_lead.status, EmployerLead.Status.IN_PIPELINE)

        # Audit Activity Logged
        activity = CRMActivity.objects.filter(lead=self.health_lead, activity_type=CRMActivity.ActivityType.STAGE_CHANGE).first()
        self.assertIsNotNone(activity)
        self.assertIn("7. Meeting Scheduled", activity.summary)
        self.assertIn("Discovery meeting confirmed", activity.details)

    def test_kanban_board_data_service(self):
        """Verifies kanban data aggregation, 10 columns, and deal calculations."""
        from apps.growth_os.services.crm_service import get_kanban_board_data

        data = get_kanban_board_data()
        self.assertGreaterEqual(len(data['columns']), 10)
        self.assertEqual(data['total_active_deals'], 1)
        self.assertEqual(data['total_pipeline_value'], Decimal('4500.00'))

        # Filter by sector
        filtered = get_kanban_board_data(sector=EmployerLead.IndustryVertical.MEDICAL_BILLING)
        self.assertEqual(filtered['total_active_deals'], 1)

        empty_filtered = get_kanban_board_data(sector=EmployerLead.IndustryVertical.HEALTHCARE_BPO)
        self.assertEqual(empty_filtered['total_active_deals'], 0)

    def test_pipeline_kanban_view_access(self):
        """Staff can view the interactive Kanban pipeline board; unauthenticated users are blocked."""
        res = self.client.get(reverse('growth_os:pipeline_kanban'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Apex Health Partners')
        self.assertContains(res, 'Sales Pipeline Kanban')
        self.assertContains(res, '4500')

        # Anonymous user blocked
        anon_client = Client()
        anon_res = anon_client.get(reverse('growth_os:pipeline_kanban'))
        self.assertNotEqual(anon_res.status_code, 200)

    def test_sales_crm_console_live_metrics_and_mobile_js_clean(self):
        """Verifies redesigned Sales CRM KPIs, 5 stage columns, bottom workbench, and clean inline JS."""
        import re
        import shutil
        import subprocess
        import tempfile

        CRMActivity.objects.create(
            lead=self.health_lead,
            activity_type=CRMActivity.ActivityType.MEETING,
            summary="Discovery call with VP Revenue Cycle",
            details="Confirmed 2 immediate openings.",
            performed_by=self.staff_user,
        )
        self.health_opp.next_follow_up_date = timezone.localdate() + timedelta(days=2)
        self.health_opp.save(update_fields=['next_follow_up_date'])

        res = self.client.get(reverse('growth_os:pipeline_kanban') + '?days=90')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Employer Sales CRM &amp; Opportunity Management')
        self.assertContains(res, 'Total Employers')
        self.assertContains(res, 'Active Opportunities')
        self.assertContains(res, 'Meetings Scheduled')
        self.assertContains(res, 'Conversion Rate')
        self.assertContains(res, '1. Discovered')
        self.assertContains(res, '2. Qualified')
        self.assertContains(res, '3. Hiring Signal')
        self.assertContains(res, '4. Contact Identified')
        self.assertContains(res, '5. Contacted')
        self.assertContains(res, 'Communication History')
        self.assertContains(res, 'Upcoming Tasks')
        self.assertContains(res, 'Opportunity Performance')
        self.assertContains(res, 'crm-kpi-grid')
        self.assertContains(res, 'crm-pipeline-grid')
        self.assertContains(res, 'crm-workbench-grid')
        self.assertContains(res, 'Discovery call with VP Revenue Cycle')

        node_bin = shutil.which('node')
        if node_bin:
            html = res.content.decode('utf-8')
            scripts = re.findall(r'<script>(.*?)</script>', html, flags=re.DOTALL)
            self.assertTrue(scripts)
            for idx, js_code in enumerate(scripts):
                with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as tmp:
                    tmp.write(js_code)
                    tmp_path = tmp.name
                try:
                    proc = subprocess.run([node_bin, '--check', tmp_path], capture_output=True, text=True)
                    self.assertEqual(proc.returncode, 0, f"JS syntax error in CRM script #{idx}: {proc.stderr}")
                finally:
                    os.unlink(tmp_path)

    def test_pipeline_update_stage_ajax(self):
        """AJAX drag-and-drop call successfully updates opportunity stage and returns JSON."""
        post_data = {
            'opportunity_id': str(self.health_opp.id),
            'stage': CRMOpportunity.Stage.STAGE_8_SHORTLIST_DELIVERED,
            'notes': 'Candidate shortlist dossier shared via email.'
        }
        res = self.client.post(reverse('growth_os:pipeline_update_stage'), data=post_data)
        self.assertEqual(res.status_code, 200)

        json_data = res.json()
        self.assertTrue(json_data['success'])
        self.assertEqual(json_data['new_stage'], CRMOpportunity.Stage.STAGE_8_SHORTLIST_DELIVERED)
        self.assertEqual(json_data['win_probability'], 85)

        self.health_opp.refresh_from_db()
        self.assertEqual(self.health_opp.stage, CRMOpportunity.Stage.STAGE_8_SHORTLIST_DELIVERED)

    def test_pipeline_update_stage_invalid_rejected(self):
        """Invalid stage codes are rejected with 400 error."""
        post_data = {
            'opportunity_id': str(self.health_opp.id),
            'stage': 'INVALID_NONEXISTENT_STAGE'
        }
        res = self.client.post(reverse('growth_os:pipeline_update_stage'), data=post_data)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['success'])

    def test_1_click_conversion_service_and_contract(self):
        """Converts EmployerLead into EmployerProfile, User account, and drafted Contract."""
        from apps.growth_os.services.crm_service import convert_lead_to_employer
        from apps.contracts.models import Contract
        from apps.accounts.models import EmployerProfile

        user_data = {
            'email': 'evelyn.hayes@apexhealth.com',
            'first_name': 'Evelyn',
            'last_name': 'Hayes',
            'company_name': 'Apex Health Partners LLC',
            'industry': 'Healthcare Revenue Cycle',
            'country': 'United States',
            'city': 'Atlanta, GA'
        }
        contract_data = {
            'candidate_id': str(self.candidate.id),
            'title': 'Senior Medical Coder - Full Time Remote',
            'contract_type': Contract.ContractType.HOURLY,
            'rate_per_hour': Decimal('28.50'),
            'weekly_hour_limit': 40,
            'scope_of_work': 'Inpatient chart coding in Epic EHR.'
        }

        result = convert_lead_to_employer(
            lead=self.health_lead,
            user_data=user_data,
            contract_data=contract_data,
            performed_by=self.staff_user
        )

        self.assertTrue(result['success'])

        # User verified
        new_user = result['user']
        self.assertEqual(new_user.email, 'evelyn.hayes@apexhealth.com')
        self.assertEqual(new_user.role, User.Role.EMPLOYER)

        # EmployerProfile verified
        profile = result['employer_profile']
        self.assertEqual(profile.company_name, 'Apex Health Partners LLC')
        self.assertEqual(profile.approval_status, EmployerProfile.ApprovalStatus.APPROVED)

        # Lead updated
        self.health_lead.refresh_from_db()
        self.assertEqual(self.health_lead.status, EmployerLead.Status.CONVERTED)
        self.assertEqual(self.health_lead.converted_employer_profile, profile)

        # Opportunity advanced to 10. Won
        self.health_opp.refresh_from_db()
        self.assertEqual(self.health_opp.stage, CRMOpportunity.Stage.STAGE_10_PLACEMENT_WON)
        self.assertEqual(self.health_opp.win_probability_percent, 100)

        # Contract verified
        contract = result['contract']
        self.assertIsNotNone(contract)
        self.assertEqual(contract.employer, profile)
        self.assertEqual(contract.candidate, self.candidate)
        self.assertEqual(contract.rate_per_hour, Decimal('28.50'))
        self.assertTrue(contract.contract_ref.startswith('KD-'))

    def test_lead_convert_controller_view(self):
        """Staff accesses the 1-click conversion page and submits conversion successfully."""
        from apps.accounts.models import EmployerProfile

        # GET conversion view
        get_res = self.client.get(reverse('growth_os:lead_convert', args=[self.health_lead.id]))
        self.assertEqual(get_res.status_code, 200)
        self.assertContains(get_res, 'Convert Lead to Kodafriq Employer')
        self.assertContains(get_res, 'Apex Health Partners')

        # POST conversion
        post_data = {
            'email': 'onboarding@apexhealth.com',
            'company_name': 'Apex Health Partners',
            'contact_person_name': 'Evelyn Hayes',
            'contact_person_title': 'VP RCM',
            'phone': '+1 555-010-9988',
            'country': 'United States',
            'city': 'Dallas, TX',
            'industry': 'Medical Billing & Coding',
            'create_contract': 'on',
            'candidate_id': str(self.candidate.id),
            'contract_title': 'Medical Coding Specialist',
            'contract_type': 'HOURLY',
            'rate_per_hour': '26.00',
            'weekly_hour_limit': 40,
            'scope_of_work': 'Clinical coding'
        }
        post_res = self.client.post(reverse('growth_os:lead_convert', args=[self.health_lead.id]), data=post_data)
        self.assertEqual(post_res.status_code, 302)

        self.health_lead.refresh_from_db()
        self.assertEqual(self.health_lead.status, EmployerLead.Status.CONVERTED)
        self.assertIsNotNone(self.health_lead.converted_employer_profile)
        self.assertEqual(self.health_lead.converted_employer_profile.company_name, 'Apex Health Partners')

    def test_quick_activity_log_with_followup(self):
        """Staff can log an activity and schedule next follow-up date simultaneously."""
        activity_data = {
            'activity_type': 'MEETING',
            'summary': 'Introductory discovery call with hiring team',
            'details': 'Discussed placing 2 medical coders by next month.',
            'next_follow_up_date': '2026-12-01'
        }
        res = self.client.post(
            reverse('growth_os:activity_quick_log', args=[self.health_lead.id]),
            data=activity_data
        )
        self.assertEqual(res.status_code, 302)

        # Activity saved
        act = CRMActivity.objects.filter(lead=self.health_lead, summary='Introductory discovery call with hiring team').first()
        self.assertIsNotNone(act)
        self.assertEqual(act.activity_type, CRMActivity.ActivityType.MEETING)

        # Follow-up date updated on opportunity
        self.health_opp.refresh_from_db()
        self.assertEqual(str(self.health_opp.next_follow_up_date), '2026-12-01')


class GrowthOSPhase5AutomationTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='staff_p5',
            email='staff_p5@kodafriq.com',
            password='testpassword123',
            role=User.Role.STAFF
        )
        self.client = Client()
        self.client.login(username='staff_p5', password='testpassword123')

        self.lead = EmployerLead.objects.create(
            company_name='Optum Health Solutions',
            domain='optumhealth.com',
            website='https://optumhealth.com',
            status=EmployerLead.Status.LEAD,
            industry_vertical=EmployerLead.IndustryVertical.RCM_SERVICES,
            hiring_intent_score=50,
            talent_fit_score=40,
            assigned_staff=self.staff_user
        )

        cand_user = User.objects.create_user(
            username='cand_p5',
            email='cand_p5@kodafriq.com',
            password='testpassword123',
            role=User.Role.CANDIDATE
        )
        self.candidate = CandidateProfile.objects.filter(user=cand_user).first()
        if not self.candidate:
            self.candidate = CandidateProfile.objects.create(user=cand_user)
        self.candidate.headline = 'Medical Coder CPC Certified'
        self.candidate.availability_status = CandidateProfile.Availability.IMMEDIATE
        self.candidate.is_employer_ready = True
        self.candidate.save()

    def test_vacancy_polling_and_aging(self):
        """Active vacancies >= 30 days are marked persistent; vacancies > 90 days are expired."""
        today = timezone.localdate()
        v_persistent = HiringSignal.objects.create(
            lead=self.lead,
            job_title='Senior Medical Coder',
            is_active=True,
            is_persistent=False,
            date_detected=today - timedelta(days=35)
        )
        v_expired = HiringSignal.objects.create(
            lead=self.lead,
            job_title='Outdated Billing Clerk',
            is_active=True,
            is_persistent=False,
            date_detected=today - timedelta(days=95)
        )

        res = poll_and_age_vacancies(crawl=False, performed_by=self.staff_user)
        self.assertTrue(res['success'])
        self.assertGreaterEqual(res['persistent_count'], 1)
        self.assertGreaterEqual(res['closed_count'], 1)

        v_persistent.refresh_from_db()
        self.assertTrue(v_persistent.is_persistent)
        self.assertTrue(v_persistent.is_active)

        v_expired.refresh_from_db()
        self.assertFalse(v_expired.is_active)

        # Audit log created
        log = GrowthAutomationLog.objects.filter(task_type=GrowthAutomationLog.TaskType.VACANCY_POLL).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, GrowthAutomationLog.Status.SUCCESS)

    def test_hiring_intent_decay(self):
        """Stale leads with no active vacancies lose 10% hiring intent score."""
        self.lead.hiring_intent_score = 60
        self.lead.save()
        # Ensure 0 active vacancies
        self.lead.vacancies.all().delete()

        # Update updated_at in past
        EmployerLead.objects.filter(id=self.lead.id).update(
            updated_at=timezone.now() - timedelta(days=40)
        )

        res = apply_hiring_intent_decay(days_stale=30, performed_by=self.staff_user)
        self.assertTrue(res['success'])
        self.assertGreaterEqual(res['decayed_count'], 1)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.hiring_intent_score, 54)  # 60 * 0.9 = 54

        log = GrowthAutomationLog.objects.filter(task_type=GrowthAutomationLog.TaskType.INTENT_DECAY).first()
        self.assertIsNotNone(log)

    def test_dormant_lead_archiving(self):
        """Leads inactive for > 90 days with 0 vacancies and low intent are archived."""
        self.lead.hiring_intent_score = 15
        self.lead.status = EmployerLead.Status.LEAD
        self.lead.save()
        self.lead.vacancies.all().delete()
        self.lead.activities.all().delete()

        EmployerLead.objects.filter(id=self.lead.id).update(
            created_at=timezone.now() - timedelta(days=100)
        )

        res = archive_dormant_leads(days_threshold=90, performed_by=self.staff_user)
        self.assertTrue(res['success'])
        self.assertGreaterEqual(res['archived_count'], 1)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, EmployerLead.Status.ARCHIVED)

        # Verify activity note logged
        note = CRMActivity.objects.filter(lead=self.lead, summary__icontains="Lead Archived").first()
        self.assertIsNotNone(note)

        log = GrowthAutomationLog.objects.filter(task_type=GrowthAutomationLog.TaskType.DORMANT_ARCHIVE).first()
        self.assertIsNotNone(log)

    def test_candidate_availability_sync(self):
        """Unavailable candidates are de-shortlisted from talent reverse matches."""
        match = TalentReverseMatch.objects.create(
            lead=self.lead,
            candidate=self.candidate,
            match_score=Decimal('85.00'),
            is_shortlisted=True
        )

        # Candidate becomes unavailable
        self.candidate.availability_status = CandidateProfile.Availability.NOT_LOOKING
        self.candidate.save()

        # Signal triggers sync_candidate_availability_to_growth
        match.refresh_from_db()
        self.assertFalse(match.is_shortlisted)

        log = GrowthAutomationLog.objects.filter(task_type=GrowthAutomationLog.TaskType.AVAILABILITY_SYNC).first()
        self.assertIsNotNone(log)

    def test_weekly_bd_digest_and_email_dispatch(self):
        """Weekly BD digest compiles multi-sector KPIs and dispatches email."""
        # Create an IT lead and a Finance lead
        EmployerLead.objects.create(
            company_name='Cloudscale DevOps Corp',
            domain='cloudscaledevops.io',
            industry_vertical=EmployerLead.IndustryVertical.IT_CLOUD_DEVOPS,
            status=EmployerLead.Status.LEAD
        )
        EmployerLead.objects.create(
            company_name='Apex Ledger Accounting',
            domain='apexledger.co',
            industry_vertical=EmployerLead.IndustryVertical.FINANCE_ACCOUNTING,
            status=EmployerLead.Status.LEAD
        )

        digest = generate_weekly_bd_digest(performed_by=self.staff_user)
        self.assertGreaterEqual(digest['new_leads_count'], 3)
        self.assertIn('sectors_breakdown', digest)

        email_res = send_weekly_bd_digest_email(
            recipients=['exec@kodafriq.com'],
            performed_by=self.staff_user
        )
        self.assertTrue(email_res['success'])
        self.assertEqual(email_res['recipients'], ['exec@kodafriq.com'])

        log = GrowthAutomationLog.objects.filter(task_type=GrowthAutomationLog.TaskType.WEEKLY_DIGEST).first()
        self.assertIsNotNone(log)

    @patch('requests.get')
    def test_sourcing_connectors_and_registry(self, mock_get):
        """Unified connector registry searches and deduplicates by domain."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<html><body><li><h4>Omega Health</h4><h3>Coder</h3><span>Remote</span></li></body></html>'
        mock_get.return_value = mock_resp

        results = search_all_connectors(query='medical billing', limit_per_source=4)
        self.assertIsInstance(results, list)
        for item in results:
            self.assertIn('domain', item)
            self.assertIn('company_name', item)
            self.assertIn('source', item)

    @patch('requests.get')
    def test_management_commands_execution(self, mock_get):
        """CLI management commands run without exceptions."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<html></html>'
        mock_get.return_value = mock_resp

        call_command('run_growth_automation', task='all')
        call_command('send_growth_weekly_digest', dry_run=True)

    @patch('requests.get')
    def test_automation_views_access_and_actions(self, mock_get):
        """Staff can view and trigger automation tasks and reports from UI."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<html><body><li><h4>Omega Health</h4><h3>Coder</h3><span>Remote</span></li></body></html>'
        mock_get.return_value = mock_resp

        # Automation Dashboard GET
        dash_res = self.client.get(reverse('growth_os:automation_dashboard'))
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, "Autonomous Growth & Ecosystem Maintenance")

        # Automation Action: poll_vacancies
        post_vac = self.client.post(reverse('growth_os:automation_dashboard'), data={'action': 'poll_vacancies'})
        self.assertEqual(post_vac.status_code, 302)

        # Automation Action: decay_intent
        post_decay = self.client.post(reverse('growth_os:automation_dashboard'), data={'action': 'decay_intent'})
        self.assertEqual(post_decay.status_code, 302)

        # Reports View GET
        rep_res = self.client.get(reverse('growth_os:reports_digest'))
        self.assertEqual(rep_res.status_code, 200)
        self.assertContains(rep_res, "Commercial & BD Executive Digest")

        # Discovery Hub GET with specific source
        disc_res = self.client.get(reverse('growth_os:discovery_hub') + '?q=billing&source=LINKEDIN_JOBS')
        self.assertEqual(disc_res.status_code, 200)


class GrowthOSWorldwideDiscoveryAndScrapingTests(TestCase):
    """
    Verifies worldwide multi-sector discovery, website contact/social/career scraping,
    daily DB re-checking without pre-set careers URL, and Discovery Hub worldwide UI.
    """
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='global_scout',
            email='global_scout@kodafriq.com',
            password='Password123!',
            role=User.Role.STAFF,
        )
        self.client = Client()
        self.client.login(username='global_scout', password='Password123!')

    def test_website_scraper_extracts_phone_email_socials_and_careers(self):
        """Scraper extracts phone, HR email, social links, and /careers BEFORE decomposing header/footer."""
        lead = EmployerLead.objects.create(
            company_name='Nordic Billing Solutions',
            domain='nordicbilling.co.uk',
            website='https://nordicbilling.co.uk',
            country='United Kingdom',
            city='London',
        )

        homepage_html = """
        <html>
            <body>
                <header>
                    <nav>
                        <a href="/careers">Careers</a>
                        <a href="/contact">Contact Us</a>
                    </nav>
                </header>
                <main>
                    <h1>Healthcare Revenue Cycle &amp; Engineering</h1>
                </main>
                <footer>
                    <p>Call us: <a href="tel:+44 20 7946 0192">+44 20 7946 0192</a></p>
                    <a href="https://www.linkedin.com/company/nordic-billing?trk=nav">LinkedIn</a>
                    <a href="https://x.com/nordicbilling">Twitter</a>
                    <a href="https://www.facebook.com/nordicbilling">Facebook</a>
                    <a href="https://www.instagram.com/nordicbilling">Instagram</a>
                </footer>
            </body>
        </html>
        """
        contact_html = """
        <html><body>
            <h1>Contact Nordic Billing</h1>
            <p>Recruitment Desk: <a href="mailto:careers@nordicbilling.co.uk">careers@nordicbilling.co.uk</a></p>
        </body></html>
        """
        careers_html = """
        <html><body>
            <h2>Open Roles</h2>
            <h3>Senior Medical Billing Specialist</h3>
            <h3>DevOps Cloud Engineer</h3>
        </body></html>
        """

        def fake_get(url, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.url = url
            if '/contact' in url:
                resp.text = contact_html
            elif '/careers' in url:
                resp.text = careers_html
            else:
                resp.text = homepage_html
            return resp

        with patch('requests.get', side_effect=fake_get):
            result = inspect_lead_career_page(lead)

        self.assertTrue(result['success'])
        lead.refresh_from_db()
        self.assertEqual(lead.phone, '+44 20 7946 0192')
        self.assertEqual(lead.contact_email, 'careers@nordicbilling.co.uk')
        self.assertEqual(lead.careers_url, 'https://nordicbilling.co.uk/careers')
        self.assertIsNotNone(lead.last_scraped_at)
        self.assertEqual(lead.social_links.get('linkedin'), 'https://www.linkedin.com/company/nordic-billing')
        self.assertEqual(lead.social_links.get('twitter'), 'https://x.com/nordicbilling')
        self.assertEqual(lead.social_links.get('facebook'), 'https://www.facebook.com/nordicbilling')
        self.assertEqual(lead.social_links.get('instagram'), 'https://www.instagram.com/nordicbilling')

        self.assertTrue(lead.contacts.filter(email='careers@nordicbilling.co.uk').exists())
        self.assertTrue(lead.vacancies.filter(job_title__icontains='Billing').exists())
        self.assertTrue(lead.vacancies.filter(job_title__icontains='DevOps').exists())

        # Lead Detail page displays scraped phone, email, and social media links
        detail_res = self.client.get(reverse('growth_os:lead_detail', args=[lead.id]))
        self.assertEqual(detail_res.status_code, 200)
        self.assertContains(detail_res, '+44 20 7946 0192')
        self.assertContains(detail_res, 'careers@nordicbilling.co.uk')
        self.assertContains(detail_res, 'LinkedIn')

    def test_worldwide_connectors_and_import_preserve_geography_and_signals(self):
        """Worldwide discovery pulls global employers from Remotive/Arbeitnow/DuckDuckGo/LinkedIn and creates HiringSignals."""
        from apps.growth_os.services.connectors import RemotiveJobsConnector, ArbeitnowJobsConnector

        def fake_get(url, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if 'remotive.com' in url:
                resp.json.return_value = {
                    'jobs': [{
                        'company_name': 'Lagoon Health Tech',
                        'title': 'Senior Backend Software Engineer',
                        'category': 'Software Development',
                        'tags': ['Python', 'AWS'],
                        'candidate_required_location': 'Nigeria, Africa, Worldwide',
                        'url': 'https://remotive.com/jobs/lagoon-dev',
                        'description': '<p>Visit <a href="https://lagoonhealthtech.ng">us</a></p>',
                    }]
                }
            elif 'arbeitnow.com' in url:
                resp.json.return_value = {
                    'data': [{
                        'company_name': 'Berlin Cloud GmbH',
                        'title': 'Platform DevOps Engineer',
                        'tags': ['Kubernetes', 'Terraform'],
                        'job_types': ['Full-time'],
                        'location': 'Berlin, Germany',
                        'remote': True,
                        'url': 'https://www.arbeitnow.com/jobs/berlin-cloud',
                        'description': '<p>Join Berlin Cloud</p>',
                    }]
                }
            else:
                resp.text = '<html></html>'
                resp.json.return_value = {}
            return resp

        with patch('requests.get', side_effect=fake_get):
            remotive_items = RemotiveJobsConnector().search('software', location='Worldwide', limit=5)
            arbeitnow_items = ArbeitnowJobsConnector().search('devops', location='Germany', limit=5)

        self.assertEqual(len(remotive_items), 1)
        self.assertEqual(remotive_items[0]['domain'], 'lagoonhealthtech.ng')
        self.assertEqual(remotive_items[0]['country'], 'Nigeria')

        lead_ng, created = import_discovered_lead(remotive_items[0], assigned_staff=self.staff_user)
        self.assertTrue(created)
        self.assertEqual(lead_ng.country, 'Nigeria')
        self.assertTrue(lead_ng.vacancies.filter(job_title='Senior Backend Software Engineer').exists())

        self.assertEqual(len(arbeitnow_items), 1)
        self.assertEqual(arbeitnow_items[0]['country'], 'Germany')

    def test_daily_db_crawl_and_worldwide_automation(self):
        """Daily poller crawls homepage-only leads without careers_url and logs global discovery."""
        from apps.growth_os.services.automation import run_worldwide_employer_discovery

        eu_lead = EmployerLead.objects.create(
            company_name='EuroMed Billing GmbH',
            domain='euromedbilling.de',
            website='https://euromedbilling.de',
            careers_url='',
            country='Germany',
            city='Munich',
        )

        mock_html = """
        <html><body>
            <footer>
                <a href="tel:+49 89 1234567">+49 89 1234567</a>
                <a href="mailto:jobs@euromedbilling.de">jobs@euromedbilling.de</a>
                <a href="https://linkedin.com/company/euromed-billing">LinkedIn</a>
            </footer>
            <h3>Senior Medical Coding Auditor</h3>
        </body></html>
        """

        def fake_get(url, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            if 'euromedbilling.de' in url:
                resp.text = mock_html
            else:
                resp.text = '<html></html>'
                resp.json.side_effect = ValueError('not json')
            return resp

        with patch('requests.get', side_effect=fake_get):
            res_poll = poll_and_age_vacancies(crawl=True, performed_by=self.staff_user)
            res_disc = run_worldwide_employer_discovery(
                queries=['medical billing'],
                markets=['Worldwide'],
                scrape_websites=False,
                performed_by=self.staff_user,
            )

        self.assertGreaterEqual(res_poll['crawled_count'], 1)
        eu_lead.refresh_from_db()
        self.assertEqual(eu_lead.phone, '+49 89 1234567')
        self.assertEqual(eu_lead.contact_email, 'jobs@euromedbilling.de')
        self.assertIsNotNone(eu_lead.last_scraped_at)
        self.assertTrue(eu_lead.vacancies.filter(job_title='Senior Medical Coding Auditor').exists())

        self.assertTrue(res_disc['success'])
        self.assertGreater(res_disc['countries_count'], 2)
        self.assertTrue(
            GrowthAutomationLog.objects.filter(task_type=GrowthAutomationLog.TaskType.WORLDWIDE_DISCOVERY).exists()
        )

    def test_discovery_hub_defaults_worldwide_and_filters_regions(self):
        """Discovery Hub defaults to Worldwide and surfaces global multi-sector employers."""
        res = self.client.get(reverse('growth_os:discovery_hub'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['current_country'], 'Worldwide')
        self.assertGreater(res.context['total_found'], 10)
        self.assertContains(res, 'United Kingdom')

        res_uk = self.client.get(reverse('growth_os:discovery_hub') + '?country=United+Kingdom')
        self.assertEqual(res_uk.status_code, 200)
        self.assertContains(res_uk, 'Bupa Global')

        with patch('requests.get') as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '<html></html>'
            mock_resp.json.side_effect = ValueError('html')
            mock_get.return_value = mock_resp

            post_global = self.client.post(
                reverse('growth_os:discovery_import'),
                data={'mode': 'discover_worldwide'},
            )
            self.assertEqual(post_global.status_code, 302)
            self.assertGreater(EmployerLead.objects.exclude(country='United States').count(), 5)

    def test_matcher_and_scraper_handle_candidate_certifications(self):
        """Regression test for live VPS crash: CandidateCertification uses certification_name, not .name."""
        from datetime import date
        from apps.accounts.models import CandidateCertification
        from apps.growth_os.services.matcher import compute_lead_reverse_matches

        cand_user = User.objects.create_user(
            username='cert_coder',
            email='cert_coder@kodafriq.com',
            password='Password123!',
            role=User.Role.CANDIDATE,
        )
        cand_profile, _ = CandidateProfile.objects.get_or_create(user=cand_user)
        cand_profile.is_employer_ready = True
        cand_profile.is_verified = True
        cand_profile.headline = 'Medical Billing & Coding Specialist'
        cand_profile.save()

        CandidateCertification.objects.create(
            candidate=cand_profile,
            certification_name='CPC (Certified Professional Coder)',
            issuing_organization='AAPC',
            issue_date=date(2024, 1, 15),
            is_verified=True,
        )

        lead = EmployerLead.objects.create(
            company_name='ShyftOff Global',
            domain='shyftoff.com',
            website='https://www.shyftoff.com',
            careers_url='https://remotive.com/remote-jobs/shyftoff',
            country='United States',
        )

        def fake_get(url, *args, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.url = url
            resp.text = (
                '<html><body>'
                '<footer><a href="tel:+1 800-555-0199">+1 800-555-0199</a>'
                '<a href="mailto:careers@shyftoff.com">careers@shyftoff.com</a></footer>'
                '<h3>Certified Coding Specialist</h3>'
                '</body></html>'
            )
            return resp

        with patch('requests.get', side_effect=fake_get):
            res = inspect_lead_career_page(lead)

        self.assertTrue(res['success'])
        self.assertIn('shyftoff.com', res['url_scanned'])
        score = compute_lead_reverse_matches(lead)
        self.assertGreater(score, 0)

    def test_legal_suffix_stripping_and_timeout_queue_rotation(self):
        """Domain slug helper strips legal suffixes and unreachable scrapes still advance last_scraped_at."""
        import requests
        from apps.growth_os.services.connectors.base import suggest_company_domain

        self.assertEqual(suggest_company_domain('Codewerk GmbH'), 'codewerk.com')
        self.assertEqual(suggest_company_domain('Compass Business Solutions Inc.'), 'compassbusinesssolutions.com')

        dead_lead = EmployerLead.objects.create(
            company_name='Unreachable Corp',
            domain='unreachable-example-host.invalid',
            website='https://unreachable-example-host.invalid',
        )
        self.assertIsNone(dead_lead.last_scraped_at)

        with patch('requests.get', side_effect=requests.exceptions.ConnectTimeout('timed out')):
            res = inspect_lead_career_page(dead_lead)

        self.assertFalse(res['success'])
        dead_lead.refresh_from_db()
        self.assertIsNotNone(dead_lead.last_scraped_at)




