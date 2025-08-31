import pytest
import json

from pathlib import Path

from api.stac.optimizer import param_cardinalities, param_factors

test_dir = Path(__file__).parent
json_path = test_dir / "example_valid_template.json"

# @pytest.fixture
# def example_optimizer():
#     template_updater = TemplateUpdater.from_json(path=json_path)
#     return TemplateOptimizer(template_updater=template_updater, budget=400)


@pytest.fixture
def example_state():
    data = json.loads(json_path.read_text())
    return data["parameters"]


def test_param_cardinalities(example_state):
    cardinalities = param_cardinalities(example_state)
    assert cardinalities == {
        "day": 15,
        "year": 10,
        "month": 8,
        "daily_statistic": 3,
        "variable": 3,
        "product_type": 1,
        "frequency": 1,
        "time_zone": 1,
    }


def test_param_factors(example_state):
    cardinalities, factors = param_factors(example_state)
    assert factors == {
        "day": 3,
        "year": 2,
        "month": 2,
        "daily_statistic": 3,
        "variable": 3,
    }
    assert cardinalities == {
        "day": 15,
        "year": 10,
        "month": 8,
        "daily_statistic": 3,
        "variable": 3,
        "product_type": 1,
        "frequency": 1,
        "time_zone": 1,
    }
