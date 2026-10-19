# AI Setup & Gemini Integration Guide

This guide explains how SVNIT ClubDocs integrates with Google's Gemini API for natural-language template drafting and field extraction, how model names are resolved dynamically, and what data is transmitted.

---

## 1. Dynamic Model Selection & Why Model Names Change

AI models are regularly updated, deprecated, and retired by upstream providers (for example, `gemini-2.5-flash` returned HTTP 404 "no longer available to new users").

To prevent broken workflows:
1. **Dynamic Model Discovery (`docgen/llm.py`)**:
   - At startup and when drafting templates, ClubDocs queries the Gemini models endpoint:
     `https://generativelanguage.googleapis.com/v1beta/models`
   - It filters for models supporting `generateContent` and containing `flash` (excluding specialized audio/image models).
   - Selection priority:
     1. `GEMINI_MODEL` from your `.env` (if valid and present in the supported models list).
     2. `gemini-flash-latest` (if present).
     3. The newest non-preview flash model (e.g. `gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-3.5-flash`).
     4. Any available flash model.
2. **1-Hour In-Memory Cache**:
   - The selected model is cached for 1 hour (`MODEL_CACHE_TTL = 3600`).
   - If an HTTP 404 ("model not found" or "no longer available") occurs, the cache is automatically cleared, the endpoint re-queried, and the next candidate model is selected and retried ONCE.
3. **HTTP 429 Quota Backoff**:
   - If an HTTP 429 quota/rate limit error occurs, the client iterates candidate flash models with a 1-second backoff (`time.sleep(1)`).

---

## 2. Configuration & How to Set `GEMINI_MODEL`

In your `.env` file or environment variables:

```ini
# Required for real AI drafting:
GEMINI_API_KEY=AIzaSy...

# Optional override:
GEMINI_MODEL=gemini-flash-latest
```

### Windows (PowerShell)
```powershell
$env:GEMINI_API_KEY="AIzaSy..."
$env:GEMINI_MODEL="gemini-flash-latest"
```

To test and discover which models are currently available with your key, run the diagnostic doctor:
```powershell
python -m server.scripts.doctor
```
This prints:
`Gemini API connected. Discovered flash models: [gemini-flash-latest, gemini-3.8-flash, ...]. Selected model for docgen: 'gemini-flash-latest'.`

---

## 3. Privacy & What Data is Sent to the AI

SVNIT ClubDocs enforces strict institutional data protection:

| Data Type | Sent to Gemini? | Explanation |
| :--- | :---: | :--- |
| **User Prompt / Description** | **YES** | The exact natural-language text entered by the user in the prompt box (e.g. *"Create a sound system permission letter for our cultural fest"*). |
| **Document Outline & Theme** | **YES (Studio)** | When using the Studio Chat Copilot, a compact outline (block types, block IDs, and short text snippets) and the active theme name are sent so the AI understands document structure. |
| **Personal Identifiable Information (PII)** | **NO** | Any detected names, roll numbers, mobile numbers, and emails are stripped (`strip_pii_from_text`) before sending text to the LLM. |
| **Club Database Records** | **NO** | Club database records, membership rosters, and audit logs are **never** sent. |
| **Passwords & Hashes** | **NO** | Never transmitted or logged. |
| **Financial & Bank Details** | **NO** | Real bank account numbers, IFSC codes, PAN, and GST numbers are never included in prompts. |
| **Other Clubs' Data** | **NO** | All queries are strictly scoped to the active club context; cross-club data leakage is impossible. |

> [!IMPORTANT]
> The API key is sent strictly in the `x-goog-api-key` HTTP header. It is **never** included in URL query parameters, never printed to terminal logs, and never included in error messages.

---

## 4. Plain-Language User Error Messages

When an AI request cannot complete, the user receives an honest, plain-language explanation rather than raw Google JSON errors:

- **Model Retired / Missing**:  
  `"The AI model is not available. Set GEMINI_MODEL in .env to one of: <list>."`
- **Quota Exceeded (429)**:  
  `"Gemini API quota exceeded or rate limit reached. Tip: Set GEMINI_API_KEY in your environment or .env..."`
- **Invalid Key (400/401/403)**:  
  `"Gemini API key is invalid or expired. Check your .env."`
- **Overloaded (503)**:  
  `"AI service is temporarily overloaded. Please try again in a few moments."`
- **Timeout**:  
  `"AI service timed out after 30s. Try a shorter prompt."`
- **Malformed Response**:  
  `"AI service returned invalid data. You can build this manually in the editor."`
- **Offline / Missing Key**:  
  Falls back cleanly to `StubLLMClient` for offline testing.

---

## 5. Security & Anti-Hallucination Guardrails

1. **Jinja Sandboxing**: All user input is treated as DATA. Jinja delimiters (`{{`, `}}`, `{%`, `%}`) in user text are escaped automatically.
2. **Official Wording Protection**: Official certification, sanction, undertaking, or approval language is never written by the AI. It is replaced with an `"Add official wording here"` placeholder unless the user typed it verbatim.
3. **No Unreviewed AI Drafts in Official PDFs**: AI-suggested content is always tagged `[AI-drafted, review]` and must be explicitly reviewed and accepted before document generation.
