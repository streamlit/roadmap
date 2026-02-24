# Streamlit public roadmap

The Streamlit roadmap is a Streamlit app itself 🤯!

This app reads our internal Roadmap DB from Notion and shows a beautiful view for everyone in the
world to marvel.

Check it out:

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://roadmap.streamlit.app/)

## Development Setup

To run this app locally:

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Create `.streamlit/secrets.toml` with Notion credentials:
```toml
[notion]
token = "your_notion_api_token"
projects_database_id = "your_database_id"
```
4. Run the app:
```bash
streamlit run streamlit_app.py
```

Note: You'll need access to the Streamlit Notion database for this to work properly.