"""1-bosqich: rubrikadan mavzu tanlash (va dastur tugasa, yangi mavzular izlash)."""
from __future__ import annotations

from . import llm
from .config import curriculum, log


def flat_topics(state: dict) -> list[dict]:
    items = []
    for mod in curriculum().get("modules", []):
        for t in mod["topics"]:
            items.append({**t, "module_uz": mod["name_uz"], "module_en": mod["name_en"]})
    items.extend(state.get("extra_topics", []))
    return items


def next_topic(ch: dict, state: dict) -> tuple[int, dict]:
    topics = flat_topics(state)
    idx = state.get("next_topic", 0)
    if idx >= len(topics):
        if not curriculum().get("auto_extend", True):
            raise SystemExit("O'quv dasturidagi mavzular tugadi. curriculum.yaml'ga yangi mavzu qo'shing.")
        state.setdefault("extra_topics", []).extend(_research_new_topics(ch, topics))
        topics = flat_topics(state)
    return idx, topics[idx]


def _research_new_topics(ch: dict, done: list[dict]) -> list[dict]:
    log("Dastur tugadi — agent yangi ilg'or mavzular izlayapti...")
    titles = "\n".join(f"- {t['en']}" for t in done[-80:])
    prompt = f"""Rubric: "{ch['rubric']}" (an Islamic finance course from zero to professional level).
These lessons are already published:
{titles}

Propose 10 NEW advanced, practical, non-repeating lessons that continue this course logically.
Use current developments where useful. Return JSON:
{{"topics":[{{"uz":"title in Uzbek (Latin)","en":"title in English","focus":"what to cover, 1-2 sentences"}}]}}"""
    data = llm.generate_json(prompt)
    new = data.get("topics", [])[:10]
    for t in new:
        t["module_uz"], t["module_en"] = "Qo'shimcha ilg'or darslar", "Advanced extra lessons"
    return new
