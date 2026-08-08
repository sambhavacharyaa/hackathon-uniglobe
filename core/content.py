"""
All copy and structured data for the marketing landing page
(templates/landing.html and everything it includes).

Kept separate from views.py because it's pure content, not logic — a
non-engineer should be able to edit product copy here without touching a
view. Every string in here describes a feature that actually exists in the
app; nothing is aspirational or fabricated (no fake pilot schools, no
invented testimonials, no model-routing claims we don't implement).
"""
from datetime import date

from django.urls import reverse

SITE_NAME = "Skill Up"
SITE_TAGLINE = "an AI co-teacher for your LMS"
SITE_DESCRIPTION = (
    "Skill Up pairs a course platform for teachers and students with four AI tools: "
    "marksheet review, an AI quiz generator, a doubt-solving chat assistant, and "
    "resource-rich lessons — built for the Uniglobe Hackathon."
)


def get_landing_context():
    register_url = reverse("register")
    login_url = reverse("login")

    return {
        "SITE_NAME": SITE_NAME,
        "SITE_TAGLINE": SITE_TAGLINE,
        "SITE_DESCRIPTION": SITE_DESCRIPTION,
        "current_year": date.today().year,

        "nav_links": [
            {"href": "#problem", "label": "Why", "hint": "Scores vs. real feedback"},
            {"href": "#capabilities", "label": "Features", "hint": "The four AI tools"},
            {"href": "#pipeline", "label": "How it works", "hint": "Sign-up to insight"},
            {"href": "#pricing", "label": "Pricing", "hint": "Self-host, free"},
            {"href": "#faq", "label": "FAQ", "hint": "Honest answers"},
        ],

        "footer_columns": [
            {
                "title": "Product",
                "links": [
                    {"href": "#capabilities", "label": "Features"},
                    {"href": "#pipeline", "label": "How it works"},
                    {"href": "#pricing", "label": "Pricing"},
                    {"href": "#faq", "label": "FAQ"},
                ],
            },
            {
                "title": "Account",
                "links": [
                    {"href": login_url, "label": "Log in"},
                    {"href": register_url, "label": "Sign up"},
                ],
            },
            {
                "title": "Project",
                "links": [
                    {"href": "https://github.com/sambhavacharyaa/hackathon-uniglobe", "label": "Source on GitHub"},
                ],
            },
        ],

        # ---------------------------------------------------------------- hero
        "hero": {
            "eyebrow": "Built for the Uniglobe Hackathon",
            "headline_lines": [
                {"text": "A score tells you", "accent": False, "split": False},
                {"text": "what happened.", "accent": False, "split": False},
                {"text": "Skill Up tells you why.", "accent": True, "split": True},
            ],
            "subhead": (
                "Skill Up is a full course platform — lessons, assignments, dashboards — "
                "with four AI tools built in: marksheet review, an AI quiz generator, a "
                "doubt-solving chat assistant, and resource-rich lessons."
            ),
            "rotating_nouns": ["marksheet reviews", "AI-generated quizzes", "student questions", "lesson plans"],
            "primary_cta": {"href": register_url, "label": "Get started free"},
            "secondary_cta": {"href": "#capabilities", "label": "See what it does"},
            "ticker": [
                {"value": "4", "suffix": "", "label": "AI tools built in"},
                {"value": "2", "suffix": "", "label": "roles: student & teacher"},
                {"value": "0", "suffix": "", "label": "cost to self-host"},
            ],
        },
        "hero_transcript": [
            {"role": "student", "text": "why does my function return None?"},
            {"role": "assistant", "text": "It runs, but nothing after the loop hits a return statement — add one."},
            {"role": "system", "text": "logged to course-chat · Intro to Python"},
            {"role": "student", "text": "oh — that fixed it, thanks!"},
        ],

        # --------------------------------------------------------------- proof
        "marquee_items": ["Django", "OpenRouter", "SQLite", "Python", "GSAP", "Three.js", "cPanel SMTP"],

        # ------------------------------------------------------------- problem
        "problem": {
            "eyebrow": "The gap a gradebook leaves",
            "title": "A percentage doesn't tell you <span class=\"u-grad\">what to do next</span>.",
            "lede": (
                "Two students can both score 6/10 for completely different reasons. "
                "A plain gradebook shows the same row for both of them."
            ),
            "before": {
                "label": "Plain gradebook",
                "kicker": "What a spreadsheet shows",
                "rows": [
                    {"mark": "correct", "q": "Q1 · Variables"},
                    {"mark": "incorrect", "q": "Q2 · Loops"},
                    {"mark": "correct", "q": "Q3 · Functions"},
                    {"mark": "incorrect", "q": "Q4 · Loops"},
                    {"mark": "incorrect", "q": "Q5 · Loops"},
                    {"mark": "correct", "q": "Q6 · Variables"},
                ],
                "verdict": "6/10 — needs review",
                "aside": "That's the whole story a spreadsheet gives you.",
            },
            "after": {
                "label": "Skill Up's AI review",
                "kicker": "Generated in seconds",
                "headline": "Loops are the actual gap — every miss clusters there.",
                "body": (
                    "This student isn't struggling generally. Everything except loops is solid. "
                    "A focused refresher on for/while loops would likely close most of it."
                ),
                "evidence": ["Q2 · Loops · missed", "Q4 · Loops · missed", "Q5 · Loops · missed"],
                "spread": ["While loops", "Nested loops", "Loop + list combinations"],
                "action": "Suggested: one worked loop example, then a fresh AI-generated quiz to confirm.",
            },
        },

        # ----------------------------------------------------------- diagnosis
        "demo_students": [
            {
                "id": "riya", "accent": "violet", "initials": "RK", "name": "Riya K.",
                "grade": "Intro to Python", "score": "6/10", "subject": "Loops & Iteration",
                "attempts": [
                    {"ok": True, "q": "What does `for i in range(3)` iterate over?", "given": "0, 1, 2", "expected": "0, 1, 2"},
                    {"ok": False, "q": "How many times does `while x < 5: x += 2` run, starting at x = 0?", "given": "5 times", "expected": "3 times"},
                    {"ok": True, "q": "Which keyword exits a loop early?", "given": "break", "expected": "break"},
                    {"ok": False, "q": "What does `range(2, 8)` produce?", "given": "2 to 8, inclusive", "expected": "2, 3, 4, 5, 6, 7"},
                    {"ok": False, "q": "What happens if a while loop's condition never becomes False?", "given": "It runs once", "expected": "It runs forever"},
                    {"ok": True, "q": "What does `continue` do inside a loop?", "given": "Skips to the next iteration", "expected": "Skips to the next iteration"},
                ],
                "label": "Miscounts loop iterations",
                "confidence": 91,
                "rule": "Treats range() bounds as inclusive on both ends, and checks a while condition only after the full block runs.",
                "note": "Not carelessness — a consistent, wrong mental model of how range() and while both terminate.",
                "spread": ["range() bounds", "Nested loops", "While-loop termination"],
                "action": "Suggested: one worked example tracing a loop variable step-by-step, then retry the quiz.",
            },
            {
                "id": "aarav", "accent": "cyan", "initials": "AS", "name": "Aarav S.",
                "grade": "Intro to Python", "score": "7/10", "subject": "Data Types",
                "attempts": [
                    {"ok": True, "q": "Which is mutable: a list or a tuple?", "given": "list", "expected": "list"},
                    {"ok": False, "q": "Can you do `my_tuple[0] = 5`?", "given": "Yes", "expected": "No — tuples are immutable"},
                    {"ok": True, "q": "What type is `3.14`?", "given": "float", "expected": "float"},
                    {"ok": False, "q": "Can you `.append()` to a tuple?", "given": "Yes", "expected": "No — tuples have no append method"},
                    {"ok": True, "q": "What type is `True`?", "given": "bool", "expected": "bool"},
                    {"ok": False, "q": "What does `t = (1, 2, 3); t[1] = 9` do?", "given": "Changes t to (1, 9, 3)", "expected": "Raises a TypeError"},
                ],
                "label": "Treats tuples like lists",
                "confidence": 85,
                "rule": "Knows the definition of \"immutable\" but hasn't yet connected it to what operations that rules out.",
                "note": "The vocabulary is right; the behavior isn't wired up yet. Common at this stage.",
                "spread": ["Tuple methods", "Sets vs. lists", "Immutability generally"],
                "action": "Suggested: a short live \"what breaks and why\" demo in the console.",
            },
            {
                "id": "priya", "accent": "amber", "initials": "PT", "name": "Priya T.",
                "grade": "Intro to Python", "score": "6/10", "subject": "Conditionals",
                "attempts": [
                    {"ok": True, "q": "What does `==` check?", "given": "If two values are equal", "expected": "If two values are equal"},
                    {"ok": False, "q": "What does `if x = 5:` do in Python?", "given": "Checks if x equals 5", "expected": "Raises a SyntaxError"},
                    {"ok": True, "q": "What does `!=` mean?", "given": "Not equal", "expected": "Not equal"},
                    {"ok": False, "q": "Is `if x = True:` valid Python?", "given": "Yes", "expected": "No — = is assignment, not comparison"},
                    {"ok": False, "q": "What's wrong with `if score = 100: print('perfect')`?", "given": "Nothing", "expected": "Should be =="},
                    {"ok": True, "q": "What does `and` require?", "given": "Both conditions true", "expected": "Both conditions true"},
                ],
                "label": "Confuses = with ==",
                "confidence": 88,
                "rule": "Correctly explains what == means out loud, but types = inside if-statements — the rule hasn't reached typing habit yet.",
                "note": "A classic gap between knowing and doing. Usually closes fast with typing practice, not more explanation.",
                "spread": ["While-loop conditions", "Function return checks", "Boolean logic"],
                "action": "Suggested: ten minutes of \"spot the bug\" snippets, not a re-lecture.",
            },
            {
                "id": "control", "accent": "slate", "initials": "—", "name": "Control · noise",
                "grade": "Intro to Python", "score": "6/10", "subject": "Mixed topics",
                "attempts": [
                    {"ok": False, "q": "What does `len([1, 2, 3])` return?", "given": "2", "expected": "3"},
                    {"ok": True, "q": "What does `print()` do?", "given": "Displays output", "expected": "Displays output"},
                    {"ok": False, "q": "What does `str(5)` return?", "given": "5", "expected": "'5'"},
                    {"ok": True, "q": "What symbol starts a comment?", "given": "#", "expected": "#"},
                    {"ok": False, "q": "What does `input()` return?", "given": "A number", "expected": "A string"},
                    {"ok": True, "q": "How do you define a function?", "given": "def", "expected": "def"},
                ],
                "label": "No consistent pattern found",
                "confidence": 22,
                "rule": "No single rule explains these misses — they span unrelated topics with no shared thread.",
                "note": "Flagged for a human, on purpose. A confident-sounding pattern here would be a false read, not a diagnosis.",
                "spread": [],
                "action": "Suggested: a quick check-in. This one needs a person, not a quiz.",
            },
        ],

        # --------------------------------------------------------- capabilities
        "capabilities": [
            {
                "id": "tutor", "icon": "i-chat", "size": "wide", "accent": "violet", "index": "01",
                "audience": "Students", "title": "AI doubt-solving chat",
                "blurb": "Ask a question about any lesson and get a clear, grounded answer in seconds — no waiting for office hours.",
                "bullets": [
                    "Grounded in that course's actual lessons",
                    "Available any time, on any device",
                    "Every conversation saved to revisit later",
                ],
                "metric": {"value": "1 course", "label": "of context per chat"},
            },
            {
                "id": "quizgen", "icon": "i-zap", "size": "tall", "accent": "cyan", "index": "02",
                "audience": "Teachers", "title": "AI quiz generator",
                "blurb": "Turn any lesson into a graded multiple-choice quiz in one click — no prep time.",
                "bullets": [
                    "5 questions generated per lesson",
                    "Auto-graded the moment a student submits",
                    "Regenerate any time the lesson changes",
                ],
                "metric": {"value": "1 click", "label": "from lesson to quiz"},
            },
            {
                "id": "marksheet", "icon": "i-brain", "size": "tall", "accent": "amber", "index": "03",
                "audience": "Students & teachers", "title": "AI marksheet review",
                "blurb": "Enter subject scores and get a real read on what's working, what isn't, and what to do next.",
                "bullets": [
                    "Strengths and focus areas, not just a percent",
                    "Encouraging, specific suggestions for the student",
                    "A separate, practical note for the teacher",
                ],
                "metric": {"value": "2", "label": "tailored write-ups per review"},
            },
            {
                "id": "lessons", "icon": "i-layers", "size": "wide", "accent": "emerald", "index": "04",
                "audience": "Teachers & students", "title": "Resource-rich lessons",
                "blurb": "Every lesson can carry embedded video, written notes, downloadable files, and links.",
                "bullets": [
                    "YouTube & Vimeo links embed automatically",
                    "Progress tracked per student, per lesson",
                    "The lesson's AI quiz lives right alongside it",
                ],
                "metric": {"value": "4", "label": "resource types supported"},
            },
        ],
        "tutor_exchange": [
            {"role": "user", "text": "What's the difference between a list and a tuple?"},
            {"role": "assistant", "text": "Lists can change after you create them; tuples can't. Use a tuple when the data shouldn't."},
            {"role": "user", "text": "Can I still loop through a tuple?"},
            {"role": "assistant", "text": "Yes — looping works exactly the same way for both."},
        ],

        # ------------------------------------------------------------ pipeline
        "pipeline": [
            {
                "step": "01", "accent": "violet", "title": "Sign up & verify",
                "body": "Register as a student or teacher and confirm your email with a 6-digit code.",
                "code": "POST /register/ → OTP emailed → account verified",
            },
            {
                "step": "02", "accent": "cyan", "title": "Teach or enrol",
                "body": "Teachers build a course: lessons, videos, notes, files, assignments. Students browse and enrol in one click.",
                "code": "Course.objects.create(...) → Enrollment.objects.create(...)",
            },
            {
                "step": "03", "accent": "amber", "title": "AI does the busywork",
                "body": "Generate a quiz from any lesson, review a marksheet, or answer a student's question — one call away, via OpenRouter.",
                "code": "llm.generate_quiz(lesson) → 5 questions, auto-graded",
            },
            {
                "step": "04", "accent": "emerald", "title": "Everyone sees what matters",
                "body": "Students get a dashboard with progress and grades. Teachers see rosters, submissions, and AI-flagged insight.",
                "code": "dashboard_student.html · dashboard_teacher.html",
            },
        ],

        # -------------------------------------------------------------- engine
        "engine_models": [
            {
                "accent": "violet", "featured": True, "name": "Default model", "tier": "fast",
                "model_id": "openai/gpt-oss-20b:free", "context": "via OpenRouter",
                "jobs": ["Quiz generation", "Marksheet review", "Chat replies"],
                "price_in": "$0", "price_out": "$0", "share": 100,
            },
        ],
        "engine_notes": [
            {
                "stat": "1 line", "stat_label": "to change models",
                "title": "Provider-agnostic by design",
                "body": "Every AI call goes through one client. Point OPENROUTER_MODEL at any OpenRouter-hosted model — GPT, Claude, Gemini, Llama — with a single environment variable, no code changes.",
            },
            {
                "stat": "0", "stat_label": "hard crashes without a key",
                "title": "Fails gracefully, always",
                "body": "No API key configured? Every AI feature detects it and shows a friendly \"not set up yet\" message instead of an error page — the rest of the app keeps working.",
            },
            {
                "stat": "Seconds", "stat_label": "not minutes",
                "title": "Fast enough to feel live",
                "body": "Quiz generation, marksheet review, and chat replies all return within a few seconds — no background jobs or polling required.",
            },
        ],

        # ------------------------------------------------------------- numbers
        "numbers": [
            {"accent": "violet", "value": "4", "suffix": "", "label": "AI-powered features"},
            {"accent": "cyan", "value": "4", "suffix": "", "label": "content types per lesson"},
            {"accent": "amber", "value": "5", "suffix": "", "label": "quiz questions per lesson"},
            {"accent": "emerald", "value": "2", "suffix": "", "label": "tailored dashboards"},
        ],

        # ------------------------------------------------------------- voices
        "testimonials": [
            {
                "accent": "violet", "initials": "01", "name": "On marksheets", "role": "Design principle",
                "quote": "A percentage tells you what happened. It doesn't tell you what to do about it — so we made the second part the whole feature.",
            },
            {
                "accent": "cyan", "initials": "02", "name": "On the chat assistant", "role": "Design principle",
                "quote": "The best time to ask a question is the moment you're stuck — not three days later in office hours.",
            },
            {
                "accent": "amber", "initials": "03", "name": "On AI quizzes", "role": "Design principle",
                "quote": "Writing five good questions takes a teacher real time. Reviewing five AI-drafted ones takes a minute.",
            },
            {
                "accent": "emerald", "initials": "04", "name": "On failing safely", "role": "Design principle",
                "quote": "No API key shouldn't mean a broken page. Every AI feature has a plain, honest fallback.",
            },
        ],

        # ------------------------------------------------------------ pricing
        "pricing": [
            {
                "accent": "cyan", "featured": False, "badge": None,
                "name": "Self-hosted", "tagline": "Run it yourself, keep everything",
                "price_monthly": 0, "price_yearly": 0, "price_note": "forever, open source",
                "features": [
                    "Full Django source code",
                    "All 4 AI features (bring your own OpenRouter key)",
                    "Unlimited students & teachers",
                    "SMTP email you control",
                ],
                "absent": [],
                "cta": "Get the code",
            },
            {
                "accent": "violet", "featured": True, "badge": "For schools",
                "name": "Managed for your school", "tagline": "We host it, you just teach",
                "price_monthly": None, "price_yearly": None, "price_note": "let's talk",
                "features": [
                    "Everything in Self-hosted",
                    "Hosting, backups & updates handled",
                    "Onboarding for your staff",
                ],
                "absent": [],
                "cta": "Get in touch",
            },
        ],

        # ---------------------------------------------------------------- faq
        "faq": [
            {
                "q": "Is this just a chatbot with a database bolted on?",
                "a": (
                    "No — the chat assistant is one of four features. The other three (marksheet review, quiz "
                    "generation, and lesson resources) don't involve a conversation at all; they're structured "
                    "AI calls that read real data and write structured feedback back into the app."
                ),
            },
            {
                "q": "What happens if the AI provider is down or the key is missing?",
                "a": (
                    "Every AI feature checks for a configured key before calling out. If it's missing or the "
                    "request fails, you get a clear in-app message instead of a crash — the rest of the LMS "
                    "(courses, dashboards, grading) doesn't depend on AI at all."
                ),
            },
            {
                "q": "Which AI provider does this actually use?",
                "a": (
                    "OpenRouter, which is OpenAI-API-compatible and proxies dozens of models. The default is a "
                    "free-tier model, and swapping to a paid one is a single environment variable — no code changes."
                ),
            },
            {
                "q": "Is the login secure?",
                "a": (
                    "Accounts are created inactive until the student or teacher verifies a 6-digit, "
                    "10-minute-expiry code sent to their real email address over SMTP — not a fake or client-side check."
                ),
            },
            {
                "q": "Does the diagnosis demo above call a real model?",
                "a": (
                    "No — it replays four seeded example students entirely in the browser, labelled as a "
                    "simulation on the page. The AI marksheet review and quiz generator elsewhere in the app do "
                    "make real calls; this demo exists so you can see the shape of that output without needing "
                    "an account first."
                ),
            },
            {
                "q": "Can a teacher and a student use the same login?",
                "a": (
                    "No — role is chosen at signup and fixed. Teacher-only pages (creating courses, grading, "
                    "generating quizzes) are blocked for students at the view level, not just hidden in the UI."
                ),
            },
        ],

        # ---------------------------------------------------------------- cta
        "cta": {
            "eyebrow": "Ready when you are",
            "title": "Create your class in the next two minutes.",
            "body": "No credit card, no sales call — register, verify your email, and start teaching or learning.",
            "reassurance": "Free to self-host. Your data stays in your own database.",
        },
    }
