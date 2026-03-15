import os
import ssl
import aiohttp
import json
from datetime import datetime, timedelta
import asyncio
from telegram import Update
from telegram.ext import ContextTypes, ApplicationBuilder, CommandHandler

# USERS ve DEVR
with open("users.json", "r", encoding="utf-8") as f:
    USERS = json.load(f)

with open("devir.json", "r", encoding="utf-8") as f:
    DEVIRS = json.load(f)

# Paneller
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

# GRUPLAR
GRUPLAR = {
    "MALEFİZ": ["SKY02","SKY03","SKY06","SKY07","SKY11","SKY12","SKY13","SKY14","SKY16","SKY17",
                "SKY21","SKY22","SKY23","SKY24","SKY25","SKY29","SKY30","SKY37","SKY46","SKY47",
                "SKY48","SKY49","SKY58"],
    "RASPUTİN": ["SKY04","SKY20","SKY39","SKY42","SKY51","SKY53","SKY65","SKY66","SKY67","SKY69",
                 "SKY70","SKY72","SKY73","SKY77","SKY36"],
    "EFE": ["SKY09","SKY15","SKY19","SKY27","SKY31","SKY38","SKY50","SKY56","SKY57","SKY59","SKY61","SKY62"],
    "BOSSMAN": ["SKY08","SKY10","SKY40","SKY63","SKY64","SKY78"],
    "ALFİE": ["SKY18","SKY33","SKY54"],
    "KURTBEY": ["SKY32"],
    "SARRAF": ["SKY28","SKY44"],
    "HEKİM": ["SKY55","SKY60"],
    "CAVİT": ["SKY43"],
    "FAST": ["SKY05"],
    "TOM SHELBY": ["SKY26"],
    "GOOGLE": ["SKY52"],
    "F BEY": ["SKY68"],
    "FAVELA": ["SKY74"],
    "DAYI": ["SKY75"],
    "XAR": ["SKY79"],
    "KAPALI": ["SKY35","SKY41"],
    "BELİER": ["SKY45"],
    "MEHMET": ["SKY71","SKY80"]
}

# Panelden veri çekme
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

# /araci komutu
async def araci(update: Update, context: ContextTypes.DEFAULT_TYPE):
    aracilar_total = 0

    for grup, skylar in GRUPLAR.items():
        mesaj = f"📌 {grup} ({len(skylar)})\n"
        tasks = []
        keys = []
        for s in skylar:
            key = s.replace(" ", "")
            keys.append(key)
            if key not in USERS:
                mesaj += f"{s} ❌ Kullanıcı bulunamadı\n"
                continue
            info = USERS[key]
            tasks.append(fetch_user_amount(PANELS[info["panel"]], info["uuid"]))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        grup_total = 0

        idx = 0
        for key in keys:
            if key not in USERS:
                continue
            total = results[idx] + float(DEVIRS.get(key, 0)) if not isinstance(results[idx], Exception) else 0
            grup_total += total
            total_str = f"{int(total):,}".replace(",", ".") + " TL"
            mesaj += f"{key} {total_str}\n"
            idx += 1

        # 2’den fazla SKY varsa toplamı ekle
        if len(skylar) > 1:
            toplam_str = f"{int(grup_total):,}".replace(",", ".") + " TL"
            mesaj += f"Toplam: {toplam_str}\n"

        aracilar_total += grup_total
        await update.message.reply_text(mesaj)
        await asyncio.sleep(0.3)

    # Aracıların toplamı
    aracilar_total_str = f"{int(aracilar_total):,}".replace(",", ".") + " TL"
    await update.message.reply_text(f"Tüm aracıların toplamı: {aracilar_total_str}\nSAYGILAR ABİ")

# BOT TOKEN ve handler ekleme
if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable bulunamadı!")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("araci", araci))

    print("Bot çalışıyor...")
    app.run_polling()


