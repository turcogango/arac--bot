import os
import ssl
import aiohttp
import json
import asyncio
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes, ApplicationBuilder, CommandHandler

# USERS ve DEVR dosyaları
with open("users.json", "r", encoding="utf-8") as f:
    USERS = json.load(f)

with open("devir.json", "r", encoding="utf-8") as f:
    DEVIRS = json.load(f)

# PANELLER
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

# GRUPLAR (örnek)
GRUPLAR = {
    "MALEFİZ": ["SKY02","SKY03","SKY06"],
    "RASPUTİN": ["SKY04","SKY08","SKY11"],
    "EFE": ["SKY09","SKY10"]
}

# Panel oturumu oluşturma
async def create_panel_session(panel_config):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx))

    login_url = f"{panel_config['url']}/login"
    reports_url = f"{panel_config['url']}/reports/quickly"

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
        if 'csrf-token' in line:
            csrf = line.split('content="')[1].split('"')[0]
            break

    return session, csrf

# Kullanıcı miktarını çekme
async def fetch_amount(session, panel_url, csrf, user_uuid):
    today = (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")
    try:
        async with session.post(
            f"{panel_url}/reports/quickly",
            headers={"X-CSRF-TOKEN": csrf, "Content-Type": "application/json"},
            json={"site": "", "dateone": today, "datetwo": today, "bank": "", "user": user_uuid}
        ) as r:
            data = await r.json()

        deposit = float(data.get("deposit", [0])[0] or 0)
        withdraw = float(data.get("withdraw", [0])[0] or 0)
        delivery_list = data.get("delivery", [0, 0])
        delivery = float(delivery_list[1] if len(delivery_list) > 1 else 0)

        return deposit - withdraw - delivery
    except:
        return 0.0

# /araci komutu
async def araci(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Tüm paneller için oturum oluştur
    panel_sessions = {}
    for name, panel in PANELS.items():
        panel_sessions[name] = await create_panel_session(panel)

    aracilar_total = 0.0

    for grup, skylar in GRUPLAR.items():
        mesaj = f"📌 {grup} ({len(skylar)})\n"
        tasks = []
        keys = []

        for s in skylar:
            key = s.strip().upper()
            if key not in USERS:
                mesaj += f"{key} ❌ Kullanıcı yok\n"
                continue
            info = USERS[key]
            session, csrf = panel_sessions[info["panel"]]
            keys.append(key)
            tasks.append(fetch_amount(session, PANELS[info["panel"]]["url"], csrf, info["uuid"]))

        # Hataları sıfır olarak değerlendir
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                results[i] = 0.0

        grup_total = 0.0
        for key, result in zip(keys, results):
            devir = float(DEVIRS.get(key, 0))
            total = result + devir
            grup_total += total
            mesaj += f"{key} {total:,.2f} ₺\n"

        if len(keys) > 1:
            mesaj += f"Toplam: {grup_total:,.2f} ₺\n"

        aracilar_total += grup_total
        await update.message.reply_text(mesaj)
        await asyncio.sleep(0.2)

    # Tüm oturumları kapat
    for session, _ in panel_sessions.values():
        await session.close()

    # Genel toplam
    await update.message.reply_text(f"🔥 GENEL TOPLAM: {aracilar_total:,.2f} ₺\nSAYGILAR ABİ")

# Bot başlatma
if __name__ == "__main__":
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN bulunamadı!")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("araci", araci))

    print("Bot çalışıyor...")
    app.run_polling()
