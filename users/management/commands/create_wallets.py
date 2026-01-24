from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from users.models import Wallet

User = get_user_model()


class Command(BaseCommand):
    help = 'Create Wallet entries for all users missing one.'

    def handle(self, *args, **options):
        users = User.objects.all()
        created = 0
        for u in users:
            w, was_created = Wallet.objects.get_or_create(user=u)
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Ensured wallets for {users.count()} users; created {created} new wallets.'))
