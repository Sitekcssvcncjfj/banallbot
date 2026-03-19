import os
import asyncio
import logging
import time
import random
import datetime
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

# ============================================
# LOGGING
# ============================================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ============================================
# ENV VARIABLES
# ============================================
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

# ============================================
# 🌍 ÇOKLU DİL DESTEĞİ (TR/EN)
# ============================================
TRANSLATIONS = {
    "tr": {
        "welcome": "👋 **Bot Aktif! (Ultimate Sürüm)**\n\nKomutlar için /help yaz.",
        "help": (
            "📖 **Yardım Menüsü**\n\n"
            "🔧 **Yönetim:**\n"
            "/banall - Kalıcı banla (Varsayılan)\n"
            "/banall temp - Herkesi at (Kalıcı değil)\n"
            "/banall date YYYY-MM-DD - Tarih sonrası katılanları banla\n"
            "/banall range min max - ID aralığı banla\n"
            "/unbanall - Tüm banları kaldır\n\n"
            "📊 **Raporlama:**\n"
            "/stats - Gelişmiş grup istatistikleri\n"
            "/history - Son işlemler\n"
            "/exportlog - Logları indir (.txt)\n"
            "/speed - Hız durumu\n\n"
            "⚙️ **Ayarlar:**\n"
            "/lang tr - Türkçe\n"
            "/lang en - İngilizce"
        ),
        "only_admin": "❌ Sadece yöneticiler bu komutu kullanabilir!",
        "no_members": "⚠️ Banlanacak uygun üye bulunamadı.",
        "ban_perm_start": "🔄 **Kalıcı Ban Başlıyor...**",
        "ban_temp_start": "🔄 **Geçici Atma (Kick) Başlıyor...**",
        "unban_start": "🔄 **Banlar Kaldırılıyor...**",
        "stats_header": "📊 **Grup İstatistikleri**",
        "stats_total": "👥 Toplam Üye",
        "stats_admin": "👑 Yönetici",
        "stats_bot": "🤖 Bot",
        "stats_user": "👤 Normal Üye",
        "log_header": "📜 **İşlem Geçmişi**",
        "log_empty": "Henüz işlem yok.",
        "lang_set": "✅ Dil değiştirildi: Türkçe",
        "err_missing_date": "❌ Tarih formatı hatalı. Örnek: /banall date 2023-01-01",
        "err_missing_range": "❌ ID formatı hatalı. Örnek: /banall range 10000 20000",
        "export_msg": "📎 İşlem log dosyası:"
    },
    "en": {
        "welcome": "👋 **Bot Active! (Ultimate Version)**\n\nType /help for commands.",
        "help": (
            "📖 **Help Menu**\n\n"
            "🔧 **Management:**\n"
            "/banall - Permanent ban (Default)\n"
            "/banall temp - Kick everyone (Not permanent)\n"
            "/banall date YYYY-MM-DD - Ban joined after date\n"
            "/banall range min max - Ban ID range\n"
            "/unbanall - Remove all bans\n\n"
            "📊 **Reporting:**\n"
            "/stats - Advanced group stats\n"
            "/history - Recent actions\n"
            "/exportlog - Download logs (.txt)\n"
            "/speed - Speed status\n\n"
            "⚙️ **Settings:**\n"
            "/lang tr - Turkish\n"
            "/lang en - English"
        ),
        "only_admin": "❌ Only admins can use this command!",
        "no_members": "⚠️ No suitable members found to ban.",
        "ban_perm_start": "🔄 **Permanent Ban Starting...**",
        "ban_temp_start": "🔄 **Temporary Kick Starting...**",
        "unban_start": "🔄 **Unbanning...**",
        "stats_header": "📊 **Group Statistics**",
        "stats_total": "👥 Total Members",
        "stats_admin": "👑 Admins",
        "stats_bot": "🤖 Bots",
        "stats_user": "👤 Normal Users",
        "log_header": "📜 **Action History**",
        "log_empty": "No actions yet.",
        "lang_set": "✅ Language changed: English",
        "err_missing_date": "❌ Invalid date format. Ex: /banall date 2023-01-01",
        "err_missing_range": "❌ Invalid ID format. Ex: /banall range 10000 20000",
        "export_msg": "📎 Action log file:"
    }
}

# Kullanıcı dil tercihleri
USER_LANGS = {}

# İşlem Logları (Bellekte tutulur)
ACTION_LOGS = []

def get_text(key, user_id):
    lang = USER_LANGS.get(user_id, "tr")
    return TRANSLATIONS.get(lang, TRANSLATIONS["tr"]).get(key, key)

def add_log(action, details):
    """Log kaydı ekle"""
    ACTION_LOGS.append({
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "details": details
    })
    # Logları 50 ile sınırla
    if len(ACTION_LOGS) > 50:
        ACTION_LOGS.pop(0)

# ============================================
# CLIENT & WEB SERVER
# ============================================
bot = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args): pass

def start_web():
    server = HTTPServer(("0.0.0.0", 8000), HealthHandler)
    server.serve_forever()

# ============================================
# SPEED MANAGER (Previous Logic)
# ============================================
class SpeedManager:
    def __init__(self):
        self.base_delay = 0.15
        self.current_delay = 0.15
    async def wait(self):
        await asyncio.sleep(self.current_delay + random.uniform(-0.02, 0.02))
    def adjust(self, success=True):
        if success:
            self.current_delay = max(0.10, self.current_delay * 0.99)
        else:
            self.current_delay = min(2.0, self.current_delay * 1.5)

speed_mgr = SpeedManager()

# ============================================
# HELPERS
# ============================================
async def is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        status_str = str(member.status).lower()
        return "administrator" in status_str or "owner" in status_str
    except: return False

def parse_date(date_str):
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").timestamp()
    except: return None

# ============================================
# 🚀 COMMANDS: START & HELP
# ============================================
@bot.on_message(filters.command("start"))
async def cmd_start(client, message: Message):
    txt = get_text("welcome", message.from_user.id)
    await message.reply_text(txt)

@bot.on_message(filters.command("help"))
async def cmd_help(client, message: Message):
    txt = get_text("help", message.from_user.id)
    await message.reply_text(txt)

@bot.on_message(filters.command("lang"))
async def cmd_lang(client, message: Message):
    try:
        new_lang = message.command[1]
        if new_lang in ["tr", "en"]:
            USER_LANGS[message.from_user.id] = new_lang
            txt = get_text("lang_set", message.from_user.id)
            await message.reply_text(txt)
    except:
        pass

# ============================================
# 📊 COMMANDS: STATS, HISTORY, SPEED, EXPORT
# ============================================
@bot.on_message(filters.command("stats") & filters.group)
async def cmd_stats(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return
    
    msg = await message.reply_text("🔄 Analiz ediliyor...")
    admins, bots, users = 0, 0, 0
    
    try:
        async for m in client.get_chat_members(message.chat.id):
            if m.user.is_bot: bots += 1
            elif "admin" in str(m.status).lower(): admins += 1
            else: users += 1
    except Exception as e:
        await msg.edit(f"❌ Hata: {e}")
        return

    header = get_text("stats_header", message.from_user.id)
    txt = (
        f"{header}\n\n"
        f"{get_text('stats_total', message.from_user.id)}: **{admins + bots + users}**\n"
        f"{get_text('stats_admin', message.from_user.id)}: **{admins}**\n"
        f"{get_text('stats_bot', message.from_user.id)}: **{bots}**\n"
        f"{get_text('stats_user', message.from_user.id)}: **{users}**"
    )
    await msg.edit(txt)

@bot.on_message(filters.command("history") & filters.group)
async def cmd_history(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    
    header = get_text("log_header", message.from_user.id)
    empty = get_text("log_empty", message.from_user.id)
    
    if not ACTION_LOGS:
        return await message.reply_text(empty)
    
    txt = f"{header}\n\n"
    for log in ACTION_LOGS[-10:]: # Son 10
        txt += f"🕒 {log['time']}\n🔹 {log['action']}: {log['details']}\n\n"
    
    await message.reply_text(txt)

@bot.on_message(filters.command("exportlog") & filters.group)
async def cmd_export(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id): return
    
    if not ACTION_LOGS:
        return await message.reply_text(get_text("log_empty", message.from_user.id))
    
    txt_content = ""
    for log in ACTION_LOGS:
        txt_content += f"{log['time']} - {log['action']} - {log['details']}\n"
    
    msg_header = get_text("export_msg", message.from_user.id)
    await message.reply_document(
        file_name=f"logs_{int(time.time())}.txt",
        document=txt_content.encode(),
        caption=msg_header
    )

@bot.on_message(filters.command("speed"))
async def cmd_speed(client, message: Message):
    txt = (
        f"⚡ **Speed Stats**\n\n"
        f"🏎️ Delay: {speed_mgr.current_delay:.2f}s\n"
        f"📊 Speed: ~{round(1/speed_mgr.current_delay, 1)} ban/s"
    )
    await message.reply_text(txt)

# ============================================
# 🚀 BANALL (Ultimate Logic)
# ============================================
@bot.on_message(filters.command("banall") & filters.group)
async def cmd_banall(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    lang = USER_LANGS.get(user_id, "tr")

    # Admin Check
    if not await is_admin(client, chat_id, user_id):
        return await message.reply_text(get_text("only_admin", user_id))

    # Args Parsing
    args = message.command
    mode = "perm" # Default
    filter_type = None # date, range
    filter_val = None

    if "temp" in args:
        mode = "temp"
    if "date" in args:
        try:
            date_idx = args.index("date")
            date_str = args[date_idx + 1]
            filter_val = parse_date(date_str)
            filter_type = "date"
        except:
            return await message.reply_text(get_text("err_missing_date", user_id))
    if "range" in args:
        try:
            range_idx = args.index("range")
            min_id = int(args[range_idx + 1])
            max_id = int(args[range_idx + 2])
            filter_val = (min_id, max_id)
            filter_type = "range"
        except:
            return await message.reply_text(get_text("err_missing_range", user_id))

    # Status Message
    start_txt = get_text("ban_perm_start", user_id) if mode == "perm" else get_text("ban_temp_start", user_id)
    status = await message.reply_text(f"{start_txt}\n🔄 Üyeler taranıyor...")

    # Collect & Filter
    users_to_ban = []
    skipped = 0
    total = 0
    
    try:
        async for m in client.get_chat_members(chat_id):
            total += 1
            u = m.user
            
            # Basit Filtreler
            if u.is_bot or u.id == user_id or ("admin" in str(m.status).lower()):
                skipped += 1
                continue
            
            # Gelişmiş Filtreler
            passed = True
            if filter_type == "date" and m.joined_date:
                if m.joined_date < filter_val: passed = False
            elif filter_type == "range":
                if not (filter_val[0] <= u.id <= filter_val[1]): passed = False
            
            if passed:
                users_to_ban.append(u)

    except Exception as e:
        return await status.edit(f"❌ Listeleme Hatası: {e}")

    if not users_to_ban:
        return await status.edit(get_text("no_members", user_id))

    # Execute Ban
    banned = 0
    failed = 0
    start_t = time.time()
    
    await status.edit(
        f"{start_txt}\n"
        f"📊 Hedef: {len(users_to_ban)}\n"
        f"🏷️ Mod: {mode} | {filter_type}"
    )

    for u in users_to_ban:
        try:
            await client.ban_chat_member(chat_id, u.id)
            
            # If Temp, immediately unban
            if mode == "temp":
                await client.unban_chat_member(chat_id, u.id)
            
            banned += 1
            speed_mgr.adjust(True)
            log.info(f"Banned: {u.first_name} ({u.id})")

        except FloodWait as e:
            log.warning(f"FloodWait {e.value}s")
            await asyncio.sleep(e.value)
            speed_mgr.adjust(False)
            try: # Retry
                await client.ban_chat_member(chat_id, u.id)
                if mode == "temp": await client.unban_chat_member(chat_id, u.id)
                banned += 1
            except: failed += 1
        except Exception as e:
            failed += 1
            log.error(f"Error: {e}")
            speed_mgr.adjust(False)

        await speed_mgr.wait()

        # İlerleme Mesajı (Her 10 kişide)
        if banned % 10 == 0:
            try:
                await status.edit(
                    f"{start_txt}\n"
                    f"✅ Tamamlandı: {banned}/{len(users_to_ban)}\n"
                    f"❌ Hata: {failed}"
                )
            except: pass

    # Log Kaydı
    add_log("BANALL", f"Mode: {mode}, Filter: {filter_type}, Banned: {banned}, Failed: {failed}")
    
    # Final
    elapsed = round(time.time() - start_t, 1)
    await status.edit(
        f"✅ **İŞLEM TAMAMLANDI!**\n\n"
        f"🚫 {mode.upper()}: {banned} kişi\n"
        f"❌ Hata: {failed} kişi\n"
        f"⏱️ Süre: {elapsed} saniye"
    )

# ============================================
# 📋 UNBANALL
# ============================================
@bot.on_message(filters.command("unbanall") & filters.group)
async def cmd_unbanall(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_admin(client, chat_id, user_id):
        return await message.reply_text(get_text("only_admin", user_id))

    status = await message.reply_text(get_text("unban_start", user_id))
    unbanned = 0
    failed = 0

    try:
        async for m in client.get_chat_members(chat_id):
            if "banned" in str(m.status).lower():
                try:
                    await client.unban_chat_member(chat_id, m.user.id)
                    unbanned += 1
                except FloodWait:
                    await asyncio.sleep(5)
                    try:
                        await client.unban_chat_member(chat_id, m.user.id)
                        unbanned += 1
                    except: failed += 1
                except: failed += 1
            
            if unbanned % 10 == 0:
                await asyncio.sleep(1)

        add_log("UNBANALL", f"Unbanned: {unbanned}, Failed: {failed}")
        await status.edit(
            f"✅ **Tamamlandı!**\n\n"
            f"🟢 Kaldırılan: {unbanned}\n"
            f"❌ Başarısız: {failed}"
        )

    except Exception as e:
        await status.edit(f"❌ Hata: {e}")

# ============================================
# 🛡️ SELF PROTECTION (Error Catcher)
# ============================================
@bot.on_message()
async def error_catcher(client, message: Message):
    # Hataları yakalayıp logla, bot çökmesin
    pass

# ============================================
# MAIN
# ============================================
if __name__ == "__main__":
    try:
        Thread(target=start_web, daemon=True).start()
        log.info("🚀 Bot Başlatılıyor (Ultimate Sürüm)...")
        bot.run()
    except KeyboardInterrupt:
        log.info("Bot durduruldu.")
    except Exception as e:
        log.critical(f"CRITICAL ERROR: {e}")
        # Hata durumunda yeniden başlatma mekanizması için Railway restart'ı bekler
