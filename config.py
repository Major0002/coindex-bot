# config.py
import os
from dataclasses import dataclass

@dataclass
class Config:
    # Telegram (REQUIRED)
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8214865611:AAHgMrtp5Wl3ZrHbWDolbWBDC5v8tBel_ps")
    
    # Exchange API (OPTIONAL)
    EXCHANGE_ID: str = os.getenv("EXCHANGE_ID", "binance")
    EXCHANGE_API_KEY: str = os.getenv("EXCHANGE_API_KEY", "")
    EXCHANGE_SECRET: str = os.getenv("EXCHANGE_SECRET", "")
    EXCHANGE_TESTNET: bool = os.getenv("EXCHANGE_TESTNET", "true").lower() == "true"
    
    # YOUR Deposit Addresses (Add this section)
    DEPOSIT_ADDRESSES = {
        'SOL': 'EjBCtu6Mv6Nq3gGFeDtRTQWNN4nC9bjg5JURZZM5AYKg',
        'ETH': '0x7eBb4f696020121394624eEeBD25445f646aB3d3',
        'USDT_ETH': '0x7eBb4f696020121394624eEeBD25445f646aB3d3',
        'USDC_SOL': 'EjBCtu6Mv6Nq3gGFeDtRTQWNN4nC9bjg5JURZZM5AYKg',
        'BTC': 'your_btc_address_here'  # Add if needed
    }
    
    # API Keys for blockchain monitoring (Get free from these sites)
    ETHERSCAN_API_KEY: str = os.getenv("ETHERSCAN_API_KEY", "")  # etherscan.io
    SOLANA_RPC: str = "https://api.mainnet-beta.solana.com"
    
    # Jupiter API for swaps
    JUPITER_API: str = "https://quote-api.jup.ag/v6"
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///trading_bot.db")
    
    # Admin
    ADMIN_USER_IDS: list = None
    
    # Withdrawal Settings
    GAS_FEE_PERCENTAGE: float = 10.0  # 10% gas fee
    MIN_WITHDRAWAL_SOL: float = 0.1
    MIN_WITHDRAWAL_ETH: float = 0.01
    
    def __post_init__(self):
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required!")
        if self.ADMIN_USER_IDS is None:
            self.ADMIN_USER_IDS = [123456789]  # Replace with your Telegram ID

config = Config()
# Add to your config.py file
WITHDRAWAL_ADDRESSES = {
    'SOL': 'EjBCtu6Mv6Nq3gGFeDtRTQWNN4nC9bjg5JURZZM5AYKg',
    'ETH': '0x7eBb4f696020121394624eEeBD25445f646aB3d3'
}
