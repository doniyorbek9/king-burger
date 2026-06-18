import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import Message
from urllib.parse import unquote

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID") or "7948989650")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message, command: CommandStart):
    args = command.args

    if args and args.startswith("order"):
        # Saytdan kelgan buyurtma
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

        # Adminga yuborish
        await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML")

        # Foydalanuvchiga tasdiqlash
        await message.answer(
            "✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
            "⏱ Tez orada siz bilan bog'lanamiz.\n"
            "📞 Savollar uchun: <b>+998 77 160 47 01</b>",
            parse_mode="HTML"
        )
    else:
        # Oddiy /start
        await message.answer(
            "🍔 <b>King Burger botiga xush kelibsiz!</b>\n\n"
            "Buyurtma berish uchun saytimizga o'ting va mahsulotlarni tanlang.\n\n"
            "📞 Telefon: <b>+998 77 160 47 01</b>\n"
            "📍 Manzil: <b>Olimbek sh., Fidokorlar ko'chasi</b>\n"
            "🕐 Ish vaqti: <b>08:00 — 23:30</b>",
            parse_mode="HTML"
        )


async def main():
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
