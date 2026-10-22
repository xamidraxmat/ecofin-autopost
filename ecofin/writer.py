"""2-bosqich: mavzu bo'yicha tadqiqot va post matnini yozish."""
from __future__ import annotations

from . import llm
from .config import log

LANG_NAME = {"uz": "Uzbek (Latin script, use the letters oʻ and gʻ correctly)", "en": "English"}


def research(topic: dict, ch: dict) -> str:
    """Mavzu bo'yicha ishonchli faktlar va maslahatlar to'plash (Google qidiruv bilan)."""
    prompt = f"""You are a senior Islamic finance scholar-practitioner preparing a lesson.
Course: "{ch['rubric']}". Lesson: "{topic['en']}". Focus: {topic.get('focus', '')}

Collect accurate teaching notes in English:
1. Precise definitions (with Arabic terms and transliteration).
2. The ruling/principle according to AAOIFI Shariah Standards and the majority (jumhur) view;
   note any well-known scholarly disagreement fairly.
3. Quran/Hadith references ONLY if you are certain (surah:ayah). Otherwise omit.
4. One realistic numeric example suited to Uzbekistan (in so'm or USD).
5. 3 practical tips for a beginner and 2 common misconceptions.
6. If the focus says USE SEARCH, verify current facts and give the year/source.
Be concise (max 350 words). Do not invent facts, numbers or quotes."""
    try:
        return llm.generate(prompt, search=True, temperature=0.3)
    except llm.LLMError as e:
        log(f"Tadqiqot bosqichida xato, faqat model bilimi bilan davom etiladi: {e}")
        return "(no research notes)"


def write_post(topic: dict, ch: dict, lesson_no: int, notes: str, feedback: str = "") -> dict:
    lang = ch["language"]
    title_key = "uz" if lang == "uz" else "en"
    fix = f"\n\nREVISION REQUIRED. Fix these problems from quality review:\n{feedback}\n" if feedback else ""
    prompt = f"""Write lesson #{lesson_no} for the Telegram channel "{ch['channel_name']}".
Lesson topic: "{topic[title_key]}"  (English: "{topic['en']}")
Module: {topic.get('module_' + title_key, '')}
Language of ALL output fields: {LANG_NAME.get(lang, lang)}.

Research notes (use them, keep facts accurate):
\"\"\"{notes}\"\"\"
{fix}
Return ONLY JSON with these fields:
{{
  "title": "lesson title for the image, max 55 characters",
  "subtitle": "one-line promise of the lesson, max 80 characters",
  "key_points": ["3 short points for the image, each max 45 characters"],
  "caption": "the Telegram post text. Max {ch.get('post_max_chars', 1000) - 90} characters. Do NOT put hashtags in it (they are added automatically). Plain text with line breaks. You may use <b>bold</b> for 2-4 key phrases; no other tags, no markdown.",
  "hashtags": ["3-5 hashtags, first one must be {ch.get('hashtag_rubric', '')}"],
  "slides": [
    {{"heading": "max 40 chars", "text": "max 160 chars shown on screen", "narration": "what the narrator says for this slide, 2-4 natural spoken sentences"}}
  ],
  "summary_en": "2-sentence English summary for the reviewer"
}}
Rules for slides: 5 or 6 slides: (1) hook, (2-4/5) explanation + example, (last) takeaway and invitation to follow the channel.
Narration is for text-to-speech: spell out numbers as words, no emojis, no hashtags, no symbols like % or $ (write them as words)."""
    return llm.generate_json(prompt, system=ch["style"])
