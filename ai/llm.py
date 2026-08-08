"""Thin wrapper around OpenRouter (an OpenAI-compatible chat completions API)
used by every AI feature in the app.

Every public function raises LLMError on failure (missing key, network
error, malformed response) so views can catch one exception type and show a
friendly message instead of a 500.
"""
import base64
import io
import json
import logging
import re

from django.conf import settings
from openai import OpenAI
from PIL import Image

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


def _chat(messages, model=None):
    _require_configured()
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=model or settings.OPENROUTER_MODEL,
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


def _generate_json(prompt, system_instruction=None, model=None):
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    # Free-tier models occasionally wrap the JSON in stray commentary or
    # return something malformed one time in a while. That's a sampling
    # fluke, not a systemic problem, so one silent retry with a fresh
    # completion clears almost all of them before the user ever sees an
    # error — cheap insurance against a flaky response mid-demo.
    last_exc = None
    for attempt in range(2):
        text = _chat(messages, model=model)
        try:
            return _extract_json(text)
        except (ValueError, TypeError) as exc:
            last_exc = exc
            logger.warning("OpenRouter returned invalid JSON on attempt %d: %r", attempt + 1, text)

    logger.exception("OpenRouter returned invalid JSON after retry", exc_info=last_exc)
    raise LLMError("The AI returned an unexpected response. Please try again.") from last_exc


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


def _image_to_data_uri(image_bytes, max_dimension=1600, quality=85):
    """Downscale to a sane size and re-encode as JPEG before sending to the
    API — keeps the request fast and well under any payload limit regardless
    of how large the original photo was."""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img = img.convert("RGB")
        if max(img.size) > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        encoded = base64.b64encode(buf.getvalue()).decode()
    except Exception as exc:
        raise LLMError("That image couldn't be read. Try a different photo or format.") from exc
    return f"data:image/jpeg;base64,{encoded}"


def review_answer_sheet(image_bytes, subject):
    """Read a photographed/scanned exam answer sheet and review it.

    Requires OPENROUTER_VISION_MODEL — most free text models can't see
    images at all, so this always uses the vision-specific model setting
    rather than the default OPENROUTER_MODEL.
    """
    _require_configured()
    data_uri = _image_to_data_uri(image_bytes)

    prompt = f"""You are an experienced exam grader reviewing a student's handwritten or printed answer sheet for: {subject}.

Read every question and answer visible in the image carefully, including any diagrams or working shown. Respond with ONLY a JSON object (no markdown fences, no extra text) of this exact shape:
{{
  "transcription": "a brief plain-text summary of what was written, question by question",
  "overall_feedback": "2-3 sentence overview of how the student performed overall",
  "strengths": ["short phrase", "short phrase"],
  "mistakes": ["short phrase describing a specific error found, referencing which question"],
  "improvement_suggestions": "A warm, encouraging, SPECIFIC paragraph on what to study or practice before the next exam, directly referencing the mistakes found in this answer sheet."
}}
If the image is too unclear to read, say so honestly in "overall_feedback" and leave the other fields as empty lists/strings rather than guessing."""

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }
    ]
    text = _chat(messages, model=settings.OPENROUTER_VISION_MODEL)
    try:
        return _extract_json(text)
    except (ValueError, TypeError) as exc:
        logger.exception("OpenRouter returned invalid JSON for answer sheet: %r", text)
        raise LLMError("The AI returned an unexpected response. Please try again.") from exc


def _viva_context_block(course):
    if not course:
        return ""
    lesson_titles = ", ".join(course.lessons.values_list("title", flat=True)) or "(none yet)"
    return f'\nThis viva is for the course "{course.title}". Lessons covered: {lesson_titles}.\n'


def generate_viva_question(topic, course, transcript):
    """Ask the opening question (transcript empty) or a targeted follow-up
    that probes whatever was weak or vague in the student's latest answer.

    transcript: list of {"question": str, "answer": str}, oldest first,
    already includes the just-answered turn.
    """
    context = _viva_context_block(course)

    if not transcript:
        prompt = f"""You are an experienced oral examiner (viva voce) about to test a student's understanding of: {topic}.{context}
Ask ONE clear, moderately challenging opening question. It should require the student to explain or apply the concept, not just recall a definition.

Respond with ONLY a JSON object (no markdown fences, no extra text):
{{"question": "your opening question"}}"""
    else:
        transcript_text = "\n\n".join(
            f"Q{i + 1}: {t['question']}\nStudent's answer: {t['answer']}" for i, t in enumerate(transcript)
        )
        prompt = f"""You are an experienced oral examiner (viva voce) probing a student's understanding of: {topic}.{context}

Conversation so far:
{transcript_text}

You are not grading yet — you are probing. Look closely at the student's MOST RECENT answer:
- If it was vague, incomplete, hedged, or sounds like a memorized definition rather than real understanding, ask a targeted follow-up that goes straight at that specific weakness: ask them to apply the idea to a new situation, explain the reasoning behind a claim they made, define a term they used loosely, or resolve an apparent contradiction.
- If the answer was genuinely strong, don't just move on to an unrelated question — push a level deeper: a harder edge case, a "what if" that tests the boundary of the same idea.
- Never ask something already covered above, and don't just reword the previous question.

Respond with ONLY a JSON object (no markdown fences, no extra text):
{{"question": "your follow-up question", "probe_reason": "one short phrase, e.g. 'answer was vague about why, not just what'"}}"""

    return _generate_json(prompt)


def generate_viva_verdict(topic, course, transcript):
    """Final read on the whole exchange: genuine understanding vs. rote
    recall, once every round has been answered."""
    context = _viva_context_block(course)
    transcript_text = "\n\n".join(
        f"Q{i + 1}: {t['question']}\nStudent's answer: {t['answer']}" for i, t in enumerate(transcript)
    )
    prompt = f"""You are an experienced oral examiner (viva voce) who has just finished questioning a student on: {topic}.{context}

Full exchange:
{transcript_text}

Give your honest verdict on whether this student genuinely understands {topic}, or whether they are reciting memorized material without real comprehension. Base this on how their answers held up under follow-up questioning — understanding that survives probing is real; understanding that collapses into vagueness under a follow-up usually is not.

Respond with ONLY a JSON object (no markdown fences, no extra text) of this exact shape:
{{
  "verdict": "strong" | "developing" | "rote" | "weak",
  "verdict_label": "a short human label for the verdict, e.g. \\"Genuine understanding\\" or \\"Memorized, not understood\\"",
  "summary": "2-3 sentence overall assessment referencing specifically how they responded to the follow-ups",
  "strengths": ["short phrase", "short phrase"],
  "gaps": ["short phrase describing a specific gap exposed by a follow-up", "short phrase"],
  "suggestions": "a specific, actionable paragraph on what to actually study or practice next, based on the gaps found"
}}"""
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
