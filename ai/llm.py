"""Thin wrapper around OpenRouter (an OpenAI-compatible chat completions API)
used by every AI feature in the app.

Every public function raises LLMError on failure (missing key, network
error, malformed response) so views can catch one exception type and show a
friendly message instead of a 500.
"""
import json
import logging
import re

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

_client = None


class LLMError(Exception):
    """Raised whenever an AI call can't be completed."""


def is_configured():
    return bool(settings.OPENROUTER_API_KEY)


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/",
                "X-Title": "LMS",
            },
        )
    return _client


def _require_configured():
    if not is_configured():
        raise LLMError(
            "AI features aren't configured yet — add OPENROUTER_API_KEY to .env to turn this on."
        )


def _chat(messages):
    _require_configured()
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=settings.OPENROUTER_MODEL,
            messages=messages,
        )
    except Exception as exc:
        logger.exception("OpenRouter request failed")
        raise LLMError("The AI service couldn't be reached. Please try again.") from exc

    choice = response.choices[0] if response.choices else None
    text = (choice.message.content or "").strip() if choice else ""
    if not text:
        logger.error("OpenRouter returned an empty response: %r", response)
        raise LLMError("The AI returned an empty response. Please try again.")
    return text


def _extract_json(text):
    """Pull a JSON object out of a model response, tolerating ```json fences
    or stray text around the object."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\n?", "", stripped)
        stripped = re.sub(r"```$", "", stripped).strip()
    try:
        return json.loads(stripped)
    except ValueError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(stripped[start : end + 1])
        raise


def _generate_json(prompt, system_instruction=None):
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    text = _chat(messages)
    try:
        return _extract_json(text)
    except (ValueError, TypeError) as exc:
        logger.exception("OpenRouter returned invalid JSON: %r", text)
        raise LLMError("The AI returned an unexpected response. Please try again.") from exc


def review_marksheet(entries, student_name):
    """entries: list of {"subject": str, "score": float, "max_score": float}."""
    lines = "\n".join(f"- {e['subject']}: {e['score']}/{e['max_score']}" for e in entries)
    prompt = f"""You are an academic performance analyst reviewing a student's marksheet.

Student: {student_name}
Scores:
{lines}

Analyze the performance and respond with ONLY a JSON object (no markdown fences, no extra text) of this exact shape:
{{
  "overall_summary": "2-3 sentence overview of how the student performed overall",
  "strengths": ["short phrase", "short phrase"],
  "weaknesses": ["short phrase", "short phrase"],
  "student_suggestions": "A warm, encouraging paragraph of specific, actionable advice for the STUDENT on how to improve, referencing their weakest subjects by name.",
  "teacher_suggestions": "A practical paragraph of advice for the TEACHER on differentiated teaching methods or interventions that would help this specific student, based on the pattern of scores."
}}"""
    return _generate_json(prompt)


def generate_quiz(lesson, num_questions=5):
    content = lesson.content or "(no written content provided — write reasonable questions based on the title alone)"
    prompt = f"""You are an expert instructional designer. Create a multiple-choice quiz that tests understanding of the following lesson.

Lesson title: {lesson.title}
Lesson content:
{content}

Write exactly {num_questions} multiple-choice questions. Respond with ONLY a JSON object (no markdown fences, no extra text) of this exact shape:
{{
  "title": "short quiz title",
  "questions": [
    {{
      "text": "question text",
      "choices": ["choice A", "choice B", "choice C", "choice D"],
      "correct_index": 0,
      "explanation": "one sentence explaining why this is correct"
    }}
  ]
}}
Each question must have exactly 4 choices, and correct_index must be an integer from 0 to 3."""
    return _generate_json(prompt)


def chat_reply(course, history, message):
    """history: list of {"role": "user"|"model", "content": str}, oldest first."""
    _require_configured()

    lesson_titles = ", ".join(course.lessons.values_list("title", flat=True)) or "(none yet)"
    system_instruction = f"""You are a friendly, patient teaching assistant helping a student in the course "{course.title}".
Course description: {course.description or "(no description)"}
Lesson topics covered so far: {lesson_titles}

Answer the student's questions clearly and concisely. If a question is unrelated to the course,
gently redirect them back to course material. Keep answers focused, use simple language, and
prefer short paragraphs or bullet points over long blocks of text. Do not use markdown headers."""

    messages = [{"role": "system", "content": system_instruction}]
    for turn in history:
        role = "assistant" if turn["role"] == "model" else "user"
        messages.append({"role": role, "content": turn["content"]})
    messages.append({"role": "user", "content": message})

    return _chat(messages)
