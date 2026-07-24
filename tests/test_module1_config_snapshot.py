import copy
import os
import unittest
from dataclasses import fields
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import yaml

from module1_analysis import Module1Analysis
from module1_calculator import Module1Calculator
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
