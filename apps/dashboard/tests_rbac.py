from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group
from django.urls import reverse

User = get_user_model()


class StaffDashboardRBACPermissionsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # 1. Superuser
        self.superuser = User.objects.create_superuser(
            username='boss_admin',
            email='boss@kodafriq.com',
            password='testpassword123',
            role=User.Role.ADMIN
        )

        # 2. Regular staff member (No extra permissions assigned)
        self.staff_user = User.objects.create_user(
            username='desk_officer',
            email='officer@kodafriq.com',
            password='testpassword123',
            role=User.Role.STAFF,
            is_staff=True
        )

        # 3. Regular candidate
        self.candidate_user = User.objects.create_user(
            username='talent_user',
            email='talent@kodafriq.com',
            password='testpassword123',
            role=User.Role.CANDIDATE
        )

    def test_permissions_exist_in_db(self):
        """Verify all 8 granular dashboard permissions exist under 'dashboard' app label."""
        expected_codenames = [
            'access_notifications',
            'access_contracts',
            'access_disputes',
            'access_payments',
            'access_automation',
            'access_analytics',
            'access_broadcasts',
            'access_security_audit',
        ]
        for codename in expected_codenames:
            exists = Permission.objects.filter(content_type__app_label='dashboard', codename=codename).exists()
            self.assertTrue(exists, f"Permission dashboard.{codename} should exist in database.")

    def test_default_staff_sidebar_shows_only_dashboard_and_control_panel(self):
        """
        By default, staff/admin users without assigned permissions must ONLY see
        the Dashboard page link and the Control Panel link.
        """
        self.client.login(username='desk_officer', password='testpassword123')
        response = self.client.get(reverse('dashboard:staff'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')

        # Must see Dashboard and Control Panel
        self.assertIn('<span>Dashboard</span>', content)
        self.assertIn('<span>Control Panel</span>', content)

        # Must NOT see any other page on sidebar
        self.assertNotIn('<span>Payments &amp; Payouts</span>', content)
        self.assertNotIn('<span>Automation Hub</span>', content)
        self.assertNotIn('<span>Dispute Center</span>', content)
        self.assertNotIn('<span>Client Contracts</span>', content)
        self.assertNotIn('<span>Analytics &amp; Reports</span>', content)
        self.assertNotIn('<span>Broadcasts &amp; Alerts</span>', content)
        self.assertNotIn('Platform Security &amp; Audit', content)

    def test_default_staff_cannot_access_restricted_views(self):
        """
        Staff members cannot access any restricted dashboard sections without permissions.
        They are redirected back to dashboard:staff with an informative message.
        """
        self.client.login(username='desk_officer', password='testpassword123')

        restricted_urls = [
            reverse('billing:payments_hub'),
            reverse('billing:automation_hub'),
            reverse('contracts:dispute_list'),
            reverse('contracts:contract_list'),
            reverse('dashboard:staff_analytics'),
            reverse('notifications:admin_broadcast'),
            reverse('dashboard:staff_audit_logs'),
            reverse('dashboard:staff_visitors'),
        ]

        for url in restricted_urls:
            resp = self.client.get(url, follow=False)
            self.assertEqual(
                resp.status_code,
                302,
                f"Staff user without permission should be redirected from {url}"
            )
            self.assertEqual(resp.url, reverse('dashboard:staff'))

    def test_staff_with_granted_permission_can_access_and_see_sidebar(self):
        """
        Granting specific permissions immediately reveals the sidebar link
        and allows access to the corresponding page.
        """
        self.client.login(username='desk_officer', password='testpassword123')

        # Initially cannot access Payments
        resp_before = self.client.get(reverse('billing:payments_hub'))
        self.assertEqual(resp_before.status_code, 302)

        # Grant access_payments permission
        perm_payments = Permission.objects.get(content_type__app_label='dashboard', codename='access_payments')
        self.staff_user.user_permissions.add(perm_payments)

        # Clear cached permissions
        self.staff_user = User.objects.get(pk=self.staff_user.pk)

        # Now can access Payments & Payouts page
        resp_after = self.client.get(reverse('billing:payments_hub'))
        self.assertEqual(resp_after.status_code, 200)

        # Sidebar now contains Payments & Payouts
        dash_resp = self.client.get(reverse('dashboard:staff'))
        dash_content = dash_resp.content.decode('utf-8')
        self.assertIn('<span>Payments &amp; Payouts</span>', dash_content)

        # Other restricted pages remain locked
        self.assertNotIn('<span>Automation Hub</span>', dash_content)
        self.assertNotIn('<span>Dispute Center</span>', dash_content)
        resp_auto = self.client.get(reverse('billing:automation_hub'))
        self.assertEqual(resp_auto.status_code, 302)

    def test_group_permission_assignment(self):
        """
        A superuser can assign permissions via standard Django Admin Groups.
        """
        group = Group.objects.create(name='Mediation Officers')
        perm_disputes = Permission.objects.get(content_type__app_label='dashboard', codename='access_disputes')
        group.permissions.add(perm_disputes)

        self.staff_user.groups.add(group)

        self.client.login(username='desk_officer', password='testpassword123')

        # Now has Dispute Center access through group
        resp = self.client.get(reverse('contracts:dispute_list'))
        self.assertEqual(resp.status_code, 200)

        # Sidebar displays Dispute Center
        dash_resp = self.client.get(reverse('dashboard:staff'))
        dash_content = dash_resp.content.decode('utf-8')
        self.assertIn('<span>Dispute Center</span>', dash_content)

    def test_superuser_has_unrestricted_sidebar_and_access(self):
        """
        Superuser unconditionally accesses all pages and sees all sidebar links.
        """
        self.client.login(username='boss_admin', password='testpassword123')

        dash_resp = self.client.get(reverse('dashboard:staff'))
        self.assertEqual(dash_resp.status_code, 200)
        dash_content = dash_resp.content.decode('utf-8')

        # Superuser sees ALL links
        self.assertIn('<span>Dashboard</span>', dash_content)
        self.assertIn('<span>Notifications</span>', dash_content)
        self.assertIn('<span>Client Contracts</span>', dash_content)
        self.assertIn('<span>Dispute Center</span>', dash_content)
        self.assertIn('<span>Payments &amp; Payouts</span>', dash_content)
        self.assertIn('<span>Automation Hub</span>', dash_content)
        self.assertIn('<span>Analytics &amp; Reports</span>', dash_content)
        self.assertIn('<span>Broadcasts &amp; Alerts</span>', dash_content)
        self.assertIn('<span>Control Panel</span>', dash_content)
        self.assertIn('Platform Security &amp; Audit', dash_content)

        # Direct access to all pages succeeds
        restricted_urls = [
            reverse('billing:payments_hub'),
            reverse('billing:automation_hub'),
            reverse('contracts:dispute_list'),
            reverse('contracts:contract_list'),
            reverse('dashboard:staff_analytics'),
            reverse('notifications:admin_broadcast'),
            reverse('dashboard:staff_audit_logs'),
            reverse('dashboard:staff_visitors'),
        ]
        for url in restricted_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Superuser should access {url}")
