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

# ================== STATES (ALL INDIA) ==================

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

STATES_PER_PAGE = 10

# ================== RUNTIME DATA ==================

session = {}
stats = {
    "requests": 0,
    "hits": 0,
    "last_state": "-"
}

def owner_only(uid: int) -> bool:
    return uid == OWNER_ID

# ================== UI ==================

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚗 States", callback_data="menu_states"),
            InlineKeyboardButton("📊 Stats", callback_data="menu_stats")
        ]
    ])

def states_menu(page=0):
    items = list(STATES.items())
    start = page * STATES_PER_PAGE
    end = start + STATES_PER_PAGE

    buttons = [
        [InlineKeyboardButton(name, callback_data=f"state_{code}")]
        for code, name in items[start:end]
    ]

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"states_{page-1}"))
    if end < len(items):
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"states_{page+1}"))

    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="menu_back")])
    return InlineKeyboardMarkup(buttons)

def batch_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("1 Batch (50)", callback_data="batch_1")],
        [InlineKeyboardButton("5 Batches (250)", callback_data="batch_5")],
        [InlineKeyboardButton("10 Batches (500)", callback_data="batch_10")],
        [InlineKeyboardButton("♾ Unlimited", callback_data="batch_unlimited")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_states")]
    ])

# ================== HANDLERS ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not owner_only(update.effective_user.id):
        await update.message.reply_text("⛔ Access Denied")
        return
    await update.message.reply_text("Select option:", reply_markup=main_menu())

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if not owner_only(q.from_user.id):
        await q.edit_message_text("⛔ Access Denied")
        return

    if q.data == "menu_states":
        await q.edit_message_text("Select State (Page 1):", reply_markup=states_menu(0))

    elif q.data.startswith("states_"):
        page = int(q.data.split("_")[1])
        await q.edit_message_text(
            f"Select State (Page {page+1}):",
            reply_markup=states_menu(page)
        )

    elif q.data == "menu_stats":
        await q.edit_message_text(
            f"📊 Stats\n\n"
            f"Requests: {stats['requests']}\n"
            f"Hits: {stats['hits']}\n"
            f"Last State: {stats['last_state']}",
            reply_markup=main_menu()
        )

    elif q.data == "menu_back":
        await q.edit_message_text("Select option:", reply_markup=main_menu())

async def state_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if not owner_only(q.from_user.id):
        await q.edit_message_text("⛔ Access Denied")
        return

    state = q.data.split("_")[1]
    session[q.from_user.id] = state
    stats["last_state"] = state

    await q.edit_message_text(
        f"State selected: {state}\nChoose batch:",
        reply_markup=batch_menu()
    )

# ================== CORE ==================

def gen_vehicle(state):
    return f"{state}{random.randint(1,99):02d}{chr(random.randint(65,90))}{chr(random.randint(65,90))}{random.randint(1000,9999)}"

def fetch_vehicle(reg):
    try:
        r = requests.get(API_URL, params={"reg": reg, "key": API_KEY}, timeout=8)
        stats["requests"] += 1
        if r.status_code == 200:
            j = r.json()
            if j.get("mobile_no"):
                stats["hits"] += 1
                return f"{j['reg_no']} | {j['mobile_no']}"
    except:
        pass
    return None

async def batch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if not owner_only(q.from_user.id):
        return

    state = session.get(q.from_user.id)
    if not state:
        await q.edit_message_text("Restart with /start")
        return

    unlimited = q.data == "batch_unlimited"
    batches = 999999 if unlimited else int(q.data.split("_")[1])

    await q.edit_message_text("⏳ Working...")

    count = 0
    for _ in range(batches):
        result = []
        for _ in range(50):
            d = fetch_vehicle(gen_vehicle(state))
            if d:
                result.append(d)

        if result:
            await context.bot.send_message(q.message.chat_id, "\n".join(result))
            await asyncio.sleep(1)

        count += 1
        if unlimited and count >= 20:
            break

    await context.bot.send_message(q.message.chat_id, "✅ Done")

# ================== APP + WEBHOOK ==================

def build_app():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(menu_handler, pattern="^(menu_|states_)"))
    app.add_handler(CallbackQueryHandler(state_select, pattern="^state_"))
    app.add_handler(CallbackQueryHandler(batch_handler, pattern="^batch_"))
    return app

async def webhook_handler(request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return web.Response(text="ok")

async def main():
    global telegram_app
    telegram_app = build_app()

    await telegram_app.initialize()

    # Render provides this automatically
    import os
    base_url = os.getenv("RENDER_EXTERNAL_URL")
    await telegram_app.bot.set_webhook(f"{base_url}{WEBHOOK_PATH}")

    await telegram_app.start()

    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", "10000")))
    await site.start()

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
