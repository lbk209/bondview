import copy
from dataclasses import dataclass, replace

import pandas as pd
from tqdm.notebook import tqdm

from module1_calculator import Module1Calculator, Module1Result
from module1_diagnostics import (
    DiagnosticInputSpec,
    Module1Diagnostics,
    RuleMappedDiagnosticSpec,
)
from module1_historical_analysis import Module1HistoricalAnalysis


@dataclass(frozen=True)
class SmoothingDiagnosticTargetProfile:
    spec: RuleMappedDiagnosticSpec
    display_target: str
    score_diff_col: str
    score_change_metric_prefix: str


class Module1SensitivityDiagnostics:
    """Sensitivity and comparison diagnostics for completed Module 1 results."""

    def __init__(
        self,
        result: Module1Result,
        historical_context: dict | None = None,
        historical_cases: pd.DataFrame | None = None,
        historical_expected_label_validation: dict | None = None,
    ):
        self.result = result
        self._diagnostics = Module1Diagnostics(result)
        self.data = self._copy_result_value(result.data)
        self.features = self._copy_result_value(result.features)
        self.scores = self._copy_result_value(result.scores)
        self.labels = self._copy_result_value(result.labels)
        self.stance_scores = self._copy_result_value(result.stance_scores)
        self.exposure_stance = self._copy_result_value(result.exposure_stance)
        self.module1_config = self._copy_result_value(result.module1_config)
        self.feature_config = (
            None
            if self.module1_config is None
            else {"features": self.module1_config["features"]}
        )
        self.component_config = (
            None
            if self.module1_config is None
            else {"components": self.module1_config["components"]}
        )
        self.exposure_stance_config = (
            None
            if self.module1_config is None
            else {
                "stance_label_rules": self.module1_config["stance_label_rules"],
                "exposure_stances": self.module1_config["exposure_stances"],
            }
        )
        self.horizons = self._copy_result_value(result.horizons)
        self.historical_context = historical_context
        self.historical_cases = historical_cases
        self.historical_expected_label_validation = historical_expected_label_validation

    @staticmethod
    def _copy_result_value(value):
        if value is None:
            return None
        if isinstance(value, pd.DataFrame):
            return value.copy(deep=True)
        if isinstance(value, pd.Series):
            return value.copy(deep=True)
        return copy.deepcopy(value)

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
                horizons=case_horizons,
            )
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
            if (
                score_config.get("state_transform") == "fixed_anchor"
                and function not in {
                    "single_feature_score",
                    "weighted_feature_score",
                }
            ):
                raise ValueError(
                    f"Unsupported current-state score function for "
                    f"{component_name}: {function}"
                )
            if function not in {
                "single_feature_score",
                "weighted_feature_score",
                "curve_move_driver_score",
            }:
                raise ValueError(
                    f"Unsupported score function for diagnostic component {component_name}: "
                    f"{function}"
                )

            return Module1Calculator.calculate_component_score(
                self.features,
                component_name,
                score_config,
                self.horizons,
                apply_input_preparation=apply_input_preparation,
                apply_score_smoothing=False,
            )

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

            component_names = self._diagnostics.diagnostic_component_names(target)
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
            return Module1Calculator.label_exposure_stance_score(
                score,
                stance_config,
                self.exposure_stance_config["stance_label_rules"],
            )

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

            spec = self._diagnostics.rule_mapped_diagnostic_spec(target)
            stance_config = spec.stance_config
            temporary_scores = self.scores.copy()
            for score_col in spec.score_input_cols:
                alternate_col = f"raw_{score_col}"
                if alternate_col not in alternate_scores.columns:
                    raise ValueError(
                        f"Missing alternate diagnostic score column for {target}: "
                        f"{alternate_col}"
                    )
                temporary_scores[score_col] = alternate_scores[alternate_col]

            reconstruction = Module1Calculator.build_rule_mapped_stance_score_breakdown(
                temporary_scores,
                self.component_config,
                spec.target,
                stance_config,
                spec.rule_mapped_schema,
            )

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

            spec = self._diagnostics.rule_mapped_diagnostic_spec(target)
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

    def _prepared_input_sources_for_diagnostic_components(
            self,
            target: str,
            component_names: tuple[str, ...],
        ) -> tuple[str, ...]:
            specs = self._diagnostics.diagnostic_input_specs(
                target,
                kinds=("prepared",),
            )
            features = []
            seen = set()
            for component_name in component_names:
                for spec in specs:
                    if spec.component != component_name or spec.source in seen:
                        continue
                    features.append(spec.source)
                    seen.add(spec.source)
            return tuple(features)

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
                for spec in self._diagnostics.diagnostic_input_specs(
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
                for spec in self._diagnostics.diagnostic_input_specs(
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
            configured_layers = self._target_smoothing_layers(target)
            if len(configured_layers) == 1:
                return next(iter(configured_layers))
            if len(configured_layers) > 1:
                raise ValueError(
                    "Automatic smoothing-layer resolution is ambiguous for "
                    f"target {target!r}: configured layers are "
                    f"{sorted(configured_layers)}. Pass smoothing_layer explicitly."
                )
            return smoothing_layer

    def _smoothing_diagnostic_target_profile(
            self,
            target: str,
        ) -> SmoothingDiagnosticTargetProfile:
            spec = self._diagnostics.rule_mapped_diagnostic_spec(target)
            return SmoothingDiagnosticTargetProfile(
                spec=spec,
                display_target=(
                    "curve" if spec.target == "curve_positioning" else spec.target
                ),
                score_diff_col=(
                    "score_diff"
                    if spec.target == "curve_positioning"
                    else f"{spec.final_score_col}_diff"
                ),
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
            spec: RuleMappedDiagnosticSpec,
        ) -> None:
            features = self._prepared_input_sources_for_diagnostic_components(
                spec.target,
                spec.component_names,
            )
            if spec.target != "credit":
                for feature in features:
                    if feature in self.features.columns:
                        detail[feature] = self.features[feature]
                return

            seen_outputs = set()
            for feature in features:
                feature_config = self.feature_config["features"].get(feature, {})
                data_col = (
                    feature_config.get("input")
                    if feature_config.get("method") == "level"
                    else None
                )
                output_col = data_col if data_col is not None else feature
                if output_col in seen_outputs:
                    continue
                seen_outputs.add(output_col)
                if (
                    data_col is not None
                    and self.data is not None
                    and data_col in self.data.columns
                ):
                    detail[output_col] = (
                        self.data[data_col].reindex(detail.index).ffill()
                    )
                    continue
                if feature in self.features.columns:
                    detail[output_col] = self.features[feature]

    def _rule_mapped_input_smoothing_effect_detail(
            self,
            target: str,
            profile: SmoothingDiagnosticTargetProfile | None = None,
        ) -> pd.DataFrame:
            profile = profile or self._smoothing_diagnostic_target_profile(target)
            spec = profile.spec
            self._validate_input_smoothing_detail_prerequisites(profile.display_target)

            required_stance_cols = [
                spec.final_score_col,
                spec.stance_label_col,
                spec.strength_label_col,
            ]
            missing_stance_cols = [
                col
                for col in required_stance_cols
                if col is None or col not in self.exposure_stance.columns
            ]
            if missing_stance_cols:
                raise ValueError(
                    f"{spec.target} exposure stance outputs are missing: "
                    f"{missing_stance_cols}"
                )

            raw_scores = self._recalculate_component_scores_for_input_preparation_diagnostic(
                spec.target,
                apply_input_preparation=False,
                output_prefix="raw_",
            )
            detail = pd.DataFrame(index=self.features.index)
            self._add_smoothing_context_columns(detail, spec)
            detail = pd.concat(
                [
                    detail,
                    self._diagnostics.prepared_filtered_input_columns(
                        spec.target
                    ).reindex(detail.index),
                ],
                axis=1,
            )
            detail = pd.concat([detail, raw_scores], axis=1)
            for score_col in spec.score_input_cols:
                detail[f"smoothed_{score_col}"] = self.scores[score_col]

            raw_stance = (
                self._reconstruct_rule_mapped_stance_for_input_preparation_diagnostic(
                    spec.target,
                    raw_scores,
                )
            )
            raw_final_score_col = f"raw_{spec.final_score_col}"
            smoothed_final_score_col = f"smoothed_{spec.final_score_col}"
            detail[raw_final_score_col] = raw_stance["score"]
            detail[smoothed_final_score_col] = self.exposure_stance[
                spec.final_score_col
            ]
            detail[profile.score_diff_col] = (
                detail[smoothed_final_score_col]
                - detail[raw_final_score_col]
            )
            detail[f"raw_{spec.stance_label_col}"] = raw_stance["direction"]
            detail[f"raw_{spec.strength_label_col}"] = raw_stance["strength"]
            detail[f"smoothed_{spec.stance_label_col}"] = self.exposure_stance[
                spec.stance_label_col
            ]
            detail[f"smoothed_{spec.strength_label_col}"] = self.exposure_stance[
                spec.strength_label_col
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
                    {
                        **row,
                        "window_id": window_id,
                        "start": start,
                        "end": end,
                    }
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

    def _prefixed_smoothing_pair_metrics(
            self,
            prefix: str,
            raw: pd.Series,
            smoothed: pd.Series,
            *,
            tolerance: float = 1e-10,
        ) -> dict:
            return {
                f"{prefix}_{metric}": value
                for metric, value in self._smoothing_pair_comparison_metrics(
                    raw,
                    smoothed,
                    tolerance=tolerance,
                ).items()
            }

    def _rule_mapped_input_smoothing_summary_row(
            self,
            detail: pd.DataFrame,
            profile: SmoothingDiagnosticTargetProfile,
        ):
            tolerance = 1e-10
            spec = profile.spec
            raw_final_score_col = f"raw_{spec.final_score_col}"
            smoothed_final_score_col = f"smoothed_{spec.final_score_col}"
            final_metrics = self._smoothing_pair_comparison_metrics(
                detail[raw_final_score_col],
                detail[smoothed_final_score_col],
                tolerance=tolerance,
            )

            row = {
                "total_rows": int(len(detail)),
                "valid_rows": final_metrics["both_valid_count"],
            }
            for score_col in spec.score_input_cols:
                row.update(
                    self._prefixed_smoothing_pair_metrics(
                        score_col,
                        detail[f"raw_{score_col}"],
                        detail[f"smoothed_{score_col}"],
                        tolerance=tolerance,
                    )
                )
            row.update(
                {
                    f"{spec.final_score_col}_{metric}": value
                    for metric, value in final_metrics.items()
                }
            )

            change_prefix = profile.score_change_metric_prefix
            raw_score_change_count = self._count_series_changes(
                detail[raw_final_score_col]
            )
            smoothed_score_change_count = self._count_series_changes(
                detail[smoothed_final_score_col]
            )
            score_change_reduction_count = (
                raw_score_change_count - smoothed_score_change_count
            )
            raw_one_day_spike_count = self._count_one_day_spikes(
                detail[raw_final_score_col]
            )
            smoothed_one_day_spike_count = self._count_one_day_spikes(
                detail[smoothed_final_score_col]
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

    def _series_change_mask(self, series: pd.Series) -> pd.Series:
            mask = pd.Series(False, index=series.index, dtype=bool)
            valid = series.dropna()
            if len(valid) < 2:
                return mask
            valid_changes = valid.ne(valid.shift(1))
            valid_changes.iloc[0] = False
            mask.loc[valid.index] = valid_changes
            return mask

    def _count_series_changes(self, series: pd.Series) -> int:
            return int(self._series_change_mask(series).sum())

    def _one_day_spike_mask(self, series: pd.Series) -> pd.Series:
            previous = series.shift(1)
            following = series.shift(-1)
            return (
                series.notna()
                & previous.notna()
                & following.notna()
                & series.ne(previous)
                & series.ne(following)
                & previous.eq(following)
            )

    def _count_one_day_spikes(self, series: pd.Series) -> int:
            return int(self._one_day_spike_mask(series).sum())

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

            prepared_inputs = self._diagnostics.prepared_filtered_input_columns(
                target
            )
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

            curve_features_without_threshold = pd.DataFrame(
                {
                    front_end_prepared_spec.source: front_end_prepared,
                    long_end_prepared_spec.source: long_end_prepared,
                },
                index=self.features.index,
            )
            curve_features_with_threshold = pd.DataFrame(
                {
                    front_end_prepared_spec.source: front_end_filtered,
                    long_end_prepared_spec.source: long_end_filtered,
                },
                index=self.features.index,
            )
            score_without_threshold = Module1Calculator.calculate_component_score(
                curve_features_without_threshold,
                "curve_move_driver",
                curve_move_driver_config,
                self.horizons,
                apply_input_preparation=False,
                apply_score_smoothing=False,
            )
            score_with_threshold = Module1Calculator.calculate_component_score(
                curve_features_with_threshold,
                "curve_move_driver",
                curve_move_driver_config,
                self.horizons,
                apply_input_preparation=False,
                apply_score_smoothing=False,
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
                    front_end_prepared_spec.output.replace(
                        "_prepared_for_",
                        "_filtered_for_",
                        1,
                    )
                ] = front_end_filtered
            else:
                detail[front_end_filtered_spec.output] = front_end_filtered
            if long_end_filtered_spec is None:
                detail[
                    long_end_prepared_spec.output.replace(
                        "_prepared_for_",
                        "_filtered_for_",
                        1,
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
            bucket_config = curve_move_driver_config.get("buckets")
            detail["curve_move_driver_bucket_without_threshold"] = (
                Module1Calculator.classify_component_score_buckets(
                    score_without_threshold,
                    bucket_config,
                )
            )
            detail["curve_move_driver_bucket_with_threshold"] = (
                Module1Calculator.classify_component_score_buckets(
                    score_with_threshold,
                    bucket_config,
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

    def _curve_stabilization_case_detail(
            self,
            baseline_diag: pd.DataFrame,
            case_diag: pd.DataFrame,
            spec: RuleMappedDiagnosticSpec,
        ) -> pd.DataFrame:
            rule_spec = spec.rule_mapped_schema
            state_inputs = {
                state_input.name: state_input
                for state_input in rule_spec.state_inputs
            }
            curve_change = state_inputs["curve_change"]
            curve_state = state_inputs["curve_state"]
            curve_move_driver = state_inputs["curve_move_driver"]
            detail = pd.DataFrame(index=self.scores.index)

            detail["curve_change_score"] = self.scores[
                curve_change.source_score_col
            ]
            detail["curve_state_score"] = self.scores[
                curve_state.source_score_col
            ]
            detail["curve_move_driver_score"] = self.scores[
                curve_move_driver.source_score_col
            ]
            detail["raw_curve_change_bucket"] = baseline_diag[
                curve_change.stabilized_output_col
            ]
            detail["stabilized_curve_change_bucket"] = case_diag[
                curve_change.stabilized_output_col
            ]
            detail["raw_curve_state_bucket"] = baseline_diag[
                curve_state.stabilized_output_col
            ]
            detail["stabilized_curve_state_bucket"] = case_diag[
                curve_state.stabilized_output_col
            ]
            detail["raw_yield_move_driver_bucket"] = baseline_diag[
                curve_move_driver.stabilized_output_col
            ]
            detail["stabilized_yield_move_driver_bucket"] = case_diag[
                curve_move_driver.stabilized_output_col
            ]
            detail["raw_curve_positioning_rule_case"] = baseline_diag[
                rule_spec.rule_case_output_col
            ]
            detail["stabilized_curve_positioning_rule_case"] = case_diag[
                rule_spec.rule_case_output_col
            ]
            detail["raw_curve_positioning_score"] = baseline_diag[
                rule_spec.score_output_col
            ]
            detail["stabilized_curve_positioning_score"] = case_diag[
                rule_spec.score_output_col
            ]
            detail["score_diff"] = (
                detail["stabilized_curve_positioning_score"]
                - detail["raw_curve_positioning_score"]
            )

            raw_direction, raw_strength = self._stance_labels_for_score(
                detail["raw_curve_positioning_score"],
                spec.stance_config,
            )
            stabilized_direction, stabilized_strength = self._stance_labels_for_score(
                detail["stabilized_curve_positioning_score"],
                spec.stance_config,
            )
            detail["raw_curve_positioning"] = raw_direction
            detail["stabilized_curve_positioning"] = stabilized_direction
            detail["raw_curve_positioning_strength"] = raw_strength
            detail["stabilized_curve_positioning_strength"] = stabilized_strength

            detail["score_changed"] = self._series_mismatch_mask(
                detail["raw_curve_positioning_score"],
                detail["stabilized_curve_positioning_score"],
                tolerance=1e-10,
            )
            detail["direction_changed"] = self._series_mismatch_mask(
                detail["raw_curve_positioning"],
                detail["stabilized_curve_positioning"],
            )
            detail["strength_changed"] = self._series_mismatch_mask(
                detail["raw_curve_positioning_strength"],
                detail["stabilized_curve_positioning_strength"],
            )
            detail["raw_score_change_flag"] = self._series_change_mask(
                detail["raw_curve_positioning_score"]
            )
            detail["stabilized_score_change_flag"] = self._series_change_mask(
                detail["stabilized_curve_positioning_score"]
            )
            detail["raw_one_day_spike_flag"] = self._one_day_spike_mask(
                detail["raw_curve_positioning_score"]
            )
            detail["stabilized_one_day_spike_flag"] = self._one_day_spike_mask(
                detail["stabilized_curve_positioning_score"]
            )
            return detail

    def _curve_stabilization_metrics(
            self,
            detail: pd.DataFrame,
        ) -> dict:
            valid = detail[
                detail["raw_curve_positioning_score"].notna()
                & detail["stabilized_curve_positioning_score"].notna()
            ]
            valid_count = int(len(valid))
            changed_score_count = int(valid["score_changed"].sum())
            return {
                "valid_count": valid_count,
                "mean_raw_score": valid["raw_curve_positioning_score"].mean(),
                "mean_stabilized_score": valid[
                    "stabilized_curve_positioning_score"
                ].mean(),
                "mean_score_diff": valid["score_diff"].mean(),
                "mean_abs_score_diff": valid["score_diff"].abs().mean(),
                "changed_score_count": changed_score_count,
                "changed_score_ratio": self._ratio_or_na(
                    changed_score_count,
                    valid_count,
                ),
                "raw_score_change_count": int(
                    self._series_change_mask(
                        detail["raw_curve_positioning_score"]
                    ).sum()
                ),
                "stabilized_score_change_count": int(
                    self._series_change_mask(
                        detail["stabilized_curve_positioning_score"]
                    ).sum()
                ),
                "one_day_spike_count_raw": int(
                    self._one_day_spike_mask(
                        detail["raw_curve_positioning_score"]
                    ).sum()
                ),
                "one_day_spike_count_stabilized": int(
                    self._one_day_spike_mask(
                        detail["stabilized_curve_positioning_score"]
                    ).sum()
                ),
                "dominant_raw_direction": self._curve_dominant_value(
                    detail["raw_curve_positioning"]
                ),
                "dominant_stabilized_direction": self._curve_dominant_value(
                    detail["stabilized_curve_positioning"]
                ),
                "dominant_raw_strength": self._curve_dominant_value(
                    detail["raw_curve_positioning_strength"]
                ),
                "dominant_stabilized_strength": self._curve_dominant_value(
                    detail["stabilized_curve_positioning_strength"]
                ),
            }

    def _curve_stabilization_summary_row(
            self,
            case_id: str,
            detail: pd.DataFrame,
            metrics: dict,
            bucket_change_count_raw: int,
            bucket_change_count_stabilized: int,
        ) -> dict:
            valid = detail[
                detail["raw_curve_positioning_score"].notna()
                & detail["stabilized_curve_positioning_score"].notna()
            ]
            valid_count = metrics["valid_count"]
            changed_direction_count = int(valid["direction_changed"].sum())
            changed_strength_count = int(valid["strength_changed"].sum())
            raw_score_change_count = metrics["raw_score_change_count"]
            stabilized_score_change_count = metrics[
                "stabilized_score_change_count"
            ]
            raw_spikes = metrics["one_day_spike_count_raw"]
            stabilized_spikes = metrics["one_day_spike_count_stabilized"]
            return {
                "case_id": case_id,
                "total_rows": int(len(detail)),
                "valid_rows": valid_count,
                "mean_raw_score": metrics["mean_raw_score"],
                "mean_stabilized_score": metrics["mean_stabilized_score"],
                "mean_score_diff": metrics["mean_score_diff"],
                "mean_abs_score_diff": metrics["mean_abs_score_diff"],
                "max_abs_score_diff": (
                    valid["score_diff"].abs().max() if valid_count else pd.NA
                ),
                "changed_score_count": metrics["changed_score_count"],
                "changed_score_ratio": metrics["changed_score_ratio"],
                "changed_direction_count": changed_direction_count,
                "changed_direction_ratio": self._ratio_or_na(
                    changed_direction_count,
                    valid_count,
                ),
                "changed_strength_count": changed_strength_count,
                "changed_strength_ratio": self._ratio_or_na(
                    changed_strength_count,
                    valid_count,
                ),
                "raw_score_change_count": raw_score_change_count,
                "stabilized_score_change_count": stabilized_score_change_count,
                "score_change_reduction_count": (
                    raw_score_change_count - stabilized_score_change_count
                ),
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
                "dominant_raw_direction": metrics["dominant_raw_direction"],
                "dominant_stabilized_direction": metrics[
                    "dominant_stabilized_direction"
                ],
                "dominant_raw_strength": metrics["dominant_raw_strength"],
                "dominant_stabilized_strength": metrics[
                    "dominant_stabilized_strength"
                ],
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
            metrics = self._curve_stabilization_metrics(window_detail)
            return {
                "case_id": case_id,
                "window_id": window_id,
                "start": start,
                "end": end,
                "obs_count": metrics["valid_count"],
                "mean_raw_score": metrics["mean_raw_score"],
                "mean_stabilized_score": metrics["mean_stabilized_score"],
                "mean_score_diff": metrics["mean_score_diff"],
                "mean_abs_score_diff": metrics["mean_abs_score_diff"],
                "changed_score_count": metrics["changed_score_count"],
                "changed_score_ratio": metrics["changed_score_ratio"],
                "raw_score_change_count": metrics["raw_score_change_count"],
                "stabilized_score_change_count": metrics[
                    "stabilized_score_change_count"
                ],
                "one_day_spike_count_raw": metrics["one_day_spike_count_raw"],
                "one_day_spike_count_stabilized": metrics[
                    "one_day_spike_count_stabilized"
                ],
                "dominant_raw_rule_case": self._curve_dominant_value(
                    window_detail["raw_curve_positioning_rule_case"]
                ),
                "dominant_stabilized_rule_case": self._curve_dominant_value(
                    window_detail["stabilized_curve_positioning_rule_case"]
                ),
                "dominant_raw_direction": metrics["dominant_raw_direction"],
                "dominant_stabilized_direction": metrics[
                    "dominant_stabilized_direction"
                ],
                "dominant_raw_strength": metrics["dominant_raw_strength"],
                "dominant_stabilized_strength": metrics[
                    "dominant_stabilized_strength"
                ],
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
            spec = self._diagnostics.rule_mapped_diagnostic_spec(
                "curve_positioning"
            )
            rule_spec = spec.rule_mapped_schema
            cases = cases or self._default_curve_stabilization_cases()
            windows = windows or self._default_curve_stabilization_windows()
            baseline_diag = (
                Module1Calculator.build_rule_mapped_stance_score_breakdown(
                    self.scores,
                    self.component_config,
                    spec.target,
                    stance_config,
                    rule_spec,
                    stabilization_overrides=(
                        self._neutral_curve_positioning_stabilization_overrides()
                    ),
                )
            )

            summary_rows = []
            window_rows = []
            bucket_rows = []
            score_distribution_rows = []
            detail_by_case = {}

            for case_id, case_config in cases.items():
                case_diag = (
                    Module1Calculator.build_rule_mapped_stance_score_breakdown(
                        self.scores,
                        self.component_config,
                        spec.target,
                        stance_config,
                        rule_spec,
                        stabilization_overrides=case_config,
                    )
                )
                detail = self._curve_stabilization_case_detail(
                    baseline_diag,
                    case_diag,
                    spec,
                )
                detail_by_case[case_id] = detail
                raw_bucket_change_count = 0
                stabilized_bucket_change_count = 0
                for bucket_type, raw_col, stabilized_col in [
                    (
                        "curve_change",
                        "raw_curve_change_bucket",
                        "stabilized_curve_change_bucket",
                    ),
                    (
                        "curve_state",
                        "raw_curve_state_bucket",
                        "stabilized_curve_state_bucket",
                    ),
                    (
                        "yield_move_driver",
                        "raw_yield_move_driver_bucket",
                        "stabilized_yield_move_driver_bucket",
                    ),
                ]:
                    raw_count = int(
                        self._series_change_mask(detail[raw_col]).sum()
                    )
                    stabilized_count = int(
                        self._series_change_mask(detail[stabilized_col]).sum()
                    )
                    raw_bucket_change_count += raw_count
                    stabilized_bucket_change_count += stabilized_count
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
                metrics = self._curve_stabilization_metrics(detail)
                summary_rows.append(
                    self._curve_stabilization_summary_row(
                        case_id,
                        detail,
                        metrics,
                        raw_bucket_change_count,
                        stabilized_bucket_change_count,
                    )
                )
                for window_id, window in windows.items():
                    window_rows.append(
                        self._curve_stabilization_window_row(
                            case_id,
                            window_id,
                            window,
                            detail,
                        )
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

            result = {
                "summary": pd.DataFrame(summary_rows),
                "window_summary": pd.DataFrame(window_rows),
                "detail_by_case": detail_by_case,
                "bucket_transition_summary": pd.DataFrame(bucket_rows),
                "score_distribution": pd.DataFrame(score_distribution_rows),
            }
            if include_diagnostics:
                result["diagnostics_by_case"] = {
                    case_id: detail.copy(deep=True)
                    for case_id, detail in detail_by_case.items()
                }
            return result

    def compare_credit_stance_persistence_cases(
            self,
            cases: dict | None = None,
            hysteresis_buffer: float = 0.05,
            windows: dict | None = None,
            include_diagnostics: bool = True,
        ) -> dict:
            """
            Compare credit stance behavior across case-local persistence settings.

            This diagnostic recalculates exposure stance only for coherent local
            Module1Result scenarios. It does not recalculate component scores or
            mutate the baseline result or Sensitivity state.
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

            diagnostics_by_case = {}
            window_metrics_rows = []
            shock_rows = []
            recovery_rows = []
            tight_rows = []
            late_rows = []
            full_rows = []
            case_records = {}

            for case_id, settings in cases.items():
                case_module1_config = copy.deepcopy(self.result.module1_config)
                case_credit_config = case_module1_config["exposure_stances"][
                    "credit"
                ]
                case_stabilization_config = {
                    "credit_spread_change": {
                        "hysteresis_buffer": float(hysteresis_buffer),
                        "min_state_persistence": settings["credit_spread_change"],
                    },
                    "credit_spread_state": {
                        "hysteresis_buffer": float(hysteresis_buffer),
                        "min_state_persistence": settings["credit_spread_state"],
                    },
                }
                case_credit_config["rule_mapped"][
                    "state_stabilization"
                ] = case_stabilization_config
                if "state_stabilization" in case_credit_config:
                    case_credit_config["state_stabilization"] = copy.deepcopy(
                        case_stabilization_config
                    )

                case_exposure_stance_config = {
                    "stance_label_rules": case_module1_config[
                        "stance_label_rules"
                    ],
                    "exposure_stances": case_module1_config["exposure_stances"],
                }
                (
                    case_stance_scores,
                    case_exposure_stance,
                ) = Module1Calculator.calculate_exposure_stance_outputs(
                    self.scores,
                    self.component_config,
                    case_exposure_stance_config,
                )
                case_result = replace(
                    self.result,
                    stance_scores=case_stance_scores,
                    exposure_stance=case_exposure_stance,
                    module1_config=case_module1_config,
                )
                diag = Module1Diagnostics(case_result).trace_stance_score(
                    "credit",
                    include_raw_input=True,
                    include_labels=False,
                )
                if "baa10y_change" in diag.columns and "baa10y" in diag.columns:
                    diagnostic_columns = list(diag.columns)
                    diagnostic_columns.remove("baa10y_change")
                    diagnostic_columns.insert(
                        diagnostic_columns.index("baa10y"),
                        "baa10y_change",
                    )
                    diag = diag.loc[:, diagnostic_columns]

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
                shock_row = {
                    "case_id": case_id,
                    "first_credit_negative_date": first_negative_date(shock),
                }

                recovery = window_slice(diag, "post_shock_recovery")
                recovery_score = recovery["credit_stance_score"].dropna()
                recovery_pair, recovery_pair_ratio = dominant_pair(recovery)
                recovery_row = {
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
                tight_row = {
                    "case_id": case_id,
                    "tight_state_count": tight_state_count,
                    "tight_state_ratio": self._ratio_or_na(
                        tight_state_count,
                        tight_obs,
                    ),
                    "tight_pair_count": tight_pair_count,
                    "tight_pair_ratio": self._ratio_or_na(
                        tight_pair_count,
                        tight_obs,
                    ),
                    "credit_stance_score_mean": (
                        tight_score.mean() if tight_obs else pd.NA
                    ),
                }

                late = window_slice(diag, "late_2022_volatility")
                late_score = late["credit_stance_score"].dropna()
                late_moves = late_score.diff().abs().dropna()
                late_row = {
                    "case_id": case_id,
                    "max_abs_daily_score_move": (
                        late_moves.max() if not late_moves.empty else pd.NA
                    ),
                    "large_move_gt_0_5_count": int((late_moves > 0.5).sum()),
                    "large_move_gt_1_0_count": int((late_moves > 1.0).sum()),
                }

                full_obs = int(diag["credit_stance_score"].notna().sum())
                full_changed_pair_count = int(
                    diag["state_stabilization_changed_pair"].sum()
                )
                full_row = {
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

                shock_rows.append(shock_row)
                recovery_rows.append(recovery_row)
                tight_rows.append(tight_row)
                late_rows.append(late_row)
                full_rows.append(full_row)
                case_records[case_id] = {
                    "settings": settings,
                    "shock": shock_row,
                    "recovery": recovery_row,
                    "tight": tight_row,
                    "late": late_row,
                    "full": full_row,
                }

            base_record = case_records.get("base_p1_p1")
            base_negative_date = (
                pd.NaT
                if base_record is None
                else base_record["shock"]["first_credit_negative_date"]
            )
            summary_rows = []
            for case_id, record in case_records.items():
                settings = record["settings"]
                shock_row = record["shock"]
                recovery_row = record["recovery"]
                tight_row = record["tight"]
                late_row = record["late"]
                full_row = record["full"]
                negative_date = shock_row["first_credit_negative_date"]
                shock_row["delay_days_vs_base"] = (
                    pd.NA
                    if pd.isna(negative_date) or pd.isna(base_negative_date)
                    else (negative_date - base_negative_date).days
                )
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

            window_metrics_df = pd.DataFrame(window_metrics_rows)
            shock_detection_df = pd.DataFrame(shock_rows)
            recovery_behavior_df = pd.DataFrame(recovery_rows)
            tight_spread_behavior_df = pd.DataFrame(tight_rows)
            late_volatility_df = pd.DataFrame(late_rows)
            full_period_stabilization_df = pd.DataFrame(full_rows)

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
