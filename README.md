# 🎬 Instagram Video Yuklovchi & 🤖 AI Suhbatdosh Telegram Bot

Ushbu bot **Python**, **aiogram 3.x**, **yt-dlp** va **Sun'iy Intellekt (AI)** kutubxonalari asosida yaratilgan universal Telegram bot hisoblanadi.

---

## 🚀 Asosiy Imkoniyatlar

1. 📥 **Instagram Video Yuklash**:
   - Instagram Reels, Post va IGTV videolarini yuqori MP4 sifatda tezkor yuklash.
   - Avtomatik tozalash (`unlink`): server xotirasini tejash maqsadida video yuborilgach fayl o'chiriladi.
   - 50 MB gacha hajmni tekshirish va yopiq profillarni aniqlash.

2. 🤖 **AI Suhbatdosh Bo'limi**:
   - Istalgan savollarga (dasturlash, fan, tillar, tarjima, maslahatlar, suhbat) o'zbek tilida to'liq va ravon javob berish.
   - Suhbat kontekstini (tarixini) eslab qolish qobiliyati.
   - Yangi mavzuni boshlash uchun `🗑️ AI Xotirani tozalash` imkoniyati.
   - Hech qanday murakkab sozlamalarsiz, to'g'ridan-to'g'ri bepul ishlaydi (ixtiyoriy tarzda Google Gemini API ham ulanishi mumkin).

3. 🛡️ **Majburiy Kanal Obunasi (Middleware)**:
   - Foydalanuvchilar kanalingizga a'zo bo'lmaguncha botdan foydalanishni cheklash.
   - Inline tekshirish tugmasi (`🔄 Tekshirish ✅`).

---

## 📁 Loyiha Strukturasi

```text
bot create/
├── config.py           # Muhit o'zgaruvchilari va yo'llar
├── downloader.py       # Instagram yuklovchi modul (yt-dlp)
├── subscription.py     # Majburiy obunani tekshiruvchi modul
├── ai_service.py       # Sun'iy intellekt (AI) xizmati va kontekst
├── main.py             # Asosiy bot, menyu va handlerlar
├── requirements.txt    # Kerakli kutubxonalar
├── run_bot.bat         # 1 ta bosish bilan botni ishga tushiruvchi fayl
├── .env                # Token va kanal sozlamalari
└── README.md           # Qo'llanma
```

---

## 🛠 Ishga Tushirish

1. `.env` faylida token va kanalni sozlang:
   ```env
   BOT_TOKEN=8346310240:AAGZlFYVbq7qCMELqIeppfBRDr4kGhskSYM
   REQUIRED_CHANNEL=@mening_kanalim
   CHANNEL_URL=https://t.me/mening_kanalim
   ```

2. Botni ishga tushiring:
   ```bash
   py main.py
   ```
   *(yoki loyiha papkasidagi `run_bot.bat` fayliga bosing)*
