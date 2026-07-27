import copy
import hashlib
import os
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

import pandas as pd

from module1_calculator import Module1Calculator, Module1Result
from module1_diagnostics import (
    DiagnosticInputSpec,
    Module1Diagnostics,
    RuleMappedDiagnosticSpec,
)
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

SMOOTHING_PAIR_METRIC_SUFFIXES = [
    "both_valid_count",
    "both_valid_changed_count",
    "both_valid_changed_ratio",
    "one_sided_missing_count",
    "one_sided_missing_ratio",
    "aligned_count",
    "aligned_changed_count",
    "aligned_changed_ratio",
    "mean_abs_diff",
]

CURVE_SMOOTHING_SUMMARY_COLUMNS = [
    "total_rows",
    "valid_rows",
    *[
        f"{prefix}_{suffix}"
        for prefix in (
            "curve_change_score",
            "curve_state_score",
            "curve_move_driver_score",
            "curve_positioning_score",
        )
        for suffix in SMOOTHING_PAIR_METRIC_SUFFIXES
    ],
    "raw_curve_score_change_count",
    "smoothed_curve_score_change_count",
    "curve_score_change_reduction_count",
    "curve_score_change_reduction_ratio",
    "raw_curve_one_day_spike_count",
    "smoothed_curve_one_day_spike_count",
    "curve_one_day_spike_reduction_count",
    "curve_one_day_spike_reduction_ratio",
]

CURVE_SMOOTHING_DETAIL_COLUMNS = [
    "curve_10y2y_change",
    "curve_10y2y_level",
    "curve_10y2y_change_prepared_for_curve_change",
    "curve_10y2y_level_prepared_for_curve_state",
    "dgs2_change_prepared_for_curve_move_driver",
    "dgs10_change_prepared_for_curve_move_driver",
    "dgs2_change_filtered_for_curve_move_driver",
    "dgs10_change_filtered_for_curve_move_driver",
    "raw_curve_change_score",
    "raw_curve_state_score",
    "raw_curve_move_driver_score",
    "smoothed_curve_change_score",
    "smoothed_curve_state_score",
    "smoothed_curve_move_driver_score",
    "raw_curve_positioning_score",
    "smoothed_curve_positioning_score",
    "score_diff",
    "raw_curve_positioning",
    "raw_curve_positioning_strength",
    "smoothed_curve_positioning",
    "smoothed_curve_positioning_strength",
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


class HorizonCaseCalculatorFake(Module1Calculator):
    instances = []
    configured_defaults = {
        "rates": 126,
        "credit": 63,
        "inflation": 21,
    }

    def __init__(
        self,
        api_key_env="FRED_API_KEY",
        series_config_path="data/fred_series_config.csv",
        module1_config_path="data/module1_config.yaml",
        data_path="data/raw_data_19980101_20260508.csv",
        horizons=None,
    ):
        self.constructor_arguments = {
            "api_key_env": api_key_env,
            "series_config_path": series_config_path,
            "module1_config_path": module1_config_path,
            "data_path": data_path,
        }
        self.constructor_horizons = copy.deepcopy(horizons)
        self.default_horizons = copy.deepcopy(self.configured_defaults)
        self.horizon_overrides = copy.deepcopy(horizons)
        self._horizons = copy.deepcopy(
            self.default_horizons if horizons is None else horizons
        )
        self.validation_calls = []
        self.pipeline_call_count = 0
        self.result_call_count = 0
        self.__class__.instances.append(self)

    @property
    def horizons(self):
        return self._horizons

    def validate_horizons(self, horizons=None, base_horizons=None):
        self.validation_calls.append(
            (
                copy.deepcopy(horizons),
                copy.deepcopy(base_horizons),
            )
        )
        return super().validate_horizons(
            horizons,
            base_horizons=base_horizons,
        )

    def run_module1_pipeline(self):
        self.pipeline_call_count += 1

    def to_module1_result(self):
        self.result_call_count += 1
        return Module1Result(
            data=None,
            features=None,
            scores=None,
            labels=None,
            stance_scores=None,
            exposure_stance=None,
            module1_config={"horizons": copy.deepcopy(self.default_horizons)},
            horizons=copy.deepcopy(self.horizons),
            default_horizons=copy.deepcopy(self.default_horizons),
            horizon_overrides=copy.deepcopy(self.horizon_overrides),
            module1_config_validation=None,
        )


class HorizonCaseHistoricalFake:
    instances = []

    def __init__(self, result):
        self.result = result
        self.context_paths = []
        self.review_calls = []
        self.__class__.instances.append(self)

    def load_historical_context(self, path):
        self.context_paths.append(path)
        return {"path": path}

    def review_historical_cases(self, **kwargs):
        self.review_calls.append(copy.deepcopy(kwargs))
        horizons = self.result.horizons
        if kwargs["output"] == "report":
            return pd.DataFrame(
                {
                    "metric": ["effective_total", "rates_metric"],
                    "value": [
                        sum(horizons.values()),
                        horizons["rates"],
                    ],
                }
            )
        return pd.DataFrame(
            {
                "row_id": ["first", "second"],
                "observed": [
                    horizons["rates"],
                    horizons["rates"] + 1,
                ],
            }
        )


class HorizonCasesOutputTests(unittest.TestCase):
    def setUp(self):
        HorizonCaseCalculatorFake.instances = []
        HorizonCaseHistoricalFake.instances = []

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

    def test_compare_horizon_cases_executes_complete_constructor_horizons(self):
        cases = pd.DataFrame(
            {
                "case_id": ["rates_only", "credit_only"],
                "rates": [100.0, float("nan")],
                "credit": [float("nan"), 45.0],
            },
            index=[8, 4],
        )
        base_horizons = {
            "credit": 70,
            "rates": 140,
            "inflation": 30,
        }
        original_cases = cases.copy(deep=True)
        original_base_horizons = copy.deepcopy(base_horizons)
        call_arguments = {
            "api_key_env": "CUSTOM_FRED_KEY",
            "series_config_path": "custom/series.csv",
            "module1_config_path": "custom/module1.yaml",
            "data_path": "custom/raw.csv",
            "historical_context_path": "custom/context.yaml",
            "target": "duration_preference",
            "context_id": "custom_context",
            "level": "component",
            "only_use_for_validation": False,
            "include_low_relevance": True,
            "min_obs": 11,
            "plausible_threshold": 0.8,
            "mixed_threshold": 0.3,
            "output": "summary",
        }

        with (
            patch(
                "module1_sensitivity_diagnostics.Module1Calculator",
                HorizonCaseCalculatorFake,
            ),
            patch(
                "module1_sensitivity_diagnostics.Module1HistoricalAnalysis",
                HorizonCaseHistoricalFake,
            ),
        ):
            first = Module1SensitivityDiagnostics.compare_horizon_cases(
                horizon_cases=cases,
                base_horizons=base_horizons,
                **call_arguments,
            )
            second = Module1SensitivityDiagnostics.compare_horizon_cases(
                horizon_cases=cases,
                base_horizons=base_horizons,
                **call_arguments,
            )

        expected = pd.DataFrame(
            {
                "case_id": ["rates_only", "credit_only"],
                "rates": [100, 140],
                "credit": [70, 45],
                "inflation": [30, 30],
                "effective_total": [200, 215],
                "rates_metric": [100, 140],
            }
        )
        pd.testing.assert_frame_equal(first, expected)
        pd.testing.assert_frame_equal(second, expected)
        pd.testing.assert_frame_equal(cases, original_cases)
        self.assertEqual(base_horizons, original_base_horizons)

        calculators = HorizonCaseCalculatorFake.instances
        self.assertEqual(len(calculators), 6)
        expected_case_horizons = [
            {"credit": 70, "rates": 100, "inflation": 30},
            {"credit": 45, "rates": 140, "inflation": 30},
        ]
        for invocation_start in (0, 3):
            base_calc = calculators[invocation_start]
            case_calculators = calculators[
                invocation_start + 1:invocation_start + 3
            ]
            self.assertIsNone(base_calc.constructor_horizons)
            self.assertEqual(
                base_calc.validation_calls,
                [
                    (
                        original_base_horizons,
                        HorizonCaseCalculatorFake.configured_defaults,
                    ),
                    (
                        {"rates": 100},
                        original_base_horizons,
                    ),
                    (
                        {"credit": 45},
                        original_base_horizons,
                    ),
                ],
            )
            self.assertEqual(base_calc.pipeline_call_count, 0)
            self.assertEqual(base_calc.result_call_count, 0)
            self.assertEqual(
                [
                    calc.constructor_horizons
                    for calc in case_calculators
                ],
                expected_case_horizons,
            )
            self.assertEqual(
                [calc.pipeline_call_count for calc in case_calculators],
                [1, 1],
            )
            self.assertEqual(
                [calc.result_call_count for calc in case_calculators],
                [1, 1],
            )
            for calc, effective_horizons in zip(
                case_calculators,
                expected_case_horizons,
            ):
                self.assertEqual(calc.horizons, effective_horizons)
                self.assertEqual(calc.horizon_overrides, effective_horizons)
                self.assertEqual(
                    calc.default_horizons,
                    HorizonCaseCalculatorFake.configured_defaults,
                )
                self.assertEqual(
                    calc.constructor_arguments,
                    {
                        key: call_arguments[key]
                        for key in (
                            "api_key_env",
                            "series_config_path",
                            "module1_config_path",
                            "data_path",
                        )
                    },
                )

        historical_instances = HorizonCaseHistoricalFake.instances
        self.assertEqual(len(historical_instances), 4)
        expected_review_call = {
            "target": "duration_preference",
            "context_id": "custom_context",
            "level": "component",
            "only_use_for_validation": False,
            "include_low_relevance": True,
            "min_obs": 11,
            "plausible_threshold": 0.8,
            "mixed_threshold": 0.3,
            "output": "report",
        }
        for historical, expected_horizons in zip(
            historical_instances,
            expected_case_horizons * 2,
        ):
            self.assertEqual(
                historical.context_paths,
                ["custom/context.yaml"],
            )
            self.assertEqual(historical.review_calls, [expected_review_call])
            self.assertEqual(historical.result.horizons, expected_horizons)
            self.assertEqual(
                historical.result.horizon_overrides,
                expected_horizons,
            )
            self.assertEqual(
                historical.result.default_horizons,
                HorizonCaseCalculatorFake.configured_defaults,
            )

    def test_compare_horizon_cases_non_summary_metadata_and_row_order(self):
        grid = {
            "rates": [90, 80],
            "credit": [None],
        }
        base_horizons = {
            "rates": 150,
            "credit": 75,
            "inflation": 25,
        }
        original_grid = copy.deepcopy(grid)
        original_base_horizons = copy.deepcopy(base_horizons)

        with (
            patch(
                "module1_sensitivity_diagnostics.Module1Calculator",
                HorizonCaseCalculatorFake,
            ),
            patch(
                "module1_sensitivity_diagnostics.Module1HistoricalAnalysis",
                HorizonCaseHistoricalFake,
            ),
        ):
            actual = Module1SensitivityDiagnostics.compare_horizon_cases(
                horizon_grid=grid,
                base_horizons=base_horizons,
                historical_context_path="context/path.yaml",
                output="detail",
            )

        expected = pd.DataFrame(
            {
                "case_id": [
                    "case_000",
                    "case_000",
                    "case_001",
                    "case_001",
                ],
                "rates": [90, 90, 80, 80],
                "credit": [75, 75, 75, 75],
                "inflation": [25, 25, 25, 25],
                "row_id": ["first", "second", "first", "second"],
                "observed": [90, 91, 80, 81],
            }
        )
        pd.testing.assert_frame_equal(actual, expected)
        self.assertEqual(grid, original_grid)
        self.assertEqual(base_horizons, original_base_horizons)
        self.assertEqual(len(HorizonCaseCalculatorFake.instances), 3)
        self.assertEqual(
            [
                calc.constructor_horizons
                for calc in HorizonCaseCalculatorFake.instances[1:]
            ],
            [
                {"rates": 90, "credit": 75, "inflation": 25},
                {"rates": 80, "credit": 75, "inflation": 25},
            ],
        )
        self.assertEqual(
            [
                historical.context_paths
                for historical in HorizonCaseHistoricalFake.instances
            ],
            [["context/path.yaml"], ["context/path.yaml"]],
        )
        expected_review_call = {
            "target": None,
            "context_id": None,
            "level": None,
            "only_use_for_validation": True,
            "include_low_relevance": False,
            "min_obs": 20,
            "plausible_threshold": 0.70,
            "mixed_threshold": 0.45,
            "output": "detail",
        }
        self.assertEqual(
            [
                historical.review_calls
                for historical in HorizonCaseHistoricalFake.instances
            ],
            [[expected_review_call], [expected_review_call]],
        )


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

    def test_incomplete_results_use_result_specific_sensitivity_errors(self):
        explicit_windows = {"full": (None, None)}
        checks = [
            *[
                (
                    f"smoothing_{field}",
                    field,
                    lambda sensitivity: sensitivity.compare_smoothing_effect(
                        "credit",
                        windows=explicit_windows,
                    ),
                    rf"Module1Result\.{field} is required for .*input smoothing",
                )
                for field in ("features", "scores", "exposure_stance")
            ],
            (
                "smoothing_module1_config",
                "module1_config",
                lambda sensitivity: sensitivity.compare_smoothing_effect(
                    "credit",
                    windows=explicit_windows,
                ),
                r"Module1Result\.module1_config is required for smoothing diagnostics",
            ),
            *[
                (
                    f"curve_threshold_{field}",
                    field,
                    lambda sensitivity: (
                        sensitivity.compare_curve_move_driver_threshold_effect()
                    ),
                    rf"Module1Result\.{field} is required for comparing "
                    r"curve_move_driver threshold",
                )
                for field in (
                    "features",
                    "scores",
                    "exposure_stance",
                    "module1_config",
                )
            ],
            *[
                (
                    f"curve_stabilization_{field}",
                    field,
                    lambda sensitivity: (
                        sensitivity.compare_curve_positioning_stabilization_cases()
                    ),
                    rf"Module1Result\.{field} is required for curve .*"
                    r"stabilization comparison",
                )
                for field in ("scores", "exposure_stance", "module1_config")
            ],
            *[
                (
                    f"credit_persistence_{field}",
                    field,
                    lambda sensitivity: (
                        sensitivity.compare_credit_stance_persistence_cases()
                    ),
                    rf"Module1Result\.{field} is required for "
                    r"compare_credit_stance_persistence_cases",
                )
                for field in (
                    "module1_config",
                    "features",
                    "scores",
                    "labels",
                    "exposure_stance",
                    "stance_scores",
                )
            ],
        ]

        for name, field, workflow, pattern in checks:
            with self.subTest(name=name):
                incomplete = replace(self.result, **{field: None})
                sensitivity = Module1SensitivityDiagnostics(
                    incomplete,
                    historical_context=copy.deepcopy(self.historical_context),
                )
                with self.assertRaisesRegex(ValueError, pattern):
                    workflow(sensitivity)

    def test_diagnostics_owns_ordered_prepared_input_specs(self):
        original_result = self.snapshot_result()
        diagnostics = Module1Diagnostics(self.result)

        expected_credit = [
            (
                "credit_spread_change",
                "baa10y_change",
                "prepared",
                "baa10y_change_prepared_for_credit_spread_change",
                None,
            ),
            (
                "credit_spread_state",
                "baa10y_level",
                "prepared",
                "baa10y_level_prepared_for_credit_spread_state",
                None,
            ),
        ]
        expected_curve = [
            (
                "curve_change",
                "curve_10y2y_change",
                "prepared",
                "curve_10y2y_change_prepared_for_curve_change",
                None,
            ),
            (
                "curve_state",
                "curve_10y2y_level",
                "prepared",
                "curve_10y2y_level_prepared_for_curve_state",
                None,
            ),
            (
                "curve_move_driver",
                "dgs2_change",
                "prepared",
                "dgs2_change_prepared_for_curve_move_driver",
                "front_end",
            ),
            (
                "curve_move_driver",
                "dgs2_change",
                "filtered",
                "dgs2_change_filtered_for_curve_move_driver",
                "front_end",
            ),
            (
                "curve_move_driver",
                "dgs10_change",
                "prepared",
                "dgs10_change_prepared_for_curve_move_driver",
                "long_end",
            ),
            (
                "curve_move_driver",
                "dgs10_change",
                "filtered",
                "dgs10_change_filtered_for_curve_move_driver",
                "long_end",
            ),
        ]

        def values(specs):
            self.assertTrue(
                all(isinstance(spec, DiagnosticInputSpec) for spec in specs)
            )
            return [
                (
                    spec.component,
                    spec.source,
                    spec.kind,
                    spec.output,
                    spec.role,
                )
                for spec in specs
            ]

        first_credit = diagnostics.diagnostic_input_specs("credit")
        first_curve = diagnostics.diagnostic_input_specs("curve_positioning")
        self.assertEqual(
            diagnostics.diagnostic_component_names("credit"),
            ("credit_spread_change", "credit_spread_state"),
        )
        self.assertEqual(
            diagnostics.diagnostic_component_names("curve_positioning"),
            ("curve_change", "curve_state", "curve_move_driver"),
        )
        self.assertEqual(values(first_credit), expected_credit)
        self.assertEqual(values(first_curve), expected_curve)
        self.assertEqual(
            values(
                diagnostics.diagnostic_input_specs(
                    "curve_positioning",
                    kinds=("filtered",),
                )
            ),
            [expected_curve[3], expected_curve[5]],
        )
        self.assertEqual(
            first_credit,
            diagnostics.diagnostic_input_specs("credit"),
        )
        self.assertEqual(
            first_curve,
            diagnostics.diagnostic_input_specs("curve_positioning"),
        )
        self.assert_result_unchanged(original_result)

    def test_diagnostics_owns_prepared_filtered_columns_and_missing_sources(self):
        original_result = self.snapshot_result()
        diagnostics = Module1Diagnostics(self.result)

        credit = diagnostics.prepared_filtered_input_columns("credit")
        curve = diagnostics.prepared_filtered_input_columns("curve_positioning")
        self.assertEqual(
            list(credit.columns),
            [
                "baa10y_change_prepared_for_credit_spread_change",
                "baa10y_level_prepared_for_credit_spread_state",
            ],
        )
        self.assertEqual(
            list(curve.columns),
            [
                "curve_10y2y_change_prepared_for_curve_change",
                "curve_10y2y_level_prepared_for_curve_state",
                "dgs2_change_prepared_for_curve_move_driver",
                "dgs10_change_prepared_for_curve_move_driver",
                "dgs2_change_filtered_for_curve_move_driver",
                "dgs10_change_filtered_for_curve_move_driver",
            ],
        )
        self.assertEqual([str(dtype) for dtype in credit.dtypes], ["float64"] * 2)
        self.assertEqual([str(dtype) for dtype in curve.dtypes], ["float64"] * 6)
        self.assertTrue(credit.index.equals(self.result.features.index))
        self.assertTrue(curve.index.equals(self.result.features.index))
        self.assertTrue(credit.iloc[0].isna().all())
        self.assertTrue(curve.iloc[0].isna().all())
        self.assertEqual(
            frame_fingerprint(credit),
            "a156caf6adfc9114cfdb60a0902547cabaeac54f78b1cef0b7eb706281c83f39",
        )
        self.assertEqual(
            frame_fingerprint(curve),
            "e393de6b5b5766708e290cb74d0ab31acb2140f09f4847a431e00f35c75c9e28",
        )
        pd.testing.assert_frame_equal(
            credit,
            diagnostics.prepared_filtered_input_columns("credit"),
        )
        pd.testing.assert_frame_equal(
            curve,
            diagnostics.prepared_filtered_input_columns("curve_positioning"),
        )

        missing_features = self.result.features.drop(columns=["dgs2_change"])
        missing_result = replace(self.result, features=missing_features)
        missing = Module1Diagnostics(
            missing_result
        ).prepared_filtered_input_columns("curve_positioning")
        self.assertEqual(
            list(missing.columns),
            [
                "curve_10y2y_change_prepared_for_curve_change",
                "curve_10y2y_level_prepared_for_curve_state",
                "dgs10_change_prepared_for_curve_move_driver",
                "dgs10_change_filtered_for_curve_move_driver",
            ],
        )
        self.assertEqual(
            frame_fingerprint(missing),
            "ae6a2a1dc076f1665e6f32b88c75557d24fe95f5069a567dcf075e84ba08d294",
        )
        pd.testing.assert_frame_equal(missing_result.features, missing_features)
        self.assert_result_unchanged(original_result)

    def test_diagnostics_owns_completed_context_rule_specs_and_traces(self):
        original_result = self.snapshot_result()
        diagnostics = self.sensitivity._diagnostics

        with patch.object(
            diagnostics,
            "get_target_context",
            wraps=diagnostics.get_target_context,
        ) as get_target_context:
            first_context = diagnostics.get_target_context(
                "credit",
                "stance",
                dependency_level="full",
            )
            second_context = diagnostics.get_target_context(
                "credit",
                "stance",
                dependency_level="full",
            )
            credit_trace = diagnostics.trace_stance_score(
                "credit",
                include_raw_input=True,
                include_labels=False,
            )
            curve_trace = diagnostics.trace_stance_score(
                "curve_positioning",
                include_raw_input=True,
                include_labels=False,
            )

        pd.testing.assert_frame_equal(first_context.data, second_context.data)
        self.assertEqual(first_context.resolution, second_context.resolution)
        self.assertEqual(
            first_context.returned_columns,
            second_context.returned_columns,
        )
        self.assertGreaterEqual(get_target_context.call_count, 4)

        credit_spec = diagnostics.rule_mapped_diagnostic_spec("credit")
        curve_spec = diagnostics.rule_mapped_diagnostic_spec(
            "curve_positioning"
        )
        self.assertIsInstance(credit_spec, RuleMappedDiagnosticSpec)
        self.assertIsInstance(curve_spec, RuleMappedDiagnosticSpec)
        self.assertEqual(
            credit_spec.score_input_cols,
            ("credit_spread_change_score", "credit_spread_state_score"),
        )
        self.assertEqual(
            curve_spec.component_names,
            ("curve_change", "curve_state", "yield_move_driver"),
        )
        self.assertEqual(
            credit_spec.rule_mapped_schema.rule_case_output_col,
            credit_spec.rule_case_col,
        )
        self.assertEqual(
            curve_spec.rule_mapped_schema.rule_case_output_col,
            curve_spec.rule_case_col,
        )
        with patch.object(
            diagnostics,
            "rule_mapped_diagnostic_spec",
            wraps=diagnostics.rule_mapped_diagnostic_spec,
        ) as rule_spec:
            smoothing = self.sensitivity.compare_smoothing_effect(
                "credit",
                windows={"focus": ("2020-03-02", "2020-03-06")},
                include_detail=False,
            )
        self.assertEqual(list(smoothing), ["summary", "window_summary"])
        self.assertGreaterEqual(rule_spec.call_count, 1)

        expected_credit_columns = (
            CREDIT_DIAGNOSTIC_COLUMNS[:17]
            + ["baa10y", "baa10y_change"]
            + CREDIT_DIAGNOSTIC_COLUMNS[19:]
        )
        self.assertEqual(list(credit_trace.columns), expected_credit_columns)
        self.assertEqual(
            list(curve_trace.columns),
            [
                "curve_change_score",
                "curve_state_score",
                "curve_move_driver_score",
                "curve_change_bucket_raw",
                "curve_change_bucket",
                "curve_state_bucket_raw",
                "curve_state_bucket",
                "yield_move_driver_bucket_raw",
                "yield_move_driver_bucket",
                "state_stabilization_changed_curve_change",
                "state_stabilization_changed_curve_state",
                "state_stabilization_changed_curve_move_driver",
                "state_stabilization_changed_any",
                "curve_positioning_rule_case",
                "curve_positioning_score",
                "curve_positioning",
                "curve_positioning_strength",
                "dgs10",
                "dgs2",
                "curve_10y2y_level",
                "curve_10y2y_change",
                "dgs2_change",
                "dgs10_change",
                "curve_10y2y_change_prepared_for_curve_change",
                "curve_10y2y_level_prepared_for_curve_state",
                "dgs2_change_prepared_for_curve_move_driver",
                "dgs10_change_prepared_for_curve_move_driver",
                "dgs2_change_filtered_for_curve_move_driver",
                "dgs10_change_filtered_for_curve_move_driver",
            ],
        )
        self.assertEqual(
            frame_fingerprint(credit_trace),
            "7c0a6901c3e8f15b439e32adf583902bdd23fad4d961df27cff843098a0b2378",
        )
        self.assertEqual(
            frame_fingerprint(curve_trace),
            "bcdfb4202caa5dfdce0c5b005597342cf4708d51ebcffa3a808c08fe4982a9bd",
        )
        pd.testing.assert_frame_equal(
            credit_trace,
            diagnostics.trace_stance_score(
                "credit",
                include_raw_input=True,
                include_labels=False,
            ),
        )
        pd.testing.assert_frame_equal(
            curve_trace,
            diagnostics.trace_stance_score(
                "curve_positioning",
                include_raw_input=True,
                include_labels=False,
            ),
        )

        self.assertEqual(
            RuleMappedDiagnosticSpec.__module__,
            "module1_diagnostics",
        )
        self.assert_result_unchanged(original_result)

    def test_sensitivity_consumes_diagnostics_owned_prepared_inputs(self):
        with (
            patch.object(
                self.sensitivity._diagnostics,
                "diagnostic_input_specs",
                wraps=self.sensitivity._diagnostics.diagnostic_input_specs,
            ) as input_specs,
            patch.object(
                self.sensitivity._diagnostics,
                "prepared_filtered_input_columns",
                wraps=(
                    self.sensitivity._diagnostics.prepared_filtered_input_columns
                ),
            ) as prepared_columns,
            patch.object(
                self.sensitivity._diagnostics,
                "rule_mapped_diagnostic_spec",
                wraps=(
                    self.sensitivity._diagnostics.rule_mapped_diagnostic_spec
                ),
            ) as rule_spec,
        ):
            result = (
                self.sensitivity.compare_curve_move_driver_threshold_effect(
                    include_detail=True
                )
            )

        self.assertGreaterEqual(input_specs.call_count, 1)
        prepared_columns.assert_called_once_with("curve_positioning")
        self.assertGreaterEqual(rule_spec.call_count, 1)

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

    def test_smoothing_auto_resolution_uses_configured_layers(self):
        original_result = self.snapshot_result()

        sole_score = Module1SensitivityDiagnostics(self.result)
        sole_score_config = sole_score.module1_config["components"][
            "credit_spread_change"
        ]["score"]
        sole_score_config["input_preparation"].pop("smoothing")
        sole_score_config["smoothing"] = "score_smoothing"
        sole_score_result = sole_score.compare_smoothing_effect("credit")
        self.assertEqual(
            sole_score_result["summary"].iloc[0].to_dict(),
            {
                "target": "credit",
                "smoothing_layer": "score",
                "status": "not_implemented",
                "reason": "Score-level smoothing comparison is not implemented.",
            },
        )

        ambiguous = Module1SensitivityDiagnostics(self.result)
        ambiguous.module1_config["components"]["credit_spread_change"]["score"][
            "smoothing"
        ] = "score_smoothing"
        with self.assertRaisesRegex(
            ValueError,
            (
                r"Automatic smoothing-layer resolution is ambiguous for target "
                r"'credit': configured layers are "
                r"\['input_preparation', 'score'\]\. "
                r"Pass smoothing_layer explicitly\."
            ),
        ):
            ambiguous.compare_smoothing_effect("credit")

        no_layer = Module1SensitivityDiagnostics(self.result)
        no_layer_score = no_layer.module1_config["components"][
            "credit_spread_change"
        ]["score"]
        no_layer_score["input_preparation"].pop("smoothing")
        no_layer_result = no_layer.compare_smoothing_effect("credit")
        self.assertEqual(
            no_layer_result["summary"].iloc[0].to_dict(),
            {
                "target": "credit",
                "smoothing_layer": "auto",
                "status": "not_applicable",
                "reason": "Target 'credit' does not use 'auto' smoothing.",
            },
        )

        duration = self.sensitivity.compare_smoothing_effect("duration")
        self.assertEqual(
            duration["summary"].iloc[0][
                ["target", "smoothing_layer", "status"]
            ].tolist(),
            ["duration", "score", "not_implemented"],
        )
        explicit_score = self.sensitivity.compare_smoothing_effect(
            "credit",
            smoothing_layer="score",
        )
        self.assertEqual(
            explicit_score["summary"].iloc[0].to_dict(),
            {
                "target": "credit",
                "smoothing_layer": "score",
                "status": "not_applicable",
                "reason": "Target 'credit' does not use 'score' smoothing.",
            },
        )
        with self.assertRaisesRegex(
            ValueError,
            (
                r"Unsupported smoothing_layer 'other'\. Allowed values are: "
                r"\"auto\", \"input_preparation\", \"score\"\."
            ),
        ):
            self.sensitivity.compare_smoothing_effect(
                "credit",
                smoothing_layer="other",
            )
        self.assert_result_unchanged(original_result)

    def test_curve_smoothing_alias_context_and_fingerprints_are_unchanged(self):
        windows = {
            "focus": ("2020-03-02", "2020-03-06"),
            "empty": ("1900-01-01", "1900-01-02"),
        }
        original_windows = copy.deepcopy(windows)
        original_result = self.snapshot_result()

        canonical = self.sensitivity.compare_smoothing_effect(
            "curve_positioning",
            windows=windows,
            include_detail=True,
        )
        alias = self.sensitivity.compare_smoothing_effect(
            "curve",
            windows=windows,
            include_detail=True,
        )
        explicit = self.sensitivity.compare_smoothing_effect(
            "curve",
            smoothing_layer="input_preparation",
            windows=windows,
            include_detail=False,
        )

        assert_nested_outputs_equal(self, canonical, alias)
        self.assertEqual(list(explicit), ["summary", "window_summary"])
        pd.testing.assert_frame_equal(canonical["summary"], explicit["summary"])
        pd.testing.assert_frame_equal(
            canonical["window_summary"],
            explicit["window_summary"],
        )
        self.assertEqual(
            list(canonical["summary"].columns),
            CURVE_SMOOTHING_SUMMARY_COLUMNS,
        )
        self.assertEqual(
            list(canonical["window_summary"].columns),
            CURVE_SMOOTHING_SUMMARY_COLUMNS + ["window_id", "start", "end"],
        )
        self.assertEqual(
            list(canonical["detail"].columns),
            CURVE_SMOOTHING_DETAIL_COLUMNS,
        )
        self.assertTrue(canonical["detail"].index.equals(self.result.features.index))
        self.assertTrue(canonical["detail"].iloc[0, :11].isna().all())
        focus = canonical["detail"].loc["2020-03-02"]
        self.assertAlmostEqual(focus["curve_10y2y_change"], 0.19)
        self.assertAlmostEqual(
            focus["curve_10y2y_change_prepared_for_curve_change"],
            0.12133333333333339,
        )
        self.assertAlmostEqual(
            focus["dgs2_change_prepared_for_curve_move_driver"],
            -0.2293333333333334,
        )
        self.assertEqual(focus["raw_curve_move_driver_score"], 1.0)

        summary = canonical["summary"].iloc[0]
        self.assertEqual(
            summary[
                [
                    "curve_positioning_score_one_sided_missing_count",
                    "raw_curve_score_change_count",
                    "smoothed_curve_score_change_count",
                    "curve_score_change_reduction_count",
                    "raw_curve_one_day_spike_count",
                    "smoothed_curve_one_day_spike_count",
                    "curve_one_day_spike_reduction_count",
                ]
            ].tolist(),
            [388, 128, 19, 109, 37, 0, 37],
        )
        empty = canonical["window_summary"].iloc[1]
        self.assertEqual(empty["total_rows"], 0)
        self.assertTrue(pd.isna(empty["curve_score_change_reduction_ratio"]))
        self.assertTrue(pd.isna(empty["curve_one_day_spike_reduction_ratio"]))
        self.assertEqual(
            frame_fingerprint(canonical["summary"]),
            "c5b1e494b9cc90d35e62a4024390d475526f6f365fa5f6bac9ea0811074cd6b3",
        )
        self.assertEqual(
            frame_fingerprint(canonical["window_summary"]),
            "27d9c2ed7a071d9c7a0783ad8cec85fa634bbc5e98c4ee52a396214e29b0fd06",
        )
        self.assertEqual(
            frame_fingerprint(canonical["detail"]),
            "24f5f529340cd019c79ff19c716c1d6ca1eb9146d77b42d51a16b84e831ffcc9",
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

    def test_curve_stabilization_uses_one_neutral_and_one_case_breakdown(self):
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
        cases = {
            "neutral": copy.deepcopy(neutral),
            "modified": {
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
            },
        }
        windows = {"focus": ("2020-03-02", "2020-03-06")}
        original_cases = copy.deepcopy(cases)
        original_windows = copy.deepcopy(windows)
        original_result = self.snapshot_result()

        with (
            patch.object(
                Module1Calculator,
                "build_rule_mapped_stance_score_breakdown",
                wraps=Module1Calculator.build_rule_mapped_stance_score_breakdown,
            ) as breakdown,
            patch.object(
                self.sensitivity._diagnostics,
                "rule_mapped_diagnostic_spec",
                wraps=(
                    self.sensitivity._diagnostics.rule_mapped_diagnostic_spec
                ),
            ) as rule_spec,
        ):
            result = (
                self.sensitivity.compare_curve_positioning_stabilization_cases(
                    cases=cases,
                    windows=windows,
                    include_diagnostics=False,
                )
            )

        self.assertEqual(rule_spec.call_count, 1)
        self.assertEqual(breakdown.call_count, 1 + len(cases))
        self.assertEqual(
            [
                call.kwargs["stabilization_overrides"]
                for call in breakdown.call_args_list
            ],
            [neutral, *cases.values()],
        )
        raw_columns = [
            column
            for column in CURVE_DETAIL_COLUMNS
            if column.startswith("raw_")
        ]
        pd.testing.assert_frame_equal(
            result["detail_by_case"]["neutral"][raw_columns],
            result["detail_by_case"]["modified"][raw_columns],
        )
        self.assertEqual(cases, original_cases)
        self.assertEqual(windows, original_windows)
        self.assert_result_unchanged(original_result)

    def test_transition_and_spike_masks_preserve_missing_value_semantics(self):
        index = pd.date_range("2024-01-01", periods=7, freq="D")
        transitions = pd.Series(
            [float("nan"), 1.0, float("nan"), 2.0, 2.0, float("nan"), 1.0],
            index=index,
        )
        expected_transitions = pd.Series(
            [False, False, False, True, False, False, True],
            index=index,
        )
        transition_mask = self.sensitivity._series_change_mask(transitions)
        pd.testing.assert_series_equal(transition_mask, expected_transitions)
        self.assertEqual(int(transition_mask.sum()), 2)
        self.assertFalse(
            self.sensitivity._series_change_mask(
                pd.Series([float("nan")] * 7, index=index)
            ).any()
        )
        self.assertFalse(
            self.sensitivity._series_change_mask(
                pd.Series(
                    [float("nan"), 1.0, *([float("nan")] * 5)],
                    index=index,
                )
            ).any()
        )

        spikes = pd.Series(
            [1.0, 2.0, 1.0, float("nan"), 1.0, 2.0, 1.0],
            index=index,
        )
        expected_spikes = pd.Series(
            [False, True, False, False, False, True, False],
            index=index,
        )
        spike_mask = self.sensitivity._one_day_spike_mask(spikes)
        pd.testing.assert_series_equal(spike_mask, expected_spikes)
        self.assertEqual(int(spike_mask.sum()), 2)

    def test_curve_stabilization_windows_recalculate_local_event_masks(self):
        index = pd.date_range("2024-01-01", periods=5, freq="D")
        scores = pd.Series([0.0, 1.0, 0.0, 0.0, 0.0], index=index)
        detail = pd.DataFrame(
            {
                "raw_curve_positioning_score": scores,
                "stabilized_curve_positioning_score": scores,
                "score_diff": 0.0,
                "score_changed": False,
                "raw_curve_positioning_rule_case": "case",
                "stabilized_curve_positioning_rule_case": "case",
                "raw_curve_positioning": "neutral",
                "stabilized_curve_positioning": "neutral",
                "raw_curve_positioning_strength": "weak",
                "stabilized_curve_positioning_strength": "weak",
            },
            index=index,
        )
        detail["raw_score_change_flag"] = (
            self.sensitivity._series_change_mask(
                detail["raw_curve_positioning_score"]
            )
        )
        detail["raw_one_day_spike_flag"] = (
            self.sensitivity._one_day_spike_mask(
                detail["raw_curve_positioning_score"]
            )
        )
        window = (index[1], index[3])
        sliced = self.sensitivity._inclusive_window_slice(detail, *window)
        self.assertEqual(int(sliced["raw_score_change_flag"].sum()), 2)
        self.assertEqual(int(sliced["raw_one_day_spike_flag"].sum()), 1)

        row = self.sensitivity._curve_stabilization_window_row(
            "case",
            "inside",
            window,
            detail,
        )
        self.assertEqual(row["raw_score_change_count"], 1)
        self.assertEqual(row["stabilized_score_change_count"], 1)
        self.assertEqual(row["one_day_spike_count_raw"], 0)
        self.assertEqual(row["one_day_spike_count_stabilized"], 0)

        outside_variant = detail.copy(deep=True)
        outside_variant.loc[index[0], "raw_curve_positioning_score"] = 1.0
        outside_variant.loc[
            index[0],
            "stabilized_curve_positioning_score",
        ] = 1.0
        variant_row = self.sensitivity._curve_stabilization_window_row(
            "case",
            "inside",
            window,
            outside_variant,
        )
        self.assertEqual(
            {
                key: row[key]
                for key in (
                    "raw_score_change_count",
                    "stabilized_score_change_count",
                    "one_day_spike_count_raw",
                    "one_day_spike_count_stabilized",
                )
            },
            {
                key: variant_row[key]
                for key in (
                    "raw_score_change_count",
                    "stabilized_score_change_count",
                    "one_day_spike_count_raw",
                    "one_day_spike_count_stabilized",
                )
            },
        )

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
        for case_id, detail in with_diagnostics["detail_by_case"].items():
            pd.testing.assert_frame_equal(
                detail,
                with_diagnostics["diagnostics_by_case"][case_id],
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
        for case_id, detail in with_diagnostics["detail_by_case"].items():
            self.assertEqual(
                summary.loc[case_id, "raw_score_change_count"],
                int(detail["raw_score_change_flag"].sum()),
            )
            self.assertEqual(
                summary.loc[case_id, "stabilized_score_change_count"],
                int(detail["stabilized_score_change_flag"].sum()),
            )
            self.assertEqual(
                summary.loc[case_id, "one_day_spike_count_raw"],
                int(detail["raw_one_day_spike_flag"].sum()),
            )
            self.assertEqual(
                summary.loc[case_id, "one_day_spike_count_stabilized"],
                int(detail["stabilized_one_day_spike_flag"].sum()),
            )
            bucket_rows = with_diagnostics["bucket_transition_summary"].query(
                "case_id == @case_id"
            )
            self.assertEqual(
                bucket_rows["bucket_type"].tolist(),
                ["curve_change", "curve_state", "yield_move_driver"],
            )
            self.assertEqual(
                summary.loc[case_id, "bucket_change_count_raw"],
                bucket_rows["raw_change_count"].sum(),
            )
            self.assertEqual(
                summary.loc[case_id, "bucket_change_count_stabilized"],
                bucket_rows["stabilized_change_count"].sum(),
            )
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
        case_diagnostic_runs = []

        def build_case_diagnostics(case_result):
            diagnostics = Module1Diagnostics(case_result)
            diagnostics.trace_stance_score = Mock(
                wraps=diagnostics.trace_stance_score
            )
            case_diagnostic_runs.append((case_result, diagnostics))
            return diagnostics

        with (
            patch.object(
                Module1Calculator,
                "calculate_exposure_stance_outputs",
                wraps=Module1Calculator.calculate_exposure_stance_outputs,
            ) as calculate_exposure_stance_outputs,
            patch(
                "module1_sensitivity_diagnostics.Module1Diagnostics",
                side_effect=build_case_diagnostics,
            ) as diagnostics_class,
        ):
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
        self.assertEqual(diagnostics_class.call_count, len(expected_settings))
        self.assertEqual(
            calculate_exposure_stance_outputs.call_count,
            len(expected_settings),
        )
        self.assertEqual(len(case_diagnostic_runs), len(expected_settings))
        for call, settings, diagnostic_run in zip(
            calculate_exposure_stance_outputs.call_args_list,
            expected_settings,
            case_diagnostic_runs,
        ):
            case_result, diagnostics = diagnostic_run
            self.assertIsInstance(case_result, Module1Result)
            diagnostics.trace_stance_score.assert_called_once_with(
                "credit",
                include_raw_input=True,
                include_labels=False,
            )
            for field_name in (
                "data",
                "features",
                "scores",
                "labels",
                "horizons",
                "default_horizons",
                "horizon_overrides",
                "module1_config_validation",
            ):
                self.assertIs(
                    getattr(case_result, field_name),
                    getattr(self.result, field_name),
                )
            self.assertIsNot(
                case_result.module1_config,
                self.result.module1_config,
            )
            scenario_config = call.args[2]["exposure_stances"]["credit"]
            nested_stabilization = scenario_config["rule_mapped"][
                "state_stabilization"
            ]
            self.assertNotIn("state_stabilization", scenario_config)
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
            self.assertIs(
                call.args[2]["exposure_stances"],
                case_result.module1_config["exposure_stances"],
            )
            self.assertIs(call.args[0], self.sensitivity.scores)
            self.assertIs(call.args[1], self.sensitivity.component_config)

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
