import streamlit as st
import pandas as pd
from datetime import datetime
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import playergamelog, leaguegamelog, leagueseasonmatchups

st.set_page_config(page_title='FOXK NBA Research',page_icon='🏀',layout='wide')
st.markdown('''<style>.stApp{background:#0b1020;color:#f2f5fc}h1,h2,h3{color:#f4f7ff}.stMetric{background:#18213a;border-radius:12px;padding:12px}</style>''',unsafe_allow_html=True)
st.title('🏀 FOXK NBA STAT LAB')
st.caption('Real NBA.com data • No subscription or API key • Public dashboard • Missing data is never invented')

@st.cache_data(ttl=3600,show_spinner=False)
def logs(pid,season,season_type):
    return playergamelog.PlayerGameLog(player_id=pid,season=season,season_type_all_star=season_type,timeout=35).get_data_frames()[0]

@st.cache_data(ttl=3600,show_spinner=False)
def season_players(season,season_type):
    return leaguegamelog.LeagueGameLog(season=season,season_type_all_star=season_type,player_or_team_abbreviation='P',timeout=45).get_data_frames()[0]

@st.cache_data(ttl=3600,show_spinner=False)
def defender_data(season,off_id,def_id):
    return leagueseasonmatchups.LeagueSeasonMatchups(season=season,off_player_id_nullable=off_id,def_player_id_nullable=def_id,timeout=35).get_data_frames()[0]

all_players=players.get_players()
names=sorted(all_players,key=lambda p:p['full_name'])
lookup={f"{p['full_name']} · {p['id']}":p['id'] for p in names}
team_names={t['abbreviation']:t['full_name'] for t in teams.get_teams()}
team_options=['All opponents']+sorted(team_names)
current_year=datetime.now().year
season_default=f'{current_year if datetime.now().month>=10 else current_year-1}-{str((current_year+1 if datetime.now().month>=10 else current_year)%100).zfill(2)}'
seasons=[f'{y}-{str((y+1)%100).zfill(2)}' for y in range(current_year,current_year-21,-1)]
with st.sidebar:
    st.header('Research filters')
    player_label=st.selectbox('Player',list(lookup),index=next((i for i,k in enumerate(lookup) if k.startswith('Donovan Mitchell ·')),0))
    pid=lookup[player_label]
    season=st.selectbox('Season',seasons,index=seasons.index(season_default) if season_default in seasons else 0)
    season_type=st.selectbox('Competition',['Regular Season','Playoffs'])
    opponent=st.selectbox('Opponent',team_options)
    venue=st.selectbox('Location',['All','Home','Away'])
    recent=st.selectbox('Games window',['All',5,10,15,20])
    stat=st.selectbox('Prop statistic',['PTS','REB','AST','FG3M','STL','BLK','PRA','PR','PA','RA'])
    line=st.number_input('Prop line (over)',min_value=0.0,value=24.5,step=0.5)
    st.caption('The source is NBA.com. Some requests may time out or be blocked by NBA.com.')

try:
    with st.spinner('Retrieving verified NBA.com game logs…'):
        df=logs(pid,season,season_type).copy()
except Exception as e:
    st.error('NBA.com did not return the game log. This can be caused by throttling, regional access, or a temporary outage. No statistics will be fabricated.')
    st.code(str(e));st.stop()
if df.empty:
    st.warning('No verified game logs available for this player and season.');st.stop()
df['GAME_DATE']=pd.to_datetime(df['GAME_DATE'])
df=df.sort_values('GAME_DATE',ascending=False)
df['OPPONENT']=df['MATCHUP'].str.extract(r'(?:vs\.|@)\s*([A-Z]{3})')[0]
df['LOCATION']=df['MATCHUP'].apply(lambda x:'Home' if 'vs.' in x else 'Away')
if opponent!='All opponents':df=df[df['OPPONENT']==opponent]
if venue!='All':df=df[df['LOCATION']==venue]
if recent!='All':df=df.head(int(recent))
for key,parts in {'PRA':['PTS','REB','AST'],'PR':['PTS','REB'],'PA':['PTS','AST'],'RA':['REB','AST']}.items():df[key]=df[parts].sum(axis=1)
if df.empty:st.warning('No games match these filters.');st.stop()
st.subheader(f'{player_label.split(" · ")[0]} — {season}')
st.caption(f'Filtered sample: {len(df)} games · {season_type} · {opponent} · {venue} · {recent} game window')
cols=st.columns(6)
for col,key in zip(cols,['PTS','REB','AST','FG3M','MIN','FG_PCT']):
    val=pd.to_numeric(df[key],errors='coerce').mean()
    col.metric(key, f'{val:.1%}' if key=='FG_PCT' else f'{val:.1f}')
values=pd.to_numeric(df[stat],errors='coerce').dropna()
hits=int((values>line).sum());n=len(values)
st.subheader('Prop research')
a,b,c=st.columns(3)
a.metric(f'{stat} over {line:g}',f'{hits}/{n} games')
b.metric('Historical hit rate',f'{hits/n:.1%}' if n else 'N/A')
c.metric(f'{stat} average',f'{values.mean():.2f}' if n else 'N/A')
st.caption('Descriptive historical hit rate, NOT a predicted probability or betting edge. Pushes on whole-number lines count as neither over nor a winning over.')
st.bar_chart(df.sort_values('GAME_DATE').set_index('GAME_DATE')[[stat]])

st.subheader('With / without teammate (game participation)')
st.caption('WITH means the selected teammate recorded a box-score appearance in the same game. This is NOT an on-court possession-level split or an injury diagnosis.')
try:
    with st.spinner('Checking teammate game appearances…'):
        league=season_players(season,season_type)
    # Restrict selection to players who shared at least one team-game with subject in full season.
    subject_games=logs(pid,season,season_type)
    sub=league[league['GAME_ID'].astype(str).isin(subject_games['GAME_ID'].astype(str))] if 'Game_ID' in subject_games else league[league['GAME_ID'].astype(str).isin(subject_games['GAME_ID'].astype(str))]
    # Match the team for each specific game to exclude opposing players.
    my_team=subject_games[['GAME_ID','MATCHUP']].copy()
    my_team['TEAM_ABBREVIATION']=my_team['MATCHUP'].str.extract(r'^([A-Z]{3})')[0]
    sub=sub.merge(my_team[['GAME_ID','TEAM_ABBREVIATION']],on=['GAME_ID','TEAM_ABBREVIATION'])
    choices=sub[sub['PLAYER_ID']!=pid][['PLAYER_ID','PLAYER_NAME']].drop_duplicates().sort_values('PLAYER_NAME')
    opts={f"{r.PLAYER_NAME} · {r.PLAYER_ID}":int(r.PLAYER_ID) for r in choices.itertuples()}
    if opts:
        mate=st.selectbox('Teammate',list(opts));mate_id=opts[mate]
        played=set(sub.loc[sub['PLAYER_ID']==mate_id,'GAME_ID'].astype(str))
        d=df.copy();d['Teammate status']=d['GAME_ID'].astype(str).map(lambda g:'WITH' if g in played else 'WITHOUT')
        summary=d.groupby('Teammate status').agg(Games=('GAME_ID','size'),PTS=('PTS','mean'),REB=('REB','mean'),AST=('AST','mean'),FG3M=('FG3M','mean'),MIN=('MIN','mean')).round(2)
        st.dataframe(summary,use_container_width=True)
        if summary.shape[0]<2:st.info('Only one status occurs in this filtered sample; there is no meaningful comparison.')
    else:st.info('No verified teammate appearances were found for this season.')
except Exception as e:
    st.warning('The NBA.com league-wide game-log request failed; teammate splits are temporarily unavailable.')
    st.caption(str(e))

st.subheader('Direct defensive matchup (when NBA tracking data is available)')
st.caption('NBA tracking possessions differ from team head-to-head game logs. No defender assignment is inferred from being in the same game.')
with st.expander('Load tracked player-versus-defender matchup'):
    def_label=st.selectbox('Defender',list(lookup),index=0)
    if st.button('Retrieve verified matchup tracking'):
        try:
            tracked=defender_data(season,pid,lookup[def_label])
            if tracked.empty:st.info('No tracked matchup data returned for this pair and season.')
            else:st.dataframe(tracked,use_container_width=True)
        except Exception as e:st.warning(f'NBA.com matchup tracking unavailable: {e}')

st.subheader('Every matching game')
columns=['GAME_DATE','MATCHUP','WL','MIN','PTS','REB','AST','FG3M','FGA','FG_PCT','STL','BLK','TOV','PRA']
st.dataframe(df[[x for x in columns if x in df.columns]],use_container_width=True,hide_index=True)
st.download_button('Export verified filtered games (CSV)',df.to_csv(index=False).encode('utf-8'),file_name='foxk_verified_games.csv',mime='text/csv')
st.divider()
st.markdown('### FOXK research summary')
st.write(f"Across **{n} verified games** matching your filters, {player_label.split(' · ')[0]} averaged **{values.mean():.2f} {stat}**, exceeding **{line:g}** in **{hits} games ({hits/n:.1%})**.")
st.caption('This is a deterministic summary of real retrieved statistics, not a paid language-model AI. It does not predict future outcomes. Data © respective owners; unofficial, not affiliated with NBA.')
