# SynXis Rate Automation

A CLI tool that replaces manual rate updates in SynXis Control Center's Daily Manager with a two-step Excel-based workflow: export current rates, edit the ones that need to change, push them back — with built-in safety checks at every step.

Built by reverse-engineering SynXis's internal `GetRates`/`Save` API endpoints (via browser DevTools network capture), since SynXis has no public API for this.

## Who can run this

This isn't a plug-and-play tool for any hotel — it talks to one specific SynXis account's rate plans and room types, which are configured via captured API payloads (see Setup). You need your own SynXis Control Center login and to capture your own session values and payload templates before this will do anything useful.

## How it works

**1. Export** — Pulls current rates for a date range into a formatted Excel file, with a blank yellow "New Rate" column for you to fill in.

**2. You edit the Excel** — Type new rates only in the rows that need to change. Leave everything else blank.

**3. Push** — Reads the edited Excel, and for every filled-in row:
   - Re-fetches the *live* rate from SynXis and compares it to what was originally exported — if it's changed since export (someone else edited it, or the grid moved), that row is skipped rather than silently overwritten
   - Pushes all remaining changes in batched Save requests
   - Re-fetches everything again afterward to confirm each value actually landed correctly

## Setup

```bash
git clone https://github.com/Ansar-haque-107/synxis-rate-automation.git
cd synxis-rate-automation
pip install -r requirements.txt
cp .env.example .env
```

Then fill in `.env` with your own session values:

1. Log into SynXis Control Center, open the Daily Manager rate grid
2. Open DevTools (F12) → Network tab → refresh the grid
3. Click any `HMS/manager` request (e.g. `GetRates`) → Headers → Request Headers
4. Copy the `cookie` value and the `x-requestverificationtoken` value into `.env`

These expire — you'll need to repeat this each time you run the tool.

For your own rate plans/rooms, capture a full `GetRates` payload the same way and add it to `GETRATES_PAYLOAD_TEMPLATES` in `synxis/config.py`.

## Usage

```bash
python main.py export    # pulls current rates into Excel
# ...edit the yellow "New Rate" column, save the file...
python main.py push      # pushes changes, with safety checks
```

`DRY_RUN = True` in `synxis/config.py` by default — it prints exactly what would be sent without touching SynXis. Flip to `False` once you've reviewed the dry-run output.

## Tech stack

Python, `requests` (session replay), `pandas` + `openpyxl` (Excel I/O), `python-dotenv` (config)

## Why these design choices

- **Excel as the interface** — revenue teams already work in spreadsheets; this avoids building a UI for something that only needs review-and-edit.
- **Pre-push cross-check against live data** — SynXis rate grids can change between export and push. Without this check, a push could silently overwrite a rate you never meant to touch.
- **Post-save verification** — a "Success" response doesn't guarantee the values landed exactly right; explicitly re-fetching closes that gap.
