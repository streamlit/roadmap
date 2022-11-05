import datetime
import re
from collections import defaultdict, namedtuple

import streamlit as st
from notion_client import Client

st.set_page_config(
    "Roadmap", "https://streamlit.io/favicon.svg"
)

_DB_ID = "fdd164419a79454f993984b1f8e21f66"
_the_token = st.secrets["notion"]["token"]  # TODO: Fix this in Core

_TTL = 12 * 60 * 60

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


@st.cache(allow_output_mutation=True, ttl=_TTL)
def _get_raw_roadmap():
    notion = Client(auth=_the_token)
    return notion.databases.query(
        database_id=_DB_ID,
        filter={
            "property": "Show on public Streamlit roadmap",
            "checkbox": {"equals": True},
        },
    )


@st.cache(allow_output_mutation=True, ttl=_TTL)
def _get_roadmap(results):
    roadmap = defaultdict(list)

    for result in results:
        props = result["properties"]

        title = _get_plain_text(props["Name"]["title"])
        # Manually remove "(parent project)" from titles.
        title = title.replace("(parent project)", "")
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
            "Planned quarter" in props
            and props["Planned quarter"]["select"] is not None
        ):
            quarter = props["Planned quarter"]["select"]["name"]
        else:
            quarter = "🌈 Future"

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

    emoji = QUARTER_TO_EMOJI[quarter_num]

    return f"{emoji} Q{quarter_num}/FY{fiscal_year} ({months})"


QUARTER_TO_EMOJI = {1: "🌱", 2: "☀️", 3: "🍂", 4: "⛄️"}
QUARTER_SORT = [
    "☀️ Q2/FY23 (May - Jul 2022)",
    "🍂 Q3/FY23 (Aug - Oct 2022)",
    "⛄️ Q4/FY23 (Nov 2022 - Jan 2023)",
    "🌱 Q1/FY24 (Feb - Apr 2023)",
    "☀️ Q2/FY24 (May - Jul 2023)",
    "🍂 Q3/FY24 (Aug - Oct 2023)",
    "⛄️ Q4/FY24 (Nov 2023 - Jan 2024)",
    "🌱 Q1/FY25 (Feb - Apr 2024)",
    "☀️ Q2/FY25 (May - Jul 2024)",
    "🍂 Q3/FY25 (Aug - Oct 2024)",
    "⛄️ Q4/FY25 (Nov 2024 - Jan 2025)",
    "🌈 Future",
]

# TODO: Need to clean these dicts and make sure they are still accurate.
STAGE_NUMBERS = defaultdict(
    lambda: -1,
    {
        "Needs triage": 0,
        "Prioritized": 1,
        "⏳ Paused / Waiting": 2,
        "👟 Scoping / speccing": 3,
        "👷 In tech design": 5,
        "👷 In development / drafting": 6,
        "👟 👷 In testing / polishing": 7,
        "🏁 Ready for launch / publish": 8,
        "✅ Done / launched / published": 9,
    },
)

STAGE_COLORS = {
    "Needs triage": "rgba(206, 205, 202, 0.5)",
    # "Backlog": "rgba(206, 205, 202, 0.5)",
    "Prioritized": "rgba(206, 205, 202, 0.5)",
    "👟 Scoping / speccing": "rgba(221, 0, 129, 0.2)",
    "👷 In tech design": "rgba(245, 93, 0, 0.2)",
    "👷 In development / drafting": "rgba(0, 135, 107, 0.2)",
    "👟 👷 In testing / polishing": "rgba(0, 120, 223, 0.2)",
    "🏁 Ready for launch / publish": "rgba(103, 36, 222, 0.2)",
    "✅ Done / launched / published": "rgba(140, 46, 0, 0.2)",
    # "❌ Won't fix": "rgba(155, 154, 151, 0.4)",
}

STAGE_SHORT_NAMES = {
    "Needs triage": "Needs triage",
    "Backlog": "Backlog",
    "Prioritized": "Prioritized",
    "👟 Scoping / speccing": "👟 Planning",
    "👷 In tech design": "👟 Planning",
    "👷 In development / drafting": "👷 Development",
    "👟 👷 In testing / polishing": "🧪 Testing",
    "🏁 Ready for launch / publish": "🏁 Ready for launch",
    "✅ Done / launched / published": "✅ Launched",
    # "❌ Won't fix": "rgba(155, 154, 151, 0.4)",
}


def get_stage_div(stage):
    color = STAGE_COLORS.get(stage, "rgba(206, 205, 202, 0.5)")
    short_name = STAGE_SHORT_NAMES.get(stage, stage)
    return (
        f'<div style="background-color: {color}; padding: 1px 6px; '
        "margin: 0 5px; display: inline; vertical-align: middle; "
        f'border-radius: 3px; font-size: 0.75rem; font-weight: 400;">{short_name}'
        "</div>"
    )


def _reverse_sort_by_stage(projects):
    return sorted(projects, key=lambda x: STAGE_NUMBERS[x.stage], reverse=True)


def _get_plain_text(rich_text_property):
    # st.write(rich_text_property)
    return "".join(part["plain_text"] for part in rich_text_property)


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

            if STAGE_NUMBERS[p.stage] >= 2:
                stage = get_stage_div(p.stage)
            else:
                stage = ""

            st.markdown(f"#### {p.icon} {p.title} {stage}", unsafe_allow_html=True)

            if p.public_description:
                st.markdown(p.public_description)


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

results = _get_raw_roadmap()["results"]
roadmap_by_group = _get_roadmap(results)  # , group_by)

sorted_groups = sorted(roadmap_by_group.keys(), key=lambda x: QUARTER_SORT.index(x))
current_quarter_index = QUARTER_SORT.index(_get_current_quarter_label())
past_groups = filter(
    lambda x: QUARTER_SORT.index(x) < current_quarter_index, sorted_groups
)
future_groups = filter(
    lambda x: QUARTER_SORT.index(x) >= current_quarter_index, sorted_groups
)

with st.expander("Show past quarters"):
    _draw_groups(roadmap_by_group, past_groups)

_draw_groups(roadmap_by_group, future_groups)
