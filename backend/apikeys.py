"""
apikeys — signed API keys for the business tier.

Design constraints, in order of importance:

  1. **The on-device app is never gated.** Everything in frontend/ runs
     without a key and always will. This module governs the HTTP API only.
  2. **A self-hosted backend is never gated either.** Someone running their
     own instance owns it; requiring a key from us would be absurd. Key
     enforcement is opt-in via REQUIRE_API_KEY=1, which is what *our* hosted
     deployment sets.
  3. **Verification is offline.** A key is a signed statement, checked
     against a public key. There is no database lookup and no call to a
     licence server on the request path, so the API works air-gapped and a
     key check costs microseconds.

Key format — the same scheme as licensing/mint.js, so there is one signing
identity for the whole product rather than two:

    dkb_live_<base64url(payload)>.<base64url(ECDSA-P256-SHA256 signature)>

The signature covers the base64url payload string exactly as transmitted.
Payload fields:

    sub      customer identifier (used as the rate-limit bucket)
    tier     plan name, e.g. "business"
    quota    requests/month, informational here; enforced by the limiter
    issued   YYYY-MM-DD
    expires  YYYY-MM-DD, or null for no expiry

Configure with either:
    DOCKBENCH_API_PUBLIC_KEY       the public JWK, inline as JSON
    DOCKBENCH_API_PUBLIC_KEY_FILE  path to a public-key.json
"""

import base64
import json
import logging
import os
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger("dockbench.apikeys")

KEY_PREFIX = "dkb_live_"

# Opt-in. Off by default so self-hosted and desktop deployments are open.
REQUIRE_API_KEY = os.environ.get("REQUIRE_API_KEY") == "1"

# Set by the desktop app's bundled engine, which is loopback-only and
# guarded by its own per-session token. Never gate that.
LOCAL_MODE = os.environ.get("DOCKBENCH_LOCAL") == "1"


class ApiKeyError(Exception):
    """Raised when a key is missing, malformed, expired or unsigned."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _load_public_key():
    """Import the verifying key from a JWK, or return None if unconfigured."""
    raw = os.environ.get("DOCKBENCH_API_PUBLIC_KEY")
    if not raw:
        path = os.environ.get("DOCKBENCH_API_PUBLIC_KEY_FILE")
        if path and os.path.isfile(path):
            with open(path) as f:
                raw = f.read()
    if not raw:
        return None

    try:
        jwk = json.loads(raw)
        from cryptography.hazmat.primitives.asymmetric import ec

        # JWK P-256: x and y are base64url big-endian coordinates.
        x = int.from_bytes(_b64url_decode(jwk["x"]), "big")
        y = int.from_bytes(_b64url_decode(jwk["y"]), "big")
        return ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()
    except Exception as e:
        logger.error("Could not load API public key: %s", e)
        return None


_public_key = _load_public_key()

if REQUIRE_API_KEY and _public_key is None:
    # Failing loudly here beats silently accepting every request on a
    # deployment that believes it is protected.
    raise RuntimeError(
        "REQUIRE_API_KEY=1 but no verifying key is configured. Set "
        "DOCKBENCH_API_PUBLIC_KEY (inline JWK) or DOCKBENCH_API_PUBLIC_KEY_FILE."
    )


def enabled() -> bool:
    """True when requests must carry a valid key."""
    return REQUIRE_API_KEY and not LOCAL_MODE


def verify(key: str) -> dict:
    """Validate an API key and return its payload. Raises ApiKeyError."""
    if _public_key is None:
        raise ApiKeyError(503, "API key verification is not configured on this server.")

    if not key.startswith(KEY_PREFIX):
        raise ApiKeyError(401, "Malformed API key.")
    body = key[len(KEY_PREFIX):]

    if body.count(".") != 1:
        raise ApiKeyError(401, "Malformed API key.")
    payload_b64, sig_b64 = body.split(".")

    try:
        signature = _b64url_decode(sig_b64)
        payload_raw = _b64url_decode(payload_b64)
    except Exception:
        raise ApiKeyError(401, "Malformed API key.")

    # Verify before trusting anything inside the payload.
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils

    try:
        # WebCrypto ECDSA emits raw r||s; cryptography expects DER.
        if len(signature) != 64:
            raise ApiKeyError(401, "Invalid API key signature.")
        r = int.from_bytes(signature[:32], "big")
        s = int.from_bytes(signature[32:], "big")
        der = asym_utils.encode_dss_signature(r, s)
        _public_key.verify(der, payload_b64.encode(), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise ApiKeyError(401, "Invalid API key signature.")
    except ApiKeyError:
        raise
    except Exception:
        raise ApiKeyError(401, "Invalid API key.")

    try:
        payload = json.loads(payload_raw)
    except Exception:
        raise ApiKeyError(401, "Malformed API key payload.")

    expires = payload.get("expires")
    if expires:
        try:
            exp = datetime.strptime(expires, "%Y-%m-%d").date()
        except ValueError:
            raise ApiKeyError(401, "Malformed expiry in API key.")
        if exp < date.today():
            raise ApiKeyError(401, f"API key expired on {expires}.")

    if not payload.get("sub"):
        raise ApiKeyError(401, "API key is missing a subject.")

    return payload


def subject_from_request(headers) -> Optional[str]:
    """Return the key's subject for rate-limiting, or None when unkeyed.

    Never raises — the limiter runs before authentication and must not be
    the thing that rejects a bad key.
    """
    auth = headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    try:
        return verify(auth[7:].strip()).get("sub")
    except ApiKeyError:
        return None
