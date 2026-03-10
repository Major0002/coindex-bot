# trading_engine.py
import logging
from typing import Dict, List
from database import SessionLocal, CopyTradingConfig, Trade
from exchange_client import ExchangeClient, MockExchangeClient

logger = logging.getLogger(__name__)

class CopyTradingEngine:
    def __init__(self):
        self.db = SessionLocal()
        self.active_traders: Dict[str, ExchangeClient] = {}
    
    def register_trader(self, trader_address: str, client: ExchangeClient):
        """Register a trader to monitor for copy trading"""
        self.active_traders[trader_address] = client
    
    def process_trader_signal(self, trader_address: str, signal: Dict):
        """
        Process a trading signal from a followed trader
        signal: {'symbol': 'BTC/USDT', 'side': 'buy', 'amount': 0.1}
        """
        # Find all users copying this trader
        configs = self.db.query(CopyTradingConfig).filter_by(
            trader_address=trader_address, 
            is_active=True
        ).all()
        
        for config in configs:
            self._execute_copy_trade(config, signal)
    
    def _execute_copy_trade(self, config: CopyTradingConfig, signal: Dict):
        """Execute a copy trade for a specific user"""
        try:
            user = config.user
            
            # Calculate position size based on user's allocation
            allocation = config.allocation_percentage / 100
            
            # Get user's exchange client
            if user.exchange_api_key:
                client = ExchangeClient(user.exchange_api_key, user.exchange_secret)
            else:
                client = MockExchangeClient()  # Paper trading
            
            # Calculate copy trade amount
            original_amount = signal.get('amount', 0)
            copy_amount = original_amount * allocation
            
            # Risk management checks
            if copy_amount > user.max_position_size:
                copy_amount = user.max_position_size
                logger.warning(f"Position size capped for user {user.telegram_id}")
            
            # Execute the trade
            order = client.create_order(
                symbol=signal['symbol'],
                side=signal['side'],
                amount=copy_amount
            )
            
            # Record in database
            trade = Trade(
                user_id=user.id,
                symbol=signal['symbol'],
                side=signal['side'].upper(),
                quantity=copy_amount,
                status='FILLED' if 'error' not in order else 'FAILED'
            )
            self.db.add(trade)
            self.db.commit()
            
            logger.info(f"Copy trade executed for user {user.telegram_id}: {order}")
            
        except Exception as e:
            logger.error(f"Error executing copy trade: {e}")
            self.db.rollback()
    
    def get_user_performance(self, user_id: int) -> Dict:
        """Calculate trading performance for a user"""
        trades = self.db.query(Trade).filter_by(user_id=user_id).all()
        
        if not trades:
            return {'message': 'No trades yet'}
        
        # Simple P&L calculation (simplified)
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.status == 'FILLED'])
        
        return {
            'total_trades': total_trades,
            'win_rate': winning_trades / total_trades if total_trades > 0 else 0,
            'recent_trades': [
                {
                    'symbol': t.symbol,
                    'side': t.side,
                    'quantity': t.quantity,
                    'status': t.status,
                    'date': t.created_at.isoformat()
                } for t in trades[-10:]
            ]
        }

class SignalMonitor:
    """
    Monitors blockchain or exchange for trader signals
    This is a placeholder - real implementation depends on your signal source
    """
    def __init__(self, engine: CopyTradingEngine):
        self.engine = engine
    
    def start_monitoring(self):
        """Start monitoring loop (async/websocket recommended)"""
        pass
    
    def on_new_trade(self, trader_address: str, trade_data: Dict):
        """Callback when a followed trader makes a trade"""
        self.engine.process_trader_signal(trader_address, trade_data)