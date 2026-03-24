# Generated migration for cancellation reasons

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('requests', '0007_alter_servicerequest_status'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CancellationReason',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('RIDER', 'Rider'), ('RODIE', 'Roadie')], max_length=10)),
                ('reason', models.CharField(max_length=100)),
                ('requires_custom_text', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ['role', 'order', 'reason'],
            },
        ),
        migrations.CreateModel(
            name='RequestCancellation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('custom_reason_text', models.TextField(blank=True, null=True)),
                ('cancelled_at', models.DateTimeField(auto_now_add=True)),
                ('distance_at_cancellation', models.DecimalField(blank=True, decimal_places=2, help_text='Distance between rider and roadie at time of cancellation (in km)', max_digits=8, null=True)),
                ('time_to_arrival_at_cancellation', models.PositiveIntegerField(blank=True, help_text='Estimated time to arrival at cancellation (in seconds)', null=True)),
                ('request', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='cancellation', to='requests.servicerequest')),
                ('cancelled_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cancellations_made', to='users.user')),
                ('reason', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cancellations', to='requests.cancellationreason')),
            ],
            options={
                'ordering': ['-cancelled_at'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='cancellationreason',
            unique_together={('role', 'reason')},
        ),
    ]
