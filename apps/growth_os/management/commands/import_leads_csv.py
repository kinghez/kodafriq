"""
apps/growth_os/management/commands/import_leads_csv.py
CLI command to import prospective healthcare employer leads in bulk from a CSV file.
Usage:
    python manage.py import_leads_csv /path/to/leads.csv
"""
import os
from django.core.management.base import BaseCommand
from apps.growth_os.services.discovery import import_leads_from_csv


class Command(BaseCommand):
    help = 'Bulk imports prospective healthcare employer leads from a CSV file.'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_path',
            type=str,
            help='Path to the CSV file on disk'
        )

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f"CSV file not found: {csv_path}"))
            return

        self.stdout.write(self.style.NOTICE(f"📂 Reading and parsing CSV file: {csv_path}..."))
        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        results = import_leads_from_csv(content)

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ CSV Ingestion Complete!"
            f"\n   Total Processed: {results['total']}"
            f"\n   Created (New):   {results['created']}"
            f"\n   Updated:         {results['updated']}"
            f"\n   Skipped:         {results['skipped']}"
        ))

        if results['errors']:
            self.stdout.write(self.style.WARNING(f"\n⚠️ Encountered {len(results['errors'])} notice(s):"))
            for err in results['errors'][:10]:
                self.stdout.write(f"   - {err}")
            if len(results['errors']) > 10:
                self.stdout.write(f"   ... and {len(results['errors']) - 10} more.")

