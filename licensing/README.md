# PDFLove offline licensing

Ad revenue only exists when a user is online — an ad network has to serve
the creative and verify the impression over a live connection, and there is
no way around that (caching/replaying an ad offline would be ad fraud and
risks a permanent network ban, so don't). For genuinely offline deployments
— a library, a school, a government office, any air-gapped machine — this
is a separate, purely local monetization path: a cryptographically signed
license key that PDFLove verifies **entirely on-device**, with the
browser's built-in Web Crypto API, no server involved before or after.

This is the same trust model commercial desktop software has used for
decades (Sublime Text, JetBrains, etc.): you hold a private key and sign
license keys with it; the app ships with only the matching *public* key,
which can verify a signature but can never forge one.

## One-time setup

```bash
node licensing/keygen.js
```

This writes two files, right here in `licensing/`:

- **`private-key.json` — secret.** Never commit it, never share it. Back it
  up somewhere safe (password manager, offline drive). `.gitignore` already
  excludes it, but that's not a substitute for a real backup — if you lose
  this file, you can never mint a valid license under this identity again,
  and every key you already sold would need to move to a new keypair.
- **`public-key.json` — safe to share.** Copy its contents into
  `frontend/index.html`, replacing:
  ```js
  const LICENSE_PUBLIC_KEY_JWK = null;
  ```
  with the actual JSON object from `public-key.json`. Until you do this,
  the app's license panel says "not configured yet" and never rejects a
  real license by mistake — it just has nothing to check one against.

## Minting a license to sell

```bash
node licensing/mint.js --tier=offline-pro --licensee="Springfield Library" --seats=50 --expires=2027-12-31
```

- `--tier` (required): any string you want — shown back to the user, and
  usable in `frontend/index.html` if you ever want different tiers to
  unlock different things.
- `--licensee`, `--seats`, `--expires` (optional): `--expires` omitted means
  a perpetual license. `--seats` is informational only (PDFLove doesn't
  enforce a seat count locally — there's no server to track activations
  against) — for a 50-seat institutional deal, hand the same key to all 50
  machines, or mint 50 individual keys if you want per-machine tracking on
  your own side.

The command prints the license key string — that's what you hand to the
buyer. They paste it into PDFLove's license panel (reachable from the
footer, or from the watermark-removal prompt), which verifies it instantly,
fully offline, and never asks again once activated on that device
(stored in `localStorage`, re-verified against the signature every load).

## What a license actually unlocks

Currently: free-tier PDF exports never get the small removable corner mark
that the optional ad-based removal flow otherwise offers — a licensed
device simply never sees a watermark or an ad prompt on that export path.
Nothing else about the app changes; the free tier already has all 104
tools with no other restriction.

## Institutional / site licenses

For a school district, library system, or government office deploying to
many offline machines: sell one license (a normal invoice/PO, handled
entirely outside the app), then either hand every machine the same key or
mint one per machine — your call, since there's no server-side seat
enforcement to work around either way. The transaction and the deployment
are both fully independent of internet access after the one-time key
hand-off.
