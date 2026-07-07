from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Module1Result:
    data: Any
    features: Any
    scores: Any
    labels: Any
    stance_scores: Any
    exposure_stance: Any
    module1_config: Any
    feature_config: Any
    component_config: Any
    exposure_stance_config: Any
    horizons: Any
    default_horizons: Any
    horizon_overrides: Any
    module1_config_validation: Any
