class Module1Calculator:
    """
    Future owner of the Module 1 runtime pipeline.

    This skeleton intentionally does not execute or move the existing
    RegimeModule calculation flow yet. Later split steps are expected to move
    ownership of:
    - Module 1 config and input data loading;
    - default horizon and horizon override resolution;
    - feature calculation;
    - component score calculation;
    - component label calculation;
    - stance score calculation;
    - exposure stance calculation;
    - Module1Result production.

    Current RegimeModule initialization/config/data fields expected to move
    here in later steps include:
    - fred, series_config_path, module1_config_path, data_path;
    - series_config, data, module1_config, module1_config_validation;
    - feature_config, component_config, exposure_stance_config;
    - default_horizons, horizon_overrides, horizons;
    - features, scores, labels, stance_scores, exposure_stance.

    Historical review, plotting, tracing, sensitivity diagnostics, and
    target-context analysis remain outside this skeleton boundary.
    """

    pass
