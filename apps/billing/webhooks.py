import json
import logging
from decimal import Decimal
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import ContractInvoice, PaymentTransaction
from .services.paystack_ghana import PaystackGhanaService
from .services.flutterwave import FlutterwaveService

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def paystack_webhook(request):
    """
    Paystack Webhook Listener.
    Receives automated notifications for GHS disbursements to candidate Mobile Money wallets.
    Signature validated via HMAC SHA512.
    """
    signature = request.headers.get('x-paystack-signature', '')
    service = PaystackGhanaService()

    if not service.verify_webhook_signature(request.body, signature):
        logger.warning("Invalid Paystack webhook signature rejected.")
        return HttpResponse(status=401)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception as e:
        logger.error(f"Error parsing Paystack webhook JSON: {e}")
        return HttpResponse(status=400)

    event = payload.get('event')
    data = payload.get('data', {})
    reference = data.get('reference') or data.get('transfer_code') or f"pstk_{timezone.now().timestamp()}"

    # Log incoming audit trail transaction
    amount_kobo = data.get('amount', 0)
    amount = Decimal(str(amount_kobo)) / Decimal('100.00')

    # Find associated invoice by gateway_payout_ref or reference in notes
    invoice = ContractInvoice.objects.filter(gateway_payout_ref=reference).first()

    status = PaymentTransaction.Status.SUCCESS if event == 'transfer.success' else PaymentTransaction.Status.PENDING
    if event == 'transfer.failed' or event == 'transfer.reversed':
        status = PaymentTransaction.Status.FAILED

    PaymentTransaction.objects.create(
        invoice=invoice,
        transaction_type=PaymentTransaction.TransactionType.PAYOUT,
        gateway=PaymentTransaction.Gateway.PAYSTACK,
        reference=reference,
        amount=amount,
        currency="GHS",
        status=status,
        raw_payload=payload,
        ip_address=request.META.get('REMOTE_ADDR', '')
    )

    if invoice:
        if event == 'transfer.success':
            invoice.mark_disbursed(gateway_payout_ref=reference)
            logger.info(f"Invoice {invoice.invoice_ref} payout marked COMPLETED via Paystack.")
        elif event in ['transfer.failed', 'transfer.reversed']:
            invoice.payout_status = ContractInvoice.PayoutStatus.FAILED
            invoice.save(update_fields=['payout_status'])
            logger.warning(f"Invoice {invoice.invoice_ref} payout FAILED via Paystack.")

    return HttpResponse(status=200)


@csrf_exempt
@require_POST
def flutterwave_webhook(request):
    """
    Flutterwave Webhook Listener.
    Receives automated notifications for employer card debits (USD/GBP) and Option A split settlements.
    Validated via secret hash.
    """
    signature = request.headers.get('verif-hash', '')
    service = FlutterwaveService()

    if not service.verify_webhook_hash(signature):
        logger.warning("Invalid Flutterwave webhook hash rejected.")
        return HttpResponse(status=401)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception as e:
        logger.error(f"Error parsing Flutterwave webhook JSON: {e}")
        return HttpResponse(status=400)

    event = payload.get('event') or payload.get('event.type')
    data = payload.get('data', {})
    tx_ref = data.get('tx_ref', '')
    flw_ref = data.get('flw_ref', '') or f"flw_{data.get('id', '')}"
    amount = Decimal(str(data.get('amount', 0)))
    currency = data.get('currency', 'USD')
    charge_status = data.get('status', '').lower()

    # Try locating invoice by tx_ref prefix (which contains invoice_ref)
    invoice = None
    if tx_ref:
        inv_ref_part = tx_ref.split('_')[0]
        invoice = ContractInvoice.objects.filter(invoice_ref=inv_ref_part).first()

    status = PaymentTransaction.Status.SUCCESS if charge_status == 'successful' else PaymentTransaction.Status.PENDING
    if charge_status == 'failed':
        status = PaymentTransaction.Status.FAILED

    PaymentTransaction.objects.create(
        invoice=invoice,
        transaction_type=PaymentTransaction.TransactionType.CHARGE,
        gateway=PaymentTransaction.Gateway.FLUTTERWAVE,
        reference=flw_ref or tx_ref,
        amount=amount,
        currency=currency,
        status=status,
        raw_payload=payload,
        ip_address=request.META.get('REMOTE_ADDR', '')
    )

    if invoice and charge_status == 'successful':
        invoice.mark_settled(
            gateway_charge_ref=flw_ref or tx_ref,
            gateway_provider=ContractInvoice.GatewayProvider.FLUTTERWAVE
        )
        logger.info(f"Invoice {invoice.invoice_ref} marked SETTLED via Flutterwave charge.")

    return HttpResponse(status=200)
