# Deploying CVMatch to Render

## 1. Set up PayFast (sandbox first)

PayFast has no CLI equivalent to `stripe listen`, and its sandbox can only
reach a publicly-reachable `notify_url` — so unlike the old Stripe setup,
the webhook half of this can't be fully exercised purely on `localhost`.
The checkout/signature half can, though, and already has been (see
`payfast.py`'s module docstring for what was empirically verified against
the real sandbox while building this).

1. Register a sandbox account at [sandbox.payfast.co.za](https://sandbox.payfast.co.za/)
   — do this even though published shared test credentials exist
   (`merchant_id=10000100`, used in `.env.example`); they're fine for a
   quick signature check, not for testing a full subscription lifecycle
   end-to-end, since you don't control that account's settings.
2. In the sandbox dashboard, find your `merchant_id` and `merchant_key`,
   and (Settings → Integration) set a passphrase if you want one — if you
   do, `PAYFAST_PASSPHRASE` must match it exactly, and if you don't, leave
   the env var blank. Appending a passphrase the account doesn't actually
   have configured is a real bug, not a no-op (see `payfast.py`).
3. Set in `.env`:
   ```
   PAYFAST_MERCHANT_ID=...
   PAYFAST_MERCHANT_KEY=...
   PAYFAST_PASSPHRASE=...        # only if you set one above
   PAYFAST_SANDBOX=true
   PAYFAST_PRO_PRICE_ZAR=99.00
   ```
4. The full lifecycle test (signup → hit free limit → upgrade → PayFast's
   hosted payment page with a sandbox test card → webhook fires → plan
   flips to Pro → cancel → plan flips back) needs to run against a real
   deployed URL, since PayFast has to be able to reach `notify_url`. Do
   this after step 3 below, against the live Render URL with
   `PAYFAST_SANDBOX` still `true` — flip to `false` with live credentials
   only once that's actually passed.

## 2. Set up Resend (email verification)

1. Create a free account at [resend.com](https://resend.com), get an API
   key (API Keys tab).
2. For real delivery to real users, verify a domain (Domains tab) and set
   `EMAIL_FROM` to an address on it. Without a verified domain, Resend's
   shared `onboarding@resend.dev` sender works but only delivers to your
   own Resend account's verified email — fine for your own testing, not
   for real signups.
3. Set `RESEND_API_KEY` and `EMAIL_FROM` in `.env`. If left unset, signup
   still works (see `email_sender.py`) — users just can't get a
   verification email until it's configured, which also means they can't
   upgrade to Pro (checkout is gated on `email_verified`).

## 3. Push to GitHub

This repo isn't connected to a remote yet. From the project folder:
```
git remote add origin https://github.com/<you>/cvmatch.git
git branch -M main
git push -u origin main
```
(Create the empty GitHub repo first if you haven't.)

## 4. Deploy the Render Blueprint

1. In the [Render Dashboard](https://dashboard.render.com), click
   **New > Blueprint**, and point it at your GitHub repo — it will read
   `render.yaml` from the repo root automatically.
2. Render provisions a Postgres database and a web service with a 1GB
   persistent disk mounted at `/var/data` (this requires the web service's
   **Starter** plan or above — persistent disks aren't available on Render's
   free web service tier; this is the one recurring cost in this setup).
3. `DATABASE_URL` and `DATA_DIR` are wired automatically by the blueprint.
   `FLASK_SECRET` is auto-generated. You'll be prompted in the dashboard to
   fill in the secrets marked `sync: false`:
   - `GROQ_API_KEY` (optional — only needed as a server-side fallback if you
     want to support users who don't paste their own key)
   - `PAYFAST_MERCHANT_ID`, `PAYFAST_MERCHANT_KEY`, `PAYFAST_PASSPHRASE`
   - `RESEND_API_KEY`, `EMAIL_FROM`
4. Deploy. Once live, your app is reachable at
   `https://cvmatch.onrender.com` (or whatever name you gave the
   service) with a free Render-issued HTTPS certificate.

## 5. Run the full PayFast lifecycle test against the live URL

With `PAYFAST_SANDBOX=true` still set on the deployed service: sign up,
verify your email, hit the free generation limit, click Upgrade, pay on
PayFast's hosted sandbox page with their test card details, and confirm:
- Render's logs show the `/webhook/payfast` request arriving and the four
  validation steps passing (signature, host, PayFast's own validate
  endpoint, amount match — see `billing.py`).
- Your account's plan flips to Pro in the app.
- "Cancel plan" actually cancels (check Render logs for the
  Subscriptions-API call in `payfast.py` — this part specifically was
  never verified before a real subscription token existed, see its
  module docstring).

Only once all of that has genuinely passed should you switch
`PAYFAST_SANDBOX` to `false` and swap in live PayFast credentials.

## Custom domain (optional)

Render's dashboard has a straightforward "Custom Domain" section under the
web service — add a CNAME record at your DNS provider pointing to the
`onrender.com` hostname it gives you; HTTPS is provisioned automatically.
