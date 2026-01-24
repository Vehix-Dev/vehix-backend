from django.core.management.base import BaseCommand
from requests.models import ServiceRequest
from users.models import WalletTransaction

class Command(BaseCommand):
    help = 'Reconcile ServiceRequests: ensure completed requests have fee transactions and wallets debited.'

    def handle(self, *args, **options):
        qs = ServiceRequest.objects.filter(status='COMPLETED')
        total = qs.count()
        created = 0
        fixed_flags = 0
        for req in qs:
            try:
                if not req.rodie:
                    continue
                reason = f'service fee for request {req.id}'
                tx_exists = WalletTransaction.objects.filter(reason=reason, wallet__user=req.rodie).exists()
                if tx_exists:
                    if not req.fee_charged:
                        req.fee_charged = True
                        req.save(update_fields=['fee_charged'])
                        fixed_flags += 1
                    continue
                # create charge
                from requests.models import charge_fee_for_request
                ok = charge_fee_for_request(req)
                if ok:
                    created += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Failed for request {req.id}: {e}'))
        self.stdout.write(self.style.SUCCESS(f'Total completed requests: {total}. Created transactions: {created}. Set fee_charged flags: {fixed_flags}'))
