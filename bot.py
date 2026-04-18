import os
import asyncio
import logging
from datetime import datetime
import pytz
import aiohttp
import xml.etree.ElementTree as ET
from telegram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TIMEZONE = pytz.timezone("Europe/Istanbul")

TRANSLATIONS = {
    "Non-Farm Payrolls": "Tarım Dışı İstihdam",
    "Unemployment Rate": "İşsizlik Oranı",
    "CPI m/m": "Tüketici Fiyat Endeksi (Aylık)",
    "CPI y/y": "Tüketici Fiyat Endeksi (Yıllık)",
    "Core CPI m/m": "Çekirdek TÜFE (Aylık)",
    "Core CPI y/y": "Çekirdek TÜFE (Yıllık)",
    "PPI m/m": "Üretici Fiyat Endeksi (Aylık)",
    "PPI y/y": "Üretici Fiyat Endeksi (Yıllık)",
    "GDP q/q": "Gayri Safi Yurt İçi Hasıla",
    "GDP m/m": "Gayri Safi Yurt İçi Hasıla (Aylık)",
    "Retail Sales m/m": "Perakende Satışlar (Aylık)",
    "Core Retail Sales m/m": "Çekirdek Perakende Satışlar",
    "FOMC Statement": "FED Para Politikası Açıklaması",
    "Fed Interest Rate Decision": "FED Faiz Kararı",
    "ECB Interest Rate Decision": "ECB Faiz Kararı",
    "ECB Monetary Policy Statement": "ECB Para Politikası Açıklaması",
    "BOE Interest Rate Decision": "İngiltere Merkez Bankası Faiz Kararı",
    "ISM Manufacturing PMI": "ISM İmalat PMI",
    "ISM Services PMI": "ISM Hizmet PMI",
    "Manufacturing PMI": "İmalat PMI",
    "Services PMI": "Hizmet PMI",
    "Flash Manufacturing PMI": "İmalat PMI (Öncü)",
    "Flash Services PMI": "Hizmet PMI (Öncü)",
    "ADP Non-Farm Employment Change": "ADP Özel Sektör İstihdamı",
    "Initial Jobless Claims": "Haftalık İşsizlik Başvuruları",
    "Trade Balance": "Dış Ticaret Dengesi",
    "Current Account": "Cari Hesap",
    "Consumer Confidence": "Tüketici Güveni",
    "CB Consumer Confidence": "Conference Board Tüketici Güveni",
    "Michigan Consumer Sentiment": "Michigan Tüketici Güveni",
    "JOLTS Job Openings": "İş İlanları (JOLTS)",
    "Durable Goods Orders m/m": "Dayanıklı Tüketim Siparişleri",
    "Building Permits": "İnşaat İzinleri",
    "Housing Starts": "Konut Başlangıçları",
    "Existing Home Sales": "Mevcut Konut Satışları",
    "New Home Sales": "Yeni Konut Satışları",
    "Industrial Production m/m": "Sanayi Üretimi (Aylık)",
    "Capacity Utilization Rate": "Kapasite Kullanım Oranı",
    "Core PCE Price Index m/m": "Çekirdek PCE Fiyat Endeksi",
    "PCE Price Index m/m": "PCE Fiyat Endeksi",
    "Crude Oil Inventories": "Ham Petrol Stokları",
    "Natural Gas Storage": "Doğal Gaz Stokları",
    "FOMC Meeting Minutes": "FED Toplantı Tutanakları",
    "Fed Chair Powell Speaks": "FED Başkanı Powell Konuşması",
    "Fed Chair Speaks": "FED Başkanı Konuşması",
    "ECB President Lagarde Speaks": "ECB Başkanı Lagarde Konuşması",
    "BOE Gov Bailey Speaks": "BOE Başkanı Bailey Konuşması",
    "German CPI m/m": "Almanya TÜFE (Aylık)",
    "German GDP q/q": "Almanya GSYİH",
    "German Ifo Business Climate": "Almanya İş İklimi Endeksi",
    "ZEW Economic Sentiment": "ZEW Ekonomik Beklenti",
    "Chinese Manufacturing PMI": "Çin İmalat PMI",
    "Caixin Manufacturing PMI": "Caixin İmalat PMI",
    "BOJ Interest Rate Decision": "Japonya Merkez Bankası Faiz Kararı",
    "Flash GDP q/q": "GSYİH (Öncü Tahmin)",
    "Prelim GDP q/q": "GSYİH (Ön Veri)",
    "Average Earnings Index": "Ortalama Kazanç Endeksi",
    "Claimant Count Change": "İşsizlik Başvuruları Değişimi",
    "Personal Income m/m": "Kişisel Gelir (Aylık)",
    "Personal Spending m/m": "Kişisel Harcama (Aylık)",
    "Empire State Manufacturing Index": "Empire State İmalat Endeksi",
    "Philadelphia Fed Manufacturing Index": "Philadelphia Fed İmalat Endeksi",
    "Chicago PMI": "Chicago PMI",
    "ISM Non-Manufacturing PMI": "ISM Hizmet Sektörü PMI",
    "Inflation Report": "Enflasyon Raporu",
}

COUNTRY_FLAGS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧",
    "JPY": "🇯🇵", "CNY": "🇨🇳", "AUD": "🇦🇺",
    "CAD": "🇨🇦", "CHF": "🇨🇭", "NZD": "🇳🇿",
    "TRY": "🇹🇷",
}

def translate(title):
    for en, tr in TRANSLATIONS.items():
        if en.lower() in title.lower():
            return tr
    return title

async def get_events():
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    root = ET.fromstring(text)
                    today = datetime.now(TIMEZONE).strftime("%m-%d-%Y")
                    events = []
                    for event in root.findall("event"):
                        date = event.findtext("date", "")
                        impact = event.findtext("impact", "")
                        if today in date and impact == "High":
                            events.append({
                                "time": event.findtext("time", ""),
                                "title": event.findtext("title", ""),
                                "country": event.findtext("country", ""),
                                "forecast": event.findtext("forecast", ""),
                                "previous": event.findtext("previous", ""),
                            })
                    return events
    except Exception as e:
        logger.error(f"Forex Factory hatası: {e}")
    return []

def parse_event_time(time_str):
    try:
        now = datetime.now(TIMEZONE)
        t = datetime.strptime(time_str.strip(), "%I:%M%p")
        eastern = pytz.timezone("America/New_York")
        event_dt = eastern.localize(datetime(now.year, now.month, now.day, t.hour, t.minute))
        return event_dt.astimezone(TIMEZONE)
    except:
        return None

async def send_morning_summary(bot):
    events = await get_events()
    now = datetime.now(TIMEZONE)
    date_str = now.strftime("%d %B %Y, %A")

    if not events:
        msg = (
            "📅 *GÜNÜN EKONOMİK TAKVİMİ*\n"
            f"_{date_str}_\n\n"
            "Bugün yüksek önemli veri açıklaması bulunmamaktadır.\n\n"
            "⚠️ _Yatırım tavsiyesi değildir._\n"
            "📊 @prismfxpro"
        )
    else:
        lines = []
        for e in events:
            flag = COUNTRY_FLAGS.get(e["country"], "🌐")
            tr_title = translate(e["title"])
            event_dt = parse_event_time(e["time"])
            t = event_dt.strftime("%H:%M") if event_dt else e["time"]
            forecast = f" | Beklenti: {e['forecast']}" if e.get("forecast") else ""
            previous = f" | Önceki: {e['previous']}" if e.get("previous") else ""
            lines.append(f"🔴 `{t}` {flag} *{tr_title}*{forecast}{previous}")

        msg = (
            "📅 *GÜNÜN EKONOMİK TAKVİMİ*\n"
            f"_{date_str}_\n\n"
            + "\n\n".join(lines) +
            "\n\n🔴 Yüksek Önemli Veriler\n"
            "⚠️ _Yatırım tavsiyesi değildir._\n"
            "📊 @prismfxpro"
        )

    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    logger.info("Sabah özeti gönderildi.")

async def check_upcoming(bot):
    events = await get_events()
    now = datetime.now(TIMEZONE)

    for e in events:
        event_dt = parse_event_time(e["time"])
        if not event_dt:
            continue
        diff = (event_dt - now).total_seconds() / 60
        if 14 <= diff <= 16:
            flag = COUNTRY_FLAGS.get(e["country"], "🌐")
            tr_title = translate(e["title"])
            t = event_dt.strftime("%H:%M")
            forecast = f"\n📈 Beklenti: *{e['forecast']}*" if e.get("forecast") else ""
            previous = f"\n📊 Önceki: {e['previous']}" if e.get("previous") else ""

            msg = (
                f"⚠️ *15 DAKİKA SONRA VERİ AÇIKLANACAK!*\n\n"
                f"🔴 {flag} *{tr_title}*\n"
                f"🕐 Saat: `{t}`"
                f"{forecast}{previous}\n\n"
                f"_Piyasalarda volatilite artabilir. Risk yönetimine dikkat!_\n\n"
                f"⚠️ _Yatırım tavsiyesi değildir._\n"
                f"📊 @prismfxpro"
            )
            await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
            logger.info(f"15 dk bildirimi: {tr_title}")

async def main():
    bot = Bot(token=TOKEN)
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(send_morning_summary, "cron", hour=8, minute=0, args=[bot])
    scheduler.add_job(check_upcoming, "interval", minutes=5, args=[bot])
    scheduler.start()
    logger.info("Prism FX Bot başlatıldı!")
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
