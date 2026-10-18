# AI Setup & Gemini Integration Guide

This guide explains how to configure, verify, and run the real LLM-powered document generation and template drafting features in **DocumentGenerator** using Google's Gemini API.

---

## 1. Environment Variable Configuration

The application uses Google's Gemini API for natural-language template drafting and field extraction. To enable real LLM calls, set the `GEMINI_API_KEY` environment variable in your terminal or `.env` file:

### Windows (PowerShell)
```powershell
$env:GEMINI_API_KEY="your-gemini-api-key-here"
```

### Windows (Command Prompt)
```cmd
set GEMINI_API_KEY=your-gemini-api-key-here
```

### Linux / macOS (Bash / Zsh)
```bash
export GEMINI_API_KEY="your-gemini-api-key-here"
```

> [!IMPORTANT]
> **API Key Privacy & Security**:
> - Never hardcode or commit API keys into source code or git history.
> - The application transmits the API key strictly via the `x-goog-api-key` HTTP header, never in the request URL query parameters where it might be logged in web server access logs or proxy traces.
> - If `GEMINI_API_KEY` is not set or empty, the application falls back safely to the deterministic `StubLLMClient` for offline testing and development.

---

## 2. API Communication & Schema Enforcement

1. **Header-Based Authentication**:
   - `GeminiLLMClient` sends all requests to Google's Generative Language API endpoint:
     `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
   - Authentication header: `x-goog-api-key: <GEMINI_API_KEY>`

2. **Simplified Inlined Schema**:
   - Gemini's `generationConfig.response_schema` does not accept complex OpenAPI schemas containing `$defs` or `$ref` pointers.
   - The application automatically simplifies Pydantic schemas via `simplify_schema_for_gemini`, recursively inlining definitions so that Gemini strictly generates conformant JSON.

3. **Typed Error Handling**:
   - The Gemini client returns typed exceptions rather than empty dicts or generic errors:
     - `AIAuthenticationError` (401/403): Invalid API key or missing permissions.
     - `AIQuotaError` (429): Quota or rate limit exceeded.
     - `AITimeoutError` (504): Network timeout.
     - `AIBadResponseError` (502): Malformed or empty JSON.
   - The API surfaces clear messages prefixed with `"AI service error: <reason>"` rather than confusing schema validation failures when the upstream service fails.

---

## 3. Security & Anti-Hallucination Guardrails

1. **Identifier Whitelisting & Sandboxed Jinja**:
   - All variable names, field keys, loop variables, and column identifiers must match `^[a-z][a-z0-9_]{0,39}$`.
   - Reserved Python and Jinja dunders/builtins are rejected with HTTP 422.
   - Compiled templates render in a `SandboxedEnvironment(autoescape=True, undefined=StrictUndefined)`.

2. **Official Wording Protection**:
   - Official certification, approval, sanction, and undertaking statements cannot be hallucinated.
   - Each paragraph in AI output that matches an official trigger is compared sentence-by-sentence against what the user wrote in their prompt.
   - If the user did not supply the exact or near-exact phrasing verbatim, the block is replaced with the visible placeholder: `"Add official wording here"` (flagged with `official_wording_required=True`).

3. **Token Accounting**:
   - Real token counts from the upstream `usageMetadata` (`promptTokenCount`, `candidatesTokenCount`) are recorded in the `ai_requests` table.
   - If `usageMetadata` is absent or the request was simulated, `tokens_in` and `tokens_out` are recorded as `null`, and `usage_estimated` is flagged as `true`. Word-count guesses are never stored as real tokens.

4. **Numbering Series Isolation**:
   - Each AI-drafted template derives a unique series key within the club (e.g., `SPON`, `SPON2`, `SPON3`). Two templates never share a numbering counter.

---

## 4. Running Tests

### Running the Standard Offline Suite
All offline tests run using the deterministic stub client without requiring network access:
```powershell
python -m pytest -v -p no:cacheprovider
```

### Running Live Gemini API Tests
To execute live integration tests against the Gemini API:
```powershell
# Set your API key in your session
$env:GEMINI_API_KEY="your-gemini-api-key"

# Run tests marked with 'live'
python -m pytest -v -m live
```
If `GEMINI_API_KEY` is not present, the live tests will be safely skipped.
