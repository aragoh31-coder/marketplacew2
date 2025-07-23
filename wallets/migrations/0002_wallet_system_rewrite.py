
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('wallets', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('login', 'Login'), ('logout', 'Logout'), ('withdrawal_request', 'Withdrawal Request'), ('withdrawal_approved', 'Withdrawal Approved'), ('withdrawal_rejected', 'Withdrawal Rejected'), ('withdrawal_cancelled', 'Withdrawal Cancelled'), ('conversion', 'Currency Conversion'), ('settings_change', 'Settings Change'), ('security_alert', 'Security Alert'), ('admin_action', 'Admin Action')], max_length=50)),
                ('ip_address', models.GenericIPAddressField()),
                ('user_agent', models.TextField()),
                ('details', models.JSONField(default=dict)),
                ('risk_score', models.IntegerField(default=0)),
                ('flagged', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ConversionRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_currency', models.CharField(max_length=3)),
                ('to_currency', models.CharField(max_length=3)),
                ('rate', models.DecimalField(decimal_places=12, max_digits=20)),
                ('source', models.CharField(default='manual', max_length=50)),
                ('source_data', models.JSONField(blank=True, default=dict)),
                ('valid_from', models.DateTimeField(default=django.utils.timezone.now)),
                ('valid_until', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='WithdrawalRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=12, max_digits=16, validators=[django.core.validators.MinValueValidator(Decimal('0.000000000001'))])),
                ('currency', models.CharField(choices=[('btc', 'Bitcoin'), ('xmr', 'Monero')], max_length=3)),
                ('address', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('reviewing', 'Under Review'), ('approved', 'Approved'), ('processing', 'Processing'), ('completed', 'Completed'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('tx_hash', models.CharField(blank=True, max_length=255, null=True)),
                ('tx_fee', models.DecimalField(blank=True, decimal_places=12, max_digits=16, null=True)),
                ('ip_address', models.GenericIPAddressField()),
                ('user_agent', models.TextField()),
                ('two_fa_verified', models.BooleanField(default=False)),
                ('pin_verified', models.BooleanField(default=False)),
                ('risk_score', models.IntegerField(default=0)),
                ('risk_factors', models.JSONField(blank=True, default=dict)),
                ('manual_review_required', models.BooleanField(default=False)),
                ('user_note', models.TextField(blank=True)),
                ('admin_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('processed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='processed_withdrawals', to=settings.AUTH_USER_MODEL)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='withdrawal_requests', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        
        migrations.CreateModel(
            name='Wallet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balance_btc', models.DecimalField(decimal_places=8, default=Decimal('0.00000000'), max_digits=16, validators=[django.core.validators.MinValueValidator(Decimal('0'))])),
                ('balance_xmr', models.DecimalField(decimal_places=12, default=Decimal('0.000000000000'), max_digits=16, validators=[django.core.validators.MinValueValidator(Decimal('0'))])),
                ('escrow_btc', models.DecimalField(decimal_places=8, default=Decimal('0.00000000'), max_digits=16, validators=[django.core.validators.MinValueValidator(Decimal('0'))])),
                ('escrow_xmr', models.DecimalField(decimal_places=12, default=Decimal('0.000000000000'), max_digits=16, validators=[django.core.validators.MinValueValidator(Decimal('0'))])),
                ('withdrawal_pin', models.CharField(blank=True, max_length=128, null=True)),
                ('two_fa_enabled', models.BooleanField(default=False)),
                ('two_fa_secret', models.CharField(blank=True, max_length=32, null=True)),
                ('daily_withdrawal_limit_btc', models.DecimalField(decimal_places=8, default=Decimal('1.00000000'), max_digits=16)),
                ('daily_withdrawal_limit_xmr', models.DecimalField(decimal_places=12, default=Decimal('100.000000000000'), max_digits=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_activity', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='wallet', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        
        migrations.CreateModel(
            name='Transaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(choices=[('deposit', 'Deposit'), ('withdrawal', 'Withdrawal'), ('conversion', 'Conversion'), ('escrow_lock', 'Escrow Lock'), ('escrow_release', 'Escrow Release'), ('escrow_refund', 'Escrow Refund'), ('fee', 'Fee'), ('adjustment', 'Adjustment')], max_length=20)),
                ('amount', models.DecimalField(decimal_places=12, max_digits=16)),
                ('currency', models.CharField(max_length=3)),
                ('converted_amount', models.DecimalField(blank=True, decimal_places=12, max_digits=16, null=True)),
                ('converted_currency', models.CharField(blank=True, max_length=3, null=True)),
                ('conversion_rate', models.DecimalField(blank=True, decimal_places=12, max_digits=20, null=True)),
                ('balance_before', models.DecimalField(decimal_places=12, max_digits=16)),
                ('balance_after', models.DecimalField(decimal_places=12, max_digits=16)),
                ('reference', models.CharField(db_index=True, max_length=255)),
                ('related_object_type', models.CharField(blank=True, max_length=50, null=True)),
                ('related_object_id', models.IntegerField(blank=True, null=True)),
                ('transaction_hash', models.CharField(max_length=64, unique=True)),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        
        migrations.CreateModel(
            name='WalletBalanceCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('expected_btc', models.DecimalField(decimal_places=8, max_digits=16)),
                ('expected_xmr', models.DecimalField(decimal_places=12, max_digits=16)),
                ('expected_escrow_btc', models.DecimalField(decimal_places=8, max_digits=16)),
                ('expected_escrow_xmr', models.DecimalField(decimal_places=12, max_digits=16)),
                ('actual_btc', models.DecimalField(decimal_places=8, max_digits=16)),
                ('actual_xmr', models.DecimalField(decimal_places=12, max_digits=16)),
                ('actual_escrow_btc', models.DecimalField(decimal_places=8, max_digits=16)),
                ('actual_escrow_xmr', models.DecimalField(decimal_places=12, max_digits=16)),
                ('discrepancy_found', models.BooleanField(default=False)),
                ('discrepancy_details', models.JSONField(blank=True, default=dict)),
                ('resolved', models.BooleanField(default=False)),
                ('resolution_notes', models.TextField(blank=True)),
                ('checked_at', models.DateTimeField(auto_now_add=True)),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('wallet', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wallets.wallet')),
            ],
        ),
        
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['user', 'action', 'created_at'], name='wallets_aud_user_id_cd4a95_idx'),
        ),
        migrations.AddIndex(
            model_name='auditlog',
            index=models.Index(fields=['flagged', 'risk_score'], name='wallets_aud_flagged_858ccc_idx'),
        ),
        migrations.AddIndex(
            model_name='conversionrate',
            index=models.Index(fields=['from_currency', 'to_currency', 'is_active'], name='wallets_con_from_cu_044657_idx'),
        ),
        migrations.AddIndex(
            model_name='conversionrate',
            index=models.Index(fields=['valid_from', 'valid_until'], name='wallets_con_valid_f_1dc20a_idx'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['user', 'type', 'created_at'], name='wallets_tra_user_id_93760e_idx'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['reference'], name='wallets_tra_referen_6d0dd5_idx'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['transaction_hash'], name='wallets_tra_transac_e0f8cc_idx'),
        ),
        migrations.AddIndex(
            model_name='wallet',
            index=models.Index(fields=['user', 'updated_at'], name='wallets_wal_user_id_c74908_idx'),
        ),
        migrations.AddIndex(
            model_name='walletbalancecheck',
            index=models.Index(fields=['discrepancy_found', 'resolved', 'checked_at'], name='wallets_wal_discrep_ae4049_idx'),
        ),
        migrations.AddIndex(
            model_name='withdrawalrequest',
            index=models.Index(fields=['user', 'status', 'created_at'], name='wallets_wit_user_id_b41185_idx'),
        ),
        migrations.AddIndex(
            model_name='withdrawalrequest',
            index=models.Index(fields=['status', 'manual_review_required'], name='wallets_wit_status_8c35ac_idx'),
        ),
        
        migrations.AlterUniqueTogether(
            name='conversionrate',
            unique_together={('from_currency', 'to_currency', 'valid_from')},
        ),
    ]
