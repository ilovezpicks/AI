import streamlit as st
import requests, pandas as pd, datetime as dt, time

st.set_page_config(page_title='FOXK NBA Stat Lab',page_icon='🏀',layout='wide')
st.markdown('''<style>.stApp{background:#0b1020;color:#f5f7ff}h1,h2,h3{color:#f5f7ff}[data-testid='stMetric']{background:#17213a;padding:12px;border-radius:12px}[data-testid='stMetricValue'],[data-testid='stMetricLabel']{color:#f5f7ff!important}</style>''',unsafe_allow_html=True)
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
    search=st.text_input('Find player',placeholder='Type a player name, e.g. Stephen Curry',key='foxk_player_query')
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

st.divider()
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

st.subheader('Individual defender matchups')
st.info('Possession-level defender tracking is not included in the free ESPN game-log feed. FOXK does not invent player-versus-defender statistics.')
st.caption('Data attribution: ESPN. This independent project is not affiliated with ESPN or the NBA. The unofficial endpoints may change or become unavailable.')
