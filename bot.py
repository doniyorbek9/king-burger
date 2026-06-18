import asyncio
import os
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from urllib.parse import unquote

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8817431816:AAEo_1VUwmuTfMYvgFVGE_yE-RBSujWORtM"
ADMIN_ID = int(os.getenv("ADMIN_ID") or "7948989650")
API_URL = os.getenv("API_URL") or "https://king-burger-api.up.railway.app"
BOT_SECRET = os.getenv("BOT_SECRET") or ""

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Pending orders: order_id -> {chat_id, message_id, order_text, task_pin, task_resend}
pending_orders: dict = {}


async def update_order_status(order_id: str, status: str):
    """Saytdagi buyurtma holatini backend orqali yangilaydi."""
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


async def pin_order_after_timeout(order_id: str, chat_id: int, message_id: int):
    """1 daqiqa javob bo'lmasa xabarni pin qiladi."""
    await asyncio.sleep(60)  # 1 daqiqa
    if order_id not in pending_orders:
        return  # Admin allaqachon javob berdi
    try:
        await bot.pin_chat_message(chat_id, message_id, disable_notification=False)
        print(f"Buyurtma #{order_id} pin qilindi (1 daqiqa javob yo'q)")
    except Exception as e:
        print(f"Pin qilishda xatolik: {e}")


async def resend_order_after_timeout(order_id: str, chat_id: int, order_text: str, original_message_id: int):
    """2 daqiqa javob bo'lmasa zakazni qayta yuboradi."""
    await asyncio.sleep(120)  # 2 daqiqa
    if order_id not in pending_orders:
        return  # Admin allaqachon javob berdi
    try:
        reminder_msg = (
            f"⚠️ <b>DIQQAT! JAVOB BERILMAGAN BUYURTMA!</b>\n\n"
            f"🔁 Quyidagi buyurtmaga hali javob berilmadi:\n\n"
            f"{order_text}\n\n"
            f"⏰ <b>2 daqiqa o'tdi — iltimos, tezroq javob bering!</b>"
        )
        sent = await bot.send_message(
            chat_id,
            reminder_msg,
            parse_mode="HTML",
            reply_markup=admin_keyboard(order_id),
            reply_to_message_id=original_message_id,
        )
        # Yangi xabar message_id ni yangilash
        pending_orders[order_id]["message_id"] = sent.message_id
        print(f"Buyurtma #{order_id} qayta yuborildi (2 daqiqa javob yo'q)")
    except Exception as e:
        print(f"Qayta yuborishda xatolik: {e}")


def cancel_pending_tasks(order_id: str):
    """Buyurtma qabul yoki bekor qilinganda taymerni to'xtatadi."""
    if order_id in pending_orders:
        data = pending_orders.pop(order_id)
        task_pin = data.get("task_pin")
        task_resend = data.get("task_resend")
        if task_pin and not task_pin.done():
            task_pin.cancel()
        if task_resend and not task_resend.done():
            task_resend.cancel()


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

        sent = await bot.send_message(
            ADMIN_ID,
            admin_msg,
            parse_mode="HTML",
            reply_markup=admin_keyboard(str(message.message_id))
        )

        order_id = str(message.message_id)

        # Taymerni ishga tushirish
        task_pin = asyncio.create_task(
            pin_order_after_timeout(order_id, ADMIN_ID, sent.message_id)
        )
        task_resend = asyncio.create_task(
            resend_order_after_timeout(order_id, ADMIN_ID, admin_msg, sent.message_id)
        )

        pending_orders[order_id] = {
            "chat_id": ADMIN_ID,
            "message_id": sent.message_id,
            "order_text": admin_msg,
            "task_pin": task_pin,
            "task_resend": task_resend,
        }

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
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
