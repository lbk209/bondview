import copy
from dataclasses import dataclass
from collections.abc import Mapping

import pandas as pd
from tqdm.notebook import tqdm

from module1_analysis import Module1Analysis, TargetContextResult
from module1_calculator import Module1Calculator, Module1Result
from module1_historical_analysis import Module1HistoricalAnalysis


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
class DiagnosticInputSpec:
    component: str
    source: str
    kind: str
    output: str
    role: str | None = None


class Module1SensitivityDiagnostics:
    """Sensitivity and comparison diagnostics for completed Module 1 results."""

    _CALCULATOR_STATE_FIELDS = (
        "data", "features", "scores", "labels", "stance_scores",
        "exposure_stance", "module1_config", "feature_config",
        "component_config", "exposure_stance_config", "horizons",
        "default_horizons", "horizon_overrides", "module1_config_validation",
    )
    _CALCULATOR_HELPERS = {
        "_prepare_component_input_series",
        "_clip_score",
        "_calculate_single_feature_component_score",
        "_calculate_weighted_feature_component_score",
        "_calculate_curve_move_driver_score",
        "_curve_move_driver_bucket_scores",
        "_component_score_bucket_config",
        "_resolve_rule_mapped_stance_schema",
        "_score_bucket",
        "_calculate_current_state_component_score",
        "_label_stance_direction",
        "_label_stance_strength",
        "_build_weighted_stance_score_breakdown",
        "_build_rule_mapped_stance_score_breakdown",
        "calculate_exposure_stance",
        "_curve_move_driver_score_from_prepared_inputs",
    }

    def __init__(
        self,
        result: Module1Result,
        historical_context: dict | None = None,
        historical_cases: pd.DataFrame | None = None,
        historical_expected_label_validation: dict | None = None,
    ):
        self.result = result
        self.analysis = Module1Analysis(result)
        self.calculator = object.__new__(Module1Calculator)
        self.data = self._copy_result_value(result.data)
        self.features = self._copy_result_value(result.features)
        self.scores = self._copy_result_value(result.scores)
        self.labels = self._copy_result_value(result.labels)
        self.stance_scores = self._copy_result_value(result.stance_scores)
        self.exposure_stance = self._copy_result_value(result.exposure_stance)
        self.module1_config = self._copy_result_value(result.module1_config)
        self.feature_config = self._copy_result_value(result.feature_config)
        self.component_config = self._copy_result_value(result.component_config)
        self.exposure_stance_config = self._copy_result_value(result.exposure_stance_config)
        self.horizons = self._copy_result_value(result.horizons)
        self.default_horizons = self._copy_result_value(result.default_horizons)
        self.horizon_overrides = self._copy_result_value(result.horizon_overrides)
        self.module1_config_validation = self._copy_result_value(result.module1_config_validation)
        self.historical_context = historical_context
        self.historical_cases = historical_cases
        self.historical_expected_label_validation = historical_expected_label_validation
        self._sync_calculator_state()

    @staticmethod
    def _copy_result_value(value):
        if value is None:
            return None
        if isinstance(value, pd.DataFrame):
            return value.copy(deep=True)
        if isinstance(value, pd.Series):
            return value.copy(deep=True)
        return copy.deepcopy(value)

    def _sync_calculator_state(self) -> None:
        for field_name in self._CALCULATOR_STATE_FIELDS:
            setattr(self.calculator, field_name, getattr(self, field_name))
        self.calculator.fred = None
        self.calculator.series_config_path = None
        self.calculator.module1_config_path = None
        self.calculator.data_path = None
        self.calculator.series_config = None

    def __getattr__(self, name):
        if name in self._CALCULATOR_HELPERS:
            self._sync_calculator_state()
            return getattr(self.calculator, name)
        raise AttributeError(name)

    def _resolve_target(self, target: str, level: str | None, allow_group: bool = False):
        return self.analysis.resolve_target(target, level, allow_group=allow_group)

    def get_target_context(
        self, target, level, dependency_level="auto", include_labels=True,
        include_strength=True, start=None, end=None,
        ffill_inputs=True,
    ) -> TargetContextResult:
        return self.analysis.get_target_context(
            target=target, level=level, dependency_level=dependency_level,
            include_labels=include_labels, include_strength=include_strength,
            start=start, end=end, ffill_inputs=ffill_inputs,
        )

    def _rule_mapped_trace_supported_functions(self) -> set[str]:
        return {
            "duration_rule_stance",
            "credit_spread_stance",
            "curve_positioning_stance",
        }

    def trace_stance_score(
        self, target: str, start=None, end=None,
        include_raw_input: bool = True, include_labels: bool = True,
    ) -> pd.DataFrame:
        if target is None or str(target).strip() == "":
            raise ValueError("target must be a non-empty stance identifier.")
        target_info = self._resolve_target(target, level="stance")
        stance_name = target_info.canonical_target
        stance_config = target_info.config
        function = stance_config.get("function")
        if function in self._rule_mapped_trace_supported_functions():
            return self._trace_rule_mapped_stance_score(
                stance_name, start=start, end=end,
                include_raw_input=include_raw_input, include_labels=include_labels,
            )
        raise ValueError(
            f"Unsupported stance trace function for sensitivity diagnostics: "
            f"{stance_name}: {function}"
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
        """
        Compare multiple horizon configurations with historical review outputs.

        This batch diagnostic creates temporary calculators for local
        counterfactual runs. It does not mutate any caller-owned calculator or
        result state.
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

        base_calc = Module1Calculator(
            api_key_env=api_key_env,
            series_config_path=series_config_path,
            module1_config_path=module1_config_path,
            data_path=data_path,
        )
        base_horizons = base_calc.validate_horizons(
            base_horizons,
            base_horizons=base_calc.default_horizons,
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

            case_horizons = base_calc.validate_horizons(
                case_overrides,
                base_horizons=base_horizons,
            )
            calc = Module1Calculator(
                api_key_env=api_key_env,
                series_config_path=series_config_path,
                module1_config_path=module1_config_path,
                data_path=data_path,
            )
            calc.horizons = case_horizons
            calc.run_module1_pipeline()

            historical = Module1HistoricalAnalysis(calc.to_module1_result())
            historical.load_historical_context(historical_context_path)

            metadata = {"case_id": case_id}
            metadata.update({key: case_horizons[key] for key in base_horizons})

            review_output = (
                "report" if normalized_output == "summary" else normalized_output
            )
            review_table = historical.review_historical_cases(
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

            if start is not None:
                diagnostics = diagnostics.loc[diagnostics.index >= pd.to_datetime(start)]
            if end is not None:
                diagnostics = diagnostics.loc[diagnostics.index <= pd.to_datetime(end)]

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

    def _curve_positioning_stance_config(self) -> dict:
            if self.exposure_stance_config is None:
                raise ValueError("Run load_module1_config() before curve diagnostics.")

            stance_config = self.exposure_stance_config["exposure_stances"].get(
                "curve_positioning"
            )
            if stance_config is None:
                raise ValueError("Curve positioning stance config is missing.")

            return stance_config

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

            historical = Module1HistoricalAnalysis(
                self.result,
                historical_context=self.historical_context,
            )
            resolved = {
                context_id: historical.resolve_historical_event_window(context_id)
                for context_id in events["context_id"]
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

    def _curve_move_driver_score_from_prepared_inputs(self, front_end: pd.Series, long_end: pd.Series, bucket_scores: dict[str, float]) -> pd.Series:
        self._sync_calculator_state()
        return self.calculator._curve_move_driver_score_from_prepared_inputs(
            front_end,
            long_end,
            bucket_scores,
        )

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
