import ccxt
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class ExchangeClient:
    def __init__(self, api_key: str, secret: str, testnet: bool = True):
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'adjustForTimeDifference': True,
                'test': testnet  # Use Binance testnet
            }
        })
        
        if testnet:
            self.exchange.set_sandbox_mode(True)
    
    def get_balance(self) -> Dict:
        """Get account balance"""
        try:
            balance = self.exchange.fetch_balance()
            return {
                'total': balance.get('total', {}),
                'free': balance.get('free', {}),
                'used': balance.get('used', {})
            }
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return {}
    
    def create_order(self, symbol: str, side: str, amount: float, 
                     price: Optional[float] = None, order_type: str = 'market') -> Dict:
        """Create a new order"""
        try:
            if order_type == 'market':
                order = self.exchange.create_market_buy_order(symbol, amount) if side == 'buy' \
                        else self.exchange.create_market_sell_order(symbol, amount)
            else:
                order = self.exchange.create_limit_buy_order(symbol, amount, price) if side == 'buy' \
                        else self.exchange.create_limit_sell_order(symbol, amount, price)
            return order
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return {'error': str(e)}
    
    def get_ticker(self, symbol: str) -> Dict:
        """Get current price for a symbol"""
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"Error fetching ticker: {e}")
            return {}
    
    def get_positions(self) -> List[Dict]:
        """Get open positions"""
        try:
            return self.exchange.fetch_positions()
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

# Mock client for users without API keys (paper trading)
class MockExchangeClient:
    def __init__(self):
        self.virtual_balance = {'USDT': 10000.0}  # Paper trading starts with 10k USDT
    
    def get_balance(self):
        return {'total': self.virtual_balance, 'free': self.virtual_balance, 'used': {}}
    
    def create_order(self, symbol, side, amount, price=None, order_type='market'):
        return {'id': 'mock_order', 'status': 'filled', 'symbol': symbol, 'side': side}