# TFN SECTOR INTELLIGENCE — FULL IMPLEMENTATION GUIDE
## From Zero to Live Agents Running on a VPS

**Stack:** Python 3.11 · Claude API · openpyxl · Gmail API · cron  
**Target:** Ubuntu 22.04 VPS (DigitalOcean / Hetzner / AWS Lightsail)  
**Estimated setup time:** 3–4 hours  

---

## CAN YOU USE CLAUDE CODE TO BUILD THIS?

**Yes. Strongly recommended.**

Claude Code is Anthropic's terminal-based coding agent. You install it once, point it at your project folder, and it reads, writes, and runs your code autonomously. For this project it means:

- You describe each agent in plain English
- Claude Code writes the full Python files
- It installs dependencies, fixes errors, and runs tests
- You supervise, approve, and deploy

You are not writing code from scratch. You are directing an AI builder.

**What you need for Claude Code:**
- Node.js v18+ installed
- A Claude Pro, Max, or API account
- Your terminal

**Install Claude Code:**
```bash
npm install -g @anthropic-ai/claude-code
```

**Authenticate:**
```bash
claude
# Follow the browser login prompt
# Or set your API key:
export ANTHROPIC_API_KEY="sk-ant-..."
```

**How to use it for this project:**
```bash
cd ~/tfn-intelligence
claude
# Then describe what you want built (see Phase prompts below)
```

---

## PROJECT STRUCTURE

```
tfn-intelligence/
├── CLAUDE.md                  # Context file Claude Code reads automatically
├── config.py                  # All settings, sources, recipients
├── orchestrator.py            # Main controller
├── agents/
│   ├── __init__.py
│   ├── io_agent.py            # Fetch + Email
│   ├── summarizer_agent.py    # Claude API calls
│   └── excel_agent.py         # Workbook writer
├── data/
│   └── TFN_Export_Intelligence.xlsx
├── logs/
│   └── run_YYYY-MM-DD.log
├── credentials/
│   └── gmail_credentials.json # Gmail OAuth (you provide)
├── requirements.txt
└── .env                       # API keys (never commit this)
```

---

## PHASE 0 — LOCAL MACHINE PREREQUISITES

### Step 1: Install Python 3.11+
```bash
# Ubuntu / Debian
sudo apt update && sudo apt install python3.11 python3.11-venv python3-pip -y

# macOS
brew install python@3.11

# Verify
python3 --version
```

### Step 2: Create project and virtual environment
```bash
mkdir ~/tfn-intelligence && cd ~/tfn-intelligence
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Create requirements.txt
```text
anthropic>=0.25.0
requests>=2.31.0
beautifulsoup4>=4.12.0
feedparser>=6.0.10
openpyxl>=3.1.2
google-auth>=2.28.0
google-auth-oauthlib>=1.2.0
google-auth-httplib2>=0.2.0
google-api-python-client>=2.120.0
python-dotenv>=1.0.1
schedule>=1.2.1
lxml>=5.1.0
```

### Step 4: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 5: Create .env file
```bash
# .env — never commit this to git
ANTHROPIC_API_KEY=sk-ant-your-key-here
GMAIL_SENDER=youremail@gmail.com
RECIPIENT_1=recipient1@gmail.com
RECIPIENT_2=recipient2@gmail.com
RECIPIENT_3=recipient3@gmail.com
```

---

## PHASE 1 — CLAUDE CODE SETUP (WRITE THE AGENTS)

### Create CLAUDE.md first

This file tells Claude Code everything about your project. It reads it automatically every session.

```markdown
# CLAUDE.md

## Project: TFN Sector Intelligence Automation

## What this is
A Python agentic workflow that collects Kenyan export sector intelligence,
summarizes it using the Anthropic Claude API, writes it into an Excel workbook,
and emails it every Friday to 3 Gmail recipients.

## Architecture
- orchestrator.py — controls agent sequence, scheduling
- agents/io_agent.py — fetches web articles + sends Gmail
- agents/summarizer_agent.py — calls Claude API, returns structured rows
- agents/excel_agent.py — writes/deduplicates rows into openpyxl workbook

## Tech stack
- Python 3.11
- anthropic SDK (claude-sonnet-4-6 model)
- requests + BeautifulSoup4 for scraping
- feedparser for RSS
- openpyxl for Excel
- Google API Python client for Gmail
- python-dotenv for env vars
- schedule for cron-like scheduling

## Key rules
- All API keys come from .env via dotenv — never hardcode
- Every agent must log its actions
- Excel workbook path: data/TFN_Export_Intelligence.xlsx
- Deduplication: hash of sector+headline+date using hashlib md5
- Impact levels: High / Medium / Low only
- Claude API model: claude-sonnet-4-6

## Sectors (10 total)
Tea, Coffee, Flowers, Avocado, Apparel & Textiles,
Macadamia Nuts, French Beans & Snow Peas, Mangoes,
Leather & Leather Products, Transport & Logistics

## Commands
- python orchestrator.py --run-now    # single run
- python orchestrator.py --schedule   # start scheduler
- python orchestrator.py --test-email # test email only
```

---

### Claude Code Prompt — Agent 1: I/O Agent

Open Claude Code and paste this prompt:

```
Build agents/io_agent.py

This agent has two jobs:

JOB 1 — FETCH (called at start of every run)
- For each sector and its sources in config.py, fetch raw articles
- Use requests + BeautifulSoup for HTML pages
- Use feedparser for any RSS feeds
- Extract: title, body_text (first 800 chars), source_name, url, date
- Skip articles older than 3 days (compare to today's date)
- Skip if URL is unreachable — log the error and continue
- Return a list of raw article dicts

JOB 2 — DELIVER (called on Fridays after Excel is complete)
- Accept workbook_path as argument
- Check the file exists and is not empty
- Build a Gmail message with the workbook attached
- Use Gmail API with credentials from credentials/gmail_credentials.json
- Send to all 3 recipients from .env
- Retry once after 60 seconds if first send fails
- Log success or failure with timestamp

Use python-dotenv to load all env vars.
Write clear docstrings on every function.
Log every major action using Python's logging module.
```

---

### Claude Code Prompt — Agent 2: Summarizer Agent

```
Build agents/summarizer_agent.py

This agent receives a raw article dict and returns a structured intelligence row.

INPUT (one article at a time):
{
  "title": str,
  "body_text": str,
  "source_name": str,
  "url": str,
  "date": str,
  "expected_sector": str
}

PROCESS:
1. Build a prompt for the Claude API
2. Call claude-sonnet-4-6 via anthropic SDK
3. Parse the JSON response
4. Validate all required fields are present
5. If JSON is malformed, retry once
6. If retry fails, log and return None (caller skips it)

CLAUDE PROMPT TO USE:
"""
You are an export intelligence analyst focused on Kenyan exporters.
Read the article below and return ONLY a valid JSON object with no extra text.

Required fields:
- headline: short, factual headline (max 12 words)
- summary: exactly 2 sentences explaining what happened
- sector: one of [Tea, Coffee, Flowers, Avocado, Apparel & Textiles, 
  Macadamia Nuts, French Beans & Snow Peas, Mangoes, 
  Leather & Leather Products, Transport & Logistics]
- exporter_implication: one sentence on what this means for Kenyan exporters
- impact: one of [High, Medium, Low]

Impact rules:
- High: regulation change, ban, levy, market closure, urgent disruption
- Medium: price trend, forecast, planning signal, competitive shift
- Low: background context, slow-moving information

Article:
{article_text}
"""

OUTPUT:
{
  "headline": str,
  "summary": str,
  "sector": str,
  "exporter_implication": str,
  "impact": str,
  "source": str,
  "url": str,
  "date": str
}

Return None if processing fails after retry.
Load ANTHROPIC_API_KEY from .env
Log every API call and outcome.
```

---

### Claude Code Prompt — Agent 3: Excel Writer Agent

```
Build agents/excel_agent.py

This agent writes structured rows into the Excel workbook.

WORKBOOK: data/TFN_Export_Intelligence.xlsx
Create it if it does not exist.

SHEETS:
- Master sheet (all sectors combined)
- One tab per sector (10 tabs total):
  Tea, Coffee, Flowers, Avocado, Apparel & Textiles,
  Macadamia Nuts, French Beans & Snow Peas, Mangoes,
  Leather & Leather Products, Transport & Logistics

COLUMNS (same on all sheets):
Date | Sector | Headline | Summary | Exporter Implication | Impact | Source | URL

FORMATTING:
- Header row: bold, white text, dark blue fill (#1F4E79), row height 20
- Column widths: Date=12, Sector=18, Headline=30, Summary=45,
  Exporter Implication=40, Impact=10, Source=20, URL=40
- Impact color coding:
  High = light red fill (#FFCCCC)
  Medium = light orange fill (#FFE5CC)
  Low = light green fill (#CCFFCC)
- Freeze top row on all sheets
- Auto-filter on all sheets

DEDUPLICATION:
- Generate hash = md5(sector + headline + date)
- Before writing, scan all existing rows in Master sheet for matching hash
- If duplicate found: skip and log "Duplicate skipped: {headline}"
- If new: append to Master sheet AND the matching sector tab

FUNCTION SIGNATURES:
- write_row(row_dict) -> bool  (returns True if written, False if duplicate)
- get_row_count() -> int
- initialize_workbook() -> None  (called if file doesn't exist)

Save workbook after every successful write.
Log every write and every skip.
Use openpyxl. Load from .env if needed.
```

---

### Claude Code Prompt — Orchestrator

```
Build orchestrator.py

This is the main controller. It runs the full pipeline.

IMPORTS: all three agents, config, logging, schedule, argparse, dotenv

DAILY RUN SEQUENCE (run_daily()):
1. Log run start with timestamp
2. Call io_agent.fetch_all_articles() → list of raw articles
3. For each article:
   a. Call summarizer_agent.process(article) → structured row or None
   b. If row is not None: call excel_agent.write_row(row)
4. Log summary: articles fetched, rows written, duplicates skipped
5. If today is Friday: call io_agent.deliver_workbook(workbook_path)
6. Log run complete

SCHEDULER MODE (--schedule flag):
- Run daily at 07:00 EAT (East Africa Time = UTC+3)
- Use the schedule library
- Keep running in a loop

SINGLE RUN MODE (--run-now flag):
- Execute run_daily() once and exit

TEST EMAIL MODE (--test-email flag):
- Skip fetch and summarize
- Just call io_agent.deliver_workbook() with current workbook
- Useful for testing Gmail credentials

CLI:
python orchestrator.py --run-now
python orchestrator.py --schedule
python orchestrator.py --test-email

Load all env vars from .env at startup.
Set up logging to both console and logs/run_YYYY-MM-DD.log
Handle all exceptions gracefully — one agent failing must not crash the run.
```

---

### Claude Code Prompt — Config File

```
Build config.py

This file contains all configuration. No hardcoded values anywhere else.

SOURCES per sector — use these exact structures:

SECTOR_SOURCES = {
    "Tea": {
        "sources": [
            {"name": "Tea Board of Kenya", "url": "https://www.teaboard.or.ke", "type": "html"},
            {"name": "EATTA", "url": "https://www.eatta.com", "type": "html"},
            {"name": "Business Daily Tea", "url": "https://www.businessdailyafrica.com/bd/economy/tea", "type": "html"},
        ],
        "search_terms": ["Kenya tea auction", "Mombasa tea prices", "Kenya tea exports"]
    },
    "Coffee": {
        "sources": [
            {"name": "Coffee Directorate", "url": "https://www.coffeeboard.co.ke", "type": "html"},
            {"name": "Business Daily Coffee", "url": "https://www.businessdailyafrica.com/bd/economy/coffee", "type": "html"},
        ],
        "search_terms": ["Kenya coffee exports", "EUDR coffee Kenya", "Kenya coffee prices"]
    },
    "Flowers": {
        "sources": [
            {"name": "Kenya Flower Council", "url": "https://kenyaflowercouncil.org", "type": "html"},
            {"name": "Floral Daily", "url": "https://www.floraldaily.com/rss", "type": "rss"},
            {"name": "FreshPlaza", "url": "https://www.freshplaza.com/rss", "type": "rss"},
        ],
        "search_terms": ["Kenya flower exports", "flower freight Kenya"]
    },
    "Avocado": {
        "sources": [
            {"name": "AFA Horticulture", "url": "https://www.horticulture.or.ke", "type": "html"},
            {"name": "FreshPlaza Avocado", "url": "https://www.freshplaza.com/rss", "type": "rss"},
        ],
        "search_terms": ["Kenya avocado exports", "Kenya avocado China market"]
    },
    "Apparel & Textiles": {
        "sources": [
            {"name": "EPZA Kenya", "url": "https://www.epzakenya.com", "type": "html"},
            {"name": "Fibre2Fashion", "url": "https://www.fibre2fashion.com/rss-feed.asp", "type": "rss"},
        ],
        "search_terms": ["Kenya apparel exports", "AGOA Kenya textile"]
    },
    "Macadamia Nuts": {
        "sources": [
            {"name": "AFA Nuts", "url": "https://www.afa.go.ke", "type": "html"},
            {"name": "Business Daily Agri", "url": "https://www.businessdailyafrica.com/bd/economy/agriculture", "type": "html"},
        ],
        "search_terms": ["Kenya macadamia exports", "macadamia prices Kenya"]
    },
    "French Beans & Snow Peas": {
        "sources": [
            {"name": "KEPHIS", "url": "https://www.kephis.org", "type": "html"},
            {"name": "FreshPlaza", "url": "https://www.freshplaza.com/rss", "type": "rss"},
        ],
        "search_terms": ["Kenya french beans exports", "Kenya snow peas EU rules"]
    },
    "Mangoes": {
        "sources": [
            {"name": "KEPHIS Mangoes", "url": "https://www.kephis.org", "type": "html"},
            {"name": "AFA Fruit", "url": "https://www.horticulture.or.ke", "type": "html"},
        ],
        "search_terms": ["Kenya mango exports", "Kenya mango fruit fly"]
    },
    "Leather & Leather Products": {
        "sources": [
            {"name": "Kenya Leather Development Council", "url": "https://www.kldc.go.ke", "type": "html"},
            {"name": "Business Daily Trade", "url": "https://www.businessdailyafrica.com", "type": "html"},
        ],
        "search_terms": ["Kenya leather exports", "Kenya footwear exports"]
    },
    "Transport & Logistics": {
        "sources": [
            {"name": "Kenya Ports Authority", "url": "https://www.kpa.co.ke", "type": "html"},
            {"name": "The East African Logistics", "url": "https://www.theeastafrican.co.ke/tea/business/logistics", "type": "html"},
        ],
        "search_terms": ["Mombasa port delay", "KRA customs notice Kenya", "Kenya freight costs"]
    }
}

WORKBOOK_PATH = "data/TFN_Export_Intelligence.xlsx"
LOG_DIR = "logs"
CREDENTIALS_PATH = "credentials/gmail_credentials.json"
MODEL = "claude-sonnet-4-6"
MAX_ARTICLE_AGE_DAYS = 3
SEND_DAY = "Friday"
SEND_TIME = "07:00"
```

---

## PHASE 2 — GMAIL API SETUP

This is the only manual step that cannot be automated.

### Step 1: Create Gmail OAuth credentials
1. Go to https://console.cloud.google.com
2. Create a new project called `tfn-intelligence`
3. Enable the **Gmail API**
4. Go to **Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Application type: **Desktop App**
6. Download the JSON file
7. Save it as `credentials/gmail_credentials.json`

### Step 2: Authorize on first run
```bash
# First time only — opens browser for authorization
python orchestrator.py --test-email
```

This creates a `token.json` file. After this, Gmail works automatically with no browser needed.

### Step 3: Gmail App Password (simpler alternative)
If OAuth feels complex, use Gmail App Password instead:

1. Go to Google Account → Security → 2-Step Verification → App Passwords
2. Generate a password for "Mail"
3. Add to .env:
```bash
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

Tell Claude Code to use SMTP with App Password instead of OAuth when building io_agent.py.

---

## PHASE 3 — TEST LOCALLY

### Run once manually
```bash
source venv/bin/activate
python orchestrator.py --run-now
```

### Check the log
```bash
tail -f logs/run-$(date +%Y-%m-%d).log
```

### Check the Excel output
```bash
ls -lh data/TFN_Export_Intelligence.xlsx
```

### Test email delivery
```bash
python orchestrator.py --test-email
```

### Expected output on a clean run
```
[07:00:01] Orchestrator started
[07:00:01] Fetching articles for 10 sectors...
[07:00:08] I/O Agent: 34 articles collected
[07:00:08] Summarizer Agent: processing 34 articles...
[07:00:45] Summarizer Agent: 31 rows returned, 3 skipped
[07:00:45] Excel Agent: 28 rows written, 3 duplicates skipped
[07:00:46] Workbook saved: data/TFN_Export_Intelligence.xlsx
[07:00:46] Today is not Friday — skipping email delivery
[07:00:46] Run complete. Duration: 45s
```

---

## PHASE 4 — DEPLOY TO VPS (TAKE IT OFF LOCALHOST)

### Step 1: Provision a VPS

Recommended providers for Kenya/East Africa:
- **Hetzner** (cheapest, €4.15/month for CX11) — best value
- **DigitalOcean** ($6/month Droplet)
- **AWS Lightsail** ($3.50/month)

Minimum specs:
- 1 vCPU
- 1GB RAM
- 20GB SSD
- Ubuntu 22.04 LTS

### Step 2: Initial server setup
```bash
# SSH into your server
ssh root@YOUR_SERVER_IP

# Update system
apt update && apt upgrade -y

# Install Python and tools
apt install python3.11 python3.11-venv python3-pip git -y

# Create a non-root user
adduser tfnagent
usermod -aG sudo tfnagent
su - tfnagent
```

### Step 3: Upload your project
```bash
# From your LOCAL machine
scp -r ~/tfn-intelligence tfnagent@YOUR_SERVER_IP:~/

# OR use git (recommended)
# Push to a private GitHub repo first, then on server:
git clone https://github.com/youruser/tfn-intelligence.git
cd tfn-intelligence
```

### Step 4: Set up Python environment on server
```bash
cd ~/tfn-intelligence
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 5: Upload credentials and .env
```bash
# From your LOCAL machine — upload the sensitive files
scp .env tfnagent@YOUR_SERVER_IP:~/tfn-intelligence/
scp credentials/gmail_credentials.json tfnagent@YOUR_SERVER_IP:~/tfn-intelligence/credentials/
scp credentials/token.json tfnagent@YOUR_SERVER_IP:~/tfn-intelligence/credentials/
```

### Step 6: Test on server
```bash
# On server
source ~/tfn-intelligence/venv/bin/activate
cd ~/tfn-intelligence
python orchestrator.py --run-now
```

---

## PHASE 5 — SET UP AUTOMATIC SCHEDULING WITH CRON

This replaces localhost. The server runs the agents on schedule automatically.

### Option A: Cron (simplest)
```bash
# Open crontab editor
crontab -e

# Add this line (runs daily at 07:00 EAT = 04:00 UTC)
0 4 * * * /home/tfnagent/tfn-intelligence/venv/bin/python /home/tfnagent/tfn-intelligence/orchestrator.py --run-now >> /home/tfnagent/tfn-intelligence/logs/cron.log 2>&1
```

### Option B: systemd service (more robust — restarts on failure)

Create the service file:
```bash
sudo nano /etc/systemd/system/tfn-intelligence.service
```

Paste:
```ini
[Unit]
Description=TFN Sector Intelligence Agent
After=network.target

[Service]
Type=simple
User=tfnagent
WorkingDirectory=/home/tfnagent/tfn-intelligence
Environment=PATH=/home/tfnagent/tfn-intelligence/venv/bin
ExecStart=/home/tfnagent/tfn-intelligence/venv/bin/python orchestrator.py --schedule
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tfn-intelligence
sudo systemctl start tfn-intelligence

# Check status
sudo systemctl status tfn-intelligence

# Watch live logs
journalctl -u tfn-intelligence -f
```

**Recommended: Use systemd.** If the server reboots or the process crashes, it restarts automatically. Cron does not do this.

---

## PHASE 6 — MONITOR AND MAINTAIN

### Check if it's running
```bash
sudo systemctl status tfn-intelligence
```

### View today's log
```bash
tail -100 ~/tfn-intelligence/logs/run-$(date +%Y-%m-%d).log
```

### Check workbook row count
```bash
python3 -c "
import openpyxl
wb = openpyxl.load_workbook('data/TFN_Export_Intelligence.xlsx')
ws = wb['Master']
print(f'Total rows in Master: {ws.max_row - 1}')
"
```

### Force a manual run at any time
```bash
source ~/tfn-intelligence/venv/bin/activate
python orchestrator.py --run-now
```

### Force send email right now
```bash
python orchestrator.py --test-email
```

---

## USING CLAUDE CODE ON THE SERVER

You can install Claude Code on the VPS for ongoing maintenance:

```bash
# On the server
curl -sL claude.ai/install.sh | sh
export ANTHROPIC_API_KEY="sk-ant-..."

# Start Claude Code in project folder
cd ~/tfn-intelligence
claude
```

Then you can say things like:
- *"Add Reuters as a new source for the Coffee sector"*
- *"The KEPHIS website URL changed, update it in config.py"*
- *"Add a new column called Trade_Volume to the Excel sheet"*
- *"The summarizer is returning None too often, debug it"*

Claude Code reads CLAUDE.md and has full context of your project.

---

## COST SUMMARY — RUNNING ON VPS

| Item | Provider | Monthly Cost |
|------|----------|-------------|
| VPS (1GB RAM, Ubuntu) | Hetzner CX11 | ~KES 650 |
| Claude API (daily runs, 10 sectors) | Anthropic | KES 2,000–5,000 |
| Gmail API | Google | Free |
| **Total** | | **KES 2,650–5,650** |

### Controlling Claude API costs
- Model used: `claude-sonnet-4-6` (balanced cost/quality)
- Switch to `claude-haiku-4-5-20251001` to cut AI costs by ~80% if budget is tight
- Limit articles per sector to 5 max per run to cap token usage

Change model in config.py:
```python
MODEL = "claude-haiku-4-5-20251001"   # cheaper
MODEL = "claude-sonnet-4-6"            # recommended
```

---

## TROUBLESHOOTING

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| `ModuleNotFoundError` | venv not activated | `source venv/bin/activate` |
| `AuthenticationError` | Wrong API key | Check .env, recheck key at console.anthropic.com |
| Excel file corrupted | Write interrupted | Delete file, let agent recreate it |
| Gmail send fails | Token expired | Delete `credentials/token.json`, re-run `--test-email` |
| Source returns 0 articles | Site blocked bots | Add `User-Agent` header in io_agent.py |
| Duplicates filling up | Hash logic broken | Ask Claude Code to debug `excel_agent.generate_hash()` |
| Service not starting | Path wrong in systemd | Check `ExecStart` path matches your venv location |

---

## EXPANDING THE SYSTEM LATER

Once live, adding capacity is straightforward:

### Add a new sector
```
# Tell Claude Code:
"Add a new sector called Pyrethrum to config.py with sources:
AFA Pyrethrum Board at https://www.pyrethrum.or.ke
Search terms: Kenya pyrethrum exports, pyrethrum prices"
```

### Add a new recipient
```bash
# In .env, add:
RECIPIENT_4=newperson@gmail.com
# Then update io_agent.py to read RECIPIENT_4
```

### Add WhatsApp delivery
```
# Tell Claude Code:
"After the Friday email, also send a summary message via
WhatsApp Business API to +254XXXXXXXXX listing only the 
High impact items from this week's run"
```

### Add a weekly narrative summary tab
```
# Tell Claude Code:
"Every Friday, before emailing, add a new sheet called 
'Weekly Brief' to the workbook. Use the Claude API to write 
a 300-word executive narrative summarizing the week's 
High impact items across all sectors."
```

---

## GO-LIVE CHECKLIST

- [ ] `.env` file created with all keys and recipients
- [ ] `requirements.txt` installed in venv
- [ ] `config.py` built with all 10 sectors and sources
- [ ] `agents/io_agent.py` built and tested
- [ ] `agents/summarizer_agent.py` built and tested
- [ ] `agents/excel_agent.py` built and tested
- [ ] `orchestrator.py` built and tested
- [ ] Gmail credentials authorized (`token.json` exists)
- [ ] `python orchestrator.py --run-now` produces rows in Excel
- [ ] `python orchestrator.py --test-email` delivers to all 3 inboxes
- [ ] VPS provisioned (Ubuntu 22.04)
- [ ] Project uploaded to VPS
- [ ] systemd service created and enabled
- [ ] `sudo systemctl status tfn-intelligence` shows `active (running)`
- [ ] Confirmed Friday email arrives correctly
- [ ] Log files writing to `logs/` directory

---

*TFN Sector Intelligence — Implementation Guide v1.0 — May 2026*
