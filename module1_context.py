from dataclasses import dataclass, field

import pandas as pd


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
            "config": self.config,
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
