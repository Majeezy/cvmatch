# Deploying to Render

## 1. Set up Stripe (test mode first)

1. In the [Stripe Dashboard](https://dashboard.stripe.com), create a
   **Product** (e.g. "Job Application Assistant Pro") with a recurring
   **Price** (e.g. $9/month). Copy the Price ID (`price_...`).
2. Locally, test the whole billing flow before deploying:
   ```
   stripe login
   stripe listen --forward-to localhost:8080/webhook/stripe
   ```
   This prints a webhook signing secret (`whsec_...`). Add to your local
   `.env`:
   ```
   STRIPE_SECRET_KEY=sk_test_...
   STRIPE_WEBHOOK_SECRET=whsec_...
   STRIPE_PRICE_ID=price_...
   ```
3. Restart `python server.py`, sign up, hit the free generation limit, click
   Upgrade, and pay with Stripe's test card `4242 4242 4242 4242` (any
   future expiry, any CVC). Confirm your plan flips to Pro, and that
   cancelling from the billing portal flips it back to Free.

## 2. Push to GitHub

This repo isn't connected to a remote yet. From the project folder:
```
git remote add origin https://github.com/<you>/job-application-assistant.git
git branch -M main
git push -u origin main
```
(Create the empty GitHub repo first if you haven't.)

## 3. Deploy the Render Blueprint

1. In the [Render Dashboard](https://dashboard.render.com), click
   **New > Blueprint**, and point it at your GitHub repo — it will read
   `render.yaml` from the repo root automatically.
2. Render provisions a Postgres database and a web service with a 1GB
   persistent disk mounted at `/var/data` (this requires the web service's
   **Starter** plan or above — persistent disks aren't available on Render's
   free web service tier).
3. `DATABASE_URL` and `DATA_DIR` are wired automatically by the blueprint.
   `FLASK_SECRET` is auto-generated. You'll be prompted in the dashboard to
   fill in the secrets marked `sync: false`:
   - `GROQ_API_KEY` (optional — only needed as a server-side fallback if you
     want to support users who don't paste their own key)
   - `STRIPE_SECRET_KEY`
   - `STRIPE_WEBHOOK_SECRET` — see step 5, you'll come back to update this
   - `STRIPE_PRICE_ID`
4. Deploy. Once live, your app is reachable at
   `https://job-application-assistant.onrender.com` (or whatever name you
   gave the service) with a free Render-issued HTTPS certificate.

## 4. Point Stripe at the live URL

In the Stripe Dashboard, add a new webhook endpoint:
```
https://<your-app>.onrender.com/webhook/stripe
```
Copy its signing secret and update `STRIPE_WEBHOOK_SECRET` in the Render
dashboard's environment variables for the web service (this replaces the
local `stripe listen` secret from step 1 — that one only works for your
local machine). When you're ready for real customers, switch your Stripe
account out of test mode and swap in live-mode keys the same way.

## 5. Smoke test

Sign up, log in, upload a CV, generate documents up to the free limit,
upgrade via Checkout with a real (or Stripe live test) card, confirm the
webhook delivered successfully in the Stripe Dashboard's webhook logs, and
confirm your account shows Pro in the app.

## Custom domain (optional)

Render's dashboard has a straightforward "Custom Domain" section under the
web service — add a CNAME record at your DNS provider pointing to the
`onrender.com` hostname it gives you; HTTPS is provisioned automatically.
