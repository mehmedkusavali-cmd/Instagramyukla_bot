import asyncio
import html
import logging
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatAction
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    CallbackQuery,
    TelegramObject,
)

from config import BOT_TOKEN, REQUIRED_CHANNEL
from downloader import (
    extract_instagram_url,
    download_instagram_video,
    MediaPrivateOrNotFoundError,
    MediaTooLargeError,
    InstagramDownloadError,
)
from subscription import (
    check_user_subscription,
    get_subscription_markup,
)
from ai_service import ask_ai, clear_user_history

# Logging sozlash
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Windows konsolida emojilar va UTF-8 to'g'ri ko'rinishi uchun
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


class SubscriptionMiddleware(BaseMiddleware):
    """
    Foydalanuvchi kanallarga a'zo ekanligini har bir xabar va buyruqdan
    oldin tekshiruvchi middleware. A'zo bo'lmasa, botdan foydalanishni cheklaydi.
    """
    async def __call__(self, handler, event: TelegramObject, data: dict):
        bot: Bot = data.get("bot")
        user = data.get("event_from_user")
        if not user or not bot:
            return await handler(event, data)

        # "check_subscription" tugmasi bosilganda to'g'ridan-to'g'ri tekshirish handleriga o'tkaziladi
        if isinstance(event, CallbackQuery) and event.data == "check_subscription":
            return await handler(event, data)

        is_sub, unsubscribed = await check_user_subscription(bot, user.id)
        if not is_sub:
            text = (
                "⚠️ <b>Botdan foydalanish uchun quyidagi kanalimizga a'zo bo'lishingiz shart!</b>\n\n"
                "Kanalga obuna bo'ling va pastdagi <b>«🔄 Tekshirish ✅»</b> tugmasini bosing:"
            )
            markup = get_subscription_markup(unsubscribed)

            if isinstance(event, Message):
                await event.answer(text, reply_markup=markup)
            elif isinstance(event, CallbackQuery):
                await event.message.answer(text, reply_markup=markup)
                await event.answer()
            return  # Jarayonni to'xtatish (handler chaqirilmaydi)

        return await handler(event, data)


# Dispatcher yaratish va middleware ulash
dp = Dispatcher()
dp.message.middleware(SubscriptionMiddleware())
dp.callback_query.middleware(SubscriptionMiddleware())


# Foydalanuvchilarning joriy rejimi: user_id -> "ai" | "instagram"
USER_MODES: dict[int, str] = {}


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Asosiy pastki menyu tugmalari"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🤖 AI Suhbatdosh"),
                KeyboardButton(text="📥 Instagram Yuklovchi"),
            ],
            [
                KeyboardButton(text="ℹ️ Qo'llanma"),
                KeyboardButton(text="🗑️ AI Xotirani tozalash"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


@dp.message(CommandStart())
async def handle_start(message: Message):
    """
    /start buyrug'i uchun handler.
    Foydalanuvchiga salomlashish va bot haqida ma'lumot beradi.
    """
    user_name = html.escape(message.from_user.first_name if message.from_user else "Foydalanuvchi")
    
    welcome_text = (
        f"👋 <b>Assalomu alaykum, {user_name}!</b>\n\n"
        "Men <b>Universal Instagram & AI Yordamchi Bot</b>man! 🚀\n\n"
        "📌 <b>Botingiz imkoniyatlari:</b>\n"
        "1️⃣ 📥 <b>Instagram Yuklovchi</b> — Instagram Reels, Post va IGTV videolarini yuqori sifatda yuklab beradi.\n"
        "2️⃣ 🤖 <b>AI Suhbatdosh</b> — Sun'iy intellekt orqali istalgan savolingizga (dasturlash, fan, tillar, tarjima, maslahatlar) o'zbek tilida javob beradi.\n\n"
        "👇 <i>Kerakli bo'limni tanlang yoki to'g'ridan-to'g'ri havolani/savolingizni yuboring:</i>"
    )

    await message.answer(welcome_text, reply_markup=get_main_keyboard())


@dp.message(Command("ai"))
@dp.message(F.text == "🤖 AI Suhbatdosh")
async def handle_ai_mode(message: Message):
    """AI Suhbatdosh bo'limini faollashtirish"""
    USER_MODES[message.from_user.id] = "ai"
    text = (
        "🤖 <b>AI Suhbatdosh bo'limiga xush kelibsiz!</b>\n\n"
        "Menga istalgan savolingizni yozib yuborishingiz mumkin:\n"
        "• Dasturlash va IT masalalari 💻\n"
        "• Matn yozish, insho, she'r va tarjimalar ✍️\n"
        "• Fan, ta'lim, chet tillarini o'rganish 📚\n"
        "• Foydali maslahatlar va umumiy suhbat 💬\n\n"
        "<i>Savolingizni yozing, men javob beraman:</i>"
    )
    await message.answer(text, reply_markup=get_main_keyboard())


@dp.message(Command("instagram"))
@dp.message(F.text == "📥 Instagram Yuklovchi")
async def handle_instagram_mode(message: Message):
    """Instagram video yuklovchi bo'limini faollashtirish"""
    USER_MODES[message.from_user.id] = "instagram"
    text = (
        "📥 <b>Instagram Video Yuklovchi bo'limi tanlandi!</b>\n\n"
        "Instagram ilovasidan xohlagan video, Reels yoki post havolasini menga yuboring. "
        "Men uni video fayl sifatida yuklab beraman! 🎬"
    )
    await message.answer(text, reply_markup=get_main_keyboard())


@dp.message(Command("clear"))
@dp.message(F.text == "🗑️ AI Xotirani tozalash")
async def handle_clear_ai_history(message: Message):
    """AI bilan suhbat tarixini tozalash"""
    clear_user_history(message.from_user.id)
    await message.reply(
        "🗑️ <b>AI bilan suhbat xotirasi muvaffaqiyatli tozalandi!</b>\n"
        "Endi yangi mavzuda savol berishingiz mumkin.",
        reply_markup=get_main_keyboard(),
    )


@dp.message(Command("help"))
@dp.message(F.text == "ℹ️ Qo'llanma")
async def handle_help_command(message: Message):
    """/help buyrug'i uchun yordam xabari"""
    await send_help_message(message)


@dp.callback_query(F.data == "help_info")
async def handle_help_callback(callback: CallbackQuery):
    """Inline tugma bosilganda yordam ma'lumotlarini yuborish"""
    await callback.answer()
    if callback.message:
        await send_help_message(callback.message)


@dp.callback_query(F.data == "check_subscription")
async def handle_check_subscription(callback: CallbackQuery, bot: Bot):
    """
    Foydalanuvchi 'Obunani tekshirish' tugmasini bosganda
    a'zolikni qayta tekshiruvchi handler.
    """
    is_sub, unsubscribed = await check_user_subscription(bot, callback.from_user.id)
    if is_sub:
        await callback.answer("✅ Rahmat! Obunangiz tasdiqlandi.", show_alert=False)
        try:
            await callback.message.delete()
        except Exception:
            pass

        user_name = html.escape(callback.from_user.first_name if callback.from_user else "")
        await callback.message.answer(
            f"🎉 <b>Xush kelibsiz, {user_name}!</b>\n\n"
            "Botingiz muvaffaqiyatli faollashtirildi. ✅\n\n"
            "• Instagram video yuklash uchun havola yuboring 📥\n"
            "• Savollaringizga javob olish uchun «🤖 AI Suhbatdosh» bo'limini tanlang!",
            reply_markup=get_main_keyboard(),
        )
    else:
        await callback.answer(
            "❌ Siz hali kanalga obuna bo'lmadingiz!\nIltimos, avval yuqoridagi kanalga a'zo bo'ling.",
            show_alert=True,
        )



async def send_help_message(message: Message):
    """Yordam ma'lumotlarini shakllantirish va yuborish"""
    help_text = (
        "📖 <b>Botdan qanday foydalaniladi?</b>\n\n"
        "📥 <b>1. Instagram Video yuklash:</b>\n"
        "1️⃣ Instagram ilovasini oching.\n"
        "2️⃣ O'zingizga yoqqan video yoki Reels havolasini nusxalang.\n"
        "3️⃣ Havolani shu botga yuboring — bot darhol videoni yuklab beradi!\n\n"
        "🤖 <b>2. AI Suhbatdosh bilan suhbat:</b>\n"
        "• «🤖 AI Suhbatdosh» tugmasini bosing yoki to'g'ridan-to'g'ri xohlagan savolingizni yozing.\n"
        "• Sun'iy intellekt IT, dasturlash, tillar, maslahatlar va barcha savollaringizga o'zbek tilida javob beradi.\n"
        "• Yangi mavzuni boshlash uchun «🗑️ AI Xotirani tozalash» tugmasini bosing.\n\n"
        "⚠️ <b>Muhim eslatmalar:</b>\n"
        "• Shaxsiy (private) Instagram profillaridan video yuklab bo'lmaydi.\n"
        "• Telegram orqali maksimal 50 MB gacha video yuborish mumkin."
    )
    await message.answer(help_text, reply_markup=get_main_keyboard())


@dp.message(F.text)
async def handle_text_message(message: Message, bot: Bot):
    """
    Foydalanuvchi yuborgan har qanday matnli xabarni tekshirish.
    1. Agar unda Instagram havolasi bo'lsa -> Videoni yuklab beradi.
    2. Aks holda -> AI orqali savolga to'liq javob qaytaradi.
    """
    text = message.text.strip()
    instagram_url = extract_instagram_url(text)

    # 1-holat: Agar xabarda Instagram havolasi bo'lsa -> Videoni yuklaymiz
    if instagram_url:
        status_msg = await message.reply("⏳ <b>Video yuklab olinmoqda, iltimos kuting...</b>")
        downloaded_path = None
        try:
            # Chat action (video yuklanmoqda holatini ko'rsatish)
            await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VIDEO)

            # Videoni yuklab olish
            data = await download_instagram_video(instagram_url)
            downloaded_path = data["file_path"]

            # Yuboriladigan xabar sarlavhasi
            bot_info = await bot.get_me()
            bot_username = bot_info.username or "InstagramDownloader"

            caption = (
                f"🎬 <b>{html.escape(data.get('title', 'Instagram Video')[:100])}</b>\n\n"
                f"📥 @{bot_username} orqali yuklab olindi."
            )

            # Telegramga video yuborish
            video_input = FSInputFile(str(downloaded_path))
            try:
                await message.reply_video(
                    video=video_input,
                    caption=caption,
                    duration=data.get("duration"),
                    width=data.get("width"),
                    height=data.get("height"),
                    supports_streaming=True,
                )
            except Exception:
                await message.answer_video(
                    video=video_input,
                    caption=caption,
                    duration=data.get("duration"),
                    width=data.get("width"),
                    height=data.get("height"),
                    supports_streaming=True,
                )

            # Holat xabarini o'chirish
            try:
                await status_msg.delete()
            except Exception:
                pass

        except MediaPrivateOrNotFoundError as e:
            await status_msg.edit_text(
                f"❌ <b>Xatolik yuz berdi:</b>\n{html.escape(str(e))}\n\n"
                "<i>Iltimos, profil ochiq (public) ekanligini yoki havola to'g'riligini tekshiring.</i>"
            )
        except MediaTooLargeError as e:
            await status_msg.edit_text(f"⚠️ <b>Hajm chegarasi:</b>\n{html.escape(str(e))}")
        except InstagramDownloadError as e:
            await status_msg.edit_text(f"❌ <b>Videoni yuklab bo'lmadi:</b>\n{html.escape(str(e))}")
        except Exception as e:
            logger.exception("Kutilmagan xatolik:")
            await status_msg.edit_text(
                "❌ <b>Kechirasiz, kutilmagan texnik xatolik yuz berdi.</b>\n"
                "Birozdan so'ng qayta urinib ko'ring."
            )
        finally:
            if downloaded_path and Path(downloaded_path).exists():
                try:
                    Path(downloaded_path).unlink()
                    logger.info(f"Vaqtinchalik fayl o'chirildi: {downloaded_path}")
                except Exception as err:
                    logger.warning(f"Faylni o'chirishda xatolik: {err}")
        return

    # 2-holat: Instagram havolasi bo'lmagan barcha matnlarga AI orqali javob beramiz
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
    ai_answer = await ask_ai(message.from_user.id, text)

    async def _safe_send(content: str):
        try:
            await message.reply(content, reply_markup=get_main_keyboard(), parse_mode=None)
        except Exception:
            await message.answer(content, reply_markup=get_main_keyboard(), parse_mode=None)

    # Telegram xabari maksimal 4096 belgidan oshmasligi kerak
    if len(ai_answer) <= 4000:
        await _safe_send(ai_answer)
    else:
        chunks = [ai_answer[i:i + 4000] for i in range(0, len(ai_answer), 4000)]
        for chunk in chunks:
            await _safe_send(chunk)



async def main():
    """Botni ishga tushirish funksiyasi"""
    if not BOT_TOKEN or "YOUR_BOT_TOKEN" in BOT_TOKEN or ":" not in BOT_TOKEN:
        print("\n" + "=" * 65)
        print("❌ DIQQAT: BOT_TOKEN hali kiritilmagan yoki noto'g'ri!")
        print("Iltimos, loyiha papkasidagi .env faylini oching va")
        print("@BotFather bergan haqiqiy tokenni kiriting.")
        print("Masalan: BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz")
        print("=" * 65 + "\n")
        return

    try:
        # Bot obyektini HTML parse mode bilan sozlash
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    except Exception as e:
        print(f"\n❌ Bot tokenida xatolik: {e}\nIltimos, .env faylidagi tokenni tekshiring.\n")
        return

    logger.info("Bot muvaffaqiyatli ishga tushmoqda...")
    try:
        # Eski o'qilmagan xabarlarni o'chirib tashlash va pollingni boshlash
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
