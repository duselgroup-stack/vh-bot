# 🏡 VOHA UYLARI — Telegram-bot va sayt

Qashqadaryo ko‘chmas mulk ekotizimi uchun **Telegram-bot + sayt**: **xaridor**, **uy egasi** va **makler** bitta tizimda.
Bot va sayt **bitta bazadan** ishlaydi va **bitta buyruq** bilan ishga tushadi (`python bot.py`).
Taqdimotdagi biznes-model to‘liq kiritilgan: yagona obyekt ID (VU-0001), 3 ta hamkorlik modeli,
obyekt va xaridor manbasini qayd etish, bitimning 7 bosqichi, komissiya hisobi va KPI statistikasi.

---

## ✨ Bot nima qila oladi

### 🔎 Xaridor / ijarachi
- Uy sotib olish yoki ijaraga olish: **hudud → mulk turi → xonalar → narx** bo‘yicha qidiruv (16 ta shahar/tuman)
- Rasmli kartochkalar, sahifalab ko‘rish, barcha rasm/videoni ko‘rish, do‘stga ulashish
- **«📩 Ko‘rishga yozilish»** — telefon, qulay vaqt, izoh → admin va mas’ul maklerga darhol boradi
- **Obuna**: talabga mos yangi uy chiqsa bot o‘zi xabar beradi
- ID bo‘yicha qidirish (`VU-0012` deb yozish kifoya), «Murojaatlarim»

### 🏡 Uy egasi
- «Uy sotaman» / «Ijaraga beraman» / «Professional reklama» — qadam-baqadam e’lon formasi
- Tariflar: **Faqat reklama 500 000**, **To‘liq sotuv 2%**, **Reklama + savdo 500 000 + 1%**
- «E’lonlarim»: holat, 7 bosqichli progress, ko‘rishlar va murojaatlar soni
- Holatni o‘zi yangilaydi: faol / muzokarada / sotildi / sotuvdan olish, syomka so‘rash

### 🤝 Makler (hamkor)
- Ro‘yxatdan o‘tish arizasi → admin tasdiqlaydi
- Obyekt qo‘shish (2-model: makler 1,2% / Voha 0,8%), syomka so‘rash
- **Obyektlar bazasi** — boshqa faol obyektlar va «mijoz olib kelsangiz ulushingiz ≈ 4 mln» ko‘rsatkichi
- **«🤝 Mijozim bor»** — mijozni obyektga qayd etish. Birinchi qayd etgan biriktiriladi, boshqa makler
  mijoz raqamini ko‘rmaydi (ishonch kafolati)
- Mijozlar va murojaatlar holatini yangilash, shaxsiy statistika, komissiya kalkulyatori

### 🛠 Admin (CRM)
- Moderatsiya: tasdiqlash → **kanalga avtomatik post** + obunachilarga xabar; syomkaga yuborish; rad etish (sabab bilan)
- Obyekt kartasi: 7 bosqich, manba, model, foiz, makler, egasi, reklama to‘lovi, xarajat, **dublikat tekshiruvi**
- Narx/model/foizni o‘zgartirish, makler biriktirish, syomkadan keyin media yuklash
- **Bitimni yopish**: narx → xaridor → manba → makler → komissiya avtomatik taqsimlanadi (yoki qo‘lda)
- Undirilmagan komissiyalar, **KPI statistika** (34-slayd bo‘yicha), **Excel eksport**, xabar tarqatish,
  foydalanuvchi savollariga javob, baza zaxira nusxasi
- Kanalda sotilgan uy avtomatik **🔴 SOTILDI** deb belgilanadi

### 🌐 Sayt (bot bilan birga ishlaydi)
- **Bosh sahifa**: qidiruv paneli, yangi e’lonlar, hududlar, tariflar, hamkorlik taklifi
- **Katalog** (`/uylar`): hudud, mulk turi, xonalar, narx oralig‘i bo‘yicha filtr, saralash, sahifalash
- **Obyekt sahifasi** (`/uy/VU-0012`): rasmlar galereyasi, **video**, ma’lumotlar, o‘xshash e’lonlar
- **«Ko‘rishga yozilish» formasi** — murojaat bazaga `sayt` manbasi bilan yoziladi va darhol adminga/maklerga botda keladi
- **Uy sotish** sahifasi (`/uy-sotish`) — tariflar, 7 bosqich va uy egasi arizasi
- **Hamkorlik** sahifasi (`/hamkorlik`) — 3 model, ulush kalkulyatori, savol-javob
- **Makler kabineti** (`/kabinet`) — o‘z obyektlari, 7 bosqich progressi, mijozlar, bitimlar va ulushlar
- **Admin panel** (`/admin`) — KPI statistika, moderatsiya navbati va dublikatlar, murojaatlar, komissiyalar, saytdan arizalar
- Kirish parolsiz: botda `/sayt` → bir martalik xavfsiz havola (15 daqiqa)
- Rasmlar Telegram’dan avtomatik olinadi — alohida yuklash shart emas. SEO: sitemap, Open Graph
- Telefon va kompyuterga moslashgan

---

## 🧰 Kerakli narsalar

| Nima | Qayerdan |
|---|---|
| Bot tokeni | Telegramda **@BotFather** (bepul) |
| Telegram ID raqamingiz | **@userinfobot** (bepul) |
| Python 3.10+ | python.org (bepul) |
| 24/7 ishlashi uchun server | VPS (oyiga ~5$) yoki Railway |
| Sayt uchun domen (ixtiyoriy) | masalan `vohauylari.uz` (yiliga ~10–15$) |

---

## 🚀 1-qadam. Botni yaratish (@BotFather)

1. Telegramda **@BotFather** ni oching → `/newbot`
2. Bot nomi: `Voha Uylari`
3. Username (oxiri `bot` bilan tugashi kerak): masalan `voha_uylari_bot`
4. BotFather bergan **token**ni nusxalang (`1234567890:AAH...` ko‘rinishida). Uni hech kimga bermang!
5. (Ixtiyoriy) `/setuserpic` — logotip, `/setdescription` — tavsif.

## 🆔 2-qadam. Telegram ID ni bilish

**@userinfobot** ga `/start` yozing — u `Id: 123456789` qaytaradi. Bu sizning **ADMIN_IDS** raqamingiz.
Bir nechta admin bo‘lsa, vergul bilan yozasiz: `123456789,987654321`.

## 📢 3-qadam (ixtiyoriy). Kanal va admin guruhi

**Kanal** (e’lonlar avtomatik joylanadi):
1. Kanal oching (masalan `@voha_uylari`), botni kanalga **administrator** qilib qo‘shing (xabar yuborish va tahrirlash huquqi bilan).
2. `.env` da: `CHANNEL_ID=@voha_uylari`

**Admin guruhi** (yangi e’lon, murojaat, arizalar bitta joyga tushadi):
1. Guruh oching, botni qo‘shing.
2. Guruh ID sini bilish: guruhga **@RawDataBot** ni qo‘shing — u `"id": -100...` raqamini yozadi, keyin uni chiqarib yuboring.
3. `.env` da: `ADMIN_GROUP_ID=-100...`

> Guruhdagi tugmalarni faqat ADMIN_IDS dagi odamlar bosa oladi. Matn kiritish kerak bo‘lsa (narx, sabab), bot sizga **shaxsiy chatda** yozadi — shuning uchun har bir admin botga bir marta `/start` bosgan bo‘lishi kerak.

## 💻 4-qadam. Kompyuterda sinab ko‘rish

1. **Python** o‘rnating: python.org → Downloads. Windows’da o‘rnatishda **«Add Python to PATH»** belgisini qo‘ying.
2. Arxivni oching (masalan `C:\voha_uylari_bot`).
3. Papkada `.env.example` faylidan nusxa olib, nomini **`.env`** qiling va Bloknotda to‘ldiring:
   ```
   BOT_TOKEN=1234567890:AAH...sizning_token
   ADMIN_IDS=123456789
   COMPANY_PHONE=+998 90 123 45 67
   ```
4. Papkada terminal (Windows: manzil satriga `cmd` yozib Enter) oching va:
   ```bash
   pip install -r requirements.txt
   python bot.py
   ```
5. `Bot ishga tushdi: @voha_uylari_bot` yozuvi chiqsa — tayyor! Telegramda botga `/start` bosing, admin panel: `/admin`.
6. **Sayt** ham shu zahoti ishlaydi: brauzerda **http://localhost:8080** ni oching. Admin panelga kirish: botga `/sayt` yozing → havolani bosing.

> Kompyuter o‘chsa bot ham to‘xtaydi. Doimiy ishlashi uchun 5-qadamga o‘ting.

## ☁️ 5-qadam. Serverga joylash (24/7)

### A variant — VPS (Ubuntu 22.04/24.04) — tavsiya etiladi
```bash
# 1) Fayllarni serverga yuklang (masalan /opt/voha_uylari_bot) va kiring
cd /opt/voha_uylari_bot

# 2) Python muhiti
apt update && apt install -y python3 python3-venv
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# 3) Sozlamalar
cp .env.example .env
nano .env        # tokenni va ADMIN_IDS ni yozing, Ctrl+O, Enter, Ctrl+X

# 4) Avtomatik ishga tushish (server qayta yoqilsa ham)
cp voha-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now voha-bot

# Holatni ko‘rish / loglar
systemctl status voha-bot
journalctl -u voha-bot -f
```
Kodni yangilaganda: `systemctl restart voha-bot`

**Saytni domenga ulash (HTTPS bilan):**
1. Domen sotib oling va uning **A-yozuvini** server IP manziliga yo‘naltiring.
2. Serverda:
   ```bash
   apt install -y nginx certbot python3-certbot-nginx
   cp nginx-voha.conf /etc/nginx/sites-available/voha
   nano /etc/nginx/sites-available/voha      # vohauylari.uz o‘rniga o‘z domeningiz
   ln -s /etc/nginx/sites-available/voha /etc/nginx/sites-enabled/
   nginx -t && systemctl reload nginx
   certbot --nginx -d vohauylari.uz -d www.vohauylari.uz   # bepul HTTPS sertifikat
   ```
3. `.env` da: `WEBSITE_URL=https://vohauylari.uz` va `systemctl restart voha-bot`.
   Shundan so‘ng kanal postlarida «🌐 Saytda ko‘rish» tugmasi ham paydo bo‘ladi.

### B variant — Railway.app
1. Kodni GitHub’ga yuklang (`.env` faylini yuklamang — u `.gitignore` da).
2. Railway → New Project → Deploy from GitHub repo.
3. **Variables** bo‘limiga `.env` dagi qiymatlarni kiriting.
4. **Muhim:** bazani saqlash uchun **Volume** qo‘shing (masalan `/data`) va `DB_PATH=/data/voha_uylari.db` yozing. Aks holda har yangilanishda baza o‘chib ketadi.
5. Start command: `python bot.py` (Procfile’da bor).
6. Sayt uchun: Settings → Networking → **Generate Domain** (Railway `PORT` ni o‘zi beradi). Olingan manzilni `WEBSITE_URL` ga yozing.

---

## 📖 Botdan foydalanish

### Instagram/Telegram’dan kelgan mijozlarni hisoblash (manba)
Maxsus havolalar — xaridor qayerdan kelgani avtomatik yoziladi:

| Qayerga qo‘yasiz | Havola |
|---|---|
| Instagram bio / stories | `https://t.me/BOT_USERNAME?start=ig` |
| Telegram kanal | `https://t.me/BOT_USERNAME?start=tg` |
| Sayt | `https://t.me/BOT_USERNAME?start=web` |
| Aniq obyekt (Instagram post ostiga) | `https://t.me/BOT_USERNAME?start=VU-0012_ig` |

Kanal postlaridagi «📩 Ko‘rishga yozilish» tugmasi o‘zi `_tg` manbasi bilan ishlaydi.

### Bitimning 7 bosqichi botda qanday aks etadi
| Bosqich | Botda |
|---|---|
| 1. Obyekt qabul qilinadi | Admin «Tasdiqlash» yoki «Syomkaga» bosadi; manba, makler, model yoziladi |
| 2. Syomka | «🎬 Syomkaga» → media yuklanadi (xarajat avtomatik +350 000) |
| 3. E’lon | «✅ Tasdiqlash va e’lon qilish» → kanal + obunachilar |
| 4. Mijoz manbasi | Har bir murojaatda manba (bot, Instagram, Telegram, sayt, makler) |
| 5. Uy ko‘rish | Murojaat holati: 📅 belgilandi → 👀 ko‘rildi |
| 6. Bitim natijasi | Faol / muzokarada / sotildi / ijaraga berildi |
| 7. Komissiya | «🏁 Bitimni yopish» → ulushlar hisoblanadi → «✅ Undirildi» |

### Hamkorlik modellari (avtomatik hisob)
| Model | Jami | Voha | Makler | 500 mln uyda makler |
|---|---|---|---|---|
| 1 · Voha obyekti | 2% | 1,2% | 0,8% | 4 mln |
| 2 · Makler obyekti | 2% | 0,8% | 1,2% | 6 mln |
| 3 · Reklama 500 ming + 1% | 1% | 0,5% | 0,5% | 2,5 mln |
| Faqat reklama | 500 000 so‘m | — | — | — |

Bitimda makler bo‘lmasa, uning ulushi Vohaga qoladi. Foiz boshqacha kelishilgan bo‘lsa — obyekt kartasida «％ Foiz» yoki bitim yopishda «✏️ Summani qo‘lda kiritish».

### Saytdagi kabinetga kirish
- **Makler**: botda «🌐 Sayt kabineti» tugmasi yoki `/sayt` → kelgan havolani bosadi → kabinet ochiladi (30 kun eslab qoladi).
- **Admin**: `/sayt` yoki Admin panel → «🌐 Sayt paneli». Admin paneldagi «Botda ochish» tugmasi obyekt kartasini to‘g‘ridan-to‘g‘ri botda ochadi.
- Havola 15 daqiqa amal qiladi va faqat bir marta ishlaydi — parol kerak emas.

### Buyruqlar
`/start` — bosh menyu · `/admin` — admin panel · `/sayt` — sayt va kabinet havolasi · `/id` — ID bo‘yicha qidirish · `/role` — rolni almashtirish · `/cancel` — bekor qilish · `/help` — yordam

---

## 💾 Zaxira nusxa (backup)
- Bot har **24 soatda** baza faylini birinchi adminga Telegram orqali yuboradi (`BACKUP_HOURS`, 0 — o‘chirish).
- Istalgan payt: Admin panel → **💾 Zaxira nusxa**.
- Tiklash: botni to‘xtating, faylni `voha_uylari.db` nomi bilan almashtiring, qayta ishga tushiring.

## 📂 Fayllar tuzilishi
```
bot.py              — ishga tushirish
config.py           — .env sozlamalari
constants.py        — hududlar, modellar, tariflar, statuslar (tahrirlash oson)
texts.py            — barcha matnlar va tugmalar
database.py         — SQLite baza
keyboards.py        — tugmalar
handlers/           — bo‘limlar: common, buyer, leads, listing_form, my_listings, broker,
                      admin, admin_deals, admin_tools, calc, web_login, fallback
services/           — kartochkalar, komissiya, xabarnomalar, zaxira nusxa
web/                — sayt: server.py (sahifalar), auth.py (kirish), media.py (rasmlar)
  templates/        — HTML sahifalar (matnlarni shu yerda o‘zgartirasiz)
  static/           — style.css (ranglar, dizayn), app.js
nginx-voha.conf     — domen uchun nginx namunasi
```
Matnni o‘zgartirmoqchi bo‘lsangiz — `texts.py`; yangi tuman qo‘shish — `constants.py` dagi `DISTRICTS` ro‘yxatining **oxiriga**.

## ❓ Muammolar
| Muammo | Yechim |
|---|---|
| `BOT_TOKEN topilmadi` | `.env` fayli nomi aniq `.env` ekanini va token to‘g‘ri yozilganini tekshiring |
| `/admin` ishlamaydi | `ADMIN_IDS` da o‘z ID’ingiz borligini tekshiring, botni qayta ishga tushiring |
| Kanalga post chiqmayapti | Bot kanalda **admin** bo‘lishi shart; `CHANNEL_ID` `@` bilan yoki `-100...` |
| «Avval botga /start bosing» | Admin guruhdagi tugmani bosgan admin bot bilan shaxsiy chatni ochmagan |
| `Conflict: terminated by other getUpdates` | Bot ikki joyda ishga tushgan — bittasini to‘xtating |
| Sayt ochilmayapti | `WEB_ENABLED=1` ekanini, serverda 8080-port (yoki nginx) ochiqligini tekshiring |
| Kabinet havolasi «eskirgan» | Havola 15 daqiqa va bir marta ishlaydi — botda `/sayt` bilan yangisini oling |
| Saytda video ko‘rinmaydi | Telegram bot 20 MB dan katta faylni bera olmaydi — bunday video kanal posti orqali ko‘rsatiladi. Videoni 20 MB gacha siqib yuklang |
| Kabinet havolasi `localhost` bo‘lib kelyapti | `.env` da `WEBSITE_URL` ni domeningiz bilan to‘ldiring |

## 🔭 Keyingi bosqichlar
- Saytda makler ommaviy profillari va obyekt xaritasi
- Click/Payme orqali reklama to‘lovi
- Ko‘p yuklamada PostgreSQL va Redis (`REDIS_URL`)

*VOHA UYLARI — Birga ishlaymiz. Birga o‘samiz.*
