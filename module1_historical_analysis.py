import warnings
from dataclasses import replace
from numbers import Real
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml

from module1_analysis import Module1Analysis, TargetCompareDataset, TargetContextResult
from module1_calculator import Module1Result


class Module1HistoricalAnalysis:
    def __init__(
        self,
        result: Module1Result,
        historical_context: dict | None = None,
        historical_cases: pd.DataFrame | None = None,
        historical_expected_label_validation: dict | None = None,
    ):
        self.result = result
        self.analysis = Module1Analysis(result)
        self.data = result.data
        self.features = result.features
        self.scores = result.scores
        self.labels = result.labels
        self.stance_scores = result.stance_scores
        self.exposure_stance = result.exposure_stance
        self.module1_config = result.module1_config
        self.feature_config = result.feature_config
        self.component_config = result.component_config
        self.exposure_stance_config = result.exposure_stance_config
        self.horizons = result.horizons
        self.default_horizons = result.default_horizons
        self.horizon_overrides = result.horizon_overrides
        self.module1_config_validation = result.module1_config_validation
        self.historical_context = historical_context
        self.historical_cases = historical_cases
        self.historical_expected_label_validation = (
            historical_expected_label_validation
        )

    def _load_yaml_config(self, path) -> dict:
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError(f"YAML config must be a mapping: {path}")

        return config

    def _resolve_target(self, target: str, level: str | None, allow_group: bool = False):
        return self.analysis.resolve_target(target, level, allow_group=allow_group)

    def resolve_historical_event_window(self, context_id=None, start=None, end=None):
        """Resolve one historical context ID to an explicit event window."""
        if context_id is None:
            return start, end
        if self.historical_context is None:
            raise ValueError("Run load_historical_context() before resolving context_id.")

        events = self.historical_context.get("events")
        if events is None or events.empty:
            raise ValueError("historical_context events are not loaded.")

        matched = events[events["context_id"] == context_id]
        if matched.empty:
            raise ValueError(f"Unknown historical context_id: {context_id}")
        if len(matched) > 1:
            raise ValueError(f"Historical context_id must be unique: {context_id}")

        row = matched.iloc[0]
        resolved_start = row["start"] if start is None else start
        resolved_end = row["end"] if end is None else end
        return resolved_start, resolved_end

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
        start, end = self.resolve_historical_event_window(
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
        start, end = self.resolve_historical_event_window(
            context_id=context_id,
            start=start,
            end=end,
        )
        dataset = self.analysis.build_target_comparison_dataset(
            target=target,
            level=level,
            compare=compare,
            start=start,
            end=end,
            include_labels=include_labels,
            include_strength=include_strength,
            ffill_inputs=ffill_inputs,
        )
        if context_id is not None:
            dataset = replace(dataset, context_id=context_id)
        return dataset

    def raw_inputs_for_target(self, target: str, level: str) -> list[str]:
        return self.analysis.raw_inputs_for_target(target, level)

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
            context_start, context_end = self.resolve_historical_event_window(
                context_id
            )
            context_start = pd.to_datetime(context_start)
            context_end = pd.to_datetime(context_end)
            case_df.attrs["start"] = context_start
            case_df.attrs["end"] = context_end

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
