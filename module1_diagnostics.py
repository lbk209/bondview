import copy
from dataclasses import dataclass, replace
from collections.abc import Mapping

import pandas as pd

from module1_analysis import Module1Analysis, TargetContextResult
from module1_calculator import Module1Calculator, Module1Result


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
class DiagnosticInputSpec:
    component: str
    source: str
    kind: str
    output: str
    role: str | None = None


class Module1Diagnostics:
    """Tracing and rule-diagnostic workflows for completed Module 1 results."""

    _CALCULATOR_STATE_FIELDS = (
        "data", "features", "scores", "labels", "stance_scores",
        "exposure_stance", "module1_config", "feature_config",
        "component_config", "exposure_stance_config", "horizons",
        "default_horizons", "horizon_overrides", "module1_config_validation",
    )
    _CALCULATOR_HELPERS = {
        "_prepare_component_input_series",
        "_resolve_rule_mapped_stance_schema",
        "_build_weighted_stance_score_breakdown",
        "_build_rule_mapped_stance_score_breakdown",
    }

    def __init__(
        self,
        result: Module1Result,
        historical_context: dict | None = None,
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
        return self.analysis._resolve_target(target, level, allow_group=allow_group)

    def _resolve_historical_event_window(self, context_id=None, start=None, end=None):
        if context_id is None:
            return start, end
        if self.historical_context is None:
            raise ValueError(
                "Run load_historical_context() before using context_id-based diagnostics."
            )
        events = self.historical_context.get("events")
        if events is None or events.empty:
            raise ValueError("historical_context events are not loaded.")
        matched_events = events[events["context_id"] == context_id]
        if matched_events.empty:
            raise ValueError(f"Unknown historical context_id: {context_id}")
        event = matched_events.iloc[0]
        if start is None:
            start = event["start"]
        if end is None:
            end = event["end"]
        return start, end

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
        start, end = self._resolve_historical_event_window(
            context_id=context_id,
            start=start,
            end=end,
        )
        result = self.analysis.get_target_context(
            target=target,
            level=level,
            dependency_level=dependency_level,
            include_labels=include_labels,
            include_strength=include_strength,
            start=start,
            end=end,
            ffill_inputs=ffill_inputs,
        )
        if context_id is not None:
            request = result.request.copy()
            request["context_id"] = context_id
            result = replace(result, request=request, context_id=context_id)
        return result

    def _count_series_changes(self, series: pd.Series) -> int:
        valid = series.dropna()
        if valid.empty:
            return 0
        return int(valid.ne(valid.shift(1)).iloc[1:].sum())

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
