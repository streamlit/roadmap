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

    # Only retrieve projects with an end date in the last twelve months, so we
    # don't have too many items (which slow down the app + make it look cluttered).
    twelve_months_ago = (
        datetime.datetime.now() - datetime.timedelta(days=365)
    ).isoformat()

    # We need this function to handle pagination because the Notion API
    # limits results to 100 items per request. This ensures we get all items
    # that match our filter, even if there are more than 100.
    def fetch_all_results(query_func, **kwargs):
        results = []
        has_more = True
        next_cursor = None

        while has_more:
            response = query_func(**kwargs, start_cursor=next_cursor)
            results.extend(response["results"])
            has_more = response["has_more"]
            next_cursor = response["next_cursor"]

        return results

    return {
        "results": fetch_all_results(
            notion.databases.query,
            database_id=st.secrets.notion.projects_database_id,
            filter={
                "and": [
                    {
                        "property": "Show on roadmap app",
                        "checkbox": {"equals": True},
                    },
                    {
                        "or": [
                            {
                                "property": "End date",
                                "date": {"on_or_after": twelve_months_ago},
                            },
                            {
                                "property": "End date",
                                "date": {"is_empty": True},
                            },
                        ]
                    },
                ]
            },
        )
    }


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
        title = title.replace("(GA, milestone 1)", "")
        title = title.replace("(GA, milestone 2)", "")
        title = title.replace(" - FKA st.database", "")
        if "icon" in result and result["icon"]["type"] == "emoji":
            icon = result["icon"]["emoji"]
        else:
            icon = "🏳️"
        public_description = _get_plain_text(
            props["Description on roadmap app"]["rich_text"]
        )

        if "Stage" in props:
            # st.write(props["Stage"])
            stage = props["Stage"]["status"]["name"]
        else:
            stage = ""

        if "Quarter" in props and props["Quarter"]["select"] is not None:
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

    return f"FY{fiscal_year}/Q{quarter_num} ({months})"


# Doing a defaultdict here because if there's a new stage, it's ok to just silently plug
# it at the bottom. For quarters above, I'd want the app to show an exception if
# something goes wrong (rather than failing silently), so keeping it as a normal dict.
STAGE_SORT = defaultdict(
    lambda: -1,
    {
        # "Needs triage": 0,
        "Backlog": 1,
        # "Prioritized": 2,
        "Paused": 3,
        "Speccing": 4,
        "Ready for development": 5,
        "In development": 6,
        "In testing / review": 7,
        "Ready for launch": 8,
        "Launched": 9,
    },
)

STAGE_COLORS = {
    "Backlog": "#F1F1F0",
    "Speccing": "#FFE2DE",
    "Ready for development": "#FFE2DE",
    "In development": "#FEEBC7",
    "In testing / review": "#E8DEEF",
    "Ready for launch": "#D3E4EF",
    "Launched": "#DCECDB",
}
STAGE_SHORT_NAMES = {
    "Backlog": "Backlog",
    "Speccing": "Planning",
    "Ready for development": "Planning",
    "In development": "Development",
    "In testing / review": "Testing",
    "Ready for launch": "Ready for launch",
    "Launched": "Launched",
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
            re.sub(r"FY../Q.", "", group)
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
            b.markdown(
                f"<strong>{p.title}</strong> {stage}{description}",
                unsafe_allow_html=True,
            )


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
roadmap_by_group = _get_roadmap(results)

sorted_groups = sorted(roadmap_by_group.keys())
current_quarter = _get_current_quarter_label()
past_groups = [group for group in sorted_groups if group < current_quarter]
future_groups = [group for group in sorted_groups if group >= current_quarter]

with st.expander("Show past quarters"):
    _draw_groups(roadmap_by_group, past_groups)
_draw_groups(roadmap_by_group, future_groups)
