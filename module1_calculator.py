import os
import warnings
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv
from fredapi import Fred

from module1_schema import validate_module1_config


@dataclass
class FredSeries:
    fred_id: str
    name: str
    description: str
    expected_frequency: str  # "daily" or "monthly"


class Module1Calculator:
    """
    Future owner of the Module 1 runtime pipeline.

    This class now owns the safest mechanical setup responsibilities:
    config/input paths, FRED client setup, core input loading, Module 1 config
    loading, config validation storage, and horizon resolution.

    Core runtime calculation remains in RegimeModule for this migration step.
    Later split steps are expected to move feature calculation, component score
    calculation, component label calculation, stance score calculation, exposure
    stance calculation, and Module1Result production here.
    """

    def __init__(
        self,
        api_key_env="FRED_API_KEY",
        series_config_path="data/fred_series_config.csv",
        module1_config_path="data/module1_config.yaml",
        data_path="data/raw_data_19980101_20260508.csv",
        horizons=None,
    ):
        """
        Initialize Module 1 setup state and load the core input files.

        The constructor preserves the previous RegimeModule setup behavior: it
        loads series config, module1 config, and input data, then resolves
        horizons from YAML defaults plus optional constructor overrides.
        """
        load_dotenv()

        api_key = os.getenv(api_key_env)
        if api_key is None:
            raise ValueError(f"{api_key_env} is not set.")

        self.fred = Fred(api_key=api_key)
        self.series_config_path = series_config_path
        self.module1_config_path = module1_config_path
        self.data_path = data_path
        self.series_config = None
        self.data = None
        self.module1_config = None
        self.module1_config_validation = None
        self.feature_config = None
        self.component_config = None
        self.exposure_stance_config = None
        self.default_horizons = None
        self.horizon_overrides = horizons.copy() if horizons is not None else None
        self.horizons = None

        self.load_core_files()

    def load_core_files(
        self,
        series_config_path=None,
        module1_config_path=None,
        data_path=None,
    ) -> None:
        """
        Load core Module 1 files, applying optional path overrides.

        Omitted paths use the instance's stored paths and only load missing
        state. Provided paths update the stored path attributes and reload that
        file.
        """
        if series_config_path is not None:
            self.series_config_path = series_config_path
            self.load_series_config(self.series_config_path)
        elif self.series_config is None:
            self.load_series_config(self.series_config_path)

        if module1_config_path is not None:
            self.module1_config_path = module1_config_path
            self.load_module1_config(self.module1_config_path)
        elif self.module1_config is None:
            self.load_module1_config(self.module1_config_path)

        if data_path is not None:
            self.data_path = data_path
            self.load_data(path_from=self.data_path)
        elif self.data is None:
            self.load_data(path_from=self.data_path)

    def _default_horizons_from_config(self, config: dict | None = None) -> dict:
        config = self.module1_config if config is None else config
        if not isinstance(config, dict):
            raise ValueError("Module 1 config must be loaded before resolving horizons.")

        horizons = config.get("horizons")
        if not isinstance(horizons, dict) or not horizons:
            raise ValueError("module1_config.yaml horizons must be a non-empty mapping.")

        invalid = {
            key: value
            for key, value in horizons.items()
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0
        }
        if invalid:
            raise ValueError(
                "All configured horizon values must be positive integers. "
                f"Invalid values: {invalid}"
            )

        return horizons.copy()

    def validate_horizons(self, horizons=None, base_horizons=None) -> dict:
        """
        Return validated horizon settings.

        Base horizons come from module1_config.yaml unless base_horizons is
        provided. horizons is treated as a partial override mapping.
        """
        if base_horizons is None:
            base_horizons = self._default_horizons_from_config()
        if not isinstance(base_horizons, dict) or not base_horizons:
            raise ValueError("base_horizons must be a non-empty mapping.")

        invalid_base = {
            key: value
            for key, value in base_horizons.items()
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0
        }
        if invalid_base:
            raise ValueError(
                "All base horizon values must be positive integers. "
                f"Invalid values: {invalid_base}"
            )

        if horizons is not None and not isinstance(horizons, dict):
            raise ValueError("horizons must be a mapping of partial overrides or None.")

        unknown = set(horizons or {}).difference(base_horizons)
        if unknown:
            raise ValueError(f"Unknown horizon keys: {sorted(unknown)}")

        resolved = base_horizons.copy()
        resolved.update(horizons or {})

        invalid = {
            key: value
            for key, value in resolved.items()
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0
        }
        if invalid:
            raise ValueError(
                f"All horizon values must be positive integers. Invalid values: {invalid}"
            )

        return resolved

    def update_horizons(self, horizons: dict | None = None) -> dict:
        """
        Apply instance-level horizon overrides over YAML defaults.

        If horizons are updated after features, scores, or stances have been
        calculated, rerun calculate_features() and downstream steps, or rerun
        the full pipeline.
        """
        if self.default_horizons is None:
            self.default_horizons = self._default_horizons_from_config()

        if horizons is None:
            self.horizon_overrides = None
        else:
            self.horizon_overrides = horizons.copy()

        self.horizons = self.validate_horizons(
            self.horizon_overrides,
            base_horizons=self.default_horizons,
        )
        return self.horizons

    def load_series_config(self, path="data/fred_series_config.csv") -> dict:
        df = pd.read_csv(path)

        self.series_config = {
            row["key"]: FredSeries(
                fred_id=row["fred_id"],
                name=row["name"],
                description=row["description"],
                expected_frequency=row["expected_frequency"],
            )
            for _, row in df.iterrows()
        }

        return self.series_config

    def download_series(self, key: str, start=None, end=None) -> pd.Series | None:
        cfg = self.series_config[key]

        try:
            sr = self.fred.get_series(
                cfg.fred_id,
                observation_start=start,
                observation_end=end,
            )
        except Exception as e:
            print(f"[ERROR] Failed to download {key} ({cfg.fred_id}): {e}")
            return None

        if sr is None or len(sr) == 0:
            print(f"[WARN] No data for {key} ({cfg.fred_id})")
            return None

        sr.name = key
        print(
            f"[OK] {key:<10} | {cfg.fred_id} | "
            f"{sr.index.min().date()} ~ {sr.index.max().date()}"
        )

        return sr

    def check_frequency_sanity(self, key: str, sr: pd.Series) -> None:
        cfg = self.series_config[key]

        median_gap = sr.index.to_series().diff().median().days

        if cfg.expected_frequency == "monthly":
            if median_gap < 25 or median_gap > 35:
                print(f"[WARN] {key} expected monthly, median gap = {median_gap} days")

        elif cfg.expected_frequency == "daily":
            if median_gap > 7:
                print(
                    f"[WARN] {key} expected daily/business-daily, "
                    f"median gap = {median_gap} days"
                )

    def load_local_data(self, path_from, start=None, end=None) -> pd.DataFrame:
        """
        Load previously saved input data from a local CSV file.

        The loaded data must contain all columns defined in self.series_config.
        The index is parsed as datetime, sorted, and filtered by start/end.
        """
        if self.series_config is None:
            raise ValueError("Run load_series_config() before load_local_data().")

        path = Path(path_from)

        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")

        df = pd.read_csv(path, index_col=0, parse_dates=True)

        missing = pd.Index(self.series_config.keys()).difference(df.columns)
        if missing.size > 0:
            missing = ", ".join(missing)
            raise ValueError(f"Data columns unavailable: {missing}")

        df = df.sort_index()

        if start is not None:
            df = df.loc[df.index >= start]
        if end is not None:
            df = df.loc[df.index <= end]

        return df

    def load_data(self, path_from=None, start=None, end=None) -> pd.DataFrame:
        """
        Download FRED input data, or load it from a local CSV file.
        """
        if self.series_config is None:
            raise ValueError("Run load_series_config() before load_data().")

        start = pd.to_datetime(start) if start is not None else None
        end = pd.to_datetime(end) if end is not None else None
        if start is not None and end is not None and start > end:
            raise ValueError("start must be earlier than or equal to end.")

        if path_from is not None:
            df = self.load_local_data(path_from, start=start, end=end)
        else:
            data = {}

            for key in self.series_config:
                sr = self.download_series(key, start=start, end=end)

                if sr is not None:
                    self.check_frequency_sanity(key, sr)
                    data[key] = sr

            if not data:
                raise ValueError("No FRED data downloaded.")

            df = pd.concat(data.values(), axis=1)
            df = df.sort_index()  # no global ffill

        self.data = df
        return df

    def _load_yaml_config(self, path) -> dict:
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError(f"YAML config must be a mapping: {path}")

        return config

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
        config = self._load_yaml_config(path)

        validation = None
        if validate_config:
            validation = validate_module1_config(config)
            issues = validation["issues"]
            self.module1_config_validation = validation
            if not issues.empty:
                message = (
                    "Invalid module1_config.yaml: "
                    f"{len(issues)} validation issue(s). Inspect "
                    'self.module1_config_validation["issues"].'
                )
                if raise_on_invalid_config:
                    raise ValueError(message)
                warnings.warn(message, UserWarning)

        self.module1_config = config
        self.default_horizons = self._default_horizons_from_config(config)
        self.horizons = self.validate_horizons(
            self.horizon_overrides,
            base_horizons=self.default_horizons,
        )
        self.feature_config = {"features": config["features"]}
        self.component_config = {"components": config["components"]}
        self.exposure_stance_config = {
            "stance_label_rules": config["stance_label_rules"],
            "exposure_stances": config["exposure_stances"],
        }
        if validate_config:
            self.module1_config_validation = validation

        return config
