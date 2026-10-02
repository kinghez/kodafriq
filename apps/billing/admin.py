from django import forms
from django.contrib import admin
from django.utils.html import format_html, mark_safe
from .models import (
    PlatformFeeConfig, PaymentGatewayConfig,
    CandidatePayoutProfile, ContractInvoice, PaymentTransaction,
    AutomationExecutionLog
)


class PaymentGatewayConfigForm(forms.ModelForm):
    class Meta:
        model = PaymentGatewayConfig
        fields = '__all__'
        widgets = {
            'paystack_secret_key': forms.PasswordInput(render_value=True, attrs={'style': 'width: 480px; font-family: monospace;'}),
            'paystack_public_key': forms.TextInput(attrs={'style': 'width: 480px; font-family: monospace;'}),
            'flutterwave_secret_key': forms.PasswordInput(render_value=True, attrs={'style': 'width: 480px; font-family: monospace;'}),
            'flutterwave_public_key': forms.TextInput(attrs={'style': 'width: 480px; font-family: monospace;'}),
            'flutterwave_encryption_key': forms.TextInput(attrs={'style': 'width: 480px; font-family: monospace;'}),
            'flutterwave_secret_hash': forms.TextInput(attrs={'style': 'width: 480px; font-family: monospace;'}),
        }


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    form = PaymentGatewayConfigForm
    list_display = (
        'status_badge',
        'paystack_badge',
        'flutterwave_badge',
        'paystack_key_preview',
        'flutterwave_key_preview',
        'updated_at'
    )
    readonly_fields = ('webhook_endpoints_guide', 'created_at', 'updated_at')

    fieldsets = (
        ("Configuration Status", {
            'fields': ('is_active',),
            'description': "Activate this configuration to route platform transactions through these API credentials."
        }),
        ("Paystack API Configuration (Ghana Mobile Money & Bank Rails)", {
            'fields': (
                'paystack_enabled',
                'paystack_mode',
                'paystack_public_key',
                'paystack_secret_key',
            ),
            'description': "Configure Paystack API keys to enable automated Mobile Money payouts (MTN, Telecel, AT Money) and GHS bank transfers. Keys are obtained from your Paystack Dashboard -> Settings -> API Keys & Webhooks."
        }),
        ("Flutterwave API Configuration (International Cards & Subaccounts)", {
            'fields': (
                'flutterwave_enabled',
                'flutterwave_mode',
                'flutterwave_public_key',
                'flutterwave_secret_key',
                'flutterwave_encryption_key',
                'flutterwave_secret_hash',
            ),
            'description': "Configure Flutterwave API keys to accept international employer debit/credit card payments (USD/GBP/EUR) and Option A Subaccount split payouts. Keys are obtained from Flutterwave Dashboard -> Settings -> API Keys."
        }),
        ("Webhook Integration Guide", {
            'fields': ('webhook_endpoints_guide',),
            'description': "Paste these URLs into your respective payment gateway dashboards so Kodafriq receives real-time transaction updates."
        }),
    )

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background: #059669; color: white; padding: 4px 10px; border-radius: 6px; font-weight: 800; font-size: 11px;">{}</span>',
                "ACTIVE"
            )
        return format_html(
            '<span style="background: #94a3b8; color: white; padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 11px;">{}</span>',
            "INACTIVE"
        )
    status_badge.short_description = "Status"

    def paystack_badge(self, obj):
        if not obj.paystack_enabled:
            return format_html('<span style="color: #94a3b8;">{}</span>', "Disabled")
        mode_color = "#0284c7" if obj.paystack_mode == 'TEST' else "#059669"
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 11px;">Paystack ({})</span>',
            mode_color,
            obj.paystack_mode
        )
    paystack_badge.short_description = "Paystack Rail"

    def flutterwave_badge(self, obj):
        if not obj.flutterwave_enabled:
            return format_html('<span style="color: #94a3b8;">{}</span>', "Disabled")
        mode_color = "#d97706" if obj.flutterwave_mode == 'TEST' else "#059669"
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 11px;">Flutterwave ({})</span>',
            mode_color,
            obj.flutterwave_mode
        )
    flutterwave_badge.short_description = "Flutterwave Rail"

    def paystack_key_preview(self, obj):
        pk = obj.paystack_public_key.strip()
        if not pk:
            return format_html('<span style="color: #94a3b8; font-style: italic;">{}</span>', "Using settings.py fallback")
        return format_html('<code style="font-size: 11px; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">{}...</code>', pk[:14])
    paystack_key_preview.short_description = "Paystack Public"

    def flutterwave_key_preview(self, obj):
        pk = obj.flutterwave_public_key.strip()
        if not pk:
            return format_html('<span style="color: #94a3b8; font-style: italic;">{}</span>', "Using settings.py fallback")
        return format_html('<code style="font-size: 11px; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">{}...</code>', pk[:14])
    flutterwave_key_preview.short_description = "Flutterwave Public"

    def webhook_endpoints_guide(self, obj):
        return mark_safe("""
        <div style="background: #0f172a; color: #f8fafc; padding: 18px 22px; border-radius: 10px; font-family: -apple-system, sans-serif; max-width: 720px; line-height: 1.6;">
            <div style="font-weight: 800; font-size: 13px; color: #38bdf8; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 0.05em;">
                Live Webhook Endpoints for Developer Portals
            </div>
            <div style="margin-bottom: 12px;">
                <strong style="color: #ffffff;">Paystack Webhook URL:</strong><br>
                <code style="background: #1e293b; color: #34d399; padding: 4px 10px; border-radius: 6px; font-family: monospace; display: inline-block; margin-top: 4px;">
                    https://&lt;your-domain&gt;/billing/webhooks/paystack/
                </code>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
                    Listens for <code>transfer.success</code> and <code>transfer.failed</code> events. Authenticated via HMAC SHA512.
                </div>
            </div>
            <div>
                <strong style="color: #ffffff;">Flutterwave Webhook URL:</strong><br>
                <code style="background: #1e293b; color: #fbbf24; padding: 4px 10px; border-radius: 6px; font-family: monospace; display: inline-block; margin-top: 4px;">
                    https://&lt;your-domain&gt;/billing/webhooks/flutterwave/
                </code>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">
                    Listens for <code>charge.completed</code> events. Authenticated via <strong>verif-hash</strong> header matching your configured Secret Hash.
                </div>
            </div>
        </div>
        """)
    webhook_endpoints_guide.short_description = "Webhook Integration Instructions"


@admin.register(PlatformFeeConfig)
class PlatformFeeConfigAdmin(admin.ModelAdmin):
    list_display = ('config_rule', 'fee_percent', 'gateway_processing_fee_percent', 'gateway_flat_fee', 'is_active', 'updated_at')
    list_display_links = ('config_rule',)

    def config_rule(self, obj):
        return f"Platform Fee ({obj.fee_percent}%)"
    config_rule.short_description = "Fee Rule" 
    list_editable = ('is_active',)


@admin.register(CandidatePayoutProfile)
class CandidatePayoutProfileAdmin(admin.ModelAdmin):
    list_display = ('candidate', 'payout_method', 'get_destination_display', 'is_verified', 'verified_at')
    list_filter = ('payout_method', 'is_verified', 'momo_network')
    search_fields = ('candidate__user__username', 'candidate__user__first_name', 'candidate__user__last_name', 'momo_phone_number', 'account_number')
    readonly_fields = ('created_at', 'updated_at')

    def get_destination_display(self, obj):
        return obj.masked_destination
    get_destination_display.short_description = "Disbursement Destination"


@admin.register(ContractInvoice)
class ContractInvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_ref', 'contract_link', 'talent_display', 'gross_amount', 'talent_earnings', 'kodafriq_fee', 'payment_status_badge', 'payout_status_badge', 'created_at')
    list_filter = ('payment_status', 'payout_status', 'gateway_provider', 'created_at')
    search_fields = ('invoice_ref', 'contract__contract_ref', 'contract__candidate__user__username', 'contract__employer__company_name', 'gateway_charge_ref', 'gateway_payout_ref')
    readonly_fields = ('invoice_ref', 'created_at', 'updated_at')

    def contract_link(self, obj):
        return obj.contract.contract_ref
    contract_link.short_description = "Contract Ref"

    def talent_display(self, obj):
        return obj.candidate.full_name
    talent_display.short_description = "Talent"

    def payment_status_badge(self, obj):
        colors = {
            'DRAFT': '#64748b',
            'ISSUED': '#d97706',
            'PROCESSING': '#0284c7',
            'SETTLED': '#059669',
            'FAILED': '#dc2626',
            'REFUNDED': '#475569',
        }
        color = colors.get(obj.payment_status, '#64748b')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 11px;">{}</span>',
            color,
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = "Employer Payment"

    def payout_status_badge(self, obj):
        colors = {
            'PENDING': '#64748b',
            'QUEUED': '#d97706',
            'PROCESSING': '#0284c7',
            'COMPLETED': '#059669',
            'FAILED': '#dc2626',
            'ON_HOLD': '#b45309',
        }
        color = colors.get(obj.payout_status, '#64748b')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 11px;">{}</span>',
            color,
            obj.get_payout_status_display()
        )
    payout_status_badge.short_description = "Talent Payout"


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('reference', 'transaction_type', 'gateway', 'amount', 'currency', 'status', 'created_at')
    list_filter = ('transaction_type', 'gateway', 'status', 'created_at')
    search_fields = ('reference', 'invoice__invoice_ref', 'error_message')
    readonly_fields = ('created_at',)


@admin.register(AutomationExecutionLog)
class AutomationExecutionLogAdmin(admin.ModelAdmin):
    list_display = ('task_type_display', 'executed_at', 'dry_run_badge', 'status_badge', 'items_processed', 'total_amount', 'executed_by')
    list_filter = ('task_type', 'is_dry_run', 'status', 'executed_at')
    search_fields = ('summary_message', 'details_json')
    readonly_fields = ('executed_at',)

    def task_type_display(self, obj):
        return obj.get_task_type_display()
    task_type_display.short_description = "Job Engine"

    def dry_run_badge(self, obj):
        if obj.is_dry_run:
            return mark_safe('<span style="background: #f59e0b; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700;">DRY-RUN</span>')
        return mark_safe('<span style="background: #10b981; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: 700;">LIVE</span>')
    dry_run_badge.short_description = "Execution Mode"

    def status_badge(self, obj):
        colors = {
            'SUCCESS': '#059669',
            'PARTIAL': '#d97706',
            'FAILED': '#dc2626',
        }
        color = colors.get(obj.status, '#64748b')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"
