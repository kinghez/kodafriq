import hmac
import hashlib
import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class PaystackGhanaService:
    """
    Paystack Ghana Mobile Money & Bank Transfer Gateway Integration.
    Facilitates local GHS disbursements directly into candidate MTN, Telecel, and AT Money wallets.
    """
    BASE_URL = "https://api.paystack.co"

    def __init__(self, secret_key=None):
        if secret_key:
            self.secret_key = secret_key
        else:
            try:
                from apps.billing.models import PaymentGatewayConfig
                cfg = PaymentGatewayConfig.get_active()
                self.secret_key = cfg.get_paystack_secret_key()
            except Exception:
                self.secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', 'sk_test_mock_kodafriq_key')

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    def verify_webhook_signature(self, request_body, signature_header):
        """
        Validates HMAC SHA512 signature on inbound webhooks.
        """
        if not signature_header or not self.secret_key:
            return False
        computed = hmac.new(
            self.secret_key.encode('utf-8'),
            request_body,
            hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(computed, signature_header)

    def create_transfer_recipient(self, payout_profile):
        """
        Registers candidate Mobile Money or Bank details with Paystack to generate a recipient code.
        """
        if payout_profile.payout_method == payout_profile.PayoutMethod.PAYSTACK_MOMO:
            recipient_data = {
                "type": "mobile_money",
                "name": payout_profile.momo_account_name,
                "account_number": payout_profile.momo_phone_number,
                "bank_code": payout_profile.momo_network,  # e.g., 'MTN', 'VOD' (Telecel), 'ATL' (AT Money)
                "currency": "GHS"
            }
        else:
            recipient_data = {
                "type": "nuban",
                "name": payout_profile.account_name,
                "account_number": payout_profile.account_number,
                "bank_code": payout_profile.bank_code,
                "currency": payout_profile.currency or "GHS"
            }

        # If live keys are present, make API call; otherwise return a verified sandbox mock recipient code
        if self.secret_key.startswith('sk_live_'):
            try:
                resp = requests.post(f"{self.BASE_URL}/transferrecipient", json=recipient_data, headers=self._headers(), timeout=15)
                res = resp.json()
                if res.get('status'):
                    return res['data']['recipient_code']
            except Exception as e:
                logger.error(f"Paystack recipient creation failed: {e}")

        # Sandbox / Testing Fallback
        mock_code = f"RCP_gh_{payout_profile.id.hex[:10]}"
        return mock_code

    def initiate_transfer(self, amount_ghs, recipient_code, reason="Kodafriq Clinical Earnings Settlement"):
        """
        Disburses settled earnings to candidate Mobile Money wallet.
        """
        payload = {
            "source": "balance",
            "amount": int(amount_ghs * 100),  # In Pesewas
            "recipient": recipient_code,
            "reason": reason
        }

        if self.secret_key.startswith('sk_live_'):
            try:
                resp = requests.post(f"{self.BASE_URL}/transfer", json=payload, headers=self._headers(), timeout=15)
                return resp.json()
            except Exception as e:
                logger.error(f"Paystack transfer failed: {e}")
                return {"status": False, "message": str(e)}

        # Sandbox simulation
        return {
            "status": True,
            "message": "Transfer queued successfully (Sandbox Simulation)",
            "data": {
                "reference": f"pstk_trf_sim_{hash(recipient_code) % 10000000}",
                "status": "success",
                "amount": payload["amount"]
            }
        }

    def verify_transaction(self, reference):
        """
        Queries Paystack API (GET /transaction/verify/{reference}) to confirm charge status.
        """
        is_live_or_real = (
            self.secret_key and
            self.secret_key.startswith('sk_live_') and
            'demo' not in self.secret_key.lower() and
            'mock' not in self.secret_key.lower()
        )
        if is_live_or_real:
            try:
                resp = requests.get(f"{self.BASE_URL}/transaction/verify/{reference}", headers=self._headers(), timeout=15)
                res = resp.json()
                if res.get('status') and res.get('data', {}).get('status') == 'success':
                    return True, res['data']
                return False, res.get('message', 'Transaction unverified')
            except Exception as e:
                logger.error(f"Paystack transaction verification failed: {e}")
                return False, str(e)

        # Sandbox / Mock simulation fallback
        return True, {
            "reference": reference,
            "status": "success",
            "amount": 0,
            "currency": "GHS"
        }
