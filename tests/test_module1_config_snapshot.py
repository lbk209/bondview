import copy
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import yaml

from module1_analysis import Module1Analysis
from module1_calculator import Module1Calculator


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
        self.assertEqual(
            self.result.feature_config,
            {"features": self.operational_config["features"]},
        )
        self.assertEqual(
            self.result.component_config,
            {"components": self.operational_config["components"]},
        )
        self.assertEqual(
            self.result.exposure_stance_config,
            {
                "stance_label_rules": self.operational_config["stance_label_rules"],
                "exposure_stances": self.operational_config["exposure_stances"],
            },
        )
        self.assertTrue(self.result.module1_config_validation["issues"].empty)

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
            result.component_config["components"]["duration_preference"]["score"][
                "clip"
            ],
            [-99.0, 99.0],
        )

        result.module1_config["horizons"]["rates"] = 777
        result.component_config["components"]["duration_preference"]["score"][
            "clip"
        ] = [-77.0, 77.0]

        self.assertEqual(calculator.module1_config["horizons"]["rates"], 999)
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
