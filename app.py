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

# ================= STATES =================
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

# ================= RUNTIME =================
session = {}
stop_flags = {}   # used by /cancel

# ================= HELPERS =================
def owner_only(uid):
    return uid == OWNER_ID

def gen_vehicle(state):
    return f"{state}{random.randint(1,99):02d}" \
           f"{chr(random.randint(65,90))}{chr(random.randint(65,90))}" \
           f"{random.randint(1000,9999)}"

def fetch_vehicle_sync(reg):
    try:
        r = requests.get(API_URL, params={"reg": reg, "key": API_KEY}, timeout=8)
        if r.status_code == 200:
            j = r.json()
            if j.get("mobile_no"):
                return f"{j['reg_no']} | {j['mobile_no']}"
    except:
        pass
    return None

# ================= UI =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚗 States", callback_data="menu_states")]
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
        nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"page_{page-1}"))
    if end < len(items):
        nav.append(InlineKeyboardButton("Next ➡", callback_data=f"page_{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="menu_back")])
    return InlineKeyboardMarkup(buttons)

def mode_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Single Vehicle", callback_data="mode_single")],
        [InlineKeyboardButton("📦 1 Batch (50)", callback_data="mode_batch_1")],
        [InlineKeyboardButton("📦 5 Batches (250)", callback_data="mode_batch_5")],
        [InlineKeyboardButton("♾ Unlimited", callback_data="mode_unlimited")]
    ])

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not owner_only(update.effective_user.id):
        return
    await update.message.reply_text("Choose option:", reply_markup=main_menu())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    stop_flags[uid] = True
    await update.message.reply_text("🛑 Stopped all running tasks.")

# ================= CALLBACK HANDLER =================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if not owner_only(q.from_user.id):
        return

    uid = q.from_user.id

    if q.data == "menu_states":
        await q.edit_message_text("Select State:", reply_markup=states_menu(0))

    elif q.data.startswith("page_"):
        page = int(q.data.split("_")[1])
        await q.edit_message_text("Select State:", reply_markup=states_menu(page))

    elif q.data.startswith("state_"):
        state = q.data.split("_")[1]
        session[uid] = state
        stop_flags[uid] = False
        await q.edit_message_text(
            f"State selected: {state}\nChoose mode:",
            reply_markup=mode_menu()
        )

    elif q.data.startswith("mode_"):
        state = session.get(uid)
        if not state:
            return

        stop_flags[uid] = False
        await q.edit_message_text("⏳ Fetching...")

        # ---------- SINGLE ----------
        if q.data == "mode_single":
            result = await asyncio.to_thread(
                fetch_vehicle_sync,
                gen_vehicle(state)
            )
            await context.bot.send_message(
                q.message.chat_id,
                result if result else "❌ No data found"
            )
            return

        # ---------- BATCH / UNLIMITED ----------
        unlimited = q.data == "mode_unlimited"
        batches = 999999 if unlimited else int(q.data.split("_")[-1])

        sent = 0
        for _ in range(batches):
            if stop_flags.get(uid):
                await context.bot.send_message(q.message.chat_id, "🛑 Cancelled")
                return

            results = []
            for _ in range(50):
                data = await asyncio.to_thread(
                    fetch_vehicle_sync,
                    gen_vehicle(state)
                )
                if data:
                    results.append(data)

            if results:
                await context.bot.send_message(
                    q.message.chat_id,
                    "\n".join(results)
                )

            sent += 1
            await asyncio.sleep(1.5)

            if unlimited and sent >= 20:
                break

        await context.bot.send_message(q.message.chat_id, "✅ Done")

    elif q.data == "menu_back":
        await q.edit_message_text("Choose option:", reply_markup=main_menu())

# ================= TELEGRAM APP =================
telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("cancel", cancel))
telegram_app.add_handler(CallbackQueryHandler(callbacks))

# ================= WEBHOOK =================
async def webhook(request):
    update = Update.de_json(await request.json(), telegram_app.bot)
    await telegram_app.process_update(update)
    return web.Response(text="ok")

async def main():
    await telegram_app.initialize()

    base_url = os.getenv("RENDER_EXTERNAL_URL")
    if base_url:
        await telegram_app.bot.set_webhook(base_url + WEBHOOK_PATH)

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
