import streamlit as st
import requests, pandas as pd, datetime as dt, time

st.set_page_config(page_title='FOXK NBA Stat Lab',page_icon='🏀',layout='wide')
# FOXK Whop VIP gate — runs before any research data is fetched.
import base64, hashlib, secrets, threading, urllib.parse

FOXK_JOIN = "https://whop.com/discord-gg-50b0/foxk-vip-picks/"
FOXK_DISCORD = "https://discord.gg/fX3BpQ5T6"
FOXK_OAUTH = "https://api.whop.com/oauth"

# OAuth state carries a signed, short-lived PKCE verifier across the browser redirect.
# The signature prevents tampering without relying on process-local memory.
import hmac, json, logging, re
FOXK_LOG = logging.getLogger("foxk.auth")

def foxk_state_create(cfg, verifier):
    payload = {"v": verifier, "t": int(time.time()), "r": foxk_b64(secrets.token_bytes(16))}
    encoded = foxk_b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = foxk_b64(hmac.new(cfg["client_secret"].encode(), encoded.encode(), hashlib.sha256).digest())
    return encoded + "." + signature

def foxk_state_verify(cfg, state):
    if not isinstance(state, str) or len(state) > 1500 or "." not in state:
        raise ValueError("Missing or malformed OAuth state")
    encoded, signature = state.split(".", 1)
    expected = foxk_b64(hmac.new(cfg["client_secret"].encode(), encoded.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise ValueError("OAuth state signature mismatch")
    payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
    age = time.time() - int(payload["t"])
    if age < 0 or age > 600 or not isinstance(payload.get("v"), str):
        raise ValueError("OAuth state expired")
    return payload["v"]

def foxk_b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def foxk_config():
    try:
        cfg = st.secrets["whop"]
        return {k: str(cfg[k]).strip() for k in ("client_id", "client_secret", "product_id", "redirect_uri")}, str(cfg.get("api_key", "")).strip(), str(cfg.get("company_id", "biz_jiBiHn3QVytpcB")).strip()
    except (KeyError, FileNotFoundError):
        return None, "", ""

def foxk_login_url(cfg):
    verifier = foxk_b64(secrets.token_bytes(48))
    challenge = foxk_b64(hashlib.sha256(verifier.encode()).digest())
    state = foxk_state_create(cfg, verifier)
    params = {
        "response_type": "code", "client_id": cfg["client_id"],
        "redirect_uri": cfg["redirect_uri"], "scope": "openid profile email",
        "state": state, "nonce": foxk_b64(secrets.token_bytes(24)),
        "code_challenge": challenge, "code_challenge_method": "S256",
    }
    return FOXK_OAUTH + "/authorize?" + urllib.parse.urlencode(params)

def foxk_token_exchange(cfg, code, verifier):
    # Keep all secrets and authorization codes server-side.
    # Whop documents a JSON body with PKCE and no secret, but an app configured as a
    # confidential client may require its secret. Try the documented form first and
    # only fall back when Whop answers 401 invalid_client (client auth is checked
    # before the code is redeemed, so the code is still usable for the next try).
    import re
    base = {"grant_type": "authorization_code", "code": code,
            "redirect_uri": cfg["redirect_uri"], "client_id": cfg["client_id"],
            "code_verifier": verifier}
    attempts = [
        ("json-pkce", {"json": dict(base)}),
        ("json-secret", {"json": dict(base, client_secret=cfg["client_secret"])}),
        ("basic-auth", {"data": {k: v for k, v in base.items() if k != "client_id"},
                        "auth": (cfg["client_id"], cfg["client_secret"])}),
    ]
    response = None
    error_type = "unavailable"
    for name, kwargs in attempts:
        response = requests.post(FOXK_OAUTH + "/token", headers={"Accept": "application/json"},
                                 timeout=15, **kwargs)
        if response.ok:
            FOXK_LOG.info("Whop token exchange succeeded via %s", name)
            break
        # Whitelist OAuth error identifiers; NEVER print response text,
        # full URLs, tokens, request data, or exception messages.
        error_type = "unavailable"
        try:
            payload = response.json()
            if isinstance(payload, dict):
                candidate = payload.get("error")
                if isinstance(candidate, str) and re.fullmatch(r"[A-Za-z_]{1,60}", candidate):
                    error_type = candidate
        except (ValueError, TypeError):
            pass
        FOXK_LOG.error("Whop token exchange (%s): HTTP %s; OAuth error=%s; response_type=%s",
                       name, response.status_code, error_type,
                       response.headers.get("Content-Type", "unknown").split(";")[0][:40])
        if not (response.status_code == 401 and error_type == "invalid_client"):
