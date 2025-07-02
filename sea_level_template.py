from enum import Enum

class SeaLevelRequest(Enum):
    LARGE = "large"
    SMALL = "small"

    @property
    def request(self):
        if self == SeaLevelRequest.LARGE:
            return sea_level_request_large
        elif self == SeaLevelRequest.SMALL:
            return sea_level_request_small

sea_level_request_large = {
    "derived_variable": ["absolute_value"],
    "product_type": ["multi_model_ensemble"],
    "multi_model_ensemble_statistic": [
        "ensemble_mean",
        "ensemble_standard_deviation",
    ],
    "statistic": [
        "1_year",
        "50th",
    ],
    "confidence_interval": [
        "best_fit",
    ],
    "period": [],
    "variable": [
        "mean_sea_level",
        "surge_level",
        "tidal_range",
        "total_water_level",
    ],
    "experiment": ["historical", "future"],
}

sea_level_request_small = {
    "derived_variable": ["absolute_change", "absolute_value", "percentage_change"],
    "product_type": ["multi_model_ensemble"],
    "period": [],
    "variable": [
        "mean_sea_level",
        "surge_level",
        "total_water_level",
    ],
    "experiment": ["historical", "future"],
    "statistic": [
        "1_year",
        "ensemble_mean",
        "ensemble_standard_deviation",
    ],
    "confidence_interval": [
        "best_fit",
    ],
    "multi_model_ensemble_statistic": [
        "ensemble_mean",
        "ensemble_standard_deviation",
    ],
}