import re
from dataclasses import replace
from datetime import date
from urllib.parse import urlparse

import streamlit as st

from github_roadmap import (
    GitHubAPIError,
    MilestoneSection,
    RoadmapItem,
    ellipsize_title,
    load_past_release_items,
    load_roadmap,
)
from roadmap_icons import icon_for_issue

GITHUB_REPOSITORY_URL = "https://github.com/streamlit/streamlit"
RELEASE_NOTES_URL = "https://docs.streamlit.io/develop/quick-reference/release-notes"
STREAMLIT_LOGO_URL = "https://streamlit.io/images/brand/streamlit-mark-color.png"
TTL = 4 * 60 * 60
ROADMAP_CACHE_VERSION = 8

STATUS_COLORS = {
    "Targeted": "blue",
    "Planned": "orange",
    "In review": "violet",
    "Complete": "green",
}

st.set_page_config(page_title="Streamlit roadmap", page_icon=STREAMLIT_LOGO_URL)


def _get_github_token() -> str | None:
    try:
        github_secrets = st.secrets.get("github", {})
    except st.errors.StreamlitSecretNotFoundError:
        return None

    token = github_secrets.get("token")
    return str(token) if token else None


@st.cache_data(
    ttl=TTL,
    max_entries=1,
    show_spinner=False,
    refresh_mode="background",
)
def _get_roadmap(_github_token: str | None, cache_version: int):
    del cache_version
    return load_roadmap(_github_token)


@st.cache_data(
    ttl=TTL,
    max_entries=1,
    show_spinner=False,
    refresh_mode="background",
)
def _get_past_release_items(
    _github_token: str | None,
    milestone_numbers: tuple[int, ...],
    cache_version: int,
):
    del cache_version
    return load_past_release_items(milestone_numbers, _github_token)


def _escape_markdown(text: str) -> str:
    parts = re.split(r"(`[^`\n]+`)", text)
    return "".join(
        part if index % 2 else re.sub(r"([\\`*_[\]{}<>#+!|~-])", r"\\\1", part)
        for index, part in enumerate(parts)
    )


def _format_date(value: date) -> str:
    return f"{value:%B} {value.day}, {value.year}"


def _safe_github_url(url: str) -> str:
    parsed_url = urlparse(url)
    if (
        parsed_url.scheme == "https"
        and parsed_url.netloc == "github.com"
        and parsed_url.path.startswith("/streamlit/streamlit/")
    ):
        return url
    return GITHUB_REPOSITORY_URL


def _draw_item(
    item: RoadmapItem,
    *,
    item_kind: str,
    status_label: str,
) -> None:
    if item.is_closed:
        status_label = "Complete"

    source = "PR" if item_kind == "pull request" else "Issue"

    with st.container(border=True, gap="xsmall"):
        with st.container(
            horizontal=True,
            vertical_alignment="center",
            gap="xsmall",
        ):
            title = _escape_markdown(ellipsize_title(item.title))
            with st.container(
                horizontal=True,
                vertical_alignment="center",
                gap="xsmall",
                width="stretch",
            ):
                if item_kind == "issue":
                    st.markdown(icon_for_issue(item.labels), width="content")
                st.markdown(title, width="stretch")
            st.badge(
                status_label,
                color=STATUS_COLORS[status_label],
                width="content",
            )
            st.link_button(
                ":material/open_in_new:",
                _safe_github_url(item.url),
                type="tertiary",
                help=f"Open {source.lower()} #{item.number} on GitHub",
                width="content",
            )

        if item.description:
            st.caption(item.description)


def _draw_items(
    items: tuple[RoadmapItem, ...],
    *,
    empty_message: str,
    status_label: str,
    item_kind: str = "issue",
) -> None:
    if not items:
        st.caption(empty_message)
        return

    with st.container(gap="xsmall"):
        for item in items:
            _draw_item(
                item,
                item_kind=item_kind,
                status_label=status_label,
            )


def _draw_release(section: MilestoneSection, *, is_past: bool = False) -> None:
    st.subheader(section.title)
    release_date = _format_date(section.due_on) if section.due_on else "To be announced"
    date_label = "Release date" if is_past else "Target release"
    st.caption(
        f"{date_label}: **{release_date}** · [View milestone on GitHub]({section.url})"
    )
    st.space("xsmall")
    _draw_items(
        section.items,
        empty_message=(
            "No roadmap issues were assigned to this milestone."
            if is_past
            else "No roadmap issues in this milestone yet."
        ),
        status_label="Complete" if is_past else "Targeted",
    )


def _draw_past_releases(
    releases: tuple[MilestoneSection, ...],
    github_token: str | None,
) -> None:
    expander = st.expander(
        "Show past releases",
        icon=":material/history:",
        key="past_releases",
        on_change="rerun",
    )
    with expander:
        if not expander.open:
            return

        st.caption(f"[Read the official release notes]({RELEASE_NOTES_URL})")
        if not releases:
            st.caption("No past release milestones are currently published.")
            return

        try:
            with st.spinner("Fetching past releases from GitHub…", show_time=True):
                items_by_milestone = _get_past_release_items(
                    github_token,
                    tuple(release.number for release in releases),
                    ROADMAP_CACHE_VERSION,
                )
        except GitHubAPIError as exc:
            st.error("We couldn't load past release issues from GitHub.")
            st.caption(str(exc))
            return

        for release in releases:
            _draw_release(
                replace(
                    release,
                    items=items_by_milestone.get(release.number, ()),
                ),
                is_past=True,
            )


st.image(STREAMLIT_LOGO_URL, width=78)
st.title("Streamlit roadmap")
st.write(
    "See what we're planning for [upcoming Streamlit releases](#upcoming-releases), "
    "what else is on our [near-term roadmap](#planned), and which "
    "[new feature specs](#specs-in-review) are being reviewed."
)
st.info(
    "Need a feature that's not here? "
    "[Tell us by opening a GitHub issue.]"
    "(https://github.com/streamlit/streamlit/issues)\n\n"
    "To help Streamlit prioritize a feature, upvote issues on GitHub with a 👍. "
    "Your vote helps us identify which enhancements matter most to our users.",
    icon=":material/lightbulb:",
)

roadmap_area = st.container()
github_token = _get_github_token()

try:
    with st.spinner("Fetching the latest roadmap from GitHub…", show_time=True):
        roadmap = _get_roadmap(github_token, ROADMAP_CACHE_VERSION)
except GitHubAPIError as exc:
    roadmap_area.error(
        "We couldn't load the roadmap from GitHub. Please try again in a few minutes.",
        icon=":material/error:",
    )
    roadmap_area.caption(str(exc))
    st.stop()

with roadmap_area:
    _draw_past_releases(roadmap.past_releases, github_token)

    st.header("Upcoming releases")
    if roadmap.releases:
        for release in roadmap.releases:
            _draw_release(release)
    else:
        st.caption("No upcoming release milestones are currently published.")

    st.header("Planned")
    if roadmap.planned:
        st.caption(
            "Other projects we think we're likely to ship within the next few months. "
            f"· [View milestone on GitHub]({roadmap.planned.url})"
        )
        st.space("xsmall")
        _draw_items(
            roadmap.planned.items,
            empty_message="No projects are currently in the Planned milestone.",
            status_label="Planned",
        )
    else:
        st.caption(
            "Other projects we think we're likely to ship within the next few months. "
            "The Planned milestone is not currently published."
        )

    st.header("Specs in review")
    st.caption(
        "Product specs for new features and enhancements currently in review. "
        "Feel free to comment with your thoughts."
    )
    st.space("xsmall")
    _draw_items(
        roadmap.specs,
        empty_message="No feature specs are currently in review.",
        status_label="In review",
        item_kind="pull request",
    )
