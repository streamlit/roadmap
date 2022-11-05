import calendar
import datetime
from collections import defaultdict, namedtuple

import pandas as pd
import streamlit as st
from notion_client import Client
import re


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
        # "start_date",
        # "end_date",
    ],
)
# TimeGrouping = namedtuple("TimeGrouping", ["year", "number"])
# _FUTURE = TimeGrouping(10000, 10000)


@st.cache(allow_output_mutation=True, ttl=_TTL)
def _get_raw_roadmap(only_public=True):
    notion = Client(auth=_the_token)

    public_filter = []

    if only_public:
        public_filter = [
            dict(
                property="Show on public Streamlit roadmap",
                checkbox=dict(
                    equals=True,
                ),
            )
        ]

    return notion.databases.query(
        database_id=_DB_ID,
        filter={
            "and": [
                # TODO: Hiding this for now, since we don't want to filter on dates any 
                # more, but on the "Planned quarter" select. We could add a simple filter
                # on end date here to filter out very old projects but I don't think
                # it's necessary. 
                # {
                #     "or": [
                #         {
                #             "property": "End date",
                #             "date": {
                #                 "after": _get_last_quarter_date_str(),
                #             },
                #         },
                #         {
                #             "property": "End date",
                #             "date": {
                #                 "is_empty": True,
                #             },
                #         },
                #     ]
                # },
                *public_filter,
            ],
        },
    )


@st.cache(allow_output_mutation=True, ttl=_TTL)
def _get_roadmap(results, show_private_roadmap):
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
            
        if "Planned quarter" in props and props["Planned quarter"]["select"] is not None:
            # st.write(props["Planned quarter"])
            quarter = props["Planned quarter"]["select"]["name"]
        else:
            quarter = "🌈 Future"

        # if (
        #     "Schedule" in props
        #     and "date" in props["Schedule"]
        #     and props["Schedule"]["date"] is not None
        # ):
        #     start_date = props["Schedule"]["date"]["start"]
        #     scheduled_end_date = props["Schedule"]["date"]["end"]
        # else:
        #     start_date = None
        #     scheduled_end_date = None

        # end_date = scheduled_end_date

        # if (
        #     "Public end date" in props
        #     and "date" in props["Public end date"]
        #     and props["Public end date"]["date"] is not None
        # ):

        #     public_end_date = props["Public end date"]["date"]["start"]
        #     end_date = public_end_date or scheduled_end_date

        p = Project(
            id=result["id"],
            title=title,
            icon=icon,
            public_description=public_description,
            stage=stage,
            quarter=quarter,
            # start_date=start_date,
            # end_date=end_date,
        )

        # if not end_date:
        #     time_group = _FUTURE
        # elif group_by == "Quarter":
        #     time_group = _get_quarter_for_iso_date(end_date)
        # else:
        #     time_group = _get_month_year_for_iso_date(end_date)

        roadmap[quarter].append(p)

    return roadmap


# def _get_last_quarter_date_str():
#     now = datetime.datetime.now()
#     this_month = now.month
#     this_quarter_num = (now.month - 1) // 3 + 1
#     prev_quarter_num = (this_quarter_num - 1) % 4
#     prev_quarter_year = now.year
#     if prev_quarter_num == 0:
#         prev_quarter_num = 4
#         prev_quarter_year -= 1
#     prev_quarter_month = (prev_quarter_num - 1) * 3 + 1
#     prev_quarter = datetime.datetime(
#         month=prev_quarter_month, day=1, year=prev_quarter_year
#     )
#     return prev_quarter.isoformat()


# def _get_quarter_for_iso_date(date_iso):
#     date = datetime.datetime.fromisoformat(date_iso)
#     quarter_num = (date.month - 1) // 3 + 1
#     return TimeGrouping(number=quarter_num, year=date.year)


# def _get_month_year_for_iso_date(date_iso):
#     date = datetime.datetime.fromisoformat(date_iso)
#     return TimeGrouping(number=date.month, year=date.year)

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
            
        # TODO: Move this outside.
        QUARTER_TO_EMOJI = {1: "🌱", 2: "☀️", 3: "🍂", 4: "⛄️"}
        emoji = QUARTER_TO_EMOJI[quarter_num]
        
        return f"{emoji} Q{quarter_num}/FY{fiscal_year} ({months})"

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


def draw(user_is_internal):
    st.image("https://streamlit.io/images/brand/streamlit-mark-color.png", width=78)

    st.write(
        """
        # Streamlit roadmap

        Welcome to our roadmap! :wave:

        This app lists some projects we're either working on or planning for the future. 
        Plus, there's always more going on behind the scenes — we sometimes like to 
        surprise you :wink: Our community is the best source of ideas. If you 
        don't see your favorite feature listed here, let us know in the 
        [forums](https://discuss.streamlit.io)!
        """
    )

    st.write("")
    st.info(
        """
        ⛴ The dates below are our best guesses. We're bullish on them but we can't make any
        guarantees!
        """
    )

    group_by = "Quarter"
    only_public = True
    only_triaged = True
    show_private_roadmap = user_is_internal

    if user_is_internal:
        with st.sidebar:
            container = st.sidebar.beta_container()
            show_private_roadmap = not st.checkbox("Show public roadmap", False)

        if show_private_roadmap:
            with container:
                # group_by = st.selectbox("Group by", ["Quarter", "Month"])

                st.write("")
                only_public = st.checkbox("Show only public projects", True)
                only_triaged = st.checkbox("Show only triaged", True)
                st.write("")

    results = _get_raw_roadmap(only_public)["results"]
    roadmap_by_group = _get_roadmap(results, show_private_roadmap)#, group_by)
    
    sorted_groups = sorted(roadmap_by_group.keys(), key=lambda x: QUARTER_SORT.index(x))
    current_quarter_index = QUARTER_SORT.index(_get_current_quarter_label())
    past_groups = filter(lambda x: QUARTER_SORT.index(x) < current_quarter_index, sorted_groups)
    future_groups = filter(lambda x: QUARTER_SORT.index(x) >= current_quarter_index, sorted_groups)
    
    with st.expander("Show past quarters"):
        _draw_groups(roadmap_by_group, past_groups, show_private_roadmap)
        
    _draw_groups(roadmap_by_group, future_groups, show_private_roadmap)

        
        
def _draw_groups(roadmap_by_group, groups, show_private_roadmap):

    for group in groups:

        projects = roadmap_by_group[group]
        cleaned_group = re.sub(r"Q./FY..", "", group).replace("(", "").replace(")", "").replace("-", "–")
        st.write("")
        st.header(cleaned_group)


        for p in _reverse_sort_by_stage(projects):
            cleaned_id = p.id.replace("-", "")
            notion_url = f"https://www.notion.so/streamlit/{cleaned_id}"

            if show_private_roadmap:
                notion_link_str = f" &nbsp; [link]({notion_url})"
            else:
                notion_link_str = ""

            if STAGE_NUMBERS[p.stage] >= 2:
                stage = get_stage_div(p.stage)
            else:
                stage = ""

            st.markdown(
                f"#### {p.icon} {p.title} {stage} <small>{notion_link_str}</small>",
                unsafe_allow_html=True,
            )

            if p.public_description:
                st.markdown(p.public_description)
