import copy
import hashlib
import os
import unittest
from dataclasses import replace
from unittest.mock import patch

import pandas as pd

from module1_calculator import Module1Calculator
from module1_historical_analysis import Module1HistoricalAnalysis
from module1_sensitivity_diagnostics import Module1SensitivityDiagnostics


SMOOTHING_SUMMARY_COLUMNS = [
    "total_rows",
    "valid_rows",
    "credit_spread_change_score_both_valid_count",
    "credit_spread_change_score_both_valid_changed_count",
    "credit_spread_change_score_both_valid_changed_ratio",
    "credit_spread_change_score_one_sided_missing_count",
    "credit_spread_change_score_one_sided_missing_ratio",
    "credit_spread_change_score_aligned_count",
    "credit_spread_change_score_aligned_changed_count",
    "credit_spread_change_score_aligned_changed_ratio",
    "credit_spread_change_score_mean_abs_diff",
    "credit_spread_state_score_both_valid_count",
    "credit_spread_state_score_both_valid_changed_count",
    "credit_spread_state_score_both_valid_changed_ratio",
    "credit_spread_state_score_one_sided_missing_count",
    "credit_spread_state_score_one_sided_missing_ratio",
    "credit_spread_state_score_aligned_count",
    "credit_spread_state_score_aligned_changed_count",
    "credit_spread_state_score_aligned_changed_ratio",
    "credit_spread_state_score_mean_abs_diff",
    "credit_stance_score_both_valid_count",
    "credit_stance_score_both_valid_changed_count",
    "credit_stance_score_both_valid_changed_ratio",
    "credit_stance_score_one_sided_missing_count",
    "credit_stance_score_one_sided_missing_ratio",
    "credit_stance_score_aligned_count",
    "credit_stance_score_aligned_changed_count",
    "credit_stance_score_aligned_changed_ratio",
    "credit_stance_score_mean_abs_diff",
    "raw_credit_score_change_count",
    "smoothed_credit_score_change_count",
    "credit_score_change_reduction_count",
    "credit_score_change_reduction_ratio",
    "raw_credit_one_day_spike_count",
    "smoothed_credit_one_day_spike_count",
    "credit_one_day_spike_reduction_count",
    "credit_one_day_spike_reduction_ratio",
]

SMOOTHING_DETAIL_COLUMNS = [
    "baa10y_change",
    "baa10y",
    "baa10y_change_prepared_for_credit_spread_change",
    "baa10y_level_prepared_for_credit_spread_state",
    "raw_credit_spread_change_score",
    "raw_credit_spread_state_score",
    "smoothed_credit_spread_change_score",
    "smoothed_credit_spread_state_score",
    "raw_credit_stance_score",
    "smoothed_credit_stance_score",
    "credit_stance_score_diff",
    "raw_credit_stance",
    "raw_credit_stance_strength",
    "smoothed_credit_stance",
    "smoothed_credit_stance_strength",
]

THRESHOLD_SUMMARY_COLUMNS = [
    "min_abs_value",
    "total_rows",
    "valid_rows",
    "rows_with_front_end_below_threshold",
    "rows_with_long_end_below_threshold",
    "rows_with_either_side_below_threshold",
    "rows_with_both_sides_below_threshold",
    "curve_move_driver_score_changed_count_vs_no_threshold",
    "curve_move_driver_score_changed_ratio_vs_no_threshold",
    "mixed_or_unclear_count_before_threshold",
    "mixed_or_unclear_count_after_threshold",
    "mixed_or_unclear_count_change",
    "curve_positioning_score_changed_count_due_to_threshold",
    "curve_positioning_score_changed_ratio_due_to_threshold",
]

THRESHOLD_DETAIL_COLUMNS = [
    "dgs2_change",
    "dgs10_change",
    "dgs2_change_prepared_for_curve_move_driver",
    "dgs10_change_prepared_for_curve_move_driver",
    "dgs2_change_filtered_for_curve_move_driver",
    "dgs10_change_filtered_for_curve_move_driver",
    "curve_move_driver_score_without_threshold",
    "curve_move_driver_score_with_threshold",
    "curve_move_driver_bucket_without_threshold",
    "curve_move_driver_bucket_with_threshold",
    "curve_positioning_score_without_threshold",
    "curve_positioning_score_with_threshold",
    "curve_positioning_score_diff_due_to_threshold",
    "curve_move_driver_score_changed_by_threshold",
    "curve_positioning_score_changed_by_threshold",
]

CURVE_SUMMARY_COLUMNS = [
    "case_id",
    "total_rows",
    "valid_rows",
    "mean_raw_score",
    "mean_stabilized_score",
    "mean_score_diff",
    "mean_abs_score_diff",
    "max_abs_score_diff",
    "changed_score_count",
    "changed_score_ratio",
    "changed_direction_count",
    "changed_direction_ratio",
    "changed_strength_count",
    "changed_strength_ratio",
    "raw_score_change_count",
    "stabilized_score_change_count",
    "score_change_reduction_count",
    "score_change_reduction_ratio",
    "one_day_spike_count_raw",
    "one_day_spike_count_stabilized",
    "one_day_spike_reduction_count",
    "one_day_spike_reduction_ratio",
    "bucket_change_count_raw",
    "bucket_change_count_stabilized",
    "dominant_raw_direction",
    "dominant_stabilized_direction",
    "dominant_raw_strength",
    "dominant_stabilized_strength",
]

CURVE_WINDOW_COLUMNS = [
    "case_id",
    "window_id",
    "start",
    "end",
    "obs_count",
    "mean_raw_score",
    "mean_stabilized_score",
    "mean_score_diff",
    "mean_abs_score_diff",
    "changed_score_count",
    "changed_score_ratio",
    "raw_score_change_count",
    "stabilized_score_change_count",
    "one_day_spike_count_raw",
    "one_day_spike_count_stabilized",
    "dominant_raw_rule_case",
    "dominant_stabilized_rule_case",
    "dominant_raw_direction",
    "dominant_stabilized_direction",
    "dominant_raw_strength",
    "dominant_stabilized_strength",
]

CURVE_DETAIL_COLUMNS = [
    "curve_change_score",
    "curve_state_score",
    "curve_move_driver_score",
    "raw_curve_change_bucket",
    "stabilized_curve_change_bucket",
    "raw_curve_state_bucket",
    "stabilized_curve_state_bucket",
    "raw_yield_move_driver_bucket",
    "stabilized_yield_move_driver_bucket",
    "raw_curve_positioning_rule_case",
    "stabilized_curve_positioning_rule_case",
    "raw_curve_positioning_score",
    "stabilized_curve_positioning_score",
    "score_diff",
    "raw_curve_positioning",
    "stabilized_curve_positioning",
    "raw_curve_positioning_strength",
    "stabilized_curve_positioning_strength",
    "score_changed",
    "direction_changed",
    "strength_changed",
    "raw_score_change_flag",
    "stabilized_score_change_flag",
    "raw_one_day_spike_flag",
    "stabilized_one_day_spike_flag",
]

CREDIT_OUTPUT_COLUMNS = {
    "summary": [
        "case_id",
        "change_persistence",
        "state_persistence",
        "covid_first_credit_negative_date",
        "covid_delay_days_vs_base",
        "recovery_mean_score",
        "recovery_negative_score_days",
        "tight_2021q2_mean_score",
        "tight_2021q2_tight_state_ratio",
        "late_2022_max_abs_daily_score_move",
        "late_2022_large_move_gt_0_5_count",
        "late_2022_large_move_gt_1_0_count",
        "full_changed_pair_count",
        "full_changed_pair_ratio",
    ],
    "window_metrics": [
        "case_id",
        "window_id",
        "obs_count",
        "credit_stance_score_mean",
        "credit_stance_score_min",
        "credit_stance_score_max",
        "credit_stance_score_std",
        "max_abs_daily_score_move",
        "baa10y_mean",
        "baa10y_min",
        "baa10y_max",
        "dominant_credit_state_pair",
        "dominant_credit_state_pair_ratio",
        "changed_pair_count",
        "changed_pair_ratio",
        "changed_change_state_count",
        "changed_spread_state_count",
    ],
    "shock_detection": [
        "case_id",
        "first_credit_negative_date",
        "delay_days_vs_base",
    ],
    "recovery_behavior": [
        "case_id",
        "dominant_credit_state_pair",
        "dominant_credit_state_pair_ratio",
        "credit_stance_score_mean",
        "negative_score_days",
    ],
    "tight_spread_behavior": [
        "case_id",
        "tight_state_count",
        "tight_state_ratio",
        "tight_pair_count",
        "tight_pair_ratio",
        "credit_stance_score_mean",
    ],
    "late_volatility": [
        "case_id",
        "max_abs_daily_score_move",
        "large_move_gt_0_5_count",
        "large_move_gt_1_0_count",
    ],
    "full_period_stabilization": [
        "case_id",
        "changed_pair_count",
        "changed_change_state_count",
        "changed_spread_state_count",
        "changed_pair_ratio",
        "non_missing_obs_count",
    ],
}

CREDIT_DIAGNOSTIC_COLUMNS = [
    "credit_spread_change_score",
    "credit_spread_state_score",
    "credit_spread_change_state_raw",
    "credit_spread_change_state",
    "credit_spread_state_category_raw",
    "credit_spread_state_category",
    "state_stabilization_changed_change_state",
    "state_stabilization_changed_spread_state",
    "state_stabilization_changed_pair",
    "credit_state_pair",
    "base_rule_score",
    "credit_spread_change_intensity",
    "credit_spread_state_intensity",
    "rule_adjustment",
    "credit_stance_score",
    "credit_stance",
    "credit_stance_strength",
    "baa10y_change",
    "baa10y",
    "baa10y_change_prepared_for_credit_spread_change",
    "baa10y_level_prepared_for_credit_spread_state",
]


def frame_fingerprint(frame: pd.DataFrame) -> str:
    """Fingerprint public values, index, columns, column order, and dtypes."""
    digest = hashlib.sha256()
    digest.update(
        pd.util.hash_pandas_object(
            frame,
            index=True,
            categorize=True,
        ).values.tobytes()
    )
    digest.update(repr(list(frame.columns)).encode())
    digest.update(repr([str(dtype) for dtype in frame.dtypes]).encode())
    return digest.hexdigest()


def assert_nested_outputs_equal(test_case, first, second):
    test_case.assertEqual(list(first), list(second))
    for key in first:
        if isinstance(first[key], pd.DataFrame):
            pd.testing.assert_frame_equal(first[key], second[key])
            continue
        test_case.assertEqual(list(first[key]), list(second[key]))
        for case_id in first[key]:
            pd.testing.assert_frame_equal(
                first[key][case_id],
                second[key][case_id],
            )


class HorizonCasesOutputTests(unittest.TestCase):
    def test_explicit_cases_generate_ids_and_preserve_values_order_and_dtypes(self):
        cases = [
            {"rates": 126, "credit": 63},
            {"rates": 90, "credit": None},
        ]
        original_cases = copy.deepcopy(cases)

        actual = Module1SensitivityDiagnostics._build_horizon_cases_df(
            horizon_cases=cases,
        )

        expected = pd.DataFrame(
            {
                "case_id": ["case_000", "case_001"],
                "rates": [126, 90],
                "credit": [63.0, float("nan")],
            }
        )
        pd.testing.assert_frame_equal(actual, expected)
        self.assertEqual(cases, original_cases)

    def test_supplied_ids_are_normalized_without_reordering_columns_or_input(self):
        cases = pd.DataFrame(
            {
                "rates": [126, 90, 63, 42],
                "case_id": ["kept", None, "  ", 42],
                "credit": [63, 42, 21, 10],
            },
            index=[9, 7, 5, 3],
        )
        original_cases = cases.copy(deep=True)

        actual = Module1SensitivityDiagnostics._build_horizon_cases_df(
            horizon_cases=cases,
        )

        self.assertEqual(list(actual.columns), ["rates", "case_id", "credit"])
        self.assertEqual(
            actual["case_id"].tolist(),
            ["kept", "case_001", "case_002", "42"],
        )
        self.assertTrue(actual.index.equals(pd.RangeIndex(4)))
        self.assertEqual(str(actual["case_id"].dtype), "str")
        pd.testing.assert_frame_equal(cases, original_cases)

    def test_grid_is_a_declaration_order_cartesian_product_and_respects_max_cases(self):
        grid = {
            "rates": [126, 90],
            "credit": (63, 42),
            "inflation": 21,
        }
        original_grid = copy.deepcopy(grid)

        actual = Module1SensitivityDiagnostics._build_horizon_cases_df(
            horizon_grid=grid,
            max_cases=4,
        )

        expected = pd.DataFrame(
            {
                "case_id": [
                    "case_000",
                    "case_001",
                    "case_002",
                    "case_003",
                ],
                "rates": [126, 126, 90, 90],
                "credit": [63, 42, 63, 42],
                "inflation": [21, 21, 21, 21],
            }
        )
        pd.testing.assert_frame_equal(actual, expected)
        self.assertEqual(grid, original_grid)

        with self.assertRaisesRegex(
            ValueError,
            "Generated 4 horizon cases, which exceeds max_cases=3",
        ):
            Module1SensitivityDiagnostics._build_horizon_cases_df(
                horizon_grid=grid,
                max_cases=3,
            )

    def test_invalid_empty_exclusive_types_and_duplicate_ids_are_characterized(self):
        with self.assertRaisesRegex(ValueError, "Provide exactly one"):
            Module1SensitivityDiagnostics._build_horizon_cases_df()
        with self.assertRaisesRegex(ValueError, "Provide exactly one"):
            Module1SensitivityDiagnostics._build_horizon_cases_df(
                horizon_cases=[{"rates": 126}],
                horizon_grid={"rates": [126]},
            )
        with self.assertRaisesRegex(ValueError, "horizon_cases must be"):
            Module1SensitivityDiagnostics._build_horizon_cases_df(
                horizon_cases={"rates": 126},
            )
        with self.assertRaisesRegex(ValueError, "horizon_grid must be a dict"):
            Module1SensitivityDiagnostics._build_horizon_cases_df(
                horizon_grid=[126, 90],
            )

        for kwargs in (
            {"horizon_cases": []},
            {"horizon_cases": pd.DataFrame()},
            {"horizon_grid": {}},
            {"horizon_grid": {"rates": []}},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, "No horizon cases"):
                    Module1SensitivityDiagnostics._build_horizon_cases_df(
                        **kwargs,
                    )

        for cases in (
            [{"case_id": "same"}, {"case_id": "same"}],
            [{"case_id": "case_001"}, {"case_id": None}],
        ):
            with self.subTest(cases=cases):
                with self.assertRaisesRegex(ValueError, "must be unique"):
                    Module1SensitivityDiagnostics._build_horizon_cases_df(
                        horizon_cases=cases,
                    )

    def test_compare_horizon_cases_normalization_path_is_deterministic_and_local(self):
        cases = [
            {"case_id": "baseline", "rates": 126},
            {"case_id": "modified", "rates": 90},
        ]
        original_cases = copy.deepcopy(cases)

        with patch(
            "module1_sensitivity_diagnostics.Module1Calculator",
            side_effect=AssertionError("calculator initialization attempted"),
        ):
            first = Module1SensitivityDiagnostics.compare_horizon_cases(
                horizon_cases=cases,
                output=" HORIZON_CASES ",
            )
            second = Module1SensitivityDiagnostics.compare_horizon_cases(
                horizon_cases=cases,
                output="horizon_cases",
            )

        expected = pd.DataFrame(cases)
        pd.testing.assert_frame_equal(first, expected)
        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(cases, original_cases)


class SensitivityPublicOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._fred_key = patch.dict(os.environ, {"FRED_API_KEY": "test"})
        cls._fred_key.start()
        calculator = Module1Calculator()
        calculator.run_module1_pipeline()
        full_result = calculator.to_module1_result()
        frame_names = (
            "data",
            "features",
            "scores",
            "labels",
            "stance_scores",
            "exposure_stance",
        )
        cls.template_result = replace(
            full_result,
            **{
                name: getattr(full_result, name)
                .loc["2019-01-01":"2023-12-31"]
                .copy(deep=True)
                for name in frame_names
            },
        )
        historical = Module1HistoricalAnalysis(cls.template_result)
        cls.historical_context = historical.load_historical_context(
            "data/historical_context.yaml"
        )

    @classmethod
    def tearDownClass(cls):
        cls._fred_key.stop()

    def setUp(self):
        self.result = copy.deepcopy(self.template_result)
        self.sensitivity = Module1SensitivityDiagnostics(
            self.result,
            historical_context=copy.deepcopy(self.historical_context),
        )

    def snapshot_result(self):
        return {
            "data": self.result.data.copy(deep=True),
            "features": self.result.features.copy(deep=True),
            "scores": self.result.scores.copy(deep=True),
            "labels": self.result.labels.copy(deep=True),
            "stance_scores": self.result.stance_scores.copy(deep=True),
            "exposure_stance": self.result.exposure_stance.copy(deep=True),
            "module1_config": copy.deepcopy(self.result.module1_config),
        }

    def assert_result_unchanged(self, snapshot):
        for name in (
            "data",
            "features",
            "scores",
            "labels",
            "stance_scores",
            "exposure_stance",
        ):
            pd.testing.assert_frame_equal(getattr(self.result, name), snapshot[name])
        self.assertEqual(
            self.result.module1_config,
            snapshot["module1_config"],
        )

    def test_compare_smoothing_effect_public_contract_and_missing_behavior(self):
        windows = {
            "focus": ("2020-03-02", "2020-03-06"),
            "empty": ("1900-01-01", "1900-01-02"),
        }
        original_windows = copy.deepcopy(windows)
        original_result = self.snapshot_result()

        with_detail = self.sensitivity.compare_smoothing_effect(
            "credit",
            windows=windows,
            include_detail=True,
        )
        without_detail = self.sensitivity.compare_smoothing_effect(
            "credit",
            windows=windows,
            include_detail=False,
        )

        self.assertEqual(
            list(with_detail),
            ["summary", "window_summary", "detail"],
        )
        self.assertEqual(list(without_detail), ["summary", "window_summary"])
        pd.testing.assert_frame_equal(
            with_detail["summary"],
            without_detail["summary"],
        )
        pd.testing.assert_frame_equal(
            with_detail["window_summary"],
            without_detail["window_summary"],
        )
        self.assertEqual(
            list(with_detail["summary"].columns),
            SMOOTHING_SUMMARY_COLUMNS,
        )
        self.assertEqual(
            list(with_detail["window_summary"].columns),
            SMOOTHING_SUMMARY_COLUMNS + ["window_id", "start", "end"],
        )
        self.assertEqual(
            list(with_detail["detail"].columns),
            SMOOTHING_DETAIL_COLUMNS,
        )
        self.assertEqual(
            with_detail["window_summary"]["window_id"].tolist(),
            ["focus", "empty"],
        )
        empty = with_detail["window_summary"].iloc[1]
        self.assertEqual(empty["total_rows"], 0)
        self.assertEqual(empty["valid_rows"], 0)
        self.assertTrue(
            pd.isna(empty["credit_stance_score_aligned_changed_ratio"])
        )
        self.assertTrue(pd.isna(empty["credit_stance_score_mean_abs_diff"]))
        self.assertEqual(
            str(
                with_detail["window_summary"][
                    "credit_stance_score_aligned_changed_ratio"
                ].dtype
            ),
            "object",
        )
        self.assertTrue(
            with_detail["detail"].index.equals(self.result.features.index)
        )
        self.assertTrue(
            with_detail["detail"].iloc[0][
                [
                    "baa10y_change",
                    "raw_credit_spread_change_score",
                    "raw_credit_stance_score",
                ]
            ].isna().all()
        )
        self.assertEqual(
            frame_fingerprint(with_detail["summary"]),
            "8a90a2572dbf066eb3f1d01c8b80e2426c62a181050d16c162f57ad135faf1d5",
        )
        self.assertEqual(
            frame_fingerprint(with_detail["window_summary"]),
            "690b8d510c1c2a7abfe0dbd7d07185719f5864f6cfece335c8b731d09f183afa",
        )
        self.assertEqual(
            frame_fingerprint(with_detail["detail"]),
            "728271beb289e32097402ca323f81dc212e20ae707abcce41308baef99360cbe",
        )
        self.assertEqual(windows, original_windows)
        self.assert_result_unchanged(original_result)

    def test_compare_smoothing_effect_defaults_and_not_applicable_outputs(self):
        default_result = self.sensitivity.compare_smoothing_effect(
            "credit",
            include_detail=False,
        )
        self.assertEqual(
            default_result["window_summary"]["window_id"].tolist(),
            [
                "dotcom_bust_2000",
                "global_financial_crisis_2008",
                "covid_shock_2020",
                "inflation_reopening_2021",
                "taper_tantrum_review",
                "fed_hiking_2022",
                "disinflation_rally_2023",
                "credit_spread_window_2024",
                "custom_period_20200101_20220101",
                "full_history",
            ],
        )
        self.assertTrue(
            pd.isna(default_result["window_summary"].iloc[-1]["start"])
        )
        self.assertTrue(
            pd.isna(default_result["window_summary"].iloc[-1]["end"])
        )
        self.assertEqual(
            frame_fingerprint(default_result["window_summary"]),
            "b7cb82946f2247f6585872512e81570e945b107e6cbc8c1578e12ac15d3b298a",
        )

        duration = self.sensitivity.compare_smoothing_effect("duration")
        self.assertEqual(list(duration), ["summary", "window_summary"])
        self.assertEqual(
            duration["summary"].iloc[0].to_dict(),
            {
                "target": "duration",
                "smoothing_layer": "score",
                "status": "not_implemented",
                "reason": "Score-level smoothing comparison is not implemented.",
            },
        )
        self.assertEqual(
            list(duration["window_summary"].columns),
            ["target", "smoothing_layer", "status", "reason"],
        )
        self.assertTrue(duration["window_summary"].empty)

        unsupported = self.sensitivity.compare_smoothing_effect("unsupported")
        self.assertEqual(
            unsupported["summary"][["target", "smoothing_layer", "status"]]
            .iloc[0]
            .tolist(),
            ["unsupported", "auto", "not_applicable"],
        )

    def test_curve_move_driver_threshold_public_contract_is_repeatable(self):
        original_result = self.snapshot_result()

        first = self.sensitivity.compare_curve_move_driver_threshold_effect(
            include_detail=True
        )
        second = self.sensitivity.compare_curve_move_driver_threshold_effect(
            include_detail=True
        )
        summary_only = (
            self.sensitivity.compare_curve_move_driver_threshold_effect(
                include_detail=False
            )
        )

        self.assertEqual(list(first), ["summary", "detail"])
        self.assertEqual(list(summary_only), ["summary"])
        assert_nested_outputs_equal(self, first, second)
        pd.testing.assert_frame_equal(first["summary"], summary_only["summary"])
        self.assertEqual(
            list(first["summary"].columns),
            THRESHOLD_SUMMARY_COLUMNS,
        )
        self.assertEqual(list(first["detail"].columns), THRESHOLD_DETAIL_COLUMNS)
        self.assertTrue(
            first["detail"].index.equals(self.result.features.index)
        )
        self.assertEqual(
            [str(dtype) for dtype in first["detail"].dtypes[-2:]],
            ["bool", "bool"],
        )
        self.assertEqual(
            [str(dtype) for dtype in first["detail"].dtypes[8:10]],
            ["str", "str"],
        )
        first_row = first["detail"].iloc[0]
        self.assertTrue(first_row.iloc[:-2].isna().all())
        self.assertFalse(first_row.iloc[-2])
        self.assertFalse(first_row.iloc[-1])
        self.assertEqual(
            first["summary"].iloc[0][
                [
                    "min_abs_value",
                    "total_rows",
                    "valid_rows",
                    "curve_move_driver_score_changed_count_vs_no_threshold",
                    "curve_positioning_score_changed_count_due_to_threshold",
                ]
            ].tolist(),
            [0.05, 1320.0, 1154.0, 199.0, 150.0],
        )
        self.assertEqual(
            frame_fingerprint(first["summary"]),
            "6c0c1df4072b17766915938702d1f12ffa99a2a36b36d2272bcc81d7b803fa49",
        )
        self.assertEqual(
            frame_fingerprint(first["detail"]),
            "6051f2b2062fe165b538f4a9e96b59cd403a08de4d69cac6647ee439111f12c2",
        )
        self.assert_result_unchanged(original_result)

    def test_curve_stabilization_custom_cases_public_contract(self):
        neutral = {
            "curve_change": {
                "hysteresis_buffer": 0.0,
                "min_state_persistence": 1,
            },
            "curve_state": {
                "hysteresis_buffer": 0.0,
                "min_state_persistence": 1,
            },
            "curve_move_driver": {
                "hysteresis_buffer": 0.0,
                "min_state_persistence": 1,
            },
        }
        modified = {
            "curve_change": {
                "hysteresis_buffer": 0.0,
                "min_state_persistence": 3,
            },
            "curve_state": {
                "hysteresis_buffer": 0.0,
                "min_state_persistence": 3,
            },
            "curve_move_driver": {
                "hysteresis_buffer": 0.0,
                "min_state_persistence": 2,
            },
        }
        cases = {
            "neutral_a": copy.deepcopy(neutral),
            "neutral_b": copy.deepcopy(neutral),
            "modified": copy.deepcopy(modified),
        }
        windows = {
            "focus": ("2020-03-02", "2020-03-06"),
            "empty": ("1900-01-01", "1900-01-02"),
        }
        original_cases = copy.deepcopy(cases)
        original_windows = copy.deepcopy(windows)
        original_result = self.snapshot_result()

        with_diagnostics = (
            self.sensitivity.compare_curve_positioning_stabilization_cases(
                cases=cases,
                windows=windows,
                include_diagnostics=True,
            )
        )
        without_diagnostics = (
            self.sensitivity.compare_curve_positioning_stabilization_cases(
                cases=cases,
                windows=windows,
                include_diagnostics=False,
            )
        )

        self.assertEqual(
            list(with_diagnostics),
            [
                "summary",
                "window_summary",
                "detail_by_case",
                "bucket_transition_summary",
                "score_distribution",
                "diagnostics_by_case",
            ],
        )
        self.assertEqual(
            list(without_diagnostics),
            [
                "summary",
                "window_summary",
                "detail_by_case",
                "bucket_transition_summary",
                "score_distribution",
            ],
        )
        assert_nested_outputs_equal(
            self,
            without_diagnostics,
            {
                key: with_diagnostics[key]
                for key in without_diagnostics
            },
        )
        self.assertEqual(
            list(with_diagnostics["summary"].columns),
            CURVE_SUMMARY_COLUMNS,
        )
        self.assertEqual(
            list(with_diagnostics["window_summary"].columns),
            CURVE_WINDOW_COLUMNS,
        )
        self.assertEqual(
            list(with_diagnostics["bucket_transition_summary"].columns),
            [
                "case_id",
                "bucket_type",
                "raw_change_count",
                "stabilized_change_count",
                "change_reduction_count",
                "change_reduction_ratio",
            ],
        )
        self.assertEqual(
            list(with_diagnostics["score_distribution"].columns),
            ["case_id", "score_type", "score", "count", "ratio"],
        )
        self.assertEqual(
            list(with_diagnostics["detail_by_case"]),
            ["neutral_a", "neutral_b", "modified"],
        )
        self.assertEqual(
            list(with_diagnostics["diagnostics_by_case"]),
            ["neutral_a", "neutral_b", "modified"],
        )
        for detail in with_diagnostics["detail_by_case"].values():
            self.assertEqual(list(detail.columns), CURVE_DETAIL_COLUMNS)
            self.assertTrue(detail.index.equals(self.result.scores.index))
            self.assertEqual(
                [str(dtype) for dtype in detail.dtypes[-7:]],
                ["bool"] * 7,
            )
        pd.testing.assert_frame_equal(
            with_diagnostics["detail_by_case"]["neutral_a"],
            with_diagnostics["detail_by_case"]["neutral_b"],
        )
        self.assertFalse(
            with_diagnostics["detail_by_case"]["neutral_a"].equals(
                with_diagnostics["detail_by_case"]["modified"]
            )
        )
        summary = with_diagnostics["summary"].set_index("case_id")
        pd.testing.assert_series_equal(
            summary.loc["neutral_a"],
            summary.loc["neutral_b"],
            check_names=False,
        )
        self.assertEqual(summary.loc["neutral_a", "changed_score_count"], 0)
        self.assertGreater(summary.loc["modified", "changed_score_count"], 0)
        self.assertEqual(
            with_diagnostics["window_summary"][
                ["case_id", "window_id"]
            ].values.tolist(),
            [
                ["neutral_a", "focus"],
                ["neutral_a", "empty"],
                ["neutral_b", "focus"],
                ["neutral_b", "empty"],
                ["modified", "focus"],
                ["modified", "empty"],
            ],
        )
        empty_rows = with_diagnostics["window_summary"].query(
            "window_id == 'empty'"
        )
        self.assertTrue((empty_rows["obs_count"] == 0).all())
        self.assertTrue(empty_rows["mean_raw_score"].isna().all())
        self.assertTrue(empty_rows["changed_score_ratio"].isna().all())
        self.assertEqual(
            frame_fingerprint(with_diagnostics["summary"]),
            "6636fdd12ebbb87018072edaadff54d8116433ae4652f7afb833d3a485f6136b",
        )
        self.assertEqual(
            frame_fingerprint(with_diagnostics["window_summary"]),
            "538f53fe21d8d43f3b396c7c1634836ed0c20c6d5f8023ca9655608db7c68882",
        )
        self.assertEqual(
            frame_fingerprint(
                with_diagnostics["bucket_transition_summary"]
            ),
            "6a810e2bcea86e06fe732855e0d39e14ed80036eefbb55dcdc8c66f455c26103",
        )
        self.assertEqual(
            frame_fingerprint(with_diagnostics["score_distribution"]),
            "2306c216294debc3bd94b70b6c099a1973db81079e71bf6a3b44917bc99889c7",
        )
        self.assertEqual(cases, original_cases)
        self.assertEqual(windows, original_windows)
        self.assert_result_unchanged(original_result)

    def test_curve_stabilization_default_cases_and_windows(self):
        result = self.sensitivity.compare_curve_positioning_stabilization_cases(
            include_diagnostics=False
        )

        self.assertEqual(
            result["summary"]["case_id"].tolist(),
            [
                "neutral_base",
                "persistence_3",
                "hysteresis_005",
                "hysteresis_005_persistence_3",
                "hysteresis_010_persistence_3",
            ],
        )
        expected_windows = [
            "taper_tantrum_review",
            "fed_hiking_2022",
            "covid_shock_2020",
            "full_history",
        ]
        for case_id in result["summary"]["case_id"]:
            self.assertEqual(
                result["window_summary"].loc[
                    result["window_summary"]["case_id"] == case_id,
                    "window_id",
                ].tolist(),
                expected_windows,
            )
        self.assertEqual(
            frame_fingerprint(result["summary"]),
            "34fd2c9c2dc55697ce195e0da4f51e6aed98c42a0eda62cf7af717870c18d1f2",
        )
        self.assertEqual(
            frame_fingerprint(result["window_summary"]),
            "0f3b55ca6b819748e4a5cee6fbe69ed72005f833a9ddf4d2f8b820e4ccd5d4cf",
        )

    def test_credit_persistence_custom_cases_public_contract(self):
        cases = {
            "base_p1_p1": {
                "credit_spread_change": 1,
                "credit_spread_state": 1,
            },
            "same": {
                "credit_spread_change": 1,
                "credit_spread_state": 1,
            },
            "modified": {
                "credit_spread_change": 2,
                "credit_spread_state": 2,
            },
        }
        windows = {
            "covid_initial_shock": ("2020-03-01", "2020-03-31"),
            "post_shock_recovery": ("2020-06-01", "2020-06-30"),
            "tight_spread_2021q2": ("2021-04-01", "2021-06-30"),
            "late_2022_volatility": ("1900-01-01", "1900-01-02"),
        }
        original_cases = copy.deepcopy(cases)
        original_windows = copy.deepcopy(windows)
        original_result = self.snapshot_result()
        original_local_config = copy.deepcopy(self.sensitivity.module1_config)
        original_local_exposure_config = copy.deepcopy(
            self.sensitivity.exposure_stance_config
        )
        original_local_frames = {
            name: getattr(self.sensitivity, name).copy(deep=True)
            for name in (
                "data",
                "features",
                "scores",
                "labels",
                "stance_scores",
                "exposure_stance",
            )
        }
        original_local_horizons = copy.deepcopy(self.sensitivity.horizons)

        with patch.object(
            Module1Calculator,
            "calculate_exposure_stance_outputs",
            wraps=Module1Calculator.calculate_exposure_stance_outputs,
        ) as calculate_exposure_stance_outputs:
            with_diagnostics = (
                self.sensitivity.compare_credit_stance_persistence_cases(
                    cases=cases,
                    windows=windows,
                    include_diagnostics=True,
                )
            )
            without_diagnostics = (
                self.sensitivity.compare_credit_stance_persistence_cases(
                    cases=cases,
                    windows=windows,
                    include_diagnostics=False,
                )
            )
            repeated_with_diagnostics = (
                self.sensitivity.compare_credit_stance_persistence_cases(
                    cases=cases,
                    windows=windows,
                    include_diagnostics=True,
                )
            )

        expected_settings = list(cases.values()) * 3
        self.assertEqual(
            calculate_exposure_stance_outputs.call_count,
            len(expected_settings),
        )
        for call, settings in zip(
            calculate_exposure_stance_outputs.call_args_list,
            expected_settings,
        ):
            scenario_config = call.args[2]["exposure_stances"]["credit"]
            nested_stabilization = scenario_config["rule_mapped"][
                "state_stabilization"
            ]
            self.assertIs(
                nested_stabilization,
                scenario_config["state_stabilization"],
            )
            self.assertEqual(
                nested_stabilization,
                {
                    "credit_spread_change": {
                        "hysteresis_buffer": 0.05,
                        "min_state_persistence": settings[
                            "credit_spread_change"
                        ],
                    },
                    "credit_spread_state": {
                        "hysteresis_buffer": 0.05,
                        "min_state_persistence": settings[
                            "credit_spread_state"
                        ],
                    },
                },
            )

        self.assertEqual(
            list(with_diagnostics),
            [
                "summary",
                "window_metrics",
                "shock_detection",
                "recovery_behavior",
                "tight_spread_behavior",
                "late_volatility",
                "full_period_stabilization",
                "diagnostics",
            ],
        )
        self.assertEqual(
            list(without_diagnostics),
            [
                "summary",
                "window_metrics",
                "shock_detection",
                "recovery_behavior",
                "tight_spread_behavior",
                "late_volatility",
                "full_period_stabilization",
            ],
        )
        assert_nested_outputs_equal(
            self,
            without_diagnostics,
            {
                key: with_diagnostics[key]
                for key in without_diagnostics
            },
        )
        assert_nested_outputs_equal(
            self,
            with_diagnostics,
            repeated_with_diagnostics,
        )
        for output_name, columns in CREDIT_OUTPUT_COLUMNS.items():
            self.assertEqual(
                list(with_diagnostics[output_name].columns),
                columns,
            )
        self.assertEqual(
            list(with_diagnostics["diagnostics"]),
            ["base_p1_p1", "same", "modified"],
        )
        for diagnostic in with_diagnostics["diagnostics"].values():
            self.assertEqual(
                list(diagnostic.columns),
                CREDIT_DIAGNOSTIC_COLUMNS,
            )
            self.assertTrue(diagnostic.index.equals(self.result.scores.index))
            self.assertEqual(
                [
                    str(diagnostic[column].dtype)
                    for column in (
                        "state_stabilization_changed_change_state",
                        "state_stabilization_changed_spread_state",
                        "state_stabilization_changed_pair",
                    )
                ],
                ["bool", "bool", "bool"],
            )
        pd.testing.assert_frame_equal(
            with_diagnostics["diagnostics"]["base_p1_p1"],
            with_diagnostics["diagnostics"]["same"],
        )
        base_diagnostic = with_diagnostics["diagnostics"]["base_p1_p1"]
        modified_diagnostic = with_diagnostics["diagnostics"]["modified"]
        mismatch_counts = {}
        for column in (
            "credit_spread_change_state",
            "credit_spread_state_category",
            "credit_state_pair",
            "credit_stance_score",
        ):
            matching = base_diagnostic[column].eq(
                modified_diagnostic[column]
            ) | (
                base_diagnostic[column].isna()
                & modified_diagnostic[column].isna()
            )
            mismatch_counts[column] = int((~matching).sum())
        self.assertEqual(
            mismatch_counts,
            {
                "credit_spread_change_state": 23,
                "credit_spread_state_category": 9,
                "credit_state_pair": 32,
                "credit_stance_score": 32,
            },
        )
        self.assertEqual(
            with_diagnostics["summary"]["case_id"].tolist(),
            ["base_p1_p1", "same", "modified"],
        )
        summary = with_diagnostics["summary"].set_index("case_id")
        pd.testing.assert_series_equal(
            summary.loc["base_p1_p1"],
            summary.loc["same"],
            check_names=False,
        )
        self.assertEqual(
            summary.loc[
                ["base_p1_p1", "same", "modified"],
                ["change_persistence", "state_persistence"],
            ].values.tolist(),
            [[1, 1], [1, 1], [2, 2]],
        )
        self.assertEqual(
            summary.loc[
                ["base_p1_p1", "modified"],
                [
                    "covid_delay_days_vs_base",
                    "full_changed_pair_count",
                ],
            ].values.tolist(),
            [[0, 128], [1, 158]],
        )
        self.assertEqual(
            with_diagnostics["window_metrics"][
                ["case_id", "window_id"]
            ].values.tolist(),
            [
                [case_id, window_id]
                for case_id in cases
                for window_id in windows
            ],
        )
        empty_metrics = with_diagnostics["window_metrics"].query(
            "window_id == 'late_2022_volatility'"
        )
        self.assertTrue((empty_metrics["obs_count"] == 0).all())
        self.assertTrue(empty_metrics["credit_stance_score_mean"].isna().all())
        self.assertTrue(empty_metrics["changed_pair_ratio"].isna().all())
        self.assertTrue(
            with_diagnostics["late_volatility"][
                "max_abs_daily_score_move"
            ].isna().all()
        )
        self.assertTrue(
            pd.api.types.is_datetime64_any_dtype(
                with_diagnostics["summary"][
                    "covid_first_credit_negative_date"
                ]
            )
        )
        expected_fingerprints = {
            "summary": "1081ec24710571774725aa35fcf53416e77631e7b8012bb245af15cbf82abaaa",
            "window_metrics": "4d77b2392ad5573d9a31f6009f11d232c3596cd93e63346f2316545b3ff54dc6",
            "shock_detection": "727ee1031ba3d477ccd778d90280dcfb12e793d10992cc27c8306b6111973b70",
            "recovery_behavior": "a2ba7f1dbaeb57f2776b16049af31a6bdeb66a82c3e432bb95fa6ece2e7487b5",
            "tight_spread_behavior": "e5625570c53b5325a70c1a342b7efba1fa8cdabc06be6721d33976feec565cb4",
            "late_volatility": "682e91629da18f5b6acf1a2a984fce320fb283a1dfaf24089bebcef722c3b38f",
            "full_period_stabilization": "1871ce51ddae34e766171c0dcf5ef1b0bfeb33a6d42a2e7df6423ecf280325bf",
        }
        for output_name, expected_fingerprint in expected_fingerprints.items():
            self.assertEqual(
                frame_fingerprint(with_diagnostics[output_name]),
                expected_fingerprint,
            )
        expected_diagnostic_fingerprints = {
            "base_p1_p1": "23a26f1d66d02b228f4d1f140f30c0d98cdbc01bb5bcde961334da34077a4b10",
            "same": "23a26f1d66d02b228f4d1f140f30c0d98cdbc01bb5bcde961334da34077a4b10",
            "modified": "d60682f6b8f8b672b23aaf49fc98629ddd31534231a2a5fbd1c952ee3c77c000",
        }
        for case_id, expected_fingerprint in (
            expected_diagnostic_fingerprints.items()
        ):
            self.assertEqual(
                frame_fingerprint(with_diagnostics["diagnostics"][case_id]),
                expected_fingerprint,
            )
        self.assertEqual(cases, original_cases)
        self.assertEqual(windows, original_windows)
        self.assertEqual(
            self.sensitivity.module1_config,
            original_local_config,
        )
        self.assertEqual(
            self.sensitivity.exposure_stance_config,
            original_local_exposure_config,
        )
        for name, original_frame in original_local_frames.items():
            pd.testing.assert_frame_equal(
                getattr(self.sensitivity, name),
                original_frame,
            )
        self.assertEqual(self.sensitivity.horizons, original_local_horizons)
        self.assert_result_unchanged(original_result)

    def test_credit_persistence_default_cases_and_windows(self):
        result = self.sensitivity.compare_credit_stance_persistence_cases(
            include_diagnostics=False
        )

        self.assertEqual(
            result["summary"]["case_id"].tolist(),
            [
                "base_p1_p1",
                "case_a_change2_state1",
                "case_b_change1_state2",
                "case_c_change2_state2",
            ],
        )
        expected_windows = [
            "covid_initial_shock",
            "post_shock_recovery",
            "tight_spread_2021q2",
            "late_2022_volatility",
        ]
        for case_id in result["summary"]["case_id"]:
            self.assertEqual(
                result["window_metrics"].loc[
                    result["window_metrics"]["case_id"] == case_id,
                    "window_id",
                ].tolist(),
                expected_windows,
            )
        self.assertEqual(
            frame_fingerprint(result["summary"]),
            "d12343dbe7302b3b3b7824fed9e2770eb7b1acec3f9d19eba0d81f76c58f985f",
        )
        self.assertEqual(
            frame_fingerprint(result["window_metrics"]),
            "e5034e9a15c36d3ffaba28f0d567e9e570d08ae665ffc329bed71a48fd81b8f9",
        )


if __name__ == "__main__":
    unittest.main()
