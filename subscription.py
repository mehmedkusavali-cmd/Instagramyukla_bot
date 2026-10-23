import logging
from typing import List, Tuple
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import REQUIRED_CHANNEL, CHANNEL_URL

logger = logging.getLogger(__name__)


def get_channel_list() -> List[Tuple[str, str]]:
    """
    Sozlamalardan kanallar ro'yxatini ajratib oladi.
    Format: [(channel_identifier, channel_url), ...]
    """
    if not REQUIRED_CHANNEL or "sizning_kanalingiz" in REQUIRED_CHANNEL:
        return []

    channels = [c.strip() for c in REQUIRED_CHANNEL.split(",") if c.strip()]
    urls = [u.strip() for u in CHANNEL_URL.split(",") if u.strip()]

    result = []
    for i, ch in enumerate(channels):
        if i < len(urls):
            url = urls[i]
        else:
            url = f"https://t.me/{ch.lstrip('@')}" if ch.startswith("@") else "https://t.me/"
        result.append((ch, url))
    return result


async def check_user_subscription(bot: Bot, user_id: int) -> Tuple[bool, List[Tuple[str, str]]]:
    """
    Foydalanuvchi barcha talab qilingan kanallarga a'zo ekanligini tekshiradi.
    
    Qaytaradi:
        (barchasiga_azo_bolganmi, [obuna_bolinmagan_kanallar_royxati])
    """
    channels = get_channel_list()
    # Agar sozlamalarda hali kanal ko'rsatilmagan bo'lsa, to'sqinlik qilmaymiz
    if not channels:
        return True, []

    unsubscribed = []
    for ch, url in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch, user_id=user_id)
            # A'zolik maqomini tekshirish
            if member.status not in (
                ChatMemberStatus.CREATOR,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.RESTRICTED,
            ):
                unsubscribed.append((ch, url))
        except Exception as e:
            logger.warning(
                f"Kanalga obunani tekshirishda xatolik ({ch}): {e}\n"
                f"DIQQAT: Bot kanal a'zolarini tekshira olishi uchun ushbu kanalda administrator (admin) bo'lishi shart!"
            )
            # Agar xatolik bo'lsa, foydalanuvchini a'zo emas deb hisoblaymiz
            unsubscribed.append((ch, url))

    is_subscribed = len(unsubscribed) == 0
    return is_subscribed, unsubscribed


def get_subscription_markup(unsubscribed: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    """Obuna bo'lish havolasi va 'Tekshirish' tugmasini yaratadi"""
    keyboard = []
    for idx, (ch, url) in enumerate(unsubscribed, 1):
        btn_text = "📢 Kanalga a'zo bo'lish" if len(unsubscribed) == 1 else f"📢 {idx}-kanalga a'zo bo'lish"
        keyboard.append([InlineKeyboardButton(text=btn_text, url=url)])

    keyboard.append([
        InlineKeyboardButton(text="🔄 Tekshirish ✅", callback_data="check_subscription")
    ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
