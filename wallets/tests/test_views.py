from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch, Mock

from wallets.models import Wallet, DepositAddress
from wallets.views import deposit_info

User = get_user_model()

class DepositInfoViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.wallet = Wallet.objects.create(user=self.user)

    def test_invalid_currency_redirects(self):
        """Test that requesting an invalid currency redirects to the dashboard."""
        request = self.factory.get(reverse('wallets:deposit_info', kwargs={'currency': 'usd'}))
        request.user = self.user
        response = deposit_info(request, currency='usd')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('wallets:dashboard'))

    def test_existing_address_is_displayed(self):
        """Test that an existing deposit address is retrieved and displayed."""
        DepositAddress.objects.create(
            user=self.user,
            currency='btc',
            address='existing_btc_address'
        )
        request = self.factory.get(reverse('wallets:deposit_info', kwargs={'currency': 'btc'}))
        request.user = self.user
        response = deposit_info(request, currency='btc')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'existing_btc_address')

    @patch('wallets.views.BitcoinRPC')
    def test_new_btc_address_generation_success(self, MockBitcoinRPC):
        """Test successful generation of a new Bitcoin address."""
        # Mock the RPC client's response
        mock_rpc_instance = Mock()
        mock_rpc_instance.get_new_address.return_value = {
            "success": True,
            "address": "new_btc_address"
        }
        MockBitcoinRPC.return_value = mock_rpc_instance

        request = self.factory.get(reverse('wallets:deposit_info', kwargs={'currency': 'btc'}))
        request.user = self.user
        response = deposit_info(request, currency='btc')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'new_btc_address')

        # Verify that a new address was saved to the database
        self.assertTrue(DepositAddress.objects.filter(user=self.user, currency='btc', address='new_btc_address').exists())
        # Verify the RPC method was called
        mock_rpc_instance.get_new_address.assert_called_once_with(label='testuser')

    @patch('wallets.views.MoneroRPC')
    def test_new_xmr_address_generation_success(self, MockMoneroRPC):
        """Test successful generation of a new Monero address."""
        mock_rpc_instance = Mock()
        mock_rpc_instance.get_new_address.return_value = {
            "success": True,
            "address": "new_xmr_address"
        }
        MockMoneroRPC.return_value = mock_rpc_instance

        request = self.factory.get(reverse('wallets:deposit_info', kwargs={'currency': 'xmr'}))
        request.user = self.user
        response = deposit_info(request, currency='xmr')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'new_xmr_address')
        self.assertTrue(DepositAddress.objects.filter(user=self.user, currency='xmr', address='new_xmr_address').exists())
        mock_rpc_instance.get_new_address.assert_called_once()

    @patch('wallets.views.BitcoinRPC')
    def test_address_generation_failure(self, MockBitcoinRPC):
        """Test handling of a failure during address generation."""
        mock_rpc_instance = Mock()
        mock_rpc_instance.get_new_address.return_value = {
            "success": False,
            "error": "Connection refused"
        }
        MockBitcoinRPC.return_value = mock_rpc_instance

        request = self.factory.get(reverse('wallets:deposit_info', kwargs={'currency': 'btc'}))
        request.user = self.user

        # We need a real session for messages to work
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)

        response = deposit_info(request, currency='btc')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Could not generate a new BTC address")
        # Verify no address was saved
        self.assertFalse(DepositAddress.objects.filter(user=self.user, currency='btc').exists())
