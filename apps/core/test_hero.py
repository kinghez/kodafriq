from django.test import TestCase, Client
from django.urls import reverse
from apps.core.models import HomePageSetting, ContactInquiry


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

    def test_faq_section_renders(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        # Check FAQ header and questions
        self.assertIn('FREQUENTLY ASKED QUESTIONS', content)
        self.assertIn('Got Questions? We’re Here to Help.', content)
        self.assertIn('How does healthcare candidate verification work on Kodafriq?', content)
        self.assertIn('Why do newly registered candidates start with a base score', content)
        self.assertIn('What healthcare specialties and roles are supported', content)
        self.assertIn('How quickly can healthcare employers hire and deploy talent?', content)
        self.assertIn('How does milestone escrow and payment protection work?', content)
        self.assertIn('Is Kodafriq compliant with healthcare data security', content)

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
        # Post valid form data
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
        
        # Check that inquiry was saved in DB
        inquiry = ContactInquiry.objects.filter(email='mvance@clinic.org').first()
        self.assertIsNotNone(inquiry)
        self.assertEqual(inquiry.name, 'Dr. Marcus Vance')
        self.assertEqual(inquiry.inquiry_type, 'employer')
        self.assertEqual(inquiry.subject, 'Inquiry about Certified Medical Coders')

    def test_contact_us_inquiry_ajax_submission(self):
        # Post via AJAX
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
        # By default, without URLs, social links shouldn't render
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
        # Check that dummy links are not present
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
        # Others must NOT be rendered
        self.assertNotIn('https://facebook.com', content)
        self.assertNotIn('https://youtube.com', content)
        self.assertNotIn('https://instagram.com', content)

    def test_footer_removed_links(self):
        response = self.client.get('/')
        content = response.content.decode('utf-8')
        # "Knowledge Base", "Pricing" and "Blog" must NOT appear in footer links
        self.assertNotIn('>Knowledge Base<', content)
        self.assertNotIn('>Pricing<', content)
        self.assertNotIn('>Blog<', content)

    def test_nav_menu_contact_us_link(self):
        response = self.client.get('/')
        content = response.content.decode('utf-8')
        # Nav menu must contain Contact Us link
        self.assertIn('Contact Us', content)
        self.assertIn('id="navLinkContact"', content)
        self.assertIn('id="mobNavLinkContact"', content)
