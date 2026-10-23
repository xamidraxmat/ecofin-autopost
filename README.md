# EcoFin-i avtopost agenti 🤖

Telegram kanal uchun to'liq avtomatik, **bepul** ishlaydigan agent:

1. **Mavzu** — "Islomiy moliyani noldan professional darajagacha" o'quv dasturidan ketma-ket oladi (70 ta dars, tugasa o'zi yangi mavzu izlaydi)
2. **Matn** — Gemini Google qidiruv bilan faktlarni tekshiradi va sizning uslubingizda post yozadi
3. **Rasm** — logoli brend karta (1080×1350)
4. **Audio + video** — o'zbekcha neyron ovoz (Edge TTS) va vertikal video-dars (FFmpeg)
5. **Sifat nazorati** — shariat, faktlar, til va uzunlik tekshiruvi; past ball bo'lsa qayta yozadi
6. **Post** — belgilangan vaqtda admin bot orqali kanalga chiqaradi

Hammasi GitHub Actions'da ishlaydi: server, karta yoki oylik to'lov kerak emas.

---

## O'rnatish (taxminan 15 daqiqa)

### 1-qadam. Telegram bot
1. **@BotFather** → `/newbot` → nom va username bering → **tokenni** saqlab qo'ying.
2. Botni kanalingizga **admin** qiling, "Xabar yuborish" huquqi bilan.
3. O'z akkauntingizdan botingizni oching va **`/start`** bosing (aks holda bot sizga yozolmaydi).
4. **@userinfobot** ga `/start` yozing — u sizning **ID raqamingizni** beradi.

### 2-qadam. Gemini API kaliti
[aistudio.google.com](https://aistudio.google.com) → **Get API key** → **Create API key**. Bepul, karta so'ramaydi.

### 3-qadam. GitHub repozitoriy
1. [github.com](https://github.com) da ro'yxatdan o'ting → **New repository** → nom: `ecofin-autopost` → **Private** → **Create**.
2. **uploading an existing file** havolasini bosing va arxivdan chiqarilgan **barcha fayl va papkalarni** sudrab tashlang (`.github` papkasi ham bo'lishi shart) → **Commit changes**.

### 4-qadam. Maxfiy kalitlar
Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**. Uchtasini qo'shing:

| Nomi | Qiymati |
|---|---|
| `TELEGRAM_BOT_TOKEN` | BotFather bergan token |
| `GEMINI_API_KEY` | AI Studio kaliti |
| `ADMIN_CHAT_ID` | @userinfobot bergan raqam |

### 5-qadam. Kanal nomini yozish
Repo'da `config/uz.yaml` → ✏️ (Edit) → `channel: "@ecofin_uz"` qatoriga **o'z kanalingiz username'ini** yozing → **Commit changes**.

### 6-qadam. Logo (ixtiyoriy)
`assets` papkasiga logongizni **`logo_uz.png`** nomi bilan yuklang (shaffof fonli, kvadrat yoki gorizontal). Logo bo'lmasa, chiroyli matnli logo chiziladi.

### 7-qadam. Sinov
Repo → **Actions** → **EcoFin-i agent** → **Run workflow** → `command: generate` → **Run**.
3–5 daqiqadan keyin bot sizga rasm, matn, audio, video va **✅ / 🔄 / ❌** tugmalarini yuboradi.
✅ bosing va yana **Run workflow** → `command: publish` qilsangiz, post darhol kanalga chiqadi.

Shundan keyin agent o'zi har kuni ishlaydi.

---

## Kundalik ish tartibi

| Vaqt (Toshkent) | Nima bo'ladi |
|---|---|
| ~06:05 | Agent post tayyorlaydi va sizga ko'rib chiqish uchun yuboradi |
| siz | ✅ Chiqarish / 🔄 Qayta yozish / ❌ Bekor |
| ~09:05 | Tasdiqlangan post kanalga chiqadi (rasm+matn, audio, video) |
| 15:00 gacha | Javob bermasangiz, post chiqmaydi (yoki `if_no_answer: publish`) |

GitHub jadvali odatda 5–20 daqiqa kechikadi — bu normal.

## Botga buyruqlar (Telegram'da)

| Buyruq | Nima qiladi |
|---|---|
| `/post <ma'lumot>` | E'lon yoki reklama: bot matn va logoli banner tayyorlab, ✅/🔄/❌ bilan ko'rsatadi |
| rasm + izohida `/post <ma'lumot>` | O'z rasmingiz bilan maxsus post |
| fayl (📎 → File) + izohida `/logo` | Kanal logosini o'rnatadi (shaffof fon saqlanadi) |
| rasm + izohida `/muallif` va ma'lumotlar | Kurs e'lonlaridagi muallif bloki (rasm, ism, unvon, sertifikatlar) |
| `/yordam` | Qo'llanma |

Bot har soatda (~:05) tekshiradi. Tezlatish uchun: Actions → Run workflow → `tick`.
Maxsus postlar dars tartibiga ta'sir qilmaydi va ✅ bosilgach darhol chiqadi.

## Sozlamalar (`config/uz.yaml`)

| Sozlama | Nima qiladi |
|---|---|
| `post_time` | Post vaqti, masalan `"09:00"` |
| `days` | Qaysi kunlari: `[mon, wed, fri]` |
| `require_approval` | `false` — tasdiqsiz, to'liq avtomat |
| `media` | rasm / audio / video ni yoqish-o'chirish |
| `voice` | `uz-UZ-SardorNeural` (erkak) yoki `uz-UZ-MadinaNeural` (ayol) |
| `colors` | Brend ranglari |
| `style` | Yozish uslubi bo'yicha ko'rsatma — namunalaringiz asosida yangilash mumkin |

Mavzular: `config/curriculum.yaml`. Qo'shish, o'chirish yoki tartibini o'zgartirish mumkin.
Agent qaysi darsda turgani: `state/uz.json` (`next_topic` — keyingi dars tartib raqami, 0 dan boshlanadi).

## Muammolar

| Belgi | Yechim |
|---|---|
| Bot sizga hech narsa yubormadi | Botga `/start` bosganmisiz? `ADMIN_CHAT_ID` to'g'rimi? Actions'dagi log'ni oching |
| `chat not found` | Bot kanalga admin emas yoki `channel` noto'g'ri |
| Gemini `429` | Bepul limit vaqtincha tugagan — agent kutib qayta urinadi |
| Actions ishlamayapti | Settings → Actions → General → **Allow all actions** va **Read and write permissions** |

## Keyinroq qo'shish mumkin
- **EN kanal** — `config/en.yaml` fayli (uz.yaml nusxasi, `language: en`, inglizcha ovoz)
- Nano Banana rasmlari yoki ElevenLabs ovozi (pullik) — tegishli modulni almashtirish bilan
