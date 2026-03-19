import os
import asyncio
import logging
import time
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import FloodWait
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

# ============================================
# 📋 LOGGING
# ============================================
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ============================================
# 🔑 ENV VARIABLES
# ============================================
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

# ============================================
# 🤖 CLIENT
# ============================================
bot = Client(
    "bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ============================================
# 🌐 BASIT WEB SUNUCU (Railway için)
# ============================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, *args):
        pass  # Gereksiz logları kapat

def start_web():
    server = HTTPServer(("0.0.0.0", 8000), HealthHandler)
    server.serve_forever()

# ============================================
# ✅ ADMIN KONTROL
# ============================================
async def check_admin(client, chat_id, user_id):
    """Kullanıcının admin olup olmadığını kontrol et"""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        log.info(f"User {user_id} status: {member.status}")

        if member.status in [
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR
        ]:
            return True
        return False
    except Exception as e:
        log.error(f"Admin check error: {e}")
        return False

# ============================================
# /start
# ============================================
@bot.on_message(filters.command("start"))
async def cmd_start(client, message: Message):
    await message.reply_text(
        "👋 **Merhaba! Bot aktif!**\n\n"
        "📌 Komutlar:\n"
        "/start - Bu mesaj\n"
        "/test - Bot çalışıyor mu\n"
        "/myid - Senin ID'n\n"
        "/chatid - Grup ID'si\n"
        "/kick (yanıtla) - Birini at\n"
        "/banall - Herkesi banla\n"
        "/unbanall - Banları kaldır\n"
    )

# ============================================
# /test - Botun çalıştığını doğrula
# ============================================
@bot.on_message(filters.command("test"))
async def cmd_test(client, message: Message):
    await message.reply_text(
        f"✅ Bot çalışıyor!\n"
        f"📝 Chat tipi: {message.chat.type}\n"
        f"👤 Sen: {message.from_user.first_name}\n"
        f"🆔 Chat ID: `{message.chat.id}`"
    )

# ============================================
# /myid - Kullanıcı ID'sini göster
# ============================================
@bot.on_message(filters.command("myid"))
async def cmd_myid(client, message: Message):
    await message.reply_text(f"🆔 Senin ID'n: `{message.from_user.id}`")

# ============================================
# /chatid - Grup ID'sini göster
# ============================================
@bot.on_message(filters.command("chatid"))
async def cmd_chatid(client, message: Message):
    await message.reply_text(
        f"🆔 Grup ID: `{message.chat.id}`\n"
        f"📝 Tip: {message.chat.type}\n"
        f"📊 Başlık: {message.chat.title}"
    )

# ============================================
# /kick - Birini at (yanıtlayarak)
# ============================================
@bot.on_message(filters.command("kick") & filters.group)
async def cmd_kick(client, message: Message):

    # Admin mi kontrol et
    if not await check_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("❌ Sadece yöneticiler kullanabilir!")
        return

    # Yanıtlanan mesaj var mı?
    if not message.reply_to_message:
        await message.reply_text("⚠️ Bir mesajı yanıtlayarak /kick yazın!")
        return

    target = message.reply_to_message.from_user
    target_id = target.id
    chat_id = message.chat.id

    # Admin olan birini atlamaya çalışıyor mu?
    if await check_admin(client, chat_id, target_id):
        await message.reply_text("❌ Bir yöneticiyi atamazsın!")
        return

    try:
        await client.ban_chat_member(chat_id, target_id)
        await message.reply_text(f"🚫 **{target.first_name}** gruptan atıldı!")
    except Exception as e:
        await message.reply_text(f"❌ Hata: {e}")

# ============================================
# /banall - HERKESİ BANLA
# ============================================
@bot.on_message(filters.command("banall") & filters.group)
async def cmd_banall(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # ========== ADMIN KONTROL ==========
    is_admin = await check_admin(client, chat_id, user_id)
    log.info(f"Admin check for {user_id}: {is_admin}")

    if not is_admin:
        await message.reply_text(
            "❌ Sadece **yöneticiler** bu komutu kullanabilir!\n\n"
            f"🆔 Senin ID: `{user_id}`\n"
            f"📝 Lütfen botun yönetici olduğundan emin olun."
        )
        return

    # ========== ÜYE TOPLAMA ==========
    status_msg = await message.reply_text("🔄 Üyeler toplanıyor...")

    # Admin ID'lerini topla
    admin_ids = []
    try:
        async for m in client.get_chat_members(chat_id, filter="administrators"):
            admin_ids.append(m.user.id)
    except Exception as e:
        await status_msg.edit_text(f"❌ Admin listesi alınamadı: {e}")
        return

    log.info(f"Admin IDs: {admin_ids}")

    # Banlanacak üyeleri topla
    users_to_ban = []
    total = 0

    try:
        async for m in client.get_chat_members(chat_id):
            total += 1
            u = m.user

            # Botları atla
            if u.is_bot:
                continue

            # Adminleri atla
            if u.id in admin_ids:
                continue

            # Kendini atla
            if u.id == user_id:
                continue

            users_to_ban.append(u)
    except Exception as e:
        await status_msg.edit_text(f"❌ Üye listesi alınamadı: {e}")
        return

    if not users_to_ban:
        await status_msg.edit_text("⚠️ Banlanacak kimse yok! Herkes admin veya bot.")
        return

    await status_msg.edit_text(
        f"🔄 **Ban işlemi başlıyor...**\n\n"
        f"📊 Toplam üye: {total}\n"
        f"🚫 Banlanacak: {len(users_to_ban)}\n"
        f"👥 Admin/bot atlanan: {total - len(users_to_ban)}\n\n"
        f"⏳ Lütfen bekleyin..."
    )

    # ========== BAN İŞLEMİ ==========
    banned = 0
    failed = 0
    start_time = time.time()

    for i, u in enumerate(users_to_ban):
        try:
            await client.ban_chat_member(chat_id, u.id)
            banned += 1

        except FloodWait as e:
            log.warning(f"FloodWait: {e.value}s")
            await asyncio.sleep(e.value)
            try:
                await client.ban_chat_member(chat_id, u.id)
                banned += 1
            except Exception:
                failed += 1

        except Exception as e:
            failed += 1
            log.error(f"Ban hatası {u.first_name}: {e}")

        # Her kullanıcı arası bekleme
        await asyncio.sleep(0.5)

        # Her 10 kişide bir ilerleme raporu
        if (i + 1) % 10 == 0:
            try:
                await status_msg.edit_text(
                    f"🔄 **Ban devam ediyor...**\n\n"
                    f"✅ Banlanan: {banned}/{len(users_to_ban)}\n"
                    f"❌ Başarısız: {failed}\n"
                    f"⏳ Bekleyin..."
                )
            except Exception:
                pass

        # Her 20 kişide bir较长 bekleme
        if (i + 1) % 20 == 0:
            await asyncio.sleep(3)

    # ========== SONUÇ ==========
    elapsed = round(time.time() - start_time, 1)

    try:
        await status_msg.edit_text(
            f"✅ **İŞLEM TAMAMLANDI!**\n\n"
            f"🚫 Banlanan: **{banned}** kişi\n"
            f"❌ Başarısız: **{failed}** kişi\n"
            f"⏭️ Atlanan: **{total - len(users_to_ban)}** kişi\n"
            f"📊 Toplam: **{total}** üye\n"
            f"⏱️ Süre: **{elapsed}** saniye\n\n"
            f"💡 Geri almak için: /unbanall"
        )
    except Exception:
        await message.reply_text(
            f"✅ Tamamlandı! Ban: {banned}, Başarısız: {failed}, Süre: {elapsed}s"
        )

# ============================================
# /unbanall - BANLARI KALDIR
# ============================================
@bot.on_message(filters.command("unbanall") & filters.group)
async def cmd_unbanall(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await check_admin(client, chat_id, user_id):
        await message.reply_text("❌ Sadece yöneticiler kullanabilir!")
        return

    status_msg = await message.reply_text("🔄 Banlar kaldırılıyor...")

    unbanned = 0
    failed = 0

    try:
        async for m in client.get_chat_members(chat_id, filter="banned"):
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

            await asyncio.sleep(0.3)

    except Exception as e:
        await status_msg.edit_text(f"❌ Hata: {e}")
        return

    await status_msg.edit_text(
        f"✅ **Unban tamamlandı!**\n\n"
        f"✅ Kaldırılan: **{unbanned}**\n"
        f"❌ Başarısız: **{failed}**\n\n"
        f"💡 Kullanıcılar gruba tekrar katılabilir."
    )

# ============================================
# 🚀 BAŞLAT
# ============================================
if __name__ == "__main__":
    Thread(target=start_web, daemon=True).start()
    log.info("🚀 Bot başlıyor...")
    bot.run()
