import os
import asyncio
import random
import requests
from collections import defaultdict
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from config import BOT_TOKEN, OWNER_ID, API_URL, API_KEY, WEBHOOK_PATH

# ================= STATES =================
STATES = {
    "AN":"Andaman & Nicobar Islands","AP":"Andhra Pradesh","AR":"Arunachal Pradesh","AS":"Assam",
    "BR":"Bihar","CH":"Chandigarh","CG":"Chhattisgarh","DD":"Daman & Diu","DL":"Delhi",
    "DN":"Dadra & Nagar Haveli","GA":"Goa","GJ":"Gujarat","HR":"Haryana","HP":"Himachal Pradesh",
    "JH":"Jharkhand","JK":"Jammu & Kashmir","KA":"Karnataka","KL":"Kerala","LA":"Ladakh",
    "LD":"Lakshadweep","MH":"Maharashtra","ML":"Meghalaya","MN":"Manipur","MP":"Madhya Pradesh",
    "MZ":"Mizoram","NL":"Nagaland","OD":"Odisha","PB":"Punjab","PY":"Puducherry",
    "RJ":"Rajasthan","SK":"Sikkim","TN":"Tamil Nadu","TR":"Tripura","TS":"Telangana",
    "UK":"Uttarakhand","UP":"Uttar Pradesh","WB":"West Bengal"
}
STATES_PER_PAGE = 8

# ================= REALISTIC DATA =================
RTO_CODES = {
    "AP":["01","02","03","04","05","07","08","09","10","11","12"],
    "MH":["01","02","03","04","05","06","07","08","09","10","12","14"],
    "KA":["01","02","03","04","05","51","53"],
    "DL":["01","02","03","04","05","06","07","08","09","10"],
    "TN":["01","02","03","04","05","06","07","09","10","11"]
}

COMMON_SERIES = [
    "AA","AB","AC","AD","AE","AF","AG",
    "BA","BB","BC","BD",
    "CA","CB","CC",
    "DA","DB",
    "EA","EB"
]

# ================= ADAPTIVE MEMORY =================
LEARNED_PREFIXES = defaultdict(set)

# ================= RUNTIME =================
session = {}
stop_flags = {}
awaiting_custom = {}

# ================= HELPERS =================
def owner_only(uid): 
    return uid == OWNER_ID

def gen_vehicle(state):
    if LEARNED_PREFIXES[state] and random.random() < 0.7:
        rto, series = random.choice(list(LEARNED_PREFIXES[state]))
    else:
        rto = random.choice(RTO_CODES.get(state, ["01"]))
        series = random.choice(COMMON_SERIES)
    number = random.randint(100, 9999)
    return f"{state}{rto}{series}{number}"

def fetch_vehicle_sync(reg):
    try:
        r = requests.get(API_URL, params={"reg": reg, "key": API_KEY}, timeout=8)
        if r.status_code == 200:
            j = r.json()
            if j.get("mobile_no"):
                state, rto, series = reg[:2], reg[2:4], reg[4:6]
                LEARNED_PREFIXES[state].add((rto, series))
                return f"{j['reg_no']} | {j['mobile_no']}"
    except:
        pass
    return None

# ================= UI =================
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚗 States", callback_data="menu_states")],
        [InlineKeyboardButton("🔎 Custom Vehicle Search", callback_data="menu_custom")]
    ])

def states_menu(page=0):
    items = list(STATES.items())
    start, end = page * STATES_PER_PAGE, (page + 1) * STATES_PER_PAGE
    buttons = [[InlineKeyboardButton(name, callback_data=f"state_{code}")]
               for code, name in items[start:end]]
    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅ Prev", callback_data=f"page_{page-1}"))
    if end < len(items): nav.append(InlineKeyboardButton("Next ➡", callback_data=f"page_{page+1}"))
    if nav: buttons.append(nav)
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="menu_back")])
    return InlineKeyboardMarkup(buttons)

def mode_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Single", callback_data="mode_single")],
        [InlineKeyboardButton("📦 Batch (50)", callback_data="mode_batch")],
        [InlineKeyboardButton("♾ Unlimited (1 by 1)", callback_data="mode_unlimited")],
        [InlineKeyboardButton("🛑 Cancel", callback_data="mode_cancel")]
    ])

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not owner_only(update.effective_user.id): return
    await update.message.reply_text("Choose option:", reply_markup=main_menu())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    stop_flags[uid] = True
    awaiting_custom.pop(uid, None)
    await update.message.reply_text("🛑 Cancelled")

# ================= CALLBACKS =================
async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if not owner_only(uid): return

    if q.data == "menu_states":
        await q.edit_message_text("Select State:", reply_markup=states_menu(0))

    elif q.data.startswith("page_"):
        await q.edit_message_text("Select State:", reply_markup=states_menu(int(q.data.split("_")[1])))

    elif q.data == "menu_custom":
        awaiting_custom[uid] = True
        await q.edit_message_text("Send vehicle number (e.g. MH02AB1234):")

    elif q.data.startswith("state_"):
        session[uid] = q.data.split("_")[1]
        stop_flags[uid] = False
        await q.edit_message_text("Choose mode:", reply_markup=mode_menu())

    elif q.data == "mode_cancel":
        stop_flags[uid] = True
        await q.edit_message_text("🛑 Cancelled", reply_markup=main_menu())

    elif q.data == "mode_single":
        state = session.get(uid)
        await q.edit_message_text("⏳ Fetching...")
        res = await asyncio.to_thread(fetch_vehicle_sync, gen_vehicle(state))
        await context.bot.send_message(q.message.chat_id, res or "❌ No data")

    elif q.data == "mode_batch":
        state = session.get(uid)
        await q.edit_message_text("⏳ Batch started...")
        for _ in range(50):
            if stop_flags.get(uid): break
            res = await asyncio.to_thread(fetch_vehicle_sync, gen_vehicle(state))
            if res:
                await context.bot.send_message(q.message.chat_id, res)
            await asyncio.sleep(0.4)
        await context.bot.send_message(q.message.chat_id, "✅ Batch done")

    elif q.data == "mode_unlimited":
        state = session.get(uid)
        await q.edit_message_text("♾ Unlimited started. Use /cancel to stop.")
        stop_flags[uid] = False
        while not stop_flags.get(uid):
            res = await asyncio.to_thread(fetch_vehicle_sync, gen_vehicle(state))
            if res:
                await context.bot.send_message(q.message.chat_id, res)
            await asyncio.sleep(0.6)
        await context.bot.send_message(q.message.chat_id, "🛑 Unlimited stopped")

    elif q.data == "menu_back":
        await q.edit_message_text("Choose option:", reply_markup=main_menu())

# ================= CUSTOM INPUT =================
async def custom_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not owner_only(uid) or not awaiting_custom.get(uid): return
    awaiting_custom.pop(uid, None)
    reg = update.message.text.strip().upper()
    await update.message.reply_text("⏳ Searching...")
    res = await asyncio.to_thread(fetch_vehicle_sync, reg)
    await update.message.reply_text(res or "❌ No data", reply_markup=main_menu())

# ================= TELEGRAM APP =================
telegram_app = Application.builder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("cancel", cancel))
telegram_app.add_handler(CallbackQueryHandler(callbacks))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, custom_input))

# ================= WEBHOOK =================
async def webhook(request):
    update = Update.de_json(await request.json(), telegram_app.bot)
    await telegram_app.process_update(update)
    return web.Response(text="ok")

async def main():
    await telegram_app.initialize()
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
