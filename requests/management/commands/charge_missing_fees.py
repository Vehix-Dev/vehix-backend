from django.core.management.base import BaseCommand
from requests.models import ServiceRequest

class Command(BaseCommand):
    help = 'Charge fees for existing completed ServiceRequest records that have not had fees charged yet.'

    def handle(self, *args, **options):
        qs = ServiceRequest.objects.filter(status='COMPLETED', fee_charged=False)
        total = qs.count()
        success = 0
        for req in qs:
            try:
                from requests.models import charge_fee_for_request
                ok = charge_fee_for_request(req)
                if ok:
                    success += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Failed charging request {req.id}: {e}'))
        self.stdout.write(self.style.SUCCESS(f'Processed {total} completed requests; charged {success} fees.'))
