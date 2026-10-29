# FOXK NBA Stat Lab — Public Edition

A free Streamlit NBA statistics dashboard. Game data comes from NBA.com via the open-source `nba_api` Python package. No API key or CSV uploads required. NBA.com can rate-limit or block requests from cloud hosts; no data is invented when unavailable.

## Publish publicly (free)

1. Create a free GitHub account at https://github.com and a new **public** repository, e.g. `foxk-nba-stat-lab`.
2. Upload `app.py`, `requirements.txt`, and the `.streamlit/config.toml` file (preserving the `.streamlit` folder). GitHub's web uploader may hide dot-folders; the theme file is optional.
3. Sign in at https://share.streamlit.io with GitHub.
4. Choose **Create app**, select your repository, the `main` branch, and `app.py` as the entrypoint.
5. Click **Deploy**. Streamlit will install the dependencies and generate a public `*.streamlit.app` URL.
6. Open the public URL from any device. You can share it with anyone.

No paid plan is required for normal free-tier use. Free hosting has resource and usage limits. Public access means everyone with the URL can use the dashboard; it is not password-protected.

## Local test (optional)

`python -m pip install -r requirements.txt`

`python -m streamlit run app.py`

## Data limitations

- With/without teammate is based on game appearances, not confirmed injury status or on-court possession-level splits.
- Defender tracking appears only when the NBA endpoint returns verified data.
- Historical prop hit rates are descriptive, not future probabilities.
- This app does not currently include a generative AI service, real-time injury reports, or live odds.
