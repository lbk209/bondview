import copy
from dataclasses import dataclass
from collections.abc import Mapping

import pandas as pd

from module1_analysis import Module1Analysis, TargetContextResult
from module1_calculator import (
    Module1Calculator,
    Module1Result,
    _RuleMappedStanceSpec,
)


@dataclass(frozen=True)
class RuleMappedDiagnosticSpec:
    target: str
    stance_config: dict
    function: str
    rule_mapped_schema: _RuleMappedStanceSpec
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

    def __init__(self, result: Module1Result):
        self.result = result
        self.analysis = Module1Analysis(result)
        self.features = self._copy_result_value(result.features)
        self.scores = self._copy_result_value(result.scores)
        self.labels = self._copy_result_value(result.labels)
        self.exposure_stance = self._copy_result_value(result.exposure_stance)
        self.feature_config = self._copy_result_value(result.feature_config)
        self.component_config = self._copy_result_value(result.component_config)
        self.exposure_stance_config = self._copy_result_value(result.exposure_stance_config)
        self.horizons = self._copy_result_value(result.horizons)

    @staticmethod
    def _copy_result_value(value):
        if value is None:
            return None
        if isinstance(value, pd.DataFrame):
            return value.copy(deep=True)
        if isinstance(value, pd.Series):
            return value.copy(deep=True)
        return copy.deepcopy(value)

    def _resolve_target(self, target: str, level: str | None, allow_group: bool = False):
        return self.analysis.resolve_target(target, level, allow_group=allow_group)

    def get_target_context(
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
        return self.analysis.get_target_context(
            target=target,
            level=level,
            dependency_level=dependency_level,
            include_labels=include_labels,
            include_strength=include_strength,
            start=start,
            end=end,
            ffill_inputs=ffill_inputs,
        )

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
        component_names = []
        for item in stance_config.get("inputs", []):
            if not isinstance(item, dict):
                continue
            score_output = item.get("component")
            component_name = component_by_score_output.get(score_output)
            if component_name is not None and component_name not in component_names:
                component_names.append(component_name)
        return tuple(component_names)

    def _score_input_features_for_diagnostic_component(
        self,
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

    def _diagnostic_input_specs(
        self,
        target: str | None = None,
        *,
        kinds: tuple[str, ...] = ("prepared", "filtered"),
    ) -> tuple[DiagnosticInputSpec, ...]:
        if self.component_config is None:
            raise ValueError("Run load_module1_config() before prepared-input diagnostics.")

        components = self.component_config["components"]
        target_component_names = self._diagnostic_component_names_for_target(target)
        component_names = (
            tuple(components)
            if target_component_names is None
            else target_component_names
        )
        specs = []
        requested_kinds = set(kinds)
        for component_name in component_names:
            component = components[component_name]
            diagnostics = component.get("diagnostics") or {}
            prepared_inputs = diagnostics.get("prepared_inputs") or {}
            if prepared_inputs.get("enabled") is not True:
                continue

            score_config = component.get("score", {})
            sources = self._score_input_features_for_diagnostic_component(
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
        specs_by_key = {}
        for spec in specs:
            key = (spec.component, spec.source, spec.kind)
            specs_by_key.setdefault(key, []).append(spec)
        prepared = pd.DataFrame(index=self.features.index)

        prepared_specs = [spec for spec in specs if spec.kind == "prepared"]
        for spec in prepared_specs:
            if spec.source not in self.features.columns:
                continue
            score_config = components.get(spec.component, {}).get("score", {})
            prepared[spec.output] = Module1Calculator._prepare_component_input_series(
                self.features[spec.source],
                score_config.get("input_preparation"),
                self.horizons,
            )

        for spec in (spec for spec in specs if spec.kind == "filtered"):
            source_key = (spec.component, spec.source, "prepared")
            source_matches = specs_by_key.get(source_key, [])
            if len(source_matches) != 1:
                raise ValueError(
                    "Expected exactly one prepared/filtered diagnostic input spec for "
                    f"{target} {spec.component} {spec.source} prepared, "
                    f"found {len(source_matches)}."
                )
            source_spec = source_matches[0]
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

        diagnostics = Module1Calculator._build_weighted_stance_score_breakdown(
            self.scores,
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

        if start is not None:
            diagnostics = diagnostics.loc[diagnostics.index >= pd.to_datetime(start)]
        if end is not None:
            diagnostics = diagnostics.loc[diagnostics.index <= pd.to_datetime(end)]

        return diagnostics

    def _resolve_rule_mapped_diagnostic_spec(
        self,
        target: str,
        target_info,
    ) -> RuleMappedDiagnosticSpec:
        stance_name = target_info.canonical_target
        stance_config = target_info.config
        function = stance_config.get("function") if stance_config else None
        if not isinstance(stance_config, Mapping) or "rule_mapped" not in stance_config:
            raise ValueError(
                f"Unsupported rule-mapped stance diagnostic target {target}: "
                f"{function}. Schema-backed rule_mapped config is required."
            )
        rule_mapped_schema = Module1Calculator._resolve_rule_mapped_stance_schema(
            stance_name,
            stance_config,
            self.component_config,
        )
        adjustment = rule_mapped_schema.adjustment

        return RuleMappedDiagnosticSpec(
            target=stance_name,
            stance_config=stance_config,
            function=function,
            rule_mapped_schema=rule_mapped_schema,
            score_input_cols=tuple(
                state_input.source_score_col
                for state_input in rule_mapped_schema.state_inputs
            ),
            raw_state_cols=tuple(
                state_input.raw_output_col
                for state_input in rule_mapped_schema.state_inputs
            ),
            stabilized_state_cols=tuple(
                state_input.stabilized_output_col
                for state_input in rule_mapped_schema.state_inputs
            ),
            rule_case_col=rule_mapped_schema.rule_case_output_col,
            final_score_col=target_info.score_col or stance_config["score_output"],
            stance_label_col=target_info.label_col or stance_config["stance_output"],
            strength_label_col=(
                target_info.strength_col or stance_config["strength_output"]
            ),
            component_names=tuple(
                state_input.diagnostic_component or state_input.component_name
                for state_input in rule_mapped_schema.state_inputs
            ),
            stabilization_change_cols=tuple(
                state_input.stabilization_changed_output_col
                for state_input in rule_mapped_schema.state_inputs
            ),
            stabilization_change_any_col=(
                rule_mapped_schema.stabilization_changed_any_output_col
            ),
            base_rule_score_col=rule_mapped_schema.base_rule_score_output_col,
            adjustment_col=(
                adjustment.adjustment_output_col
                if adjustment is not None
                else None
            ),
            adjusted_score_col=rule_mapped_schema.adjusted_score_output_col,
            rule_metadata_cols=(
                adjustment.metadata_output_cols
                if adjustment is not None
                else ()
            ),
        )

    def _trace_rule_mapped_stance_score(
        self,
        spec: RuleMappedDiagnosticSpec,
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

        diagnostics = Module1Calculator._build_rule_mapped_stance_score_breakdown(
            self.scores,
            self.component_config,
            spec.target,
            spec.stance_config,
            spec.rule_mapped_schema,
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
        """Build trace context in explicit metadata order or the generic default.

        The default group order is features, raw inputs, then prepared/filtered
        inputs. Score inputs default to resolved rule-mapped declaration order.
        """
        declared_prepared_specs = self._diagnostic_input_specs(
            spec.target,
            kinds=("prepared",),
        )
        if declared_prepared_specs:
            trace_context = (
                (spec.stance_config.get("diagnostics") or {}).get("trace_context")
                or {}
            )
            ordered_score_inputs = trace_context.get(
                "score_input_order",
                spec.score_input_cols,
            )
            component_by_score_output = self._component_by_score_output()
            ordered_sources = []
            for score_input in ordered_score_inputs:
                component_name = component_by_score_output.get(score_input)
                for item in declared_prepared_specs:
                    if (
                        item.component == component_name
                        and item.source not in ordered_sources
                    ):
                        ordered_sources.append(item.source)

            returned_features = ctx.returned_columns["features"]
            feature_definitions = self.feature_config["features"]
            feature_cols = []
            visited_features = set()

            def add_feature_with_dependencies(feature_name: str) -> None:
                if feature_name in visited_features:
                    return
                visited_features.add(feature_name)

                definition = feature_definitions.get(feature_name, {})
                method = definition.get("method")
                dependencies = []
                if method in {"change", "pct_change", "level"}:
                    dependencies.append(definition.get("input"))
                elif method == "spread":
                    dependencies.extend(definition.get("inputs") or [])

                for dependency in dependencies:
                    if dependency in returned_features:
                        add_feature_with_dependencies(dependency)

                if (
                    feature_name in returned_features
                    and method != "level"
                    and feature_name not in feature_cols
                ):
                    feature_cols.append(feature_name)

            for source in ordered_sources:
                add_feature_with_dependencies(source)

            returned_raw_inputs = ctx.returned_columns["raw_inputs"]
            feature_dependency_map = ctx.resolved_path["feature_to_raw_inputs"]
            raw_input_cols = []
            for source in ordered_sources:
                for raw_input in feature_dependency_map.get(source, ()):
                    if (
                        raw_input in returned_raw_inputs
                        and raw_input not in raw_input_cols
                    ):
                        raw_input_cols.append(raw_input)

            context_groups = {
                "raw_inputs": ctx.data[raw_input_cols].reindex(index),
                "features": ctx.data[feature_cols].reindex(index),
                "prepared_filtered_inputs": self._prepared_filtered_input_columns(
                    spec.target
                ).reindex(index),
            }
            group_order = trace_context.get(
                "group_order",
                ("features", "raw_inputs", "prepared_filtered_inputs"),
            )
            return [
                context_groups[group_name]
                for group_name in group_order
                if context_groups[group_name].shape[1] > 0
            ]

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
        if target is None or str(target).strip() == "":
            raise ValueError("target must be a non-empty stance identifier.")

        allowed_views = {"state", "transitions", "stability"}
        if view not in allowed_views:
            allowed = ", ".join(
                f'"{allowed_view}"' for allowed_view in sorted(allowed_views)
            )
            raise ValueError(
                f"Unsupported rule-mapped stance diagnostic view {view!r}. "
                f"Allowed values are: {allowed}."
            )

        target_info = self._resolve_target(target, level="stance")
        spec = self._resolve_rule_mapped_diagnostic_spec(target, target_info)
        if view != "state":
            include_scores = False
            include_raw_states = True
            include_stabilized_states = True
            include_rule_case = True
            include_labels = True

        diagnostics = self._trace_rule_mapped_stance_score(
            spec,
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

    def trace_stance_score(
        self,
        target: str,
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
                start=start,
                end=end,
                include_raw_input=include_raw_input,
                include_labels=include_labels,
            )

        if "rule_mapped" in stance_config:
            spec = self._resolve_rule_mapped_diagnostic_spec(target, target_info)
            return self._trace_rule_mapped_stance_score(
                spec,
                start=start,
                end=end,
                include_raw_input=include_raw_input,
                include_labels=include_labels,
            )

        raise ValueError(
            f"Unsupported stance trace function for {stance_name}: {function}"
        )
