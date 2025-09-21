import json
import logging
import requests
from typing import Any, Dict

logger = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

PROMPT_TEMPLATE = (
    "You are a content moderation and positivity detector for a Discord server.\n"
    "Classify the following message and return STRICT JSON with these fields: \n"
    "{\n"
    "  \"flagged\": boolean, // true if harmful/abusive/profane\n"
    "  \"reasons\": string[], // reasons like ['abuse','profanity','harassment']\n"
    "  \"good_advice\": boolean, // true if the message gives polite, helpful advice\n"
    "  \"problem_solved\": boolean, // true if the message solves someone's problem\n"
    "  \"praise\": boolean // true if the message praises or thanks someone for help\n"
    "}\n"
    "Do not include any extra commentary, only raw JSON.\n"
    "Message: \n" 
)


def analyze_message(api_key: str, text: str) -> Dict[str, Any]:
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": PROMPT_TEMPLATE + text}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "topP": 0.1,
            "topK": 32,
            "maxOutputTokens": 256,
            "responseMimeType": "application/json"
        }
    }
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": api_key,
    }
    try:
        res = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=15)
        res.raise_for_status()
        data = res.json()
        # The response JSON may include candidates -> content -> parts -> text
        text_out = None
        try:
            text_out = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            # Fallback to raw
            text_out = json.dumps(data)
        result = {
            "flagged": False,
            "reasons": [],
            "good_advice": False,
            "problem_solved": False,
            "praise": False,
        }
        if text_out:
            try:
                parsed = json.loads(text_out)
                result.update({
                    "flagged": bool(parsed.get("flagged", False)),
                    "reasons": list(parsed.get("reasons", []) or []),
                    "good_advice": bool(parsed.get("good_advice", False)),
                    "problem_solved": bool(parsed.get("problem_solved", False)),
                    "praise": bool(parsed.get("praise", False)),
                })
            except json.JSONDecodeError:
                logger.warning("Gemini non-JSON output, treating as not flagged")
        return result
    except requests.HTTPError as e:
        logger.error("Gemini API HTTP error: %s", e)
    except Exception as e:
        logger.error("Gemini API error: %s", e)
    return {"flagged": False, "reasons": [], "good_advice": False, "problem_solved": False}
