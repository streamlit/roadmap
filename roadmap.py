import streamlit as st
from notion_client import Client
from collections import namedtuple, defaultdict
import datetime
import pandas as pd
import calendar

_DB_ID = "fdd164419a79454f993984b1f8e21f66"
_the_token = st.secrets["notion"]["token"]  # TODO: Fix this in Core

_TTL = 12*60*60

Project = namedtuple("Project", [
    "id",
    "title",
    "public_description",
    "stage",
    "start_date",
    "end_date",
])
TimeGrouping = namedtuple("TimeGrouping", ["year", "number"])
_FUTURE = TimeGrouping(10000, 10000)

@st.cache(allow_output_mutation=True, ttl=_TTL)
def _get_raw_roadmap(only_public=True):
    notion = Client(auth=_the_token)

    public_filter = []

    if only_public:
        public_filter = [dict(
            property="Show on public roadmap",
            checkbox=dict(
                equals=True,
            ),
        )]

    return notion.databases.query(
        database_id=_DB_ID,
        filter={
            "and": [{
                "or": [{
                    "property": "End date",
                    "date": {
                        "after": _get_last_quarter_date_str(),
                    },
                }, {
                    "property": "End date",
                    "date": {
                        "is_empty": True,
                    },
                }]
            }, *public_filter],
        },
    )

@st.cache(allow_output_mutation=True, ttl=_TTL)
def _get_roadmap(results, show_private_roadmap, group_by):
    roadmap = defaultdict(list)

    for result in results:
        props = result["properties"]

        title = _get_plain_text(props["Name"]["title"])
        public_description = _get_plain_text(props["Public description"]["rich_text"])

        if "Stage" in props:
            stage = props["Stage"]["select"]["name"]
        else:
            stage = ""

        if "Schedule" in props and "date" in props["Schedule"]:
            start_date = props["Schedule"]["date"]["start"]
            scheduled_end_date = props["Schedule"]["date"]["end"]
        else:
            start_date = None
            scheduled_end_date = None

        end_date = scheduled_end_date

        if ("Public end date" in props
            and "date" in props["Public end date"]):

            public_end_date = props["Public end date"]["date"]["start"]
            end_date = public_end_date or scheduled_end_date

        p = Project(
            id=result["id"],
            title=title,
            public_description=public_description,
            stage=stage,
            start_date=start_date,
            end_date=end_date,
        )

        if not end_date:
            time_group = _FUTURE
        elif group_by == "Quarter":
            time_group = _get_quarter_for_iso_date(end_date)
        else:
            time_group = _get_month_year_for_iso_date(end_date)

        roadmap[time_group].append(p)

    return roadmap

def _get_last_quarter_date_str():
    now = datetime.datetime.now()
    this_month = now.month
    this_quarter_num = (now.month - 1) // 3 + 1
    prev_quarter_num = (this_quarter_num - 1) % 4
    prev_quarter_year = now.year
    if prev_quarter_num == 0:
        prev_quarter_num = 4
        prev_quarter_year -= 1
    prev_quarter_month = (prev_quarter_num - 1) * 3 + 1
    prev_quarter = datetime.datetime(month=prev_quarter_month, day=1, year=prev_quarter_year)
    return prev_quarter.isoformat()

def _get_quarter_for_iso_date(date_iso):
    date = datetime.datetime.fromisoformat(date_iso)
    quarter_num = (date.month - 1) // 3 + 1
    return TimeGrouping(number=quarter_num, year=date.year)

def _get_month_year_for_iso_date(date_iso):
    date = datetime.datetime.fromisoformat(date_iso)
    return TimeGrouping(number=date.month, year=date.year)

STAGE_NUMBERS = defaultdict(lambda: -1, {
    "Needs triage": 0,
    "Prioritized": 1,
    "⏳ Paused / Waiting": 2,
    "👟 Scoping / speccing": 3,
    "👷 Ready for tech design": 4,
    "👷 In tech design": 5,
    "👷 In development": 6,
    "👟 👷 In testing + polishing": 7,
    "✅ Done": 8,
    "🏁 Ready for launch": 9,
})

def _reverse_sort_by_stage(projects):
    return sorted(
        projects,
        key=lambda x: STAGE_NUMBERS[x.stage],
        reverse=True)

def _get_plain_text(rich_text_property):
    #st.write(rich_text_property)
    return "".join(part["plain_text"] for part in rich_text_property)

def draw(user_is_internal):
    st.image("https://streamlit.io/images/brand/streamlit-mark-color.png", width=50)

    st.write("""
        # Streamlit roadmap

        Welcome to our roadmap! :wave:

        This app lists some important things we're either working on, or
        about to work on. Plus there's always a lot more going on behind the scenes — we sometimes
        like to surprise you :wink:

        Streamlit's incredible growth has been fueled by our amazing community which has
        always been our best source of ideas. So if you don't see your favorite feature listed
        here, ask about it in our [forums](https://discuss.streamlit.io)!
        """)

    st.warning("""
        ✏️ **NOTE:** The dates below are our best guesses. We're bullish on them but we can't make any
        guarantees!
    """)

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
                group_by = st.selectbox("Group by", ["Quarter", "Month"])

                st.write("")
                only_public = st.checkbox("Show only public projects", True)
                only_triaged = st.checkbox("Show only triaged", True)
                st.write("")

    results = _get_raw_roadmap(only_public)["results"]
    roadmap_by_group = _get_roadmap(results, show_private_roadmap, group_by)

    for group in sorted(roadmap_by_group.keys()):

        st.write("")
        st.write("")

        if group == _FUTURE:
            st.header(f"Future 🌈")
        elif group_by == "Quarter":
            st.header(f"Q{group.number} {group.year}")
        else:
            st.header(f"{calendar.month_name[group.number]} {group.year}")

        projects = roadmap_by_group[group]

        for p in _reverse_sort_by_stage(projects):
            cleaned_id = p.id.replace("-", "")
            notion_url = f"https://www.notion.so/streamlit/{cleaned_id}"

            if show_private_roadmap:
                notion_link_str = f" &nbsp; [link]({notion_url})"
            else:
                notion_link_str = ""

            if STAGE_NUMBERS[p.stage] >= 2:
                stage = f" &nbsp; {p.stage}"
            else:
                stage = ""

            st.markdown(f"### {p.title}<small>{stage}{notion_link_str}</small>", unsafe_allow_html=True)

            if p.public_description:
                st.markdown(p.public_description)

