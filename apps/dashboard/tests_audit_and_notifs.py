from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.contrib.admin.sites import AdminSite
from apps.dashboard.models import AuditLog, Notification
from apps.accounts.models import CandidateProfile, EmployerProfile
from apps.accounts.admin import CustomUserAdmin
from apps.employers.models import Job, Application, Shortlist
from apps.scoring.services import calculate_candidate_score

User = get_user_model()

class DummyForm:
    def __init__(self, changed_data):
        self.changed_data = changed_data

class AuditAndNotificationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@kodafriq.com',
            password='Password123!',
            first_name='Admin',
            last_name='Tester'
        )
        self.candidate_user = User.objects.create_user(
            username='candidate_test',
            email='candidate@example.com',
            password='Password123!',
            first_name='John',
            last_name='Doe',
            role=User.Role.CANDIDATE
        )
        self.candidate_profile = CandidateProfile.objects.get(user=self.candidate_user)

        self.employer_user = User.objects.create_user(
            username='employer_test',
            email='employer@example.com',
            password='Password123!',
            first_name='Jane',
            last_name='Smith',
            role=User.Role.EMPLOYER
        )
        self.employer_profile = EmployerProfile.objects.get(user=self.employer_user)

    def test_admin_user_suspension_creates_audit_log(self):
        """Editing a user in Django Admin to suspend them records an AuditLog with target_user and reason."""
        admin_obj = CustomUserAdmin(User, AdminSite())
        request = self.factory.post('/admin/accounts/user/1/change/')
        request.user = self.admin_user
        
        self.candidate_user.is_suspended = True
        self.candidate_user.suspension_reason = 'Suspicious compliance activity detected'
        form = DummyForm(changed_data=['is_suspended', 'suspension_reason'])

        admin_obj.save_model(request, self.candidate_user, form, change=True)
        self.candidate_user.refresh_from_db()
        self.assertTrue(self.candidate_user.is_suspended)

        # Check AuditLog
        suspension_log = AuditLog.objects.filter(
            action_category=AuditLog.Category.SUSPENSION,
            target_user=self.candidate_user
        ).first()
        self.assertIsNotNone(suspension_log)
        self.assertEqual(suspension_log.actor, self.admin_user)
        self.assertIn('Suspicious compliance activity detected', suspension_log.details)

    def test_admin_user_reactivation_creates_audit_log(self):
        """Lifting a suspension records an AuditLog entry."""
        self.candidate_user.is_suspended = True
        self.candidate_user.save()

        admin_obj = CustomUserAdmin(User, AdminSite())
        request = self.factory.post('/admin/accounts/user/1/change/')
        request.user = self.admin_user

        self.candidate_user.is_suspended = False
        form = DummyForm(changed_data=['is_suspended'])

        admin_obj.save_model(request, self.candidate_user, form, change=True)
        self.candidate_user.refresh_from_db()
        self.assertFalse(self.candidate_user.is_suspended)

        reactivation_log = AuditLog.objects.filter(
            action_category=AuditLog.Category.SUSPENSION,
            target_user=self.candidate_user,
            action__contains="Reactivated"
        ).first()
        self.assertIsNotNone(reactivation_log)

    def test_shortlist_dispatches_in_app_notification(self):
        """When an employer shortlists a candidate, an in-app Notification is generated."""
        self.client.force_login(self.employer_user)
        shortlist_url = reverse('employers:shortlist_toggle', args=[self.candidate_profile.id])
        
        response = self.client.post(shortlist_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)

        notif = Notification.objects.filter(
            recipient=self.candidate_user,
            notification_type=Notification.NotificationType.APPLICATION,
            title="Profile Shortlisted"
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn(self.employer_profile.company_name, notif.message)

    def test_candidate_dashboard_dynamic_context(self):
        """Candidate dashboard computes actual completion and zero baseline for new profile."""
        self.client.force_login(self.candidate_user)
        dash_url = reverse('dashboard:candidate')
        response = self.client.get(dash_url)
        self.assertEqual(response.status_code, 200)
        
        # Verify context is dynamically set and not forced to 20 or fake score
        self.assertIn('completion_pct', response.context)
        self.assertIn('verified_skills_count', response.context)
        self.assertIn('total_skills_count', response.context)
        self.assertIn('completed_assessments_count', response.context)
        self.assertEqual(response.context['verified_skills_count'], 0)
        self.assertEqual(response.context['completed_assessments_count'], 0)

    def test_employer_dashboard_dynamic_context(self):
        """Employer dashboard loads dynamically without hardcoded counts."""
        self.client.force_login(self.employer_user)
        dash_url = reverse('dashboard:employer')
        response = self.client.get(dash_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('talent_by_skill', response.context)
        self.assertIn('upcoming_interviews', response.context)
        self.assertIn('recent_notifications', response.context)

    def test_scoring_service_persists_final_score(self):
        """calculate_candidate_score updates kodafriq_verified_score on candidate profile."""
        score_data = calculate_candidate_score(self.candidate_profile)
        self.candidate_profile.refresh_from_db()
        self.assertEqual(float(self.candidate_profile.kodafriq_verified_score), score_data['final_score'])
