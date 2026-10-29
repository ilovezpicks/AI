import streamlit as st
import requests, pandas as pd, datetime as dt, time

st.set_page_config(page_title='FOXK NBA Stat Lab',page_icon='🏀',layout='wide')
st.markdown('\n<style>\n#MainMenu,footer{visibility:hidden}\n[data-testid="stHeader"]{background:#101316!important;height:3rem}\n.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:#101316!important;color:#f0f1f2!important}\n.block-container{max-width:1320px!important;padding-top:1.6rem!important;padding-bottom:4rem!important}\nh1,h2,h3{font-family:Arial,Helvetica,sans-serif!important;letter-spacing:-.035em!important;color:#f4f5f6!important}\nh1{font-size:2.2rem!important;font-weight:800!important;margin-bottom:.1rem!important}\nh2{font-size:1.6rem!important}\np,li,label,span{line-height:1.5}\n[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p{color:#aab2bb!important;opacity:1!important}\n[data-testid="stSidebar"]{background:#191d21!important;border-right:1px solid #343a40!important}\n[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,[data-testid="stSidebar"] p,[data-testid="stSidebar"] label{color:#f0f1f2!important}\n[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p{color:#d5d9dd!important;font-weight:600!important}\n[data-testid="stSidebar"] input{color:#f0f1f2!important;background:#262b30!important}\n[data-testid="stSidebar"] input::placeholder{color:#a6b0ba!important;opacity:1!important}\n[data-baseweb="select"]>div,[data-baseweb="input"]>div{background:#262b30!important;border:1px solid #454c54!important;border-radius:7px!important}\n[data-baseweb="select"] *,[data-baseweb="input"] input{color:#f0f1f2!important}\n[data-baseweb="select"] svg{fill:#d5d9dd!important}\n[data-baseweb="tab-list"]{gap:0!important;border-bottom:1px solid #343a40!important;flex-wrap:wrap!important}\nbutton[data-baseweb="tab"]{background:transparent!important;border:0!important;border-bottom:2px solid transparent!important;border-radius:0!important;padding:13px 16px!important}\nbutton[data-baseweb="tab"] *,button[data-baseweb="tab"]{color:#b5bdc5!important;opacity:1!important;font-weight:650!important}\nbutton[data-baseweb="tab"][aria-selected="true"]{border-bottom:2px solid #ed854d!important}\nbutton[data-baseweb="tab"][aria-selected="true"] *{color:#fff!important}\nbutton[data-baseweb="tab"]:hover *{color:#fff!important}\n[data-testid="stMetric"]{background:#1c2126!important;border:1px solid #363d44!important;border-radius:9px!important;padding:18px 20px!important}\n[data-testid="stMetricLabel"] *,[data-testid="stMetricLabel"]{color:#b8c2cb!important;font-weight:650!important;font-size:.82rem!important}\n[data-testid="stMetricValue"] *,[data-testid="stMetricValue"]{color:#f6f7f8!important;font-weight:750!important}\n[data-testid="stDataFrame"]{border:1px solid #363d44!important;border-radius:8px!important}\n[data-testid="stAlert"]{border:1px solid #38414a!important;border-radius:8px!important}\n.stButton button,[data-testid="stDownloadButton"] button{border-radius:7px!important}\nhr{border-color:#343a40!important}\n@media(max-width:768px){.block-container{padding:1rem!important}h1{font-size:1.65rem!important}button[data-baseweb="tab"]{padding:9px!important}}\n</style>\n',unsafe_allow_html=True)
st.markdown('<style>\n[data-testid="stTabs"] [role="tablist"]{display:flex!important;flex-wrap:wrap!important;gap:4px!important;border-bottom:1px solid #363c42!important}\n[data-testid="stTabs"] button[role="tab"]{color:#d1d6dd!important;opacity:1!important;background:transparent!important;border:0!important;border-bottom:3px solid transparent!important;padding:12px 15px!important;min-height:46px!important;white-space:nowrap!important}\n[data-testid="stTabs"] button[role="tab"] *,[data-testid="stTabs"] [role="tab"] p,[data-testid="stTabs"] [role="tab"] span{color:inherit!important;opacity:1!important;font-size:14px!important;font-weight:650!important;-webkit-text-fill-color:currentColor!important}\n[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{color:#fff!important;border-bottom:3px solid #f28c50!important;background:#202428!important}\n[data-testid="stTabs"] button[role="tab"]:hover{color:#fff!important;background:#252a2f!important}\n[data-testid="stTabs"] button[role="tab"]:focus-visible{outline:2px solid #f28c50!important;outline-offset:-2px!important}\n[data-testid="stTabs"] [data-baseweb="tab-highlight"]{background:#f28c50!important}\n</style>', unsafe_allow_html=True)
st.markdown('\n<style>\n/* FOXK contrast polish: scoped to Streamlit\'s actual widgets */\n[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:3px!important;border-bottom:1px solid #41474e!important}\n[data-testid="stTabs"] button[role="tab"], [data-testid="stTabs"] button[data-baseweb="tab"]{color:#d4d9df!important;opacity:1!important;font-weight:650!important;border-radius:0!important;transition:color .12s ease,border-color .12s ease!important}\n[data-testid="stTabs"] button[role="tab"] *,[data-testid="stTabs"] button[data-baseweb="tab"] *{color:inherit!important;opacity:1!important;-webkit-text-fill-color:currentColor!important}\n[data-testid="stTabs"] button[aria-selected="true"]{color:#fff!important;border-bottom:2px solid #f18a4b!important}\n[data-testid="stTabs"] button[role="tab"]:hover{color:#fff!important;background:#20252a!important}\n/* Labels in main panel */\n[data-testid="stMain"] [data-testid="stWidgetLabel"] p,[data-testid="stMain"] [data-testid="stWidgetLabel"] label,[data-testid="stMain"] [data-testid="stWidgetLabel"]{color:#dbe0e6!important;opacity:1!important}\n/* Select widgets: dark throughout, including arrow section */\n[data-testid="stSelectbox"] [data-baseweb="select"]>div,[data-testid="stSelectbox"] [data-baseweb="select"]>div>div{background:#252b31!important;color:#f6f7f8!important}\n[data-testid="stSelectbox"] [data-baseweb="select"]>div{border:1px solid #4b545d!important;border-radius:7px!important;box-shadow:none!important}\n[data-testid="stSelectbox"] [data-baseweb="select"] *{color:#f6f7f8!important;-webkit-text-fill-color:#f6f7f8!important}\n[data-testid="stSelectbox"] [data-baseweb="select"] svg{fill:#dce1e6!important;color:#dce1e6!important}\n[data-testid="stSelectbox"] [data-baseweb="select"] [role="button"]{background:transparent!important}\n[data-testid="stSelectbox"] [data-baseweb="select"]>div:focus-within{border-color:#f18a4b!important}\n[data-baseweb="popover"] [role="listbox"], [data-baseweb="popover"] ul{background:#252b31!important;color:#f6f7f8!important}\n[data-baseweb="popover"] [role="option"]{background:#252b31!important;color:#f6f7f8!important}\n[data-baseweb="popover"] [role="option"]:hover,[data-baseweb="popover"] [aria-selected="true"]{background:#39424b!important}\n/* Number input buttons and text */\n[data-testid="stNumberInput"] [data-baseweb="input"]>div,[data-testid="stNumberInput"] button{background:#252b31!important;color:#f6f7f8!important}\n[data-testid="stNumberInput"] svg{fill:#dce1e6!important}\n/* Reduce visual gaps without changing content */\n[data-testid="stMain"] .block-container{padding-top:1.1rem!important}\n[data-testid="stMain"] [data-testid="stVerticalBlock"]{row-gap:.7rem}\n@media(max-width:800px){[data-testid="stTabs"] button[role="tab"]{padding:10px 12px!important}}\n</style>\n', unsafe_allow_html=True)
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
def team_defensive_sample(team_code, season):
    teams=fetch(BASE+'/teams',{'limit':100}).get('sports',[{}])[0].get('leagues',[{}])[0].get('teams',[])
    matches=[x.get('team',x) for x in teams if x.get('team',x).get('abbreviation','').upper()==team_code]
    if not matches: raise ValueError('Team not present in current ESPN team index')
    tid=str(matches[0]['id'])
    payload=fetch(BASE+'/teams/'+tid+'/schedule',{'season':season})
    records=[]
    for ev in payload.get('events',[]):
        comp=(ev.get('competitions') or [{}])[0]
        status=comp.get('status',ev.get('status',{}))
        completed=status.get('type',{}).get('completed',False) if isinstance(status,dict) else False
        if not completed: continue
        entries=comp.get('competitors',[])
        if len(entries)!=2:continue
        own=next((c for c in entries if str(c.get('id') or c.get('team',{}).get('id'))==tid),None)
        opp=next((c for c in entries if c is not own),None) if own else None
        if not opp:continue
        score=opp.get('score')
        if isinstance(score,dict): score=score.get('value') or score.get('displayValue')
        try: allowed=float(score)
        except (TypeError,ValueError):continue
        records.append({'Date':ev.get('date'),'Opponent':opp.get('team',{}).get('abbreviation',''),'Points allowed':allowed})
    return pd.DataFrame(records)

def describe_rates(frame,metric,threshold):
    if metric not in frame:return None
    x=frame[metric].dropna()
    if x.empty:return None
    return {'games':len(x),'average':round(x.mean(),1),'over':int((x>threshold).sum()),'push':int((x==threshold).sum())}

st.title('FOXK  /  NBA STAT LAB')
st.caption('PLAYER RESEARCH  /  NBA DATA  /  ESPN GAME LOGS')
with st.expander('Data source & methodology'):
    st.caption('ESPN public basketball endpoints (unofficial). Statistics appear only when the provider returns usable game logs. No fabricated data or guessed matchups.')
with st.sidebar:
    st.header('FILTERS')
    season=st.selectbox('Season',[2027,2026,2025,2024,2023,2022],index=0,format_func=lambda x:f'{x-1}–{str(x)[-2:]}')
    search=st.text_input('Find player',placeholder='Type a player name, e.g. Stephen Curry',key='foxk_player_query')
    window=st.selectbox('Recent games',[5,10,15,20,40,82],index=1)
    opponent=st.text_input('Opponent abbreviation (optional)',placeholder='ATL')
    location=st.selectbox('Location',['All','Home','Away'])
    stat=st.selectbox('Prop stat',['PTS','REB','AST','3PM','STL','BLK','PRA','PR','PA','RA'])
    line=st.number_input('Prop line',min_value=0.0,value=24.5,step=0.5)

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
st.caption(f'{len(matches)} matching player(s). Type a new name in the sidebar to search again.')
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
df=df.head(window).copy()
# Combined props require all contributing box-score stats to be present.
for combined, parts in {'PRA':['PTS','REB','AST'], 'PR':['PTS','REB'], 'PA':['PTS','AST'], 'RA':['REB','AST']}.items():
    if all(part in df.columns for part in parts):
        df[combined]=df[parts].sum(axis=1,min_count=len(parts))
valid=[c for c in ['PTS','REB','AST','3PM','STL','BLK','PRA','PR','PA','RA'] if c in df and df[c].notna().any()]
if not valid:
    st.warning('ESPN returned game events but no parseable numeric player box-score statistics. Provider format may have changed.');st.dataframe(df.head(5));st.stop()
tabs=st.tabs(['Overview', 'Prop research', 'Teammates', 'Career H2H', 'Team defense', 'Scouting report'])
with tabs[0]:
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

with tabs[1]:
    st.subheader('Advanced player-prop research')
    st.caption('PRA, PR, PA and RA are also available in the sidebar Prop stat selector above.')
    st.caption('Uses the selected season’s actual ESPN game logs. Filters below apply to this analyzer only, not career head-to-head history.')
    prop_source=player_log(selected['id'],season).copy()
    if prop_source.empty:
        st.info('No verified season game logs available for advanced prop research.')
    else:
        if 'event_id' in prop_source.columns:
            prop_source=prop_source.drop_duplicates(subset=['event_id'])
        prop_source['PRA']=prop_source[['PTS','REB','AST']].sum(axis=1,min_count=3) if all(k in prop_source for k in ['PTS','REB','AST']) else float('nan')
        prop_source['PR']=prop_source[['PTS','REB']].sum(axis=1,min_count=2) if all(k in prop_source for k in ['PTS','REB']) else float('nan')
        prop_source['PA']=prop_source[['PTS','AST']].sum(axis=1,min_count=2) if all(k in prop_source for k in ['PTS','AST']) else float('nan')
        prop_source['RA']=prop_source[['REB','AST']].sum(axis=1,min_count=2) if all(k in prop_source for k in ['REB','AST']) else float('nan')
        available=[k for k in ['PTS','REB','AST','3PM','STL','BLK','PRA','PR','PA','RA'] if k in prop_source and prop_source[k].notna().any()]
        if not available:
            st.warning('ESPN returned no numeric statistics for advanced prop calculations.')
        else:
            a,b,c=st.columns(3)
            with a: prop_metric=st.selectbox('Stat to research',available,key='foxk_adv_metric')
            with b: prop_line=st.number_input('Research line',min_value=0.0,value=24.5,step=0.5,key='foxk_adv_line')
            with c: prop_side=st.selectbox('Result', ['Over','Under'],key='foxk_adv_side')
            f1,f2,f3=st.columns(3)
            with f1:
                opps=sorted(set(prop_source['opponent'].dropna().astype(str).str.upper())) if 'opponent' in prop_source else []
                prop_opponent=st.selectbox('Opponent',['All']+opps,key='foxk_adv_opponent')
            with f2: prop_location=st.selectbox('Home / away',['All','Home','Away'],key='foxk_adv_location')
            with f3: prop_window=st.selectbox('Sample window',['Full season',5,10,15,20,40,82],key='foxk_adv_window')
            f4,f5=st.columns(2)
            with f4:
                weekdays=['All','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
                prop_weekday=st.selectbox('Day of week',weekdays,key='foxk_adv_weekday')
            with f5:
                rest_choice=st.selectbox('Rest between recorded appearances',['All','0 days (back-to-back)','1 day','2+ days'],key='foxk_adv_rest')
            # Derive rest from dated recorded appearances, before narrowing to opponent or venue.
            if 'date' in prop_source and prop_source['date'].notna().any():
                prop_source=prop_source.sort_values('date')
                prop_source['rest_days']=(prop_source['date'].dt.normalize()-prop_source['date'].shift(1).dt.normalize()).dt.days-1
                prop_source['weekday']=prop_source['date'].dt.day_name()
                prop_source=prop_source.sort_values('date',ascending=False)
            filtered=prop_source.copy()
            if prop_opponent!='All' and 'opponent' in filtered:
                filtered=filtered[filtered['opponent'].astype(str).str.upper()==prop_opponent]
            if prop_location!='All' and 'homeAway' in filtered:
                filtered=filtered[filtered['homeAway'].astype(str).str.lower()==prop_location.lower()]
            if prop_weekday!='All':
                if 'weekday' in filtered: filtered=filtered[filtered['weekday']==prop_weekday]
                else: filtered=filtered.iloc[0:0]
            if rest_choice!='All':
                if 'rest_days' not in filtered: filtered=filtered.iloc[0:0]
                elif rest_choice.startswith('0'): filtered=filtered[filtered['rest_days']==0]
                elif rest_choice.startswith('1'): filtered=filtered[filtered['rest_days']==1]
                else: filtered=filtered[filtered['rest_days']>=2]
            if prop_window!='Full season': filtered=filtered.head(int(prop_window))
            filtered=filtered[filtered[prop_metric].notna()].copy()
            if filtered.empty:
                st.warning('No verified games match this combination of filters. Try broadening the selection.')
            else:
                vals=filtered[prop_metric]
                hits=vals>prop_line if prop_side=='Over' else vals<prop_line
                pushes=vals==prop_line
                decisions=int((~pushes).sum())
                successes=int(hits.sum())
                x,y,z=st.columns(3)
                x.metric('Games with stats',len(filtered))
                y.metric(f'{prop_metric} average',f'{vals.mean():.1f}')
                z.metric(f'{prop_side} {prop_line:g} hit rate',f'{successes}/{decisions} ({successes/decisions:.1%})' if decisions else 'No decisions')
                st.caption(f'{int(pushes.sum())} push(es) excluded from hit-rate denominator. Historical frequency only, not a forecast. Rest is estimated from consecutive recorded appearances, NOT confirmed team rest or travel schedule.')
                chart=filtered.sort_values('date').copy() if 'date' in filtered else filtered.copy()
                chart['Line']=prop_line
                chart['Actual']=chart[prop_metric]
                chart['Hit']=hits.reindex(chart.index).map({True:'Hit',False:'Miss'})
                st.markdown('**Actual game results vs. research line**')
                st.bar_chart(chart.assign(**{'Hit game':chart['Actual'].where(chart['Hit']=='Hit'),'Miss game':chart['Actual'].where(chart['Hit']=='Miss')}).set_index('date')[['Hit game','Miss game','Line']] if 'date' in chart and chart['date'].notna().all() else chart[['Actual','Line']])
                cols=[k for k in ['date','opponent','homeAway','weekday','rest_days','MIN','PTS','REB','AST','3PM','STL','BLK',prop_metric,'Hit'] if k in chart]
                cols=list(dict.fromkeys(cols))
                st.dataframe(chart[cols].sort_values('date',ascending=False) if 'date' in cols else chart[cols],use_container_width=True,hide_index=True)
                st.download_button('Download filtered prop research (CSV)',chart.to_csv(index=False).encode(),file_name='FOXK_prop_research.csv',mime='text/csv',key='foxk_adv_csv')


with tabs[2]:
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
                if opponent.strip() and 'opponent' in comparison.columns:
                    comparison=comparison[comparison['opponent'].astype(str).str.upper()==opponent.strip().upper()]
                if location!='All' and 'homeAway' in comparison.columns:
                    comparison=comparison[comparison['homeAway'].astype(str).str.lower()==location.lower()]
                # Explicitly include all games matching season/opponent/location; not just recent window.
                st.caption('Comparison uses all available season games matching opponent/location filters, independent of the recent-games slider.')
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

with tabs[3]:
    st.subheader('Career head-to-head vs. an NBA team')
    st.caption('Independent of the season and recent-games filters above. FOXK retrieves each selected season separately and shows the full verified game history available from ESPN.')
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
    h2h_team=st.selectbox('Head-to-head opponent',canonical,index=default_idx,key='foxk_h2h_opponent')
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
                        st.caption('Historical frequency only, not a future-game probability. The prop line comes from the sidebar.')
                st.markdown('**Every retrieved head-to-head game**')
                display=[c for c in ['Season','date','opponent','homeAway','result','MIN','PTS','REB','AST','3PM','STL','BLK'] if c in history]
                st.dataframe(history[display],use_container_width=True,hide_index=True)
                st.download_button('Download career H2H game logs (CSV)',history.to_csv(index=False).encode(),file_name=f'FOXK_{selected["id"]}_vs_{h2h_team}_history.csv',mime='text/csv')
                st.caption('Coverage is limited to seasons selected and successfully returned by ESPN. Includes only game logs ESPN supplies; this is not individual defender tracking.')


with tabs[4]:

    st.subheader('Opponent defensive research')
    st.caption('Verified final-score points allowed from ESPN team schedules. This is team-level scoring allowed, NOT player-specific defensive ranking or individual defender tracking.')
    def_team=st.selectbox('Defensive opponent',canonical,index=default_idx,key='foxk_defense_team')
    if st.button('Load opponent defense',key='foxk_defense_load'):
        try:
            defense=team_defensive_sample(def_team,season)
            if defense.empty:st.warning('No completed games with parseable scores were returned. No defensive averages can be calculated.')
            else:
                st.metric('Completed games',len(defense))
                st.metric('Opponent points allowed / game',f"{defense['Points allowed'].mean():.1f}")
                st.caption('Raw team points allowed is affected by pace and opponent strength. Do not interpret as a position-specific defensive rating.')
                defense=defense.sort_values('Date',ascending=False).reset_index(drop=True)
                dc=st.columns(3)
                for i,(name,n) in enumerate([('Last 5',5),('Last 10',10),('All returned',len(defense))]):
                    part=defense.head(n)
                    dc[i].metric(f'{name} allowed (n={len(part)})',f"{part['Points allowed'].mean():.1f}")
                if len(defense)>1:
                    st.caption(f"Range: {defense['Points allowed'].min():.0f}–{defense['Points allowed'].max():.0f} points allowed across completed games.")
                st.bar_chart(defense.iloc[::-1].set_index('Date')['Points allowed'])
                st.dataframe(defense,use_container_width=True,hide_index=True)
                st.download_button('Download defensive game sample',defense.to_csv(index=False),file_name='FOXK_team_defense.csv',mime='text/csv')
        except Exception as e:st.warning(f'ESPN team schedule data unavailable: {e}')
    st.divider()
    st.subheader('Individual defender tracking')
    st.info('Individual possession-level player-versus-defender stats are not provided by this free data source. FOXK does not infer defensive assignments from team game logs.')

with tabs[5]:
    st.subheader('FOXK matchup research assistant')
    st.caption('Free rules-based scouting from actual ESPN game logs. No paid AI model, fabricated defender matchups, or invented predictions.')
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
            st.caption('Enter an opponent abbreviation in the sidebar to add a same-season matchup comparison.')
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
