# database.py - COIN DEX AI - Complete Database Models

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    wallet_address = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    deposits = relationship("Deposit", back_populates="user", lazy='dynamic')
    trades = relationship("Trade", back_populates="user", lazy='dynamic')
    copy_trading_configs = relationship("CopyTradingConfig", back_populates="user", lazy='dynamic')
    stake_positions = relationship("StakePosition", back_populates="user", lazy='dynamic')
    tool_usage = relationship("ToolUsage", back_populates="user", lazy='dynamic')
    withdrawals = relationship("Withdrawal", back_populates="user", lazy='dynamic')


class Deposit(Base):
    __tablename__ = 'deposits'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    currency = Column(String(10), nullable=False)  # SOL, ETH, USDT
    amount = Column(Float, nullable=False)
    tx_hash = Column(String(100))
    status = Column(String(20), default='pending')  # pending, confirmed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime)
    
    user = relationship("User", back_populates="deposits")


class Trade(Base):
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    token_in = Column(String(50), nullable=False)
    token_out = Column(String(50), nullable=False)
    amount_in = Column(Float, nullable=False)
    amount_out = Column(Float)
    price = Column(Float)
    pnl = Column(Float)  # Profit/Loss
    tx_hash = Column(String(100))
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="trades")


class CopyTradingConfig(Base):
    __tablename__ = 'copy_trading_configs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    trader_address = Column(String(100), nullable=False)
    network = Column(String(20), default='solana')  # solana, ethereum
    allocation_percentage = Column(Float, default=50.0)
    is_active = Column(Boolean, default=True)
    copy_buys = Column(Boolean, default=True)
    copy_sells = Column(Boolean, default=True)
    max_slippage = Column(Float, default=2.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="copy_trading_configs")


class StakePosition(Base):
    __tablename__ = 'stake_positions'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    token_address = Column(String(100), nullable=False)
    token_symbol = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    apy = Column(Float, default=0.0)
    status = Column(String(20), default='active')  # active, withdrawn, closed
    created_at = Column(DateTime, default=datetime.utcnow)
    withdrawn_at = Column(DateTime)
    
    user = relationship("User", back_populates="stake_positions")


class ToolUsage(Base):
    __tablename__ = 'tool_usage'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    tool_name = Column(String(50), nullable=False)  # price_alerts, analytics, etc.
    usage_count = Column(Integer, default=1)
    last_used = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="tool_usage")


class Withdrawal(Base):
    __tablename__ = 'withdrawals'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    currency = Column(String(10), nullable=False)  # SOL, ETH, etc.
    amount = Column(Float, nullable=False)
    to_address = Column(String(100), nullable=False)
    gas_fee_paid = Column(Boolean, default=False)
    status = Column(String(20), default='pending')  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="withdrawals")


# Database connection
def get_db_url():
    """Get database URL - modify as needed"""
    return 'sqlite:///trading_bot.db'


def init_db():
    """Initialize database"""
    engine = create_engine(get_db_url())
    Base.metadata.create_all(engine)
    return engine


def get_session():
    """Get database session"""
    engine = create_engine(get_db_url())
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


# For backward compatibility
engine = create_engine(get_db_url())
SessionLocal = sessionmaker(bind=engine)

if __name__ == '__main__':
    print("Initializing database...")
    init_db()
    print("Database created successfully!")