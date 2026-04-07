from django.core.management.base import BaseCommand
from requests.models import CancellationReason

class Command(BaseCommand):
    help = 'Seed cancellation reasons for Riders and Roadies'

    def handle(self, *args, **options):
        # Rider Reasons
        rider_reasons = [
            ("Taking too long", False, 1),
            ("Not responding to call/message", False, 2),
            ("Mistaken request", False, 3),
            ("Got another helper", False, 4),
            ("Roadie requested cancellation", False, 5),
            ("Other", True, 6),
        ]

        # Roadie Reasons
        roadie_reasons = [
            ("Rider not responding to call/message", False, 1),
            ("Rider requested cancellation", False, 2),
            ("Got lost on the way", False, 3),
            ("Issue encountered along the way", False, 4),
            ("Other", True, 5),
        ]

        # Clear existing reasons to avoid duplicates/conflicts if necessary, 
        # or just update/create. Let's update/create.
        
        # Deactivating old ones might be safer than deleting if they are referenced
        # But for seed, we can just ensure these exist.
        
        # Resetting: Optional, but ensures the list is exactly as requested
        # CancellationReason.objects.all().delete() 

        for text, requires_custom, order in rider_reasons:
            obj, created = CancellationReason.objects.update_or_create(
                role='RIDER',
                reason=text,
                defaults={
                    'requires_custom_text': requires_custom,
                    'order': order,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created Rider reason: {text}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Updated Rider reason: {text}'))

        for text, requires_custom, order in roadie_reasons:
            obj, created = CancellationReason.objects.update_or_create(
                role='RODIE',
                reason=text,
                defaults={
                    'requires_custom_text': requires_custom,
                    'order': order,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created Roadie reason: {text}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Updated Roadie reason: {text}'))

        # Deactivate any reason not in the new lists
        all_new_rider_reasons = [r[0] for r in rider_reasons]
        all_new_roadie_reasons = [r[0] for r in roadie_reasons]
        
        CancellationReason.objects.filter(role='RIDER').exclude(reason__in=all_new_rider_reasons).update(is_active=False)
        CancellationReason.objects.filter(role='RODIE').exclude(reason__in=all_new_roadie_reasons).update(is_active=False)
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded cancellation reasons'))
