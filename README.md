# Small Home Business Expense & Sales Tracker

A simple, clean web app for a small home-business owner to track expenses, products, sales/orders, customers, payments, and profit — built with Python, Flask, and SQLite.

## Features

- Dashboard with summary cards (sales, expenses, profit, received, pending, customers, orders) and charts (sales vs expenses, sales by product, payment status), filterable by day/week/month/year/custom range
- Customer management with full purchase history
- Product catalog with automatic per-item profit calculation
- Sales/order entry with automatic total, pending amount, and payment status calculation
- Expense tracking by category
- Pending Payments page — see who owes you money, sortable, with a quick "record payment" action
- Reports: monthly summary, expense breakdown, customer report, product report
- Search and filters everywhere: customers, products, sales, expenses
- Mobile-friendly, responsive UI
- Password-protected: every page requires signing in, with the first account created on first visit

## Project Structure

```
business_tracker/
├── app.py              # Flask application factory (creates `app`)
├── wsgi.py             # WSGI entry point for PythonAnywhere
├── config.py           # Configuration (reads SECRET_KEY, DATABASE_URL from env)
├── extensions.py       # Shared SQLAlchemy `db` instance
├── requirements.txt
├── seed_data.py        # Optional: loads a few sample records
├── models/             # SQLAlchemy models (Customer, Product, Sale, OrderItem, Expense)
├── routes/             # Flask blueprints (dashboard, customers, products, sales, expenses, payments, reports, settings)
├── utils/              # Validation helpers and business calculations
├── templates/          # Jinja2 templates
├── static/             # CSS, JS, images
└── instance/           # Created automatically; holds the SQLite database file
```

## Running Locally

1. Create a virtual environment and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. (Optional) Copy `.env.example` to `.env` and set a real `SECRET_KEY`.
3. Run the app:
   ```bash
   python app.py
   ```
   The database tables are created automatically on first run inside `instance/business_tracker.db`.
   Running this file directly uses the development config, so no `SECRET_KEY` is needed locally.
4. Open http://127.0.0.1:5000 in your browser. The first visit asks you to create the
   username and password you will sign in with from then on.

   **On macOS**, port 5000 is used by AirPlay Receiver (Control Center). If the page
   shows a 403 or "Forbidden" that did not come from this app, run it on another port:
   ```bash
   PORT=5001 python app.py     # then open http://127.0.0.1:5001
   ```
   Or turn AirPlay Receiver off under System Settings → General → AirDrop & Handoff.
5. (Optional) Load sample data to see the app in action:
   ```bash
   python seed_data.py
   ```

## Deploying to PythonAnywhere

1. **Upload the code.** Easiest options:
   - Push this project to a GitHub repo, then in a PythonAnywhere **Bash console** run:
     ```bash
     git clone https://github.com/your-username/your-repo.git business_tracker
     ```
   - Or zip the project and upload it via the **Files** tab, then unzip it in a Bash console:
     ```bash
     unzip business_tracker.zip
     ```

2. **Create a virtual environment** (in a PythonAnywhere Bash console):
   ```bash
   cd business_tracker
   python3.10 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Create a new Web App:**
   - Go to the **Web** tab → **Add a new web app**.
   - Choose **Manual configuration** (not the Flask quickstart wizard) and select the Python version matching your virtualenv (e.g. 3.10).

4. **Set the virtualenv path** in the Web tab, under "Virtualenv":
   ```
   /home/yourusername/business_tracker/venv
   ```

5. **Edit the WSGI configuration file** (link is on the Web tab, e.g. `/var/www/yourusername_pythonanywhere_com_wsgi.py`). Replace its contents with:
   ```python
   import sys
   import os

   project_home = '/home/yourusername/business_tracker'
   if project_home not in sys.path:
       sys.path.insert(0, project_home)

   os.environ.setdefault('FLASK_ENV', 'production')
   os.environ.setdefault('SECRET_KEY', 'paste-a-long-random-value-here')

   from wsgi import application
   ```
   Replace `yourusername` with your actual PythonAnywhere username, and set a real `SECRET_KEY` (generate one locally with `python -c "import secrets; print(secrets.token_hex(32))"`).

6. **Set the source code / working directory** on the Web tab to:
   ```
   /home/yourusername/business_tracker
   ```

7. **Reload the web app** (green "Reload" button on the Web tab). The database and its tables are created automatically the first time the app starts, inside `business_tracker/instance/business_tracker.db` — no manual database setup step is required.

8. Visit `https://yourusername.pythonanywhere.com` — your tracker is live.

### Updating the app later

After pushing new code (e.g. `git pull` in a Bash console), just click **Reload** on the Web tab again. Your existing SQLite data in `instance/business_tracker.db` is never touched by a reload or by `db.create_all()` — it only creates tables that don't exist yet.

### Backing up your data

Your entire business database is the single file `instance/business_tracker.db`. Periodically download a copy of this file from the **Files** tab as a simple backup.

## Signing In

- Every page requires a signed-in user. The very first visit shows a one-time
  **Create your account** screen; that screen closes itself permanently once an
  account exists, so nobody else can use it to make a second account.
- Passwords are stored only as a scrypt hash (via Werkzeug), never as text.
- After 5 wrong passwords the account pauses for 5 minutes, so the app cannot
  simply be guessed at on a public URL.
- Change your password under **Settings → Your Account**.
- **Forgotten password?** There is no email reset (the app sends no email). From a
  Bash console on the machine hosting it:
  ```bash
  cd business_tracker
  source venv/bin/activate
  FLASK_APP=app.py SECRET_KEY=your-real-key flask reset-password
  ```

### SECRET_KEY is now required in production

The login session is a signed cookie, so anyone who knows the signing key can forge
one and skip the login page entirely. Because the old placeholder key is published in
this repository, **the app refuses to start in production while it is still in use** —
it fails loudly at startup rather than looking protected without being so. Generate one
with `python -c "import secrets; print(secrets.token_hex(32))"` and set it as
`SECRET_KEY` (see the PythonAnywhere steps above).

Changing `SECRET_KEY` later signs everyone out, which is also how you revoke access if
a session is ever compromised.

## Data Safety Notes

- All amounts are validated server-side (no negative prices/amounts allowed) regardless of what the browser sends.
- Payment status (Paid / Partially Paid / Pending) is always derived from `amount_paid` vs `total_amount` in the database — never set directly — so it can't drift out of sync.
- Deleting a customer or product that has existing sales history is blocked; deactivate the product instead to keep historical reports accurate.
- All totals shown on the dashboard and reports are computed fresh from the database on each request, never cached in memory — important because PythonAnywhere may run multiple worker processes.
- **Forms do not carry CSRF tokens yet.** The session cookie is `SameSite=Lax`, which
  stops another website submitting these forms as you in current browsers, but adding
  Flask-WTF tokens would be the belt-and-braces fix if this is ever exposed more widely.

## Extending Later

The codebase is organized so these can be added without restructuring:
- Invoice / PDF generation (add a `routes/invoices.py` + a PDF library)
- Excel/CSV export (add export routes using `csv`/`openpyxl`)
- Backup & restore (download/upload the `instance/business_tracker.db` file)
- WhatsApp payment reminders (integrate a WhatsApp API from `routes/payments.py`)
- Inventory/stock tracking (add a `stock_quantity` column to `Product`)
- Additional user accounts (the `User` model and login already exist; what is missing
  is a screen to invite a second user and per-user permissions)
- CSRF tokens on forms (see Data Safety Notes)
