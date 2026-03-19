import os
import asyncio
import logging
import time
import random
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
# CLIENT
# ============================================
bot = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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
# ⚡ DİNAMİK HIZ YÖNETİCİSİ
# ============================================
class SpeedManager:
    """
    Telegram'ın limitlerine göre hızı otomatik ayarlar.
    FloodWait yemeden maksimum hızda çalışır.
    """

    def __init__(self):
        self.base_delay = 0.15          # Başlangıç hızı (saniye)
        self.min_delay = 0.10           # En hızlı (saniye)
        self.max_delay = 2.0            # En yavaş (saniye)
        self.current_delay = 0.15       # Şu anki hız
        self.consecutive_ok = 0         # Ardışık başarılı işlem sayısı
        self.consecutive_fail = 0       # Ardışık hata sayısı
        self.total_floodwaits = 0       # Toplam FloodWait sayısı
        self.last_floodwait = 0         # Son FloodWait zamanı
        self.success_count = 0          # Toplam başarılı
        self.fail_count = 0             # Toplam başarısız

    async def wait(self):
        """Bir sonraki işlem öncesi bekle"""
        # Rastgele küçük varyasyon ekle (insan benzeri)
        jitter = random.uniform(-0.03, 0.03)
        delay = max(self.min_delay, self.current_delay + jitter)
        await asyncio.sleep(delay)

    def on_success(self):
        """Başarılı ban sonrası çağrılır"""
        self.success_count += 1
        self.consecutive_ok += 1
        self.consecutive_fail = 0

        # 15 ardışık başarılı işlem sonrası hızı artır
        if self.consecutive_ok >= 15 and self.current_delay > self.min_delay:
            self.current_delay = max(
                self.min_delay,
                self.current_delay - 0.02
            )
            self.consecutive_ok = 0
            log.info(f"⚡ Hız arttı! Gecikme: {self.current_delay:.2f}s")

    def on_floodwait(self, wait_time):
        """FloodWait yedikten sonra çağrılır"""
        self.total_floodwaits += 1
        self.last_floodwait = time.time()
        self.consecutive_ok = 0
        self.consecutive_fail += 1

        # FloodWait süresine göre hızı düşür
        if wait_time <= 3:
            # Kısa FloodWait → hafif yavaşlat
            self.current_delay = min(
                self.max_delay,
                self.current_delay * 1.5
            )
        elif wait_time <= 10:
            # Orta FloodWait → yavaşlat
            self.current_delay = min(
                self.max_delay,
                self.current_delay * 2.0
            )
        else:
            # Uzun FloodWait → çok yavaşlat
            self.current_delay = min(
                self.max_delay,
                self.current_delay * 3.0
            )

        log.warning(
            f"⏳ FloodWait {wait_time}s → Gecikme: {self.current_delay:.2f}s | "
            f"Toplam FloodWait: {self.total_floodwaits}"
        )

    def on_error(self):
        """Normal hata sonrası çağrılır"""
        self.fail_count += 1
        self.consecutive_ok = 0
        self.consecutive_fail += 1

        # 3 ardışık hata sonrası hafif yavaşlat
        if self.consecutive_fail >= 3:
            self.current_delay = min(
                self.max_delay,
                self.current_delay * 1.2
            )
            self.consecutive_fail = 0

    def get_stats(self):
        """İstatistikleri döndür"""
        total = self.success_count + self.fail_count
        speed = round(1 / self.current_delay, 1) if self.current_delay > 0 else 0
        return {
            "success": self.success_count,
            "failed": self.fail_count,
            "floodwaits": self.total_floodwaits,
            "delay": round(self.current_delay, 2),
            "speed": speed,
            "total": total
        }

# Global hız yöneticisi
speed_mgr = SpeedManager()

# ============================================
# ADMIN KONTROL
# ============================================
async def is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        status_str = str(member.status).lower()
        if "administrator" in status_str or "owner" in status_str:
            return True
        return False
    except Exception as e:
        log.error(f"Admin kontrol hatası: {e}")
        return False

# ============================================
# /start
# ============================================
@bot.on_message(filters.command("start"))
async def cmd_start(client, message: Message):
    await message.reply_text(
        "👋 **Bot aktif! (Hızlı Sürüm ⚡)**\n\n"
        "/test - Test\n"
        "/myid - ID'n\n"
        "/say - Üye sayısı\n"
        "/admincheck - Admin misin?\n"
        "/speed - Hız ayarları\n"
        "/kick (yanıtla) - Birini at\n"
        "/banall - Herkesi banla ⚡\n"
        "/unbanall - Banları kaldır\n"
    )

# ============================================
# /test
# ============================================
@bot.on_message(filters.command("test"))
async def cmd_test(client, message: Message):
    await message.reply_text(
        f"✅ Bot çalışıyor! ⚡\n"
        f"🆔 Chat: `{message.chat.id}`\n"
        f"📝 Tip: {message.chat.type}\n"
        f"👤 Sen: {message.from_user.first_name}"
    )

# ============================================
# /myid
# ============================================
@bot.on_message(filters.command("myid"))
async def cmd_myid(client, message: Message):
    await message.reply_text(f"🆔 ID: `{message.from_user.id}`")

# ============================================
# /admincheck
# ============================================
@bot.on_message(filters.command("admincheck"))
async def cmd_admincheck(client, message: Message):
    try:
        member = await client.get_chat_member(
            message.chat.id, message.from_user.id
        )
        await message.reply_text(f"📝 Durum: `{member.status}`")
    except Exception as e:
        await message.reply_text(f"❌ Hata: {e}")

# ============================================
# /say - Üye sayısı
# ============================================
@bot.on_message(filters.command("say") & filters.group)
async def cmd_say(client, message: Message):
    count = 0
    async for _ in client.get_chat_members(message.chat.id):
        count += 1
    await message.reply_text(f"📊 Toplam üye: **{count}**")

# ============================================
# /speed - Hız ayarlarını göster
# ============================================
@bot.on_message(filters.command("speed"))
async def cmd_speed(client, message: Message):
    stats = speed_mgr.get_stats()
    await message.reply_text(
        f"⚡ **Hız İstatistikleri**\n\n"
        f"├ Şu anki hız: **{stats['speed']}** ban/sn\n"
        f"├ Gecikme: **{stats['delay']}** saniye\n"
        f"├ Başarılı: **{stats['success']}**\n"
        f"├ Başarısız: **{stats['failed']}**\n"
        f"├ FloodWait: **{stats['floodwaits']}**\n"
        f"└ Toplam: **{stats['total']}**\n\n"
        f"💡 Gecikme ne kadar düşükse o kadar hızlısın."
    )

# ============================================
# /kick - Birini at
# ============================================
@bot.on_message(filters.command("kick") & filters.group)
async def cmd_kick(client, message: Message):
    chat_id = message.chat.id

    if not await is_admin(client, chat_id, message.from_user.id):
        await message.reply_text("❌ Sadece yöneticiler!")
        return

    if not message.reply_to_message:
        await message.reply_text("⚠️ Bir mesajı yanıtlayarak /kick yaz!")
        return

    target = message.reply_to_message.from_user

    try:
        await client.ban_chat_member(chat_id, target.id)
        await message.reply_text(f"🚫 **{target.first_name}** atıldı!")
    except Exception as e:
        await message.reply_text(f"❌ Hata: {e}")

# ============================================
# /banall - HERKESİ BANLA (HIZLI)
# ============================================
@bot.on_message(filters.command("banall") & filters.group)
async def cmd_banall(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # ========== ADMIN KONTROL ==========
    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("❌ Sadece yöneticiler!")
        return

    status_msg = await message.reply_text(
        "⚡ **Hızlı Ban Başlıyor...**\n\n"
        "🔄 Üyeler toplanıyor..."
    )

    # ========== ÜYELERİ TOPLA ==========
    all_members = []
    try:
        async for m in client.get_chat_members(chat_id):
            all_members.append(m)
    except Exception as e:
        await status_msg.edit_text(f"❌ Üyeler alınamadı: {e}")
        return

    # ========== FİLTRELE ==========
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

        status_str = str(m.status).lower()
        if "administrator" in status_str or "owner" in status_str:
            admin_count += 1
            continue

        users_to_ban.append(u)

    if len(users_to_ban) == 0:
        await status_msg.edit_text(
            f"⚠️ Banlanacak kimse yok!\n\n"
            f"📊 Toplam: {len(all_members)}\n"
            f"👑 Admin: {admin_count}\n"
            f"🤖 Bot: {bot_count}"
        )
        return

    await status_msg.edit_text(
        f"⚡ **Hızlı Ban Başlıyor!**\n\n"
        f"📊 Toplam üye: **{len(all_members)}**\n"
        f"🚫 Banlanacak: **{len(users_to_ban)}**\n"
        f"⏭️ Atlanan: **{admin_count + bot_count + 1}**\n"
        f"⚡ Hız: **{round(1/speed_mgr.current_delay, 1)}** ban/sn\n\n"
        f"⏳ İşlem başlıyor..."
    )

    # ========== HIZLI BAN İŞLEMİ ==========
    banned = 0
    failed = 0
    start_time = time.time()

    for i, u in enumerate(users_to_ban):
        try:
            await client.ban_chat_member(chat_id, u.id)
            banned += 1
            speed_mgr.on_success()
            log.info(f"✅ [{banned}/{len(users_to_ban)}] {u.first_name}")

        except FloodWait as e:
            speed_mgr.on_floodwait(e.value)
            log.warning(f"⏳ FloodWait: {e.value}s")
            await asyncio.sleep(e.value)
            try:
                await client.ban_chat_member(chat_id, u.id)
                banned += 1
                speed_mgr.on_success()
            except Exception:
                failed += 1
                speed_mgr.on_error()

        except Exception as e:
            failed += 1
            speed_mgr.on_error()
            log.error(f"❌ {u.first_name}: {e}")

        # Dinamik bekleme
        await speed_mgr.wait()

        # Her 10 kişide bir ilerleme göster
        if (i + 1) % 10 == 0:
            stats = speed_mgr.get_stats()
            elapsed = round(time.time() - start_time, 1)
            remaining = round(
                (len(users_to_ban) - banned - failed) / stats["speed"]
            ) if stats["speed"] > 0 else "?"
            try:
                await status_msg.edit_text(
                    f"⚡ **Hızlı Ban Devam Ediyor...**\n\n"
                    f"✅ Banlanan: **{banned}**/{len(users_to_ban)}\n"
                    f"❌ Başarısız: **{failed}**\n"
                    f"⏱️ Geçen: **{elapsed}** sn\n"
                    f"⚡ Hız: **{stats['speed']}** ban/sn\n"
                    f"⏳ Tahmini kalan: **~{remaining}** sn\n"
                    f"🔄 FloodWait: **{stats['floodwaits']}**"
                )
            except Exception:
                pass

    # ========== SONUÇ ==========
    stats = speed_mgr.get_stats()
    elapsed = round(time.time() - start_time, 1)
    avg_speed = round(banned / elapsed, 1) if elapsed > 0 else 0

    await status_msg.edit_text(
        f"✅ **İŞLEM TAMAMLANDI!** ⚡\n\n"
        f"🚫 Banlanan: **{banned}**\n"
        f"❌ Başarısız: **{failed}**\n"
        f"⏭️ Atlanan: **{admin_count + bot_count + 1}**\n"
        f"📊 Toplam: **{len(all_members)}**\n\n"
        f"⚡ Ortalama hız: **{avg_speed}** ban/sn\n"
        f"⏱️ Toplam süre: **{elapsed}** sn\n"
        f"🔄 FloodWait: **{stats['floodwaits']}**\n\n"
        f"💡 Geri almak için: /unbanall"
    )

# ============================================
# /unbanall
# ============================================
@bot.on_message(filters.command("unbanall") & filters.group)
async def cmd_unbanall(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("❌ Sadece yöneticiler!")
        return

    status_msg = await message.reply_text("🔄 Banlar kaldırılıyor...")

    unbanned = 0
    failed = 0
    start = time.time()

    try:
        async for m in client.get_chat_members(chat_id):
            status_str = str(m.status).lower()
            if "banned" in status_str or "kicked" in status_str:
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

                await asyncio.sleep(0.1)
    except Exception as e:
        await status_msg.edit_text(f"❌ Hata: {e}")
        return

    elapsed = round(time.time() - start, 1)

    await status_msg.edit_text(
        f"✅ **Unban Tamamlandı!**\n\n"
        f"🟢 Açılan: **{unbanned}**\n"
        f"❌ Başarısız: **{failed}**\n"
        f"⏱️ Süre: **{elapsed}** sn"
    )

# ============================================
# BAŞLAT
# ============================================
if __name__ == "__main__":
    Thread(target=start_web, daemon=True).start()
    log.info("🚀 Bot başlıyor (⚡ Hızlı Sürüm)...")
    bot.run()
