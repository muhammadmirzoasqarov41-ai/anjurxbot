# AnjurX | Rss Bot

Tezkor, ishonchli va resurslarni tejamkor ishlatuvchi Telegram RSS/Atom/JSON Feed o'quvchi boti va Web boshqaruv paneli.

Ushbu bot siz yoqtirgan veb-saytlar, bloglar va yangiliklar lentasidan yangi maqolalarni Telegram chatlari, guruhlari va kanallariga avtomatik ravishda chiroyli HTML formatida yetkazib beradi.

## Imkoniyatlari (Features)

- **Universal Feed Parsing:** RSS 2.0, Atom 1.0, JSON Feed v1 formatlarini to'liq qo'llab-quvvatlaydi.
- **Autodiscovery:** Sayt havolasini yuborsangiz, uning ichidagi RSS feed avtomatik aniqlanadi.
- **Guruhlar va Kanallar:** Shaxsiy chatlardan tashqari, botni guruhlar va kanallarga administrator qilib qo'shib yangiliklarni avtomatik e'lon qilish mumkin.
- **OPML Import & Export:** Mavjud obunalarni `.opml` fayl ko'rinishida yuklab olish va boshqa ilovalardan yuklangan faylni bir zumda botga ommaviy import qilish.
- **Smart Deduplication & Caching:** SHA-256 maqola xeshlari orqali eski postlar qayta yuborilmaydi; ETag va Last-Modified orqali server trafigi tejaladi.
- **Gibrid Saqlash Tizimi:** Firebase Firestore orqali bulutli xavfsiz saqlash va mahalliy JSON (`data/rssbot.json`) orqali uzluksiz ishlash.
- **Web Dashboard:** Zamonaviy React & Tailwind asosidagi lentalar monitoringi va boshqaruv paneli.

## Telegram Buyruqlari

- `/start` — Botni ishga tushirish va asosiy menyu
- `/sub <url>` — Yangi RSS feedga obuna bo'lish (masalan: `/sub https://kun.uz/news/rss`)
- `/unsub` — Obunani bekor qilish menyusi (yoki `/unsub <url>`)
- `/rss` — Faol obunalar ro'yxatini ko'rish
- `/rss raw` — Obunalar havolalarini xom matn ko'rinishida olish
- `/export` — Barcha obunalarni OPML fayl sifatida yuklab olish
- `/allunsub` — Barcha obunalarni o'chirish
- `.opml` fayl yuborish — Ommaviy feedlarni import qilish

## O'rnatish va Ishga Tushirish

```bash
git clone https://github.com/muhammadmirzoasqarov41-ai/anjurxbot.git
cd anjurxbot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` faylida quyidagi asosiy o'zgaruvchilarni ko'rsating:

```env
BOT_TOKEN=your_telegram_bot_token
BOT_USERNAME=AnjurXBot
ADMIN_IDS=8157452043
SUPER_ADMIN_ID=8157452043
MIN_INTERVAL=300
MAX_INTERVAL=43200
```

### Ishga tushirish:
```bash
python main.py
```
Yoki Web panel bilan ishlash uchun:
```bash
npm run dev
```
