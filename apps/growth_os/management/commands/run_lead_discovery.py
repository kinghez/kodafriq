"""
apps/growth_os/management/commands/run_lead_discovery.py
CLI command to execute automated healthcare employer discovery searches and ingest leads.
Usage:
    python manage.py run_lead_discovery --query="medical billing services Texas" --limit=10
"""
from django.core.management.base import BaseCommand
from apps.growth_os.services.discovery import search_healthcare_employers, import_discovered_lead


class Command(BaseCommand):
    help = 'Discovers healthcare employers, RCM firms, and medical billing/coding targets.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--query',
            type=str,
            default='medical billing revenue cycle management',
            help='Search terms or vertical criteria'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='Maximum number of companies to discover'
        )
        parser.add_argument(
            '--country',
            type=str,
            default='United States',
            help='Target country'
        )

    def handle(self, *args, **options):
        query = options['query']
        limit = options['limit']
        country = options['country']

        self.stdout.write(self.style.NOTICE(f"🔍 Executing GrowthOS Discovery for '{query}' in {country} (Limit: {limit})..."))
        results = search_healthcare_employers(query=query, limit=limit, country=country)

        if not results:
            self.stdout.write(self.style.WARNING("No matching organizations found."))
            return

        self.stdout.write(self.style.SUCCESS(f"Found {len(results)} candidate organizations. Ingesting into database..."))
        created_count = 0
        updated_count = 0

        for r in results:
            try:
                lead, created = import_discovered_lead(r)
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  + [NEW] {lead.company_name} ({lead.domain}) - Intent: {lead.hiring_intent_score}% | Fit: {lead.talent_fit_score}%"))
                else:
                    updated_count += 1
                    self.stdout.write(f"  ~ [EXISTS] {lead.company_name} ({lead.domain})")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ! Error importing {r.get('company_name')}: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Discovery complete. Total: {len(results)} | Created: {created_count} | Updated: {updated_count}"
        ))

