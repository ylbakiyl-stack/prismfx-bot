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

# ── ENV ──────────────────────────────────────────────────
TOKEN     = os.environ.get("BOT_TOKEN")
COMMUNITY = os.environ.get("CHAT_ID")
VIP       = os.environ.get("VIP_CHAT_ID")
TIMEZONE  = pytz.timezone("Europe/Istanbul")

# ── FONT ─────────────────────────────────────────────────
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]

def find_font(bold=False):
    candidates = [p for p in FONT_PATHS if ("Bold" in p) == bold]
    for p in candidates:
        if os.path.exists(p):
            return p
    # fallback: herhangi bir ttf
    for p in FONT_PATHS:
        if os.path.exists(p):
            return p
    return None

def get_font(size, bold=False):
    path = find_font(bold)
    try:
        if path:
            return ImageFont.truetype(path, size)
    except:
        pass
    return ImageFont.load_default()

# ── RENKLER ──────────────────────────────────────────────
C_BG     = "#0A1828"
C_HEADER = "#042C53"
C_GOLD   = "#FAC775"
C_RED    = "#E24B4A"
C_GREEN  = "#5DCAA5"
C_WHITE  = "#FFFFFF"
C_MUTED  = "#6B7A8D"
C_CARD   = "#0F1E2E"
C_BORDER = "#1A3050"

def hex_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)

# ── ÇEVİRİ ───────────────────────────────────────────────
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
    "Inflation Report": "Enflasyon Raporu",
    "Core PCE Price Index m/m": "Cekirdek PCE Fiyat Endeksi",
    "Crude Oil": "Ham Petrol",
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

def translate(title):
    for en, tr in TRANSLATIONS.items():
        if en.lower() in title.lower():
            return tr
    return title

def country_label(c):
    labels = {
        "USD":"[ABD]","EUR":"[AB]","GBP":"[GBR]",
        "JPY":"[JPN]","CNY":"[CHN]","AUD":"[AUS]",
        "CAD":"[CAN]","CHF":"[ISV]","NZD":"[YZL]","TRY":"[TUR]",
    }
    return labels.get(c, "")

# ── TAKVİM GÖRSELİ ──────────────────────────────────────
def create_calendar_image(events, date_str):
    S = 2
    W = 1080 * S
    PAD = 56 * S
    HEADER_H = 150 * S
    CARD_H = 100 * S
    GAP = 14 * S
    FOOTER_H = 110 * S
    n = max(len(events), 1)
    H = HEADER_H + 24*S + (CARD_H + GAP) * n + 70*S + FOOTER_H

    img = Image.new("RGB", (W, H), hex_rgb(C_BG))
    d = ImageDraw.Draw(img)

    # Header
    d.rectangle([0, 0, W, HEADER_H], fill=hex_rgb(C_HEADER))
    d.text((PAD, 30*S), "PRISM FX - OTOMATIK EKONOMIK TAKVIM", font=get_font(20*S), fill=hex_rgb(C_GOLD))
    d.text((PAD, 64*S), "Gunun Ekonomik Takvimi", font=get_font(36*S, True), fill=hex_rgb(C_WHITE))
    d.text((PAD, 114*S), date_str, font=get_font(20*S), fill=hex_rgb(C_MUTED))
    d.rectangle([PAD, HEADER_H+10*S, W-PAD, HEADER_H+13*S], fill=hex_rgb(C_GOLD))

    y = HEADER_H + 28*S
    if not events:
        d.text((PAD, y+30*S), "Bugun yuksek onemli veri bulunmamaktadir.", font=get_font(26*S), fill=hex_rgb(C_MUTED))
    else:
        for e in events:
            d.rounded_rectangle([PAD, y, W-PAD, y+CARD_H], radius=14*S, fill=hex_rgb(C_CARD), outline=hex_rgb(C_BORDER), width=2)
            d.rounded_rectangle([PAD, y, PAD+7*S, y+CARD_H], radius=4*S, fill=hex_rgb(C_RED))
            d.text((PAD+20*S, y+18*S), e.get("time_local","--:--"), font=get_font(26*S, True), fill=hex_rgb(C_RED))
            flag = country_label(e.get("country",""))
            title = translate(e.get("title",""))
            d.text((PAD+125*S, y+18*S), f"{flag} {title}", font=get_font(26*S, True), fill=hex_rgb(C_WHITE))
            parts = []
            if e.get("forecast"): parts.append(f"Beklenti: {e['forecast']}")
            if e.get("previous"): parts.append(f"Onceki: {e['previous']}")
            sub = "  |  ".join(parts) if parts else "Veri bekleniyor"
            d.text((PAD+125*S, y+60*S), sub, font=get_font(19*S), fill=hex_rgb(C_MUTED))
            y += CARD_H + GAP

    d.rectangle([PAD, y+14*S, W-PAD, y+16*S], fill=hex_rgb(C_BORDER))
    d.text((PAD, y+26*S), "Yuksek Onemli Veriler  |  Yatirim tavsiyesi degildir.", font=get_font(18*S), fill=hex_rgb(C_MUTED))

    fy = H - FOOTER_H
    d.rectangle([0, fy, W, H], fill=hex_rgb(C_HEADER))
    d.text((PAD, fy+26*S), "PRISM FX", font=get_font(32*S, True), fill=hex_rgb(C_WHITE))
    d.text((PAD, fy+68*S), "Telegram  |  Discord  |  prismfxpro.com", font=get_font(19*S), fill=hex_rgb(C_MUTED))
    handle = "@prismfxpro"
    hb = d.textbbox((0,0), handle, font=get_font(22*S))
    d.text((W-PAD-(hb[2]-hb[0]), fy+46*S), handle, font=get_font(22*S), fill=hex_rgb(C_GOLD))

    out = img.resize((W//S, H//S), Image.LANCZOS)
    buf = BytesIO(); out.save(buf, "PNG", quality=95); buf.seek(0)
    return buf

# ── SİNYAL GÖRSELİ ──────────────────────────────────────
def create_signal_image(symbol, direction, entry, tp, sl, is_vip=False):
    S = 2
    W, H = 1080*S, 560*S
    img = Image.new("RGB", (W, H), hex_rgb(C_BG))
    d = ImageDraw.Draw(img)
    PAD = 56*S

    # Header
    d.rectangle([0, 0, W, 120*S], fill=hex_rgb(C_HEADER))
    label = "VIP SINYAL" if is_vip else "SINYAL"
    d.text((PAD, 26*S), f"PRISM FX  -  {label}", font=get_font(20*S), fill=hex_rgb(C_GOLD))
    full_symbol = SYMBOL_MAP.get(symbol.upper(), symbol.upper())
    d.text((PAD, 58*S), full_symbol, font=get_font(42*S, True), fill=hex_rgb(C_WHITE))

    is_long = direction.upper() in ("AL","BUY","LONG")
    dir_color = C_GREEN if is_long else C_RED
    dir_text  = "LONG" if is_long else "SHORT"
    bw, bh = 170*S, 58*S
    bx, by = W-PAD-bw, 32*S
    d.rounded_rectangle([bx, by, bx+bw, by+bh], radius=10*S, fill=hex_rgb(C_CARD), outline=hex_rgb(dir_color), width=3)
    bbox = d.textbbox((0,0), dir_text, font=get_font(30*S, True))
    tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
    d.text((bx+(bw-tw)//2, by+(bh-th)//2), dir_text, font=get_font(30*S, True), fill=hex_rgb(dir_color))

    d.rectangle([PAD, 128*S, W-PAD, 131*S], fill=hex_rgb(C_GOLD))

    # 3 kart
    cw = (W - 2*PAD - 2*24*S) // 3
    ch = 120*S
    cy = 150*S
    for i, (lbl, val, clr) in enumerate([
        ("GIRIS", str(entry), C_WHITE),
        ("HEDEF", str(tp), C_GREEN),
        ("STOP",  str(sl), C_RED),
    ]):
        cx = PAD + i*(cw+24*S)
        d.rounded_rectangle([cx, cy, cx+cw, cy+ch], radius=14*S,
            fill=hex_rgb(C_CARD), outline=hex_rgb(clr), width=2)
        lb = d.textbbox((0,0), lbl, font=get_font(19*S))
        d.text((cx+(cw-(lb[2]-lb[0]))//2, cy+18*S), lbl, font=get_font(19*S), fill=hex_rgb(C_MUTED))
        vb = d.textbbox((0,0), val, font=get_font(40*S, True))
        d.text((cx+(cw-(vb[2]-vb[0]))//2, cy+52*S), val, font=get_font(40*S, True), fill=hex_rgb(clr))

    # R:R
    try:
        ef = float(str(entry).replace(",","."))
        tf = float(str(tp).replace(",","."))
        sf = float(str(sl).replace(",","."))
        reward = abs(tf-ef); risk = abs(ef-sf)
        rr = round(reward/risk, 2) if risk > 0 else 0
        rr_text = f"Risk / Odul:  1 : {rr}   |   Risk: -{round(risk,1)}   |   Hedef: +{round(reward,1)}"
    except:
        rr_text = "R:R hesaplanamadi"

    ry = cy+ch+22*S
    d.rounded_rectangle([PAD, ry, W-PAD, ry+62*S], radius=10*S, fill=hex_rgb(C_CARD), outline=hex_rgb(C_BORDER), width=2)
    rb = d.textbbox((0,0), rr_text, font=get_font(21*S))
    d.text((PAD+(W-2*PAD-(rb[2]-rb[0]))//2, ry+19*S), rr_text, font=get_font(21*S), fill=hex_rgb(C_GOLD))

    dy = ry+72*S
    d.rectangle([PAD, dy, W-PAD, dy+2], fill=hex_rgb(C_BORDER))
    d.text((PAD, dy+14*S), "Yatirim tavsiyesi degildir. Kendi risk yonetiminizi uygulayiniz.", font=get_font(18*S), fill=hex_rgb(C_MUTED))

    fy = H-110*S
    d.rectangle([0, fy, W, H], fill=hex_rgb(C_HEADER))
    d.text((PAD, fy+24*S), "PRISM FX", font=get_font(32*S, True), fill=hex_rgb(C_WHITE))
    d.text((PAD, fy+66*S), "Telegram  |  Discord  |  prismfxpro.com", font=get_font(19*S), fill=hex_rgb(C_MUTED))
    handle = "@prismfxpro"
    hb = d.textbbox((0,0), handle, font=get_font(22*S))
    d.text((W-PAD-(hb[2]-hb[0]), fy+44*S), handle, font=get_font(22*S), fill=hex_rgb(C_GOLD))

    out = img.resize((W//S, H//S), Image.LANCZOS)
    buf = BytesIO(); out.save(buf, "PNG", quality=95); buf.seek(0)
    return buf

# ── FOREX FACTORY ────────────────────────────────────────
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
        logger.error(f"FF hatasi: {e}")
    return []

# ── SABAH TAKVİM ─────────────────────────────────────────
async def send_morning_summary(bot):
    events = await get_events()
    now = datetime.now(TIMEZONE)
    date_str = now.strftime("%d %B %Y  -  %A")
    img = create_calendar_image(events, date_str)
    caption = "📅 *GUNUN EKONOMIK TAKVIMI*\n"
    if not events:
        caption += "\nBugun yuksek onemli veri bulunmamaktadir."
    else:
        for e in events:
            caption += f"\n🔴 `{e['time_local']}` *{translate(e['title'])}*"
    caption += "\n\n⚠️ _Yatirim tavsiyesi degildir._\n📊 @prismfxpro"
    await bot.send_photo(chat_id=COMMUNITY, photo=img, caption=caption, parse_mode="Markdown")
    logger.info("Sabah takvimi gonderildi.")

# ── 15 DK UYARISI ────────────────────────────────────────
async def check_upcoming(bot):
    events = await get_events()
    now = datetime.now(TIMEZONE)
    for e in events:
        dt = e.get("dt")
        if not dt: continue
        diff = (dt - now).total_seconds() / 60
        if 14 <= diff <= 16:
            tr = translate(e["title"])
            fc = f"\n📈 Beklenti: *{e['forecast']}*" if e.get("forecast") else ""
            pv = f"\n📊 Onceki: {e['previous']}" if e.get("previous") else ""
            msg = (f"⚠️ *15 DAKIKA SONRA VERI ACIKLANACAK!*\n\n"
                   f"🔴 *{tr}*\n🕐 Saat: `{e['time_local']}`{fc}{pv}\n\n"
                   f"_Piyasalarda volatilite artabilir!_\n\n"
                   f"⚠️ _Yatirim tavsiyesi degildir._\n📊 @prismfxpro")
            await bot.send_message(chat_id=COMMUNITY, text=msg, parse_mode="Markdown")
            logger.info(f"15dk uyari: {tr}")

# ── VERİ SONUCU ──────────────────────────────────────────
async def check_results(bot):
    events = await get_events()
    now = datetime.now(TIMEZONE)
    for e in events:
        dt = e.get("dt")
        if not dt: continue
        diff = (now - dt).total_seconds() / 60
        if 2 <= diff <= 4 and e.get("actual"):
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
            msg = (f"{emoji} *VERI SONUCU*\n\n*{tr}*\n\n"
                   f"✅ Gerceklesen: *{actual}*\n"
                   f"📈 Beklenti: {forecast}\n"
                   f"📊 Onceki: {previous}\n\n"
                   f"_{yorum}_\n\n"
                   f"⚠️ _Yatirim tavsiyesi degildir._\n📊 @prismfxpro")
            await bot.send_message(chat_id=COMMUNITY, text=msg, parse_mode="Markdown")
            logger.info(f"Sonuc: {tr} = {actual}")

# ── SİNYAL PARSER ────────────────────────────────────────
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

# ── MESAJ HANDLER ────────────────────────────────────────
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
        caption = (f"📊 *SINYAL*\n\n*{full}*  -  {'LONG 🟢' if is_long else 'SHORT 🔴'}\n\n"
                   f"Giris: `{s['entry']}`  |  Hedef: `{s['tp']}`  |  Stop: `{s['sl']}`\n\n"
                   f"⚠️ _Yatirim tavsiyesi degildir._\n📊 @prismfxpro")
        img1 = create_signal_image(s["symbol"],s["direction"],s["entry"],s["tp"],s["sl"])
        img2 = create_signal_image(s["symbol"],s["direction"],s["entry"],s["tp"],s["sl"])
        await bot.send_photo(chat_id=COMMUNITY, photo=img1, caption=caption, parse_mode="Markdown")
        await bot.send_photo(chat_id=VIP, photo=img2, caption=caption, parse_mode="Markdown")

    elif text.lower().startswith("!vip "):
        s = parse_signal(text[5:].strip())
        if not s:
            await msg.reply_text("Format: !vip ALTIN AL 2318 TP 2340 SL 2300")
            return
        await msg.delete()
        full = SYMBOL_MAP.get(s["symbol"], s["symbol"])
        is_long = s["direction"] in ("AL","BUY","LONG")
        teaser = (f"👑 *VIP SINYAL VERILDI*\n\n*{full}*  -  {'LONG 🟢' if is_long else 'SHORT 🔴'}\n\n"
                  f"Giris, hedef ve stop icin VIP kanala katil 👇\n"
                  f"t.me/+KPo5wu7MwlQ1YzA0\n\n"
                  f"⚠️ _Yatirim tavsiyesi degildir._\n📊 @prismfxpro")
        await bot.send_message(chat_id=COMMUNITY, text=teaser, parse_mode="Markdown")
        caption = (f"👑 *VIP SINYAL*\n\n*{full}*  -  {'LONG 🟢' if is_long else 'SHORT 🔴'}\n\n"
                   f"Giris: `{s['entry']}`  |  Hedef: `{s['tp']}`  |  Stop: `{s['sl']}`\n\n"
                   f"⚠️ _Yatirim tavsiyesi degildir._\n📊 @prismfxpro")
        img = create_signal_image(s["symbol"],s["direction"],s["entry"],s["tp"],s["sl"],is_vip=True)
        await bot.send_photo(chat_id=VIP, photo=img, caption=caption, parse_mode="Markdown")

# ── MAIN ─────────────────────────────────────────────────
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
