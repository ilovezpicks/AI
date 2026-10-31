import streamlit as st
import requests, pandas as pd, datetime as dt, time
import altair as alt

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
            break
    if not response.ok:
        # Raise a generic exception so requests never embeds request URL details.
        raise ValueError("Whop rejected token exchange (HTTP %s, %s)" %
                         (response.status_code, error_type))
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
        raise ValueError("Whop token response missing access token")
    return payload

def foxk_userinfo(access_token):
    response = requests.get(FOXK_OAUTH + "/userinfo", headers={
        "Authorization": "Bearer " + access_token,
    }, timeout=15)
    response.raise_for_status()
    data = response.json()
    if not str(data.get("sub", "")).startswith("user_"):
        raise ValueError("Whop did not return a valid user identity")
    return data

def foxk_active_member(api_key, company_id, user_id, product_id):
    # API key is server-side and must have member:basic:read and member:email:read.
    # Explicitly recheck the returned user, product and status, regardless of filters.
    cursor = None
    for _ in range(15):
        params = {"account_id": company_id, "user_ids[]": user_id,
                  "product_ids[]": product_id, "first": 50}
        if cursor:
            params["after"] = cursor
        response = requests.get("https://api.whop.com/api/v1/memberships",
            params=params, headers={"Authorization": "Bearer " + api_key}, timeout=15)
        response.raise_for_status()
        payload = response.json()
        for membership in payload.get("data", []):
            if (membership.get("user") or {}).get("id") != user_id:
                continue
            if (membership.get("product") or {}).get("id") != product_id:
                continue
            if membership.get("status") != "active":
                continue
            return True
        page = payload.get("page_info") or {}
        if not page.get("has_next_page"):
            return False
        cursor = page.get("end_cursor")
        if not cursor:
            raise ValueError("Membership results were incomplete")
    raise ValueError("Membership results exceeded the pagination safety limit")

def foxk_gate():
    cfg, api_key, company_id = foxk_config()
    st.markdown("""<style>
    .foxk-login{background:#191e23;border:1px solid #353b43;border-radius:14px;padding:30px;margin:30px auto;max-width:680px}
    .foxk-login h2{color:#fff!important}.foxk-login p{color:#bac2ca!important}
    .foxk-login a{color:#f39a62!important}
    </style>""", unsafe_allow_html=True)
    if not cfg or not api_key:
        st.title("FOXK / VIP ACCESS")
        st.error("VIP verification is not fully configured yet. The research dashboard is locked until the Whop membership API key is added in Streamlit Secrets.")
        st.markdown(f"[Join the free Discord]({FOXK_DISCORD})")
        st.stop()
    def _safe(s):
        return re.sub(r"[^A-Za-z0-9_ .:-]", "", str(s))[:120]

    err = st.query_params.get("error")
    code = st.query_params.get("code")
    state = st.query_params.get("state")
    if err:
        FOXK_LOG.error("Whop OAuth error=%s description=%s", _safe(err),
                       _safe(st.query_params.get("error_description", "")))
        st.query_params.clear()
        st.warning(f"Whop sign-in could not be completed ({_safe(err)}). Please try again.")
    elif code or state:
        # Clear authorization code from the address bar before rendering the app.
        st.query_params.clear()
        try:
            if not isinstance(code, str):
                raise ValueError("OAuth callback missing code")
            verifier = foxk_state_verify(cfg, state)
        except (ValueError, KeyError, TypeError) as exc:
            FOXK_LOG.warning("OAuth callback state rejected: %s: %s", type(exc).__name__, exc)
            st.error("Sign-in expired or failed security validation. Please try again.")
            st.stop()
        try:
            tokens = foxk_token_exchange(cfg, code, verifier)
            access = tokens["access_token"]
            identity = foxk_userinfo(access)
            st.session_state["foxk_whop_user"] = identity["sub"]
            st.session_state["foxk_whop_access"] = access
            st.session_state["foxk_whop_expires"] = time.time() + min(int(tokens.get("expires_in", 3600)), 3600)
        except (requests.RequestException, KeyError, ValueError, TypeError) as exc:
            FOXK_LOG.error("OAuth callback failed: %s", type(exc).__name__)
            detail = str(exc) if isinstance(exc, ValueError) and str(exc).startswith("Whop ") else ""
            st.error(("Whop sign-in could not be verified. " + detail).strip())
            st.stop()
    user = st.session_state.get("foxk_whop_user")
    access = st.session_state.get("foxk_whop_access")
    if user and access and time.time() < st.session_state.get("foxk_whop_expires", 0) - 30:
        try:
            # Never trust the stored user ID without validating the OAuth token.
            identity = foxk_userinfo(access)
            if identity["sub"] != user:
                raise ValueError("Whop identity changed")
            # Owner bypass is valid only for the verified Whop user ID configured
            # privately in Streamlit Secrets, never a query parameter or username.
            owner_id = str(st.secrets["whop"].get("owner_user_id", "")).strip()
            allowed = (bool(owner_id) and user == owner_id) or foxk_active_member(api_key, company_id, user, cfg["product_id"])
        except (requests.RequestException, ValueError, KeyError):
            st.error("We could not verify your VIP membership right now. Access is temporarily locked. Please retry shortly.")
            st.stop()
        if allowed:
            with st.sidebar:
                st.caption("FOXK VIP · Verified with Whop")
                if st.button("Sign out", key="foxk_whop_signout"):
                    for key in ("foxk_whop_user", "foxk_whop_access", "foxk_whop_expires"):
                        st.session_state.pop(key, None)
                    st.rerun()
            return
        st.markdown("<div class='foxk-login'><h2>FOXK VIP membership required</h2><p>Your Whop account does not currently have an active FOXK VIP PICKS membership. The Stat Lab remains locked.</p></div>", unsafe_allow_html=True)
        st.link_button("Get FOXK VIP", FOXK_JOIN, type="primary")
        st.link_button("Join free Discord", FOXK_DISCORD)
        if st.button("Sign in with a different Whop account"):
            for key in ("foxk_whop_user", "foxk_whop_access", "foxk_whop_expires"):
                st.session_state.pop(key, None)
            st.rerun()
        st.stop()
    for key in ("foxk_whop_user", "foxk_whop_access", "foxk_whop_expires"):
        st.session_state.pop(key, None)
    st.markdown("<div class='foxk-login'><h2>FOXK / NBA STAT LAB</h2><p>Premium NBA research, exclusively for active FOXK VIP PICKS subscribers.</p><p>Sign in with Whop to verify your membership. Free Discord members can still join the community.</p></div>", unsafe_allow_html=True)
    st.link_button("Sign in with Whop", foxk_login_url(cfg), type="primary")
    st.link_button("Get FOXK VIP", FOXK_JOIN)
    st.link_button("Join free Discord", FOXK_DISCORD)
    st.stop()

from foxk_auth import require_vip

require_vip()

st.markdown('\n<style>\n#MainMenu,footer{visibility:hidden}\n[data-testid="stHeader"]{background:#101316!important;height:3rem}\n.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#101316!important;color:#f0f1f2!important}\n.block-container{max-width:1320px!important;padding-top:1.6rem!important;padding-bottom:4rem!important}\nh1,h2,h3{font-family:Arial,Helvetica,sans-serif!important;letter-spacing:-.035em!important;color:#f4f5f6!important}\nh1{font-size:2.2rem!important;font-weight:800!important;margin-bottom:.1rem!important}\nh2{font-size:1.6rem!important}\np,li,label,span{line-height:1.5}\n[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p{color:#aab2bb!important;opacity:1!important}\n[data-testid="stSidebar"]{background:#191d21!important;border-right:1px solid #343a40!important}\n[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,[data-testid="stSidebar"] p,[data-testid="stSidebar"] label{color:#f0f1f2!important}\n[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p{color:#d5d9dd!important;font-weight:600!important}\n[data-testid="stSidebar"] input{color:#f0f1f2!important;background:#262b30!important}\n[data-testid="stSidebar"] input::placeholder{color:#a6b0ba!important;opacity:1!important}\n[data-baseweb="select"]>div,[data-baseweb="input"]>div{background:#262b30!important;border:1px solid #454c54!important;border-radius:7px!important}\n[data-baseweb="select"] *,[data-baseweb="input"] input{color:#f0f1f2!important}\n[data-baseweb="select"] svg{fill:#d5d9dd!important}\n[data-baseweb="tab-list"]{gap:0!important;border-bottom:1px solid #343a40!important;flex-wrap:wrap!important}\nbutton[data-baseweb="tab"]{background:transparent!important;border:0!important;border-bottom:2px solid transparent!important;border-radius:0!important;padding:13px 16px!important}\nbutton[data-baseweb="tab"] *,button[data-baseweb="tab"]{color:#b5bdc5!important;opacity:1!important;font-weight:650!important}\nbutton[data-baseweb="tab"][aria-selected="true"]{border-bottom:2px solid #ed854d!important}\nbutton[data-baseweb="tab"][aria-selected="true"] *{color:#fff!important}\nbutton[data-baseweb="tab"]:hover *{color:#fff!important}\n[data-testid="stMetric"]{background:#1c2126!important;border:1px solid #363d44!important;border-radius:9px!important;padding:18px 20px!important}\n[data-testid="stMetricLabel"] *,[data-testid="stMetricLabel"]{color:#b8c2cb!important;font-weight:650!important;font-size:.82rem!important}\n[data-testid="stMetricValue"] *,[data-testid="stMetricValue"]{color:#f6f7f8!important;font-weight:750!important}\n[data-testid="stDataFrame"]{border:1px solid #363d44!important;border-radius:8px!important}\n[data-testid="stAlert"]{border:1px solid #38414a!important;border-radius:8px!important}\n.stButton button,[data-testid="stDownloadButton"] button{border-radius:7px!important}\nhr{border-color:#343a40!important}\n@media(max-width:768px){.block-container{padding:1rem!important}h1{font-size:1.65rem!important}button[data-baseweb="tab"]{padding:9px!important}}\n</style>\n',unsafe_allow_html=True)
st.markdown('<style>\n[data-testid="stTabs"] [role="tablist"]{display:flex!important;flex-wrap:wrap!important;gap:4px!important;border-bottom:1px solid #363c42!important}\n[data-testid="stTabs"] button[role="tab"]{color:#d1d6dd!important;opacity:1!important;background:transparent!important;border:0!important;border-bottom:3px solid transparent!important;padding:12px 15px!important;min-height:46px!important;white-space:nowrap!important}\n[data-testid="stTabs"] button[role="tab"] *,[data-testid="stTabs"] [role="tab"] p,[data-testid="stTabs"] [role="tab"] span{color:inherit!important;opacity:1!important;font-size:14px!important;font-weight:650!important;-webkit-text-fill-color:currentColor!important}\n[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{color:#fff!important;border-bottom:3px solid #f28c50!important;background:#202428!important}\n[data-testid="stTabs"] button[role="tab"]:hover{color:#fff!important;background:#252a2f!important}\n[data-testid="stTabs"] button[role="tab"]:focus-visible{outline:2px solid #f28c50!important;outline-offset:-2px!important}\n[data-testid="stTabs"] [data-baseweb="tab-highlight"]{background:#f28c50!important}\n</style>', unsafe_allow_html=True)
st.markdown('\n<style>\n/* FOXK contrast polish: scoped to Streamlit\'s actual widgets */\n[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:3px!important;border-bottom:1px solid #41474e!important}\n[data-testid="stTabs"] button[role="tab"], [data-testid="stTabs"] button[data-baseweb="tab"]{color:#d4d9df!important;opacity:1!important;font-weight:650!important;border-radius:0!important;transition:color .12s ease,border-color .12s ease!important}\n[data-testid="stTabs"] button[role="tab"] *,[data-testid="stTabs"] button[data-baseweb="tab"] *{color:inherit!important;opacity:1!important;-webkit-text-fill-color:currentColor!important}\n[data-testid="stTabs"] button[aria-selected="true"]{color:#fff!important;border-bottom:2px solid #f18a4b!important}\n[data-testid="stTabs"] button[role="tab"]:hover{color:#fff!important;background:#20252a!important}\n/* Labels in main panel */\n[data-testid="stMain"] [data-testid="stWidgetLabel"] p,[data-testid="stMain"] [data-testid="stWidgetLabel"] label,[data-testid="stMain"] [data-testid="stWidgetLabel"]{color:#dbe0e6!important;opacity:1!important}\n/* Select widgets: dark throughout, including arrow section */\n[data-testid="stSelectbox"] [data-baseweb="select"]>div,[data-testid="stSelectbox"] [data-baseweb="select"]>div>div{background:#252b31!important;color:#f6f7f8!important}\n[data-testid="stSelectbox"] [data-baseweb="select"]>div{border:1px solid #4b545d!important;border-radius:7px!important;box-shadow:none!important}\n[data-testid="stSelectbox"] [data-baseweb="select"] *{color:#f6f7f8!important;-webkit-text-fill-color:#f6f7f8!important}\n[data-testid="stSelectbox"] [data-baseweb="select"] svg{fill:#dce1e6!important;color:#dce1e6!important}\n[data-testid="stSelectbox"] [data-baseweb="select"] [role="button"]{background:transparent!important}\n[data-testid="stSelectbox"] [data-baseweb="select"]>div:focus-within{border-color:#f18a4b!important}\n[data-baseweb="popover"] [role="listbox"], [data-baseweb="popover"] ul{background:#252b31!important;color:#f6f7f8!important}\n[data-baseweb="popover"] [role="option"]{background:#252b31!important;color:#f6f7f8!important}\n[data-baseweb="popover"] [role="option"]:hover,[data-baseweb="popover"] [aria-selected="true"]{background:#39424b!important}\n/* Number input buttons and text */\n[data-testid="stNumberInput"] [data-baseweb="input"]>div,[data-testid="stNumberInput"] button{background:#252b31!important;color:#f6f7f8!important}\n[data-testid="stNumberInput"] svg{fill:#dce1e6!important}\n/* Reduce visual gaps without changing content */\n[data-testid="stMain"] .block-container{padding-top:1.1rem!important}\n[data-testid="stMain"] [data-testid="stVerticalBlock"]{row-gap:.7rem}\n@media(max-width:800px){[data-testid="stTabs"] button[role="tab"]{padding:10px 12px!important}}\n</style>\n', unsafe_allow_html=True)
st.markdown('<style>\n/* Native button navigation with reliable contrast */\ndiv[class*="st-key-foxk_nav_"] button {min-height:45px!important;border-radius:8px!important;font-weight:700!important;font-size:14px!important;opacity:1!important;transition:background .15s ease!important}\ndiv[class*="st-key-foxk_nav_"] button[kind="secondary"] {background:#252b31!important;border:1px solid #4a535d!important;color:#f0f2f5!important}\ndiv[class*="st-key-foxk_nav_"] button[kind="secondary"] * {color:#f0f2f5!important;opacity:1!important}\ndiv[class*="st-key-foxk_nav_"] button[kind="primary"] {background:#ed854d!important;border:1px solid #ed854d!important;color:#151719!important}\ndiv[class*="st-key-foxk_nav_"] button[kind="primary"] * {color:#151719!important;opacity:1!important}\ndiv[class*="st-key-foxk_nav_"] button:hover {border-color:#ffad7e!important;filter:brightness(1.12)}\n</style>', unsafe_allow_html=True)
BASE='https://site.api.espn.com/apis/site/v2/sports/basketball/nba'
WEB='https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba'
S=requests.Session()
S.headers.update({'Accept':'application/json'})

def fetch(url, params=None):
    for i in range(2):
        try:
            r=S.get(url,params=params,timeout=14)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            err=e
            if i==0: time.sleep(1)
    raise RuntimeError(f'Data provider unavailable: {err}')

@st.cache_data(ttl=86400,show_spinner=False)
def roster_index():
    teams=fetch(BASE+'/teams',{'limit':100}).get('sports',[{}])[0].get('leagues',[{}])[0].get('teams',[])
    out={}; errors=0
    for item in teams:
        t=item.get('team',item)
        try:
            payload=fetch(BASE+'/teams/'+str(t['id'])+'/roster')
            for group in payload.get('athletes',[]):
                athletes=group.get('items',[]) if isinstance(group,dict) else []
                if not athletes and isinstance(group,dict) and group.get('id'): athletes=[group]
                for p in athletes:
                    if p.get('id') and p.get('displayName'):
                        out[str(p['id'])]={'name':p['displayName'],'team':t.get('abbreviation',''),'id':str(p['id'])}
        except Exception: errors+=1
    return out,errors

def _foxk_three_made(value):
    """Parse ESPN 3PT field as made-attempted, never attempts as makes."""
    import re
    if value is None or pd.isna(value): return float('nan')
    text=str(value).strip()
    match=re.fullmatch(r"(\d+)\s*[-/]\s*(\d+)",text)
    if match: return float(match.group(1))
    try: return float(text.replace(',',''))
    except (ValueError,TypeError): return float('nan')

def _foxk_venue(event, entry):
    """ESPN game-log venue may be represented by atVs rather than homeAway."""
    for obj in (event,entry):
        if not isinstance(obj,dict): continue
        value=str(obj.get('homeAway') or obj.get('home_away') or '').strip().lower()
        if value in ('home','away'): return value.title()
        for field in ('atVs','at_vs','gameLocation','location'):
            val=str(obj.get(field) or '').strip().lower()
            if val in ('@','at','away','a'): return 'Away'
            if val in ('vs','vs.','v','home','h'): return 'Home'
        # Some feeds mark away games with '@' in matchup display.
        for field in ('shortName','displayName','matchup'):
            val=str(obj.get(field) or '')
            if ' @ ' in val: return 'Away'
            if ' vs ' in val.lower() or ' vs. ' in val.lower(): return 'Home'
    return None

@st.cache_data(ttl=1800,show_spinner=False)
def player_log(pid,season):
    payload=fetch(f'{WEB}/athletes/{pid}/gamelog',{'season':season})
    labels=payload.get('labels',[])
    events=payload.get('events',{})
    if isinstance(events,list): events={str(x.get('id')):x for x in events if isinstance(x,dict)}
    rows=[]
    for season_type in payload.get('seasonTypes',[]):
        for cat in season_type.get('categories',[]):
            cat_labels=cat.get('labels') or labels
            for entry in cat.get('events',[]):
                if not isinstance(entry,dict): continue
                eid=str(entry.get('eventId') or entry.get('id') or '')
                event=events.get(eid,{})
                vals=entry.get('stats',[])
                record=dict(zip(cat_labels,vals)) if isinstance(vals,list) else (dict(vals) if isinstance(vals,dict) else {})
                opp=event.get('opponent') or entry.get('opponent') or {}
                opp=opp.get('abbreviation') if isinstance(opp,dict) else opp
                record.update({'event_id':eid,
                               'date':event.get('gameDate') or event.get('date') or entry.get('date'),
                               'opponent':opp,
                               'homeAway':_foxk_venue(event,entry),
                               'result':event.get('gameResult') or entry.get('gameResult')})
                rows.append(record)
    if not rows:
        for entry in payload.get('entries',[]):
            if isinstance(entry,dict):
                record=dict(entry)
                record['homeAway']=_foxk_venue(entry,entry)
                rows.append(record)
    df=pd.DataFrame(rows)
    if df.empty:return df
    aliases={'PTS':['PTS','points'],'REB':['REB','rebounds'],'AST':['AST','assists'],
             'STL':['STL','steals'],'BLK':['BLK','blocks'],'MIN':['MIN','minutes'],
             'FGA':['FGA','fieldGoalsAttempted'],'FGM':['FGM','fieldGoalsMade'],
             'FTA':['FTA','freeThrowsAttempted']}
    for key,choices in aliases.items():
        match=next((c for c in choices if c in df.columns),None)
        if match: df[key]=pd.to_numeric(df[match].astype(str).str.replace(',',''),errors='coerce')
    # ESPN commonly reports '3PT' as made-attempted (e.g. '4-9').
    # Direct made-only fields take priority; otherwise parse the left-hand number.
    made_col=next((c for c in ['3PM','3PTM','threePointFieldGoalsMade'] if c in df.columns),None)
    if made_col:
        df['3PM']=df[made_col].apply(_foxk_three_made)
    else:
        split_col=next((c for c in ['3PT','3PT FG','3PT-FG','threePointFieldGoalsMade-threePointFieldGoalsAttempted'] if c in df.columns),None)
        if split_col: df['3PM']=df[split_col].apply(_foxk_three_made)
    for combo,parts in {'PRA':['PTS','REB','AST'],'PR':['PTS','REB'],'PA':['PTS','AST'],'RA':['REB','AST']}.items():
        if all(k in df for k in parts): df[combo]=df[parts].sum(axis=1,min_count=len(parts))
    if 'date' in df:
        df['date']=pd.to_datetime(df['date'],errors='coerce',utc=True)
        df=df.sort_values('date',ascending=False)
    return df


@st.cache_data(ttl=3600,show_spinner=False)
@st.cache_data(ttl=1800, show_spinner=False)
def team_defensive_sample(team_code, season):
    """Only ESPN-confirmed final games; team-level points scored/allowed."""
    teams=fetch(BASE+'/teams',{'limit':100}).get('sports',[{}])[0].get('leagues',[{}])[0].get('teams',[])
    aliases={'GSW':{'GSW','GS'},'NOP':{'NOP','NO'},'NYK':{'NYK','NY'},'SAS':{'SAS','SA'},'UTA':{'UTA','UTAH'},'WAS':{'WAS','WSH'}}
    accepted=aliases.get(team_code,{team_code})
    matches=[x.get('team',x) for x in teams if x.get('team',x).get('abbreviation','').upper() in accepted]
    if not matches:raise ValueError('Selected team not found in ESPN team directory')
    tid=str(matches[0]['id'])
    payload=fetch(BASE+'/teams/'+tid+'/schedule',{'season':season})
    def numeric_score(value):
        if isinstance(value,dict):
            value=value.get('value') if value.get('value') is not None else value.get('displayValue')
        try:return float(value)
        except (TypeError,ValueError):return None
    records=[]
    for ev in payload.get('events',[]):
        comp=(ev.get('competitions') or [{}])[0]
        status=comp.get('status') or ev.get('status') or {}
        if not isinstance(status,dict) or status.get('type',{}).get('completed') is not True:continue
        entries=comp.get('competitors') or []
        if len(entries)!=2:continue
        own=next((c for c in entries if str(c.get('id') or c.get('team',{}).get('id'))==tid),None)
        if own is None:continue
        opp=next((c for c in entries if c is not own),None)
        if opp is None:continue
        allowed=numeric_score(opp.get('score'))
        scored=numeric_score(own.get('score'))
        if allowed is None or scored is None:continue
        homeaway=str(own.get('homeAway') or '').lower()
        venue='Home' if homeaway=='home' else ('Away' if homeaway=='away' else 'Unknown')
        records.append({'Date':ev.get('date'),'Opponent':opp.get('team',{}).get('abbreviation',''),
                        'Venue':venue,'Points allowed':allowed,'Points scored':scored,
                        'Margin':scored-allowed,'Result':'W' if scored>allowed else ('L' if scored<allowed else 'T'),
                        'Event ID':str(ev.get('id',''))})
    frame=pd.DataFrame(records,columns=['Date','Opponent','Venue','Points allowed','Points scored','Margin','Result','Event ID'])
    if not frame.empty:
        frame['Date']=pd.to_datetime(frame['Date'],errors='coerce',utc=True)
        frame=frame.dropna(subset=['Date']).drop_duplicates(subset=['Event ID','Date'])
        frame=frame.sort_values('Date',ascending=False).reset_index(drop=True)
        frame['Date']=frame['Date'].dt.strftime('%Y-%m-%d')
    return frame

def describe_rates(frame,metric,threshold):
    if metric not in frame:return None
    x=frame[metric].dropna()
    if x.empty:return None
    return {'games':len(x),'average':round(x.mean(),1),'over':int((x>threshold).sum()),'push':int((x==threshold).sum())}

# Tighten the top padding without changing the navigation or data logic.
st.markdown('''<style>
[data-testid="stMain"] .block-container {padding-top:0.35rem!important;}
[data-testid="stMain"] h1 {margin-top:0!important;}
</style>''', unsafe_allow_html=True)
# Visual-only FOXK 2026 refresh. No authentication, API, or calculation changes.
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');
:root{--foxk-bg:#090e17;--foxk-surface:#111a29;--foxk-edge:#263348;--foxk-orange:#ff965a;--foxk-text:#f5f8ff;--foxk-muted:#9eacc0}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:radial-gradient(ellipse at 88% 0%,#18263b 0%,transparent 42%),linear-gradient(160deg,#0c1320 0%,#090e17 78%)!important;color:var(--foxk-text)!important}
html,body,p,li,label,button,input{font-family:'DM Sans',Arial,sans-serif!important}
h1,h2,h3,h4{font-family:'Space Grotesk','DM Sans',sans-serif!important;letter-spacing:-.025em!important;color:var(--foxk-text)!important}
[data-testid="stHeader"]{background:rgba(9,14,23,.88)!important;border-bottom:1px solid #263348!important;backdrop-filter:blur(14px)}
[data-testid="stMain"] .block-container{max-width:1440px!important;padding:1.2rem 2rem 5rem!important}
[data-testid="stSidebar"]{background:#0e1624!important;border-right:1px solid var(--foxk-edge)!important}
[data-testid="stMetric"]{background:linear-gradient(155deg,#172337,#111a29)!important;border:1px solid #2d3c52!important;border-radius:16px!important;padding:21px 22px!important;box-shadow:0 12px 32px rgba(0,0,0,.14)!important}
[data-testid="stMetricValue"] *,[data-testid="stMetricValue"]{font-family:'Space Grotesk',sans-serif!important;font-size:clamp(1.5rem,2.3vw,2.15rem)!important;color:#fff!important}
[data-testid="stMetricLabel"] *,[data-testid="stMetricLabel"]{color:#aabbd0!important;font-size:.8rem!important;letter-spacing:.025em!important}
[data-testid="stCaptionContainer"] p,[data-testid="stCaptionContainer"]{color:#aabbd0!important}
[data-testid="stExpander"]{background:rgba(17,26,41,.82)!important;border:1px solid #2b3a50!important;border-radius:14px!important;overflow:hidden!important}
[data-testid="stDataFrame"],[data-testid="stTable"]{border:1px solid #2b3a50!important;border-radius:14px!important;overflow:hidden!important}
[data-testid="stAlert"]{border-radius:12px!important}
[data-baseweb="select"]>div,[data-baseweb="input"]>div,[data-testid="stDateInput"] input{background:#172236!important;border:1px solid #35465f!important;border-radius:11px!important;min-height:44px!important}
[data-baseweb="select"]>div:focus-within,[data-baseweb="input"]>div:focus-within{border-color:var(--foxk-orange)!important;box-shadow:0 0 0 2px rgba(255,150,90,.12)!important}
.stButton button,[data-testid="stDownloadButton"] button{min-height:43px!important;border-radius:11px!important;font-weight:700!important;transition:transform .15s ease,background .15s ease,border-color .15s ease!important}
.stButton button:hover,[data-testid="stDownloadButton"] button:hover{transform:translateY(-1px)}
.stButton button[kind="primary"],div[class*="st-key-foxk_nav_"] button[kind="primary"]{background:linear-gradient(120deg,#ffae6d,#f27c48)!important;border:1px solid #ffad75!important;color:#1a1720!important;box-shadow:0 5px 20px rgba(242,124,72,.16)!important}
.stButton button[kind="primary"] *,div[class*="st-key-foxk_nav_"] button[kind="primary"] *{color:#1a1720!important}
div[class*="st-key-foxk_nav_"] button[kind="secondary"]{background:#152035!important;border:1px solid #2d3d55!important;color:#d5e0ef!important}
div[class*="st-key-foxk_nav_"] button[kind="secondary"] *{color:#d5e0ef!important}
div[class*="st-key-foxk_nav_"] button{min-height:49px!important;border-radius:12px!important}
hr{border-color:#263348!important;margin:1.1rem 0!important}
a{color:#ffb583!important}
.foxk-hero{position:relative;overflow:hidden;padding:27px 31px 25px;margin:0 0 18px;background:linear-gradient(115deg,#18253a 0%,#121e31 60%,#1f2739 100%);border:1px solid #36465e;border-radius:21px;box-shadow:0 20px 55px rgba(0,0,0,.18)}
.foxk-hero:after{content:'◉';position:absolute;right:26px;top:-65px;font-size:245px;color:rgba(255,150,90,.075);pointer-events:none}
.foxk-eyebrow{font-size:11px;font-weight:800;letter-spacing:.2em;color:#ffae7b;margin-bottom:9px}
.foxk-hero h1{font-size:clamp(1.75rem,3.3vw,3.1rem)!important;line-height:1.1!important;margin:0 0 9px!important;font-weight:700!important}
.foxk-hero h1 span{color:#ff9d65}
.foxk-hero p{color:#b4c4d9;font-size:.91rem;margin:0!important}
.foxk-tag{display:inline-block;margin-top:17px;padding:6px 11px;background:rgba(255,150,90,.11);border:1px solid rgba(255,150,90,.3);border-radius:999px;color:#ffbb91;font-size:.72rem;font-weight:800;letter-spacing:.06em}
@media(max-width:768px){[data-testid="stMain"] .block-container{padding:1rem .75rem 3rem!important}.foxk-hero{padding:20px 18px;border-radius:15px}.foxk-hero:after{display:none}div[class*="st-key-foxk_nav_"] button{font-size:12px!important;min-height:43px!important}}
</style>""",unsafe_allow_html=True)
# FOXK App Store edition: visual layer only; preserves auth, data and research logic.
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Outfit:wght@500;600;700;800;900&display=swap');
:root{--app-bg:#070a12;--app-panel:#121824;--app-line:rgba(172,194,225,.13);--app-orange:#ff854d;--app-ink:#f8faff;--app-dim:#9caec5}
html,body,.stApp{font-family:'Inter',sans-serif!important}
.stApp,[data-testid='stAppViewContainer'],[data-testid='stMain']{background:radial-gradient(ellipse 52% 30% at 96% 1%,rgba(249,103,58,.10),transparent 85%),radial-gradient(ellipse 60% 40% at 2% 35%,rgba(47,82,149,.09),transparent 80%),#070a12!important;color:var(--app-ink)!important}
[data-testid='stHeader']{background:rgba(7,10,18,.72)!important;border-bottom:1px solid rgba(180,200,230,.07)!important;backdrop-filter:blur(24px)!important}
[data-testid='stMain'] .block-container{max-width:1480px!important;padding:1.1rem clamp(.8rem,3vw,3.1rem) 5rem!important}
[data-testid='stSidebar']{background:#0c111b!important;border-right:1px solid var(--app-line)!important}
[data-testid='stSidebar'] [data-testid='stVerticalBlock']{gap:.65rem!important}
h1,h2,h3,h4{font-family:'Outfit','Inter',sans-serif!important;letter-spacing:-.035em!important}
h2{font-size:clamp(1.4rem,2.4vw,2rem)!important;font-weight:800!important}
h3{font-weight:750!important}
.foxk-app-hero{position:relative;overflow:hidden;isolation:isolate;border:1px solid rgba(255,255,255,.13);border-radius:29px;padding:32px 35px 29px;margin:0 0 22px;background:linear-gradient(115deg,#1b263a 0%,#111b2b 48%,#1c1721 100%);box-shadow:0 22px 55px rgba(0,0,0,.27),inset 0 1px rgba(255,255,255,.08)}
.foxk-app-hero:before{content:'';position:absolute;width:440px;height:440px;right:-115px;top:-220px;border-radius:50%;background:radial-gradient(circle,rgba(255,125,67,.35),rgba(255,125,67,0) 70%);z-index:-1}
.foxk-app-hero:after{content:'';position:absolute;width:250px;height:250px;right:70px;bottom:-230px;border-radius:50%;background:radial-gradient(circle,rgba(104,136,255,.18),transparent 70%);z-index:-1}
.foxk-app-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:26px;flex-wrap:wrap}
.foxk-app-brand{display:flex;align-items:center;gap:11px;font-size:.86rem;font-weight:850;letter-spacing:.10em;color:#f8faff}
.foxk-app-icon{display:grid;place-items:center;width:42px;height:42px;border-radius:13px;background:linear-gradient(145deg,#ffad6d,#f56a3c);color:#21150e;font-size:24px;box-shadow:0 8px 22px rgba(250,111,60,.27)}
.foxk-app-chip{font-size:.69rem;font-weight:800;letter-spacing:.13em;border:1px solid rgba(255,175,123,.31);border-radius:100px;padding:8px 12px;background:rgba(255,135,72,.12);color:#ffba8f}
.foxk-app-eyebrow{color:#ffad7c;font-size:.73rem;font-weight:850;letter-spacing:.2em;margin-bottom:10px}
.foxk-app-hero h1{font-size:clamp(2.3rem,5.5vw,4.5rem)!important;font-weight:900!important;line-height:1.02!important;letter-spacing:-.06em!important;margin:0 0 12px!important}
.foxk-app-hero h1 em{font-style:normal;background:linear-gradient(110deg,#ffc090,#ff8752);background-clip:text;-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.foxk-app-sub{color:#bac8db!important;font-size:clamp(.84rem,1.3vw,1rem)!important;line-height:1.65!important;max-width:670px;margin:0!important}
.foxk-app-tiles{display:flex;gap:9px;flex-wrap:wrap;margin-top:23px}
.foxk-app-tiles span{display:inline-flex;align-items:center;gap:7px;padding:9px 13px;border:1px solid rgba(255,255,255,.13);background:rgba(255,255,255,.055);border-radius:11px;font-size:.76rem;font-weight:650;color:#e1eaf7}
.foxk-section-marker{display:flex;align-items:center;gap:10px;margin:3px 0 12px;color:#94a6bf;font-size:.72rem;font-weight:850;letter-spacing:.16em;text-transform:uppercase}
.foxk-section-marker:before{content:'';height:7px;width:7px;border-radius:50%;background:#ff925b;box-shadow:0 0 0 4px rgba(255,146,91,.11)}
[data-testid='stMetric']{background:linear-gradient(155deg,rgba(29,40,58,.95),rgba(15,22,34,.97))!important;border:1px solid rgba(172,194,225,.16)!important;border-radius:20px!important;padding:23px!important;box-shadow:0 12px 38px rgba(0,0,0,.14),inset 0 1px rgba(255,255,255,.035)!important}
[data-testid='stMetricValue'] *,[data-testid='stMetricValue']{font-family:'Outfit',sans-serif!important;font-weight:850!important;font-size:clamp(1.65rem,2.8vw,2.55rem)!important}
[data-testid='stMetricLabel'] *{font-size:.75rem!important;letter-spacing:.07em!important;text-transform:uppercase!important;color:#9cacc1!important}
[data-testid='stExpander']{border-radius:18px!important;background:rgba(19,27,41,.75)!important;border:1px solid var(--app-line)!important}
[data-testid='stDataFrame']{border-radius:18px!important;border:1px solid var(--app-line)!important;overflow:hidden!important}
[data-testid='stAlert']{border-radius:15px!important}
[data-baseweb='select']>div,[data-baseweb='input']>div,[data-testid='stDateInput'] input{background:#161f2e!important;border:1px solid #344258!important;border-radius:13px!important;min-height:48px!important}
.stButton button,[data-testid='stDownloadButton'] button{border-radius:13px!important;min-height:48px!important;font-size:.84rem!important;font-weight:750!important;transition:transform .17s ease,box-shadow .17s ease,background .17s ease!important}
.stButton button:hover,[data-testid='stDownloadButton'] button:hover{transform:translateY(-2px);box-shadow:0 10px 22px rgba(0,0,0,.16)!important}
div[class*='st-key-foxk_nav_'] button{min-height:52px!important;border-radius:15px!important;letter-spacing:-.01em!important}
div[class*='st-key-foxk_nav_'] button[kind='secondary']{background:#141d2c!important;border:1px solid #29384c!important;color:#dbe5f2!important}
div[class*='st-key-foxk_nav_'] button[kind='primary']{background:linear-gradient(125deg,#ffb078,#ff804a)!important;border:1px solid #ffad7b!important;color:#20140f!important;box-shadow:0 7px 20px rgba(255,128,74,.16)!important}
div[class*='st-key-foxk_nav_'] button[kind='primary'] *{color:#20140f!important}
[data-testid='stWidgetLabel'] p{font-size:.81rem!important;font-weight:700!important;color:#c5d1e2!important}
hr{border-color:rgba(172,194,225,.13)!important}
@media(max-width:700px){[data-testid='stMain'] .block-container{padding:.8rem .7rem 4rem!important}.foxk-app-hero{border-radius:21px;padding:21px 19px 23px;margin-bottom:15px}.foxk-app-top{margin-bottom:21px}.foxk-app-tiles span{padding:7px 9px;font-size:.69rem}div[class*='st-key-foxk_nav_'] button{min-height:45px!important;font-size:.72rem!important;padding:.3rem!important}[data-testid='stMetric']{padding:15px!important;border-radius:15px!important}}
@media(prefers-reduced-motion:reduce){.stButton button{transition:none!important}.stButton button:hover{transform:none!important}}
</style>""",unsafe_allow_html=True)
# FOXK ULTRA — visual-only override. Existing login, stats, API calls remain intact.
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');
:root{--ultra-bg:#070910;--ultra-card:#101625;--ultra-edge:rgba(183,198,238,.14);--ultra-violet:#9b7cff;--ultra-orange:#ff9869}
html,body,.stApp{font-family:'Manrope',sans-serif}
h1,h2,h3,h4,[data-testid='stMetricValue']{font-family:'Space Grotesk',sans-serif!important}
.stApp,[data-testid='stAppViewContainer'],[data-testid='stMain']{background:radial-gradient(ellipse 58% 35% at 83% 3%,rgba(106,66,196,.17),transparent 75%),radial-gradient(ellipse 44% 36% at 1% 56%,rgba(250,107,64,.08),transparent 85%),#070910!important}
[data-testid='stHeader']{background:rgba(7,9,16,.8)!important;backdrop-filter:blur(24px)!important;border-bottom:1px solid rgba(255,255,255,.065)!important}
[data-testid='stMain'] .block-container{max-width:1520px!important;padding:1.15rem clamp(.75rem,3vw,3rem) 5rem!important}
[data-testid='stSidebar']{background:linear-gradient(180deg,#111525,#0a0d16)!important;border-right:1px solid var(--ultra-edge)!important}
.foxk-app-hero{border-radius:32px!important;padding:38px 42px!important;background:radial-gradient(circle at 85% 28%,rgba(255,140,92,.24),transparent 33%),radial-gradient(circle at 64% 110%,rgba(128,88,255,.25),transparent 55%),linear-gradient(120deg,#1a1e35,#101627 62%,#221828)!important;border:1px solid rgba(201,191,255,.24)!important;box-shadow:0 28px 75px rgba(0,0,0,.38),inset 0 1px rgba(255,255,255,.10)!important}
.foxk-app-hero h1{font-size:clamp(2.6rem,6vw,5.6rem)!important;letter-spacing:-.075em!important}
.foxk-app-hero h1 em{background:linear-gradient(100deg,#ffb37f 15%,#ffa1b9 53%,#bba7ff 100%)!important;background-clip:text!important;-webkit-background-clip:text!important;-webkit-text-fill-color:transparent!important}
.foxk-app-icon{border-radius:15px!important;background:linear-gradient(135deg,#ffb476,#fa7771 60%,#ac78ff)!important;box-shadow:0 8px 30px rgba(253,120,96,.3)!important}
.foxk-app-chip{border-color:rgba(193,166,255,.4)!important;background:rgba(144,104,240,.17)!important;color:#d8c7ff!important}
.foxk-app-tiles span{background:rgba(255,255,255,.07)!important;border-color:rgba(255,255,255,.13)!important;border-radius:100px!important;backdrop-filter:blur(10px)!important}
.foxk-section-marker{color:#aab0d0!important;letter-spacing:.18em!important}
.foxk-section-marker:before{background:#b69aff!important;box-shadow:0 0 0 4px rgba(171,137,255,.12)!important}
/* App-launcher style navigation tiles */
div[class*='st-key-foxk_nav_'] button{height:76px!important;min-height:76px!important;border-radius:20px!important;text-align:left!important;justify-content:flex-start!important;padding:15px 18px!important;font-size:.9rem!important;letter-spacing:-.02em!important;font-weight:800!important;position:relative!important;overflow:hidden!important;box-shadow:inset 0 1px rgba(255,255,255,.045),0 8px 18px rgba(0,0,0,.12)!important;transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease!important}
div[class*='st-key-foxk_nav_'] button[kind='secondary']{background:linear-gradient(140deg,#171d30,#101624)!important;border:1px solid rgba(184,196,236,.17)!important;color:#d9e1f5!important}
div[class*='st-key-foxk_nav_'] button[kind='primary']{background:linear-gradient(115deg,#faab78,#f48a85 50%,#c4a3ff)!important;border:1px solid rgba(255,207,185,.9)!important;color:#211427!important;box-shadow:0 9px 30px rgba(194,119,231,.19)!important}
div[class*='st-key-foxk_nav_'] button:hover{transform:translateY(-3px)!important;border-color:#c5a4ff!important;box-shadow:0 15px 30px rgba(0,0,0,.25)!important}
div[class*='st-key-foxk_nav_'] button:focus-visible{outline:2px solid #c8a8ff!important;outline-offset:2px!important}
/* Bento-style metric tiles */
[data-testid='stMetric']{border-radius:24px!important;background:linear-gradient(150deg,rgba(32,37,62,.96),rgba(14,19,34,.97))!important;border:1px solid rgba(181,172,255,.17)!important;padding:25px 24px!important;box-shadow:0 15px 36px rgba(0,0,0,.17),inset 0 1px rgba(255,255,255,.06)!important;min-height:130px!important}
[data-testid='stMetricValue'] *,[data-testid='stMetricValue']{color:#fff!important;font-size:clamp(1.7rem,2.6vw,2.5rem)!important;letter-spacing:-.055em!important}
[data-testid='stMetricLabel'] *{color:#a9b4d1!important;letter-spacing:.08em!important}
/* Glassy research cards, expanders, alerts and charts */
[data-testid='stExpander']{border-radius:22px!important;background:linear-gradient(145deg,rgba(25,30,51,.95),rgba(13,18,31,.94))!important;border:1px solid rgba(174,170,241,.19)!important;box-shadow:0 14px 30px rgba(0,0,0,.12)!important}
[data-testid='stExpander'] summary{padding:7px 5px!important;font-weight:800!important}
[data-testid='stDataFrame'],[data-testid='stTable'],[data-testid='stPlotlyChart'],[data-testid='stVegaLiteChart']{border:1px solid rgba(174,170,241,.18)!important;border-radius:20px!important;overflow:hidden!important;background:#111725!important}
[data-testid='stAlert']{border-radius:18px!important;border:1px solid rgba(174,170,241,.19)!important}
[data-testid='stHorizontalBlock']{row-gap:12px!important}
/* Floating inputs, polished filters */
[data-baseweb='select']>div,[data-baseweb='input']>div,[data-testid='stDateInput'] input,textarea{background:#151b2c!important;border:1px solid rgba(172,187,231,.25)!important;border-radius:15px!important;min-height:50px!important;color:#f6f5ff!important;box-shadow:inset 0 1px rgba(255,255,255,.025)!important}
[data-baseweb='select']>div:focus-within,[data-baseweb='input']>div:focus-within{border-color:#ba9cff!important;box-shadow:0 0 0 3px rgba(173,139,255,.15)!important}
[data-testid='stWidgetLabel'] p{color:#c8d1e9!important;font-weight:750!important}
[data-baseweb='popover'] [role='listbox'],[data-baseweb='popover'] ul{background:#171d2e!important;border:1px solid #3d405b!important;border-radius:15px!important}
[data-baseweb='popover'] [role='option']:hover{background:#302c4e!important}
/* Pill buttons and premium segmented tabs */
.stButton button,[data-testid='stDownloadButton'] button{border-radius:15px!important;min-height:49px!important;font-weight:800!important}
.stButton button[kind='primary']:not(div[class*='st-key-foxk_nav_'] button){background:linear-gradient(110deg,#ffb47f,#fa898b,#b99bff)!important;border-color:transparent!important;color:#211427!important}
[data-testid='stTabs'] [role='tablist']{background:#11182a!important;border:1px solid rgba(174,170,241,.17)!important;padding:6px!important;border-radius:17px!important;gap:5px!important}
[data-testid='stTabs'] button[role='tab']{border:0!important;border-radius:12px!important;padding:11px 16px!important;color:#bac5dd!important;background:transparent!important}
[data-testid='stTabs'] button[role='tab'][aria-selected='true']{background:linear-gradient(110deg,#fdab7b,#bd9bff)!important;color:#1b1529!important;box-shadow:0 4px 15px rgba(0,0,0,.2)!important}
[data-testid='stTabs'] button[role='tab'][aria-selected='true'] *{color:#1b1529!important;-webkit-text-fill-color:#1b1529!important}
[data-testid='stTabs'] [data-baseweb='tab-highlight']{display:none!important}
/* Section title ribbon */
.foxk-current-section{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:8px 0 22px;padding:16px 22px;background:linear-gradient(100deg,rgba(136,98,229,.18),rgba(255,143,102,.07));border:1px solid rgba(171,147,255,.23);border-radius:19px}
.foxk-current-section strong{font-family:'Space Grotesk',sans-serif;font-size:1.13rem;color:#f7f3ff}
.foxk-current-section small{color:#b1a8d5;font-weight:800;letter-spacing:.12em;font-size:.66rem}
@media(max-width:800px){.foxk-app-hero{padding:23px 20px!important;border-radius:24px!important}div[class*='st-key-foxk_nav_'] button{height:64px!important;min-height:64px!important;padding:10px!important;font-size:.73rem!important;border-radius:14px!important}[data-testid='stMetric']{padding:18px!important;border-radius:18px!important;min-height:100px!important}.foxk-current-section{padding:12px 14px!important}}
@media(prefers-reduced-motion:reduce){div[class*='st-key-foxk_nav_'] button{transition:none!important}div[class*='st-key-foxk_nav_'] button:hover{transform:none!important}}
</style>""",unsafe_allow_html=True)

st.markdown("""<div class="foxk-app-hero">
<div class="foxk-app-top"><div class="foxk-app-brand"><span class="foxk-app-icon">🦊</span><span>FOXK &nbsp;/&nbsp; NBA INTELLIGENCE</span></div><div class="foxk-app-chip">✦ VIP ACCESS</div></div>
<div class="foxk-app-eyebrow">YOUR COURTSIDE DATA EXPERIENCE</div>
<h1>THE GAME.<br><em>DECODED.</em></h1>
<p class="foxk-app-sub">A premium workspace for NBA player trends, matchup research, and sportsbook prop analysis — built for clarity, speed, and confidence in the data.</p>
<div class="foxk-app-tiles"><span>◈ Player intelligence</span><span>▥ Matchup insights</span><span>◎ Prop research</span></div>
</div>""",unsafe_allow_html=True)

with st.expander('Data source & methodology'):
    st.caption('ESPN public basketball endpoints (unofficial). Statistics appear only when the provider returns usable game logs. No fabricated data or guessed matchups.')
@st.cache_data(ttl=600,show_spinner=False)
def foxk_today_scoreboard(day):
    return fetch(BASE+'/scoreboard', {'dates':day, 'limit':100})

from zoneinfo import ZoneInfo
from html import escape as foxk_html_escape

FOXK_TIMEZONES = {
    "Eastern (Indiana)": "America/Indiana/Indianapolis",
    "Central": "America/Chicago",
    "Mountain": "America/Denver",
    "Pacific": "America/Los_Angeles",
}

st.markdown("""<style>

/* FOXK compact NBA schedule grid: 3 columns desktop, 2 tablet, 1 phone. */
.foxk-schedule-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0 16px}
.foxk-schedule-grid .foxk-game-card{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:8px;align-items:center;min-width:0;
 padding:12px 14px;margin:0;border-radius:14px;box-shadow:none;background:linear-gradient(135deg,#1b2b45,#111d31)}
.foxk-schedule-grid .foxk-game-name{font-size:18px;line-height:1.1}
.foxk-schedule-grid .foxk-game-tag{font-size:9px;margin-bottom:3px}
.foxk-schedule-grid .foxk-game-middle{min-width:95px}
.foxk-schedule-grid .foxk-game-time{font-size:13px}
.foxk-schedule-grid .foxk-game-date{font-size:10px;margin-top:2px}
.foxk-schedule-grid .foxk-game-status{font-size:9px;padding:3px 6px;margin-top:5px}
.foxk-schedule-grid .foxk-game-score{font-size:13px;margin-top:3px}
@media(max-width:1100px){.foxk-schedule-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:680px){.foxk-schedule-grid{grid-template-columns:1fr}}

/* FOXK Game Day — full-width premium matchup cards */
.foxk-schedule-intro{font-size:12px;font-weight:800;letter-spacing:.13em;color:#ffad77;margin:7px 0 15px}
.foxk-game-card{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:16px;
 background:linear-gradient(135deg,#1c2b46 0%,#101a2d 100%);border:1px solid #3b506f;border-radius:20px;
 padding:20px 22px;margin:12px 0;box-shadow:0 10px 28px rgba(0,0,0,.18)}
.foxk-game-team{min-width:0}.foxk-game-team.right{text-align:right}
.foxk-game-tag{font-size:10px;color:#9eafca;font-weight:800;letter-spacing:.14em;margin-bottom:5px}
.foxk-game-name{font-size:23px;font-weight:850;color:#f7f9ff;letter-spacing:-.04em;overflow-wrap:anywhere}
.foxk-game-middle{text-align:center;min-width:138px}
.foxk-game-time{font-size:17px;font-weight:850;color:#ffb17d;white-space:nowrap}
.foxk-game-date{font-size:11px;color:#a6b7d2;margin-top:3px}
.foxk-game-status{display:inline-block;font-size:10px;letter-spacing:.07em;text-transform:uppercase;
 border:1px solid #435775;background:#243751;color:#d8e5f8;padding:5px 10px;border-radius:999px;margin-top:8px}
.foxk-game-status.final{background:#123d37;border-color:#287765;color:#7ef0cd}
.foxk-game-score{font-size:18px;color:#f8faff;font-weight:800;margin-top:5px}
@media(max-width:650px){.foxk-game-card{gap:8px;padding:14px 10px;border-radius:15px}
 .foxk-game-name{font-size:17px}.foxk-game-middle{min-width:110px}
 .foxk-game-time{font-size:13px}.foxk-game-date{font-size:10px}}
</style>""", unsafe_allow_html=True)

# FOXK compact schedule controls: native date input and calendar popup.
st.markdown("""<style>
/* Calendar field and all its internal layers: remove the white surface. */
[data-testid="stDateInput"],
[data-testid="stDateInput"] [data-baseweb="input"],
[data-testid="stDateInput"] [data-baseweb="input"] > div,
[data-testid="stDateInput"] [data-baseweb="input"] > div > div,
[data-testid="stDateInput"] input,
[data-testid="stDateInput"] button {
 background:#142239!important;background-color:#142239!important;
 color:#F8FAFC!important;-webkit-text-fill-color:#F8FAFC!important;
}
[data-testid="stDateInput"] [data-baseweb="input"] {
 border:1px solid #3E5679!important;border-radius:14px!important;
 overflow:hidden!important;min-height:45px!important;
}
[data-testid="stDateInput"] input {min-height:43px!important;height:43px!important;}
[data-testid="stDateInput"] svg {color:#FFAA75!important;fill:none!important;}
[data-testid="stDateInput"] [data-baseweb="input"]:focus-within {
 border-color:#FF995D!important;box-shadow:0 0 0 2px rgba(255,153,93,.13)!important;
}
/* The date-picker overlay lives outside the input component. */
[data-baseweb="calendar"],
[data-baseweb="calendar"] > div,
[data-baseweb="calendar"] button,
[data-baseweb="calendar"] select,
[data-baseweb="calendar"] [role="grid"],
[data-baseweb="calendar"] [role="gridcell"] {
 background-color:#142239!important;color:#F8FAFC!important;
}
[data-baseweb="calendar"] [aria-selected="true"] {
 background:#FF995D!important;color:#0A1020!important;
}
[data-baseweb="calendar"] [aria-disabled="true"] {opacity:.4!important;}
[data-baseweb="calendar"] button:hover {background:#293F60!important;}
</style>""",unsafe_allow_html=True)

with st.expander("🏀 Today's NBA games — live ESPN schedule", expanded=False):
    st.markdown('<div class="foxk-schedule-intro">FOXK GAME DAY · NBA MATCHUPS</div>', unsafe_allow_html=True)
    sched_left, sched_right, sched_spacer = st.columns([1.1, 1.35, 2.5])
    with sched_right:
        foxk_tz_label = st.selectbox('Display timezone', list(FOXK_TIMEZONES),
                                     key='foxk_schedule_timezone')
    foxk_tz = ZoneInfo(FOXK_TIMEZONES[foxk_tz_label])
    # Native date_input stayed white under some Streamlit versions.
    # Use the same dark selectbox component as FOXK's other working dropdowns.
    today_local = dt.datetime.now(foxk_tz).date()
    schedule_days = [today_local + dt.timedelta(days=offset) for offset in range(-365, 366)]
    if st.session_state.get('foxk_schedule_day_choice') not in schedule_days:
        st.session_state['foxk_schedule_day_choice'] = today_local

    def foxk_shift_schedule_day(amount):
        next_day = st.session_state['foxk_schedule_day_choice'] + dt.timedelta(days=amount)
        if next_day in schedule_days:
            st.session_state['foxk_schedule_day_choice'] = next_day

    with sched_left:
        game_day = st.selectbox(
            'Schedule date',
            options=schedule_days,
            format_func=lambda day: day.strftime('%a, %b %d, %Y'),
            key='foxk_schedule_day_choice',
        )
        prev_col, next_col = st.columns(2)
        with prev_col:
            st.button('← Previous', key='foxk_schedule_prev',
                      on_click=foxk_shift_schedule_day, args=(-1,),
                      use_container_width=True)
        with next_col:
            st.button('Next →', key='foxk_schedule_next',
                      on_click=foxk_shift_schedule_day, args=(1,),
                      use_container_width=True)
    st.caption(f"All tipoff times shown in {foxk_tz_label} time; daylight saving changes are handled automatically.")
    try:
        scoreboard = foxk_today_scoreboard(game_day.strftime('%Y%m%d'))
        schedule = []
        for event in scoreboard.get('events', []):
            comp = (event.get('competitions') or [{}])[0]
            teams = comp.get('competitors', [])
            home = next((x for x in teams if x.get('homeAway') == 'home'), {})
            away = next((x for x in teams if x.get('homeAway') == 'away'), {})
            if not home or not away:
                continue
            raw_time = event.get('date', '')
            try:
                parsed = dt.datetime.fromisoformat(raw_time.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=dt.timezone.utc)
                local = parsed.astimezone(foxk_tz)
                tipoff = local.strftime('%-I:%M %p %Z')
                local_day = local.strftime('%a, %b %-d')
                sort_time = parsed
            except (ValueError, TypeError):
                tipoff, local_day, sort_time = 'Time TBA', '', dt.datetime.max.replace(tzinfo=dt.timezone.utc)
            status = event.get('status', {}).get('type', {})
            completed = bool(status.get('completed'))
            away_score = away.get('score', '')
            home_score = home.get('score', '')
            score = f'{away_score} – {home_score}' if completed and away_score != '' and home_score != '' else ''
            schedule.append({'away': away.get('team', {}).get('abbreviation', '?'),
                             'home': home.get('team', {}).get('abbreviation', '?'),
                             'tipoff': tipoff, 'local_day': local_day,
                             'status': status.get('description', 'Scheduled'),
                             'completed': completed, 'score': score, 'sort_time': sort_time})
        if schedule:
            schedule.sort(key=lambda game: game['sort_time'])
            st.caption(f"{len(schedule)} NBA games returned for {game_day.strftime('%B %d, %Y')}")
            schedule_cards = []
            for game in schedule:
                away = foxk_html_escape(str(game['away']))
                home = foxk_html_escape(str(game['home']))
                time_text = foxk_html_escape(game['tipoff'])
                date_text = foxk_html_escape(game['local_day'])
                status_text = foxk_html_escape(str(game['status']))
                score_text = foxk_html_escape(game['score'])
                status_class = 'final' if game['completed'] else ''
                score_markup = f'<div class="foxk-game-score">{score_text}</div>' if score_text else ''
                schedule_cards.append(f"""<div class="foxk-game-card">
                  <div class="foxk-game-team"><div class="foxk-game-tag">AWAY</div><div class="foxk-game-name">{away}</div></div>
                  <div class="foxk-game-middle"><div class="foxk-game-time">{time_text}</div>
                    <div class="foxk-game-date">{date_text}</div>
                    <span class="foxk-game-status {status_class}">{status_text}</span>{score_markup}</div>
                  <div class="foxk-game-team right"><div class="foxk-game-tag">HOME</div><div class="foxk-game-name">{home}</div></div>
                </div>""")
            st.markdown('<div class="foxk-schedule-grid">' + ''.join(schedule_cards) + '</div>', unsafe_allow_html=True)
        else:
            st.info('No NBA games returned for this date.')
        st.caption('Source: ESPN schedule feed. Times are converted from the source timestamp; verify schedule changes before game time.')
    except Exception as exc:
        st.warning(f'Schedule feed unavailable: {exc}')


# FOXK player search and season selector — use exact widget targets across the app.
st.markdown("""<style>
/* Search input: style BOTH BaseWeb outer shell and the real input. */
div[data-testid="stTextInput"] div[data-baseweb="input"],
div[data-testid="stTextInput"] div[data-baseweb="input"] > div,
div[data-testid="stTextInput"] div[data-baseweb="input"] input,
div[data-testid="stTextInput"] input[type="text"] {
  background:#111D31!important;background-color:#111D31!important;
  color:#F8FAFC!important;-webkit-text-fill-color:#F8FAFC!important;
}
div[data-testid="stTextInput"] div[data-baseweb="input"] {
  border:1px solid #3E5577!important;border-radius:15px!important;
  box-shadow:0 6px 18px rgba(0,0,0,.15)!important;
  overflow:hidden!important;
}
div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
  border-color:#FF995D!important;box-shadow:0 0 0 2px rgba(255,153,93,.13)!important;
}
div[data-testid="stTextInput"] input::placeholder {
  color:#879DBE!important;-webkit-text-fill-color:#879DBE!important;
}
/* All selectboxes: eliminate white outer shell, inner flex wrappers, and input */
div[data-testid="stSelectbox"] div[data-baseweb="select"],
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div,
div[data-testid="stSelectbox"] div[data-baseweb="select"] input,
div[data-testid="stSelectbox"] div[data-baseweb="select"] [role="combobox"] {
  background:#111D31!important;background-color:#111D31!important;
  color:#F8FAFC!important;-webkit-text-fill-color:#F8FAFC!important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  border:1px solid #3E5577!important;border-radius:15px!important;
  overflow:hidden!important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within > div {
  border-color:#FF995D!important;
}
/* Selectbox open menu */
div[data-baseweb="popover"] [role="listbox"],
div[data-baseweb="popover"] [role="option"] {
  background:#111D31!important;color:#F8FAFC!important;
}
div[data-baseweb="popover"] [role="option"]:hover,
div[data-baseweb="popover"] [aria-selected="true"] {
  background:#263C5C!important;color:#FFB78A!important;
}
/* Streamlit info/warning panels: navy, not default bright blue */
div[data-testid="stAlert"] {
  background:#101D32!important;border:1px solid #2F496C!important;
  border-radius:15px!important;
}
div[data-testid="stAlert"] p,
div[data-testid="stAlert"] span {
  color:#BBD0EE!important;
}
</style>""", unsafe_allow_html=True)

# Global player and season selection; research filters belong to their own sections.
top_left,top_right=st.columns([3,1])
with top_left:
    search=st.text_input('Find player',placeholder='Search NBA players',key='foxk_player_query')
with top_right:
    season=st.selectbox('Season',[2027,2026,2025,2024,2023,2022],
        index=0,format_func=lambda x:f'{x-1}–{str(x)[-2:]}')
# Safe defaults for independent sections; each section can override them locally.
window=10
opponent=''
location='All'
stat='PTS'
line=24.5

try:
    with st.spinner('Finding NBA players from current team rosters…'):
        players,roster_errors=roster_index()
except Exception as e:
    st.error(f'Unable to load the free roster feed. Please retry later. {e}')
    st.stop()

# One search input is the sole player selector. A unique match opens automatically.
# Multiple matches require a more specific search rather than silently selecting
# the wrong athlete.
query=search.strip().casefold()
all_players=sorted(players.values(),key=lambda p:p['name'])
if not query:
    st.info('Enter a player name above to view their research.')
    st.stop()
matches=[p for p in all_players if query in p['name'].casefold()]
if not matches:
    st.warning('No player found. Try a different spelling or part of the name. Retired and unsigned players may be missing.')
    st.stop()
exact=[p for p in matches if p['name'].casefold()==query]
if len(exact)==1:
    selected=exact[0]
elif len(matches)==1:
    selected=matches[0]
else:
    st.info(f'{len(matches)} players match your search. Type more of the name to narrow it down.')
    st.caption('Examples: ' + ', '.join(f"{p['name']} ({p['team']})" for p in matches[:8]))
    st.stop()
st.caption(f"Viewing {selected['name']} · {selected['team']}")
if roster_errors:st.caption(f'{roster_errors} team roster feeds were unavailable; search may be incomplete.')
try:
    with st.spinner('Retrieving verified game logs…'):
        df=player_log(selected['id'],season)
except Exception as e:
    st.error(str(e));st.stop()
if df.empty:
    st.warning('ESPN returned no game-log rows for this player and season. Try another season. No numbers will be invented.')
    st.stop()
# Do not globally filter game logs: every research section manages its own sample.
df=df.copy()
# Combined props require all contributing box-score stats to be present.
for combined, parts in {'PRA':['PTS','REB','AST'], 'PR':['PTS','REB'], 'PA':['PTS','AST'], 'RA':['REB','AST']}.items():
    if all(part in df.columns for part in parts):
        df[combined]=df[parts].sum(axis=1,min_count=len(parts))
valid=[c for c in ['PTS','REB','AST','3PM','STL','BLK','PRA','PR','PA','RA'] if c in df and df[c].notna().any()]
if not valid:
    st.warning('ESPN returned game events but no parseable numeric player box-score statistics. Provider format may have changed.');st.dataframe(df.head(5));st.stop()
# Native Streamlit navigation buttons: no st.tabs CSS or unreadable inactive labels.
st.markdown('<div class="foxk-section-marker">Explore your workspace</div>',unsafe_allow_html=True)
# Keep legacy section IDs for all existing analysis and calculation code.
NAV_ITEMS = ['Overview', 'Prop research', 'Teammates', 'Career H2H', 'Team defense', 'Scouting report', 'Compare players', 'Watchlist', 'VIP access']
FOXK_WORKSPACES = {
    '🎯 Prop Lab': ['Prop research'],
    '📈 Player Trends': ['Overview', 'Compare players'],
    '🛡️ Matchup Intel': ['Team defense', 'Career H2H', 'Scouting report'],
    '👥 Lineup Impact': ['Teammates'],
    '⭐ My Watchlist': ['Watchlist'],
}
FOXK_SECTION_LABELS = {
    'Prop research': 'Prop research', 'Overview': 'Game logs & trends',
    'Compare players': 'Compare players', 'Team defense': 'Opponent defense',
    'Career H2H': 'Career head-to-head', 'Scouting report': 'Scouting notes',
    'Teammates': 'Teammate availability', 'Watchlist': 'Saved props',
}
FOXK_SUBTITLES = {
    '🎯 Prop Lab': 'Evaluate the line, recent results, and sample size.',
    '📈 Player Trends': 'Inspect consistency, minutes, and historical game logs.',
    '🛡️ Matchup Intel': 'Explore opponent context, head-to-head records, and scouting notes.',
    '👥 Lineup Impact': 'Compare recorded games with and without selected teammates.',
    '⭐ My Watchlist': 'Save and export your research before game time.',
}
if 'foxk_section' not in st.session_state:
    st.session_state.foxk_section = 'Prop research'
if st.session_state.foxk_section not in NAV_ITEMS:
    st.session_state.foxk_section = 'Prop research'

def foxk_workspace_for_section(section):
    return next((workspace for workspace, children in FOXK_WORKSPACES.items()
                 if section in children), '🎯 Prop Lab')

if 'foxk_workspace' not in st.session_state:
    st.session_state.foxk_workspace = foxk_workspace_for_section(st.session_state.foxk_section)

def foxk_choose_workspace(workspace):
    st.session_state.foxk_workspace = workspace
    if st.session_state.foxk_section not in FOXK_WORKSPACES[workspace]:
        st.session_state.foxk_section = FOXK_WORKSPACES[workspace][0]

def foxk_choose_section(section):
    st.session_state.foxk_section = section

st.markdown('''<div class="foxk-workspace-heading"><span>FOXK / RESEARCH WORKSPACE</span><h3>Find the evidence behind the pick.</h3><p>Explore player form, matchup context and line history without mistaking past results for future probabilities.</p></div>''', unsafe_allow_html=True)

workspaces = list(FOXK_WORKSPACES)
for offset, count in [(0, 3), (3, 2)]:
    row = st.columns(count, gap='small')
    for col, workspace in zip(row, workspaces[offset:offset+count]):
        with col:
            st.button(workspace, key='foxk_workspace_'+str(workspaces.index(workspace)),
                      use_container_width=True,
                      type='primary' if st.session_state.foxk_workspace == workspace else 'secondary',
                      on_click=foxk_choose_workspace, args=(workspace,))

current_workspace = st.session_state.foxk_workspace
st.markdown(f'<div class="foxk-workspace-caption">{FOXK_SUBTITLES[current_workspace]}</div>', unsafe_allow_html=True)
subsections = FOXK_WORKSPACES[current_workspace]
if len(subsections) > 1:
    subcols = st.columns(len(subsections), gap='small')
    for col, section in zip(subcols, subsections):
        with col:
            st.button(FOXK_SECTION_LABELS[section], key='foxk_sub_'+str(NAV_ITEMS.index(section)),
                      use_container_width=True,
                      type='primary' if st.session_state.foxk_section == section else 'secondary',
                      on_click=foxk_choose_section, args=(section,))
st.markdown(f'<div class="foxk-current-section"><strong>{FOXK_SECTION_LABELS.get(st.session_state.foxk_section, st.session_state.foxk_section)}</strong><small>FOXK / {current_workspace.replace("🎯 ", "").replace("📈 ", "").replace("🛡️ ", "").replace("👥 ", "").replace("⭐ ", "").upper()}</small></div>',unsafe_allow_html=True)

st.markdown('''<style>
.foxk-workspace-heading{margin:10px 0 18px;padding:18px 22px;border:1px solid #344963;border-radius:19px;background:linear-gradient(120deg,#1B2A44,#10192C)}
.foxk-workspace-heading span{font-size:10px;font-weight:850;letter-spacing:.16em;color:#FFAD78}
.foxk-workspace-heading h3{font-size:24px!important;margin:7px 0!important;color:#fff!important}
.foxk-workspace-heading p{color:#AFC1DE;font-size:13px;margin:0}
.foxk-workspace-caption{font-size:13px;color:#AFC1DE;margin:10px 0 15px}
</style>''',unsafe_allow_html=True)

st.markdown("""<style>
/* FOXK performance card / game log: App Store edition */
.foxk-chart-kicker{display:flex;justify-content:space-between;gap:12px;align-items:center;color:#ffab77;font-size:11px;font-weight:850;letter-spacing:.15em;margin:18px 0 10px}
.foxk-chart-kicker span{font-size:10px;color:#8194b1;letter-spacing:.10em}
[data-testid="stVegaLiteChart"]{background:linear-gradient(155deg,#121e31,#0e1727)!important;border:1px solid #2d3d54!important;border-radius:22px!important;padding:14px 15px 5px!important;box-shadow:0 12px 35px rgba(0,0,0,.22)}
.foxk-chart-legend{display:flex;gap:20px;flex-wrap:wrap;color:#aebbd0;font-size:12px;margin:8px 0 28px}
.foxk-chart-legend span{display:inline-flex;align-items:center;gap:7px}
.foxk-legend-dot,.foxk-legend-hit{display:inline-block;width:9px;height:9px;border-radius:50%;background:#ff975f}
.foxk-legend-hit{background:#60e3ba}
.foxk-legend-rule{display:inline-block;width:18px;border-top:2px dashed #a1a9c4}
.foxk-log-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:23px 0 15px}
.foxk-log-title h3{margin:3px 0 0!important;font-size:1.65rem!important;letter-spacing:-.04em!important}
.foxk-log-kicker{font-size:10px;font-weight:850;color:#ffab77;letter-spacing:.18em}
.foxk-log-title>span{border:1px solid #354762;background:#18273a;color:#a7bdd7;padding:7px 11px;border-radius:100px;font-size:10px;font-weight:750;letter-spacing:.09em}
[data-testid="stDataFrame"]{border:1px solid #34445d!important;border-radius:19px!important;overflow:hidden!important;box-shadow:0 12px 35px rgba(0,0,0,.19)}
@media(max-width:700px){.foxk-chart-legend{gap:10px}.foxk-log-title h3{font-size:1.35rem!important}}
</style>""",unsafe_allow_html=True)

st.markdown("""<style>
/* FOXK CONTROL DECK: native Streamlit inputs, premium dark finish */
[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div > div,
[data-testid="stMain"] [data-testid="stNumberInput"] [data-baseweb="input"] > div,
[data-testid="stMain"] [data-testid="stNumberInput"] [data-baseweb="input"] > div > div {
  background:#141d30!important;background-color:#141d30!important;
  border-color:#384762!important;color:#f6f7ff!important;
  border-radius:16px!important;min-height:54px!important;
}
[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMain"] [data-testid="stNumberInput"] [data-baseweb="input"] > div {
  border:1px solid #384762!important;
  box-shadow:0 8px 24px rgba(0,0,0,.18),inset 0 1px rgba(255,255,255,.04)!important;
  overflow:hidden!important;
}
[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] *,
[data-testid="stMain"] [data-testid="stNumberInput"] input {
  color:#f6f7ff!important;-webkit-text-fill-color:#f6f7ff!important;
  background-color:transparent!important;font-weight:700!important;
}
[data-testid="stMain"] [data-testid="stNumberInput"] input {padding-left:16px!important;font-size:17px!important;}
[data-testid="stMain"] [data-testid="stNumberInput"] button {
  background:#24314a!important;background-color:#24314a!important;
  color:#ffab7e!important;border:0!important;border-left:1px solid #40516b!important;
  min-width:42px!important;
}
[data-testid="stMain"] [data-testid="stNumberInput"] button:hover{background:#36435d!important}
[data-testid="stMain"] [data-testid="stNumberInput"] button svg,
[data-testid="stMain"] [data-testid="stSelectbox"] svg {color:#ffad7f!important;fill:#ffad7f!important}
[data-testid="stMain"] [data-testid="stWidgetLabel"] p {
  color:#c4cee1!important;font-size:12px!important;letter-spacing:.055em!important;
  text-transform:uppercase!important;font-weight:800!important;
}
[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within,
[data-testid="stMain"] [data-testid="stNumberInput"] [data-baseweb="input"] > div:focus-within {
  border-color:#ff995e!important;box-shadow:0 0 0 3px rgba(255,153,94,.16)!important;
}
[data-baseweb="popover"] [role="listbox"],
[data-baseweb="popover"] [role="option"]{background:#182238!important;color:#f7f8ff!important}
[data-baseweb="popover"] [role="option"]:hover{background:#30405d!important}
.foxk-controls-title{margin:10px 0 14px;padding:14px 18px;border:1px solid #34445f;
 border-radius:17px;background:linear-gradient(110deg,#1b2840,#111a2b);display:flex;
 justify-content:space-between;align-items:center;gap:12px}
.foxk-controls-title strong{font-size:15px;color:#fff;letter-spacing:-.01em}
.foxk-controls-title span{color:#ffa56d;font-size:10px;letter-spacing:.13em;font-weight:850}
@media(max-width:640px){.foxk-controls-title{padding:12px 14px}}
</style>""",unsafe_allow_html=True)

st.markdown("""<style>
/* FOXK FINAL INPUT SKIN — target the real input nodes, not only wrappers */
[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] input,
[data-testid="stMain"] [data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stMain"] [data-testid="stNumberInput"] [data-baseweb="input"] > div,
[data-testid="stMain"] [data-testid="stNumberInput"] input,
[data-testid="stMain"] [data-testid="stNumberInput"] input[type="number"] {
 background:#111d31!important;background-color:#111d31!important;
 color:#fff!important;-webkit-text-fill-color:#fff!important;
 caret-color:#ff995d!important;
}
[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMain"] [data-testid="stNumberInput"] [data-baseweb="input"] {
 border:1px solid #3d536f!important;border-radius:18px!important;
 box-shadow:inset 0 1px 0 rgba(255,255,255,.06),0 12px 24px rgba(0,0,0,.24)!important;
 min-height:58px!important;overflow:hidden!important;
}
[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div:hover,
[data-testid="stMain"] [data-testid="stNumberInput"] [data-baseweb="input"]:hover {
 border-color:#ff985d!important;
}
[data-testid="stMain"] [data-testid="stNumberInput"] button {
 background:#243550!important;color:#ffb486!important;
 border-left:1px solid #455a77!important;min-width:47px!important;
}
[data-testid="stMain"] [data-testid="stNumberInput"] button:hover {background:#364968!important}
[data-testid="stMain"] [data-testid="stNumberInput"] input::placeholder {color:#a9b9d1!important;-webkit-text-fill-color:#a9b9d1!important}
[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] span,
[data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] div {color:#f7f9ff!important;-webkit-text-fill-color:#f7f9ff!important}
[data-testid="stMain"] [data-testid="stWidgetLabel"] p {font-size:11px!important;letter-spacing:.11em!important}
</style>""",unsafe_allow_html=True)

# FOXK selectbox final color override — all nested BaseWeb surfaces
st.markdown("""<style>
[data-testid="stMain"] [data-testid="stSelectbox"] div[data-baseweb="select"],
[data-testid="stMain"] [data-testid="stSelectbox"] div[data-baseweb="select"] div,
[data-testid="stMain"] [data-testid="stSelectbox"] div[data-baseweb="select"] [role="combobox"],
[data-testid="stMain"] [data-testid="stSelectbox"] div[data-baseweb="select"] [data-testid="stMarkdownContainer"] {
 background:#111d31!important;background-color:#111d31!important;
 color:#f8fafc!important;-webkit-text-fill-color:#f8fafc!important;
}
[data-testid="stMain"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div:first-child {
 border:1px solid #455b7b!important;border-radius:16px!important;min-height:56px!important;
 box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 10px 24px rgba(0,0,0,.22)!important;
}
[data-testid="stMain"] [data-testid="stSelectbox"] div[data-baseweb="select"] * {
 color:#f8fafc!important;-webkit-text-fill-color:#f8fafc!important;
}
[data-testid="stMain"] [data-testid="stSelectbox"] div[data-baseweb="select"] svg,
[data-testid="stMain"] [data-testid="stSelectbox"] div[data-baseweb="select"] svg path {
 color:#ffa66d!important;fill:#ffa66d!important;
}
[data-testid="stMain"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div:first-child:hover {border-color:#ff995d!important}
[data-testid="stMain"] [data-testid="stSelectbox"] div[data-baseweb="select"] > div:first-child:focus-within {border-color:#ff995d!important;box-shadow:0 0 0 3px rgba(255,153,93,.17)!important}
</style>""", unsafe_allow_html=True)

# FOXK native dark-theme dropdown fallback, works across BaseWeb variants.
st.markdown("""<style>
.stApp [data-testid="stSelectbox"] [role="combobox"],
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div,
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div > div,
.stApp [data-testid="stSelectbox"] input,
.stApp div[data-baseweb="select"] > div,
.stApp div[data-baseweb="select"] > div > div {
  background-color:#111d31!important;
  color:#f8fafc!important;
  -webkit-text-fill-color:#f8fafc!important;
}
.stApp [data-testid="stSelectbox"] [role="combobox"],
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div {
  border-radius:16px!important;border:1px solid #435876!important;
}
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] svg {fill:#ff995d!important;color:#ff995d!important}
</style>""", unsafe_allow_html=True)

# FOXK dropdown: remove the pale outer shell and theme the OPEN menu as well.
st.markdown(r"""<style>
/* Every nested surface of the select, including the pale right-hand arrow rail. */
.stApp [data-testid="stSelectbox"],
.stApp [data-testid="stSelectbox"] div,
.stApp [data-testid="stSelectbox"] [role="combobox"],
.stApp [data-testid="stSelectbox"] [data-baseweb="select"],
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] *,
.stApp [data-testid="stSelectbox"] input {
  background-color:#111d31 !important;
  color:#f8fafc !important;
  -webkit-text-fill-color:#f8fafc !important;
}
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div {
  border:1px solid #435876 !important;
  border-radius:16px !important;
  overflow:hidden !important;
  box-shadow:0 10px 22px rgba(0,0,0,.2) !important;
}
.stApp [data-testid="stSelectbox"] [data-baseweb="select"]:focus-within > div {
  border-color:#ff995d !important;
  box-shadow:0 0 0 2px rgba(255,153,93,.15) !important;
}
.stApp [data-testid="stSelectbox"] svg,
.stApp [data-testid="stSelectbox"] svg path {
  color:#ff995d !important;
  fill:#ff995d !important;
}
/* Streamlit renders opened dropdowns in a portal outside the select element. */
body [data-baseweb="popover"],
body [data-baseweb="popover"] > div,
body [data-baseweb="popover"] [data-baseweb="menu"],
body [data-baseweb="popover"] [role="listbox"],
body [data-baseweb="popover"] [role="option"],
body [data-baseweb="popover"] li,
body [data-baseweb="menu"],
body [data-baseweb="menu"] li,
body [role="listbox"],
body [role="listbox"] [role="option"] {
  background-color:#111d31 !important;
  color:#f8fafc !important;
  -webkit-text-fill-color:#f8fafc !important;
  border-color:#344763 !important;
}
body [data-baseweb="popover"] [role="option"]:hover,
body [data-baseweb="popover"] li:hover,
body [role="listbox"] [role="option"]:hover,
body [role="listbox"] [aria-selected="true"] {
  background-color:#263a55 !important;
  color:#ffb486 !important;
  -webkit-text-fill-color:#ffb486 !important;
}
body [data-baseweb="popover"] input,
body [data-baseweb="popover"] [data-baseweb="input"] {
  background-color:#17263c !important;
  color:#f8fafc !important;
  -webkit-text-fill-color:#f8fafc !important;
}
</style>""", unsafe_allow_html=True)


# Distinctive FOXK chart design: orange area, green hit dots, floating threshold.
def foxk_overview_chart(data, stat, threshold):
    base = alt.Chart(data).encode(
        x=alt.X('_game_index:Q', title=None,
                axis=alt.Axis(grid=False, labelColor='#A5B8D5', tickMinStep=1, domain=False)),
        y=alt.Y('_value:Q', title=None, scale=alt.Scale(zero=False, padding=24),
                axis=alt.Axis(gridColor='#293C58', labelColor='#A5B8D5', domain=False)),
        tooltip=[alt.Tooltip('_game_label:N', title='GAME'),
                 alt.Tooltip('_opponent:N', title='OPPONENT'),
                 alt.Tooltip('_value:Q', title=stat, format='.1f'),
                 alt.Tooltip('_result:N', title='RESULT')],
    )
    glow = base.mark_line(color='#FF995D', strokeWidth=10, opacity=.12, interpolate='monotone')
    fill = base.mark_area(color=alt.Gradient(
        gradient='linear', x1=0, y1=0, x2=0, y2=1,
        stops=[alt.GradientStop(color='#FF995D', offset=0),
               alt.GradientStop(color='#101B2E', offset=1)]
    ), opacity=.23, interpolate='monotone')
    line = base.mark_line(color='#FF995D', strokeWidth=3.5, interpolate='monotone')
    dots = base.mark_circle(size=120, stroke='#101B2E', strokeWidth=2).encode(
        color=alt.condition(alt.datum._hit, alt.value('#40E0B2'), alt.value('#FF995D')))
    ref = alt.Chart(pd.DataFrame({'target':[float(threshold)]})).mark_rule(
        color='#B9C9E4', strokeDash=[7,5], strokeWidth=2
    ).encode(y='target:Q')
    chart=(fill + glow + ref + line + dots).properties(
        height=350, background='#101B2E'
    ).configure_view(stroke='#344963', cornerRadius=18).configure_axis(labelFontSize=12)
    st.altair_chart(chart, use_container_width=True, theme=None)


# Dark, readable HTML data tables across FOXK's research tabs.
def foxk_dark_table(data, **kwargs):
    from html import escape as _esc
    frame = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
    frame = frame.copy()
    if frame.empty:
        st.info("No rows available.")
        return
    for col in frame.columns:
        if pd.api.types.is_datetime64_any_dtype(frame[col]):
            frame[col] = pd.to_datetime(frame[col], errors="coerce", utc=True).dt.strftime("%b %d, %Y")
    focus = next((c for c in ["PTS", "REB", "AST", "3PM", "PRA", "STL", "BLK"] if c in frame.columns), None)
    headers = "".join(f'<th>{_esc(str(c))}</th>' for c in frame.columns)
    rows = []
    for record in frame.itertuples(index=False, name=None):
        cells = []
        for col, value in zip(frame.columns, record):
            if pd.isna(value):
                shown = "—"
            elif isinstance(value, float):
                shown = f"{value:,.1f}" if value != int(value) else f"{value:,.0f}"
            else:
                shown = str(value)
            badge = col in ("W/L", "result", "Result") and shown.upper() in ("W", "L")
            if badge:
                color = "foxk-win" if shown.upper() == "W" else "foxk-loss"
                content = f'<span class="{color}">{_esc(shown)}</span>'
            else:
                content = _esc(shown)
            cls = "foxk-log-focus" if col == focus else ""
            if pd.api.types.is_numeric_dtype(frame[col]):
                cls += " foxk-log-number"
            cells.append(f'<td class="{cls.strip()}">{content}</td>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')
    st.markdown('''<style>
    .foxk-global-table-wrap{width:100%;max-height:520px;overflow:auto;border:1px solid #34445d;
       border-radius:19px;background:#101a2a;box-shadow:0 16px 40px rgba(0,0,0,.22);margin:9px 0 18px}
    .foxk-global-table{width:100%;border-collapse:separate;border-spacing:0;min-width:650px;
       color:#e7eefc;font-family:Inter,system-ui,sans-serif;font-size:13px}
    .foxk-global-table th{position:sticky;top:0;background:#1a2940;color:#afc5e5;
       font-size:11px;letter-spacing:.055em;text-align:left;padding:15px 14px;
       border-bottom:1px solid #354a66;z-index:2;white-space:nowrap}
    .foxk-global-table td{padding:14px;border-bottom:1px solid rgba(125,157,199,.13);white-space:nowrap}
    .foxk-global-table tr:nth-child(even){background:#142137}
    .foxk-global-table tbody tr:hover{background:#233854}
    .foxk-global-table .foxk-log-focus{color:#ffb47c;font-weight:800;background:rgba(255,151,95,.09)}
    .foxk-global-table .foxk-log-number{text-align:right;font-variant-numeric:tabular-nums}
    .foxk-global-table .foxk-win{padding:4px 9px;border-radius:8px;background:#193c36;color:#61e6b5;font-weight:800}
    .foxk-global-table .foxk-loss{padding:4px 9px;border-radius:8px;background:#442635;color:#ff94a2;font-weight:800}
    </style>''' + '<div class="foxk-global-table-wrap"><table class="foxk-global-table"><thead><tr>' + headers +
                '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>', unsafe_allow_html=True)

# FOXK unified visuals for every research section.
def foxk_trend_chart(frame, x_col, series, threshold_name=None):
    """Dark, interactive Altair line chart with honest historical data."""
    view = frame[[x_col] + series].copy()
    view[x_col] = view[x_col].astype(str)
    long = view.melt(id_vars=[x_col], value_vars=series, var_name="Series", value_name="Value")
    long["Value"] = pd.to_numeric(long["Value"], errors="coerce")
    long = long.dropna(subset=["Value"])
    if long.empty:
        st.info("No numeric values available for this chart.")
        return
    names = [name for name in series if name != threshold_name]
    colors = ["#FF995D", "#60A5FA", "#A78BFA", "#38D9AD"]
    palette = [colors[i % len(colors)] for i in range(len(names))]
    if threshold_name:
        names.append(threshold_name)
        palette.append("#A1AFC7")
    base = alt.Chart(long).encode(
        x=alt.X(f"{x_col}:N", sort=None, title=None,
                axis=alt.Axis(labelAngle=-35, labelColor="#A7B8D3", tickColor="#31445F", domain=False)),
        y=alt.Y("Value:Q", title=None, scale=alt.Scale(zero=False),
                axis=alt.Axis(labelColor="#A7B8D3", gridColor="#26354B", domain=False)),
        color=alt.Color("Series:N", scale=alt.Scale(domain=names, range=palette),
                        legend=alt.Legend(orient="top", title=None, labelColor="#D7E2F6")),
        tooltip=[alt.Tooltip(f"{x_col}:N", title="Game"),
                 alt.Tooltip("Series:N"), alt.Tooltip("Value:Q", format=".1f")],
    )
    if threshold_name:
        actual = base.transform_filter(alt.datum.Series != threshold_name)
        limit = base.transform_filter(alt.datum.Series == threshold_name)
        chart = (actual.mark_line(strokeWidth=9, opacity=.13, interpolate="monotone")
                 + actual.mark_line(point=alt.OverlayMarkDef(filled=True, size=90),
                                    strokeWidth=3.5, interpolate="monotone")
                 + limit.mark_line(strokeDash=[7, 5], strokeWidth=2.5))
    else:
        chart = (base.mark_line(strokeWidth=9, opacity=.13, interpolate="monotone")
                 + base.mark_line(point=alt.OverlayMarkDef(filled=True, size=90),
                                  strokeWidth=3.5, interpolate="monotone"))
    chart = chart.properties(height=350, background="#101B2E").configure_view(
        stroke="#344963", cornerRadius=18
    ).configure_axis(labelFontSize=12, titleColor="#C8D5EB")
    st.altair_chart(chart, use_container_width=True, theme=None)

st.markdown("""<style>
/* Global FOXK styling, applies to all nine navigation pages. */
[data-testid="stMain"] [data-testid="stWidgetLabel"] p {
  color:#C1D0E8!important;font-size:12px!important;font-weight:750!important;
  text-transform:uppercase!important;letter-spacing:.065em!important;
}
[data-testid="stMain"] [data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stMain"] [data-testid="stTextArea"] [data-baseweb="textarea"],
[data-testid="stMain"] [data-testid="stDateInput"] [data-baseweb="input"],
[data-testid="stMain"] [data-testid="stTimeInput"] [data-baseweb="input"] {
  background:#111D31!important;border:1px solid #405574!important;
  border-radius:15px!important;overflow:hidden!important;
}
[data-testid="stMain"] [data-testid="stTextInput"] input,
[data-testid="stMain"] [data-testid="stTextArea"] textarea,
[data-testid="stMain"] [data-testid="stDateInput"] input {
  background:#111D31!important;color:#F8FAFC!important;
  -webkit-text-fill-color:#F8FAFC!important;
}
[data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
[data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div > div {
  background:#111D31!important;color:#F8FAFC!important;
  -webkit-text-fill-color:#F8FAFC!important;
}
[data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
  border:1px solid #405574!important;border-radius:15px!important;
}
[data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="tag"] {
  background:#304464!important;color:#FFC19B!important;
}
[data-testid="stMain"] .stButton > button,
[data-testid="stMain"] [data-testid="stDownloadButton"] > button {
  background:#1A2A43!important;color:#F8FAFC!important;
  border:1px solid #425A7B!important;border-radius:14px!important;
  min-height:43px!important;font-weight:700!important;
}
[data-testid="stMain"] .stButton > button:hover,
[data-testid="stMain"] [data-testid="stDownloadButton"] > button:hover {
  background:#263B5A!important;border-color:#FF995D!important;
}
[data-testid="stMain"] [data-testid="stTabs"] [role="tablist"] {
  background:#101B2E!important;border-radius:14px!important;
  padding:5px!important;border:1px solid #344965!important;
}
[data-testid="stMain"] [data-testid="stTabs"] button[role="tab"] {
  color:#A8BAD5!important;border-radius:10px!important;
}
[data-testid="stMain"] [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
  color:#FFF!important;background:#2B405E!important;
}
[data-testid="stMain"] [data-testid="stMetric"] {
  background:linear-gradient(140deg,#19263F,#111B2E)!important;
  border:1px solid #344562!important;border-radius:18px!important;
  padding:18px!important;
}
[data-testid="stMain"] [data-testid="stMetricValue"] {
  color:#FFB184!important;font-weight:800!important;
}
[data-testid="stMain"] [data-testid="stDataFrame"] {
  border:1px solid #344562!important;border-radius:17px!important;
  overflow:hidden!important;
}
[data-testid="stMain"] [data-testid="stAlert"] {
  border-radius:15px!important;
}
</style>""", unsafe_allow_html=True)


# FOXK premium segmented navigation — research sample and any other segmented selectors.
st.markdown("""<style>
/* Override the default white segmented-control button group */
[data-testid="stSegmentedControl"],
[data-testid="stSegmentedControl"] [data-baseweb="button-group"],
[data-testid="stSegmentedControl"] [role="group"],
[data-testid="stSegmentedControl"] > div,
[data-testid="stSegmentedControl"] > div > div {
  background:#111D31!important;
  background-color:#111D31!important;
  border-color:#344966!important;
  border-radius:16px!important;
}
[data-testid="stSegmentedControl"] [role="group"],
[data-testid="stSegmentedControl"] [data-baseweb="button-group"] {
  padding:5px!important;
  border:1px solid #344966!important;
  gap:5px!important;
  box-shadow:0 8px 20px rgba(0,0,0,.18)!important;
}
[data-testid="stSegmentedControl"] button,
[data-testid="stSegmentedControl"] button[kind],
[data-testid="stSegmentedControl"] label {
  background:#17263D!important;
  background-color:#17263D!important;
  color:#C8D7EC!important;
  -webkit-text-fill-color:#C8D7EC!important;
  border:1px solid transparent!important;
  border-radius:11px!important;
  min-height:40px!important;
  font-weight:750!important;
  box-shadow:none!important;
}
[data-testid="stSegmentedControl"] button *,
[data-testid="stSegmentedControl"] label * {
  color:inherit!important;
  -webkit-text-fill-color:inherit!important;
}
[data-testid="stSegmentedControl"] button:hover,
[data-testid="stSegmentedControl"] label:hover {
  background:#263B58!important;
  color:#FFF!important;
  -webkit-text-fill-color:#FFF!important;
}
[data-testid="stSegmentedControl"] button[aria-pressed="true"],
[data-testid="stSegmentedControl"] button[aria-checked="true"],
[data-testid="stSegmentedControl"] button[data-selected="true"],
[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"],
[data-testid="stSegmentedControl"] label:has(input:checked) {
  background:linear-gradient(135deg,#FFB079,#FF8548)!important;
  background-color:#FF995D!important;
  color:#151A26!important;
  -webkit-text-fill-color:#151A26!important;
  border-color:#FFC092!important;
  box-shadow:0 4px 14px rgba(255,153,93,.22)!important;
}
[data-testid="stSegmentedControl"] button[aria-pressed="true"] *,
[data-testid="stSegmentedControl"] button[aria-checked="true"] *,
[data-testid="stSegmentedControl"] button[data-selected="true"] *,
[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"] * {
  color:#151A26!important;
  -webkit-text-fill-color:#151A26!important;
}
</style>""", unsafe_allow_html=True)

# FOXK universal selector theme: buttons, button groups, pills and segmented widgets.
st.markdown("""<style>
.foxk-sample-label {color:#c1d0e8;font-size:12px;font-weight:800;letter-spacing:.08em;margin:12px 0 6px;}
/* Target the current Streamlit ButtonGroup used by pills and segmented controls. */
[data-testid="stButtonGroup"], [data-testid="stButtonGroup"] > div,
[data-testid="stButtonGroup"] [role="group"],
[data-testid="stPills"], [data-testid="stPills"] > div,
[data-testid="stSegmentedControl"], [data-testid="stSegmentedControl"] > div {
 background:#111d31!important;background-color:#111d31!important;
 border-color:#344966!important;color:#f8fafc!important;
}
[data-testid="stButtonGroup"] button,
[data-testid="stPills"] button,
[data-testid="stSegmentedControl"] button {
 background:#1b2a43!important;background-color:#1b2a43!important;
 color:#f8fafc!important;-webkit-text-fill-color:#f8fafc!important;
 border:1px solid #3d5273!important;border-radius:12px!important;
}
[data-testid="stButtonGroup"] button[aria-pressed="true"],
[data-testid="stButtonGroup"] button[aria-checked="true"],
[data-testid="stPills"] button[aria-pressed="true"],
[data-testid="stSegmentedControl"] button[aria-pressed="true"] {
 background:#ff995d!important;background-color:#ff995d!important;
 color:#141b29!important;-webkit-text-fill-color:#141b29!important;
 border-color:#ff995d!important;
}
/* Native sample buttons and any other app buttons: selected=orange, idle=navy. */
[data-testid="stMain"] .stButton > button[kind="secondary"] {
 background:#1b2a43!important;background-color:#1b2a43!important;
 color:#f8fafc!important;-webkit-text-fill-color:#f8fafc!important;
 border:1px solid #3d5273!important;border-radius:12px!important;
}
[data-testid="stMain"] .stButton > button[kind="primary"] {
 background:#ff995d!important;background-color:#ff995d!important;
 color:#141b29!important;-webkit-text-fill-color:#141b29!important;
 border:1px solid #ff995d!important;border-radius:12px!important;
}
[data-testid="stMain"] .stButton > button[kind="primary"] * {
 color:#141b29!important;-webkit-text-fill-color:#141b29!important;
}
</style>""",unsafe_allow_html=True)


# Universal FOXK dark multiselect and popover controls.
st.markdown("""<style>
[data-testid="stMultiSelect"] [data-baseweb="select"],
[data-testid="stMultiSelect"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] input {
 background:#111D31!important;background-color:#111D31!important;
 color:#F8FAFC!important;-webkit-text-fill-color:#F8FAFC!important;
}
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
 border:1px solid #415678!important;border-radius:14px!important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
 background:#2C405F!important;border:1px solid #4C6383!important;
 border-radius:9px!important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span,
[data-testid="stMultiSelect"] [data-baseweb="tag"] svg {
 color:#FFB88A!important;-webkit-text-fill-color:#FFB88A!important;
 fill:#FFB88A!important;
}
[data-testid="stPopover"] button,
[data-testid="stPopover"] button * {
 color:#F8FAFC!important;
}
[data-testid="stPopover"] button {
 background:#1B2B46!important;border:1px solid #415678!important;
 border-radius:14px!important;min-height:46px!important;
}
[data-testid="stPopover"] button:hover {
 border-color:#FF995D!important;background:#273B58!important;
}
div[data-baseweb="popover"],div[data-baseweb="popover"] > div,
div[data-baseweb="popover"] [role="listbox"],
div[data-baseweb="popover"] [role="option"],
div[data-baseweb="menu"] {
 background:#101B2E!important;color:#F8FAFC!important;
}
div[data-baseweb="popover"] [role="option"]:hover,
div[data-baseweb="popover"] [aria-selected="true"] {
 background:#2A405F!important;color:#FFB88A!important;
}
div[data-baseweb="popover"] [data-baseweb="tag"] {
 background:#304563!important;color:#FFB88A!important;
}
</style>""",unsafe_allow_html=True)


st.markdown("""<style>
/* FOXK global dark expandable panels and checkbox pickers */
[data-testid="stExpander"] {
  background:#111D31!important;border:1px solid #3B5376!important;
  border-radius:16px!important;overflow:hidden!important;
}
[data-testid="stExpander"] details,
[data-testid="stExpander"] summary,
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {
  background:#111D31!important;color:#F8FAFC!important;
}
[data-testid="stExpander"] summary:hover {
  background:#1E304C!important;
}
[data-testid="stExpander"] summary p,
[data-testid="stExpander"] summary svg {
  color:#F8FAFC!important;fill:#FF995D!important;
}
[data-testid="stExpander"] [data-testid="stCheckbox"] label {
  background:#1B2C46!important;border:1px solid #3C5474!important;
  border-radius:11px!important;padding:7px 9px!important;
}
[data-testid="stExpander"] [data-testid="stCheckbox"] label:hover {
  border-color:#FF995D!important;
}
[data-testid="stExpander"] [data-testid="stCheckbox"] label p {
  color:#F8FAFC!important;
}
</style>""",unsafe_allow_html=True)


st.markdown("""<style>
/* FIX: Global font rules must not override Streamlit's Material icon glyphs. */
.material-icons,
.material-icons-outlined,
.material-icons-round,
.material-icons-sharp,
.material-icons-two-tone {
  font-family:"Material Icons"!important;
  font-weight:normal!important;font-style:normal!important;
  letter-spacing:normal!important;text-transform:none!important;
  white-space:nowrap!important;word-wrap:normal!important;
  font-feature-settings:"liga"!important;-webkit-font-feature-settings:"liga"!important;
}
.material-symbols-rounded,
.material-symbols-outlined,
.material-symbols-sharp,
span[data-testid="stIconMaterial"] {
  font-family:"Material Symbols Rounded"!important;
  font-weight:normal!important;font-style:normal!important;
  letter-spacing:normal!important;text-transform:none!important;
  white-space:nowrap!important;font-feature-settings:"liga"!important;
  -webkit-font-feature-settings:"liga"!important;
}
[data-testid="stExpander"] summary {
  display:flex!important;align-items:center!important;
  gap:12px!important;min-height:52px!important;
  padding:12px 16px!important;
}
[data-testid="stExpander"] summary p {
  color:#F8FAFC!important;font-weight:750!important;
  margin:0!important;line-height:1.45!important;
}
[data-testid="stExpander"] summary [data-testid="stExpanderToggleIcon"] {
  flex-shrink:0!important;width:22px!important;min-width:22px!important;
  overflow:hidden!important;
}
</style>""",unsafe_allow_html=True)

if st.session_state.foxk_section == NAV_ITEMS[0]:
    st.subheader(f"{selected['name']} — {season-1}–{str(season)[-2:]}")
    with st.expander('Overview filters',expanded=False):
        ov1,ov2,ov3=st.columns(3)
        with ov1: window=st.selectbox('Recent games',[5,10,15,20,40,82],index=1,key='foxk_overview_window')
        with ov2: opponent=st.selectbox('Opponent',['All']+sorted(df['opponent'].dropna().astype(str).unique().tolist()) if 'opponent' in df else ['All'],key='foxk_overview_opp')
        with ov3: location=st.selectbox('Location',['All','Home','Away'],key='foxk_overview_location')
    if opponent!='All' and 'opponent' in df: df=df[df['opponent'].astype(str)==opponent]
    if location!='All' and 'homeAway' in df: df=df[df['homeAway'].astype(str).str.lower()==location.lower()]
    df=df.head(window).copy()
    if df.empty:
        st.info('No games match these overview filters.')
        st.stop()
    st.markdown('<div class="foxk-controls-title"><strong>🎯 Prop Control Center</strong><span>BUILD YOUR LINE</span></div>',unsafe_allow_html=True)
    metric_col, line_col = st.columns([1.15, 1], gap='medium')
    with metric_col:
        stat=st.selectbox('Overview metric',valid,key='foxk_overview_stat')
    with line_col:
        line=st.number_input('Overview comparison line',min_value=0.0,value=24.5,step=0.5,key='foxk_overview_line')
    st.caption(f'{len(df)} recorded games match your filters. Sample size is shown explicitly; missing values are excluded.')
    cols=st.columns(min(4,len(valid)))
    for i,key in enumerate(valid[:4]):cols[i].metric(key,f'{df[key].mean():.1f}')
    if stat in valid:
        s=df[stat].dropna()
        if len(s):
            hits=int((s>line).sum()); st.metric(f'{stat} over {line:g} historical hit rate',f'{hits}/{len(s)} ({hits/len(s):.1%})')
            st.caption('Descriptive past hit rate, not a prediction or betting probability. Pushes are not counted as overs.')
            # Premium FOXK trend chart: real game-log data, with an editable comparison line.
            chart_data = df.copy()
            if 'date' in chart_data:
                chart_data['_game_date'] = pd.to_datetime(chart_data['date'], errors='coerce', utc=True)
                chart_data = chart_data.sort_values('_game_date')
            else:
                chart_data['_game_date'] = pd.date_range('2020-01-01', periods=len(chart_data), freq='D', tz='UTC')
            chart_data['_value'] = pd.to_numeric(chart_data[stat], errors='coerce')
            chart_data = chart_data.dropna(subset=['_game_date', '_value']).copy()
            chart_data['_game_label'] = chart_data['_game_date'].dt.strftime('%b %d')
            chart_data['_game_index'] = range(1, len(chart_data) + 1)
            chart_data['_opponent'] = chart_data['opponent'].fillna('Unknown').astype(str) if 'opponent' in chart_data else 'Unknown'
            chart_data['_result'] = chart_data['result'].fillna('—').astype(str) if 'result' in chart_data else '—'
            chart_data['_hit'] = chart_data['_value'].gt(line)
            if not chart_data.empty:
                st.markdown('<div class="foxk-chart-kicker">◉ PERFORMANCE TRACKER <span>RECORDED GAMES ONLY</span></div>', unsafe_allow_html=True)
                foxk_overview_chart(chart_data, stat, line)
                st.markdown(f'<div class="foxk-chart-legend"><span><i class="foxk-legend-dot"></i> Recorded {stat}</span><span><i class="foxk-legend-rule"></i> Comparison line {line:g}</span><span><i class="foxk-legend-hit"></i> Above line</span></div>',unsafe_allow_html=True)
    st.markdown('<div class="foxk-log-title"><div><div class="foxk-log-kicker">THE RECEIPTS</div><h3>Verified game log</h3></div><span>ESPN GAME DATA</span></div>',unsafe_allow_html=True)
    show=[c for c in ['date','opponent','homeAway','result','MIN','PTS','REB','AST','3PM','STL','BLK'] if c in df.columns]
    display_log=df[show].copy()
    if 'date' in display_log:
        formatted_dates=pd.to_datetime(display_log['date'],errors='coerce',utc=True)
        display_log['date']=formatted_dates.dt.strftime('%b %d, %Y').fillna(display_log['date'].astype(str))
    display_log=display_log.rename(columns={'date':'DATE','opponent':'OPP','homeAway':'VENUE','result':'W/L'})
    numeric_cols=[col for col in ['MIN','PTS','REB','AST','3PM','STL','BLK'] if col in display_log]
    for col in numeric_cols:
        display_log[col]=pd.to_numeric(display_log[col],errors='coerce')
    # FOXK native dark game log: HTML avoids the Streamlit dataframe's white grid.
    from html import escape as _foxk_escape
    _foxk_css = """
    <style>
    .foxk-log-scroll{width:100%;max-height:490px;overflow:auto;border:1px solid #34445d;
      border-radius:20px;background:#101a2a;box-shadow:0 16px 40px rgba(0,0,0,.24);margin:8px 0 16px}
    .foxk-log-table{width:100%;border-collapse:separate;border-spacing:0;min-width:790px;
      font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#e7eefc;font-size:13px}
    .foxk-log-table thead th{position:sticky;top:0;z-index:2;text-align:left;padding:15px 14px;
      background:#1a2940;color:#9fb5d0;font-size:10px;letter-spacing:.12em;font-weight:800;
      border-bottom:1px solid #354a66}
    .foxk-log-table tbody td{padding:14px;border-bottom:1px solid rgba(125,157,199,.13);white-space:nowrap}
    .foxk-log-table tbody tr:nth-child(even){background:#142137}
    .foxk-log-table tbody tr:hover{background:#233854}
    .foxk-log-table tbody tr:last-child td{border-bottom:0}
    .foxk-log-table td.foxk-log-focus{color:#ffb47c;font-weight:850;background:rgba(255,151,95,.11)}
    .foxk-log-table td.foxk-log-number{text-align:right;font-variant-numeric:tabular-nums}
    .foxk-log-table th.foxk-log-number{text-align:right}
    .foxk-log-table .foxk-win{display:inline-flex;padding:4px 9px;border-radius:8px;
      background:rgba(77,213,159,.13);color:#61e6b5;font-weight:800}
    .foxk-log-table .foxk-loss{display:inline-flex;padding:4px 9px;border-radius:8px;
      background:rgba(255,113,129,.12);color:#ff94a2;font-weight:800}
    .foxk-log-table td:first-child{font-weight:650;color:#f3f7ff}
    @media(max-width:700px){.foxk-log-table{font-size:12px}.foxk-log-table tbody td{padding:12px}}
    </style>
    """
    _foxk_headers=''.join('<th class="foxk-log-number">'+_foxk_escape(str(c))+'</th>' if c in numeric_cols else '<th>'+_foxk_escape(str(c))+'</th>' for c in display_log.columns)
    _foxk_rows=[]
    for _, _foxk_record in display_log.iterrows():
        _foxk_cells=[]
        for _foxk_col in display_log.columns:
            _foxk_val=_foxk_record[_foxk_col]
            _foxk_txt='—' if pd.isna(_foxk_val) else (f'{float(_foxk_val):.0f}' if _foxk_col in numeric_cols else str(_foxk_val))
            _foxk_class='foxk-log-number' if _foxk_col in numeric_cols else ''
            if _foxk_col == stat:
                _foxk_class+=' foxk-log-focus'
            if _foxk_col == 'W/L' and _foxk_txt.upper() in ('W','L'):
                _foxk_badge='foxk-win' if _foxk_txt.upper()=='W' else 'foxk-loss'
                _foxk_content=f'<span class="{_foxk_badge}">{_foxk_escape(_foxk_txt)}</span>'
            else:
                _foxk_content=_foxk_escape(_foxk_txt)
            _foxk_cells.append(f'<td class="{_foxk_class.strip()}">{_foxk_content}</td>')
        _foxk_rows.append('<tr>'+''.join(_foxk_cells)+'</tr>')
    st.markdown(_foxk_css+'<div class="foxk-log-scroll"><table class="foxk-log-table"><thead><tr>'+_foxk_headers+'</tr></thead><tbody>'+''.join(_foxk_rows)+'</tbody></table></div>',unsafe_allow_html=True)
    st.download_button('Download actual results (CSV)',df.to_csv(index=False).encode(),file_name='foxk_real_game_log.csv',mime='text/csv')

# All 30 NBA franchises are selectable, including teams not yet faced this season.
FOXK_ALL_NBA_TEAMS=['ATL','BOS','BKN','CHA','CHI','CLE','DAL','DEN','DET','GSW','HOU','IND','LAC','LAL','MEM','MIA','MIL','MIN','NOP','NYK','OKC','ORL','PHI','PHX','POR','SAC','SAS','TOR','UTA','WAS']

if st.session_state.foxk_section == NAV_ITEMS[1]:
    st.subheader('Prop research 2.0')
    st.caption('Historical game-log research. All rates use recorded games with numeric stats; pushes are excluded from decisions.')
    prop_source=player_log(selected['id'],season).copy()
    if prop_source.empty:
        st.info('No game logs were returned for this season.')
    else:
        if 'event_id' in prop_source:
            prop_source=prop_source.drop_duplicates(subset=['event_id'])
        if 'date' in prop_source:
            prop_source=prop_source.sort_values('date',ascending=False)
        for combo,parts in {'PRA':['PTS','REB','AST'],'PR':['PTS','REB'],'PA':['PTS','AST'],'RA':['REB','AST']}.items():
            if all(c in prop_source for c in parts):
                prop_source[combo]=prop_source[parts].sum(axis=1,min_count=len(parts))
        available=[c for c in ['PTS','REB','AST','3PM','STL','BLK','PRA','PR','PA','RA'] if c in prop_source and prop_source[c].notna().any()]
        if not available:
            st.warning('ESPN did not return numeric game-log statistics for this player.')
        else:
            a,b,c=st.columns(3)
            with a: prop_metric=st.selectbox('Statistic',available,key='foxk_prop20_metric')
            # Auto-fill a pregame sportsbook line; manual editing stays enabled.
            # Load once per five minutes via foxk_odds.get_nba_prop_odds cache.
            auto_line = None
            auto_book = None
            auto_issue = None
            try:
                from foxk_odds import get_nba_prop_odds
                import unicodedata

                def _foxk_name(value):
                    normalized = unicodedata.normalize('NFKD', str(value or ''))
                    return ''.join(ch for ch in normalized.casefold() if ch.isalnum())

                market_key = {
                    'PTS': 'player_points', 'REB': 'player_rebounds',
                    'AST': 'player_assists', '3PM': 'player_threes',
                    'STL': 'player_steals', 'BLK': 'player_blocks',
                    'PRA': 'player_points_rebounds_assists',
                    'PR': 'player_points_rebounds',
                    'PA': 'player_points_assists',
                    'RA': 'player_rebounds_assists',
                }.get(prop_metric)
                odds_data = get_nba_prop_odds() if market_key else []
                events = odds_data if isinstance(odds_data, list) else odds_data.get('events', odds_data.get('data', []))
                if not isinstance(events, list):
                    events = []
                candidates = []
                now_utc = dt.datetime.now(dt.timezone.utc)
                for event in events:
                    if not isinstance(event, dict) or event.get('live'):
                        continue
                    start_time = event.get('commence_time')
                    if start_time:
                        try:
                            game_start = dt.datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                            if game_start.tzinfo and game_start < now_utc:
                                continue
                        except (TypeError, ValueError):
                            continue
                    for book in event.get('bookmakers', []):
                        if not isinstance(book, dict):
                            continue
                        for market in book.get('markets', []):
                            if market.get('key') != market_key:
                                continue
                            by_line = {}
                            for outcome in market.get('outcomes', []):
                                if not isinstance(outcome, dict):
                                    continue
                                if _foxk_name(outcome.get('description')) != _foxk_name(selected['name']):
                                    continue
                                if str(outcome.get('name', '')).lower() not in ('over', 'under'):
                                    continue
                                try:
                                    point = float(outcome['point'])
                                    price = float(outcome['price'])
                                except (TypeError, ValueError, KeyError):
                                    continue
                                if point < 0:
                                    continue
                                by_line.setdefault(point, {})[outcome['name'].lower()] = price
                            for point, sides in by_line.items():
                                if 'over' not in sides or 'under' not in sides:
                                    continue
                                # Prefer the main line (both prices closest to -110).
                                score = abs(sides['over'] + 110) + abs(sides['under'] + 110)
                                candidates.append((score, str(book.get('title') or book.get('key') or 'Sportsbook'), point))
                if candidates:
                    candidates.sort(key=lambda x: (x[0], x[1]))
                    _, auto_book, auto_line = candidates[0]
            except Exception as exc:
                auto_issue = type(exc).__name__

            # Set the widget value BEFORE creating it. Only overwrite manual edits
            # when player/stat changes or the user explicitly refreshes the line.
            line_identity = (str(selected['id']), prop_metric)
            if st.session_state.get('foxk_odds_line_identity') != line_identity:
                st.session_state['foxk_odds_line_identity'] = line_identity
                st.session_state['foxk_prop20_line'] = float(auto_line) if auto_line is not None else 0.0
            with b:
                prop_line = st.number_input('Research threshold', min_value=0.0,
                    step=0.5, key='foxk_prop20_line')
            if auto_line is not None:
                st.caption(f'Pregame sportsbook line: {auto_line:g} · {auto_book}. Research threshold is editable; sportsbook quotes may change.')
                if st.button('Use latest sportsbook line', key='foxk_odds_reset'):
                    st.session_state['foxk_prop20_line'] = float(auto_line)
                    st.rerun()
            elif auto_issue:
                st.caption(f'Live sportsbook line unavailable ({auto_issue}). Enter the research threshold manually.')
            else:
                st.caption('No matching pregame sportsbook line available. Enter the research threshold manually.')
            with c: prop_side=st.selectbox('Direction',['Over','Under'],key='foxk_prop20_side')
            st.markdown('#### Prop Research 3.0 — quick sample comparison')
            quick_rows=[]
            for label,n in [('Last 5',5),('Last 10',10),('Last 20',20),('Full season',len(prop_source))]:
                sample=prop_source[prop_metric].dropna().head(n)
                if sample.empty: continue
                over=(sample>prop_line).sum()
                under=(sample<prop_line).sum()
                pushes=(sample==prop_line).sum()
                decisions=len(sample)-pushes
                hits=over if prop_side=='Over' else under
                quick_rows.append({'Sample':label,'Games':len(sample),'Average':round(float(sample.mean()),2),
                                   'Hits':int(hits),'Decisions':int(decisions),
                                   'Hit rate':f'{hits/decisions:.0%}' if decisions else 'N/A'})
            if quick_rows: foxk_dark_table(pd.DataFrame(quick_rows),hide_index=True,use_container_width=True)
            st.caption('These windows use all available games before applying the matchup filters below. Descriptive results only.')
            f1,f2,f3=st.columns(3)
            with f1:
                opponents=FOXK_ALL_NBA_TEAMS
                prop_opp=st.selectbox('Opponent',['All']+opponents,key='foxk_prop20_opp')
            with f2: prop_venue=st.selectbox('Location',['All','Home','Away'],key='foxk_prop20_venue')
            with f3: prop_sample=st.selectbox('Game window',['All games',5,10,15,20,40,82],key='foxk_prop20_sample')
            f4,f5=st.columns(2)
            with f4: prop_day=st.selectbox('Day of week',['All','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'],key='foxk_prop20_day')
            with f5: prop_rest=st.selectbox('Days off between recorded appearances',['All','0 days','1 day','2+ days'],key='foxk_prop20_rest')
            if 'date' in prop_source and prop_source['date'].notna().any():
                prop_source=prop_source.sort_values('date')
                prop_source['rest_days']=(prop_source['date'].dt.normalize()-prop_source['date'].shift().dt.normalize()).dt.days-1
                prop_source['weekday']=prop_source['date'].dt.day_name()
                prop_source=prop_source.sort_values('date',ascending=False)
            filtered=prop_source.copy()
            if prop_opp!='All' and 'opponent' in filtered:
                filtered=filtered[filtered['opponent'].astype(str).map(lambda x: {'GS':'GSW','NO':'NOP','NY':'NYK','SA':'SAS','UTAH':'UTA','WSH':'WAS'}.get(x.strip().upper(),x.strip().upper()))==prop_opp]
            if prop_venue!='All':
                filtered=filtered[filtered['homeAway'].astype(str).str.lower()==prop_venue.lower()] if 'homeAway' in filtered else filtered.iloc[0:0]
            if prop_day!='All':
                filtered=filtered[filtered['weekday']==prop_day] if 'weekday' in filtered else filtered.iloc[0:0]
            if prop_rest!='All':
                if 'rest_days' not in filtered: filtered=filtered.iloc[0:0]
                elif prop_rest=='0 days': filtered=filtered[filtered['rest_days']==0]
                elif prop_rest=='1 day': filtered=filtered[filtered['rest_days']==1]
                else: filtered=filtered[filtered['rest_days']>=2]
            if prop_sample!='All games': filtered=filtered.head(int(prop_sample))
            filtered=filtered[filtered[prop_metric].notna()].copy()
            if filtered.empty:
                st.warning('No recorded games against this opponent in the selected season.' if prop_opp!='All' and not prop_source['opponent'].astype(str).map(lambda x: {'GS':'GSW','NO':'NOP','NY':'NYK','SA':'SAS','UTAH':'UTA','WSH':'WAS'}.get(x.strip().upper(),x.strip().upper())).eq(prop_opp).any() else 'No games match these filters. Broaden your selection to see results.')
            else:
                vals=filtered[prop_metric]
                hit=(vals>prop_line) if prop_side=='Over' else (vals<prop_line)
                push=vals==prop_line
                decisions=int((~push).sum())
                n_hits=int(hit.sum())
                m1,m2,m3,m4=st.columns(4)
                m1.metric('Recorded games',len(vals))
                m2.metric('Average',f'{vals.mean():.1f}')
                m3.metric('Median',f'{vals.median():.1f}')
                m4.metric(f'{prop_side} hit rate',f'{n_hits}/{decisions} ({n_hits/decisions:.0%})' if decisions else 'No decisions')
                st.caption(f'{int(push.sum())} pushes excluded from the hit-rate denominator. The selected sample is descriptive, not predictive.')
                st.markdown('#### Recent trend by sample size')
                trends=[]
                for label,n in [('Last 5',5),('Last 10',10),('Last 20',20),('All filtered',len(filtered))]:
                    part=filtered.head(n)[prop_metric]
                    wins=(part>prop_line) if prop_side=='Over' else (part<prop_line)
                    valid=part!=prop_line
                    count=int(valid.sum())
                    trends.append({'Window':label,'Games':len(part),'Average':round(float(part.mean()),1),
                                   'Hits':int(wins.sum()),'Decisions':count,
                                   'Hit rate':f'{int(wins.sum())/count:.0%}' if count else 'N/A'})
                foxk_dark_table(pd.DataFrame(trends),hide_index=True,use_container_width=True)
                st.markdown('#### Game-by-game results vs. threshold')
                graph=filtered.copy()
                graph['Threshold']=prop_line
                graph['Actual']=graph[prop_metric]
                if 'date' in graph and graph['date'].notna().all():
                    graph=graph.sort_values('date')
                    graph['Game']=graph['date'].dt.strftime('%b %d')
                else:
                    graph=graph.iloc[::-1].copy()
                    graph['Game']=[f'Game {i+1}' for i in range(len(graph))]
                graph['Outcome']=graph['Actual'].apply(lambda v:'Push' if v==prop_line else ('Hit' if (v>prop_line if prop_side=='Over' else v<prop_line) else 'Miss'))
                foxk_trend_chart(graph, 'Game', ['Actual', 'Threshold'], threshold_name='Threshold')
                st.caption('The line chart plots observed game totals and your research threshold; it does not project future results.')
                st.markdown('#### Opponent comparison')
                if 'opponent' in filtered and filtered['opponent'].notna().any():
                    opponent_rows=[]
                    for code,group in filtered.groupby('opponent',dropna=True):
                        x=group[prop_metric]
                        wins=(x>prop_line) if prop_side=='Over' else (x<prop_line)
                        decision=int((x!=prop_line).sum())
                        opponent_rows.append({'Opponent':str(code),'Games':len(x),'Average':round(float(x.mean()),1),
                                              'Hits':int(wins.sum()),'Decisions':decision,
                                              'Hit rate':f'{int(wins.sum())/decision:.0%}' if decision else 'N/A'})
                    foxk_dark_table(pd.DataFrame(opponent_rows).sort_values(['Games','Opponent'],ascending=[False,True]),hide_index=True,use_container_width=True)
                else: st.caption('Opponent labels are not available for these game logs.')
                st.markdown('#### Home / away comparison')
                if 'homeAway' in filtered and filtered['homeAway'].notna().any():
                    venue_rows=[]
                    for venue,group in filtered.groupby(filtered['homeAway'].astype(str).str.title()):
                        x=group[prop_metric]
                        wins=(x>prop_line) if prop_side=='Over' else (x<prop_line)
                        decision=int((x!=prop_line).sum())
                        venue_rows.append({'Location':venue,'Games':len(x),'Average':round(float(x.mean()),1),
                                           'Hits':int(wins.sum()),'Decisions':decision,
                                           'Hit rate':f'{int(wins.sum())/decision:.0%}' if decision else 'N/A'})
                    foxk_dark_table(pd.DataFrame(venue_rows),hide_index=True,use_container_width=True)
                else: st.caption('Home/away labels are not available for these game logs.')
                st.markdown('#### Auditable game log')
                cols=[k for k in ['date','opponent','homeAway','weekday','rest_days','MIN','PTS','REB','AST','3PM','STL','BLK',prop_metric] if k in filtered]
                cols=list(dict.fromkeys(cols))
                audit=filtered[cols].copy()
                audit['Outcome']=graph['Outcome'].reindex(audit.index)
                foxk_dark_table(audit,use_container_width=True,hide_index=True)
                st.download_button('Download research (CSV)',audit.to_csv(index=False).encode('utf-8'),
                                   file_name=f'FOXK_{selected["id"]}_{prop_metric}_{season}_prop.csv',mime='text/csv',key='foxk_prop20_csv')
                st.caption('Small matchup samples can be misleading. Days off are inferred from player appearances, not official team schedules. ESPN endpoints are unofficial.')


if st.session_state.foxk_section == NAV_ITEMS[2]:
    st.subheader('Teammate availability comparison')
    st.caption('Compares games where a teammate is recorded playing versus games without a recorded appearance. A missing appearance is NOT proof of an injury or official OUT designation.')

    # Compare the complete selected-player log before applying opponent/location/recent-game filters.
    # Matching by ESPN event ID prevents accidental comparison across different dates or teams.
    try:
        full_player_log=player_log(selected['id'],season)
        candidates=[p for p in all_players if p['id']!=selected['id'] and p['team']==selected['team']]
        if not candidates:
            st.info('No current teammates found in the ESPN roster index.')
        else:
            teammate=st.selectbox('Compare with teammate',candidates,
                format_func=lambda p:p['name'],key='foxk_teammate_comparison')
            with st.spinner('Retrieving teammate appearances from ESPN…'):
                mate_log=player_log(teammate['id'],season)
            if full_player_log.empty or 'event_id' not in full_player_log.columns:
                st.warning('Selected player game IDs are unavailable; cannot calculate an accurate comparison.')
            elif mate_log.empty or 'event_id' not in mate_log.columns:
                st.warning('Teammate game IDs are unavailable for this season. Cannot determine appearances.')
            else:
                comparison=full_player_log.copy()
                comparison=comparison[comparison['event_id'].astype(str).str.len()>0]
                comparison=comparison.drop_duplicates(subset=['event_id'])
                mate_events=set(mate_log.loc[mate_log['event_id'].astype(str).str.len()>0,'event_id'].astype(str))
                comparison['Teammate recorded']=comparison['event_id'].astype(str).isin(mate_events)
                if 'MIN' in mate_log.columns:
                    # If minutes are numeric, zero-minute entries are not treated as played.
                    valid_minutes=mate_log['MIN'].notna()
                    if valid_minutes.any():
                        minute_events=set(mate_log.loc[valid_minutes & (mate_log['MIN']>0),'event_id'].astype(str))
                        unknown_events=set(mate_log.loc[~valid_minutes,'event_id'].astype(str))
                        comparison['Teammate recorded']=comparison['event_id'].astype(str).isin(minute_events | unknown_events)
                st.caption('Comparison uses all available recorded season games, independent of Overview filters.')
                metrics=[c for c in ['PTS','REB','AST','3PM','STL','BLK','MIN'] if c in comparison.columns and comparison[c].notna().any()]
                if comparison.empty or not metrics:
                    st.warning('No comparable games or numeric stats available.')
                else:
                    grouped=[]
                    for flag, label in [(True,'Teammate recorded playing'),(False,'No teammate appearance recorded')]:
                        part=comparison[comparison['Teammate recorded']==flag]
                        row={'Group':label,'Games':len(part)}
                        for metric in metrics:
                            row[metric]=round(float(part[metric].mean()),2) if part[metric].notna().any() else None
                        grouped.append(row)
                    foxk_dark_table(pd.DataFrame(grouped),use_container_width=True,hide_index=True)
                    st.caption('Interpretation: "No teammate appearance recorded" can include injuries, rest, DNP, roster changes, missing ESPN logs, or data gaps. These are NOT confirmed official injury-out splits. Current-roster membership does not prove both players were teammates for every historical game.')
                    with st.expander('See games used in the comparison'):
                        fields=[c for c in ['date','opponent','homeAway','Teammate recorded','PTS','REB','AST','3PM','MIN'] if c in comparison.columns]
                        foxk_dark_table(comparison[fields],use_container_width=True,hide_index=True)
    except Exception as e:
        st.warning(f'Teammate comparison is temporarily unavailable: {e}')


    st.markdown('### Multiple teammates — all recorded playing vs. at least one not recorded')
    st.caption('Uses appearance records, not official injury statuses. Historical roster changes may make some comparisons invalid; inspect individual game dates.')
    extra=st.multiselect('Choose up to 3 teammates', [p for p in all_players if p['id']!=selected['id'] and p['team']==selected['team']], format_func=lambda p:p['name'],max_selections=3,key='foxk_multi_mates')
    if extra and st.button('Calculate multi-teammate split'):
        base=player_log(selected['id'],season).copy()
        if base.empty or 'event_id' not in base:st.warning('Missing player game identifiers.')
        else:
            base=base.drop_duplicates('event_id')
            missing=[]; statuses=[]
            for mate in extra:
                try:
                    log=player_log(mate['id'],season)
                    if log.empty or 'event_id' not in log:missing.append(mate['name']);continue
                    played=set(log.loc[log['MIN']>0,'event_id'].astype(str)) if 'MIN' in log else set(log['event_id'].astype(str))
                    statuses.append(base['event_id'].astype(str).isin(played))
                except Exception:missing.append(mate['name'])
            if missing:st.warning('Cannot classify these teammates: '+', '.join(missing))
            if statuses and not missing:
                import functools
                base['All selected teammates recorded playing']=functools.reduce(lambda a,b:a & b,statuses)
                metrics=[x for x in ['PTS','REB','AST','PRA','PR','PA','RA','3PM','MIN','FGA','FTA'] if x in base]
                rows=[]
                for flag,name in [(True,'All recorded playing'),(False,'At least one not recorded')]:
                    part=base[base['All selected teammates recorded playing']==flag]
                    row={'Group':name,'Games':len(part)}
                    row.update({m:round(part[m].mean(),2) if part[m].notna().any() else None for m in metrics})
                    rows.append(row)
                foxk_dark_table(pd.DataFrame(rows),hide_index=True,use_container_width=True)
                with st.expander('Audit games and appearances'):
                    foxk_dark_table(base[[x for x in ['date','opponent','All selected teammates recorded playing','PTS','REB','AST','MIN'] if x in base]],hide_index=True,use_container_width=True)

# Shared team lookup must be available in both Career H2H and Team defense.
team_codes=['ATL','BOS','BKN','CHA','CHI','CLE','DAL','DEN','DET','GS','GSW','HOU','IND','LAC','LAL','MEM','MIA','MIL','MIN','NO','NOP','NY','NYK','OKC','ORL','PHI','PHX','POR','SAC','SA','SAS','TOR','UTAH','UTA','WAS','WSH']
# ESPN team abbreviations can vary historically, so normalize known alternatives.
team_aliases={'GSW':{'GSW','GS'},'NOP':{'NOP','NO'},'NYK':{'NYK','NY'},'SAS':{'SAS','SA'},'UTA':{'UTA','UTAH'},'WAS':{'WAS','WSH'}}
canonical=['ATL','BOS','BKN','CHA','CHI','CLE','DAL','DEN','DET','GSW','HOU','IND','LAC','LAL','MEM','MIA','MIL','MIN','NOP','NYK','OKC','ORL','PHI','PHX','POR','SAC','SAS','TOR','UTA','WAS']
def canonical_team(code):
    code=str(code).strip().upper()
    for name,aliases in team_aliases.items():
        if code in aliases:return name
    return code
initial=canonical_team(opponent.strip())
default_idx=canonical.index(initial) if initial in canonical else 0

if st.session_state.foxk_section == NAV_ITEMS[3]:
    st.subheader('Career head-to-head vs. an NBA team')
    st.caption('Independent of the selected season and Overview filters. FOXK retrieves each selected season separately and shows the full verified game history available from ESPN.')
    h2h_team=st.selectbox('Head-to-head opponent',canonical,index=default_idx,key='foxk_h2h_opponent')
    h2h_cols=st.columns(2)
    with h2h_cols[0]: stat=st.selectbox('H2H metric',['PTS','REB','AST','3PM','STL','BLK','PRA','PR','PA','RA'],key='foxk_h2h_stat')
    with h2h_cols[1]: line=st.number_input('H2H comparison line',min_value=0.0,value=24.5,step=0.5,key='foxk_h2h_line')
    # End-year values, e.g. 2027 means the 2026-27 season.
    # Compact season picker using native checkboxes rather than the white BaseWeb multi-select.
    # No popup, overlapping arrow glyphs, or bright red chips.
    if 'foxk_h2h_year_selection' not in st.session_state:
        st.session_state.foxk_h2h_year_selection = list(range(2027, 2016, -1))
    selected_years = st.session_state.foxk_h2h_year_selection
    st.markdown('**HISTORICAL SEASONS TO INCLUDE**')
    with st.expander(f"📅  {len(selected_years)} seasons selected  ·  Edit seasons", expanded=False):
        st.caption("Select the NBA season ending years to include in Career H2H.")
        season_cols = st.columns(4)
        updated_years = []
        for idx, year in enumerate(range(2027, 2010, -1)):
            with season_cols[idx % 4]:
                checked = st.checkbox(
                    f"{year-1}–{str(year)[-2:]}",
                    value=year in selected_years,
                    key=f"foxk_h2h_season_checkbox_{year}",
                )
                if checked:
                    updated_years.append(year)
        st.session_state.foxk_h2h_year_selection = updated_years
    h2h_years = st.session_state.foxk_h2h_year_selection
    if h2h_years:
        st.caption(f"{len(h2h_years)} seasons selected · {min(h2h_years)-1}–{str(min(h2h_years))[-2:]} through {max(h2h_years)-1}–{str(max(h2h_years))[-2:]}")
    h2h_run=st.button('Load full head-to-head history',type='primary',key='foxk_h2h_load')
    if h2h_run:
        if not h2h_years:
            st.warning('Select at least one historical season.')
        else:
            historical=[]; failures=[]; empties=[]
            bar=st.progress(0,text='Fetching historical game logs…')
            for idx,yr in enumerate(sorted(h2h_years,reverse=True)):
                try:
                    year_log=player_log(selected['id'],yr)
                    if year_log.empty:
                        empties.append(yr)
                    elif 'opponent' not in year_log.columns:
                        failures.append(f'{yr}: opponent field missing')
                    else:
                        filtered=year_log[year_log['opponent'].astype(str).map(canonical_team)==h2h_team].copy()
                        if not filtered.empty:
                            filtered['Season']=f'{yr-1}–{str(yr)[-2:]}'
                            filtered['Season ending']=yr
                            historical.append(filtered)
                except Exception as exc:
                    failures.append(f'{yr}: {str(exc)[:120]}')
                bar.progress((idx+1)/len(h2h_years),text=f'Checked {idx+1} of {len(h2h_years)} seasons')
            bar.empty()
            if failures:
                st.warning('Incomplete history: some seasons could not be retrieved. These are not counted as zero-game seasons: '+ '; '.join(failures[:6]) + (' …' if len(failures)>6 else ''))
            if not historical:
                st.info(f'No verified games found against {h2h_team} in the successfully retrieved seasons. Try selecting additional seasons.')
            else:
                history=pd.concat(historical,ignore_index=True)
                if 'event_id' in history:
                    history=history.drop_duplicates(subset=['event_id','Season ending'])
                if 'date' in history:history=history.sort_values('date',ascending=False)
                st.success(f'{len(history)} verified games against {h2h_team} across {history["Season"].nunique()} seasons retrieved.')
                hmetrics=[m for m in ['PTS','REB','AST','3PM','STL','BLK','MIN'] if m in history and history[m].notna().any()]
                if hmetrics:
                    cols=st.columns(min(4,len(hmetrics)))
                    for i,m in enumerate(hmetrics[:4]):
                        cols[i].metric('Career H2H '+m,f'{history[m].mean():.1f}')
                    summary=history.groupby('Season',sort=False).agg(Games=('Season','size'),**{m:(m,'mean') for m in hmetrics}).reset_index()
                    for m in hmetrics:summary[m]=summary[m].round(1)
                    st.markdown('**Season-by-season head-to-head averages**')
                    foxk_dark_table(summary,use_container_width=True,hide_index=True)
                    if stat in history and history[stat].notna().any():
                        vals=history[stat].dropna()
                        hits=int((vals>line).sum())
                        st.metric(f'Career H2H {stat} over {line:g}',f'{hits}/{len(vals)} ({hits/len(vals):.1%})')
                        st.caption('Historical frequency only, not a future-game probability. The comparison line is selected above.')
                st.markdown('**Every retrieved head-to-head game**')
                display=[c for c in ['Season','date','opponent','homeAway','result','MIN','PTS','REB','AST','3PM','STL','BLK'] if c in history]
                foxk_dark_table(history[display],use_container_width=True,hide_index=True)
                st.download_button('Download career H2H game logs (CSV)',history.to_csv(index=False).encode(),file_name=f'FOXK_{selected["id"]}_vs_{h2h_team}_history.csv',mime='text/csv')
                st.caption('Coverage is limited to seasons selected and successfully returned by ESPN. Includes only game logs ESPN supplies; this is not individual defender tracking.')


if st.session_state.foxk_section == NAV_ITEMS[4]:
    st.subheader('Opponent Defense 2.0')
    st.caption('Actual final-score results from ESPN team schedules. Team scoring allowed is not individual-player or position-specific defense.')
    def_team=st.selectbox('Defensive opponent',canonical,index=default_idx,key='foxk_defense_team')
    try:
        with st.spinner('Loading completed NBA games from ESPN…'):
            defense=team_defensive_sample(def_team,season)
    except Exception as exc:
        defense=pd.DataFrame()
        st.error(f'ESPN team schedule could not be retrieved: {exc}')
    if defense.empty:
        st.info('No completed games with valid scores were returned for this team and season. No defensive numbers are estimated.')
    else:
        st.caption(f'{def_team} · {season-1}–{str(season)[-2:]} season · {len(defense)} completed games returned')
        # Render FOXK sample selection with native buttons rather than Streamlit's white segmented widget.
        # The selected choice persists across reruns and uses the app-wide button theme.
        st.markdown('<div class="foxk-sample-label">RESEARCH SAMPLE</div>', unsafe_allow_html=True)
        choices=['Last 5','Last 10','Last 20','All games']
        if st.session_state.get('foxk_def_period') not in choices:
            st.session_state['foxk_def_period']='Last 10'
        sample_cols=st.columns(4, gap='small')
        for sample_col, sample_choice in zip(sample_cols, choices):
            with sample_col:
                if st.button(sample_choice, key='foxk_sample_'+sample_choice.lower().replace(' ','_'),
                             type='primary' if st.session_state['foxk_def_period']==sample_choice else 'secondary',
                             use_container_width=True):
                    st.session_state['foxk_def_period']=sample_choice
        period=st.session_state['foxk_def_period']
        count={'Last 5':5,'Last 10':10,'Last 20':20,'All games':len(defense)}[period]
        sample=defense.head(count).copy()
        st.caption(f'Sample includes {len(sample)} completed games; smaller-than-requested samples are shown as-is.')
        m=st.columns(4)
        m[0].metric('Points allowed / game',f"{sample['Points allowed'].mean():.1f}")
        m[1].metric('Points scored / game',f"{sample['Points scored'].mean():.1f}")
        m[2].metric('Avg. point margin',f"{sample['Margin'].mean():+.1f}")
        m[3].metric('Games in sample',len(sample))
        st.markdown('#### Defensive trend')
        trend=defense.head(min(20,len(defense))).iloc[::-1]
        foxk_trend_chart(trend, 'Date', ['Points allowed', 'Points scored'])
        st.markdown('#### Home vs. away')
        venues=[]
        for name in ['Home','Away']:
            part=sample[sample['Venue']==name]
            if not part.empty:
                venues.append({'Venue':name,'Games':len(part),'Points allowed / game':round(part['Points allowed'].mean(),1),
                               'Points scored / game':round(part['Points scored'].mean(),1),
                               'Average margin':round(part['Margin'].mean(),1)})
        if venues:foxk_dark_table(pd.DataFrame(venues),hide_index=True,use_container_width=True)
        else:st.caption('ESPN did not return reliable home/away labels for these games.')
        st.markdown('#### Recent form comparison')
        comparisons=[]
        for label,n in [('Last 5',5),('Last 10',10),('Last 20',20),('Season returned',len(defense))]:
            part=defense.head(n)
            comparisons.append({'Period':label,'Games':len(part),'Points allowed / game':round(part['Points allowed'].mean(),1),
                                'Points scored / game':round(part['Points scored'].mean(),1),
                                'Average margin':round(part['Margin'].mean(),1)})
        foxk_dark_table(pd.DataFrame(comparisons),hide_index=True,use_container_width=True)
        st.markdown('#### Completed game log')
        display=['Date','Opponent','Venue','Result','Points allowed','Points scored','Margin']
        foxk_dark_table(sample[display],hide_index=True,use_container_width=True)
        st.download_button('Download defensive research (CSV)',defense.to_csv(index=False).encode('utf-8'),
                           file_name=f'FOXK_{def_team}_{season}_defense.csv',mime='text/csv',key='foxk_def_csv')
        st.caption('Limitations: unadjusted scores are affected by pace, opponent strength, overtime and game context. No individual defender matchups, position rankings, or future outcomes are inferred.')
    st.divider()
    st.info('Player-versus-defender assignments and position-specific defensive ratings are not provided by this free ESPN team schedule feed.')

if st.session_state.foxk_section == NAV_ITEMS[5]:
    st.subheader('FOXK matchup research assistant')
    st.caption('Free rules-based scouting from actual ESPN game logs. No paid AI model, fabricated defender matchups, or invented predictions.')
    scout_a,scout_b,scout_c=st.columns(3)
    with scout_a: stat=st.selectbox('Scouting metric',['PTS','REB','AST','3PM','STL','BLK','PRA','PR','PA','RA'],key='foxk_scout_stat')
    with scout_b: line=st.number_input('Scouting comparison line',min_value=0.0,value=24.5,step=0.5,key='foxk_scout_line')
    with scout_c: opponent=st.selectbox('Scouting opponent',['All']+canonical,key='foxk_scout_opponent')
    if opponent=='All': opponent=''
    source=player_log(selected['id'],season).copy()
    if source.empty:
        st.warning('No game logs available for this report.')
    else:
        if 'date' in source:
            source=source.sort_values('date',ascending=False)
        st.markdown(f"### {selected['name']} — {season-1}–{str(season)[-2:]} scouting brief")
        st.write(f"**Season sample:** {len(source)} recorded game logs. Results below use only games with the relevant numeric stat.")
        st.markdown('#### Form and playing time')
        report_rows=[]
        for m in ['MIN','PTS','REB','AST','3PM','PRA','PR','PA','RA','FGA','FTA']:
            if m not in source: continue
            vals=source[m].dropna()
            if vals.empty: continue
            recent5=vals.head(5)
            recent10=vals.head(10)
            report_rows.append({
                'Metric':m,'Season games':len(vals),
                'Season avg':round(float(vals.mean()),2),
                'Last 5 avg':round(float(recent5.mean()),2),
                'Last 10 avg':round(float(recent10.mean()),2)
            })
        if report_rows:
            foxk_dark_table(pd.DataFrame(report_rows),hide_index=True,use_container_width=True)
        else:
            st.warning('No numeric statistics are available to summarize.')
        st.markdown('#### Selected prop — historical evidence')
        if stat in source:
            for label,part in [('Last 5',source.head(5)),('Last 10',source.head(10)),('Season',source)]:
                r=describe_rates(part,stat,line)
                if r:
                    st.write(f"**{label}:** {r['over']}/{r['games']} over {line:g} {stat} "
                             f"({r['over']/r['games']:.1%}); {r['push']} pushes; "
                             f"average {r['average']:.1f}.")
        else:
            st.info(f'No reliable {stat} values are available.')
        st.markdown('#### Opponent and location')
        if opponent.strip():
            if 'opponent' in source:
                matchup=source[source['opponent'].astype(str).str.upper()==opponent.strip().upper()]
                st.write(f"**Against {opponent.strip().upper()} this season:** {len(matchup)} recorded games.")
                r=describe_rates(matchup,stat,line)
                if r:
                    st.write(f"**{stat}:** {r['average']:.1f} average; {r['over']}/{r['games']} above {line:g}.")
                else:
                    st.info('Insufficient opponent-specific data for the selected stat.')
            else:
                st.info('Opponent codes are unavailable in these game logs.')
        else:
            st.caption('Select an opponent above to add a same-season matchup comparison.')
        if 'homeAway' in source and stat in source:
            loc_rows=[]
            for loc in ['home','away']:
                part=source[source['homeAway'].astype(str).str.lower()==loc]
                r=describe_rates(part,stat,line)
                if r:
                    loc_rows.append({'Location':loc.title(),'Games':r['games'],
                                     f'{stat} avg':r['average'],
                                     'Over hits':r['over'],'Pushes':r['push']})
            if loc_rows:
                foxk_dark_table(pd.DataFrame(loc_rows),hide_index=True,use_container_width=True)
        st.markdown('#### Data-quality checklist')
        st.write('- This report uses game-log averages, not a predictive betting model.')
        st.write('- A teammate missing from a log is not proof of a confirmed injury.')
        st.write('- Team points allowed cannot identify which defender guarded a player.')
        st.write('- Very small opponent and venue samples are especially unstable.')
        st.write('- ESPN endpoints are unofficial and may omit games or change format.')
        st.caption('Source: ESPN public NBA game-log endpoints. Verify the game log and current availability before using these trends.')



if st.session_state.foxk_section == NAV_ITEMS[6]:
    st.subheader('Compare two NBA players')
    st.caption('Side-by-side recorded game-log averages and threshold hit rates. The first player is your search selection.')
    others=[p for p in all_players if p['id']!=selected['id']]
    compare_query=st.text_input('Find second player',key='foxk_compare_search',placeholder='Enter second player name')
    choices=[p for p in others if compare_query.strip().casefold() in p['name'].casefold()] if compare_query.strip() else []
    if not compare_query.strip():
        st.info('Type the second player’s name to compare.')
    elif len(choices)>25:
        st.info('Keep typing to narrow the player search.')
    elif not choices:
        st.info('No matching player in current ESPN team rosters.')
    else:
        other=st.selectbox('Second player',[p['id'] for p in choices],
                           format_func=lambda pid:next(p['name']+' · '+p['team'] for p in choices if p['id']==pid),
                           key='foxk_compare_pid')
        p2=next(p for p in choices if p['id']==other)
        try:
            other_df=player_log(p2['id'],season)
            if other_df.empty: st.info('No second-player game logs available.')
            else:
                common=[x for x in ['PTS','REB','AST','3PM','STL','BLK','PRA','PR','PA','RA','MIN']
                        if x in df and x in other_df and df[x].notna().any() and other_df[x].notna().any()]
                if common:
                    cm1,cm2,cm3=st.columns(3)
                    with cm1: comparison_metric=st.selectbox('Comparison statistic',common,key='foxk_compare_stat')
                    with cm2: comparison_n=st.selectbox('Games to compare',[5,10,20,40,82],key='foxk_compare_n')
                    with cm3: comparison_line=st.number_input('Comparison threshold',min_value=0.0,value=20.5,step=.5,key='foxk_compare_line')
                    result=[]
                    for p,frame in [(selected,df),(p2,other_df)]:
                        vals=frame[comparison_metric].dropna().head(comparison_n)
                        decisions=int((vals!=comparison_line).sum())
                        hits=int((vals>comparison_line).sum())
                        result.append({'Player':p['name'],'Games':len(vals),'Average':round(float(vals.mean()),2) if len(vals) else None,
                                       'Median':round(float(vals.median()),2) if len(vals) else None,
                                       'Over hits':hits,'Over decisions':decisions,
                                       'Over hit rate':f'{hits/decisions:.0%}' if decisions else 'N/A'})
                    foxk_dark_table(pd.DataFrame(result),hide_index=True,use_container_width=True)
                else: st.warning('The players have no shared numeric statistics in this season.')
        except Exception as exc: st.warning(f'Second-player log unavailable: {exc}')

if st.session_state.foxk_section == NAV_ITEMS[7]:
    st.subheader('Saved prop watchlist')
    st.caption('This watchlist is stored only in your current browser session. Export CSV to keep it; it is not synced across devices.')
    if 'foxk_watchlist' not in st.session_state: st.session_state.foxk_watchlist=[]
    w1,w2,w3=st.columns(3)
    with w1: w_metric=st.selectbox('Watchlist statistic',valid,key='foxk_watch_metric')
    with w2: w_line=st.number_input('Watchlist threshold',min_value=0.0,value=20.5,step=.5,key='foxk_watch_line')
    with w3: w_side=st.selectbox('Watchlist direction',['Over','Under'],key='foxk_watch_side')
    if st.button('Save this player + prop',type='primary',key='foxk_watch_add'):
        item={'Player':selected['name'],'Team':selected['team'],'Player ID':selected['id'],
              'Season':season,'Statistic':w_metric,'Threshold':w_line,'Direction':w_side}
        if item not in st.session_state.foxk_watchlist:
            st.session_state.foxk_watchlist.append(item)
            st.success('Added to this session’s watchlist.')
        else: st.info('Already saved.')
    if st.session_state.foxk_watchlist:
        saved=pd.DataFrame(st.session_state.foxk_watchlist)
        foxk_dark_table(saved,hide_index=True,use_container_width=True)
        st.download_button('Export watchlist CSV',saved.to_csv(index=False).encode('utf-8'),
                           'FOXK_watchlist.csv','text/csv',key='foxk_watch_export')
        if st.button('Clear watchlist',key='foxk_watch_clear'):
            st.session_state.foxk_watchlist=[]
            st.rerun()
    else: st.info('Your watchlist is empty.')

if st.session_state.foxk_section == NAV_ITEMS[8]:
    st.subheader('FOXK VIP access')
    st.success('Whop sign-in and active-product membership verification are enabled.')
    st.caption('Your membership is rechecked on every app rerun. Discord role synchronization must be configured separately in Whop.')

st.caption('FOXK is independent of ESPN and the NBA. Unofficial free feeds may change or become unavailable. All displayed statistics must be backed by returned game records.')
