import streamlit as st
import requests, pandas as pd, datetime as dt, time

st.set_page_config(page_title='FOXK NBA Stat Lab',page_icon='🏀',layout='wide')
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

@st.cache_data(ttl=1800,show_spinner=False)
def player_log(pid,season):
    # ESPN's web athlete game-log feed is unofficial and its schema can change.
    payload=fetch(f'{WEB}/athletes/{pid}/gamelog',{'season':season})
    labels=payload.get('labels',[])
    events=payload.get('events',{})
    if isinstance(events,list): events={str(x.get('id')):x for x in events if isinstance(x,dict)}
    rows=[]
    for season_type in payload.get('seasonTypes',[]):
        for cat in season_type.get('categories',[]):
            cat_labels=cat.get('labels') or labels
            for entry in cat.get('events',[]):
                if not isinstance(entry,dict):continue
                eid=str(entry.get('eventId') or entry.get('id') or '')
                event=events.get(eid,{})
                vals=entry.get('stats',[])
                if isinstance(vals,dict):vals=list(vals.values())
                record=dict(zip(cat_labels,vals)) if isinstance(vals,list) else {}
                record.update({'event_id':eid,'date':event.get('gameDate') or event.get('date'), 'opponent':(event.get('opponent') or {}).get('abbreviation') if isinstance(event.get('opponent'),dict) else event.get('opponent'), 'homeAway':event.get('homeAway'),'result':event.get('gameResult')})
                rows.append(record)
    # Some seasons expose event lists directly.
    if not rows:
        for entry in payload.get('entries',[]):
            if isinstance(entry,dict): rows.append(entry)
    df=pd.DataFrame(rows)
    if df.empty: return df
    aliases={'PTS':['PTS','points'],'REB':['REB','rebounds'],'AST':['AST','assists'],'3PM':['3PM','3PT','3PTM','threePointFieldGoalsMade'],'STL':['STL','steals'],'BLK':['BLK','blocks'],'MIN':['MIN','minutes'],'FGA':['FGA','fieldGoalsAttempted'],'FGM':['FGM','fieldGoalsMade'],'FTA':['FTA','freeThrowsAttempted']}
    for key,choices in aliases.items():
        match=next((c for c in choices if c in df.columns),None)
        if match:df[key]=pd.to_numeric(df[match].astype(str).str.replace(',',''),errors='coerce')
    for combo, parts in {'PRA':['PTS','REB','AST'],'PR':['PTS','REB'],'PA':['PTS','AST'],'RA':['REB','AST']}.items():
        if all(k in df for k in parts): df[combo]=df[parts].sum(axis=1,min_count=len(parts))
    if 'date' in df: df['date']=pd.to_datetime(df['date'],errors='coerce',utc=True)
    if 'date' in df:df=df.sort_values('date',ascending=False)
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

st.title('FOXK  /  NBA STAT LAB')
st.caption('PLAYER RESEARCH  /  NBA DATA  /  ESPN GAME LOGS')
with st.expander('Data source & methodology'):
    st.caption('ESPN public basketball endpoints (unofficial). Statistics appear only when the provider returns usable game logs. No fabricated data or guessed matchups.')
# Global player and season selection; research filters belong to their own sections.
st.markdown('**PLAYER SEARCH**')
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

# Player picker is tied to the search query: typing a new name updates the options.
# Do not preserve the previous player's ID across different searches.
query=search.strip().casefold()
all_players=sorted(players.values(),key=lambda p:p['name'])
if query:
    matches=[p for p in all_players if query in p['name'].casefold()]
    matches.sort(key=lambda p:(not p['name'].casefold().startswith(query),p['name']))
else:
    matches=all_players
if not matches:
    st.warning('No player found in the current roster index. Try part of the name (e.g. Curry). Retired and unsigned players are not included.')
    st.stop()
# Recreate the select widget when the query changes to avoid stale selections.
# When the search identifies one player, select that player automatically.
selected=st.selectbox('Select player',matches,
    format_func=lambda p:f"{p['name']} · {p['team']}",
    key='player_select_'+query)
st.caption(f'{len(matches)} matching player(s). Search above to find a different player.')
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
NAV_ITEMS = ['Overview', 'Prop research', 'Teammates', 'Career H2H', 'Team defense', 'Scouting report']
if 'foxk_section' not in st.session_state:
    st.session_state.foxk_section = NAV_ITEMS[0]

def choose_foxk_section(section):
    st.session_state.foxk_section = section

for start in (0, 3):
    nav_cols = st.columns(3, gap='small')
    for j, section in enumerate(NAV_ITEMS[start:start+3]):
        with nav_cols[j]:
            st.button(section, key=f'foxk_nav_{start+j}',
                      type='primary' if st.session_state.foxk_section == section else 'secondary',
                      use_container_width=True, on_click=choose_foxk_section, args=(section,))
st.divider()

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
    stat=st.selectbox('Overview metric',valid,key='foxk_overview_stat')
    line=st.number_input('Overview comparison line',min_value=0.0,value=24.5,step=0.5,key='foxk_overview_line')
    st.caption(f'{len(df)} recorded games match your filters. Sample size is shown explicitly; missing values are excluded.')
    cols=st.columns(min(4,len(valid)))
    for i,key in enumerate(valid[:4]):cols[i].metric(key,f'{df[key].mean():.1f}')
    if stat in valid:
        s=df[stat].dropna()
        if len(s):
            hits=int((s>line).sum()); st.metric(f'{stat} over {line:g} historical hit rate',f'{hits}/{len(s)} ({hits/len(s):.1%})')
            st.caption('Descriptive past hit rate, not a prediction or betting probability. Pushes are not counted as overs.')
            st.line_chart(df.sort_values('date').set_index('date')[stat] if 'date' in df else df[stat])
    st.subheader('Verified game log')
    show=[c for c in ['date','opponent','homeAway','result','MIN','PTS','REB','AST','3PM','STL','BLK'] if c in df.columns]
    st.dataframe(df[show],use_container_width=True,hide_index=True)
    st.download_button('Download actual results (CSV)',df.to_csv(index=False).encode(),file_name='foxk_real_game_log.csv',mime='text/csv')

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
            with b: prop_line=st.number_input('Research threshold',min_value=0.0,value=24.5,step=0.5,key='foxk_prop20_line')
            with c: prop_side=st.selectbox('Direction',['Over','Under'],key='foxk_prop20_side')
            f1,f2,f3=st.columns(3)
            with f1:
                opponents=sorted(prop_source['opponent'].dropna().astype(str).str.upper().unique()) if 'opponent' in prop_source else []
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
                filtered=filtered[filtered['opponent'].astype(str).str.upper()==prop_opp]
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
                st.warning('No games match these filters. Broaden your selection to see results.')
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
                st.dataframe(pd.DataFrame(trends),hide_index=True,use_container_width=True)
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
                st.line_chart(graph.set_index('Game')[['Actual','Threshold']],use_container_width=True)
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
                    st.dataframe(pd.DataFrame(opponent_rows).sort_values(['Games','Opponent'],ascending=[False,True]),hide_index=True,use_container_width=True)
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
                    st.dataframe(pd.DataFrame(venue_rows),hide_index=True,use_container_width=True)
                else: st.caption('Home/away labels are not available for these game logs.')
                st.markdown('#### Auditable game log')
                cols=[k for k in ['date','opponent','homeAway','weekday','rest_days','MIN','PTS','REB','AST','3PM','STL','BLK',prop_metric] if k in filtered]
                cols=list(dict.fromkeys(cols))
                audit=filtered[cols].copy()
                audit['Outcome']=graph['Outcome'].reindex(audit.index)
                st.dataframe(audit,use_container_width=True,hide_index=True)
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
                    st.dataframe(pd.DataFrame(grouped),use_container_width=True,hide_index=True)
                    st.caption('Interpretation: "No teammate appearance recorded" can include injuries, rest, DNP, roster changes, missing ESPN logs, or data gaps. These are NOT confirmed official injury-out splits. Current-roster membership does not prove both players were teammates for every historical game.')
                    with st.expander('See games used in the comparison'):
                        fields=[c for c in ['date','opponent','homeAway','Teammate recorded','PTS','REB','AST','3PM','MIN'] if c in comparison.columns]
                        st.dataframe(comparison[fields],use_container_width=True,hide_index=True)
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
                st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
                with st.expander('Audit games and appearances'):
                    st.dataframe(base[[x for x in ['date','opponent','All selected teammates recorded playing','PTS','REB','AST','MIN'] if x in base]],hide_index=True,use_container_width=True)

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
    h2h_years=st.multiselect('Historical seasons to include (NBA season ending year)',list(range(2027,2010,-1)),default=list(range(2027,2016,-1)),key='foxk_h2h_years',help='Default: 2016–17 through 2026–27. Select older seasons to extend history. Seasons before the player entered the NBA will have no games.')
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
                    st.dataframe(summary,use_container_width=True,hide_index=True)
                    if stat in history and history[stat].notna().any():
                        vals=history[stat].dropna()
                        hits=int((vals>line).sum())
                        st.metric(f'Career H2H {stat} over {line:g}',f'{hits}/{len(vals)} ({hits/len(vals):.1%})')
                        st.caption('Historical frequency only, not a future-game probability. The comparison line is selected above.')
                st.markdown('**Every retrieved head-to-head game**')
                display=[c for c in ['Season','date','opponent','homeAway','result','MIN','PTS','REB','AST','3PM','STL','BLK'] if c in history]
                st.dataframe(history[display],use_container_width=True,hide_index=True)
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
        period=st.segmented_control('Research sample',['Last 5','Last 10','Last 20','All games'],default='Last 10',key='foxk_def_period')
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
        st.line_chart(trend.set_index('Date')[['Points allowed','Points scored']],color=['#ed854d','#c6d0dc'])
        st.markdown('#### Home vs. away')
        venues=[]
        for name in ['Home','Away']:
            part=sample[sample['Venue']==name]
            if not part.empty:
                venues.append({'Venue':name,'Games':len(part),'Points allowed / game':round(part['Points allowed'].mean(),1),
                               'Points scored / game':round(part['Points scored'].mean(),1),
                               'Average margin':round(part['Margin'].mean(),1)})
        if venues:st.dataframe(pd.DataFrame(venues),hide_index=True,use_container_width=True)
        else:st.caption('ESPN did not return reliable home/away labels for these games.')
        st.markdown('#### Recent form comparison')
        comparisons=[]
        for label,n in [('Last 5',5),('Last 10',10),('Last 20',20),('Season returned',len(defense))]:
            part=defense.head(n)
            comparisons.append({'Period':label,'Games':len(part),'Points allowed / game':round(part['Points allowed'].mean(),1),
                                'Points scored / game':round(part['Points scored'].mean(),1),
                                'Average margin':round(part['Margin'].mean(),1)})
        st.dataframe(pd.DataFrame(comparisons),hide_index=True,use_container_width=True)
        st.markdown('#### Completed game log')
        display=['Date','Opponent','Venue','Result','Points allowed','Points scored','Margin']
        st.dataframe(sample[display],hide_index=True,use_container_width=True)
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
            st.dataframe(pd.DataFrame(report_rows),hide_index=True,use_container_width=True)
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
                st.dataframe(pd.DataFrame(loc_rows),hide_index=True,use_container_width=True)
        st.markdown('#### Data-quality checklist')
        st.write('- This report uses game-log averages, not a predictive betting model.')
        st.write('- A teammate missing from a log is not proof of a confirmed injury.')
        st.write('- Team points allowed cannot identify which defender guarded a player.')
        st.write('- Very small opponent and venue samples are especially unstable.')
        st.write('- ESPN endpoints are unofficial and may omit games or change format.')
        st.caption('Source: ESPN public NBA game-log endpoints. Verify the game log and current availability before using these trends.')

st.caption('FOXK is independent of ESPN and the NBA. Unofficial free feeds may change or become unavailable. All displayed statistics must be backed by returned game records.')
