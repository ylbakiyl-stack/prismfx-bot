import os
import asyncio
import logging
from datetime import datetime
import pytz
import aiohttp
import xml.etree.ElementTree as ET
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN     = os.environ.get("BOT_TOKEN")
COMMUNITY = os.environ.get("CHAT_ID")
VIP       = os.environ.get("VIP_CHAT_ID")
TIMEZONE  = pytz.timezone("Europe/Istanbul")

TRANSLATIONS = {
    "Non-Farm Payrolls": "Tarim Disi Istihdam",
    "Unemployment Rate": "Issizlik Orani",
    "CPI m/m": "TUFE (Aylik)",
    "CPI y/y": "TUFE (Yillik)",
    "Core CPI m/m": "Cekirdek TUFE (Aylik)",
    "Core CPI y/y": "Cekirdek TUFE (Yillik)",
    "PPI m/m": "Uretici Fiyat Endeksi (Aylik)",
    "GDP q/q": "GSYIH (Ceyreklik)",
    "GDP m/m": "GSYIH (Aylik)",
    "Retail Sales m/m": "Perakende Satislar (Aylik)",
    "Core Retail Sales m/m": "Cekirdek Perakende Satislar",
    "FOMC Statement": "FED Para Politikasi Aciklamasi",
    "Fed Interest Rate Decision": "FED Faiz Karari",
    "ECB Interest Rate Decision": "ECB Faiz Karari",
    "BOE Interest Rate Decision": "BOE Faiz Karari",
    "ISM Manufacturing PMI": "ISM Imalat PMI",
    "ISM Services PMI": "ISM Hizmet PMI",
    "Manufacturing PMI": "Imalat PMI",
    "Services PMI": "Hizmet PMI",
    "ADP Non-Farm Employment Change": "ADP Ozel Sektor Istihdami",
    "Initial Jobless Claims": "Haftalik Issizlik Basvurulari",
    "Trade Balance": "Dis Ticaret Dengesi",
    "Consumer Confidence": "Tuketici Guveni",
    "CB Consumer Confidence": "CB Tuketici Guveni",
    "Michigan Consumer Sentiment": "Michigan Tuketici Guveni",
    "JOLTS Job Openings": "Is Ilanlari (JOLTS)",
    "Durable Goods Orders m/m": "Dayanikli Tuketim Siparisleri",
    "Building Permits": "Insaat Izinleri",
    "Crude Oil Inventories": "Ham Petrol Stoklari",
    "FOMC Meeting Minutes": "FED Toplanti Tutanaklari",
    "Fed Chair Powell Speaks": "FED Baskani Powell Konusmasi",
    "Fed Chair Speaks": "FED Baskani Konusmasi",
    "ECB President Lagarde Speaks": "ECB Baskani Lagarde Konusmasi",
    "German CPI m/m": "Almanya TUFE (Aylik)",
    "German GDP q/q": "Almanya GSYIH",
    "ZEW Economic Sentiment": "ZEW Ekonomik Beklenti",
    "Chinese Manufacturing PMI": "Cin Imalat PMI",
    "Caixin Manufacturing PMI": "Caixin Imalat PMI",
    "BOJ Interest Rate Decision": "BOJ Faiz Karari",
    "Flash GDP q/q": "GSYIH (Oncu)",
    "Chicago PMI": "Chicago PMI",
    "Core PCE Price Index m/m": "Cekirdek PCE Fiyat Endeksi",
    "Inflation Report": "Enflasyon Raporu",
}

SYMBOL_MAP = {
    "ALTIN":"XAU/USD","GOLD":"XAU/USD",
    "EURUSD":"EUR/USD","GBPUSD":"GBP/USD",
    "USDJPY":"USD/JPY","USDTRY":"USD/TRY",
    "NASDAQ":"NASDAQ 100","NAS100":"NASDAQ 100",
    "SP500":"S&P 500","SPX":"S&P 500",
    "DAX":"DAX 30","PETROL":"WTI/USD",
    "OIL":"WTI/USD","BTC":"BTC/USD",
    "BTCUSD":"BTC/USD","BIST":"BIST 100",
}

COUNTRY_FLAGS = {
    "USD":"🇺🇸","EUR":"🇪🇺","GBP":"🇬🇧",
    "JPY":"🇯🇵","CNY":"🇨🇳","AUD":"🇦🇺",
    "CAD":"🇨🇦","CHF":"🇨🇭","NZD":"🇳🇿","TRY":"🇹🇷",
}

def translate(title):
    for en, tr in TRANSLATIONS.items():
        if en.lower() in title.lower():
            return tr
    return title

def parse_event_time(time_str):
    try:
        now = datetime.now(TIMEZONE)
        t = datetime.strptime(time_str.strip(), "%I:%M%p")
        eastern = pytz.timezone("America/New_York")
        dt = eastern.localize(datetime(now.year, now.month, now.day, t.hour, t.minute))
        return dt.astimezone(TIMEZONE)
    except:
        return None

async def get_events():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    root = ET.fromstring(await r.text())
                    today = datetime.now(TIMEZONE).strftime("%m-%d-%Y")
                    events = []
                    for ev in root.findall("event"):
                        if today in ev.findtext("date","") and ev.findtext("impact","") == "High":
                            ts = ev.findtext("time","").strip()
                            dt = parse_event_time(ts)
                            events.append({
                                "time_local": dt.strftime("%H:%M") if dt else ts,
                                "title": ev.findtext("title",""),
                                "country": ev.findtext("country",""),
                                "forecast": ev.findtext("forecast",""),
                                "previous": ev.findtext("previous",""),
                                "actual": ev.findtext("actual",""),
                                "dt": dt,
                            })
                    return events
    except Exception as e:
        logger.error(f"FF hatasi: {e}")
    return []

async def send_morning_summary(bot):
    events = await get_events()
    now = datetime.now(TIMEZONE)
    date_str = now.strftime("%d %B %Y - %A")

    msg = f"📅 *GUNUN EKONOMIK TAKVIMI*\n_{date_str}_\n\n"

    if not events:
        msg += "Bugun yuksek onemli veri aciklamasi bulunmamaktadir.\n"
    else:
        for e in events:
            flag = COUNTRY_FLAGS.get(e["country"], "🌐")
            tr = translate(e["title"])
            fc = f" | Beklenti: {e['forecast']}" if e.get("forecast") else ""
            pv = f" | Onceki: {e['previous']}" if e.get("previous") else ""
            msg += f"🔴 `{e['time_local']}` {flag} *{tr}*{fc}{pv}\n\n"

    msg += "⚠️ _Yatirim tavsiyesi degildir._\n📊 @prismfxpro"
    await bot.send_message(chat_id=COMMUNITY, text=msg, parse_mode="Markdown")
    logger.info("Sabah takvimi gonderildi.")

async def check_upcoming(bot):
    events = await get_events()
    now = datetime.now(TIMEZONE)
    for e in events:
        dt = e.get("dt")
        if not dt: continue
        diff = (dt - now).total_seconds() / 60
        if 14 <= diff <= 16:
            flag = COUNTRY_FLAGS.get(e["country"], "🌐")
            tr = translate(e["title"])
            fc = f"\n📈 Beklenti: *{e['forecast']}*" if e.get("forecast") else ""
            pv = f"\n📊 Onceki: {e['previous']}" if e.get("previous") else ""
            msg = (f"⚠️ *15 DAKIKA SONRA VERI ACIKLANACAK!*\n\n"
                   f"🔴 {flag} *{tr}*\n"
                   f"🕐 Saat: `{e['time_local']}`{fc}{pv}\n\n"
                   f"_Piyasalarda volatilite artabilir. Risk yonetimine dikkat!_\n\n"
                   f"⚠️ _Yatirim tavsiyesi degildir._\n📊 @prismfxpro")
            await bot.send_message(chat_id=COMMUNITY, text=msg, parse_mode="Markdown")
            logger.info(f"15dk uyari: {tr}")

async def check_results(bot):
    events = await get_events()
    now = datetime.now(TIMEZONE)
    for e in events:
        dt = e.get("dt")
        if not dt: continue
        diff = (now - dt).total_seconds() / 60
        if 2 <= diff <= 4 and e.get("actual"):
            flag = COUNTRY_FLAGS.get(e["country"], "🌐")
            tr = translate(e["title"])
            actual = e["actual"]
            forecast = e.get("forecast","?")
            previous = e.get("previous","?")
            try:
                a = float(actual.replace("K","000").replace("M","000000").replace("%","").replace(",","."))
                f = float(forecast.replace("K","000").replace("M","000000").replace("%","").replace(",","."))
                emoji = "🟢" if a > f else "🔴" if a < f else "🟡"
                yorum = "Beklentinin uzerinde geldi" if a > f else "Beklentinin altinda geldi" if a < f else "Beklentiyle uyumlu geldi"
            except:
                emoji = "📊"; yorum = "Veri aciklandi"
            msg = (f"{emoji} *VERI SONUCU*\n\n"
                   f"{flag} *{tr}*\n\n"
                   f"✅ Gerceklesen: *{actual}*\n"
                   f"📈 Beklenti: {forecast}\n"
                   f"📊 Onceki: {previous}\n\n"
                   f"_{yorum}_\n\n"
                   f"⚠️ _Yatirim tavsiyesi degildir._\n📊 @prismfxpro")
            await bot.send_message(chat_id=COMMUNITY, text=msg, parse_mode="Markdown")
            logger.info(f"Sonuc: {tr} = {actual}")

def parse_signal(text):
    parts = text.upper().split()
    try:
        symbol    = parts[0]
        direction = parts[1]
        entry     = parts[2]
        tp        = parts[parts.index("TP")+1]
        sl        = parts[parts.index("SL")+1]
        return {"symbol":symbol,"direction":direction,"entry":entry,"tp":tp,"sl":sl}
    except:
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text: return
    text = msg.text.strip()
    bot  = context.bot

    if text.lower().startswith("!sinyal "):
        s = parse_signal(text[8:].strip())
        if not s:
            await msg.reply_text("Format: !sinyal ALTIN AL 2318 TP 2340 SL 2300")
            return
        await msg.delete()
        full = SYMBOL_MAP.get(s["symbol"], s["symbol"])
        is_long = s["direction"] in ("AL","BUY","LONG")
        dir_text = "LONG 🟢" if is_long else "SHORT 🔴"

        try:
            ef = float(str(s["entry"]).replace(",","."))
            tf = float(str(s["tp"]).replace(",","."))
            sf = float(str(s["sl"]).replace(",","."))
            reward = abs(tf-ef); risk = abs(ef-sf)
            rr = round(reward/risk, 2) if risk > 0 else 0
            rr_line = f"\n📐 Risk/Odul: 1:{rr}"
        except:
            rr_line = ""

        caption = (f"📊 *SINYAL*\n\n"
                   f"*{full}* — {dir_text}\n\n"
                   f"🎯 Giris: `{s['entry']}`\n"
                   f"✅ Hedef: `{s['tp']}`\n"
                   f"❌ Stop: `{s['sl']}`"
                   f"{rr_line}\n\n"
                   f"⚠️ _Yatirim tavsiyesi degildir._\n📊 @prismfxpro")
        await bot.send_message(chat_id=COMMUNITY, text=caption, parse_mode="Markdown")
        await bot.send_message(chat_id=VIP, text=caption, parse_mode="Markdown")

    elif text.lower().startswith("!vip "):
        s = parse_signal(text[5:].strip())
        if not s:
            await msg.reply_text("Format: !vip ALTIN AL 2318 TP 2340 SL 2300")
            return
        await msg.delete()
        full = SYMBOL_MAP.get(s["symbol"], s["symbol"])
        is_long = s["direction"] in ("AL","BUY","LONG")
        dir_text = "LONG 🟢" if is_long else "SHORT 🔴"

        teaser = (f"👑 *VIP SINYAL VERILDI*\n\n"
                  f"*{full}* — {dir_text}\n\n"
                  f"Tam detaylar icin VIP kanala katil 👇\n"
                  f"t.me/+KPo5wu7MwlQ1YzA0\n\n"
                  f"⚠️ _Yatirim tavsiyesi degildir._\n📊 @prismfxpro")
        await bot.send_message(chat_id=COMMUNITY, text=teaser, parse_mode="Markdown")

        try:
            ef = float(str(s["entry"]).replace(",","."))
            tf = float(str(s["tp"]).replace(",","."))
            sf = float(str(s["sl"]).replace(",","."))
            reward = abs(tf-ef); risk = abs(ef-sf)
            rr = round(reward/risk, 2) if risk > 0 else 0
            rr_line = f"\n📐 Risk/Odul: 1:{rr}"
        except:
            rr_line = ""

        vip_msg = (f"👑 *VIP SINYAL*\n\n"
                   f"*{full}* — {dir_text}\n\n"
                   f"🎯 Giris: `{s['entry']}`\n"
                   f"✅ Hedef: `{s['tp']}`\n"
                   f"❌ Stop: `{s['sl']}`"
                   f"{rr_line}\n\n"
                   f"⚠️ _Yatirim tavsiyesi degildir._\n📊 @prismfxpro")
        await bot.send_message(chat_id=VIP, text=vip_msg, parse_mode="Markdown")

async def main():
    bot = Bot(token=TOKEN)
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(send_morning_summary, "cron", hour=8, minute=0, args=[bot])
    scheduler.add_job(check_upcoming, "interval", minutes=5, args=[bot])
    scheduler.add_job(check_results,  "interval", minutes=2, args=[bot])
    scheduler.start()
    logger.info("Prism FX Bot basladi!")

    async with app:
        await app.start()
        await app.updater.start_polling()
        while True:
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
