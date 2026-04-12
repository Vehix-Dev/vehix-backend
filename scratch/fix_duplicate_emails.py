import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db.models import Count

User = get_user_model()

def find_and_fix_duplicates():
    duplicates = User.objects.values('email').annotate(email_count=Count('id')).filter(email_count__gt=1)
    
    if not duplicates:
        print("No duplicate emails found.")
        return

    print(f"Found {len(duplicates)} duplicate email groups.")
    
    for dup in duplicates:
        email = dup['email']
        users = list(User.objects.filter(email=email).order_by('id'))
        print(f"Duplicates for {email}: {[u.id for u in users]}")
        
        # Keep the first user, modify the others
        for i, user in enumerate(users[1:], start=1):
            new_email = f"duplicate_{i}_{user.email}"
            print(f"  Modifying user {user.id}: {user.email} -> {new_email}")
            user.email = new_email
            user.save()

if __name__ == "__main__":
    find_and_fix_duplicates()
