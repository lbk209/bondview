from itertools import product
from numbers import Real
from collections.abc import Mapping

import pandas as pd


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

    def is_number(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool)

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
    draft_exposure_stances = config.get("draft_exposure_stances")
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

    if not isinstance(components, dict) or not components:
        add_issue(
            "components",
            None,
            "components",
            "invalid",
            "components must be a non-empty mapping.",
        )
        components = {}

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

    def validate_anchor_block(component_name, anchors, field):
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
            if not is_number(anchor_value):
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

    def bucket_names_from_score(component_name, score):
        buckets = score.get("buckets")
        if isinstance(buckets, dict):
            return set(buckets)
        return set()

    def validate_threshold_label_mode(component_name, label):
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
        if not is_number(positive_threshold):
            add_issue(
                "components",
                component_name,
                "label.thresholds.positive",
                "invalid",
                "positive threshold must be numeric.",
            )
        if not is_number(negative_threshold):
            add_issue(
                "components",
                component_name,
                "label.thresholds.negative",
                "invalid",
                "negative threshold must be numeric.",
            )
        if (
            is_number(positive_threshold)
            and is_number(negative_threshold)
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

    def validate_curve_change_buckets(score):
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
        if not is_number(steepening_min):
            add_issue(
                "components",
                component_name,
                "score.buckets.steepening.min",
                "invalid",
                "curve_change steepening.min must be numeric and not bool.",
            )
        if not is_number(flattening_max):
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
            is_number(steepening_min)
            and is_number(flattening_max)
            and flattening_max >= steepening_min
        ):
            add_issue(
                "components",
                component_name,
                "score.buckets",
                "invalid_order",
                "curve_change flattening.max must be less than steepening.min.",
            )

    def validate_curve_state_buckets(score):
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
                if not is_number(value):
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
                is_number(value)
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

    def validate_curve_move_driver_buckets(score):
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
            if rule.get("default") is True and "score" in rule and not is_number(score_value):
                add_issue(
                    "components",
                    component_name,
                    f"score.buckets.{bucket_name}.score",
                    "invalid",
                    "curve_move_driver default bucket score must be numeric and not bool when present.",
                )
            if rule.get("default") is True:
                continue
            if not is_number(score_value):
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

    for component_name, component in components.items():
        add_checked("components", component_name, "component")
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

        if function not in known_score_functions:
            add_issue(
                "components",
                component_name,
                "score.function",
                "unsupported",
                f"Supported score functions: {sorted(known_score_functions)}.",
            )

        input_preparation = score.get("input_preparation")
        supported_input_preparation_components = {
            "curve_change",
            "curve_state",
            "curve_move_driver",
            "credit_spread_change",
            "credit_spread_state",
        }
        if input_preparation is not None:
            field_prefix = "score.input_preparation"
            if component_name not in supported_input_preparation_components:
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
                    if component_name != "curve_move_driver":
                        add_issue(
                            "components",
                            component_name,
                            f"{field_prefix}.min_abs_value",
                            "unsupported_for_component",
                            "input_preparation.min_abs_value is only supported for curve_move_driver.",
                        )
                    elif (
                        not is_number(min_abs_value)
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
                    elif not is_number(item.get("weight")) or pd.isna(
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
            if component_name != "curve_move_driver":
                add_issue(
                    "components",
                    component_name,
                    "score.function",
                    "unsupported_for_component",
                    "curve_move_driver_score is only supported for the "
                    "curve_move_driver component.",
                )

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
            component_name == "curve_move_driver"
            and function == "curve_move_driver_score"
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
            component_name == "curve_move_driver"
            and function == "curve_move_driver_score"
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

        if component_name == "curve_change":
            validate_curve_change_buckets(score)
        elif component_name == "curve_state":
            validate_curve_state_buckets(score)
        elif component_name == "curve_move_driver":
            validate_curve_move_driver_buckets(score)

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
    if not is_number(positive_min):
        add_issue(
            "stance_label_rules",
            None,
            "direction_thresholds.positive_min",
            "invalid",
            "positive_min must be numeric.",
        )
    if not is_number(negative_max):
        add_issue(
            "stance_label_rules",
            None,
            "direction_thresholds.negative_max",
            "invalid",
            "negative_max must be numeric.",
        )
    if is_number(positive_min) and is_number(negative_max) and positive_min <= negative_max:
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
        if not is_number(value):
            add_issue(
                "stance_label_rules",
                None,
                f"strength_thresholds.{key}",
                "invalid",
                f"{key} must be numeric.",
            )
    if (
        is_number(weak_max_abs)
        and is_number(moderate_max_abs)
        and is_number(strong_min_abs)
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

    if not isinstance(exposure_stances, dict) or not exposure_stances:
        add_issue(
            "exposure_stances",
            None,
            "exposure_stances",
            "invalid",
            "exposure_stances must be a non-empty mapping.",
        )
        exposure_stances = {}

    if draft_exposure_stances is not None and not isinstance(draft_exposure_stances, dict):
        add_issue(
            "draft_exposure_stances",
            None,
            "draft_exposure_stances",
            "invalid",
            "draft_exposure_stances must be a mapping when provided.",
        )
        draft_exposure_stances = {}

    stance_output_names = {}
    known_custom_stance_functions = {
        "credit_spread_stance",
        "curve_positioning_stance",
        "duration_rule_stance",
    }
    known_draft_stance_functions = {
        "duration_rule_stance",
    }

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

        lower = cap.get("min")
        upper = cap.get("max")
        has_lower = "min" in cap
        has_upper = "max" in cap
        if has_lower and not is_number(lower):
            add_issue(
                "exposure_stances",
                stance_name,
                f"{field_prefix}.min",
                "invalid",
                "Credit rule adjustment cap.min must be numeric and not bool.",
            )
        if has_upper and not is_number(upper):
            add_issue(
                "exposure_stances",
                stance_name,
                f"{field_prefix}.max",
                "invalid",
                "Credit rule adjustment cap.max must be numeric and not bool.",
            )
        if has_lower and has_upper and is_number(lower) and is_number(upper) and lower >= upper:
            add_issue(
                "exposure_stances",
                stance_name,
                field_prefix,
                "invalid_order",
                "Credit rule adjustment cap.min must be less than cap.max.",
            )

    def validate_credit_spread_stance_parameters(stance_name, stance):
        state_buckets = stance.get("state_buckets")
        expected_pair_keys = set()
        if not isinstance(state_buckets, dict):
            add_issue(
                "exposure_stances",
                stance_name,
                "state_buckets",
                "missing" if state_buckets is None else "invalid",
                "Credit stance state_buckets must be a mapping.",
            )
        else:
            bucket_values = {}
            for component_key in ["credit_spread_change", "credit_spread_state"]:
                component_buckets = state_buckets.get(component_key)
                field_prefix = f"state_buckets.{component_key}"
                if not isinstance(component_buckets, dict):
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        field_prefix,
                        "missing" if component_buckets is None else "invalid",
                        "Credit stance state_buckets component block must be a mapping.",
                    )
                    continue

                bucket_values[component_key] = {}
                for bucket_key in ["positive", "neutral", "negative"]:
                    bucket_value = component_buckets.get(bucket_key)
                    if not non_empty_string(bucket_value):
                        add_issue(
                            "exposure_stances",
                            stance_name,
                            f"{field_prefix}.{bucket_key}",
                            "invalid",
                            "Credit stance state bucket value must be a non-empty string.",
                        )
                    else:
                        bucket_values[component_key][bucket_key] = bucket_value

            change_values = bucket_values.get("credit_spread_change", {})
            state_values = bucket_values.get("credit_spread_state", {})
            if len(change_values) == 3 and len(state_values) == 3:
                expected_pair_keys = {
                    f"{change_state}|{level_state}"
                    for change_state in change_values.values()
                    for level_state in state_values.values()
                }

        state_stabilization = stance.get("state_stabilization")
        required_stabilization_keys = {
            "credit_spread_change",
            "credit_spread_state",
        }
        if not isinstance(state_stabilization, dict):
            add_issue(
                "exposure_stances",
                stance_name,
                "state_stabilization",
                "missing" if state_stabilization is None else "invalid",
                "Credit stance state_stabilization must be a mapping.",
            )
        else:
            for key in sorted(required_stabilization_keys):
                stabilization = state_stabilization.get(key)
                field_prefix = f"state_stabilization.{key}"
                if not isinstance(stabilization, dict):
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        field_prefix,
                        "missing" if stabilization is None else "invalid",
                        "Credit state stabilization block must be a mapping.",
                    )
                    continue

                hysteresis_buffer = stabilization.get("hysteresis_buffer")
                if "hysteresis_buffer" not in stabilization:
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"{field_prefix}.hysteresis_buffer",
                        "missing",
                        "Credit state stabilization hysteresis_buffer is required.",
                    )
                elif not is_number(hysteresis_buffer) or hysteresis_buffer < 0:
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"{field_prefix}.hysteresis_buffer",
                        "invalid",
                        "hysteresis_buffer must be numeric, not bool, and >= 0.",
                    )

                min_state_persistence = stabilization.get("min_state_persistence")
                if "min_state_persistence" not in stabilization:
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"{field_prefix}.min_state_persistence",
                        "missing",
                        "Credit state stabilization min_state_persistence is required.",
                    )
                elif (
                    not isinstance(min_state_persistence, int)
                    or isinstance(min_state_persistence, bool)
                    or min_state_persistence < 1
                ):
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"{field_prefix}.min_state_persistence",
                        "invalid",
                        "min_state_persistence must be an integer, not bool, and >= 1.",
                    )

            for key in state_stabilization:
                if key not in required_stabilization_keys:
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"state_stabilization.{key}",
                        "unknown",
                        "Unknown credit state stabilization key.",
                    )

        rule_scores = stance.get("rule_scores")
        if not isinstance(rule_scores, dict):
            add_issue(
                "exposure_stances",
                stance_name,
                "rule_scores",
                "missing" if rule_scores is None else "invalid",
                "Credit stance rule_scores must be a mapping.",
            )
            rule_scores = {}
        else:
            actual_keys = set(rule_scores)
            if expected_pair_keys and actual_keys != expected_pair_keys:
                for key in sorted(expected_pair_keys - actual_keys):
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"rule_scores.{key}",
                        "missing",
                        "Credit stance rule_scores must include every configured state pair.",
                    )
                for key in sorted(actual_keys - expected_pair_keys):
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"rule_scores.{key}",
                        "unknown",
                        "Credit stance rule_scores contains an unknown state pair.",
                    )
            for key, value in rule_scores.items():
                if not is_number(value):
                    add_issue(
                        "exposure_stances",
                        stance_name,
                        f"rule_scores.{key}",
                        "invalid",
                        "Credit stance rule score values must be numeric and not bool.",
                    )

        rule_adjustments = stance.get("rule_adjustments")
        if not isinstance(rule_adjustments, dict):
            add_issue(
                "exposure_stances",
                stance_name,
                "rule_adjustments",
                "missing" if rule_adjustments is None else "invalid",
                "Credit stance rule_adjustments must be a mapping.",
            )
            return

        default_cap = rule_adjustments.get("default_cap")
        if not isinstance(default_cap, dict):
            add_issue(
                "exposure_stances",
                stance_name,
                "rule_adjustments.default_cap",
                "missing" if default_cap is None else "invalid",
                "Credit stance rule_adjustments.default_cap must be a mapping.",
            )
        else:
            validate_credit_cap_block(
                stance_name,
                "rule_adjustments.default_cap",
                default_cap,
            )
            if "min" not in default_cap:
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "rule_adjustments.default_cap.min",
                    "missing",
                    "Credit stance default_cap.min is required.",
                )
            if "max" not in default_cap:
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "rule_adjustments.default_cap.max",
                    "missing",
                    "Credit stance default_cap.max is required.",
                )

        adjustment_states = rule_adjustments.get("states")
        if not isinstance(adjustment_states, dict):
            add_issue(
                "exposure_stances",
                stance_name,
                "rule_adjustments.states",
                "missing" if adjustment_states is None else "invalid",
                "Credit stance rule_adjustments.states must be a mapping.",
            )
            return

        actual_adjustment_keys = set(adjustment_states)
        if expected_pair_keys and actual_adjustment_keys != expected_pair_keys:
            for key in sorted(expected_pair_keys - actual_adjustment_keys):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    f"rule_adjustments.states.{key}",
                    "missing",
                    "Credit stance rule_adjustments.states must include every configured state pair.",
                )
            for key in sorted(actual_adjustment_keys - expected_pair_keys):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    f"rule_adjustments.states.{key}",
                    "unknown",
                    "Credit stance rule_adjustments.states contains an unknown state pair.",
                )

        for key, adjustment in adjustment_states.items():
            field_prefix = f"rule_adjustments.states.{key}"
            if not isinstance(adjustment, dict):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    field_prefix,
                    "invalid",
                    "Credit rule adjustment state block must be a mapping.",
                )
                continue
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
                elif not is_number(weight):
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

    def validate_duration_rule_stance_schema(section_name, stance_name, stance):
        if not isinstance(stance, dict):
            add_issue(
                section_name,
                stance_name,
                "definition",
                "invalid",
                "duration_rule_stance definition must be a mapping.",
            )
            return

        function = stance.get("function")
        if function != "duration_rule_stance":
            add_issue(
                section_name,
                stance_name,
                "function",
                "unsupported",
                "duration_rule_stance function must be duration_rule_stance.",
            )

        for field in ["score_output", "stance_output", "strength_output"]:
            if not non_empty_string(stance.get(field)):
                add_issue(
                    section_name,
                    stance_name,
                    field,
                    "invalid",
                    f"{field} must be a non-empty string.",
                )

        rule_state_components = stance.get("rule_state_components")
        ordered_components = []
        if isinstance(rule_state_components, set):
            add_issue(
                section_name,
                stance_name,
                "rule_state_components",
                "invalid",
                "rule_state_components must be an ordered list or tuple, not a set.",
            )
        elif not isinstance(rule_state_components, (list, tuple)) or not rule_state_components:
            add_issue(
                section_name,
                stance_name,
                "rule_state_components",
                "missing" if rule_state_components is None else "invalid",
                "rule_state_components must be a non-empty ordered list or tuple.",
            )
        else:
            ordered_components = list(rule_state_components)
            for idx, component_name in enumerate(ordered_components):
                if not non_empty_string(component_name):
                    add_issue(
                        section_name,
                        stance_name,
                        f"rule_state_components[{idx}]",
                        "invalid",
                        "rule_state_components entries must be non-empty strings.",
                    )
            if len(ordered_components) != len(set(ordered_components)):
                add_issue(
                    section_name,
                    stance_name,
                    "rule_state_components",
                    "duplicate",
                    "rule_state_components must not contain duplicates.",
                )

        expected_duration_components = [
            "duration_preference",
            "duration_rate_shock",
            "inflation",
            "policy",
        ]
        if ordered_components and ordered_components != expected_duration_components:
            add_issue(
                section_name,
                stance_name,
                "rule_state_components",
                "invalid_order",
                "Duration rule-state components must be ordered as "
                "duration_preference, duration_rate_shock, inflation, policy.",
            )

        inputs = stance.get("inputs")
        if not isinstance(inputs, list) or not inputs:
            add_issue(
                section_name,
                stance_name,
                "inputs",
                "invalid",
                "inputs must be a non-empty list.",
            )
            inputs = []

        input_components = []
        for idx, item in enumerate(inputs):
            if not isinstance(item, dict):
                add_issue(
                    section_name,
                    stance_name,
                    f"inputs[{idx}]",
                    "invalid",
                    "Input item must be a mapping.",
                )
                continue
            component_col = item.get("component")
            if not non_empty_string(component_col):
                add_issue(
                    section_name,
                    stance_name,
                    f"inputs[{idx}].component",
                    "invalid",
                    "Input component must be a non-empty string.",
                )
                continue
            input_components.append(component_col)
            if component_col not in component_score_outputs:
                add_issue(
                    section_name,
                    stance_name,
                    f"inputs[{idx}].component",
                    "unknown_component_score",
                    f"Input component must refer to a component score output: {component_col}.",
                )
        if len(input_components) != len(set(input_components)):
            add_issue(
                section_name,
                stance_name,
                "inputs",
                "duplicate",
                "duration_rule_stance inputs must not contain duplicates.",
            )
        expected_duration_input_score_outputs = [
            "duration_preference_score",
            "duration_rate_shock_score",
            "inflation_pressure_score",
            "policy_stance_score",
        ]
        missing_input_components = [
            component_col
            for component_col in expected_duration_input_score_outputs
            if component_col not in input_components
        ]
        unknown_input_components = [
            component_col
            for component_col in input_components
            if component_col not in expected_duration_input_score_outputs
        ]
        for component_col in missing_input_components:
            add_issue(
                section_name,
                stance_name,
                f"inputs.{component_col}",
                "missing",
                "duration_rule_stance inputs must include every required component score output.",
            )
        for component_col in unknown_input_components:
            add_issue(
                section_name,
                stance_name,
                f"inputs.{component_col}",
                "unknown",
                "duration_rule_stance inputs contains an unknown component score output.",
            )

        state_thresholds = stance.get("state_thresholds")
        if not isinstance(state_thresholds, dict):
            add_issue(
                section_name,
                stance_name,
                "state_thresholds",
                "missing" if state_thresholds is None else "invalid",
                "state_thresholds must be a mapping.",
            )
        else:
            for key in ["positive", "negative"]:
                value = state_thresholds.get(key)
                if key not in state_thresholds:
                    add_issue(
                        section_name,
                        stance_name,
                        f"state_thresholds.{key}",
                        "missing",
                        "duration_rule_stance state_thresholds must define positive and negative.",
                    )
                elif not is_number(value):
                    add_issue(
                        section_name,
                        stance_name,
                        f"state_thresholds.{key}",
                        "invalid",
                        "duration_rule_stance state threshold values must be numeric and not bool.",
                    )
            for key in state_thresholds:
                if key not in {"positive", "negative"}:
                    add_issue(
                        section_name,
                        stance_name,
                        f"state_thresholds.{key}",
                        "unknown",
                        "Unknown duration_rule_stance state threshold key.",
                    )
            positive = state_thresholds.get("positive")
            negative = state_thresholds.get("negative")
            if is_number(positive) and is_number(negative) and negative >= positive:
                add_issue(
                    section_name,
                    stance_name,
                    "state_thresholds",
                    "invalid_order",
                    "state_thresholds.negative must be less than state_thresholds.positive.",
                )

        state_buckets = stance.get("state_buckets")
        states_by_component = []
        if not isinstance(state_buckets, dict):
            add_issue(
                section_name,
                stance_name,
                "state_buckets",
                "missing" if state_buckets is None else "invalid",
                "state_buckets must be a mapping.",
            )
        elif ordered_components:
            unknown_bucket_components = [
                component_name
                for component_name in state_buckets
                if component_name not in ordered_components
            ]
            for component_name in unknown_bucket_components:
                add_issue(
                    section_name,
                    stance_name,
                    f"state_buckets.{component_name}",
                    "unknown",
                    "state_buckets contains an unknown rule-state component.",
                )

            for component_name in ordered_components:
                component_buckets = state_buckets.get(component_name)
                field_prefix = f"state_buckets.{component_name}"
                if not isinstance(component_buckets, dict) or not component_buckets:
                    add_issue(
                        section_name,
                        stance_name,
                        field_prefix,
                        "missing" if component_buckets is None else "invalid",
                        "Each rule-state component must define a non-empty state bucket mapping.",
                    )
                    continue

                required_bucket_keys = ["positive", "neutral", "negative"]
                for bucket_key in required_bucket_keys:
                    if bucket_key not in component_buckets:
                        add_issue(
                            section_name,
                            stance_name,
                            f"{field_prefix}.{bucket_key}",
                            "missing",
                            "Each duration rule-state component must define positive, neutral, and negative state buckets.",
                        )
                for bucket_key in component_buckets:
                    if bucket_key not in required_bucket_keys:
                        add_issue(
                            section_name,
                            stance_name,
                            f"{field_prefix}.{bucket_key}",
                            "unknown",
                            "Unknown duration rule-state bucket key.",
                        )

                state_values = []
                for bucket_key, state_value in component_buckets.items():
                    if not non_empty_string(bucket_key):
                        add_issue(
                            section_name,
                            stance_name,
                            f"{field_prefix}.{bucket_key}",
                            "invalid",
                            "State bucket keys must be non-empty strings.",
                        )
                    if not non_empty_string(state_value):
                        add_issue(
                            section_name,
                            stance_name,
                            f"{field_prefix}.{bucket_key}",
                            "invalid",
                            "State bucket values must be non-empty strings.",
                        )
                    else:
                        state_values.append(state_value.strip())
                if len(state_values) != len(set(state_values)):
                    add_issue(
                        section_name,
                        stance_name,
                        field_prefix,
                        "duplicate_values",
                        "State bucket values must be unique within each rule-state component.",
                    )
                if state_values:
                    states_by_component.append(state_values)

        state_stabilization = stance.get("state_stabilization")
        if ordered_components:
            try:
                _resolve_rule_mapped_stabilization_config(
                    stance,
                    ordered_components,
                    context=f"{section_name}.{stance_name}",
                )
            except ValueError as exc:
                add_issue(
                    section_name,
                    stance_name,
                    "state_stabilization",
                    "invalid",
                    str(exc),
                )
        elif not isinstance(state_stabilization, dict):
            add_issue(
                section_name,
                stance_name,
                "state_stabilization",
                "missing" if state_stabilization is None else "invalid",
                "state_stabilization must be a mapping.",
            )

        rule_scores = stance.get("rule_scores")
        parsed_rule_scores = {}
        if not isinstance(rule_scores, dict) or not rule_scores:
            add_issue(
                section_name,
                stance_name,
                "rule_scores",
                "missing" if rule_scores is None else "invalid",
                "rule_scores must be a non-empty mapping.",
            )
        else:
            try:
                parsed_rule_scores = _parse_rule_scores_n_parts(
                    rule_scores,
                    expected_parts=4,
                    context=f"{section_name}.{stance_name}",
                )
            except ValueError as exc:
                add_issue(
                    section_name,
                    stance_name,
                    "rule_scores",
                    "invalid",
                    str(exc),
                )

        if (
            len(ordered_components) == 4
            and len(states_by_component) == 4
            and parsed_rule_scores
        ):
            expected_rule_tuples = set(product(*states_by_component))
            actual_rule_tuples = set(parsed_rule_scores)
            for rule_tuple in sorted(expected_rule_tuples - actual_rule_tuples):
                add_issue(
                    section_name,
                    stance_name,
                    f"rule_scores.{'|'.join(rule_tuple)}",
                    "missing",
                    "duration_rule_stance rule_scores must cover every configured state cross-product case.",
                )
            for rule_tuple in sorted(actual_rule_tuples - expected_rule_tuples):
                add_issue(
                    section_name,
                    stance_name,
                    f"rule_scores.{'|'.join(rule_tuple)}",
                    "unknown",
                    "duration_rule_stance rule_scores contains an unknown state cross-product case.",
                )

        labels = stance.get("labels")
        if not isinstance(labels, dict):
            add_issue(
                section_name,
                stance_name,
                "labels",
                "missing",
                "labels must be a mapping.",
            )
            labels = {}

        direction = labels.get("direction")
        if not isinstance(direction, dict):
            add_issue(
                section_name,
                stance_name,
                "labels.direction",
                "missing",
                "labels.direction must be a mapping.",
            )
            direction = {}
        for key in ["positive", "neutral", "negative"]:
            if not non_empty_string(direction.get(key)):
                add_issue(
                    section_name,
                    stance_name,
                    f"labels.direction.{key}",
                    "invalid",
                    "Direction label value must be a non-empty string.",
                )

        strength = labels.get("strength")
        if not isinstance(strength, dict):
            add_issue(
                section_name,
                stance_name,
                "labels.strength",
                "missing",
                "labels.strength must be a mapping.",
            )
            strength = {}
        for key in ["weak", "moderate", "strong"]:
            if not non_empty_string(strength.get(key)):
                add_issue(
                    section_name,
                    stance_name,
                    f"labels.strength.{key}",
                    "invalid",
                    "Strength label value must be a non-empty string.",
                )

    def validate_rule_mapped_stance_schema(section_name, stance_name, stance):
        rule_mapped = stance.get("rule_mapped")
        field_root = "rule_mapped"
        if not isinstance(rule_mapped, dict):
            add_issue(
                section_name,
                stance_name,
                field_root,
                "invalid",
                "rule_mapped must be a mapping when present.",
            )
            return

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
        optional_output_fields = {
            "raw_output",
            "stabilized_output",
            "stabilization_changed_output",
        }

        state_inputs = rule_mapped.get("state_inputs")
        ordered_names = []
        expected_state_values_by_input = []
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

            classification = state_input.get("classification")
            if classification not in supported_classifications:
                add_issue(
                    section_name,
                    stance_name,
                    f"{input_prefix}.classification",
                    "unsupported",
                    "rule_mapped classification must be threshold_state, threshold_bucket, or score_bucket.",
                )

            for output_field in optional_output_fields:
                output_name = state_input.get(output_field)
                if output_name is not None and not non_empty_string(output_name):
                    add_issue(
                        section_name,
                        stance_name,
                        f"{input_prefix}.{output_field}",
                        "invalid",
                        f"rule_mapped state input {output_field} must be a non-empty string when present.",
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
                        component_name = component_score_outputs.get(source_score)
                        component_score = components.get(component_name, {}).get(
                            "score",
                            {},
                        )
                        expected_classification, mixed_bucket_style = (
                            _rule_mapped_bucket_classification_from_score(
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
                            bucket_names_from_score(component_name, component_score),
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

        state_input_count = len(state_inputs)
        if ordered_names and len(ordered_names) == state_input_count:
            state_stabilization = rule_mapped.get("state_stabilization")
            if isinstance(state_stabilization, dict):
                try:
                    _resolve_rule_mapped_stabilization_config(
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

        rule_scores = rule_mapped.get("rule_scores")
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
                parsed_rule_scores = _parse_rule_scores_n_parts(
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

        if (
            expected_state_values_by_input
            and len(expected_state_values_by_input) == state_input_count
            and parsed_rule_scores
        ):
            expected_rule_tuples = set(product(*expected_state_values_by_input))
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

        adjustment = rule_mapped.get("adjustment")
        if adjustment is not None:
            if not isinstance(adjustment, dict):
                add_issue(
                    section_name,
                    stance_name,
                    f"{field_root}.adjustment",
                    "invalid",
                    "rule_mapped.adjustment must be a mapping when present.",
                )
            else:
                metadata_outputs = adjustment.get("metadata_outputs")
                if metadata_outputs is not None:
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
                            if not non_empty_string(output_name):
                                add_issue(
                                    section_name,
                                    stance_name,
                                    f"{field_root}.adjustment.metadata_outputs[{idx}]",
                                    "invalid",
                                    "Adjustment metadata output names must be non-empty strings.",
                                )
                                continue
                            if output_name in seen_metadata_outputs:
                                add_issue(
                                    section_name,
                                    stance_name,
                                    f"{field_root}.adjustment.metadata_outputs[{idx}]",
                                    "duplicate",
                                    "Adjustment metadata output names must be unique.",
                                )
                            seen_metadata_outputs.add(output_name)

                adjustment_output = adjustment.get("adjustment_output")
                if adjustment_output is not None and not non_empty_string(adjustment_output):
                    add_issue(
                        section_name,
                        stance_name,
                        f"{field_root}.adjustment.adjustment_output",
                        "invalid",
                        "rule_mapped adjustment_output must be a non-empty string when present.",
                    )

                config = adjustment.get("config")
                if config is not None:
                    validate_credit_spread_stance_parameters(
                        stance_name,
                        {
                            "state_buckets": {
                                state_input.get("name"): state_input.get("state_buckets")
                                for state_input in state_inputs
                                if isinstance(state_input, dict)
                                and state_input.get("classification") == "threshold_state"
                            },
                            "state_stabilization": rule_mapped.get("state_stabilization"),
                            "rule_scores": rule_mapped.get("rule_scores"),
                            "rule_adjustments": config,
                        },
                    )

    for stance_name, stance in exposure_stances.items():
        add_checked("exposure_stances", stance_name, "stance")
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
        if not (
            is_weighted_stance
            or function in known_custom_stance_functions
        ):
            add_issue(
                "exposure_stances",
                stance_name,
                "function",
                "unsupported",
                "function must be weighted_sum, one of "
                f"{sorted(known_custom_stance_functions)}.",
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
                elif not is_number(item.get("weight")):
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

        has_rule_mapped_schema = "rule_mapped" in stance

        if function == "credit_spread_stance" and not has_rule_mapped_schema:
            validate_credit_spread_stance_parameters(stance_name, stance)

        if function == "duration_rule_stance" and not has_rule_mapped_schema:
            validate_duration_rule_stance_schema(
                "exposure_stances",
                stance_name,
                stance,
            )

        if has_rule_mapped_schema:
            validate_rule_mapped_stance_schema(
                "exposure_stances",
                stance_name,
                stance,
            )

        if (
            not has_rule_mapped_schema
            and (
                stance_name == "curve_positioning"
                or function == "curve_positioning_stance"
            )
        ):
            required_stabilization_keys = {
                "curve_change",
                "curve_state",
                "curve_move_driver",
            }
            allowed_stabilization_fields = {
                "hysteresis_buffer",
                "min_state_persistence",
            }
            state_stabilization = stance.get("state_stabilization")
            if not isinstance(state_stabilization, dict):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "state_stabilization",
                    "missing" if state_stabilization is None else "invalid",
                    "Curve positioning state_stabilization must be a mapping.",
                )
            else:
                for key in sorted(required_stabilization_keys):
                    stabilization = state_stabilization.get(key)
                    field_prefix = f"state_stabilization.{key}"
                    if not isinstance(stabilization, dict):
                        add_issue(
                            "exposure_stances",
                            stance_name,
                            field_prefix,
                            "missing" if stabilization is None else "invalid",
                            "Curve state stabilization block must be a mapping.",
                        )
                        continue
                    for field in stabilization:
                        if field not in allowed_stabilization_fields:
                            add_issue(
                                "exposure_stances",
                                stance_name,
                                f"{field_prefix}.{field}",
                                "unknown",
                                "Unknown curve state stabilization field.",
                            )

                    hysteresis_buffer = stabilization.get("hysteresis_buffer")
                    if "hysteresis_buffer" not in stabilization:
                        add_issue(
                            "exposure_stances",
                            stance_name,
                            f"{field_prefix}.hysteresis_buffer",
                            "missing",
                            "Curve state stabilization hysteresis_buffer is required.",
                        )
                    elif not is_number(hysteresis_buffer) or hysteresis_buffer < 0:
                        add_issue(
                            "exposure_stances",
                            stance_name,
                            f"{field_prefix}.hysteresis_buffer",
                            "invalid",
                            "hysteresis_buffer must be numeric, not bool, and >= 0.",
                        )

                    min_state_persistence = stabilization.get(
                        "min_state_persistence"
                    )
                    if "min_state_persistence" not in stabilization:
                        add_issue(
                            "exposure_stances",
                            stance_name,
                            f"{field_prefix}.min_state_persistence",
                            "missing",
                            "Curve state stabilization min_state_persistence is required.",
                        )
                    elif (
                        not isinstance(min_state_persistence, int)
                        or isinstance(min_state_persistence, bool)
                        or min_state_persistence < 1
                    ):
                        add_issue(
                            "exposure_stances",
                            stance_name,
                            f"{field_prefix}.min_state_persistence",
                            "invalid",
                            "min_state_persistence must be an integer, not bool, and >= 1.",
                        )

                for key in state_stabilization:
                    if key not in required_stabilization_keys:
                        add_issue(
                            "exposure_stances",
                            stance_name,
                            f"state_stabilization.{key}",
                            "unknown",
                            "Unknown curve state stabilization key.",
                        )

            expected_change_buckets = curve_bucket_names.get(
                "curve_change",
                bucket_names_from_score(
                    "curve_change",
                    components.get("curve_change", {}).get("score", {}),
                ),
            )
            expected_state_buckets = curve_bucket_names.get(
                "curve_state",
                bucket_names_from_score(
                    "curve_state",
                    components.get("curve_state", {}).get("score", {}),
                ),
            )
            expected_driver_buckets = curve_bucket_names.get(
                "curve_move_driver",
                bucket_names_from_score(
                    "curve_move_driver",
                    components.get("curve_move_driver", {}).get("score", {}),
                ),
            )
            expected_rule_keys = {
                f"{change_bucket}|{state_bucket}|{driver_bucket}"
                for change_bucket in expected_change_buckets
                for state_bucket in expected_state_buckets
                for driver_bucket in expected_driver_buckets
            }
            rule_scores = stance.get("rule_scores")
            if not isinstance(rule_scores, dict):
                add_issue(
                    "exposure_stances",
                    stance_name,
                    "rule_scores",
                    "missing" if rule_scores is None else "invalid",
                    "Curve positioning rule_scores must be a mapping.",
                )
                rule_scores = {}
            else:
                actual_keys = set(rule_scores)
                if expected_rule_keys and actual_keys != expected_rule_keys:
                    for key in sorted(expected_rule_keys - actual_keys):
                        add_issue(
                            "exposure_stances",
                            stance_name,
                            f"rule_scores.{key}",
                            "missing",
                            "Curve positioning rule_scores must include every configured bucket cross-product key.",
                        )
                    for key in sorted(actual_keys - expected_rule_keys):
                        add_issue(
                            "exposure_stances",
                            stance_name,
                            f"rule_scores.{key}",
                            "unknown",
                            "Curve positioning rule_scores contains an unknown bucket cross-product key.",
                        )
                for key, value in rule_scores.items():
                    if not is_number(value):
                        add_issue(
                            "exposure_stances",
                            stance_name,
                            f"rule_scores.{key}",
                            "invalid",
                            "Curve positioning rule score values must be numeric and not bool.",
                        )

    if draft_exposure_stances:
        for stance_name, stance in draft_exposure_stances.items():
            add_checked("draft_exposure_stances", stance_name, "stance")
            if not isinstance(stance, dict):
                add_issue(
                    "draft_exposure_stances",
                    stance_name,
                    "definition",
                    "invalid",
                    "Draft exposure stance definition must be a mapping.",
                )
                continue

            function = stance.get("function")
            if function not in known_draft_stance_functions:
                add_issue(
                    "draft_exposure_stances",
                    stance_name,
                    "function",
                    "unsupported",
                    "Draft exposure stance function must be one of "
                    f"{sorted(known_draft_stance_functions)}.",
                )
                continue

            if function == "duration_rule_stance":
                validate_duration_rule_stance_schema(
                    "draft_exposure_stances",
                    stance_name,
                    stance,
                )

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


def _parse_rule_scores_n_parts(
    rule_scores: Mapping,
    *,
    expected_parts: int,
    context: str = "Rule-mapped stance",
) -> dict[tuple[str, ...], float]:
    if (
        not isinstance(expected_parts, int)
        or isinstance(expected_parts, bool)
        or expected_parts < 1
    ):
        raise ValueError("expected_parts must be an integer >= 1.")
    if not isinstance(rule_scores, Mapping) or not rule_scores:
        raise ValueError(f"{context} rule_scores must be a non-empty mapping.")

    parsed_scores = {}
    for case_key, score in rule_scores.items():
        if not isinstance(case_key, str):
            raise ValueError(f"{context} rule score keys must be strings.")

        parts = tuple(part.strip() for part in case_key.split("|"))
        if len(parts) != expected_parts:
            raise ValueError(
                f"{context} rule score key must have exactly "
                f"{expected_parts} part(s): {case_key}"
            )
        if any(part == "" for part in parts):
            raise ValueError(
                f"{context} rule score key contains an empty part: {case_key}"
            )
        if parts in parsed_scores:
            raise ValueError(
                f"{context} rule score key duplicates an existing case after "
                f"normalization: {case_key}"
            )
        if isinstance(score, bool) or not isinstance(score, Real):
            raise ValueError(
                f"{context} rule score value must be numeric and not bool: "
                f"{case_key}"
            )

        parsed_scores[parts] = float(score)

    return parsed_scores


def _rule_mapped_bucket_classification_from_score(
    score: Mapping,
) -> tuple[str | None, bool]:
    buckets = score.get("buckets") if isinstance(score, Mapping) else None
    if not isinstance(buckets, Mapping) or not buckets:
        return None, False

    range_fields = {"min", "max", "min_exclusive", "max_exclusive"}
    has_range_rule = False
    has_score_rule = False
    for rule in buckets.values():
        if not isinstance(rule, Mapping):
            continue
        if set(rule).intersection(range_fields):
            has_range_rule = True
        if "score" in rule:
            has_score_rule = True

    if has_range_rule and has_score_rule:
        return None, True
    if has_range_rule:
        return "threshold_bucket", False
    if has_score_rule:
        return "score_bucket", False
    return None, False


def _resolve_rule_mapped_stabilization_config(
    stance_config: dict,
    required_state_components,
    *,
    context: str = "Rule-mapped stance",
) -> dict:
    if not isinstance(stance_config, Mapping):
        raise ValueError(f"{context} stance config must be a mapping.")
    if isinstance(required_state_components, str) or not isinstance(
        required_state_components,
        (list, tuple, set),
    ):
        raise ValueError(
            f"{context} required state components must be a sequence."
        )
    if not required_state_components:
        raise ValueError(
            f"{context} required state components must not be empty."
        )
    for component_name in required_state_components:
        if not isinstance(component_name, str) or component_name.strip() == "":
            raise ValueError(
                f"{context} required state components must be non-empty strings."
            )
    if len(set(required_state_components)) != len(required_state_components):
        raise ValueError(
            f"{context} required state components must not contain duplicates."
        )

    configured = stance_config.get("state_stabilization")
    if not isinstance(configured, dict):
        raise ValueError(f"{context} state_stabilization must be a mapping.")
    for component_name in configured:
        if not isinstance(component_name, str) or component_name.strip() == "":
            raise ValueError(
                f"{context} state_stabilization component keys must be "
                "non-empty strings."
            )
    required_component_set = set(required_state_components)
    unknown_components = sorted(set(configured) - required_component_set)
    if unknown_components:
        raise ValueError(
            f"{context} state_stabilization contains unknown component(s): "
            f"{unknown_components}"
        )

    resolved = {}
    for component_name in required_state_components:
        component_config = configured.get(component_name)
        if not isinstance(component_config, dict):
            raise ValueError(
                f"{context} state_stabilization.{component_name} must be a mapping."
            )
        allowed_fields = {"hysteresis_buffer", "min_state_persistence"}
        for field_name in component_config:
            if not isinstance(field_name, str) or field_name.strip() == "":
                raise ValueError(
                    f"{context} state_stabilization.{component_name} field "
                    "names must be non-empty strings."
                )
        unknown_fields = sorted(set(component_config) - allowed_fields)
        if unknown_fields:
            raise ValueError(
                f"{context} state_stabilization.{component_name} contains "
                f"unknown field(s): {unknown_fields}"
            )

        if "hysteresis_buffer" not in component_config:
            raise ValueError(
                f"{context} state_stabilization.{component_name}.hysteresis_buffer is required."
            )
        hysteresis_buffer = component_config["hysteresis_buffer"]
        if (
            isinstance(hysteresis_buffer, bool)
            or not isinstance(hysteresis_buffer, Real)
            or hysteresis_buffer < 0
        ):
            raise ValueError(
                f"{context} state_stabilization.{component_name}.hysteresis_buffer "
                "must be numeric, not bool, and >= 0."
            )

        if "min_state_persistence" not in component_config:
            raise ValueError(
                f"{context} state_stabilization.{component_name}.min_state_persistence is required."
            )
        min_state_persistence = component_config["min_state_persistence"]
        if (
            not isinstance(min_state_persistence, int)
            or isinstance(min_state_persistence, bool)
            or min_state_persistence < 1
        ):
            raise ValueError(
                f"{context} state_stabilization.{component_name}.min_state_persistence "
                "must be an integer, not bool, and >= 1."
            )

        resolved[component_name] = {
            "hysteresis_buffer": float(hysteresis_buffer),
            "min_state_persistence": int(min_state_persistence),
        }

    return resolved
