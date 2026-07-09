import warnings
from dataclasses import replace
from numbers import Real
import pandas as pd
from pathlib import Path

from module1_analysis import (
    Module1Analysis,
    _first_valid_dates_by_column,
    _inspect_module1_result_tables,
    _label_distributions,
    _latest_valid_dates_by_column,
)
from module1_context import (
    TargetCompareDataset,
    TargetContextResult,
)
from module1_calculator import FredSeries, Module1Calculator, _RuleMappedStanceSpec
from module1_historical_analysis import Module1HistoricalAnalysis
from module1_sensitivity_diagnostics import Module1SensitivityDiagnostics
from module1_diagnostics import Module1Diagnostics
from module1_result import Module1Result


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

    def _module1_diagnostics(self) -> Module1Diagnostics:
        return Module1Diagnostics(
            self._module1_result_for_historical_analysis(),
            historical_context=self.historical_context,
        )

    def _module1_analysis(self) -> Module1Analysis:
        return Module1Analysis(self._module1_result_for_historical_analysis())

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
        """
        start, end = self._resolve_historical_event_window(context_id, start, end)
        analysis = self._module1_analysis()
        ctx = analysis.get_target_context(
            target=target,
            level=level,
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
        """
        start, end = self._resolve_historical_event_window(context_id, start, end)
        analysis = self._module1_analysis()
        dataset = analysis.build_target_comparison_dataset(
            target=target,
            level=level,
            compare=compare,
            start=start,
            end=end,
            include_labels=include_labels,
            include_strength=include_strength,
            ffill_inputs=ffill_inputs,
        )

        if context_id is None:
            return dataset

        return replace(dataset, context_id=context_id)

    def raw_inputs_for_target(self, target: str, level: str) -> list[str]:
        """
        Return raw input columns used directly or indirectly by a target.
        """
        analysis = self._module1_analysis()
        return analysis.raw_inputs_for_target(target, level)


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


    def trace_stance_score(
        self,
        target: str,
        context_id: str | None = None,
        start=None,
        end=None,
        include_raw_input: bool = True,
        include_labels: bool = True,
    ) -> pd.DataFrame:
        diagnostics = self._module1_diagnostics()
        return diagnostics.trace_stance_score(
            target=target,
            context_id=context_id,
            start=start,
            end=end,
            include_raw_input=include_raw_input,
            include_labels=include_labels,
        )

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
        diagnostics = self._module1_diagnostics()
        return diagnostics.diagnose_rule_mapped_stance(
            target=target,
            context_id=context_id,
            start=start,
            end=end,
            include_scores=include_scores,
            include_raw_states=include_raw_states,
            include_stabilized_states=include_stabilized_states,
            include_rule_case=include_rule_case,
            include_labels=include_labels,
            view=view,
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
        analysis = self._module1_analysis()
        return analysis.plot_target_comparison_dataset(
            dataset,
            target_label=target,
            normalize=normalize,
            return_data=return_data,
            ax=ax,
            figsize=figsize,
        )
