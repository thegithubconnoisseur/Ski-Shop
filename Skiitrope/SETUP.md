# Skiitrope — Setup Guide

This guide walks you through everything needed to run the shop locally and to
switch on the four integrations: **Supabase** (database), **Mailgun** (emails),
**Google** (sign-in) and **Stripe** (card payments in USD).

Everything is configured through environment variables in a single `.env` file,
so you never have to edit Python code to add your keys.

---

## 0. Local quickstart (do this first)

You need Python 3.13+ installed. From the project folder:

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your .env file (skip if .env already exists)
cp .env.example .env

# 4. Set up the database
python manage.py migrate

# 5. Seed the catalogue (5 categories, 9 products)
python manage.py seed_products

# 6. Create your admin account (enter your email + a password)
python manage.py createsuperuser

# 7. Run the site
python manage.py runserver
```

Open http://127.0.0.1:8000/ — the shop runs out of the box on SQLite with
emails printed to the console and payments switched off. Add the integrations
below one at a time, restarting the server after each `.env` change.

Useful commands:

| Command | What it does |
| --- | --- |
| `python manage.py test` | Runs the full test suite |
| `python manage.py check` | Sanity-checks your settings |
| `python manage.py runserver` | Starts the dev server |
| `/admin/` in the browser | Manage products, categories, orders |

---

## 1. Supabase (database)

1. Go to https://supabase.com and sign up (free tier is fine).
2. Click **New project**. Choose a name (e.g. `skiitrope`), a database
   password (save it somewhere safe) and the region closest to you —
   for Nigeria, `eu-central-1` (Frankfurt) is a good choice.
3. Wait ~2 minutes for the project to finish provisioning.
4. Click **Connect** (top bar) → **Connection string** tab. Copy the
   **Session pooler** URI. It looks like:

   ```
   postgres://postgres.abcdefghijklm:YOUR-PASSWORD@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
   ```

   The Session pooler works over IPv4, which is why we use it instead of the
   direct connection.
5. Open your `.env` file and set `DATABASE_URL` to your connection string
   (paste the real password, keep the `?sslmode=require` ending):

   ```
   DATABASE_URL=postgres://postgres.abcdefghijklm:YOUR-PASSWORD@aws-0-eu-central-1.pooler.supabase.com:5432/postgres?sslmode=require
   DB_CONN_MAX_AGE=0
   ```

   Keep `DB_CONN_MAX_AGE=0` — the pooler manages connections itself.
6. Load the schema and demo data into Supabase:

   ```bash
   python manage.py migrate
   python manage.py seed_products
   ```

7. Confirm it worked: in the Supabase dashboard open **Table Editor** — you
   should see tables like `store_product`, `accounts_user`, `orders_order`.
   Visit the shop again and your data now comes from Supabase.

> Tip: if you ever want to go back to a local SQLite file, just clear
> `DATABASE_URL` in `.env` — the project falls back automatically.

---

## 2. Mailgun (order confirmation emails)

Without this section, emails are printed to the terminal (console backend) so
you can test the whole flow without sending anything real.

1. Sign up at https://mailgun.com (free plan: 100 emails/day).
2. **Fastest option while testing — Sandbox domain:** Mailgun gives every
   account a sandbox domain like `sandbox1234.mailgun.org`. Its API key is on
   the dashboard under **Sending → Domain settings → API keys**. With the
   sandbox you must add your own email under **Authorized recipients** or
   Mailgun will refuse to deliver.

   **Heads-up:** Gmail usually routes sandbox emails to the **spam folder**
   (they fail Gmail's DMARC checks because sandbox domains share
   `mailgun.org`'s poor reputation). The email *is* delivered — search Gmail
   for `in:anywhere skiitrope` and click **Not spam**. Delivering to the
   inbox reliably requires your own verified domain (below).

   **Production option — your own domain:** add a subdomain like
   `mg.yourdomain.com` under **Sending → Domains → Add domain**, then add the
   DNS records Mailgun shows you (SPF TXT and DKIM CNAME/TXT) at your domain
   registrar. Wait for the domain status to become **Verified**.

3. Fill these values in `.env`:

   ```
   MAILGUN_API_KEY=your-private-api-key
   MAILGUN_SENDER_DOMAIN=mg.yourdomain.com        # or sandbox1234.mailgun.org
   MAILGUN_API_URL=https://api.mailgun.net/v3     # use https://api.eu.mailgun.net/v3 if your domain is in the EU region
   DEFAULT_FROM_EMAIL=Skiitrope <orders@mg.yourdomain.com>
   SERVER_EMAIL=Skiitrope <alerts@mg.yourdomain.com>
   ORDER_NOTIFICATION_EMAIL=you@yourdomain.com    # where you want order alerts
   ```

4. Where emails are sent from in the code:
   - **Customer confirmation** — after a payment is confirmed (Stripe webhook
     or the success page), `orders/emails.py` emails the order number, items
     and totals to the address on the order.
   - **Owner alert** — every order placed also emails `ORDER_NOTIFICATION_EMAIL`
     (sent from `SERVER_EMAIL`) so you know an order came in, even before
     payment completes.
   - Make sure `DEFAULT_FROM_EMAIL` uses your Mailgun domain, or the send
     will fail.

5. Test it: place a full test order with Stripe in test mode (section 4).
   The confirmation email should arrive within a minute — with a sandbox
   domain, check the spam folder too. You can also watch every message in
   the Mailgun dashboard under **Sending → Logs**.

---

## 3. Google (sign in with Google)

1. Go to https://console.cloud.google.com — sign in with your Google account.
2. Create a project: click the project dropdown (top bar) → **New project** →
   name it `Skiitrope` → **Create**, then select it.
3. Configure the consent screen: **APIs & Services → OAuth consent screen**
   - User type: **External** → **Create**.
   - App name: `Skiitrope`, your support email, developer contact email.
   - Save through the steps; you can leave scopes at the defaults.
   - Under **Test users**, add your own Gmail address (while the app is in
     "Testing" status, only listed test users can sign in — that is fine for
     development).
4. Create the credentials: **APIs & Services → Credentials →
   Create credentials → OAuth client ID**
   - Application type: **Web application**
   - Name: `Skiitrope web`
   - **Authorized redirect URIs** — add exactly:

     ```
     http://localhost:8000/accounts/google/login/callback/
     ```

     (When you deploy, add a second entry for your real domain, e.g.
     `https://yourdomain.com/accounts/google/login/callback/`.)
   - Click **Create**, then copy the **Client ID** and **Client secret**.
5. Fill them into `.env`:

   ```
   GOOGLE_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxx
   ```

6. Restart the server and open http://127.0.0.1:8000/accounts/login/ —
   "Continue with Google" now signs you in. The credentials are read straight
   from `.env` (`SOCIALACCOUNT_PROVIDERS` in `settings.py`), so you do **not**
   need to create a social application in the Django admin.

> Redirect URI not matching is the most common error. It must match
> character-for-character — including the trailing slash.

---

## 4. Stripe (card payments in USD)

Payments are off until `STRIPE_SECRET_KEY` is set; the checkout page shows a
friendly notice telling you so. No business registration is needed for test
mode.

1. Sign up at https://stripe.com and stay in **Test mode** (toggle in the
   dashboard header).
2. Copy your test keys: **Developers → API keys**
   - **Publishable key** (`pk_test_...`)
   - **Secret key** (`sk_test_...`) — click to reveal, copy it.
3. Fill them into `.env`:

   ```
   STRIPE_PUBLIC_KEY=pk_test_xxxxxxxx
   STRIPE_SECRET_KEY=sk_test_xxxxxxxx
   ```

4. Set up the webhook (this is what reliably confirms payment and triggers the
   confirmation email):
   - **Live on a deployed site:** **Developers → Webhooks → Add endpoint**.
     Endpoint URL: `https://yourdomain.com/stripe/webhook/`, and select the
     event **`checkout.session.completed`**. After saving, copy the
     **Signing secret** (`whsec_...`).
   - **Locally while developing:** install the Stripe CLI
     (https://docs.stripe.com/stripe-cli) and run:

     ```bash
     stripe login
     stripe listen --forward-to localhost:8000/stripe/webhook/
     ```

     The CLI prints its own `whsec_...` — use that one locally.
5. Put the signing secret in `.env`:

   ```
   STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxx
   ```

   Note: the CLI secret and the dashboard secret are different; each Stripe
   environment (local vs deployed) uses its own.
6. Test a purchase end to end:
   - Add something to the cart → checkout → fill the shipping form → pay.
   - Test card: `4242 4242 4242 4242`, any future expiry, any CVC, any ZIP.
   - You should land on the success page, the order flips to **Paid** in
     `/admin/`, and (with Mailgun configured) the confirmation email is sent.
7. When you are ready for real money: complete your Stripe account activation,
   switch the dashboard to **Live mode**, repeat steps 2–5 with the live keys
   and add a live webhook endpoint.

> Shipping is charged as a line item: free over `FREE_SHIPPING_THRESHOLD`
> ($300), otherwise `FLAT_SHIPPING_RATE` ($15). Both are configurable in `.env`.

---

## 5. Run the tests

```bash
python manage.py test
```

The suite (55 tests) covers the catalogue, cart maths, checkout/orders,
Stripe webhook handling and the email flow. It uses fast SQLite + an in-memory
mail backend automatically, so your Supabase data and Mailgun quota are never
touched while testing.

---

## 6. Deploying to Render

**Why a first attempt fails:** your GitHub repo (`Ski-Shop`) holds several
projects in one repo and Skiitrope sits in a subfolder. Render only scans the
**root** of the repo — with "Root Directory" left empty it finds no Python
project and the build fails immediately. One field fixes it (step 3).

1. In the Render dashboard: **New + → Web Service**.
2. Connect your GitHub account if asked, then pick the **Ski-Shop** repo.
3. On the settings page, fill in:
   - **Name**: `skiitrope`
   - **Region**: Frankfurt (closest to Nigeria)
   - **Branch**: `main`
   - **Root Directory**: `Skiitrope` ← the important one
   - **Runtime**: Python 3
   - **Build Command**:

     ```bash
     pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --no-input && python manage.py seed_products
     ```

   - **Start Command**: `gunicorn skiitrope.wsgi:application`
   - **Instance Type**: Free
4. Under **Environment**, add these variables — the same values as your
   local `.env` (Render does not read `.env`; it only sees what you add here):

   | Variable | Value |
   | --- | --- |
   | `DJANGO_SECRET_KEY` | the long key from your `.env` |
   | `DATABASE_URL` | your Supabase session-pooler string ending in `?sslmode=require` |
   | `DB_CONN_MAX_AGE` | `0` |
   | `STRIPE_PUBLIC_KEY`, `STRIPE_SECRET_KEY` | your Stripe test keys |
   | `STRIPE_WEBHOOK_SECRET` | the signing secret from the endpoint you create in step 6 |
   | `MAILGUN_API_KEY`, `MAILGUN_SENDER_DOMAIN` | from Mailgun |
   | `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL` | `postmaster@<your-sandbox-domain>` |
   | `ORDER_NOTIFICATION_EMAIL` | your email |
   | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | from Google Cloud Console |

   Leave `DJANGO_DEBUG` unset — on Render the app automatically runs with
   `DEBUG=False` and trusts its own `*.onrender.com` address
   (`skiitrope/settings.py` reads `RENDER_EXTERNAL_HOSTNAME`).

5. Click **Create Web Service** and wait for the build (a few minutes on the
   first deploy). The site is then live at
   `https://<your-service-name>.onrender.com`. Log into `/admin/` with your
   existing admin account — it lives in the shared Supabase database.
6. Point the integrations at the live URL:
   - **Stripe** → Developers → Webhooks → **Add endpoint**:
     `https://<your-service>.onrender.com/stripe/webhook/` with the event
     `checkout.session.completed`. Copy the new signing secret into
     `STRIPE_WEBHOOK_SECRET` on Render — each endpoint has its own secret.
   - **Google Cloud Console** → your OAuth client → add the authorized
     redirect URI `https://<your-service>.onrender.com/accounts/google/login/callback/`.
   - Django admin → **Sites** → change `example.com` to your
     `*.onrender.com` domain (used for absolute links and account emails).

Free-tier notes: the service sleeps after ~15 minutes of inactivity (the
next visit then takes ~30 seconds to wake up), and uploaded files reset when
Render restarts the service — fine while testing; move to paid disk or
object storage before taking real customers.

Deploying somewhere else instead? The same env vars apply, plus: run
`python manage.py migrate`, `collectstatic --no-input` and
`seed_products` once, and serve with
`gunicorn skiitrope.wsgi:application`.

---

## Where things live (cheat sheet)

| Path | Purpose |
| --- | --- |
| `.env` | All secrets and settings (never committed) |
| `skiitrope/settings.py` | Reads `.env`, wires Supabase / Mailgun / Google / Stripe |
| `store/` | Catalogue: categories, products, shop and detail pages |
| `cart/` | Session cart with stock caps and shipping maths |
| `orders/` | Checkout form, orders, Stripe integration, emails |
| `accounts/` | Custom email-based user model |
| `templates/` | All pages (black / white with red & blue accents) |
| `static/css/styles.css` | The theme |
