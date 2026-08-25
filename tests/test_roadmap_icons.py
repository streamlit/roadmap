import unittest

from roadmap_icons import LABEL_ICON_MAP, icon_for_issue


class RoadmapIconTests(unittest.TestCase):
    def test_maps_every_current_area_and_feature_label(self):
        self.assertEqual(len(LABEL_ICON_MAP), 148)
        self.assertTrue(
            all(label.startswith(("area:", "feature:")) for label in LABEL_ICON_MAP)
        )

    def test_specific_feature_takes_precedence_over_area(self):
        icon = icon_for_issue(("area:layout", "feature:st.dataframe"))

        self.assertEqual(icon, ":material/table_chart:")

    def test_area_is_used_when_no_feature_label_is_present(self):
        icon = icon_for_issue(("type:enhancement", "area:accessibility"))

        self.assertEqual(icon, ":material/accessibility_new:")

    def test_bug_and_feature_request_fallbacks(self):
        self.assertEqual(icon_for_issue(("type:bug",)), ":material/bug_report:")
        self.assertEqual(icon_for_issue(("type:regression",)), ":material/bug_report:")
        self.assertEqual(
            icon_for_issue(("type:enhancement",)),
            ":material/lightbulb:",
        )


if __name__ == "__main__":
    unittest.main()
