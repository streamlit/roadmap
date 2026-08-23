# Streamlit public roadmap

The Streamlit roadmap is a Streamlit app itself 🤯!

The app reads roadmap data from the public
[`streamlit/streamlit`](https://github.com/streamlit/streamlit) repository:

- Open, dated milestones provide upcoming versions and target release dates.
- Closed, dated milestones and their issues load lazily in a past-releases history.
- The `Planned` milestone provides other near-term projects.
- Open, non-draft pull requests labeled `change:spec` provide specs in review.
- Issue captions use the generated [open-issues summary CSV](https://github.com/streamlit/st-issues/blob/main/static/github_issues_open_cleaned_all_summarized.csv)
  and are omitted when a generated summary is unavailable.
- Issue title icons use an explicit mapping of every current `feature:` and `area:`
  label, with generic feature-request and bug icons as fallbacks.

GitHub data is cached globally for four hours. After expiry, Streamlit serves the
cached roadmap while refreshing it in the background.

## Run locally

Create the environment and install dependencies with [`uv`](https://docs.astral.sh/uv/):

```bash
uv venv
uv pip install -r requirements.txt
source .venv/bin/activate
streamlit run streamlit_app.py
```

The app can read this public data without authentication. For a higher GitHub API
rate limit, add a token to `.streamlit/secrets.toml` (which is gitignored):

```toml
[github]
token = "your-github-token"
```

Check out the deployed app:

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/streamlit/roadmap)
