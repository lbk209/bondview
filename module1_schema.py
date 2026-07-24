import math
from itertools import product
from numbers import Real
from collections.abc import Mapping

import pandas as pd

from module1_calculator import Module1Calculator


def _is_finite_number(value) -> bool:
    if isinstance(value, bool) or not isinstance(value, Real):
        return False
    if isinstance(value, int):
        return True
    try:
        return math.isfinite(value)
    except (TypeError, ValueError, OverflowError):
        return False


def validate_module1_config(config: dict) -> dict:
    """
    Validate the Module 1 config schema before assigning it to object state.
    """
    issues = []
    checked = []

    def add_issue(section, name, field, issue, detail):
        issues.append(
            {
                "section": section,
                "name": name,
                "field": field,
                "issue": issue,
                "detail": detail,
            }
        )

    def add_checked(section, name, field, value=None, status="checked"):
        checked.append(
            {
                "section": section,
                "name": name,
                "field": field,
                "value": value,
                "status": status,
            }
        )

    def non_empty_string(value):
        return isinstance(value, str) and value.strip() != ""

    def validate_string_members(
        section,
        name,
        field,
        values,
        known_members=None,
        unknown_issue="unknown",
    ):
        if not isinstance(values, list):
            add_issue(
                section,
                name,
                field,
                "invalid",
                f"{field} must be a list when present.",
            )
            return

        seen = set()
        for index, member in enumerate(values):
            member_field = f"{field}[{index}]"
            if not non_empty_string(member):
                add_issue(
                    section,
                    name,
                    member_field,
                    "invalid",
                    f"{field} members must be non-empty strings.",
                )
                continue
            if member in seen:
                add_issue(
                    section,
                    name,
                    member_field,
                    "duplicate",
                    f"{field} contains duplicate member: {member}.",
                )
            seen.add(member)
            if known_members is not None and member not in known_members:
                add_issue(
                    section,
                    name,
                    member_field,
                    unknown_issue,
                    f"{field} member is not defined: {member}.",
                )

    # Layer A — generic YAML structure
    def validate_top_level_structure(config):
        """Validate required sections, metadata references, and horizon structure."""
        required_top_level = {
            "horizons",
            "features",
            "components",
            "stance_label_rules",
            "exposure_stances",
        }
        for key in sorted(required_top_level):
            add_checked("top_level", key, "required_key", key in config)
            if key not in config:
                add_issue(
                    "top_level",
                    key,
                    "required_key",
                    "missing",
                    "Required top-level key is missing.",
                )

        horizons = config.get("horizons")
        features = config.get("features")
        components = config.get("components")
        stance_label_rules = config.get("stance_label_rules")
        exposure_stances = config.get("exposure_stances")
        model_metadata = config.get("model_metadata")

        if model_metadata is not None:
            add_checked("model_metadata", None, "model_metadata")
            if not isinstance(model_metadata, dict):
                add_issue(
                    "model_metadata",
                    None,
                    "model_metadata",
                    "invalid",
                    "model_metadata must be a mapping when present.",
                )
                model_metadata = {}
            else:
                target_groups = model_metadata.get("target_groups")
                if target_groups is not None:
                    add_checked(
                        "model_metadata",
                        "target_groups",
                        "target_groups",
                    )
                    if not isinstance(target_groups, dict):
                        add_issue(
                            "model_metadata",
                            "target_groups",
                            "target_groups",
                            "invalid",
                            "model_metadata.target_groups must be a mapping when present.",
                        )
                    else:
                        known_components = (
                            set(components) if isinstance(components, dict) else None
                        )
                        known_stances = (
                            set(exposure_stances)
                            if isinstance(exposure_stances, dict)
                            else None
                        )
                        allowed_group_keys = {"component", "stance"}
                        for group_name, group in target_groups.items():
                            if not non_empty_string(group_name):
                                add_issue(
                                    "model_metadata",
                                    group_name,
                                    "target_groups",
                                    "invalid",
                                    "model_metadata.target_groups group names must be non-empty strings.",
                                )
                                continue
                            add_checked(
                                "model_metadata.target_groups",
                                group_name,
                                "definition",
                            )
                            if not isinstance(group, dict):
                                add_issue(
                                    "model_metadata.target_groups",
                                    group_name,
                                    "definition",
                                    "invalid",
                                    "Target group definition must be a mapping.",
                                )
                                continue

                            for key in sorted(set(group) - allowed_group_keys):
                                add_issue(
                                    "model_metadata.target_groups",
                                    group_name,
                                    key,
                                    "unknown",
                                    "Target group keys must be only component or stance.",
                                )

                            for level_name, known_members in [
                                ("component", known_components),
                                ("stance", known_stances),
                            ]:
                                if level_name in group:
                                    validate_string_members(
                                        "model_metadata.target_groups",
                                        group_name,
                                        level_name,
                                        group.get(level_name),
                                        known_members=known_members,
                                        unknown_issue=f"unknown_{level_name}",
                                    )

                diagnostics = model_metadata.get("diagnostics")
                if diagnostics is not None:
                    add_checked(
                        "model_metadata",
                        "diagnostics",
                        "diagnostics",
                    )
                    if not isinstance(diagnostics, dict):
                        add_issue(
                            "model_metadata",
                            "diagnostics",
                            "diagnostics",
                            "invalid",
                            "model_metadata.diagnostics must be a mapping when present.",
                        )

        if not isinstance(horizons, dict) or not horizons:
            add_issue(
                "horizons",
                None,
                "horizons",
                "missing" if horizons is None else "invalid",
                "horizons must be a non-empty mapping.",
            )
            horizons = {}
        else:
            for horizon_name, horizon_value in horizons.items():
                add_checked("horizons", horizon_name, "value", horizon_value)
                if (
                    isinstance(horizon_value, bool)
                    or not isinstance(horizon_value, int)
                    or horizon_value <= 0
                ):
                    add_issue(
                        "horizons",
                        horizon_name,
                        "value",
                        "invalid",
                        "Horizon values must be positive integers and not bool.",
                    )

        return (
            horizons,
            features,
            components,
            stance_label_rules,
            exposure_stances,
        )

    (
        horizons,
        features,
        components,
        stance_label_rules,
        exposure_stances,
    ) = validate_top_level_structure(config)

    def validate_horizon_reference(section, name, field, horizon_key):
        if horizon_key is None or pd.isna(horizon_key):
            return
        if horizon_key not in horizons:
            add_issue(
                section,
                name,
                field,
                "unknown_horizon",
                f"Horizon reference is not defined in config['horizons']: {horizon_key}.",
            )

    # Layer A section orchestration with Layer B feature-method dispatch.
    def validate_features_section(features):
        """Apply Layer A feature grammar and Layer B calculator capabilities once."""
        known_feature_methods = {"change", "pct_change", "spread", "level"}
        known_frequencies = {"daily", "monthly"}
        if not isinstance(features, dict) or not features:
            add_issue(
                "features",
                None,
                "features",
                "invalid",
                "features must be a non-empty mapping.",
            )
            features = {}

        for feature_name, feature in features.items():
            add_checked("features", feature_name, "feature")
            if not isinstance(feature, dict):
                add_issue(
                    "features",
                    feature_name,
                    "definition",
                    "invalid",
                    "Feature definition must be a mapping.",
                )
                continue

            method = feature.get("method")
            if method not in known_feature_methods:
                add_issue(
                    "features",
                    feature_name,
                    "method",
                    "unsupported",
                    f"Supported methods: {sorted(known_feature_methods)}.",
                )

            if method in {"change", "pct_change", "level"}:
                if "input" not in feature or pd.isna(feature.get("input")):
                    add_issue(
                        "features",
                        feature_name,
                        "input",
                        "missing",
                        f"{method} feature requires input.",
                    )

            if method in {"change", "pct_change"}:
                if "horizon" not in feature or pd.isna(feature.get("horizon")):
                    add_issue(
                        "features",
                        feature_name,
                        "horizon",
                        "missing",
                        f"{method} feature requires horizon.",
                    )
                else:
                    validate_horizon_reference(
                        "features",
                        feature_name,
                        "horizon",
                        feature.get("horizon"),
                    )

            if method == "spread":
                inputs = feature.get("inputs")
                if not isinstance(inputs, list) or len(inputs) != 2:
                    add_issue(
                        "features",
                        feature_name,
                        "inputs",
                        "invalid",
                        "spread feature requires inputs as a list of exactly two items.",
                    )

            frequency = feature.get("frequency")
            if frequency is not None and frequency not in known_frequencies:
                add_issue(
                    "features",
                    feature_name,
                    "frequency",
                    "unsupported",
                    f"Expected one of {sorted(known_frequencies)} when present.",
                )

        return features

    features = validate_features_section(features)

    component_score_outputs = {}
    component_label_outputs = {}
    component_output_names = set()
    known_score_functions = {
        "single_feature_score",
        "weighted_feature_score",
        "curve_move_driver_score",
    }
    known_normalizations = {None, "rolling_zscore", "rolling_std"}
    current_state_components = {"credit_spread_state", "curve_state"}

    curve_bucket_names = {}

    # Layer B — calculator capability contract
    def validate_score_sign_and_clip_contract(component_name, score):
        """Validate score transforms that the calculator reads directly."""
        function = score.get("function")
        state_transform = score.get("state_transform")
        if "sign" in score and function in known_score_functions:
            sign = score.get("sign")
            supports_sign = function == "single_feature_score" or (
                function == "weighted_feature_score"
                and state_transform == "fixed_anchor"
            )
            if not supports_sign:
                add_issue(
                    "components",
                    component_name,
                    "score.sign",
                    "unsupported",
                    "score.sign is not supported for this score form.",
                )
            elif sign not in {"direct", "inverse"}:
                add_issue(
                    "components",
                    component_name,
                    "score.sign",
                    "unsupported",
                    "score.sign must be direct or inverse when present.",
                )

        if "clip" not in score:
            return
        clip = score.get("clip")
        if not isinstance(clip, dict):
            add_issue(
                "components",
                component_name,
                "score.clip",
                "invalid",
                "score.clip must be a mapping when present.",
            )
            return

        allowed_clip_fields = {"min", "max"}
        for field_name in clip:
            if field_name not in allowed_clip_fields:
                add_issue(
                    "components",
                    component_name,
                    f"score.clip.{field_name}",
                    "unknown",
                    "Unknown score.clip field.",
                )

        for field_name in ("min", "max"):
            if field_name in clip and not _is_finite_number(clip.get(field_name)):
                add_issue(
                    "components",
                    component_name,
                    f"score.clip.{field_name}",
                    "invalid",
                    "score.clip bounds must be finite numeric values and not bool.",
                )

        lower = clip.get("min")
        upper = clip.get("max")
        if (
            "min" in clip
            and "max" in clip
            and _is_finite_number(lower)
            and _is_finite_number(upper)
            and lower > upper
        ):
            add_issue(
                "components",
                component_name,
                "score.clip",
                "invalid_order",
                "score.clip must satisfy min <= max.",
            )

    def validate_anchor_block(component_name, anchors, field):
        """Validate the fixed-anchor shape consumed by current-state scoring."""
        if anchors is None:
            add_issue(
                "components",
                component_name,
                field,
                "missing",
                "fixed_anchor scoring requires anchors.",
            )
            return
        if not isinstance(anchors, dict):
            add_issue(
                "components",
                component_name,
                field,
                "invalid",
                "fixed_anchor scoring anchors must be a mapping.",
            )
            return

        required_anchors = {"negative", "neutral", "positive"}
        values = {}
        for anchor_name in sorted(required_anchors):
            anchor_value = anchors.get(anchor_name)
            anchor_field = f"{field}.{anchor_name}"
            if anchor_name not in anchors:
                add_issue(
                    "components",
                    component_name,
                    anchor_field,
                    "missing",
                    "fixed_anchor scoring requires negative, neutral, and positive anchors.",
                )
                continue
            if not _is_finite_number(anchor_value):
                add_issue(
                    "components",
                    component_name,
                    anchor_field,
                    "invalid",
                    "anchor values must be numeric.",
                )
                continue
            values[anchor_name] = anchor_value

        if (
            required_anchors.issubset(values)
            and not values["negative"] < values["neutral"] < values["positive"]
        ):
            add_issue(
                "components",
                component_name,
                field,
                "invalid_order",
                "anchors must satisfy negative < neutral < positive.",
            )

    def bucket_names_from_score(score):
        buckets = score.get("buckets")
        if isinstance(buckets, dict):
            return set(buckets)
        return set()

    def validate_threshold_label_mode(component_name, label):
        """Validate the calculator-supported threshold label form."""
        thresholds = label.get("thresholds")
        if not isinstance(thresholds, dict):
            add_issue(
                "components",
                component_name,
                "label.thresholds",
                "missing" if thresholds is None else "invalid",
                "threshold label mode requires label.thresholds as a mapping.",
            )
            thresholds = {}

        positive_threshold = thresholds.get("positive")
        negative_threshold = thresholds.get("negative")
        if not _is_finite_number(positive_threshold):
            add_issue(
                "components",
                component_name,
                "label.thresholds.positive",
                "invalid",
                "positive threshold must be numeric.",
            )
        if not _is_finite_number(negative_threshold):
            add_issue(
                "components",
                component_name,
                "label.thresholds.negative",
                "invalid",
                "negative threshold must be numeric.",
            )
        if (
            _is_finite_number(positive_threshold)
            and _is_finite_number(negative_threshold)
            and positive_threshold <= negative_threshold
        ):
            add_issue(
                "components",
                component_name,
                "label.thresholds",
                "invalid_order",
                "positive threshold must be greater than negative threshold.",
            )

        labels = label.get("labels")
        if not isinstance(labels, dict):
            add_issue(
                "components",
                component_name,
                "label.labels",
                "missing" if labels is None else "invalid",
                "label.labels must be a mapping.",
            )
            labels = {}

        required_labels = {"positive", "neutral", "negative"}
        label_values = []
        for key in sorted(required_labels):
            value = labels.get(key)
            if not non_empty_string(value):
                add_issue(
                    "components",
                    component_name,
                    f"label.labels.{key}",
                    "invalid",
                    "Label value must be a non-empty string.",
                )
            else:
                label_values.append(value)
        if len(label_values) != len(set(label_values)):
            add_issue(
                "components",
                component_name,
                "label.labels",
                "duplicate_values",
                "Threshold label values must be unique within one component.",
            )

    def validate_bucket_label_mode(component_name, score, label):
        """Validate the calculator-supported bucket label form."""
        buckets = score.get("buckets")
        bucket_labels = label.get("bucket_labels")
        labels = label.get("labels")
        if not isinstance(buckets, dict) or not buckets:
            add_issue(
                "components",
                component_name,
                "score.buckets",
                "missing" if buckets is None else "invalid",
                "bucket label mode requires score.buckets as a non-empty mapping.",
            )
            buckets = {}
        if not isinstance(bucket_labels, dict):
            add_issue(
                "components",
                component_name,
                "label.bucket_labels",
                "missing" if bucket_labels is None else "invalid",
                "bucket label mode requires label.bucket_labels as a mapping.",
            )
            bucket_labels = {}
        if not isinstance(labels, dict):
            add_issue(
                "components",
                component_name,
                "label.labels",
                "missing" if labels is None else "invalid",
                "label.labels must be a mapping.",
            )
            labels = {}

        bucket_names = set(buckets)
        mapped_buckets = set(bucket_labels)
        for bucket_name in sorted(bucket_names - mapped_buckets):
            add_issue(
                "components",
                component_name,
                f"label.bucket_labels.{bucket_name}",
                "missing",
                "bucket label mode must map every configured score bucket.",
            )
        for bucket_name in sorted(mapped_buckets - bucket_names):
            add_issue(
                "components",
                component_name,
                f"label.bucket_labels.{bucket_name}",
                "unknown",
                "label.bucket_labels contains an unknown score bucket.",
            )
        for bucket_name, label_key in bucket_labels.items():
            if label_key not in labels:
                add_issue(
                    "components",
                    component_name,
                    f"label.bucket_labels.{bucket_name}",
                    "unknown_label_key",
                    "label.bucket_labels values must refer to label.labels keys.",
                )
                continue
            label_value = labels.get(label_key)
            if not non_empty_string(label_value):
                add_issue(
                    "components",
                    component_name,
                    f"label.labels.{label_key}",
                    "invalid",
                    "Bucket label values must be non-empty strings.",
                )

    # Layer C — intentional Module 1 named-model invariants
    def validate_curve_change_model_invariants(score):
        """Validate the active curve-change categories used by Module 1."""
        component_name = "curve_change"
        buckets = score.get("buckets")
        if not isinstance(buckets, dict):
            add_issue(
                "components",
                component_name,
                "score.buckets",
                "missing" if buckets is None else "invalid",
                "curve_change score.buckets must be a mapping.",
            )
            return
        curve_bucket_names[component_name] = set(buckets)
        required = {"steepening", "stable", "flattening"}
        for bucket_name in sorted(required - set(buckets)):
            add_issue(
                "components",
                component_name,
                f"score.buckets.{bucket_name}",
                "missing",
                "curve_change buckets must define steepening, stable, and flattening.",
            )
        steepening = buckets.get("steepening", {})
        flattening = buckets.get("flattening", {})
        stable = buckets.get("stable", {})
        steepening_min = steepening.get("min") if isinstance(steepening, dict) else None
        flattening_max = flattening.get("max") if isinstance(flattening, dict) else None
        if not _is_finite_number(steepening_min):
            add_issue(
                "components",
                component_name,
                "score.buckets.steepening.min",
                "invalid",
                "curve_change steepening.min must be numeric and not bool.",
            )
        if not _is_finite_number(flattening_max):
            add_issue(
                "components",
                component_name,
                "score.buckets.flattening.max",
                "invalid",
                "curve_change flattening.max must be numeric and not bool.",
            )
        if not isinstance(stable, dict) or stable.get("default") is not True:
            add_issue(
                "components",
                component_name,
                "score.buckets.stable.default",
                "invalid",
                "curve_change stable.default must be true.",
            )
        if (
            _is_finite_number(steepening_min)
            and _is_finite_number(flattening_max)
            and flattening_max >= steepening_min
        ):
            add_issue(
                "components",
                component_name,
                "score.buckets",
                "invalid_order",
                "curve_change flattening.max must be less than steepening.min.",
            )

    def validate_curve_state_model_invariants(score):
        """Validate the active curve-state categories used by Module 1."""
        component_name = "curve_state"
        buckets = score.get("buckets")
        if not isinstance(buckets, dict):
            add_issue(
                "components",
                component_name,
                "score.buckets",
                "missing" if buckets is None else "invalid",
                "curve_state score.buckets must be a mapping.",
            )
            return
        curve_bucket_names[component_name] = set(buckets)
        required = {"inverted", "flat", "normal", "steep"}
        for bucket_name in sorted(required - set(buckets)):
            add_issue(
                "components",
                component_name,
                f"score.buckets.{bucket_name}",
                "missing",
                "curve_state buckets must define inverted, flat, normal, and steep.",
            )

        values = {}
        specs = {
            "inverted": ["max"],
            "flat": ["min_exclusive", "max_exclusive"],
            "normal": ["min", "max_exclusive"],
            "steep": ["min"],
        }
        for bucket_name, fields in specs.items():
            rule = buckets.get(bucket_name)
            if not isinstance(rule, dict):
                add_issue(
                    "components",
                    component_name,
                    f"score.buckets.{bucket_name}",
                    "missing" if rule is None else "invalid",
                    "curve_state bucket definition must be a mapping.",
                )
                continue
            values[bucket_name] = {}
            for field in fields:
                value = rule.get(field)
                if not _is_finite_number(value):
                    add_issue(
                        "components",
                        component_name,
                        f"score.buckets.{bucket_name}.{field}",
                        "invalid",
                        "curve_state bucket boundary must be numeric and not bool.",
                    )
                else:
                    values[bucket_name][field] = value

        if all(
            key in values
            for key in ["inverted", "flat", "normal", "steep"]
        ):
            inverted_max = values.get("inverted", {}).get("max")
            flat_min = values.get("flat", {}).get("min_exclusive")
            flat_max = values.get("flat", {}).get("max_exclusive")
            normal_min = values.get("normal", {}).get("min")
            normal_max = values.get("normal", {}).get("max_exclusive")
            steep_min = values.get("steep", {}).get("min")
            if all(
                _is_finite_number(value)
                for value in [
                    inverted_max,
                    flat_min,
                    flat_max,
                    normal_min,
                    normal_max,
                    steep_min,
                ]
            ) and not (
                inverted_max == flat_min
                and flat_min < flat_max
                and flat_max == normal_min
                and normal_min < normal_max
                and normal_max == steep_min
            ):
                add_issue(
                    "components",
                    component_name,
                    "score.buckets",
                    "invalid_order",
                    "curve_state buckets must form contiguous ordered intervals.",
                )

    def validate_curve_move_driver_model_invariants(score):
        """Validate move-driver categories and exact scores used by calculator logic."""
        component_name = "curve_move_driver"
        buckets = score.get("buckets")
        if not isinstance(buckets, dict):
            add_issue(
                "components",
                component_name,
                "score.buckets",
                "missing" if buckets is None else "invalid",
                "curve_move_driver score.buckets must be a mapping.",
            )
            return
        curve_bucket_names[component_name] = set(buckets)
        required = {
            "bull_parallel",
            "bear_parallel",
            "front_end_down_long_end_up",
            "front_end_up_long_end_down",
            "mixed_or_unclear",
        }
        for bucket_name in sorted(required - set(buckets)):
            add_issue(
                "components",
                component_name,
                f"score.buckets.{bucket_name}",
                "missing",
                "curve_move_driver buckets must define every driver category.",
            )

        score_values = []
        for bucket_name, rule in buckets.items():
            if not isinstance(rule, dict):
                add_issue(
                    "components",
                    component_name,
                    f"score.buckets.{bucket_name}",
                    "invalid",
                    "curve_move_driver bucket definition must be a mapping.",
                )
                continue
            score_value = rule.get("score")
            if rule.get("default") is True and "score" in rule and not _is_finite_number(score_value):
                add_issue(
                    "components",
                    component_name,
                    f"score.buckets.{bucket_name}.score",
                    "invalid",
                    "curve_move_driver default bucket score must be numeric and not bool when present.",
                )
            if rule.get("default") is True:
                continue
            if not _is_finite_number(score_value):
                add_issue(
                    "components",
                    component_name,
                    f"score.buckets.{bucket_name}.score",
                    "invalid",
                    "curve_move_driver non-default bucket score must be numeric and not bool.",
                )
            else:
                score_values.append(score_value)
        mixed = buckets.get("mixed_or_unclear", {})
        if not isinstance(mixed, dict) or mixed.get("default") is not True:
            add_issue(
                "components",
                component_name,
                "score.buckets.mixed_or_unclear.default",
                "invalid",
                "curve_move_driver mixed_or_unclear.default must be true.",
            )
        if len(score_values) != len(set(score_values)):
            add_issue(
                "components",
                component_name,
                "score.buckets",
                "duplicate_score_values",
                "curve_move_driver non-default bucket score values must be unique.",
            )

    def configured_score_features(score):
        feature_names = []
        input_name = score.get("input")
        if non_empty_string(input_name):
            feature_names.append(input_name)
        inputs = score.get("inputs")
        if isinstance(inputs, list):
            for item in inputs:
                if not isinstance(item, dict):
                    continue
                feature_name = item.get("feature")
                if non_empty_string(feature_name):
                    feature_names.append(feature_name)
        return set(feature_names)

    def validate_component_diagnostics(component_name, component, score):
        """Validate supported prepared-input diagnostic declarations."""
        diagnostics = component.get("diagnostics")
        if diagnostics is None:
            return
        if not isinstance(diagnostics, dict):
            add_issue(
                "components",
                component_name,
                "diagnostics",
                "invalid",
                "diagnostics must be a mapping when present.",
            )
            return

        allowed_diagnostics_fields = {"prepared_inputs"}
        for field in diagnostics:
            if field not in allowed_diagnostics_fields:
                add_issue(
                    "components",
                    component_name,
                    f"diagnostics.{field}",
                    "unknown",
                    "Unknown diagnostics field.",
                )

        prepared_inputs = diagnostics.get("prepared_inputs")
        if prepared_inputs is None:
            return
        if not isinstance(prepared_inputs, dict):
            add_issue(
                "components",
                component_name,
                "diagnostics.prepared_inputs",
                "invalid",
                "diagnostics.prepared_inputs must be a mapping when present.",
            )
            return

        allowed_prepared_input_fields = {"enabled", "input_roles"}
        for field in prepared_inputs:
            if field not in allowed_prepared_input_fields:
                add_issue(
                    "components",
                    component_name,
                    f"diagnostics.prepared_inputs.{field}",
                    "unknown",
                    "Unknown prepared_inputs field.",
                )

        enabled = prepared_inputs.get("enabled")
        if not isinstance(enabled, bool):
            add_issue(
                "components",
                component_name,
                "diagnostics.prepared_inputs.enabled",
                "invalid",
                "diagnostics.prepared_inputs.enabled must be bool.",
            )

        input_roles = prepared_inputs.get("input_roles")
        if input_roles is None:
            return
        if not isinstance(input_roles, dict):
            add_issue(
                "components",
                component_name,
                "diagnostics.prepared_inputs.input_roles",
                "invalid",
                "diagnostics.prepared_inputs.input_roles must be a mapping.",
            )
            return

        score_features = configured_score_features(score)
        role_values = []
        for source, role in input_roles.items():
            if not non_empty_string(source):
                add_issue(
                    "components",
                    component_name,
                    "diagnostics.prepared_inputs.input_roles",
                    "invalid_source",
                    "Prepared-input role source must be a non-empty string.",
                )
                continue
            if source not in score_features:
                add_issue(
                    "components",
                    component_name,
                    f"diagnostics.prepared_inputs.input_roles.{source}",
                    "unknown_score_feature",
                    "Prepared-input role source must refer to a configured score input feature.",
                )
            if not non_empty_string(role):
                add_issue(
                    "components",
                    component_name,
                    f"diagnostics.prepared_inputs.input_roles.{source}",
                    "invalid_role",
                    "Prepared-input role must be a non-empty string.",
                )
            else:
                role_values.append(role)

        if len(role_values) != len(set(role_values)):
            add_issue(
                "components",
                component_name,
                "diagnostics.prepared_inputs.input_roles",
                "duplicate_roles",
                "Prepared-input roles must be unique within one component.",
            )

    # Layer A section orchestration; Layer B/C helpers above own specific rules.
    def validate_components_section(components):
        """Validate component structure, calculator forms, and named invariants in one pass."""
        if not isinstance(components, dict) or not components:
            add_issue(
                "components",
                None,
                "components",
                "invalid",
                "components must be a non-empty mapping.",
            )
            components = {}

        for component_name, component in components.items():
            add_checked("components", component_name, "component")

            # Layer A: generic component mapping and output relationships.
            if not isinstance(component, dict):
                add_issue(
                    "components",
                    component_name,
                    "definition",
                    "invalid",
                    "Component definition must be a mapping.",
                )
                continue

            score = component.get("score")
            label = component.get("label")
            if not isinstance(score, dict):
                add_issue(
                    "components",
                    component_name,
                    "score",
                    "missing",
                    "Component must have a score section.",
                )
                score = {}
            if not isinstance(label, dict):
                add_issue(
                    "components",
                    component_name,
                    "label",
                    "missing",
                    "Component must have a label section.",
                )
                label = {}
            validate_component_diagnostics(component_name, component, score)

            score_output = score.get("output")
            if not non_empty_string(score_output):
                add_issue(
                    "components",
                    component_name,
                    "score.output",
                    "missing",
                    "score.output must be a non-empty string.",
                )
            elif score_output in component_score_outputs:
                add_issue(
                    "components",
                    component_name,
                    "score.output",
                    "duplicate",
                    f"Also used by {component_score_outputs[score_output]}.",
                )
            else:
                component_score_outputs[score_output] = component_name
                component_output_names.add(score_output)

            function = score.get("function")

            # Layer C: invariants tied to the named current-state components.
            is_current_state_component = component_name in current_state_components
            state_transform = score.get("state_transform")
            if state_transform is not None and state_transform != "fixed_anchor":
                add_issue(
                    "components",
                    component_name,
                    "score.state_transform",
                    "unsupported",
                    "state_transform must be fixed_anchor when present.",
                )
            if is_current_state_component and state_transform != "fixed_anchor":
                add_issue(
                    "components",
                    component_name,
                    "score.state_transform",
                    "missing",
                    "current-state components must use state_transform: fixed_anchor.",
                )
            if not is_current_state_component and state_transform is not None:
                add_issue(
                    "components",
                    component_name,
                    "score.state_transform",
                    "unsupported_for_component",
                    "state_transform is only supported for current-state components.",
                )

            # Layer B: calculator-supported score, preparation, and transform forms.
            if function not in known_score_functions:
                add_issue(
                    "components",
                    component_name,
                    "score.function",
                    "unsupported",
                    f"Supported score functions: {sorted(known_score_functions)}.",
                )

            validate_score_sign_and_clip_contract(component_name, score)

            input_preparation = score.get("input_preparation")
            supported_input_preparation_components = {
                "curve_change",
                "curve_state",
                "curve_move_driver",
                "credit_spread_change",
                "credit_spread_state",
            }
            supports_input_preparation = (
                component_name in supported_input_preparation_components
                or function == "curve_move_driver_score"
            )
            if input_preparation is not None:
                field_prefix = "score.input_preparation"
                if not supports_input_preparation:
                    add_issue(
                        "components",
                        component_name,
                        field_prefix,
                        "unsupported_for_component",
                        "input_preparation is only supported for selected curve and credit components.",
                    )
                elif not isinstance(input_preparation, dict):
                    add_issue(
                        "components",
                        component_name,
                        field_prefix,
                        "invalid",
                        "input_preparation must be a mapping when present.",
                    )
                else:
                    allowed_input_preparation_fields = {
                        "smoothing",
                        "min_abs_value",
                    }
                    for field in input_preparation:
                        if field not in allowed_input_preparation_fields:
                            add_issue(
                                "components",
                                component_name,
                                f"{field_prefix}.{field}",
                                "unknown",
                                "Unknown input_preparation field.",
                            )
                    smoothing_key = input_preparation.get("smoothing")
                    if smoothing_key is not None:
                        validate_horizon_reference(
                            "components",
                            component_name,
                            f"{field_prefix}.smoothing",
                            smoothing_key,
                        )
                    min_abs_value = input_preparation.get("min_abs_value")
                    if min_abs_value is not None:
                        if function != "curve_move_driver_score":
                            add_issue(
                                "components",
                                component_name,
                                f"{field_prefix}.min_abs_value",
                                "unsupported_for_component",
                                "input_preparation.min_abs_value is only supported for curve_move_driver_score.",
                            )
                        elif (
                            not _is_finite_number(min_abs_value)
                            or min_abs_value < 0
                        ):
                            add_issue(
                                "components",
                                component_name,
                                f"{field_prefix}.min_abs_value",
                                "invalid",
                                "input_preparation.min_abs_value must be numeric, not bool, and >= 0.",
                            )

            if function == "single_feature_score":
                feature_name = score.get("input")
                if feature_name not in features:
                    add_issue(
                        "components",
                        component_name,
                        "score.input",
                        "unknown_feature",
                        f"Feature is not defined: {feature_name}.",
                    )
                if component_name == "credit_spread_state":
                    validate_anchor_block(
                        component_name,
                        score.get("anchors"),
                        "score.anchors",
                    )

            if function == "weighted_feature_score":
                inputs = score.get("inputs")
                requires_weighted_inputs = state_transform != "fixed_anchor"
                requires_input_anchors = state_transform == "fixed_anchor"
                if not isinstance(inputs, list) or not inputs:
                    add_issue(
                        "components",
                        component_name,
                        "score.inputs",
                        "invalid",
                        "weighted_feature_score requires a non-empty inputs list.",
                    )
                    inputs = []
                has_explicit_weight = any(
                    isinstance(item, dict) and "weight" in item for item in inputs
                )
                requires_fixed_anchor_weights = (
                    state_transform == "fixed_anchor"
                    and (len(inputs) > 1 or has_explicit_weight)
                )
                for idx, item in enumerate(inputs):
                    if not isinstance(item, dict):
                        add_issue(
                            "components",
                            component_name,
                            f"score.inputs[{idx}]",
                            "invalid",
                            "Weighted input item must be a mapping.",
                        )
                        continue
                    feature_name = item.get("feature")
                    if feature_name not in features:
                        add_issue(
                            "components",
                            component_name,
                            f"score.inputs[{idx}].feature",
                            "unknown_feature",
                            f"Feature is not defined: {feature_name}.",
                        )
                    if requires_weighted_inputs or requires_fixed_anchor_weights:
                        if "weight" not in item:
                            add_issue(
                                "components",
                                component_name,
                                f"score.inputs[{idx}].weight",
                                "missing",
                                "weighted_feature_score input weight is required.",
                            )
                        elif not _is_finite_number(item.get("weight")) or pd.isna(
                            item.get("weight")
                        ):
                            add_issue(
                                "components",
                                component_name,
                                f"score.inputs[{idx}].weight",
                                "invalid",
                                "weighted_feature_score input weight must be numeric and not bool.",
                            )
                    if requires_input_anchors:
                        validate_anchor_block(
                            component_name,
                            item.get("anchors"),
                            f"score.inputs[{idx}].anchors",
                        )

            if function == "curve_move_driver_score":
                inputs = score.get("inputs")
                if not isinstance(inputs, list) or len(inputs) != 2:
                    add_issue(
                        "components",
                        component_name,
                        "score.inputs",
                        "invalid",
                        "curve_move_driver_score requires exactly two feature inputs.",
                    )
                    inputs = []
                for idx, item in enumerate(inputs):
                    if not isinstance(item, dict):
                        add_issue(
                            "components",
                            component_name,
                            f"score.inputs[{idx}]",
                            "invalid",
                            "Curve move driver input item must be a mapping.",
                        )
                        continue
                    feature_name = item.get("feature")
                    if feature_name not in features:
                        add_issue(
                            "components",
                            component_name,
                            f"score.inputs[{idx}].feature",
                            "unknown_feature",
                            f"Feature is not defined: {feature_name}.",
                        )
            normalization = score.get("normalization")
            if normalization not in known_normalizations:
                add_issue(
                    "components",
                    component_name,
                    "score.normalization",
                    "unsupported",
                    "normalization must be None, rolling_zscore, or rolling_std.",
                )
            normalization_horizon = score.get("normalization_horizon")
            if normalization_horizon is not None:
                validate_horizon_reference(
                    "components",
                    component_name,
                    "score.normalization_horizon",
                    normalization_horizon,
                )
            elif normalization is not None:
                validate_horizon_reference(
                    "components",
                    component_name,
                    "score.normalization_horizon",
                    "normalization",
                )
            if is_current_state_component and normalization is not None:
                add_issue(
                    "components",
                    component_name,
                    "score.normalization",
                    "unsupported_for_current_state",
                    "current-state components use fixed-anchor scoring and must not use rolling normalization.",
                )
            if (
                function == "curve_move_driver_score"
                and normalization is not None
            ):
                add_issue(
                    "components",
                    component_name,
                    "score.normalization",
                    "unsupported_for_curve_move_driver",
                    "curve_move_driver_score is categorical and must not use normalization.",
                )

            smoothing = score.get("smoothing")
            if smoothing is not None:
                validate_horizon_reference(
                    "components",
                    component_name,
                    "score.smoothing",
                    smoothing,
                )
            if is_current_state_component and smoothing is not None:
                add_issue(
                    "components",
                    component_name,
                    "score.smoothing",
                    "unsupported_for_current_state",
                    "current-state components use fixed-anchor scoring and must not use rolling score smoothing.",
                )
            if (
                function == "curve_move_driver_score"
                and smoothing is not None
            ):
                add_issue(
                    "components",
                    component_name,
                    "score.smoothing",
                    "unsupported_for_curve_move_driver",
                    "curve_move_driver_score is categorical and must not use smoothing.",
                )

            label_output = label.get("output")

            # Layer A output registration followed by Layer B label-mode dispatch.
            if not non_empty_string(label_output):
                add_issue(
                    "components",
                    component_name,
                    "label.output",
                    "missing",
                    "label.output must be a non-empty string.",
                )
            elif label_output in component_label_outputs:
                add_issue(
                    "components",
                    component_name,
                    "label.output",
                    "duplicate",
                    f"Also used by {component_label_outputs[label_output]}.",
                )
            else:
                component_label_outputs[label_output] = component_name
                component_output_names.add(label_output)

            source = label.get("source")
            if source != score_output:
                add_issue(
                    "components",
                    component_name,
                    "label.source",
                    "unknown_score_output",
                    f"label.source must refer to this component score output: {score_output}.",
                )

            label_mode = label.get("mode")
            if label_mode not in {"threshold", "bucket"}:
                add_issue(
                    "components",
                    component_name,
                    "label.mode",
                    "missing" if label_mode is None else "unsupported",
                    "label.mode must be threshold or bucket.",
                )
            elif label_mode == "threshold":
                validate_threshold_label_mode(component_name, label)
            elif label_mode == "bucket":
                validate_bucket_label_mode(component_name, score, label)

            # Layer C: active Curve category and score invariants.
            if component_name == "curve_change":
                validate_curve_change_model_invariants(score)
            elif component_name == "curve_state":
                validate_curve_state_model_invariants(score)
            elif component_name == "curve_move_driver":
                validate_curve_move_driver_model_invariants(score)

        return components

    components = validate_components_section(components)

    # Layer A stance-label structure with Layer B threshold semantics.
    def validate_stance_label_rules_section(stance_label_rules):
        """Validate generic stance-label structure and supported threshold semantics."""
        if not isinstance(stance_label_rules, dict):
            add_issue(
                "stance_label_rules",
                None,
                "stance_label_rules",
                "invalid",
                "stance_label_rules must be a mapping.",
            )
            stance_label_rules = {}

        direction_thresholds = stance_label_rules.get("direction_thresholds")
        if not isinstance(direction_thresholds, dict):
            add_issue(
                "stance_label_rules",
                None,
                "direction_thresholds",
                "missing",
                "direction_thresholds must be a mapping.",
            )
            direction_thresholds = {}

        positive_min = direction_thresholds.get("positive_min")
        negative_max = direction_thresholds.get("negative_max")
        if not _is_finite_number(positive_min):
            add_issue(
                "stance_label_rules",
                None,
                "direction_thresholds.positive_min",
                "invalid",
                "positive_min must be numeric.",
            )
        if not _is_finite_number(negative_max):
            add_issue(
                "stance_label_rules",
                None,
                "direction_thresholds.negative_max",
                "invalid",
                "negative_max must be numeric.",
            )
        if _is_finite_number(positive_min) and _is_finite_number(negative_max) and positive_min <= negative_max:
            add_issue(
                "stance_label_rules",
                None,
                "direction_thresholds",
                "invalid_order",
                "positive_min must be greater than negative_max.",
            )

        strength_thresholds = stance_label_rules.get("strength_thresholds")
        if not isinstance(strength_thresholds, dict):
            add_issue(
                "stance_label_rules",
                None,
                "strength_thresholds",
                "missing",
                "strength_thresholds must be a mapping.",
            )
            strength_thresholds = {}

        weak_max_abs = strength_thresholds.get("weak_max_abs")
        moderate_max_abs = strength_thresholds.get("moderate_max_abs")
        strong_min_abs = strength_thresholds.get("strong_min_abs")
        for key, value in [
            ("weak_max_abs", weak_max_abs),
            ("moderate_max_abs", moderate_max_abs),
            ("strong_min_abs", strong_min_abs),
        ]:
            if not _is_finite_number(value):
                add_issue(
                    "stance_label_rules",
                    None,
                    f"strength_thresholds.{key}",
                    "invalid",
                    f"{key} must be numeric.",
                )
        if (
            _is_finite_number(weak_max_abs)
            and _is_finite_number(moderate_max_abs)
            and _is_finite_number(strong_min_abs)
            and not (weak_max_abs <= moderate_max_abs <= strong_min_abs)
        ):
            add_issue(
                "stance_label_rules",
                None,
                "strength_thresholds",
                "invalid_order",
                "Require weak_max_abs <= moderate_max_abs <= strong_min_abs.",
            )

        neutral_strength = stance_label_rules.get("neutral_strength")
        if neutral_strength is not None and not non_empty_string(neutral_strength):
            add_issue(
                "stance_label_rules",
                None,
                "neutral_strength",
                "invalid",
                "neutral_strength must be a non-empty string when present.",
            )

        return stance_label_rules, neutral_strength

    stance_label_rules, neutral_strength = validate_stance_label_rules_section(
        stance_label_rules
    )

    stance_output_names = {}

    # Layer C — Credit stance model invariants
    def validate_credit_cap_block(stance_name, field_prefix, cap):
        if not isinstance(cap, dict):
            add_issue(
                "exposure_stances",
                stance_name,
                field_prefix,
                "invalid",
                "Credit rule adjustment cap must be a mapping.",
            )
            return

        for field_name in cap:
            if field_name not in {"min", "max"}:
                add_issue(
                    "exposure_stances",
                    stance_name,
                    f"{field_prefix}.{field_name}",
                    "unknown",
                    "Unknown Credit rule adjustment cap field.",
                )

        lower = cap.get("min")
        upper = cap.get("max")
        has_lower = "min" in cap
        has_upper = "max" in cap
        if has_lower and not _is_finite_number(lower):
            add_issue(
                "exposure_stances",
                stance_name,
                f"{field_prefix}.min",
                "invalid",
                "Credit rule adjustment cap.min must be numeric and not bool.",
            )
        if has_upper and not _is_finite_number(upper):
            add_issue(
                "exposure_stances",
                stance_name,
                f"{field_prefix}.max",
                "invalid",
                "Credit rule adjustment cap.max must be numeric and not bool.",
            )
        if (
            has_lower
            and has_upper
            and _is_finite_number(lower)
            and _is_finite_number(upper)
            and lower >= upper
        ):
            add_issue(
                "exposure_stances",
                stance_name,
                field_prefix,
                "invalid_order",
                "Credit rule adjustment cap.min must be less than cap.max.",
            )

    def validate_credit_rule_adjustment_config(
        stance_name,
        adjustment_config,
        expected_case_keys,
    ):
        """Apply Layer C Credit adjustment invariants to the active nested config."""
        field_root = "rule_mapped.adjustment.config"
        if not isinstance(adjustment_config, dict):
            add_issue(
                "exposure_stances",
                stance_name,
                field_root,
                "invalid",
                "Credit rule adjustment config must be a mapping.",
            )
            return

        for field_name in adjustment_config:
            if field_name not in {"default_cap", "states"}:
                add_issue(
                    "exposure_stances",
                    stance_name,
                    f"{field_root}.{field_name}",
                    "unknown",
                    "Unknown Credit rule adjustment config field.",
                )

        default_cap = adjustment_config.get("default_cap")
        if not isinstance(default_cap, dict):
            add_issue(
                "exposure_stances",
                stance_name,
                f"{field_root}.default_cap",
                "missing" if default_cap is None else "invalid",
                "Credit rule adjustment default_cap must be a mapping.",
            )
        else:
            validate_credit_cap_block(
                stance_name,
                f"{field_root}.default_cap",
                default_cap,
            )
            if "min" not in default_cap:
                add_issue(
                    "exposure_stances",
                    stance_name,
                    f"{field_root}.default_cap.min",
                    "missing",
                    "Credit rule adjustment default_cap.min is required.",
                )
            if "max" not in default_cap:
                add_issue(
                    "exposure_stances",
                    stance_name,
                    f"{field_root}.default_cap.max",
                    "missing",
                    "Credit rule adjustment default_cap.max is required.",
                )

        adjustment_states = adjustment_config.get("states")
        if not isinstance(adjustment_states, dict):
            add_issue(
                "exposure_stances",
                stance_name,
                f"{field_root}.states",
                "missing" if adjustment_states is None else "invalid",
                "Credit rule adjustment states must be a mapping.",
            )
            return

        actual_adjustment_keys = set(adjustment_states)
        if expected_case_keys and actual_adjustment_keys != expected_case_keys:
            for key in sorted(expected_case_keys - actual_adjustment_keys):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    f"{field_root}.states.{key}",
                    "missing",
                    "Credit rule adjustment states must include every configured rule case.",
                )
            for key in sorted(actual_adjustment_keys - expected_case_keys):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    f"{field_root}.states.{key}",
                    "unknown",
                    "Credit rule adjustment states contains an unknown rule case.",
                )

        for key, adjustment in adjustment_states.items():
            field_prefix = f"{field_root}.states.{key}"
            if not isinstance(adjustment, dict):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    field_prefix,
                    "invalid",
                    "Credit rule adjustment state block must be a mapping.",
                )
                continue
            for field_name in adjustment:
                if field_name not in {
                    "change_intensity_weight",
                    "level_intensity_weight",
                    "cap",
                }:
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"{field_prefix}.{field_name}",
                        "unknown",
                        "Unknown Credit rule adjustment state field.",
                    )
            for weight_field in [
                "change_intensity_weight",
                "level_intensity_weight",
            ]:
                weight = adjustment.get(weight_field)
                if weight_field not in adjustment:
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"{field_prefix}.{weight_field}",
                        "missing",
                        "Credit rule adjustment weight is required.",
                    )
                elif not _is_finite_number(weight):
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"{field_prefix}.{weight_field}",
                        "invalid",
                        "Credit rule adjustment weight must be numeric and not bool.",
                    )
            if "cap" in adjustment:
                validate_credit_cap_block(
                    stance_name,
                    f"{field_prefix}.cap",
                    adjustment.get("cap"),
                )

    # Layer A — generic rule declaration and cross-product structure
    def validate_rule_mapped_rule_scores(
        section_name,
        stance_name,
        rule_scores,
        state_input_count,
        expected_state_values_by_input,
    ):
        """Parse rule keys once and validate declared state cross-product coverage."""
        field_root = "rule_mapped"
        parsed_rule_scores = {}
        if not isinstance(rule_scores, dict) or not rule_scores:
            add_issue(
                section_name,
                stance_name,
                f"{field_root}.rule_scores",
                "missing" if rule_scores is None else "invalid",
                "rule_mapped.rule_scores must be a non-empty mapping.",
            )
        elif state_input_count:
            try:
                parsed_rule_scores = Module1Calculator.parse_rule_scores_n_parts(
                    rule_scores,
                    expected_parts=state_input_count,
                    context=f"{section_name}.{stance_name}.rule_mapped",
                )
            except ValueError as exc:
                add_issue(
                    section_name,
                    stance_name,
                    f"{field_root}.rule_scores",
                    "invalid",
                    str(exc),
                )

        expected_rule_tuples = set()
        if (
            expected_state_values_by_input
            and len(expected_state_values_by_input) == state_input_count
        ):
            expected_rule_tuples = set(product(*expected_state_values_by_input))

        if expected_rule_tuples and parsed_rule_scores:
            actual_rule_tuples = set(parsed_rule_scores)
            for rule_tuple in sorted(expected_rule_tuples - actual_rule_tuples):
                add_issue(
                    section_name,
                    stance_name,
                    f"{field_root}.rule_scores.{'|'.join(rule_tuple)}",
                    "missing",
                    "rule_mapped.rule_scores must cover every declared state or bucket cross-product case.",
                )
            for rule_tuple in sorted(actual_rule_tuples - expected_rule_tuples):
                add_issue(
                    section_name,
                    stance_name,
                    f"{field_root}.rule_scores.{'|'.join(rule_tuple)}",
                    "unknown",
                    "rule_mapped.rule_scores contains an unknown state or bucket cross-product case.",
                )

        return expected_rule_tuples

    # Layer B — calculator-supported rule-mapped adjustment structure
    def validate_rule_mapped_adjustment_contract(
        section_name,
        stance_name,
        adjustment,
        state_inputs,
        expected_rule_tuples,
    ):
        """Validate executable Credit adjustment structure and return output roles."""
        if adjustment is None:
            return []

        field_root = "rule_mapped"
        if not isinstance(adjustment, dict):
            add_issue(
                section_name,
                stance_name,
                f"{field_root}.adjustment",
                "invalid",
                "rule_mapped.adjustment must be a mapping when present.",
            )
            return []

        allowed_adjustment_fields = {
            "metadata_outputs",
            "adjustment_output",
            "config",
        }
        for field_name in adjustment:
            if field_name not in allowed_adjustment_fields:
                add_issue(
                    section_name,
                    stance_name,
                    f"{field_root}.adjustment.{field_name}",
                    "unknown",
                    "Unknown rule_mapped adjustment field.",
                )

        state_input_count = len(state_inputs)
        if state_input_count != 2:
            add_issue(
                section_name,
                stance_name,
                f"{field_root}.state_inputs",
                "invalid",
                "Credit rule_mapped adjustment requires exactly two state inputs.",
            )
        for idx, state_input in enumerate(state_inputs):
            if (
                isinstance(state_input, dict)
                and state_input.get("classification") != "threshold_state"
            ):
                add_issue(
                    section_name,
                    stance_name,
                    f"{field_root}.state_inputs[{idx}].classification",
                    "unsupported",
                    "Credit rule_mapped adjustment inputs must use threshold_state.",
                )

        output_roles = []
        if "metadata_outputs" in adjustment:
            metadata_outputs = adjustment.get("metadata_outputs")
            if not isinstance(metadata_outputs, list):
                add_issue(
                    section_name,
                    stance_name,
                    f"{field_root}.adjustment.metadata_outputs",
                    "invalid",
                    "rule_mapped adjustment metadata_outputs must be a list when present.",
                )
            else:
                seen_metadata_outputs = set()
                for idx, output_name in enumerate(metadata_outputs):
                    output_field = f"{field_root}.adjustment.metadata_outputs[{idx}]"
                    if not non_empty_string(output_name):
                        add_issue(
                            section_name,
                            stance_name,
                            output_field,
                            "invalid",
                            "Adjustment metadata output names must be non-empty strings.",
                        )
                        continue
                    output_roles.append((output_field, output_name))
                    if output_name in seen_metadata_outputs:
                        add_issue(
                            section_name,
                            stance_name,
                            output_field,
                            "duplicate",
                            "Adjustment metadata output names must be unique.",
                        )
                    seen_metadata_outputs.add(output_name)
                if len(metadata_outputs) != state_input_count:
                    add_issue(
                        section_name,
                        stance_name,
                        f"{field_root}.adjustment.metadata_outputs",
                        "invalid",
                        "Adjustment metadata_outputs must match the state-input count.",
                    )

        adjustment_output = adjustment.get("adjustment_output")
        if adjustment_output is not None:
            output_field = f"{field_root}.adjustment.adjustment_output"
            if not non_empty_string(adjustment_output):
                add_issue(
                    section_name,
                    stance_name,
                    output_field,
                    "invalid",
                    "rule_mapped adjustment_output must be a non-empty string when present.",
                )
            else:
                output_roles.append((output_field, adjustment_output))

        adjustment_config = adjustment.get("config")
        config_field = f"{field_root}.adjustment.config"
        if "config" not in adjustment:
            add_issue(
                section_name,
                stance_name,
                config_field,
                "missing",
                "Credit rule_mapped adjustment.config is required.",
            )
        elif not isinstance(adjustment_config, dict):
            add_issue(
                section_name,
                stance_name,
                config_field,
                "invalid",
                "Credit rule_mapped adjustment.config must be a mapping.",
            )
        else:
            validate_credit_rule_adjustment_config(
                stance_name,
                adjustment_config,
                {
                    "|".join(rule_tuple)
                    for rule_tuple in expected_rule_tuples
                },
            )

        return output_roles

    def validate_rule_mapped_output_contract(
        section_name,
        stance_name,
        source_score_roles,
        generated_output_roles,
    ):
        """Validate per-stance source uniqueness and generated-column ownership."""
        source_columns = {}
        for field_name, column_name in source_score_roles:
            if column_name in source_columns:
                add_issue(
                    section_name,
                    stance_name,
                    field_name,
                    "duplicate",
                    "rule_mapped source_score values must be unique within a stance.",
                )
            else:
                source_columns[column_name] = field_name

        generated_columns = {}
        for field_name, column_name in generated_output_roles:
            conflict_field = source_columns.get(column_name)
            if conflict_field is None:
                conflict_field = generated_columns.get(column_name)
            if conflict_field is not None:
                add_issue(
                    section_name,
                    stance_name,
                    field_name,
                    "output_conflict",
                    "rule_mapped generated outputs must be unique and must not overwrite source scores.",
                )
            else:
                generated_columns[column_name] = field_name

    def validate_rule_mapped_stance_schema(section_name, stance_name, stance):
        """Orchestrate Layer A/B rule-mapped checks and Layer C compatibility."""
        rule_mapped = stance.get("rule_mapped")
        field_root = "rule_mapped"

        # Layer B: custom stances require the executable rule-mapped form.
        if not isinstance(rule_mapped, dict):
            add_issue(
                section_name,
                stance_name,
                field_root,
                "missing" if rule_mapped is None else "invalid",
                "rule_mapped must be a mapping for custom stance functions.",
            )
            return

        allowed_rule_mapped_fields = {
            "function",
            "state_inputs",
            "state_stabilization",
            "rule_scores",
            "rule_case_output",
            "stabilization_changed_any_output",
            "base_rule_score_output",
            "adjustment",
            "adjusted_score_output",
            "score_output",
            "stance_output",
            "strength_output",
        }
        for field_name in rule_mapped:
            if field_name not in allowed_rule_mapped_fields:
                add_issue(
                    section_name,
                    stance_name,
                    f"{field_root}.{field_name}",
                    "unknown",
                    "Unknown rule_mapped field.",
                )

        # Layer B: calculator dispatch and required active output bindings.
        if rule_mapped.get("function") != "rule_mapped_stance":
            add_issue(
                section_name,
                stance_name,
                f"{field_root}.function",
                "unsupported",
                "rule_mapped.function must be rule_mapped_stance.",
            )

        for output_field in ["score_output", "stance_output", "strength_output"]:
            output_name = rule_mapped.get(output_field)
            if not non_empty_string(output_name):
                add_issue(
                    section_name,
                    stance_name,
                    f"{field_root}.{output_field}",
                    "invalid",
                    f"rule_mapped.{output_field} must be a non-empty string.",
                )
                continue
            if output_name != stance.get(output_field):
                add_issue(
                    section_name,
                    stance_name,
                    f"{field_root}.{output_field}",
                    "mismatch",
                    f"rule_mapped.{output_field} must match the active stance {output_field}.",
                )

        supported_classifications = {
            "threshold_state",
            "threshold_bucket",
            "score_bucket",
        }
        required_state_input_output_fields = (
            "raw_output",
            "stabilized_output",
            "stabilization_changed_output",
        )

        # Layer A state-input grammar with Layer B classification dispatch.
        state_inputs = rule_mapped.get("state_inputs")
        ordered_names = []
        expected_state_values_by_input = []
        source_score_roles = []
        state_output_roles = []
        if not isinstance(state_inputs, list) or not state_inputs:
            add_issue(
                section_name,
                stance_name,
                f"{field_root}.state_inputs",
                "invalid",
                "rule_mapped.state_inputs must be a non-empty ordered list.",
            )
            state_inputs = []

        for idx, state_input in enumerate(state_inputs):
            input_prefix = f"{field_root}.state_inputs[{idx}]"
            if not isinstance(state_input, dict):
                add_issue(
                    section_name,
                    stance_name,
                    input_prefix,
                    "invalid",
                    "rule_mapped state input entries must be mappings.",
                )
                continue

            input_name = state_input.get("name")
            if not non_empty_string(input_name):
                add_issue(
                    section_name,
                    stance_name,
                    f"{input_prefix}.name",
                    "invalid",
                    "rule_mapped state input name must be a non-empty string.",
                )
            else:
                ordered_names.append(input_name)

            source_score = state_input.get("source_score")
            if not non_empty_string(source_score):
                add_issue(
                    section_name,
                    stance_name,
                    f"{input_prefix}.source_score",
                    "invalid",
                    "rule_mapped state input source_score must be a non-empty string.",
                )
            elif source_score not in component_score_outputs:
                add_issue(
                    section_name,
                    stance_name,
                    f"{input_prefix}.source_score",
                    "unknown_component_score",
                    "rule_mapped source_score must refer to a configured component score output.",
                )
            if non_empty_string(source_score):
                source_score_roles.append(
                    (f"{input_prefix}.source_score", source_score)
                )

            classification = state_input.get("classification")
            if classification not in supported_classifications:
                add_issue(
                    section_name,
                    stance_name,
                    f"{input_prefix}.classification",
                    "unsupported",
                    "rule_mapped classification must be threshold_state, threshold_bucket, or score_bucket.",
                )

            allowed_state_input_fields = {
                "name",
                "source_score",
                "classification",
                "raw_output",
                "stabilized_output",
                "stabilization_changed_output",
                "diagnostic_component",
            }
            if classification == "threshold_state":
                allowed_state_input_fields.add("state_buckets")
            elif classification in {"threshold_bucket", "score_bucket"}:
                allowed_state_input_fields.add("buckets")
            else:
                allowed_state_input_fields.update({"state_buckets", "buckets"})
            for field_name in state_input:
                if field_name not in allowed_state_input_fields:
                    add_issue(
                        section_name,
                        stance_name,
                        f"{input_prefix}.{field_name}",
                        "unknown",
                        "Unknown rule_mapped state input field.",
                    )

            for output_field in required_state_input_output_fields:
                output_name = state_input.get(output_field)
                if output_field not in state_input:
                    add_issue(
                        section_name,
                        stance_name,
                        f"{input_prefix}.{output_field}",
                        "missing",
                        f"rule_mapped state input {output_field} is required.",
                    )
                elif not non_empty_string(output_name):
                    add_issue(
                        section_name,
                        stance_name,
                        f"{input_prefix}.{output_field}",
                        "invalid",
                        f"rule_mapped state input {output_field} must be a non-empty string.",
                    )
                else:
                    state_output_roles.append(
                        (f"{input_prefix}.{output_field}", output_name)
                    )

            diagnostic_component = state_input.get("diagnostic_component")
            if (
                diagnostic_component is not None
                and not non_empty_string(diagnostic_component)
            ):
                add_issue(
                    section_name,
                    stance_name,
                    f"{input_prefix}.diagnostic_component",
                    "invalid",
                    "rule_mapped state input diagnostic_component must be a non-empty string when present.",
                )

            values = []
            if classification == "threshold_state":
                state_buckets = state_input.get("state_buckets")
                if not isinstance(state_buckets, dict):
                    add_issue(
                        section_name,
                        stance_name,
                        f"{input_prefix}.state_buckets",
                        "missing" if state_buckets is None else "invalid",
                        "threshold_state inputs must define state_buckets as a mapping.",
                    )
                else:
                    for bucket_key in ["positive", "neutral", "negative"]:
                        state_value = state_buckets.get(bucket_key)
                        if not non_empty_string(state_value):
                            add_issue(
                                section_name,
                                stance_name,
                                f"{input_prefix}.state_buckets.{bucket_key}",
                                "invalid",
                                "threshold_state bucket values must be non-empty strings.",
                            )
                        else:
                            values.append(state_value.strip())
                    for bucket_key in state_buckets:
                        if bucket_key not in {"positive", "neutral", "negative"}:
                            add_issue(
                                section_name,
                                stance_name,
                                f"{input_prefix}.state_buckets.{bucket_key}",
                                "unknown",
                                "Unknown threshold_state bucket key.",
                            )
            elif classification in {"threshold_bucket", "score_bucket"}:
                buckets = state_input.get("buckets")
                if not isinstance(buckets, list) or not buckets:
                    add_issue(
                        section_name,
                        stance_name,
                        f"{input_prefix}.buckets",
                        "invalid",
                        "bucket-classified rule_mapped inputs must define buckets as a non-empty list.",
                    )
                else:
                    for bucket_idx, bucket_name in enumerate(buckets):
                        if not non_empty_string(bucket_name):
                            add_issue(
                                section_name,
                                stance_name,
                                f"{input_prefix}.buckets[{bucket_idx}]",
                                "invalid",
                                "Bucket names must be non-empty strings.",
                            )
                        else:
                            values.append(bucket_name.strip())
                    if values and non_empty_string(source_score):
                        # Layer C: declared buckets must match active component models.
                        component_name = component_score_outputs.get(source_score)
                        component_score = components.get(component_name, {}).get(
                            "score",
                            {},
                        )
                        expected_classification, mixed_bucket_style = (
                            Module1Calculator
                            ._rule_mapped_bucket_classification_from_score(
                                component_score
                            )
                        )
                        if mixed_bucket_style:
                            add_issue(
                                section_name,
                                stance_name,
                                f"{input_prefix}.classification",
                                "mixed_bucket_style",
                                "rule_mapped state input "
                                f"{idx}"
                                f" ({input_name}) references {source_score}, whose component "
                                "score.buckets mix range-style keys with exact score keys.",
                            )
                        elif (
                            expected_classification is not None
                            and classification != expected_classification
                        ):
                            add_issue(
                                section_name,
                                stance_name,
                                f"{input_prefix}.classification",
                                "classification_mismatch",
                                "rule_mapped state input "
                                f"{idx}"
                                f" ({input_name}) declares classification {classification}; "
                                f"expected {expected_classification} from component "
                                f"{component_name} score.buckets.",
                            )
                        expected_buckets = curve_bucket_names.get(
                            component_name,
                            bucket_names_from_score(component_score),
                        )
                        if expected_buckets and set(values) != expected_buckets:
                            for bucket_name in sorted(expected_buckets - set(values)):
                                add_issue(
                                    section_name,
                                    stance_name,
                                    f"{input_prefix}.buckets.{bucket_name}",
                                    "missing",
                                    "bucket-classified inputs must declare every configured component bucket.",
                                )
                            for bucket_name in sorted(set(values) - expected_buckets):
                                add_issue(
                                    section_name,
                                    stance_name,
                                    f"{input_prefix}.buckets.{bucket_name}",
                                    "unknown",
                                    "bucket-classified input declares an unknown component bucket.",
                                )

            if values:
                if len(values) != len(set(values)):
                    add_issue(
                        section_name,
                        stance_name,
                        input_prefix,
                        "duplicate_values",
                        "Rule-mapped state or bucket values must be unique per input.",
                    )
                expected_state_values_by_input.append(values)

        if ordered_names and len(ordered_names) != len(set(ordered_names)):
            add_issue(
                section_name,
                stance_name,
                f"{field_root}.state_inputs",
                "duplicate",
                "rule_mapped state input names must be unique.",
            )

        # Layer A: generic ordered stabilization structure.
        state_input_count = len(state_inputs)
        if ordered_names and len(ordered_names) == state_input_count:
            state_stabilization = rule_mapped.get("state_stabilization")
            if isinstance(state_stabilization, dict):
                try:
                    Module1Calculator.resolve_rule_mapped_stabilization_config(
                        rule_mapped,
                        ordered_names,
                        context=f"{section_name}.{stance_name}.rule_mapped",
                    )
                except ValueError as exc:
                    add_issue(
                        section_name,
                        stance_name,
                        f"{field_root}.state_stabilization",
                        "invalid",
                        str(exc),
                    )
            else:
                add_issue(
                    section_name,
                    stance_name,
                    f"{field_root}.state_stabilization",
                    "missing" if state_stabilization is None else "invalid",
                    "rule_mapped.state_stabilization must be a mapping.",
                )

        # Layer B: outputs consumed by calculator and diagnostic dispatch.
        for output_field in [
            "rule_case_output",
            "stabilization_changed_any_output",
            "base_rule_score_output",
            "adjusted_score_output",
        ]:
            output_name = rule_mapped.get(output_field)
            if output_name is not None and not non_empty_string(output_name):
                add_issue(
                    section_name,
                    stance_name,
                    f"{field_root}.{output_field}",
                    "invalid",
                    f"rule_mapped.{output_field} must be a non-empty string when present.",
                )

        adjusted_score_output = rule_mapped.get("adjusted_score_output")
        if (
            non_empty_string(adjusted_score_output)
            and adjusted_score_output != rule_mapped.get("score_output")
        ):
            add_issue(
                section_name,
                stance_name,
                f"{field_root}.adjusted_score_output",
                "mismatch",
                "rule_mapped.adjusted_score_output must equal score_output when present.",
            )

        if not non_empty_string(rule_mapped.get("rule_case_output")):
            add_issue(
                section_name,
                stance_name,
                f"{field_root}.rule_case_output",
                "invalid",
                "rule_mapped.rule_case_output must be declared or derivable.",
            )

        if not non_empty_string(rule_mapped.get("stabilization_changed_any_output")):
            add_issue(
                section_name,
                stance_name,
                f"{field_root}.stabilization_changed_any_output",
                "invalid",
                "rule_mapped.stabilization_changed_any_output must be declared or derivable.",
            )

        expected_rule_tuples = validate_rule_mapped_rule_scores(
            section_name,
            stance_name,
            rule_mapped.get("rule_scores"),
            state_input_count,
            expected_state_values_by_input,
        )
        adjustment_output_roles = validate_rule_mapped_adjustment_contract(
            section_name,
            stance_name,
            rule_mapped.get("adjustment"),
            state_inputs,
            expected_rule_tuples,
        )

        generated_output_roles = list(state_output_roles)
        for output_field in (
            "rule_case_output",
            "stabilization_changed_any_output",
            "base_rule_score_output",
        ):
            output_name = rule_mapped.get(output_field)
            if non_empty_string(output_name):
                generated_output_roles.append(
                    (f"{field_root}.{output_field}", output_name)
                )
        generated_output_roles.extend(adjustment_output_roles)
        for output_field in ("score_output", "stance_output", "strength_output"):
            output_name = rule_mapped.get(output_field)
            if non_empty_string(output_name):
                generated_output_roles.append(
                    (f"{field_root}.{output_field}", output_name)
                )
        validate_rule_mapped_output_contract(
            section_name,
            stance_name,
            source_score_roles,
            generated_output_roles,
        )

    # Layer A section orchestration with Layer B/C dispatch at each stance.
    def validate_exposure_stances_section(exposure_stances):
        """Validate stance structure, executable forms, and stance model invariants once."""
        if not isinstance(exposure_stances, dict) or not exposure_stances:
            add_issue(
                "exposure_stances",
                None,
                "exposure_stances",
                "invalid",
                "exposure_stances must be a non-empty mapping.",
            )
            exposure_stances = {}

        if "draft_exposure_stances" in config:
            add_issue(
                "draft_exposure_stances",
                None,
                "draft_exposure_stances",
                "unsupported",
                "draft_exposure_stances is not supported.",
            )

        for stance_name, stance in exposure_stances.items():
            add_checked("exposure_stances", stance_name, "stance")

            # Layer A: generic stance mapping, outputs, inputs, and labels.
            if not isinstance(stance, dict):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "definition",
                    "invalid",
                    "Exposure stance definition must be a mapping.",
                )
                continue

            for field in ["score_output", "stance_output", "strength_output"]:
                output_name = stance.get(field)
                if not non_empty_string(output_name):
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        field,
                        "invalid",
                        f"{field} must be a non-empty string.",
                    )
                    continue
                if output_name in component_output_names:
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        field,
                        "output_conflict",
                        "Stance outputs must not conflict with component outputs.",
                    )
                if output_name in stance_output_names:
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        field,
                        "duplicate",
                        f"Also used by {stance_output_names[output_name]}.",
                    )
                stance_output_names[output_name] = f"{stance_name}.{field}"

            function = stance.get("function")
            is_weighted_stance = function == "weighted_sum"

            # Layer B: calculator stance dispatch and weighted-input contract.
            if not is_weighted_stance and not non_empty_string(function):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "function",
                    "invalid",
                    "function must be weighted_sum or another non-empty string.",
                )

            inputs = stance.get("inputs")
            if not isinstance(inputs, list) or not inputs:
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "inputs",
                    "invalid",
                    "inputs must be a non-empty list.",
                )
                inputs = []

            for idx, item in enumerate(inputs):
                if not isinstance(item, dict):
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"inputs[{idx}]",
                        "invalid",
                        "Input item must be a mapping.",
                    )
                    continue
                component_col = item.get("component")
                if component_col not in component_score_outputs:
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"inputs[{idx}].component",
                        "unknown_component_score",
                        f"Input component must refer to a component score output: {component_col}.",
                    )
                if is_weighted_stance:
                    if "weight" not in item:
                        add_issue(
                            "exposure_stances",
                            stance_name,
                            f"inputs[{idx}].weight",
                            "missing",
                            f"Weighted stance {stance_name} inputs[{idx}].weight is required.",
                        )
                    elif not _is_finite_number(item.get("weight")):
                        add_issue(
                            "exposure_stances",
                            stance_name,
                            f"inputs[{idx}].weight",
                            "invalid",
                            f"Weighted stance {stance_name} inputs[{idx}].weight must be numeric and not bool.",
                        )
            labels = stance.get("labels")
            if not isinstance(labels, dict):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "labels",
                    "missing",
                    "labels must be a mapping.",
                )
                labels = {}

            direction = labels.get("direction")
            if not isinstance(direction, dict):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "labels.direction",
                    "missing",
                    "labels.direction must be a mapping.",
                )
                direction = {}

            strength = labels.get("strength")
            if not isinstance(strength, dict):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "labels.strength",
                    "missing",
                    "labels.strength must be a mapping.",
                )
                strength = {}

            direction_values = []
            for key in ["positive", "neutral", "negative"]:
                value = direction.get(key)
                if not non_empty_string(value):
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"labels.direction.{key}",
                        "invalid",
                        "Direction label value must be a non-empty string.",
                    )
                else:
                    direction_values.append(value)
            if len(direction_values) != len(set(direction_values)):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "labels.direction",
                    "duplicate_values",
                    "Direction label values must be unique within one stance.",
                )

            strength_values = []
            for key in ["weak", "moderate", "strong"]:
                value = strength.get(key)
                if not non_empty_string(value):
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"labels.strength.{key}",
                        "invalid",
                        "Strength label value must be a non-empty string.",
                    )
                else:
                    strength_values.append(value)
            if len(strength_values) != len(set(strength_values)):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "labels.strength",
                    "duplicate_values",
                    "Strength label values must be unique within one stance.",
                )

            if neutral_strength is not None and strength and neutral_strength not in strength:
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "labels.strength.neutral_strength",
                    "unknown_strength_key",
                    "neutral_strength should be one of the configured strength label keys.",
                )

            # Layer B rule-mapped dispatch owns generic checks and calls Layer C.
            if (
                not is_weighted_stance and non_empty_string(function)
            ) or "rule_mapped" in stance:
                validate_rule_mapped_stance_schema(
                    "exposure_stances",
                    stance_name,
                    stance,
                )

    validate_exposure_stances_section(exposure_stances)

    issues_df = pd.DataFrame(
        issues,
        columns=["section", "name", "field", "issue", "detail"],
    )
    full_df = pd.DataFrame(
        checked,
        columns=["section", "name", "field", "value", "status"],
    )
    report_df = pd.DataFrame(
        [
            {
                "checked_sections": len(set(full_df["section"])) if not full_df.empty else 0,
                "issue_count": int(issues_df.shape[0]),
                "overall_status": "valid" if issues_df.empty else "invalid",
            }
        ]
    )
    return {
        "report": report_df,
        "issues": issues_df,
        "full": full_df,
    }
