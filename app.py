import os
import asyncio
import random
import requests
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)

from config import BOT_TOKEN, OWNER_ID, API_URL, API_KEY, WEBHOOK_PATH

# ================= STATES (ALL INDIA) =================
STATES = {
    "AN": "Andaman & Nicobar Islands",
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CH": "Chandigarh",
    "CG": "Chhattisgarh",
    "DD": "Daman & Diu",
    "DL": "Delhi",
    "DN": "Dadra & Nagar Haveli",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HR": "Haryana",
    "HP": "Himachal Pradesh",
    "JH": "Jharkhand",
    "JK": "Jammu & Kashmir",
    "KA": "Karnataka",
    "KL": "Kerala",
    "LA": "Ladakh",
    "LD": "Lakshadweep",
    "MH": "Maharashtra",
    "ML": "Meghalaya",
    "MN": "Manipur",
    "MP": "Madhya Pradesh",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OD": "Odisha",
    "PB": "Punjab",
    "PY": "Puducherry",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TN": "Tamil Nadu",
    "TR": "Tripura",
    "TS": "Telangana",
    "UK": "Uttarakhand",
    "UP": "Uttar Pradesh",
    "WB": "West Bengal"
}

STATES_PER_PAGE = 8
session = {}
stats = {"requests": 0, "hits": 0}

# ================= HELPERS =================
def owner_only(uid): return uid == OWNER_ID

def gen_vehicle(state):
    return f"{state}{random.randint(1,99):02d}{chr(random.randint(65,90))}{chr(random.randint(65,90))}{random.randint(1000,9999)}"

def fetch_vehicle(reg):
    try:
        stats["requests"] += 1
        r = requests.get(API_URL, params={"reg": reg, "key": API_KEY}, timeout=8)
        if r.status_code == 200:
            j = r.json()
            if j.get("mobile_no"):
                stats["hits"] += 1
                return f"{j['reg_no']} | {j['mobile_no']}"
    except:
        pass
    return None

# ================= UI =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚗 States", callback_data="menu_states"),
         InlineKeyboardButton("📊 Stats", callback_data="menu_stats")]
    ])

def states_menu(page=0):
    items = list(STATES.items())
    start = page * STATES_PER_PAGE
    end = start + STATES_PER_PAGE

    buttons = [[InlineKeyboardButton(name, callback_data=f"state_{code}")]
               for code, name in items[start:end]]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"page_{page-1}"))
    if end < len(items):
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"page_{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="menu_back")])
    return InlineKeyboardMarkup(buttons)

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not owner_only(update.effective_user.id): return
    await update.message.reply_text("Choose option:", reply_markup=main_menu())

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not owner_only(q.from_user.id): return

    if q.data == "menu_states":
        await q.edit_message_text("Select State:", reply_markup=states_menu())

    elif q.data.startswith("page_"):
        await q.edit_message_text("Select State:", reply_markup=states_menu(int(q.data.split("_")[1])))

    elif q.data.startswith("state_"):
        state = q.data.split("_")[1]
        await q.edit_message_text("⏳ Fetching...")
        out = [fetch_vehicle(gen_vehicle(state)) for _ in range(50)]
        out = [x for x in out if x]
        await context.bot.send_message(q.message.chat_id, "\n".join(out) if out else "No data")

    elif q.data == "menu_stats":
        await q.edit_message_text(
            f"📊 Stats\nRequests: {stats['requests']}\nHits: {stats['hits']}",
            reply_markup=main_menu()
        )

    elif q.data == "menu_back":
        await q.edit_message_text("Choose option:", reply_markup=main_menu())

# ================= TELEGRAM APP =================
telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(callbacks))

# ================= WEBHOOK SERVER =================
async def webhook(request):
    update = Update.de_json(await request.json(), telegram_app.bot)
    await telegram_app.process_update(update)
    return web.Response(text="ok")

async def main():
    await telegram_app.initialize()

    # 🔥 Render-compatible auto webhook
    base = os.getenv("RENDER_EXTERNAL_URL")
    if base:
        await telegram_app.bot.set_webhook(base + WEBHOOK_PATH)

    await telegram_app.start()

    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 10000)))
    await site.start()

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
