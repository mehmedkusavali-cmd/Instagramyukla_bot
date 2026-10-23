import asyncio
import os
import re
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, Any

import yt_dlp

from config import DOWNLOADS_DIR, COOKIES_FILE, MAX_FILE_SIZE_BYTES

logger = logging.getLogger(__name__)

# Instagram havolasini aniqlash uchun regex
INSTAGRAM_URL_REGEX = re.compile(
    r"https?://(?:www\.)?(?:instagram\.com|instagr\.am)/(?:reel|reels|p|tv|share/[a-zA-Z0-9_\-]+)/([a-zA-Z0-9_\-]+)",
    re.IGNORECASE,
)

# Har qanday Instagram URL'ni matndan ajratib olish uchun
ANY_INSTAGRAM_REGEX = re.compile(
    r"https?://(?:www\.)?(?:instagram\.com|instagr\.am)/[^\s]+",
    re.IGNORECASE,
)


class InstagramDownloadError(Exception):
    """Instagram yuklab olish bilan bog'liq asosiy xatolik"""
    pass


class MediaTooLargeError(InstagramDownloadError):
    """Media hajmi 50MB dan oshib ketganda chiqadigan xatolik"""
    pass


class MediaPrivateOrNotFoundError(InstagramDownloadError):
    """Media o'chirilgan yoki profil yopiq bo'lganda"""
    pass


def extract_instagram_url(text: str) -> Optional[str]:
    """Matn ichidan Instagram havolasini ajratib oladi"""
    match = ANY_INSTAGRAM_REGEX.search(text)
    if match:
        url = match.group(0)
        # URL oxiridagi keraksiz belgilarni tozalash (masalan, qavslar yoki nuqta)
        url = url.rstrip(").,;:?!")
        return url
    return None


def _sync_download(url: str) -> Dict[str, Any]:
    """Sinxron tarzda yt-dlp orqali videoni yuklab olish"""
    file_prefix = f"ig_{uuid.uuid4().hex[:8]}"
    outtmpl = str(DOWNLOADS_DIR / f"{file_prefix}_%(id)s.%(ext)s")

    ydl_opts: Dict[str, Any] = {
        # Eng yaxshi MP4 video formatini tanlash
        "format": "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
        "outtmpl": outtmpl,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }

    # Agar cookies.txt mavjud bo'lsa, foydalanamiz
    if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 0:
        ydl_opts["cookiefile"] = str(COOKIES_FILE)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Avval ma'lumotni olish
            info = ydl.extract_info(url, download=True)

            if not info:
                raise MediaPrivateOrNotFoundError("Video ma'lumotlarini olib bo'lmadi.")

            # Agar bir nechta yozuvlar bo'lsa (carousel), birinchisini olamiz
            if "entries" in info and info["entries"]:
                info = info["entries"][0]

            # Yuklangan fayl yo'lini aniqlash
            # ydl.prepare_filename info ga asoslanadi
            downloaded_file = Path(ydl.prepare_filename(info))

            # Ba'zan kengaytma o'zgarishi mumkin (.mkv -> .mp4)
            if not downloaded_file.exists():
                # Papkada prefiks bo'yicha qidirish
                candidates = list(DOWNLOADS_DIR.glob(f"{file_prefix}_*"))
                if candidates:
                    downloaded_file = candidates[0]
                else:
                    raise InstagramDownloadError("Yuklangan fayl saqlash joyida topilmadi.")

            # Fayl hajmini tekshirish
            file_size = downloaded_file.stat().st_size
            if file_size > MAX_FILE_SIZE_BYTES:
                # Faylni o'chirib yuboramiz
                try:
                    downloaded_file.unlink()
                except Exception:
                    pass
                raise MediaTooLargeError(
                    f"Video hajmi juda katta ({file_size / (1024 * 1024):.1f} MB). "
                    "Telegram bot orqali faqat 50 MB gacha fayl yuborish mumkin."
                )

            return {
                "file_path": downloaded_file,
                "title": info.get("title") or info.get("description") or "Instagram Video",
                "duration": info.get("duration"),
                "width": info.get("width"),
                "height": info.get("height"),
                "uploader": info.get("uploader") or info.get("channel") or "",
            }

    except yt_dlp.utils.DownloadError as e:
        err_msg = str(e).lower()
        logger.error(f"yt-dlp xatoligi: {e}")
        if "private" in err_msg or "login" in err_msg or "checkpoint" in err_msg:
            raise MediaPrivateOrNotFoundError(
                "Bu profil yopiq (private) yoki Instagram tizimga kirishni talab qilmoqda."
            )
        elif "not found" in err_msg or "404" in err_msg:
            raise MediaPrivateOrNotFoundError(
                "Ushbu havola bo'yicha video topilmadi yoki u o'chirib yuborilgan."
            )
        else:
            raise InstagramDownloadError(f"Videoni yuklab olishda xatolik: {e}")
    except Exception as e:
        if isinstance(e, InstagramDownloadError):
            raise
        logger.exception("Kutilmagan xatolik yuz berdi:")
        raise InstagramDownloadError(f"Yuklab olishda xatolik yuz berdi: {str(e)}")


async def download_instagram_video(url: str) -> Dict[str, Any]:
    """
    Asinxron wrapper: Telegram botining event loop'i qotib qolmasligi uchun
    yuklab olish jarayonini alohida thread'da bajaradi.
    """
    return await asyncio.to_thread(_sync_download, url)
