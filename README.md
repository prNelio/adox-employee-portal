# Adox Employee Portal

A secure internal portal for **Adox Service LTD** (currency exchange). Replaces paper-based workflows with a simple, multilingual web app.

## Features
- Employee/Admin login
- GBP/EUR transaction entry (date/time, client, recipient, bank, Kz)
- Calculator (GBP/EUR → Kz)
- Reports with totals, delete row, CSV export
- Backups: save, load, reset totals (creates backup)
- EN/PT language toggle
- Universal Back button on all inner pages

## Tech Stack
- **Backend:** Python (Flask, Werkzeug)
- **DB:** SQLite3
- **Frontend:** HTML, CSS, Jinja2 templates
- **Deploy:** PythonAnywhere

## Run locally
```bash
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:5000
