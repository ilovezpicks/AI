# FOXK NBA Stat Lab — ESPN feed edition

Public Streamlit app, no API key. ESPN's publicly accessible endpoints are unofficial and can change, throttle, or stop working. No invented data. Current team rosters and per-player season game logs are loaded automatically and cached.

## Update your existing site
Upload `app.py`, `requirements.txt`, and `.streamlit/config.toml` into the root of your existing GitHub repository (`ilovezpicks/AI`), replacing the old versions. Streamlit Community Cloud should redeploy automatically, preserving your existing app URL.

## Limitations
This edition provides player search, game logs, opponent/home-away filtering when returned by ESPN, averages and historical prop hit rates. It does not yet provide teammate in/out splits or defender matchups. These require additional verified data and should never be guessed. Free ESPN feeds have no uptime guarantee.
