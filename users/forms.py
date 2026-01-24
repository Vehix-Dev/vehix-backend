from django import forms

class STKPushDepositForm(forms.Form):
    phone_number = forms.CharField(max_length=15, help_text="Enter phone number to receive the PIN prompt (e.g., 254712345678)")
    amount = forms.DecimalField(max_digits=10, decimal_places=2, help_text="Amount to deposit")
    description = forms.CharField(max_length=255, required=False, initial="Admin Wallet Deposit")
