from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django.contrib.messages.storage.fallback import FallbackStorage

from apps.notifications.models import NotificationBroadcast, BroadcastDeliveryLog
from apps.notifications.services import NotificationService
from apps.notifications.views import AdminBroadcastCenterView, AdminBroadcastDetailView
from apps.dashboard.models import Notification

User = get_user_model()


class NotificationBroadcastSystemTests(TestCase):
    def setUp(self):
        # Create users for all roles
        self.admin = User.objects.create_superuser(
            username='notif_admin',
            email='admin@kodafriq.test',
            password='testpassword123',
            role='ADMIN'
        )
        self.employer1 = User.objects.create_user(
            username='notif_emp1',
            email='emp1@hospital.test',
            password='testpassword123',
            role='EMPLOYER'
        )
        self.employer2 = User.objects.create_user(
            username='notif_emp2',
            email='emp2@clinic.test',
            password='testpassword123',
            role='EMPLOYER'
        )
        self.candidate1 = User.objects.create_user(
            username='notif_cand1',
            email='cand1@coder.test',
            password='testpassword123',
            role='CANDIDATE'
        )
        self.candidate2 = User.objects.create_user(
            username='notif_cand2',
            email='cand2@coder.test',
            password='testpassword123',
            role='CANDIDATE'
        )
        # Create a Django auth group
        self.group = Group.objects.create(name="Clinical Reviewers")
        self.candidate1.groups.add(self.group)

        self.rf = RequestFactory()

    def test_single_user_in_app_broadcast(self):
        broadcast = NotificationBroadcast.objects.create(
            sender=self.admin,
            channel=NotificationBroadcast.Channel.IN_APP,
            target_type=NotificationBroadcast.TargetType.SINGLE_USER,
            title="Single User Alert",
            message="Your clinical verification document is ready for review.",
            action_url="/dashboard/"
        )
        broadcast.target_users.set([self.candidate1])

        results = NotificationService.dispatch_broadcast(broadcast)
        broadcast.refresh_from_db()

        self.assertEqual(results['total_recipients'], 1)
        self.assertEqual(results['success_count'], 1)
        self.assertEqual(broadcast.status, NotificationBroadcast.Status.SENT)

        # Check in-app notification created for candidate1
        cand1_notif = Notification.objects.filter(recipient=self.candidate1, title="Single User Alert").first()
        self.assertIsNotNone(cand1_notif)
        self.assertEqual(cand1_notif.message, "Your clinical verification document is ready for review.")
        self.assertEqual(cand1_notif.link, "/dashboard/")

        # Ensure candidate2 did not receive it
        cand2_notif = Notification.objects.filter(recipient=self.candidate2, title="Single User Alert").first()
        self.assertIsNone(cand2_notif)

        # Check delivery log
        log = BroadcastDeliveryLog.objects.filter(broadcast=broadcast, recipient=self.candidate1).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, BroadcastDeliveryLog.DeliveryStatus.SUCCESS)
        self.assertEqual(log.channel, 'IN_APP')

    def test_all_employers_broadcast(self):
        broadcast = NotificationBroadcast.objects.create(
            sender=self.admin,
            channel=NotificationBroadcast.Channel.IN_APP,
            target_type=NotificationBroadcast.TargetType.ALL_EMPLOYERS,
            title="New Candidates Verified",
            message="15 new certified inpatient coders are available for requisition matching."
        )
        results = NotificationService.dispatch_broadcast(broadcast)

        # Employer 1 and Employer 2 should receive it
        self.assertTrue(Notification.objects.filter(recipient=self.employer1, title="New Candidates Verified").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.employer2, title="New Candidates Verified").exists())
        # Candidates should not receive it
        self.assertFalse(Notification.objects.filter(recipient=self.candidate1, title="New Candidates Verified").exists())

    def test_all_professionals_broadcast(self):
        broadcast = NotificationBroadcast.objects.create(
            sender=self.admin,
            channel=NotificationBroadcast.Channel.IN_APP,
            target_type=NotificationBroadcast.TargetType.ALL_PROFESSIONALS,
            title="New Training Modules Released",
            message="AAPC accredited CEU module is now live on your workspace."
        )
        results = NotificationService.dispatch_broadcast(broadcast)

        # Candidates receive it
        self.assertTrue(Notification.objects.filter(recipient=self.candidate1, title="New Training Modules Released").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.candidate2, title="New Training Modules Released").exists())
        # Employers should not receive it
        self.assertFalse(Notification.objects.filter(recipient=self.employer1, title="New Training Modules Released").exists())

    def test_django_group_targeting(self):
        broadcast = NotificationBroadcast.objects.create(
            sender=self.admin,
            channel=NotificationBroadcast.Channel.IN_APP,
            target_type=NotificationBroadcast.TargetType.GROUP,
            target_group=self.group,
            title="Group Notice: Clinical Reviewers",
            message="Meeting at 2 PM GMT for audit standard alignment."
        )
        results = NotificationService.dispatch_broadcast(broadcast)

        # Candidate1 is in the group -> receives it
        self.assertTrue(Notification.objects.filter(recipient=self.candidate1, title="Group Notice: Clinical Reviewers").exists())
        # Candidate2 is NOT in the group -> does not receive it
        self.assertFalse(Notification.objects.filter(recipient=self.candidate2, title="Group Notice: Clinical Reviewers").exists())

    def test_multi_channel_broadcast(self):
        broadcast = NotificationBroadcast.objects.create(
            sender=self.admin,
            channel=NotificationBroadcast.Channel.BOTH,
            target_type=NotificationBroadcast.TargetType.SINGLE_USER,
            title="Urgent Security Verification",
            message="Please verify your two-factor credentials.",
            action_url="/accounts/security/",
            action_button_text="Verify Now"
        )
        broadcast.target_users.set([self.candidate1])

        results = NotificationService.dispatch_broadcast(broadcast)

        # Both In-App and Email logs created
        logs = BroadcastDeliveryLog.objects.filter(broadcast=broadcast, recipient=self.candidate1)
        self.assertEqual(logs.count(), 2)
        channels = set(logs.values_list('channel', flat=True))
        self.assertEqual(channels, {'IN_APP', 'EMAIL'})

    def test_admin_broadcast_center_view_get(self):
        req = self.rf.get(reverse('notifications:admin_broadcast'))
        req.user = self.admin
        setattr(req, 'session', {})
        setattr(req, '_messages', FallbackStorage(req))
        view = AdminBroadcastCenterView.as_view()
        response = view(req)
        self.assertEqual(response.status_code, 200)

    def test_admin_broadcast_center_view_non_staff_denied(self):
        req = self.rf.get(reverse('notifications:admin_broadcast'))
        req.user = self.candidate1
        setattr(req, 'session', {})
        setattr(req, '_messages', FallbackStorage(req))
        view = AdminBroadcastCenterView.as_view()
        response = view(req)
        # Should redirect with error
        self.assertEqual(response.status_code, 302)

    def test_admin_broadcast_center_view_post_send(self):
        req = self.rf.post(reverse('notifications:admin_broadcast'), data={
            'channel': 'IN_APP',
            'target_type': 'SINGLE_USER',
            'target_single_user': self.candidate2.id,
            'notification_type': 'SYSTEM',
            'title': 'Test Post Broadcast',
            'message': 'Testing broadcast dispatch from view POST handler.',
            'action_url': '/dashboard/',
            'action_button_text': 'View Dashboard',
        })
        req.user = self.admin
        setattr(req, 'session', {})
        setattr(req, '_messages', FallbackStorage(req))

        view = AdminBroadcastCenterView.as_view()
        response = view(req)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Notification.objects.filter(recipient=self.candidate2, title='Test Post Broadcast').exists())
