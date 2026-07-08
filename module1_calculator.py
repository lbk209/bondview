import os
import warnings
import copy
from itertools import product
from dataclasses import dataclass, field
from numbers import Real
from pathlib import Path
from collections.abc import Mapping

import pandas as pd
import yaml
from dotenv import load_dotenv
from fredapi import Fred

from module1_schema import (
    _parse_rule_scores_n_parts,
    _resolve_rule_mapped_stabilization_config,
    _rule_mapped_bucket_classification_from_score,
    validate_module1_config,
)
from module1_result import Module1Result


@dataclass
class FredSeries:
    fred_id: str
    name: str
    description: str
    expected_frequency: str  # "daily" or "monthly"


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


class Module1Calculator:
    """
    Future owner of the Module 1 runtime pipeline.

    This class now owns the safest mechanical setup responsibilities:
    config/input paths, FRED client setup, core input loading, Module 1 config
    loading, config validation storage, and horizon resolution.

    Core runtime calculation now lives here. RegimeModule remains a temporary
    compatibility path for historical review, plotting, tracing, sensitivity
    diagnostics, and target-context workflows that have not yet moved.
    """

    def __init__(
        self,
        api_key_env="FRED_API_KEY",
        series_config_path="data/fred_series_config.csv",
        module1_config_path="data/module1_config.yaml",
        data_path="data/raw_data_19980101_20260508.csv",
        horizons=None,
    ):
        """
        Initialize Module 1 setup state and load the core input files.

        The constructor preserves the previous RegimeModule setup behavior: it
        loads series config, module1 config, and input data, then resolves
        horizons from YAML defaults plus optional constructor overrides.
        """
        load_dotenv()

        api_key = os.getenv(api_key_env)
        if api_key is None:
            raise ValueError(f"{api_key_env} is not set.")

        self.fred = Fred(api_key=api_key)
        self.series_config_path = series_config_path
        self.module1_config_path = module1_config_path
        self.data_path = data_path
        self.series_config = None
        self.data = None
        self.module1_config = None
        self.module1_config_validation = None
        self.feature_config = None
        self.component_config = None
        self.exposure_stance_config = None
        self.default_horizons = None
        self.horizon_overrides = horizons.copy() if horizons is not None else None
        self.horizons = None
        self.features = None
        self.scores = None
        self.labels = None
        self.stance_scores = None
        self.exposure_stance = None

        self.load_core_files()

    def load_core_files(
        self,
        series_config_path=None,
        module1_config_path=None,
        data_path=None,
    ) -> None:
        """
        Load core Module 1 files, applying optional path overrides.

        Omitted paths use the instance's stored paths and only load missing
        state. Provided paths update the stored path attributes and reload that
        file.
        """
        if series_config_path is not None:
            self.series_config_path = series_config_path
            self.load_series_config(self.series_config_path)
        elif self.series_config is None:
            self.load_series_config(self.series_config_path)

        if module1_config_path is not None:
            self.module1_config_path = module1_config_path
            self.load_module1_config(self.module1_config_path)
        elif self.module1_config is None:
            self.load_module1_config(self.module1_config_path)

        if data_path is not None:
            self.data_path = data_path
            self.load_data(path_from=self.data_path)
        elif self.data is None:
            self.load_data(path_from=self.data_path)

    def _default_horizons_from_config(self, config: dict | None = None) -> dict:
        config = self.module1_config if config is None else config
        if not isinstance(config, dict):
            raise ValueError("Module 1 config must be loaded before resolving horizons.")

        horizons = config.get("horizons")
        if not isinstance(horizons, dict) or not horizons:
            raise ValueError("module1_config.yaml horizons must be a non-empty mapping.")

        invalid = {
            key: value
            for key, value in horizons.items()
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0
        }
        if invalid:
            raise ValueError(
                "All configured horizon values must be positive integers. "
                f"Invalid values: {invalid}"
            )

        return horizons.copy()

    def validate_horizons(self, horizons=None, base_horizons=None) -> dict:
        """
        Return validated horizon settings.

        Base horizons come from module1_config.yaml unless base_horizons is
        provided. horizons is treated as a partial override mapping.
        """
        if base_horizons is None:
            base_horizons = self._default_horizons_from_config()
        if not isinstance(base_horizons, dict) or not base_horizons:
            raise ValueError("base_horizons must be a non-empty mapping.")

        invalid_base = {
            key: value
            for key, value in base_horizons.items()
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0
        }
        if invalid_base:
            raise ValueError(
                "All base horizon values must be positive integers. "
                f"Invalid values: {invalid_base}"
            )

        if horizons is not None and not isinstance(horizons, dict):
            raise ValueError("horizons must be a mapping of partial overrides or None.")

        unknown = set(horizons or {}).difference(base_horizons)
        if unknown:
            raise ValueError(f"Unknown horizon keys: {sorted(unknown)}")

        resolved = base_horizons.copy()
        resolved.update(horizons or {})

        invalid = {
            key: value
            for key, value in resolved.items()
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0
        }
        if invalid:
            raise ValueError(
                f"All horizon values must be positive integers. Invalid values: {invalid}"
            )

        return resolved

    def update_horizons(self, horizons: dict | None = None) -> dict:
        """
        Apply instance-level horizon overrides over YAML defaults.

        If horizons are updated after features, scores, or stances have been
        calculated, rerun calculate_features() and downstream steps, or rerun
        the full pipeline.
        """
        if self.default_horizons is None:
            self.default_horizons = self._default_horizons_from_config()

        if horizons is None:
            self.horizon_overrides = None
        else:
            self.horizon_overrides = horizons.copy()

        self.horizons = self.validate_horizons(
            self.horizon_overrides,
            base_horizons=self.default_horizons,
        )
        return self.horizons

    def load_series_config(self, path="data/fred_series_config.csv") -> dict:
        df = pd.read_csv(path)

        self.series_config = {
            row["key"]: FredSeries(
                fred_id=row["fred_id"],
                name=row["name"],
                description=row["description"],
                expected_frequency=row["expected_frequency"],
            )
            for _, row in df.iterrows()
        }

        return self.series_config

    def download_series(self, key: str, start=None, end=None) -> pd.Series | None:
        cfg = self.series_config[key]

        try:
            sr = self.fred.get_series(
                cfg.fred_id,
                observation_start=start,
                observation_end=end,
            )
        except Exception as e:
            print(f"[ERROR] Failed to download {key} ({cfg.fred_id}): {e}")
            return None

        if sr is None or len(sr) == 0:
            print(f"[WARN] No data for {key} ({cfg.fred_id})")
            return None

        sr.name = key
        print(
            f"[OK] {key:<10} | {cfg.fred_id} | "
            f"{sr.index.min().date()} ~ {sr.index.max().date()}"
        )

        return sr

    def check_frequency_sanity(self, key: str, sr: pd.Series) -> None:
        cfg = self.series_config[key]

        median_gap = sr.index.to_series().diff().median().days

        if cfg.expected_frequency == "monthly":
            if median_gap < 25 or median_gap > 35:
                print(f"[WARN] {key} expected monthly, median gap = {median_gap} days")

        elif cfg.expected_frequency == "daily":
            if median_gap > 7:
                print(
                    f"[WARN] {key} expected daily/business-daily, "
                    f"median gap = {median_gap} days"
                )

    def load_local_data(self, path_from, start=None, end=None) -> pd.DataFrame:
        """
        Load previously saved input data from a local CSV file.

        The loaded data must contain all columns defined in self.series_config.
        The index is parsed as datetime, sorted, and filtered by start/end.
        """
        if self.series_config is None:
            raise ValueError("Run load_series_config() before load_local_data().")

        path = Path(path_from)

        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")

        df = pd.read_csv(path, index_col=0, parse_dates=True)

        missing = pd.Index(self.series_config.keys()).difference(df.columns)
        if missing.size > 0:
            missing = ", ".join(missing)
            raise ValueError(f"Data columns unavailable: {missing}")

        df = df.sort_index()

        if start is not None:
            df = df.loc[df.index >= start]
        if end is not None:
            df = df.loc[df.index <= end]

        return df

    def load_data(self, path_from=None, start=None, end=None) -> pd.DataFrame:
        """
        Download FRED input data, or load it from a local CSV file.
        """
        if self.series_config is None:
            raise ValueError("Run load_series_config() before load_data().")

        start = pd.to_datetime(start) if start is not None else None
        end = pd.to_datetime(end) if end is not None else None
        if start is not None and end is not None and start > end:
            raise ValueError("start must be earlier than or equal to end.")

        if path_from is not None:
            df = self.load_local_data(path_from, start=start, end=end)
        else:
            data = {}

            for key in self.series_config:
                sr = self.download_series(key, start=start, end=end)

                if sr is not None:
                    self.check_frequency_sanity(key, sr)
                    data[key] = sr

            if not data:
                raise ValueError("No FRED data downloaded.")

            df = pd.concat(data.values(), axis=1)
            df = df.sort_index()  # no global ffill

        self.data = df
        return df

    def _load_yaml_config(self, path) -> dict:
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError(f"YAML config must be a mapping: {path}")

        return config

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
        config = self._load_yaml_config(path)

        validation = None
        if validate_config:
            validation = validate_module1_config(config)
            issues = validation["issues"]
            self.module1_config_validation = validation
            if not issues.empty:
                message = (
                    "Invalid module1_config.yaml: "
                    f"{len(issues)} validation issue(s). Inspect "
                    'self.module1_config_validation["issues"].'
                )
                if raise_on_invalid_config:
                    raise ValueError(message)
                warnings.warn(message, UserWarning)

        self.module1_config = config
        self.default_horizons = self._default_horizons_from_config(config)
        self.horizons = self.validate_horizons(
            self.horizon_overrides,
            base_horizons=self.default_horizons,
        )
        self.feature_config = {"features": config["features"]}
        self.component_config = {"components": config["components"]}
        self.exposure_stance_config = {
            "stance_label_rules": config["stance_label_rules"],
            "exposure_stances": config["exposure_stances"],
        }
        if validate_config:
            self.module1_config_validation = validation

        return config


    def _get_horizon(self, key) -> int:
        if isinstance(key, int):
            return key

        if self.horizons is None:
            raise ValueError("Run load_module1_config() before resolving horizons.")

        if key not in self.horizons:
            raise ValueError(f"Unknown horizon key: {key}")

        return self.horizons[key]


    def _get_input_series(self, name: str, features: pd.DataFrame) -> pd.Series:
        if name in features.columns:
            return features[name]

        if name in self.data.columns:
            return self.data[name]

        raise KeyError(name)


    def _calculate_feature_from_definition(
        self,
        definition: dict,
        features: pd.DataFrame,
    ) -> pd.Series:
        method = definition.get("method")
        frequency = definition.get("frequency")

        if method in {"change", "pct_change"}:
            input_name = definition.get("input")
            if input_name is None:
                raise ValueError(f"{method} feature is missing input.")

            sr = self._get_input_series(input_name, features)
            horizon = self._get_horizon(definition.get("horizon"))

            if frequency == "monthly":
                calc_sr = sr.dropna()
            else:
                calc_sr = sr

            if method == "change":
                result = calc_sr - calc_sr.shift(horizon)
            else:
                result = calc_sr.pct_change(horizon, fill_method=None)

            return result.reindex(self.data.index)

        if method == "level":
            input_name = definition.get("input")
            if input_name is None:
                raise ValueError("level feature is missing input.")

            sr = self._get_input_series(input_name, features)
            return sr.reindex(self.data.index)

        if method == "spread":
            inputs = definition.get("inputs")
            if not isinstance(inputs, list) or len(inputs) != 2:
                raise ValueError("spread feature requires exactly two inputs.")

            first = self._get_input_series(inputs[0], features)
            second = self._get_input_series(inputs[1], features)
            return first - second

        raise ValueError(f"Unsupported feature method: {method}")


    def calculate_features(self) -> pd.DataFrame:
        if self.data is None:
            raise ValueError("Run load_data() before calculate_features().")

        if self.feature_config is None:
            raise ValueError("Run load_module1_config() before calculate_features().")

        definitions = self.feature_config["features"]
        features = pd.DataFrame(index=self.data.index)
        unresolved = dict(definitions)

        while unresolved:
            progressed = False

            for name, definition in list(unresolved.items()):
                try:
                    features[name] = self._calculate_feature_from_definition(
                        definition,
                        features,
                    )
                except KeyError:
                    continue

                del unresolved[name]
                progressed = True

            if not progressed:
                unresolved_names = ", ".join(sorted(unresolved))
                raise ValueError(f"Unable to resolve feature dependencies: {unresolved_names}")

        self.features = features
        return features


    def _normalize_score_input(
        self,
        sr: pd.Series,
        method: str | None,
        horizon_key: str = "normalization",
    ) -> pd.Series:
        if method is None:
            return sr

        if method not in {"rolling_zscore", "rolling_std"}:
            raise ValueError(f"Unsupported normalization method: {method}")

        if self.horizons is None:
            raise ValueError("Run load_module1_config() before normalizing scores.")

        if horizon_key not in self.horizons:
            raise ValueError(f"Unknown normalization horizon key: {horizon_key}")

        window = self.horizons[horizon_key]
        valid = sr.dropna()
        rolling = valid.rolling(window=window, min_periods=window)
        rolling_std = rolling.std()

        if method == "rolling_zscore":
            normalized = (valid - rolling.mean()) / rolling_std
        else:
            normalized = valid / rolling_std

        return normalized.reindex(sr.index)


    def _smooth_score(self, sr: pd.Series, method: str | None) -> pd.Series:
        if method is None:
            return sr

        if self.horizons is None:
            raise ValueError("Run load_module1_config() before smoothing scores.")

        if method not in self.horizons:
            raise ValueError(f"Unknown smoothing horizon key: {method}")

        window = self.horizons[method]
        return sr.dropna().rolling(window=window, min_periods=window).mean().reindex(sr.index)


    def _prepare_component_input_series(
        self,
        sr: pd.Series,
        input_preparation: dict | None,
    ) -> pd.Series:
        if not input_preparation:
            return sr

        smoothing = input_preparation.get("smoothing")
        if smoothing is None:
            return sr

        window = self._get_horizon(smoothing)
        return (
            sr.dropna()
            .rolling(window=window, min_periods=window)
            .mean()
            .reindex(sr.index)
        )


    def _prepared_component_score_inputs(
        self,
        component_name: str,
        score_config: dict,
        *,
        expected_count: int | None = None,
        apply_input_preparation: bool = True,
        apply_min_abs_value: bool = False,
    ) -> list[pd.Series]:
        inputs = score_config.get("inputs")
        if not isinstance(inputs, list) or not inputs:
            raise ValueError(
                f"Component {component_name} score.inputs must be a non-empty list."
            )
        if expected_count is not None and len(inputs) != expected_count:
            raise ValueError(
                f"Component {component_name} requires exactly {expected_count} inputs."
            )

        prepared = []
        input_preparation = score_config.get("input_preparation")
        for idx, item in enumerate(inputs):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Component {component_name} inputs[{idx}] must be a mapping."
                )

            feature_name = item.get("feature")
            if feature_name not in self.features.columns:
                raise ValueError(f"Missing feature for {component_name}: {feature_name}")

            score_input = self.features[feature_name]
            if apply_input_preparation:
                score_input = self._prepare_component_input_series(
                    score_input,
                    input_preparation,
                )

            prepared.append(score_input)

        min_abs_value = None
        if apply_min_abs_value and apply_input_preparation and input_preparation:
            min_abs_value = input_preparation.get("min_abs_value")
        if min_abs_value is not None:
            prepared = [
                score_input.mask(score_input.abs() < min_abs_value, 0.0)
                for score_input in prepared
            ]

        return prepared


    def _clip_score(self, sr: pd.Series, clip_config: dict | None) -> pd.Series:
        if not clip_config:
            return sr

        return sr.clip(
            lower=clip_config.get("min"),
            upper=clip_config.get("max"),
        )


    def _apply_sign(self, sr: pd.Series, sign: str | None) -> pd.Series:
        if sign in {None, "direct"}:
            return sr

        if sign == "inverse":
            return sr * -1

        raise ValueError(f"Unsupported score sign: {sign}")


    def _fixed_anchor_state_score(
        self,
        sr: pd.Series,
        anchors: dict,
        *,
        context: str,
    ) -> pd.Series:
        required = {"negative", "neutral", "positive"}
        missing = sorted(required.difference(anchors or {}))
        if missing:
            raise ValueError(
                f"{context} fixed-anchor state score is missing anchor(s): {missing}"
            )

        negative_anchor = anchors["negative"]
        neutral_anchor = anchors["neutral"]
        positive_anchor = anchors["positive"]
        if not negative_anchor < neutral_anchor < positive_anchor:
            raise ValueError(
                f"{context} fixed-anchor state score requires "
                "negative < neutral < positive anchors."
            )

        lower_denominator = neutral_anchor - negative_anchor
        upper_denominator = positive_anchor - neutral_anchor
        score = sr.copy().astype("float64")
        below_neutral = score < neutral_anchor
        score.loc[below_neutral] = (
            (score.loc[below_neutral] - neutral_anchor) / lower_denominator
        )
        score.loc[~below_neutral] = (
            (score.loc[~below_neutral] - neutral_anchor) / upper_denominator
        )
        return score


    def _weighted_sum_score(
        self,
        weighted_terms: list[tuple[pd.Series, float]],
        *,
        context: str,
    ) -> pd.Series:
        if not weighted_terms:
            raise ValueError(f"{context} has no weighted inputs.")

        weighted = [series * weight for series, weight in weighted_terms]
        return pd.concat(weighted, axis=1).sum(axis=1, skipna=False)


    def align_component_scores(self) -> pd.DataFrame:
        """
        Align component scores to the Module 1 output index.

        Raw data and feature construction remain sparse. This alignment happens only
        after component scores are calculated so monthly-driven component scores can
        be used on daily output rows without back-filling.
        """
        if self.scores is None:
            raise ValueError("Run calculate_component_scores() before align_component_scores().")

        self.scores = self.scores.reindex(self.features.index).ffill()
        return self.scores


    def _calculate_single_feature_component_score(
        self,
        component_name: str,
        score_config: dict,
        normalization: str | None,
        normalization_horizon: str,
        *,
        apply_input_preparation: bool = True,
    ) -> pd.Series:
        feature_name = score_config.get("input")
        if feature_name not in self.features.columns:
            raise ValueError(f"Missing feature for {component_name}: {feature_name}")

        score = self.features[feature_name]
        if apply_input_preparation:
            score = self._prepare_component_input_series(
                score,
                score_config.get("input_preparation"),
            )
        score = self._apply_sign(score, score_config.get("sign"))
        return self._normalize_score_input(
            score,
            normalization,
            normalization_horizon,
        )


    def _calculate_weighted_feature_component_score(
        self,
        component_name: str,
        score_config: dict,
        normalization: str | None,
        normalization_horizon: str,
        *,
        apply_input_preparation: bool = True,
    ) -> pd.Series:
        weighted_terms = []
        inputs = score_config.get("inputs")
        if not isinstance(inputs, list) or not inputs:
            raise ValueError(
                f"Component {component_name} weighted_feature_score requires inputs."
            )

        for idx, item in enumerate(inputs):
            if not isinstance(item, dict):
                raise ValueError(
                    f"Component {component_name} inputs[{idx}] must be a mapping."
                )

            feature_name = item.get("feature")
            if feature_name not in self.features.columns:
                raise ValueError(f"Missing feature for {component_name}: {feature_name}")

            if "weight" not in item:
                raise ValueError(
                    f"Component {component_name} inputs[{idx}].weight is required."
                )
            weight = item.get("weight")
            if isinstance(weight, bool) or not isinstance(weight, Real) or pd.isna(weight):
                raise ValueError(
                    f"Component {component_name} inputs[{idx}].weight must be numeric and not bool."
                )

            score_input = self.features[feature_name]
            if apply_input_preparation:
                score_input = self._prepare_component_input_series(
                    score_input,
                    score_config.get("input_preparation"),
                )
            feature_score = self._normalize_score_input(
                score_input,
                normalization,
                normalization_horizon,
            )
            weighted_terms.append((feature_score, float(weight)))

        return self._weighted_sum_score(
            weighted_terms,
            context=f"Component {component_name}",
        )


    def _curve_move_driver_score_from_prepared_inputs(
        self,
        front_end: pd.Series,
        long_end: pd.Series,
        bucket_scores: dict[str, float],
    ) -> pd.Series:
        score = pd.Series(bucket_scores["default"], index=front_end.index)
        score.loc[(front_end < 0) & (long_end < 0)] = bucket_scores["bull_parallel"]
        score.loc[(front_end > 0) & (long_end > 0)] = bucket_scores["bear_parallel"]
        score.loc[(front_end < 0) & (long_end > 0)] = bucket_scores[
            "front_end_down_long_end_up"
        ]
        score.loc[(front_end > 0) & (long_end < 0)] = bucket_scores[
            "front_end_up_long_end_down"
        ]
        score.loc[front_end.isna() | long_end.isna()] = pd.NA
        return score


    def _calculate_curve_move_driver_score(
        self,
        component_name: str,
        score_config: dict,
        *,
        apply_input_preparation: bool = True,
    ) -> pd.Series:
        front_end, long_end = self._prepared_component_score_inputs(
            component_name,
            score_config,
            expected_count=2,
            apply_input_preparation=apply_input_preparation,
            apply_min_abs_value=True,
        )
        bucket_scores = self._curve_move_driver_bucket_scores(
            self._component_score_bucket_config(component_name)
        )
        return self._curve_move_driver_score_from_prepared_inputs(
            front_end,
            long_end,
            bucket_scores,
        )


    def _curve_move_driver_bucket_scores(self, bucket_config: dict) -> dict[str, float]:
        def bucket_score(bucket_name: str) -> float:
            bucket_rule = bucket_config.get(bucket_name)
            if not isinstance(bucket_rule, dict) or "score" not in bucket_rule:
                raise ValueError(
                    f"curve_move_driver bucket {bucket_name} must define score."
                )
            return float(bucket_rule["score"])

        default_scores = [
            bucket_rule.get("score")
            for bucket_rule in bucket_config.values()
            if isinstance(bucket_rule, dict) and bucket_rule.get("default") is True
        ]
        if len(default_scores) != 1 or pd.isna(default_scores[0]):
            raise ValueError(
                "curve_move_driver must define exactly one default bucket with a score."
            )

        return {
            "default": float(default_scores[0]),
            "bull_parallel": bucket_score("bull_parallel"),
            "bear_parallel": bucket_score("bear_parallel"),
            "front_end_down_long_end_up": bucket_score("front_end_down_long_end_up"),
            "front_end_up_long_end_down": bucket_score("front_end_up_long_end_down"),
        }


    def _component_score_bucket_config(self, component_name: str) -> dict:
        if self.component_config is None:
            raise ValueError("Run load_module1_config() before bucket classification.")

        buckets = (
            self.component_config
            .get("components", {})
            .get(component_name, {})
            .get("score", {})
            .get("buckets")
        )
        if not isinstance(buckets, dict) or not buckets:
            raise ValueError(
                f"Component {component_name} score.buckets must be a non-empty mapping."
            )
        return buckets


    def _rule_state_is_missing(self, state) -> bool:
        if state is None:
            return True
        try:
            missing = pd.isna(state)
        except TypeError:
            return False
        if isinstance(missing, bool):
            return missing
        return False


    def _rule_case_from_states(self, states):
        if isinstance(states, str) or not isinstance(states, (list, tuple)):
            raise ValueError("Rule case states must be a list or tuple.")
        if not states:
            raise ValueError("Rule case states must not be empty.")
        if any(self._rule_state_is_missing(state) for state in states):
            return pd.NA

        parts = tuple(str(state).strip() for state in states)
        if any(part == "" for part in parts):
            raise ValueError("Rule case states must not contain empty values.")
        return "|".join(parts)


    def _lookup_rule_score(
        self,
        states,
        rule_scores: Mapping,
        *,
        context: str = "Rule-mapped stance",
    ):
        if isinstance(states, str) or not isinstance(states, (list, tuple)):
            raise ValueError("Rule score lookup states must be a list or tuple.")
        if not states:
            raise ValueError("Rule score lookup states must not be empty.")
        if any(self._rule_state_is_missing(state) for state in states):
            return pd.NA

        rule_key = tuple(str(state).strip() for state in states)
        if any(part == "" for part in rule_key):
            raise ValueError("Rule score lookup states must not contain empty values.")
        if not isinstance(rule_scores, Mapping):
            raise ValueError(f"{context} rule_scores must be a mapping.")
        if rule_key not in rule_scores:
            raise ValueError(
                f"Missing {context} rule score for case: {'|'.join(rule_key)}"
            )
        return rule_scores[rule_key]


    def _validate_required_score_columns(
        self,
        required_score_cols,
        *,
        context: str = "Rule-mapped stance",
    ) -> None:
        if self.scores is None:
            raise ValueError(
                f"Run calculate_component_scores() before {context} calculation."
            )
        if isinstance(required_score_cols, str) or not isinstance(
            required_score_cols,
            (list, tuple, set),
        ):
            raise ValueError(f"{context} required score columns must be a sequence.")
        if not required_score_cols:
            raise ValueError(f"{context} required score columns must not be empty.")
        for col in required_score_cols:
            if not isinstance(col, str) or col.strip() == "":
                raise ValueError(
                    f"{context} required score columns must be non-empty strings."
                )
        if len(set(required_score_cols)) != len(required_score_cols):
            raise ValueError(
                f"{context} required score columns must not contain duplicates."
            )

        missing = [col for col in required_score_cols if col not in self.scores.columns]
        if missing:
            raise ValueError(
                f"Missing component score column(s) for {context}: {missing}"
            )


    def _resolve_component_name_for_score_output(
        self,
        score_output: str,
        *,
        context: str,
    ) -> str:
        if self.component_config is None:
            raise ValueError(f"Run load_module1_config() before resolving {context}.")
        if not isinstance(score_output, str) or score_output.strip() == "":
            raise ValueError(f"{context} source_score must be a non-empty string.")

        matches = []
        for component_name, component in self.component_config["components"].items():
            output = component.get("score", {}).get("output")
            if output == score_output:
                matches.append(component_name)
        if not matches:
            raise ValueError(
                f"{context} source_score must refer to a configured component "
                f"score output: {score_output}."
            )
        if len(matches) > 1:
            raise ValueError(
                f"{context} source_score {score_output} resolves to multiple "
                f"components: {matches}."
            )
        return matches[0]


    def _resolve_rule_mapped_stance_schema(
        self,
        stance_name: str,
        stance_config: dict,
    ) -> _RuleMappedStanceSpec:
        context = f"rule_mapped stance {stance_name}"
        if not isinstance(stance_name, str) or stance_name.strip() == "":
            raise ValueError("rule_mapped stance name must be a non-empty string.")
        if not isinstance(stance_config, Mapping):
            raise ValueError(f"{context} config must be a mapping.")
        if self.component_config is None:
            raise ValueError(
                "Run load_module1_config() before resolving rule_mapped stance schemas."
            )

        rule_mapped = stance_config.get("rule_mapped")
        if not isinstance(rule_mapped, Mapping):
            raise ValueError(f"{context}.rule_mapped must be a mapping.")
        function = rule_mapped.get("function")
        if function != "rule_mapped_stance":
            raise ValueError(
                f"{context}.rule_mapped.function must be rule_mapped_stance, "
                f"got {function}."
            )

        def require_string(mapping, field_name: str, field_context: str) -> str:
            value = mapping.get(field_name)
            if not isinstance(value, str) or value.strip() == "":
                raise ValueError(f"{field_context}.{field_name} must be a non-empty string.")
            return value.strip()

        state_inputs_config = rule_mapped.get("state_inputs")
        if not isinstance(state_inputs_config, list) or not state_inputs_config:
            raise ValueError(f"{context}.rule_mapped.state_inputs must be a non-empty list.")

        supported_classifications = {
            "threshold_state",
            "threshold_bucket",
            "score_bucket",
        }
        state_inputs = []
        expected_values_by_input = []
        for idx, state_input in enumerate(state_inputs_config):
            input_context = f"{context}.rule_mapped.state_inputs[{idx}]"
            if not isinstance(state_input, Mapping):
                raise ValueError(f"{input_context} must be a mapping.")

            name = require_string(state_input, "name", input_context)
            source_score_col = require_string(state_input, "source_score", input_context)
            classification = require_string(state_input, "classification", input_context)
            if classification not in supported_classifications:
                raise ValueError(
                    f"{input_context} ({name}) has unsupported classification "
                    f"{classification}; expected one of {sorted(supported_classifications)}."
                )

            component_name = self._resolve_component_name_for_score_output(
                source_score_col,
                context=f"{input_context} ({name})",
            )
            component_score = (
                self.component_config["components"].get(component_name, {}).get("score", {})
            )
            if classification in {"threshold_bucket", "score_bucket"}:
                expected_classification, mixed_bucket_style = (
                    _rule_mapped_bucket_classification_from_score(component_score)
                )
                if mixed_bucket_style:
                    raise ValueError(
                        f"{input_context} ({name}) references {source_score_col}, "
                        "whose component score.buckets mix range-style keys with "
                        "exact score keys."
                    )
                if (
                    expected_classification is not None
                    and classification != expected_classification
                ):
                    raise ValueError(
                        f"{input_context} ({name}) declares classification "
                        f"{classification}; expected {expected_classification} "
                        f"from component {component_name} score.buckets."
                    )

            raw_output_col = require_string(state_input, "raw_output", input_context)
            stabilized_output_col = require_string(
                state_input,
                "stabilized_output",
                input_context,
            )
            stabilization_changed_output_col = require_string(
                state_input,
                "stabilization_changed_output",
                input_context,
            )
            diagnostic_component = None
            if state_input.get("diagnostic_component") is not None:
                diagnostic_component = require_string(
                    state_input,
                    "diagnostic_component",
                    input_context,
                )

            state_buckets = {}
            values = []
            if classification == "threshold_state":
                configured_buckets = state_input.get("state_buckets")
                if not isinstance(configured_buckets, Mapping):
                    raise ValueError(f"{input_context} ({name}).state_buckets must be a mapping.")
                required_bucket_keys = ("positive", "neutral", "negative")
                unknown_keys = sorted(set(configured_buckets) - set(required_bucket_keys))
                if unknown_keys:
                    raise ValueError(
                        f"{input_context} ({name}).state_buckets contains unknown "
                        f"keys: {unknown_keys}."
                    )
                for bucket_key in required_bucket_keys:
                    bucket_value = configured_buckets.get(bucket_key)
                    if not isinstance(bucket_value, str) or bucket_value.strip() == "":
                        raise ValueError(
                            f"{input_context} ({name}).state_buckets.{bucket_key} "
                            "must be a non-empty string."
                        )
                    state_buckets[bucket_key] = bucket_value.strip()
                    values.append(bucket_value.strip())
            else:
                configured_buckets = state_input.get("buckets")
                if not isinstance(configured_buckets, list) or not configured_buckets:
                    raise ValueError(f"{input_context} ({name}).buckets must be a non-empty list.")
                for bucket_idx, bucket_name in enumerate(configured_buckets):
                    if not isinstance(bucket_name, str) or bucket_name.strip() == "":
                        raise ValueError(
                            f"{input_context} ({name}).buckets[{bucket_idx}] "
                            "must be a non-empty string."
                        )
                    values.append(bucket_name.strip())
                component_buckets = component_score.get("buckets")
                if isinstance(component_buckets, Mapping):
                    expected_buckets = set(component_buckets)
                    actual_buckets = set(values)
                    if expected_buckets != actual_buckets:
                        raise ValueError(
                            f"{input_context} ({name}).buckets must match configured "
                            f"component buckets; missing={sorted(expected_buckets - actual_buckets)}, "
                            f"unknown={sorted(actual_buckets - expected_buckets)}."
                        )

            if len(values) != len(set(values)):
                raise ValueError(f"{input_context} ({name}) values must be unique.")

            state_inputs.append(
                _RuleMappedStateInputSpec(
                    name=name,
                    source_score_col=source_score_col,
                    component_name=component_name,
                    classification=classification,
                    raw_output_col=raw_output_col,
                    stabilized_output_col=stabilized_output_col,
                    stabilization_changed_output_col=stabilization_changed_output_col,
                    values=tuple(values),
                    diagnostic_component=diagnostic_component,
                    state_buckets=state_buckets,
                )
            )
            expected_values_by_input.append(tuple(values))

        state_input_names = [state_input.name for state_input in state_inputs]
        if len(state_input_names) != len(set(state_input_names)):
            raise ValueError(f"{context}.rule_mapped.state_inputs names must be unique.")

        stabilization_config = _resolve_rule_mapped_stabilization_config(
            rule_mapped,
            state_input_names,
            context=f"{context}.rule_mapped",
        )

        rule_scores = _parse_rule_scores_n_parts(
            rule_mapped.get("rule_scores"),
            expected_parts=len(state_inputs),
            context=f"{context}.rule_mapped",
        )
        expected_rule_tuples = set(product(*expected_values_by_input))
        actual_rule_tuples = set(rule_scores)
        if expected_rule_tuples != actual_rule_tuples:
            missing = sorted("|".join(rule_tuple) for rule_tuple in expected_rule_tuples - actual_rule_tuples)
            unknown = sorted("|".join(rule_tuple) for rule_tuple in actual_rule_tuples - expected_rule_tuples)
            raise ValueError(
                f"{context}.rule_mapped.rule_scores must cover every declared "
                f"state or bucket cross-product; missing={missing}, unknown={unknown}."
            )

        score_output_col = require_string(rule_mapped, "score_output", f"{context}.rule_mapped")
        stance_output_col = require_string(rule_mapped, "stance_output", f"{context}.rule_mapped")
        strength_output_col = require_string(rule_mapped, "strength_output", f"{context}.rule_mapped")
        for field_name, resolved_value in [
            ("score_output", score_output_col),
            ("stance_output", stance_output_col),
            ("strength_output", strength_output_col),
        ]:
            active_value = stance_config.get(field_name)
            if resolved_value != active_value:
                raise ValueError(
                    f"{context}.rule_mapped.{field_name} must match active stance "
                    f"{field_name}; got {resolved_value}, expected {active_value}."
                )

        adjustment_spec = None
        adjustment_config = rule_mapped.get("adjustment")
        if adjustment_config is not None:
            if not isinstance(adjustment_config, Mapping):
                raise ValueError(f"{context}.rule_mapped.adjustment must be a mapping.")
            metadata_outputs = adjustment_config.get("metadata_outputs", ())
            if not isinstance(metadata_outputs, list):
                raise ValueError(
                    f"{context}.rule_mapped.adjustment.metadata_outputs must be a list."
                )
            metadata_output_cols = []
            for idx, output_name in enumerate(metadata_outputs):
                if not isinstance(output_name, str) or output_name.strip() == "":
                    raise ValueError(
                        f"{context}.rule_mapped.adjustment.metadata_outputs[{idx}] "
                        "must be a non-empty string."
                    )
                metadata_output_cols.append(output_name.strip())
            if len(metadata_output_cols) != len(set(metadata_output_cols)):
                raise ValueError(
                    f"{context}.rule_mapped.adjustment.metadata_outputs must be unique."
                )
            adjustment_output_col = None
            if adjustment_config.get("adjustment_output") is not None:
                adjustment_output_col = require_string(
                    adjustment_config,
                    "adjustment_output",
                    f"{context}.rule_mapped.adjustment",
                )
            config = adjustment_config.get("config")
            if config is not None and not isinstance(config, Mapping):
                raise ValueError(f"{context}.rule_mapped.adjustment.config must be a mapping.")
            adjustment_spec = _RuleMappedAdjustmentSpec(
                metadata_output_cols=tuple(metadata_output_cols),
                adjustment_output_col=adjustment_output_col,
                config=copy.deepcopy(config) if config is not None else None,
            )

        base_rule_score_output_col = None
        if rule_mapped.get("base_rule_score_output") is not None:
            base_rule_score_output_col = require_string(
                rule_mapped,
                "base_rule_score_output",
                f"{context}.rule_mapped",
            )

        adjusted_score_output_col = None
        if rule_mapped.get("adjusted_score_output") is not None:
            adjusted_score_output_col = require_string(
                rule_mapped,
                "adjusted_score_output",
                f"{context}.rule_mapped",
            )

        return _RuleMappedStanceSpec(
            stance_name=stance_name,
            function=function,
            state_inputs=tuple(state_inputs),
            stabilization_config=stabilization_config,
            rule_case_output_col=require_string(
                rule_mapped,
                "rule_case_output",
                f"{context}.rule_mapped",
            ),
            stabilization_changed_any_output_col=require_string(
                rule_mapped,
                "stabilization_changed_any_output",
                f"{context}.rule_mapped",
            ),
            rule_scores=rule_scores,
            score_output_col=score_output_col,
            stance_output_col=stance_output_col,
            strength_output_col=strength_output_col,
            base_rule_score_output_col=base_rule_score_output_col,
            adjustment=adjustment_spec,
            adjusted_score_output_col=adjusted_score_output_col,
        )


    def _bucket_matches_value(self, value: float, bucket_rule: dict) -> bool:
        if "min" in bucket_rule and value < bucket_rule["min"]:
            return False
        if "min_exclusive" in bucket_rule and value <= bucket_rule["min_exclusive"]:
            return False
        if "max" in bucket_rule and value > bucket_rule["max"]:
            return False
        if "max_exclusive" in bucket_rule and value >= bucket_rule["max_exclusive"]:
            return False
        return True


    def _threshold_bucket(self, score, bucket_config: dict):
        if pd.isna(score):
            return pd.NA

        default_bucket = None
        for bucket_name, bucket_rule in bucket_config.items():
            if not isinstance(bucket_rule, dict):
                raise ValueError(f"Curve bucket {bucket_name} must be a mapping.")
            if bucket_rule.get("default") is True:
                default_bucket = bucket_name
                continue
            if self._bucket_matches_value(float(score), bucket_rule):
                return bucket_name

        if default_bucket is not None:
            return default_bucket
        raise ValueError(f"Curve score {score} did not match any configured bucket.")


    def _score_bucket(self, score, bucket_config: dict):
        if pd.isna(score):
            return pd.NA

        default_bucket = None
        for bucket_name, bucket_rule in bucket_config.items():
            if not isinstance(bucket_rule, dict):
                raise ValueError(f"Curve bucket {bucket_name} must be a mapping.")
            if bucket_rule.get("default") is True:
                default_bucket = bucket_name
                continue
            if "score" in bucket_rule and float(score) == float(bucket_rule["score"]):
                return bucket_name

        if default_bucket is not None:
            return default_bucket
        raise ValueError(f"Curve score {score} did not match any configured bucket.")


    def _component_bucket_config(self, component_name: str) -> dict:
        if self.component_config is None:
            raise ValueError("Run load_module1_config() before bucket label classification.")

        buckets = (
            self.component_config
            .get("components", {})
            .get(component_name, {})
            .get("score", {})
            .get("buckets")
        )
        if not isinstance(buckets, dict) or not buckets:
            raise ValueError(
                f"Component {component_name} score.buckets must be a non-empty mapping."
            )
        return buckets


    def _component_bucket_labels(self, component_name: str) -> dict:
        if self.component_config is None:
            raise ValueError("Run load_module1_config() before bucket label classification.")

        bucket_labels = (
            self.component_config
            .get("components", {})
            .get(component_name, {})
            .get("label", {})
            .get("bucket_labels")
        )
        if not isinstance(bucket_labels, dict) or not bucket_labels:
            raise ValueError(
                f"Component {component_name} label.bucket_labels must be a non-empty mapping."
            )
        return bucket_labels


    def _component_bucket_style(self, bucket_config: dict) -> str:
        non_default_rules = [
            bucket_rule
            for bucket_rule in bucket_config.values()
            if isinstance(bucket_rule, dict) and bucket_rule.get("default") is not True
        ]
        has_score_rule = any("score" in bucket_rule for bucket_rule in non_default_rules)
        has_range_rule = any(
            any(
                key in bucket_rule
                for key in ["min", "max", "min_exclusive", "max_exclusive"]
            )
            for bucket_rule in non_default_rules
        )
        if has_score_rule and has_range_rule:
            raise ValueError(
                "Bucket label classification is ambiguous: score and range rules are mixed."
            )
        if has_score_rule:
            return "score"
        return "threshold"


    def _component_bucket_for_score(self, score, bucket_config: dict):
        style = self._component_bucket_style(bucket_config)
        if style == "score":
            return self._score_bucket(score, bucket_config)
        return self._threshold_bucket(score, bucket_config)


    def _calculate_current_state_component_score(
        self,
        component_name: str,
        score_config: dict,
        *,
        apply_input_preparation: bool = True,
    ) -> pd.Series:
        if score_config.get("state_transform") != "fixed_anchor":
            raise ValueError(
                f"Current-state component {component_name} must use "
                "state_transform: fixed_anchor."
            )

        function = score_config.get("function")

        if function == "single_feature_score":
            feature_name = score_config.get("input")
            if feature_name not in self.features.columns:
                raise ValueError(f"Missing feature for {component_name}: {feature_name}")

            score_input = self.features[feature_name]
            if apply_input_preparation:
                score_input = self._prepare_component_input_series(
                    score_input,
                    score_config.get("input_preparation"),
                )
            score = self._fixed_anchor_state_score(
                score_input,
                score_config.get("anchors", {}),
                context=component_name,
            )
            return self._apply_sign(score, score_config.get("sign"))

        if function == "weighted_feature_score":
            inputs = score_config.get("inputs")
            if not isinstance(inputs, list) or not inputs:
                raise ValueError(
                    f"Current-state component {component_name} "
                    "weighted_feature_score requires inputs."
                )

            transformed_terms = []
            has_explicit_weight = any(
                isinstance(item, dict) and "weight" in item for item in inputs
            )

            for idx, item in enumerate(inputs):
                if not isinstance(item, dict):
                    raise ValueError(
                        f"Current-state component {component_name} "
                        f"inputs[{idx}] must be a mapping."
                    )

                feature_name = item.get("feature")
                if feature_name not in self.features.columns:
                    raise ValueError(
                        f"Missing feature for {component_name}: {feature_name}"
                    )

                score_input = self.features[feature_name]
                if apply_input_preparation:
                    score_input = self._prepare_component_input_series(
                        score_input,
                        score_config.get("input_preparation"),
                    )
                feature_score = self._fixed_anchor_state_score(
                    score_input,
                    item.get("anchors", {}),
                    context=f"{component_name} {feature_name}",
                )

                weight = item.get("weight")
                if weight is None:
                    if len(inputs) > 1 or has_explicit_weight:
                        raise ValueError(
                            f"Current-state component {component_name} "
                            f"inputs[{idx}].weight is required when fixed-anchor "
                            "scoring combines multiple weighted inputs."
                        )
                    weight = 1.0
                elif (
                    isinstance(weight, bool)
                    or not isinstance(weight, Real)
                    or pd.isna(weight)
                ):
                    raise ValueError(
                        f"Current-state component {component_name} "
                        f"inputs[{idx}].weight must be numeric and not bool."
                    )
                transformed_terms.append((feature_score, float(weight)))

            score = self._weighted_sum_score(
                transformed_terms,
                context=f"Current-state component {component_name}",
            )
            return self._apply_sign(score, score_config.get("sign"))

        raise ValueError(
            f"Unsupported current-state score function for {component_name}: {function}"
        )


    def calculate_component_scores(self) -> pd.DataFrame:
        if self.features is None:
            raise ValueError("Run calculate_features() before calculate_component_scores().")

        if self.component_config is None:
            raise ValueError(
                "Run load_module1_config() before calculate_component_scores()."
            )

        scores = pd.DataFrame(index=self.features.index)
        for component_name, component in self.component_config["components"].items():
            score_config = component.get("score", {})
            output = score_config.get("output")
            function = score_config.get("function")

            if output is None:
                raise ValueError(f"Component {component_name} score is missing output.")

            normalization = score_config.get("normalization")
            normalization_horizon = score_config.get(
                "normalization_horizon",
                "normalization",
            )

            if score_config.get("state_transform") == "fixed_anchor":
                score = self._calculate_current_state_component_score(
                    component_name,
                    score_config,
                )
                score = self._clip_score(score, score_config.get("clip"))
                scores[output] = score
                continue

            if function == "single_feature_score":
                score = self._calculate_single_feature_component_score(
                    component_name,
                    score_config,
                    normalization,
                    normalization_horizon,
                )

            elif function == "weighted_feature_score":
                score = self._calculate_weighted_feature_component_score(
                    component_name,
                    score_config,
                    normalization,
                    normalization_horizon,
                )

            elif function == "curve_move_driver_score":
                score = self._calculate_curve_move_driver_score(
                    component_name,
                    score_config,
                )

            else:
                raise ValueError(
                    f"Unsupported score function for {component_name}: {function}"
                )

            score = self._smooth_score(score, score_config.get("smoothing"))
            score = self._clip_score(score, score_config.get("clip"))
            scores[output] = score

        self.scores = scores
        self.align_component_scores()
        return self.scores


    def calculate_component_labels(self) -> pd.DataFrame:
        if self.scores is None:
            raise ValueError("Run calculate_component_scores() before calculate_component_labels().")

        if self.component_config is None:
            raise ValueError(
                "Run load_module1_config() before calculate_component_labels()."
            )

        labels = pd.DataFrame(index=self.scores.index)

        def calculate_threshold_labels(component_name, source, label_config):
            thresholds = label_config.get("thresholds", {})
            label_names = label_config.get("labels", {})
            positive_threshold = thresholds.get("positive")
            negative_threshold = thresholds.get("negative")

            if positive_threshold is None or negative_threshold is None:
                raise ValueError(
                    f"Component {component_name} label thresholds are incomplete."
                )

            def label_score(value):
                if pd.isna(value):
                    return pd.NA
                if value >= positive_threshold:
                    return label_names.get("positive")
                if value <= negative_threshold:
                    return label_names.get("negative")
                return label_names.get("neutral")

            return self.scores[source].apply(label_score)

        def calculate_bucket_labels(component_name, source, label_config):
            label_names = label_config.get("labels", {})
            bucket_config = self._component_bucket_config(component_name)
            bucket_to_label_key = self._component_bucket_labels(component_name)

            def label_score(value):
                if pd.isna(value):
                    return pd.NA
                bucket_name = self._component_bucket_for_score(value, bucket_config)
                return label_names.get(bucket_to_label_key[bucket_name])

            return self.scores[source].apply(label_score)

        for component_name, component in self.component_config["components"].items():
            label_config = component.get("label", {})
            output = label_config.get("output")
            source = label_config.get("source")
            mode = label_config.get("mode")

            if output is None or source is None:
                raise ValueError(f"Component {component_name} label is missing output/source.")

            if source not in self.scores.columns:
                raise ValueError(f"Missing score for {component_name} label: {source}")

            if mode == "threshold":
                labels[output] = calculate_threshold_labels(
                    component_name,
                    source,
                    label_config,
                )
            elif mode == "bucket":
                labels[output] = calculate_bucket_labels(
                    component_name,
                    source,
                    label_config,
                )
            else:
                raise ValueError(
                    f"Unsupported label mode for {component_name}: {mode}"
                )

        self.labels = labels
        return labels


    def _label_stance_direction(
        self,
        score: float,
        direction_thresholds: dict,
        labels: dict,
    ):
        if pd.isna(score):
            return pd.NA

        if score >= direction_thresholds["positive_min"]:
            return labels.get("positive")

        if score <= direction_thresholds["negative_max"]:
            return labels.get("negative")

        return labels.get("neutral")


    def _label_stance_strength(
        self,
        score: float,
        direction_label,
        direction_labels: dict,
        strength_thresholds: dict,
        strength_labels: dict,
        neutral_strength: str,
    ):
        if pd.isna(score):
            return pd.NA

        if direction_label == direction_labels.get("neutral"):
            return strength_labels.get(neutral_strength, neutral_strength)

        abs_score = abs(score)

        if abs_score <= strength_thresholds["weak_max_abs"]:
            return strength_labels.get("weak")

        if abs_score <= strength_thresholds["moderate_max_abs"]:
            return strength_labels.get("moderate")

        if abs_score >= strength_thresholds["strong_min_abs"]:
            return strength_labels.get("strong")

        return strength_labels.get("moderate")


    def _stance_weight_terms(
        self,
        stance_name: str,
        stance_config: Mapping,
    ) -> list[tuple[str, float]]:
        if not isinstance(stance_config, Mapping):
            raise ValueError(
                f"Exposure stance {stance_name} configuration must be a mapping."
            )

        inputs = stance_config.get("inputs")
        if not isinstance(inputs, list) or not inputs:
            raise ValueError(
                f"Exposure stance {stance_name} inputs must be a non-empty list."
            )

        weighted_terms = []
        for idx, item in enumerate(inputs):
            if not isinstance(item, Mapping):
                raise ValueError(
                    f"Exposure stance {stance_name} inputs[{idx}] must be a mapping."
                )

            component_col = item.get("component")
            if component_col is None:
                raise ValueError(
                    f"Weighted stance target {stance_name} inputs[{idx}] "
                    "is missing component."
                )
            if component_col not in self.scores.columns:
                raise ValueError(
                    f"Missing component score column for weighted stance target "
                    f"{stance_name}: "
                    f"{component_col}"
                )

            if "weight" not in item:
                raise ValueError(
                    f"Weighted stance target {stance_name} inputs[{idx}] "
                    "is missing weight."
                )
            weight = item["weight"]
            if (
                isinstance(weight, bool)
                or not isinstance(weight, Real)
                or pd.isna(weight)
            ):
                raise ValueError(
                    f"Exposure stance {stance_name} inputs[{idx}].weight "
                    "must be numeric and not bool."
                )

            weighted_terms.append((component_col, float(weight)))

        return weighted_terms


    def _build_weighted_stance_score_breakdown(
        self,
        stance_name: str,
        stance_config: dict,
    ) -> pd.DataFrame:
        weighted_terms = self._stance_weight_terms(stance_name, stance_config)
        component_score_cols = [component_col for component_col, _ in weighted_terms]

        score_output = stance_config.get("score_output")
        if score_output is None:
            raise ValueError(f"Exposure stance {stance_name} score output is missing.")

        breakdown = self.scores[component_score_cols].copy()
        weighted_series_terms = []

        for component_col, weight in weighted_terms:
            weight_col = f"{component_col}_weight"
            contribution_col = f"{component_col}_contribution"
            breakdown[weight_col] = weight
            breakdown[contribution_col] = breakdown[component_col] * weight
            weighted_series_terms.append((breakdown[component_col], weight))

        breakdown[score_output] = self._weighted_sum_score(
            weighted_series_terms,
            context=f"Exposure stance {stance_name}",
        )
        return breakdown


    def _rule_mapped_thresholds_for_input(
        self,
        state_input: _RuleMappedStateInputSpec,
        stance_config: dict,
    ) -> dict:
        stance_thresholds = stance_config.get("state_thresholds")
        if isinstance(stance_thresholds, Mapping):
            positive = stance_thresholds.get("positive")
            negative = stance_thresholds.get("negative")
        else:
            component = self.component_config["components"].get(
                state_input.component_name,
                {},
            )
            thresholds = component.get("label", {}).get("thresholds", {})
            positive = thresholds.get("positive")
            negative = thresholds.get("negative")

        if (
            isinstance(positive, bool)
            or isinstance(negative, bool)
            or not isinstance(positive, Real)
            or not isinstance(negative, Real)
        ):
            raise ValueError(
                f"rule_mapped input {state_input.name} requires numeric positive "
                "and negative thresholds."
            )
        if negative >= positive:
            raise ValueError(
                f"rule_mapped input {state_input.name} threshold negative must be "
                "less than positive."
            )
        return {
            "positive": float(positive),
            "negative": float(negative),
        }


    def _rule_mapped_bucket_config_for_input(
        self,
        state_input: _RuleMappedStateInputSpec,
    ) -> dict:
        buckets = (
            self.component_config["components"]
            .get(state_input.component_name, {})
            .get("score", {})
            .get("buckets")
        )
        if not isinstance(buckets, dict) or not buckets:
            raise ValueError(
                f"rule_mapped input {state_input.name} requires component "
                f"{state_input.component_name} score.buckets."
            )
        return buckets


    def _rule_mapped_bucket_candidate(
        self,
        state_input: _RuleMappedStateInputSpec,
        bucket_config: dict,
        value,
        *,
        active_state=None,
        hysteresis_buffer: float = 0.0,
    ):
        if state_input.classification == "score_bucket":
            return self._score_bucket(value, bucket_config)

        if self._threshold_tail_default_bucket_parts(bucket_config) is not None:
            return self._threshold_bucket_hysteresis_candidate(
                value,
                active_state=active_state,
                hysteresis_buffer=hysteresis_buffer,
                bucket_config=bucket_config,
            )

        if self._is_ordered_threshold_bucket_config(bucket_config):
            return self._ordered_threshold_bucket_hysteresis_candidate(
                value,
                active_state=active_state,
                hysteresis_buffer=hysteresis_buffer,
                bucket_config=bucket_config,
            )

        return self._threshold_bucket(value, bucket_config)


    def _threshold_tail_default_bucket_parts(self, bucket_config: dict):
        min_buckets = [
            (bucket_name, rule["min"])
            for bucket_name, rule in bucket_config.items()
            if isinstance(rule, dict) and "min" in rule and "max" not in rule
        ]
        max_buckets = [
            (bucket_name, rule["max"])
            for bucket_name, rule in bucket_config.items()
            if isinstance(rule, dict) and "max" in rule and "min" not in rule
        ]
        default_buckets = [
            bucket_name
            for bucket_name, rule in bucket_config.items()
            if isinstance(rule, dict) and rule.get("default") is True
        ]
        if len(min_buckets) != 1 or len(max_buckets) != 1 or len(default_buckets) != 1:
            return None
        return min_buckets[0], max_buckets[0], default_buckets[0]


    def _is_ordered_threshold_bucket_config(self, bucket_config: dict) -> bool:
        if not isinstance(bucket_config, dict) or not bucket_config:
            return False
        range_fields = {"min", "max", "min_exclusive", "max_exclusive"}
        for rule in bucket_config.values():
            if not isinstance(rule, dict):
                return False
            if rule.get("default") is True or "score" in rule:
                return False
            if not any(field in rule for field in range_fields):
                return False
        return True


    def _rule_mapped_adjusted_row(
        self,
        state_tuple: tuple,
        score_tuple: tuple,
        base_score,
        spec: _RuleMappedStanceSpec,
        thresholds_by_input: dict[str, dict],
        buckets_by_input: dict[str, dict],
    ) -> dict:
        row = {}
        if spec.base_rule_score_output_col is not None:
            row[spec.base_rule_score_output_col] = base_score

        adjustment = spec.adjustment
        if adjustment is None:
            row[spec.score_output_col] = base_score
            return row

        for metadata_col in adjustment.metadata_output_cols:
            row[metadata_col] = pd.NA
        if adjustment.adjustment_output_col is not None:
            row[adjustment.adjustment_output_col] = pd.NA

        if (
            self._rule_state_is_missing(base_score)
            or any(self._rule_state_is_missing(state) for state in state_tuple)
            or any(pd.isna(score) for score in score_tuple)
        ):
            row[spec.score_output_col] = pd.NA
            return row

        intensities = []
        for state_input, score_value, state_value in zip(
            spec.state_inputs,
            score_tuple,
            state_tuple,
        ):
            if state_input.classification != "threshold_state":
                raise ValueError(
                    f"rule_mapped adjustment for {spec.stance_name} only supports "
                    "threshold_state inputs."
                )
            intensity = self._credit_spread_state_intensity(
                score_value,
                state_value,
                thresholds_by_input[state_input.name],
                buckets_by_input[state_input.name],
            )
            intensities.append(intensity)

        for metadata_col, intensity in zip(
            adjustment.metadata_output_cols,
            intensities,
        ):
            row[metadata_col] = intensity

        adjusted_score, rule_adjustment = self._adjust_credit_spread_rule_score(
            base_score,
            tuple(str(state) for state in state_tuple),
            intensities[0],
            intensities[1],
            adjustment.config,
        )
        if adjustment.adjustment_output_col is not None:
            row[adjustment.adjustment_output_col] = rule_adjustment
        row[spec.score_output_col] = adjusted_score
        return row


    def _build_rule_mapped_stance_score_breakdown(
        self,
        stance_name: str,
        stance_config: dict,
        *,
        stabilization_overrides: dict | None = None,
    ) -> pd.DataFrame:
        spec = self._resolve_rule_mapped_stance_schema(stance_name, stance_config)
        required_score_cols = [
            state_input.source_score_col for state_input in spec.state_inputs
        ]
        self._validate_required_score_columns(
            required_score_cols,
            context=f"rule_mapped stance {stance_name}",
        )

        stabilization_config = spec.stabilization_config
        if stabilization_overrides is not None:
            stabilization_config = _resolve_rule_mapped_stabilization_config(
                {"state_stabilization": stabilization_overrides},
                [state_input.name for state_input in spec.state_inputs],
                context=f"rule_mapped stance {stance_name}",
            )

        breakdown = self.scores[required_score_cols].copy()
        state_detail = pd.DataFrame(index=breakdown.index)
        thresholds_by_input = {}
        buckets_by_input = {}
        for state_input in spec.state_inputs:
            score = breakdown[state_input.source_score_col]
            if state_input.classification == "threshold_state":
                thresholds = self._rule_mapped_thresholds_for_input(
                    state_input,
                    stance_config,
                )
                buckets = dict(state_input.state_buckets)
                thresholds_by_input[state_input.name] = thresholds
                buckets_by_input[state_input.name] = buckets
                state_detail[state_input.raw_output_col] = score.apply(
                    lambda value, thresholds=thresholds, buckets=buckets: (
                        self._threshold_state_from_score(value, thresholds, buckets)
                    )
                )
                state_detail[state_input.stabilized_output_col] = (
                    self._stabilize_state_series(
                        score,
                        lambda value, active_state, hysteresis_buffer, thresholds=thresholds, buckets=buckets: self._threshold_hysteresis_candidate(
                            value,
                            thresholds=thresholds,
                            positive_label=buckets["positive"],
                            neutral_label=buckets["neutral"],
                            negative_label=buckets["negative"],
                            active_state=active_state,
                            hysteresis_buffer=hysteresis_buffer,
                        ),
                        hysteresis_buffer=stabilization_config[state_input.name][
                            "hysteresis_buffer"
                        ],
                        min_state_persistence=stabilization_config[state_input.name][
                            "min_state_persistence"
                        ],
                    )
                )
            elif state_input.classification in {"threshold_bucket", "score_bucket"}:
                bucket_config = self._rule_mapped_bucket_config_for_input(state_input)
                state_detail[state_input.raw_output_col] = score.apply(
                    lambda value, state_input=state_input, bucket_config=bucket_config: (
                        self._score_bucket(value, bucket_config)
                        if state_input.classification == "score_bucket"
                        else self._threshold_bucket(value, bucket_config)
                    )
                )
                state_detail[state_input.stabilized_output_col] = (
                    self._stabilize_state_series(
                        score,
                        lambda value, active_state, hysteresis_buffer, state_input=state_input, bucket_config=bucket_config: self._rule_mapped_bucket_candidate(
                            state_input,
                            bucket_config,
                            value,
                            active_state=active_state,
                            hysteresis_buffer=hysteresis_buffer,
                        ),
                        hysteresis_buffer=stabilization_config[state_input.name][
                            "hysteresis_buffer"
                        ],
                        min_state_persistence=stabilization_config[state_input.name][
                            "min_state_persistence"
                        ],
                    )
                )
            else:
                raise ValueError(
                    f"Unsupported rule_mapped classification for {state_input.name}: "
                    f"{state_input.classification}"
                )

        if spec.adjustment is not None:
            missing_adjustment_input = breakdown[required_score_cols].isna().any(axis=1)
            for state_input in spec.state_inputs:
                state_detail.loc[
                    missing_adjustment_input,
                    state_input.stabilized_output_col,
                ] = pd.NA

        for state_input in spec.state_inputs:
            state_detail[state_input.stabilization_changed_output_col] = (
                state_detail[state_input.raw_output_col]
                != state_detail[state_input.stabilized_output_col]
            ) & state_detail[state_input.raw_output_col].notna()

        changed_cols = [
            state_input.stabilization_changed_output_col
            for state_input in spec.state_inputs
        ]
        state_detail[spec.stabilization_changed_any_output_col] = (
            state_detail[changed_cols].any(axis=1)
        )

        rule_rows = []
        for idx, row in state_detail.iterrows():
            state_tuple = tuple(
                row[state_input.stabilized_output_col]
                for state_input in spec.state_inputs
            )
            score_tuple = tuple(
                breakdown.loc[idx, state_input.source_score_col]
                for state_input in spec.state_inputs
            )
            rule_case = self._rule_case_from_states(state_tuple)
            base_score = self._lookup_rule_score(
                state_tuple,
                spec.rule_scores,
                context=f"rule_mapped stance {stance_name}",
            )
            rule_row = {spec.rule_case_output_col: rule_case}
            rule_row.update(
                self._rule_mapped_adjusted_row(
                    state_tuple,
                    score_tuple,
                    base_score,
                    spec,
                    thresholds_by_input,
                    buckets_by_input,
                )
            )
            rule_rows.append(rule_row)

        rule_detail = pd.DataFrame(rule_rows, index=breakdown.index)
        if spec.score_output_col in rule_detail:
            rule_detail[spec.score_output_col] = pd.to_numeric(
                rule_detail[spec.score_output_col],
                errors="coerce",
            )
        return pd.concat([breakdown, state_detail, rule_detail], axis=1)


    def _threshold_bucket_hysteresis_candidate(
        self,
        value: float,
        *,
        active_state=None,
        hysteresis_buffer: float = 0.0,
        bucket_config=None,
    ) -> str:
        if pd.isna(value):
            return pd.NA
        if hysteresis_buffer == 0.0:
            return self._threshold_bucket(value, bucket_config)

        bucket_parts = self._threshold_tail_default_bucket_parts(bucket_config)
        if bucket_parts is None:
            raise ValueError(
                "Threshold buckets must define one min, one max, and one default bucket."
            )

        (
            (positive_bucket, positive_threshold),
            (negative_bucket, negative_threshold),
            neutral_bucket,
        ) = bucket_parts
        buffer = hysteresis_buffer

        if active_state == positive_bucket:
            if value >= positive_threshold - buffer:
                return positive_bucket
            if value <= negative_threshold - buffer:
                return negative_bucket
            return neutral_bucket

        if active_state == negative_bucket:
            if value <= negative_threshold + buffer:
                return negative_bucket
            if value >= positive_threshold + buffer:
                return positive_bucket
            return neutral_bucket

        if value >= positive_threshold + buffer:
            return positive_bucket
        if value <= negative_threshold - buffer:
            return negative_bucket
        return neutral_bucket


    def _ordered_threshold_buckets(self, bucket_config: dict) -> list[dict]:
        ordered = []
        for bucket_name, rule in bucket_config.items():
            if not isinstance(rule, dict):
                raise ValueError(f"Curve bucket {bucket_name} must be a mapping.")
            lower = None
            lower_inclusive = True
            upper = None
            upper_inclusive = True
            if "min" in rule:
                lower = float(rule["min"])
                lower_inclusive = True
            if "min_exclusive" in rule:
                lower = float(rule["min_exclusive"])
                lower_inclusive = False
            if "max" in rule:
                upper = float(rule["max"])
                upper_inclusive = True
            if "max_exclusive" in rule:
                upper = float(rule["max_exclusive"])
                upper_inclusive = False
            ordered.append(
                {
                    "name": bucket_name,
                    "lower": lower,
                    "lower_inclusive": lower_inclusive,
                    "upper": upper,
                    "upper_inclusive": upper_inclusive,
                }
            )
        return sorted(
            ordered,
            key=lambda item: float("-inf") if item["lower"] is None else item["lower"],
        )


    def _value_in_expanded_interval(
        self,
        value: float,
        interval: dict,
        buffer: float,
    ) -> bool:
        lower = interval["lower"]
        if lower is not None:
            lower_value = lower - buffer
            if interval["lower_inclusive"]:
                if value < lower_value:
                    return False
            elif value <= lower_value:
                return False

        upper = interval["upper"]
        if upper is not None:
            upper_value = upper + buffer
            if interval["upper_inclusive"]:
                if value > upper_value:
                    return False
            elif value >= upper_value:
                return False

        return True


    def _ordered_threshold_bucket_hysteresis_candidate(
        self,
        value: float,
        *,
        active_state=None,
        hysteresis_buffer: float = 0.0,
        bucket_config=None,
    ) -> str:
        if pd.isna(value):
            return pd.NA
        if active_state is None or hysteresis_buffer == 0.0:
            return self._threshold_bucket(value, bucket_config)

        ordered = self._ordered_threshold_buckets(bucket_config)
        active_interval = next(
            (interval for interval in ordered if interval["name"] == active_state),
            None,
        )
        if active_interval is not None and self._value_in_expanded_interval(
            float(value),
            active_interval,
            hysteresis_buffer,
        ):
            return active_state

        for idx, interval in enumerate(ordered[:-1]):
            upper = interval["upper"]
            if upper is None:
                continue
            boundary = upper - hysteresis_buffer if idx == 0 else upper + hysteresis_buffer
            if interval["upper_inclusive"]:
                if value <= boundary:
                    return interval["name"]
            elif value < boundary:
                return interval["name"]
        return ordered[-1]["name"]


    def _threshold_state_from_score(
        self,
        value: float,
        thresholds: dict,
        buckets: dict,
    ):
        if pd.isna(value):
            return pd.NA
        if value >= thresholds["positive"]:
            return buckets["positive"]
        if value <= thresholds["negative"]:
            return buckets["negative"]
        return buckets["neutral"]


    def _credit_spread_state_intensity(
        self,
        value: float,
        state: str,
        thresholds: dict,
        state_buckets: dict,
    ) -> float:
        if state == state_buckets["neutral"]:
            return 0.0
        if state == state_buckets["positive"]:
            threshold = thresholds["positive"]
            if threshold == 0:
                return 0.0
            intensity = (value - threshold) / threshold
        elif state == state_buckets["negative"]:
            threshold = thresholds["negative"]
            if threshold == 0:
                return 0.0
            intensity = (threshold - value) / abs(threshold)
        else:
            raise ValueError(f"Unsupported credit component state: {state}")

        return min(max(float(intensity), 0.0), 1.0)


    def _apply_state_persistence(
        self,
        candidate_states: pd.Series,
        min_state_persistence: int,
    ) -> pd.Series:
        if min_state_persistence <= 1:
            return candidate_states.copy()

        persisted = pd.Series(index=candidate_states.index, dtype="object")
        active_state = None
        pending_state = None
        pending_count = 0

        for idx, candidate_state in candidate_states.items():
            if pd.isna(candidate_state):
                persisted.loc[idx] = pd.NA
                pending_state = None
                pending_count = 0
                continue

            if active_state is None:
                active_state = candidate_state
                persisted.loc[idx] = active_state
                continue

            if candidate_state == active_state:
                pending_state = None
                pending_count = 0
                persisted.loc[idx] = active_state
                continue

            if candidate_state == pending_state:
                pending_count += 1
            else:
                pending_state = candidate_state
                pending_count = 1

            if pending_count >= min_state_persistence:
                active_state = candidate_state
                pending_state = None
                pending_count = 0

            persisted.loc[idx] = active_state

        return persisted


    def _classify_state_series_with_hysteresis(
        self,
        score: pd.Series,
        classify_candidate,
        *,
        hysteresis_buffer: float = 0.0,
    ) -> pd.Series:
        states = pd.Series(index=score.index, dtype="object")
        active_state = None

        for idx, value in score.items():
            if pd.isna(value):
                states.loc[idx] = pd.NA
                continue

            candidate_state = classify_candidate(
                value,
                active_state=active_state,
                hysteresis_buffer=hysteresis_buffer,
            )
            states.loc[idx] = candidate_state
            active_state = candidate_state

        return states


    def _stabilize_state_series(
        self,
        score: pd.Series,
        classify_candidate,
        *,
        hysteresis_buffer: float = 0.0,
        min_state_persistence: int = 1,
    ) -> pd.Series:
        candidate_states = self._classify_state_series_with_hysteresis(
            score,
            classify_candidate,
            hysteresis_buffer=hysteresis_buffer,
        )
        return self._apply_state_persistence(
            candidate_states,
            min_state_persistence,
        )


    def _threshold_hysteresis_candidate(
        self,
        value: float,
        *,
        thresholds: dict,
        positive_label: str,
        neutral_label: str,
        negative_label: str,
        active_state,
        hysteresis_buffer: float,
    ) -> str:
        positive_threshold = thresholds["positive"]
        negative_threshold = thresholds["negative"]
        positive_entry = positive_threshold + hysteresis_buffer
        positive_exit = positive_threshold - hysteresis_buffer
        negative_entry = negative_threshold - hysteresis_buffer
        negative_exit = negative_threshold + hysteresis_buffer

        if active_state == positive_label:
            if value >= positive_exit:
                return positive_label
            if value <= negative_entry:
                return negative_label
            return neutral_label

        if active_state == negative_label:
            if value <= negative_exit:
                return negative_label
            if value >= positive_entry:
                return positive_label
            return neutral_label

        if value >= positive_entry:
            return positive_label
        if value <= negative_entry:
            return negative_label
        return neutral_label


    def _adjust_credit_spread_rule_score(
        self,
        base_score: float,
        state: tuple[str, str],
        change_intensity: float,
        level_intensity: float,
        rule_adjustments: dict,
    ) -> tuple[float, float]:
        change_state_name, level_state_name = state
        pair_key = f"{change_state_name}|{level_state_name}"
        adjustment_config = rule_adjustments["states"].get(pair_key)
        if not isinstance(adjustment_config, dict):
            raise ValueError(f"Missing credit rule adjustment for state pair: {pair_key}")

        change_weight = float(adjustment_config["change_intensity_weight"])
        level_weight = float(adjustment_config["level_intensity_weight"])
        adjustment = change_weight * change_intensity + level_weight * level_intensity

        default_cap = rule_adjustments["default_cap"]
        pair_cap = adjustment_config.get("cap") or {}
        lower_cap = float(pair_cap.get("min", default_cap["min"]))
        upper_cap = float(pair_cap.get("max", default_cap["max"]))

        adjusted_score = min(max(base_score + adjustment, lower_cap), upper_cap)
        return adjusted_score, adjusted_score - base_score


    def _calculate_exposure_stance_score(
        self,
        stance_name: str,
        stance_config: dict,
    ) -> pd.Series:
        function = stance_config.get("function")

        if function == "weighted_sum":
            score_output = stance_config.get("score_output")
            if score_output is None:
                raise ValueError(f"Exposure stance {stance_name} score output is missing.")

            breakdown = self._build_weighted_stance_score_breakdown(
                stance_name,
                stance_config,
            )
            return breakdown[score_output]

        if function in {
            "curve_positioning_stance",
            "duration_rule_stance",
            "credit_spread_stance",
        }:
            score_output = stance_config.get("score_output")
            if score_output is None:
                raise ValueError(f"Exposure stance {stance_name} score output is missing.")

            breakdown = self._build_rule_mapped_stance_score_breakdown(
                stance_name,
                stance_config,
            )
            return breakdown[score_output]

        raise ValueError(
            f"Unsupported exposure stance function for {stance_name}: {function}"
        )


    def calculate_exposure_stance(self) -> pd.DataFrame:
        if self.scores is None:
            raise ValueError("Run calculate_component_scores() before calculate_exposure_stance().")

        if self.exposure_stance_config is None:
            raise ValueError(
                "Run load_module1_config() before calculate_exposure_stance()."
            )

        rules = self.exposure_stance_config["stance_label_rules"]
        direction_thresholds = rules.get("direction_thresholds", {})
        strength_thresholds = rules.get("strength_thresholds", {})
        neutral_strength = rules.get("neutral_strength", "weak")

        for key in ["positive_min", "negative_max"]:
            if key not in direction_thresholds:
                raise ValueError(f"Missing direction threshold: {key}")

        for key in ["weak_max_abs", "moderate_max_abs", "strong_min_abs"]:
            if key not in strength_thresholds:
                raise ValueError(f"Missing strength threshold: {key}")

        stance_scores = pd.DataFrame(index=self.scores.index)
        exposure_stance = pd.DataFrame(index=self.scores.index)

        for stance_name, stance_config in self.exposure_stance_config[
            "exposure_stances"
        ].items():
            score_output = stance_config.get("score_output")
            stance_output = stance_config.get("stance_output")
            strength_output = stance_config.get("strength_output")

            if score_output is None or stance_output is None or strength_output is None:
                raise ValueError(f"Exposure stance {stance_name} outputs are incomplete.")

            score = self._calculate_exposure_stance_score(
                stance_name,
                stance_config,
            )
            labels = stance_config.get("labels", {})
            direction_labels = labels.get("direction", {})
            strength_labels = labels.get("strength", {})

            direction = score.apply(
                lambda value: self._label_stance_direction(
                    value,
                    direction_thresholds,
                    direction_labels,
                )
            )
            strength = pd.Series(index=score.index, dtype="object")

            for idx, value in score.items():
                strength.loc[idx] = self._label_stance_strength(
                    value,
                    direction.loc[idx],
                    direction_labels,
                    strength_thresholds,
                    strength_labels,
                    neutral_strength,
                )

            stance_scores[score_output] = score
            exposure_stance[score_output] = score
            exposure_stance[stance_output] = direction
            exposure_stance[strength_output] = strength

        self.stance_scores = stance_scores
        self.exposure_stance = exposure_stance
        return exposure_stance


    def run_module1_pipeline(
        self,
    ) -> pd.DataFrame:
        """
        Calculate Module 1 outputs from loaded core files.
        """
        self.calculate_features()
        self.calculate_component_scores()
        self.calculate_component_labels()
        self.calculate_exposure_stance()
        return self.exposure_stance


    @staticmethod
    def _copy_module1_result_value(value):
        if value is None:
            return None
        if isinstance(value, pd.DataFrame):
            return value.copy(deep=True)
        if isinstance(value, pd.Series):
            return value.copy(deep=True)
        return copy.deepcopy(value)


    def to_module1_result(self) -> Module1Result:
        """
        Return a safe snapshot of completed Module 1 runtime outputs.

        This method does not run or rerun any pipeline step. It only validates
        that the completed-output tables already exist and copies the current
        state into a Module1Result.
        """
        required_outputs = {
            "features": self.features,
            "scores": self.scores,
            "labels": self.labels,
            "stance_scores": self.stance_scores,
            "exposure_stance": self.exposure_stance,
        }
        missing = [
            name
            for name, value in required_outputs.items()
            if value is None
        ]
        if missing:
            missing_text = ", ".join(missing)
            raise ValueError(
                "Cannot build Module1Result before completed Module 1 outputs "
                f"exist. Missing: {missing_text}. Run run_module1_pipeline() or "
                "the required calculation steps first."
            )

        return Module1Result(
            data=self._copy_module1_result_value(self.data),
            features=self._copy_module1_result_value(self.features),
            scores=self._copy_module1_result_value(self.scores),
            labels=self._copy_module1_result_value(self.labels),
            stance_scores=self._copy_module1_result_value(self.stance_scores),
            exposure_stance=self._copy_module1_result_value(self.exposure_stance),
            module1_config=self._copy_module1_result_value(self.module1_config),
            feature_config=self._copy_module1_result_value(self.feature_config),
            component_config=self._copy_module1_result_value(self.component_config),
            exposure_stance_config=self._copy_module1_result_value(
                self.exposure_stance_config
            ),
            horizons=self._copy_module1_result_value(self.horizons),
            default_horizons=self._copy_module1_result_value(self.default_horizons),
            horizon_overrides=self._copy_module1_result_value(self.horizon_overrides),
            module1_config_validation=self._copy_module1_result_value(
                self.module1_config_validation
            ),
        )
