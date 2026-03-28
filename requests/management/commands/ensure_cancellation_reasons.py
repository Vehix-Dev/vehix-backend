from django.core.management.base import BaseCommand
from requests.models import CancellationReason

class Command(BaseCommand):
    help = 'Ensures basic cancellation reasons exist in the database'

    def handle(self, *args, **options):
        # Specific user-requested Rider reasons
        rider_reasons = [
            ('RIDER', 'Taking too long'),
            ('RIDER', 'Not responding to call/message'),
            ('RIDER', 'Mistaken request'),
            ('RIDER', 'Got another helper'),
            ('RIDER', 'Roadie requested cancellation'),
            ('RIDER', 'Other', True), # requires custom text
        ]

        # Standard Roadie reasons
        rodie_reasons = [
            ('RODIE', 'Traffic issues'),
            ('RODIE', 'Vehicle problems'),
            ('RODIE', 'Rider requested cancellation'),
            ('RODIE', 'Other', True), # requires custom text
        ]

        all_reasons = rider_reasons + rodie_reasons
        
        created_count = 0
        for i, reason_data in enumerate(all_reasons):
            role = reason_data[0]
            reason_text = reason_data[1]
            requires_custom = reason_data[2] if len(reason_data) > 2 else False
            
            reason, created = CancellationReason.objects.update_or_create(
                role=role,
                reason=reason_text,
                defaults={
                    'requires_custom_text': requires_custom,
                    'order': i,
                    'is_active': True
                }
            )
            if created:
                created_count += 1
        
        self.stdout.write(self.style.SUCCESS(f'Successfully ensured {len(all_reasons)} cancellation reasons ({created_count} new)'))
