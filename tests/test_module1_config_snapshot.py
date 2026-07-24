import copy
import os
import unittest
from dataclasses import fields
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import yaml

from module1_analysis import Module1Analysis
from module1_calculator import (
    Module1Calculator,
    RuleMappedStanceSpec,
)
from module1_diagnostics import Module1Diagnostics
from module1_historical_analysis import Module1HistoricalAnalysis
from module1_sensitivity_diagnostics import Module1SensitivityDiagnostics


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


if __name__ == "__main__":
    unittest.main()
