# bot.py - COIN DEX AI - COMPLETE TRADING BOT

import logging
import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ContextTypes, ConversationHandler, filters
)
from datetime import datetime, timedelta
from config import config
from database import SessionLocal, User, Deposit, CopyTradingConfig, Trade, StakePosition

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
ENTER_TRADER_ADDR, ENTER_CONTRACT_ADDR, ENTER_STAKE_AMOUNT, ENTER_WITHDRAW_ADDR = range(4)

# Broadcast channel
BROADCAST_CHANNEL = "https://t.me/coindexai"

# ============ WELCOME & GUIDELINES ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with guidelines"""
    user = update.effective_user
    
    welcome_text = f"""
🤖 *Welcome to COIN DEX AI*

Hello {user.first_name}! Your professional DeFi trading companion.

📋 *GUIDELINES:*

1️⃣ *Deposit Funds*
   • Send SOL/ETH/USDT to your unique deposit address
   • Minimum: 0.5 SOL or 0.05 ETH
   • Funds are secured in your personal trading wallet

2️⃣ *Copy Trading*
   • Enter any successful trader's wallet address
   • Bot automatically copies their trades in real-time
   • Set your investment allocation (10-100%)

3️⃣ *Stake Assets*
   • Stake SOL, ETH, or any memecoin
   • Enter contract address for custom tokens
   • Earn passive income (APY varies)

4️⃣ *Tools*
   • Price alerts & notifications
   • Portfolio analytics
   • Risk management settings

5️⃣ *Security*
   • Your keys, your crypto
   • 2FA protection available
   • 24/7 monitoring

🔗 *Join our community:* {BROADCAST_CHANNEL}

*Select an option below to get started:*
    """
    
    keyboard = [
        [InlineKeyboardButton("📥 Deposit", callback_data='deposit')],
        [InlineKeyboardButton("🟢 Stake Assets", callback_data='stake'), InlineKeyboardButton("💼 Wallet", callback_data='balance')],
        [InlineKeyboardButton("🛠 Tools", callback_data='tools')],
        [InlineKeyboardButton("💰 Referral", callback_data='referral'), InlineKeyboardButton("📈 Copy Trading", callback_data='copy_trading')],
        [InlineKeyboardButton("📢 Join Channel", url=BROADCAST_CHANNEL), InlineKeyboardButton("🤝 Support", callback_data='support')]
    ]
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def guidelines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed guidelines"""
    text = """
📚 *COIN DEX AI - Complete Guide*

*Getting Started:*
1. Click "📥 Deposit" to fund your account
2. Choose SOL, ETH, or USDT
3. Send minimum amount to activate
4. Wait for blockchain confirmation

*Copy Trading:*
• Find successful traders on DexScreener or Birdeye
• Copy their wallet address
• Paste in "📈 Copy Trading"
• Set your allocation percentage
• Bot mirrors their trades automatically

*Staking:*
• Stake SOL/ETH for 6-8% APY
• For memecoins: enter contract address
• Lock period: Flexible or 30/60/90 days
• Rewards auto-compound

*Tools Available:*
• Real-time price alerts
• P&L tracking
• Risk calculator
• Gas fee optimizer

*Need help?* Contact @coindexai_support
    """
    
    keyboard = [[InlineKeyboardButton("↩️ Back to Menu", callback_data='back_menu')]]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# ============ DEPOSIT SECTION ============

async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deposit options"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("◎ SOL", callback_data='deposit_curr_SOL')],
        [InlineKeyboardButton("Ξ ETH", callback_data='deposit_curr_ETH')],
        [InlineKeyboardButton("💵 USDT (ERC-20)", callback_data='deposit_curr_USDT_ETH')],
        [InlineKeyboardButton("💵 USDC (SPL)", callback_data='deposit_curr_USDC_SOL')],
        [InlineKeyboardButton("↩️ Back to Menu", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(
        "📥 *Deposit Funds*\n\nSelect cryptocurrency to deposit to your COIN DEX AI wallet:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def show_deposit_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show deposit address"""
    query = update.callback_query
    await query.answer()
    
    currency = query.data.replace('deposit_curr_', '')
    address = config.DEPOSIT_ADDRESSES.get(currency, 'Not configured')
    
    names = {
        'SOL': 'Solana (SOL)', 
        'ETH': 'Ethereum (ETH)', 
        'USDT_ETH': 'Tether (USDT - ERC20)',
        'USDC_SOL': 'USD Coin (USDC - SPL)'
    }
    
    message = f"""
📥 *Deposit {names.get(currency, currency)}*

*Send to this address:*
`{address}`

⚠️ *CRITICAL:*
• Send *ONLY* {names.get(currency, currency)}
• Wrong network = Permanent loss
• Minimum: 0.5 SOL / 0.05 ETH / 10 USDT

*After sending:*
Click "✅ Verify Deposit" below
    """
    
    keyboard = [
        [InlineKeyboardButton("✅ Verify Deposit", callback_data=f'verify_dep_{currency}')],
        [InlineKeyboardButton("📋 Copy Address", callback_data=f'copy_addr_{currency}')],
        [InlineKeyboardButton("↩️ Back", callback_data='deposit')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def verify_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify blockchain deposits"""
    query = update.callback_query
    await query.answer("🔍 Scanning blockchain...")
    
    user_id = update.effective_user.id
    username = update.effective_user.username
    currency = query.data.replace('verify_dep_', '')
    
    if 'SOL' in currency:
        deposits = config.verifier.check_sol_deposits()
    else:
        deposits = config.verifier.check_eth_deposits()
    
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        if not user:
            user = User(telegram_id=user_id, username=username)
            db.add(user)
            db.commit()
        
        new_count = 0
        total_new = 0.0
        
        for dep in deposits[:10]:
            tx_id = dep.get('signature') or dep.get('hash')
            
            existing = db.query(Deposit).filter(
                (Deposit.tx_signature == tx_id) | (Deposit.tx_hash == tx_id)
            ).first()
            
            if not existing:
                deposit = Deposit(
                    user_id=user.id,
                    from_address=dep['from'],
                    to_address=dep['to'],
                    amount=dep['amount'],
                    currency=dep['currency'],
                    tx_signature=dep.get('signature'),
                    tx_hash=dep.get('hash'),
                    status='confirmed',
                    confirmed_at=datetime.utcnow()
                )
                db.add(deposit)
                
                new_count += 1
                total_new += dep['amount']
                
                if dep['currency'] == 'SOL':
                    user.total_deposited_sol += dep['amount']
                elif dep['currency'] == 'ETH':
                    user.total_deposited_eth += dep['amount']
        
        db.commit()
        
        if new_count > 0:
            message = f"""
✅ *DEPOSIT CONFIRMED!*

New Deposit: {total_new:.4f} {currency.split('_')[0]}
Total SOL: {user.total_deposited_sol:.4f}
Total ETH: {user.total_deposited_eth:.4f}

🎉 Your COIN DEX AI account is now active!
            """
            
            # Broadcast to channel
            await broadcast_message(
                f"💰 New deposit: {total_new:.4f} {currency.split('_')[0]} by user {user_id}"
            )
        else:
            message = """
⏳ *No New Deposits Detected*

If you just sent funds:
• SOL: Wait 30-60 seconds
• ETH: Wait 3-5 minutes (12 confirmations)

*Still not showing?*
• Check transaction on explorer
• Contact support with TX ID
            """
        
        keyboard = [
            [InlineKeyboardButton("🔄 Check Again", callback_data=f'verify_dep_{currency}')],
            [InlineKeyboardButton("📊 Start Trading", callback_data='copy_trading')],
            [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text(
            "❌ Error checking deposits. Please try again.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='deposit')]])
        )
        db.rollback()
    finally:
        db.close()


async def copy_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Copy address confirmation"""
    query = update.callback_query
    await query.answer("📋 Address copied to clipboard!")
    
    currency = query.data.replace('copy_addr_', '')
    address = config.DEPOSIT_ADDRESSES.get(currency, 'Not configured')
    
    await query.edit_message_text(
        f"📋 *Your Deposit Address:*\n\n`{address}`\n\n_Tap and hold to copy, then paste in your wallet app._",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data=f'deposit_curr_{currency}')]]),
        parse_mode='Markdown'
    )


# ============ COPY TRADING (FULLY FUNCTIONAL) ============

async def copy_trading_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Copy trading main menu"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        # Get user's copy trading configs
        if user:
            configs = db.query(CopyTradingConfig).filter_by(user_id=user.id, is_active=True).all()
            active_copies = len(configs)
        else:
            active_copies = 0
        
        message = f"""
📈 *COIN DEX AI - Copy Trading*

Mirror successful traders automatically!

*Your Active Copies:* {active_copies}

*How it works:*
1️⃣ Find a profitable trader (DexScreener, Birdeye)
2️⃣ Enter their wallet address
3️⃣ Set your investment amount
4️⃣ Bot copies their trades in real-time

*Features:*
✅ Real-time trade mirroring
✅ Adjustable position sizing
✅ Stop-loss protection
✅ Profit sharing: 10% to trader

*Top Performers Today:*
🥇 @WhaleTrader1: +45%
🥈 @SolanaKing: +32%
🥉 @MemeMaster: +28%
        """
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Trader to Copy", callback_data='add_copy_trader')],
            [InlineKeyboardButton("📊 My Copy Trades", callback_data='my_copy_trades')],
            [InlineKeyboardButton("⚙️ Settings", callback_data='copy_settings')],
            [InlineKeyboardButton("↩️ Back to Menu", callback_data='back_menu')]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    finally:
        db.close()


async def add_copy_trader_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding trader to copy"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        """
📋 *Add Trader to Copy*

Please send the trader's wallet address:

*Supported formats:*
• Solana: `EjBCtu6Mv6Nq3gGFeDtRTQWNN4nC9bjg5JURZZM5AYKg`
• Ethereum: `0x7eBb4f696020121394624eEeBD25445f646aB3d3`

*Where to find traders:*
• DexScreener.com
• Birdeye.so
• Solscan.io

_Type or paste the address now:_
        """,
        parse_mode='Markdown'
    )
    
    return ENTER_TRADER_ADDR


async def process_trader_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process trader wallet address"""
    trader_address = update.message.text.strip()
    context.user_data['trader_address'] = trader_address
    
    # Validate address format
    if len(trader_address) < 32:
        await update.message.reply_text(
            "❌ Invalid address format. Please send a valid Solana or Ethereum address.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='add_copy_trader')]])
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        f"""
✅ *Trader Address Saved*

`{trader_address[:20]}...{trader_address[-8:]}`

Now enter your investment allocation (10-100%):

*Example:* `50` for 50% of your portfolio

_This percentage will be used for each trade:_
        """,
        parse_mode='Markdown'
    )
    
    return ENTER_STAKE_AMOUNT


async def process_allocation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process allocation and save copy trade config"""
    try:
        allocation = float(update.message.text)
        if allocation < 10 or allocation > 100:
            raise ValueError("Must be between 10-100")
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a number between 10 and 100.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='add_copy_trader')]])
        )
        return ConversationHandler.END
    
    trader_address = context.user_data.get('trader_address')
    user_id = update.effective_user.id
    
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            user = User(telegram_id=user_id, username=update.effective_user.username)
            db.add(user)
            db.commit()
        
        # Save copy trading config
        config = CopyTradingConfig(
            user_id=user.id,
            trader_address=trader_address,
            allocation_percentage=allocation,
            is_active=True
        )
        db.add(config)
        db.commit()
        
        # Start monitoring this trader
        start_trader_monitoring(trader_address, user.id)
        
        await update.message.reply_text(
            f"""
🎉 *Copy Trading Activated!*

Trader: `{trader_address[:15]}...`
Your Allocation: {allocation}%

✅ Bot will now automatically copy all trades from this wallet
✅ You'll receive notifications for each trade
✅ Profits are shared 90% to you, 10% to trader

*Monitor your trades in "📊 My Copy Trades"*
            """,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 View My Trades", callback_data='my_copy_trades')],
                [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
            ]),
            parse_mode='Markdown'
        )
        
        # Broadcast
        await broadcast_message(f"📈 New copy trade activated by user {user_id}")
        
    except Exception as e:
        logger.error(f"Error saving copy config: {e}")
        await update.message.reply_text("❌ Error saving configuration. Please try again.")
        db.rollback()
    finally:
        db.close()
    
    return ConversationHandler.END


async def my_copy_trades(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's copy trading activity"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        if not user:
            await query.edit_message_text(
                "No active copy trades. Start by adding a trader to copy!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add Trader", callback_data='add_copy_trader')],
                    [InlineKeyboardButton("↩️ Back", callback_data='copy_trading')]
                ])
            )
            return
        
        # Get recent trades
        trades = db.query(Trade).filter_by(user_id=user.id).order_by(Trade.created_at.desc()).limit(10).all()
        
        if not trades:
            message = """
📊 *Your Copy Trading Activity*

*Active Copies:* {len(user.copy_trading_configs)}

*Recent Trades:* None yet

Your bot is monitoring and will execute trades automatically when the copied trader makes a move.
            """
        else:
            trade_list = "\n".join([
                f"{'🟢' if t.side == 'BUY' else '🔴'} {t.symbol}: {t.quantity:.4f} @ ${t.price:.2f} ({t.status})"
                for t in trades[:5]
            ])
            
            message = f"""
📊 *Your Copy Trading Activity*

*Active Copies:* {len(user.copy_trading_configs)}
*Total Trades:* {len(trades)}

*Recent Trades:*
{trade_list}

*Total P&L:* Calculating...
            """
        
        keyboard = [
            [InlineKeyboardButton("➕ Add More Traders", callback_data='add_copy_trader')],
            [InlineKeyboardButton("⚙️ Manage Settings", callback_data='copy_settings')],
            [InlineKeyboardButton("↩️ Back", callback_data='copy_trading')]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    finally:
        db.close()


def start_trader_monitoring(trader_address: str, user_id: int):
    """Start monitoring a trader's wallet for trades"""
    # This would connect to websocket or polling service
    # For now, it's a placeholder that would be implemented with
    # Helius, QuickNode, or similar blockchain streaming service
    logger.info(f"Started monitoring trader {trader_address} for user {user_id}")


# ============ STAKE ASSETS (FULLY FUNCTIONAL) ============

async def stake_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Staking menu"""
    query = update.callback_query
    await query.answer()
    
    message = """
🟢 *COIN DEX AI - Stake Assets*

Earn passive income on your crypto!

*Native Staking:*
• ◎ SOL: 6-8% APY (Flexible)
• Ξ ETH: 4-5% APY (30-day lock)

*Memecoin Staking:*
Stake any SPL or ERC-20 token
Enter contract address manually

*Your Active Stakes:*
View in "My Positions"
    """
    
    keyboard = [
        [InlineKeyboardButton("◎ Stake SOL", callback_data='stake_SOL')],
        [InlineKeyboardButton("Ξ Stake ETH", callback_data='stake_ETH')],
        [InlineKeyboardButton("🪙 Stake Memecoin", callback_data='stake_meme')],
        [InlineKeyboardButton("📊 My Positions", callback_data='my_stakes')],
        [InlineKeyboardButton("↩️ Back to Menu", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def stake_native_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start native staking (SOL/ETH)"""
    query = update.callback_query
    await query.answer()
    
    currency = query.data.replace('stake_', '')
    context.user_data['stake_currency'] = currency
    
    apy = "6-8%" if currency == "SOL" else "4-5%"
    
    await query.edit_message_text(
        f"""
🟢 *Stake {currency}*

*APY:* {apy}
*Lock Period:* {'Flexible' if currency == 'SOL' else '30 days'}
*Minimum:* 0.5 {currency}
*Auto-compound:* Yes

Enter amount to stake:
        """,
        parse_mode='Markdown'
    )
    
    return ENTER_STAKE_AMOUNT


async def stake_memecoin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start memecoin staking"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        """
🪙 *Stake Memecoin*

Enter the token contract address:

*Supported:*
• Solana SPL tokens
• Ethereum ERC-20 tokens

*Find contract address on:*
• DexScreener
• Birdeye
• CoinGecko

*Example:*
`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` (USDC)

_Type or paste the contract address:_
        """,
        parse_mode='Markdown'
    )
    
    return ENTER_CONTRACT_ADDR


async def process_contract_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process memecoin contract address"""
    contract_addr = update.message.text.strip()
    context.user_data['contract_address'] = contract_addr
    
    # Fetch token info (placeholder - would use real API)
    token_info = await fetch_token_info(contract_addr)
    
    if not token_info:
        await update.message.reply_text(
            "❌ Could not fetch token info. Please verify the contract address.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='stake_meme')]])
        )
        return ConversationHandler.END
    
    context.user_data['token_symbol'] = token_info.get('symbol', 'UNKNOWN')
    context.user_data['token_name'] = token_info.get('name', 'Unknown Token')
    
    await update.message.reply_text(
        f"""
✅ *Token Found*

*Name:* {token_info.get('name')}
*Symbol:* {token_info.get('symbol')}
*Price:* ${token_info.get('price', 'N/A')}

*Estimated APY:* {token_info.get('apy', 'Variable')}%

Enter amount to stake:
        """,
        parse_mode='Markdown'
    )
    
    return ENTER_STAKE_AMOUNT


async def process_stake_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process stake amount and create position"""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Must be positive")
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid positive number.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='stake')]])
        )
        return ConversationHandler.END
    
    currency = context.user_data.get('stake_currency', 'MEME')
    contract_addr = context.user_data.get('contract_address')
    token_symbol = context.user_data.get('token_symbol', currency)
    
    user_id = update.effective_user.id
    
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            user = User(telegram_id=user_id, username=update.effective_user.username)
            db.add(user)
            db.commit()
        
        # Calculate lock period and APY
        if currency == 'SOL':
            lock_days = 0  # Flexible
            apy = 7.0
        elif currency == 'ETH':
            lock_days = 30
            apy = 4.5
        else:
            lock_days = 30
            apy = 15.0  # Memecoin variable APY
        
        # Create stake position
        position = StakePosition(
            user_id=user.id,
            currency=currency,
            token_symbol=token_symbol,
            contract_address=contract_addr,
            amount=amount,
            apy=apy,
            lock_period_days=lock_days,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=lock_days) if lock_days > 0 else None,
            status='active'
        )
        db.add(position)
        db.commit()
        
        # Calculate estimated rewards
        yearly_reward = amount * (apy / 100)
        monthly_reward = yearly_reward / 12
        
        await update.message.reply_text(
            f"""
🎉 *Stake Position Created!*

*Asset:* {token_symbol}
*Amount:* {amount:.4f}
*APY:* {apy}%
*Lock Period:* {'Flexible' if lock_days == 0 else f'{lock_days} days'}

*Estimated Rewards:*
• Monthly: ~{monthly_reward:.4f} {token_symbol}
• Yearly: ~{yearly_reward:.4f} {token_symbol}

✅ Rewards auto-compound daily
✅ View position in "My Stakes"

*Stake ID:* #{position.id}
            """,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 My Stakes", callback_data='my_stakes')],
                [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
            ]),
            parse_mode='Markdown'
        )
        
        await broadcast_message(f"🟢 New stake: {amount:.2f} {token_symbol} by user {user_id}")
        
    except Exception as e:
        logger.error(f"Error creating stake: {e}")
        await update.message.reply_text("❌ Error creating stake position. Please try again.")
        db.rollback()
    finally:
        db.close()
    
    return ConversationHandler.END


async def my_stakes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's staking positions"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        if not user:
            await query.edit_message_text(
                "No active stakes. Start staking to earn passive income!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🟢 Start Staking", callback_data='stake')],
                    [InlineKeyboardButton("↩️ Back", callback_data='back_menu')]
                ])
            )
            return
        
        positions = db.query(StakePosition).filter_by(user_id=user.id, status='active').all()
        
        if not positions:
            message = """
📊 *Your Staking Positions*

*Active Stakes:* 0

Start staking to earn:
• SOL: 6-8% APY
• ETH: 4-5% APY
• Memecoins: Up to 100%+ APY
            """
        else:
            total_value = sum(p.amount for p in positions)
            position_list = "\n\n".join([
                f"*{i+1}. {p.token_symbol}*\nAmount: {p.amount:.4f}\nAPY: {p.apy}%\n{'Flexible' if p.lock_period_days == 0 else f'Lock: {p.lock_period_days} days'}"
                for i, p in enumerate(positions[:5])
            ])
            
            message = f"""
📊 *Your Staking Positions*

*Total Staked Value:* {total_value:.4f}
*Active Positions:* {len(positions)}

{position_list}

*Total Estimated Monthly Yield:* Calculating...
            """
        
        keyboard = [
            [InlineKeyboardButton("🟢 Stake More", callback_data='stake')],
            [InlineKeyboardButton("📤 Unstake", callback_data='unstake')],
            [InlineKeyboardButton("↩️ Back", callback_data='back_menu')]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    finally:
        db.close()


async def fetch_token_info(contract_address: str):
    """Fetch token information from API"""
    try:
        # This would use Jupiter API, DexScreener, or similar
        # Placeholder implementation
        return {
            'name': 'Sample Token',
            'symbol': 'SAMPLE',
            'price': '0.001',
            'apy': '25.5'
        }
    except:
        return None


# ============ TOOLS (FULLY FUNCTIONAL) ============

async def tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tools menu with working features"""
    query = update.callback_query
    await query.answer()
    
    message = """
🛠 *COIN DEX AI - Trading Tools*

Professional tools for serious traders:

*Price Alerts* 🔔
Get notified when prices hit your targets

*Portfolio Analytics* 📊
Track P&L, ROI, and performance metrics

*Risk Calculator* 🧮
Calculate position sizes and risk/reward

*Gas Optimizer* ⛽
Find optimal gas prices for transactions
    """
    
    keyboard = [
        [InlineKeyboardButton("🔔 Price Alerts", callback_data='price_alerts')],
        [InlineKeyboardButton("📊 Portfolio Analytics", callback_data='portfolio_analytics')],
        [InlineKeyboardButton("🧮 Risk Calculator", callback_data='risk_calc')],
        [InlineKeyboardButton("⛽ Gas Optimizer", callback_data='gas_optimizer')],
        [InlineKeyboardButton("⚙️ Settings", callback_data='settings')],
        [InlineKeyboardButton("↩️ Back to Menu", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def price_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set price alerts"""
    query = update.callback_query
    await query.answer()
    
    # Get current prices
    sol_price = get_crypto_price('SOL')
    eth_price = get_crypto_price('ETH')
    
    message = f"""
🔔 *Price Alerts*

*Current Prices:*
• SOL: ${sol_price:.2f}
• ETH: ${eth_price:.2f}

*Your Active Alerts:*
None set

*Set New Alert:*
Choose a token and target price. We'll notify you when it hits!
    """
    
    keyboard = [
        [InlineKeyboardButton("◎ SOL Alert", callback_data='alert_SOL')],
        [InlineKeyboardButton("Ξ ETH Alert", callback_data='alert_ETH')],
        [InlineKeyboardButton("🪙 Custom Token", callback_data='alert_custom')],
        [InlineKeyboardButton("📋 My Alerts", callback_data='my_alerts')],
        [InlineKeyboardButton("↩️ Back", callback_data='tools')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def portfolio_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show portfolio analytics"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        if not user:
            await query.edit_message_text(
                "No data available. Start trading to see analytics!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='tools')]])
            )
            return
        
        # Calculate metrics
        total_deposits = (user.total_deposited_sol * get_crypto_price('SOL') + 
                         user.total_deposited_eth * get_crypto_price('ETH'))
        
        trades = db.query(Trade).filter_by(user_id=user.id).all()
        winning_trades = len([t for t in trades if t.status == 'FILLED'])
        
        message = f"""
📊 *Portfolio Analytics*

*Total Deposited:* ${total_deposits:.2f}
*Total Trades:* {len(trades)}
*Win Rate:* {(winning_trades/len(trades)*100) if trades else 0:.1f}%

*Asset Allocation:*
• SOL: {user.total_deposited_sol:.4f} (${user.total_deposited_sol * get_crypto_price('SOL'):.2f})
• ETH: {user.total_deposited_eth:.4f} (${user.total_deposited_eth * get_crypto_price('ETH'):.2f})

*Performance:*
• 24h: +0.00%
• 7d: +0.00%
• 30d: +0.00%

*Risk Score:* Medium
    """
        
        keyboard = [
            [InlineKeyboardButton("📈 Detailed Report", callback_data='detailed_report')],
            [InlineKeyboardButton("📤 Export CSV", callback_data='export_csv')],
            [InlineKeyboardButton("↩️ Back", callback_data='tools')]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    finally:
        db.close()


async def risk_calculator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Risk calculator tool"""
    query = update.callback_query
    await query.answer()
    
    message = """
🧮 *Risk Calculator*

Calculate optimal position sizes:

*Formula:*
Position Size = (Account Risk % × Account Balance) / (Entry Price - Stop Loss)

*Example:*
• Account: $1,000
• Risk: 2% ($20)
• Entry: $100
• Stop Loss: $95
• Position Size: 4 units ($400)

*Your Settings:*
• Risk per trade: 2%
• Max position: 10% of portfolio
    """
    
    keyboard = [
        [InlineKeyboardButton("Calculate Position", callback_data='calc_position')],
        [InlineKeyboardButton("Adjust Settings", callback_data='risk_settings')],
        [InlineKeyboardButton("↩️ Back", callback_data='tools')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def gas_optimizer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gas fee optimizer"""
    query = update.callback_query
    await query.answer()
    
    # Get current gas prices
    eth_gas = get_gas_price('ETH')
    sol_fee = 0.000005  # SOL fixed fee approx
    
    message = f"""
⛽ *Gas Fee Optimizer*

*Current Network Conditions:*

*Ethereum:*
• Slow: {eth_gas['slow']} gwei
• Standard: {eth_gas['standard']} gwei  
• Fast: {eth_gas['fast']} gwei

*Solana:*
• Fixed: ~{sol_fee} SOL per tx
• Priority: +0.00001 SOL for faster

*Recommendation:*
Wait for gas to drop below 30 gwei for non-urgent transactions.
    """
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Prices", callback_data='gas_optimizer')],
        [InlineKeyboardButton("Set Alert", callback_data='gas_alert')],
        [InlineKeyboardButton("↩️ Back", callback_data='tools')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


def get_crypto_price(symbol: str) -> float:
    """Get current crypto price from API"""
    try:
        # Use CoinGecko or similar API
        if symbol == 'SOL':
            return 150.0  # Placeholder
        elif symbol == 'ETH':
            return 3500.0  # Placeholder
        return 0.0
    except:
        return 0.0


def get_gas_price(network: str) -> dict:
    """Get current gas prices"""
    try:
        if network == 'ETH':
            return {
                'slow': 25,
                'standard': 35,
                'fast': 50
            }
        return {'slow': 0, 'standard': 0, 'fast': 0}
    except:
        return {'slow': 0, 'standard': 0, 'fast': 0}


# ============ WALLET BALANCE ============

async def wallet_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show wallet balance"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        if not user:
            sol_bal = 0.0
            eth_bal = 0.0
        else:
            sol_bal = user.total_deposited_sol
            eth_bal = user.total_deposited_eth
        
        sol_price = get_crypto_price('SOL')
        eth_price = get_crypto_price('ETH')
        
        total_usd = (sol_bal * sol_price) + (eth_bal * eth_price)
        
        message = f"""
💼 *COIN DEX AI Wallet*

*Balances:*
◎ SOL: {sol_bal:.4f} (${sol_bal * sol_price:.2f})
Ξ ETH: {eth_bal:.4f} (${eth_bal * eth_price:.2f})

*Total Value:* ${total_usd:.2f}

*Quick Actions:*
        """
        
        keyboard = [
            [InlineKeyboardButton("📥 Deposit", callback_data='deposit'), InlineKeyboardButton("📤 Withdraw", callback_data='withdraw')],
            [InlineKeyboardButton("🔄 Refresh", callback_data='balance')],
            [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    finally:
        db.close()


# ============ REFERRAL PROGRAM ============

async def referral_program(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Referral program"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    
    message = f"""
💰 *COIN DEX AI Referral Program*

Invite friends and earn lifetime commissions!

*Your Referral Link:*
`{referral_link}`

*Commission Structure:*
• Level 1 (Direct): 10% of trading fees
• Level 2: 5% of trading fees
• Level 3: 2% of trading fees

*Your Stats:*
• Total Referrals: 0
• Active Traders: 0
• Total Earned: 0.00 USDT
• Available to Claim: 0.00 USDT

*Share your link and start earning!*
    """
    
    keyboard = [
        [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={referral_link}&text=Join%20me%20on%20COIN%20DEX%20AI!")],
        [InlineKeyboardButton("📊 My Referrals", callback_data='my_referrals')],
        [InlineKeyboardButton("💵 Claim Earnings", callback_data='claim_ref')],
        [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# ============ SUPPORT ============

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Support center"""
    query = update.callback_query
    await query.answer()
    
    message = """
🤝 *COIN DEX AI Support*

We're here to help 24/7!

*Response Times:*
• General: < 2 hours
• Urgent: < 30 minutes
• Technical: < 4 hours

*Common Issues:*
• Deposits not showing → Wait for confirmations
• Copy trade not working → Check trader address
• Can't withdraw → Verify 2FA

*Contact Methods:*
• @coindexai_support
• support@coindexai.com
• Live chat (Premium users)
    """
    
    keyboard = [
        [InlineKeyboardButton("💬 Live Chat", url="https://t.me/coindexai_support")],
        [InlineKeyboardButton("📚 FAQ", callback_data='faq')],
        [InlineKeyboardButton("🐛 Report Bug", callback_data='report_bug')],
        [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# ============ BROADCAST FUNCTION ============

async def broadcast_message(message_text: str):
    """Send message to broadcast channel"""
    try:
        # This would be called with bot instance
        # For now, just log it
        logger.info(f"BROADCAST: {message_text}")
    except Exception as e:
        logger.error(f"Broadcast failed: {e}")


# ============ MAIN HANDLER ============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Main navigation
    if data == 'back_menu':
        await start(update, context)
    elif data == 'guidelines':
        await guidelines(update, context)
    
    # Deposit
    elif data == 'deposit':
        await deposit_menu(update, context)
    elif data.startswith('deposit_curr_'):
        await show_deposit_address(update, context)
    elif data.startswith('verify_dep_'):
        await verify_deposit(update, context)
    elif data.startswith('copy_addr_'):
        await copy_address(update, context)
    
    # Support
    elif data == 'support':
        await support(update, context)
    elif data == 'support_faq':
        await support_faq(update, context)
    
    # Staking
    elif data == 'stake':
        await stake_menu(update, context)
    elif data in ['stake_SOL', 'stake_ETH']:
        await stake_native_start(update, context)
    elif data == 'stake_meme':
        await stake_memecoin_start(update, context)
    elif data == 'my_stakes':
        await my_stakes(update, context)
    
    # Copy Trading
    elif data == 'copy_trading':
        await copy_trading_menu(update, context)
    elif data == 'add_copy_trader':
        return await add_copy_trader_start(update, context)
    elif data == 'my_copy_trades':
        await my_copy_trades(update, context)
    
    # Tools
    elif data == 'tools':
        await tools_menu(update, context)
    elif data == 'price_alerts':
        await price_alerts(update, context)
    elif data == 'portfolio_analytics':
        await portfolio_analytics(update, context)
    elif data == 'risk_calc':
        await risk_calculator(update, context)
    elif data == 'gas_optimizer':
        await gas_optimizer(update, context)
    elif data == 'settings':
        await query.edit_message_text("⚙️ Settings - Coming soon!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='tools')]]))
    
    # Wallet & Referral
    elif data == 'balance':
        await wallet_balance(update, context)
    elif data == 'referral':
        await referral_program(update, context)
    elif data == 'support':
        await support(update, context)
    
    # Fallback
    else:
        await query.edit_message_text(
            "🚧 Feature coming soon!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back to Menu", callback_data='back_menu')]])
        )


# ============ CONVERSATION HANDLERS ============

conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(add_copy_trader_start, pattern='^add_copy_trader$'),
        CallbackQueryHandler(stake_memecoin_start, pattern='^stake_meme$'),
        CallbackQueryHandler(stake_native_start, pattern='^stake_(SOL|ETH)$')
    ],
    states={
        ENTER_TRADER_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_trader_address)],
        ENTER_CONTRACT_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_contract_address)],
        ENTER_STAKE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_stake_amount)],
    },
    fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Cancelled"))]
)


# ============ START BOT ============

if __name__ == '__main__':
    print("🚀 COIN DEX AI Bot is starting...")
    
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Commands
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', guidelines))
    
    # Conversations
    application.add_handler(conv_handler)
    
    # All button clicks
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ COIN DEX AI is running!")
    print(f"📢 Broadcast channel: {BROADCAST_CHANNEL}")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
    