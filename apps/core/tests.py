from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from apps.core.models import Announcement


class AnnouncementModelTestCase(TestCase):
    def setUp(self):
        self.announcement = Announcement.objects.create(
            title="Kodafriq Launch Test",
            eyebrow_badge="LIVE LAUNCH",
            headline="Global Healthcare Talent",
            body_text="Testing announcement body text.",
            event_datetime_text="Saturday, 10 October 2026 • 5:00 PM UK",
            primary_action_text="Join Live",
            primary_action_url="https://calendar.app.google/ox5GwEg89EsPeYJ39",
            target_placement="both",
            display_mode="both",
            content_format="full",
            popup_trigger_type="delay",
            popup_delay_seconds=3,
            is_active=True,
            priority=100
        )

    def test_announcement_creation(self):
        self.assertEqual(self.announcement.title, "Kodafriq Launch Test")
        self.assertTrue(self.announcement.is_active)
        self.assertTrue(self.announcement.has_links)
        self.assertIn("ACTIVE", str(self.announcement))

    def test_inactive_announcement(self):
        self.announcement.is_active = False
        self.announcement.save()
        self.assertIn("INACTIVE", str(self.announcement))

    def test_schedule_filtering(self):
        # In the future
        future_announcement = Announcement.objects.create(
            title="Future Event",
            start_datetime=timezone.now() + timedelta(days=2),
            is_active=True
        )
        c = Client()
        r = c.get('/')
        self.assertNotIn("Future Event", r.content.decode('utf-8'))

    def test_homepage_rendering(self):
        c = Client()
        r = c.get('/')
        self.assertEqual(r.status_code, 200)
        content = r.content.decode('utf-8')
        self.assertIn("kfAnnouncementBanner", content)
        self.assertIn("kfAnnouncementModalBackdrop", content)
        self.assertIn("calendar.app.google", content)
