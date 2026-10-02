from django.core.management.base import BaseCommand
from datetime import date
from apps.billing.services.automation import lock_closing_timesheets


class Command(BaseCommand):
    help = (
        "Weekly Timesheet Lock Engine (Sunday 23:59 Cron): "
        "Locks active draft timesheets, generates issued employer invoices, "
        "dispatches notifications, and initializes next week's empty timesheets."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate timesheet lock and invoice generation without writing mutations to the database.',
        )
        parser.add_argument(
            '--date',
            type=str,
            default=None,
            help='Target reference date in YYYY-MM-DD format (defaults to today).',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force locking of all draft timesheets regardless of week_end_date.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        target_date_str = options['date']
        force = options['force']

        mode_str = "DRY-RUN SIMULATION" if dry_run else "LIVE COMMITTED RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(f"=== Starting Weekly Timesheet Lock Engine [{mode_str}] ==="))
        if target_date_str:
            self.stdout.write(f"Target Reference Date: {target_date_str}")

        result = lock_closing_timesheets(
            as_of_date=target_date_str,
            dry_run=dry_run,
            actor=None,
            force=force
        )

        self.stdout.write(f"Evaluated Contracts: {result['contracts_evaluated']}")
        self.stdout.write(f"Timesheets Locked: {result['timesheets_locked']}")
        self.stdout.write(f"Total Hours Locked: {result['total_hours']} hrs")
        self.stdout.write(f"Total Amount Invoiced: ${result['total_amount']}")
        self.stdout.write(f"Next-Week Timesheets Initialized: {result['next_week_initialized']}")

        if result['records']:
            self.stdout.write("\nDetailed Records Breakdown:")
            for rec in result['records']:
                status_color = self.style.SUCCESS if rec.get('action') in ['LOCKED_AND_INVOICED', 'PREVIEW_LOCK'] else self.style.WARNING
                self.stdout.write(status_color(
                    f" - [{rec['contract_ref']}] {rec['candidate']} | Week Ending: {rec['week_ending']} | "
                    f"Hours: {rec['hours']} | Gross: ${rec['amount']} | Invoice: {rec['invoice_ref']} | Action: {rec['action']}"
                ))

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\n[DRY RUN COMPLETE] {result['summary']} (No database modifications committed)"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n[SUCCESS] {result['summary']} (Audit Log ID: {result['log_id']})"))
