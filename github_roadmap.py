from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse

import requests

API_ROOT = "https://api.github.com"
REPOSITORY = "streamlit/streamlit"
REQUEST_TIMEOUT = 20
SPEC_LABEL = "change:spec"
MAX_TITLE_LENGTH = 75
ISSUE_SUMMARIES_URL = (
    "https://raw.githubusercontent.com/streamlit/st-issues/refs/heads/main/"
    "static/github_issues_open_cleaned_all_summarized.csv"
)

JsonObject = dict[str, Any]


class GitHubAPIError(RuntimeError):
    """Raised when GitHub cannot provide roadmap data."""


@dataclass(frozen=True)
class RoadmapItem:
    number: int
    title: str
    url: str
    is_closed: bool = False
    description: str | None = None
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class MilestoneSection:
    number: int
    title: str
    url: str
    due_on: date | None
    items: tuple[RoadmapItem, ...]


@dataclass(frozen=True)
class Roadmap:
    releases: tuple[MilestoneSection, ...]
    past_releases: tuple[MilestoneSection, ...]
    planned: MilestoneSection | None
    specs: tuple[RoadmapItem, ...]


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self._session = session or requests.Session()
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "streamlit-roadmap",
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def get_paginated(
        self,
        path: str,
        params: dict[str, str | int] | None = None,
        *,
        collection_key: str | None = None,
    ) -> list[JsonObject]:
        url = f"{API_ROOT}{path}"
        results: list[JsonObject] = []
        request_params = params

        while url:
            try:
                response = self._session.get(
                    url,
                    headers=self._headers,
                    params=request_params,
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.RequestException as exc:
                raise GitHubAPIError(f"GitHub request failed: {exc}") from exc

            request_params = None
            if not response.ok:
                self._raise_api_error(response)

            try:
                payload = response.json()
            except ValueError as exc:
                raise GitHubAPIError(
                    "GitHub returned an invalid JSON response."
                ) from exc

            if collection_key and isinstance(payload, dict):
                payload = payload.get(collection_key)

            if not isinstance(payload, list):
                raise GitHubAPIError("GitHub returned an unexpected response shape.")

            results.extend(payload)
            url = response.links.get("next", {}).get("url")
            if url:
                parsed_url = urlparse(url)
                if (
                    parsed_url.scheme != "https"
                    or parsed_url.netloc != "api.github.com"
                ):
                    raise GitHubAPIError(
                        "GitHub returned an unexpected pagination URL."
                    )

        return results

    @staticmethod
    def _raise_api_error(response: requests.Response) -> None:
        if response.headers.get("X-RateLimit-Remaining") == "0":
            raise GitHubAPIError(
                "GitHub's API rate limit was reached. Configure a GitHub token in "
                "Streamlit secrets to increase the limit."
            )

        try:
            message = response.json().get("message", "Unexpected GitHub API error")
        except ValueError:
            message = "Unexpected GitHub API error"
        raise GitHubAPIError(f"GitHub API error {response.status_code}: {message}")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _is_roadmap_milestone(milestone: JsonObject) -> bool:
    return milestone.get("title", "").casefold() == "planned" or bool(
        milestone.get("due_on")
    )


def _parse_labels(item: JsonObject) -> tuple[str, ...]:
    return tuple(
        str(label["name"])
        for label in item.get("labels", [])
        if isinstance(label, dict) and label.get("name")
    )


def _clean_title(title: object) -> str:
    return re.sub(
        r"\s*\[coming soon\]\s*",
        " ",
        str(title),
        flags=re.IGNORECASE,
    ).strip()


def ellipsize_title(title: str, max_length: int = MAX_TITLE_LENGTH) -> str:
    """Shorten a displayed title while keeping inline Markdown code balanced."""
    if len(title) <= max_length:
        return title

    shortened = title[: max_length - 1].rstrip()
    if shortened.count("`") % 2:
        shortened += "`"
    return f"{shortened}…"


def _parse_issue(issue: JsonObject, summary: str | None = None) -> RoadmapItem:
    return RoadmapItem(
        number=int(issue["number"]),
        title=_clean_title(issue["title"]),
        url=str(issue["html_url"]),
        is_closed=issue.get("state") == "closed",
        description=summary,
        labels=_parse_labels(issue),
    )


def _parse_milestone(
    milestone: JsonObject,
    issues: list[JsonObject],
    issue_summaries: dict[int, str],
) -> MilestoneSection:
    roadmap_issues = (
        issue
        for issue in issues
        if "pull_request" not in issue and issue.get("state_reason") != "not_planned"
    )
    return MilestoneSection(
        number=int(milestone["number"]),
        title=str(milestone["title"]),
        url=str(milestone["html_url"]),
        due_on=_parse_date(milestone.get("due_on")),
        items=tuple(
            _parse_issue(
                issue,
                issue_summaries.get(int(issue["number"])),
            )
            for issue in roadmap_issues
        ),
    )


def _is_spec_pull_request(pull_request: JsonObject) -> bool:
    labels = {
        str(label.get("name", "")).casefold()
        for label in pull_request.get("labels", [])
    }
    return not pull_request.get("draft", False) and SPEC_LABEL in labels


def _parse_spec(pull_request: JsonObject) -> RoadmapItem:
    title = re.sub(
        r"^\s*\[spec\]\s*",
        "",
        _clean_title(pull_request["title"]),
        flags=re.IGNORECASE,
    )
    return RoadmapItem(
        number=int(pull_request["number"]),
        title=title,
        url=str(pull_request["html_url"]),
        labels=_parse_labels(pull_request),
    )


def build_roadmap(
    milestones: list[JsonObject],
    issues_by_milestone: dict[int, list[JsonObject]],
    pull_requests: list[JsonObject],
    issue_summaries: dict[int, str] | None = None,
) -> Roadmap:
    issue_summaries = issue_summaries or {}
    sections = [
        _parse_milestone(
            milestone,
            issues_by_milestone.get(int(milestone["number"]), []),
            issue_summaries,
        )
        for milestone in milestones
        if milestone.get("state") != "closed" and _is_roadmap_milestone(milestone)
    ]

    past_releases = sorted(
        (
            MilestoneSection(
                number=int(milestone["number"]),
                title=str(milestone["title"]),
                url=str(milestone["html_url"]),
                due_on=_parse_date(milestone.get("due_on")),
                items=(),
            )
            for milestone in milestones
            if milestone.get("state") == "closed" and milestone.get("due_on")
        ),
        key=lambda section: section.due_on or date.min,
        reverse=True,
    )

    planned = next(
        (section for section in sections if section.title.casefold() == "planned"),
        None,
    )
    releases = sorted(
        (
            section
            for section in sections
            if section.title.casefold() != "planned" and section.due_on is not None
        ),
        key=lambda section: section.due_on or date.max,
    )

    spec_pull_requests = sorted(
        (
            pull_request
            for pull_request in pull_requests
            if _is_spec_pull_request(pull_request)
        ),
        key=lambda pull_request: str(pull_request.get("updated_at", "")),
        reverse=True,
    )
    specs = tuple(_parse_spec(pull_request) for pull_request in spec_pull_requests)

    return Roadmap(
        releases=tuple(releases),
        past_releases=tuple(past_releases),
        planned=planned,
        specs=specs,
    )


def parse_issue_summaries_csv(csv_text: str) -> dict[int, str]:
    """Return non-empty generated summaries keyed by GitHub issue number."""
    summaries: dict[int, str] = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        try:
            issue_number = int(row.get("number", ""))
        except (TypeError, ValueError):
            continue

        summary_value = row.get("summary")
        summary = summary_value.strip() if summary_value else ""
        if summary:
            summaries[issue_number] = summary

    return summaries


def load_issue_summaries(
    session: requests.Session | None = None,
) -> dict[int, str]:
    """Load optional issue summaries without exposing GitHub API credentials."""
    request_session = session or requests.Session()
    try:
        response = request_session.get(
            ISSUE_SUMMARIES_URL,
            headers={"User-Agent": "streamlit-roadmap"},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        return {}

    if not response.ok:
        return {}

    return parse_issue_summaries_csv(response.text)


def load_past_release_items(
    milestone_numbers: tuple[int, ...],
    token: str | None = None,
    session: requests.Session | None = None,
) -> dict[int, tuple[RoadmapItem, ...]]:
    """Load past-release issues only when the history view is opened."""
    client = GitHubClient(token=token, session=session)
    items_by_milestone = {}
    for milestone_number in milestone_numbers:
        issues = client.get_paginated(
            f"/repos/{REPOSITORY}/issues",
            params={
                "state": "all",
                "milestone": milestone_number,
                "per_page": 100,
            },
        )
        roadmap_issues = (
            issue
            for issue in issues
            if "pull_request" not in issue
            and issue.get("state_reason") != "not_planned"
        )
        items_by_milestone[milestone_number] = tuple(
            _parse_issue(issue) for issue in roadmap_issues
        )

    return items_by_milestone


def load_roadmap(
    token: str | None = None,
    session: requests.Session | None = None,
) -> Roadmap:
    issue_summaries = load_issue_summaries(session=session)
    client = GitHubClient(token=token, session=session)
    milestones = client.get_paginated(
        f"/repos/{REPOSITORY}/milestones",
        params={"state": "all", "per_page": 100},
    )
    roadmap_milestones = [
        milestone
        for milestone in milestones
        if milestone.get("state") != "closed" and _is_roadmap_milestone(milestone)
    ]
    issues_by_milestone = {
        int(milestone["number"]): client.get_paginated(
            f"/repos/{REPOSITORY}/issues",
            params={
                "state": "all",
                "milestone": int(milestone["number"]),
                "per_page": 100,
            },
        )
        for milestone in roadmap_milestones
    }
    pull_requests = client.get_paginated(
        "/search/issues",
        params={
            "q": (f'repo:{REPOSITORY} is:pr is:open draft:false label:"{SPEC_LABEL}"'),
            "per_page": 100,
        },
        collection_key="items",
    )
    return build_roadmap(
        milestones,
        issues_by_milestone,
        pull_requests,
        issue_summaries,
    )
