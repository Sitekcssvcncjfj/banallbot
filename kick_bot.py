import os
import asyncio
import logging
import time
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatAdminRequired, UserAdminInvalid, PeerIdInvalid
from flask import Flask
from threading import Thread

# ============================================
# 🌐 FLASK - Railway health check
# ============================================
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "✅ Bot çalışıyor!"

# ============================================
# 📋 LOGGING
# ============================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# 🔑 ENVIRONMENT VARIABLES (Railway'den)
# ============================================
API_ID = int(os.getenv("API_ID"))          # my.telegram.org
API_HASH = os.getenv("API_HASH")           # my.telegram.org
BOT_TOKEN = os.getenv("BOT_TOKEN")         # @BotFather

# ============================================
# ⚙️ RATE LIMIT AYARLARI (Spam'a düşmemek için)
# ============================================
BATCH_SIZE = 15        # Her 15 kişi için bir bekle
BATCH_DELAY = 4.0      # Batch arası bekleme (saniye)
USER_DELAY = 0.4       # Her ban arası bekleme (saniye)

# ============================================
# 🤖 PYROGRAM CLIENT
# ============================================
app = Client(
    "ban_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ============================================
# 🔐 ADMIN KONTROL FONKSİYONU
# ============================================
async def is_admin(client, chat_id: int, user_id: int) -> bool:
    """
    Verilen kullanıcı'nın grupta admin olup olmadığını kontrol eder.
    """
    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status in ["administrator", "creator"]:
            logger.info(f"✅ {user_id} ({member.user.first_name}) admin! [{chat_id}]")
            return True
        else:
            logger.warning(f"❌ {user_id} admin DEĞİL! [{chat_id}]")
            return False
    except (PeerIdInvalid, UserAdminInvalid) as e:
        logger.error(f"⚠️ Kullanıcı bulunamadı veya admin değil: {e}")
        return False
    except Exception as e:
        logger.error(f"❗ Admin kontrol hatası: {e}")
        return False

# ============================================
# 📌 /start KOMUTU (SADECE ÖZEL MESAJ)
# ============================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    await message.reply_text(
        "👋 **Merhaba!**\n\n"
        "Bu bot **sadece gruplarda** çalışır ve **sadece yöneticiler** komutları kullanabilir.\n\n"
        "📌 Komutlar:\n"
        "`/banall`  → Gruptaki **tüm üyeleri** banla (adminler ve bot hariç)\n"
        "`/unbanall` → Tüm banları kaldır\n"
        "`/count`   → Grup üye sayısını göster\n\n"
        "⚠️ Botu gruba **yönetici** olarak eklemeyi unutma!"
    )

# ============================================
# 📊 /count KOMUTU - ÜYE SAYISI (SADECE ADMIN)
# ============================================
@app.on_message(filters.command("count") & filters.group)
async def count_cmd(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    chat_title = message.chat.title

    # ✅ ADMIN KONTROLÜ
    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("⚠️ **Sadece yöneticiler** bu komutu kullanabilir!", quote=True)
        return

    await message.reply_text("🔄 Üyeler sayılıyor...", quote=True)

    count = 0
    async for _ in client.get_chat_members(chat_id):
        count += 1

    await message.reply_text(
        f"📊 **{chat_title}** grubunda **{count}** üye var!",
        quote=True
    )

# ============================================
# 🚫 /banall KOMUTU - TÜM ÜYELERİ BANLA (SADECE ADMIN)
# ============================================
@app.on_message(filters.command("banall") & filters.group)
async def ban_all_cmd(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    chat_title = message.chat.title
    sender_name = message.from_user.first_name

    # ✅ ADMIN KONTROLÜ
    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("⚠️ **Sadece yöneticiler** bu komutu kullanabilir!", quote=True)
        return

    # Bot kendisini banlayamasın!
    bot_id = (await client.get_me()).id
    if user_id == bot_id:
        await message.reply_text("🤖 Ben kendimi banlayamam!", quote=True)
        return

    status_msg = await message.reply_text(
        f"🔄 **{sender_name}**, tüm üyeler banlanıyor...\n"
        "Lütfen bekleyin!",
        quote=True
    )

    # Admin ID'lerini topla (banlanmayacaklar)
    admin_ids = []
    try:
        async for admin in client.get_chat_members(chat_id, filter="administrators"):
            admin_ids.append(admin.user.id)
        logger.info(f"Admin ID'leri: {admin_ids}")
    except Exception as e:
        logger.error(f"Admin listesi alınamadı: {e}")
        admin_ids = []

    banned = 0
    skipped = 0
    failed = 0
    start_time = time.time()

    # TÜM ÜYELERİ GEZ
    async for member in client.get_chat_members(chat_id):
        user = member.user
        user_id_to_ban = user.id

        # Botu, kendisini ve adminleri atla
        if user.is_bot or user_id_to_ban == user_id or user_id_to_ban in admin_ids:
            skipped += 1
            continue

        try:
            await client.ban_chat_member(chat_id, user_id_to_ban)
            banned += 1
            logger.info(f"✅ {user.first_name} ({user_id_to_ban}) banlandı.")

            # Her ban sonrası bekleme (rate limit)
            await asyncio.sleep(USER_DELAY)

            # Her BATCH_SIZE kişide bir daha uzun bekle
            if banned % BATCH_SIZE == 0:
                await status_msg.edit_text(
                    f"🔄 Ban devam ediyor...\n"
                    f"✅ Banlanan: **{banned}**\n"
                    f"⏭️ Atlanan: **{skipped}**\n"
                    f"❌ Başarısız: **{failed}**\n"
                    f"⏳ {BATCH_DELAY} saniye bekleniyor..."
                )
                await asyncio.sleep(BATCH_DELAY)

        except FloodWait as e:
            # Telegram'ın rate limit uyarısı
            wait_time = e.value
            logger.warning(f"⏳ FloodWait: {wait_time} saniye bekleniyor...")
            await status_msg.edit_text(f"⏳ Telegram rate limit! **{wait_time}** saniye bekleniyor...")
            await asyncio.sleep(wait_time)
            # Tekrar dene
            try:
                await client.ban_chat_member(chat_id, user_id_to_ban)
                banned += 1
            except Exception:
                failed += 1

        except (ChatAdminRequired, UserAdminInvalid) as e:
            failed += 1
            logger.error(f"❌ Yetki hatası (banlanamadı): {user.first_name} - {e}")

        except Exception as e:
            failed += 1
            logger.error(f"❌ Hata ({user.first_name}): {e}")

    # ⏱️ Süre hesapla
    elapsed = round(time.time() - start_time, 1)

    await status_msg.edit_text(
        f"✅ **Ban işlemi tamamlandı!** 🎉\n\n"
        f"📊 **{chat_title}** grubunda:\n"
        f"🚫 Banlanan: **{banned}** kişi\n"
        f"⏭️ Atlanan (admin/bot/sen): **{skipped}** kişi\n"
        f"❌ Başarısız: **{failed}** kişi\n"
        f"⏱️ Toplam süre: **{elapsed}** saniye\n\n"
        f"🔁 Geri almak için `/unbanall` yaz."
    )

# ============================================
# 🔓 /unbanall KOMUTU - TÜM BANLARI KALDIR (SADECE ADMIN)
# ============================================
@app.on_message(filters.command("unbanall") & filters.group)
async def unban_all_cmd(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    chat_title = message.chat.title

    # ✅ ADMIN KONTROLÜ
    if not await is_admin(client, chat_id, user_id):
        await message.reply_text("⚠️ **Sadece yöneticiler** bu komutu kullanabilir!", quote=True)
        return

    status_msg = await message.reply_text("🔄 Tüm banlar kaldırılıyor...", quote=True)

    unbanned = 0
    failed = 0
    start_time = time.time()

    try:
        # Banlı üyeleri al
        async for member in client.get_chat_members(chat_id, filter="banned"):
            user = member.user
            try:
                await client.unban_chat_member(chat_id, user.id)
                unbanned += 1
                logger.info(f"✅ {user.first_name} unban edildi.")

                await asyncio.sleep(USER_DELAY)
                if unbanned % BATCH_SIZE == 0:
                    await asyncio.sleep(BATCH_DELAY)

            except Exception as e:
                failed += 1
                logger.error(f"❌ Unban hatası ({user.first_name}): {e}")

    except Exception as e:
        await status_msg.edit_text(f"❌ Hata: {e}")
        return

    elapsed = round(time.time() - start_time, 1)

    await status_msg.edit_text(
        f"✅ **Unban işlemi tamamlandı!** 🎉\n\n"
        f"📊 **{chat_title}** grubunda:\n"
        f"🔓 Unban edilen: **{unbanned}** kişi\n"
        f"❌ Başarısız: **{failed}** kişi\n"
        f"⏱️ Süre: **{elapsed}** saniye"
    )

# ============================================
# 🚀 BOTU BAŞLAT
# ============================================
if __name__ == "__main__":
    # Flask'ı ayrı thread'de başlat (Railway için)
    Thread(
        target=app_flask.run,
        kwargs={"host": "0.0.0.0", "port": 8000},
        daemon=True
    ).start()

    logger.info("🚀 Bot başlatılıyor...")
    app.run()
