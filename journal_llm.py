"""
journal_llm.py
LLM helper functions for PS 47 - Daily Journal Summarizer.
All prompts and Groq API calls live here, so app.py only handles the UI.
"""

import json
import re

from groq import Groq

# Groq shut down llama-3.3-70b-versatile / llama-3.1-8b-instant for free accounts
# in Aug 2026 and recommends the gpt-oss models instead.
DEFAULT_MODEL = "openai/gpt-oss-120b"
AVAILABLE_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b"]

# Fixed list of moods so the chart and the summary stay consistent.
MOOD_LABELS = [
    "Happy", "Excited", "Motivated", "Calm", "Neutral",
    "Tired", "Anxious", "Stressed", "Sad", "Angry",
]

# ---------------------------------------------------------------- prompts --

TAG_SYSTEM_PROMPT = f"""You are a careful, kind journaling assistant.
You read ONE daily journal entry and tag the writer's overall mood.

Rules:
- Choose exactly one mood from this list: {", ".join(MOOD_LABELS)}.
- Give a mood_score from 1 to 10 (1 = very negative day, 5 = neutral, 10 = very positive day).
- Base the mood only on what is written. Do not invent events.
- "highlight" = the single most important thing that happened, in under 15 words.
- "reason" = one short sentence explaining why you chose this mood.

Reply with ONLY a JSON object in exactly this format:
{{"mood": "<one label>", "mood_score": <integer 1-10>, "highlight": "<text>", "reason": "<text>"}}"""

SUMMARY_SYSTEM_PROMPT = """You are a supportive journaling coach.
You receive one week of journal entries. Each entry already has a date, a mood and a mood score (1-10).
Write a short weekly review for the writer, addressed to them as "you".

Rules:
- Use only the information in the entries. Do not make up events.
- mood_trend: describe how the mood changed across the week (e.g. "started stressed, improved after Wednesday").
- highlights: 3 best moments of the week.
- challenges: up to 3 difficult moments (empty list if none).
- patterns: 1-2 things that seem to affect the mood (e.g. sleep, exams, friends).
- suggestion: one gentle, practical suggestion for next week. Do not give medical advice.

Reply with ONLY a JSON object in exactly this format:
{
  "overall_mood": "<one word>",
  "summary": "<3-4 sentence summary of the week>",
  "mood_trend": "<one sentence>",
  "highlights": ["...", "...", "..."],
  "challenges": ["..."],
  "patterns": ["..."],
  "suggestion": "<one sentence>"
}"""


# ---------------------------------------------------------------- helpers --

def get_client(api_key: str) -> Groq:
    return Groq(api_key=api_key)


def extract_json(text: str) -> dict:
    """Parse JSON from the model output, even if it added extra text or ``` fences."""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Model did not return valid JSON:\n{text[:300]}")


def call_llm(client, model: str, system_prompt: str, user_prompt: str) -> dict:
    """Send the prompt to Groq and return the parsed JSON answer."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        # JSON mode makes the model return valid JSON
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
    except Exception as err:
        # Some models don't support JSON mode -> retry without it
        if "response_format" in str(err) or "json" in str(err).lower():
            response = client.chat.completions.create(
                model=model, messages=messages, temperature=0.3
            )
        else:
            raise
    return extract_json(response.choices[0].message.content)


# ---------------------------------------------------------- main features --

def tag_entry(client, model: str, date: str, entry: str) -> dict:
    """Ask the LLM for mood, score, highlight and reason for one entry."""
    user_prompt = f"Date: {date}\nJournal entry:\n\"\"\"{entry}\"\"\""
    result = call_llm(client, model, TAG_SYSTEM_PROMPT, user_prompt)

    # Validate / clean the answer so bad outputs don't break the chart
    mood = str(result.get("mood", "Neutral")).strip().title()
    if mood not in MOOD_LABELS:
        mood = "Neutral"
    try:
        score = int(round(float(result.get("mood_score", 5))))
    except (TypeError, ValueError):
        score = 5
    score = max(1, min(10, score))

    return {
        "mood": mood,
        "mood_score": score,
        "highlight": str(result.get("highlight", "")).strip(),
        "reason": str(result.get("reason", "")).strip(),
    }


def summarize_week(client, model: str, week_df) -> dict:
    """Ask the LLM for a weekly review of already-tagged entries."""
    lines = []
    for _, row in week_df.sort_values("date").iterrows():
        lines.append(
            f"- {row['date'].strftime('%A %d %b %Y')} | mood: {row['mood']} "
            f"({int(row['mood_score'])}/10) | entry: {row['entry']}"
        )
    user_prompt = "Here are this week's journal entries:\n" + "\n".join(lines)
    result = call_llm(client, model, SUMMARY_SYSTEM_PROMPT, user_prompt)

    # Make sure list fields are always lists
    for key in ("highlights", "challenges", "patterns"):
        value = result.get(key, [])
        result[key] = value if isinstance(value, list) else [str(value)]
    return result
