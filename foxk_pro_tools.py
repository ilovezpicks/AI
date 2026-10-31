# FOXK Pro Tools: research aids, not verified predictions or automated wagers.
import datetime as dt
import html
import math
import pandas as pd
import streamlit as st
import altair as alt
from zoneinfo import ZoneInfo

METRICS = ['PTS','REB','AST','3PM','STL','BLK','PRA','PR','PA','RA','MIN']
COMBOS = {'PRA':['PTS','REB','AST'],'PR':['PTS','REB'],'PA':['PTS','AST'],'RA':['REB','AST']}


def normalized(frame):
    out = frame.copy()
    for key, columns in COMBOS.items():
        if all(x in out for x in columns):
            out[key] = out[columns].apply(pd.to_numeric, errors='coerce').sum(axis=1,min_count=len(columns))
    if 'date' in out:
        out['date'] = pd.to_datetime(out['date'],errors='coerce',utc=True)
        out = out.sort_values('date',ascending=False)
    if 'event_id' in out:
        out = out.drop_duplicates(subset='event_id')
    return out


def sample(frame, metric, line, side='Over', n=10):
    if metric not in frame:
        return None
    values = pd.to_numeric(frame[metric],errors='coerce').dropna().head(n)
    if values.empty:
        return None
    decisions = values[values != line]
    hits = int((decisions > line).sum()) if side=='Over' else int((decisions < line).sum())
    return {'games':len(values),'decisions':len(decisions),'hits':hits,
            'pushes':len(values)-len(decisions),'rate':hits/len(decisions) if len(decisions) else None,
            'avg':float(values.mean()),'median':float(values.median()),
            'range':f'{values.min():g}–{values.max():g}'}


def stats_cards(frame, metric, line, side):
    cols = st.columns(3)
    for col,n in zip(cols,[5,10,20]):
        info=sample(frame,metric,line,side,n)
        with col:
            if info and info['rate'] is not None:
                st.metric(f'Last {n} · {info["games"]} games',f'{info["hits"]}/{info["decisions"]}',
                          help=f'{info["rate"]:.0%} historical hit rate. {info["pushes"]} pushes excluded.')
                st.caption(f'Avg {info["avg"]:.1f} · {info["rate"]:.0%} historical')
            else:
                st.metric(f'Last {n}','N/A')


def chart(frame, metric, line):
    """Premium dark chart shared by Prop Analyzer and Injury Context."""
    if metric not in frame:
        return
    view = frame.head(20).iloc[::-1].copy()
    view['value'] = pd.to_numeric(view[metric], errors='coerce')
    view = view.dropna(subset=['value'])
    if view.empty:
        st.info('No recorded values available for this chart.')
        return
    view['game'] = range(1, len(view) + 1)
    view['outcome'] = view['value'].apply(lambda v: 'Above line' if v > line else ('Below line' if v < line else 'Push'))
    base = alt.Chart(view).encode(
        x=alt.X('game:O', title=None, axis=alt.Axis(labelColor='#B5C8E5', grid=False, domain=False)),
        y=alt.Y('value:Q', title=None, scale=alt.Scale(zero=False, padding=16),
                axis=alt.Axis(labelColor='#B5C8E5', gridColor='#293A55', domain=False)),
        tooltip=[alt.Tooltip('game:O', title='Recorded game'),
                 alt.Tooltip('value:Q', title=metric, format='.1f'),
                 alt.Tooltip('outcome:N', title='Compared with line')],
    )
    area = base.mark_area(opacity=.15, color='#FF995D', interpolate='monotone')
    glow = base.mark_line(color='#FF995D', strokeWidth=9, opacity=.13, interpolate='monotone')
    trace = base.mark_line(color='#FF995D', strokeWidth=3.5, interpolate='monotone')
    dots = base.mark_circle(size=105, stroke='#101B2E', strokeWidth=2).encode(
        color=alt.condition(alt.datum.value > float(line), alt.value('#38D9AD'), alt.value('#FF995D')))
    target = alt.Chart(pd.DataFrame({'target': [float(line)]})).mark_rule(
        color='#B3C5E1', strokeDash=[7, 5], strokeWidth=2
    ).encode(y='target:Q')
    figure = (area + glow + target + trace + dots).properties(
        height=300, background='#101B2E'
    ).configure_view(stroke='#344A68', cornerRadius=14)
    st.altair_chart(figure, use_container_width=True, theme=None)


def foxk_pro_theme():
    """Style all native Streamlit widgets used by the eight Pro Tools pages."""
    st.markdown("""<style>
    /* Universal FOXK dark inputs: both the wrapper AND actual BaseWeb nodes. */
    [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"],
    [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div > div,
    [data-testid="stMain"] [data-testid="stSelectbox"] input,
    [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"],
    [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
    [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div > div,
    [data-testid="stMain"] [data-testid="stMultiSelect"] input,
    [data-testid="stMain"] [data-testid="stNumberInput"] [data-baseweb="input"],
    [data-testid="stMain"] [data-testid="stNumberInput"] [data-baseweb="input"] > div,
    [data-testid="stMain"] [data-testid="stNumberInput"] input,
    [data-testid="stMain"] [data-testid="stTextInput"] [data-baseweb="input"],
    [data-testid="stMain"] [data-testid="stTextInput"] input,
    [data-testid="stMain"] [data-testid="stTextArea"] [data-baseweb="textarea"],
    [data-testid="stMain"] [data-testid="stTextArea"] textarea {
      background:#111D31!important;background-color:#111D31!important;
      color:#F8FAFC!important;-webkit-text-fill-color:#F8FAFC!important;
      caret-color:#FF995D!important;
    }
    [data-testid="stMain"] [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="select"] > div,
    [data-testid="stMain"] [data-testid="stNumberInput"] [data-baseweb="input"],
    [data-testid="stMain"] [data-testid="stTextInput"] [data-baseweb="input"],
    [data-testid="stMain"] [data-testid="stTextArea"] [data-baseweb="textarea"] {
      border:1px solid #405777!important;border-radius:15px!important;
      box-shadow:0 6px 20px rgba(0,0,0,.14)!important;overflow:hidden!important;
    }
    [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="tag"] {
      background:#304460!important;color:#FFB98F!important;border-radius:9px!important;
    }
    [data-testid="stMain"] [data-testid="stMultiSelect"] [data-baseweb="tag"] * {
      color:#FFB98F!important;-webkit-text-fill-color:#FFB98F!important;
    }
    [data-testid="stMain"] [data-testid="stNumberInput"] button {
      background:#233753!important;color:#FFB98F!important;border-left:1px solid #425A79!important;
    }
    [data-testid="stMain"] input::placeholder,
    [data-testid="stMain"] textarea::placeholder {
      color:#91A7C6!important;-webkit-text-fill-color:#91A7C6!important;
    }
    [data-testid="stMain"] [data-testid="stWidgetLabel"] p {
      color:#C4D2E8!important;font-weight:750!important;letter-spacing:.055em!important;
    }
    /* Portal menus render outside the main Streamlit content container. */
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    div[data-baseweb="popover"] [role="listbox"],
    div[data-baseweb="popover"] [role="option"],
    div[data-baseweb="menu"] {
      background:#101B2E!important;color:#F8FAFC!important;
    }
    div[data-baseweb="popover"] [role="option"]:hover,
    div[data-baseweb="popover"] [aria-selected="true"] {
      background:#2A405E!important;color:#FFB98F!important;
    }
    [data-testid="stMain"] [data-testid="stMetric"] {
      background:linear-gradient(135deg,#1A2943,#101B2E)!important;
      border:1px solid #354C6A!important;border-radius:18px!important;padding:15px!important;
    }
    [data-testid="stMain"] [data-testid="stMetricValue"] {
      color:#FFB383!important;font-weight:800!important;
    }
    [data-testid="stMain"] [data-testid="stAlert"] {
      border-radius:14px!important;
    }
    [data-testid="stMain"] .stButton > button,
    [data-testid="stMain"] [data-testid="stDownloadButton"] > button {
      background:#1C2D49!important;border:1px solid #405878!important;
      color:#F8FAFC!important;border-radius:14px!important;
    }
    [data-testid="stMain"] .stButton > button:hover,
    [data-testid="stMain"] [data-testid="stDownloadButton"] > button:hover {
      border-color:#FF995D!important;background:#2A3D5B!important;
    }
    </style>""", unsafe_allow_html=True)


def get_state_list(key):
    if key not in st.session_state: st.session_state[key]=[]
    return st.session_state[key]


def pro_header(title,description):
    st.markdown(f'<div class="foxk-pro-header"><small>FOXK / VIP RESEARCH</small><h2>{html.escape(title)}</h2><p>{html.escape(description)}</p></div>',unsafe_allow_html=True)
    st.markdown("""<style>.foxk-pro-header{background:linear-gradient(110deg,#1C2B47,#10192C);border:1px solid #354B6A;border-radius:18px;padding:17px 20px;margin-bottom:16px}.foxk-pro-header small{color:#FFB080;letter-spacing:.14em;font-weight:850;font-size:10px}.foxk-pro-header h2{color:white!important;font-size:23px!important;margin:5px 0!important}.foxk-pro-header p{color:#AFC1DC;font-size:13px;margin:0}</style>""",unsafe_allow_html=True)


def render_pro_tools(section,selected,df,season,all_players,player_log,dark_table,scoreboard):
    pro_sections={'Today Dashboard','Prop Finder','Prop Analyzer','Line Movement','Injury Context','Pick Tracker','FOXK Assistant','Smart Watchlist'}
    if section not in pro_sections: return
    foxk_pro_theme()
    frame=normalized(df)
    available=[x for x in METRICS if x in frame and pd.to_numeric(frame[x],errors='coerce').notna().any()]
    if section=='Today Dashboard':
        pro_header("Today's Slate",'A compact game-day overview and quick links to your research tools.')
        local_tz=ZoneInfo('America/Indiana/Indianapolis')
        day=dt.datetime.now(local_tz).date()
        st.caption('Schedule from ESPN · Eastern Indiana time · refresh the page for updated scores.')
        try:
            data=scoreboard(day.strftime('%Y%m%d'))
            events=data.get('events',[])
            if not events: st.info('No NBA games returned for today.')
            else:
                cols=st.columns(3)
                for idx,event in enumerate(events):
                    comp=(event.get('competitions') or [{}])[0]
                    teams=comp.get('competitors') or []
                    home=next((x for x in teams if x.get('homeAway')=='home'),{})
                    away=next((x for x in teams if x.get('homeAway')=='away'),{})
                    def name(x): return x.get('team',{}).get('abbreviation','?')
                    stamp=event.get('date','')
                    try: tip=dt.datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(local_tz).strftime('%-I:%M %p %Z')
                    except (ValueError,TypeError): tip='TBA'
                    status=event.get('status',{}).get('type',{}).get('shortDetail','Scheduled')
                    with cols[idx%3]:
                        st.markdown(f'<div style="padding:15px;margin-bottom:12px;border:1px solid #344D70;border-radius:15px;background:#15243B"><div style="color:#FFAE7B;font-size:12px">{html.escape(tip)}</div><div style="color:#FFF;font-size:20px;font-weight:800">{html.escape(name(away))} @ {html.escape(name(home))}</div><div style="color:#AFC2DE;font-size:12px">{html.escape(str(status))}</div></div>',unsafe_allow_html=True)
        except Exception:
            st.warning('The live ESPN schedule could not be retrieved right now.')
        st.caption('Available sportsbook props are displayed in Prop Lab when the configured odds source returns them.')
    elif section=='Prop Finder':
        pro_header('Prop Finder','Compare verified game-log trends across a limited selection of NBA players.')
        st.info('Research candidates, not betting picks. No unverified sportsbook lines or implied win probabilities.')
        roster=[p for p in all_players if p.get('team')==selected.get('team')]
        roster=sorted(roster,key=lambda p:p.get('name',''))
        default_ids=[selected['id']]
        picked=st.multiselect('Players to scan (max 8)',[p['id'] for p in roster],default=default_ids,
             format_func=lambda pid:next((p['name'] for p in roster if p['id']==pid),str(pid)),key='foxk_finder_players')
        metric=st.selectbox('Statistic',available,key='foxk_finder_stat') if available else None
        c1,c2=st.columns(2)
        with c1: line=st.number_input('Comparison threshold (manual research line)',0.0,value=20.5,step=.5,key='foxk_finder_line')
        with c2: side=st.selectbox('Side',['Over','Under'],key='foxk_finder_side')
        if len(picked)>8: st.warning('Choose up to eight players for this scan.')
        elif st.button('Scan selected players',type='primary',key='foxk_finder_run') and metric:
            rows=[]
            for pid in picked:
                p=next((p for p in roster if p['id']==pid),None)
                if not p: continue
                try:
                    log=normalized(player_log(pid,season))
                    result=sample(log,metric,line,side,10)
                    if result:
                        rows.append({'Player':p['name'],'Games':result['games'],'Over/Under':side,
                           'Threshold':line,'Hits / decisions':f"{result['hits']}/{result['decisions']}",
                           'Historical hit rate':f"{result['rate']:.0%}" if result['rate'] is not None else 'N/A',
                           'Average':round(result['avg'],1),'Pushes':result['pushes']})
                except Exception: continue
            if rows:
                dark_table(pd.DataFrame(rows),hide_index=True,use_container_width=True)
                st.caption('All players are compared to the same manually entered threshold; this is NOT a scan of live sportsbook offerings.')
            else: st.info('No comparable game logs were returned.')
    elif section=='Prop Analyzer':
        pro_header('Prop Analyzer','One-screen historical evidence for the currently selected player.')
        if not available: st.info('No numeric player statistics returned.');return
        a,b,c=st.columns(3)
        with a: metric=st.selectbox('Statistic',available,key='foxk_analyzer_metric')
        with b: line=st.number_input('Research line',0.0,value=20.5,step=.5,key='foxk_analyzer_line')
        with c: side=st.selectbox('Direction',['Over','Under'],key='foxk_analyzer_side')
        st.caption('Research line is manually entered; it is not verified as a current sportsbook offering.')
        stats_cards(frame,metric,line,side)
        chart(frame,metric,line)
        if 'MIN' in frame:
            mins=pd.to_numeric(frame['MIN'],errors='coerce').dropna()
            if not mins.empty: st.caption(f'Average minutes, last {min(10,len(mins))} recorded games: {mins.head(10).mean():.1f}')
        if 'opponent' in frame:
            st.caption('Opponent history and teammate context are available in Matchup Intel and Lineup Impact.')
    elif section=='Line Movement':
        pro_header('Line Movement','Save observed sportsbook lines and inspect changes over time.')
        st.warning('This is a manual observation log, not an automated real-time odds feed. Enter only lines you have verified.')
        saved=get_state_list('foxk_line_snapshots')
        a,b,c=st.columns(3)
        with a: metric=st.selectbox('Market',available,key='foxk_line_market') if available else 'PTS'
        with b: book=st.text_input('Sportsbook name',placeholder='Verified source',key='foxk_line_book')
        with c: value=st.number_input('Observed line',min_value=0.0,value=20.5,step=.5,key='foxk_line_value')
        if st.button('Save observed line',key='foxk_line_save'):
            if not book.strip(): st.warning('Enter the sportsbook name.')
            else:
                saved.append({'Recorded at (UTC)':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                    'Player':selected['name'],'Market':metric,'Sportsbook':book.strip()[:60],'Line':float(value)})
                st.success('Saved for this browser session.')
        relevant=[r for r in saved if r['Player']==selected['name']]
        if relevant:
            dark_table(pd.DataFrame(relevant[::-1]),hide_index=True,use_container_width=True)
            matching=[r for r in relevant if r['Market']==metric and r['Sportsbook']==book.strip()]
            if len(matching)>=2:
                observations=pd.DataFrame(matching).copy()
                observations['Observation']=range(1,len(observations)+1)
                movement=alt.Chart(observations).mark_line(
                    point=alt.OverlayMarkDef(filled=True,size=90),color='#FF995D',strokeWidth=3.5
                ).encode(
                    x=alt.X('Observation:O',title='Saved observation',axis=alt.Axis(labelColor='#B5C8E5')),
                    y=alt.Y('Line:Q',title='Observed line',scale=alt.Scale(zero=False),
                            axis=alt.Axis(labelColor='#B5C8E5',gridColor='#293A55')),
                    tooltip=['Recorded at (UTC):N','Sportsbook:N','Line:Q']
                ).properties(height=245,background='#101B2E').configure_view(stroke='#344A68',cornerRadius=14)
                st.altair_chart(movement,use_container_width=True,theme=None)
                st.caption('Manually saved observations only, not a live sportsbook feed.')
            st.download_button('Export line observations',pd.DataFrame(saved).to_csv(index=False).encode(),
                               'foxk_line_observations.csv','text/csv',key='foxk_line_export')
        else: st.info('No line observations saved for this player.')
    elif section=='Injury Context':
        pro_header('Injury & Lineup Context','Research minutes and teammate availability without guessing injury status.')
        st.warning('FOXK does not have a verified real-time injury feed. Confirm official team or NBA injury reports before using injury information.')
        st.markdown('**Minutes trend**')
        if 'MIN' in frame:
            mins=pd.to_numeric(frame['MIN'],errors='coerce').dropna()
            cols=st.columns(3)
            for col,n in zip(cols,[5,10,20]):
                with col: st.metric(f'Last {n} avg minutes',f'{mins.head(n).mean():.1f}' if len(mins) else 'N/A')
            chart(frame,'MIN',float(mins.head(10).mean()) if len(mins) else 0)
        st.markdown('**Manual availability notes**')
        st.text_area('Your notes (unverified until checked)',key='foxk_injury_notes',
            placeholder='Record an official report and timestamp; do not infer an injury from missing box-score rows.')
        st.caption('For recorded with/without teammate game comparisons, use the Lineup Impact tab.')
    elif section=='Pick Tracker':
        pro_header('Pick Tracker','Record picks, outcomes, and transparent historical results.')
        st.caption('Stored in the current Streamlit session only. Export CSV to keep records. No automatic settlement or betting account connection.')
        picks=get_state_list('foxk_pick_tracker')
        a,b,c,d=st.columns(4)
        with a: metric=st.selectbox('Statistic',available,key='foxk_pick_metric') if available else 'PTS'
        with b: line=st.number_input('Line',0.0,value=20.5,step=.5,key='foxk_pick_line')
        with c: side=st.selectbox('Side',['Over','Under'],key='foxk_pick_side')
        with d: american=st.number_input('American odds',value=-110,step=5,key='foxk_pick_odds')
        if st.button('Add to pick tracker',type='primary',key='foxk_pick_add'):
            picks.append({'ID':len(picks)+1,'Date':dt.date.today().isoformat(),'Player':selected['name'],
              'Stat':metric,'Line':float(line),'Side':side,'American odds':int(american),'Result':'Pending','Units':1.0})
            st.success('Pick saved for this session.')
        if picks:
            dark_table(pd.DataFrame(picks),hide_index=True,use_container_width=True)
            pending=[p for p in picks if p['Result']=='Pending']
            if pending:
                a,b=st.columns(2)
                with a: chosen=st.selectbox('Settle a pick',pending,
                    format_func=lambda p:f"#{p['ID']} · {p['Player']} {p['Stat']} {p['Side']} {p['Line']}",key='foxk_pick_settle_id')
                with b: result=st.selectbox('Result',['Win','Loss','Push'],key='foxk_pick_result')
                if st.button('Save result',key='foxk_pick_settle'):
                    chosen['Result']=result
                    st.rerun()
            settled=[p for p in picks if p['Result']!='Pending']
            profit=0.0
            for p in settled:
                odds=p['American odds']; stake=p['Units']
                if p['Result']=='Win': profit+=stake*(odds/100 if odds>0 else 100/abs(odds)) if odds else 0
                elif p['Result']=='Loss': profit-=stake
            stake_sum=sum(p['Units'] for p in settled)
            a,b,c=st.columns(3)
            a.metric('Settled picks',len(settled));b.metric('Net units',f'{profit:+.2f}');c.metric('ROI',f'{profit/stake_sum:.1%}' if stake_sum else 'N/A')
            st.download_button('Export all picks CSV',pd.DataFrame(picks).to_csv(index=False).encode(),
                               'foxk_pick_tracker.csv','text/csv',key='foxk_picks_export')
    elif section=='FOXK Assistant':
        pro_header('FOXK Research Assistant','Ask a stats question about the selected player.')
        st.caption('This is a deterministic research assistant using returned game logs, not a generative AI model or live news feed.')
        question=st.text_input('Ask about recent performance',placeholder='e.g. last 10 points, rebounds average, minutes',key='foxk_assistant_q')
        if question:
            q=question.lower()
            terms={'points':'PTS','pts':'PTS','rebounds':'REB','reb':'REB','assists':'AST','ast':'AST',
                   'threes':'3PM','3pm':'3PM','minutes':'MIN','min':'MIN','steals':'STL','blocks':'BLK','pra':'PRA'}
            metric=next((m for word,m in terms.items() if word in q and m in available),None)
            n=5 if 'last 5' in q else 20 if 'last 20' in q else 10
            if metric:
                vals=pd.to_numeric(frame[metric],errors='coerce').dropna().head(n)
                if len(vals):
                    st.success(f"{selected['name']} · {metric}: {vals.mean():.1f} average over {len(vals)} recorded games; median {vals.median():.1f}, range {vals.min():g}–{vals.max():g}.")
                    st.caption('Source: ESPN player game logs returned for the selected season. Historical description only.')
                else: st.info('No numeric values for this question.')
            else:
                st.info('Try: “last 10 points”, “last 5 rebounds”, “last 20 assists”, or “minutes”.')
    elif section=='Smart Watchlist':
        pro_header('Smart Watchlist','Save player props and inspect them when you return to this session.')
        saved=get_state_list('foxk_smart_watchlist')
        a,b,c=st.columns(3)
        with a: metric=st.selectbox('Market',available,key='foxk_smart_metric') if available else 'PTS'
        with b: line=st.number_input('Research threshold',0.0,value=20.5,step=.5,key='foxk_smart_line')
        with c: side=st.selectbox('Direction',['Over','Under'],key='foxk_smart_side')
        if st.button('Add to smart watchlist',type='primary',key='foxk_smart_add'):
            item={'Player':selected['name'],'Player ID':selected['id'],'Season':season,
                  'Market':metric,'Threshold':float(line),'Side':side}
            if item not in saved: saved.append(item);st.success('Saved for this session.')
            else: st.info('Already on your watchlist.')
        if saved:
            dark_table(pd.DataFrame(saved),hide_index=True,use_container_width=True)
            st.download_button('Export watchlist CSV',pd.DataFrame(saved).to_csv(index=False).encode(),
                               'foxk_smart_watchlist.csv','text/csv',key='foxk_smart_export')
            if st.button('Clear smart watchlist',key='foxk_smart_clear'):
                saved.clear();st.rerun()
        else: st.info('No saved props yet.')
        st.caption('Automatic background alerts and cross-device syncing require a persistent database and notification service; not enabled in this version.')
