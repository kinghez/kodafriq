from django import forms
from .models import CandidatePayoutProfile, ContractInvoice


class CandidatePayoutProfileForm(forms.ModelForm):
    class Meta:
        model = CandidatePayoutProfile
        fields = [
            'payout_method', 'momo_network', 'momo_phone_number', 'momo_account_name',
            'bank_name', 'bank_code', 'account_number', 'account_name', 'bank_country', 'currency'
        ]
        widgets = {
            'payout_method': forms.Select(attrs={'class': 'kf-input', 'id': 'id_payout_method'}),
            'momo_network': forms.Select(attrs={'class': 'kf-input', 'id': 'id_momo_network'}),
            'momo_phone_number': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. +233 24 123 4567'}),
            'momo_account_name': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'Full Name as on MoMo'}),
            'bank_name': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Ecobank Ghana / GTBank'}),
            'bank_code': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'Routing / Sort Code (optional)'}),
            'account_number': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'Bank Account Number'}),
            'account_name': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'Account Holder Name'}),
            'bank_country': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'e.g. Ghana, Nigeria, Kenya'}),
            'currency': forms.TextInput(attrs={'class': 'kf-input', 'placeholder': 'GHS / NGN / KES / USD'}),
        }

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get('payout_method')
        if method == CandidatePayoutProfile.PayoutMethod.PAYSTACK_MOMO:
            if not cleaned.get('momo_phone_number'):
                self.add_error('momo_phone_number', 'Mobile Money phone number is required.')
            if not cleaned.get('momo_account_name'):
                self.add_error('momo_account_name', 'Mobile Money registered account name is required.')
        elif method == CandidatePayoutProfile.PayoutMethod.FLUTTERWAVE_BANK:
            if not cleaned.get('bank_name'):
                self.add_error('bank_name', 'Bank name is required.')
            if not cleaned.get('account_number'):
                self.add_error('account_number', 'Account number is required.')
            if not cleaned.get('account_name'):
                self.add_error('account_name', 'Account name is required.')
        return cleaned


class InvoicePayForm(forms.Form):
    payment_method = forms.ChoiceField(
        choices=[
            ('CARD', 'Credit / Debit Card (Visa, Mastercard, Amex)'),
            ('DIRECT_DEBIT', 'Corporate ACH / Direct Debit'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'kf-radio'})
    )
    confirm_authorization = forms.BooleanField(
        required=True,
        label="I authorize Kodafriq to charge my payment method for this approved clinical engagement invoice."
    )
