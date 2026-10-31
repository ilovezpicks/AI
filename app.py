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
                    st.dataframe(pd.DataFrame(result),hide_index=True,use_container_width=True)
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
        st.dataframe(saved,hide_index=True,use_container_width=True)
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
