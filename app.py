import streamlit as st
import requests, pandas as pd, datetime as dt, time

st.set_page_config(page_title='FOXK NBA Stat Lab',page_icon='🏀',layout='wide')
st.markdown('''<style>.stApp{background:#0b1020;color:#f5f7ff}h1,h2,h3{color:#f5f7ff}.stMetric{background:#17213a;padding:12px;border-radius:12px}</style>''',unsafe_allow_html=True)
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
    aliases={'PTS':['PTS','points'],'REB':['REB','rebounds'],'AST':['AST','assists'],'3PM':['3PM','3PT','3PTM','threePointFieldGoalsMade'],'STL':['STL','steals'],'BLK':['BLK','blocks'],'MIN':['MIN','minutes']}
    for key,choices in aliases.items():
        match=next((c for c in choices if c in df.columns),None)
        if match:df[key]=pd.to_numeric(df[match].astype(str).str.replace(',',''),errors='coerce')
    if 'date' in df: df['date']=pd.to_datetime(df['date'],errors='coerce',utc=True)
    if 'date' in df:df=df.sort_values('date',ascending=False)
    return df

st.title('🏀 FOXK NBA STAT LAB')
st.caption('Public NBA research • Free ESPN data feeds • Real results only • Cached requests')
st.info('Data source: ESPN public basketball endpoints (unofficial). Statistics are shown only when the provider returns usable game logs. No fake data or guessed matchups.')
with st.sidebar:
    st.header('Research filters')
    season=st.selectbox('Season',[2027,2026,2025,2024,2023,2022],index=0,format_func=lambda x:f'{x-1}–{str(x)[-2:]}')
    search=st.text_input('Find player','Donovan Mitchell')
    window=st.selectbox('Recent games',[5,10,15,20,40,82],index=1)
    opponent=st.text_input('Opponent abbreviation (optional)',placeholder='ATL')
    location=st.selectbox('Location',['All','Home','Away'])
    stat=st.selectbox('Prop stat',['PTS','REB','AST','3PM','STL','BLK'])
    line=st.number_input('Prop line',min_value=0.0,value=24.5,step=0.5)

try:
    with st.spinner('Finding NBA players from current team rosters…'):
        players,roster_errors=roster_index()
except Exception as e:
    st.error(f'Unable to load the free roster feed. Please retry later. {e}')
    st.stop()

matches=sorted([p for p in players.values() if search.lower().strip() in p['name'].lower()],key=lambda p:p['name']) if search.strip() else []
if not matches:
    st.warning('No matching player in available current rosters. Try a different name. Historical/retired players are not indexed in this version.')
    st.stop()
selected=st.selectbox('Player',matches,format_func=lambda p:f"{p['name']} · {p['team']}")
if roster_errors:st.caption(f'{roster_errors} team roster feeds were unavailable; search may be incomplete.')
try:
    with st.spinner('Retrieving verified game logs…'):
        df=player_log(selected['id'],season)
except Exception as e:
    st.error(str(e));st.stop()
if df.empty:
    st.warning('ESPN returned no game-log rows for this player and season. Try another season. No numbers will be invented.')
    st.stop()
if opponent.strip() and 'opponent' in df.columns:
    df=df[df['opponent'].astype(str).str.upper()==opponent.strip().upper()]
if location!='All' and 'homeAway' in df.columns:
    df=df[df['homeAway'].astype(str).str.lower()==location.lower()]
if df.empty:
    st.warning('No recorded games match these filters.');st.stop()
df=df.head(window)
valid=[c for c in ['PTS','REB','AST','3PM','STL','BLK'] if c in df and df[c].notna().any()]
if not valid:
    st.warning('ESPN returned game events but no parseable numeric player box-score statistics. Provider format may have changed.');st.dataframe(df.head(5));st.stop()
st.subheader(f"{selected['name']} — {season-1}–{str(season)[-2:]}")
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
st.divider()
st.subheader('Teammate in/out and defender matchups')
st.info('Not enabled yet: accurate teammate-absence and possession-level defender splits require verified complete box scores or tracking. FOXK will not infer absences or invent defensive matchups.')
st.caption('Data attribution: ESPN. This independent project is not affiliated with ESPN or the NBA. The unofficial endpoints may change or become unavailable.')
