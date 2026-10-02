import uuid
import random
from decimal import Decimal
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from apps.accounts.models import CandidateProfile, EmployerProfile
from apps.contracts.models import Contract, Timesheet, Milestone


class PlatformFeeConfig(models.Model):
    """
    Admin-configurable monetization parameters (10% platform markup, pass-through gateway fees).
    """
    fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        help_text="Kodafriq platform service markup percentage charged to employer (default 10.00%)"
    )
    gateway_processing_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.90'),
        help_text="Payment gateway interchange pass-through fee (default 2.90%)"
    )
    gateway_flat_fee = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.30'),
        help_text="Gateway flat fee per charge ($0.30)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform Fee Configuration"
        verbose_name_plural = "Platform Fee Configurations"

    @classmethod
    def get_active(cls):
        cfg = cls.objects.filter(is_active=True).first()
        if not cfg:
            cfg = cls.objects.create(
                fee_percent=Decimal('10.00'),
                gateway_processing_fee_percent=Decimal('2.90'),
                gateway_flat_fee=Decimal('0.30'),
                is_active=True
            )
        return cfg

    def __str__(self):
        return f"Fee Config: {self.fee_percent}% Platform Markup (Active: {self.is_active})"


class PaymentGatewayConfig(models.Model):
    """
    Central administrative configuration for Paystack and Flutterwave API credentials,
    webhook secrets, and execution environments (Test vs. Live).
    Allows Staff/Superusers to insert and manage live or test API keys directly via Django Admin.
    """
    class Mode(models.TextChoices):
        TEST = 'TEST', 'Test / Sandbox Mode'
        LIVE = 'LIVE', 'Live / Production Mode'

    # Paystack API Settings (Ghana Mobile Money & Bank Disbursements)
    paystack_enabled = models.BooleanField(
        default=True,
        verbose_name="Paystack Enabled",
        help_text="Enable/disable Paystack for candidate Mobile Money disbursements."
    )
    paystack_mode = models.CharField(
        max_length=10,
        choices=Mode.choices,
        default=Mode.TEST,
        verbose_name="Paystack Environment",
        help_text="Operating mode: Test/Sandbox or Live/Production."
    )
    paystack_public_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Paystack Public Key",
        help_text="Public API key from Paystack Dashboard (e.g. pk_test_... or pk_live_...)."
    )
    paystack_secret_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Paystack Secret Key",
        help_text="Secret API key from Paystack Dashboard (e.g. sk_test_... or sk_live_...). Used for authenticating transfer requests & HMAC webhook verification."
    )

    # Flutterwave API Settings (Employer Card Billing & International Transfers)
    flutterwave_enabled = models.BooleanField(
        default=True,
        verbose_name="Flutterwave Enabled",
        help_text="Enable/disable Flutterwave for employer card payments and settlements."
    )
    flutterwave_mode = models.CharField(
        max_length=10,
        choices=Mode.choices,
        default=Mode.TEST,
        verbose_name="Flutterwave Environment",
        help_text="Operating mode: Test/Sandbox or Live/Production."
    )
    flutterwave_public_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Flutterwave Public Key",
        help_text="Public API key from Flutterwave Dashboard (e.g. FLWPUBK_TEST-... or FLWPUBK-...)."
    )
    flutterwave_secret_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Flutterwave Secret Key",
        help_text="Secret API key from Flutterwave Dashboard (e.g. FLWSECK_TEST-... or FLWSECK-...)."
    )
    flutterwave_encryption_key = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Flutterwave Encryption Key",
        help_text="Optional encryption key from Flutterwave Dashboard for card tokenization."
    )
    flutterwave_secret_hash = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name="Flutterwave Webhook Secret Hash",
        help_text="Secret hash entered in Flutterwave Dashboard settings to authenticate inbound webhooks via 'verif-hash' header."
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Active Configuration",
        help_text="Only one configuration can be active at a time."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment Gateway API Configuration"
        verbose_name_plural = "Payment Gateway API Configurations"

    @classmethod
    def get_active(cls):
        cfg = cls.objects.filter(is_active=True).first()
        if not cfg:
            cfg = cls.objects.create(
                paystack_mode=cls.Mode.TEST,
                flutterwave_mode=cls.Mode.TEST,
                is_active=True
            )
        return cfg

    def get_paystack_secret_key(self):
        val = self.paystack_secret_key.strip() if self.paystack_secret_key else ''
        return val or getattr(settings, 'PAYSTACK_SECRET_KEY', 'sk_test_mock_kodafriq_key')

    def get_paystack_public_key(self):
        val = self.paystack_public_key.strip() if self.paystack_public_key else ''
        return val or getattr(settings, 'PAYSTACK_PUBLIC_KEY', 'pk_test_mock_kodafriq_key')

    def get_flutterwave_secret_key(self):
        val = self.flutterwave_secret_key.strip() if self.flutterwave_secret_key else ''
        return val or getattr(settings, 'FLUTTERWAVE_SECRET_KEY', 'FLWSECK_TEST_mock_kodafriq_key')

    def get_flutterwave_public_key(self):
        val = self.flutterwave_public_key.strip() if self.flutterwave_public_key else ''
        return val or getattr(settings, 'FLUTTERWAVE_PUBLIC_KEY', 'FLWPUBK_TEST_mock_kodafriq_key')

    def get_flutterwave_secret_hash(self):
        val = self.flutterwave_secret_hash.strip() if self.flutterwave_secret_hash else ''
        return val or getattr(settings, 'FLUTTERWAVE_SECRET_HASH', 'kodafriq_webhook_hash')

    def save(self, *args, **kwargs):
        if self.is_active:
            PaymentGatewayConfig.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"Payment Gateways [{self.get_paystack_mode_display()} / {self.get_flutterwave_mode_display()}] ({status})"


class CandidatePayoutProfile(models.Model):
    """
    Healthcare Professional verified payout destination.
    Supports Paystack Ghana MoMo (GHS) and Flutterwave Direct Pan-African Bank Transfer.
    """
    class PayoutMethod(models.TextChoices):
        PAYSTACK_MOMO = 'PAYSTACK_MOMO', 'Paystack Mobile Money (Ghana GHS)'
        FLUTTERWAVE_BANK = 'FLUTTERWAVE_BANK', 'Flutterwave Bank Transfer (Pan-Africa)'

    class MoMoNetwork(models.TextChoices):
        MTN = 'MTN', 'MTN Mobile Money'
        TELECEL = 'TELECEL', 'Telecel Cash (Vodafone)'
        AT_MONEY = 'AT_MONEY', 'AT Money (AirtelTigo)'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.OneToOneField(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name='payout_profile'
    )
    payout_method = models.CharField(
        max_length=30,
        choices=PayoutMethod.choices,
        default=PayoutMethod.PAYSTACK_MOMO
    )

    # Mobile Money Fields (Paystack Ghana)
    momo_network = models.CharField(
        max_length=20,
        choices=MoMoNetwork.choices,
        default=MoMoNetwork.MTN,
        blank=True
    )
    momo_phone_number = models.CharField(
        max_length=24,
        blank=True,
        help_text="e.g., +233241234567 or 0241234567"
    )
    momo_account_name = models.CharField(
        max_length=120,
        blank=True,
        help_text="Verified name as registered on Mobile Money account"
    )

    # Bank Account Fields (Flutterwave Pan-Africa)
    bank_name = models.CharField(max_length=120, blank=True)
    bank_code = models.CharField(max_length=50, blank=True, help_text="Sort code or routing code")
    account_number = models.CharField(max_length=50, blank=True)
    account_name = models.CharField(max_length=120, blank=True)
    bank_country = models.CharField(max_length=50, default="Ghana", blank=True)
    currency = models.CharField(max_length=10, default='GHS')

    # Gateway specific tokenization
    paystack_recipient_code = models.CharField(
        max_length=100,
        blank=True,
        help_text="Paystack Transfer Recipient Code (e.g. RCP_xxxx)"
    )
    flutterwave_subaccount_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Flutterwave Subaccount ID for split settlement"
    )

    # Verification status
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Candidate Payout Profile"
        verbose_name_plural = "Candidate Payout Profiles"

    @property
    def is_configured(self):
        if self.payout_method == self.PayoutMethod.PAYSTACK_MOMO:
            return bool(self.momo_phone_number and self.momo_account_name)
        elif self.payout_method == self.PayoutMethod.FLUTTERWAVE_BANK:
            return bool(self.bank_name and self.account_number and self.account_name)
        return False

    @property
    def masked_destination(self):
        """Executive summary display: e.g. MTN Mobile Money (+233 24 ••• ••45)"""
        if self.payout_method == self.PayoutMethod.PAYSTACK_MOMO:
            num = self.momo_phone_number.strip()
            if len(num) >= 6:
                masked = num[:4] + " ••• ••" + num[-2:]
            else:
                masked = num
            return f"{self.get_momo_network_display()} ({masked})"
        elif self.payout_method == self.PayoutMethod.FLUTTERWAVE_BANK:
            acc = self.account_number.strip()
            masked = f"•••• {acc[-4:]}" if len(acc) >= 4 else acc
            return f"{self.bank_name} ({masked})"
        return "Not Configured"

    def __str__(self):
        return f"{self.candidate.full_name} - {self.masked_destination}"


class ContractInvoice(models.Model):
    """
    The Business State Record for the Non-Custodial Earnings Ledger.
    Tracks candidate net earnings, Kodafriq 10% platform markup, pass-through gateway fees,
    employer settlement status, and candidate disbursement status.
    """
    class PaymentStatus(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft (Review Window)'
        ISSUED = 'ISSUED', 'Issued / Pending Charge'
        PROCESSING = 'PROCESSING', 'Processing Gateway Charge'
        SETTLED = 'SETTLED', 'Settled / Paid by Employer'
        FAILED = 'FAILED', 'Payment Failed'
        REFUNDED = 'REFUNDED', 'Refunded'

    class PayoutStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Employer Settlement'
        QUEUED = 'QUEUED', 'Queued for Upcoming Payout Run (Friday)'
        PROCESSING = 'PROCESSING', 'Processing Disbursement Transfer'
        COMPLETED = 'COMPLETED', 'Disbursed / Completed'
        FAILED = 'FAILED', 'Payout Failed'
        ON_HOLD = 'ON_HOLD', 'On Hold / Disputed'

    class GatewayProvider(models.TextChoices):
        NONE = 'NONE', 'None / Manual'
        FLUTTERWAVE = 'FLUTTERWAVE', 'Flutterwave'
        PAYSTACK = 'PAYSTACK', 'Paystack Ghana'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_ref = models.CharField(max_length=32, unique=True, editable=False)

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name='invoices')
    timesheet = models.OneToOneField(Timesheet, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice')
    milestone = models.OneToOneField(Milestone, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice')

    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    currency = models.CharField(max_length=10, default='USD')

    # Core Financial Breakdown
    talent_earnings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Guaranteed net compensation disbursed to candidate ($)"
    )
    kodafriq_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="10% Kodafriq platform service revenue ($)"
    )
    processing_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Payment gateway pass-through interchange fee ($)"
    )
    gross_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total employer billed amount ($)"
    )

    # Status Engines
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.DRAFT
    )
    payout_status = models.CharField(
        max_length=20,
        choices=PayoutStatus.choices,
        default=PayoutStatus.PENDING
    )

    # Gateway Tracking & Reconciliation
    gateway_provider = models.CharField(
        max_length=20,
        choices=GatewayProvider.choices,
        default=GatewayProvider.NONE
    )
    gateway_charge_ref = models.CharField(max_length=120, blank=True, help_text="e.g. flw_tx_849204128")
    gateway_payout_ref = models.CharField(max_length=120, blank=True, help_text="e.g. pstk_trf_9921045")

    due_date = models.DateField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.invoice_ref:
            rand_suffix = random.randint(1000, 9999)
            year = timezone.now().year
            self.invoice_ref = f"INV-{year}-{rand_suffix}"
            while ContractInvoice.objects.filter(invoice_ref=self.invoice_ref).exclude(pk=self.pk).exists():
                rand_suffix = random.randint(1000, 9999)
                self.invoice_ref = f"INV-{year}-{rand_suffix}"
        super().save(*args, **kwargs)

    @property
    def candidate(self):
        return self.contract.candidate

    @property
    def employer(self):
        return self.contract.employer

    def mark_settled(self, gateway_charge_ref="", gateway_provider=GatewayProvider.FLUTTERWAVE):
        """
        Transition invoice to SETTLED upon successful employer payment.
        Automatically queues candidate earnings for next scheduled payout run.
        """
        self.payment_status = self.PaymentStatus.SETTLED
        self.payout_status = self.PayoutStatus.QUEUED
        self.settled_at = timezone.now()
        self.gateway_provider = gateway_provider
        if gateway_charge_ref:
            self.gateway_charge_ref = gateway_charge_ref
        self.save()

        # Update timesheet status if associated
        if self.timesheet and self.timesheet.status != Timesheet.Status.PAID:
            self.timesheet.status = Timesheet.Status.PAID
            self.timesheet.save(update_fields=['status'])

        # Update milestone status if associated
        if self.milestone and self.milestone.status != Milestone.Status.PAID:
            self.milestone.status = Milestone.Status.PAID
            self.milestone.save(update_fields=['status'])

    def mark_disbursed(self, gateway_payout_ref=""):
        """
        Transition invoice to COMPLETED upon successful disbursement to talent.
        """
        self.payout_status = self.PayoutStatus.COMPLETED
        self.disbursed_at = timezone.now()
        if gateway_payout_ref:
            self.gateway_payout_ref = gateway_payout_ref
        self.save()

    def __str__(self):
        return f"{self.invoice_ref} ({self.contract.contract_ref}): Gross ${self.gross_amount} [{self.get_payment_status_display()}]"


class PaymentTransaction(models.Model):
    """
    Immutable audit trail of all gateway webhooks, employer card charges, and talent disbursements.
    """
    class TransactionType(models.TextChoices):
        CHARGE = 'CHARGE', 'Employer Card Debit'
        PAYOUT = 'PAYOUT', 'Candidate Disbursement Transfer'
        REFUND = 'REFUND', 'Employer Refund'

    class Gateway(models.TextChoices):
        PAYSTACK = 'PAYSTACK', 'Paystack Ghana'
        FLUTTERWAVE = 'FLUTTERWAVE', 'Flutterwave'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        ContractInvoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    gateway = models.CharField(max_length=20, choices=Gateway.choices)
    reference = models.CharField(max_length=120, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='USD')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    raw_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    ip_address = models.CharField(max_length=45, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.gateway} {self.transaction_type}: {self.reference} (${self.amount} {self.status})"


class AutomationExecutionLog(models.Model):
    """
    Audit log of automated scheduled jobs:
    - Weekly Timesheet Lock (Sunday 23:59)
    - Friday Batch Payout Disbursement (Friday 09:00)
    Captures run metadata, execution status, amounts processed, and error/success summaries.
    """
    class TaskType(models.TextChoices):
        TIMESHEET_LOCK = 'TIMESHEET_LOCK', 'Weekly Timesheet Lock (Sunday 23:59)'
        FRIDAY_PAYOUT = 'FRIDAY_PAYOUT', 'Friday Batch Payout (Friday 09:00)'

    class Status(models.TextChoices):
        SUCCESS = 'SUCCESS', 'Success'
        PARTIAL = 'PARTIAL', 'Partial Success / Warnings'
        FAILED = 'FAILED', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_type = models.CharField(max_length=30, choices=TaskType.choices)
    executed_at = models.DateTimeField(default=timezone.now)
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='automation_runs',
        help_text="Null for automated cron triggers, user for manual staff runs."
    )
    is_dry_run = models.BooleanField(default=False)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUCCESS)

    items_evaluated = models.PositiveIntegerField(default=0)
    items_processed = models.PositiveIntegerField(default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    summary_message = models.TextField(blank=True)
    details_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-executed_at']
        verbose_name = "Automation Execution Log"
        verbose_name_plural = "Automation Execution Logs"

    def __str__(self):
        mode = " [DRY-RUN]" if self.is_dry_run else ""
        return f"{self.get_task_type_display()}{mode} - {self.executed_at.strftime('%Y-%m-%d %H:%M')} ({self.get_status_display()})"
