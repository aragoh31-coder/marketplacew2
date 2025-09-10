import bitcoinlib
from django.conf import settings

class BitcoinRPC:
    def __init__(self):
        self.rpc = bitcoinlib.rpc.BitcoinRPC(
            settings.BITCOIND_RPC_URL,
            rpcuser=settings.BITCOIND_RPC_USER,
            rpcpassword=settings.BITCOIND_RPC_PASSWORD,
        )

    def get_new_address(self, label=""):
        """Generate a new Bitcoin address."""
        try:
            # Use bech32 address type for modern wallets
            address = self.rpc.getnewaddress(label=label, address_type="bech32")
            return {"success": True, "address": address}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def validate_address(self, address):
        """Validate a Bitcoin address."""
        try:
            result = self.rpc.validateaddress(address)
            return {"success": True, "is_valid": result["isvalid"]}
        except Exception as e:
            return {"success": False, "error": str(e)}


from monero.wallet import Wallet as MoneroWallet
from monero.backends.jsonrpc import JSONRPCWallet

class MoneroRPC:
    def __init__(self):
        self.wallet = MoneroWallet(
            JSONRPCWallet(
                port=settings.MONERO_WALLET_RPC_PORT
            )
        )

    def get_new_address(self):
        """Generate a new Monero address."""
        try:
            # Create a new subaddress for the deposit
            new_address = self.wallet.new_address()
            return {"success": True, "address": str(new_address.address)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def validate_address(self, address):
        """Validate a Monero address."""
        try:
            # The monero library doesn't have a direct validation method,
            # but creating an Address object will fail if it's invalid.
            from monero.address import address as monero_address
            monero_address(address)
            return {"success": True, "is_valid": True}
        except ValueError:
            return {"success": True, "is_valid": False}
        except Exception as e:
            return {"success": False, "error": str(e)}
