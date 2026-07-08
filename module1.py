import warnings
from dataclasses import dataclass, field, replace
from numbers import Real
from collections.abc import Mapping

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from module1_schema import (
    _parse_rule_scores_n_parts,
    _resolve_rule_mapped_stabilization_config,
    _rule_mapped_bucket_classification_from_score,
)
from module1_analysis import (
    _first_valid_dates_by_column,
    _inspect_module1_result_tables,
    _label_distributions,
    _latest_valid_dates_by_column,
)
from module1_context import (
    TargetCompareDataset,
    TargetContextResult,
    TargetDependency,
    TargetResolution,
)
from module1_calculator import FredSeries, Module1Calculator
from module1_historical_analysis import Module1HistoricalAnalysis
from module1_sensitivity_diagnostics import Module1SensitivityDiagnostics
from module1_result import Module1Result


@dataclass(frozen=True)
class RuleMappedDiagnosticSpec:
    target: str
    function: str
    score_input_cols: tuple[str, ...]
    raw_state_cols: tuple[str, ...]
    stabilized_state_cols: tuple[str, ...]
    rule_case_col: str
    final_score_col: str
    stance_label_col: str
    strength_label_col: str
    component_names: tuple[str, ...] = ()
    stabilization_change_cols: tuple[str, ...] = ()
    stabilization_change_any_col: str | None = None
    base_rule_score_col: str | None = None
    adjustment_col: str | None = None
    adjusted_score_col: str | None = None
    rule_metadata_cols: tuple[str, ...] = ()


@dataclass(frozen=True)
class SmoothingDiagnosticComponentScorePair:
    source_score_col: str
    raw_col: str
    smoothed_col: str
    metric_prefix: str


@dataclass(frozen=True)
class SmoothingDiagnosticContextColumn:
    output_col: str
    feature_col: str | None = None
    data_col: str | None = None


@dataclass(frozen=True)
class SmoothingDiagnosticTargetProfile:
    target: str
    display_target: str
    spec: RuleMappedDiagnosticSpec
    component_score_pairs: tuple[SmoothingDiagnosticComponentScorePair, ...]
    context_columns: tuple[SmoothingDiagnosticContextColumn, ...]
    raw_final_score_col: str
    smoothed_final_score_col: str
    raw_stance_label_col: str
    smoothed_stance_label_col: str
    raw_strength_label_col: str
    smoothed_strength_label_col: str
    score_diff_col: str
    final_score_metric_prefix: str
    score_change_metric_prefix: str


@dataclass(frozen=True)
class _RuleMappedStateInputSpec:
    name: str
    source_score_col: str
    component_name: str
    classification: str
    raw_output_col: str
    stabilized_output_col: str
    stabilization_changed_output_col: str
    values: tuple[str, ...]
    diagnostic_component: str | None = None
    state_buckets: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class _RuleMappedAdjustmentSpec:
    metadata_output_cols: tuple[str, ...] = ()
    adjustment_output_col: str | None = None
    config: dict | None = None


@dataclass(frozen=True)
class _RuleMappedStanceSpec:
    stance_name: str
    function: str
    state_inputs: tuple[_RuleMappedStateInputSpec, ...]
    stabilization_config: dict[str, dict[str, float | int]]
    rule_case_output_col: str
    stabilization_changed_any_output_col: str
    rule_scores: dict[tuple[str, ...], float]
    score_output_col: str
    stance_output_col: str
    strength_output_col: str
    base_rule_score_output_col: str | None = None
    adjustment: _RuleMappedAdjustmentSpec | None = None
    adjusted_score_output_col: str | None = None


@dataclass(frozen=True)
class DiagnosticInputSpec:
    component: str
    source: str
    kind: str
    output: str
    role: str | None = None


class RegimeModule:
    _CALCULATOR_SETUP_FIELDS = (
        "fred",
        "series_config_path",
        "module1_config_path",
        "data_path",
        "series_config",
        "data",
        "module1_config",
        "module1_config_validation",
        "feature_config",
        "component_config",
        "exposure_stance_config",
        "default_horizons",
        "horizon_overrides",
        "horizons",
        "features",
        "scores",
        "labels",
        "stance_scores",
        "exposure_stance",
    )

    def __init__(
        self,
        api_key_env="FRED_API_KEY",
        series_config_path="data/fred_series_config.csv",
        module1_config_path="data/module1_config.yaml",
        data_path="data/raw_data_19980101_20260508.csv",
        horizons=None,
    ):
        """
        Initialize a Module 1 runtime and load the core input files.

        The constructor loads series config, module1 config, and input data, then
        resolves horizons from YAML defaults plus optional constructor overrides.
        It does not calculate features, scores, labels, stances, or load
        historical context. Historical context remains explicit via
        load_historical_context(), except for convenience workflows.
        """
        self.calculator = Module1Calculator(
            api_key_env=api_key_env,
            series_config_path=series_config_path,
            module1_config_path=module1_config_path,
            data_path=data_path,
            horizons=horizons,
        )
        self._sync_setup_from_calculator()
        self.scores = None
        self.labels = None
        self.component_boundaries = None
        self.features = None
        self.historical_context = None
        self.historical_cases = None
        self.historical_expected_label_validation = None
        self.stance_scores = None
        self.exposure_stance = None

    def _sync_setup_from_calculator(self) -> None:
        for field_name in self._CALCULATOR_SETUP_FIELDS:
            setattr(self, field_name, getattr(self.calculator, field_name))

    def _sync_setup_to_calculator(self) -> None:
        for field_name in self._CALCULATOR_SETUP_FIELDS:
            if hasattr(self, field_name):
                setattr(self.calculator, field_name, getattr(self, field_name))

    def _module1_result_for_historical_analysis(self) -> Module1Result:
        return Module1Result(
            data=self.data,
            features=self.features,
            scores=self.scores,
            labels=self.labels,
            stance_scores=self.stance_scores,
            exposure_stance=self.exposure_stance,
            module1_config=self.module1_config,
            feature_config=self.feature_config,
            component_config=self.component_config,
            exposure_stance_config=self.exposure_stance_config,
            horizons=self.horizons,
            default_horizons=self.default_horizons,
            horizon_overrides=self.horizon_overrides,
            module1_config_validation=self.module1_config_validation,
        )

    def _module1_historical_analysis(self) -> Module1HistoricalAnalysis:
        return Module1HistoricalAnalysis(
            self._module1_result_for_historical_analysis(),
            historical_context=self.historical_context,
            historical_cases=self.historical_cases,
            historical_expected_label_validation=(
                self.historical_expected_label_validation
            ),
        )

    def _module1_sensitivity_diagnostics(self) -> Module1SensitivityDiagnostics:
        return Module1SensitivityDiagnostics(
            self._module1_result_for_historical_analysis(),
            historical_context=self.historical_context,
            historical_cases=self.historical_cases,
            historical_expected_label_validation=(
                self.historical_expected_label_validation
            ),
        )

    def _sync_historical_from_analysis(
        self,
        analysis: Module1HistoricalAnalysis,
    ) -> None:
        self.historical_context = analysis.historical_context
        self.historical_cases = analysis.historical_cases
        self.historical_expected_label_validation = (
            analysis.historical_expected_label_validation
        )

    def load_core_files(
        self,
        series_config_path=None,
        module1_config_path=None,
        data_path=None,
    ) -> None:
        """
        Load core Module 1 files, applying optional path overrides.

        Omitted paths use the instance's stored paths and only load missing state.
        Provided paths update the stored path attributes and reload that file.
        """
        self._sync_setup_to_calculator()
        result = self.calculator.load_core_files(
            series_config_path=series_config_path,
            module1_config_path=module1_config_path,
            data_path=data_path,
        )
        self._sync_setup_from_calculator()
        return result

    def _default_horizons_from_config(self, config: dict | None = None) -> dict:
        self._sync_setup_to_calculator()
        return self.calculator._default_horizons_from_config(config)

    def validate_horizons(self, horizons=None, base_horizons=None) -> dict:
        """
        Return validated horizon settings.

        Base horizons come from module1_config.yaml unless base_horizons is
        provided. horizons is treated as a partial override mapping.
        """
        self._sync_setup_to_calculator()
        return self.calculator.validate_horizons(
            horizons=horizons,
            base_horizons=base_horizons,
        )

    def update_horizons(self, horizons: dict | None = None) -> dict:
        """
        Apply instance-level horizon overrides over YAML defaults.

        If horizons are updated after features, scores, or stances have been
        calculated, rerun calculate_features() and downstream steps, or rerun the
        full pipeline.
        """
        self._sync_setup_to_calculator()
        result = self.calculator.update_horizons(horizons)
        self._sync_setup_from_calculator()
        return result


    @classmethod
    def _build_horizon_cases_df(
        cls,
        horizon_cases=None,
        horizon_grid=None,
        max_cases=100,
    ) -> pd.DataFrame:
        return Module1SensitivityDiagnostics._build_horizon_cases_df(
            horizon_cases=horizon_cases,
            horizon_grid=horizon_grid,
            max_cases=max_cases,
        )


    @classmethod
    def compare_horizon_cases(
        cls,
        horizon_cases=None,
        horizon_grid=None,
        base_horizons=None,
        *,
        api_key_env="FRED_API_KEY",
        series_config_path="data/fred_series_config.csv",
        module1_config_path="data/module1_config.yaml",
        data_path="data/raw_data_19980101_20260508.csv",
        historical_context_path="data/historical_context.yaml",
        target=None,
        context_id=None,
        level=None,
        only_use_for_validation=True,
        include_low_relevance=False,
        min_obs=20,
        plausible_threshold=0.70,
        mixed_threshold=0.45,
        output: str = "summary",
        max_cases=100,
    ) -> pd.DataFrame:
        return Module1SensitivityDiagnostics.compare_horizon_cases(
            horizon_cases=horizon_cases,
            horizon_grid=horizon_grid,
            base_horizons=base_horizons,
            api_key_env=api_key_env,
            series_config_path=series_config_path,
            module1_config_path=module1_config_path,
            data_path=data_path,
            historical_context_path=historical_context_path,
            target=target,
            context_id=context_id,
            level=level,
            only_use_for_validation=only_use_for_validation,
            include_low_relevance=include_low_relevance,
            min_obs=min_obs,
            plausible_threshold=plausible_threshold,
            mixed_threshold=mixed_threshold,
            output=output,
            max_cases=max_cases,
        )
        

    def load_series_config(self, path="data/fred_series_config.csv") -> dict:
        self._sync_setup_to_calculator()
        result = self.calculator.load_series_config(path)
        self._sync_setup_from_calculator()
        return result


    def download_series(self, key: str, start=None, end=None) -> pd.Series | None:
        self._sync_setup_to_calculator()
        return self.calculator.download_series(key, start=start, end=end)

        
    def check_frequency_sanity(self, key: str, sr: pd.Series) -> None:
        self._sync_setup_to_calculator()
        return self.calculator.check_frequency_sanity(key, sr)


    def load_local_data(self, path_from, start=None, end=None) -> pd.DataFrame:
        """
        Load previously saved input data from a local CSV file.
    
        The loaded data must contain all columns defined in self.series_config.
        The index is parsed as datetime, sorted, and filtered by start/end.
        """
        self._sync_setup_to_calculator()
        return self.calculator.load_local_data(path_from, start=start, end=end)
    
    
    def load_data(self, path_from=None, start=None, end=None) -> pd.DataFrame:
        """
        Download FRED input data, or load it from a local CSV file if path_from is given.
        """
        self._sync_setup_to_calculator()
        result = self.calculator.load_data(
            path_from=path_from,
            start=start,
            end=end,
        )
        self._sync_setup_from_calculator()
        return result


    def save_data(self, file, overwrite: bool = False):
        """
        Save self.data to CSV.
    
        If overwrite=False and the file already exists, append a numeric suffix:
        data.csv -> data_1.csv -> data_2.csv
        """
        if self.data is None:
            return print("ERROR: No data to save")
    
        path = Path(file)
    
        if path.exists() and not overwrite:
            stem = path.stem
            suffix = path.suffix
            parent = path.parent
    
            i = 1
            while True:
                new_path = parent / f"{stem}_{i}{suffix}"
                if not new_path.exists():
                    path = new_path
                    break
                i += 1
    
        self.data.to_csv(path)
        print(f"Saved data to: {path}")
    
        return None


    def _load_yaml_config(self, path) -> dict:
        return self.calculator._load_yaml_config(path)



    def load_module1_config(
        self,
        path="data/module1_config.yaml",
        validate_config: bool = True,
        raise_on_invalid_config: bool = True,
    ) -> dict:
        """
        Load module1_config.yaml with strict validation by default.

        module1_config.yaml is the source of truth for Module 1 labels,
        thresholds, and output schema. In strict mode, invalid config raises
        ValueError and is not assigned to object state.
        """
        self._sync_setup_to_calculator()
        result = self.calculator.load_module1_config(
            path=path,
            validate_config=validate_config,
            raise_on_invalid_config=raise_on_invalid_config,
        )
        self._sync_setup_from_calculator()
        return result








    def calculate_features(self) -> pd.DataFrame:
        self._sync_setup_to_calculator()
        result = self.calculator.calculate_features()
        self._sync_setup_from_calculator()
        return result





    def _prepare_component_input_series(self, sr: pd.Series, input_preparation: dict | None) -> pd.Series:
        self._sync_setup_to_calculator()
        result = self.calculator._prepare_component_input_series(sr, input_preparation)
        self._sync_setup_from_calculator()
        return result




    def _clip_score(self, sr: pd.Series, clip_config: dict | None) -> pd.Series:
        self._sync_setup_to_calculator()
        result = self.calculator._clip_score(sr, clip_config)
        self._sync_setup_from_calculator()
        return result








    def align_component_scores(self) -> pd.DataFrame:
        self._sync_setup_to_calculator()
        result = self.calculator.align_component_scores()
        self._sync_setup_from_calculator()
        return result


    def _calculate_single_feature_component_score(self, component_name: str, score_config: dict, normalization: str | None, normalization_horizon: str, *, apply_input_preparation: bool=True) -> pd.Series:
        self._sync_setup_to_calculator()
        result = self.calculator._calculate_single_feature_component_score(component_name, score_config, normalization, normalization_horizon, apply_input_preparation=apply_input_preparation)
        self._sync_setup_from_calculator()
        return result


    def _calculate_weighted_feature_component_score(self, component_name: str, score_config: dict, normalization: str | None, normalization_horizon: str, *, apply_input_preparation: bool=True) -> pd.Series:
        self._sync_setup_to_calculator()
        result = self.calculator._calculate_weighted_feature_component_score(component_name, score_config, normalization, normalization_horizon, apply_input_preparation=apply_input_preparation)
        self._sync_setup_from_calculator()
        return result


    def _calculate_curve_move_driver_score(self, component_name: str, score_config: dict, *, apply_input_preparation: bool=True) -> pd.Series:
        self._sync_setup_to_calculator()
        result = self.calculator._calculate_curve_move_driver_score(component_name, score_config, apply_input_preparation=apply_input_preparation)
        self._sync_setup_from_calculator()
        return result

    def _curve_move_driver_bucket_scores(self, bucket_config: dict) -> dict[str, float]:
        self._sync_setup_to_calculator()
        result = self.calculator._curve_move_driver_bucket_scores(bucket_config)
        self._sync_setup_from_calculator()
        return result

    def _component_score_bucket_config(self, component_name: str) -> dict:
        self._sync_setup_to_calculator()
        result = self.calculator._component_score_bucket_config(component_name)
        self._sync_setup_from_calculator()
        return result








    def _resolve_rule_mapped_stance_schema(self, stance_name: str, stance_config: dict) -> _RuleMappedStanceSpec:
        self._sync_setup_to_calculator()
        result = self.calculator._resolve_rule_mapped_stance_schema(stance_name, stance_config)
        self._sync_setup_from_calculator()
        return result



    def _score_bucket(self, score, bucket_config: dict):
        self._sync_setup_to_calculator()
        result = self.calculator._score_bucket(score, bucket_config)
        self._sync_setup_from_calculator()
        return result





    def _calculate_current_state_component_score(self, component_name: str, score_config: dict, *, apply_input_preparation: bool=True) -> pd.Series:
        self._sync_setup_to_calculator()
        result = self.calculator._calculate_current_state_component_score(component_name, score_config, apply_input_preparation=apply_input_preparation)
        self._sync_setup_from_calculator()
        return result












    def calculate_component_scores(self) -> pd.DataFrame:
        self._sync_setup_to_calculator()
        result = self.calculator.calculate_component_scores()
        self._sync_setup_from_calculator()
        return result


    def calculate_component_labels(self) -> pd.DataFrame:
        self._sync_setup_to_calculator()
        result = self.calculator.calculate_component_labels()
        self._sync_setup_from_calculator()
        return result


    def _label_stance_direction(self, score: float, direction_thresholds: dict, labels: dict):
        self._sync_setup_to_calculator()
        result = self.calculator._label_stance_direction(score, direction_thresholds, labels)
        self._sync_setup_from_calculator()
        return result


    def _label_stance_strength(self, score: float, direction_label, direction_labels: dict, strength_thresholds: dict, strength_labels: dict, neutral_strength: str):
        self._sync_setup_to_calculator()
        result = self.calculator._label_stance_strength(score, direction_label, direction_labels, strength_thresholds, strength_labels, neutral_strength)
        self._sync_setup_from_calculator()
        return result


    def _build_weighted_stance_score_breakdown(self, stance_name: str, stance_config: dict) -> pd.DataFrame:
        self._sync_setup_to_calculator()
        result = self.calculator._build_weighted_stance_score_breakdown(stance_name, stance_config)
        self._sync_setup_from_calculator()
        return result







    def _build_rule_mapped_stance_score_breakdown(self, stance_name: str, stance_config: dict, *, stabilization_overrides: dict | None=None) -> pd.DataFrame:
        self._sync_setup_to_calculator()
        result = self.calculator._build_rule_mapped_stance_score_breakdown(stance_name, stance_config, stabilization_overrides=stabilization_overrides)
        self._sync_setup_from_calculator()
        return result






    def _credit_spread_component_thresholds(self) -> dict:
        if self.component_config is None:
            raise ValueError(
                "Run load_module1_config() before calculating credit spread stance."
            )

        components = self.component_config["components"]
        component_thresholds = {}
        for component_name in ["credit_spread_change", "credit_spread_state"]:
            thresholds = (
                components
                .get(component_name, {})
                .get("label", {})
                .get("thresholds", {})
            )
            positive_threshold = thresholds.get("positive")
            negative_threshold = thresholds.get("negative")
            if positive_threshold is None or negative_threshold is None:
                raise ValueError(
                    f"Component {component_name} label thresholds are incomplete."
                )
            component_thresholds[component_name] = {
                "positive": positive_threshold,
                "negative": negative_threshold,
            }

        return component_thresholds


    def _credit_spread_rule_scores(self, stance_config: dict) -> dict:
        rule_scores = stance_config.get("rule_scores")
        if not isinstance(rule_scores, dict) or not rule_scores:
            raise ValueError("Credit stance rule_scores must be a non-empty mapping.")

        parsed_scores = {}
        for pair_key, score in rule_scores.items():
            if not isinstance(pair_key, str) or "|" not in pair_key:
                raise ValueError(
                    f"Credit stance rule score key must use change|level format: {pair_key}"
                )
            change_state, level_state = pair_key.split("|", 1)
            parsed_scores[(change_state, level_state)] = float(score)

        return parsed_scores


    def _credit_stance_state_buckets(self, stance_config: dict) -> dict:
        state_buckets = stance_config.get("state_buckets")
        if not isinstance(state_buckets, dict):
            raise ValueError("Credit stance state_buckets must be a mapping.")

        required_components = ["credit_spread_change", "credit_spread_state"]
        required_states = ["positive", "neutral", "negative"]
        for component_name in required_components:
            component_buckets = state_buckets.get(component_name)
            if not isinstance(component_buckets, dict):
                raise ValueError(
                    f"Credit stance state_buckets.{component_name} must be a mapping."
                )
            for state_name in required_states:
                bucket_name = component_buckets.get(state_name)
                if not isinstance(bucket_name, str) or bucket_name.strip() == "":
                    raise ValueError(
                        "Credit stance state bucket values must be non-empty "
                        f"strings: state_buckets.{component_name}.{state_name}"
                    )

        return state_buckets


    def _credit_spread_rule_adjustments(self, stance_config: dict) -> dict:
        rule_adjustments = stance_config.get("rule_adjustments")
        if not isinstance(rule_adjustments, dict):
            raise ValueError("Credit stance rule_adjustments must be a mapping.")
        if not isinstance(rule_adjustments.get("default_cap"), dict):
            raise ValueError("Credit stance rule_adjustments.default_cap must be a mapping.")
        if not isinstance(rule_adjustments.get("states"), dict):
            raise ValueError("Credit stance rule_adjustments.states must be a mapping.")
        return rule_adjustments


    def _credit_spread_state_intensity(self, value: float, state: str, thresholds: dict, state_buckets: dict) -> float:
        self._sync_setup_to_calculator()
        result = self.calculator._credit_spread_state_intensity(value, state, thresholds, state_buckets)
        self._sync_setup_from_calculator()
        return result


    def _credit_stance_stabilization_config(self, stance_config: dict) -> dict:
        configured = stance_config.get("state_stabilization")
        if not isinstance(configured, dict):
            raise ValueError("Credit stance state_stabilization must be a mapping.")

        resolved = {}
        for component_name in ["credit_spread_change", "credit_spread_state"]:
            component_config = configured.get(component_name)
            if not isinstance(component_config, dict):
                raise ValueError(
                    f"Credit stance state_stabilization.{component_name} must be a mapping."
                )
            if "hysteresis_buffer" not in component_config:
                raise ValueError(
                    f"Credit stance state_stabilization.{component_name}.hysteresis_buffer is required."
                )
            if "min_state_persistence" not in component_config:
                raise ValueError(
                    f"Credit stance state_stabilization.{component_name}.min_state_persistence is required."
                )
            resolved[component_name] = {
                "hysteresis_buffer": float(component_config["hysteresis_buffer"]),
                "min_state_persistence": int(component_config["min_state_persistence"]),
            }

        return resolved






    def _stabilize_state_series(self, score: pd.Series, classify_candidate, *, hysteresis_buffer: float=0.0, min_state_persistence: int=1) -> pd.Series:
        self._sync_setup_to_calculator()
        result = self.calculator._stabilize_state_series(score, classify_candidate, hysteresis_buffer=hysteresis_buffer, min_state_persistence=min_state_persistence)
        self._sync_setup_from_calculator()
        return result


    def _threshold_hysteresis_candidate(self, value: float, *, thresholds: dict, positive_label: str, neutral_label: str, negative_label: str, active_state, hysteresis_buffer: float) -> str:
        self._sync_setup_to_calculator()
        result = self.calculator._threshold_hysteresis_candidate(value, thresholds=thresholds, positive_label=positive_label, neutral_label=neutral_label, negative_label=negative_label, active_state=active_state, hysteresis_buffer=hysteresis_buffer)
        self._sync_setup_from_calculator()
        return result


    def _stabilize_credit_rule_states(
        self,
        change_score: pd.Series,
        state_score: pd.Series,
        component_thresholds: dict,
        stance_config: dict,
    ) -> pd.DataFrame:
        stabilization_config = self._credit_stance_stabilization_config(stance_config)
        state_buckets = self._credit_stance_state_buckets(stance_config)
        change_buckets = state_buckets["credit_spread_change"]
        level_buckets = state_buckets["credit_spread_state"]
        states = pd.DataFrame(index=change_score.index)

        def classify_raw_state(value, thresholds, buckets):
            if value >= thresholds["positive"]:
                return buckets["positive"]
            if value <= thresholds["negative"]:
                return buckets["negative"]
            return buckets["neutral"]

        states["credit_spread_change_state_raw"] = change_score.apply(
            lambda value: (
                pd.NA
                if pd.isna(value)
                else classify_raw_state(
                    value,
                    component_thresholds["credit_spread_change"],
                    change_buckets,
                )
            )
        )
        states["credit_spread_state_category_raw"] = state_score.apply(
            lambda value: (
                pd.NA
                if pd.isna(value)
                else classify_raw_state(
                    value,
                    component_thresholds["credit_spread_state"],
                    level_buckets,
                )
            )
        )

        change_candidate = self._stabilize_state_series(
            change_score,
            lambda value, active_state, hysteresis_buffer: self._threshold_hysteresis_candidate(
                value,
                thresholds=component_thresholds["credit_spread_change"],
                positive_label=change_buckets["positive"],
                neutral_label=change_buckets["neutral"],
                negative_label=change_buckets["negative"],
                active_state=active_state,
                hysteresis_buffer=hysteresis_buffer,
            ),
            hysteresis_buffer=stabilization_config["credit_spread_change"][
                "hysteresis_buffer"
            ],
            min_state_persistence=stabilization_config["credit_spread_change"][
                "min_state_persistence"
            ],
        )
        state_candidate = self._stabilize_state_series(
            state_score,
            lambda value, active_state, hysteresis_buffer: self._threshold_hysteresis_candidate(
                value,
                thresholds=component_thresholds["credit_spread_state"],
                positive_label=level_buckets["positive"],
                neutral_label=level_buckets["neutral"],
                negative_label=level_buckets["negative"],
                active_state=active_state,
                hysteresis_buffer=hysteresis_buffer,
            ),
            hysteresis_buffer=stabilization_config["credit_spread_state"][
                "hysteresis_buffer"
            ],
            min_state_persistence=stabilization_config["credit_spread_state"][
                "min_state_persistence"
            ],
        )

        states["credit_spread_change_state"] = change_candidate
        states["credit_spread_state_category"] = state_candidate

        return states


    def _adjust_credit_spread_rule_score(self, base_score: float, state: tuple[str, str], change_intensity: float, level_intensity: float, rule_adjustments: dict) -> tuple[float, float]:
        self._sync_setup_to_calculator()
        result = self.calculator._adjust_credit_spread_rule_score(base_score, state, change_intensity, level_intensity, rule_adjustments)
        self._sync_setup_from_calculator()
        return result


    def _credit_spread_rule_row_from_states(
        self,
        change_score: float,
        level_score: float,
        change_state: str,
        level_state: str,
        component_thresholds: dict,
        rule_scores: dict,
        state_buckets: dict,
        rule_adjustments: dict,
    ) -> dict:
        if (
            pd.isna(change_score)
            or pd.isna(level_score)
            or pd.isna(change_state)
            or pd.isna(level_state)
        ):
            return {
                "credit_spread_change_state": pd.NA,
                "credit_spread_state_category": pd.NA,
                "credit_state_pair": pd.NA,
                "base_rule_score": pd.NA,
                "credit_spread_change_intensity": pd.NA,
                "credit_spread_state_intensity": pd.NA,
                "rule_adjustment": pd.NA,
                "adjusted_credit_stance_score": pd.NA,
            }

        state_pair = (change_state, level_state)
        base_score = rule_scores[state_pair]
        change_intensity = self._credit_spread_state_intensity(
            change_score,
            change_state,
            component_thresholds["credit_spread_change"],
            state_buckets["credit_spread_change"],
        )
        level_intensity = self._credit_spread_state_intensity(
            level_score,
            level_state,
            component_thresholds["credit_spread_state"],
            state_buckets["credit_spread_state"],
        )
        adjusted_score, rule_adjustment = self._adjust_credit_spread_rule_score(
            base_score,
            state_pair,
            change_intensity,
            level_intensity,
            rule_adjustments,
        )

        return {
            "credit_spread_change_state": change_state,
            "credit_spread_state_category": level_state,
            "credit_state_pair": f"{change_state}|{level_state}",
            "base_rule_score": base_score,
            "credit_spread_change_intensity": change_intensity,
            "credit_spread_state_intensity": level_intensity,
            "rule_adjustment": rule_adjustment,
            "adjusted_credit_stance_score": adjusted_score,
        }




    def calculate_exposure_stance(self) -> pd.DataFrame:
        self._sync_setup_to_calculator()
        result = self.calculator.calculate_exposure_stance()
        self._sync_setup_from_calculator()
        return result


    def run_module1_pipeline(
        self,
    ) -> pd.DataFrame:
        self._sync_setup_to_calculator()
        result = self.calculator.run_module1_pipeline()
        self._sync_setup_from_calculator()
        return result


    def to_module1_result(self) -> Module1Result:
        self._sync_setup_to_calculator()
        result = self.calculator.to_module1_result()
        self._sync_setup_from_calculator()
        return result


    def load_historical_context(self, historical_context_path, validate_expected_labels: bool=True, raise_on_invalid_expected_labels: bool=True) -> dict:
        analysis = self._module1_historical_analysis()
        result = analysis.load_historical_context(historical_context_path, validate_expected_labels, raise_on_invalid_expected_labels)
        self._sync_historical_from_analysis(analysis)
        return result


    def _valid_historical_label_vocabularies(self) -> dict:
        analysis = self._module1_historical_analysis()
        result = analysis._valid_historical_label_vocabularies()
        self._sync_historical_from_analysis(analysis)
        return result


    def _validate_historical_expected_labels_from_cases(self, cases: pd.DataFrame) -> dict:
        analysis = self._module1_historical_analysis()
        result = analysis._validate_historical_expected_labels_from_cases(cases)
        self._sync_historical_from_analysis(analysis)
        return result


    def validate_historical_expected_labels(self, target: str | None=None, context_id: str | None=None, level: str | None=None, only_use_for_validation: bool=False, include_low_relevance: bool=True, raise_on_error: bool=False) -> dict:
        analysis = self._module1_historical_analysis()
        result = analysis.validate_historical_expected_labels(target, context_id, level, only_use_for_validation, include_low_relevance, raise_on_error)
        self._sync_historical_from_analysis(analysis)
        return result


    def _normalize_review_label(self, value):
        analysis = self._module1_historical_analysis()
        result = analysis._normalize_review_label(value)
        self._sync_historical_from_analysis(analysis)
        return result


    def _historical_review_target_aliases(self, level: str | None=None) -> dict:
        analysis = self._module1_historical_analysis()
        result = analysis._historical_review_target_aliases(level)
        self._sync_historical_from_analysis(analysis)
        return result


    def _historical_review_target_groups(self) -> dict:
        analysis = self._module1_historical_analysis()
        result = analysis._historical_review_target_groups()
        self._sync_historical_from_analysis(analysis)
        return result


    def _build_historical_cases(self, events: pd.DataFrame, expectations: pd.DataFrame) -> pd.DataFrame:
        analysis = self._module1_historical_analysis()
        result = analysis._build_historical_cases(events, expectations)
        self._sync_historical_from_analysis(analysis)
        return result


    def _filter_historical_cases_by_target(self, cases: pd.DataFrame, target: str, level: str | None=None) -> pd.DataFrame:
        analysis = self._module1_historical_analysis()
        result = analysis._filter_historical_cases_by_target(cases, target, level)
        self._sync_historical_from_analysis(analysis)
        return result


    def _select_historical_cases(self, target: str | None=None, level: str | None=None, context_id: str | None=None, only_use_for_validation: bool | None=None, include_low_relevance: bool | None=None, *, error_context: str='historical cases', require_non_empty: bool=True) -> pd.DataFrame:
        analysis = self._module1_historical_analysis()
        result = analysis._select_historical_cases(target, level, context_id, only_use_for_validation, include_low_relevance, error_context=error_context, require_non_empty=require_non_empty)
        self._sync_historical_from_analysis(analysis)
        return result


    def _historical_case_to_target_context(self, case: pd.Series, *, dependency_level: str='none', include_labels: bool=True, include_strength: bool=True) -> TargetContextResult:
        analysis = self._module1_historical_analysis()
        result = analysis._historical_case_to_target_context(case, dependency_level=dependency_level, include_labels=include_labels, include_strength=include_strength)
        self._sync_historical_from_analysis(analysis)
        return result


    def _review_flag_from_match_ratio(self, match_ratio, valid_obs: int, min_obs: int, plausible_threshold: float, mixed_threshold: float):
        analysis = self._module1_historical_analysis()
        result = analysis._review_flag_from_match_ratio(match_ratio, valid_obs, min_obs, plausible_threshold, mixed_threshold)
        self._sync_historical_from_analysis(analysis)
        return result


    def _make_historical_case_key(self, case: pd.Series, expected_label_normalized, expected_strength_normalized) -> str:
        analysis = self._module1_historical_analysis()
        result = analysis._make_historical_case_key(case, expected_label_normalized, expected_strength_normalized)
        self._sync_historical_from_analysis(analysis)
        return result


    def _evaluate_historical_case(self, case: pd.Series, min_obs: int=20, plausible_threshold: float=0.7, mixed_threshold: float=0.45) -> dict:
        analysis = self._module1_historical_analysis()
        result = analysis._evaluate_historical_case(case, min_obs, plausible_threshold, mixed_threshold)
        self._sync_historical_from_analysis(analysis)
        return result


    def _build_historical_case_summary_table(self, target: str | None=None, context_id: str | None=None, level: str | None=None, only_use_for_validation: bool=True, include_low_relevance: bool=False, min_obs: int=20, plausible_threshold: float=0.7, mixed_threshold: float=0.45) -> pd.DataFrame:
        analysis = self._module1_historical_analysis()
        result = analysis._build_historical_case_summary_table(target, context_id, level, only_use_for_validation, include_low_relevance, min_obs, plausible_threshold, mixed_threshold)
        self._sync_historical_from_analysis(analysis)
        return result


    def _format_historical_case_summary_view(self, case_summary: pd.DataFrame, view: str='full') -> pd.DataFrame:
        analysis = self._module1_historical_analysis()
        result = analysis._format_historical_case_summary_view(case_summary, view)
        self._sync_historical_from_analysis(analysis)
        return result


    def _build_historical_detail_table(self, target: str | None=None, context_id: str | None=None, level: str | None=None, only_use_for_validation: bool=True, include_low_relevance: bool=False, min_obs: int=20, plausible_threshold: float=0.7, mixed_threshold: float=0.45) -> pd.DataFrame:
        analysis = self._module1_historical_analysis()
        result = analysis._build_historical_detail_table(target, context_id, level, only_use_for_validation, include_low_relevance, min_obs, plausible_threshold, mixed_threshold)
        self._sync_historical_from_analysis(analysis)
        return result


    def _build_historical_review_report(self, case_summary: pd.DataFrame) -> pd.DataFrame:
        analysis = self._module1_historical_analysis()
        result = analysis._build_historical_review_report(case_summary)
        self._sync_historical_from_analysis(analysis)
        return result


    def _build_historical_review_distributions(self, detail: pd.DataFrame) -> dict:
        analysis = self._module1_historical_analysis()
        result = analysis._build_historical_review_distributions(detail)
        self._sync_historical_from_analysis(analysis)
        return result


    def _build_historical_review_windows(self, detail: pd.DataFrame) -> pd.DataFrame:
        analysis = self._module1_historical_analysis()
        result = analysis._build_historical_review_windows(detail)
        self._sync_historical_from_analysis(analysis)
        return result


    def _build_historical_diagnostic_summary(self, case_summary: pd.DataFrame, detail: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
        analysis = self._module1_historical_analysis()
        result = analysis._build_historical_diagnostic_summary(case_summary, detail, windows)
        self._sync_historical_from_analysis(analysis)
        return result


    def review_historical_cases(self, target: str | None=None, context_id: str | None=None, level: str | None=None, only_use_for_validation: bool=True, include_low_relevance: bool=False, min_obs: int=20, plausible_threshold: float=0.7, mixed_threshold: float=0.45, output: str='cases') -> pd.DataFrame:
        analysis = self._module1_historical_analysis()
        result = analysis.review_historical_cases(target, context_id, level, only_use_for_validation, include_low_relevance, min_obs, plausible_threshold, mixed_threshold, output)
        self._sync_historical_from_analysis(analysis)
        return result


    def run_module1_historical_review(self, historical_context_path, target: str | None=None, context_id: str | None=None, level: str | None=None, only_use_for_validation: bool=True, include_low_relevance: bool=False, min_obs: int=20, plausible_threshold: float=0.7, mixed_threshold: float=0.45, output: str='cases') -> pd.DataFrame:
        self.run_module1_pipeline()
        analysis = self._module1_historical_analysis()
        result = analysis.run_module1_historical_review(historical_context_path, target, context_id, level, only_use_for_validation, include_low_relevance, min_obs, plausible_threshold, mixed_threshold, output)
        self._sync_historical_from_analysis(analysis)
        return result


    def _first_valid_dates_by_column(self, table: pd.DataFrame | None) -> pd.Series | None:
        return _first_valid_dates_by_column(table)


    def _latest_valid_dates_by_column(self, table: pd.DataFrame | None) -> pd.Series | None:
        return _latest_valid_dates_by_column(table)


    def _label_distributions(self, table: pd.DataFrame | None) -> dict | None:
        return _label_distributions(table)


    def inspect_module1_results(self, n=10) -> dict:
        """
        Inspect the current Module 1 outputs for sanity checking.
    
        Returns recent snapshots, non-null availability diagnostics, first/latest
        valid dates, latest complete exposure-stance date, and label distributions.
        This is an internal-output inspection tool, not a historical-context review.
        """
        return _inspect_module1_result_tables(
            features=self.features,
            scores=self.scores,
            labels=self.labels,
            exposure_stance=self.exposure_stance,
            n=n,
        )


    def _target_resolution_from_canonical(
        self,
        requested_target: str,
        normalized_target: str,
        level: str,
        canonical_target: str,
        *,
        kind: str = "target",
    ) -> TargetResolution:
        if level == "stance":
            stance_config = self.exposure_stance_config["exposure_stances"][
                canonical_target
            ]
            score_col = stance_config.get("score_output")
            label_col = stance_config.get("stance_output")
            strength_col = stance_config.get("strength_output")
            component_score_cols = tuple(
                item.get("component")
                for item in stance_config.get("inputs", [])
                if item.get("component") is not None
            )
            return TargetResolution(
                requested_target=requested_target,
                normalized_target=normalized_target,
                level="stance",
                kind=kind,
                canonical_target=canonical_target,
                score_col=score_col,
                label_col=label_col,
                strength_col=strength_col,
                config=stance_config,
                related_score_cols=tuple(
                    col for col in [score_col] if col is not None
                ),
                related_label_cols=tuple(
                    col for col in [label_col] if col is not None
                ),
                related_strength_cols=tuple(
                    col for col in [strength_col] if col is not None
                ),
                related_component_score_cols=component_score_cols,
                related_targets=((level, canonical_target),),
                has_stance_score=score_col is not None,
                source_layer="stance",
                source_table="exposure_stance",
                available_output_fields=tuple(
                    col
                    for col in [score_col, label_col, strength_col]
                    if col is not None
                ),
            )

        component_config = self.component_config["components"][canonical_target]
        score_col = component_config.get("score", {}).get("output")
        label_col = component_config.get("label", {}).get("output")
        return TargetResolution(
            requested_target=requested_target,
            normalized_target=normalized_target,
            level="component",
            kind=kind,
            canonical_target=canonical_target,
            score_col=score_col,
            label_col=label_col,
            strength_col=None,
            config=component_config,
            related_score_cols=tuple(col for col in [score_col] if col is not None),
            related_label_cols=tuple(col for col in [label_col] if col is not None),
            related_targets=((level, canonical_target),),
            has_stance_score=False,
            source_layer="component",
            source_table="scores",
            available_output_fields=tuple(
                col for col in [score_col, label_col] if col is not None
            ),
        )


    def _target_resolution_for_raw_input(
        self,
        requested_target: str,
        normalized_target: str,
        canonical_target: str,
    ) -> TargetResolution:
        return TargetResolution(
            requested_target=requested_target,
            normalized_target=normalized_target,
            level="raw_input",
            kind="target",
            canonical_target=canonical_target,
            score_col=canonical_target,
            label_col=None,
            strength_col=None,
            config=None,
            related_score_cols=(canonical_target,),
            related_targets=(("raw_input", canonical_target),),
            source_layer="raw_input",
            source_table="data",
            available_output_fields=(canonical_target,),
        )


    def _target_resolution_for_feature(
        self,
        requested_target: str,
        normalized_target: str,
        canonical_target: str,
    ) -> TargetResolution:
        if self.feature_config is None:
            raise ValueError("Run load_module1_config() before resolving features.")

        feature_def = self.feature_config["features"][canonical_target]
        return TargetResolution(
            requested_target=requested_target,
            normalized_target=normalized_target,
            level="feature",
            kind="target",
            canonical_target=canonical_target,
            score_col=canonical_target,
            label_col=None,
            strength_col=None,
            config=feature_def,
            related_score_cols=(canonical_target,),
            related_targets=(("feature", canonical_target),),
            source_layer="feature",
            source_table="features",
            available_output_fields=(canonical_target,),
        )


    def _normalize_target_level(self, level: str | None) -> str:
        if level is None:
            raise ValueError(
                "Target level is required. Use one of: raw_input, feature, "
                "component, stance."
            )

        normalized_level = self._normalize_review_label(level)
        aliases = {
            "raw": "raw_input",
            "input": "raw_input",
            "inputs": "raw_input",
            "raw_inputs": "raw_input",
            "features": "feature",
            "components": "component",
            "stances": "stance",
        }
        normalized_level = aliases.get(normalized_level, normalized_level)

        if normalized_level not in {"raw_input", "feature", "component", "stance"}:
            raise ValueError(
                f"Unsupported level: {level}. Use one of: raw_input, feature, "
                "component, stance."
            )

        return normalized_level


    def _resolve_target_for_context(self, target: str, level: str) -> TargetResolution:
        normalized_level = self._normalize_target_level(level)
        normalized_target = self._normalize_review_label(target)

        if normalized_level == "raw_input":
            if self.data is None:
                raise ValueError("Run load_data() before resolving raw inputs.")
            matches = {
                self._normalize_review_label(col): col
                for col in self.data.columns
            }
            canonical = matches.get(normalized_target)
            if canonical is None:
                raise ValueError(f"Unknown raw_input target: {target}")
            return self._target_resolution_for_raw_input(
                target,
                normalized_target,
                canonical,
            )

        if normalized_level == "feature":
            if self.feature_config is None:
                raise ValueError("Run load_module1_config() before resolving features.")
            matches = {
                self._normalize_review_label(col): col
                for col in self.feature_config["features"]
            }
            canonical = matches.get(normalized_target)
            if canonical is None:
                raise ValueError(f"Unknown feature target: {target}")
            return self._target_resolution_for_feature(
                target,
                normalized_target,
                canonical,
            )

        return self._resolve_target(target, normalized_level)


    def _resolve_target(
        self,
        target: str,
        level: str | None = None,
        *,
        allow_group: bool = False,
    ) -> TargetResolution:
        """
        Resolve a user-facing target into the canonical internal target shape.

        This helper only identifies what the target refers to under the current
        config. It does not decide whether a caller should plot, diagnose, or
        require stance-specific outputs.
        """
        normalized_level = (
            None if level is None else self._normalize_review_label(level)
        )
        if normalized_level not in {None, "stance", "component"}:
            if level is None:
                raise ValueError(f"Unsupported historical review level: {level}")
            raise ValueError(
                f'level must be either "stance" or "component"; got: {level}'
            )

        normalized_target = self._normalize_review_label(target)
        aliases = self._historical_review_target_aliases(normalized_level)
        groups = self._historical_review_target_groups()

        if normalized_target in groups:
            resolved = []
            group = groups[normalized_target]
            levels = (
                ["component", "stance"]
                if normalized_level is None
                else [normalized_level]
            )

            for level_name in levels:
                level_aliases = (
                    aliases
                    if normalized_level == level_name
                    else self._historical_review_target_aliases(level_name)
                )
                for member in group.get(level_name, []):
                    canonical = level_aliases.get(self._normalize_review_label(member))
                    if canonical is not None:
                        resolved.append(canonical)

            resolved = tuple(sorted(set(resolved)))
            if not resolved:
                if normalized_level is None:
                    raise ValueError(
                        f"Unable to resolve historical review target group: {target} "
                        f"for level={level}."
                    )
                raise ValueError(
                    f"Unable to resolve target group '{target}' for "
                    f"level='{normalized_level}'."
                )
            if allow_group:
                has_stance_score = any(
                    level_name == "stance" for level_name, _ in resolved
                )
                related_score_cols = []
                related_label_cols = []
                related_strength_cols = []
                related_component_score_cols = []
                for level_name, canonical_target in resolved:
                    member = self._target_resolution_from_canonical(
                        target,
                        normalized_target,
                        level_name,
                        canonical_target,
                        kind="target_group_member",
                    )
                    related_score_cols.extend(member.related_score_cols)
                    related_label_cols.extend(member.related_label_cols)
                    related_strength_cols.extend(member.related_strength_cols)
                    related_component_score_cols.extend(
                        member.related_component_score_cols
                    )
                return TargetResolution(
                    requested_target=target,
                    normalized_target=normalized_target,
                    level=normalized_level,
                    kind="target_group",
                    canonical_target=None,
                    score_col=None,
                    label_col=None,
                    strength_col=None,
                    config=None,
                    related_score_cols=tuple(dict.fromkeys(related_score_cols)),
                    related_label_cols=tuple(dict.fromkeys(related_label_cols)),
                    related_strength_cols=tuple(dict.fromkeys(related_strength_cols)),
                    related_component_score_cols=tuple(
                        dict.fromkeys(related_component_score_cols)
                    ),
                    related_targets=resolved,
                    supported=True,
                    has_stance_score=has_stance_score,
                    source_layer="target_group",
                    source_table=None,
                    available_output_fields=tuple(
                        dict.fromkeys(
                            related_score_cols
                            + related_label_cols
                            + related_strength_cols
                        )
                    ),
                )
            if len(resolved) > 1:
                available = [canonical_target for _, canonical_target in resolved]
                raise ValueError(
                    f"Target group '{target}' is ambiguous for "
                    f"level='{normalized_level}'. Matching targets: {available}. "
                    "Use a more specific target."
                )

            resolved_level, canonical_target = resolved[0]
            return self._target_resolution_from_canonical(
                target,
                normalized_target,
                resolved_level,
                canonical_target,
                kind="target_group_member",
            )

        canonical = aliases.get(normalized_target)
        if canonical is None:
            available = sorted(aliases)
            level_for_error = (
                "historical review" if normalized_level is None else normalized_level
            )
            raise ValueError(
                f"Unable to resolve {level_for_error} target: {target}. "
                f"Available targets and aliases: {available}"
            )

        resolved_level, canonical_target = canonical
        return self._target_resolution_from_canonical(
            target,
            normalized_target,
            resolved_level,
            canonical_target,
        )

    def _features_for_component_score(self, component_score: str) -> list[str]:
        """
        Return feature names used by the component score output column.
        """
        if self.component_config is None:
            raise ValueError("Run load_module1_config() first.")

        for component_name, component_config in self.component_config["components"].items():
            score_config = component_config.get("score", {})

            if score_config.get("output") != component_score:
                continue

            function = score_config.get("function")

            if function == "single_feature_score":
                feature = score_config.get("input")
                return [] if feature is None else [feature]

            if function == "weighted_feature_score":
                return [
                    item["feature"]
                    for item in score_config.get("inputs", [])
                    if "feature" in item
                ]

            if function == "curve_move_driver_score":
                return [
                    item["feature"]
                    for item in score_config.get("inputs", [])
                    if "feature" in item
                ]

            raise ValueError(
                f"Unsupported score function for {component_name}: {function}"
            )

        raise ValueError(f"Component score not found in component_config: {component_score}")


    def _raw_input_dependencies_for_feature(
        self,
        feature_name: str,
        visited=None,
    ) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
        if visited is None:
            visited = set()

        if feature_name in visited:
            raise ValueError(f"Circular feature dependency detected: {feature_name}")

        visited.add(feature_name)

        if self.data is not None and feature_name in self.data.columns:
            return (feature_name,), {feature_name: (feature_name,)}

        if self.feature_config is None:
            raise ValueError("Run load_module1_config() first.")

        feature_defs = self.feature_config["features"]

        if feature_name not in feature_defs:
            raise ValueError(f"Feature not found in feature_config: {feature_name}")

        definition = feature_defs[feature_name]
        method = definition.get("method")

        if method in {"change", "pct_change", "level"}:
            input_name = definition.get("input")
            if input_name is None:
                raise ValueError(f"Feature {feature_name} is missing input.")

            raw_inputs, dependency_map = self._raw_input_dependencies_for_feature(
                input_name,
                visited,
            )
            dependency_map = dependency_map.copy()
            dependency_map[feature_name] = raw_inputs
            return raw_inputs, dependency_map

        if method == "spread":
            inputs = definition.get("inputs")
            if not isinstance(inputs, list) or len(inputs) != 2:
                raise ValueError(
                    f"Spread feature {feature_name} requires exactly two inputs."
                )

            raw_inputs = []
            dependency_map = {}
            for input_name in inputs:
                input_raw_inputs, input_dependency_map = (
                    self._raw_input_dependencies_for_feature(
                        input_name,
                        visited.copy(),
                    )
                )
                raw_inputs.extend(input_raw_inputs)
                dependency_map.update(input_dependency_map)

            raw_inputs = tuple(dict.fromkeys(raw_inputs))
            dependency_map[feature_name] = raw_inputs
            return raw_inputs, dependency_map

        raise ValueError(f"Unsupported feature method for {feature_name}: {method}")


    def _dependencies_for_resolution(
        self,
        resolution: TargetResolution,
        *,
        dependency_level: str = "raw_inputs",
    ) -> TargetDependency:
        normalized_dependency_level = self._normalize_dependency_level(
            resolution.level,
            dependency_level,
        )

        if resolution.kind == "target_group":
            component_score_cols = []
            component_label_cols = []
            feature_cols = []
            raw_input_cols = []
            feature_dependency_map = {}

            for level, canonical_target in resolution.related_targets:
                member = self._target_resolution_from_canonical(
                    resolution.requested_target,
                    resolution.normalized_target,
                    level,
                    canonical_target,
                    kind="target_group_member",
                )
                member_dependency = self._dependencies_for_resolution(
                    member,
                    dependency_level=normalized_dependency_level,
                )
                component_score_cols.extend(member_dependency.component_score_cols)
                component_label_cols.extend(member_dependency.component_label_cols)
                feature_cols.extend(member_dependency.feature_cols)
                raw_input_cols.extend(member_dependency.raw_input_cols)
                feature_dependency_map.update(
                    member_dependency.feature_dependency_map
                )

            return TargetDependency(
                resolution=resolution,
                target_members=resolution.related_targets,
                component_score_cols=tuple(dict.fromkeys(component_score_cols)),
                component_label_cols=tuple(dict.fromkeys(component_label_cols)),
                feature_cols=tuple(dict.fromkeys(feature_cols)),
                raw_input_cols=tuple(sorted(dict.fromkeys(raw_input_cols))),
                feature_dependency_map=feature_dependency_map,
                supported=resolution.supported,
            )

        if resolution.level == "raw_input":
            if normalized_dependency_level not in {"none"}:
                raise ValueError(
                    "raw_input targets do not have lower-level dependencies."
                )
            return TargetDependency(
                resolution=resolution,
                target_members=resolution.related_targets,
                supported=resolution.supported,
            )

        if resolution.level == "feature":
            feature_cols = tuple(
                col
                for col in [resolution.score_col]
                if col is not None and normalized_dependency_level == "full"
            )
            raw_input_cols = []
            feature_dependency_map = {}
            if normalized_dependency_level in {"raw_inputs", "full"}:
                raw_inputs, feature_dependency_map = (
                    self._raw_input_dependencies_for_feature(
                        resolution.canonical_target
                    )
                )
                raw_input_cols.extend(raw_inputs)

            return TargetDependency(
                resolution=resolution,
                target_members=resolution.related_targets,
                feature_cols=feature_cols,
                raw_input_cols=tuple(sorted(dict.fromkeys(raw_input_cols))),
                feature_dependency_map=feature_dependency_map,
                supported=resolution.supported,
            )

        if normalized_dependency_level == "none":
            return TargetDependency(
                resolution=resolution,
                target_members=resolution.related_targets,
                supported=resolution.supported,
            )

        if resolution.level == "stance":
            component_score_cols = resolution.related_component_score_cols
            component_label_cols = tuple(
                self._component_label_columns_for_scores(list(component_score_cols))
            )
        elif resolution.level == "component":
            component_score_cols = tuple(
                col for col in [resolution.score_col] if col is not None
            )
            component_label_cols = tuple(
                col for col in [resolution.label_col] if col is not None
            )
        else:
            component_score_cols = ()
            component_label_cols = ()

        feature_cols = []
        raw_input_cols = []
        feature_dependency_map = {}

        if normalized_dependency_level in {"features", "raw_inputs", "full"}:
            for component_score_col in component_score_cols:
                component_features = self._features_for_component_score(
                    component_score_col
                )
                feature_cols.extend(component_features)

        if normalized_dependency_level in {"raw_inputs", "full"}:
            for feature_name in feature_cols:
                feature_raw_inputs, feature_map = (
                    self._raw_input_dependencies_for_feature(feature_name)
                )
                raw_input_cols.extend(feature_raw_inputs)
                feature_dependency_map.update(feature_map)

        return TargetDependency(
            resolution=resolution,
            target_members=resolution.related_targets,
            component_score_cols=tuple(dict.fromkeys(component_score_cols)),
            component_label_cols=tuple(dict.fromkeys(component_label_cols)),
            feature_cols=tuple(dict.fromkeys(feature_cols)),
            raw_input_cols=tuple(sorted(dict.fromkeys(raw_input_cols))),
            feature_dependency_map=feature_dependency_map,
            supported=resolution.supported,
        )


    def _normalize_dependency_level(
        self,
        target_level: str | None,
        dependency_level: str | None,
    ) -> str:
        requested = "auto" if dependency_level is None else str(dependency_level)
        normalized = self._normalize_review_label(requested)
        if normalized == "labels":
            raise ValueError(
                'dependency_level="labels" is not supported. Labels are selected '
                "with include_labels, not as a dependency level."
            )

        aliases = {
            "raw": "raw_inputs",
            "raw_input": "raw_inputs",
            "inputs": "raw_inputs",
            "component": "components",
            "feature": "features",
            "none": "none",
        }
        normalized = aliases.get(normalized, normalized)

        if target_level == "raw_input":
            if normalized in {"auto", "none"}:
                return "none"
            raise ValueError("raw_input targets do not have lower-level dependencies.")

        if target_level == "feature":
            if normalized == "auto":
                return "raw_inputs"
            if normalized in {"none", "raw_inputs", "full"}:
                return normalized
            if normalized in {"components", "stances", "stance"}:
                raise ValueError(
                    f"feature targets cannot request {dependency_level} dependencies."
                )
            raise ValueError(f"Unsupported dependency_level for feature: {dependency_level}")

        if target_level == "component":
            if normalized == "auto":
                return "features"
            if normalized in {"none", "features", "raw_inputs", "full"}:
                return normalized
            if normalized in {"stance", "stances", "components"}:
                raise ValueError(
                    f"component targets cannot request {dependency_level} dependencies."
                )
            raise ValueError(
                f"Unsupported dependency_level for component: {dependency_level}"
            )

        if target_level == "stance":
            if normalized == "auto":
                return "components"
            if normalized in {
                "none",
                "components",
                "features",
                "raw_inputs",
                "full",
            }:
                return normalized
            if normalized in {"stance", "stances"}:
                raise ValueError(
                    f"stance targets cannot request {dependency_level} dependencies."
                )
            raise ValueError(f"Unsupported dependency_level for stance: {dependency_level}")

        raise ValueError(f"Unsupported target level: {target_level}")


    def _required_output_table(
        self,
        table_name: str,
        *,
        purpose: str,
    ) -> pd.DataFrame:
        table = getattr(self, table_name)
        if table is not None:
            return table

        missing_steps = {
            "data": "load_data()",
            "features": "calculate_features()",
            "scores": "calculate_component_scores()",
            "labels": "calculate_component_labels()",
            "exposure_stance": "calculate_exposure_stance()",
        }
        step = missing_steps.get(table_name, f"create {table_name}")
        raise ValueError(f"Run {step} before {purpose}; missing self.{table_name}.")


    def _window_series_or_frame(self, obj, start=None, end=None):
        if obj is None:
            return None
        result = obj.copy()
        if start is not None:
            result = result.loc[result.index >= pd.to_datetime(start)]
        if end is not None:
            result = result.loc[result.index <= pd.to_datetime(end)]
        return result


    def _add_context_frame(
        self,
        parts: list[pd.DataFrame],
        column_roles: dict[str, str],
        source_layer_mapping: dict[str, str],
        source_column_mapping: dict[str, str],
        frame: pd.DataFrame | None,
        *,
        role: str,
        source_layer: str,
        source_table: str,
        columns: list[str],
        target_list: list[str],
    ) -> None:
        if frame is None or not columns:
            return

        missing = [col for col in columns if col not in frame.columns]
        if missing:
            raise ValueError(
                f"Missing {source_layer} column(s) in self.{source_table}: {missing}"
            )

        available_cols = [col for col in columns if col not in column_roles]
        if not available_cols:
            return

        parts.append(frame[available_cols].copy())
        for col in available_cols:
            column_roles[col] = role
            source_layer_mapping[col] = source_layer
            source_column_mapping[col] = f"{source_table}.{col}"
            target_list.append(col)


    def _resolved_path_metadata(
        self,
        resolution: TargetResolution,
        dependency: TargetDependency,
    ) -> dict:
        return {
            "target_members": dependency.target_members,
            "component_scores": dependency.component_score_cols,
            "component_labels": dependency.component_label_cols,
            "features": dependency.feature_cols,
            "raw_inputs": dependency.raw_input_cols,
            "feature_to_raw_inputs": dependency.feature_dependency_map,
            "supported": dependency.supported,
            "target_level": resolution.level,
        }


    def _get_target_context_explicit_window(
        self,
        target,
        level,
        dependency_level="auto",
        include_labels=True,
        include_strength=True,
        start=None,
        end=None,
        ffill_inputs=True,
    ) -> TargetContextResult:
        """
        Build target outputs and lower-level dependencies for explicit dates.

        This helper is result-only: it does not resolve historical context IDs,
        calculate outputs, or mutate runtime state.
        """
        normalized_level = self._normalize_target_level(level)
        normalized_dependency_level = self._normalize_dependency_level(
            normalized_level,
            dependency_level,
        )

        resolution = self._resolve_target_for_context(target, normalized_level)
        dependency = self._dependencies_for_resolution(
            resolution,
            dependency_level=normalized_dependency_level,
        )

        parts = []
        column_roles = {}
        source_layer_mapping = {}
        source_column_mapping = {}
        target_columns = []
        component_score_columns = []
        component_label_columns = []
        feature_columns = []
        raw_input_columns = []
        label_columns = []
        strength_columns = []

        if normalized_level == "raw_input":
            data = self._required_output_table("data", purpose="target context retrieval")
            frame = self._window_series_or_frame(data, start, end)
            self._add_context_frame(
                parts,
                column_roles,
                source_layer_mapping,
                source_column_mapping,
                frame,
                role="target_raw_input",
                source_layer="raw_input",
                source_table="data",
                columns=[resolution.score_col],
                target_list=target_columns,
            )

        if normalized_level == "feature":
            features = self._required_output_table(
                "features",
                purpose="target context retrieval",
            )
            frame = self._window_series_or_frame(features, start, end)
            self._add_context_frame(
                parts,
                column_roles,
                source_layer_mapping,
                source_column_mapping,
                frame,
                role="target_feature",
                source_layer="feature",
                source_table="features",
                columns=[resolution.score_col],
                target_list=target_columns,
            )
            feature_columns.extend(target_columns)

        if normalized_level == "component":
            scores = self._required_output_table(
                "scores",
                purpose="target context retrieval",
            )
            score_frame = self._window_series_or_frame(scores, start, end)
            self._add_context_frame(
                parts,
                column_roles,
                source_layer_mapping,
                source_column_mapping,
                score_frame,
                role="target_component_score",
                source_layer="component_score",
                source_table="scores",
                columns=[resolution.score_col],
                target_list=target_columns,
            )
            component_score_columns.extend(target_columns)
            if include_labels and resolution.label_col is not None:
                labels = self._required_output_table(
                    "labels",
                    purpose="target context retrieval",
                )
                label_frame = self._window_series_or_frame(labels, start, end)
                self._add_context_frame(
                    parts,
                    column_roles,
                    source_layer_mapping,
                    source_column_mapping,
                    label_frame,
                    role="target_component_label",
                    source_layer="component_label",
                    source_table="labels",
                    columns=[resolution.label_col],
                    target_list=label_columns,
                )
                component_label_columns.extend(label_columns)

        if normalized_level == "stance":
            exposure_stance = self._required_output_table(
                "exposure_stance",
                purpose="target context retrieval",
            )
            stance_frame = self._window_series_or_frame(exposure_stance, start, end)
            self._add_context_frame(
                parts,
                column_roles,
                source_layer_mapping,
                source_column_mapping,
                stance_frame,
                role="target_stance_score",
                source_layer="stance_score",
                source_table="exposure_stance",
                columns=[resolution.score_col],
                target_list=target_columns,
            )
            if include_labels and resolution.label_col is not None:
                self._add_context_frame(
                    parts,
                    column_roles,
                    source_layer_mapping,
                    source_column_mapping,
                    stance_frame,
                    role="target_stance_label",
                    source_layer="stance_label",
                    source_table="exposure_stance",
                    columns=[resolution.label_col],
                    target_list=label_columns,
                )
            if include_strength and resolution.strength_col is not None:
                self._add_context_frame(
                    parts,
                    column_roles,
                    source_layer_mapping,
                    source_column_mapping,
                    stance_frame,
                    role="target_stance_strength",
                    source_layer="stance_strength",
                    source_table="exposure_stance",
                    columns=[resolution.strength_col],
                    target_list=strength_columns,
                )

        should_include_components = normalized_dependency_level in {
            "components",
            "full",
        }
        if normalized_level == "stance" and should_include_components:
            scores = self._required_output_table(
                "scores",
                purpose="target context retrieval",
            )
            score_frame = self._window_series_or_frame(scores, start, end)
            self._add_context_frame(
                parts,
                column_roles,
                source_layer_mapping,
                source_column_mapping,
                score_frame,
                role="component_score",
                source_layer="component_score",
                source_table="scores",
                columns=list(dependency.component_score_cols),
                target_list=component_score_columns,
            )
            if include_labels and dependency.component_label_cols:
                labels = self._required_output_table(
                    "labels",
                    purpose="target context retrieval",
                )
                label_frame = self._window_series_or_frame(labels, start, end)
                self._add_context_frame(
                    parts,
                    column_roles,
                    source_layer_mapping,
                    source_column_mapping,
                    label_frame,
                    role="component_label",
                    source_layer="component_label",
                    source_table="labels",
                    columns=list(dependency.component_label_cols),
                    target_list=component_label_columns,
                )
                label_columns.extend(
                    col for col in component_label_columns if col not in label_columns
                )

        should_include_features = normalized_dependency_level in {
            "features",
            "full",
        }
        if normalized_level in {"component", "stance"} and should_include_features:
            features = self._required_output_table(
                "features",
                purpose="target context retrieval",
            )
            feature_frame = self._window_series_or_frame(features, start, end)
            self._add_context_frame(
                parts,
                column_roles,
                source_layer_mapping,
                source_column_mapping,
                feature_frame,
                role="feature",
                source_layer="feature",
                source_table="features",
                columns=list(dependency.feature_cols),
                target_list=feature_columns,
            )

        should_include_raw_inputs = normalized_dependency_level in {
            "raw_inputs",
            "full",
        }
        if should_include_raw_inputs and dependency.raw_input_cols:
            data = self._required_output_table("data", purpose="target context retrieval")
            raw_frame = self._window_series_or_frame(data, start, end)
            if ffill_inputs:
                raw_frame = raw_frame.ffill()
            self._add_context_frame(
                parts,
                column_roles,
                source_layer_mapping,
                source_column_mapping,
                raw_frame,
                role="raw_input",
                source_layer="raw_input",
                source_table="data",
                columns=list(dependency.raw_input_cols),
                target_list=raw_input_columns,
            )

        data = pd.concat(parts, axis=1) if parts else pd.DataFrame()
        data = data.loc[:, ~data.columns.duplicated()]

        resolution_metadata = resolution.to_target_info()
        resolution_metadata.update(
            {
                "requested_target": resolution.requested_target,
                "normalized_target": resolution.normalized_target,
                "kind": resolution.kind,
                "related_targets": resolution.related_targets,
            }
        )
        request_metadata = {
            "requested_dependency_level": dependency_level,
            "effective_dependency_level": normalized_dependency_level,
            "include_labels": include_labels,
            "include_strength": include_strength,
            "context_id": None,
            "start": start,
            "end": end,
        }
        resolved_path_metadata = self._resolved_path_metadata(resolution, dependency)
        returned_columns = {
            "target": tuple(dict.fromkeys(target_columns)),
            "component_scores": tuple(dict.fromkeys(component_score_columns)),
            "component_labels": tuple(dict.fromkeys(component_label_columns)),
            "features": tuple(dict.fromkeys(feature_columns)),
            "raw_inputs": tuple(dict.fromkeys(raw_input_columns)),
            "labels": tuple(dict.fromkeys(label_columns)),
            "strength": tuple(dict.fromkeys(strength_columns)),
        }
        metadata = {
            "target": target,
            "level": normalized_level,
            "ffill_inputs": ffill_inputs,
            "column_roles": column_roles,
        }

        return TargetContextResult(
            resolution=resolution_metadata,
            request=request_metadata,
            resolved_path=resolved_path_metadata,
            returned_columns=returned_columns,
            data=data,
            source_layer_mapping=source_layer_mapping,
            source_column_mapping=source_column_mapping,
            start=start,
            end=end,
            context_id=None,
            metadata=metadata,
        )


    def get_target_context(
        self,
        target,
        level,
        dependency_level="auto",
        include_labels=True,
        include_strength=True,
        context_id=None,
        start=None,
        end=None,
        ffill_inputs=True,
    ) -> TargetContextResult:
        """
        Retrieve target outputs and lower-level dependencies without display modes.

        This is the shared, consumer-neutral retrieval interface for plots,
        diagnostics, reports, documentation, and future utilities. It only reads
        already-generated output tables and never calculates features, component
        scores, labels, or exposure stances.
        """
        start, end = self._resolve_historical_event_window(context_id, start, end)
        ctx = self._get_target_context_explicit_window(
            target,
            level,
            dependency_level=dependency_level,
            include_labels=include_labels,
            include_strength=include_strength,
            start=start,
            end=end,
            ffill_inputs=ffill_inputs,
        )

        if context_id is None:
            return ctx

        request_metadata = ctx.request.copy()
        request_metadata["context_id"] = context_id
        return replace(
            ctx,
            request=request_metadata,
            context_id=context_id,
        )


    def _resolve_target_compare(
        self,
        level: str,
        compare: str | None,
    ) -> tuple[str, str]:
        target_level = self._normalize_target_level(level)
        requested = "auto" if compare is None else str(compare)
        normalized_compare = self._normalize_review_label(requested)

        supported = {"auto", "components", "features", "raw_inputs", "full"}
        if normalized_compare not in supported:
            raise ValueError(
                f"Unsupported compare value: {compare}. Use one of: auto, "
                "components, features, raw_inputs, full."
            )

        if target_level == "raw_input":
            raise ValueError(
                "raw_input targets do not have a lower comparison layer."
            )

        if normalized_compare == "auto":
            effective = {
                "feature": "raw_inputs",
                "component": "features",
                "stance": "components",
            }[target_level]
            return normalized_compare, effective

        if target_level == "feature":
            if normalized_compare in {"components", "features"}:
                raise ValueError(
                    f"feature targets cannot compare against {compare}."
                )
            return normalized_compare, normalized_compare

        if target_level == "component":
            if normalized_compare == "components":
                raise ValueError("component targets cannot compare against components.")
            return normalized_compare, normalized_compare

        if target_level == "stance":
            return normalized_compare, normalized_compare

        raise ValueError(f"Unsupported target level: {level}")


    def _comparison_normalization_recommendation(
        self,
        target_level: str,
        effective_compare: str,
        comparison_columns: tuple[str, ...],
        source_layer_mapping: dict[str, str],
    ) -> bool:
        if not comparison_columns:
            return False
        if target_level == "stance" and effective_compare == "components":
            return False
        if effective_compare == "full":
            comparison_layers = {
                source_layer_mapping.get(col)
                for col in comparison_columns
            }
            return not comparison_layers.issubset({"component_score"})
        return effective_compare in {"features", "raw_inputs"}


    def build_target_comparison_dataset(
        self,
        target,
        level,
        compare="auto",
        context_id=None,
        start=None,
        end=None,
        include_labels=True,
        include_strength=True,
        ffill_inputs=True,
    ) -> TargetCompareDataset:
        """
        Build a consumer-neutral target comparison dataset from target context.

        This compare-based path is independent of legacy plot modes and does not
        perform plot normalization.
        """
        target_level = self._normalize_target_level(level)
        requested_compare, effective_compare = self._resolve_target_compare(
            target_level,
            compare,
        )
        dependency_level = effective_compare
        ctx = self.get_target_context(
            target,
            target_level,
            dependency_level=dependency_level,
            include_labels=include_labels,
            include_strength=include_strength,
            context_id=context_id,
            start=start,
            end=end,
            ffill_inputs=ffill_inputs,
        )

        returned = ctx.returned_columns
        target_columns = tuple(returned.get("target", ()))
        if effective_compare == "components":
            comparison_columns = tuple(returned.get("component_scores", ()))
        elif effective_compare == "features":
            comparison_columns = tuple(returned.get("features", ()))
        elif effective_compare == "raw_inputs":
            comparison_columns = tuple(returned.get("raw_inputs", ()))
        elif effective_compare == "full":
            comparison_columns = tuple(
                dict.fromkeys(
                    tuple(returned.get("component_scores", ()))
                    + tuple(returned.get("features", ()))
                    + tuple(returned.get("raw_inputs", ()))
                )
            )
        else:
            raise ValueError(f"Unsupported effective compare value: {effective_compare}")

        target_set = set(target_columns)
        comparison_columns = tuple(
            col for col in comparison_columns if col not in target_set
        )
        label_columns = tuple(returned.get("labels", ())) if include_labels else ()
        strength_columns = (
            tuple(returned.get("strength", ())) if include_strength else ()
        )

        for group_name, columns in {
            "target_columns": target_columns,
            "comparison_columns": comparison_columns,
            "label_columns": label_columns,
            "strength_columns": strength_columns,
        }.items():
            missing = [col for col in columns if col not in ctx.data.columns]
            if missing:
                raise ValueError(
                    f"{group_name} contains columns not present in comparison data: "
                    f"{missing}"
                )

        comparison_source_layers = {
            col: ctx.source_layer_mapping.get(col)
            for col in comparison_columns
        }
        normalization_recommendation = self._comparison_normalization_recommendation(
            target_level,
            effective_compare,
            comparison_columns,
            ctx.source_layer_mapping,
        )
        metadata = {
            "requested_compare": requested_compare,
            "effective_compare": effective_compare,
            "dependency_level": dependency_level,
            "target_level": target_level,
            "canonical_target": ctx.resolution.get("canonical_target"),
            "target_source_layer": ctx.resolution.get("source_layer"),
            "target_source_table": ctx.resolution.get("source_table"),
            "comparison_source_layers": comparison_source_layers,
            "normalization_recommendation": normalization_recommendation,
            "returned_columns": returned,
            "resolved_path": ctx.resolved_path,
        }

        return TargetCompareDataset(
            data=ctx.data,
            target_columns=target_columns,
            comparison_columns=comparison_columns,
            label_columns=label_columns,
            strength_columns=strength_columns,
            returned_columns=returned,
            resolved_path=ctx.resolved_path,
            resolution=ctx.resolution,
            compare=requested_compare,
            effective_compare=effective_compare,
            target_level=target_level,
            source_layer_mapping=ctx.source_layer_mapping,
            source_column_mapping=ctx.source_column_mapping,
            start=ctx.start,
            end=ctx.end,
            context_id=ctx.context_id,
            metadata=metadata,
        )


    def raw_inputs_for_target(self, target: str, level: str) -> list[str]:
        """
        Return raw input columns used directly or indirectly by a target.
        """
        retrieval = self.get_target_context(
            target,
            level,
            dependency_level="raw_inputs",
            include_labels=False,
            include_strength=False,
        )
        return list(retrieval.returned_columns["raw_inputs"])


    def _resolve_historical_event_window(self, context_id=None, start=None, end=None):
        """
        Resolve optional historical context boundaries for diagnostics/plotting.

        context_id lookup requires historical context to have been loaded
        explicitly with load_historical_context().
        """
        if context_id is None:
            return start, end

        if self.historical_context is None:
            raise ValueError(
                "Run load_historical_context() before using context_id-based diagnostics."
            )

        events = self.historical_context["events"]
        matched_events = events[events["context_id"] == context_id]

        if matched_events.empty:
            raise ValueError(f"Unknown historical context_id: {context_id}")

        event = matched_events.iloc[0]
        if start is None:
            start = event["start"]
        if end is None:
            end = event["end"]

        return start, end


    def _diagnostic_input_column_name(
        self,
        source: str,
        kind: str,
        component: str,
    ) -> str:
        if kind not in {"prepared", "filtered"}:
            raise ValueError(f"Unsupported diagnostic input kind: {kind}")
        return f"{source}_{kind}_for_{component}"

    def _component_by_score_output(self) -> dict[str, str]:
        if self.component_config is None:
            raise ValueError("Run load_module1_config() before resolving component outputs.")

        return {
            component.get("score", {}).get("output"): component_name
            for component_name, component in self.component_config["components"].items()
            if component.get("score", {}).get("output") is not None
        }

    def _diagnostic_component_filter_for_target(
        self,
        target: str | None,
    ) -> set[str] | None:
        component_names = self._diagnostic_component_names_for_target(target)
        return None if component_names is None else set(component_names)

    def _diagnostic_component_names_for_target(
        self,
        target: str | None,
    ) -> tuple[str, ...] | None:
        if target is None:
            return None
        if self.exposure_stance_config is None:
            raise ValueError("Run load_module1_config() before prepared-input diagnostics.")

        stance_config = self.exposure_stance_config["exposure_stances"].get(target)
        if stance_config is None:
            raise ValueError(f"Unknown prepared-input diagnostic target: {target}")

        component_by_score_output = self._component_by_score_output()
        component_names = set()
        for item in stance_config.get("inputs", []):
            if not isinstance(item, dict):
                continue
            score_output = item.get("component")
            component_name = component_by_score_output.get(score_output)
            if component_name is not None:
                component_names.add(component_name)
        return tuple(
            component_name
            for component_name in component_by_score_output.values()
            if component_name in component_names
        )

    def _score_input_features_for_diagnostic_component(
        self,
        component_name: str,
        score_config: dict,
    ) -> tuple[str, ...]:
        input_name = score_config.get("input")
        if input_name is not None:
            return (input_name,)

        inputs = score_config.get("inputs")
        if not isinstance(inputs, list):
            return ()

        return tuple(
            item.get("feature")
            for item in inputs
            if isinstance(item, dict) and item.get("feature") is not None
        )

    def _score_input_features_for_diagnostic_components(
        self,
        component_names: tuple[str, ...],
    ) -> tuple[str, ...]:
        if self.component_config is None:
            raise ValueError("Run load_module1_config() before prepared-input diagnostics.")

        features = []
        seen = set()
        components = self.component_config["components"]
        for component_name in component_names:
            score_config = components[component_name].get("score", {})
            for feature in self._score_input_features_for_diagnostic_component(
                component_name,
                score_config,
            ):
                if feature not in seen:
                    features.append(feature)
                    seen.add(feature)
        return tuple(features)

    def _diagnostic_input_specs(
        self,
        target: str | None = None,
        *,
        kinds: tuple[str, ...] = ("prepared", "filtered"),
    ) -> tuple[DiagnosticInputSpec, ...]:
        if self.component_config is None:
            raise ValueError("Run load_module1_config() before prepared-input diagnostics.")

        components = self.component_config["components"]
        target_component_filter = self._diagnostic_component_filter_for_target(target)
        specs = []
        requested_kinds = set(kinds)
        for component_name, component in components.items():
            if (
                target_component_filter is not None
                and component_name not in target_component_filter
            ):
                continue

            diagnostics = component.get("diagnostics") or {}
            prepared_inputs = diagnostics.get("prepared_inputs") or {}
            if prepared_inputs.get("enabled") is not True:
                continue

            score_config = component.get("score", {})
            sources = self._score_input_features_for_diagnostic_component(
                component_name,
                score_config,
            )
            if not sources:
                raise ValueError(
                    "Prepared-input diagnostics are enabled but no score input "
                    f"feature is configured for component: {component_name}"
                )

            input_roles = prepared_inputs.get("input_roles") or {}
            for source in sources:
                role = input_roles.get(source)
                if "prepared" in requested_kinds:
                    specs.append(
                        DiagnosticInputSpec(
                            component=component_name,
                            source=source,
                            kind="prepared",
                            role=role,
                            output=self._diagnostic_input_column_name(
                                source,
                                "prepared",
                                component_name,
                            ),
                        )
                    )
                input_preparation = score_config.get("input_preparation") or {}
                if (
                    "filtered" in requested_kinds
                    and input_preparation.get("min_abs_value") is not None
                ):
                    specs.append(
                        DiagnosticInputSpec(
                            component=component_name,
                            source=source,
                            kind="filtered",
                            role=role,
                            output=self._diagnostic_input_column_name(
                                source,
                                "filtered",
                                component_name,
                            ),
                        )
                    )
        return tuple(specs)

    def _diagnostic_input_spec(
        self,
        target: str,
        component: str,
        source: str,
        kind: str,
        role: str | None = None,
    ) -> DiagnosticInputSpec:
        matches = [
            spec
            for spec in self._diagnostic_input_specs(
                target,
                kinds=("prepared", "filtered"),
            )
            if spec.component == component
            and spec.source == source
            and spec.kind == kind
            and (role is None or spec.role == role)
        ]
        if len(matches) != 1:
            raise ValueError(
                "Expected exactly one prepared/filtered diagnostic input spec for "
                f"{target} {component} {source} {kind}, found {len(matches)}."
            )
        return matches[0]

    def _diagnostic_input_spec_by_role(
        self,
        target: str,
        component: str,
        kind: str,
        role: str,
    ) -> DiagnosticInputSpec:
        matches = [
            spec
            for spec in self._diagnostic_input_specs(
                target,
                kinds=("prepared", "filtered"),
            )
            if spec.component == component
            and spec.kind == kind
            and spec.role == role
        ]
        if len(matches) != 1:
            raise ValueError(
                "Expected exactly one prepared/filtered diagnostic input spec for "
                f"{target} {component} {kind} role={role}, found {len(matches)}."
            )
        return matches[0]

    def _prepared_filtered_input_columns(self, target: str) -> pd.DataFrame:
        if self.features is None:
            raise ValueError("Run calculate_features() before prepared-input diagnostics.")
        if self.component_config is None:
            raise ValueError("Run load_module1_config() before prepared-input diagnostics.")

        components = self.component_config["components"]
        specs = self._diagnostic_input_specs(
            target,
            kinds=("prepared", "filtered"),
        )
        prepared = pd.DataFrame(index=self.features.index)

        prepared_specs = [spec for spec in specs if spec.kind == "prepared"]
        for spec in prepared_specs:
            if spec.source not in self.features.columns:
                continue
            score_config = components.get(spec.component, {}).get("score", {})
            prepared[spec.output] = self._prepare_component_input_series(
                self.features[spec.source],
                score_config.get("input_preparation"),
            )

        for spec in (spec for spec in specs if spec.kind == "filtered"):
            source_spec = self._diagnostic_input_spec(
                target,
                spec.component,
                spec.source,
                "prepared",
                role=spec.role,
            )
            if source_spec.output not in prepared.columns:
                continue
            score_config = components.get(spec.component, {}).get("score", {})
            input_preparation = score_config.get("input_preparation") or {}
            min_abs_value = input_preparation.get("min_abs_value")
            if min_abs_value is None:
                continue
            prepared[spec.output] = prepared[source_spec.output].mask(
                prepared[source_spec.output].abs() < min_abs_value,
                0.0,
            )

        return prepared




    def _component_label_columns_for_scores(
        self,
        component_score_cols: list[str],
    ) -> list[str]:
        if self.component_config is None:
            raise ValueError("Run load_module1_config() before stance diagnostics.")

        label_cols = []
        for component_score_col in component_score_cols:
            for component in self.component_config["components"].values():
                score_output = component.get("score", {}).get("output")
                if score_output != component_score_col:
                    continue

                label_output = component.get("label", {}).get("output")
                if label_output is not None:
                    label_cols.append(label_output)
                break
            else:
                raise ValueError(
                    "Unable to resolve component label for score column: "
                    f"{component_score_col}"
                )

        return label_cols

    def _trace_weighted_stance_score(
        self,
        stance_name: str,
        stance_config: dict,
        context_id: str | None = None,
        start=None,
        end=None,
        include_raw_input: bool = True,
        include_labels: bool = True,
    ) -> pd.DataFrame:
        if self.scores is None:
            raise ValueError(
                "Run calculate_component_scores() before _trace_weighted_stance_score()."
            )
        if self.exposure_stance is None:
            raise ValueError(
                "Run calculate_exposure_stance() before _trace_weighted_stance_score()."
            )
        if self.component_config is None:
            raise ValueError(
                "Run load_module1_config() before _trace_weighted_stance_score()."
            )
        if self.exposure_stance_config is None:
            raise ValueError(
                "Run load_module1_config() before _trace_weighted_stance_score()."
            )
        if include_labels and self.labels is None:
            raise ValueError(
                "Run calculate_component_labels() before _trace_weighted_stance_score(include_labels=True)."
            )

        ctx = self.get_target_context(
            target=stance_name,
            level="stance",
            dependency_level="full" if include_raw_input else "components",
            include_labels=True,
            include_strength=True,
        )
        score_output = ctx.resolution.get("score_col") or stance_config.get("score_output")
        stance_output = ctx.resolution.get("label_col") or stance_config.get("stance_output")
        strength_output = (
            ctx.resolution.get("strength_col")
            or stance_config.get("strength_output")
        )
        required_stance_cols = [score_output, stance_output, strength_output]
        missing_stance_cols = [
            col
            for col in required_stance_cols
            if col is None or col not in ctx.data.columns
        ]
        if missing_stance_cols:
            raise ValueError(
                f"Exposure stance outputs are missing for {stance_name}: "
                f"{missing_stance_cols}"
            )

        diagnostics = self._build_weighted_stance_score_breakdown(
            stance_name,
            stance_config,
        )
        diagnostics = pd.concat(
            [
                diagnostics,
                ctx.data[[stance_output, strength_output]].reindex(
                    diagnostics.index
                ),
            ],
            axis=1,
        )

        if include_labels:
            label_cols = list(ctx.returned_columns["component_labels"])
            missing_label_cols = [
                col for col in label_cols if col not in ctx.data.columns
            ]
            if missing_label_cols:
                raise ValueError(
                    f"Component labels are missing for {stance_name}: "
                    f"{missing_label_cols}"
                )
            diagnostics = pd.concat(
                [diagnostics, ctx.data[label_cols].reindex(diagnostics.index)],
                axis=1,
            )

        if include_raw_input:
            raw_inputs = list(ctx.returned_columns["raw_inputs"])
            missing_raw_inputs = [
                col for col in raw_inputs if col not in ctx.data.columns
            ]
            if missing_raw_inputs:
                raise ValueError(
                    f"Raw input columns are unavailable for {stance_name}: "
                    f"{missing_raw_inputs}"
                )
            if raw_inputs:
                diagnostics = pd.concat(
                    [
                        diagnostics,
                        ctx.data[raw_inputs].reindex(diagnostics.index),
                    ],
                    axis=1,
                )

        start, end = self._resolve_historical_event_window(context_id, start, end)
        if start is not None:
            diagnostics = diagnostics.loc[diagnostics.index >= pd.to_datetime(start)]
        if end is not None:
            diagnostics = diagnostics.loc[diagnostics.index <= pd.to_datetime(end)]

        return diagnostics

    def _resolve_rule_mapped_diagnostic_config(self, target: str) -> dict:
        if target is None or str(target).strip() == "":
            raise ValueError("target must be a non-empty stance identifier.")

        target_info = self._resolve_target(target, level="stance")
        stance_name = target_info.canonical_target
        stance_config = target_info.config
        function = stance_config.get("function") if stance_config else None
        if not isinstance(stance_config, Mapping) or "rule_mapped" not in stance_config:
            raise ValueError(
                f"Unsupported rule-mapped stance diagnostic target {target}: "
                f"{function}. Schema-backed rule_mapped config is required."
            )
        rule_mapped_spec = self._resolve_rule_mapped_stance_schema(
            stance_name,
            stance_config,
        )
        score_input_cols = tuple(
            state_input.source_score_col
            for state_input in rule_mapped_spec.state_inputs
        )
        return {
            "target_info": target_info,
            "stance_name": stance_name,
            "stance_config": stance_config,
            "function": function,
            "score_input_cols": score_input_cols,
            "final_score_col": target_info.score_col or stance_config["score_output"],
            "stance_label_col": target_info.label_col or stance_config["stance_output"],
            "strength_label_col": (
                target_info.strength_col or stance_config["strength_output"]
            ),
            "rule_mapped_spec": rule_mapped_spec,
        }

    def _derive_rule_mapped_diagnostic_spec_from_context(
        self,
        context: dict,
    ) -> RuleMappedDiagnosticSpec:
        stance_name = context["stance_name"]
        function = context["function"]
        rule_mapped_spec = context.get("rule_mapped_spec")
        adjustment = rule_mapped_spec.adjustment

        return RuleMappedDiagnosticSpec(
            target=stance_name,
            function=function,
            score_input_cols=tuple(
                state_input.source_score_col
                for state_input in rule_mapped_spec.state_inputs
            ),
            raw_state_cols=tuple(
                state_input.raw_output_col
                for state_input in rule_mapped_spec.state_inputs
            ),
            stabilized_state_cols=tuple(
                state_input.stabilized_output_col
                for state_input in rule_mapped_spec.state_inputs
            ),
            rule_case_col=rule_mapped_spec.rule_case_output_col,
            final_score_col=context["final_score_col"],
            stance_label_col=context["stance_label_col"],
            strength_label_col=context["strength_label_col"],
            component_names=tuple(
                state_input.diagnostic_component or state_input.component_name
                for state_input in rule_mapped_spec.state_inputs
            ),
            stabilization_change_cols=tuple(
                state_input.stabilization_changed_output_col
                for state_input in rule_mapped_spec.state_inputs
            ),
            stabilization_change_any_col=(
                rule_mapped_spec.stabilization_changed_any_output_col
            ),
            base_rule_score_col=rule_mapped_spec.base_rule_score_output_col,
            adjustment_col=(
                adjustment.adjustment_output_col
                if adjustment is not None
                else None
            ),
            adjusted_score_col=rule_mapped_spec.adjusted_score_output_col,
            rule_metadata_cols=(
                adjustment.metadata_output_cols
                if adjustment is not None
                else ()
            ),
        )

    def _trace_rule_mapped_stance_score(
        self,
        target: str,
        context_id: str | None = None,
        start=None,
        end=None,
        include_raw_input: bool = True,
        include_labels: bool = True,
    ) -> pd.DataFrame:
        if self.scores is None:
            raise ValueError(
                "Run calculate_component_scores() before rule-mapped stance diagnostics."
            )
        if self.exposure_stance is None:
            raise ValueError(
                "Run calculate_exposure_stance() before rule-mapped stance diagnostics."
            )
        if self.exposure_stance_config is None:
            raise ValueError(
                "Run load_module1_config() before rule-mapped stance diagnostics."
            )
        if include_labels and self.labels is None:
            raise ValueError(
                "Run calculate_component_labels() before rule-mapped stance "
                "diagnostics with include_labels=True."
            )

        context = self._resolve_rule_mapped_diagnostic_config(target)
        spec = self._derive_rule_mapped_diagnostic_spec_from_context(context)
        target_info = self._resolve_target(spec.target, level="stance")
        stance_config = target_info.config
        ctx = self.get_target_context(
            target=spec.target,
            level="stance",
            dependency_level="full" if include_raw_input else "components",
            include_labels=True,
            include_strength=True,
        )
        required_stance_cols = [
            spec.final_score_col,
            spec.stance_label_col,
            spec.strength_label_col,
        ]
        missing_stance_cols = [
            col
            for col in required_stance_cols
            if col is None or col not in ctx.data.columns
        ]
        if missing_stance_cols:
            raise ValueError(
                f"Rule-mapped stance outputs are missing for {spec.target}: "
                f"{missing_stance_cols}"
            )

        diagnostics = self._build_rule_mapped_stance_score_breakdown(
            spec.target,
            stance_config,
        )
        diagnostics = pd.concat(
            [
                diagnostics,
                ctx.data[[spec.stance_label_col, spec.strength_label_col]].reindex(
                    diagnostics.index
                ),
            ],
            axis=1,
        )

        if include_labels:
            label_cols = list(ctx.returned_columns["component_labels"])
            missing_label_cols = [
                col for col in label_cols if col not in ctx.data.columns
            ]
            if missing_label_cols:
                raise ValueError(
                    f"Component labels are missing for {spec.target}: "
                    f"{missing_label_cols}"
                )
            diagnostics = pd.concat(
                [diagnostics, ctx.data[label_cols].reindex(diagnostics.index)],
                axis=1,
            )

        if include_raw_input:
            context_parts = self._rule_mapped_trace_context_parts(
                spec,
                ctx,
                diagnostics.index,
            )
            if context_parts:
                diagnostics = pd.concat([diagnostics, *context_parts], axis=1)

        start, end = self._resolve_historical_event_window(context_id, start, end)
        if start is not None:
            diagnostics = diagnostics.loc[diagnostics.index >= pd.to_datetime(start)]
        if end is not None:
            diagnostics = diagnostics.loc[diagnostics.index <= pd.to_datetime(end)]

        return diagnostics

    def _ensure_rule_mapped_stabilization_change_flags(
        self,
        diagnostics: pd.DataFrame,
        spec: RuleMappedDiagnosticSpec,
    ) -> pd.DataFrame:
        missing_change_cols = [
            col for col in spec.stabilization_change_cols if col not in diagnostics.columns
        ]
        missing_any_col = (
            spec.stabilization_change_any_col is not None
            and spec.stabilization_change_any_col not in diagnostics.columns
        )
        if not missing_change_cols and not missing_any_col:
            return diagnostics

        diagnostics = diagnostics.copy()
        derived_cols = []
        for raw_col, state_col, changed_col in zip(
            spec.raw_state_cols,
            spec.stabilized_state_cols,
            spec.stabilization_change_cols,
        ):
            if changed_col not in diagnostics.columns:
                diagnostics[changed_col] = (
                    diagnostics[raw_col] != diagnostics[state_col]
                ) & diagnostics[raw_col].notna()
            derived_cols.append(changed_col)

        if missing_any_col:
            diagnostics[spec.stabilization_change_any_col] = diagnostics[
                derived_cols
            ].any(axis=1)

        return diagnostics

    def _rule_mapped_trace_context_parts(
        self,
        spec: RuleMappedDiagnosticSpec,
        ctx: TargetContextResult,
        index: pd.Index,
    ) -> list[pd.DataFrame]:
        if spec.target == "credit":
            context_parts = []
            feature_cols = list(ctx.returned_columns["features"])
            raw_input_cols = list(ctx.returned_columns["raw_inputs"])
            if "baa10y_change" in feature_cols:
                context_parts.append(ctx.data[["baa10y_change"]].reindex(index))
            if "baa10y" in raw_input_cols:
                context_parts.append(ctx.data[["baa10y"]].reindex(index))
            context_parts.append(
                self._prepared_filtered_input_columns(spec.target).reindex(index)
            )
            return context_parts

        if spec.target == "curve_positioning":
            context_cols = [
                col
                for col in ["dgs2", "dgs10"]
                if col in ctx.returned_columns["raw_inputs"]
            ]
            component_names = self._diagnostic_component_names_for_target(spec.target)
            feature_cols = (
                self._score_input_features_for_diagnostic_components(
                    tuple(reversed(component_names))
                )
                if component_names is not None
                else ()
            )
            context_cols.extend(
                col
                for col in feature_cols
                if col in ctx.returned_columns["features"]
            )
            context_parts = []
            if context_cols:
                context_parts.append(ctx.data[context_cols].reindex(index))
            context_parts.append(
                self._prepared_filtered_input_columns(spec.target).reindex(index)
            )
            return context_parts

        raw_inputs = list(ctx.returned_columns["raw_inputs"])
        missing_raw_inputs = [col for col in raw_inputs if col not in ctx.data.columns]
        if missing_raw_inputs:
            raise ValueError(
                f"Raw input columns are unavailable for {spec.target}: "
                f"{missing_raw_inputs}"
            )
        if raw_inputs:
            return [ctx.data[raw_inputs].reindex(index)]
        return []

    def _duration_rule_stance_config(self) -> dict:
        if self.exposure_stance_config is None:
            raise ValueError("Run load_module1_config() before duration diagnostics.")

        stance_config = self.exposure_stance_config["exposure_stances"].get("duration")
        if stance_config is None:
            raise ValueError("Duration exposure stance config is missing.")
        if stance_config.get("function") != "duration_rule_stance":
            raise ValueError("Active duration stance is not duration_rule_stance.")
        return stance_config

    def _rule_mapped_selected_columns(
        self,
        spec: RuleMappedDiagnosticSpec,
        diagnostics: pd.DataFrame,
        *,
        include_scores: bool = True,
        include_raw_states: bool = True,
        include_stabilized_states: bool = True,
        include_rule_case: bool = True,
        include_labels: bool = True,
    ) -> list[str]:
        selected_cols = []
        if include_scores:
            selected_cols.extend(spec.score_input_cols)
        if include_raw_states:
            selected_cols.extend(spec.raw_state_cols)
        if include_stabilized_states:
            selected_cols.extend(spec.stabilized_state_cols)
            selected_cols.extend(spec.stabilization_change_cols)
            if spec.stabilization_change_any_col is not None:
                selected_cols.append(spec.stabilization_change_any_col)
        if include_rule_case:
            selected_cols.append(spec.rule_case_col)
            if spec.base_rule_score_col is not None:
                selected_cols.append(spec.base_rule_score_col)
            if spec.adjustment_col is not None:
                selected_cols.append(spec.adjustment_col)
            if spec.adjusted_score_col is not None:
                selected_cols.append(spec.adjusted_score_col)
            selected_cols.append(spec.final_score_col)
            selected_cols.extend(spec.rule_metadata_cols)
        if include_labels:
            selected_cols.extend([spec.stance_label_col, spec.strength_label_col])

        return [
            col
            for idx, col in enumerate(selected_cols)
            if col in diagnostics.columns and col not in selected_cols[:idx]
        ]

    def diagnose_rule_mapped_stance(
        self,
        target: str,
        context_id: str | None = None,
        start=None,
        end=None,
        *,
        include_scores: bool = True,
        include_raw_states: bool = True,
        include_stabilized_states: bool = True,
        include_rule_case: bool = True,
        include_labels: bool = True,
        view: str = "state",
    ) -> pd.DataFrame | dict:
        """
        Unified public entry point for rule-mapped stance diagnostics.

        Supported views:

        - ``view="state"``: point/row-level rule-mapped stance diagnostics.
        - ``view="transitions"``: transition-focused diagnostics.
        - ``view="stability"``: period-level stability/churn summary.

        Different views may return different object types. The state and
        transitions views return DataFrames; the stability view returns a dict of
        summary DataFrames.

        Future plan: the detailed boundary between state diagnostics, transition
        diagnostics, and stability summaries may be refined later. This change
        only centralizes access through one public entry point and preserves the
        existing outputs.
        """
        allowed_views = {"state", "transitions", "stability"}
        if view not in allowed_views:
            allowed = ", ".join(
                f'"{allowed_view}"' for allowed_view in sorted(allowed_views)
            )
            raise ValueError(
                f"Unsupported rule-mapped stance diagnostic view {view!r}. "
                f"Allowed values are: {allowed}."
            )

        context = self._resolve_rule_mapped_diagnostic_config(target)
        spec = self._derive_rule_mapped_diagnostic_spec_from_context(context)
        if view != "state":
            include_scores = False
            include_raw_states = True
            include_stabilized_states = True
            include_rule_case = True
            include_labels = True

        diagnostics = self._trace_rule_mapped_stance_score(
            spec.target,
            context_id=context_id,
            start=start,
            end=end,
            include_raw_input=False,
            include_labels=False,
        )
        diagnostics = self._ensure_rule_mapped_stabilization_change_flags(
            diagnostics,
            spec,
        )
        selected_cols = self._rule_mapped_selected_columns(
            spec,
            diagnostics,
            include_scores=include_scores,
            include_raw_states=include_raw_states,
            include_stabilized_states=include_stabilized_states,
            include_rule_case=include_rule_case,
            include_labels=include_labels,
        )
        diagnostics = diagnostics[selected_cols].copy()

        if view == "state":
            return diagnostics
        if view == "transitions":
            return self._diagnose_rule_mapped_stance_transitions(diagnostics, spec)
        return self._summarize_rule_mapped_stance_stability(diagnostics, spec)

    def _diagnose_rule_mapped_stance_transitions(
        self,
        diagnostics: pd.DataFrame,
        spec: RuleMappedDiagnosticSpec,
    ) -> pd.DataFrame:
        """
        Build transition diagnostics from precomputed unified state diagnostics.
        """
        transitions = pd.DataFrame(index=diagnostics.index)
        transitions["date"] = diagnostics.index
        for raw_col, state_col in zip(spec.raw_state_cols, spec.stabilized_state_cols):
            transitions[raw_col] = diagnostics[raw_col]
            transitions[state_col] = diagnostics[state_col]
        transitions[spec.rule_case_col] = diagnostics[spec.rule_case_col]
        transitions[f"previous_{spec.rule_case_col}"] = diagnostics[
            spec.rule_case_col
        ].shift(1)
        transitions[f"{spec.rule_case_col}_changed"] = (
            diagnostics[spec.rule_case_col]
            != transitions[f"previous_{spec.rule_case_col}"]
        ) & diagnostics[spec.rule_case_col].notna()
        transitions[spec.final_score_col] = diagnostics[spec.final_score_col]
        transitions[f"previous_{spec.final_score_col}"] = diagnostics[
            spec.final_score_col
        ].shift(1)
        transitions[f"{spec.final_score_col}_change"] = (
            diagnostics[spec.final_score_col]
            - transitions[f"previous_{spec.final_score_col}"]
        )
        transitions[spec.stance_label_col] = diagnostics[spec.stance_label_col]
        transitions[spec.strength_label_col] = diagnostics[spec.strength_label_col]
        if spec.stabilization_change_any_col is not None:
            transitions[spec.stabilization_change_any_col] = diagnostics[
                spec.stabilization_change_any_col
            ]

        first_valid = diagnostics[spec.rule_case_col].first_valid_index()
        if first_valid is not None:
            transitions.loc[first_valid, f"{spec.rule_case_col}_changed"] = False

        return transitions

    def _rule_mapped_component_state_summary(
        self,
        diagnostics: pd.DataFrame,
        spec: RuleMappedDiagnosticSpec,
    ) -> pd.DataFrame:
        component_rows = []
        for idx, (raw_col, state_col) in enumerate(
            zip(spec.raw_state_cols, spec.stabilized_state_cols)
        ):
            component = (
                spec.component_names[idx]
                if idx < len(spec.component_names)
                else state_col
            )
            changed_col = (
                spec.stabilization_change_cols[idx]
                if idx < len(spec.stabilization_change_cols)
                else None
            )
            valid_raw = diagnostics[raw_col].dropna()
            valid_state = diagnostics[state_col].dropna()
            if changed_col is not None and changed_col in diagnostics.columns:
                valid_changed = diagnostics[changed_col].dropna()
                changed_count = int(diagnostics[changed_col].sum())
                change_ratio = (
                    changed_count / int(valid_changed.shape[0])
                    if int(valid_changed.shape[0])
                    else pd.NA
                )
            else:
                changed_count = pd.NA
                change_ratio = pd.NA
            raw_count = int(valid_raw.shape[0])
            component_rows.append(
                {
                    "component": component,
                    "raw_state_transition_count": self._count_series_changes(
                        diagnostics[raw_col]
                    ),
                    "stabilized_state_transition_count": self._count_series_changes(
                        diagnostics[state_col]
                    ),
                    "stabilization_changed_count": changed_count,
                    "stabilization_change_ratio": change_ratio,
                    "most_frequent_raw_state": (
                        valid_raw.mode().iloc[0] if not valid_raw.empty else pd.NA
                    ),
                    "most_frequent_stabilized_state": (
                        valid_state.mode().iloc[0] if not valid_state.empty else pd.NA
                    ),
                    "valid_raw_state_count": raw_count,
                    "valid_stabilized_state_count": int(valid_state.shape[0]),
                }
            )

        return pd.DataFrame(component_rows)

    def _series_value_shares(self, series: pd.Series, prefix: str) -> dict:
        valid = series.dropna()
        valid_count = int(valid.shape[0])
        shares = {}
        if valid_count:
            for value, count in valid.value_counts().items():
                shares[f"{prefix}_{value}_share"] = float(count / valid_count)
        return shares

    def _rule_mapped_score_distribution(
        self,
        diagnostics: pd.DataFrame,
        spec: RuleMappedDiagnosticSpec,
    ) -> pd.DataFrame:
        valid_score = diagnostics[spec.final_score_col].dropna()
        counts = valid_score.value_counts().sort_index()
        distribution = counts.rename_axis(spec.final_score_col).reset_index(name="count")
        distribution["share"] = (
            distribution["count"] / int(valid_score.shape[0])
            if int(valid_score.shape[0])
            else pd.NA
        )
        return distribution

    def _summarize_rule_mapped_stance_stability(
        self,
        diagnostics: pd.DataFrame,
        spec: RuleMappedDiagnosticSpec,
    ) -> dict:
        """
        Build stability summaries from precomputed unified state diagnostics.
        """
        valid_cases = diagnostics[spec.rule_case_col].dropna()
        case_counts = valid_cases.value_counts()
        score = diagnostics[spec.final_score_col].dropna()
        stance = diagnostics[spec.stance_label_col].dropna()
        strength = diagnostics[spec.strength_label_col].dropna()
        stance_count = int(stance.shape[0])
        strength_count = int(strength.shape[0])

        rule_case_summary = {
            f"{spec.rule_case_col}_transition_count": self._count_series_changes(
                diagnostics[spec.rule_case_col]
            ),
            "unique_rule_case_count": int(valid_cases.nunique()),
            "most_frequent_rule_case": (
                case_counts.index[0] if not case_counts.empty else pd.NA
            ),
            "most_frequent_rule_case_ratio": (
                float(case_counts.iloc[0] / len(valid_cases))
                if len(valid_cases)
                else pd.NA
            ),
            "valid_rule_case_count": int(len(valid_cases)),
        }
        score_summary = {
            "score_mean": score.mean() if not score.empty else pd.NA,
            "score_median": score.median() if not score.empty else pd.NA,
            "score_min": score.min() if not score.empty else pd.NA,
            "score_max": score.max() if not score.empty else pd.NA,
            "score_std": score.std() if not score.empty else pd.NA,
            "valid_score_count": int(score.shape[0]),
            "valid_stance_count": stance_count,
            "valid_strength_count": strength_count,
        }
        score_summary.update(self._series_value_shares(stance, "stance"))
        score_summary.update(self._series_value_shares(strength, "strength"))

        if spec.target == "duration":
            stance_config = self._duration_rule_stance_config()
            positive_label = stance_config["labels"]["direction"].get("positive")
            neutral_label = stance_config["labels"]["direction"].get("neutral")
            negative_label = stance_config["labels"]["direction"].get("negative")
            score_summary.update(
                {
                    "positive_stance_share": (
                        float((stance == positive_label).sum() / stance_count)
                        if stance_count
                        else pd.NA
                    ),
                    "neutral_stance_share": (
                        float((stance == neutral_label).sum() / stance_count)
                        if stance_count
                        else pd.NA
                    ),
                    "negative_stance_share": (
                        float((stance == negative_label).sum() / stance_count)
                        if stance_count
                        else pd.NA
                    ),
                }
            )

        return {
            "component_state_summary": self._rule_mapped_component_state_summary(
                diagnostics,
                spec,
            ),
            "rule_case_summary": pd.DataFrame([rule_case_summary]),
            "mapped_score_distribution": self._rule_mapped_score_distribution(
                diagnostics,
                spec,
            ),
            "score_summary": pd.DataFrame([score_summary]),
        }

    def _curve_positioning_stance_config(self) -> dict:
        if self.exposure_stance_config is None:
            raise ValueError("Run load_module1_config() before curve diagnostics.")

        stance_config = self.exposure_stance_config["exposure_stances"].get(
            "curve_positioning"
        )
        if stance_config is None:
            raise ValueError("Curve positioning stance config is missing.")

        return stance_config

    def _rule_mapped_trace_supported_functions(self) -> set[str]:
        return {
            "duration_rule_stance",
            "credit_spread_stance",
            "curve_positioning_stance",
        }

    def trace_stance_score(
        self,
        target: str,
        context_id: str | None = None,
        start=None,
        end=None,
        include_raw_input: bool = True,
        include_labels: bool = True,
    ) -> pd.DataFrame:
        """
        Explain how a Module 1 stance score was generated.
        """
        if target is None or str(target).strip() == "":
            raise ValueError("target must be a non-empty stance identifier.")

        target_info = self._resolve_target(target, level="stance")
        stance_name = target_info.canonical_target
        stance_config = target_info.config
        function = stance_config.get("function")

        if function == "weighted_sum":
            return self._trace_weighted_stance_score(
                stance_name,
                stance_config,
                context_id=context_id,
                start=start,
                end=end,
                include_raw_input=include_raw_input,
                include_labels=include_labels,
            )

        if function in self._rule_mapped_trace_supported_functions():
            return self._trace_rule_mapped_stance_score(
                stance_name,
                context_id=context_id,
                start=start,
                end=end,
                include_raw_input=include_raw_input,
                include_labels=include_labels,
            )

        raise ValueError(
            f"Unsupported stance trace function for {stance_name}: {function}"
        )












    def compare_smoothing_effect(
        self,
        target: str,
        smoothing_layer: str = "auto",
        windows: dict | None = None,
        include_detail: bool = True,
    ) -> dict:
        diagnostics = self._module1_sensitivity_diagnostics()
        return diagnostics.compare_smoothing_effect(
            target=target,
            smoothing_layer=smoothing_layer,
            windows=windows,
            include_detail=include_detail,
        )













    def _count_series_changes(self, series: pd.Series) -> int:
        valid = series.dropna()
        if valid.empty:
            return 0
        return int(valid.ne(valid.shift(1)).iloc[1:].sum())






    def compare_curve_move_driver_threshold_effect(
        self,
        include_detail: bool = True,
    ) -> dict:
        diagnostics = self._module1_sensitivity_diagnostics()
        return diagnostics.compare_curve_move_driver_threshold_effect(
            include_detail=include_detail,
        )





    def compare_curve_positioning_stabilization_cases(
        self,
        cases: dict | None = None,
        windows: dict | None = None,
        include_diagnostics: bool = True,
    ) -> dict:
        diagnostics = self._module1_sensitivity_diagnostics()
        return diagnostics.compare_curve_positioning_stabilization_cases(
            cases=cases,
            windows=windows,
            include_diagnostics=include_diagnostics,
        )

    def compare_credit_stance_persistence_cases(
        self,
        cases: dict | None = None,
        hysteresis_buffer: float = 0.05,
        windows: dict | None = None,
        include_diagnostics: bool = True,
    ) -> dict:
        diagnostics = self._module1_sensitivity_diagnostics()
        return diagnostics.compare_credit_stance_persistence_cases(
            cases=cases,
            hysteresis_buffer=hysteresis_buffer,
            windows=windows,
            include_diagnostics=include_diagnostics,
        )


    def _select_related_inputs(self, target, level, inputs=None, related_inputs=None):
        analysis = self._module1_historical_analysis()
        result = analysis._select_related_inputs(target, level, inputs, related_inputs)
        self._sync_historical_from_analysis(analysis)
        return result


    def _mark_label_changes(self, ax, label_table, label_col, index):
        analysis = self._module1_historical_analysis()
        result = analysis._mark_label_changes(ax, label_table, label_col, index)
        self._sync_historical_from_analysis(analysis)
        return result


    def _add_score_zones(self, ax, target_info: dict, normalize_target: bool=False):
        analysis = self._module1_historical_analysis()
        result = analysis._add_score_zones(ax, target_info, normalize_target)
        self._sync_historical_from_analysis(analysis)
        return result


    def _plot_historical_review_state_timeline(self, ax, case_df: pd.DataFrame, decomposition: pd.DataFrame):
        analysis = self._module1_historical_analysis()
        result = analysis._plot_historical_review_state_timeline(ax, case_df, decomposition)
        self._sync_historical_from_analysis(analysis)
        return result


    def _decompose_match_windows(self, case_df: pd.DataFrame) -> pd.DataFrame:
        analysis = self._module1_historical_analysis()
        result = analysis._decompose_match_windows(case_df)
        self._sync_historical_from_analysis(analysis)
        return result


    def plot_historical_review_case(self, target: str, level: str, context_id: str, expected_label: str | None=None, inputs=None, start=None, end=None, normalize_inputs: bool=True, normalize_target: bool=False, ffill_inputs: bool=True, mark_label_changes: bool=False, show_score_zones: bool=False, include_target_inputs: bool=True, figsize=(12, 7), height_ratios=(3, 1), show: bool=True):
        analysis = self._module1_historical_analysis()
        result = analysis.plot_historical_review_case(target, level, context_id, expected_label, inputs, start, end, normalize_inputs, normalize_target, ffill_inputs, mark_label_changes, show_score_zones, include_target_inputs, figsize, height_ratios, show)
        self._sync_historical_from_analysis(analysis)
        return result


    def _resolve_historical_display_window(self, context_start, context_end, start=None, end=None, warn_no_overlap: bool=True):
        analysis = self._module1_historical_analysis()
        result = analysis._resolve_historical_display_window(context_start, context_end, start, end, warn_no_overlap)
        self._sync_historical_from_analysis(analysis)
        return result


    def _mark_context_window_and_update_legend(self, ax, start, end, twin_ax=None):
        analysis = self._module1_historical_analysis()
        result = analysis._mark_context_window_and_update_legend(ax, start, end, twin_ax)
        self._sync_historical_from_analysis(analysis)
        return result


    def _normalize_for_comparison_plot(self, df: pd.DataFrame) -> pd.DataFrame:
        analysis = self._module1_historical_analysis()
        result = analysis._normalize_for_comparison_plot(df)
        self._sync_historical_from_analysis(analysis)
        return result


    def _resolve_compare_plot_normalize(
        self,
        normalize,
        dataset: TargetCompareDataset,
    ) -> bool:
        if normalize == "auto":
            return bool(dataset.metadata.get("normalization_recommendation", False))
        if isinstance(normalize, bool):
            return normalize
        raise ValueError('normalize must be one of: "auto", True, False.')


    def _render_compare_dataset_on_axes(
        self,
        ax_target,
        ax_comparison,
        dataset: TargetCompareDataset,
        *,
        normalize: bool,
        title: str | None = None,
    ) -> dict:
        if ax_target is None or ax_comparison is None:
            raise ValueError("Both target and comparison axes are required.")
        if not dataset.target_columns:
            raise ValueError("TargetCompareDataset has no target columns to plot.")
        if not dataset.comparison_columns:
            raise ValueError("TargetCompareDataset has no comparison columns to plot.")

        missing_target_cols = [
            col for col in dataset.target_columns if col not in dataset.data.columns
        ]
        missing_comparison_cols = [
            col for col in dataset.comparison_columns if col not in dataset.data.columns
        ]
        if missing_target_cols:
            raise ValueError(f"Target plot columns are missing: {missing_target_cols}")
        if missing_comparison_cols:
            raise ValueError(
                f"Comparison plot columns are missing: {missing_comparison_cols}"
            )

        target_plot = dataset.data.loc[:, list(dataset.target_columns)].copy()
        comparison_plot = dataset.data.loc[:, list(dataset.comparison_columns)].copy()

        target_plot = target_plot.select_dtypes(include="number")
        comparison_plot = comparison_plot.select_dtypes(include="number")
        if target_plot.empty:
            raise ValueError("No numeric target columns are available for plotting.")
        if comparison_plot.empty:
            raise ValueError("No numeric comparison columns are available for plotting.")

        if normalize:
            target_plot = self._normalize_for_comparison_plot(target_plot)
            comparison_plot = self._normalize_for_comparison_plot(comparison_plot)

        for index, col in enumerate(target_plot.columns):
            plot_kwargs = {"linewidth": 2.0, "label": f"target: {col}"}
            if index == 0:
                plot_kwargs["color"] = "grey"
            ax_target.plot(target_plot.index, target_plot[col], **plot_kwargs)

        ax_target.axhline(0, linewidth=1, linestyle="--", color="grey")
        ax_target.set_ylabel(
            "normalized target" if normalize else "target raw values"
        )

        for col in comparison_plot.columns:
            ax_comparison.plot(
                comparison_plot.index,
                comparison_plot[col],
                linewidth=1.2,
                alpha=0.75,
                label=f"comparison: {col}",
            )
        ax_comparison.set_ylabel(
            "normalized comparisons" if normalize else "comparison raw values"
        )

        if title is None:
            title = (
                f"{dataset.resolution.get('canonical_target')} "
                f"({dataset.target_level}) vs {dataset.effective_compare}"
            )
            if dataset.context_id is not None:
                title = f"{title} [{dataset.context_id}]"
        ax_target.set_title(title)

        lines_1, labels_1 = ax_target.get_legend_handles_labels()
        lines_2, labels_2 = ax_comparison.get_legend_handles_labels()
        ax_target.legend(lines_1 + lines_2, labels_1 + labels_2, loc="best")

        plotted_data = pd.concat([target_plot, comparison_plot], axis=1)
        return {
            "target_plot": target_plot.copy(),
            "comparison_plot": comparison_plot.copy(),
            "plotted_data": plotted_data.copy(),
            "target_cols": tuple(target_plot.columns),
            "comparison_cols": tuple(comparison_plot.columns),
            "axes": {
                "target": ax_target,
                "comparison": ax_comparison,
            },
        }


    def _plot_target_inputs_on_axes(self, ax_target, target: str, level: str, inputs=None, start=None, end=None, context_id=None, normalize_inputs: bool=True, normalize_target: bool=False, ffill_inputs: bool=True, mark_label_changes: bool=False, show_score_zones: bool=False, target_color='grey'):
        analysis = self._module1_historical_analysis()
        result = analysis._plot_target_inputs_on_axes(ax_target, target, level, inputs, start, end, context_id, normalize_inputs, normalize_target, ffill_inputs, mark_label_changes, show_score_zones, target_color)
        self._sync_historical_from_analysis(analysis)
        return result


    def plot_target_comparison(
        self,
        target: str,
        level: str,
        compare="auto",
        context_id=None,
        start=None,
        end=None,
        normalize="auto",
        include_labels: bool = True,
        include_strength: bool = True,
        ffill_inputs: bool = True,
        return_data: bool = False,
        ax=None,
        figsize=(12, 6),
    ):
        """
        Plot a target against a lower-layer comparison dataset.

        compare supports "auto", "components", "features", "raw_inputs", and
        "full". Plot data is built by build_target_comparison_dataset().
        """
        dataset = self.build_target_comparison_dataset(
            target=target,
            level=level,
            compare=compare,
            context_id=context_id,
            start=start,
            end=end,
            include_labels=include_labels,
            include_strength=include_strength,
            ffill_inputs=ffill_inputs,
        )
        normalize_resolved = self._resolve_compare_plot_normalize(
            normalize,
            dataset,
        )

        if ax is None:
            fig, ax_target = plt.subplots(figsize=figsize)
        else:
            ax_target = ax
            fig = ax_target.figure
        ax_comparison = ax_target.twinx()

        rendered = self._render_compare_dataset_on_axes(
            ax_target,
            ax_comparison,
            dataset,
            normalize=normalize_resolved,
            title=(
                f"{target} ({dataset.target_level}) vs "
                f"{dataset.effective_compare}"
                + (f" [{context_id}]" if context_id is not None else "")
            ),
        )

        if return_data:
            plt.close(fig)
            return {
                "fig": fig,
                "axes": rendered["axes"],
                "dataset": dataset,
                "plotted_data": rendered["plotted_data"].copy(),
                "target_plot": rendered["target_plot"].copy(),
                "comparison_plot": rendered["comparison_plot"].copy(),
                "target_columns": rendered["target_cols"],
                "comparison_columns": rendered["comparison_cols"],
                "compare": dataset.compare,
                "effective_compare": dataset.effective_compare,
                "normalize": normalize,
                "normalize_resolved": normalize_resolved,
                "start": dataset.start,
                "end": dataset.end,
            }

        return fig, (ax_target, ax_comparison)
