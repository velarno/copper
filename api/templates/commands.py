from tempfile import gettempdir
from pathlib import Path
import typer

from cdsapi import Client
from typing import Optional
from rich.console import Console
from api.stac.crud import CollectionBrowser, TemplateUpdater
from api.stac.utils import models_to_json, models_to_table
from api.stac.config import OutputFormat

console = Console()

# Template management subapp
app = typer.Typer(
    name="template",
    help="Template management commands",
)

@app.command(
    name="list",
    help="List all templates",
)
def list(
    format: OutputFormat = typer.Option(OutputFormat.json, "--format", "-f", help="Output format"),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", help="Limit the number of templates to list"),
):
    templates = TemplateUpdater.list(limit)
    match format:
        case OutputFormat.json:
            console.print_json(models_to_json(templates))
        case OutputFormat.table:
            table = models_to_table(templates)
            console.print(table)
        case _:
            raise ValueError(f"Invalid format: {format}")

@app.command(
    name="new",
    help="Create a new template",
)
def new(
    dataset_id: str = typer.Argument(..., help="Dataset ID"),
    template_name: str = typer.Argument(..., help="Template name"),
    ):
    template_updater = TemplateUpdater(template_name, dataset_id)
    template_updater.commit()
    console.print_json(template_updater.to_json())

@app.command(
    name="add",
    help="Add a parameter to a template",
)
def add(
    template_name: str = typer.Argument(..., help="Template name"),
    parameter_name: str = typer.Argument(..., help="Parameter name"),
    parameter_value: Optional[str] = typer.Option(None, "--value", "-v", help="Parameter value"),
    parameter_range: Optional[str] = typer.Option(None, "--range", "-r", help="Parameter range, format: from-to"),
):
    template_updater = TemplateUpdater(template_name)
    if parameter_range:
        from_value, to_value = parameter_range.split("-")
        template_updater.add_parameter_range(parameter_name, from_value, to_value)
    elif parameter_value:
        template_updater.add_parameter(parameter_name, parameter_value)
    else:
        raise typer.BadParameter("Either --value or --range must be provided")
    template_updater.commit()
    console.print_json(template_updater.to_json())

@app.command(
    name="update",
    help="Update a parameter in a template",
)
def update(
    template_name: str = typer.Argument(..., help="Template name"),
    parameter_name: str = typer.Argument(..., help="Parameter name"),
    old_value: str = typer.Argument(..., help="Old parameter value"),
    new_value: str = typer.Argument(..., help="New parameter value"),
):
    template_updater = TemplateUpdater(template_name)
    template_updater.update_parameter(parameter_name, old_value, new_value)
    template_updater.commit()
    console.print_json(template_updater.to_json())

@app.command(
    name="remove",
    help="Remove a parameter from a template",
)
def remove(
    template_name: str = typer.Argument(..., help="Template name"),
    parameter_name: str = typer.Argument(..., help="Parameter name"),
):
    template_updater = TemplateUpdater(template_name)
    template_updater.remove_parameter(parameter_name)
    template_updater.commit()
    console.print_json(template_updater.to_json())

@app.command(
    name="show",
    help="Show a template",
)
def show(
    template_name: str = typer.Argument(..., help="Template name"),
):
    template_updater = TemplateUpdater(template_name)
    console.print_json(template_updater.to_json())

@app.command(
    name="parameters",
    help="Show the parameters of a template",
)
def parameters(
    template_name: str = typer.Argument(..., help="Template name"),
    hide_values: bool = typer.Option(False, "--hide-values", "-V", help="Hide parameter values"),
    format: OutputFormat = typer.Option(OutputFormat.json, "--format", "-f", help="Output format"),
):
    template_updater = TemplateUpdater(template_name)
    match format:
        case OutputFormat.json:
            console.print_json(models_to_json(template_updater.allowed_parameters(hide_values)))
        case OutputFormat.table:
            table = models_to_table(template_updater.allowed_parameters(hide_values))
            console.print(table)
        case _:
            raise ValueError(f"Invalid format: {format}")

@app.command(
    name="cost",
    help="Calculate the cost of a template",
)
def cost(
    template_name: str = typer.Argument(..., help="Template name"),
):
    template_updater = TemplateUpdater(template_name)
    cost = template_updater._estimate_cost()
    console.print(cost)

@app.command(
    name="delete",
    help="Delete a template",
)
def delete(
    template_name: str = typer.Argument(..., help="Template name"),
):
    template_updater = TemplateUpdater(template_name)
    template_updater.delete()

@app.command(
    name="history",
    help="Show the history of a template",
)
def history(
    template_name: str = typer.Argument(..., help="Template name"),
):
    template_updater = TemplateUpdater(template_name)
    history = template_updater.fetch_latest_history()
    console.print_json(models_to_json([history]))

@app.command(
    name="mandatory",
    help="Show the mandatory parameters of a template",
)
def mandatory(
    template_name: str = typer.Argument(..., help="Template name"),
):
    template_updater = TemplateUpdater(template_name)
    browser = CollectionBrowser(template_updater.dataset_id)
    console.print('\n'.join(browser.mandatory_parameters))

default_output_dir = Path(gettempdir()) / "cds_download"

@app.command(
    name="download",
    help="Download a dataset using a template",
)
def download(
    template_name: str = typer.Argument(..., help="Template name"),
    output_dir: Path = typer.Option(default_output_dir, "--output-dir", "-o", help="Output directory", dir_okay=True),
):
    template_updater = TemplateUpdater(template_name)
    client = Client()
    client.retrieve(template_updater.dataset_id, template_updater.to_dict()).download(output_dir)