import os
from pathlib import Path
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# Asosiy sozlamalar
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Fayllar saqlanadigan vaqtinchalik papka
BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Instagram cookies fayli (agar mavjud bo'lsa)
COOKIES_FILE = BASE_DIR / "cookies.txt"

# Telegram bot orqali yuborish mumkin bo'lgan maksimal hajm (50 MB)
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

# Majburiy obuna kanallari sozlamalari
# Masalan: @kanal_nomi yoki kanal ID (-100...)
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL", "").strip()
# Kanal havolasi (masalan: https://t.me/kanal_nomi)
CHANNEL_URL = os.getenv("CHANNEL_URL", "").strip()
