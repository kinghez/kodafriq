"""
apps/growth_os/management/commands/run_lead_discovery.py
CLI command to execute worldwide multi-source employer discovery across Healthcare,
IT/Cloud/Security, Finance, and BPO and optionally scrape discovered company websites.
Usage:
    python manage.py run_lead_discovery --query="medical billing" --country="Worldwide" --limit=30
"""
from django.core.management.base import BaseCommand
from apps.growth_os.services.connectors import search_all_connectors
from apps.growth_os.services.discovery import import_discovered_lead


class Command(BaseCommand):
    help = 'Discovers worldwide hiring employers across Healthcare, IT, Finance & BPO from multiple live sources.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--query',
            type=str,
            default='medical billing software engineering accounting',
            help='Search terms or vertical criteria'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=30,
            help='Maximum number of companies to discover'
        )
        parser.add_argument(
            '--country',
            type=str,
            default='Worldwide',
            help='Target country or Worldwide'
        )
        parser.add_argument(
            '--scrape',
            action='store_true',
            help='Also scrape each newly discovered company website for contact details, social profiles, and careers pages'
        )

    def handle(self, *args, **options):
        query = options['query']
        limit = options['limit']
        country = options['country']
        scrape = options.get('scrape', False)

        self.stdout.write(self.style.NOTICE(
            f"🔍 Executing Worldwide GrowthOS Discovery for '{query}' in {country} (Limit: {limit})..."
        ))
        results = search_all_connectors(
            query=query,
            location=country,
            limit_per_source=max(4, min(15, (limit // 3) + 2)),
        )[:limit]

        if not results:
            self.stdout.write(self.style.WARNING("No matching organizations found."))
            return

        self.stdout.write(self.style.SUCCESS(f"Found {len(results)} candidate organizations. Ingesting into database..."))
        created_count = 0
        updated_count = 0

        for r in results:
            try:
                lead, created = import_discovered_lead(r, scrape_website=scrape)
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  + [NEW] {lead.company_name} ({lead.domain}, {lead.country}) - Intent: {lead.hiring_intent_score}% | Fit: {lead.talent_fit_score}%"
                    ))
                else:
                    updated_count += 1
                    self.stdout.write(f"  ~ [EXISTS] {lead.company_name} ({lead.domain})")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ! Error importing {r.get('company_name')}: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Discovery complete. Total: {len(results)} | Created: {created_count} | Updated: {updated_count}"
        ))
