import asyncio
import os
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from urllib.parse import unquote

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8817431816:AAEo_1VUwmuTfMYvgFVGE_yE-RBSujWORtM"
ADMIN_ID = int(os.getenv("ADMIN_ID") or "7948989650")
API_URL = os.getenv("API_URL") or "https://king-burger-api.up.railway.app"
BOT_SECRET = os.getenv("BOT_SECRET") or ""
BOT_PORT = int(os.getenv("BOT_PORT") or "8080")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Faol zakazlar: order_id -> {message_id, task_pin, task_resend}
pending_orders: dict = {}


async def update_order_status(order_id: str, status: str):
    url = f"{API_URL}/api/orders/{order_id}/status"
    headers = {"Content-Type": "application/json"}
    if BOT_SECRET:
        headers["x-bot-secret"] = BOT_SECRET
    try:
        async with aiohttp.ClientSession() as session:
            async with session.patch(url, json={"status": status}, headers=headers) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    print(f"Status yangilanmadi ({resp.status}): {text}")
    except Exception as e:
        print("Backendga ulanishda xatolik:", e)


def admin_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Qabul qildim", callback_data=f"accept:{order_id}"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel:{order_id}"),
    ]])


def cancel_pending_tasks(order_id: str):
    if order_id in pending_orders:
        data = pending_orders.pop(order_id)
        for key in ("task_pin", "task_resend"):
            t = data.get(key)
            if t and not t.done():
                t.cancel()


async def pin_after_1min(order_id: str, message_id: int):
    await asyncio.sleep(60)
    if order_id not in pending_orders:
        return
    try:
        await bot.pin_chat_message(ADMIN_ID, message_id, disable_notification=False)
        print(f"#{order_id} — 1 daqiqa o'tdi, xabar pin qilindi")
    except Exception as e:
        print(f"Pin xatolik: {e}")


async def resend_after_2min(order_id: str, text: str, original_msg_id: int):
    await asyncio.sleep(120)
    if order_id not in pending_orders:
        return
    try:
        reminder = (
            f"⚠️ <b>DIQQAT! JAVOB BERILMAGAN BUYURTMA!</b>\n\n"
            f"{text}\n\n"
            f"⏰ <b>2 daqiqa o'tdi — tezroq javob bering!</b>"
        )
        sent = await bot.send_message(
            ADMIN_ID,
            reminder,
            parse_mode="HTML",
            reply_markup=admin_keyboard(order_id),
            reply_to_message_id=original_msg_id,
        )
        pending_orders[order_id]["message_id"] = sent.message_id
        print(f"#{order_id} — 2 daqiqa o'tdi, qayta yuborildi")
    except Exception as e:
        print(f"Qayta yuborish xatolik: {e}")


async def send_new_order(order_id: str, text: str) -> int:
    """Yangi zakaz xabarini adminga yuboradi va taymerni ishga tushiradi."""
    sent = await bot.send_message(
        ADMIN_ID,
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard(order_id),
    )
    task_pin = asyncio.create_task(pin_after_1min(order_id, sent.message_id))
    task_resend = asyncio.create_task(resend_after_2min(order_id, text, sent.message_id))
    pending_orders[order_id] = {
        "message_id": sent.message_id,
        "task_pin": task_pin,
        "task_resend": task_resend,
    }
    return sent.message_id


# ---- HTTP endpoint: server.js bu yerga yuboradi ----
async def handle_new_order(request: web.Request):
    """POST /notify — server.js dan kelgan yangi zakaz."""
    try:
        data = await request.json()
        order_id = str(data.get("orderId", ""))
        text = data.get("text", "")
        if not order_id or not text:
            return web.json_response({"ok": False, "error": "orderId va text kerak"}, status=400)
        await send_new_order(order_id, text)
        return web.json_response({"ok": True})
    except Exception as e:
        print("handle_new_order xatolik:", e)
        return web.json_response({"ok": False, "error": str(e)}, status=500)


# ---- Aiogram handlers ----
@dp.message(CommandStart())
async def start_handler(message: Message, command: CommandStart):
    args = command.args
    if args and args.startswith("order"):
        try:
            order_text = unquote(args)
        except Exception:
            order_text = args

        user = message.from_user
        user_info = f"👤 Mijoz: {user.full_name}"
        if user.username:
            user_info += f" (@{user.username})"
        user_info += f"\n🆔 ID: {user.id}"

        admin_msg = (
            f"🔔 <b>YANGI BUYURTMA!</b>\n\n"
            f"{user_info}\n\n"
            f"📋 <b>Buyurtma:</b>\n{order_text}"
        )
        order_id = str(message.message_id)
        await send_new_order(order_id, admin_msg)

        await message.answer(
            "✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
            "⏱ Tez orada siz bilan bog'lanamiz.\n"
            "📞 Savollar uchun: <b>+998 77 160 47 01</b>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🍔 <b>King Burger botiga xush kelibsiz!</b>\n\n"
            "Buyurtma berish uchun saytimizga o'ting va mahsulotlarni tanlang.\n\n"
            "📞 Telefon: <b>+998 77 160 47 01</b>\n"
            "📍 Manzil: <b>Olimbek sh., Fidokorlar ko'chasi</b>\n"
            "🕐 Ish vaqti: <b>08:00 — 23:30</b>",
            parse_mode="HTML"
        )


@dp.callback_query(F.data.startswith("accept:"))
async def accept_order(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]
    cancel_pending_tasks(order_id)
    await update_order_status(order_id, "qabul_qilindi")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply("✅ <b>Buyurtma qabul qilindi!</b>", parse_mode="HTML")
    await callback.answer("✅ Qabul qilindi!")


@dp.callback_query(F.data.startswith("cancel:"))
async def cancel_order(callback: CallbackQuery):
    order_id = callback.data.split(":")[1]
    cancel_pending_tasks(order_id)
    await update_order_status(order_id, "bekor_qilindi")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.reply("❌ <b>Buyurtma bekor qilindi.</b>", parse_mode="HTML")
    await callback.answer("❌ Bekor qilindi!")


async def main():
    print("Bot ishga tushdi...")

    # HTTP server (server.js dan notify olish uchun)
    app_web = web.Application()
    app_web.router.add_post("/notify", handle_new_order)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", BOT_PORT)
    await site.start()
    print(f"HTTP server {BOT_PORT}-portda ishga tushdi")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
