# test_team_mock.py
import json
from dotenv import load_dotenv
import os

from team_email_digest import summarize_email, compose_brief, send_to_slack

# --- Optional: call the model directly to see RAW JSON (before normalization) ---
try:
    from openai import OpenAI
    load_dotenv()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
except Exception:
    openai_client = None

# Safe template (double braces) + manual replacement for body
RAW_PROMPT_TMPL = (
    'Return ONLY valid JSON with keys exactly as follows:\n'
    '{{\n'
    '  "summary": "1-2 sentence concise summary",\n'
    '  "decisions": ["short decision 1", "short decision 2"],\n'
    '  "actions": [\n'
    '    {{"title": "action title", "owner": "", "due": "", "priority": "high|med|low"}}\n'
    '  ]\n'
    '}}\n'
    'Rules:\n'
    '- No text outside the JSON.\n'
    '- Always return "actions" as objects.\n'
    '- Prefer ISO due dates in the future (YYYY-MM-DD). If only a weekday is given, use the next occurrence.\n'
    '- If owner or due is unknown, use an empty string.\n\n'
    'Email:\n<<EMAIL_BODY>>'
)

def get_raw_model_json(email_body: str):
    """Directly ask the model for JSON (to compare with our normalized output)."""
    if not openai_client:
        return None  # no key set; skip
    prompt = RAW_PROMPT_TMPL.replace("<<EMAIL_BODY>>", email_body)
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"user","content": prompt}],
        max_tokens=400
    )
    raw_text = resp.choices[0].message.content.strip()
    start, end = raw_text.find("{"), raw_text.rfind("}")
    json_text = raw_text[start:end+1] if (start != -1 and end != -1 and end > start) else raw_text
    try:
        return json.loads(json_text)
    except Exception:
        return {"_parse_error": True, "_raw": raw_text}

# --- Mock emails for demo ---
MOCK_EMAILS = [
    {
        "subject": "Budget approved for Alpha",
        "from": "CEO <ceo@company.com>",
        "body": "We approved an extra $15k for Alpha. Priya to update the plan. Target date is Nov 1."
    },
    {
        "subject": "Client needs final draft",
        "from": "Client <pm@bigcorp.com>",
        "body": "Please send the final proposal by Thursday EOD. John is responsible."
    },
    {
        "subject": "Weekly Newsletter",
        "from": "news@service.com",
        "body": "This week: AI trends, market shifts. Nothing urgent."
    }
]

def main():
    items = []

    for m in MOCK_EMAILS:
        email_payload = f"Subject: {m['subject']}\nFrom: {m['from']}\n\n{m['body']}"

        # 1) RAW model JSON (before normalize)
        raw_json = get_raw_model_json(email_payload)
        if raw_json is not None:
            print("\n--- RAW MODEL JSON for:", m["subject"], "---")
            print(json.dumps(raw_json, indent=2))

        # 2) NORMALIZED via our pipeline
        norm = summarize_email(email_payload)
        print("\n--- NORMALIZED for:", m["subject"], "---")
        print(json.dumps(norm, indent=2))

        items.append({
            "subject": m["subject"],
            "summary": norm.get("summary",""),
            "decisions": norm.get("decisions", []),
            "actions": norm.get("actions", [])
        })

    brief = compose_brief(items)
    print("\n==== DIGEST ====\n")
    print(brief)

    # If SLACK_WEBHOOK_URL is set in .env, this will post:
    send_to_slack(brief)

if __name__ == "__main__":
    main()
