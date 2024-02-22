import datetime
import re
from collections import defaultdict, namedtuple

import streamlit as st
from notion_client import Client

st.set_page_config("Roadmap", "https://streamlit.io/favicon.svg")
TTL = 24 * 60 * 60

Project = namedtuple(
    "Project",
    [
        "id",
        "title",
        "icon",
        "public_description",
        "stage",
        "quarter",
    ],
)


@st.cache_data(ttl=TTL, show_spinner="Fetching roadmap...")
def _get_raw_roadmap():
    notion = Client(auth=st.secrets.notion.token)
    return notion.databases.query(
        database_id=st.secrets.notion.projects_database_id,
        filter={
            "property": "Show on public Streamlit roadmap",
            "checkbox": {"equals": True},
        },
    )


@st.cache_data(ttl=TTL, show_spinner="Fetching roadmap...")
def _get_roadmap(results):
    roadmap = defaultdict(list)

    for result in results:
        props = result["properties"]

        title = _get_plain_text(props["Name"]["title"])
        # Manually remove "(parent project)" and "(release)" and "(experimental release)" from titles.
        # TODO: Could extend this to remove everything in brackets. 
        title = title.replace("(parent project)", "")
        title = title.replace("(release)", "")
        title = title.replace("(experimental release)", "")
        title = title.replace("(PrPr)", "")
        title = title.replace("(PuPr)", "")
        title = title.replace("(GA)", "")
        title = title.replace(" - FKA st.database", "")
        if "icon" in result and result["icon"]["type"] == "emoji":
            icon = result["icon"]["emoji"]
        else:
            icon = "🏳️"
        public_description = _get_plain_text(props["Public description"]["rich_text"])

        if "Stage" in props:
            stage = props["Stage"]["select"]["name"]
        else:
            stage = ""

        if (
            "Quarter" in props
            and props["Quarter"]["select"] is not None
        ):
            quarter = props["Quarter"]["select"]["name"]
        else:
            quarter = "Future"

        p = Project(
            id=result["id"],
            title=title,
            icon=icon,
            public_description=public_description,
            stage=stage,
            quarter=quarter,
        )
        roadmap[quarter].append(p)

    return roadmap


def _get_current_quarter_label():
    now = datetime.datetime.now()

    # Note that we are using Snowflake fiscal quarters, i.e. Q1 starts in February.
    if now.month == 1:
        quarter_num = 4
        months = f"Nov {now.year - 1} - Jan {now.year}"
    if now.month >= 2 and now.month <= 4:
        quarter_num = 1
        months = f"Feb - Apr {now.year}"
    elif now.month >= 5 and now.month <= 7:
        quarter_num = 2
        months = f"May - Jul {now.year}"
    elif now.month >= 8 and now.month <= 10:
        quarter_num = 3
        months = f"Aug - Oct {now.year}"
    elif now.month >= 11 and now.month <= 12:
        quarter_num = 4
        months = f"Nov {now.year} - Jan {now.year + 1}"

    if now.month == 1:
        fiscal_year = str(now.year)[2:]
    else:
        fiscal_year = str(now.year + 1)[2:]

    return f"Q{quarter_num}/FY{fiscal_year} ({months})"


QUARTER_SORT = {
    "Q2/FY23 (May - Jul 2022)": 0,
    "Q3/FY23 (Aug - Oct 2022)": 1,
    "Q4/FY23 (Nov 2022 - Jan 2023)": 2,
    "Q1/FY24 (Feb - Apr 2023)": 3,
    "Q2/FY24 (May - Jul 2023)": 4,
    "Q3/FY24 (Aug - Oct 2023)": 5,
    "Q4/FY24 (Nov 2023 - Jan 2024)": 6,
    "Q1/FY25 (Feb - Apr 2024)": 7,
    "Q2/FY25 (May - Jul 2024)": 8,
    "Q3/FY25 (Aug - Oct 2024)": 9,
    "Q4/FY25 (Nov 2024 - Jan 2025)": 10,
    "Future": 11,
}

# Doing a defaultdict here because if there's a new stage, it's ok to just silently plug
# it at the bottom. For quarters above, I'd want the app to show an exception if
# something goes wrong (rather than failing silently), so keeping it as a normal dict.
STAGE_SORT = defaultdict(
    lambda: -1,
    {
        "Needs triage": 0,
        "Backlog": 1,
        "Prioritized": 2,
        "⏳ Paused / Waiting": 3,
        "👟 Scoping / speccing": 4,
        "👷 In tech design": 5,
        "👷 Ready for dev / work": 6,
        "👷 In development / drafting": 7,
        "👟 👷 In testing / review": 8,
        "🏁 Ready for launch / publish": 9,
        "✅ Done / launched / published": 10,
    },
)

STAGE_COLORS = {
    "Needs triage": "rgba(206, 205, 202, 0.5)",
    "Backlog": "rgba(206, 205, 202, 0.5)",
    "Prioritized": "rgba(206, 205, 202, 0.5)",
    "👟 Scoping / speccing": "rgba(221, 0, 129, 0.2)",
    "👷 In tech design": "rgba(221, 0, 129, 0.2)",
    "👷 Ready for dev / work": "rgba(221, 0, 129, 0.2)",
    "👷 In development / drafting": "rgba(0, 135, 107, 0.2)",
    "👟 👷 In testing / review": "rgba(0, 120, 223, 0.2)",
    "🏁 Ready for launch / publish": "rgba(103, 36, 222, 0.2)",
    "✅ Done / launched / published": "rgba(140, 46, 0, 0.2)",
}
STAGE_SHORT_NAMES = {
    "Needs triage": "Needs triage",
    "Backlog": "Backlog",
    "Prioritized": "Prioritized",
    "👟 Scoping / speccing": "👟 Planning",
    "👷 In tech design": "👟 Planning",
    "👷 Ready for dev / work": "👟 Planning",
    "👷 In development / drafting": "👷 Development",
    "👟 👷 In testing / review": "🧪 Testing",
    "🏁 Ready for launch / publish": "🏁 Ready for launch",
    "✅ Done / launched / published": "✅ Launched",
}


def _get_stage_tag(stage):
    color = STAGE_COLORS.get(stage, "rgba(206, 205, 202, 0.5)")
    short_name = STAGE_SHORT_NAMES.get(stage, stage)
    return (
        f'<span style="background-color: {color}; padding: 1px 6px; '
        "margin: 0 5px; display: inline; vertical-align: middle; "
        f"border-radius: 0.25rem; font-size: 0.75rem; font-weight: 400; "
        f'white-space: nowrap">{short_name}'
        "</span>"
    )


def _reverse_sort_by_stage(projects):
    return sorted(projects, key=lambda x: STAGE_SORT[x.stage], reverse=True)


def _get_plain_text(rich_text_property):
    return "".join(part["plain_text"] for part in rich_text_property)


SPACE = "&nbsp;"


def _draw_groups(roadmap_by_group, groups):

    for group in groups:

        projects = roadmap_by_group[group]
        cleaned_group = (
            re.sub(r"Q./FY..", "", group)
            .replace("(", "")
            .replace(")", "")
            .replace("-", "–")
        )
        st.write("")
        st.header(cleaned_group)

        for p in _reverse_sort_by_stage(projects):

            if STAGE_SORT[p.stage] >= 4:
                stage = _get_stage_tag(p.stage)
            else:
                stage = ""

            description = ""

            if p.public_description:
                description = f"<br /><small style='color: #808495'>{p.public_description}</small>"

            a, b = st.columns([0.03, 0.97])
            a.markdown(p.icon)
            b.markdown(f"<strong>{p.title}</strong> {stage}{description}", unsafe_allow_html=True)



st.image("https://streamlit.io/images/brand/streamlit-mark-color.png", width=78)

st.write(
    """
    # Streamlit roadmap

    Welcome to our roadmap! 👋 This app shows some projects we're working on or have
    planned for the future. Plus, there's always more going on behind the scenes — we
    sometimes like to surprise you ✨
    """
)

st.info(
    """
    Need a feature that's not on here?
    [Let us know by opening a GitHub issue!](https://github.com/streamlit/streamlit/issues)
    """,
    icon="👾",
)

st.success(
    """
    Read [the blog post on Streamlit's roadmap](https://blog.streamlit.io/the-next-frontier-for-streamlit/)
    to understand our broader vision.
    """,
    icon="🗺",
)

results = _get_raw_roadmap()["results"]
roadmap_by_group = _get_roadmap(results)  # , group_by)

sorted_groups = sorted(roadmap_by_group.keys(), key=lambda x: QUARTER_SORT[x])
current_quarter_index = QUARTER_SORT[_get_current_quarter_label()]
past_groups = filter(lambda x: QUARTER_SORT[x] < current_quarter_index, sorted_groups)
future_groups = filter(
    lambda x: QUARTER_SORT[x] >= current_quarter_index, sorted_groups
)

with st.expander("Show past quarters"):
    _draw_groups(roadmap_by_group, past_groups)
_draw_groups(roadmap_by_group, future_groups)
