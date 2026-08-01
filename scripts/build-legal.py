#!/usr/bin/env python3
"""
Generate the legal pages for PDF Love.

    python scripts/build-legal.py

Seven documents, one source of truth. Every page names the same operator,
the same contact addresses and the same effective date, because the fastest
way to look untrustworthy is to have a privacy policy that disagrees with
the terms about who you are.

Why generated rather than hand-written: these pages repeat the operator's
identity, the grievance contact and the footer a dozen times between them.
Hand-maintained, they drift the first time anything changes.

    NOT LEGAL ADVICE. These are careful, well-researched documents that cite
    the right statutes and say true things, which puts this ahead of most
    sites of its size. Before taking meaningful ad revenue, have an Indian
    advocate read the liability clause in the Terms and confirm the
    Grievance Officer designation.

Fill in OPERATOR below. scripts/check-legal.py fails the build while any
detail is still missing, so half-filled pages cannot reach production.
"""

import html
import os
import re
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "frontend", "company")
SITE = os.environ.get("SITE_ORIGIN", "https://pdflove.co.in").rstrip("/")

# --------------------------------------------------------------------
# The only block that needs editing. None = not supplied yet; the build
# emits a visible TO-BE-COMPLETED marker and check-legal.py fails on it.
# --------------------------------------------------------------------
OPERATOR = {
    # Your full legal name, as you would sign a contract. Under India's DPDP
    # Act you are the "Data Fiduciary"; under GDPR the "controller". A named
    # individual is perfectly lawful — no company registration is required to
    # run an ad-supported website.
    "legal_name": None,

    # Published as your place of business. City and state only: you are an
    # individual, and publishing a home address is a real safety problem that
    # no law requires you to accept. The full address is given on request and
    # is held privately by AdSense for payments.
    "city": None,
    "state": None,
    "country": "India",

    # IT Rules 2021 require a named Grievance Officer with working contact
    # details. As a sole operator this is you.
    "grievance_officer": None,

    # Courts with exclusive jurisdiction. Normally where you are based.
    "jurisdiction": None,

    # Cloudflare Email Routing aliases forwarding to one real inbox. Every
    # one of these must exist as a routing rule before the pages go live — a
    # grievance address that bounces is worse than none, and the IT Rules
    # require the published contact to work. business@ is used by
    # company/contact.html, which is hand-written rather than generated.
    "email_grievance": "grievance@pdflove.co.in",
    "email_business": "business@pdflove.co.in",
    "email_privacy": "privacy@pdflove.co.in",
    "email_legal": "legal@pdflove.co.in",
    "email_support": "support@pdflove.co.in",
    "email_security": "security@pdflove.co.in",
    "email_billing": "billing@pdflove.co.in",

    "brand": "PDF Love",
    "effective_date": date.today().isoformat(),
}

MISSING_MARK = "[TO BE COMPLETED"


def v(key):
    """Operator value, or a loud marker that check-legal.py will catch."""
    val = OPERATOR.get(key)
    if val:
        return html.escape(str(val))
    return f"{MISSING_MARK}: {key}]"


def esc(s):
    return html.escape(s, quote=True)


BRAND = OPERATOR["brand"]

FOOTER_NAV = [
    ("../index.html", "Tools"),
    ("../download.html", "Download"),
    ("../tools/index.html", "All tools"),
    ("../guides/index.html", "Guides"),
    ("about.html", "About"),
    ("pricing.html", "Pricing"),
    ("contact.html", "Contact"),
    ("legal.html", "Legal"),
    ("privacy.html", "Privacy"),
    ("terms.html", "Terms"),
    ("cookies.html", "Cookies"),
    ("grievance.html", "Grievance"),
    ("security.html", "Security"),
    ("refund.html", "Refunds"),
]


def page(slug, title, description, h1, lede, body):
    nav = "\n    ".join(f'<a href="{h}">{esc(t)}</a>' for h, t in FOOTER_NAV)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{SITE}/company/{slug}.html">
<link href="../vendor/fonts/fonts.css" rel="stylesheet">
<link href="company.css" rel="stylesheet">
</head>
<body>
<header><div class="wrap"><a class="brand" href="../index.html"><span class="dot"></span>{esc(BRAND)}</a></div></header>
<main><div class="wrap">

  <h1>{esc(h1)}</h1>
  <p class="lede">{lede}</p>
  <p class="meta">Effective {v('effective_date')}. Operated by {v('legal_name')},
  {v('city')}, {v('state')}, {v('country')}.</p>

{body}
</div></main>
<footer class="site-footer"><div class="wrap">
  <nav>
    {nav}
  </nav>
  <p class="fine">{esc(BRAND)} — PDF, image and video tools that run on your own device.<br>
  &copy; <span id="yr">2026</span> {v('legal_name')}. All rights reserved.</p>
</div></footer>
<script>document.getElementById('yr').textContent=new Date().getFullYear();</script>
</body>
</html>
"""


def mailto(key):
    return f'<a href="mailto:{v(key)}">{v(key)}</a>'


# --------------------------------------------------------------------
# 1. The hub — plain English, one screen. Everything else is the detail.
# --------------------------------------------------------------------
def doc_legal():
    body = f"""
  <div class="note">
    <strong>The whole thing in five lines.</strong>
    <ul>
      <li>Your files are opened, edited and saved by your own browser. They are never uploaded to us.</li>
      <li>We have no accounts, no analytics and no tracking of our own. We could not identify you if we tried.</li>
      <li>Adverts appear only on information pages — never in the tool itself, and never while a file is being processed.</li>
      <li>You are responsible for the files you handle and for checking the results.</li>
      <li>The service is free and provided as-is.</li>
    </ul>
  </div>

  <h2>Why you can check this rather than trust it</h2>
  <p>Most privacy policies are promises about how a company intends to behave.
  Ours is mostly a description of how the software is built, which you can
  verify yourself in about thirty seconds: open your browser's developer
  tools, switch to the Network tab, pick a file, and run any tool. Nothing
  fires. An automated test asserts exactly that on every single deploy — if
  it ever stopped being true, the build would fail before you saw it.</p>

  <h2>The documents</h2>
  <div class="card">
    <ul style="list-style:none;padding:0;">
      <li><strong><a href="privacy.html">Privacy Policy</a></strong> — what we
      collect (almost nothing), what advertising partners receive, and your
      rights wherever you live.</li>
      <li><strong><a href="terms.html">Terms of Use</a></strong> — the deal:
      free, as-is, and your files are your responsibility.</li>
      <li><strong><a href="cookies.html">Cookies &amp; Advertising</a></strong> —
      we set no cookies of our own; what ad partners set, and how to refuse.</li>
      <li><strong><a href="grievance.html">Grievance Redressal</a></strong> —
      how to complain and how fast we must answer, as Indian law requires.</li>
      <li><strong><a href="security.html">Security</a></strong> — the
      architecture, and how to report a vulnerability.</li>
      <li><strong><a href="refund.html">Refunds</a></strong> — for paid API
      plans only. The app itself is free.</li>
    </ul>
  </div>

  <h2>Who runs this</h2>
  <p>{esc(BRAND)} is operated by {v('legal_name')}, an individual based in
  {v('city')}, {v('state')}, {v('country')}. That is the whole organisation.
  There is no company standing behind it and no investor to answer to, which
  is exactly why the product can afford to collect nothing.</p>
  <p>Write to {mailto('email_support')} for anything ordinary,
  {mailto('email_privacy')} about your data, or {mailto('email_grievance')} to
  file a formal complaint.</p>
"""
    return page(
        "legal", f"Legal, privacy and terms in plain English — {BRAND}",
        "Privacy, terms, cookies and grievance redressal for PDF Love, in plain English. Files never leave your device.",
        "Legal, in plain English",
        "Everything here in one screen. The full documents are linked below, "
        "but this page is the honest summary and nothing in them contradicts it.",
        body)


# --------------------------------------------------------------------
# 2. Privacy
# --------------------------------------------------------------------
def doc_privacy():
    body = f"""
  <h2>1. Who is responsible for your data</h2>
  <p>{v('legal_name')}, {v('city')}, {v('state')}, {v('country')} — the
  "Data Fiduciary" under India's Digital Personal Data Protection Act, 2023,
  and the "controller" under the UK and EU GDPR. Contact:
  {mailto('email_privacy')}.</p>

  <h2>2. The short version</h2>
  <p>We do not have a database of users, because we do not have users in the
  usual sense. There is no sign-up, no login, no profile and no analytics.
  For 94 of our 104 tools your file is read, processed and saved entirely by
  your own browser and is never transmitted anywhere.</p>

  <h2>3. Why there is no login</h2>
  <p>Every other site like this one asks you to create an account. We have
  decided not to, and it is a policy rather than a feature we have not got
  round to yet — so it is worth saying plainly why, and what you give up.</p>
  <p><strong>An account would be a database of you.</strong> The moment we
  ask for an email address we are holding personal data: something that
  identifies you, that has to be stored, secured, retained under a policy,
  disclosed on request, deleted on request, and reported if it leaks. Every
  promise on this page would become a promise about how well we run a
  database. Not having one is a stronger guarantee than any assurance we
  could give about how carefully we would run it.</p>
  <p><strong>We could not breach what we do not hold.</strong> Account
  databases are the single most common thing lost in a data breach, and the
  reason is arithmetic: they are the most valuable thing a file-tools site
  holds. There is no credential of yours here to steal, no email address to
  add to a list, and no record that you converted anything.</p>
  <p><strong>Logins exist to meter and to track.</strong> The usual reason a
  free file tool wants an account is to count your conversions so it can
  stop you at three and sell you the fourth, and to follow you between
  visits. Neither applies here. Your device does the processing, so a
  conversion costs us nothing and there is nothing to ration.</p>
  <p><strong>What you give up.</strong> Being honest about the trade: nothing
  syncs between your devices, there is no history of what you have processed,
  and your favourites and recent tools live in that browser on that machine
  only. Clear your site data and they are gone, with no way for us to restore
  them, because we never had a copy. If you use the site on a phone and a
  laptop, they will not know about each other. We think that is the right side
  of the trade for a tool you use for a minute at a time — but it is a real
  trade, and you should know about it rather than discover it.</p>
  <p><strong>Business API keys are the one exception</strong>, and only
  because a paid API cannot work otherwise. That is described in the
  <a href="terms.html">Terms</a> and the key is tied to a billing account,
  not to a person browsing the site.</p>

  <h2>4. What we never collect</h2>
  <ul>
    <li>Your files, their names, their contents or their metadata.</li>
    <li>Your name, email address or phone number — we never ask.</li>
    <li>Analytics, behavioural data, session recordings or heatmaps.</li>
    <li>Any identifier we could use to recognise you on a later visit.</li>
  </ul>

  <h2>5. What stays on your device</h2>
  <p>A few small values live in your browser's local storage so the app is
  useful across visits. They never leave your device and we cannot read them.
  Clearing your browser's site data removes them permanently. The full list is
  in the <a href="cookies.html">Cookies &amp; Advertising</a> page.</p>

  <h2>6. What other companies receive, and exactly when</h2>
  <p>This is the complete list. A test in our build pipeline fails if any host
  appears in our code that is not declared here, so this table cannot quietly
  go out of date.</p>
  <div class="table-scroll">
  <table>
    <thead><tr><th>Who</th><th>When</th><th>What they get</th></tr></thead>
    <tbody>
      <tr><td>Advertising partners</td><td>On information pages only — never in the tool, never while a file is being processed</td><td>Your IP address and browser user-agent, because any request over the internet reveals those, plus cookies they set themselves. See section 6.</td></tr>
      <tr><td>Exchange-rate provider</td><td>Only if you open the Currency Converter</td><td>Nothing but the request itself.</td></tr>
      <tr><td>AI model host</td><td>First use of an on-device AI tool, once</td><td>Nothing. The model downloads, caches, and then runs offline forever.</td></tr>
      <tr><td>Optional backend</td><td>Only if you use one of the 10 server-assisted tools</td><td>The file you deliberately submitted. These are clearly labelled in the interface.</td></tr>
      <tr><td>Cloudflare (our host)</td><td>Every page load</td><td>Standard server logs — IP, time, page. Unavoidable for any website that exists.</td></tr>
    </tbody>
  </table>
  </div>

  <h2>7. Advertising — what we do and honestly cannot do</h2>
  <p>{esc(BRAND)} is free, and adverts on the information pages are how it
  stays free. We want to be precise about this, because vague privacy claims
  are worse than none.</p>
  <p><strong>What we guarantee, and test:</strong></p>
  <ul>
    <li>Adverts never appear inside the tool workspace.</li>
    <li>No advert script is loaded, and no request of any kind is made, between
    the moment you choose a file and the moment your result is delivered.</li>
    <li>We pass no information about you to any advertising partner. We have
    none to pass.</li>
    <li>We do not sell or share personal information, in the sense the
    California CCPA/CPRA gives those words.</li>
  </ul>
  <p><strong>What we cannot honestly promise:</strong> an advertising partner
  whose advert is displayed on a page will see your IP address and browser
  user-agent, and will generally set its own cookie. That is a property of how
  the web works, not a choice we make, and no wording on this page could make
  it untrue. Where you live decides what happens next:</p>
  <div class="table-scroll">
  <table>
    <thead><tr><th>Where you are</th><th>What applies</th></tr></thead>
    <tbody>
      <tr><td>EU, EEA, UK, Switzerland</td><td>No advertising cookie is set until you agree through the consent banner. Refuse, and you get non-personalised adverts or none. You can change your mind at any time.</td></tr>
      <tr><td>California</td><td>We do not sell or share personal information. We honour the Global Privacy Control signal.</td></tr>
      <tr><td>India</td><td>Processing is limited to what advertising needs; your DPDP rights in section 7 apply.</td></tr>
      <tr><td>Everywhere else</td><td>Contextual advertising — matched to the page you are reading, not to you.</td></tr>
    </tbody>
  </table>
  </div>

  <h2>8. Your rights</h2>
  <p>You have these rights regardless of where you live; we do not ration them
  by geography. Write to {mailto('email_privacy')} and we will answer within
  30 days, and within 15 days for grievances filed under Indian rules.</p>
  <ul>
    <li><strong>Know</strong> what we hold about you and why.</li>
    <li><strong>Correct</strong> anything inaccurate.</li>
    <li><strong>Erase</strong> it.</li>
    <li><strong>Object to, or restrict,</strong> processing.</li>
    <li><strong>Withdraw consent</strong> you previously gave, as easily as you gave it.</li>
    <li><strong>Portability</strong> — a copy in a machine-readable form.</li>
    <li><strong>Nominate</strong> someone to exercise your rights if you die or become incapacitated (India, DPDP Act s.14).</li>
    <li><strong>Complain</strong> — see section 11.</li>
  </ul>
  <p>In practice the honest answer to most of these requests will be that we
  hold nothing about you. We will say so plainly, and explain how to verify it,
  rather than sending a form.</p>

  <h2>9. Children</h2>
  <p>{esc(BRAND)} is not directed at children. India's DPDP Act sets the
  highest bar of the laws that apply to us — verifiable parental consent for
  anyone under 18 — and we meet it the only way that is genuinely reliable: we
  collect no personal data from anyone, of any age. We do not knowingly process
  a child's data and we do not profile or target advertising at children.</p>

  <h2>10. Retention and international transfer</h2>
  <p>We retain nothing, so there is nothing to delete on a schedule and nothing
  to transfer across a border. Our host serves the site from a global network,
  which means the page itself may be delivered from a server near you — but no
  personal data of yours travels with it, because none was collected.</p>

  <h2>11. Complaints</h2>
  <p>Contact our Grievance Officer first — details and timelines on the
  <a href="grievance.html">Grievance Redressal</a> page. If you are not
  satisfied you may escalate to the Data Protection Board of India, or, in the
  EEA or UK, to your national supervisory authority. You do not need our
  permission to do either.</p>

  <h2>12. Changes</h2>
  <p>If this policy changes materially we will update the effective date above
  and describe what changed. We will not quietly broaden what we collect.</p>
"""
    return page(
        "privacy", f"Privacy Policy — {BRAND}",
        "PDF Love collects nothing: no accounts, no analytics, no uploads. What advertising partners receive, and your rights under DPDP, GDPR and CCPA.",
        "Privacy Policy",
        "We do not collect your files, your identity, or your behaviour. This "
        "page explains exactly what that means, and is candid about the one "
        "place third parties are involved.",
        body)


# --------------------------------------------------------------------
# 3. Terms
# --------------------------------------------------------------------
def doc_terms():
    body = f"""
  <h2>1. Who you are dealing with</h2>
  <p>{esc(BRAND)} is operated by {v('legal_name')}, an individual based in
  {v('city')}, {v('state')}, {v('country')} ("we", "us"). "Service" means the
  {esc(BRAND)} website, web app, desktop app, Android app and API. Using any of
  them means you accept these terms.</p>

  <h2>2. What the Service actually is</h2>
  <p>{esc(BRAND)} is a set of tools that run on your own device. We are not a
  file host, a storage provider or a conduit for anyone's content: for 94 of
  our 104 tools nothing you open ever reaches our servers. We mention this in
  the terms because it decides who is responsible for what.</p>

  <h2>3. Your files, and your responsibility</h2>
  <p>You keep every right in the files you process. We claim no licence over
  them — not out of generosity, but because we never receive them and could
  not claim rights in something we never hold.</p>
  <p>The other side of that is yours. <strong>You are solely responsible
  for:</strong></p>
  <ul>
    <li>having the legal right to process, edit, unlock or convert any file you use the Service on;</li>
    <li>the content of those files and any consequence of what you do with the results;</li>
    <li>checking the output before you rely on it — document conversion is imperfect by nature;</li>
    <li><strong>keeping your originals.</strong> The Service edits and downloads; it does not back anything up, and we cannot recover a file we never had.</li>
  </ul>
  <p>Because your files never reach us, we cannot inspect, moderate, restore or
  hand over your content — not for you, and not for anyone who asks us to.</p>

  <h2>4. Acceptable use</h2>
  <p>Do not use the Service to process material you have no right to process;
  to defeat encryption or access controls on documents that are not yours; to
  infringe intellectual-property or privacy rights; to disrupt the Service or
  circumvent API rate limits; or to break any law that applies to you.</p>

  <h2>5. Free, and no warranty</h2>
  <p>The on-device app is free, with no account and no usage limit. It is
  provided <strong>"as is" and "as available"</strong>, without warranties of
  any kind to the fullest extent the law permits — including any implied
  warranty of merchantability, fitness for a particular purpose, accuracy or
  uninterrupted availability.</p>

  <h2>6. Limitation of liability</h2>
  <p>To the fullest extent permitted by law, we are not liable for indirect,
  incidental, special or consequential loss, nor for lost data, lost profits or
  business interruption. Our total liability arising out of the Service in any
  twelve-month period is limited to the amount you actually paid us in that
  period — which, for the free app, is nil.</p>
  <p><strong>What that clause cannot do,</strong> stated plainly rather than
  buried: no contract can exclude liability that the law refuses to let anyone
  exclude. Your rights under the Indian Consumer Protection Act, 2019, our
  obligations as a Data Fiduciary under the DPDP Act, 2023, and liability under
  the GDPR where it applies to you, all survive everything in this section.
  Anyone claiming otherwise is writing an unenforceable clause.</p>

  <h2>7. Indemnity</h2>
  <p>If a third party brings a claim against us because of files you processed
  or your breach of section 4, you agree to cover our reasonable losses and
  legal costs in defending it.</p>

  <h2>8. Advertising</h2>
  <p>Information pages carry advertising, which is what keeps the tools free.
  Adverts never appear in the tool workspace and never load while a file is
  being processed. We do not endorse advertised products and are not
  responsible for them. See the <a href="cookies.html">Cookies &amp;
  Advertising</a> page.</p>

  <h2>9. Paid plans and licences</h2>
  <p>Paid API access is governed by the plan you buy. API keys belong to your
  organisation and must not be shared or resold without written agreement. We
  may suspend a key that exceeds its limits or breaches section 4, and we will
  tell you why. Refunds: see <a href="refund.html">Refunds</a>.</p>

  <h2>10. Open-source components</h2>
  <p>{esc(BRAND)} includes open-source software under its own licences,
  including AGPL-3 components in the optional backend. Those licences govern
  those components, and nothing here limits your rights under them.</p>

  <h2>11. Changes and ending</h2>
  <p>We may update these terms; the effective date above will change and
  continued use means acceptance. You may stop using the Service at any time —
  there is no account to close. The on-device app keeps working offline
  whatever happens to us, which is deliberate.</p>

  <h2>12. Governing law</h2>
  <p>These terms are governed by the laws of India, and the courts at
  {v('jurisdiction')} have exclusive jurisdiction. If you use the Service as a
  consumer elsewhere, this does not deprive you of any protection your local
  law gives you that cannot be contracted away.</p>

  <h2>13. Contact</h2>
  <p>{mailto('email_legal')}</p>
"""
    return page(
        "terms", f"Terms of Use — {BRAND}",
        "The terms for using PDF Love: free, as-is, and your files stay yours because they never reach us. Acceptable use, liability and governing law.",
        "Terms of Use",
        "Short, and readable. The unusual part is section 3: because your files "
        "never reach us, responsibility for them sits with you in a way that is "
        "architectural rather than merely contractual.",
        body)


# --------------------------------------------------------------------
# 4. Cookies & advertising
# --------------------------------------------------------------------
def doc_cookies():
    body = f"""
  <div class="note">
    <strong>We set no cookies of our own.</strong> Not one — not for
    analytics, not for sessions, not for preferences. There is no cookie
    banner outside Europe because outside Europe there is nothing of ours to
    consent to.
  </div>

  <h2>1. What we store on your device</h2>
  <p>The app keeps a few values in your browser's local storage. This is not a
  cookie: it is never attached to a network request and never sent anywhere.
  We cannot read it; only your browser can.</p>
  <div class="table-scroll">
  <table>
    <thead><tr><th>What</th><th>Why</th></tr></thead>
    <tbody>
      <tr><td>Pinned tools</td><td>Keeps your starred tools at the top.</td></tr>
      <tr><td>Recently used</td><td>Puts the last few tools you used within reach.</td></tr>
      <tr><td>Licence key</td><td>Only if you bought one, so you are not asked again.</td></tr>
      <tr><td>Backend address</td><td>Only if you configured your own self-hosted backend.</td></tr>
      <tr><td>Exchange rates</td><td>A short-lived cache, only if you used the Currency Converter.</td></tr>
    </tbody>
  </table>
  </div>
  <p>Clear it any time through your browser's "clear site data" or private
  browsing. Nothing breaks; the tools simply forget your preferences.</p>

  <h2>2. Advertising cookies</h2>
  <p>Advertising partners set their own cookies when an advert is displayed —
  typically to cap how often you see the same advert and to detect click
  fraud. These are theirs, not ours, and are governed by their policies.</p>
  <p><strong>Adverts never appear inside the tool workspace, and no advert
  script loads while a file is being processed.</strong> That is enforced in
  the code and verified by an automated test on every deploy, not merely
  promised here.</p>

  <h2>3. What happens where you are</h2>
  <div class="table-scroll">
  <table>
    <thead><tr><th>Where you are</th><th>What happens</th></tr></thead>
    <tbody>
      <tr><td>EU, EEA, UK, Switzerland</td><td>A consent banner appears before any advertising cookie is set, as the ePrivacy Directive and GDPR require. Decline and you still get the full tools — adverts become non-personalised or absent. Reopen the banner any time to change your answer.</td></tr>
      <tr><td>California</td><td>We do not sell or share personal information. We honour the Global Privacy Control browser signal automatically.</td></tr>
      <tr><td>Everywhere else</td><td>Contextual advertising, matched to the page rather than to you.</td></tr>
    </tbody>
  </table>
  </div>

  <h2>4. Refusing advertising cookies anywhere</h2>
  <ul>
    <li>Block third-party cookies in your browser settings — the tools are unaffected, because they use none.</li>
    <li>Turn on Global Privacy Control, which we honour.</li>
    <li>Use the ad networks' own opt-outs at
    <a href="https://optout.aboutads.info" rel="nofollow noopener">optout.aboutads.info</a> and
    <a href="https://youronlinechoices.eu" rel="nofollow noopener">youronlinechoices.eu</a>.</li>
    <li>Install the desktop or Android app, or use the site offline — with no
    connection there are no adverts at all, and every on-device tool still works.</li>
  </ul>

  <h2>5. Questions</h2>
  <p>{mailto('email_privacy')}</p>
"""
    return page(
        "cookies", f"Cookies & Advertising — {BRAND}",
        "PDF Love sets no cookies of its own. What we store locally, what advertising partners set, and how to refuse them wherever you live.",
        "Cookies & Advertising",
        "We set no cookies. This page explains the small amount we keep in your "
        "browser, what advertising partners do, and how to say no.",
        body)


# --------------------------------------------------------------------
# 5. Grievance redressal (India: IT Rules 2021 + DPDP)
# --------------------------------------------------------------------
def doc_grievance():
    body = f"""
  <h2>Why this page exists</h2>
  <p>Rule 3(2) of India's Information Technology (Intermediary Guidelines and
  Digital Media Ethics Code) Rules, 2021 requires a named Grievance Officer
  with working contact details and published timelines. The Digital Personal
  Data Protection Act, 2023 and the DPDP Rules, 2025 require a readily
  available way to raise a complaint about personal data. This page is both.</p>

  <h2>Grievance Officer</h2>
  <div class="card">
    <p style="margin:0;">
      <strong>{v('grievance_officer')}</strong><br>
      Grievance Officer, {esc(BRAND)}<br>
      {v('city')}, {v('state')}, {v('country')}<br>
      {mailto('email_grievance')}
    </p>
  </div>
  <p class="meta">Full postal address supplied on request — as a sole
  individual operator rather than a registered company, we publish the city and
  state and give the street address to anyone with a genuine need for it.</p>

  <h2>What you can raise</h2>
  <ul>
    <li>Anything about your personal data, including a request to know, correct or erase it.</li>
    <li>Content on this site you believe is unlawful, infringing or wrong.</li>
    <li>An advert you saw here that was misleading, offensive or malicious — we
    want to know; a bad advert is our problem to fix, not yours to tolerate.</li>
    <li>Anything the Service did that you believe it should not have.</li>
  </ul>

  <h2>How to file, and what happens</h2>
  <p>Email {mailto('email_grievance')} with enough detail to identify the
  problem — the page or tool involved, what happened, and what you would like
  done. You do not need a lawyer, a form or any particular wording.</p>
  <div class="table-scroll">
  <table>
    <thead><tr><th>Stage</th><th>Within</th></tr></thead>
    <tbody>
      <tr><td>We acknowledge your complaint</td><td>24 hours</td></tr>
      <tr><td>We resolve it and tell you what we did</td><td>15 days</td></tr>
      <tr><td>Requests to remove certain unlawful content</td><td>As required by the applicable rule, and faster where the law says so</td></tr>
    </tbody>
  </table>
  </div>
  <p>If we cannot do what you asked, we will say so and explain why, rather
  than letting the clock run out.</p>

  <h2>If we do not satisfy you</h2>
  <p>You are entitled to escalate, and you do not need our agreement:</p>
  <ul>
    <li><strong>India</strong> — the Data Protection Board of India, for
    complaints about personal data under the DPDP Act, 2023.</li>
    <li><strong>EEA or UK</strong> — your national data protection supervisory
    authority.</li>
    <li><strong>Elsewhere</strong> — your local consumer or data protection
    regulator. Ask us and we will point you to the right one.</li>
  </ul>
"""
    return page(
        "grievance", f"Grievance Redressal — {BRAND}",
        "How to complain to PDF Love and how quickly we must answer: named Grievance Officer, 24-hour acknowledgement, 15-day resolution, and how to escalate.",
        "Grievance Redressal",
        "A named person, a working address, and published deadlines — as India's "
        "IT Rules 2021 and the DPDP Act require. Escalation routes included, "
        "because you should not have to ask us for them.",
        body)


# --------------------------------------------------------------------
# 6. Refunds
# --------------------------------------------------------------------
def doc_refund():
    body = f"""
  <div class="note">
    The app is free and involves no payment, so none of this applies to it.
    This page covers the Business API and site licences only.
  </div>

  <h2>Cooling-off period</h2>
  <p>A new API subscription can be cancelled for a full refund within 14 days
  of the first payment, provided usage has stayed under 1,000 requests. Ask via
  {mailto('email_billing')} and we will return it to the original payment
  method within 10 business days.</p>

  <h2>Cancelling</h2>
  <p>Cancel whenever you like. Your plan runs to the end of the period you have
  already paid for and then stops. We do not pro-rate part-months, and we do
  not bill you again after you cancel.</p>

  <h2>Renewals</h2>
  <p>We email the billing contact before any renewal charge, in time to cancel.
  A renewal you were not warned about is refundable in full — tell us and we
  will fix it without argument.</p>

  <h2>If something is broken</h2>
  <p>If the API materially fails to do what we said it does and we cannot fix
  it in reasonable time, you get a pro-rata refund for the unused period. This
  is separate from the cooling-off period and is not time-limited.</p>

  <h2>Your statutory rights</h2>
  <p>Nothing here reduces rights you have under the Indian Consumer Protection
  Act, 2019, or under consumer law where you live. Where those give you more
  than this page does, they win.</p>

  <h2>Contact</h2>
  <p>{mailto('email_billing')}</p>
"""
    return page(
        "refund", f"Refund & Cancellation Policy — {BRAND}",
        "Refund and cancellation terms for PDF Love paid API plans: 14-day cooling-off, how to cancel, renewals, and your statutory rights.",
        "Refund & Cancellation Policy",
        "For paid API plans. The app itself is free, so most people will never "
        "need this page.",
        body)


# --------------------------------------------------------------------
# 7. Security
# --------------------------------------------------------------------
def doc_security():
    body = f"""
  <h2>The on-device guarantee, stated precisely</h2>
  <p>On-device tools read your file with the browser's File API, process it in
  page memory, and hand the result to the browser's download mechanism. No
  network request carries file contents or filenames. This is verifiable: pick
  a file and watch the Network tab — nothing fires while it is being
  processed.</p>
  <p>We word it this way deliberately. "We don't store your files" is a promise
  about someone's conduct. "Your file is never transmitted" is a property of
  the system that you can check for yourself, and that an automated test checks
  on every deploy.</p>

  <h2>Every request the app can make</h2>
  <p>This is the complete list, and it is enforced: a build check fails if any
  host appears in the code that is not declared here.</p>
  <div class="table-scroll">
  <table>
    <thead><tr><th>Request</th><th>When</th><th>What it carries</th></tr></thead>
    <tbody>
      <tr><td>Advertising</td><td>Information pages only, never in a tool and never during processing</td><td>Your IP and user-agent, plus the partner's own cookies. See <a href="cookies.html">Cookies &amp; Advertising</a>.</td></tr>
      <tr><td>Desktop update check</td><td>Desktop app launch</td><td>A version string out; a signed manifest back. No telemetry.</td></tr>
      <tr><td>Exchange rates</td><td>Only when you open the Currency Converter</td><td>Nothing but the request itself.</td></tr>
      <tr><td>AI model download</td><td>First use of an on-device AI tool</td><td>Nothing. Cached afterwards, then fully offline.</td></tr>
      <tr><td>Server-assisted tools</td><td>Only if you use one of the 10, and only with a backend configured</td><td>The file you explicitly submitted, to a backend you or we run.</td></tr>
    </tbody>
  </table>
  </div>
  <p><strong>{esc(BRAND)} itself sends nothing.</strong> There is no analytics,
  no telemetry and no "which platform is this user on" ping — not even for
  advertising. An advert network already sees the user-agent and IP when it
  serves an advert, so there is nothing for us to add and no reason to weaken
  the claim.</p>

  <h2>Where the guarantee does not apply</h2>
  <p>Honesty matters more than a clean claim:</p>
  <ul>
    <li><strong>Server-assisted tools</strong> (10 of 104) do transmit the file
    you submit. They appear only when a backend is reachable and are labelled
    in the interface. That backend logs no file contents or filenames and
    deletes per-request temporary files as soon as the response is built. In
    the desktop app that "backend" is on your own machine, bound to loopback.</li>
    <li><strong>Currency converter</strong> requests live rates. No file or
    personal data is sent; as with any request, your IP is visible to that
    provider.</li>
    <li><strong>On-device AI models</strong> download once from a public model
    host, then run offline from cache.</li>
  </ul>

  <h2>Application security</h2>
  <ul>
    <li>Strict Content-Security-Policy. Every library is served from our own
    origin; the tool pages depend on no third-party script.</li>
    <li><code>object-src 'none'</code>, <code>frame-ancestors 'none'</code>,
    <code>X-Frame-Options: DENY</code>, <code>nosniff</code>.</li>
    <li>Encryption uses qpdf compiled to WebAssembly — real AES-256, not an
    obfuscation trick.</li>
    <li>The optional backend runs as a non-root user with
    <code>no-new-privileges</code>, per-endpoint rate limits and a request size cap.</li>
    <li>Page rendering is capped at 8192px to blunt decompression-bomb inputs,
    and heavy tools estimate memory before starting.</li>
  </ul>

  <h2>Reporting a vulnerability</h2>
  <p>Email {mailto('email_security')} with enough detail to reproduce. Please
  give us a reasonable window to ship a fix before publishing.</p>
  <p>In return: we will acknowledge within 3 business days, keep you updated,
  credit you if you would like, and we will not pursue legal action over
  good-faith research that respects user privacy and does not degrade the
  service for others.</p>
  <p>Out of scope: reports produced solely by automated scanners with no
  demonstrated impact, and anything that requires an already-compromised
  device.</p>
"""
    return page(
        "security", f"Security & the on-device guarantee — {BRAND}",
        "PDF Love's security model: why there is no server to breach, every request the app can make, and how to report a vulnerability.",
        "Security",
        "The architecture is the security story: for 94 of 104 tools there is no "
        "server to breach, because your file never reaches one.",
        body)


DOCS = {
    "legal": doc_legal,
    "privacy": doc_privacy,
    "terms": doc_terms,
    "cookies": doc_cookies,
    "grievance": doc_grievance,
    "refund": doc_refund,
    "security": doc_security,
}


# The marketing pages (about, contact, pricing, for-business, index) are
# hand-written — they carry real prose that no generator should own. But they
# repeat the operator's identity in the footer and the contact block, so they
# read from the same OPERATOR dict via a one-way substitution. Idempotent:
# once a token is replaced there is nothing left to match.
HANDWRITTEN = ["about.html", "contact.html", "for-business.html",
               "index.html", "pricing.html"]

# The scaffolding warning box that told the author to fill placeholders in.
# It must never reach production, so it is removed in the same pass that
# makes the placeholders unnecessary.
PLACEHOLDER_DIV = re.compile(
    r'\s*<div class="placeholder">.*?</div>\s*', re.DOTALL)


def patch_handwritten():
    tokens = {
        "[COMPANY LEGAL NAME]": OPERATOR["legal_name"],
        "[SUPPORT@YOURDOMAIN]": OPERATOR["email_support"],
        # A sole operator has no separate sales desk; pretending otherwise
        # means an address that nobody reads.
        "[SALES@YOURDOMAIN]": OPERATOR["email_support"],
        "[SECURITY@YOURDOMAIN]": OPERATOR["email_security"],
        "[STREET ADDRESS]": f'{OPERATOR["city"]}, {OPERATOR["state"]}',
        "[COUNTRY]": OPERATOR["country"],
    }
    patched = []
    for name in HANDWRITTEN:
        path = os.path.join(OUT_DIR, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            original = f.read()
        text = original
        for token, value in tokens.items():
            text = text.replace(token, html.escape(str(value)))
        text = PLACEHOLDER_DIV.sub("\n\n", text)
        if text != original:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            patched.append(name)
    return patched


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for slug, fn in DOCS.items():
        with open(os.path.join(OUT_DIR, slug + ".html"), "w", encoding="utf-8") as f:
            f.write(fn())
    print(f"wrote {len(DOCS)} legal page(s) into frontend/company/")

    missing = [k for k, val in OPERATOR.items() if val is None]
    if missing:
        # Deliberately do NOT touch the hand-written pages while details are
        # missing: writing a TO-BE-COMPLETED marker over [COMPANY LEGAL NAME]
        # would destroy the token this function matches on, so the second run
        # could never fix it.
        print("\n  NOT PUBLISHABLE YET — OPERATOR details still missing:")
        for m in missing:
            print(f"    - {m}")
        print("\n  Fill them in at the top of this file and re-run."
              "\n  scripts/check-legal.py fails the build until then.")
        return

    patched = patch_handwritten()
    if patched:
        print(f"patched operator details into {len(patched)} hand-written "
              f"page(s): {', '.join(patched)}")


if __name__ == "__main__":
    main()
