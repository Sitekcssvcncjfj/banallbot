import os
import asyncio
import logging
import time
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
# ADMIN KONTROL - BASİT VE SAĞLAM
# ============================================
async def is_admin(client, chat_id, user_id):
    """Kullanıcının admin olup olmadığını basit şekilde kontrol et"""
    try:
        member = await client.get_chat_member(chat_id, user_id)
        # Status string olarak gelebilir, enum olarak gelebilir
        # İkisini de kontrol et
        status_str = str(member.status).lower()
        log.info(f"Admin kontrol - User: {user_id}, Status: {status_str}")

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
        "👋 **Bot aktif!**\n\n"
        "/test - Test\n"
        "/myid - ID'n\n"
        "/chatid - Grup ID\n"
        "/admincheck - Admin misin?\n"
        "/say - Üye say\n"
        "/kick (yanıtla) - Birini at\n"
        "/banall - Herkesi banla\n"
        "/unbanall - Banları kaldır\n"
    )

# ============================================
# /test
# ============================================
@bot.on_message(filters.command("test"))
async def cmd_test(client, message: Message):
    await message.reply_text(
        f"✅ Bot çalışıyor!\n"
        f"🆔 Chat ID: `{message.chat.id}`\n"
        f"📝 Chat tipi: {message.chat.type}\n"
        f"👤 Sen: {message.from_user.first_name} (`{message.from_user.id}`)"
    )

# ============================================
# /myid
# ============================================
@bot.on_message(filters.command("myid"))
async def cmd_myid(client, message: Message):
    await message.reply_text(f"🆔 Senin ID: `{message.from_user.id}`")

# ============================================
# /chatid
# ============================================
@bot.on_message(filters.command("chatid"))
async def cmd_chatid(client, message: Message):
    await message.reply_text(
        f"🆔 Grup ID: `{message.chat.id}`\n"
        f"📝 Tip: {message.chat.type}\n"
        f"📊 Adı: {message.chat.title}"
    )

# ============================================
# /admincheck
# ============================================
@bot.on_message(filters.command("admincheck"))
async def cmd_admincheck(client, message: Message):
    uid = message.from_user.id
    cid = message.chat.id
    try:
        member = await client.get_chat_member(cid, uid)
        await message.reply_text(
            f"📝 Status: `{member.status}`\n"
            f"🆔 ID: `{uid}`"
        )
    except Exception as e:
        await message.reply_text(f"❌ Hata: {e}")

# ============================================
# /say - Üye sayısını göster
# ============================================
@bot.on_message(filters.command("say") & filters.group)
async def cmd_say(client, message: Message):
    count = 0
    try:
        async for m in client.get_chat_members(message.chat.id):
            count += 1
        await message.reply_text(f"📊 Toplam üye: **{count}**")
    except Exception as e:
        await message.reply_text(f"❌ Hata: {e}")
        log.error(f"Say error: {e}")

# ============================================
# /kick - Birini at (yanıtla)
# ============================================
@bot.on_message(filters.command("kick") & filters.group)
async def cmd_kick(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("❌ Sadece yöneticiler!")
        return

    if not message.reply_to_message:
        await message.reply_text("⚠️ Bir mesajı yanıtlayarak /kick yaz!")
        return

    target_id = message.reply_to_message.from_user.id
    target_name = message.reply_to_message.from_user.first_name

    try:
        await client.ban_chat_member(chat_id, target_id)
        await message.reply_text(f"🚫 **{target_name}** atıldı!")
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
    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("❌ Sadece yöneticiler bu komutu kullanabilir!")
        return

    status_msg = await message.reply_text("🔄 İşlem başlıyor... Lütfen bekleyin.")

    # ========== ÜYELERİ TOPLA ==========
    all_members = []

    try:
        async for m in client.get_chat_members(chat_id):
            all_members.append(m)
    except Exception as e:
        await status_msg.edit_text(f"❌ Üyeler alınamadı: {e}")
        log.error(f"get_chat_members hatası: {e}")
        return

    log.info(f"Toplam {len(all_members)} üye bulundu.")

    # ========== KİMLERİ BANLAYACAĞIMIZI BELİRLE ==========
    users_to_ban = []
    admin_count = 0
    bot_count = 0

    for m in all_members:
        u = m.user

        # Botları atla
        if u.is_bot:
            bot_count += 1
            continue

        # Kendini atla
        if u.id == user_id:
            continue

        # Adminleri atla
        status_str = str(m.status).lower()
        if "administrator" in status_str or "owner" in status_str:
            admin_count += 1
            continue

        users_to_ban.append(u)

    log.info(f"Banlanacak: {len(users_to_ban)}, Admin: {admin_count}, Bot: {bot_count}")

    if len(users_to_ban) == 0:
        await status_msg.edit_text(
            f"⚠️ Banlanacak kimse yok!\n\n"
            f"📊 Toplam üye: {len(all_members)}\n"
            f"👑 Admin: {admin_count}\n"
            f"🤖 Bot: {bot_count}\n"
            f"👤 Normal üye: 0"
        )
        return

    await status_msg.edit_text(
        f"🔄 **Ban başlıyor...**\n\n"
        f"📊 Toplam: {len(all_members)}\n"
        f"🚫 Banlanacak: {len(users_to_ban)}\n"
        f"⏭️ Atlanan: {admin_count + bot_count + 1}\n\n"
        f"⏳ Bekleyin..."
    )

    # ========== BAN İŞLEMİ ==========
    banned = 0
    failed = 0
    start = time.time()

    for i, u in enumerate(users_to_ban):
        try:
            await client.ban_chat_member(chat_id, u.id)
            banned += 1
            log.info(f"✅ [{banned}/{len(users_to_ban)}] {u.first_name} banlandı")

        except FloodWait as e:
            wait_time = e.value
            log.warning(f"⏳ FloodWait: {wait_time}s")
            await asyncio.sleep(wait_time)
            try:
                await client.ban_chat_member(chat_id, u.id)
                banned += 1
            except Exception:
                failed += 1

        except Exception as e:
            failed += 1
            log.error(f"❌ {u.first_name} banlanamadı: {e}")

        # Her kullanıcı arası bekle
        await asyncio.sleep(0.5)

        # Her 10 kişide bir ilerleme göster
        if (i + 1) % 10 == 0:
            try:
                await status_msg.edit_text(
                    f"🔄 **Ban devam ediyor...**\n\n"
                    f"✅ Banlanan: {banned}/{len(users_to_ban)}\n"
                    f"❌ Başarısız: {failed}\n"
                    f"⏳ Devam ediyor..."
                )
            except Exception:
                pass

        # Her 25 kişide bir较长 bekle (spam koruma)
        if (i + 1) % 25 == 0:
            await asyncio.sleep(5)

    # ========== SONUÇ ==========
    elapsed = round(time.time() - start, 1)

    await status_msg.edit_text(
        f"✅ **İŞLEM TAMAMLANDI!**\n\n"
        f"🚫 Banlanan: **{banned}**\n"
        f"❌ Başarısız: **{failed}**\n"
        f"⏭️ Atlanan: **{admin_count + bot_count + 1}**\n"
        f"📊 Toplam: **{len(all_members)}**\n"
        f"⏱️ Süre: **{elapsed}** sn\n\n"
        f"💡 Geri almak için: /unbanall"
    )

# ============================================
# /unbanall - BANLARI KALDIR
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

    try:
        async for m in client.get_chat_members(chat_id):
            # Sadece banlı olanları unban et
            status_str = str(m.status).lower()
            if "banned" in status_str or "kicked" in status_str:
                try:
                    await client.unban_chat_member(chat_id, m.user.id)
                    unbanned += 1
                    log.info(f"✅ {m.user.first_name} unbanlandı")
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
        f"🟢 Geri açılan: **{unbanned}**\n"
        f"❌ Başarısız: **{failed}**"
    )

# ============================================
# BAŞLAT
# ============================================
if __name__ == "__main__":
    Thread(target=start_web, daemon=True).start()
    log.info("🚀 Bot başlıyor...")
    bot.run()
