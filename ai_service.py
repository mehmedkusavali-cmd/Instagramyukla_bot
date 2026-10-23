import os
import logging
from typing import Dict, List
import aiohttp

logger = logging.getLogger(__name__)

# Foydalanuvchilar suhbat konteksti (xotirasi)
# user_id -> [{'role': 'user'|'assistant', 'content': '...'}]
USER_CONVERSATIONS: Dict[int, List[Dict[str, str]]] = {}
MAX_HISTORY_LENGTH = 6

SYSTEM_PROMPT = (
    "Siz aqlli, bilimdon, xushmuomala va foydali sun'iy intellekt yordamchisisiz. "
    "Foydalanuvchilarning barcha savollariga (fan, texnologiya, dasturlash, til, "
    "hayotiy maslahatlar, ta'lim va boshqa sohalar) o'zbek tilida aniq, tushunarli, "
    "ravon va batafsil javob bering. Javoblarda qulay o'qilishi uchun emojilar, "
    "ro'yxatlar va chiroyli formatlashdan foydalaning."
)


def clear_user_history(user_id: int):
    """Foydalanuvchining AI bilan suhbat tarixini tozalash"""
    if user_id in USER_CONVERSATIONS:
        del USER_CONVERSATIONS[user_id]


async def _ask_pollinations(messages: List[Dict[str, str]]) -> str:
    """Bepul va tezkor AI API orqali javob olish"""
    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *messages
        ],
        "model": "openai",
        "seed": 42,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://text.pollinations.ai/",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status == 200:
                text = await resp.text()
                return text.strip()
            else:
                logger.error(f"Pollinations API status code: {resp.status}")
                return "Kechirasiz, sun'iy intellekt serverida vaqtinchalik uzilish yuz berdi. Birozdan so'ng qayta urinib ko'ring."


async def _ask_gemini(api_key: str, messages: List[Dict[str, str]]) -> str:
    """Google Gemini rasmiy API orqali javob olish"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    
    contents = []
    # System promptni birinchi xabar sifatida qo'shamiz
    contents.append({
        "role": "user",
        "parts": [{"text": f"SYSTEM INSTRUCTION: {SYSTEM_PROMPT}"}]
    })
    contents.append({
        "role": "model",
        "parts": [{"text": "Tushundim. Foydalanuvchiga o'zbek tilida yordam berishga tayyorman!"}]
    })

    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": m["content"]}]
        })

    payload = {"contents": contents}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0]["content"]["parts"][0]["text"]
                        return text.strip()
                else:
                    err_text = await resp.text()
                    logger.warning(f"Gemini API javobi ({resp.status}): {err_text[:200]}")
    except Exception as e:
        logger.warning(f"Gemini so'rovida uzilish yoki vaqt tugashi: {e}")
    
    # Agar Gemini xatolik bersa yoki ulanish sekin bo'lsa, tezkor bepul API ga fallback qilamiz
    return await _ask_pollinations(messages)


async def ask_ai(user_id: int, user_message: str) -> str:
    """
    Foydalanuvchi savoliga AI orqali javob qaytaradi va suhbat tarixini saqlaydi.
    """
    if user_id not in USER_CONVERSATIONS:
        USER_CONVERSATIONS[user_id] = []

    history = USER_CONVERSATIONS[user_id]
    history.append({"role": "user", "content": user_message})

    # Kontekst hajmini cheklash
    if len(history) > MAX_HISTORY_LENGTH:
        history = history[-MAX_HISTORY_LENGTH:]
        USER_CONVERSATIONS[user_id] = history

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    try:
        if gemini_key:
            reply = await _ask_gemini(gemini_key, history)
        else:
            reply = await _ask_pollinations(history)

        # AI javobini tarixga qo'shish
        history.append({"role": "assistant", "content": reply})
        return reply

    except Exception as e:
        logger.exception(f"AI javobini olishda xatolik: {e}")
        return "⚠️ Kechirasiz, savolingizga javob olishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
