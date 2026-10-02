from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import models
from apps.billing.models import ContractInvoice, PlatformFeeConfig, CandidatePayoutProfile
from apps.contracts.models import Timesheet, Milestone, Contract


def get_next_payout_date(from_date=None):
    """
    Computes the upcoming Friday payout settlement date.
    Friday = weekday 4.
    """
    if from_date is None:
        today = timezone.localdate()
    else:
        today = from_date

    # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    days_ahead = 4 - today.weekday()
    if days_ahead <= 0:  # Today is Friday, Saturday, or Sunday -> next Friday
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def generate_invoice_for_timesheet(timesheet):
    """
    Generates or updates a ContractInvoice from an approved or submitted timesheet.
    Implements the Upwork-style formula:
    - Talent Guaranteed Earnings: $R (100% of candidate agreed rate)
    - Kodafriq Service Markup: 10% ($M)
    - Gateway Processing Fee: 2.9% + $0.30 pass-through
    - Employer Gross Billed: $R + $M + Processing Fee
    """
    contract = timesheet.contract
    fee_cfg = PlatformFeeConfig.get_active()

    talent_earnings = timesheet.talent_gross_earnings
    if talent_earnings <= Decimal('0.00'):
        return None

    # Calculate Kodafriq 10% fee
    fee_percent = contract.kodafriq_fee_percent or fee_cfg.fee_percent
    kodafriq_fee = (talent_earnings * (fee_percent / Decimal('100.00'))).quantize(Decimal('0.01'))

    subtotal = talent_earnings + kodafriq_fee

    # Gateway interchange pass-through (2.9% + $0.30)
    processing_fee = ((subtotal * (fee_cfg.gateway_processing_fee_percent / Decimal('100.00'))) + fee_cfg.gateway_flat_fee).quantize(Decimal('0.01'))
    gross_amount = (subtotal + processing_fee).quantize(Decimal('0.01'))

    due_date = timesheet.week_end_date + timedelta(days=4)  # Thursday of the following week

    invoice, created = ContractInvoice.objects.get_or_create(
        timesheet=timesheet,
        defaults={
            'contract': contract,
            'billing_period_start': timesheet.week_start_date,
            'billing_period_end': timesheet.week_end_date,
            'currency': contract.currency,
            'talent_earnings': talent_earnings,
            'kodafriq_fee': kodafriq_fee,
            'processing_fee': processing_fee,
            'gross_amount': gross_amount,
            'payment_status': ContractInvoice.PaymentStatus.ISSUED if timesheet.status == Timesheet.Status.APPROVED else ContractInvoice.PaymentStatus.DRAFT,
            'payout_status': ContractInvoice.PayoutStatus.PENDING,
            'due_date': due_date,
        }
    )

    if not created:
        invoice.talent_earnings = talent_earnings
        invoice.kodafriq_fee = kodafriq_fee
        invoice.processing_fee = processing_fee
        invoice.gross_amount = gross_amount
        if timesheet.status == Timesheet.Status.APPROVED and invoice.payment_status == ContractInvoice.PaymentStatus.DRAFT:
            invoice.payment_status = ContractInvoice.PaymentStatus.ISSUED
        invoice.save()

    return invoice


def generate_invoice_for_milestone(milestone):
    """
    Generates or updates a ContractInvoice for an approved milestone deliverable.
    """
    contract = milestone.contract
    fee_cfg = PlatformFeeConfig.get_active()

    talent_earnings = milestone.amount
    if talent_earnings <= Decimal('0.00'):
        return None

    fee_percent = contract.kodafriq_fee_percent or fee_cfg.fee_percent
    kodafriq_fee = (talent_earnings * (fee_percent / Decimal('100.00'))).quantize(Decimal('0.01'))
    subtotal = talent_earnings + kodafriq_fee

    processing_fee = ((subtotal * (fee_cfg.gateway_processing_fee_percent / Decimal('100.00'))) + fee_cfg.gateway_flat_fee).quantize(Decimal('0.01'))
    gross_amount = (subtotal + processing_fee).quantize(Decimal('0.01'))

    today = timezone.localdate()
    due_date = today + timedelta(days=3)

    invoice, created = ContractInvoice.objects.get_or_create(
        milestone=milestone,
        defaults={
            'contract': contract,
            'billing_period_start': milestone.due_date or today,
            'billing_period_end': milestone.due_date or today,
            'currency': contract.currency,
            'talent_earnings': talent_earnings,
            'kodafriq_fee': kodafriq_fee,
            'processing_fee': processing_fee,
            'gross_amount': gross_amount,
            'payment_status': ContractInvoice.PaymentStatus.ISSUED,
            'payout_status': ContractInvoice.PayoutStatus.PENDING,
            'due_date': due_date,
        }
    )

    if not created:
        invoice.talent_earnings = talent_earnings
        invoice.kodafriq_fee = kodafriq_fee
        invoice.processing_fee = processing_fee
        invoice.gross_amount = gross_amount
        invoice.save()

    return invoice


def get_candidate_ledger_summary(candidate_profile):
    """
    Calculates the candidate's executive Kodafriq Earnings Ledger state:
    - AVAILABLE: Invoices settled by employer, queued for Friday payout run ($)
    - PENDING: Invoices issued/draft awaiting employer settlement ($)
    - PAID TO DATE: Historical completed disbursements sent to MoMo/Bank ($)
    - NEXT PAYOUT: Amount queued for upcoming Friday
    - DESTINATION: Verified Mobile Money or Bank details
    """
    invoices = ContractInvoice.objects.filter(contract__candidate=candidate_profile)

    # 1. Available (Settled by employer, queued for next payout run)
    available_qs = invoices.filter(
        payment_status=ContractInvoice.PaymentStatus.SETTLED,
        payout_status=ContractInvoice.PayoutStatus.QUEUED
    )
    available = available_qs.aggregate(models.Sum('talent_earnings'))['talent_earnings__sum'] or Decimal('0.00')

    # 2. Pending (Issued or in draft review, not yet settled by employer)
    pending_qs = invoices.filter(
        payout_status__in=[ContractInvoice.PayoutStatus.PENDING, ContractInvoice.PayoutStatus.PROCESSING]
    )
    pending = pending_qs.aggregate(models.Sum('talent_earnings'))['talent_earnings__sum'] or Decimal('0.00')

    # 3. Paid to date (Completed disbursements)
    paid_qs = invoices.filter(
        payout_status=ContractInvoice.PayoutStatus.COMPLETED
    )
    lifetime_paid = paid_qs.aggregate(models.Sum('talent_earnings'))['talent_earnings__sum'] or Decimal('0.00')

    # Next payout parameters
    next_payout_amount = available
    next_payout_date = get_next_payout_date()

    # Destination details
    payout_profile = getattr(candidate_profile, 'payout_profile', None)

    return {
        'available': available.quantize(Decimal('0.01')),
        'pending': pending.quantize(Decimal('0.01')),
        'lifetime_paid': lifetime_paid.quantize(Decimal('0.01')),
        'next_payout_amount': next_payout_amount.quantize(Decimal('0.01')),
        'next_payout_date': next_payout_date,
        'payout_profile': payout_profile,
        'has_destination': bool(payout_profile and payout_profile.is_configured),
        'destination_display': payout_profile.masked_destination if payout_profile else "No Payout Method Configured",
        'invoices': invoices.select_related('contract__employer', 'timesheet', 'milestone'),
    }
