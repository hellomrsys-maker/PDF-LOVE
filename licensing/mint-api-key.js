#!/usr/bin/env node
/**
 * Mints a signed API key for a business customer.
 *
 * Uses the SAME private-key.json as mint.js, so there is one signing
 * identity for the whole product rather than two to keep track of. Run it
 * on your own machine; it touches no network and the private key never has
 * to leave this directory.
 *
 * Usage:
 *   node licensing/mint-api-key.js --sub="acme-corp" [--tier=business] \
 *        [--quota=50000] [--expires=2027-12-31]
 *
 * Hand the printed key to the customer. The backend verifies it offline
 * against the public key in DOCKBENCH_API_PUBLIC_KEY — no database lookup
 * and no licence server on the request path, so it works air-gapped.
 *
 * To revoke before expiry you need a deny-list on the server; signature
 * verification alone cannot un-issue a key. Short --expires values with
 * periodic reissue are the simpler answer for most customers.
 */
const fs = require('fs');
const path = require('path');
const { webcrypto } = require('crypto');

const PRIVATE_PATH = path.join(__dirname, 'private-key.json');

function parseArgs(argv) {
  const out = {};
  for (const arg of argv) {
    const m = arg.match(/^--([\w-]+)=(.*)$/);
    if (m) out[m[1]] = m[2];
  }
  return out;
}

function b64url(bytes) {
  return Buffer.from(bytes).toString('base64')
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

async function main() {
  if (!fs.existsSync(PRIVATE_PATH)) {
    console.error(`No private key found at ${PRIVATE_PATH}.`);
    console.error('Run `node licensing/keygen.js` first.');
    process.exit(1);
  }
  const args = parseArgs(process.argv.slice(2));
  if (!args.sub) {
    console.error('Required: --sub=<customer-id>   (e.g. acme-corp)');
    console.error('Optional: --tier=business --quota=50000 --expires=YYYY-MM-DD');
    process.exit(1);
  }
  if (args.expires && !/^\d{4}-\d{2}-\d{2}$/.test(args.expires)) {
    console.error('--expires must be YYYY-MM-DD');
    process.exit(1);
  }

  const privateJwk = JSON.parse(fs.readFileSync(PRIVATE_PATH, 'utf8'));
  const privateKey = await webcrypto.subtle.importKey(
    'jwk', privateJwk, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']
  );

  const payload = {
    sub: args.sub,
    tier: args.tier || 'business',
    quota: args.quota ? parseInt(args.quota, 10) : null,
    issued: new Date().toISOString().slice(0, 10),
    expires: args.expires || null,   // null = no expiry
  };

  const payloadB64 = b64url(Buffer.from(JSON.stringify(payload), 'utf8'));
  const signature = await webcrypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    privateKey,
    Buffer.from(payloadB64, 'utf8')
  );
  const apiKey = 'dkb_live_' + payloadB64 + '.' + b64url(signature);

  console.log('Payload:', JSON.stringify(payload, null, 2));
  console.log('');
  console.log('API key (give this to the customer — it cannot be recovered later):');
  console.log(apiKey);
  console.log('');
  console.log('The customer sends it as:');
  console.log('  Authorization: Bearer ' + apiKey.slice(0, 32) + '...');
}

main().catch(e => { console.error(e); process.exit(1); });
