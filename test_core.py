import unittest

from core import compare, flows_from_rows, presets, recommendation


class FlexSaveCoreTests(unittest.TestCase):
    def test_main_example_reproduces_stated_decision(self):
        scenario = presets()["Ví dụ chính: thù lao đến chậm"]
        result = recommendation(scenario, 1_500_000, 900_000, 2_000_000)
        self.assertEqual(result["expected_min"], 2_600_000)
        self.assertEqual(result["stress_min"], 1_400_000)
        self.assertEqual(result["saving"], 0)
        self.assertEqual(result["preexisting_shortfall"], 100_000)

    def test_adverse_case_is_visible_in_policy_comparison(self):
        scenario = presets()["Ví dụ chính: thù lao đến chậm"]
        _, _, metrics = compare(scenario, 1_500_000, 900_000, 2_000_000, True)
        self.assertEqual(metrics["FlexSave dự báo 30 ngày"]["saved"], 0)
        self.assertEqual(metrics["Tích lũy cố định"]["saved"], 900_000)
        self.assertGreater(
            metrics["Tích lũy cố định"]["worst_shortfall"],
            metrics["FlexSave dự báo 30 ngày"]["worst_shortfall"],
        )

    def test_cap_and_goal_limit_safe_recommendation(self):
        scenario = presets()["Ví dụ chính: thù lao đến chậm"]
        # A lower reserve makes both futures safe; the remaining goal binds.
        result = recommendation(scenario, 1_000_000, 900_000, 250_000)
        self.assertEqual(result["saving"], 250_000)

    def test_edited_cashflow_rows_change_the_recommendation(self):
        base = presets()["Ví dụ chính: thù lao đến chậm"]
        rows = [
            {"day": 1, "kind": "Chi", "label": "Tiền nhà", "amount": 2_400_000},
            {"day": 10, "kind": "Chi", "label": "Hóa đơn", "amount": 1_200_000},
            {"day": 4, "kind": "Thu", "label": "Thù lao đã đổi ngày", "amount": 3_000_000},
        ]
        income, expense = flows_from_rows(rows)
        changed = type(base)(base.name, base.opening, income, income, expense,
                             expense, base.history_net_per_day, base.description)
        self.assertEqual(recommendation(changed, 1_500_000, 900_000, 2_000_000)["saving"], 900_000)

    def test_invalid_edited_row_is_rejected(self):
        with self.assertRaises(ValueError):
            flows_from_rows([{"day": 31, "kind": "Thu", "label": "Sai ngày", "amount": 100_000}])


if __name__ == "__main__":
    unittest.main()
