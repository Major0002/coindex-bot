# wallet_service.py
from typing import Dict
import requests
import logging

logger = logging.getLogger(__name__)

class WalletService:
    """
    Read-only wallet balance checker.
    NEVER stores or requests private keys/seed phrases.
    """
    
    def __init__(self):
        self.ethscan_api_key = "YourEtherscanAPIKey"
        self.solana_rpc = "https://api.mainnet-beta.solana.com"
    
    def get_eth_balance(self, address: str) -> Dict:
        """Get Ethereum balance via Etherscan"""
        try:
            url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={self.ethscan_api_key}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            eth_balance = int(data.get('result', 0)) / 1e18
            
            return {
                'ETH': eth_balance,
                'address': address,
                'network': 'Ethereum'
            }
        except Exception as e:
            logger.error(f"Error fetching ETH balance: {e}")
            return {'error': str(e)}
    
    def get_sol_balance(self, address: str) -> Dict:
        """Get Solana balance"""
        try:
            headers = {"Content-Type": "application/json"}
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [address]
            }
            response = requests.post(self.solana_rpc, json=payload, headers=headers, timeout=10)
            data = response.json()
            
            lamports = data.get('result', {}).get('value', 0)
            sol_balance = lamports / 1e9
            
            return {
                'SOL': sol_balance,
                'address': address,
                'network': 'Solana'
            }
        except Exception as e:
            logger.error(f"Error fetching SOL balance: {e}")
            return {'error': str(e)}