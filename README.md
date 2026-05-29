# TFN Sector Intelligence Automation

An agentic Python workflow that collects Kenyan export-sector news, summarizes it
into structured intelligence using LLMs, records it in an Excel workbook, and emails
the workbook to recipients every **Friday**.

The pipeline runs daily: it fetches and summarizes new articles every day (building up
the workbook and de-duplicating), and only sends the email on Fridays.

---

## How it works

```
orchestrator.py
   │
   ├─ 1. io_agent.fetch_all_articles()      Gemini Google-Search grounding (DuckDuckGo fallback)
   │
   ├─ 2. summarizer_agent.process(article)  LLM → structured JSON (Gemini, Groq fallback)
   │
   ├─ 3. excel_agent.write_row(row)         openpyxl, de-duped by MD5(url)
   │
   └─ 4. io_agent.deliver_workbook()        Gmail SMTP — only on Friday
```

### Sectors covered (10)
Tea · Coffee · Flowers · Avocado · Apparel & Textiles · Macadamia Nuts ·
French Beans & Snow Peas · Mangoes · Leather & Leather Products · Transport & Logistics

### Tech stack
- Python 3.11
- `google-genai` (Gemini 2.5 Flash) with Google-Search grounding — primary fetch + summarization
- `groq` (Llama 3.3 70B) — summarization fallback on rate-limit
- `ddgs` — search fallback when Gemini is rate-limited
- `trafilatura` / `feedparser` — article extraction
- `openpyxl` — Excel output
- `smtplib` + Gmail App Password — delivery
- `schedule` — daily scheduler

---

## Prerequisites

- Python 3.11+
- A **Gemini API key** — https://aistudio.google.com/apikey
- A **Groq API key** (fallback) — https://console.groq.com/keys
- A **Gmail account** with 2FA enabled and an **App Password** — https://myaccount.google.com/apppasswords

---

## Quick start (local)

```bash
git clone git@github.com:davidzeck/TFN-Research-Agent.git
cd TFN-Research-Agent/tfn-intelligence

# 1. Create & activate a virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure secrets
cp .env.example .env
#    then edit .env and fill in your real keys / emails

# 4. Verify email delivery works (sends the current workbook)
python orchestrator.py --test-email

# 5. Run the full pipeline once
python orchestrator.py --run-now
```

### Commands

| Command | What it does |
|---|---|
| `python orchestrator.py --run-now` | One full pipeline run (fetch → summarize → write → deliver if Friday), then exit |
| `python orchestrator.py --schedule` | Run forever; executes daily at **07:00 EAT (Africa/Nairobi)**, regardless of host timezone. Use on the server. |
| `python orchestrator.py --test-email` | Send the current workbook only — for testing Gmail credentials |

### Environment variables (`.env`)

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | yes | Primary fetch + summarization |
| `GROQ_API_KEY` | yes | Summarization fallback |
| `GMAIL_SENDER` | yes | Gmail address that sends the report |
| `GMAIL_APP_PASSWORD` | yes | Gmail App Password (not your login password) |
| `RECIPIENT_1` / `RECIPIENT_2` | yes | Report recipients |
| `RECIPIENT_3` | no | Optional third recipient |

Outputs land in `data/TFN_Export_Intelligence.xlsx`; daily logs in `logs/run-YYYY-MM-DD.log`.

---

## Deployment (Linux server / VPS)

The recommended setup runs the scheduler continuously under **systemd**, so it
survives reboots and restarts on failure. The scheduler runs the pipeline daily
at 07:00 EAT and emails the workbook on Fridays.

### 1. Provision the server

```bash
# On the server (Ubuntu/Debian)
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
```

### 2. Clone and set up

```bash
sudo mkdir -p /opt/tfn && sudo chown "$USER" /opt/tfn
cd /opt/tfn
git clone git@github.com:davidzeck/TFN-Research-Agent.git .
cd tfn-intelligence

python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
```

### 3. Configure secrets on the server

```bash
cp .env.example .env
nano .env        # fill in real keys / emails — this file is gitignored
```

### 4. Smoke-test before enabling the service

```bash
./venv/bin/python orchestrator.py --test-email   # confirm email works
./venv/bin/python orchestrator.py --run-now      # confirm full pipeline works
```

### 5. Create the systemd service

Create `/etc/systemd/system/tfn-intelligence.service`:

```ini
[Unit]
Description=TFN Sector Intelligence daily scheduler
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=YOUR_LINUX_USER
WorkingDirectory=/opt/tfn/tfn-intelligence
ExecStart=/opt/tfn/tfn-intelligence/venv/bin/python orchestrator.py --schedule
Restart=on-failure
RestartSec=30
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

> Replace `YOUR_LINUX_USER` with the account that owns `/opt/tfn`.
> `WorkingDirectory` must point at `tfn-intelligence/` because the app uses
> relative paths for `data/` and `logs/`.

### 6. Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tfn-intelligence.service
```

### 7. Verify it's running

```bash
sudo systemctl status tfn-intelligence.service     # should be "active (running)"
journalctl -u tfn-intelligence.service -f          # live logs
```

The scheduler logs "Scheduler started…" on boot, then fires once daily at
07:00 EAT. If the service is (re)started after 07:00 EAT on a day it hasn't yet
run, it runs immediately (missed-run recovery). A per-day sentinel in `logs/`
makes runs idempotent, so a restart never sends a duplicate report.

### Operations

```bash
# After pulling new code
cd /opt/tfn && git pull
./tfn-intelligence/venv/bin/pip install -r tfn-intelligence/requirements.txt   # if deps changed
sudo systemctl restart tfn-intelligence.service

# Tail today's app log (separate from journald)
tail -f /opt/tfn/tfn-intelligence/logs/run-$(date +%F).log
```

### What must keep running
- **`tfn-intelligence.service`** — the only long-lived process. It owns the daily
  schedule and Friday delivery. If it's stopped, no reports go out.
- No database, message broker, or web server is required.

### Timezone note
The scheduler is anchored to the **Africa/Nairobi** timezone in code, so it
fires at 07:00 EAT on any host regardless of the server's local timezone.
No `timedatectl` change is needed. (Requires OS tzdata, present by default on
Ubuntu/Debian; install `tzdata` if running a minimal container image.)

---

## Security
- `.env`, `credentials/`, `data/`, and `logs/` are gitignored — **never commit secrets**.
- Use a Gmail **App Password**, not your account password.
- Restrict `.env` permissions on the server: `chmod 600 .env`.
