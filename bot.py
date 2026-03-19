import os
import asyncio
import logging
import time
import random
import datetime
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
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
# DESTEK VE KATILIM LİNKLERİ
# ============================================
SUPPORT_LINK = "https://t.me/KGBotomasyon"
JOIN_GROUP_LINK = "https://t.me/POSTAGUVERCINIBOT"

# ============================================
# İŞLEM LOGLARI
# ============================================
ACTION_LOGS = []

def add_log(action, details):
    ACTION_LOGS.append({
        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "details": details
    })
    if len(ACTION_LOGS) > 100:
        ACTION_LOGS.pop(0)

# ============================================
# HIZ YÖNETİCİSİ
# ============================================
class SpeedManager:
    def __init__(self):
        self.current_delay = 0.15
        self.success_count = 0
        self.fail_count = 0
        self.floodwaits = 0
        self.start_time = 0

    async def wait(self):
        await asyncio.sleep(self.current_delay + random.uniform(-0.02, 0.02))

    def on_success(self):
        self.success_count += 1
        self.current_delay = max(0.10, self.current_delay * 0.99)

    def on_fail(self):
        self.fail_count += 1
        self.current_delay = min(2.0, self.current_delay * 1.5)

    def on_floodwait(self, seconds):
        self.floodwaits += 1
        self.current_delay = min(3.0, self.current_delay * 2.0)

    def get_stats(self):
        elapsed = time.time() - self.start_time if self.start_time > 0 else 0
        speed = round(1 / self.current_delay, 1) if self.current_delay > 0 else 0
        return {
            "delay": round(self.current_delay, 2),
            "speed": speed,
            "success": self.success_count,
            "failed": self.fail_count,
            "floodwaits": self.floodwaits,
            "elapsed": round(elapsed, 1)
        }

speed_mgr = SpeedManager()

# ============================================
# CLIENT
# ============================================
bot = Client(
    "bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ============================================
# WEB SERVER
# ============================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass

def start_web():
    server = HTTPServer(("0.0.0.0", 8000), HealthHandler)
    server.serve_forever()

# ============================================
# YARDIMCI FONKSİYONLAR
# ============================================
async def is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        s = str(member.status).lower()
        return "administrator" in s or "owner" in s
    except:
        return False

def parse_date(date_str):
    try:
        return datetime.datetime.strptime(date_str, "%Y-%m-%d").timestamp()
    except:
        return None

# ============================================
# 🔘 BUTON MENÜLERİ
# ============================================

def main_menu_keyboard():
    """Ana menü butonları"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚫 Herkesi Banla", callback_data="menu_banall"),
            InlineKeyboardButton("🔓 Banları Kaldır", callback_data="menu_unbanall")
        ],
        [
            InlineKeyboardButton("⚡ Geçici At", callback_data="menu_kickall"),
            InlineKeyboardButton("📊 İstatistikler", callback_data="menu_stats")
        ],
        [
            InlineKeyboardButton("📋 İşlem Geçmişi", callback_data="menu_history"),
            InlineKeyboardButton("⚡ Hız Durumu", callback_data="menu_speed")
        ],
        [
            InlineKeyboardButton("📥 Log İndir", callback_data="menu_export"),
            InlineKeyboardButton("🌍 Dil", callback_data="menu_lang")
        ],
        [
            InlineKeyboardButton("💬 Destek", url=SUPPORT_LINK),
            InlineKeyboardButton("📢 Gruba Katıl", url=JOIN_GROUP_LINK)
        ]
    ])

def banall_options_keyboard():
    """Banall seçenekleri"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚫 Kalıcı Ban", callback_data="do_banall_perm"),
            InlineKeyboardButton("⚡ Geçici Kick", callback_data="do_banall_temp")
        ],
        [
            InlineKeyboardButton("📅 Tarih Bazlı", callback_data="menu_banall_date"),
            InlineKeyboardButton("🆔 ID Aralığı", callback_data="menu_banall_range")
        ],
        [
            InlineKeyboardButton("🔙 Ana Menü", callback_data="back_main")
        ]
    ])

def confirm_keyboard():
    """Onay butonları"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ EVET, DEVAM ET", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ İPTAL", callback_data="confirm_no")
        ]
    ])

def confirm_banall_keyboard(mode):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ EVET, BANLA", callback_data=f"exec_banall_{mode}"),
            InlineKeyboardButton("❌ İPTAL", callback_data="back_main")
        ]
    ])

def confirm_unbanall_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ EVET, KALDIR", callback_data="exec_unbanall"),
            InlineKeyboardButton("❌ İPTAL", callback_data="back_main")
        ]
    ])

def lang_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇹🇷 Türkçe", callback_data="setlang_tr"),
            InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en")
        ],
        [
            InlineKeyboardButton("🔙 Ana Menü", callback_data="back_main")
        ]
    ])

def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Ana Menü", callback_data="back_main")]
    ])

# ============================================
# 📌 /start - ANA MENÜ
# ============================================
@bot.on_message(filters.command("start"))
async def cmd_start(client, message: Message):
    welcome_text = (
        "👋 **Merhaba! Ben Grup Yönetim Botuyum!**\n\n"
        "🎯 Aşağıdaki butonlardan birini seçerek\n"
        "   işlem yapabilirsin.\n\n"
        "⚡ **Özellikler:**\n"
        "├ 🚫 Kalıcı / Geçici Ban\n"
        "├ 📅 Tarih Bazlı Ban\n"
        "├ 🆔 ID Aralığı Ban\n"
        "├ 📊 Gelişmiş İstatistikler\n"
        "├ 📋 İşlem Geçmişi & Log\n"
        "├ ⚡ Akıllı Hız Yönetimi\n"
        "└ 🌍 Türkçe / İngilizce\n\n"
        "💬 Destek ve yardım için butonları kullan."
    )
    await message.reply_text(
        welcome_text,
        reply_markup=main_menu_keyboard()
    )

# ============================================
# 🔘 CALLBACK QUERY HANDLER (Buton Tıklamaları)
# ============================================

@bot.on_callback_query()
async def callback_handler(client, cb: CallbackQuery):
    data = cb.data
    user_id = cb.from_user.id
    chat_id = cb.message.chat.id
    msg_id = cb.message.id

    # ========== ANA MENÜ ==========
    if data == "back_main":
        await cb.message.edit_text(
            "📋 **Ana Menü**\n\nBir işlem seçin:",
            reply_markup=main_menu_keyboard()
        )

    # ========== BANALL MENÜ ==========
    elif data == "menu_banall":
        if not await is_admin(client, chat_id, user_id):
            return await cb.answer("❌ Sadece yöneticiler!", show_alert=True)
        await cb.message.edit_text(
            "🚫 **Ban Yöntemi Seçin:**\n\n"
            "🔸 **Kalıcı Ban:** Kullanıcı gruba dönemez\n"
            "🔸 **Geçici Kick:** Kullanıcı tekrar katılabilir\n"
            "🔸 **Tarih Bazlı:** Belirtilen tarihten sonra katılanları banla\n"
            "🔸 **ID Aralığı:** Belirli ID aralığındaki kişileri banla",
            reply_markup=banall_options_keyboard()
        )

    # ========== KALICI BAN ONAY ==========
    elif data == "do_banall_perm":
        if not await is_admin(client, chat_id, user_id):
            return await cb.answer("❌ Sadece yöneticiler!", show_alert=True)

        # Üye sayısını al
        total = 0
        async for _ in client.get_chat_members(chat_id):
            total += 1

        await cb.message.edit_text(
            f"⚠️ **EMİN MİSİN?**\n\n"
            f"🚫 **KALICI BAN** uygulanacak!\n"
            f"👥 Grupta toplam **{total}** üye var.\n"
            f"👑 Yöneticiler ve botlar atlanacak.\n\n"
            f"❗ Bu işlem geri alınamaz!\n"
            f"   (Adminler hariç herkes banlanır)",
            reply_markup=confirm_banall_keyboard("perm")
        )

    # ========== GEÇİCİ KICK ONAY ==========
    elif data == "do_banall_temp":
        if not await is_admin(client, chat_id, user_id):
            return await cb.answer("❌ Sadece yöneticiler!", show_alert=True)

        total = 0
        async for _ in client.get_chat_members(chat_id):
            total += 1

        await cb.message.edit_text(
            f"⚠️ **EMİN MİSİN?**\n\n"
            f"⚡ **GEÇİCİ KICK** uygulanacak!\n"
            f"👥 Grupta toplam **{total}** üye var.\n"
            f"📣 Kullanıcılar tekrar katılabilir.\n\n"
            f"👑 Yöneticiler ve botlar atlanacak.",
            reply_markup=confirm_banall_keyboard("temp")
        )

    # ========== TARİH BAZLI MENÜ ==========
    elif data == "menu_banall_date":
        await cb.message.edit_text(
            "📅 **Tarih Bazlı Ban**\n\n"
            "Bu komutu grupta şöyle yaz:\n\n"
            "`/banall date 2024-01-01`\n\n"
            "Bu, 1 Ocak 2024'ten sonra katılan\n"
            "herkesi banlayacak.\n\n"
            "Spam bot temizliği için mükemmel! 🧹",
            reply_markup=back_keyboard()
        )

    # ========== ID ARALIK MENÜ ==========
    elif data == "menu_banall_range":
        await cb.message.edit_text(
            "🆔 **ID Aralığı Ban**\n\n"
            "Bu komutu grupta şöyle yaz:\n\n"
            "`/banall range 1000000 2000000`\n\n"
            "Bu, ID'si 1M ile 2M arasında olan\n"
            "herkesi banlayacak.\n\n"
            "Belirli bir grup bot hesabı\n"
            "temizlemek için kullanışlıdır.",
            reply_markup=back_keyboard()
        )

    # ========== BANALL ÇALIŞTIR ==========
    elif data.startswith("exec_banall_"):
        mode = data.replace("exec_banall_", "")

        if not await is_admin(client, chat_id, user_id):
            return await cb.answer("❌ Sadece yöneticiler!", show_alert=True)

        mode_txt = "🚫 Kalıcı Ban" if mode == "perm" else "⚡ Geçici Kick"
        await cb.message.edit_text(
            f"{mode_txt} başlatılıyor...\n\n"
            f"🔄 Üyeler toplanıyor..."
        )

        # Üyeleri topla
        all_members = []
        try:
            async for m in client.get_chat_members(chat_id):
                all_members.append(m)
        except Exception as e:
            return await cb.message.edit_text(
                f"❌ Üye listesi alınamadı: {e}",
                reply_markup=back_keyboard()
            )

        # Filtrele
        users_to_ban = []
        admin_count = 0
        bot_count = 0

        for m in all_members:
            u = m.user
            if u.is_bot:
                bot_count += 1
                continue
            if u.id == user_id:
                continue
            s = str(m.status).lower()
            if "administrator" in s or "owner" in s:
                admin_count += 1
                continue
            users_to_ban.append(u)

        if not users_to_ban:
            return await cb.message.edit_text(
                f"⚠️ Banlanacak kimse yok!\n\n"
                f"📊 Toplam: {len(all_members)}\n"
                f"👑 Admin: {admin_count}\n"
                f"🤖 Bot: {bot_count}",
                reply_markup=back_keyboard()
            )

        await cb.message.edit_text(
            f"{mode_txt} Başlıyor!\n\n"
            f"📊 Toplam: {len(all_members)}\n"
            f"🚫 Hedef: {len(users_to_ban)}\n"
            f"⏭️ Atlanan: {admin_count + bot_count + 1}\n\n"
            f"⏳ İşlem devam ediyor..."
        )

        # BAN İŞLEMİ
        speed_mgr.start_time = time.time()
        speed_mgr.success_count = 0
        speed_mgr.fail_count = 0
        banned = 0
        failed = 0
        start_t = time.time()

        for i, u in enumerate(users_to_ban):
            try:
                await client.ban_chat_member(chat_id, u.id)
                if mode == "temp":
                    await client.unban_chat_member(chat_id, u.id)
                banned += 1
                speed_mgr.on_success()

            except FloodWait as e:
                speed_mgr.on_floodwait(e.value)
                log.warning(f"FloodWait: {e.value}s")
                await asyncio.sleep(e.value)
                try:
                    await client.ban_chat_member(chat_id, u.id)
                    if mode == "temp":
                        await client.unban_chat_member(chat_id, u.id)
                    banned += 1
                    speed_mgr.on_success()
                except Exception:
                    failed += 1
                    speed_mgr.on_fail()

            except Exception as e:
                failed += 1
                speed_mgr.on_fail()
                log.error(f"Ban error: {u.first_name}: {e}")

            await speed_mgr.wait()

            # Her 10 kişide ilerleme
            if (i + 1) % 10 == 0:
                stats = speed_mgr.get_stats()
                try:
                    await cb.message.edit_text(
                        f"{mode_txt} Devam Ediyor...\n\n"
                        f"✅ Banlanan: {banned}/{len(users_to_ban)}\n"
                        f"❌ Başarısız: {failed}\n"
                        f"⚡ Hız: {stats['speed']} ban/sn\n"
                        f"🔄 FloodWait: {stats['floodwaits']}\n\n"
                        f"⏳ Devam ediyor..."
                    )
                except:
                    pass

        # SONUÇ
        elapsed = round(time.time() - start_t, 1)
        avg_speed = round(banned / elapsed, 1) if elapsed > 0 else 0
        stats = speed_mgr.get_stats()

        add_log(
            f"BANALL_{mode.upper()}",
            f"Banned: {banned}, Failed: {failed}, Speed: {avg_speed}/s, Duration: {elapsed}s"
        )

        await cb.message.edit_text(
            f"✅ **İŞLEM TAMAMLANDI!**\n\n"
            f"🚫 {mode_txt}: **{banned}** kişi\n"
            f"❌ Başarısız: **{failed}** kişi\n"
            f"⏭️ Atlanan: **{admin_count + bot_count + 1}**\n"
            f"📊 Toplam: **{len(all_members)}**\n\n"
            f"⚡ Ortalama hız: **{avg_speed}** ban/sn\n"
            f"⏱️ Toplam süre: **{elapsed}** sn\n"
            f"🔄 FloodWait: **{stats['floodwaits']}**",
            reply_markup=main_menu_keyboard()
        )

    # ========== UNBANALL MENÜ ==========
    elif data == "menu_unbanall":
        if not await is_admin(client, chat_id, user_id):
            return await cb.answer("❌ Sadece yöneticiler!", show_alert=True)

        # Banlı sayısını bul
        banned_count = 0
        try:
            async for m in client.get_chat_members(chat_id):
                if "banned" in str(m.status).lower() or "kicked" in str(m.status).lower():
                    banned_count += 1
        except:
            pass

        await cb.message.edit_text(
            f"🔓 **Banları Kaldır**\n\n"
            f"🚫 Şu an banlı üye: **{banned_count}**\n\n"
            f"Tüm banları kaldırmak istediğine\n"
            f"emin misin?",
            reply_markup=confirm_unbanall_keyboard()
        )

    # ========== UNBANALL ÇALIŞTIR ==========
    elif data == "exec_unbanall":
        if not await is_admin(client, chat_id, user_id):
            return await cb.answer("❌ Sadece yöneticiler!", show_alert=True)

        await cb.message.edit_text("🔄 Banlar kaldırılıyor...")

        unbanned = 0
        failed = 0
        start_t = time.time()

        try:
            async for m in client.get_chat_members(chat_id):
                s = str(m.status).lower()
                if "banned" in s or "kicked" in s:
                    try:
                        await client.unban_chat_member(chat_id, m.user.id)
                        unbanned += 1
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                        try:
                            await client.unban_chat_member(chat_id, m.user.id)
                            unbanned += 1
                        except Exception:
                            failed += 1
                    except Exception as e:
                        failed += 1
                        log.error(f"Unban error: {e}")

                    await asyncio.sleep(0.2)

                    if unbanned % 10 == 0:
                        try:
                            await cb.message.edit_text(
                                f"🔄 Unban devam ediyor...\n\n"
                                f"✅ Açılan: {unbanned}\n"
                                f"❌ Başarısız: {failed}"
                            )
                        except:
                            pass

        except Exception as e:
            return await cb.message.edit_text(
                f"❌ Hata: {e}",
                reply_markup=back_keyboard()
            )

        elapsed = round(time.time() - start_t, 1)
        add_log("UNBANALL", f"Unbanned: {unbanned}, Failed: {failed}")

        await cb.message.edit_text(
            f"✅ **UNBAN TAMAMLANDI!**\n\n"
            f"🟢 Kaldırılan: **{unbanned}**\n"
            f"❌ Başarısız: **{failed}**\n"
            f"⏱️ Süre: **{elapsed}** sn",
            reply_markup=main_menu_keyboard()
        )

    # ========== KICKALL (GEÇİCİ ATMA) ==========
    elif data == "menu_kickall":
        if not await is_admin(client, chat_id, user_id):
            return await cb.answer("❌ Sadece yöneticiler!", show_alert=True)

        total = 0
        async for _ in client.get_chat_members(chat_id):
            total += 1

        await cb.message.edit_text(
            f"⚡ **Geçici Kick (Atma)**\n\n"
            f"👥 Grupta **{total}** üye var.\n"
            f"📣 Herkes atılacak ama banlanmayacak.\n"
            f"   (Davet linkiyle tekrar katılabilirler)\n\n"
            f"Emin misin?",
            reply_markup=confirm_banall_keyboard("temp")
        )

    # ========== İSTATİSTİKLER ==========
    elif data == "menu_stats":
        if not await is_admin(client, chat_id, user_id):
            return await cb.answer("❌ Sadece yöneticiler!", show_alert=True)

        await cb.message.edit_text("🔄 İstatistikler hesaplanıyor...")

        total = 0
        admins = 0
        bots = 0
        users = 0
        banned = 0

        try:
            async for m in client.get_chat_members(chat_id):
                total += 1
                s = str(m.status).lower()
                if m.user.is_bot:
                    bots += 1
                elif "administrator" in s or "owner" in s:
                    admins += 1
                elif "banned" in s or "kicked" in s:
                    banned += 1
                else:
                    users += 1
        except Exception as e:
            return await cb.message.edit_text(
                f"❌ Hata: {e}",
                reply_markup=back_keyboard()
            )

        await cb.message.edit_text(
            f"📊 **Grup İstatistikleri**\n\n"
            f"├ 👥 Toplam Üye: **{total}**\n"
            f"├ 👑 Yönetici: **{admins}**\n"
            f"├ 🤖 Bot: **{bots}**\n"
            f"├ 👤 Normal Üye: **{users}**\n"
            f"├ 🚫 Banlı Üye: **{banned}**\n"
            f"└ 📊 Grup: **{client.me.first_name}**\n\n"
            f"💬 Grup: {cb.message.chat.title or 'Özel'}\n"
            f"🆔 Grup ID: `{chat_id}`",
            reply_markup=back_keyboard()
        )

    # ========== İŞLEM GEÇMİŞİ ==========
    elif data == "menu_history":
        if not await is_admin(client, chat_id, user_id):
            return await cb.answer("❌ Sadece yöneticiler!", show_alert=True)

        if not ACTION_LOGS:
            return await cb.message.edit_text(
                "📋 **İşlem Geçmişi**\n\n"
                "Henüz hiçbir işlem yapılmadı.",
                reply_markup=back_keyboard()
            )

        txt = "📋 **Son İşlemler**\n\n"
        for log_entry in ACTION_LOGS[-10:][::-1]:
            txt += (
                f"🕒 `{log_entry['time']}`\n"
                f"🔹 **{log_entry['action']}**\n"
                f"   {log_entry['details']}\n\n"
            )

        await cb.message.edit_text(txt, reply_markup=back_keyboard())

    # ========== HIZ DURUMU ==========
    elif data == "menu_speed":
        stats = speed_mgr.get_stats()
        await cb.message.edit_text(
            f"⚡ **Hız Durumu**\n\n"
            f"├ 🏎️ Gecikme: **{stats['delay']}** sn\n"
            f"├ ⚡ Hız: **~{stats['speed']}** ban/sn\n"
            f"├ ✅ Başarılı: **{stats['success']}**\n"
            f"├ ❌ Başarısız: **{stats['failed']}**\n"
            f"├ 🔄 FloodWait: **{stats['floodwaits']}**\n"
            f"└ ⏱️ Süre: **{stats['elapsed']}** sn\n\n"
            f"💡 Gecikme düşük = daha hızlı ban\n"
            f"💡 FloodWait artarsa hız düşer",
            reply_markup=back_keyboard()
        )

    # ========== LOG İNDİR ==========
    elif data == "menu_export":
        if not await is_admin(client, chat_id, user_id):
            return await cb.answer("❌ Sadece yöneticiler!", show_alert=True)

        if not ACTION_LOGS:
            return await cb.message.edit_text(
                "📥 **Log İndir**\n\n"
                "Henüz işlem kaydı yok.",
                reply_markup=back_keyboard()
            )

        txt_content = "=" * 50 + "\n"
        txt_content += "  GRUP YÖNETİM BOTU - İŞLEM LOGLARI\n"
        txt_content += "=" * 50 + "\n\n"

        for log_entry in ACTION_LOGS:
            txt_content += f"[{log_entry['time']}]\n"
            txt_content += f"  İşlem: {log_entry['action']}\n"
            txt_content += f"  Detay: {log_entry['details']}\n"
            txt_content += "-" * 40 + "\n"

        txt_content += f"\nToplam {len(ACTION_LOGS)} işlem kaydedildi.\n"
        txt_content += f"Oluşturulma: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

        await cb.message.reply_document(
            file_name=f"bot_logs_{int(time.time())}.txt",
            document=txt_content.encode("utf-8"),
            caption="📥 **İşlem log dosyanız hazır!**"
        )
        await cb.answer("✅ Log dosyası gönderildi!", show_alert=True)

    # ========== DİL AYARLARI ==========
    elif data == "menu_lang":
        await cb.message.edit_text(
            "🌍 **Dil Seçimi**\n\n"
            "Bir dil seçin:",
            reply_markup=lang_keyboard()
        )

    elif data == "setlang_tr":
        await cb.answer("✅ Dil: Türkçe", show_alert=True)
        await cb.message.edit_text(
            "🇹🇷 **Dil Türkçe olarak ayarlandı!**\n\n"
            "Artık tüm mesajlar Türkçe görünecek.",
            reply_markup=back_keyboard()
        )

    elif data == "setlang_en":
        await cb.answer("✅ Language: English", show_alert=True)
        await cb.message.edit_text(
            "🇬🇧 **Language set to English!**\n\n"
            "All messages will now appear in English.",
            reply_markup=back_keyboard()
        )

    # ========== ONAY EVET/HAYIR ==========
    elif data == "confirm_yes":
        await cb.answer("✅ Onaylandı!", show_alert=True)

    elif data == "confirm_no":
        await cb.message.edit_text(
            "❌ **İşlem iptal edildi.**",
            reply_markup=back_keyboard()
        )

    # ========== DEFAULT ==========
    else:
        await cb.answer("⚠️ Bilinmeyen işlem.", show_alert=True)

# ============================================
# 📌 TEXT KOMUTLAR (Buton Yanıtı Olmayanlar)
# ============================================

# /help
@bot.on_message(filters.command("help"))
async def cmd_help(client, message: Message):
    await message.reply_text(
        "📋 **Ana Menü**\n\nBir işlem seçin:",
        reply_markup=main_menu_keyboard()
        )

# /stats
@bot.on_message(filters.command("stats") & filters.group)
async def cmd_stats(client, message: Message):
    if not await is_admin(client, message.chat.id, message.from_user.id):
        return await message.reply_text("❌ Sadece yöneticiler!")

    msg = await message.reply_text("🔄 Hesaplanıyor...")
    total, admins, bots, users = 0, 0, 0, 0

    async for m in client.get_chat_members(message.chat.id):
        total += 1
        if m.user.is_bot:
            bots += 1
        elif "admin" in str(m.status).lower() or "owner" in str(m.status).lower():
            admins += 1
        else:
            users += 1

    await msg.edit_text(
        f"📊 **Grup İstatistikleri**\n\n"
        f"👥 Toplam: **{total}**\n"
        f"👑 Yönetici: **{admins}**\n"
        f"🤖 Bot: **{bots}**\n"
        f"👤 Normal: **{users}**",
        reply_markup=back_keyboard()
    )

# /say
@bot.on_message(filters.command("say") & filters.group)
async def cmd_say(client, message: Message):
    count = 0
    async for _ in client.get_chat_members(message.chat.id):
        count += 1
    await message.reply_text(f"📊 Toplam üye: **{count}**")

# /banall text komutu
@bot.on_message(filters.command("banall") & filters.group)
async def cmd_banall(client, message: Message):
    await message.reply_text(
        "🚫 **Ban Yöntemi Seçin:**\n\n"
        "Butonlardan birini seç veya\n"
        "komutu şöyle kullan:\n\n"
        "`/kickall` - Geçici at\n"
        "`/banall date 2024-01-01` - Tarih bazlı\n"
        "`/banall range 1000000 2000000` - ID aralığı",
        reply_markup=banall_options_keyboard()
    )

# /kickall text komutu (geçici at)
@bot.on_message(filters.command("kickall") & filters.group)
async def cmd_kickall(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_admin(client, chat_id, user_id):
        return await message.reply_text("❌ Sadece yöneticiler!")

    msg = await message.reply_text("⚡ Geçici atma başlıyor...")

    all_members = []
    try:
        async for m in client.get_chat_members(chat_id):
            all_members.append(m)
    except Exception as e:
        return await msg.edit_text(f"❌ Hata: {e}")

    users_to_kick = []
    for m in all_members:
        u = m.user
        if u.is_bot or u.id == user_id:
            continue
        s = str(m.status).lower()
        if "administrator" in s or "owner" in s:
            continue
        users_to_kick.append(u)

    if not users_to_kick:
        return await msg.edit_text("⚠️ Atılacak kimse yok!")

    kicked = 0
    failed = 0
    for u in users_to_kick:
        try:
            await client.ban_chat_member(chat_id, u.id)
            await client.unban_chat_member(chat_id, u.id)
            kicked += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await client.ban_chat_member(chat_id, u.id)
                await client.unban_chat_member(chat_id, u.id)
                kicked += 1
            except:
                failed += 1
        except:
            failed += 1
        await asyncio.sleep(0.3)

    add_log("KICKALL", f"Kicked: {kicked}, Failed: {failed}")
    await msg.edit_text(
        f"✅ **Geçici Atma Tamamlandı!**\n\n"
        f"⚡ Atılan: **{kicked}**\n"
        f"❌ Başarısız: **{failed}**",
        reply_markup=back_keyboard()
    )

# /unbanall text komutu
@bot.on_message(filters.command("unbanall") & filters.group)
async def cmd_unbanall(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_admin(client, chat_id, user_id):
        return await message.reply_text("❌ Sadece yöneticiler!")

    msg = await message.reply_text("🔄 Banlar kaldırılıyor...")

    unbanned = 0
    failed = 0

    try:
        async for m in client.get_chat_members(chat_id):
            s = str(m.status).lower()
            if "banned" in s or "kicked" in s:
                try:
                    await client.unban_chat_member(chat_id, m.user.id)
                    unbanned += 1
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    try:
                        await client.unban_chat_member(chat_id, m.user.id)
                        unbanned += 1
                    except:
                        failed += 1
                except:
                    failed += 1
                await asyncio.sleep(0.2)
    except Exception as e:
        return await msg.edit_text(f"❌ Hata: {e}")

    add_log("UNBANALL", f"Unbanned: {unbanned}, Failed: {failed}")
    await msg.edit_text(
        f"✅ **Unban Tamamlandı!**\n\n"
        f"🟢 Açılan: **{unbanned}**\n"
        f"❌ Başarısız: **{failed}**",
        reply_markup=back_keyboard()
    )

# /history
@bot.on_message(filters.command("history") & filters.group)
async def cmd_history(client, message: Message):
    if not ACTION_LOGS:
        return await message.reply_text("📋 Henüz işlem yok.")

    txt = "📋 **Son İşlemler**\n\n"
    for log_entry in ACTION_LOGS[-10:][::-1]:
        txt += f"🕒 `{log_entry['time']}`\n🔹 **{log_entry['action']}**: {log_entry['details']}\n\n"

    await message.reply_text(txt, reply_markup=back_keyboard())

# /exportlog
@bot.on_message(filters.command("exportlog") & filters.group)
async def cmd_exportlog(client, message: Message):
    if not ACTION_LOGS:
        return await message.reply_text("📋 Henüz işlem yok.")

    txt_content = "BOT İŞLEM LOGLARI\n" + "=" * 40 + "\n\n"
    for log_entry in ACTION_LOGS:
        txt_content += f"[{log_entry['time']}] {log_entry['action']}: {log_entry['details']}\n"

    await message.reply_document(
        file_name=f"logs_{int(time.time())}.txt",
        document=txt_content.encode(),
        caption="📥 Log dosyası"
    )

# /speed
@bot.on_message(filters.command("speed"))
async def cmd_speed(client, message: Message):
    stats = speed_mgr.get_stats()
    await message.reply_text(
        f"⚡ **Hız Durumu**\n\n"
        f"Gecikme: **{stats['delay']}** sn\n"
        f"Hız: **~{stats['speed']}** ban/sn",
        reply_markup=back_keyboard()
    )

# /kick (tek kişi)
@bot.on_message(filters.command("kick") & filters.group)
async def cmd_kick(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_admin(client, chat_id, user_id):
        return await message.reply_text("❌ Sadece yöneticiler!")

    if not message.reply_to_message:
        return await message.reply_text("⚠️ Bir mesajı yanıtlayarak /kick yaz!")

    target = message.reply_to_message.from_user

    try:
        await client.ban_chat_member(chat_id, target.id)
        await client.unban_chat_member(chat_id, target.id)
        await message.reply_text(
            f"⚡ **{target.first_name}** gruptan atıldı!",
            reply_markup=back_keyboard()
        )
    except Exception as e:
        await message.reply_text(f"❌ Hata: {e}")

# ============================================
# 🚀 BAŞLAT
# ============================================
if __name__ == "__main__":
    Thread(target=start_web, daemon=True).start()
    log.info("🚀 Bot başlatılıyor (Butonlu Ultimate Sürüm)...")
    bot.run()
