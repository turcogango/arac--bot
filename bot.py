import ssl
import aiohttp
import json
from datetime import datetime, timedelta
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# ==============================
# PANEL BİLGİLERİ (RAILWAY için)
# ==============================
# Ortam değişkenlerinden okunuyor
PANELS = {
    "panel1": {
        "url": os.environ.get("PANEL1_URL"),
        "username": os.environ.get("PANEL1_USER"),
        "password": os.environ.get("PANEL1_PASS")
    },
    "panel2": {
        "url": os.environ.get("PANEL2_URL"),
        "username": os.environ.get("PANEL2_USER"),
        "password": os.environ.get("PANEL2_PASS")
    }
}

# ==============================
# USERS JSON DOSYASINI YÜKLE
# ==============================
with open("users.json", "r", encoding="utf-8") as f:
    USERS = json.load(f)

# ==============================
# DEVRİRES DOSYASINDAN OKUMA
# ==============================
def load_devirs():
    try:
        with open("devir.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# ==============================
# PANELDEN YATIRIM, ÇEKİM & TESLİMAT ÇEK
# ==============================
async def fetch_user_amount(panel_config, user_uuid):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    login_url = f"{panel_config['url']}/login"
    reports_url = f"{panel_config['url']}/reports/quickly"

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
        async with session.get(login_url) as r:
            text = await r.text()
        token = ""
        for line in text.splitlines():
            if 'name="_token"' in line:
                token = line.split('value="')[1].split('"')[0]
                break
        await session.post(login_url, data={
            "_token": token,
            "email": panel_config['username'],
            "password": panel_config['password']
        })

        async with session.get(reports_url) as r:
            text = await r.text()
        csrf = ""
        for line in text.splitlines():
            if 'name="csrf-token"' in line or 'meta name="csrf-token"' in line:
                csrf = line.split('content="')[1].split('"')[0]
                break

        today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
        async with session.post(
            reports_url,
            headers={"X-CSRF-TOKEN": csrf, "Content-Type": "application/json"},
            json={"site": "", "dateone": today, "datetwo": today, "bank": "", "user": user_uuid}
        ) as r:
            data = await r.json()

        deposit_total = float(data.get("deposit", [0])[0] or 0)
        withdraw_total = float(data.get("withdraw", [0])[0] or 0)
        delivery_total = float(data.get("delivery", [0,0])[1] or 0)

        net = deposit_total - withdraw_total - delivery_total
        return net

# ==============================
# /kasaXX KOMUTU (sadece yöneticiler)
# ==============================
async def kasa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("⏳ Kasa verileri alınıyor...")
    try:
        # Sadece yönetici kontrolü
        member = await update.effective_chat.get_member(update.effective_user.id)
        if member.status not in ["administrator", "creator"]:
            await msg.edit_text("❌ Bu komutu sadece grup yöneticileri kullanabilir.")
            return

        # Hangi kasa komutu çalıştıysa onu yakala
        command = update.message.text.lstrip("/").upper()  # Örn: KASA02
        username = command.replace("KASA", "SKY")           # Örn: SKY02

        if username not in USERS:
            await msg.edit_text("❌ Bu kullanıcı için veri bulunamadı.")
            return

        info = USERS[username]
        panel = info["panel"]
        uuid = info["uuid"]

        net = await fetch_user_amount(PANELS[panel], uuid)
        devirs = load_devirs()
        devir = float(devirs.get(username, 0))
        total = net + devir
        total_str = f"{int(total):,}".replace(",", ".") + " TL"

        await msg.edit_text(f"💰 {username} KASA: {total_str}")

    except Exception as e:
        await msg.edit_text(f"❌ Hata oluştu:\n{e}")

# ==============================
# /gunceladres
# ==============================
async def gunceladres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("TSjQYavgJBGPr8iV3zH7qo1bx927qKVMwA")

# ==============================
# /gandalf
# ==============================
async def gandalf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👑👑👑👑")

# ==============================
# /esref
# ==============================
async def esref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👑👑👑👑")

# ==============================
# BOTU BAŞLAT
# ==============================
if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Railway ortam değişkeni
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable bulunamadı!")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # /kasaXX komutlarını tek handler ile tüm SKY’lar için dinle
    app.add_handler(MessageHandler(filters.Regex(r'^/kasa\d{2,}$'), kasa))

    # Diğer komutlar
    app.add_handler(CommandHandler("gunceladres", gunceladres))
    app.add_handler(CommandHandler("gandalf", gandalf))
    app.add_handler(CommandHandler("esref", esref))

    print("Bot Railway üzerinde çalışıyor...")
    app.run_polling()
