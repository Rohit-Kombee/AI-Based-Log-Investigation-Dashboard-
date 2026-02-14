# Postman Collection — AI Log Investigation Assistant

## Import

1. Open Postman → **Import** → choose `AI_Log_Investigation_Assistant.postman_collection.json`.
2. Set **base_url** if needed: collection variables → `base_url` = `http://127.0.0.1:5000` (or your port, e.g. 8080).

## Run order (for demo / marking)

1. **Health** — confirm server is up: `{"status": "ok"}`.
2. **Ingest** — run “Valid logs (standard)”, then “Valid logs (alternate fields)” so you have data.
3. **Ingest edge cases** — “Empty logs array”, “Malformed”, “Mixed” to show rejection handling.
4. **Normalize** — “Standard raw log” and “Alternate fields” to show canonical output.
5. **Validate** — “Valid log”, “Invalid log (bad level)” to show valid vs reject.
6. **Group** — “All”, “With limit & service”, “By level ERROR” to show clustering.
7. **Spikes** — “Default” (and “Custom window” if you want).
8. **Insights** — “Default” to show human-friendly summary (LLM or fallback).

---

## What you see in Postman (expected responses)

### 1. POST /ingest

| Request | Expected status | What you see |
|--------|-----------------|--------------|
| Valid logs (standard) | 200 | `accepted: 2`, `rejected: 0`, `errors: []` |
| Valid logs (alternate) | 200 | `accepted: 1`, `rejected: 0` — logs stored after normalization |
| Empty logs array | 200 | `accepted: 0`, `rejected: 0`, `errors: []` |
| Malformed | 200 | `accepted: 0`, `rejected: 1`, `errors: [{ "index": 0, "error": "..." }]` |
| Mixed | 200 | `accepted: 2`, `rejected: 1`, `errors` for the one rejected |

### 2. POST /normalize

| Request | Expected status | What you see |
|--------|-----------------|--------------|
| Standard / Alternate | 200 | JSON with `timestamp`, `level`, `message`, `service` (canonical). Alternate fields mapped (e.g. `lvl`→`level`, `msg`→`message`). |

### 3. POST /validate

| Request | Expected status | What you see |
|--------|-----------------|--------------|
| Valid log | 200 | `valid: true`, `errors: []` |
| Invalid (bad level) | 200 | `valid: false`, `errors: ["Invalid level: INVALID. Allowed: ..."]` |

### 4. GET /group

| Request | Expected status | What you see |
|--------|-----------------|--------------|
| All / With params | 200 | `groups: [{ group_id, count, level, service, sample_message, first_seen, last_seen }, ...]`, `total_groups`. Same fingerprint = same group. |

### 5. GET /spikes

| Request | Expected status | What you see |
|--------|-----------------|--------------|
| Default / Custom | 200 | `spikes: [{ group_id, service, level, count, baseline_avg, ratio }, ...]` — groups where current volume is above baseline. |

### 6. GET /insights

| Request | Expected status | What you see |
|--------|-----------------|--------------|
| Default | 200 | `summary` (string — human-friendly text), `top_groups`, `spikes`. With API key: LLM summary; without: short text summary. |

---

## Mapping to scoring

- **Correctness (30):** Use Ingest (valid + empty + malformed + mixed), Normalize, Validate, Group, Spikes, Insights — all return 200 and expected shapes; rejections and errors are clear.
- **Log domain (20):** Show Group (similar errors clustered), Spikes (volume vs baseline), Insights (summary) to demonstrate log-as-signal and metadata.
- **API design (15):** Collection shows clear request/response; body examples and descriptions document contracts.
- **Insights (10):** Demo Insights response and, if possible, LLM vs fallback to show actionable summary.
