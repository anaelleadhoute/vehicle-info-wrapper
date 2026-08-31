# Vehicle Info Wrapper API

Part A of the car-insurance onboarding assignment: a small service that
wraps the insurer's upstream vehicle-info stub API, for use as a webhook
from the Insait/Encore Conversation Flow Agent in Part B.

## Why wrap it instead of calling upstream directly?

- **Normalized responses.** Upstream returns different HTTP status codes
  (200/400/404) with different body shapes for different outcomes. This
  service always returns `200` for business outcomes (`ok`,
  `invalid_format`, `not_found`) with a single `status` field, which is far
  easier for a no-code flow builder to branch on than parsing HTTP status
  codes. Genuine infrastructure failures (upstream unreachable/timeout)
  return `502` so they can be handled differently (e.g. escalate to a
  human) rather than treated as a normal conversational branch.
- **Input validation before forwarding.** Plate format is checked here
  first, saving a wasted upstream call for input that's already invalid.
- **Resilience.** Requests to upstream have a timeout and are retried on
  transient failures (timeouts / 5xx) — not on business failures (400/404).
- **Caching.** Repeated lookups of the same plate within 60s are served
  from an in-memory cache instead of re-hitting upstream.
- **A stable contract.** If the upstream API's shape ever changes, only
  this service needs updating — the flow in Part B keeps working against
  the same contract.
- **Hebrew → English translation.** Upstream returns `manufacturer`,
  `model`, and `color` in Hebrew. This service translates them to English
  via a lookup table in `app/translate.py` (deterministic, no external
  translation API needed since the upstream dataset is small and fixed).
  Unknown values pass through untranslated rather than erroring, and are
  logged so the table can be extended as new values are seen.

## API

### `POST /vehicle-info`

Request:
```json
{ "license_plate": "12345678" }
```

Response (always `200` unless it's a genuine upstream failure):
```json
{
  "status": "ok",
  "vehicle": {
    "license_plate": "12345678",
    "manufacturer": "Toyota",
    "model": "Corolla",
    "year": 2020,
    "color": "White"
  },
  "message": "Vehicle found.",
  "cached": false
}
```

`status` is one of: `ok`, `invalid_format`, `not_found`, `upstream_error`.

### `GET /health`

Basic health check, returns `{"status": "ok"}`.

## Running locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then:
```bash
curl -X POST http://localhost:8000/vehicle-info \
  -H "Content-Type: application/json" \
  -d '{"license_plate": "12345678"}'
```

## Deploying to Render

1. Push this folder to a GitHub repo.
2. In Render, "New +" → "Blueprint", point it at the repo — it will pick up
   `render.yaml` automatically and configure the service.
   (Alternatively: "New +" → "Web Service", build command
   `pip install -r requirements.txt`, start command
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.)
3. Once deployed, Render gives you a public URL like
   `https://vehicle-info-wrapper.onrender.com`. Use
   `https://vehicle-info-wrapper.onrender.com/vehicle-info` as the webhook
   URL in the Part B flow.

A `Dockerfile` is also included if you'd rather deploy via a container
(e.g. to Cloud Run) instead of Render's native Python runtime.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `UPSTREAM_BASE_URL` | the assignment's stub API URL | Upstream base URL |
| `UPSTREAM_TIMEOUT_SECONDS` | `5` | Per-request timeout to upstream |
| `UPSTREAM_MAX_RETRIES` | `2` | Retries on timeout/5xx before giving up |
