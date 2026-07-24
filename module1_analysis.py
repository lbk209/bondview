import copy
from dataclasses import dataclass, field

import pandas as pd
import matplotlib.pyplot as plt

from module1_calculator import Module1Result


@dataclass(frozen=True)
class TargetResolution:
    requested_target: str
    normalized_target: str
    level: str | None
    kind: str
    canonical_target: str | None
    score_col: str | None
    label_col: str | None
    strength_col: str | None
    config: dict | None
    related_score_cols: tuple[str, ...] = ()
    related_label_cols: tuple[str, ...] = ()
    related_strength_cols: tuple[str, ...] = ()
    related_component_score_cols: tuple[str, ...] = ()
    related_targets: tuple[tuple[str, str], ...] = ()
    supported: bool = True
    has_stance_score: bool = False
    source_layer: str | None = None
    source_table: str | None = None
    available_output_fields: tuple[str, ...] = ()

    def to_target_info(self) -> dict:
        return {
            "level": self.level,
            "target": self.requested_target,
            "canonical_target": self.canonical_target,
            "source_layer": self.source_layer,
            "source_table": self.source_table,
            "score_col": self.score_col,
            "label_col": self.label_col,
            "strength_col": self.strength_col,
            "config": copy.deepcopy(self.config),
            "available_output_fields": self.available_output_fields,
        }


@dataclass(frozen=True)
class TargetDependency:
    resolution: TargetResolution
    target_members: tuple[tuple[str, str], ...] = ()
    component_score_cols: tuple[str, ...] = ()
    component_label_cols: tuple[str, ...] = ()
    feature_cols: tuple[str, ...] = ()
    raw_input_cols: tuple[str, ...] = ()
    feature_dependency_map: dict[str, tuple[str, ...]] = field(default_factory=dict)
    supported: bool = True


@dataclass(frozen=True)
class TargetContextResult:
    resolution: dict
    request: dict
    resolved_path: dict
    returned_columns: dict
    data: pd.DataFrame
    source_layer_mapping: dict[str, str] = field(default_factory=dict)
    source_column_mapping: dict[str, str] = field(default_factory=dict)
    start: object = None
    end: object = None
    context_id: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class TargetCompareDataset:
    data: pd.DataFrame
    target_columns: tuple[str, ...] = ()
    comparison_columns: tuple[str, ...] = ()
    label_columns: tuple[str, ...] = ()
    strength_columns: tuple[str, ...] = ()
    returned_columns: dict = field(default_factory=dict)
    resolved_path: dict = field(default_factory=dict)
    resolution: dict = field(default_factory=dict)
    compare: str = "auto"
    effective_compare: str = "auto"
    target_level: str | None = None
    source_layer_mapping: dict[str, str] = field(default_factory=dict)
    source_column_mapping: dict[str, str] = field(default_factory=dict)
    start: object = None
    end: object = None
    context_id: str | None = None
    metadata: dict = field(default_factory=dict)


def _first_valid_dates_by_column(table: pd.DataFrame | None) -> pd.Series | None:
    if table is None:
        return None

    return table.apply(lambda col: col.first_valid_index())


def _latest_valid_dates_by_column(table: pd.DataFrame | None) -> pd.Series | None:
    if table is None:
        return None

    return table.apply(lambda col: col.last_valid_index())


def _label_distributions(table: pd.DataFrame | None) -> dict | None:
    if table is None:
        return None

    distributions = {}

    for col in table.columns:
        counts = table[col].dropna().value_counts()
        if not counts.empty:
            distributions[col] = counts

    return distributions


class Module1Analysis:
    def __init__(self, result: Module1Result):
        self.result = result

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
            if self.result.module1_config is None:
                raise ValueError("Run load_module1_config() before historical review.")

            for component_name, component_config in self.result.module1_config[
                "components"
            ].items():
                score_col = component_config.get("score", {}).get("output")
                label_col = component_config.get("label", {}).get("output")
                canonical = ("component", component_name)

                for alias in [component_name, score_col, label_col]:
                    if alias is not None:
                        aliases[self._normalize_review_label(alias)] = canonical

        if normalized_level in {None, "stance"}:
            if self.result.module1_config is None:
                raise ValueError("Run load_module1_config() before historical review.")

            for stance_name, stance_config in self.result.module1_config[
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
        if self.result.module1_config is None:
            raise ValueError("Run load_module1_config() before historical review.")

        target_groups = (
            self.result.module1_config
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
            stance_config = self.result.module1_config["exposure_stances"][
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

        component_config = self.result.module1_config["components"][canonical_target]
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
            if self.result.data is None:
                raise ValueError("Run load_data() before resolving raw inputs.")
            matches = {
                self._normalize_review_label(col): col
                for col in self.result.data.columns
            }
            canonical = matches.get(normalized_target)
            if canonical is None:
                raise ValueError(f"Unknown raw_input target: {target}")
            return TargetResolution(
                requested_target=target,
                normalized_target=normalized_target,
                level="raw_input",
                kind="target",
                canonical_target=canonical,
                score_col=canonical,
                label_col=None,
                strength_col=None,
                config=None,
                related_score_cols=(canonical,),
                related_targets=(("raw_input", canonical),),
                source_layer="raw_input",
                source_table="data",
                available_output_fields=(canonical,),
            )

        if normalized_level == "feature":
            if self.result.module1_config is None:
                raise ValueError("Run load_module1_config() before resolving features.")
            matches = {
                self._normalize_review_label(col): col
                for col in self.result.module1_config["features"]
            }
            canonical = matches.get(normalized_target)
            if canonical is None:
                raise ValueError(f"Unknown feature target: {target}")
            feature_def = self.result.module1_config["features"][canonical]
            return TargetResolution(
                requested_target=target,
                normalized_target=normalized_target,
                level="feature",
                kind="target",
                canonical_target=canonical,
                score_col=canonical,
                label_col=None,
                strength_col=None,
                config=feature_def,
                related_score_cols=(canonical,),
                related_targets=(("feature", canonical),),
                source_layer="feature",
                source_table="features",
                available_output_fields=(canonical,),
            )

        return self.resolve_target(target, normalized_level)

    def resolve_target(
        self,
        target: str,
        level: str | None = None,
        *,
        allow_group: bool = False,
    ) -> TargetResolution:
        """
        Resolve component or stance targets, aliases, and configured target groups.

        A group may resolve to a single member or, when ``allow_group`` is true,
        retain its configured component/stance member ordering in the returned
        resolution metadata. Raw-input and feature context resolution is handled
        separately by ``_resolve_target_for_context()``.
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

            resolved = tuple(dict.fromkeys(resolved))
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
        component_name, component_config = self._component_for_score_output(
            component_score
        )
        score_config = component_config.get("score", {})
        function = score_config.get("function")

        if function == "single_feature_score":
            feature = score_config.get("input")
            return [] if feature is None else [feature]

        if function in {"weighted_feature_score", "curve_move_driver_score"}:
            return [
                item["feature"]
                for item in score_config.get("inputs", [])
                if "feature" in item
            ]

        raise ValueError(
            f"Unsupported score function for {component_name}: {function}"
        )

    def _component_for_score_output(
        self,
        component_score: str,
    ) -> tuple[str, dict]:
        if self.result.module1_config is None:
            raise ValueError("Run load_module1_config() first.")

        for component_name, component_config in self.result.module1_config[
            "components"
        ].items():
            if component_config.get("score", {}).get("output") == component_score:
                return component_name, component_config

        raise ValueError(
            f"Component score not found in component_config: {component_score}"
        )

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

        if self.result.data is not None and feature_name in self.result.data.columns:
            return (feature_name,), {}

        if self.result.module1_config is None:
            raise ValueError("Run load_module1_config() first.")

        feature_defs = self.result.module1_config["features"]

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

    def _component_label_columns_for_scores(
        self,
        component_score_cols: list[str],
    ) -> list[str]:
        label_cols = []
        for component_score_col in component_score_cols:
            _, component_config = self._component_for_score_output(
                component_score_col
            )
            label_output = component_config.get("label", {}).get("output")
            if label_output is not None:
                label_cols.append(label_output)

        return label_cols

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
                raw_input_cols=tuple(dict.fromkeys(raw_input_cols)),
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
                raw_input_cols=tuple(dict.fromkeys(raw_input_cols)),
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
            raw_input_cols=tuple(dict.fromkeys(raw_input_cols)),
            feature_dependency_map=feature_dependency_map,
            supported=resolution.supported,
        )

    def _required_output_table(
        self,
        table_name: str,
        *,
        purpose: str,
    ) -> pd.DataFrame:
        table = getattr(self.result, table_name)
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

    def inspect_module1_results(self, n=10) -> dict:
        """
        Inspect completed Module 1 result outputs for sanity checking.
        """
        features = self.result.features
        scores = self.result.scores
        labels = self.result.labels
        exposure_stance = self.result.exposure_stance
    
        tables = {
            "features": features,
            "scores": scores,
            "labels": labels,
            "exposure_stance": exposure_stance,
        }
    
        combined_parts = [
            table
            for table in [scores, labels, exposure_stance]
            if table is not None
        ]
        recent_combined_snapshot = (
            None if not combined_parts else pd.concat(combined_parts, axis=1).tail(n)
        )
    
        exposure_label_cols = None
        if exposure_stance is not None:
            exposure_label_cols = [
                col
                for col in exposure_stance.columns
                if not pd.api.types.is_numeric_dtype(exposure_stance[col])
            ]
    
        latest_complete_exposure_stance_date = None
        if exposure_stance is not None:
            complete_exposure = exposure_stance.dropna(how="any")
            if not complete_exposure.empty:
                latest_complete_exposure_stance_date = complete_exposure.index.max()
    
        review = {
            "recent_combined_snapshot": recent_combined_snapshot,
            "recent_scores": None if scores is None else scores.tail(n),
            "recent_labels": None if labels is None else labels.tail(n),
            "recent_exposure_stance": (
                None if exposure_stance is None else exposure_stance.tail(n)
            ),
            "non_null_counts": {
                name: None if table is None else table.notna().sum()
                for name, table in tables.items()
            },
            "non_null_ratio": {
                name: None if table is None else table.notna().mean()
                for name, table in tables.items()
            },
            "first_valid_dates": {
                name: _first_valid_dates_by_column(table)
                for name, table in tables.items()
            },
            "latest_valid_dates": {
                name: _latest_valid_dates_by_column(table)
                for name, table in tables.items()
            },
            "latest_dates": {
                name: (
                    None
                    if table is None or table.dropna(how="all").empty
                    else table.dropna(how="all").index.max()
                )
                for name, table in tables.items()
            },
            "latest_complete_exposure_stance_date": latest_complete_exposure_stance_date,
            "component_label_distributions": _label_distributions(labels),
            "exposure_stance_label_distributions": (
                None
                if exposure_stance is None or not exposure_label_cols
                else _label_distributions(exposure_stance[exposure_label_cols])
            ),
        }
    
        return review
    

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
        Retrieve target outputs and lower-level dependencies for explicit dates.

        Module1Analysis is result-only and does not resolve historical
        context_id windows.
        """
        if context_id is not None:
            raise ValueError(
                "Module1Analysis.get_target_context(...) accepts explicit "
                "start/end only; resolve context_id before calling it."
            )

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
            raw_frame = data.ffill() if ffill_inputs else data
            raw_frame = self._window_series_or_frame(raw_frame, start, end)
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
        resolved_path_metadata = {
            "target_members": dependency.target_members,
            "component_scores": dependency.component_score_cols,
            "component_labels": dependency.component_label_cols,
            "features": dependency.feature_cols,
            "raw_inputs": dependency.raw_input_cols,
            "feature_to_raw_inputs": dependency.feature_dependency_map,
            "supported": dependency.supported,
            "target_level": resolution.level,
        }
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
        Build a consumer-neutral target comparison dataset from result outputs.
        """
        if context_id is not None:
            raise ValueError(
                "Module1Analysis.build_target_comparison_dataset(...) accepts "
                "explicit start/end only; resolve context_id before calling it."
            )

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
        Return lower-level raw-input dependencies for a feature, component,
        or stance target.

        Raw-input targets are unsupported because they have no lower-level
        dependencies.
        """
        normalized_level = self._normalize_target_level(level)
        if normalized_level == "raw_input":
            raise ValueError(
                "raw_inputs_for_target() requires a feature, component, or stance "
                "target; raw_input targets have no lower-level dependencies."
            )

        retrieval = self.get_target_context(
            target,
            normalized_level,
            dependency_level="raw_inputs",
            include_labels=False,
            include_strength=False,
        )
        return list(retrieval.returned_columns["raw_inputs"])

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

    def plot_target_comparison_dataset(
        self,
        dataset: TargetCompareDataset,
        *,
        target_label: str | None = None,
        normalize="auto",
        return_data: bool = False,
        ax=None,
        figsize=(12, 6),
        title: str | None = None,
    ):
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

        if title is None and target_label is not None:
            title = (
                f"{target_label} ({dataset.target_level}) vs "
                f"{dataset.effective_compare}"
                + (
                    f" [{dataset.context_id}]"
                    if dataset.context_id is not None
                    else ""
                )
            )

        rendered = self._render_compare_dataset_on_axes(
            ax_target,
            ax_comparison,
            dataset,
            normalize=normalize_resolved,
            title=title,
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

        Module1Analysis accepts explicit start/end only. Resolve historical
        context_id windows before calling this method.
        """
        if context_id is not None:
            raise ValueError(
                "Module1Analysis.plot_target_comparison(...) accepts explicit "
                "start/end only; resolve context_id before calling it."
            )
        dataset = self.build_target_comparison_dataset(
            target=target,
            level=level,
            compare=compare,
            start=start,
            end=end,
            include_labels=include_labels,
            include_strength=include_strength,
            ffill_inputs=ffill_inputs,
        )
        return self.plot_target_comparison_dataset(
            dataset,
            target_label=target,
            normalize=normalize,
            return_data=return_data,
            ax=ax,
            figsize=figsize,
        )
