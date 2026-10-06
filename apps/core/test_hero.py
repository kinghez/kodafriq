from django.test import TestCase, Client
from django.urls import reverse
from apps.core.models import HomePageSetting, ContactInquiry, FAQItem, LegalPage


class HomepageHeroTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_homepage_hero_renders_successfully(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        
        # Check eyebrow & headline
        self.assertIn('DIGITAL HEALTHCARE TALENT VERIFICATION', content)
        self.assertIn('Verified Talent.', content)
        self.assertIn('Better Healthcare.', content)
        
        # Check 4 pillars
        self.assertIn('Verify', content)
        self.assertIn('Assess', content)
        self.assertIn('Connect', content)
        self.assertIn('Grow', content)
        self.assertIn('Skills &amp;<br>Credentials', content)
        
        # Check CTAs
        self.assertIn('Get Started', content)
        self.assertIn('Watch How It Works', content)
        
        # Check trust bar
        self.assertIn('Trusted by', content)
        self.assertIn('Verified Professionals', content)
        self.assertIn('Building a Healthier', content)
        
        # Check hero mobile artwork fallback
        self.assertIn('hero_nurse_mobile_blended.png', content)

    def test_faq_section_renders_and_is_dynamic(self):
        # Create a custom FAQ item
        FAQItem.objects.create(
            question="Can healthcare facilities hire part-time coders?",
            answer="Yes, facilities can engage professionals on flexible full-time, part-time, or milestone-based contracts.",
            category="employers",
            display_order=99,
            is_active=True
        )

        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Check FAQ header
        self.assertIn('FREQUENTLY ASKED QUESTIONS', content)
        self.assertIn('Got Questions? We’re Here to Help.', content)
        
        # Check that dynamic FAQ appears
        self.assertIn('Can healthcare facilities hire part-time coders?', content)
        self.assertIn('facilities can engage professionals on flexible full-time', content)

    def test_contact_us_section_renders(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Check Contact header and details
        self.assertIn('CONTACT US', content)
        self.assertIn('Let’s Build Stronger Healthcare Teams Together', content)
        self.assertIn('support@kodafriq.com', content)
        self.assertIn('partnerships@kodafriq.com', content)
        self.assertIn('Send Us a Message', content)

    def test_contact_us_inquiry_submission(self):
        data = {
            'name': 'Dr. Marcus Vance',
            'email': 'mvance@clinic.org',
            'phone': '+1 (555) 234-5678',
            'inquiry_type': 'employer',
            'subject': 'Inquiry about Certified Medical Coders',
            'message': 'We are looking to onboard 3 ICD-10 certified coders for our clinic.'
        }
        response = self.client.post(reverse('core:contact_submit'), data)
        self.assertEqual(response.status_code, 302)
        
        inquiry = ContactInquiry.objects.filter(email='mvance@clinic.org').first()
        self.assertIsNotNone(inquiry)
        self.assertEqual(inquiry.name, 'Dr. Marcus Vance')
        self.assertEqual(inquiry.inquiry_type, 'employer')
        self.assertEqual(inquiry.subject, 'Inquiry about Certified Medical Coders')

    def test_contact_us_inquiry_ajax_submission(self):
        data = {
            'name': 'Jane Doe',
            'email': 'jane@example.com',
            'phone': '+234 800 000 0000',
            'inquiry_type': 'candidate',
            'subject': 'Verification inquiry',
            'message': 'How long does credential verification take?'
        }
        response = self.client.post(
            reverse('core:contact_submit'),
            data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertTrue(json_data['success'])

        inquiry = ContactInquiry.objects.filter(email='jane@example.com').first()
        self.assertIsNotNone(inquiry)

    def test_social_media_links_backend_configuration(self):
        settings = HomePageSetting.get_settings()
        settings.linkedin_url = ''
        settings.twitter_url = ''
        settings.facebook_url = ''
        settings.instagram_url = ''
        settings.youtube_url = ''
        settings.whatsapp_url = ''
        settings.save()

        response = self.client.get('/')
        content = response.content.decode('utf-8')
        self.assertNotIn('https://linkedin.com"', content)
        self.assertNotIn('https://twitter.com"', content)
        self.assertNotIn('https://facebook.com"', content)
        self.assertNotIn('https://youtube.com"', content)

        # Configure only LinkedIn and Twitter
        settings.linkedin_url = 'https://linkedin.com/company/kodafriq-official'
        settings.twitter_url = 'https://x.com/kodafriq'
        settings.save()

        response = self.client.get('/')
        content = response.content.decode('utf-8')
        self.assertIn('https://linkedin.com/company/kodafriq-official', content)
        self.assertIn('https://x.com/kodafriq', content)
        self.assertNotIn('https://facebook.com', content)
        self.assertNotIn('https://youtube.com', content)

    def test_footer_removed_links_including_cookie_policy(self):
        response = self.client.get('/')
        content = response.content.decode('utf-8')
        # Knowledge Base, Pricing, Blog and Cookie Policy must NOT appear in footer links
        self.assertNotIn('>Knowledge Base<', content)
        self.assertNotIn('>Pricing<', content)
        self.assertNotIn('>Blog<', content)
        self.assertNotIn('>Cookie Policy<', content)
        self.assertNotIn('Cookie Policy', content)

    def test_nav_menu_contact_us_link(self):
        response = self.client.get('/')
        content = response.content.decode('utf-8')
        self.assertIn('Contact Us', content)
        self.assertIn('id="navLinkContact"', content)
        self.assertIn('id="mobNavLinkContact"', content)

    def test_privacy_policy_page_renders_and_is_dynamic(self):
        # Check initial rendered page
        response = self.client.get(reverse('core:privacy_policy'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('Privacy Policy', content)
        self.assertIn('LEGAL &amp; COMPLIANCE', content)
        self.assertIn('Information We Collect', content)
        self.assertIn('Data Protection Office', content)

        # Test admin modification
        page = LegalPage.objects.filter(page_type='privacy').first()
        self.assertIsNotNone(page)
        page.title = "Kodafriq Global Privacy Policy"
        page.save()

        response2 = self.client.get(reverse('core:privacy_policy'))
        self.assertEqual(response2.status_code, 200)
        content2 = response2.content.decode('utf-8')
        self.assertIn('Kodafriq Global Privacy Policy', content2)

    def test_terms_of_service_page_renders_and_is_dynamic(self):
        # Check initial rendered page
        response = self.client.get(reverse('core:terms_of_service'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('Terms of Service', content)
        self.assertIn('Acceptance of Terms', content)
        self.assertIn('Healthcare Professional Obligations', content)
        self.assertIn('Milestone Escrow', content)

        # Test admin modification
        page = LegalPage.objects.filter(page_type='terms').first()
        self.assertIsNotNone(page)
        page.title = "Kodafriq Standard Terms of Service"
        page.save()

        response2 = self.client.get(reverse('core:terms_of_service'))
        self.assertEqual(response2.status_code, 200)
        content2 = response2.content.decode('utf-8')
        self.assertIn('Kodafriq Standard Terms of Service', content2)
