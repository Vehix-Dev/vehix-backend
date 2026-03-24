from django.core.management.base import BaseCommand
from requests.models_cancellation import CancellationReason


class Command(BaseCommand):
    help = 'Create default cancellation reasons for riders and roadies'

    def handle(self, *args, **options):
        # Rider cancellation reasons
        rider_reasons = [
            ("Taking too long", False, 1),
            ("Not responding to call/message", False, 2),
            ("Mistaken request", False, 3),
            ("Got another helper", False, 4),
            ("Roadie requested cancellation", False, 5),
            ("Other", True, 6),
        ]

        # Roadie cancellation reasons
        roadie_reasons = [
            ("Rider not responding to call/message", False, 1),
            ("Rider requested cancellation", False, 2),
            ("Got lost on the way", False, 3),
            ("Issue encountered along the way", False, 4),
            ("Other", True, 5),
        ]

        # Create rider reasons
        for reason, requires_custom, order in rider_reasons:
            CancellationReason.objects.get_or_create(
                role='RIDER',
                reason=reason,
                defaults={
                    'requires_custom_text': requires_custom,
                    'order': order
                }
            )

        # Create roadie reasons
        for reason, requires_custom, order in roadie_reasons:
            CancellationReason.objects.get_or_create(
                role='RODIE',
                reason=reason,
                defaults={
                    'requires_custom_text': requires_custom,
                    'order': order
                }
            )

        self.stdout.write(
            self.style.SUCCESS('Successfully created default cancellation reasons')
        )
