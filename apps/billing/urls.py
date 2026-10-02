from django.urls import path
from . import views
from . import webhooks

app_name = 'billing'

urlpatterns = [
    # Candidate Earnings Ledger
    path('earnings/', views.CandidateEarningsLedgerView.as_view(), name='candidate_earnings'),
    path('ledger/', views.CandidateEarningsLedgerView.as_view(), name='candidate_ledger'),
    path('payout-settings/', views.CandidatePayoutSettingsView.as_view(), name='candidate_payout_settings'),

    # Employer Invoices
    path('invoices/', views.EmployerInvoiceListView.as_view(), name='invoice_list'),
    path('invoices/<uuid:pk>/', views.EmployerInvoiceDetailView.as_view(), name='invoice_detail'),
    path('invoices/<uuid:pk>/pay/', views.EmployerInvoicePayView.as_view(), name='invoice_pay'),
    path('invoices/<uuid:pk>/verify-payment/', views.InvoiceVerifyPaymentView.as_view(), name='invoice_verify_payment'),
    path('invoices/<uuid:pk>/pdf/', views.InvoicePDFDownloadView.as_view(), name='invoice_pdf'),
    path('earnings/statement/pdf/', views.CandidateStatementPDFView.as_view(), name='candidate_statement_pdf'),

    # Staff Executive Payment & Payout Command Center
    path('admin/payments/', views.StaffPaymentsOverviewView.as_view(), name='admin_payments_hub'),
    path('payments/', views.StaffPaymentsOverviewView.as_view(), name='payments_hub'),

    # Staff Operational Automation Engine
    path('automation/', views.StaffAutomationHubView.as_view(), name='automation_hub'),

    # Payment Gateway Webhooks
    path('webhooks/paystack/', webhooks.paystack_webhook, name='paystack_webhook'),
    path('webhooks/flutterwave/', webhooks.flutterwave_webhook, name='flutterwave_webhook'),
]
