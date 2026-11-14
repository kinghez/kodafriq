"""
apps/growth_os/management/commands/scan_hiring_intent.py
CLI command to scan employer career pages and recalculate hiring intent scores across leads.
Usage:
    python manage.py scan_hiring_intent --rescore-all
    python manage.py scan_hiring_intent --domain=optum.com
"""
from django.core.management.base import BaseCommand
from apps.growth_os.models import EmployerLead
from apps.growth_os.services.scraper import inspect_lead_career_page
from apps.growth_os.services.intent import calculate_lead_intent_score
from apps.growth_os.services.matcher import compute_lead_reverse_matches


class Command(BaseCommand):
    help = 'Scans career pages, evaluates active vacancies, and updates hiring intent scores.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--rescore-all',
            action='store_true',
            help='Recalculate intent scores and reverse matches for all tracked employer leads'
        )
        parser.add_argument(
            '--crawl',
            action='store_true',
            help='Actively fetch and crawl career portals / websites of tracked leads'
        )
        parser.add_argument(
            '--domain',
            type=str,
            help='Scan a single employer by domain'
        )

    def handle(self, *args, **options):
        domain = options.get('domain')
        rescore_all = options.get('rescore_all')
        crawl = options.get('crawl')

        if domain:
            leads = EmployerLead.objects.filter(domain=domain)
            if not leads.exists():
                self.stdout.write(self.style.ERROR(f"No employer lead found with domain '{domain}'."))
                return
        elif rescore_all or crawl:
            leads = EmployerLead.objects.all()
        else:
            leads = EmployerLead.objects.filter(status__in=[
                EmployerLead.Status.LEAD,
                EmployerLead.Status.QUALIFIED,
                EmployerLead.Status.IN_PIPELINE
            ])

        total = leads.count()
        self.stdout.write(self.style.NOTICE(f"🚀 Scanning {total} employer lead(s)... (crawl={crawl})"))

        scanned = 0
        promoted_tier_1 = 0

        for lead in leads:
            old_tier = lead.priority_tier
            old_intent = lead.hiring_intent_score

            if crawl and (lead.careers_url or lead.website):
                try:
                    res = inspect_lead_career_page(lead)
                    vac_found = res.get('vacancies_detected', 0)
                    if vac_found > 0:
                        self.stdout.write(self.style.SUCCESS(f"  [{lead.company_name}] Discovered {vac_found} vacancy signal(s)."))
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"  [{lead.company_name}] Web scan error: {e}"))

            new_intent = calculate_lead_intent_score(lead)
            new_fit = compute_lead_reverse_matches(lead)
            new_tier = lead.priority_tier

            if new_tier == 1 and old_tier != 1:
                promoted_tier_1 += 1
                self.stdout.write(self.style.SUCCESS(f"  🔥 PROMOTED TO TIER 1: {lead.company_name} (Intent: {new_intent}%, Fit: {new_fit}%)"))
            elif new_intent != old_intent:
                self.stdout.write(f"  ~ {lead.company_name}: Intent {old_intent}% -> {new_intent}% (Tier {new_tier})")

            scanned += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Completed intent scan for {scanned} leads. Promoted to Tier 1: {promoted_tier_1}."
        ))

