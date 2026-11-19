"""
apps/growth_os/management/commands/send_growth_weekly_digest.py
Dispatches the GrowthOS Weekly Executive BD & Commercial Pipeline Performance Digest.

Usage:
    python manage.py send_growth_weekly_digest
    python manage.py send_growth_weekly_digest --email=ceo@kodafriq.com
    python manage.py send_growth_weekly_digest --dry-run
"""
from django.core.management.base import BaseCommand
from apps.growth_os.services.automation import generate_weekly_bd_digest, send_weekly_bd_digest_email


class Command(BaseCommand):
    help = 'Generates and dispatches the weekly GrowthOS Executive BD and Commercial Performance Digest.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            help='Override recipient email address (defaults to staff & superusers)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Computes digest KPIs and prints to console without dispatching email'
        )

    def handle(self, *args, **options):
        recipient = options.get('email')
        dry_run = options.get('dry_run', False)

        self.stdout.write(self.style.NOTICE("📊 Computing Weekly GrowthOS Commercial Digest..."))

        if dry_run:
            digest = generate_weekly_bd_digest()
            self.stdout.write(self.style.SUCCESS(
                f"\n--- GROWTHOS WEEKLY DIGEST ({digest['period_start']} – {digest['period_end']}) ---"
            ))
            self.stdout.write(f"New Leads Sourced:         {digest['new_leads_count']}")
            if digest.get('sectors_breakdown'):
                for sec, count in digest['sectors_breakdown'].items():
                    self.stdout.write(f"  - {sec}: {count}")
            else:
                self.stdout.write("  - No sector leads recorded in window.")
            self.stdout.write(f"New Vacancies Detected:    {digest['new_vacancies_count']}")
            self.stdout.write(f"Persistent Vacancies:      {digest['persistent_signals_count']}")
            self.stdout.write(f"Tier 1 High-Intent Leads:  {digest['tier_1_count']}")
            self.stdout.write(f"Outreach Dispatched:       {digest['outreach_sent_count']}")
            self.stdout.write(f"Outreach Response Rate:    {digest['response_rate']}%")
            self.stdout.write(f"Total Pipeline Value:      ${digest['active_pipeline_value']:,.2f}")
            self.stdout.write(f"Closed Won MRR:            ${digest['won_mrr_added']:,.2f}")
            self.stdout.write(f"Overdue Follow-ups:        {digest['overdue_followups_count']}")
            self.stdout.write(self.style.SUCCESS("\n[DRY RUN] No email was dispatched."))
            return

        recipients = [recipient] if recipient else None
        res = send_weekly_bd_digest_email(recipients=recipients)

        if res.get('success'):
            self.stdout.write(self.style.SUCCESS(
                f"✅ Weekly digest successfully sent to {len(res['recipients'])} recipient(s): "
                f"{', '.join(res['recipients'])}"
            ))
        else:
            self.stdout.write(self.style.ERROR(f"❌ Failed to dispatch digest email: {res.get('error')}"))

