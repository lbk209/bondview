import warnings
import copy
from itertools import product
from dataclasses import dataclass, field, replace
from numbers import Real
from collections.abc import Mapping

import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from tqdm.notebook import tqdm

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
        """
        Normalize explicit horizon cases or a Cartesian horizon grid.
        """
        if (horizon_cases is None) == (horizon_grid is None):
            raise ValueError("Provide exactly one of horizon_cases or horizon_grid.")

        if horizon_cases is not None:
            if isinstance(horizon_cases, pd.DataFrame):
                cases_df = horizon_cases.copy()
            elif isinstance(horizon_cases, list):
                cases_df = pd.DataFrame(horizon_cases)
            else:
                raise ValueError(
                    "horizon_cases must be a pandas DataFrame or a list of dicts."
                )
        else:
            if not isinstance(horizon_grid, dict):
                raise ValueError("horizon_grid must be a dict.")

            import itertools

            keys = list(horizon_grid)
            values = []
            for key in keys:
                value = horizon_grid[key]
                if isinstance(value, (list, tuple)):
                    values.append(list(value))
                else:
                    values.append([value])

            rows = [
                dict(zip(keys, combination))
                for combination in itertools.product(*values)
            ]
            cases_df = pd.DataFrame(rows)

        if cases_df.empty:
            raise ValueError("No horizon cases were provided.")
        if len(cases_df) > max_cases:
            raise ValueError(
                f"Generated {len(cases_df)} horizon cases, which exceeds "
                f"max_cases={max_cases}."
            )

        cases_df = cases_df.reset_index(drop=True)
        if "case_id" not in cases_df.columns:
            cases_df.insert(
                0,
                "case_id",
                [f"case_{idx:03d}" for idx in range(len(cases_df))],
            )
        else:
            cases_df["case_id"] = cases_df["case_id"].fillna("").astype(str)
            missing_case_ids = cases_df["case_id"].str.strip() == ""
            cases_df.loc[missing_case_ids, "case_id"] = [
                f"case_{idx:03d}" for idx in cases_df.index[missing_case_ids]
            ]

        if cases_df["case_id"].duplicated().any():
            duplicates = sorted(cases_df.loc[
                cases_df["case_id"].duplicated(),
                "case_id",
            ].unique())
            raise ValueError(f"horizon case_id values must be unique: {duplicates}")

        return cases_df


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
        """
        Compare multiple horizon configurations with historical review outputs.

        This is a batch diagnostic, not an optimizer or tuning function. Horizon
        cases override base_horizons only inside a temporary RegimeModule instance
        created by this method, so caller-created instances are not mutated. If
        base_horizons is None, the default horizons are used as the base.

        Returns exactly one selected flat DataFrame controlled by output. The
        default output is "summary", which returns one row per horizon case based
        on review_historical_cases(output="report"). output="horizon_cases"
        returns the normalized horizon settings. output="compact", "cases", and
        "diagnostic" return concatenated review_historical_cases outputs across
        horizon cases with case_id and horizon columns inserted.

        Main output values are:
        - "summary"
        - "horizon_cases"
        - "compact"
        - "cases"
        - "diagnostic"

        Other review_historical_cases(output=...) values may also be used for
        advanced inspection, such as "detail", "windows", "label_distribution",
        "strength_distribution", and "report".
        """
        normalized_output = (
            output if pd.isna(output) else str(output).strip().lower()
        )
        main_outputs = {"summary", "horizon_cases", "compact", "cases", "diagnostic"}
        review_outputs = {
            "cases",
            "compact",
            "diagnostic",
            "detail",
            "report",
            "windows",
            "label_distribution",
            "strength_distribution",
        }
        if normalized_output not in {"summary", "horizon_cases"} | review_outputs:
            raise ValueError(
                f"Unsupported compare_horizon_cases output: {output}. "
                f"Main outputs are: {', '.join(sorted(main_outputs))}. "
                "Other review_historical_cases output values may also be available "
                "for advanced inspection."
            )

        horizon_cases_df = cls._build_horizon_cases_df(
            horizon_cases=horizon_cases,
            horizon_grid=horizon_grid,
            max_cases=max_cases,
        )
        if normalized_output == "horizon_cases":
            return horizon_cases_df

        rgm = cls(
            api_key_env=api_key_env,
            series_config_path=series_config_path,
            module1_config_path=module1_config_path,
            data_path=data_path,
        )
        rgm.load_historical_context(historical_context_path)

        base_horizons = rgm.validate_horizons(
            base_horizons,
            base_horizons=rgm.default_horizons,
        )
        horizon_columns = [
            col for col in horizon_cases_df.columns if col != "case_id"
        ]
        unknown_cols = set(horizon_columns).difference(base_horizons)
        if unknown_cols:
            raise ValueError(f"Unknown horizon case columns: {sorted(unknown_cols)}")

        summary_rows = []
        output_tables = []

        for _, case in tqdm(horizon_cases_df.iterrows(), total=len(horizon_cases_df)):
            case_id = case["case_id"]
            case_overrides = {}
            for col in horizon_columns:
                value = case[col]
                if pd.isna(value):
                    continue
                if hasattr(value, "item"):
                    value = value.item()
                if isinstance(value, float) and value.is_integer():
                    value = int(value)
                case_overrides[col] = value
            case_horizons = rgm.validate_horizons(
                case_overrides,
                base_horizons=base_horizons,
            )
            rgm.horizons = case_horizons

            rgm.features = None
            rgm.scores = None
            rgm.labels = None
            rgm.stance_scores = None
            rgm.exposure_stance = None

            rgm.calculate_features()
            rgm.calculate_component_scores()
            rgm.calculate_component_labels()
            rgm.calculate_exposure_stance()

            metadata = {"case_id": case_id}
            metadata.update({key: case_horizons[key] for key in base_horizons})

            review_output = (
                "report" if normalized_output == "summary" else normalized_output
            )
            review_table = rgm.review_historical_cases(
                target=target,
                context_id=context_id,
                level=level,
                only_use_for_validation=only_use_for_validation,
                include_low_relevance=include_low_relevance,
                min_obs=min_obs,
                plausible_threshold=plausible_threshold,
                mixed_threshold=mixed_threshold,
                output=review_output,
            )

            if normalized_output == "summary":
                report_values = review_table.set_index("metric")["value"].to_dict()
                summary_rows.append({**metadata, **report_values})
                continue

            review_table = review_table.copy()
            for col, value in reversed(list(metadata.items())):
                review_table.insert(0, col, value)
            output_tables.append(review_table)

        if normalized_output == "summary":
            return pd.DataFrame(summary_rows)

        if output_tables:
            return pd.concat(output_tables, ignore_index=True)
        return pd.DataFrame()
        

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


    def _calculate_component_score_for_input_preparation_diagnostic(
        self,
        component_name: str,
        score_config: dict,
        *,
        apply_input_preparation: bool,
    ) -> pd.Series:
        function = score_config.get("function")

        if score_config.get("state_transform") == "fixed_anchor":
            score = self._calculate_current_state_component_score(
                component_name,
                score_config,
                apply_input_preparation=apply_input_preparation,
            )
            return self._clip_score(score, score_config.get("clip"))

        normalization = score_config.get("normalization")
        normalization_horizon = score_config.get(
            "normalization_horizon",
            "normalization",
        )

        if function == "single_feature_score":
            score = self._calculate_single_feature_component_score(
                component_name,
                score_config,
                normalization,
                normalization_horizon,
                apply_input_preparation=apply_input_preparation,
            )
        elif function == "weighted_feature_score":
            score = self._calculate_weighted_feature_component_score(
                component_name,
                score_config,
                normalization,
                normalization_horizon,
                apply_input_preparation=apply_input_preparation,
            )
        elif function == "curve_move_driver_score":
            score = self._calculate_curve_move_driver_score(
                component_name,
                score_config,
                apply_input_preparation=apply_input_preparation,
            )
        else:
            raise ValueError(
                f"Unsupported score function for diagnostic component {component_name}: "
                f"{function}"
            )

        return self._clip_score(score, score_config.get("clip"))


    def _recalculate_component_scores_for_input_preparation_diagnostic(
        self,
        target: str,
        *,
        apply_input_preparation: bool,
        output_prefix: str,
    ) -> pd.DataFrame:
        if self.features is None:
            raise ValueError(
                "Run calculate_features() before recalculating diagnostic component scores."
            )
        if self.component_config is None or self.exposure_stance_config is None:
            raise ValueError(
                "Run load_module1_config() before recalculating diagnostic component scores."
            )

        component_names = self._diagnostic_component_names_for_target(target)
        if component_names is None:
            raise ValueError(f"Unable to resolve diagnostic components for target: {target}")

        recalculated = pd.DataFrame(index=self.features.index)
        components = self.component_config["components"]
        for component_name in component_names:
            score_config = components[component_name].get("score", {})
            output = score_config.get("output")
            if not isinstance(output, str) or output.strip() == "":
                raise ValueError(f"Component {component_name} score is missing output.")
            recalculated[f"{output_prefix}{output}"] = (
                self._calculate_component_score_for_input_preparation_diagnostic(
                    component_name,
                    score_config,
                    apply_input_preparation=apply_input_preparation,
                )
            )

        return recalculated


    def _stance_labels_for_score(
        self,
        score: pd.Series,
        stance_config: dict,
    ) -> tuple[pd.Series, pd.Series]:
        rules = self.exposure_stance_config["stance_label_rules"]
        direction_thresholds = rules.get("direction_thresholds", {})
        strength_thresholds = rules.get("strength_thresholds", {})
        neutral_strength = rules.get("neutral_strength", "weak")
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
        return direction, strength


    def _reconstruct_rule_mapped_stance_for_input_preparation_diagnostic(
        self,
        target: str,
        alternate_scores: pd.DataFrame,
    ) -> dict[str, pd.Series]:
        if self.scores is None:
            raise ValueError(
                "Run calculate_component_scores() before reconstructing diagnostic stances."
            )
        if self.exposure_stance_config is None:
            raise ValueError(
                "Run load_module1_config() before reconstructing diagnostic stances."
            )

        context = self._resolve_rule_mapped_diagnostic_config(target)
        spec = self._derive_rule_mapped_diagnostic_spec_from_context(context)
        stance_config = context["stance_config"]
        temporary_scores = self.scores.copy()
        for score_col in spec.score_input_cols:
            alternate_col = f"raw_{score_col}"
            if alternate_col not in alternate_scores.columns:
                raise ValueError(
                    f"Missing alternate diagnostic score column for {target}: "
                    f"{alternate_col}"
                )
            temporary_scores[score_col] = alternate_scores[alternate_col]

        original_scores = self.scores
        try:
            self.scores = temporary_scores
            reconstruction = self._build_rule_mapped_stance_score_breakdown(
                spec.target,
                stance_config,
            )
        finally:
            self.scores = original_scores

        score = reconstruction[spec.final_score_col]
        direction, strength = self._stance_labels_for_score(score, stance_config)
        return {
            "score": score,
            "direction": direction,
            "strength": strength,
        }


    def _rule_mapped_component_parameter_effect_detail(
        self,
        target: str,
        component_score_col: str,
        baseline_score: pd.Series,
        alternate_score: pd.Series,
        *,
        baseline_component_output: str,
        alternate_component_output: str,
        baseline_stance_output: str,
        alternate_stance_output: str,
        stance_diff_output: str,
        component_changed_output: str,
        stance_changed_output: str,
    ) -> pd.DataFrame:
        if self.scores is None:
            raise ValueError(
                "Run calculate_component_scores() before comparing parameter effects."
            )

        context = self._resolve_rule_mapped_diagnostic_config(target)
        spec = self._derive_rule_mapped_diagnostic_spec_from_context(context)
        if component_score_col not in spec.score_input_cols:
            raise ValueError(
                f"{component_score_col} is not an input to rule-mapped stance {target}."
            )

        def scenario_scores(scenario_component_score: pd.Series) -> pd.DataFrame:
            scenario = pd.DataFrame(index=self.scores.index)
            for score_col in spec.score_input_cols:
                scenario[f"raw_{score_col}"] = (
                    scenario_component_score
                    if score_col == component_score_col
                    else self.scores[score_col]
                )
            return scenario

        baseline_stance = (
            self._reconstruct_rule_mapped_stance_for_input_preparation_diagnostic(
                target,
                scenario_scores(baseline_score),
            )["score"]
        )
        alternate_stance = (
            self._reconstruct_rule_mapped_stance_for_input_preparation_diagnostic(
                target,
                scenario_scores(alternate_score),
            )["score"]
        )

        detail = pd.DataFrame(index=self.scores.index)
        detail[baseline_component_output] = baseline_score
        detail[alternate_component_output] = alternate_score
        detail[baseline_stance_output] = baseline_stance
        detail[alternate_stance_output] = alternate_stance
        detail[stance_diff_output] = (
            detail[alternate_stance_output] - detail[baseline_stance_output]
        )
        detail[component_changed_output] = self._series_mismatch_mask(
            detail[baseline_component_output],
            detail[alternate_component_output],
            tolerance=1e-10,
        )
        detail[stance_changed_output] = self._series_mismatch_mask(
            detail[baseline_stance_output],
            detail[alternate_stance_output],
            tolerance=1e-10,
        )
        return detail


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


    def load_historical_context(
        self,
        historical_context_path,
        validate_expected_labels: bool = True,
        raise_on_invalid_expected_labels: bool = True,
    ) -> dict:
        """
        Load historical_context.yaml with strict expected-label validation.

        Historical expectations are checked against the already-loaded
        module1_config.yaml, which is the source of truth for label vocabulary.
        In strict mode, invalid historical context raises ValueError and is not
        assigned to object state.
        """
        config = self._load_yaml_config(historical_context_path)
        context = config.get("historical_context", config)

        required = {"events", "expectations"}
        missing = required.difference(context)
        if missing:
            missing = ", ".join(sorted(missing))
            raise ValueError(
                "historical_context is missing required top-level keys: "
                f"{missing}"
            )

        events = pd.DataFrame(context["events"])
        expectations = pd.DataFrame(context["expectations"])

        if events.empty:
            raise ValueError("historical_context events must not be empty.")
        if expectations.empty:
            raise ValueError("historical_context expectations must not be empty.")

        required_event_cols = {"context_id", "start", "end"}
        missing = required_event_cols.difference(events.columns)
        if missing:
            missing = ", ".join(sorted(missing))
            raise ValueError(f"historical_context events missing columns: {missing}")

        required_expectation_cols = {
            "context_id",
            "target",
            "level",
            "expected_label",
        }
        missing = required_expectation_cols.difference(expectations.columns)
        if missing:
            missing = ", ".join(sorted(missing))
            raise ValueError(
                f"historical_context expectations missing columns: {missing}"
            )

        events = events.copy()
        expectations = expectations.copy()
        events["start"] = pd.to_datetime(events["start"])
        events["end"] = pd.to_datetime(events["end"])

        if "use_for_validation" not in events.columns:
            events["use_for_validation"] = True
        events["use_for_validation"] = events["use_for_validation"].fillna(True)

        if "expected_strength" not in expectations.columns:
            expectations["expected_strength"] = pd.NA
        if "relevance" not in expectations.columns:
            expectations["relevance"] = "medium"
        expectations["relevance"] = expectations["relevance"].fillna("medium")
        expectations["level"] = expectations["level"].apply(
            self._normalize_review_label
        )

        historical_cases = self._build_historical_cases(events, expectations)

        validation = None
        if validate_expected_labels:
            validation = self._validate_historical_expected_labels_from_cases(
                historical_cases
            )
            self.historical_expected_label_validation = validation
            issues = validation["issues"]
            if not issues.empty:
                report = validation["report"].iloc[0]
                message = (
                    "Invalid historical_context.yaml expected labels: "
                    f"{int(report['invalid_label_cases'])} invalid expected_label "
                    "case(s), "
                    f"{int(report['invalid_strength_cases'])} invalid "
                    "expected_strength case(s), "
                    f"{int(report['non_applicable_strength_cases'])} "
                    "non-applicable expected_strength case(s). Inspect "
                    'self.historical_expected_label_validation["issues"] or run '
                    "validate_historical_expected_labels()."
                )
                if raise_on_invalid_expected_labels:
                    raise ValueError(message)
                warnings.warn(message, UserWarning)

        self.historical_context = {
            "events": events,
            "expectations": expectations,
        }
        self.historical_cases = historical_cases
        if validate_expected_labels:
            self.historical_expected_label_validation = validation
        return self.historical_context


    def _valid_historical_label_vocabularies(self) -> dict:
        """
        Build strict historical label vocabularies from loaded Module 1 config.
        """
        if self.component_config is None or self.exposure_stance_config is None:
            raise ValueError("Run load_module1_config() before validating historical labels.")

        labels = {}
        strengths = {}

        try:
            components = self.component_config["components"]
            exposure_stances = self.exposure_stance_config["exposure_stances"]
        except KeyError as exc:
            raise ValueError(
                "Loaded module1_config is missing expected validated sections."
            ) from exc

        for component_name, component in components.items():
            label_values = component["label"]["labels"].values()
            labels[("component", component_name)] = {
                self._normalize_review_label(value)
                for value in label_values
                if not pd.isna(value)
            }

        for stance_name, stance in exposure_stances.items():
            direction_values = stance["labels"]["direction"].values()
            strength_values = stance["labels"]["strength"].values()
            labels[("stance", stance_name)] = {
                self._normalize_review_label(value)
                for value in direction_values
                if not pd.isna(value)
            }
            strengths[("stance", stance_name)] = {
                self._normalize_review_label(value)
                for value in strength_values
                if not pd.isna(value)
            }

        return {
            "labels": labels,
            "strengths": strengths,
        }


    def _validate_historical_expected_labels_from_cases(
        self,
        cases: pd.DataFrame,
    ) -> dict:
        """
        Validate built historical cases against Module 1 label vocabularies.
        """
        vocabularies = self._valid_historical_label_vocabularies()
        valid_label_map = vocabularies["labels"]
        valid_strength_map = vocabularies["strengths"]

        rows = []
        for _, case in cases.iterrows():
            level = self._normalize_review_label(case["level"])
            canonical_target = case["canonical_target"]
            key = (level, canonical_target)
            expected_label = case["expected_label"]
            expected_label_normalized = self._normalize_review_label(expected_label)
            valid_labels = valid_label_map.get(key, set())

            if not valid_labels:
                label_status = "missing_valid_label_config"
            elif expected_label_normalized in valid_labels:
                label_status = "valid"
            else:
                label_status = "invalid"

            expected_strength = case.get("expected_strength", pd.NA)
            expected_strength_normalized = (
                pd.NA
                if pd.isna(expected_strength)
                else self._normalize_review_label(expected_strength)
            )
            valid_strengths = valid_strength_map.get(key, set())
            strength_col = case.get("strength_col", pd.NA)

            if pd.isna(expected_strength):
                strength_status = "not_applicable"
            elif level == "component" or pd.isna(strength_col):
                strength_status = "non_applicable_expected_strength"
            elif level == "stance":
                if not valid_strengths:
                    strength_status = "missing_valid_strength_config"
                elif expected_strength_normalized in valid_strengths:
                    strength_status = "valid"
                else:
                    strength_status = "invalid"
            else:
                strength_status = "invalid"

            rows.append(
                {
                    "context_id": case.get("context_id"),
                    "start": case.get("start"),
                    "end": case.get("end"),
                    "target": case.get("target"),
                    "canonical_target": canonical_target,
                    "level": level,
                    "expected_label": expected_label,
                    "expected_label_normalized": expected_label_normalized,
                    "valid_labels": sorted(valid_labels),
                    "label_status": label_status,
                    "expected_strength": expected_strength,
                    "expected_strength_normalized": expected_strength_normalized,
                    "valid_strengths": sorted(valid_strengths),
                    "strength_status": strength_status,
                    "relevance": case.get("relevance"),
                    "use_for_validation": case.get("use_for_validation"),
                    "label_col": case.get("label_col"),
                    "strength_col": strength_col,
                }
            )

        full_columns = [
            "context_id",
            "start",
            "end",
            "target",
            "canonical_target",
            "level",
            "expected_label",
            "expected_label_normalized",
            "valid_labels",
            "label_status",
            "expected_strength",
            "expected_strength_normalized",
            "valid_strengths",
            "strength_status",
            "relevance",
            "use_for_validation",
            "label_col",
            "strength_col",
        ]
        full_df = pd.DataFrame(rows, columns=full_columns)
        if full_df.empty:
            issues_df = pd.DataFrame(columns=full_columns)
        else:
            issue_mask = (
                full_df["label_status"].ne("valid")
                | full_df["strength_status"].isin(
                    [
                        "invalid",
                        "missing_valid_strength_config",
                        "non_applicable_expected_strength",
                    ]
                )
            )
            issues_df = full_df[issue_mask].copy()

        valid_rows = []
        for key in sorted(valid_label_map):
            level, canonical_target = key
            valid_rows.append(
                {
                    "level": level,
                    "canonical_target": canonical_target,
                    "valid_labels": sorted(valid_label_map.get(key, set())),
                    "valid_strengths": sorted(valid_strength_map.get(key, set())),
                }
            )
        valid_labels_df = pd.DataFrame(
            valid_rows,
            columns=["level", "canonical_target", "valid_labels", "valid_strengths"],
        )

        checked_cases = int(full_df.shape[0])
        invalid_label_cases = (
            0 if full_df.empty else int(full_df["label_status"].ne("valid").sum())
        )
        invalid_strength_cases = (
            0
            if full_df.empty
            else int(
                full_df["strength_status"]
                .isin(["invalid", "missing_valid_strength_config"])
                .sum()
            )
        )
        non_applicable_strength_cases = (
            0
            if full_df.empty
            else int(
                (full_df["strength_status"] == "non_applicable_expected_strength").sum()
            )
        )
        report_df = pd.DataFrame(
            [
                {
                    "checked_cases": checked_cases,
                    "valid_label_cases": checked_cases - invalid_label_cases,
                    "invalid_label_cases": invalid_label_cases,
                    "invalid_strength_cases": invalid_strength_cases,
                    "non_applicable_strength_cases": non_applicable_strength_cases,
                    "overall_status": "valid" if issues_df.empty else "invalid",
                }
            ]
        )

        return {
            "report": report_df,
            "issues": issues_df,
            "full": full_df,
            "valid_labels": valid_labels_df,
        }


    def validate_historical_expected_labels(
        self,
        target: str | None = None,
        context_id: str | None = None,
        level: str | None = None,
        only_use_for_validation: bool = False,
        include_low_relevance: bool = True,
        raise_on_error: bool = False,
    ) -> dict:
        """
        Validate loaded historical-context expectations against module1_config.yaml.

        Historical context must be loaded explicitly with load_historical_context().
        module1_config.yaml is the source of truth for valid historical labels.
        Invalid expected labels can make match_ratio misleading because a valid
        model output may never match an invalid fixture label. Level matters:
        component credit_spread_change uses credit_spread_widening, while
        stance credit uses credit_negative.
        """
        cases = self._select_historical_cases(
            target=target,
            level=level,
            context_id=context_id,
            only_use_for_validation=only_use_for_validation,
            include_low_relevance=include_low_relevance,
            error_context="historical expected-label validation cases",
            require_non_empty=False,
        )

        validation = self._validate_historical_expected_labels_from_cases(cases)
        self.historical_expected_label_validation = validation

        if raise_on_error and not validation["issues"].empty:
            report = validation["report"].iloc[0]
            raise ValueError(
                "Historical expected-label validation failed: "
                f"{int(report['invalid_label_cases'])} invalid expected_label "
                "case(s), "
                f"{int(report['invalid_strength_cases'])} invalid "
                "expected_strength case(s), "
                f"{int(report['non_applicable_strength_cases'])} "
                "non-applicable expected_strength case(s). Inspect "
                'self.historical_expected_label_validation["issues"].'
            )

        return validation


    def _normalize_review_label(self, value):
        if pd.isna(value):
            return pd.NA

        return str(value).strip().lower()


    def _historical_review_target_aliases(self, level: str | None = None) -> dict:
        aliases = {}
        normalized_level = (
            None if level is None else self._normalize_review_label(level)
        )

        if normalized_level in {None, "component"}:
            if self.component_config is None:
                raise ValueError("Run load_module1_config() before historical review.")

            for component_name, component_config in self.component_config[
                "components"
            ].items():
                score_col = component_config.get("score", {}).get("output")
                label_col = component_config.get("label", {}).get("output")
                canonical = ("component", component_name)

                for alias in [component_name, score_col, label_col]:
                    if alias is not None:
                        aliases[self._normalize_review_label(alias)] = canonical

        if normalized_level in {None, "stance"}:
            if self.exposure_stance_config is None:
                raise ValueError("Run load_module1_config() before historical review.")

            for stance_name, stance_config in self.exposure_stance_config[
                "exposure_stances"
            ].items():
                score_col = stance_config.get("score_output")
                label_col = stance_config.get("stance_output")
                canonical = ("stance", stance_name)

                for alias in [stance_name, score_col, label_col]:
                    if alias is not None:
                        aliases[self._normalize_review_label(alias)] = canonical

        if normalized_level not in {None, "component", "stance"}:
            raise ValueError(f"Unsupported historical review level: {level}")

        return aliases


    def _historical_review_target_groups(self) -> dict:
        if self.module1_config is None:
            raise ValueError("Run load_module1_config() before historical review.")

        target_groups = (
            self.module1_config
            .get("model_metadata", {})
            .get("target_groups", {})
        )
        return {
            group_name: {
                "component": list(group.get("component", [])),
                "stance": list(group.get("stance", [])),
            }
            for group_name, group in target_groups.items()
        }


    def _build_historical_cases(
        self,
        events: pd.DataFrame,
        expectations: pd.DataFrame,
    ) -> pd.DataFrame:
        if self.component_config is None or self.exposure_stance_config is None:
            raise ValueError("Run load_module1_config() before load_historical_context().")

        event_map = {
            event["context_id"]: event
            for _, event in events.iterrows()
        }
        rows = []

        for _, expectation in expectations.iterrows():
            context_id = expectation["context_id"]
            event = event_map.get(context_id)
            if event is None:
                raise ValueError(
                    "historical_context expectation references unknown "
                    f"context_id={context_id}."
                )

            target = expectation["target"]
            level = self._normalize_review_label(expectation["level"])

            try:
                target_info = self._resolve_target(target, level)
            except ValueError as exc:
                raise ValueError(
                    "Unable to resolve historical expectation target "
                    f"context_id={context_id} target={target} level={level}: {exc}"
                ) from exc

            rows.append(
                {
                    "context_id": context_id,
                    "start": event["start"],
                    "end": event["end"],
                    "target": target,
                    "canonical_target": target_info.canonical_target,
                    "level": target_info.level,
                    "expected_label": expectation["expected_label"],
                    "expected_strength": expectation.get("expected_strength", pd.NA),
                    "relevance": expectation.get("relevance", "medium"),
                    "validation_confidence": event.get(
                        "validation_confidence",
                        pd.NA,
                    ),
                    "use_for_validation": event.get("use_for_validation", True),
                    "notes": expectation.get("notes", pd.NA),
                    "score_col": target_info.score_col,
                    "label_col": target_info.label_col,
                    "strength_col": target_info.strength_col,
                }
            )

        historical_cases = pd.DataFrame(rows)
        if historical_cases.empty:
            return historical_cases

        historical_cases["use_for_validation"] = (
            historical_cases["use_for_validation"].fillna(True).astype(bool)
        )
        historical_cases["relevance"] = (
            historical_cases["relevance"]
            .fillna("medium")
            .apply(self._normalize_review_label)
        )

        return (
            historical_cases.sort_values(
                ["level", "canonical_target", "start", "context_id"]
            )
            .reset_index(drop=True)
        )


    def _filter_historical_cases_by_target(
        self,
        cases: pd.DataFrame,
        target: str,
        level: str | None = None,
    ) -> pd.DataFrame:
        normalized_target = self._normalize_review_label(target)
        normalized_level = (
            None if level is None else self._normalize_review_label(level)
        )
        if normalized_level not in {None, "component", "stance"}:
            raise ValueError(f"Unsupported historical review level: {level}")
        groups = self._historical_review_target_groups()

        if normalized_target in groups:
            resolution = self._resolve_target(
                target,
                level,
                allow_group=True,
            )
            requested = set(resolution.related_targets)

            row_keys = list(zip(cases["level"], cases["canonical_target"]))
            keep = pd.Series(
                [row_key in requested for row_key in row_keys],
                index=cases.index,
            )
            return cases[keep]

        aliases = self._historical_review_target_aliases(level)

        if normalized_target not in aliases:
            available = sorted(aliases)
            raise ValueError(
                f"Unable to resolve historical review target filter: {target}. "
                f"Available targets and aliases: {available}"
            )

        requested = aliases[normalized_target]
        keep = (
            (cases["level"] == requested[0])
            & (cases["canonical_target"] == requested[1])
        )

        return cases[keep]


    def _select_historical_cases(
        self,
        target: str | None = None,
        level: str | None = None,
        context_id: str | None = None,
        only_use_for_validation: bool | None = None,
        include_low_relevance: bool | None = None,
        *,
        error_context: str = "historical cases",
        require_non_empty: bool = True,
    ) -> pd.DataFrame:
        if self.historical_cases is None:
            raise ValueError("Run load_historical_context() before historical review.")

        cases = self.historical_cases.copy()
        filter_parts = []

        if only_use_for_validation is True:
            cases = cases[cases["use_for_validation"].fillna(True).astype(bool)]
            filter_parts.append("use_for_validation=True")

        if include_low_relevance is False:
            relevance = cases["relevance"].apply(self._normalize_review_label)
            cases = cases[relevance != "low"]
            filter_parts.append("relevance!=low")

        if context_id is not None:
            cases = cases[cases["context_id"] == context_id]
            filter_parts.append(f"context_id={context_id}")

        if target is not None:
            cases = self._filter_historical_cases_by_target(cases, target, level)
            filter_parts.append(f"target={target}")

        if level is not None:
            normalized_level = self._normalize_review_label(level)
            cases = cases[cases["level"] == normalized_level]
            filter_parts.append(f"level={normalized_level}")

        if require_non_empty and cases.empty:
            filters = ", ".join(filter_parts) if filter_parts else "none"
            raise ValueError(
                f"No {error_context} match the requested filters ({filters})."
            )

        return cases


    def _historical_case_to_target_context(
        self,
        case: pd.Series,
        *,
        dependency_level: str = "none",
        include_labels: bool = True,
        include_strength: bool = True,
    ) -> TargetContextResult:
        canonical_target = case.get("canonical_target")
        if canonical_target is None or pd.isna(canonical_target):
            raise ValueError(
                "Historical case target context requires a concrete canonical "
                f"target; got: {canonical_target}"
            )

        ctx = self.get_target_context(
            target=canonical_target,
            level=case["level"],
            dependency_level=dependency_level,
            include_labels=include_labels,
            include_strength=include_strength,
            start=case["start"],
            end=case["end"],
        )

        score_col = ctx.resolution["score_col"]
        label_col = ctx.resolution["label_col"]
        strength_col = ctx.resolution.get("strength_col")

        if score_col not in ctx.data.columns:
            raise ValueError(
                f"Historical case target context score column not found: {score_col}"
            )
        if include_labels and label_col not in ctx.data.columns:
            raise ValueError(
                f"Historical case target context label column not found: {label_col}"
            )
        if (
            include_strength
            and strength_col is not None
            and strength_col not in ctx.data.columns
        ):
            raise ValueError(
                "Historical case target context strength column not found: "
                f"{strength_col}"
            )

        return ctx


    def _review_flag_from_match_ratio(
        self,
        match_ratio,
        valid_obs: int,
        min_obs: int,
        plausible_threshold: float,
        mixed_threshold: float,
    ):
        if valid_obs < min_obs or pd.isna(match_ratio):
            return "insufficient_data"
        if match_ratio >= plausible_threshold:
            return "plausible"
        if match_ratio >= mixed_threshold:
            return "mixed"
        return "inconsistent"


    def _make_historical_case_key(
        self,
        case: pd.Series,
        expected_label_normalized,
        expected_strength_normalized,
    ) -> str:
        expected_label_key = (
            "none"
            if pd.isna(expected_label_normalized)
            else str(expected_label_normalized)
        )
        expected_strength_key = (
            "none"
            if pd.isna(expected_strength_normalized)
            else str(expected_strength_normalized)
        )
        return "|".join(
            [
                str(case["context_id"]),
                str(case["level"]),
                str(case["canonical_target"]),
                expected_label_key,
                expected_strength_key,
            ]
        )


    def _evaluate_historical_case(
        self,
        case: pd.Series,
        min_obs: int = 20,
        plausible_threshold: float = 0.70,
        mixed_threshold: float = 0.45,
    ) -> dict:
        """
        Evaluate one selected historical case using the shared target context path.
        """
        ctx = self._historical_case_to_target_context(
            case,
            dependency_level="none",
            include_labels=True,
            include_strength=True,
        )
        period = ctx.data.copy()
        score_col = ctx.resolution["score_col"]
        label_col = ctx.resolution["label_col"]
        strength_col = ctx.resolution.get("strength_col")
        if pd.isna(strength_col):
            strength_col = None

        expected_label = case["expected_label"]
        expected_strength = case.get("expected_strength", pd.NA)
        expected_label_normalized = self._normalize_review_label(expected_label)
        has_expected_strength = not pd.isna(expected_strength)
        expected_strength_normalized = (
            self._normalize_review_label(expected_strength)
            if has_expected_strength
            else pd.NA
        )
        case_key = self._make_historical_case_key(
            case,
            expected_label_normalized,
            expected_strength_normalized,
        )

        summary = {
            "case_key": case_key,
            "context_id": case["context_id"],
            "start": case["start"],
            "end": case["end"],
            "target": case["target"],
            "canonical_target": case["canonical_target"],
            "level": case["level"],
            "expected_label": expected_label,
            "actual_label": pd.NA,
            "actual_label_mode": pd.NA,
            "label_match": pd.NA,
            "match_ratio": pd.NA,
            "expected_strength": expected_strength,
            "actual_strength": pd.NA,
            "actual_strength_mode": pd.NA,
            "strength_match": pd.NA,
            "strength_match_ratio": pd.NA,
            "review_flag": "insufficient_data",
            "direction_review_flag": "insufficient_data",
            "strength_review_flag": pd.NA,
            "score_mean": pd.NA,
            "score_median": pd.NA,
            "score_min": pd.NA,
            "score_max": pd.NA,
            "abs_score_mean": pd.NA,
            "abs_score_median": pd.NA,
            "obs_count": int(period.shape[0]),
            "valid_obs": 0,
            "match_count": 0,
            "mismatch_count": 0,
            "missing_count": int(period.shape[0]),
            "strength_valid_obs": 0,
            "strength_match_count": 0,
            "strength_mismatch_count": 0,
            "score_col": score_col,
            "label_col": label_col,
            "strength_col": strength_col,
            "relevance": case.get("relevance", "medium"),
            "validation_confidence": case.get("validation_confidence", pd.NA),
            "use_for_validation": case.get("use_for_validation", pd.NA),
            "notes": case.get("notes", pd.NA),
            "component_strength_note": pd.NA,
        }

        detail_columns = [
            "date",
            "case_key",
            "context_id",
            "target",
            "canonical_target",
            "level",
            "expected_label",
            "actual_label",
            "label_match",
            "match_state",
            "expected_strength",
            "actual_strength",
            "strength_match",
            "score",
            "score_col",
            "label_col",
            "strength_col",
        ]
        if period.empty:
            return {
                "summary": summary,
                "detail": pd.DataFrame(columns=detail_columns),
            }

        detail = pd.DataFrame(index=period.index)
        detail["date"] = period.index
        detail["case_key"] = case_key
        detail["context_id"] = case["context_id"]
        detail["target"] = case["target"]
        detail["canonical_target"] = case["canonical_target"]
        detail["level"] = case["level"]
        detail["expected_label"] = expected_label
        detail["actual_label"] = period[label_col]

        def label_match_state(actual_label):
            if pd.isna(actual_label):
                return "missing"
            if self._normalize_review_label(actual_label) == expected_label_normalized:
                return "match"
            return "mismatch"

        detail["match_state"] = detail["actual_label"].apply(label_match_state)
        detail["label_match"] = detail["match_state"].map(
            {"match": True, "mismatch": False}
        )
        detail["expected_strength"] = expected_strength
        detail["actual_strength"] = (
            period[strength_col] if strength_col is not None else pd.NA
        )

        def strength_match_state(actual_strength):
            if not has_expected_strength or pd.isna(actual_strength):
                return pd.NA
            return (
                self._normalize_review_label(actual_strength)
                == expected_strength_normalized
            )

        detail["strength_match"] = detail["actual_strength"].apply(
            strength_match_state
        )
        detail["score"] = period[score_col]
        detail["score_col"] = score_col
        detail["label_col"] = label_col
        detail["strength_col"] = strength_col
        detail = detail[detail_columns]

        actual_labels = detail["actual_label"].dropna()
        valid_obs = int(actual_labels.shape[0])
        match_count = int((detail["match_state"] == "match").sum())
        mismatch_count = int((detail["match_state"] == "mismatch").sum())
        missing_count = int((detail["match_state"] == "missing").sum())
        match_ratio = pd.NA if valid_obs == 0 else float(match_count / valid_obs)
        score = detail["score"].dropna()

        if not actual_labels.empty:
            actual_label = actual_labels.mode().iloc[0]
            summary["actual_label"] = actual_label
            summary["actual_label_mode"] = actual_label
            summary["label_match"] = (
                self._normalize_review_label(actual_label)
                == expected_label_normalized
            )
        if not score.empty:
            summary["score_mean"] = float(score.mean())
            summary["score_median"] = float(score.median())
            summary["score_min"] = float(score.min())
            summary["score_max"] = float(score.max())
            summary["abs_score_mean"] = float(score.abs().mean())
            summary["abs_score_median"] = float(score.abs().median())

        direction_review_flag = self._review_flag_from_match_ratio(
            match_ratio,
            valid_obs,
            min_obs,
            plausible_threshold,
            mixed_threshold,
        )
        summary["valid_obs"] = valid_obs
        summary["match_count"] = match_count
        summary["mismatch_count"] = mismatch_count
        summary["missing_count"] = missing_count
        summary["match_ratio"] = match_ratio
        summary["direction_review_flag"] = direction_review_flag
        summary["review_flag"] = direction_review_flag

        if strength_col is None:
            if has_expected_strength:
                summary["component_strength_note"] = (
                    "expected_strength ignored because this target has no "
                    "strength column."
                )
        else:
            actual_strength = detail["actual_strength"].dropna()
            strength_valid_obs = int(actual_strength.shape[0])
            if not actual_strength.empty:
                actual_strength_mode = actual_strength.mode().iloc[0]
                summary["actual_strength"] = actual_strength_mode
                summary["actual_strength_mode"] = actual_strength_mode

            if has_expected_strength and strength_valid_obs > 0:
                strength_matches = detail["strength_match"].dropna()
                strength_match_count = int((strength_matches == True).sum())
                strength_mismatch_count = int((strength_matches == False).sum())
                strength_match_ratio = float(
                    strength_match_count / strength_valid_obs
                )
                strength_review_flag = self._review_flag_from_match_ratio(
                    strength_match_ratio,
                    strength_valid_obs,
                    min_obs,
                    plausible_threshold,
                    mixed_threshold,
                )
                summary["strength_valid_obs"] = strength_valid_obs
                summary["strength_match_count"] = strength_match_count
                summary["strength_mismatch_count"] = strength_mismatch_count
                summary["strength_match_ratio"] = strength_match_ratio
                summary["strength_review_flag"] = strength_review_flag
                summary["strength_match"] = (
                    self._normalize_review_label(summary["actual_strength"])
                    == expected_strength_normalized
                    if not pd.isna(summary["actual_strength"])
                    else pd.NA
                )

                if case["level"] == "stance":
                    if direction_review_flag == "insufficient_data":
                        summary["review_flag"] = "insufficient_data"
                    elif direction_review_flag == "inconsistent":
                        summary["review_flag"] = "inconsistent"
                    elif direction_review_flag == "plausible":
                        summary["review_flag"] = (
                            "plausible"
                            if strength_review_flag == "plausible"
                            else "mixed"
                        )
                    else:
                        summary["review_flag"] = "mixed"

        return {
            "summary": summary,
            "detail": detail,
        }


    def _build_historical_case_summary_table(
        self,
        target: str | None = None,
        context_id: str | None = None,
        level: str | None = None,
        only_use_for_validation: bool = True,
        include_low_relevance: bool = False,
        min_obs: int = 20,
        plausible_threshold: float = 0.70,
        mixed_threshold: float = 0.45,
    ) -> pd.DataFrame:
        cases = self._select_historical_cases(
            target=target,
            level=level,
            context_id=context_id,
            only_use_for_validation=only_use_for_validation,
            include_low_relevance=include_low_relevance,
            error_context="historical review cases",
            require_non_empty=True,
        )

        rows = []
        for _, case in cases.iterrows():
            rows.append(
                self._evaluate_historical_case(
                    case,
                    min_obs=min_obs,
                    plausible_threshold=plausible_threshold,
                    mixed_threshold=mixed_threshold,
                )["summary"]
            )

        summary = pd.DataFrame(rows)
        sort_cols = [
            col
            for col in ["level", "canonical_target", "start", "context_id"]
            if col in summary.columns
        ]
        if sort_cols:
            summary = summary.sort_values(sort_cols).reset_index(drop=True)
        return summary


    def _format_historical_case_summary_view(
        self,
        case_summary: pd.DataFrame,
        view: str = "full",
    ) -> pd.DataFrame:
        if not isinstance(case_summary, pd.DataFrame):
            raise ValueError("case_summary must be a DataFrame.")

        normalized_view = self._normalize_review_label(view)
        if normalized_view == "full":
            return case_summary.copy()
        if normalized_view != "compact":
            raise ValueError('view must be "full" or "compact".')

        compact_columns = [
            "context_id",
            "start",
            "end",
            "level",
            "target",
            "canonical_target",
            "expected_label",
            "actual_label",
            "match_ratio",
            "valid_obs",
            "review_flag",
            "expected_strength",
            "actual_strength",
            "strength_match_ratio",
        ]
        compact_columns = [
            col for col in compact_columns if col in case_summary.columns
        ]
        return case_summary[compact_columns].copy()


    def _build_historical_detail_table(
        self,
        target: str | None = None,
        context_id: str | None = None,
        level: str | None = None,
        only_use_for_validation: bool = True,
        include_low_relevance: bool = False,
        min_obs: int = 20,
        plausible_threshold: float = 0.70,
        mixed_threshold: float = 0.45,
    ) -> pd.DataFrame:
        cases = self._select_historical_cases(
            target=target,
            level=level,
            context_id=context_id,
            only_use_for_validation=only_use_for_validation,
            include_low_relevance=include_low_relevance,
            error_context="historical review detail cases",
            require_non_empty=True,
        )

        details = []
        for _, case in cases.iterrows():
            details.append(
                self._evaluate_historical_case(
                    case,
                    min_obs=min_obs,
                    plausible_threshold=plausible_threshold,
                    mixed_threshold=mixed_threshold,
                )["detail"]
            )

        if not details:
            return pd.DataFrame()
        detail = pd.concat(details, axis=0)
        if not detail.empty:
            detail = detail.sort_values(
                ["level", "canonical_target", "date", "context_id"]
            )
        return detail.reset_index(drop=True)


    def _build_historical_review_report(
        self,
        case_summary: pd.DataFrame,
    ) -> pd.DataFrame:
        if not isinstance(case_summary, pd.DataFrame):
            raise ValueError("case_summary must be a DataFrame.")
        if case_summary.empty:
            raise ValueError("case_summary must not be empty.")
        if "review_flag" not in case_summary.columns:
            raise ValueError('case_summary must contain a "review_flag" column.')

        flags = case_summary["review_flag"]
        total = int(case_summary.shape[0])
        plausible = int((flags == "plausible").sum())
        mixed = int((flags == "mixed").sum())
        inconsistent = int((flags == "inconsistent").sum())
        insufficient_data = int((flags == "insufficient_data").sum())

        if insufficient_data == total:
            overall_review_flag = "insufficient_data"
        elif inconsistent > 0:
            overall_review_flag = "needs_review"
        elif mixed > 0:
            overall_review_flag = "partly_validated"
        elif plausible == total and total > 0:
            overall_review_flag = "validated"
        else:
            overall_review_flag = "needs_review"

        return pd.DataFrame(
            [
                {
                    "metric": "overall_review_flag",
                    "value": overall_review_flag,
                    "review_flag": pd.NA,
                },
                {
                    "metric": "total",
                    "value": total,
                    "review_flag": pd.NA,
                },
                {
                    "metric": "plausible",
                    "value": plausible,
                    "review_flag": "plausible",
                },
                {
                    "metric": "mixed",
                    "value": mixed,
                    "review_flag": "mixed",
                },
                {
                    "metric": "inconsistent",
                    "value": inconsistent,
                    "review_flag": "inconsistent",
                },
                {
                    "metric": "insufficient_data",
                    "value": insufficient_data,
                    "review_flag": "insufficient_data",
                },
            ],
            columns=["metric", "value", "review_flag"],
        )


    def _build_historical_review_distributions(
        self,
        detail: pd.DataFrame,
    ) -> dict:
        if not isinstance(detail, pd.DataFrame):
            raise ValueError("detail must be a DataFrame.")

        distribution_columns = [
            "case_key",
            "context_id",
            "target",
            "canonical_target",
            "level",
            "value",
            "count",
            "ratio",
        ]
        if detail.empty:
            empty = pd.DataFrame(columns=distribution_columns)
            return {
                "label_distribution": empty.copy(),
                "strength_distribution": empty.copy(),
            }

        group_cols = [
            "case_key",
            "context_id",
            "target",
            "canonical_target",
            "level",
        ]

        def build_distribution(value_col):
            rows = []
            for keys, group in detail.groupby(group_cols, dropna=False, sort=False):
                values = group[value_col].dropna()
                total = int(values.shape[0])
                if total == 0:
                    continue
                counts = values.value_counts(normalize=False)
                base = dict(zip(group_cols, keys))
                for value, count in counts.items():
                    row = base.copy()
                    row["value"] = value
                    row["count"] = int(count)
                    row["ratio"] = float(count / total)
                    rows.append(row)
            return pd.DataFrame(rows, columns=distribution_columns)

        return {
            "label_distribution": build_distribution("actual_label"),
            "strength_distribution": build_distribution("actual_strength"),
        }


    def _build_historical_review_windows(
        self,
        detail: pd.DataFrame,
    ) -> pd.DataFrame:
        if not isinstance(detail, pd.DataFrame):
            raise ValueError("detail must be a DataFrame.")

        window_columns = [
            "case_key",
            "context_id",
            "target",
            "canonical_target",
            "level",
            "start",
            "end",
            "match_state",
            "obs_count",
            "ratio",
        ]
        if detail.empty:
            return pd.DataFrame(columns=window_columns)

        group_cols = [
            "case_key",
            "context_id",
            "target",
            "canonical_target",
            "level",
        ]
        windows = []
        for keys, group in detail.groupby(group_cols, dropna=False, sort=False):
            case_df = group.copy()
            case_df = case_df.set_index(pd.to_datetime(case_df["date"]))
            decomposition = self._decompose_match_windows(case_df)
            if decomposition.empty:
                continue
            for col, value in reversed(list(zip(group_cols, keys))):
                decomposition.insert(0, col, value)
            windows.append(decomposition[window_columns])

        if not windows:
            return pd.DataFrame(columns=window_columns)
        return pd.concat(windows, ignore_index=True)


    def _build_historical_diagnostic_summary(
        self,
        case_summary: pd.DataFrame,
        detail: pd.DataFrame,
        windows: pd.DataFrame,
    ) -> pd.DataFrame:
        if not isinstance(case_summary, pd.DataFrame):
            raise ValueError("case_summary must be a DataFrame.")
        if not isinstance(detail, pd.DataFrame):
            raise ValueError("detail must be a DataFrame.")
        if not isinstance(windows, pd.DataFrame):
            raise ValueError("windows must be a DataFrame.")

        diagnostic_columns = [
            "mismatch_ratio",
            "missing_ratio",
            "first_match_date",
            "first_mismatch_date",
            "first_missing_date",
            "longest_match_streak",
            "longest_mismatch_streak",
            "longest_missing_streak",
        ]
        if case_summary.empty:
            return case_summary.copy().assign(
                **{column: pd.Series(dtype="object") for column in diagnostic_columns}
            )

        diagnostic = case_summary.copy()
        case_keys = diagnostic["case_key"].drop_duplicates().reset_index(drop=True)

        default_stats = pd.DataFrame(
            {
                "case_key": case_keys,
                "mismatch_ratio": pd.NA,
                "missing_ratio": pd.NA,
                "first_match_date": pd.NaT,
                "first_mismatch_date": pd.NaT,
                "first_missing_date": pd.NaT,
                "longest_match_streak": 0,
                "longest_mismatch_streak": 0,
                "longest_missing_streak": 0,
            }
        )

        if not detail.empty:
            stats = []
            for case_key, group in detail.groupby(
                "case_key", dropna=False, sort=False
            ):
                total_obs = int(group.shape[0])
                states = group["match_state"]

                def first_date_for(state):
                    dates = group.loc[states == state, "date"]
                    if dates.empty:
                        return pd.NaT
                    return dates.min()

                match_count = int((states == "match").sum())
                mismatch_count = int((states == "mismatch").sum())
                missing_count = int((states == "missing").sum())
                valid_obs = match_count + mismatch_count

                stats.append(
                    {
                        "case_key": case_key,
                        "mismatch_ratio": (
                            pd.NA
                            if valid_obs == 0
                            else float(mismatch_count / valid_obs)
                        ),
                        "missing_ratio": missing_count / total_obs,
                        "first_match_date": first_date_for("match"),
                        "first_mismatch_date": first_date_for("mismatch"),
                        "first_missing_date": first_date_for("missing"),
                    }
                )

            detail_stats = pd.DataFrame(stats)
            default_stats = default_stats.drop(
                columns=[
                    "mismatch_ratio",
                    "missing_ratio",
                    "first_match_date",
                    "first_mismatch_date",
                    "first_missing_date",
                ]
            ).merge(detail_stats, on="case_key", how="left")

        if not windows.empty:
            streaks = (
                windows.pivot_table(
                    index="case_key",
                    columns="match_state",
                    values="obs_count",
                    aggfunc="max",
                    fill_value=0,
                )
                .rename(
                    columns={
                        "match": "longest_match_streak",
                        "mismatch": "longest_mismatch_streak",
                        "missing": "longest_missing_streak",
                    }
                )
                .reset_index()
            )
            streak_columns = [
                "longest_match_streak",
                "longest_mismatch_streak",
                "longest_missing_streak",
            ]
            for column in streak_columns:
                if column not in streaks.columns:
                    streaks[column] = 0
            default_stats = default_stats.drop(columns=streak_columns).merge(
                streaks[["case_key", *streak_columns]], on="case_key", how="left"
            )
            default_stats[streak_columns] = (
                default_stats[streak_columns].fillna(0).astype(int)
            )

        return diagnostic.merge(default_stats, on="case_key", how="left")


    def review_historical_cases(
        self,
        target: str | None = None,
        context_id: str | None = None,
        level: str | None = None,
        only_use_for_validation: bool = True,
        include_low_relevance: bool = False,
        min_obs: int = 20,
        plausible_threshold: float = 0.70,
        mixed_threshold: float = 0.45,
        output: str = "cases",
    ) -> pd.DataFrame:
        """
        Return one selected canonical historical review output.
        """
        normalized_output = self._normalize_review_label(output)
        supported_outputs = {
            "cases",
            "compact",
            "diagnostic",
            "detail",
            "report",
            "windows",
            "label_distribution",
            "strength_distribution",
        }
        if normalized_output not in supported_outputs:
            supported = ", ".join(sorted(supported_outputs))
            raise ValueError(
                f"Unsupported historical review output: {output}. "
                f"Use one of: {supported}."
            )

        if normalized_output in {"cases", "compact", "report", "diagnostic"}:
            summary = self._build_historical_case_summary_table(
                target=target,
                context_id=context_id,
                level=level,
                only_use_for_validation=only_use_for_validation,
                include_low_relevance=include_low_relevance,
                min_obs=min_obs,
                plausible_threshold=plausible_threshold,
                mixed_threshold=mixed_threshold,
            )
            if normalized_output == "cases":
                return summary
            if normalized_output == "compact":
                return self._format_historical_case_summary_view(
                    summary,
                    view="compact",
                )
            if normalized_output == "report":
                return self._build_historical_review_report(summary)

        detail = self._build_historical_detail_table(
            target=target,
            context_id=context_id,
            level=level,
            only_use_for_validation=only_use_for_validation,
            include_low_relevance=include_low_relevance,
            min_obs=min_obs,
            plausible_threshold=plausible_threshold,
            mixed_threshold=mixed_threshold,
        )
        if normalized_output == "detail":
            return detail
        if normalized_output == "windows":
            return self._build_historical_review_windows(detail)
        if normalized_output == "diagnostic":
            windows = self._build_historical_review_windows(detail)
            return self._build_historical_diagnostic_summary(
                summary,
                detail,
                windows,
            )

        distributions = self._build_historical_review_distributions(detail)
        if normalized_output == "label_distribution":
            return distributions["label_distribution"]
        return distributions["strength_distribution"]


    def run_module1_historical_review(
        self,
        historical_context_path,
        target: str | None = None,
        context_id: str | None = None,
        level: str | None = None,
        only_use_for_validation: bool = True,
        include_low_relevance: bool = False,
        min_obs: int = 20,
        plausible_threshold: float = 0.70,
        mixed_threshold: float = 0.45,
        output: str = "cases",
    ) -> pd.DataFrame:
        """
        Convenience wrapper for running Module 1 and one historical review output.
    
        This method runs the Module 1 pipeline, explicitly loads historical context
        from historical_context_path, and returns exactly one selected output from
        review_historical_cases(..., output=...).
    
        Supported output values are:
        - "cases"
        - "compact"
        - "detail"
        - "report"
        - "windows"
        - "label_distribution"
        - "strength_distribution"
        - "diagnostic"
    
        This method no longer returns the legacy review_historical_context() bundle.
        """
        self.run_module1_pipeline()
        self.load_historical_context(historical_context_path)
    
        return self.review_historical_cases(
            target=target,
            context_id=context_id,
            level=level,
            only_use_for_validation=only_use_for_validation,
            include_low_relevance=include_low_relevance,
            min_obs=min_obs,
            plausible_threshold=plausible_threshold,
            mixed_threshold=mixed_threshold,
            output=output,
        )


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

    def _smoothing_diagnostic_windows(self, windows: dict | None) -> dict:
        if windows is not None:
            return windows
        if self.historical_context is None:
            raise ValueError(
                "Run load_historical_context(...) before using default smoothing "
                "diagnostic windows, or pass explicit windows."
            )

        events = self.historical_context.get("events")
        if events is None or events.empty:
            raise ValueError(
                "historical_context events are required for default smoothing "
                "diagnostic windows."
            )

        resolved = {
            row["context_id"]: (row["start"], row["end"])
            for _, row in events.iterrows()
        }
        resolved["full_history"] = (None, None)
        return resolved

    def _not_applicable_smoothing_result(
        self,
        target: str,
        smoothing_layer: str,
        status: str,
        reason: str,
    ) -> dict:
        row = {
            "target": target,
            "smoothing_layer": smoothing_layer,
            "status": status,
            "reason": reason,
        }
        return {
            "summary": pd.DataFrame([row]),
            "window_summary": pd.DataFrame(columns=list(row.keys())),
        }

    def _normalize_smoothing_target(self, target: str) -> str | None:
        if target == "curve":
            return "curve_positioning"
        if target in {"credit", "curve_positioning", "duration"}:
            return target
        return None

    def _target_smoothing_layers(self, target: str) -> set[str]:
        if self.module1_config is None:
            raise ValueError("Run load_module1_config() before smoothing diagnostics.")

        target_group = "curve" if target == "curve_positioning" else target
        groups = self.module1_config.get("model_metadata", {}).get("target_groups", {})
        components = groups.get(target_group, {}).get("component", [])
        component_config = self.module1_config.get("components", {})

        layers = set()
        for component in components:
            score_config = component_config.get(component, {}).get("score", {})
            input_preparation = score_config.get("input_preparation") or {}
            if input_preparation.get("smoothing") is not None:
                layers.add("input_preparation")
            if score_config.get("smoothing") is not None:
                layers.add("score")
        return layers

    def _resolve_smoothing_layer(self, target: str, smoothing_layer: str) -> str:
        if smoothing_layer != "auto":
            return smoothing_layer
        if target in {"credit", "curve_positioning"}:
            return "input_preparation"
        if target == "duration":
            return "score"
        return smoothing_layer

    def _smoothing_context_columns(
        self,
        target: str,
        spec: RuleMappedDiagnosticSpec,
    ) -> tuple[SmoothingDiagnosticContextColumn, ...]:
        if target == "credit":
            component_by_score_output = self._component_by_score_output()
            components = self.component_config["components"]
            context_columns = []
            for score_col in spec.score_input_cols:
                component_name = component_by_score_output.get(score_col)
                if component_name is None:
                    continue
                score_config = components[component_name].get("score", {})
                features = self._score_input_features_for_diagnostic_component(
                    component_name,
                    score_config,
                )
                for feature in features:
                    feature_config = self.feature_config["features"].get(feature, {})
                    data_col = (
                        feature_config.get("input")
                        if feature_config.get("method") == "level"
                        else None
                    )
                    output_col = data_col if data_col is not None else feature
                    context_columns.append(
                        SmoothingDiagnosticContextColumn(
                            output_col=output_col,
                            feature_col=feature,
                            data_col=data_col,
                        )
                    )
            return tuple(
                column
                for idx, column in enumerate(context_columns)
                if column.output_col
                not in {prior.output_col for prior in context_columns[:idx]}
            )

        component_names = self._diagnostic_component_names_for_target(target)
        return tuple(
            SmoothingDiagnosticContextColumn(
                output_col=feature,
                feature_col=feature,
            )
            for feature in self._score_input_features_for_diagnostic_components(
                component_names or (),
            )
        )

    def _smoothing_diagnostic_target_profile(
        self,
        target: str,
    ) -> SmoothingDiagnosticTargetProfile:
        context = self._resolve_rule_mapped_diagnostic_config(target)
        spec = self._derive_rule_mapped_diagnostic_spec_from_context(context)
        component_score_pairs = tuple(
            SmoothingDiagnosticComponentScorePair(
                source_score_col=score_col,
                raw_col=f"raw_{score_col}",
                smoothed_col=f"smoothed_{score_col}",
                metric_prefix=score_col,
            )
            for score_col in spec.score_input_cols
        )
        return SmoothingDiagnosticTargetProfile(
            target=spec.target,
            display_target="curve" if spec.target == "curve_positioning" else spec.target,
            spec=spec,
            component_score_pairs=component_score_pairs,
            context_columns=self._smoothing_context_columns(spec.target, spec),
            raw_final_score_col=f"raw_{spec.final_score_col}",
            smoothed_final_score_col=f"smoothed_{spec.final_score_col}",
            raw_stance_label_col=f"raw_{spec.stance_label_col}",
            smoothed_stance_label_col=f"smoothed_{spec.stance_label_col}",
            raw_strength_label_col=f"raw_{spec.strength_label_col}",
            smoothed_strength_label_col=f"smoothed_{spec.strength_label_col}",
            score_diff_col=(
                "score_diff"
                if spec.target == "curve_positioning"
                else f"{spec.final_score_col}_diff"
            ),
            final_score_metric_prefix=spec.final_score_col,
            score_change_metric_prefix=(
                "curve" if spec.target == "curve_positioning" else spec.target
            ),
        )

    def _validate_input_smoothing_detail_prerequisites(self, target: str) -> None:
        if self.features is None:
            raise ValueError(
                f"Run calculate_features() before comparing {target} input smoothing."
            )
        if self.scores is None:
            raise ValueError(
                "Run calculate_component_scores() before comparing "
                f"{target} input smoothing."
            )
        if self.exposure_stance is None:
            raise ValueError(
                "Run calculate_exposure_stance() before comparing "
                f"{target} input smoothing."
            )
        if self.component_config is None or self.exposure_stance_config is None:
            raise ValueError(
                "Run load_module1_config() before comparing "
                f"{target} input smoothing."
            )

    def _add_smoothing_context_columns(
        self,
        detail: pd.DataFrame,
        profile: SmoothingDiagnosticTargetProfile,
    ) -> None:
        for column in profile.context_columns:
            if column.data_col is not None and self.data is not None:
                if column.data_col in self.data.columns:
                    detail[column.output_col] = (
                        self.data[column.data_col].reindex(detail.index).ffill()
                    )
                    continue
            if (
                column.feature_col is not None
                and column.feature_col in self.features.columns
            ):
                detail[column.output_col] = self.features[column.feature_col]

    def _rule_mapped_input_smoothing_effect_detail(
        self,
        target: str,
        profile: SmoothingDiagnosticTargetProfile | None = None,
    ) -> pd.DataFrame:
        profile = profile or self._smoothing_diagnostic_target_profile(target)
        self._validate_input_smoothing_detail_prerequisites(profile.display_target)

        required_stance_cols = [
            profile.spec.final_score_col,
            profile.spec.stance_label_col,
            profile.spec.strength_label_col,
        ]
        missing_stance_cols = [
            col
            for col in required_stance_cols
            if col is None or col not in self.exposure_stance.columns
        ]
        if missing_stance_cols:
            raise ValueError(
                f"{profile.target} exposure stance outputs are missing: "
                f"{missing_stance_cols}"
            )

        raw_scores = self._recalculate_component_scores_for_input_preparation_diagnostic(
            profile.target,
            apply_input_preparation=False,
            output_prefix="raw_",
        )
        detail = pd.DataFrame(index=self.features.index)
        self._add_smoothing_context_columns(detail, profile)
        detail = pd.concat(
            [
                detail,
                self._prepared_filtered_input_columns(profile.target).reindex(
                    detail.index
                ),
            ],
            axis=1,
        )
        detail = pd.concat([detail, raw_scores], axis=1)
        for pair in profile.component_score_pairs:
            detail[pair.smoothed_col] = self.scores[pair.source_score_col]

        raw_stance = (
            self._reconstruct_rule_mapped_stance_for_input_preparation_diagnostic(
                profile.target,
                raw_scores,
            )
        )
        detail[profile.raw_final_score_col] = raw_stance["score"]
        detail[profile.smoothed_final_score_col] = self.exposure_stance[
            profile.spec.final_score_col
        ]
        detail[profile.score_diff_col] = (
            detail[profile.smoothed_final_score_col]
            - detail[profile.raw_final_score_col]
        )
        detail[profile.raw_stance_label_col] = raw_stance["direction"]
        detail[profile.raw_strength_label_col] = raw_stance["strength"]
        detail[profile.smoothed_stance_label_col] = self.exposure_stance[
            profile.spec.stance_label_col
        ]
        detail[profile.smoothed_strength_label_col] = self.exposure_stance[
            profile.spec.strength_label_col
        ]
        return detail

    def _smoothing_effect_result(
        self,
        detail: pd.DataFrame,
        windows: dict,
        summary_row_builder,
        include_detail: bool,
    ) -> dict:
        summary = pd.DataFrame([summary_row_builder(detail)])
        window_rows = []
        for window_id, window in windows.items():
            start, end = window
            window_detail = self._inclusive_window_slice(detail, start, end)
            row = summary_row_builder(window_detail)
            window_rows.append(
                self._window_summary_row(window_id, start, end, row)
            )

        result = {
            "summary": summary,
            "window_summary": pd.DataFrame(window_rows),
        }
        if include_detail:
            result["detail"] = detail
        return result

    def compare_smoothing_effect(
        self,
        target: str,
        smoothing_layer: str = "auto",
        windows: dict | None = None,
        include_detail: bool = True,
    ) -> dict:
        """
        Compare the effect of smoothing for a Module 1 target.

        For input-preparation smoothing, rebuild the rule-mapped stance from raw
        inputs and compare it with the production smoothed-input result. The summary
        reports decomposed differences, including both-valid changes, one-sided
        missing observations, aligned changes, transition counts, and one-day spike
        counts.

        Score-level smoothing diagnostics are recognized but currently reported as
        not implemented.
        """
        allowed_layers = {"auto", "input_preparation", "score"}
        if smoothing_layer not in allowed_layers:
            allowed = ", ".join(
                f'"{allowed_layer}"' for allowed_layer in sorted(allowed_layers)
            )
            raise ValueError(
                f"Unsupported smoothing_layer {smoothing_layer!r}. "
                f"Allowed values are: {allowed}."
            )

        resolved_target = self._normalize_smoothing_target(target)
        if resolved_target is None:
            return self._not_applicable_smoothing_result(
                target,
                smoothing_layer,
                "not_applicable",
                f"No smoothing-effect diagnostic is defined for target {target!r}.",
            )

        effective_layer = self._resolve_smoothing_layer(
            resolved_target,
            smoothing_layer,
        )
        available_layers = self._target_smoothing_layers(resolved_target)
        if effective_layer not in available_layers:
            return self._not_applicable_smoothing_result(
                resolved_target,
                effective_layer,
                "not_applicable",
                (
                    f"Target {resolved_target!r} does not use "
                    f"{effective_layer!r} smoothing."
                ),
            )

        if effective_layer == "score":
            return self._not_applicable_smoothing_result(
                resolved_target,
                effective_layer,
                "not_implemented",
                "Score-level smoothing comparison is not implemented.",
            )

        resolved_windows = self._smoothing_diagnostic_windows(windows)
        if resolved_target in {"credit", "curve_positioning"}:
            profile = self._smoothing_diagnostic_target_profile(resolved_target)
            detail = self._rule_mapped_input_smoothing_effect_detail(
                resolved_target,
                profile,
            )
            return self._smoothing_effect_result(
                detail,
                resolved_windows,
                lambda summary_detail: (
                    self._rule_mapped_input_smoothing_summary_row(
                        summary_detail,
                        profile,
                    )
                ),
                include_detail,
            )

        return self._not_applicable_smoothing_result(
            resolved_target,
            effective_layer,
            "not_applicable",
            (
                f"No {effective_layer!r} smoothing-effect diagnostic is defined "
                f"for target {resolved_target!r}."
            ),
        )

    def _credit_stance_config(self) -> dict:
        if self.exposure_stance_config is None:
            raise ValueError("Run load_module1_config() before credit diagnostics.")
        stance_config = self.exposure_stance_config["exposure_stances"].get("credit")
        if stance_config is None:
            raise ValueError("Credit exposure stance config is missing.")
        return stance_config

    def _credit_stance_score_from_component_scores(
        self,
        change_score: pd.Series,
        state_score: pd.Series,
        stance_config: dict,
    ) -> pd.Series:
        component_thresholds = self._credit_spread_component_thresholds()
        rule_scores = self._credit_spread_rule_scores(stance_config)
        state_buckets = self._credit_stance_state_buckets(stance_config)
        rule_adjustments = self._credit_spread_rule_adjustments(stance_config)
        rule_states = self._stabilize_credit_rule_states(
            change_score,
            state_score,
            component_thresholds,
            stance_config,
        )
        score = pd.Series(index=change_score.index, dtype="float64")
        for idx in change_score.index[change_score.notna() & state_score.notna()]:
            row = self._credit_spread_rule_row_from_states(
                change_score.loc[idx],
                state_score.loc[idx],
                rule_states.loc[idx, "credit_spread_change_state"],
                rule_states.loc[idx, "credit_spread_state_category"],
                component_thresholds,
                rule_scores,
                state_buckets,
                rule_adjustments,
            )
            score.loc[idx] = row["adjusted_credit_stance_score"]
        return score

    def _credit_stance_labels_for_score(
        self,
        score: pd.Series,
        stance_config: dict,
    ) -> tuple[pd.Series, pd.Series]:
        return self._stance_labels_for_score(score, stance_config)

    def _ratio_or_na(self, numerator, denominator):
        return numerator / denominator if denominator else pd.NA

    def _smoothing_pair_comparison_metrics(
        self,
        raw: pd.Series,
        smoothed: pd.Series,
        *,
        tolerance: float = 1e-10,
    ) -> dict:
        both_valid = raw.notna() & smoothed.notna()
        one_sided_missing = raw.isna() ^ smoothed.isna()
        aligned = both_valid | one_sided_missing
        both_valid_count = int(both_valid.sum())
        one_sided_missing_count = int(one_sided_missing.sum())

        changed = self._series_mismatch_mask(
            raw,
            smoothed,
            tolerance=tolerance,
        )
        both_valid_changed_count = int((changed & both_valid).sum())
        aligned_changed_count = both_valid_changed_count + one_sided_missing_count
        aligned_count = int(aligned.sum())

        mean_abs_diff = pd.NA
        if both_valid.any():
            mean_abs_diff = (smoothed.loc[both_valid] - raw.loc[both_valid]).abs().mean()

        return {
            "both_valid_count": both_valid_count,
            "both_valid_changed_count": both_valid_changed_count,
            "both_valid_changed_ratio": self._ratio_or_na(
                both_valid_changed_count,
                both_valid_count,
            ),
            "one_sided_missing_count": one_sided_missing_count,
            "one_sided_missing_ratio": self._ratio_or_na(
                one_sided_missing_count,
                aligned_count,
            ),
            "aligned_count": aligned_count,
            "aligned_changed_count": aligned_changed_count,
            "aligned_changed_ratio": self._ratio_or_na(
                aligned_changed_count,
                aligned_count,
            ),
            "mean_abs_diff": mean_abs_diff,
        }

    def _smoothing_pair_comparison_metrics_for_columns(
        self,
        frame: pd.DataFrame,
        raw_col: str,
        smoothed_col: str,
        *,
        tolerance: float = 1e-10,
    ) -> dict:
        return self._smoothing_pair_comparison_metrics(
            frame[raw_col],
            frame[smoothed_col],
            tolerance=tolerance,
        )

    def _add_prefixed_smoothing_pair_metrics(
        self,
        row: dict,
        prefix: str,
        metrics: dict,
    ) -> None:
        for metric, value in metrics.items():
            row[f"{prefix}_{metric}"] = value

    def _rule_mapped_input_smoothing_summary_row(
        self,
        detail: pd.DataFrame,
        profile: SmoothingDiagnosticTargetProfile,
    ):
        tolerance = 1e-10
        final_metrics = self._smoothing_pair_comparison_metrics_for_columns(
            detail,
            profile.raw_final_score_col,
            profile.smoothed_final_score_col,
            tolerance=tolerance,
        )

        row = {
            "total_rows": int(len(detail)),
            "valid_rows": final_metrics["both_valid_count"],
        }
        for pair in profile.component_score_pairs:
            metrics = self._smoothing_pair_comparison_metrics_for_columns(
                detail,
                pair.raw_col,
                pair.smoothed_col,
                tolerance=tolerance,
            )
            self._add_prefixed_smoothing_pair_metrics(
                row,
                pair.metric_prefix,
                metrics,
            )
        self._add_prefixed_smoothing_pair_metrics(
            row,
            profile.final_score_metric_prefix,
            final_metrics,
        )

        change_prefix = profile.score_change_metric_prefix
        raw_score_change_count = self._count_series_changes(
            detail[profile.raw_final_score_col]
        )
        smoothed_score_change_count = self._count_series_changes(
            detail[profile.smoothed_final_score_col]
        )
        score_change_reduction_count = (
            raw_score_change_count - smoothed_score_change_count
        )
        raw_one_day_spike_count = self._count_one_day_spikes(
            detail[profile.raw_final_score_col]
        )
        smoothed_one_day_spike_count = self._count_one_day_spikes(
            detail[profile.smoothed_final_score_col]
        )
        one_day_spike_reduction_count = (
            raw_one_day_spike_count - smoothed_one_day_spike_count
        )
        row.update(
            {
                f"raw_{change_prefix}_score_change_count": raw_score_change_count,
                f"smoothed_{change_prefix}_score_change_count": (
                    smoothed_score_change_count
                ),
                f"{change_prefix}_score_change_reduction_count": (
                    score_change_reduction_count
                ),
                f"{change_prefix}_score_change_reduction_ratio": self._ratio_or_na(
                    score_change_reduction_count,
                    raw_score_change_count,
                ),
                f"raw_{change_prefix}_one_day_spike_count": raw_one_day_spike_count,
                f"smoothed_{change_prefix}_one_day_spike_count": (
                    smoothed_one_day_spike_count
                ),
                f"{change_prefix}_one_day_spike_reduction_count": (
                    one_day_spike_reduction_count
                ),
                f"{change_prefix}_one_day_spike_reduction_ratio": self._ratio_or_na(
                    one_day_spike_reduction_count,
                    raw_one_day_spike_count,
                ),
            }
        )
        return row

    def _inclusive_window_slice(
        self,
        frame: pd.DataFrame,
        start=None,
        end=None,
    ) -> pd.DataFrame:
        window = frame
        if start is not None:
            window = window.loc[window.index >= pd.to_datetime(start)]
        if end is not None:
            window = window.loc[window.index <= pd.to_datetime(end)]
        return window

    def _window_summary_row(
        self,
        window_id: str,
        start,
        end,
        summary_row: dict,
    ) -> dict:
        row = summary_row.copy()
        row.update({"window_id": window_id, "start": start, "end": end})
        return row

    def _series_mismatch_mask(
        self,
        left: pd.Series,
        right: pd.Series,
        *,
        tolerance: float | None = None,
    ) -> pd.Series:
        both_missing = left.isna() & right.isna()
        comparable = left.notna() & right.notna()
        equal = pd.Series(False, index=left.index)
        if tolerance is None:
            equal.loc[comparable] = (
                left.loc[comparable].astype("object").to_numpy()
                == right.loc[comparable].astype("object").to_numpy()
            )
        else:
            equal.loc[comparable] = (
                (left.loc[comparable] - right.loc[comparable]).abs()
                <= tolerance
            )
        return ~(equal | both_missing)

    def _curve_dominant_value(self, sr: pd.Series):
        values = sr.dropna()
        if values.empty:
            return pd.NA
        return values.mode().iloc[0]

    def _count_series_changes(self, series: pd.Series) -> int:
        valid = series.dropna()
        if valid.empty:
            return 0
        return int(valid.ne(valid.shift(1)).iloc[1:].sum())

    def _count_one_day_spikes(self, series: pd.Series) -> int:
        values = series.reset_index(drop=True)
        count = 0
        for idx in range(1, len(values) - 1):
            previous_value = values.iloc[idx - 1]
            current_value = values.iloc[idx]
            next_value = values.iloc[idx + 1]
            if (
                pd.isna(previous_value)
                or pd.isna(current_value)
                or pd.isna(next_value)
            ):
                continue
            if current_value != previous_value and current_value != next_value and previous_value == next_value:
                count += 1
        return count

    def _default_curve_stabilization_cases(self) -> dict:
        neutral_case = self._neutral_curve_positioning_stabilization_overrides()
        return {
            "neutral_base": neutral_case,
            "persistence_3": {
                "curve_change": {"hysteresis_buffer": 0.0, "min_state_persistence": 3},
                "curve_state": {"hysteresis_buffer": 0.0, "min_state_persistence": 3},
                "curve_move_driver": {"hysteresis_buffer": 0.0, "min_state_persistence": 2},
            },
            "hysteresis_005": {
                "curve_change": {"hysteresis_buffer": 0.05, "min_state_persistence": 1},
                "curve_state": {"hysteresis_buffer": 0.05, "min_state_persistence": 1},
                "curve_move_driver": {"hysteresis_buffer": 0.0, "min_state_persistence": 1},
            },
            "hysteresis_005_persistence_3": {
                "curve_change": {"hysteresis_buffer": 0.05, "min_state_persistence": 3},
                "curve_state": {"hysteresis_buffer": 0.05, "min_state_persistence": 3},
                "curve_move_driver": {"hysteresis_buffer": 0.0, "min_state_persistence": 2},
            },
            "hysteresis_010_persistence_3": {
                "curve_change": {"hysteresis_buffer": 0.10, "min_state_persistence": 3},
                "curve_state": {"hysteresis_buffer": 0.10, "min_state_persistence": 3},
                "curve_move_driver": {"hysteresis_buffer": 0.0, "min_state_persistence": 2},
            },
        }

    def _neutral_curve_positioning_stabilization_overrides(self) -> dict:
        return {
            "curve_change": {"hysteresis_buffer": 0.0, "min_state_persistence": 1},
            "curve_state": {"hysteresis_buffer": 0.0, "min_state_persistence": 1},
            "curve_move_driver": {
                "hysteresis_buffer": 0.0,
                "min_state_persistence": 1,
            },
        }

    def _default_curve_stabilization_windows(self) -> dict:
        return {
            "taper_tantrum_review": ("2012-08-01", "2014-06-01"),
            "fed_hiking_2022": ("2022-03-01", "2022-12-31"),
            "covid_shock_2020": ("2020-02-01", "2020-06-30"),
            "full_history": (None, None),
        }

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

    def compare_curve_move_driver_threshold_effect(
        self,
        include_detail: bool = True,
    ) -> dict:
        """
        Compare curve_move_driver classification with and without the local
        min_abs_value filter, holding the smoothed inputs fixed.
        """
        if self.features is None:
            raise ValueError(
                "Run calculate_features() before comparing curve_move_driver threshold."
            )
        if self.scores is None:
            raise ValueError(
                "Run calculate_component_scores() before comparing curve_move_driver threshold."
            )
        if self.exposure_stance is None:
            raise ValueError(
                "Run calculate_exposure_stance() before comparing curve_move_driver threshold."
            )
        if self.component_config is None or self.exposure_stance_config is None:
            raise ValueError(
                "Run load_module1_config() before comparing curve_move_driver threshold."
            )

        target = "curve_positioning"
        curve_move_driver_config = self.component_config["components"][
            "curve_move_driver"
        ]["score"]
        input_preparation = curve_move_driver_config.get("input_preparation") or {}
        min_abs_value = input_preparation.get("min_abs_value")

        prepared_inputs = self._prepared_filtered_input_columns(target)
        front_end_prepared_spec = self._diagnostic_input_spec_by_role(
            target,
            "curve_move_driver",
            "prepared",
            "front_end",
        )
        long_end_prepared_spec = self._diagnostic_input_spec_by_role(
            target,
            "curve_move_driver",
            "prepared",
            "long_end",
        )
        front_end_prepared = prepared_inputs[front_end_prepared_spec.output]
        long_end_prepared = prepared_inputs[long_end_prepared_spec.output]
        if min_abs_value is None:
            front_end_filtered_spec = None
            long_end_filtered_spec = None
            front_end_filtered = front_end_prepared.copy()
            long_end_filtered = long_end_prepared.copy()
        else:
            front_end_filtered_spec = self._diagnostic_input_spec_by_role(
                target,
                "curve_move_driver",
                "filtered",
                "front_end",
            )
            long_end_filtered_spec = self._diagnostic_input_spec_by_role(
                target,
                "curve_move_driver",
                "filtered",
                "long_end",
            )
            front_end_filtered = prepared_inputs[front_end_filtered_spec.output]
            long_end_filtered = prepared_inputs[long_end_filtered_spec.output]

        curve_move_driver_bucket_scores = self._curve_move_driver_bucket_scores(
            self._component_score_bucket_config("curve_move_driver")
        )
        score_without_threshold = self._clip_score(
            self._curve_move_driver_score_from_prepared_inputs(
                front_end_prepared,
                long_end_prepared,
                curve_move_driver_bucket_scores,
            ),
            curve_move_driver_config.get("clip"),
        )
        score_with_threshold = self._clip_score(
            self._curve_move_driver_score_from_prepared_inputs(
                front_end_filtered,
                long_end_filtered,
                curve_move_driver_bucket_scores,
            ),
            curve_move_driver_config.get("clip"),
        )

        parameter_effect = self._rule_mapped_component_parameter_effect_detail(
            target,
            "curve_move_driver_score",
            score_without_threshold,
            score_with_threshold,
            baseline_component_output="curve_move_driver_score_without_threshold",
            alternate_component_output="curve_move_driver_score_with_threshold",
            baseline_stance_output="curve_positioning_score_without_threshold",
            alternate_stance_output="curve_positioning_score_with_threshold",
            stance_diff_output="curve_positioning_score_diff_due_to_threshold",
            component_changed_output="curve_move_driver_score_changed_by_threshold",
            stance_changed_output="curve_positioning_score_changed_by_threshold",
        )

        detail = pd.DataFrame(index=self.features.index)
        for column in [front_end_prepared_spec.source, long_end_prepared_spec.source]:
            if column in self.features.columns:
                detail[column] = self.features[column]
        detail[front_end_prepared_spec.output] = front_end_prepared
        detail[long_end_prepared_spec.output] = long_end_prepared
        if front_end_filtered_spec is None:
            detail[
                self._diagnostic_input_column_name(
                    front_end_prepared_spec.source,
                    "filtered",
                    "curve_move_driver",
                )
            ] = front_end_filtered
        else:
            detail[front_end_filtered_spec.output] = front_end_filtered
        if long_end_filtered_spec is None:
            detail[
                self._diagnostic_input_column_name(
                    long_end_prepared_spec.source,
                    "filtered",
                    "curve_move_driver",
                )
            ] = long_end_filtered
        else:
            detail[long_end_filtered_spec.output] = long_end_filtered
        detail["curve_move_driver_score_without_threshold"] = parameter_effect[
            "curve_move_driver_score_without_threshold"
        ]
        detail["curve_move_driver_score_with_threshold"] = parameter_effect[
            "curve_move_driver_score_with_threshold"
        ]
        detail["curve_move_driver_bucket_without_threshold"] = (
            score_without_threshold.apply(
                lambda value: self._score_bucket(
                    value,
                    self._component_score_bucket_config("curve_move_driver"),
                )
            )
        )
        detail["curve_move_driver_bucket_with_threshold"] = (
            score_with_threshold.apply(
                lambda value: self._score_bucket(
                    value,
                    self._component_score_bucket_config("curve_move_driver"),
                )
            )
        )
        for column in [
            "curve_positioning_score_without_threshold",
            "curve_positioning_score_with_threshold",
            "curve_positioning_score_diff_due_to_threshold",
            "curve_move_driver_score_changed_by_threshold",
            "curve_positioning_score_changed_by_threshold",
        ]:
            detail[column] = parameter_effect[column]

        valid = detail[
            detail["curve_move_driver_score_without_threshold"].notna()
            & detail["curve_move_driver_score_with_threshold"].notna()
        ]
        valid_count = int(len(valid))
        valid_positioning = detail[
            detail["curve_positioning_score_without_threshold"].notna()
            & detail["curve_positioning_score_with_threshold"].notna()
        ]
        valid_positioning_count = int(len(valid_positioning))
        if min_abs_value is None:
            front_below = pd.Series(False, index=detail.index)
            long_below = pd.Series(False, index=detail.index)
        else:
            front_below = (
                front_end_prepared.notna()
                & (front_end_prepared.abs() < min_abs_value)
            )
            long_below = (
                long_end_prepared.notna()
                & (long_end_prepared.abs() < min_abs_value)
            )
        move_changed_count = int(
            detail["curve_move_driver_score_changed_by_threshold"].sum()
        )
        positioning_changed_count = int(
            detail["curve_positioning_score_changed_by_threshold"].sum()
        )
        mixed_before = int((score_without_threshold == 0.0).sum())
        mixed_after = int((score_with_threshold == 0.0).sum())
        summary = pd.DataFrame(
            [
                {
                    "min_abs_value": min_abs_value,
                    "total_rows": int(len(detail)),
                    "valid_rows": valid_count,
                    "rows_with_front_end_below_threshold": int(front_below.sum()),
                    "rows_with_long_end_below_threshold": int(long_below.sum()),
                    "rows_with_either_side_below_threshold": int(
                        (front_below | long_below).sum()
                    ),
                    "rows_with_both_sides_below_threshold": int(
                        (front_below & long_below).sum()
                    ),
                    "curve_move_driver_score_changed_count_vs_no_threshold": (
                        move_changed_count
                    ),
                    "curve_move_driver_score_changed_ratio_vs_no_threshold": (
                        self._ratio_or_na(move_changed_count, valid_count)
                    ),
                    "mixed_or_unclear_count_before_threshold": mixed_before,
                    "mixed_or_unclear_count_after_threshold": mixed_after,
                    "mixed_or_unclear_count_change": mixed_after - mixed_before,
                    "curve_positioning_score_changed_count_due_to_threshold": (
                        positioning_changed_count
                    ),
                    "curve_positioning_score_changed_ratio_due_to_threshold": (
                        self._ratio_or_na(
                            positioning_changed_count,
                            valid_positioning_count,
                        )
                    ),
                }
            ]
        )

        result = {"summary": summary}
        if include_detail:
            result["detail"] = detail
        return result

    def _rule_mapped_stabilization_case_detail_comparison(
        self,
        stance_name: str,
        stance_config: dict,
        *,
        baseline_stabilization_overrides: dict,
        case_stabilization_overrides: dict,
        detail_columns: dict,
    ) -> pd.DataFrame:
        spec = self._resolve_rule_mapped_stance_schema(stance_name, stance_config)
        baseline_diag = self._build_rule_mapped_stance_score_breakdown(
            stance_name,
            stance_config,
            stabilization_overrides=baseline_stabilization_overrides,
        )
        case_diag = self._build_rule_mapped_stance_score_breakdown(
            stance_name,
            stance_config,
            stabilization_overrides=case_stabilization_overrides,
        )
        detail = pd.DataFrame(index=self.scores.index)

        for state_input in spec.state_inputs:
            output_col = detail_columns["score_inputs"].get(
                state_input.name,
                state_input.source_score_col,
            )
            detail[output_col] = self.scores[state_input.source_score_col]

        for state_input in spec.state_inputs:
            state_columns = detail_columns["states"][state_input.name]
            detail[state_columns["raw"]] = baseline_diag[
                state_input.stabilized_output_col
            ]
            detail[state_columns["stabilized"]] = case_diag[
                state_input.stabilized_output_col
            ]

        rule_case_columns = detail_columns["rule_case"]
        detail[rule_case_columns["raw"]] = baseline_diag[spec.rule_case_output_col]
        detail[rule_case_columns["stabilized"]] = case_diag[spec.rule_case_output_col]

        score_columns = detail_columns["score"]
        detail[score_columns["raw"]] = baseline_diag[spec.score_output_col]
        detail[score_columns["stabilized"]] = case_diag[spec.score_output_col]
        detail[detail_columns["score_diff"]] = (
            detail[score_columns["stabilized"]]
            - detail[score_columns["raw"]]
        )

        raw_direction, raw_strength = self._stance_labels_for_score(
            detail[score_columns["raw"]], stance_config
        )
        stabilized_direction, stabilized_strength = self._stance_labels_for_score(
            detail[score_columns["stabilized"]], stance_config
        )
        direction_columns = detail_columns["direction"]
        strength_columns = detail_columns["strength"]
        detail[direction_columns["raw"]] = raw_direction
        detail[direction_columns["stabilized"]] = stabilized_direction
        detail[strength_columns["raw"]] = raw_strength
        detail[strength_columns["stabilized"]] = stabilized_strength

        change_columns = detail_columns["changed"]
        detail[change_columns["score"]] = self._series_mismatch_mask(
            detail[score_columns["raw"]],
            detail[score_columns["stabilized"]],
            tolerance=1e-10,
        )
        detail[change_columns["direction"]] = self._series_mismatch_mask(
            detail[direction_columns["raw"]],
            detail[direction_columns["stabilized"]],
        )
        detail[change_columns["strength"]] = self._series_mismatch_mask(
            detail[strength_columns["raw"]],
            detail[strength_columns["stabilized"]],
        )

        score_change_flag_columns = detail_columns["score_change_flags"]
        detail[score_change_flag_columns["raw"]] = (
            detail[score_columns["raw"]]
            .dropna()
            .ne(detail[score_columns["raw"]].dropna().shift(1))
            .reindex(detail.index, fill_value=False)
        )
        detail[score_change_flag_columns["stabilized"]] = (
            detail[score_columns["stabilized"]]
            .dropna()
            .ne(detail[score_columns["stabilized"]].dropna().shift(1))
            .reindex(detail.index, fill_value=False)
        )
        if detail[score_change_flag_columns["raw"]].notna().any():
            first_raw = detail[score_columns["raw"]].first_valid_index()
            if first_raw is not None:
                detail.loc[first_raw, score_change_flag_columns["raw"]] = False
        if detail[score_change_flag_columns["stabilized"]].notna().any():
            first_stabilized = detail[score_columns["stabilized"]].first_valid_index()
            if first_stabilized is not None:
                detail.loc[
                    first_stabilized,
                    score_change_flag_columns["stabilized"],
                ] = False

        one_day_spike_flag_columns = detail_columns["one_day_spike_flags"]
        detail[one_day_spike_flag_columns["raw"]] = False
        detail[one_day_spike_flag_columns["stabilized"]] = False
        for score_col, flag_col in [
            (score_columns["raw"], one_day_spike_flag_columns["raw"]),
            (score_columns["stabilized"], one_day_spike_flag_columns["stabilized"]),
        ]:
            values = detail[score_col]
            for pos in range(1, len(values) - 1):
                previous_value = values.iloc[pos - 1]
                current_value = values.iloc[pos]
                next_value = values.iloc[pos + 1]
                if (
                    pd.isna(previous_value)
                    or pd.isna(current_value)
                    or pd.isna(next_value)
                ):
                    continue
                if current_value != previous_value and current_value != next_value and previous_value == next_value:
                    detail.iloc[pos, detail.columns.get_loc(flag_col)] = True
        return detail

    def _curve_stabilization_case_detail(
        self,
        case_config: dict,
        stance_config: dict,
    ) -> pd.DataFrame:
        return self._rule_mapped_stabilization_case_detail_comparison(
            "curve_positioning",
            stance_config,
            baseline_stabilization_overrides=self._neutral_curve_positioning_stabilization_overrides(),
            case_stabilization_overrides=case_config,
            detail_columns={
                "score_inputs": {
                    "curve_change": "curve_change_score",
                    "curve_state": "curve_state_score",
                    "curve_move_driver": "curve_move_driver_score",
                },
                "states": {
                    "curve_change": {
                        "raw": "raw_curve_change_bucket",
                        "stabilized": "stabilized_curve_change_bucket",
                    },
                    "curve_state": {
                        "raw": "raw_curve_state_bucket",
                        "stabilized": "stabilized_curve_state_bucket",
                    },
                    "curve_move_driver": {
                        "raw": "raw_yield_move_driver_bucket",
                        "stabilized": "stabilized_yield_move_driver_bucket",
                    },
                },
                "rule_case": {
                    "raw": "raw_curve_positioning_rule_case",
                    "stabilized": "stabilized_curve_positioning_rule_case",
                },
                "score": {
                    "raw": "raw_curve_positioning_score",
                    "stabilized": "stabilized_curve_positioning_score",
                },
                "score_diff": "score_diff",
                "direction": {
                    "raw": "raw_curve_positioning",
                    "stabilized": "stabilized_curve_positioning",
                },
                "strength": {
                    "raw": "raw_curve_positioning_strength",
                    "stabilized": "stabilized_curve_positioning_strength",
                },
                "changed": {
                    "score": "score_changed",
                    "direction": "direction_changed",
                    "strength": "strength_changed",
                },
                "score_change_flags": {
                    "raw": "raw_score_change_flag",
                    "stabilized": "stabilized_score_change_flag",
                },
                "one_day_spike_flags": {
                    "raw": "raw_one_day_spike_flag",
                    "stabilized": "stabilized_one_day_spike_flag",
                },
            },
        )

    def _curve_stabilization_summary_row(
        self,
        case_id: str,
        detail: pd.DataFrame,
    ) -> dict:
        valid = detail[
            detail["raw_curve_positioning_score"].notna()
            & detail["stabilized_curve_positioning_score"].notna()
        ]
        valid_count = int(len(valid))
        raw_score_change_count = self._count_series_changes(
            detail["raw_curve_positioning_score"]
        )
        stabilized_score_change_count = self._count_series_changes(
            detail["stabilized_curve_positioning_score"]
        )
        raw_spikes = self._count_one_day_spikes(detail["raw_curve_positioning_score"])
        stabilized_spikes = self._count_one_day_spikes(
            detail["stabilized_curve_positioning_score"]
        )
        bucket_change_count_raw = sum(
            self._count_series_changes(detail[col])
            for col in [
                "raw_curve_change_bucket",
                "raw_curve_state_bucket",
                "raw_yield_move_driver_bucket",
            ]
        )
        bucket_change_count_stabilized = sum(
            self._count_series_changes(detail[col])
            for col in [
                "stabilized_curve_change_bucket",
                "stabilized_curve_state_bucket",
                "stabilized_yield_move_driver_bucket",
            ]
        )
        return {
            "case_id": case_id,
            "total_rows": int(len(detail)),
            "valid_rows": valid_count,
            "mean_raw_score": valid["raw_curve_positioning_score"].mean(),
            "mean_stabilized_score": valid[
                "stabilized_curve_positioning_score"
            ].mean(),
            "mean_score_diff": valid["score_diff"].mean(),
            "mean_abs_score_diff": valid["score_diff"].abs().mean(),
            "max_abs_score_diff": valid["score_diff"].abs().max() if valid_count else pd.NA,
            "changed_score_count": int(valid["score_changed"].sum()),
            "changed_score_ratio": self._ratio_or_na(
                int(valid["score_changed"].sum()),
                valid_count,
            ),
            "changed_direction_count": int(valid["direction_changed"].sum()),
            "changed_direction_ratio": self._ratio_or_na(
                int(valid["direction_changed"].sum()),
                valid_count,
            ),
            "changed_strength_count": int(valid["strength_changed"].sum()),
            "changed_strength_ratio": self._ratio_or_na(
                int(valid["strength_changed"].sum()),
                valid_count,
            ),
            "raw_score_change_count": raw_score_change_count,
            "stabilized_score_change_count": stabilized_score_change_count,
            "score_change_reduction_count": raw_score_change_count - stabilized_score_change_count,
            "score_change_reduction_ratio": self._ratio_or_na(
                raw_score_change_count - stabilized_score_change_count,
                raw_score_change_count,
            ),
            "one_day_spike_count_raw": raw_spikes,
            "one_day_spike_count_stabilized": stabilized_spikes,
            "one_day_spike_reduction_count": raw_spikes - stabilized_spikes,
            "one_day_spike_reduction_ratio": self._ratio_or_na(
                raw_spikes - stabilized_spikes,
                raw_spikes,
            ),
            "bucket_change_count_raw": bucket_change_count_raw,
            "bucket_change_count_stabilized": bucket_change_count_stabilized,
            "dominant_raw_direction": self._curve_dominant_value(detail["raw_curve_positioning"]),
            "dominant_stabilized_direction": self._curve_dominant_value(detail["stabilized_curve_positioning"]),
            "dominant_raw_strength": self._curve_dominant_value(detail["raw_curve_positioning_strength"]),
            "dominant_stabilized_strength": self._curve_dominant_value(detail["stabilized_curve_positioning_strength"]),
        }

    def _curve_stabilization_window_row(
        self,
        case_id: str,
        window_id: str,
        window: tuple,
        detail: pd.DataFrame,
    ) -> dict:
        start, end = window
        window_detail = self._inclusive_window_slice(detail, start, end)
        valid = window_detail[
            window_detail["raw_curve_positioning_score"].notna()
            & window_detail["stabilized_curve_positioning_score"].notna()
        ]
        obs_count = int(len(valid))
        return {
            "case_id": case_id,
            "window_id": window_id,
            "start": start,
            "end": end,
            "obs_count": obs_count,
            "mean_raw_score": valid["raw_curve_positioning_score"].mean(),
            "mean_stabilized_score": valid["stabilized_curve_positioning_score"].mean(),
            "mean_score_diff": valid["score_diff"].mean(),
            "mean_abs_score_diff": valid["score_diff"].abs().mean(),
            "changed_score_count": int(valid["score_changed"].sum()),
            "changed_score_ratio": self._ratio_or_na(
                int(valid["score_changed"].sum()),
                obs_count,
            ),
            "raw_score_change_count": self._count_series_changes(window_detail["raw_curve_positioning_score"]),
            "stabilized_score_change_count": self._count_series_changes(window_detail["stabilized_curve_positioning_score"]),
            "one_day_spike_count_raw": self._count_one_day_spikes(window_detail["raw_curve_positioning_score"]),
            "one_day_spike_count_stabilized": self._count_one_day_spikes(window_detail["stabilized_curve_positioning_score"]),
            "dominant_raw_rule_case": self._curve_dominant_value(window_detail["raw_curve_positioning_rule_case"]),
            "dominant_stabilized_rule_case": self._curve_dominant_value(window_detail["stabilized_curve_positioning_rule_case"]),
            "dominant_raw_direction": self._curve_dominant_value(window_detail["raw_curve_positioning"]),
            "dominant_stabilized_direction": self._curve_dominant_value(window_detail["stabilized_curve_positioning"]),
            "dominant_raw_strength": self._curve_dominant_value(window_detail["raw_curve_positioning_strength"]),
            "dominant_stabilized_strength": self._curve_dominant_value(window_detail["stabilized_curve_positioning_strength"]),
        }

    def compare_curve_positioning_stabilization_cases(
        self,
        cases: dict | None = None,
        windows: dict | None = None,
        include_diagnostics: bool = True,
    ) -> dict:
        if self.scores is None or self.exposure_stance is None:
            raise ValueError(
                "Run calculate_component_scores() and calculate_exposure_stance() before curve stabilization comparison."
            )
        if self.exposure_stance_config is None:
            raise ValueError("Run load_module1_config() before curve stabilization comparison.")

        stance_config = self._curve_positioning_stance_config()
        cases = cases or self._default_curve_stabilization_cases()
        windows = windows or self._default_curve_stabilization_windows()

        summary_rows = []
        window_rows = []
        bucket_rows = []
        score_distribution_rows = []
        detail_by_case = {}
        diagnostics_by_case = {}

        for case_id, case_config in cases.items():
            detail = self._curve_stabilization_case_detail(case_config, stance_config)
            detail_by_case[case_id] = detail
            summary_rows.append(self._curve_stabilization_summary_row(case_id, detail))
            for window_id, window in windows.items():
                window_rows.append(
                    self._curve_stabilization_window_row(case_id, window_id, window, detail)
                )
            for bucket_type, raw_col, stabilized_col in [
                ("curve_change", "raw_curve_change_bucket", "stabilized_curve_change_bucket"),
                ("curve_state", "raw_curve_state_bucket", "stabilized_curve_state_bucket"),
                ("yield_move_driver", "raw_yield_move_driver_bucket", "stabilized_yield_move_driver_bucket"),
            ]:
                raw_count = self._count_series_changes(detail[raw_col])
                stabilized_count = self._count_series_changes(detail[stabilized_col])
                bucket_rows.append(
                    {
                        "case_id": case_id,
                        "bucket_type": bucket_type,
                        "raw_change_count": raw_count,
                        "stabilized_change_count": stabilized_count,
                        "change_reduction_count": raw_count - stabilized_count,
                        "change_reduction_ratio": self._ratio_or_na(
                            raw_count - stabilized_count,
                            raw_count,
                        ),
                    }
                )
            for score_type, score_col in [
                ("raw", "raw_curve_positioning_score"),
                ("stabilized", "stabilized_curve_positioning_score"),
            ]:
                counts = detail[score_col].dropna().value_counts().sort_index()
                total = counts.sum()
                for score_value, count in counts.items():
                    score_distribution_rows.append(
                        {
                            "case_id": case_id,
                            "score_type": score_type,
                            "score": score_value,
                            "count": int(count),
                            "ratio": self._ratio_or_na(count, total),
                        }
                    )
            if include_diagnostics:
                diagnostics_by_case[case_id] = detail

        result = {
            "summary": pd.DataFrame(summary_rows),
            "window_summary": pd.DataFrame(window_rows),
            "detail_by_case": detail_by_case,
            "bucket_transition_summary": pd.DataFrame(bucket_rows),
            "score_distribution": pd.DataFrame(score_distribution_rows),
        }
        if include_diagnostics:
            result["diagnostics_by_case"] = diagnostics_by_case
        return result

    def compare_credit_stance_persistence_cases(
        self,
        cases: dict | None = None,
        hysteresis_buffer: float = 0.05,
        windows: dict | None = None,
        include_diagnostics: bool = True,
    ) -> dict:
        """
        Compare credit stance behavior across temporary persistence settings.

        This diagnostic recalculates exposure stance only. It does not recalculate
        component scores and restores the original stance config and outputs before
        returning.
        """
        if self.exposure_stance_config is None:
            raise ValueError(
                "Run load_module1_config() before compare_credit_stance_persistence_cases()."
            )
        if self.features is None:
            raise ValueError(
                "Run calculate_features() before compare_credit_stance_persistence_cases()."
            )
        if self.scores is None:
            raise ValueError(
                "Run calculate_component_scores() before compare_credit_stance_persistence_cases()."
            )
        if self.labels is None:
            raise ValueError(
                "Run calculate_component_labels() before compare_credit_stance_persistence_cases()."
            )
        if self.exposure_stance is None or self.stance_scores is None:
            raise ValueError(
                "Run calculate_exposure_stance() before compare_credit_stance_persistence_cases()."
            )
        if "credit" not in self.exposure_stance_config.get("exposure_stances", {}):
            raise ValueError("Credit exposure stance config is missing.")

        if not (
            isinstance(hysteresis_buffer, (int, float))
            and not isinstance(hysteresis_buffer, bool)
            and hysteresis_buffer >= 0
        ):
            raise ValueError(
                "hysteresis_buffer must be numeric, not bool, and >= 0."
            )

        if cases is None:
            cases = {
                "base_p1_p1": {
                    "credit_spread_change": 1,
                    "credit_spread_state": 1,
                },
                "case_a_change2_state1": {
                    "credit_spread_change": 2,
                    "credit_spread_state": 1,
                },
                "case_b_change1_state2": {
                    "credit_spread_change": 1,
                    "credit_spread_state": 2,
                },
                "case_c_change2_state2": {
                    "credit_spread_change": 2,
                    "credit_spread_state": 2,
                },
            }

        if windows is None:
            windows = {
                "covid_initial_shock": ("2020-03-01", "2020-03-31"),
                "post_shock_recovery": ("2020-06-01", "2020-06-30"),
                "tight_spread_2021q2": ("2021-04-01", "2021-06-30"),
                "late_2022_volatility": ("2022-10-01", "2022-12-31"),
            }

        required_case_keys = {"credit_spread_change", "credit_spread_state"}
        for case_id, settings in cases.items():
            if not isinstance(settings, dict):
                raise ValueError(f"Case {case_id} settings must be a mapping.")
            missing = required_case_keys.difference(settings)
            if missing:
                raise ValueError(
                    f"Case {case_id} is missing persistence setting(s): {sorted(missing)}."
                )
            for key in sorted(required_case_keys):
                value = settings[key]
                if (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or value < 1
                ):
                    raise ValueError(
                        f"Case {case_id} {key} persistence must be an integer, "
                        "not bool, and >= 1."
                    )

        for window_id, window in windows.items():
            if not isinstance(window, (tuple, list)) or len(window) != 2:
                raise ValueError(
                    f"Window {window_id} must be a (start, end) tuple or list."
                )
        required_window_ids = {
            "covid_initial_shock",
            "post_shock_recovery",
            "tight_spread_2021q2",
            "late_2022_volatility",
        }
        missing_windows = sorted(required_window_ids.difference(windows))
        if missing_windows:
            raise ValueError(
                "windows is missing required diagnostic window(s): "
                f"{missing_windows}"
            )

        def first_negative_date(diag: pd.DataFrame):
            negative_dates = diag.index[diag["credit_stance_score"] <= -0.5]
            if len(negative_dates) == 0:
                return pd.NaT
            return negative_dates[0]

        def dominant_pair(diag: pd.DataFrame) -> tuple[object, object]:
            pairs = diag["credit_state_pair"].dropna()
            if pairs.empty:
                return pd.NA, pd.NA
            counts = pairs.value_counts()
            return counts.index[0], counts.iloc[0] / len(pairs)

        def window_slice(diag: pd.DataFrame, window_id: str) -> pd.DataFrame:
            start, end = windows[window_id]
            return self._inclusive_window_slice(diag, start, end)

        def baa_metric(diag: pd.DataFrame, metric: str):
            if "baa10y" not in diag.columns:
                return pd.NA
            values = diag["baa10y"].dropna()
            if values.empty:
                return pd.NA
            if metric == "mean":
                return values.mean()
            if metric == "min":
                return values.min()
            if metric == "max":
                return values.max()
            raise ValueError(f"Unsupported baa10y metric: {metric}")

        def base_window_metrics(case_id: str, diag: pd.DataFrame, window_id: str) -> dict:
            win = window_slice(diag, window_id)
            score = win["credit_stance_score"].dropna()
            obs_count = int(score.shape[0])
            dominant_state_pair, dominant_state_pair_ratio = dominant_pair(win)
            changed_pair_count = int(win["state_stabilization_changed_pair"].sum())

            return {
                "case_id": case_id,
                "window_id": window_id,
                "obs_count": obs_count,
                "credit_stance_score_mean": score.mean() if obs_count else pd.NA,
                "credit_stance_score_min": score.min() if obs_count else pd.NA,
                "credit_stance_score_max": score.max() if obs_count else pd.NA,
                "credit_stance_score_std": score.std() if obs_count else pd.NA,
                "max_abs_daily_score_move": (
                    score.diff().abs().max() if obs_count else pd.NA
                ),
                "baa10y_mean": baa_metric(win, "mean"),
                "baa10y_min": baa_metric(win, "min"),
                "baa10y_max": baa_metric(win, "max"),
                "dominant_credit_state_pair": dominant_state_pair,
                "dominant_credit_state_pair_ratio": dominant_state_pair_ratio,
                "changed_pair_count": changed_pair_count,
                "changed_pair_ratio": self._ratio_or_na(
                    changed_pair_count,
                    obs_count,
                ),
                "changed_change_state_count": int(
                    win["state_stabilization_changed_change_state"].sum()
                ),
                "changed_spread_state_count": int(
                    win["state_stabilization_changed_spread_state"].sum()
                ),
            }

        required_diagnostic_cols = {
            "credit_stance_score",
            "credit_state_pair",
            "state_stabilization_changed_change_state",
            "state_stabilization_changed_spread_state",
            "state_stabilization_changed_pair",
            "credit_spread_state_category",
            "credit_spread_change_state",
        }

        original_exposure_stance_config = copy.deepcopy(self.exposure_stance_config)
        original_stance_scores = self.stance_scores.copy(deep=True)
        original_exposure_stance = self.exposure_stance.copy(deep=True)

        diagnostics_by_case = {}
        window_metrics_rows = []
        shock_rows = []
        recovery_rows = []
        tight_rows = []
        late_rows = []
        full_rows = []

        try:
            for case_id, settings in cases.items():
                case_exposure_stance_config = copy.deepcopy(
                    original_exposure_stance_config
                )
                case_exposure_stance_config["exposure_stances"]["credit"][
                    "state_stabilization"
                ] = {
                    "credit_spread_change": {
                        "hysteresis_buffer": float(hysteresis_buffer),
                        "min_state_persistence": settings["credit_spread_change"],
                    },
                    "credit_spread_state": {
                        "hysteresis_buffer": float(hysteresis_buffer),
                        "min_state_persistence": settings["credit_spread_state"],
                    },
                }
                self.exposure_stance_config = case_exposure_stance_config
                self.calculate_exposure_stance()
                diag = self.trace_stance_score(
                    "credit",
                    include_raw_input=True,
                    include_labels=False,
                )

                missing_cols = sorted(required_diagnostic_cols.difference(diag.columns))
                if missing_cols:
                    raise ValueError(
                        "Credit stance diagnostics are missing required columns: "
                        f"{missing_cols}"
                    )

                diagnostics_by_case[case_id] = diag.copy(deep=True)

                for window_id in windows:
                    window_metrics_rows.append(
                        base_window_metrics(case_id, diag, window_id)
                    )

                shock = window_slice(diag, "covid_initial_shock")
                shock_rows.append(
                    {
                        "case_id": case_id,
                        "first_credit_negative_date": first_negative_date(shock),
                    }
                )

                recovery = window_slice(diag, "post_shock_recovery")
                recovery_score = recovery["credit_stance_score"].dropna()
                recovery_pair, recovery_pair_ratio = dominant_pair(recovery)
                recovery_rows.append(
                    {
                        "case_id": case_id,
                        "dominant_credit_state_pair": recovery_pair,
                        "dominant_credit_state_pair_ratio": recovery_pair_ratio,
                        "credit_stance_score_mean": (
                            recovery_score.mean()
                            if not recovery_score.empty
                            else pd.NA
                        ),
                        "negative_score_days": int((recovery_score <= -0.5).sum()),
                    }
                )

                tight = window_slice(diag, "tight_spread_2021q2")
                tight_score = tight["credit_stance_score"].dropna()
                tight_obs = int(tight_score.shape[0])
                tight_state_count = int(
                    (tight["credit_spread_state_category"] == "tight").sum()
                )
                tight_pair_count = int(
                    tight["credit_state_pair"]
                    .dropna()
                    .astype(str)
                    .str.contains(r"\|tight$")
                    .sum()
                )
                tight_rows.append(
                    {
                        "case_id": case_id,
                        "tight_state_count": tight_state_count,
                        "tight_state_ratio": (
                            self._ratio_or_na(tight_state_count, tight_obs)
                        ),
                        "tight_pair_count": tight_pair_count,
                        "tight_pair_ratio": (
                            self._ratio_or_na(tight_pair_count, tight_obs)
                        ),
                        "credit_stance_score_mean": (
                            tight_score.mean() if tight_obs else pd.NA
                        ),
                    }
                )

                late = window_slice(diag, "late_2022_volatility")
                late_score = late["credit_stance_score"].dropna()
                late_moves = late_score.diff().abs().dropna()
                late_rows.append(
                    {
                        "case_id": case_id,
                        "max_abs_daily_score_move": (
                            late_moves.max() if not late_moves.empty else pd.NA
                        ),
                        "large_move_gt_0_5_count": int((late_moves > 0.5).sum()),
                        "large_move_gt_1_0_count": int((late_moves > 1.0).sum()),
                    }
                )

                full_obs = int(diag["credit_stance_score"].notna().sum())
                full_changed_pair_count = int(
                    diag["state_stabilization_changed_pair"].sum()
                )
                full_rows.append(
                    {
                        "case_id": case_id,
                        "changed_pair_count": full_changed_pair_count,
                        "changed_change_state_count": int(
                            diag["state_stabilization_changed_change_state"].sum()
                        ),
                        "changed_spread_state_count": int(
                            diag["state_stabilization_changed_spread_state"].sum()
                        ),
                        "changed_pair_ratio": self._ratio_or_na(
                            full_changed_pair_count,
                            full_obs,
                        ),
                        "non_missing_obs_count": full_obs,
                    }
                )
        finally:
            self.exposure_stance_config = original_exposure_stance_config
            self.stance_scores = original_stance_scores
            self.exposure_stance = original_exposure_stance

        shock_detection_df = pd.DataFrame(shock_rows)
        base_negative_date = shock_detection_df.loc[
            shock_detection_df["case_id"] == "base_p1_p1",
            "first_credit_negative_date",
        ]
        base_negative_date = (
            base_negative_date.iloc[0] if not base_negative_date.empty else pd.NaT
        )
        shock_detection_df["delay_days_vs_base"] = shock_detection_df[
            "first_credit_negative_date"
        ].apply(
            lambda value: (
                pd.NA
                if pd.isna(value) or pd.isna(base_negative_date)
                else (value - base_negative_date).days
            )
        )

        window_metrics_df = pd.DataFrame(window_metrics_rows)
        recovery_behavior_df = pd.DataFrame(recovery_rows)
        tight_spread_behavior_df = pd.DataFrame(tight_rows)
        late_volatility_df = pd.DataFrame(late_rows)
        full_period_stabilization_df = pd.DataFrame(full_rows)

        summary_rows = []
        for case_id, settings in cases.items():
            shock_row = shock_detection_df[
                shock_detection_df["case_id"] == case_id
            ].iloc[0]
            recovery_row = recovery_behavior_df[
                recovery_behavior_df["case_id"] == case_id
            ].iloc[0]
            tight_row = tight_spread_behavior_df[
                tight_spread_behavior_df["case_id"] == case_id
            ].iloc[0]
            late_row = late_volatility_df[
                late_volatility_df["case_id"] == case_id
            ].iloc[0]
            full_row = full_period_stabilization_df[
                full_period_stabilization_df["case_id"] == case_id
            ].iloc[0]

            summary_rows.append(
                {
                    "case_id": case_id,
                    "change_persistence": settings["credit_spread_change"],
                    "state_persistence": settings["credit_spread_state"],
                    "covid_first_credit_negative_date": shock_row[
                        "first_credit_negative_date"
                    ],
                    "covid_delay_days_vs_base": shock_row["delay_days_vs_base"],
                    "recovery_mean_score": recovery_row[
                        "credit_stance_score_mean"
                    ],
                    "recovery_negative_score_days": recovery_row[
                        "negative_score_days"
                    ],
                    "tight_2021q2_mean_score": tight_row[
                        "credit_stance_score_mean"
                    ],
                    "tight_2021q2_tight_state_ratio": tight_row[
                        "tight_state_ratio"
                    ],
                    "late_2022_max_abs_daily_score_move": late_row[
                        "max_abs_daily_score_move"
                    ],
                    "late_2022_large_move_gt_0_5_count": late_row[
                        "large_move_gt_0_5_count"
                    ],
                    "late_2022_large_move_gt_1_0_count": late_row[
                        "large_move_gt_1_0_count"
                    ],
                    "full_changed_pair_count": full_row["changed_pair_count"],
                    "full_changed_pair_ratio": full_row["changed_pair_ratio"],
                }
            )

        result = {
            "summary": pd.DataFrame(summary_rows),
            "window_metrics": window_metrics_df,
            "shock_detection": shock_detection_df,
            "recovery_behavior": recovery_behavior_df,
            "tight_spread_behavior": tight_spread_behavior_df,
            "late_volatility": late_volatility_df,
            "full_period_stabilization": full_period_stabilization_df,
        }
        if include_diagnostics:
            result["diagnostics"] = diagnostics_by_case

        return result


    def _select_related_inputs(self, target, level, inputs=None, related_inputs=None):
        """
        Select requested raw inputs if they are related to the target.
        """
        import warnings

        related_inputs = (
            self.raw_inputs_for_target(target, level)
            if related_inputs is None
            else list(related_inputs)
        )

        if not related_inputs:
            raise ValueError(
                f"No related raw inputs found for {level} target: {target}"
            )

        if inputs is None:
            return related_inputs

        if isinstance(inputs, str):
            requested_inputs = [inputs]
        else:
            requested_inputs = list(inputs)

        unrelated = [item for item in requested_inputs if item not in related_inputs]

        if unrelated:
            warnings.warn(
                "The following inputs are not related to "
                f"{level} target '{target}' and will be ignored: {unrelated}. "
                f"Plotting all related inputs instead: {related_inputs}",
                UserWarning,
            )
            return related_inputs

        return requested_inputs


    def _mark_label_changes(self, ax, label_table, label_col, index):
        """
        Mark label transition dates on an existing target-score axis.
        """
        if label_table is None:
            raise ValueError(
                "mark_label_changes=True requires labels before plotting."
            )
        if label_col is None or label_col not in label_table.columns:
            raise ValueError(f"Target label column not found: {label_col}")

        labels = label_table[label_col].reindex(index).ffill()
        labels_valid = labels.dropna()

        if labels_valid.empty:
            return

        change_dates = labels_valid.index[
            labels_valid.ne(labels_valid.shift(1))
        ]

        for dt in change_dates:
            if dt == labels_valid.index.min():
                continue
            ax.axvline(dt, linestyle=":", linewidth=0.8, alpha=0.35)


    def _add_score_zones(
        self,
        ax,
        target_info: dict,
        normalize_target: bool = False,
    ):
        """
        Add threshold-based background zones to the target-score axis.
        """
        if normalize_target:
            raise ValueError(
                "show_score_zones=True requires normalize_target=False because "
                "score-zone thresholds use raw score units."
            )

        level = target_info["level"]
        canonical_target = target_info["canonical_target"]
        ymin, ymax = ax.get_ylim()

        def clipped_span(low, high, **kwargs):
            low = max(low, ymin)
            high = min(high, ymax)
            if low < high:
                ax.axhspan(low, high, zorder=0, **kwargs)

        if level == "component":
            thresholds = target_info["config"].get("label", {}).get("thresholds", {})
            for key in ["positive", "negative"]:
                if key not in thresholds:
                    raise ValueError(
                        f"Component target '{canonical_target}' is missing "
                        f"label threshold: {key}"
                    )

            positive_threshold = thresholds["positive"]
            negative_threshold = thresholds["negative"]
        elif level == "stance":
            if self.exposure_stance_config is None:
                raise ValueError("Run load_module1_config() first.")

            rules = self.exposure_stance_config.get("stance_label_rules", {})
            direction_thresholds = rules.get("direction_thresholds", {})
            for key in ["positive_min", "negative_max"]:
                if key not in direction_thresholds:
                    raise ValueError(
                        f"Stance label rules are missing direction threshold: {key}"
                    )

            positive_threshold = direction_thresholds["positive_min"]
            negative_threshold = direction_thresholds["negative_max"]
        else:
            raise ValueError(f"Unsupported target level for score zones: {level}")

        clipped_span(
            positive_threshold,
            ymax,
            color="C2",
            alpha=0.08,
        )
        clipped_span(
            negative_threshold,
            positive_threshold,
            color="C7",
            alpha=0.06,
        )
        clipped_span(
            ymin,
            negative_threshold,
            color="C3",
            alpha=0.08,
        )
        ax.set_ylim(ymin, ymax)


    def _plot_historical_review_state_timeline(
        self,
        ax,
        case_df: pd.DataFrame,
        decomposition: pd.DataFrame,
    ):
        """
        Plot contiguous and per-date match states for one review case.
        """
        state_to_y = {
            "missing": -1,
            "mismatch": 0,
            "match": 1,
        }
        colors = {
            "match": "C2",
            "mismatch": "C3",
            "missing": "C7",
        }
        labels_seen = set()

        for _, row in decomposition.iterrows():
            state = row["match_state"]
            label = state if state not in labels_seen else None
            ax.axvspan(
                row["start"],
                row["end"],
                color=colors.get(state, "C7"),
                alpha=0.12,
                label=label,
            )
            labels_seen.add(state)

        for state, y_value in state_to_y.items():
            rows = case_df[case_df["match_state"] == state]
            if rows.empty:
                continue
            label = state if state not in labels_seen else None
            ax.scatter(
                rows.index,
                [y_value] * len(rows),
                s=14,
                alpha=0.8,
                color=colors[state],
                label=label,
            )
            labels_seen.add(state)

        ax.set_yticks([-1, 0, 1])
        ax.set_yticklabels(["missing", "mismatch", "match"])
        ax.set_ylim(-1.5, 1.5)
        ax.set_ylabel("label state")
        ax.set_title("Historical review match-state timeline")
        ax.grid(axis="y", alpha=0.2)
        handles, labels = ax.get_legend_handles_labels()
        unique = {}
        for handle, label in zip(handles, labels):
            if label not in unique:
                unique[label] = handle
        ax.legend(unique.values(), unique.keys(), loc="best")


    def _decompose_match_windows(self, case_df: pd.DataFrame) -> pd.DataFrame:
        """
        Summarize contiguous match-state windows.
        """
        if case_df.empty:
            return pd.DataFrame(
                columns=["start", "end", "match_state", "obs_count", "ratio"]
            )

        total_obs = len(case_df)
        groups = case_df["match_state"].ne(case_df["match_state"].shift()).cumsum()
        segments = []

        for _, segment in case_df.groupby(groups, sort=False):
            segments.append(
                {
                    "start": segment.index.min(),
                    "end": segment.index.max(),
                    "match_state": segment["match_state"].iloc[0],
                    "obs_count": int(len(segment)),
                    "ratio": float(len(segment) / total_obs),
                }
            )

        return pd.DataFrame(segments)


    def plot_historical_review_case(
        self,
        target: str,
        level: str,
        context_id: str,
        expected_label: str | None = None,
        inputs=None,
        start=None,
        end=None,
        normalize_inputs: bool = True,
        normalize_target: bool = False,
        ffill_inputs: bool = True,
        mark_label_changes: bool = False,
        show_score_zones: bool = False,
        include_target_inputs: bool = True,
        figsize=(12, 7),
        height_ratios=(3, 1),
        show: bool = True,
    ):
        """
        Plot one YAML-defined historical event case.
    
        context_id is required and selects the historical review case, expected
        label, target, and diagnostic event window.
    
        Optional start/end control only the visual display window. They may be:
        - None: use the context_id event-window boundary.
        - Date-like values: use explicit display-window boundaries.
        - Numeric ratios: extend the display window by that ratio of the context
          window length. Numeric start extends backward from context_start, and
          numeric end extends forward from context_end.
    
        Examples:
        - start=None, end=None: plot the context window only.
        - start=1, end=1: add one context-window length before and after.
        - start=0.5, end=0.5: add half a context-window length before and after.
        - start="2019-01-01", end=1: use explicit start and ratio-based end.
    
        The match-state timeline remains based on the original context_id event
        window, and that context window is marked on the target/input panel.
    
        By default, the plot includes a top target-score/raw-input panel and a
        bottom match-state timeline panel with a shared x-axis. Set
        include_target_inputs=False to use a single-panel match-state plot.
    
        Batch quantitative diagnostics are available through
        review_historical_cases(output="diagnostic"), not through plotting.

        Historical review observations and match-state windows are consumed from
        the canonical review_historical_cases() detail and windows outputs.
    
        Returns:
        - include_target_inputs=True: fig, {"target", "inputs", "state"}
        - include_target_inputs=False: fig, ax
        """
        if context_id is None:
            raise ValueError("context_id is required for plot_historical_review_case().")
    
        cases = self._select_historical_cases(
            target=target,
            level=level,
            context_id=None,
            only_use_for_validation=None,
            include_low_relevance=None,
            error_context="historical plot cases",
            require_non_empty=False,
        )
        cases = cases[cases["context_id"] == context_id]
        if cases.empty:
            raise ValueError(
                "No historical cases match the requested plot filters: "
                f"target={target}, level={level}, context_id={context_id}."
            )
        if len(cases) > 1:
            matches = cases[
                ["context_id", "level", "canonical_target", "target"]
            ].to_dict("records")
            raise ValueError(
                "Multiple historical cases match the requested plot filters: "
                f"{matches}. Use a more specific target."
            )
    
        case = cases.iloc[0]
        expected_strength = case.get("expected_strength", pd.NA)
        selected_case_key = self._make_historical_case_key(
            case,
            self._normalize_review_label(case["expected_label"]),
            (
                pd.NA
                if pd.isna(expected_strength)
                else self._normalize_review_label(expected_strength)
            ),
        )

        review_kwargs = {
            "target": target,
            "context_id": context_id,
            "level": level,
            "only_use_for_validation": False,
            "include_low_relevance": True,
        }
        detail = self.review_historical_cases(
            **review_kwargs,
            output="detail",
        )
        windows = self.review_historical_cases(
            **review_kwargs,
            output="windows",
        )

        detail_for_case = detail[detail["case_key"] == selected_case_key].copy()
        windows_for_case = windows[windows["case_key"] == selected_case_key].copy()
        if detail_for_case.empty:
            raise ValueError(
                "No canonical historical review detail is available for the "
                "selected plot case."
            )

        detail_for_case["date"] = pd.to_datetime(detail_for_case["date"])
        case_df = detail_for_case.set_index("date").sort_index()
        case_df["model_label"] = case_df["actual_label"]
        case_df["model_strength"] = case_df["actual_strength"]
        case_df.attrs["start"] = pd.to_datetime(case["start"])
        case_df.attrs["end"] = pd.to_datetime(case["end"])

        if expected_label is None:
            decomposition = windows_for_case
        else:
            expected_normalized = self._normalize_review_label(expected_label)
            case_df["expected_label"] = expected_label
            case_df["match_state"] = case_df["model_label"].apply(
                lambda model_label: (
                    "missing"
                    if pd.isna(model_label)
                    else (
                        "match"
                        if self._normalize_review_label(model_label)
                        == expected_normalized
                        else "mismatch"
                    )
                )
            )
            decomposition = self._decompose_match_windows(case_df)
    
        context_start = pd.to_datetime(case["start"])
        context_end = pd.to_datetime(case["end"])
        display_start, display_end = self._resolve_historical_display_window(
            context_start=context_start,
            context_end=context_end,
            start=start,
            end=end,
            warn_no_overlap=True,
        )
    
        if include_target_inputs:
            fig, (ax_target, ax_state) = plt.subplots(
                2,
                1,
                figsize=figsize,
                sharex=True,
                gridspec_kw={"height_ratios": height_ratios},
            )
    
            ax_target, ax_inputs = self._plot_target_inputs_on_axes(
                ax_target,
                target=case["canonical_target"],
                level=case["level"],
                inputs=inputs,
                start=display_start,
                end=display_end,
                context_id=None,
                normalize_inputs=normalize_inputs,
                normalize_target=normalize_target,
                ffill_inputs=ffill_inputs,
                mark_label_changes=mark_label_changes,
                show_score_zones=show_score_zones,
            )
    
            ax_target = self._mark_context_window_and_update_legend(
                ax_target,
                context_start,
                context_end,
                twin_ax=ax_inputs,
            )
            ax_target.set_xlabel("")
    
            self._plot_historical_review_state_timeline(
                ax_state,
                case_df,
                decomposition,
            )
            ax_state.set_xlabel("date")
            ax_state.set_xlim(display_start, display_end)
    
            #fig.tight_layout()
    
            if show:
                plt.show()
    
            return fig, {
                "target": ax_target,
                "inputs": ax_inputs,
                "state": ax_state,
            }
    
        fig, ax = plt.subplots(figsize=figsize)
        self._plot_historical_review_state_timeline(
            ax,
            case_df,
            decomposition,
        )
        ax.set_xlim(display_start, display_end)
        ax.set_xlabel("date")
        #fig.tight_layout()
    
        if show:
            plt.show()
    
        return fig, ax


    def _resolve_historical_display_window(
        self,
        context_start,
        context_end,
        start=None,
        end=None,
        warn_no_overlap: bool = True,
    ):
        """
        Resolve the visual display window for plot_historical_review_case().
    
        start/end may be:
        - None: use the context window boundary.
        - Date-like value: use it as an explicit display boundary.
        - Numeric value: treat it as a ratio of the context window length.
            - numeric start extends backward from context_start.
            - numeric end extends forward from context_end.
        """
        from numbers import Real
        import warnings
    
        context_start = pd.to_datetime(context_start)
        context_end = pd.to_datetime(context_end)
    
        if context_start > context_end:
            raise ValueError("context_start must be earlier than or equal to context_end.")
    
        context_span = context_end - context_start
    
        def is_ratio(value):
            return isinstance(value, Real) and not isinstance(value, bool)
    
        def resolve_start(value):
            if value is None:
                return context_start
            if is_ratio(value):
                if value < 0:
                    raise ValueError("Numeric start ratio must be non-negative.")
                return context_start - context_span * float(value)
            return pd.to_datetime(value)
    
        def resolve_end(value):
            if value is None:
                return context_end
            if is_ratio(value):
                if value < 0:
                    raise ValueError("Numeric end ratio must be non-negative.")
                return context_end + context_span * float(value)
            return pd.to_datetime(value)
    
        display_start = resolve_start(start)
        display_end = resolve_end(end)
    
        if display_start > display_end:
            raise ValueError("start must be earlier than or equal to end.")
    
        if warn_no_overlap and (
            display_end < context_start or display_start > context_end
        ):
            warnings.warn(
                "The selected start/end display window does not overlap the "
                "context_id event window. The target/input panel will use the "
                "requested display window, while the review-state timeline still "
                "reflects the context_id event window.",
                UserWarning,
            )
    
        return display_start, display_end


    def _mark_context_window_and_update_legend(self, ax, start, end, twin_ax=None):
        """
        Mark the historical context window and rebuild the legend.
    
        If twin_ax is provided, include legend items from both ax and twin_ax.
        This is needed for target-vs-input plots where inputs are drawn on a
        twinx axis.
        """
        ax.axvspan(
            pd.to_datetime(start),
            pd.to_datetime(end),
            alpha=0.08,
            color="C0",
            label="context window",
            zorder=0,
        )
    
        handles_1, labels_1 = ax.get_legend_handles_labels()
    
        if twin_ax is None:
            handles_2, labels_2 = [], []
        else:
            handles_2, labels_2 = twin_ax.get_legend_handles_labels()
    
        unique = {}
        for handle, label in zip(handles_1 + handles_2, labels_1 + labels_2):
            if label and label not in unique:
                unique[label] = handle
    
        if unique:
            ax.legend(unique.values(), unique.keys(), loc="best")
    
        return ax


    def _normalize_for_comparison_plot(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize numeric plot columns while preserving unusable columns as NaN.
        """
        if df.empty:
            return df.copy()

        numeric = df.apply(pd.to_numeric, errors="coerce")
        mean = numeric.mean()
        std = numeric.std().replace(0, pd.NA)
        return (numeric - mean) / std


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


    def _plot_target_inputs_on_axes(
        self,
        ax_target,
        target: str,
        level: str,
        inputs=None,
        start=None,
        end=None,
        context_id=None,
        normalize_inputs: bool = True,
        normalize_target: bool = False,
        ffill_inputs: bool = True,
        mark_label_changes: bool = False,
        show_score_zones: bool = False,
        target_color="grey",
    ):
        dataset = self.build_target_comparison_dataset(
            target=target,
            level=level,
            compare="raw_inputs",
            context_id=context_id,
            start=start,
            end=end,
            include_labels=True,
            include_strength=True,
            ffill_inputs=ffill_inputs,
        )
        selected_inputs = self._select_related_inputs(
            dataset.resolution.get("canonical_target"),
            dataset.target_level,
            inputs,
            related_inputs=dataset.comparison_columns,
        )
        dataset = replace(dataset, comparison_columns=tuple(selected_inputs))

        ax_inputs = ax_target.twinx()
        target_plot = dataset.data.loc[:, list(dataset.target_columns)].copy()
        input_plot = dataset.data.loc[:, list(dataset.comparison_columns)].copy()
        if normalize_target:
            target_plot = self._normalize_for_comparison_plot(target_plot)
        if normalize_inputs:
            input_plot = self._normalize_for_comparison_plot(input_plot)

        for index, col in enumerate(target_plot.columns):
            plot_kwargs = {"linewidth": 2.0, "label": col}
            if index == 0:
                plot_kwargs["color"] = target_color
            ax_target.plot(target_plot.index, target_plot[col], **plot_kwargs)
        ax_target.axhline(0, linewidth=1, linestyle="--", color=target_color)
        ax_target.set_ylabel(dataset.target_columns[0])

        if show_score_zones:
            self._add_score_zones(
                ax_target,
                dataset.resolution,
                normalize_target=normalize_target,
            )

        for col in input_plot.columns:
            ax_inputs.plot(
                input_plot.index,
                input_plot[col],
                linewidth=1.2,
                alpha=0.75,
                label=col,
            )
        ax_inputs.set_ylabel(
            "normalized raw inputs" if normalize_inputs else "raw inputs"
        )

        if mark_label_changes:
            label_col = dataset.resolution.get("label_col")
            label_table = (
                self.exposure_stance
                if dataset.target_level == "stance"
                else self.labels
            )
            if label_table is None:
                raise ValueError(
                    "mark_label_changes=True requires generated labels."
                )
            self._mark_label_changes(
                ax_target,
                label_table,
                label_col,
                target_plot.index,
            )

        title = (
            f"{dataset.target_level} {dataset.resolution.get('canonical_target')}: "
            f"{dataset.target_columns[0]} vs raw inputs"
        )
        ax_target.set_title(title)
        lines_1, labels_1 = ax_target.get_legend_handles_labels()
        lines_2, labels_2 = ax_inputs.get_legend_handles_labels()
        ax_target.legend(lines_1 + lines_2, labels_1 + labels_2, loc="best")
        return ax_target, ax_inputs


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
