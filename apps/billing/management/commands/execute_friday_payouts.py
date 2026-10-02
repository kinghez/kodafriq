from django.core.management.base import BaseCommand
from datetime import date
from apps.billing.services.automation import execute_friday_payout_run


class Command(BaseCommand):
    help = (
        "Friday Batch Payout Engine (Friday 09:00 Cron): "
        "Evaluates settled invoices queued for payout, executes batch transfers "
        "via Paystack Ghana MoMo or Flutterwave Bank, marks invoices COMPLETED, and records transactions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate payout disbursements without executing transfers or modifying invoice statuses.',
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
            help='Force execution regardless of current day of week.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        target_date_str = options['date']
        force = options['force']

        mode_str = "DRY-RUN SIMULATION" if dry_run else "LIVE COMMITTED RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(f"=== Starting Friday Batch Payout Engine [{mode_str}] ==="))
        if target_date_str:
            self.stdout.write(f"Target Reference Date: {target_date_str}")

        result = execute_friday_payout_run(
            as_of_date=target_date_str,
            dry_run=dry_run,
            actor=None,
            force=force
        )

        self.stdout.write(f"Settled Invoices Evaluated: {result['invoices_evaluated']}")
        self.stdout.write(f"Candidates with Queued Funds: {result['candidates_count']}")
        self.stdout.write(f"Candidates Disbursed: {result['candidates_paid']}")
        self.stdout.write(f"Candidates Skipped / On Hold: {result['candidates_skipped']}")
        self.stdout.write(f"Invoices Completed: {result['invoices_completed']}")
        self.stdout.write(f"Total Disbursed: ${result['total_disbursed']}")

        if result['records']:
            self.stdout.write("\nDisbursement Batches Breakdown:")
            for rec in result['records']:
                if rec.get('status') in ['DISBURSED', 'PREVIEW_READY']:
                    status_color = self.style.SUCCESS
                    self.stdout.write(status_color(
                        f" - [PAID] {rec['candidate']} | Total: ${rec['amount']} | Destination: {rec['destination']} | "
                        f"Gateway: {rec.get('gateway')} | Ref: {rec.get('reference')} | Invoices: {', '.join(rec.get('invoices', []))}"
                    ))
                else:
                    status_color = self.style.ERROR
                    self.stdout.write(status_color(
                        f" - [HOLD] {rec['candidate']} | Total: ${rec['amount']} | Reason: {rec.get('message')} | Invoices: {', '.join(rec.get('invoices', []))}"
                    ))

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\n[DRY RUN COMPLETE] {result['summary']} (No database modifications committed)"))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n[SUCCESS] {result['summary']} (Audit Log ID: {result['log_id']})"))
