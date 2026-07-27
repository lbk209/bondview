import copy
import os
import unittest
from dataclasses import fields, replace
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import yaml

from module1_analysis import Module1Analysis
from module1_calculator import (
    Module1Calculator,
    Module1Result,
    RuleMappedStanceSpec,
)
from module1_diagnostics import Module1Diagnostics
from module1_historical_analysis import Module1HistoricalAnalysis
from module1_sensitivity_diagnostics import Module1SensitivityDiagnostics


def build_constructed_module1_result(**overrides) -> Module1Result:
    """Build a small, coherent result without calculator initialization or I/O."""
    index = pd.date_range("2024-01-01", periods=4, freq="D")
    module1_config = {
        "model_metadata": {
            "target_groups": {
                "constructed_group": {
                    "component": ["component_a"],
                    "stance": ["weighted"],
                }
            }
        },
        "horizons": {"short": 2},
        "features": {
            "feature_a": {
                "method": "level",
                "input": "raw_a",
            },
            "feature_b": {
                "method": "change",
                "input": "raw_b",
            },
        },
        "components": {
            "component_a": {
                "score": {
                    "function": "single_feature_score",
                    "input": "feature_a",
                    "input_preparation": {
                        "smoothing": "short",
                        "min_abs_value": 0.5,
                    },
                    "output": "component_a_score",
                },
                "label": {
                    "output": "component_a_label",
                    "thresholds": {
                        "positive": 0.5,
                        "negative": -0.5,
                    },
                    "labels": {
                        "positive": "a_positive",
                        "neutral": "a_neutral",
                        "negative": "a_negative",
                    },
                },
                "diagnostics": {
                    "prepared_inputs": {
                        "enabled": True,
                    }
                },
            },
            "component_b": {
                "score": {
                    "function": "single_feature_score",
                    "input": "feature_b",
                    "output": "component_b_score",
                },
                "label": {
                    "output": "component_b_label",
                    "thresholds": {
                        "positive": 0.5,
                        "negative": -0.5,
                    },
                    "labels": {
                        "positive": "b_positive",
                        "neutral": "b_neutral",
                        "negative": "b_negative",
                    },
                },
            },
        },
        "stance_label_rules": {
            "direction_thresholds": {
                "positive_min": 0.5,
                "negative_max": -0.5,
            },
            "strength_thresholds": {
                "weak_max_abs": 0.25,
                "moderate_max_abs": 0.75,
                "strong_min_abs": 0.75,
            },
        },
        "exposure_stances": {
            "weighted": {
                "function": "weighted_sum",
                "inputs": [
                    {"component": "component_a_score", "weight": 0.6},
                    {"component": "component_b_score", "weight": 0.4},
                ],
                "score_output": "weighted_score",
                "stance_output": "weighted_stance",
                "strength_output": "weighted_strength",
                "labels": {
                    "direction": {
                        "positive": "weighted_positive",
                        "neutral": "weighted_neutral",
                        "negative": "weighted_negative",
                    },
                    "strength": {
                        "weak": "weighted_weak",
                        "moderate": "weighted_moderate",
                        "strong": "weighted_strong",
                    },
                },
            },
            "rule": {
                "function": "rule_mapped_stance",
                "inputs": [
                    {"component": "component_a_score"},
                ],
                "score_output": "rule_score",
                "stance_output": "rule_stance",
                "strength_output": "rule_strength",
                "labels": {
                    "direction": {
                        "positive": "rule_positive",
                        "neutral": "rule_neutral",
                        "negative": "rule_negative",
                    },
                    "strength": {
                        "weak": "rule_weak",
                        "moderate": "rule_moderate",
                        "strong": "rule_strong",
                    },
                },
                "rule_mapped": {
                    "function": "rule_mapped_stance",
                    "state_inputs": [
                        {
                            "name": "state",
                            "source_score": "component_a_score",
                            "classification": "threshold_state",
                            "raw_output": "rule_state_raw",
                            "stabilized_output": "rule_state",
                            "stabilization_changed_output": (
                                "rule_state_stabilization_changed"
                            ),
                            "state_buckets": {
                                "positive": "positive",
                                "neutral": "neutral",
                                "negative": "negative",
                            },
                        }
                    ],
                    "state_stabilization": {
                        "state": {
                            "hysteresis_buffer": 0,
                            "min_state_persistence": 1,
                        }
                    },
                    "rule_scores": {
                        "positive": 1,
                        "neutral": 0,
                        "negative": -1,
                    },
                    "rule_case_output": "rule_case",
                    "stabilization_changed_any_output": (
                        "rule_stabilization_changed"
                    ),
                    "score_output": "rule_score",
                    "stance_output": "rule_stance",
                    "strength_output": "rule_strength",
                },
            },
        },
    }
    data = pd.DataFrame(
        {
            "raw_a": [1.0, 2.0, 3.0, 4.0],
            "raw_b": [10.0, 11.0, 13.0, 12.0],
        },
        index=index,
    )
    features = pd.DataFrame(
        {
            "feature_a": [0.2, 0.4, 1.0, -1.0],
            "feature_b": [0.0, 1.0, 2.0, -1.0],
        },
        index=index,
    )
    scores = pd.DataFrame(
        {
            "component_a_score": [1.0, 0.0, -1.0, 1.0],
            "component_b_score": [0.0, 1.0, 0.0, -1.0],
        },
        index=index,
    )
    labels = pd.DataFrame(
        {
            "component_a_label": [
                "a_positive",
                "a_neutral",
                "a_negative",
                "a_positive",
            ],
            "component_b_label": [
                "b_neutral",
                "b_positive",
                "b_neutral",
                "b_negative",
            ],
        },
        index=index,
    )

    weighted_config = module1_config["exposure_stances"]["weighted"]
    weighted_breakdown = Module1Calculator.build_weighted_stance_score_breakdown(
        scores,
        "weighted",
        weighted_config,
    )
    rule_config = module1_config["exposure_stances"]["rule"]
    component_config = {"components": module1_config["components"]}
    rule_spec = Module1Calculator.resolve_rule_mapped_stance_spec(
        "rule",
        rule_config,
        component_config,
    )
    rule_breakdown = Module1Calculator.build_rule_mapped_stance_score_breakdown(
        scores,
        component_config,
        "rule",
        rule_config,
        rule_spec,
    )
    stance_scores = pd.DataFrame(
        {
            "weighted_score": weighted_breakdown["weighted_score"],
            "rule_score": rule_breakdown["rule_score"],
        },
        index=index,
    )
    exposure_stance = pd.DataFrame(
        {
            "weighted_score": stance_scores["weighted_score"],
            "weighted_stance": [
                "weighted_positive",
                "weighted_neutral",
                "weighted_negative",
                "weighted_neutral",
            ],
            "weighted_strength": pd.Series(
                [
                    "weighted_moderate",
                    "weighted_weak",
                    "weighted_moderate",
                    "weighted_weak",
                ],
                index=index,
                dtype="object",
            ),
            "rule_score": stance_scores["rule_score"],
            "rule_stance": [
                "rule_positive",
                "rule_neutral",
                "rule_negative",
                "rule_positive",
            ],
            "rule_strength": pd.Series(
                [
                    "rule_strong",
                    "rule_weak",
                    "rule_strong",
                    "rule_strong",
                ],
                index=index,
                dtype="object",
            ),
        },
        index=index,
    )

    values = {
        "data": data,
        "features": features,
        "scores": scores,
        "labels": labels,
        "stance_scores": stance_scores,
        "exposure_stance": exposure_stance,
        "module1_config": module1_config,
        "horizons": {"short": 2},
        "default_horizons": {"short": 2},
        "horizon_overrides": None,
        "module1_config_validation": {"issues": pd.DataFrame()},
    }
    unknown_overrides = sorted(set(overrides) - set(values))
    if unknown_overrides:
        raise TypeError(f"Unknown Module1Result override(s): {unknown_overrides}")
    values.update(
        {
            field_name: copy.deepcopy(field_value)
            for field_name, field_value in overrides.items()
        }
    )
    return Module1Result(**values)


class Module1ConfigSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._fred_key = patch.dict(os.environ, {"FRED_API_KEY": "test"})
        cls._fred_key.start()
        cls.calculator = Module1Calculator()
        cls.operational_config = copy.deepcopy(cls.calculator.module1_config)
        cls.calculator.run_module1_pipeline()
        cls.result = cls.calculator.to_module1_result()

    @classmethod
    def tearDownClass(cls):
        cls._fred_key.stop()

    def test_result_contains_complete_parsed_operational_config(self):
        config_path = Path("data/module1_config.yaml")
        with config_path.open("r", encoding="utf-8") as config_file:
            parsed_config = yaml.safe_load(config_file)

        self.assertEqual(self.operational_config, parsed_config)
        self.assertEqual(self.calculator.module1_config, self.operational_config)
        self.assertEqual(self.result.module1_config, self.operational_config)
        self.assertTrue(self.result.module1_config_validation["issues"].empty)

    def test_result_has_no_independently_stored_config_subsection_fields(self):
        result_field_names = {field.name for field in fields(type(self.result))}

        for field_name in (
            "feature_config",
            "component_config",
            "exposure_stance_config",
        ):
            self.assertNotIn(field_name, result_field_names)
            self.assertNotIn(field_name, self.result.__dict__)
            self.assertFalse(hasattr(self.result, field_name))

    def test_calculator_and_result_configuration_are_deeply_isolated(self):
        with patch.dict(os.environ, {"FRED_API_KEY": "test"}):
            calculator = Module1Calculator()
            calculator.run_module1_pipeline()
            result = calculator.to_module1_result()

        calculator.module1_config["horizons"]["rates"] = 999
        calculator.component_config["components"]["duration_preference"]["score"][
            "clip"
        ] = [-99.0, 99.0]

        self.assertEqual(result.module1_config["horizons"]["rates"], 126)
        self.assertNotEqual(
            result.module1_config["components"]["duration_preference"]["score"][
                "clip"
            ],
            [-99.0, 99.0],
        )

        result.module1_config["horizons"]["rates"] = 777
        result.module1_config["components"]["duration_preference"]["score"][
            "clip"
        ] = [-77.0, 77.0]

        self.assertEqual(calculator.module1_config["horizons"]["rates"], 999)
        self.assertEqual(
            calculator.module1_config["components"]["duration_preference"]["score"][
                "clip"
            ],
            [-99.0, 99.0],
        )
        self.assertEqual(
            calculator.component_config["components"]["duration_preference"]["score"][
                "clip"
            ],
            [-99.0, 99.0],
        )

    def test_result_specific_resolution_uses_stored_snapshot(self):
        result = self.calculator.to_module1_result()
        result.module1_config["model_metadata"]["target_groups"]["snapshot_only"] = {
            "component": ["duration_preference"],
            "stance": [],
        }

        with patch.object(
            Module1Calculator,
            "_load_yaml_config",
            side_effect=AssertionError("result resolution loaded external YAML"),
        ):
            resolution = Module1Analysis(result).resolve_target(
                "snapshot_only",
                level="component",
            )

        self.assertEqual(resolution.canonical_target, "duration_preference")
        self.assertEqual(resolution.kind, "target_group_member")

    def test_feature_resolution_config_is_isolated_from_result(self):
        result = self.calculator.to_module1_result()
        resolution = Module1Analysis(result)._resolve_target_for_context(
            "curve_10y2y_level",
            "feature",
        )

        resolution.config["inputs"][0] = "mutated_input"

        self.assertEqual(
            result.module1_config["features"]["curve_10y2y_level"]["inputs"],
            ["dgs10", "dgs2"],
        )

    def test_component_resolution_config_is_isolated_from_result(self):
        result = self.calculator.to_module1_result()
        resolution = Module1Analysis(result).resolve_target(
            "duration_preference",
            "component",
        )

        resolution.config["score"]["clip"]["min"] = -99.0

        self.assertEqual(
            result.module1_config["components"]["duration_preference"]["score"][
                "clip"
            ]["min"],
            -3.0,
        )

    def test_stance_resolution_config_is_isolated_from_result(self):
        result = self.calculator.to_module1_result()
        resolution = Module1Analysis(result).resolve_target(
            "credit",
            "stance",
        )

        resolution.config["labels"]["direction"]["positive"] = "mutated_label"

        self.assertEqual(
            result.module1_config["exposure_stances"]["credit"]["labels"]["direction"][
                "positive"
            ],
            "credit_positive",
        )

    def test_historical_local_config_is_isolated_from_result(self):
        result = self.calculator.to_module1_result()
        historical = Module1HistoricalAnalysis(result)

        historical.component_config["components"]["duration_preference"]["score"][
            "clip"
        ]["min"] = -99.0
        historical.exposure_stance_config["exposure_stances"]["credit"]["labels"][
            "direction"
        ]["positive"] = "mutated_label"

        self.assertEqual(
            result.module1_config["components"]["duration_preference"]["score"][
                "clip"
            ]["min"],
            -3.0,
        )
        self.assertEqual(
            result.module1_config["exposure_stances"]["credit"]["labels"]["direction"][
                "positive"
            ],
            "credit_positive",
        )

    def test_diagnostics_and_sensitivity_local_config_remain_isolated(self):
        result = self.calculator.to_module1_result()
        diagnostics = Module1Diagnostics(result)
        sensitivity = Module1SensitivityDiagnostics(result)
        context = diagnostics.get_target_context(
            "duration_preference",
            "component",
        )

        diagnostics.feature_config["features"]["curve_10y2y_level"]["inputs"][
            0
        ] = "diagnostics_input"
        diagnostics.component_config["components"]["duration_preference"]["score"][
            "clip"
        ]["min"] = -98.0
        diagnostics.exposure_stance_config["exposure_stances"]["credit"]["labels"][
            "direction"
        ]["positive"] = "diagnostics_label"
        context.resolution["config"]["score"]["clip"]["min"] = -96.0
        sensitivity.feature_config["features"]["curve_10y2y_level"]["inputs"][
            0
        ] = "sensitivity_input"
        sensitivity.component_config["components"]["duration_preference"]["score"][
            "clip"
        ]["min"] = -97.0
        sensitivity.exposure_stance_config["exposure_stances"]["credit"]["labels"][
            "direction"
        ]["positive"] = "sensitivity_label"

        self.assertEqual(
            result.module1_config["features"]["curve_10y2y_level"]["inputs"],
            ["dgs10", "dgs2"],
        )
        self.assertEqual(
            result.module1_config["components"]["duration_preference"]["score"][
                "clip"
            ]["min"],
            -3.0,
        )
        self.assertEqual(
            result.module1_config["exposure_stances"]["credit"]["labels"]["direction"][
                "positive"
            ],
            "credit_positive",
        )

    def test_shared_capabilities_are_direct_static_interfaces(self):
        shared_capabilities = (
            "prepare_component_input_series",
            "build_weighted_stance_score_breakdown",
            "parse_rule_scores_n_parts",
            "resolve_rule_mapped_stabilization_config",
            "resolve_rule_mapped_stance_spec",
            "build_rule_mapped_stance_score_breakdown",
            "calculate_component_score",
            "classify_component_score_buckets",
            "label_exposure_stance_score",
            "calculate_exposure_stance_outputs",
        )
        removed_private_names = (
            "_prepare_component_input_series",
            "_build_weighted_stance_score_breakdown",
            "_parse_rule_scores_n_parts",
            "_resolve_rule_mapped_stabilization_config",
            "_resolve_rule_mapped_stance_spec",
            "_build_rule_mapped_stance_score_breakdown",
        )

        for capability_name in shared_capabilities:
            self.assertIsInstance(
                Module1Calculator.__dict__[capability_name],
                staticmethod,
            )
        for private_name in removed_private_names:
            self.assertFalse(hasattr(Module1Calculator, private_name))

    def test_prepare_component_input_series_is_stateless_and_non_mutating(self):
        series = pd.Series([1.0, 3.0, 5.0], name="input")
        input_preparation = {"smoothing": "short"}
        horizons = {"short": 2}
        original_series = series.copy(deep=True)
        original_input_preparation = copy.deepcopy(input_preparation)
        original_horizons = copy.deepcopy(horizons)

        prepared = Module1Calculator.prepare_component_input_series(
            series,
            input_preparation,
            horizons,
        )

        pd.testing.assert_series_equal(
            prepared,
            pd.Series([float("nan"), 2.0, 4.0], name="input"),
        )
        pd.testing.assert_series_equal(series, original_series)
        self.assertEqual(input_preparation, original_input_preparation)
        self.assertEqual(horizons, original_horizons)
        with self.assertRaisesRegex(ValueError, "Unknown horizon key: missing"):
            Module1Calculator.prepare_component_input_series(
                series,
                {"smoothing": "missing"},
                horizons,
            )

    def test_weighted_breakdown_is_stateless_and_non_mutating(self):
        scores = pd.DataFrame(
            {
                "first_score": [1.0, 2.0, float("nan")],
                "second_score": [3.0, 4.0, 5.0],
            }
        )
        stance_config = {
            "inputs": [
                {"component": "first_score", "weight": 0.25},
                {"component": "second_score", "weight": 0.75},
            ],
            "score_output": "combined_score",
        }
        original_scores = scores.copy(deep=True)
        original_stance_config = copy.deepcopy(stance_config)

        breakdown = Module1Calculator.build_weighted_stance_score_breakdown(
            scores,
            "example",
            stance_config,
        )

        self.assertEqual(
            list(breakdown.columns),
            [
                "first_score",
                "second_score",
                "first_score_weight",
                "first_score_contribution",
                "second_score_weight",
                "second_score_contribution",
                "combined_score",
            ],
        )
        pd.testing.assert_series_equal(
            breakdown["combined_score"],
            pd.Series([2.5, 3.5, float("nan")], name="combined_score"),
        )
        pd.testing.assert_frame_equal(scores, original_scores)
        self.assertEqual(stance_config, original_stance_config)

        invalid_config = copy.deepcopy(stance_config)
        invalid_config.pop("score_output")
        with self.assertRaisesRegex(
            ValueError,
            "Exposure stance example score output is missing",
        ):
            Module1Calculator.build_weighted_stance_score_breakdown(
                scores,
                "example",
                invalid_config,
            )

    def test_rule_parsing_and_stabilization_interfaces_are_non_mutating(self):
        rule_scores = {"positive|wide": 1, "negative|tight": -1.5}
        original_rule_scores = copy.deepcopy(rule_scores)
        parsed = Module1Calculator.parse_rule_scores_n_parts(
            rule_scores,
            expected_parts=2,
            context="example",
        )

        self.assertEqual(
            parsed,
            {
                ("positive", "wide"): 1.0,
                ("negative", "tight"): -1.5,
            },
        )
        self.assertEqual(rule_scores, original_rule_scores)
        with self.assertRaisesRegex(
            ValueError,
            "example rule score key must have exactly 2 part",
        ):
            Module1Calculator.parse_rule_scores_n_parts(
                {"positive": 1.0},
                expected_parts=2,
                context="example",
            )

        stance_config = {
            "state_stabilization": {
                "state": {
                    "hysteresis_buffer": 0,
                    "min_state_persistence": 2,
                }
            }
        }
        original_stance_config = copy.deepcopy(stance_config)
        stabilization = (
            Module1Calculator.resolve_rule_mapped_stabilization_config(
                stance_config,
                ["state"],
                context="example",
            )
        )

        self.assertEqual(
            stabilization,
            {
                "state": {
                    "hysteresis_buffer": 0.0,
                    "min_state_persistence": 2,
                }
            },
        )
        self.assertEqual(stance_config, original_stance_config)

        invalid_stance_config = copy.deepcopy(stance_config)
        invalid_stance_config["state_stabilization"]["state"].pop(
            "hysteresis_buffer"
        )
        with self.assertRaisesRegex(
            ValueError,
            "example state_stabilization.state.hysteresis_buffer is required",
        ):
            Module1Calculator.resolve_rule_mapped_stabilization_config(
                invalid_stance_config,
                ["state"],
                context="example",
            )

    def test_rule_mapped_capabilities_are_stateless_and_non_mutating(self):
        config = self.result.module1_config
        component_config = {"components": copy.deepcopy(config["components"])}
        original_component_config = copy.deepcopy(component_config)
        original_scores = self.result.scores.copy(deep=True)
        configured_rule_mapped_stances = []

        for stance_name, configured_stance in config["exposure_stances"].items():
            if "rule_mapped" not in configured_stance:
                continue

            configured_rule_mapped_stances.append(stance_name)
            stance_config = copy.deepcopy(configured_stance)
            original_stance_config = copy.deepcopy(stance_config)
            spec = Module1Calculator.resolve_rule_mapped_stance_spec(
                stance_name,
                stance_config,
                component_config,
            )
            original_spec = copy.deepcopy(spec)

            self.assertIsInstance(spec, RuleMappedStanceSpec)
            self.assertEqual(spec.stance_name, stance_name)
            self.assertEqual(stance_config, original_stance_config)
            self.assertEqual(component_config, original_component_config)

            breakdown = (
                Module1Calculator.build_rule_mapped_stance_score_breakdown(
                    self.result.scores,
                    component_config,
                    stance_name,
                    stance_config,
                    spec,
                )
            )
            required_score_columns = [
                state_input.source_score_col for state_input in spec.state_inputs
            ]
            expected_columns = list(required_score_columns)
            for state_input in spec.state_inputs:
                expected_columns.extend(
                    [
                        state_input.raw_output_col,
                        state_input.stabilized_output_col,
                    ]
                )
            expected_columns.extend(
                state_input.stabilization_changed_output_col
                for state_input in spec.state_inputs
            )
            expected_columns.append(spec.stabilization_changed_any_output_col)
            expected_columns.append(spec.rule_case_output_col)
            if spec.base_rule_score_output_col is not None:
                expected_columns.append(spec.base_rule_score_output_col)
            if spec.adjustment is not None:
                expected_columns.extend(spec.adjustment.metadata_output_cols)
                if spec.adjustment.adjustment_output_col is not None:
                    expected_columns.append(spec.adjustment.adjustment_output_col)
            expected_columns.append(spec.score_output_col)

            self.assertEqual(list(breakdown.columns), expected_columns)
            pd.testing.assert_series_equal(
                breakdown[spec.score_output_col],
                self.result.stance_scores[spec.score_output_col],
            )
            pd.testing.assert_frame_equal(self.result.scores, original_scores)
            self.assertEqual(component_config, original_component_config)
            self.assertEqual(stance_config, original_stance_config)
            self.assertEqual(spec, original_spec)

        self.assertEqual(
            configured_rule_mapped_stances,
            ["duration", "credit", "curve_positioning"],
        )

        invalid_stance_config = copy.deepcopy(
            config["exposure_stances"]["duration"]
        )
        invalid_stance_config["rule_mapped"]["function"] = "invalid"
        with self.assertRaisesRegex(
            ValueError,
            "rule_mapped.function must be rule_mapped_stance",
        ):
            Module1Calculator.resolve_rule_mapped_stance_spec(
                "duration",
                invalid_stance_config,
                component_config,
            )

        valid_stance_config = copy.deepcopy(
            config["exposure_stances"]["duration"]
        )
        valid_spec = Module1Calculator.resolve_rule_mapped_stance_spec(
            "duration",
            valid_stance_config,
            component_config,
        )
        missing_scores = self.result.scores.drop(
            columns=[valid_spec.state_inputs[0].source_score_col]
        )
        with self.assertRaisesRegex(
            ValueError,
            "Missing component score column",
        ):
            Module1Calculator.build_rule_mapped_stance_score_breakdown(
                missing_scores,
                component_config,
                "duration",
                valid_stance_config,
                valid_spec,
            )

    def test_migrated_consumers_resolve_metadata_from_module1_config(self):
        config = self.result.module1_config
        analysis = Module1Analysis(self.result)

        feature = analysis._resolve_target_for_context("dgs2_change", "feature")
        component = analysis.resolve_target("duration_preference_score", "component")
        stance = analysis.resolve_target("credit_stance", "stance")
        target_group = analysis.resolve_target(
            "duration",
            allow_group=True,
        )

        self.assertEqual(feature.config, config["features"]["dgs2_change"])
        self.assertEqual(feature.score_col, "dgs2_change")
        self.assertEqual(component.canonical_target, "duration_preference")
        self.assertEqual(
            component.config,
            config["components"]["duration_preference"],
        )
        self.assertEqual(
            (component.score_col, component.label_col),
            (
                config["components"]["duration_preference"]["score"]["output"],
                config["components"]["duration_preference"]["label"]["output"],
            ),
        )
        self.assertEqual(stance.canonical_target, "credit")
        self.assertEqual(stance.config, config["exposure_stances"]["credit"])
        self.assertEqual(
            (stance.score_col, stance.label_col, stance.strength_col),
            (
                config["exposure_stances"]["credit"]["score_output"],
                config["exposure_stances"]["credit"]["stance_output"],
                config["exposure_stances"]["credit"]["strength_output"],
            ),
        )
        self.assertEqual(
            target_group.related_targets,
            (
                ("component", "duration_preference"),
                ("component", "duration_rate_shock"),
                ("stance", "duration"),
            ),
        )

        diagnostics = Module1Diagnostics(self.result)
        diagnostic_context = diagnostics.get_target_context(
            "duration_preference",
            "component",
        )
        self.assertEqual(
            diagnostics.feature_config,
            {"features": config["features"]},
        )
        self.assertEqual(
            diagnostics.component_config,
            {"components": config["components"]},
        )
        self.assertEqual(
            diagnostics.exposure_stance_config,
            {
                "stance_label_rules": config["stance_label_rules"],
                "exposure_stances": config["exposure_stances"],
            },
        )
        self.assertEqual(
            diagnostic_context.resolution["score_col"],
            component.score_col,
        )

        historical = Module1HistoricalAnalysis(self.result)
        historical.load_historical_context("data/historical_context.yaml")
        historical_context = historical.get_target_context(
            "duration_preference",
            "component",
            context_id="covid_shock_2020",
        )
        self.assertEqual(
            historical.component_config,
            {"components": config["components"]},
        )
        self.assertEqual(
            historical.exposure_stance_config,
            {
                "stance_label_rules": config["stance_label_rules"],
                "exposure_stances": config["exposure_stances"],
            },
        )
        self.assertEqual(historical_context.context_id, "covid_shock_2020")
        self.assertEqual(
            historical_context.resolution["score_col"],
            component.score_col,
        )

        sensitivity = Module1SensitivityDiagnostics(self.result)
        self.assertEqual(
            sensitivity.feature_config,
            {"features": config["features"]},
        )
        self.assertEqual(
            sensitivity.component_config,
            {"components": config["components"]},
        )
        self.assertEqual(
            sensitivity.exposure_stance_config,
            {
                "stance_label_rules": config["stance_label_rules"],
                "exposure_stances": config["exposure_stances"],
            },
        )
        self.assertIs(
            sensitivity.feature_config["features"],
            sensitivity.module1_config["features"],
        )
        self.assertIs(
            sensitivity.component_config["components"],
            sensitivity.module1_config["components"],
        )
        self.assertIs(
            sensitivity.exposure_stance_config["exposure_stances"],
            sensitivity.module1_config["exposure_stances"],
        )

    def test_horizon_scenarios_use_normal_calculators_and_apply_overrides(self):
        cases = [
            {"case_id": "same_a", "rates": 126},
            {"case_id": "same_b", "rates": 126},
            {"case_id": "modified", "rates": 90},
        ]
        with patch(
            "module1_sensitivity_diagnostics.Module1Calculator",
            wraps=Module1Calculator,
        ) as calculator_class:
            comparison = Module1SensitivityDiagnostics.compare_horizon_cases(
                horizon_cases=cases,
                target="duration_preference",
                level="component",
                output="summary",
            )

        self.assertEqual(calculator_class.call_count, 4)
        same_a = comparison.loc[comparison["case_id"] == "same_a"].iloc[0]
        same_b = comparison.loc[comparison["case_id"] == "same_b"].iloc[0]
        modified = comparison.loc[
            comparison["case_id"] == "modified"
        ].iloc[0]
        pd.testing.assert_series_equal(
            same_a.drop(labels=["case_id"]),
            same_b.drop(labels=["case_id"]),
            check_names=False,
        )
        self.assertNotEqual(
            modified["mixed"],
            same_a["mixed"],
        )
        self.assertNotEqual(
            modified["inconsistent"],
            same_a["inconsistent"],
        )

    def test_credit_persistence_is_repeatable_and_does_not_mutate_result(self):
        result = self.calculator.to_module1_result()
        original_data = result.data.copy(deep=True)
        original_features = result.features.copy(deep=True)
        original_scores = result.scores.copy(deep=True)
        original_labels = result.labels.copy(deep=True)
        original_stance_scores = result.stance_scores.copy(deep=True)
        original_exposure_stance = result.exposure_stance.copy(deep=True)
        original_config = copy.deepcopy(result.module1_config)
        sensitivity = Module1SensitivityDiagnostics(result)
        cases = {
            "base_p1_p1": {
                "credit_spread_change": 1,
                "credit_spread_state": 1,
            }
        }

        first = sensitivity.compare_credit_stance_persistence_cases(
            cases=cases,
            include_diagnostics=False,
        )
        second = sensitivity.compare_credit_stance_persistence_cases(
            cases=cases,
            include_diagnostics=False,
        )

        self.assertEqual(first.keys(), second.keys())
        for output_name in first:
            pd.testing.assert_frame_equal(
                first[output_name],
                second[output_name],
            )
        pd.testing.assert_frame_equal(result.data, original_data)
        pd.testing.assert_frame_equal(result.features, original_features)
        pd.testing.assert_frame_equal(result.scores, original_scores)
        pd.testing.assert_frame_equal(result.labels, original_labels)
        pd.testing.assert_frame_equal(
            result.stance_scores,
            original_stance_scores,
        )
        pd.testing.assert_frame_equal(
            result.exposure_stance,
            original_exposure_stance,
        )
        self.assertEqual(result.module1_config, original_config)

    def test_representative_pipeline_outputs_are_unchanged(self):
        latest = pd.Timestamp("2026-05-08")

        self.assertAlmostEqual(
            self.result.scores.loc[latest, "duration_preference_score"],
            -1.151538,
            places=6,
        )
        self.assertAlmostEqual(
            self.result.stance_scores.loc[latest, "credit_stance_score"],
            -0.258067,
            places=6,
        )
        self.assertEqual(
            self.result.labels.loc[latest, "duration_label"],
            "duration_unfavorable",
        )
        self.assertEqual(
            self.result.exposure_stance.loc[latest, "curve_positioning"],
            "short_end",
        )


class Module1ConstructedResultTests(unittest.TestCase):
    def setUp(self):
        self.result = build_constructed_module1_result()

    def test_sensitivity_constructs_no_calculator_and_uses_no_external_setup(self):
        original_data = self.result.data.copy(deep=True)
        original_scores = self.result.scores.copy(deep=True)
        original_config = copy.deepcopy(self.result.module1_config)

        with (
            patch.object(
                Module1Calculator,
                "__init__",
                side_effect=AssertionError("calculator initialization attempted"),
            ),
            patch.object(
                Module1Calculator,
                "_load_yaml_config",
                side_effect=AssertionError("Module 1 YAML access attempted"),
            ),
            patch(
                "module1_schema.validate_module1_config",
                side_effect=AssertionError("raw configuration validation attempted"),
            ),
            patch("builtins.open", side_effect=AssertionError("file I/O attempted")),
            patch(
                "os.getenv",
                side_effect=AssertionError("environment lookup attempted"),
            ),
        ):
            sensitivity = Module1SensitivityDiagnostics(self.result)
            diagnostics = sensitivity._diagnostics
            first = diagnostics.trace_stance_score(
                "rule",
                include_raw_input=False,
                include_labels=False,
            )
            second = diagnostics.trace_stance_score(
                "rule",
                include_raw_input=False,
                include_labels=False,
            )
            weighted = diagnostics.trace_stance_score(
                "weighted",
                include_raw_input=False,
                include_labels=False,
            )

        pd.testing.assert_frame_equal(first, second)
        self.assertEqual(
            list(first.columns),
            [
                "component_a_score",
                "rule_state_raw",
                "rule_state",
                "rule_state_stabilization_changed",
                "rule_stabilization_changed",
                "rule_case",
                "rule_score",
                "rule_stance",
                "rule_strength",
            ],
        )
        self.assertEqual(
            list(weighted.columns),
            [
                "component_a_score",
                "component_b_score",
                "component_a_score_weight",
                "component_a_score_contribution",
                "component_b_score_weight",
                "component_b_score_contribution",
                "weighted_score",
                "weighted_stance",
                "weighted_strength",
            ],
        )
        pd.testing.assert_frame_equal(self.result.data, original_data)
        pd.testing.assert_frame_equal(self.result.scores, original_scores)
        self.assertEqual(self.result.module1_config, original_config)

    def test_explicit_calculator_capabilities_are_stateless_and_non_mutating(self):
        features = self.result.features.copy(deep=True)
        scores = self.result.scores.copy(deep=True)
        config = copy.deepcopy(self.result.module1_config)
        original_features = features.copy(deep=True)
        original_scores = scores.copy(deep=True)
        original_config = copy.deepcopy(config)

        component_score = Module1Calculator.calculate_component_score(
            features,
            "component_a",
            config["components"]["component_a"]["score"],
            {"short": 2},
            apply_score_smoothing=False,
        )
        pd.testing.assert_series_equal(
            component_score,
            pd.Series(
                [float("nan"), 0.3, 0.7, 0.0],
                index=features.index,
                name="feature_a",
            ),
        )

        stance_scores, exposure_stance = (
            Module1Calculator.calculate_exposure_stance_outputs(
                scores,
                {"components": config["components"]},
                {
                    "stance_label_rules": config["stance_label_rules"],
                    "exposure_stances": config["exposure_stances"],
                },
            )
        )
        pd.testing.assert_frame_equal(stance_scores, self.result.stance_scores)
        pd.testing.assert_frame_equal(
            exposure_stance,
            self.result.exposure_stance,
        )

        bucket_config = {
            "positive": {"score": 1.0},
            "negative": {"score": -1.0},
            "neutral": {"default": True},
        }
        original_bucket_config = copy.deepcopy(bucket_config)
        buckets = Module1Calculator.classify_component_score_buckets(
            pd.Series([1.0, 0.0, -1.0, float("nan")]),
            bucket_config,
        )
        pd.testing.assert_series_equal(
            buckets,
            pd.Series(
                ["positive", "neutral", "negative", pd.NA],
                dtype="str",
            ),
        )

        pd.testing.assert_frame_equal(features, original_features)
        pd.testing.assert_frame_equal(scores, original_scores)
        self.assertEqual(config, original_config)
        self.assertEqual(bucket_config, original_bucket_config)

    def test_builder_creates_fresh_coherent_results_without_external_setup(self):
        with (
            patch.object(
                Module1Calculator,
                "__init__",
                side_effect=AssertionError("calculator initialization attempted"),
            ),
            patch("builtins.open", side_effect=AssertionError("file I/O attempted")),
            patch(
                "os.getenv",
                side_effect=AssertionError("environment lookup attempted"),
            ),
        ):
            first = build_constructed_module1_result()
            second = build_constructed_module1_result()

        table_names = (
            "data",
            "features",
            "scores",
            "labels",
            "stance_scores",
            "exposure_stance",
        )
        for table_name in table_names:
            first_table = getattr(first, table_name)
            second_table = getattr(second, table_name)
            self.assertTrue(first_table.index.equals(first.data.index))
            self.assertIsNot(first_table, second_table)

        self.assertIsNot(first.module1_config, second.module1_config)
        self.assertIsNot(
            first.module1_config["components"],
            second.module1_config["components"],
        )
        for component in first.module1_config["components"].values():
            self.assertIn(component["score"]["output"], first.scores.columns)
            self.assertIn(component["label"]["output"], first.labels.columns)
        for stance in first.module1_config["exposure_stances"].values():
            self.assertIn(stance["score_output"], first.stance_scores.columns)
            self.assertIn(stance["score_output"], first.exposure_stance.columns)
            self.assertIn(stance["stance_output"], first.exposure_stance.columns)
            self.assertIn(stance["strength_output"], first.exposure_stance.columns)

        first.data.loc[first.data.index[0], "raw_a"] = 999.0
        first.module1_config["components"]["component_a"]["score"][
            "output"
        ] = "mutated"
        self.assertEqual(second.data.iloc[0]["raw_a"], 1.0)
        self.assertEqual(
            second.module1_config["components"]["component_a"]["score"]["output"],
            "component_a_score",
        )

    def test_analysis_resolves_constructed_result_layers_and_dependencies(self):
        with (
            patch.object(
                Module1Calculator,
                "__init__",
                side_effect=AssertionError("calculator initialization attempted"),
            ),
            patch.object(
                Module1Calculator,
                "_load_yaml_config",
                side_effect=AssertionError("Module 1 YAML access attempted"),
            ),
            patch(
                "module1_schema.validate_module1_config",
                side_effect=AssertionError("raw configuration validation attempted"),
            ),
            patch("yaml.safe_load", side_effect=AssertionError("YAML access attempted")),
        ):
            analysis = Module1Analysis(self.result)
            raw_context = analysis.get_target_context(
                "raw_a",
                "raw_input",
                dependency_level="none",
            )
            feature_context = analysis.get_target_context(
                "feature_a",
                "feature",
                dependency_level="full",
            )
            component_context = analysis.get_target_context(
                "component_a_score",
                "component",
                dependency_level="full",
            )
            stance_context = analysis.get_target_context(
                "weighted_stance",
                "stance",
                dependency_level="full",
            )
            component_alias = analysis.resolve_target(
                "component_a_label",
                "component",
            )
            target_group = analysis.resolve_target(
                "constructed_group",
                allow_group=True,
            )
            raw_dependencies = analysis.raw_inputs_for_target(
                "weighted",
                "stance",
            )

        self.assertEqual(raw_context.returned_columns["target"], ("raw_a",))
        self.assertEqual(
            feature_context.returned_columns,
            {
                "target": ("feature_a",),
                "component_scores": (),
                "component_labels": (),
                "features": ("feature_a",),
                "raw_inputs": ("raw_a",),
                "labels": (),
                "strength": (),
            },
        )
        self.assertEqual(component_alias.canonical_target, "component_a")
        self.assertEqual(
            target_group.related_targets,
            (
                ("component", "component_a"),
                ("stance", "weighted"),
            ),
        )
        self.assertEqual(
            raw_dependencies,
            ["raw_a", "raw_b"],
        )
        self.assertEqual(
            list(component_context.data.columns),
            [
                "component_a_score",
                "component_a_label",
                "feature_a",
                "raw_a",
            ],
        )
        self.assertEqual(
            list(stance_context.data.columns),
            [
                "weighted_score",
                "weighted_stance",
                "weighted_strength",
                "component_a_score",
                "component_b_score",
                "component_a_label",
                "component_b_label",
                "feature_a",
                "feature_b",
                "raw_a",
                "raw_b",
            ],
        )

        component_alias.config["score"]["output"] = "mutated"
        self.assertEqual(
            self.result.module1_config["components"]["component_a"]["score"][
                "output"
            ],
            "component_a_score",
        )

    def test_diagnostics_use_stateless_capabilities_and_preserve_trace_order(self):
        with (
            patch.object(
                Module1Calculator,
                "__init__",
                side_effect=AssertionError("calculator initialization attempted"),
            ),
            patch.object(
                Module1Calculator,
                "_load_yaml_config",
                side_effect=AssertionError("Module 1 YAML access attempted"),
            ),
            patch(
                "module1_schema.validate_module1_config",
                side_effect=AssertionError("raw configuration validation attempted"),
            ),
            patch("yaml.safe_load", side_effect=AssertionError("YAML access attempted")),
            patch.object(
                Module1Calculator,
                "prepare_component_input_series",
                wraps=Module1Calculator.prepare_component_input_series,
            ) as prepare_input,
            patch.object(
                Module1Calculator,
                "build_weighted_stance_score_breakdown",
                wraps=Module1Calculator.build_weighted_stance_score_breakdown,
            ) as weighted_breakdown,
            patch.object(
                Module1Calculator,
                "resolve_rule_mapped_stance_spec",
                wraps=Module1Calculator.resolve_rule_mapped_stance_spec,
            ) as resolve_rule_spec,
            patch.object(
                Module1Calculator,
                "build_rule_mapped_stance_score_breakdown",
                wraps=Module1Calculator.build_rule_mapped_stance_score_breakdown,
            ) as rule_breakdown,
        ):
            diagnostics = Module1Diagnostics(self.result)
            prepared = diagnostics.prepared_filtered_input_columns("weighted")
            weighted = diagnostics.trace_stance_score(
                "weighted",
                include_raw_input=False,
            )
            rule = diagnostics.diagnose_rule_mapped_stance("rule", view="state")

        self.assertEqual(
            list(prepared.columns),
            [
                "feature_a_prepared_for_component_a",
                "feature_a_filtered_for_component_a",
            ],
        )
        pd.testing.assert_series_equal(
            prepared["feature_a_prepared_for_component_a"],
            pd.Series(
                [float("nan"), 0.3, 0.7, 0.0],
                index=self.result.features.index,
                name="feature_a_prepared_for_component_a",
            ),
        )
        pd.testing.assert_series_equal(
            prepared["feature_a_filtered_for_component_a"],
            pd.Series(
                [float("nan"), 0.0, 0.7, 0.0],
                index=self.result.features.index,
                name="feature_a_filtered_for_component_a",
            ),
        )
        self.assertEqual(
            list(weighted.columns),
            [
                "component_a_score",
                "component_b_score",
                "component_a_score_weight",
                "component_a_score_contribution",
                "component_b_score_weight",
                "component_b_score_contribution",
                "weighted_score",
                "weighted_stance",
                "weighted_strength",
                "component_a_label",
                "component_b_label",
            ],
        )
        self.assertEqual(
            list(rule.columns),
            [
                "component_a_score",
                "rule_state_raw",
                "rule_state",
                "rule_state_stabilization_changed",
                "rule_stabilization_changed",
                "rule_case",
                "rule_score",
                "rule_stance",
                "rule_strength",
            ],
        )
        prepare_input.assert_called_once()
        weighted_breakdown.assert_called_once()
        resolve_rule_spec.assert_called_once()
        rule_breakdown.assert_called_once()

        diagnostics.component_config["components"]["component_a"]["score"][
            "output"
        ] = "mutated"
        self.assertEqual(
            self.result.module1_config["components"]["component_a"]["score"][
                "output"
            ],
            "component_a_score",
        )

    def test_historical_analysis_uses_result_snapshot_and_in_memory_context(self):
        event_index = self.result.data.index
        historical_context = {
            "events": pd.DataFrame(
                {
                    "context_id": ["constructed_event"],
                    "start": [event_index[1]],
                    "end": [event_index[2]],
                }
            ),
            "expectations": pd.DataFrame(),
        }

        with (
            patch.object(
                Module1Calculator,
                "__init__",
                side_effect=AssertionError("calculator initialization attempted"),
            ),
            patch.object(
                Module1Calculator,
                "_load_yaml_config",
                side_effect=AssertionError("Module 1 YAML access attempted"),
            ),
            patch.object(
                Module1HistoricalAnalysis,
                "_load_yaml_config",
                side_effect=AssertionError("YAML access attempted"),
            ),
            patch(
                "module1_schema.validate_module1_config",
                side_effect=AssertionError("raw configuration validation attempted"),
            ),
        ):
            historical = Module1HistoricalAnalysis(
                self.result,
                historical_context=historical_context,
            )
            target = historical.analysis.resolve_target(
                "weighted_score",
                "stance",
            )
            context = historical.get_target_context(
                "weighted",
                "stance",
                dependency_level="components",
                context_id="constructed_event",
            )

        self.assertEqual(target.canonical_target, "weighted")
        self.assertEqual(context.context_id, "constructed_event")
        self.assertEqual(
            list(context.data.index),
            list(event_index[1:3]),
        )
        historical.exposure_stance_config["exposure_stances"]["weighted"][
            "score_output"
        ] = "mutated"
        self.assertEqual(
            self.result.module1_config["exposure_stances"]["weighted"][
                "score_output"
            ],
            "weighted_score",
        )

    def test_incomplete_results_fail_with_result_specific_errors(self):
        no_config = replace(self.result, module1_config=None)
        with self.assertRaisesRegex(
            ValueError,
            r"Module1Result\.module1_config is required for feature resolution",
        ):
            Module1Analysis(no_config).get_target_context("feature_a", "feature")

        no_data = replace(self.result, data=None)
        with self.assertRaisesRegex(
            ValueError,
            r"Module1Result\.data is required for raw-input resolution",
        ):
            Module1Analysis(no_data).get_target_context("raw_a", "raw_input")

        no_features = replace(self.result, features=None)
        with self.assertRaisesRegex(
            ValueError,
            r"Module1Result\.features is required for prepared-input diagnostics",
        ):
            Module1Diagnostics(no_features).prepared_filtered_input_columns(
                "weighted"
            )

        no_scores = replace(self.result, scores=None)
        with self.assertRaisesRegex(
            ValueError,
            r"Module1Result\.scores is required for weighted stance diagnostics",
        ):
            Module1Diagnostics(no_scores).trace_stance_score(
                "weighted",
                include_raw_input=False,
            )

        missing_component_score = replace(
            self.result,
            scores=self.result.scores.drop(columns=["component_a_score"]),
        )
        with self.assertRaisesRegex(
            ValueError,
            r"Missing component_score column\(s\) in self\.scores",
        ):
            Module1Analysis(missing_component_score).get_target_context(
                "component_a",
                "component",
            )

        with self.assertRaisesRegex(
            ValueError,
            r"Module1Result\.module1_config is required for historical label validation",
        ):
            Module1HistoricalAnalysis(
                no_config
            )._valid_historical_label_vocabularies()


if __name__ == "__main__":
    unittest.main()
