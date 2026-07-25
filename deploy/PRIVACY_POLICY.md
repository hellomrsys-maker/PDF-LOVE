# Dockbench Privacy Policy

*Last updated: [fill in date before publishing]*

## The short version

Dockbench processes your files entirely on your own device. For the vast
majority of tools, nothing about your files — not their contents, not their
names, not even the fact that you used a tool — is ever sent anywhere. There
is no account system for individuals, so there is no login, no email
address, and no personal profile for us to collect in the first place.

## What we do not collect

- File contents or filenames processed by on-device tools (merge, split,
  compress, OCR, encrypt, redact, image/video tools, and the rest of the
  103 on-device tools)
- Analytics, trackers, or advertising identifiers, by default
- Any account information for individual users — there is no login
- Location data, contacts, or device identifiers

## What optional features do collect (only if you use them)

- **Server-assisted tools** (Office→PDF full fidelity, deep compression,
  PDF/A, background removal at scale, chat-with-PDF): these appear only
  when a backend is available, and only send the file you explicitly
  submit to that specific tool — to a backend that is either operated by
  us or self-hosted by you, as documented in the project's README. That
  backend's own logging policy (see `backend/main.py`'s privacy contract)
  applies: no file contents or filenames are logged, and per-request temp
  files are deleted immediately after the response is built.
- **Currency Converter**: fetches live exchange rates from a third-party
  rate provider (no file or personal data is sent — just the request
  itself, which may reveal your IP address to that provider, as with any
  network request).
- **On-device AI features** (background removal, summarize, translate,
  voice-to-text, image captioning): the underlying models are downloaded
  once from their public model host (e.g. Hugging Face) and cached in your
  browser; after that first download, these features run fully offline
  with no further network requests.
- **Advertising** (if enabled by whoever is operating this deployment):
  Dockbench's free tier can optionally show a passive banner ad or an
  optional rewarded video ad (to remove a small mark from a free PDF
  export). These are off by default. If an operator turns them on, the
  specific ad network they choose will have its own data collection
  practices governing ad delivery (impressions, and typically some device/
  browser signals) — consult that network's own privacy policy, linked
  from wherever this deployment enables ads.

## Enterprise/self-hosted deployments

If you're using a self-hosted or enterprise deployment of Dockbench with
its own login/SSO, that operator's own privacy policy and data handling
practices govern your account and any audit logs they choose to keep — this
document describes the public, individual-tier product only.

## Changes to this policy

If this deployment's data practices change (e.g. ads are enabled, or a new
optional feature is added that sends data somewhere), this document will be
updated and the "Last updated" date above will change accordingly.

## Contact

[Fill in a contact email or form before publishing this policy publicly —
Play Console requires a working contact method alongside the privacy
policy URL.]
