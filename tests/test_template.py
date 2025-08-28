import pytest

from pathlib import Path

from api.stac.crud import TemplateUpdater, is_catalog_loaded
from api.stac.optimizer import TemplateOptimizer

test_dir = Path(__file__).parent

json_path = test_dir / "example_template.json"
template_updater = TemplateUpdater.from_json(json_data=json_path.read_text())


@pytest.fixture
def sample_template():
    return template_updater.template


@pytest.fixture
def sample_template_updater():
    return template_updater


@pytest.mark.critical
def test_is_catalog_loaded():
    assert is_catalog_loaded()


def test_load_json_template(sample_template_updater):
    template_updater = sample_template_updater
    assert template_updater.template_name == "test_template"
    assert template_updater.dataset_id == "derived-era5-single-levels-daily-statistics"
    assert len(template_updater.parameter_names) == 5
    assert template_updater.template_exists
    assert template_updater.cost == 1800


def test_add_remove_parameter(sample_template_updater):
    template_updater = sample_template_updater
    template_updater.add_parameter("test_parameter", "test_value")
    assert "test_parameter" in template_updater.parameter_names

    template_updater.remove_parameter("test_parameter")
    assert "test_parameter" not in template_updater.parameter_names


def test_remove_parameter_values_update_cost(sample_template_updater):
    template_updater = sample_template_updater
    assert template_updater.cost == 1800
    template_updater.remove_parameter_value("year", "2013")
    assert template_updater.cost == 1620
    template_updater.add_parameter("year", "2013")
    assert template_updater.cost == 1800


def test_template_optimizer(sample_template_updater):
    template_updater = sample_template_updater
    optimizer = TemplateOptimizer(template_updater=template_updater, budget=400)
    templates = optimizer.ensure_budget("year")
    assert len(templates) > 0
    assert not (any(optimizer.cost(template) > 400 for template in templates))


def test_delete_template(sample_template_updater):
    template_updater = sample_template_updater
    template_updater.delete()
    assert not template_updater.template_exists
