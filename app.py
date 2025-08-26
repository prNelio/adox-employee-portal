# Adox Employee Portal – Flask + SQLite (with universal Back button)
# -----------------------------------------------------------------
# Features:
# - Login (admin + 4 employees)
# - Record GBP/EUR transactions
# - Calculator (GBP/EUR → Kz)
# - Reports with totals, delete, CSV export
# - Backups: save, load, reset totals (with backup)
# - EN/PT language toggle
# - Back button on all inner pages

import os, sqlite3, secrets, json, io, csv
from datetime import datetime
from flask import (
    Flask, g, session, request, redirect, url_for,
    render_template_string, flash, send_file, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

APP_SECRET = os.environ.get("ADOX_SECRET", secrets.token_hex(16))
DB_PATH = os.environ.get("ADOX_DB", "adox.db")

app = Flask(__name__)
app.config.update(SECRET_KEY=APP_SECRET)

# ---------------- DB helpers ----------------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop('db', None)
    if db: db.close()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','employee'))
);
CREATE TABLE IF NOT EXISTS transactions(
  id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  date TEXT NOT NULL,
  time TEXT NOT NULL,
  client TEXT NOT NULL,
  origin TEXT,
  currency TEXT NOT NULL CHECK(currency in ('GBP','EUR')),
  amount REAL NOT NULL,
  recipient TEXT NOT NULL,
  bank TEXT,
  kz INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS backups(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(user_id,name),
  FOREIGN KEY(user_id) REFERENCES users(id)
);
"""

SEED_USERS = [
    ("admin","Admin123!","admin"),
    ("ana","Adox123!","employee"),
    ("domingas","Adox123!","employee"),
    ("nelio","Adox123!","employee"),
    ("staff4","Adox123!","employee"),
]

def init_db():
    db = get_db()
    for stmt in SCHEMA.split(";"):
        if stmt.strip(): db.execute(stmt)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        for u,p,r in SEED_USERS:
            db.execute("INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",
                       (u, generate_password_hash(p), r))
        db.commit()

@app.before_request
def before():
    init_db()
    session.setdefault("lang", "en")

# ---------------- i18n ----------------
STRINGS = {
  "en": {
    "title":"Adox – Employee Portal","loginTitle":"Sign in","username":"Username","password":"Password",
    "signIn":"Sign in","signOut":"Sign out","as":"as",
    "welcomeTitle":"Welcome 👋",
    "welcomeCopy":"Use the big buttons below to record transactions, calculate exchange amounts, and print simple receipts. Designed for ease of use.",
    "btnGbp":"Record Transaction (GBP)","btnEur":"Record Transaction (EUR)","btnCalc":"Exchange Rate Calculator",
    "btnReports":"Reports","btnBackups":"Saved Backups","btnHelp":"Help",
    "gbpTitle":"Record Transaction – GBP","eurTitle":"Record Transaction – EUR",
    "txTip":"Tip: Fill the form top-to-bottom. Fields marked * are required.",
    "lblDate":"Date *","lblTime":"Time *","lblClient":"Client name *","lblOrigin":"Client origin country",
    "lblAmountGbp":"Amount received (GBP) *","lblAmountEur":"Amount received (EUR) *",
    "lblRecipient":"Who should receive the money *","lblBank":"Recipient bank","lblKz":"Amount sent (AOA/Kz) *",
    "btnSubmit":"Submit Transaction","btnClear":"Clear","btnReceipt":"Print Receipt",
    "calcTitle":"Exchange Rate Calculator","btnCalcNow":"Calculate",
    "reportsTitle":"Reports","sumGbp":"Total GBP received","sumEur":"Total EUR received","sumKz":"Total Kz sent",
    "btnExport":"Export CSV","btnReset":"Reset Totals (with backup)",
    "thDate":"Date","thTime":"Time","thClient":"Client","thCurrency":"Currency","thAmount":"Amount",
    "thRecipient":"Recipient","thKz":"Kz Sent","thDelete":"Delete",
    "backupsTitle":"Saved Backups","lblBackupName":"Backup name","btnSaveBackup":"Save current data",
    "btnLoadBackup":"Load selected","lblBackups":"Existing backups",
    "helpTitle":"Help","help1":"Click a big button to open a task (e.g., Record GBP).",
    "help2":"Fill the form from the top to the bottom.","help3":"Press “Submit Transaction” to save. Go to Reports to view totals.",
    "help4":"Use EN/PT to switch language.","help5":"Use Export CSV to share with accounting."
  },
  "pt": {
    "title":"Adox – Portal do Colaborador","loginTitle":"Entrar","username":"Utilizador","password":"Palavra-passe",
    "signIn":"Entrar","signOut":"Sair","as":"como",
    "welcomeTitle":"Bem-vindo 👋",
    "welcomeCopy":"Use os botões grandes para registar transações, calcular montantes e imprimir recibos simples. Feito para ser fácil.",
    "btnGbp":"Registar Transação (GBP)","btnEur":"Registar Transação (EUR)","btnCalc":"Calculadora de Câmbio",
    "btnReports":"Relatórios","btnBackups":"Cópias Guardadas","btnHelp":"Ajuda",
    "gbpTitle":"Registar Transação – GBP","eurTitle":"Registar Transação – EUR",
    "txTip":"Dica: Preencha o formulário de cima para baixo. Campos * são obrigatórios.",
    "lblDate":"Data *","lblTime":"Hora *","lblClient":"Nome do cliente *","lblOrigin":"País de origem do cliente",
    "lblAmountGbp":"Montante recebido (GBP) *","lblAmountEur":"Montante recebido (EUR) *",
    "lblRecipient":"Quem deve receber o dinheiro *","lblBank":"Banco do destinatário","lblKz":"Montante enviado (AOA/Kz) *",
    "btnSubmit":"Submeter Transação","btnClear":"Limpar","btnReceipt":"Imprimir Recibo",
    "calcTitle":"Calculadora de Câmbio","btnCalcNow":"Calcular",
    "reportsTitle":"Relatórios","sumGbp":"Total GBP recebido","sumEur":"Total EUR recebido","sumKz":"Total Kz enviado",
    "btnExport":"Exportar CSV","btnReset":"Repor Totais (com cópia)",
    "thDate":"Data","thTime":"Hora","thClient":"Cliente","thCurrency":"Moeda","thAmount":"Montante",
    "thRecipient":"Destinatário","thKz":"Kz Enviado","thDelete":"Apagar",
    "backupsTitle":"Cópias Guardadas","lblBackupName":"Nome da cópia","btnSaveBackup":"Guardar dados atuais",
    "btnLoadBackup":"Carregar selecionado","lblBackups":"Cópias existentes",
    "helpTitle":"Ajuda","help1":"Clique num botão grande para abrir a tarefa (ex.: Registar GBP).",
    "help2":"Preencha o formulário de cima para baixo.","help3":"Carregue em “Submeter Transação” para guardar. Veja os totais em Relatórios.",
    "help4":"Use EN/PT para mudar o idioma.","help5":"Use Exportar CSV para a contabilidade."
  }
}
def t(k): return STRINGS[session.get("lang","en")].get(k,k)

# ---------------- Auth helpers ----------------
def current_user():
    uid = session.get("uid")
    if not uid: return None
    return get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

def login_required(fn):
    def inner(*args, **kwargs):
        if not current_user(): return redirect(url_for("login"))
        return fn(*args, **kwargs)
    inner.__name__ = fn.__name__
    return inner

# ---------------- Layout + renderer ----------------
BASE_HTML = """
<!doctype html>
<html lang="{{ 'pt' if session.get('lang')=='pt' else 'en' }}">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{{ t('title') }}</title>
  <style>
    body{font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;max-width:1100px;margin:0 auto;padding:16px 16px 64px;background:#f7f7fb;color:#1f2937}
    header{position:sticky;top:0;background:#fff;border-bottom:1px solid #e5e7eb;margin:0 -16px 16px;padding:12px 16px}
    .btn{display:inline-block;padding:12px 16px;border-radius:12px;background:#0B5ED7;color:#fff;text-decoration:none;border:none;cursor:pointer;font-weight:600}
    .btn:hover{filter:brightness(1.05)}
    .btn.ghost{background:#fff;color:#0B5ED7;border:1px solid #0B5ED7}
    .row{margin:.5rem 0}
    .field label{display:block;font-weight:600;margin-bottom:4px}
    .field input, .field select{width:320px;max-width:100%;padding:10px 12px;border:1px solid #d1d5db;border-radius:10px}
    .card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:16px;margin-bottom:16px}
    table{width:100%;border-collapse:collapse} th,td{border-bottom:1px solid #eee;padding:8px;text-align:left}
    .muted{color:#6b7280}
    .actions .btn{margin:.25rem}
  </style>
</head>
<body>
  <header>
    <div style="display:flex;justify-content:space-between;align-items:center;gap:12px">
      <h1 style="margin:0">{{ t('title') }}</h1>
      <div style="display:flex;gap:8px;align-items:center">
        {% if user %}<span class="muted">{{ user['username'] }} ({{ user['role'] }})</span>
        <a class="btn ghost" href="/logout">{{ t('signOut') }}</a>{% endif %}
        <a class="btn ghost" href="/lang/en">EN</a>
        <a class="btn ghost" href="/lang/pt">PT</a>
      </div>
    </div>
  </header>

  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      {% for cat,msg in messages %}
        <div class="card" style="border-color: {{ 'green' if cat=='ok' else '#ffd1d6' }};">{{ msg }}</div>
      {% endfor %}
    {% endif %}
  {% endwith %}

  {{ body|safe }}
</body>
</html>
"""

def render_page(body_tpl: str, show_back: bool = True, **ctx):
    """Render body first (so inner {{ }} works), then drop into base layout.
       show_back=False for login and home."""
    inner = render_template_string(body_tpl, **ctx, t=t, user=current_user())
    if show_back:
        inner += """<p><a class="btn ghost" href="/">⬅ Back</a></p>"""
    return render_template_string(BASE_HTML, body=inner, t=t, user=current_user())

# ---------------- Routes ----------------
@app.get("/lang/<lang>")
def set_lang(lang):
    session["lang"] = "pt" if lang=="pt" else "en"
    return redirect(request.referrer or url_for("index"))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        row = get_db().execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        if row and check_password_hash(row["password_hash"], p):
            session["uid"] = row["id"]
            flash(f"{t('signIn')} {t('as')} {row['username']}", "ok")
            return redirect(url_for("index"))
        flash("Invalid credentials", "err")

    body = """
    <section class="card">
      <h2>{{ t('loginTitle') }}</h2>
      <form method="post">
        <div class="row field"><label>{{ t('username') }}</label><input name="username" required placeholder="e.g., nelio"></div>
        <div class="row field"><label>{{ t('password') }}</label><input name="password" type="password" required></div>
        <p><button class="btn">{{ t('signIn') }}</button></p>
      </form>
      <p class="muted">admin/Admin123! • ana/Adox123! • domingas/Adox123! • nelio/Adox123! • staff4/Adox123!</p>
    </section>
    """
    return render_page(body, show_back=False)

@app.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.get("/")
@login_required
def index():
    body = """
    <section class="card">
      <h2>{{ t('welcomeTitle') }}</h2>
      <p class="muted">{{ t('welcomeCopy') }}</p>
    </section>
    <section class="card actions">
      <a class="btn" href="/tx/GBP">💷 {{ t('btnGbp') }}</a>
      <a class="btn" href="/tx/EUR">💶 {{ t('btnEur') }}</a>
      <a class="btn" href="/calc">🧮 {{ t('btnCalc') }}</a>
      <a class="btn" href="/reports">📊 {{ t('btnReports') }}</a>
      <a class="btn" href="/backups">💾 {{ t('btnBackups') }}</a>
      <a class="btn" href="/help">❓ {{ t('btnHelp') }}</a>
    </section>
    """
    return render_page(body, show_back=False)

@app.get("/tx/<currency>")
@login_required
def tx_page(currency):
    if currency not in ("GBP","EUR"): abort(404)
    body = """
    <section class="card">
      <h2>{{ title }}</h2>
      <p class="muted">{{ t('txTip') }}</p>
      <form method="post" action="/tx/{{ currency }}">
        <div class="row field"><label>{{ t('lblDate') }}</label><input type="date" name="date" required></div>
        <div class="row field"><label>{{ t('lblTime') }}</label><input type="time" name="time" required></div>
        <div class="row field"><label>{{ t('lblClient') }}</label><input name="client" required placeholder="e.g., Ana Silva"></div>
        <div class="row field"><label>{{ t('lblOrigin') }}</label><input name="origin" placeholder="e.g., UK"></div>
        <div class="row field"><label>{{ t('lblRecipient') }}</label><input name="recipient" required placeholder="Recipient full name"></div>
        <div class="row field"><label>{{ t('lblBank') }}</label><input name="bank" placeholder="e.g., BAI"></div>
        <div class="row field"><label>{{ amount_label }}</label><input type="number" step="0.01" name="amount" required></div>
        <div class="row field"><label>{{ t('lblKz') }}</label><input type="number" step="1" name="kz" required></div>
        <p>
          <button class="btn">{{ t('btnSubmit') }}</button>
          <a class="btn ghost" href="/tx/{{ currency }}">{{ t('btnClear') }}</a>
          <a class="btn ghost" target="_blank" href="/receipt/{{ currency }}">{{ t('btnReceipt') }}</a>
        </p>
      </form>
    </section>
    """
    return render_page(
        body, currency=currency,
        title=t('gbpTitle') if currency=='GBP' else t('eurTitle'),
        amount_label=t('lblAmountGbp') if currency=='GBP' else t('lblAmountEur')
    )

@app.post("/tx/<currency>")
@login_required
def save_tx(currency):
    if currency not in ("GBP","EUR"): abort(404)
    d = request.form
    required_ok = all(d.get(k) for k in ("date","time","client","recipient","amount","kz"))
    if not required_ok:
        flash("Please fill the required fields", "err")
        return redirect(url_for("tx_page", currency=currency))
    db = get_db()
    db.execute("""INSERT INTO transactions
      (id,user_id,date,time,client,origin,currency,amount,recipient,bank,kz,created_at)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
      (secrets.token_hex(8), current_user()["id"], d["date"], d["time"],
       d["client"].strip(), (d.get("origin") or "").strip(), currency,
       float(d["amount"] or 0), d["recipient"].strip(), (d.get("bank") or "").strip(),
       int(float(d["kz"] or 0)), datetime.utcnow().isoformat())
    )
    db.commit()
    flash("Transaction saved", "ok")
    return redirect(url_for("tx_page", currency=currency))

@app.get("/receipt/<currency>")
@login_required
def print_receipt(currency):
    if currency not in ("GBP","EUR"): abort(404)
    now = datetime.now()
    body = """
    <section class="card">
      <pre style="font:16px/1.4 monospace">Adox – Receipt
Date: {{ date }}  Time: {{ time }}
Currency: {{ currency }}
(Use Reports to view full details.)</pre>
      <button class="btn" onclick="window.print()">Print</button>
    </section>
    """
    return render_page(body, date=now.strftime("%Y-%m-%d"), time=now.strftime("%H:%M"), currency=currency)

@app.route("/calc", methods=["GET","POST"])
@login_required
def calc_page():
    result = None
    if request.method == "POST":
        amount = float(request.form.get("amount") or 0)
        currency = request.form.get("currency","GBP")
        rate = float(request.form.get("rate") or 0)
        if amount and rate:
            kz = round(amount * rate)
            result = f"{amount:,.2f} {currency} ≈ {kz:,} Kz"
        else:
            result = "Enter amount and rate."
    body = """
    <section class="card">
      <h2>{{ t('calcTitle') }}</h2>
      <form method="post">
        <div class="row field"><label>Amount</label><input name="amount" type="number" step="0.01" required></div>
        <div class="row field"><label>Currency</label>
          <select name="currency"><option>GBP</option><option>EUR</option></select>
        </div>
        <div class="row field"><label>Rate</label><input name="rate" type="number" step="0.0001" placeholder="e.g., 1650" required></div>
        <p><button class="btn">{{ t('btnCalcNow') }}</button></p>
      </form>
      {% if result %}<div class="card"><b>{{ result }}</b></div>{% endif %}
    </section>
    """
    return render_page(body, result=result)

@app.get("/reports")
@login_required
def reports_page():
    user = current_user()
    db = get_db()
    if user["role"] == "admin":
        rows = db.execute("""
          SELECT t.*, u.username FROM transactions t
          JOIN users u ON u.id=t.user_id
          ORDER BY date DESC, time DESC
        """).fetchall()
    else:
        rows = db.execute("""
          SELECT t.*, u.username FROM transactions t
          JOIN users u ON u.id=t.user_id
          WHERE t.user_id=?
          ORDER BY date DESC, time DESC
        """, (user["id"],)).fetchall()
    sumGBP = sum(r["amount"] for r in rows if r["currency"]=="GBP")
    sumEUR = sum(r["amount"] for r in rows if r["currency"]=="EUR")
    sumKZ  = sum(r["kz"] for r in rows)

    body = """
    <section class="card">
      <h2>{{ t('reportsTitle') }}</h2>
      <p class="muted">{{ t('sumGbp') }}: <b>{{ sumGBP }}</b> &nbsp; • &nbsp;
         {{ t('sumEur') }}: <b>{{ sumEUR }}</b> &nbsp; • &nbsp;
         {{ t('sumKz') }}: <b>{{ sumKZ }}</b></p>
      <p>
        <a class="btn" href="/export.csv">{{ t('btnExport') }}</a>
        <a class="btn ghost" href="/reset-totals">{{ t('btnReset') }}</a>
      </p>
      <div style="overflow:auto">
        <table>
          <thead>
            <tr>
              <th>{{ t('thDate') }}</th><th>{{ t('thTime') }}</th><th>{{ t('thClient') }}</th>
              <th>{{ t('thCurrency') }}</th><th>{{ t('thAmount') }}</th>
              <th>{{ t('thRecipient') }}</th><th>{{ t('thKz') }}</th><th>{{ t('thDelete') }}</th>
            </tr>
          </thead>
          <tbody>
          {% for r in rows %}
            <tr>
              <td>{{ r['date'] }}</td><td>{{ r['time'] }}</td><td>{{ r['client'] }}</td>
              <td>{{ r['currency'] }}</td><td>{{ '%.2f'|format(r['amount']) }}</td>
              <td>{{ r['recipient'] }}</td><td>{{ r['kz'] }}</td>
              <td><a class="btn ghost" href="/tx/delete/{{ r['id'] }}">✖</a></td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </section>
    """
    return render_page(
        body, rows=rows,
        sumGBP=f"{sumGBP:,.2f}", sumEUR=f"{sumEUR:,.2f}", sumKZ=f"{sumKZ:,}"
    )

@app.get("/tx/delete/<tx_id>")
@login_required
def del_tx(tx_id):
    user = current_user()
    db = get_db()
    if user["role"] == "admin":
        db.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
    else:
        db.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (tx_id, user["id"]))
    db.commit()
    flash("Deleted", "ok")
    return redirect(url_for("reports_page"))

@app.get("/export.csv")
@login_required
def export_csv():
    user = current_user()
    db = get_db()
    if user["role"] == "admin":
        rows = db.execute("SELECT t.*, u.username FROM transactions t JOIN users u ON u.id=t.user_id").fetchall()
    else:
        rows = db.execute("SELECT t.*, u.username FROM transactions t JOIN users u ON u.id=t.user_id WHERE t.user_id=?", (user["id"],)).fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Date","Time","Client","Currency","Amount","Recipient","Bank","Kz","User"])
    for r in rows:
        w.writerow([r["date"], r["time"], r["client"], r["currency"], f"{r['amount']:.2f}", r["recipient"], r["bank"] or "", r["kz"], r["username"]])
    mem = io.BytesIO(out.getvalue().encode("utf-8"))
    return send_file(mem, mimetype="text/csv", as_attachment=True, download_name="adox_transactions.csv")

@app.get("/backups")
@login_required
def backups_page():
    user = current_user()
    rows = get_db().execute("SELECT * FROM backups WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
    body = """
    <section class="card">
      <h2>{{ t('backupsTitle') }}</h2>
      <form method="post" action="/backups/save">
        <div class="row field"><label>{{ t('lblBackupName') }}</label><input name="name" placeholder="e.g., Week_34_2025" required></div>
        <p><button class="btn">{{ t('btnSaveBackup') }}</button></p>
      </form>
      <form method="post" action="/backups/load">
        <div class="row field"><label>{{ t('lblBackups') }}</label>
          <select name="name">
            {% for b in backups %}
              <option value="{{ b['name'] }}">{{ b['name'] }} ({{ b['created_at'] }})</option>
            {% endfor %}
          </select>
        </div>
        <p><button class="btn ghost">{{ t('btnLoadBackup') }}</button></p>
      </form>
    </section>
    """
    return render_page(body, backups=rows)

@app.post("/backups/save")
@login_required
def save_backup():
    user = current_user()
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Provide a backup name", "err")
        return redirect(url_for("backups_page"))
    db = get_db()
    tx = db.execute("SELECT date,time,client,origin,currency,amount,recipient,bank,kz FROM transactions WHERE user_id=?", (user["id"],)).fetchall()
    payload = [dict(r) for r in tx]
    db.execute("INSERT OR REPLACE INTO backups(user_id,name,payload_json,created_at) VALUES(?,?,?,?)",
               (user["id"], name, json.dumps(payload), datetime.utcnow().isoformat()))
    db.commit()
    flash("Backup saved", "ok")
    return redirect(url_for("backups_page"))

@app.post("/backups/load")
@login_required
def load_backup():
    user = current_user()
    name = (request.form.get("name") or "").strip()
    db = get_db()
    row = db.execute("SELECT * FROM backups WHERE user_id=? AND name=?", (user["id"], name)).fetchone()
    if not row:
        flash("Backup not found", "err")
        return redirect(url_for("backups_page"))
    db.execute("DELETE FROM transactions WHERE user_id=?", (user["id"],))
    for item in json.loads(row["payload_json"]):
        db.execute("""INSERT INTO transactions
            (id,user_id,date,time,client,origin,currency,amount,recipient,bank,kz,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (secrets.token_hex(8), user["id"], item["date"], item["time"], item["client"],
             item.get("origin",""), item["currency"], float(item["amount"]), item["recipient"],
             item.get("bank",""), int(item["kz"]), datetime.utcnow().isoformat()))
    db.commit()
    flash("Backup loaded", "ok")
    return redirect(url_for("reports_page"))

@app.get("/reset-totals")
@login_required
def reset_totals():
    body = """
    <section class="card">
      <h2>{{ t('btnReset') }}</h2>
      <form method="post" action="/reset-totals">
        <div class="row field"><label>{{ t('lblBackupName') }}</label><input name="name" required placeholder="BeforeReset_YYYY-MM-DD"></div>
        <p><button class="btn">{{ t('btnSaveBackup') }}</button></p>
      </form>
    </section>
    """
    return render_page(body)

@app.post("/reset-totals")
@login_required
def do_reset_totals():
    user = current_user()
    name = (request.form.get("name") or "").strip()
    db = get_db()
    tx = db.execute("SELECT date,time,client,origin,currency,amount,recipient,bank,kz FROM transactions WHERE user_id=?", (user["id"],)).fetchall()
    payload = [dict(r) for r in tx]
    db.execute("INSERT OR REPLACE INTO backups(user_id,name,payload_json,created_at) VALUES(?,?,?,?)",
               (user["id"], name, json.dumps(payload), datetime.utcnow().isoformat()))
    db.execute("DELETE FROM transactions WHERE user_id=?", (user["id"],))
    db.commit()
    flash("Totals reset and backup saved", "ok")
    return redirect(url_for("reports_page"))

@app.get("/help")
@login_required
def help_page():
    body = """
    <section class="card">
      <h2>{{ t('helpTitle') }}</h2>
      <ol>
        <li>{{ t('help1') }}</li>
        <li>{{ t('help2') }}</li>
        <li>{{ t('help3') }}</li>
        <li>{{ t('help4') }}</li>
        <li>{{ t('help5') }}</li>
      </ol>
    </section>
    """
    return render_page(body)

# ---------------- Run ----------------
if __name__ == "__main__":
    print("\nAdox Employee Portal running on http://127.0.0.1:5000  (Ctrl+C to stop)\n")
    app.run(debug=True)
