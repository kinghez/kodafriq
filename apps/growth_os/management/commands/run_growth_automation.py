"""
apps/growth_os/management/commands/run_growth_automation.py
CLI Command for executing autonomous continuous acquisition, worldwide discovery,
website contact/hiring crawling, and housekeeping routines.

Usage:
    python manage.py run_growth_automation --task=all --crawl
    python manage.py run_growth_automation --task=discover_worldwide --crawl
    python manage.py run_growth_automation --task=poll_vacancies --crawl
    python manage.py run_growth_automation --task=decay_intent
    python manage.py run_growth_automation --task=archive_dormant
"""
from django.core.management.base import BaseCommand
from apps.growth_os.services.automation import (
    run_worldwide_employer_discovery,
    poll_and_age_vacancies,
    apply_hiring_intent_decay,
    archive_dormant_leads,
    sync_candidate_availability_to_growth,
)
from apps.accounts.models import CandidateProfile


class Command(BaseCommand):
    help = 'Executes autonomous worldwide employer discovery, continuous monitoring, intent degradation, and housekeeping.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            default='all',
            choices=['all', 'discover_worldwide', 'poll_vacancies', 'decay_intent', 'archive_dormant', 'sync_availability'],
            help='Specific automation task to execute (default: all)'
        )
        parser.add_argument(
            '--crawl',
            action='store_true',
            help='Actively fetch and crawl employer websites & career portals for contacts, social links, and open roles'
        )
        parser.add_argument(
            '--markets',
            type=str,
            default='Worldwide',
            help='Comma-separated target markets for worldwide discovery (default: Worldwide)'
        )

    def handle(self, *args, **options):
        task = options.get('task')
        crawl = options.get('crawl', False)
        markets_raw = options.get('markets', 'Worldwide')
        markets = [m.strip() for m in markets_raw.split(',') if m.strip()] or ['Worldwide']

        self.stdout.write(self.style.NOTICE(f"🚀 Starting GrowthOS Autonomous Engine (task={task}, crawl={crawl})..."))

        if task in ['discover_worldwide', 'all']:
            self.stdout.write("  -> Running Worldwide Multi-Source Employer Discovery...")
            res_disc = run_worldwide_employer_discovery(
                markets=markets,
                scrape_websites=crawl,
            )
            self.stdout.write(self.style.SUCCESS(
                f"     Evaluated {res_disc['evaluated_count']} global companies across {res_disc['countries_count']} region(s): "
                f"{res_disc['created_count']} new imported, {res_disc['scraped_count']} scraped."
            ))

        if task in ['poll_vacancies', 'all']:
            self.stdout.write("  -> Running Vacancy Polling, Aging & DB Website Crawl...")
            res_vac = poll_and_age_vacancies(crawl=crawl)
            self.stdout.write(self.style.SUCCESS(
                f"     Evaluated {res_vac['total_evaluated']} vacancies: "
                f"{res_vac['persistent_count']} persistent, {res_vac['closed_count']} expired, "
                f"{res_vac.get('crawled_count', 0)} DB websites crawled."
            ))

        if task in ['decay_intent', 'all']:
            self.stdout.write("  -> Running Hiring Intent Degradation...")
            res_decay = apply_hiring_intent_decay()
            self.stdout.write(self.style.SUCCESS(
                f"     Evaluated {res_decay['total_evaluated']} leads: "
                f"{res_decay['decayed_count']} decayed."
            ))

        if task in ['archive_dormant', 'all']:
            self.stdout.write("  -> Running Dormant Lead Archiving...")
            res_arch = archive_dormant_leads()
            self.stdout.write(self.style.SUCCESS(
                f"     Evaluated {res_arch['total_evaluated']} leads: "
                f"{res_arch['archived_count']} auto-archived."
            ))

        if task == 'sync_availability':
            self.stdout.write("  -> Syncing Candidate Availability to GrowthOS...")
            candidates = CandidateProfile.objects.all()
            total_cand = candidates.count()
            updated_total = 0
            for cand in candidates:
                res_cand = sync_candidate_availability_to_growth(cand)
                updated_total += res_cand.get('updated_matches', 0)
            self.stdout.write(self.style.SUCCESS(
                f"     Evaluated {total_cand} candidates: {updated_total} matches adjusted."
            ))

        self.stdout.write(self.style.SUCCESS("\n✅ GrowthOS automation run completed successfully."))
