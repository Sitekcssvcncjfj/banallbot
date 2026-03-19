import os
import asyncio
import logging
import time
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatAdminRequired, UserAdminInvalid
from flask import Flask
from threading import Thread

# ============================================
# 🌐 FLASK - Railway web sunucusu (sağlık kontrolü)
# ============================================
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "✅ Bot çalışıyor! 🚀"

@app_flask.route("/health")
def health():
    return {"status": "ok", "bot": "running"}

# ============================================
# 📋 LOGGING
# ============================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# 🔑 ENVIRONMENT VARIABLES (Railway'den alınır)
# ============================================
API_ID = int(os.getenv("API_ID"))          # my.telegram.org
API_HASH = os.getenv("API_HASH")           # my.telegram.org
BOT_TOKEN = os.getenv("BOT_TOKEN")         # @BotFather

# ============================================
# ⚙️ RATE LIMIT AYARLARI (Spam'a düşmemek için)
# ============================================
BATCH_SIZE = 20        # Her seferde banlanacak kişi sayısı
BATCH_DELAY = 3.0      # Batch'ler arası bekleme süresi (saniye)
USER_DELAY = 0.3       # Her kullanıcı banı arası bekleme (saniye)

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
# 🔧 YARDIMCI FONKSİYONLAR
# ============================================

def is_admin_sync(chat_id: int, user_id: int) -> bool:
    """Kullanıcının admin olup olmadığını kontrol et (sync wrapper)"""
    # Bu async olduğu için ayrı ele alacağız
    return True  # Placeholder

async def get_admin_ids(client, chat_id: int) -> list:
    """Gruptaki tüm admin ID'lerini döndür"""
    admin_ids = []
    async for member in client.get_chat_members(
        chat_id, 
        filter="administrators"
    ):
        admin_ids.append(member.user.id)
    return admin_ids


# ============================================
# 📌 /start KOMUTU
# ============================================
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    await message.reply_text(
        "👋 **Merhaba!**\n\n"
        "🤖 Ben bir grup yönetim botuyum.\n\n"
        "📌 **Komutlar:**\n"
        "├ `/banall` → Gruptaki herkesi banla\n"
        "├ `/unbanall` → Tüm banları kaldır\n"
        "├ `/count` → Grup üye sayısını göster\n"
        "└ `/start` → Bu mesajı göster\n\n"
        "⚠️ Botu grubuna ekle ve **yönetici** yap!\n"
        "⚠️ Sadece **adminler** komutları kullanabilir."
    )


# ============================================
# 📌 /count KOMUTU - Üye sayısını göster
# ============================================
@app.on_message(filters.command("count") & filters.group)
async def count_cmd(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # Admin kontrolü
    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            await message.reply_text("⚠️ Sadece **adminler** bu komutu kullanabilir!")
            return
    except Exception:
        await message.reply_text("❌ Admin kontrolü yapılamadı!")
        return

    await message.reply_text("🔄 Üye sayılıyor...")

    count = 0
    async for _ in client.get_chat_members(chat_id):
        count += 1

    await message.reply_text(f"📊 Grupta toplam **{count}** üye var.")


# ============================================
# 📌 /banall KOMUTU - HERKESİ BANLA
# ============================================
@app.on_message(filters.command("banall") & filters.group)
async def ban_all_cmd(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # ---------- Admin kontrolü ----------
    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            await message.reply_text("⚠️ Sadece **adminler** bu komutu kullanabilir!")
            return
    except Exception:
        await message.reply_text("❌ Admin kontrolü yapılamadı!")
        return

    # ---------- Onay mesajı ----------
    status_msg = await message.reply_text(
        "🔄 **Ban işlemi başlıyor...**\n\n"
        "⏳ Lütfen bekleyin..."
    )

    # ---------- Admin ID'lerini topla ----------
    admin_ids = await get_admin_ids(client, chat_id)
    logger.info(f"Admin ID'leri: {admin_ids}")

    # ---------- Üye toplama ----------
    users_to_ban = []
    total_members = 0
    skipped_admins = 0
    skipped_bots = 0

    async for mem in client.get_chat_members(chat_id):
        total_members += 1
        user = mem.user

        # Botu atla
        if user.is_bot:
            skipped_bots += 1
            continue

        # Adminleri atla
        if user.id in admin_ids:
            skipped_admins += 1
            continue

        # Komutu kullananı atla
        if user.id == user_id:
            skipped_admins += 1
            continue

        users_to_ban.append(user)

    # ---------- Bilgi güncelle ----------
    await status_msg.edit_text(
        f"🔄 **Ban işlemi başlıyor...**\n\n"
        f"📊 Toplam üye: **{total_members}**\n"
        f"🚫 Banlanacak: **{len(users_to_ban)}**\n"
        f"⏭️ Atlanacak (admin/bot): **{skipped_admins + skipped_bots}**\n\n"
        f"⏳ İşlem başlatılıyor..."
    )

    # ---------- BAN İŞLEMİ (Batch ile) ----------
    banned = 0
    failed = 0
    start_time = time.time()

    for i, user in enumerate(users_to_ban):
        try:
            await client.ban_chat_member(chat_id, user.id)
            banned += 1
            logger.info(f"✅ [{banned}/{len(users_to_ban)}] {user.first_name} banlandı.")

        except FloodWait as e:
            # Telegram "bekle" dedi, bekliyoruz
            logger.warning(f"⏳ FloodWait: {e.value} saniye bekleniyor...")
            await status_msg.edit_text(
                f"🔄 **Ban devam ediyor...**\n\n"
                f"✅ Banlanan: **{banned}** / {len(users_to_ban)}\n"
                f"❌ Başarısız: **{failed}**\n"
                f"⏳ Telegram rate limit! {e.value} sn bekleniyor..."
            )
            await asyncio.sleep(e.value)
            # Tekrar dene
            try:
                await client.ban_chat_member(chat_id, user.id)
                banned += 1
            except Exception:
                failed += 1

        except (ChatAdminRequired, UserAdminInvalid) as e:
            failed += 1
            logger.error(f"❌ Yetki hatası - {user.first_name}: {e}")

        except Exception as e:
            failed += 1
            logger.error(f"❌ Hata - {user.first_name}: {e}")

        # ---------- Her kullanıcı arası bekleme ----------
        await asyncio.sleep(USER_DELAY)

        # ---------- Her BATCH_SIZE kişide bir较长 bekleme ----------
        if (i + 1) % BATCH_SIZE == 0:
            await status_msg.edit_text(
                f"🔄 **Ban devam ediyor...**\n\n"
                f"✅ Banlanan: **{banned}** / {len(users_to_ban)}\n"
                f"❌ Başarısız: **{failed}**\n"
                f"⏳ {BATCH_DELAY} saniye bekleniyor (batch sonu)..."
            )
            await asyncio.sleep(BATCH_DELAY)

    # ---------- SONUÇ ----------
    elapsed = round(time.time() - start_time, 1)

    await status_msg.edit_text(
        f"✅ **Ban işlemi tamamlandı!** 🎉\n\n"
        f"📊 **İstatistikler:**\n"
        f"├ 🚫 Banlanan: **{banned}** kişi\n"
        f"├ ❌ Başarısız: **{failed}** kişi\n"
        f"├ ⏭️ Atlanan (admin/bot): **{skipped_admins + skipped_bots}** kişi\n"
        f"├ 📈 Toplam üye: **{total_members}** kişi\n"
        f"└ ⏱️ Süre: **{elapsed}** saniye\n\n"
        f"💡 Geri almak için `/unbanall` yaz."
    )

    logger.info(
        f"Banall tamamlandı! "
        f"Banlanan: {banned}, Başarısız: {failed}, Süre: {elapsed}s"
    )


# ============================================
# 📌 /unbanall KOMUTU - TÜM BANLARI KALDIR
# ============================================
@app.on_message(filters.command("unbanall") & filters.group)
async def unban_all_cmd(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    # ---------- Admin kontrolü ----------
    try:
        member = await client.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            await message.reply_text("⚠️ Sadece **adminler** bu komutu kullanabilir!")
            return
    except Exception:
        await message.reply_text("❌ Admin kontrolü yapılamadı!")
        return

    status_msg = await message.reply_text("🔄 **Banlar kaldırılıyor...**")

    # ---------- Banlı üyeleri al ve unban et ----------
    unbanned = 0
    failed = 0
    start_time = time.time()

    try:
        async for mem in client.get_chat_members(
            chat_id, 
            filter="banned"
        ):
            try:
                await client.unban_chat_member(chat_id, mem.user.id)
                unbanned += 1
                logger.info(f"✅ {mem.user.first_name} unbanlandı.")

            except FloodWait as e:
                logger.warning(f"⏳ FloodWait: {e.value} sn")
                await asyncio.sleep(e.value)
                try:
                    await client.unban_chat_member(chat_id, mem.user.id)
                    unbanned += 1
                except Exception:
                    failed += 1

            except Exception as e:
                failed += 1
                logger.error(f"❌ Unban hatası: {e}")

            await asyncio.sleep(USER_DELAY)

            if (unbanned + failed) % BATCH_SIZE == 0:
                await asyncio.sleep(BATCH_DELAY)

    except Exception as e:
        await status_msg.edit_text(f"❌ Hata: {e}")
        return

    elapsed = round(time.time() - start_time, 1)

    await status_msg.edit_text(
        f"✅ **Unban işlemi tamamlandı!** 🎉\n\n"
        f"├ ✅ Unban edilen: **{unbanned}** kişi\n"
        f"├ ❌ Başarısız: **{failed}** kişi\n"
        f"└ ⏱️ Süre: **{elapsed}** saniye\n\n"
        f"💡 Kullanıcılar gruba tekrar katılabilir."
    )


# ============================================
# ❌ HATA YAKALAMA
# ============================================
@app.on_message()
async def unknown_cmd(client, message: Message):
    # Bilinmeyen mesajları yok say
    pass


# ============================================
# 🚀 MAIN - BOTU BAŞLAT
# ============================================
if __name__ == "__main__":
    # Flask'ı ayrı thread'de başlat (Railway health check için)
    Thread(
        target=app_flask.run,
        kwargs={"host": "0.0.0.0", "port": 8000},
        daemon=True
    ).start()

    logger.info("🚀 Bot başlatılıyor...")
    app.run()
