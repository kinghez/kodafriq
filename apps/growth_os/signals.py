"""
apps/growth_os/signals.py
Signal receivers connecting core ecosystem events (Candidate availability changes,
Contract signings, timesheet placements) to the GrowthOS Acquisition & Reverse Matching Engine.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.accounts.models import CandidateProfile
from apps.contracts.models import Contract
from apps.growth_os.services.automation import sync_candidate_availability_to_growth

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CandidateProfile)
def candidate_profile_growth_sync(sender, instance, created, **kwargs):
    """
    Whenever candidate availability or profile changes, automatically sync
    their readiness with active GrowthOS reverse match opportunities.
    """
    try:
        sync_candidate_availability_to_growth(instance)
    except Exception as e:
        logger.warning(f"[GrowthOS Signals] Candidate profile sync failed for id={instance.id}: {e}")


@receiver(post_save, sender=Contract)
def contract_status_growth_sync(sender, instance, created, **kwargs):
    """
    When a contract is created or updated (e.g. marked ACTIVE or TERMINATED),
    sync candidate availability status across employer pipeline shortlists.
    """
    try:
        if instance.candidate:
            sync_candidate_availability_to_growth(instance.candidate)
    except Exception as e:
        logger.warning(f"[GrowthOS Signals] Contract status sync failed for contract_ref={instance.contract_ref}: {e}")


@receiver(post_delete, sender=Contract)
def contract_delete_growth_sync(sender, instance, **kwargs):
    """
    When a contract is deleted, re-evaluate candidate availability.
    """
    try:
        if instance.candidate:
            sync_candidate_availability_to_growth(instance.candidate)
    except Exception as e:
        logger.warning(f"[GrowthOS Signals] Contract deletion sync failed: {e}")

