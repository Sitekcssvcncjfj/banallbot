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
# 🔧 AYARLAR VE LOGGİNG
# ============================================
app_flask = Flask(__name__)

@app_flask.route("/")
def home():
    return "✅ Bot çalışıyor! 🚀"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

BATCH_SIZE = 15       # Spam düşmemek için azaltıldı
USER_DELAY = 0.5      # Kullanıcı başına bekleme arttırıldı

# ============================================
# 🤖 BOT OLUŞTURMA
# ============================================
app = Client(
    "ban_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ============================================
# ✅ GÜVENLİ ADMIN KONTROL FONKSİYONU
# ============================================
async def is_user_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        status = member.status
        
        # Pyrogram farklı versiyonlarda 'status'u string veya Enum olarak döndürebilir. 
        # Her ikisine de eşleşecek genişletilmiş kontrol:
        if status == "administrator":
            logger.info(f"Kullanıcı {user_id} admin olarak kabul edildi (string).")
            return True
        elif hasattr(member, 'is_administrator') and member.is_administrator:
            logger.info(f"Kullanıcı {user_id} admin olarak kabul edildi (flag).")
            return True
        else:
            logger.warning(f"Kullanıcı {user_id} yönetici değil. Durum: {status}")
            return False
            
    except Exception as e:
        logger.error(f"Admin kontrol hatası: {e}")
        return False

# ============================================
# /count KOMUTU
# ============================================
@app.on_message(filters.command("count") & filters.group)
async def count_cmd(client, message: Message):
    chat_id = message.chat.id
    
    if not await is_user_admin(client, chat_id, message.from_user.id):
        await message.reply_text("⚠️ Sadece **yöneticiler** bu komutu kullanabilir!")
        return

    await message.reply_text("🔄 Üye sayılıyor...")
    count = sum([1 async for _ in client.get_chat_members(chat_id)])
    await message.reply_text(f"📊 Grupta toplam **{count}** üye var.")

# ============================================
# /banall KOMUTU
# ============================================
@app.on_message(filters.command("banall") & filters.group)
async def ban_all_cmd(client, message: Message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if not await is_user_admin(client, chat_id, user_id):
        await message.reply_text("⚠️ Yalnızca grubun **yöneticileri** bu komutu kullanabilir!")
        return

    status_msg = await message.reply_text("⚠️ İŞLEM BAŞLATILIYOR...\nBekleyin lütfen.")
    
    try:
        all_admins = []
        async for mem in client.get_chat_members(chat_id, filter="administrators"):
            all_admins.append(mem.user.id)

        users_to_ban = []
        skipped = 0

        async for mem in client.get_chat_members(chat_id):
            user = mem.user
            if user.is_bot or user.id == user_id or user.id in all_admins:
                skipped += 1
                continue
            users_to_ban.append(user)

        banned_count = 0
        failed_count = 0
        start_time = time.time()

        for i, user in enumerate(users_to_ban):
            try:
                await client.ban_chat_member(chat_id, user.id)
                banned_count += 1
                logger.info(f"Banned: {user.first_name}")
                
            except FloodWait as e:
                logger.warning(f"FloodWait ({e.value}s bekleniyor)")
                await asyncio.sleep(e.value)
                try:
                    await client.ban_chat_member(chat_id, user.id)
                    banned_count += 1
                except Exception as e2:
                    failed_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"Hata: {e}")

            await asyncio.sleep(USER_DELAY)

        elapsed = round(time.time() - start_time, 1)
        await status_msg.edit_text(
            f"✅ İşlem Tamamlandı!\n\n"
            f"🔸 Banlanan: **{banned_count}**\n"
            f"🔸 Başarısız: **{failed_count}**\n"
            f"🔸 Atlanan: **{skipped}**\n"
            f"⏱️ Süre: **{elapsed} sn**"
        )

    except Exception as e:
        await status_msg.edit_text(f"❌ Kritik Hata: {e}")

# ============================================
# BAŞLATMA
# ============================================
if __name__ == "__main__":
    Thread(target=app_flask.run, kwargs={"host": "0.0.0.0", "port": 8000}, daemon=True).start()
    app.run()
