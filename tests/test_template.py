import pytest

from pathlib import Path

from api.stac.crud import TemplateUpdater

test_dir = Path(__file__).parent


@pytest.fixture
def sample_template():
    json_path = test_dir / 'example_template.json'
    return json_path.read_text()

def test_load_json_template(sample_template):
    template_updater = TemplateUpdater.from_json(json_data=sample_template)
    assert template_updater.template_name == "test_template"
    assert template_updater.dataset_id == "derived-era5-single-levels-daily-statistics"
    assert len(template_updater.parameter_names) == 5

def test_add_remove_parameter(sample_template):
    template_updater = TemplateUpdater(template_name="test_template")
    template_updater.add_parameter("test_parameter", "test_value")
    assert "test_parameter" in template_updater.parameter_names

    template_updater.remove_parameter("test_parameter")
    assert "test_parameter" not in template_updater.parameter_names

def test_delete_template(sample_template):
    template_updater = TemplateUpdater(template_name="test_template")
    template_updater.delete()
    assert not template_updater.template_exists

