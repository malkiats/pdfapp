# ADR-0007: AI tools through Groq, in-request, with consent

Status: accepted · Date: 2026-11-01

## Context
The AI tools (summarize, translate, markdown, Q&A) are kept. They are short outbound calls that fit the 60 s limit of ADR-0006. There is no storage or accounts, so usage cannot be metered per user.

## Decision
- **One client**: `services/ai/groq_client.py`, using httpx pinned to the Groq base URL. Model ids and `max_tokens` come from settings (`APP_AI__MODEL_*`). `GROQ_API_KEY` comes from Vercel env, with no default. There is a global kill switch, `APP_AI__ENABLED`.
- **Consent**: the request must include `ai_consent: true`, otherwise the API returns `400 ai_consent_required`. The UI names Groq and links to its terms. Consent is not stored, because there is nowhere to store it.
- **Input**: text in the JSON body, or a PDF whose text is extracted with pdfplumber. Capped at `APP_AI__MAX_INPUT_CHARS` (default 20,000) and the 4 MB request limit. Request timeout 30 s, no retries beyond one on 429/5xx.
- **Metering and abuse**: rate limits per ADR-0006, plus a monthly spend cap on the Groq account. Token counts per tool are logged (counts only). Per-user metering waits for Phase 7.
- **Privacy**: prompts and outputs are never logged or stored. Before enabling the tools in production, verify Groq's current retention and training terms and turn on any zero-retention option they offer. Disclosed in privacy.md.

## Consequences
- (+) Simple. Fits the no-storage design.
- (−) No per-user quota. Cost is bounded only by rate limits and the provider spend cap.
- (−) Content leaves our boundary to a third party (disclosed, opt-in).
