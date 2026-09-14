from django.test import TestCase, Client
from django.urls import reverse

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
        
        # Check master artwork reference
        self.assertIn('hero_master_1024.png', content)
