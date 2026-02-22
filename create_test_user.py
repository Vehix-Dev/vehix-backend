import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

username = 'testrider'
phone = '+256700000000'
password = 'testpassword123'

if not User.objects.filter(username=username).exists():
    User.objects.create_user(username=username, phone=phone, password=password, role='RIDER')
    print(f"Created user {username} with phone {phone}")
else:
    u = User.objects.get(username=username)
    u.set_password(password)
    u.phone = phone
    u.save()
    print(f"Updated user {username} with phone {phone}")
