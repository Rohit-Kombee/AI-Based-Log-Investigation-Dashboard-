# AI Log Investigation Assistant

Log ingestion, normalization, validation, error grouping, spike detection, and LLM-powered insights.

---

## How to set up the project

1. **Clone or open the project** and go to the project folder:

   ```bash
   cd "C:\Users\Kombee\Desktop\Today Training"
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate   # macOS/Linux
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**

   Copy `.env.example` to `.env` and add your API key(s). For **OpenRouter** (recommended, one API for 300+ models):

   - Get a key: [https://openrouter.ai/settings/keys](https://openrouter.ai/settings/keys)
   - In `.env`: `OPENROUTER_API_KEY=sk-or-v1-...`

   See `.env.example` for all options (e.g. `OPENROUTER_MODEL`, `DATABASE_URL`).

---

## How to run the project

Start the API server:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 5000
```

- **API docs (Swagger):** [http://127.0.0.1:5000/docs](http://127.0.0.1:5000/docs)
- **Dashboard:** [http://127.0.0.1:5000/dashboard](http://127.0.0.1:5000/dashboard)
- **Generator:** [http://127.0.0.1:5000/generator](http://127.0.0.1:5000/generator)
- **Health:** [http://127.0.0.1:5000/health](http://127.0.0.1:5000/health)

> **Windows:** If you get `WinError 10013` on a port, try another (e.g. 5000 or 8080). Port 8000 is often reserved by Hyper-V.

---

## How the endpoints work

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ingest` | POST | Accept raw logs; normalize, validate, and store. Returns `accepted`, `rejected`, and `errors` per log. |
| `/normalize` | POST | Convert one raw log to canonical schema (e.g. `lvl`→`level`, `msg`→`message`). |
| `/validate` | POST | Validate a log; returns `valid` and list of `errors` if invalid. |
| `/group` | GET | Cluster similar errors by fingerprint. Query: `service`, `level`, `limit`, `since`. |
| `/spikes` | GET | Detect volume spikes per group (current vs baseline). Query: `window_minutes`, `ratio_threshold`, `service`, `level`. |
| `/insights` | GET | LLM-generated human-friendly summary of top groups and spikes. Query: `service`, `level`, `since`. Uses OpenRouter → Gemini → OpenAI if keys are set. |
| `/health` | GET | Health check; returns `{"status": "ok"}`. |
| `/stats` | GET | Dashboard data: `total_logs`, `total_groups`, `total_rejected`, `spikes_count`, `recent_ingests`. |
| `/api/logs` | GET | Last N logs (for dashboard drill-down). Query: `limit`. |
| `/api/groups` | GET | First N error groups (for dashboard). Query: `limit`. |
| `/api/spikes` | GET | First N spikes (for dashboard). Query: `limit`. |
| `/api/rejected` | GET | Last N rejected log entries (for dashboard). Query: `limit`. |
| `/dashboard` | GET | Serves the log dashboard HTML page. |
| `/generator` | GET | Serves the generator HTML page. |
| `/generator/send` | POST | Run a generator scenario: send batches of logs to ingest. Body: `scenario`, `batches`, `batch_size`. |


## Dashboard

The **Dashboard** ([http://127.0.0.1:5000/dashboard](http://127.0.0.1:5000/dashboard)) shows:

- **Summary cards:** Total logs, total groups, total rejected, spikes count.
- **Clickable cards** that load the corresponding data (e.g. recent logs, top groups, spikes, rejected entries).
- **LLM insights** summary (when an API key is configured).
- **Tables** (up to 10 rows each) for recent logs, groups, spikes, and rejected logs.

<img width="1908" height="909" alt="image" src="https://github.com/user-attachments/assets/0103a0ce-b2a5-4f71-940c-2788753ea9de" />

---

## Generator

The **Generator** ([http://127.0.0.1:5000/generator](http://127.0.0.1:5000/generator)) lets you:


- **Choose a scenario** from a dropdown: Normal, Error spike, Malformed, Alternate fields, or Mixed.
- **Set batches and batch size** and click **Send** to push log batches to the ingest API.
- See **results** (accepted/rejected counts) and then check the **Dashboard** for the new data.

<img width="1903" height="907" alt="image" src="https://github.com/user-attachments/assets/19e53d3b-8afe-448c-8816-e8fe26cf5ff1" />

---

## Postman collection

A Postman collection is included to call all main APIs.

**Location:** `postman/AI_Log_Investigation_Assistant.postman_collection.json`

**Import in Postman:**

1. Open Postman → **Import** → select `AI_Log_Investigation_Assistant.postman_collection.json`.
2. Set the collection variable **`base_url`** to your server (default: `http://127.0.0.1:5000`).  
   (Collection → Variables → `base_url`.)

**Suggested run order:** Health → Ingest (valid + edge cases) → Normalize → Validate → Group → Spikes → Insights.

More detail and expected responses: see `postman/README.md`.

---

## Run the log generator (CLI)

In a **second terminal** (with the API running), you can also generate logs from the command line:

```bash
.venv\Scripts\activate
# If not using port 5000, set: $env:INGEST_URL="http://127.0.0.1:5000/ingest"   # PowerShell

python -m generator.main -n 20 -b 5
python -m generator.main --error-spike -n 10
python -m generator.main --malformed 0.2 -n 10
```

---

## Project layout

```
app/
  main.py          # FastAPI app, routes
  config.py        # Settings (OpenRouter, Gemini, OpenAI, DB)
  schema.py        # Canonical log + request/response models
  db.py            # SQLite connection, init
  normalize.py     # Raw → canonical
  validate.py      # Validation rules
  fingerprint.py   # Grouping fingerprint
  ingest.py        # Ingest pipeline
  group.py         # /group
  spikes.py        # /spikes
  insights.py      # /insights (OpenRouter / Gemini / OpenAI)
  generator_service.py  # Generator scenarios for /generator/send
static/
  dashboard.html   # Dashboard UI
  generator.html   # Generator UI
generator/
  main.py          # CLI log generator script
postman/
  AI_Log_Investigation_Assistant.postman_collection.json
  README.md
```

---

## Team

Rohit Sahu, Bhargav Bhutwala, Sam Wesley — AI Log Investigation Assistant





