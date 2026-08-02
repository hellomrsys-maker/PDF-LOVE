#!/usr/bin/env node
/**
 * Generates the ECDSA P-256 keypair for PDFLove's offline license system.
 * Run this ONCE, on your own machine, entirely offline if you like — it
 * touches no network.
 *
 * Usage:  node licensing/keygen.js
 *
 * Produces two files in this directory:
 *   private-key.json  — KEEP THIS SECRET. Never commit it, never share it,
 *                        back it up somewhere safe. Anyone who has it can
 *                        mint valid license keys for your app.
 *   public-key.json    — Safe to share/commit. This is what gets pasted
 *                        into frontend/index.html (LICENSE_PUBLIC_KEY_JWK)
 *                        so the app can verify licenses entirely offline.
 *
 * If private-key.json already exists, this script refuses to overwrite it
 * (regenerating would invalidate every license key you've already sold).
 */
const fs = require('fs');
const path = require('path');
const { webcrypto } = require('crypto');

const DIR = __dirname;
const PRIVATE_PATH = path.join(DIR, 'private-key.json');
const PUBLIC_PATH = path.join(DIR, 'public-key.json');

async function main() {
  if (fs.existsSync(PRIVATE_PATH)) {
    console.error(`Refusing to overwrite existing ${PRIVATE_PATH}.`);
    console.error('Delete it yourself first if you really want a fresh keypair —');
    console.error('but every license key you already sold would stop verifying.');
    process.exit(1);
  }

  const keyPair = await webcrypto.subtle.generateKey(
    { name: 'ECDSA', namedCurve: 'P-256' },
    true,
    ['sign', 'verify']
  );

  const privateJwk = await webcrypto.subtle.exportKey('jwk', keyPair.privateKey);
  const publicJwk = await webcrypto.subtle.exportKey('jwk', keyPair.publicKey);

  fs.writeFileSync(PRIVATE_PATH, JSON.stringify(privateJwk, null, 2));
  fs.writeFileSync(PUBLIC_PATH, JSON.stringify(publicJwk, null, 2));

  console.log('Generated:');
  console.log('  ' + PRIVATE_PATH + '  (SECRET — .gitignore already excludes this)');
  console.log('  ' + PUBLIC_PATH + '   (safe to commit)');
  console.log('');
  console.log('Next steps:');
  console.log('1. Back up private-key.json somewhere safe (password manager, offline drive).');
  console.log('   If you lose it, you can never mint a valid license again with this identity.');
  console.log('2. Copy the contents of public-key.json into frontend/index.html,');
  console.log('   replacing:  const LICENSE_PUBLIC_KEY_JWK = null;');
  console.log('3. Mint your first license:  node licensing/mint.js --tier=offline-pro --licensee="Test"');
}

main().catch(e => { console.error(e); process.exit(1); });
