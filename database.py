from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

# In database.py, update StakePosition model:

class StakePosition(Base):
    __tablename__ = 'stake_positions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    currency = Column(String(10))
    token_symbol = Column(String(50))
    contract_address = Column(String(100), nullable=True)
    amount = Column(Float, default=0.0)
    original_amount = Column(Float, default=0.0)  # Track original stake
    apy = Column(Float, default=20.0)
    lock_period_days = Column(Integer, default=0)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    status = Column(String(20), default='active')
    last_compound_date = Column(DateTime, nullable=True)
    last_notification_date = Column(DateTime, nullable=True)  # Track daily notifications
    milestone_100_notified = Column(Boolean, default=False)  # Track 100% milestone
    total_earnings = Column(Float, default=0.0)  # Track cumulative earnings
    
    user = relationship("User", back_populates="stake_positions")
    
class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Trading settings
    risk_percentage = Column(Float, default=1.0)
    max_position_size = Column(Float, default=100.0)
    
    # Exchange connection
    exchange_api_key = Column(String, nullable=True)
    exchange_secret = Column(String, nullable=True)
    
    # Deposit tracking
    total_deposited_sol = Column(Float, default=0.0)
    total_deposited_eth = Column(Float, default=0.0)
    deposit_count = Column(Integer, default=0)
    
    # Relationships
    copy_trading_configs = relationship("CopyTradingConfig", back_populates="user")
    trades = relationship("Trade", back_populates="user")
    deposits = relationship("Deposit", back_populates="user")
    stakes = relationship("StakePosition", back_populates="user")
    tool_usage = relationship("ToolUsage", back_populates="user")

class CopyTradingConfig(Base):
    __tablename__ = 'copy_trading_configs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    trader_address = Column(String, nullable=False)
    network = Column(String(10), default='solana')  # solana or ethereum
    allocation_percentage = Column(Float, default=10.0)
    is_active = Column(Boolean, default=True)
    copy_buys = Column(Boolean, default=True)
    copy_sells = Column(Boolean, default=True)
    max_slippage = Column(Float, default=2.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="copy_trading_configs")

class Trade(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float)
    entry_price = Column(Float)
    exit_price = Column(Float)
    pnl = Column(Float, default=0.0)
    status = Column(String, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="trades")

# In database.py, update StakePosition model:

class StakePosition(Base):
    __tablename__ = 'stake_positions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    currency = Column(String(10))
    token_symbol = Column(String(50))
    contract_address = Column(String(100), nullable=True)
    amount = Column(Float, default=0.0)
    original_amount = Column(Float, default=0.0)  # Track original stake
    apy = Column(Float, default=20.0)
    lock_period_days = Column(Integer, default=0)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    status = Column(String(20), default='active')
    last_compound_date = Column(DateTime, nullable=True)
    last_notification_date = Column(DateTime, nullable=True)  # Track daily notifications
    milestone_100_notified = Column(Boolean, default=False)  # Track 100% milestone
    total_earnings = Column(Float, default=0.0)  # Track cumulative earnings
    
    user = relationship("User", back_populates="stake_positions")

class Deposit(Base):
    __tablename__ = 'deposits'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    from_address = Column(String(50))
    to_address = Column(String(50))
    amount = Column(Float, nullable=False)
    currency = Column(String(10))
    tx_signature = Column(String(88))
    tx_hash = Column(String(66))
    confirmations = Column(Integer, default=0)
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime)
    
    user = relationship("User", back_populates="deposits")

class StakePosition(Base):
    __tablename__ = 'stake_positions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    currency = Column(String(10))
    token_symbol = Column(String(20))
    contract_address = Column(String(50))
    amount = Column(Float, default=0.0)
    apy = Column(Float, default=0.0)
    lock_period_days = Column(Integer, default=0)
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime)
    status = Column(String(20), default='active')
    
    user = relationship("User", back_populates="stakes")

class ToolUsage(Base):
    __tablename__ = 'tool_usage'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    tool_name = Column(String(50))
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="tool_usage")

# Initialize database
def init_db(database_url):
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)

SessionLocal = init_db("sqlite:///trading_bot.db")

