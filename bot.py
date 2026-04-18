import os
import asyncio
import logging
from datetime import datetime
from io import BytesIO
import pytz
import aiohttp
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN       = os.environ.get("BOT_TOKEN")
COMMUNITY   = os.environ.get("CHAT_ID")          # -1003976013512
VIP         = os.environ.get("VIP_CHAT_ID")       # -1003721473246
TIMEZONE    = pytz.timezone("Europe/Istanbul")

# ── RENKLER ──────────────────────────────────────────────
C_BG     = "#0A1828"
C_HEADER = "#042C53"
C_GOLD   = "#FAC775"
C_RED    = "#E24B4A"
C_GREEN  = "#5DCAA5"
C_WHITE  = "#FFFFFF"
C_MUTED  = "#888888"
C_CARD   = "#111F30"
C_BORDER = "#1E3450"

# ── ÇEVİRİ SÖZLÜĞÜ ───────────────────────────────────────
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

SYMBOL_MAP = {
    "ALTIN": "XAU/USD", "GOLD": "XAU/USD",
    "EURUSD": "EUR/USD", "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY", "USDTRY": "USD/TRY",
    "NASDAQ": "NASDAQ 100", "NAS100": "NASDAQ 100",
    "SP500": "S&P 500", "SPX": "S&P 500",
    "DAX": "DAX 30", "PETROL": "WTI/USD",
    "OIL": "WTI/USD", "BTC": "BTC/USD",
    "BTCUSD": "BTC/USD", "BIST": "BIST 100",
}

# ── YARDIMCI FONKSİYONLAR ───────────────────────────────
def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def get_font(size, bold=False):
    try:
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else \
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()

def translate(title):
    for en, tr in TRANSLATIONS.items():
        if en.lower() in title.lower():
            return tr
    return title

# ── TAKVİM GÖRSELİ ──────────────────────────────────────
def create_calendar_image(events, date_str):
    W = 1080
    HEADER_H, CARD_H, PAD, FOOTER_H, GAP = 140, 90, 48, 100, 12
    n = max(len(events), 1)
    H = HEADER_H + 20 + (CARD_H + GAP) * n + 60 + FOOTER_H

    img = Image.new("RGB", (W, H), hex_rgb(C_BG))
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, HEADER_H], fill=hex_rgb(C_HEADER))
    d.text((PAD, 28), "PRISM FX · OTOMATİK TAKVİM", font=get_font(20), fill=hex_rgb(C_GOLD))
    d.text((PAD, 60), "Günün Ekonomik Takvimi", font=get_font(36, True), fill=hex_rgb(C_WHITE))
    d.text((PAD, 108), date_str, font=get_font(22), fill=(*hex_rgb(C_WHITE), 100))
    d.rectangle([PAD, HEADER_H+8, W-PAD, HEADER_H+9], fill=(*hex_rgb(C_GOLD), 40))

    y = HEADER_H + 28
    if not events:
        d.text((PAD, y+30), "Bugün yüksek önemli veri bulunmamaktadır.", font=get_font(26), fill=hex_rgb(C_MUTED))
    else:
        for e in events:
            d.rounded_rectangle([PAD, y, W-PAD, y+CARD_H], radius=12, fill=hex_rgb(C_CARD), outline=hex_rgb(C_BORDER), width=1)
            d.rounded_rectangle([PAD, y, PAD+5, y+CARD_H], radius=4, fill=hex_rgb(C_RED))
            d.text((PAD+20, y+14), e.get("time_local",""), font=get_font(26, True), fill=hex_rgb(C_RED))
            flag = COUNTRY_FLAGS.get(e.get("country",""), "🌐")
            title = translate(e.get("title",""))
            d.text((PAD+130, y+14), f"{flag} {title}", font=get_font(26, True), fill=hex_rgb(C_WHITE))
            parts = []
            if e.get("forecast"): parts.append(f"Beklenti: {e['forecast']}")
            if e.get("previous"): parts.append(f"Önceki: {e['previous']}")
            d.text((PAD+130, y+54), "  ·  ".join(parts) or "Veri bekleniyor", font=get_font(20), fill=hex_rgb(C_MUTED))
            y += CARD_H + GAP

    d.rectangle([PAD, y+10, W-PAD, y+11], fill=(*hex_rgb(C_WHITE), 15))
    d.text((PAD, y+22), "🔴 Yüksek Önemli  ·  Yatırım tavsiyesi değildir.", font=get_font(20), fill=hex_rgb(C_MUTED))

    footer_y = H - FOOTER_H
    d.rectangle([0, footer_y, W, H], fill=hex_rgb(C_HEADER))
    d.text((PAD, footer_y+22), "PRISM FX", font=get_font(32, True), fill=hex_rgb(C_WHITE))
    d.text((PAD, footer_y+62), "Telegram · Discord · prismfxpro.com", font=get_font(20), fill=(*hex_rgb(C_WHITE), 80))
    d.text((W-PAD, footer_y+38), "@prismfxpro", font=get_font(24), fill=(*hex_rgb(C_GOLD), 160), anchor="ra")

    buf = BytesIO(); img.save(buf, "PNG", quality=95); buf.seek(0)
    return buf

# ── SİNYAL GÖRSELİ ──────────────────────────────────────
def create_signal_image(symbol, direction, entry, tp, sl, is_vip=False):
    W, H = 1080, 520
    img = Image.new("RGB", (W, H), hex_rgb(C_BG))
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 110], fill=hex_rgb(C_HEADER))
    label = "VIP SİNYAL" if is_vip else "SİNYAL"
    d.text((48, 28), f"PRISM FX · {label}", font=get_font(22), fill=hex_rgb(C_GOLD))
    full_symbol = SYMBOL_MAP.get(symbol.upper(), symbol.upper())
    d.text((48, 62), full_symbol, font=get_font(42, True), fill=hex_rgb(C_WHITE))

    dir_color = C_GREEN if direction.upper() in ("AL", "BUY", "LONG") else C_RED
    dir_text  = "LONG" if direction.upper() in ("AL", "BUY", "LONG") else "SHORT"
    d.rounded_rectangle([W-200, 24, W-48, 86], radius=10, fill=(*hex_rgb(dir_color), 30), outline=hex_rgb(dir_color), width=2)
    d.text(((W-200+W-48)//2, 55), dir_text, font=get_font(30, True), fill=hex_rgb(dir_color), anchor="mm")

    d.rectangle([48, 118, W-48, 119], fill=(*hex_rgb(C_GOLD), 40))

    # 3 kart
    cw, ch, cy = 310, 110, 134
    for i, (lbl, val, clr) in enumerate([
        ("GİRİŞ", str(entry), C_WHITE),
        ("HEDEF", str(tp), C_GREEN),
        ("STOP", str(sl), C_RED),
    ]):
        cx = 48 + i * (cw + 27)
        d.rounded_rectangle([cx, cy, cx+cw, cy+ch], radius=12,
            fill=(*hex_rgb(clr), 15) if clr != C_WHITE else hex_rgb(C_CARD),
            outline=(*hex_rgb(clr), 60) if clr != C_WHITE else hex_rgb(C_BORDER), width=1)
        d.text((cx+cw//2, cy+28), lbl, font=get_font(20), fill=(*hex_rgb(clr), 160), anchor="mm")
        d.text((cx+cw//2, cy+72), str(val), font=get_font(40, True), fill=hex_rgb(clr), anchor="mm")

    # R:R hesapla
    try:
        e_f, tp_f, sl_f = float(str(entry).replace(",",".")), float(str(tp).replace(",",".")), float(str(sl).replace(",","."))
        reward = abs(tp_f - e_f)
        risk   = abs(e_f - sl_f)
        rr = round(reward / risk, 2) if risk > 0 else 0
        rr_text = f"Risk / Ödül Oranı:  1 : {rr}   |   Risk: {round(risk,2)}   |   Hedef: +{round(reward,2)}"
    except:
        rr_text = "R:R hesaplanamadı"

    d.rounded_rectangle([48, 262, W-48, 318], radius=10, fill=hex_rgb(C_CARD), outline=hex_rgb(C_BORDER), width=1)
    d.text((W//2, 290), rr_text, font=get_font(22), fill=hex_rgb(C_GOLD), anchor="mm")

    d.rectangle([48, 332, W-48, 333], fill=(*hex_rgb(C_WHITE), 10))
    d.text((48, 348), "⚠️ Yatırım tavsiyesi değildir. Kendi risk yönetiminizi uygulayınız.", font=get_font(20), fill=hex_rgb(C_MUTED))

    d.rectangle([0, 390, W, H], fill=hex_rgb(C_HEADER))
    d.text((48, 416), "PRISM FX", font=get_font(34, True), fill=hex_rgb(C_WHITE))
    d.text((48, 458), "Telegram · Discord · prismfxpro.com", font=get_font(20), fill=(*hex_rgb(C_WHITE), 80))
    d.text((W-48, 434), "@prismfxpro", font=get_font(24), fill=(*hex_rgb(C_GOLD), 160), anchor="ra")

    buf = BytesIO(); img.save(buf, "PNG", quality=95); buf.seek(0)
    return buf

# ── FOREKs FACTORy ──────────────────────────────────────
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
                                "time": ts,
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
        logger.error(f"FF hatası: {e}")
    return []

# ── SABAH TAKVİM ─────────────────────────────────────────
async def send_morning_summary(bot):
    events = await get_events()
    now = datetime.now(TIMEZONE)
    date_str = now.strftime("%d %B %Y · %A · 08:00")
    img = create_calendar_image(events, date_str)

    caption = "📅 *GÜNÜN EKONOMİK TAKVİMİ*\n"
    if not events:
        caption += "\nBugün yüksek önemli veri bulunmamaktadır."
    else:
        for e in events:
            flag = COUNTRY_FLAGS.get(e["country"],"🌐")
            caption += f"\n🔴 `{e['time_local']}` {flag} *{translate(e['title'])}*"
    caption += "\n\n⚠️ _Yatırım tavsiyesi değildir._\n📊 @prismfxpro"

    await bot.send_photo(chat_id=COMMUNITY, photo=img, caption=caption, parse_mode="Markdown")
    logger.info("Sabah takvimi gönderildi.")

# ── 15 DK UYARISI ────────────────────────────────────────
async def check_upcoming(bot):
    events = await get_events()
    now = datetime.now(TIMEZONE)
    for e in events:
        dt = e.get("dt")
        if not dt: continue
        diff = (dt - now).total_seconds() / 60
        if 14 <= diff <= 16:
            flag = COUNTRY_FLAGS.get(e["country"],"🌐")
            tr = translate(e["title"])
            fc = f"\n📈 Beklenti: *{e['forecast']}*" if e.get("forecast") else ""
            pv = f"\n📊 Önceki: {e['previous']}" if e.get("previous") else ""
            msg = (f"⚠️ *15 DAKİKA SONRA VERİ AÇIKLANACAK!*\n\n"
                   f"🔴 {flag} *{tr}*\n🕐 Saat: `{e['time_local']}`{fc}{pv}\n\n"
                   f"_Piyasalarda volatilite artabilir. Risk yönetimine dikkat!_\n\n"
                   f"⚠️ _Yatırım tavsiyesi değildir._\n📊 @prismfxpro")
            await bot.send_message(chat_id=COMMUNITY, text=msg, parse_mode="Markdown")
            logger.info(f"15dk uyarı: {tr}")

# ── VERİ SONUCU ──────────────────────────────────────────
async def check_results(bot):
    events = await get_events()
    now = datetime.now(TIMEZONE)
    for e in events:
        dt = e.get("dt")
        if not dt: continue
        diff = (now - dt).total_seconds() / 60
        # Açıklandıktan 2-4 dk sonra sonucu gönder
        if 2 <= diff <= 4 and e.get("actual"):
            flag = COUNTRY_FLAGS.get(e["country"],"🌐")
            tr = translate(e["title"])
            actual = e["actual"]
            forecast = e.get("forecast","?")
            previous = e.get("previous","?")

            try:
                a = float(actual.replace("K","000").replace("M","000000").replace("%","").replace(",","."))
                f = float(forecast.replace("K","000").replace("M","000000").replace("%","").replace(",","."))
                if a > f:
                    emoji = "🟢"
                    yorum = "Beklentinin üzerinde geldi"
                elif a < f:
                    emoji = "🔴"
                    yorum = "Beklentinin altında geldi"
                else:
                    emoji = "🟡"
                    yorum = "Beklentiyle uyumlu geldi"
            except:
                emoji = "📊"
                yorum = "Veri açıklandı"

            msg = (f"{emoji} *VERİ SONUCU AÇIKLANDI*\n\n"
                   f"{flag} *{tr}*\n\n"
                   f"✅ Gerçekleşen: *{actual}*\n"
                   f"📈 Beklenti: {forecast}\n"
                   f"📊 Önceki: {previous}\n\n"
                   f"_{yorum}_\n\n"
                   f"⚠️ _Yatırım tavsiyesi değildir._\n📊 @prismfxpro")
            await bot.send_message(chat_id=COMMUNITY, text=msg, parse_mode="Markdown")
            logger.info(f"Sonuç gönderildi: {tr} = {actual}")

# ── SİNYAL KOMUTLARI ─────────────────────────────────────
def parse_signal(text):
    """ALTIN AL 2318 TP 2340 SL 2300 → dict"""
    parts = text.upper().split()
    try:
        symbol   = parts[0]
        direction = parts[1]
        entry    = parts[2]
        tp       = parts[parts.index("TP")+1]
        sl       = parts[parts.index("SL")+1]
        return {"symbol": symbol, "direction": direction, "entry": entry, "tp": tp, "sl": sl}
    except:
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    bot  = context.bot

    # !sinyal komutu — her iki gruba tam sinyal
    if text.lower().startswith("!sinyal "):
        signal_text = text[8:].strip()
        s = parse_signal(signal_text)
        if not s:
            await msg.reply_text("⚠️ Format hatalı. Örnek: !sinyal ALTIN AL 2318 TP 2340 SL 2300")
            return
        await msg.delete()
        img = create_signal_image(s["symbol"], s["direction"], s["entry"], s["tp"], s["sl"], is_vip=False)

        caption = (f"📊 *SİNYAL*\n\n"
                   f"*{SYMBOL_MAP.get(s['symbol'], s['symbol'])}* · "
                   f"{'LONG 🟢' if s['direction'] in ('AL','BUY','LONG') else 'SHORT 🔴'}\n\n"
                   f"Giriş: `{s['entry']}` | Hedef: `{s['tp']}` | Stop: `{s['sl']}`\n\n"
                   f"⚠️ _Yatırım tavsiyesi değildir._\n📊 @prismfxpro")

        img2 = create_signal_image(s["symbol"], s["direction"], s["entry"], s["tp"], s["sl"], is_vip=False)
        await bot.send_photo(chat_id=COMMUNITY, photo=img, caption=caption, parse_mode="Markdown")
        await bot.send_photo(chat_id=VIP, photo=img2, caption=caption, parse_mode="Markdown")
        logger.info(f"Sinyal gönderildi: {signal_text}")

    # !vip komutu — community'ye teaser, VIP'e tam sinyal
    elif text.lower().startswith("!vip "):
        signal_text = text[5:].strip()
        s = parse_signal(signal_text)
        if not s:
            await msg.reply_text("⚠️ Format hatalı. Örnek: !vip ALTIN AL 2318 TP 2340 SL 2300")
            return
        await msg.delete()

        full_symbol = SYMBOL_MAP.get(s["symbol"], s["symbol"])
        dir_emoji   = "🟢 LONG" if s["direction"] in ("AL","BUY","LONG") else "🔴 SHORT"

        # Community'ye teaser
        teaser = (f"👑 *VIP SİNYAL VERİLDİ*\n\n"
                  f"*{full_symbol}* · {dir_emoji}\n\n"
                  f"Giriş, hedef ve stop seviyeleri için VIP kanala katıl 👇\n"
                  f"t.me/+KPo5wu7MwlQ1YzA0\n\n"
                  f"⚠️ _Yatırım tavsiyesi değildir._\n📊 @prismfxpro")
        await bot.send_message(chat_id=COMMUNITY, text=teaser, parse_mode="Markdown")

        # VIP'e tam sinyal
        img = create_signal_image(s["symbol"], s["direction"], s["entry"], s["tp"], s["sl"], is_vip=True)
        caption = (f"👑 *VIP SİNYAL*\n\n"
                   f"*{full_symbol}* · {dir_emoji}\n\n"
                   f"Giriş: `{s['entry']}` | Hedef: `{s['tp']}` | Stop: `{s['sl']}`\n\n"
                   f"⚠️ _Yatırım tavsiyesi değildir._\n📊 @prismfxpro")
        await bot.send_photo(chat_id=VIP, photo=img, caption=caption, parse_mode="Markdown")
        logger.info(f"VIP sinyal gönderildi: {signal_text}")

# ── ANA FONKSİYON ────────────────────────────────────────
async def main():
    bot  = Bot(token=TOKEN)
    app  = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    scheduler.add_job(send_morning_summary, "cron", hour=8, minute=0, args=[bot])
    scheduler.add_job(check_upcoming, "interval", minutes=5, args=[bot])
    scheduler.add_job(check_results,  "interval", minutes=2, args=[bot])
    scheduler.start()

    logger.info("Prism FX Bot başlatıldı!")
    async with app:
        await app.start()
        await app.updater.start_polling()
        while True:
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
