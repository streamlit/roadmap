import unittest

from github_roadmap import (
    GitHubAPIError,
    GitHubClient,
    build_roadmap,
    ellipsize_title,
    load_issue_summaries,
    load_past_release_items,
    load_roadmap,
    parse_issue_summaries_csv,
)


class FakeResponse:
    def __init__(self, payload, *, next_url=None, ok=True, text=""):
        self._payload = payload
        self.ok = ok
        self.text = text
        self.links = {"next": {"url": next_url}} if next_url else {}
        self.headers = {}
        self.status_code = 200

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class GitHubClientTests(unittest.TestCase):
    def test_get_paginated_follows_next_link_and_authenticates(self):
        session = FakeSession(
            [
                FakeResponse([{"number": 1}], next_url="https://api.github.com/next"),
                FakeResponse([{"number": 2}]),
            ]
        )

        results = GitHubClient(token="test-token", session=session).get_paginated(
            "/items", params={"per_page": 100}
        )

        self.assertEqual(results, [{"number": 1}, {"number": 2}])
        self.assertEqual(session.calls[0][1]["params"], {"per_page": 100})
        self.assertIsNone(session.calls[1][1]["params"])
        self.assertEqual(
            session.calls[0][1]["headers"]["Authorization"], "Bearer test-token"
        )

    def test_get_paginated_rejects_an_external_next_link(self):
        session = FakeSession(
            [FakeResponse([{"number": 1}], next_url="https://example.com/next")]
        )

        with self.assertRaisesRegex(GitHubAPIError, "unexpected pagination URL"):
            GitHubClient(token="test-token", session=session).get_paginated("/items")

        self.assertEqual(len(session.calls), 1)

    def test_get_paginated_reads_a_named_collection(self):
        session = FakeSession([FakeResponse({"items": [{"number": 1}]})])

        results = GitHubClient(session=session).get_paginated(
            "/search/issues",
            params={"q": "is:pr"},
            collection_key="items",
        )

        self.assertEqual(results, [{"number": 1}])


class BuildRoadmapTests(unittest.TestCase):
    def test_loads_and_filters_past_release_items(self):
        session = FakeSession(
            [
                FakeResponse(
                    [
                        {
                            "number": 101,
                            "title": "Completed feature",
                            "html_url": "https://github.com/issues/101",
                            "state": "closed",
                            "state_reason": "completed",
                        },
                        {
                            "number": 102,
                            "title": "Cancelled feature",
                            "html_url": "https://github.com/issues/102",
                            "state": "closed",
                            "state_reason": "not_planned",
                        },
                        {
                            "number": 103,
                            "title": "Pull request",
                            "html_url": "https://github.com/pull/103",
                            "state": "closed",
                            "pull_request": {},
                        },
                    ]
                )
            ]
        )

        items = load_past_release_items((4,), "test-token", session)

        self.assertEqual([item.number for item in items[4]], [101])
        self.assertTrue(items[4][0].is_closed)
        self.assertEqual(session.calls[0][1]["params"]["milestone"], 4)
        self.assertEqual(
            session.calls[0][1]["headers"]["Authorization"],
            "Bearer test-token",
        )

    def test_loads_past_releases_without_fetching_their_issues(self):
        session = FakeSession(
            [
                FakeResponse(None, text="number,summary\n"),
                FakeResponse(
                    [
                        {
                            "number": 1,
                            "title": "1.64",
                            "html_url": "https://github.com/milestone/1",
                            "due_on": "2026-09-11T00:00:00Z",
                            "state": "open",
                        },
                        {
                            "number": 2,
                            "title": "1.63",
                            "html_url": "https://github.com/milestone/2",
                            "due_on": "2026-08-28T00:00:00Z",
                            "state": "closed",
                        },
                    ]
                ),
                FakeResponse([]),
                FakeResponse({"items": []}),
            ]
        )

        roadmap = load_roadmap("test-token", session)

        self.assertEqual([release.title for release in roadmap.releases], ["1.64"])
        self.assertEqual(
            [release.title for release in roadmap.past_releases],
            ["1.63"],
        )
        self.assertEqual(session.calls[1][1]["params"]["state"], "all")
        issue_calls = [
            call
            for call in session.calls
            if call[0].endswith("/repos/streamlit/streamlit/issues")
        ]
        self.assertEqual(len(issue_calls), 1)
        self.assertEqual(issue_calls[0][1]["params"]["milestone"], 1)

    def test_ellipsizes_long_titles_at_75_characters(self):
        exact_title = "a" * 75
        long_title = "a" * 76

        self.assertEqual(ellipsize_title(exact_title), exact_title)
        self.assertEqual(ellipsize_title(long_title), f"{'a' * 74}…")

    def test_ellipsized_title_keeps_inline_code_balanced(self):
        title = f"A long title with `{'x' * 80}` and more text"

        shortened = ellipsize_title(title)

        self.assertTrue(shortened.endswith("`…"))
        self.assertEqual(shortened.count("`") % 2, 0)

    def test_loads_summaries_without_sending_api_credentials(self):
        session = FakeSession(
            [
                FakeResponse(
                    None,
                    text="number,summary\n101,A generated summary.\n",
                )
            ]
        )

        summaries = load_issue_summaries(session)

        self.assertEqual(summaries, {101: "A generated summary."})
        self.assertEqual(
            session.calls[0][1]["headers"],
            {"User-Agent": "streamlit-roadmap"},
        )

    def test_missing_summary_csv_does_not_block_the_roadmap(self):
        session = FakeSession([FakeResponse(None, ok=False)])

        self.assertEqual(load_issue_summaries(session), {})

    def test_parses_non_empty_generated_issue_summaries(self):
        summaries = parse_issue_summaries_csv(
            "number,title,summary\n"
            '101,"Feature, with comma","A generated summary with `code`."\n'
            '102,"Missing summary",""\n'
            'not-a-number,"Invalid issue","Ignored"\n'
        )

        self.assertEqual(summaries, {101: "A generated summary with `code`."})

    def test_builds_releases_planned_projects_and_specs(self):
        milestones = [
            {
                "number": 9,
                "title": "Planned",
                "html_url": "https://github.com/milestone/9",
                "due_on": None,
            },
            {
                "number": 6,
                "title": "1.64",
                "html_url": "https://github.com/milestone/6",
                "due_on": "2026-09-11T00:00:00Z",
            },
            {
                "number": 5,
                "title": "1.63",
                "html_url": "https://github.com/milestone/5",
                "due_on": "2026-08-28T00:00:00Z",
            },
            {
                "number": 10,
                "title": "Internal triage",
                "html_url": "https://github.com/milestone/10",
                "due_on": None,
            },
            {
                "number": 4,
                "title": "1.62",
                "html_url": "https://github.com/milestone/4",
                "due_on": "2026-08-18T00:00:00Z",
                "state": "closed",
            },
        ]
        issues = {
            5: [
                {
                    "number": 101,
                    "title": "[Coming soon] Open feature",
                    "html_url": "https://github.com/issues/101",
                    "state": "open",
                    "body": "### Summary\n\nA concise feature summary.",
                    "labels": [{"name": "feature:st.widget"}],
                },
                {
                    "number": 102,
                    "title": "Completed feature",
                    "html_url": "https://github.com/issues/102",
                    "state": "closed",
                    "state_reason": "completed",
                },
                {
                    "number": 103,
                    "title": "Cancelled feature",
                    "html_url": "https://github.com/issues/103",
                    "state": "closed",
                    "state_reason": "not_planned",
                },
                {
                    "number": 104,
                    "title": "Implementation pull request",
                    "html_url": "https://github.com/pull/104",
                    "state": "open",
                    "pull_request": {},
                },
            ],
            6: [],
            9: [
                {
                    "number": 201,
                    "title": "Planned project",
                    "html_url": "https://github.com/issues/201",
                    "state": "open",
                    "body": "### Summary\n\nA fallback issue-body summary.",
                }
            ],
        }
        pull_requests = [
            {
                "number": 301,
                "title": "[spec] Older proposal",
                "html_url": "https://github.com/pull/301",
                "draft": False,
                "updated_at": "2026-08-01T00:00:00Z",
                "labels": [{"name": "change:spec"}],
            },
            {
                "number": 302,
                "title": "[SPEC] [Coming Soon] Newer proposal",
                "html_url": "https://github.com/pull/302",
                "draft": False,
                "updated_at": "2026-08-02T00:00:00Z",
                "labels": [{"name": "CHANGE:SPEC"}],
                "body": "## Describe your changes\n\nA concise spec summary.",
            },
            {
                "number": 303,
                "title": "[spec] Draft proposal",
                "html_url": "https://github.com/pull/303",
                "draft": True,
                "updated_at": "2026-08-03T00:00:00Z",
                "labels": [{"name": "change:spec"}],
            },
            {
                "number": 304,
                "title": "Regular pull request",
                "html_url": "https://github.com/pull/304",
                "draft": False,
                "updated_at": "2026-08-04T00:00:00Z",
                "labels": [{"name": "change:feature"}],
            },
        ]

        roadmap = build_roadmap(
            milestones,
            issues,
            pull_requests,
            {101: "A generated CSV summary."},
        )

        self.assertEqual(
            [release.title for release in roadmap.releases], ["1.63", "1.64"]
        )
        self.assertEqual([release.title for release in roadmap.past_releases], ["1.62"])
        self.assertEqual(roadmap.past_releases[0].number, 4)
        self.assertEqual(
            [item.number for item in roadmap.releases[0].items], [101, 102]
        )
        self.assertTrue(roadmap.releases[0].items[1].is_closed)
        self.assertEqual(roadmap.releases[0].items[0].title, "Open feature")
        self.assertEqual(
            roadmap.releases[0].items[0].description, "A generated CSV summary."
        )
        self.assertEqual(roadmap.releases[0].items[0].labels, ("feature:st.widget",))
        self.assertIsNotNone(roadmap.planned)
        self.assertEqual([item.number for item in roadmap.planned.items], [201])
        self.assertIsNone(roadmap.planned.items[0].description)
        self.assertEqual([item.number for item in roadmap.specs], [302, 301])
        self.assertEqual(roadmap.specs[0].title, "Newer proposal")
        self.assertIsNone(roadmap.specs[0].description)


if __name__ == "__main__":
    unittest.main()
