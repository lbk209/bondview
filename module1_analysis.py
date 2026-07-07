import pandas as pd

from module1_result import Module1Result


class Module1Analysis:
    def __init__(self, result: Module1Result):
        self.result = result

    def _first_valid_dates_by_column(self, table: pd.DataFrame | None) -> pd.Series | None:
        if table is None:
            return None

        return table.apply(lambda col: col.first_valid_index())

    def _latest_valid_dates_by_column(self, table: pd.DataFrame | None) -> pd.Series | None:
        if table is None:
            return None

        return table.apply(lambda col: col.last_valid_index())

    def _label_distributions(self, table: pd.DataFrame | None) -> dict | None:
        if table is None:
            return None

        distributions = {}

        for col in table.columns:
            counts = table[col].dropna().value_counts()
            if not counts.empty:
                distributions[col] = counts

        return distributions

    def inspect_module1_results(self, n=10) -> dict:
        """
        Inspect completed Module 1 result outputs for sanity checking.
        """
        tables = {
            "features": self.result.features,
            "scores": self.result.scores,
            "labels": self.result.labels,
            "exposure_stance": self.result.exposure_stance,
        }

        combined_parts = [
            table
            for table in [
                self.result.scores,
                self.result.labels,
                self.result.exposure_stance,
            ]
            if table is not None
        ]
        recent_combined_snapshot = (
            None if not combined_parts else pd.concat(combined_parts, axis=1).tail(n)
        )

        exposure_label_cols = None

        if self.result.exposure_stance is not None:
            exposure_label_cols = [
                col
                for col in self.result.exposure_stance.columns
                if not pd.api.types.is_numeric_dtype(self.result.exposure_stance[col])
            ]

        latest_complete_exposure_stance_date = None

        if self.result.exposure_stance is not None:
            complete_exposure = self.result.exposure_stance.dropna(how="any")
            if not complete_exposure.empty:
                latest_complete_exposure_stance_date = complete_exposure.index.max()

        review = {
            "recent_combined_snapshot": recent_combined_snapshot,
            "recent_scores": (
                None if self.result.scores is None else self.result.scores.tail(n)
            ),
            "recent_labels": (
                None if self.result.labels is None else self.result.labels.tail(n)
            ),
            "recent_exposure_stance": (
                None
                if self.result.exposure_stance is None
                else self.result.exposure_stance.tail(n)
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
                name: self._first_valid_dates_by_column(table)
                for name, table in tables.items()
            },
            "latest_valid_dates": {
                name: self._latest_valid_dates_by_column(table)
                for name, table in tables.items()
            },
            "latest_dates": {
                name: None
                if table is None or table.dropna(how="all").empty
                else table.dropna(how="all").index.max()
                for name, table in tables.items()
            },
            "latest_complete_exposure_stance_date": latest_complete_exposure_stance_date,
            "component_label_distributions": self._label_distributions(
                self.result.labels
            ),
            "exposure_stance_label_distributions": (
                None
                if self.result.exposure_stance is None or not exposure_label_cols
                else self._label_distributions(
                    self.result.exposure_stance[exposure_label_cols]
                )
            ),
        }

        return review
