"""
apps/growth_os/management/commands/run_growth_automation.py
CLI Command for executing autonomous continuous acquisition & housekeeping routines:
- Recurring vacancy polling & aging (persistent vacancy detection)
- Hiring intent score decay for stale leads
- Automated archiving of dormant leads (90+ days without open roles or CRM touches)
- Candidate availability synchronization

Usage:
    python manage.py run_growth_automation --task=all
    python manage.py run_growth_automation --task=poll_vacancies --crawl
    python manage.py run_growth_automation --task=decay_intent
    python manage.py run_growth_automation --task=archive_dormant
"""
from django.core.management.base import BaseCommand
from apps.growth_os.services.automation import (
    poll_and_age_vacancies,
    apply_hiring_intent_decay,
    archive_dormant_leads,
    sync_candidate_availability_to_growth
)
from apps.accounts.models import CandidateProfile


class Command(BaseCommand):
    help = 'Executes autonomous continuous acquisition, intent degradation, and housekeeping routines.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            default='all',
            choices=['all', 'poll_vacancies', 'decay_intent', 'archive_dormant', 'sync_availability'],
            help='Specific automation task to execute (default: all)'
        )
        parser.add_argument(
            '--crawl',
            action='store_true',
            help='Actively fetch and crawl employer career portals during vacancy polling'
        )

    def handle(self, *args, **options):
        task = options.get('task')
        crawl = options.get('crawl', False)

        self.stdout.write(self.style.NOTICE(f"🚀 Starting GrowthOS Autonomous Engine (task={task}, crawl={crawl})..."))

        if task in ['poll_vacancies', 'all']:
            self.stdout.write("  -> Running Vacancy Polling & Aging...")
            res_vac = poll_and_age_vacancies(crawl=crawl)
            self.stdout.write(self.style.SUCCESS(
                f"     Evaluated {res_vac['total_evaluated']} vacancies: "
                f"{res_vac['persistent_count']} persistent, {res_vac['closed_count']} expired."
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

