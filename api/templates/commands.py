from tempfile import gettempdir
from pathlib import Path
import typer

from cdsapi import Client
from typing import Optional
from rich.console import Console
from api.stac.crud import CollectionBrowser, TemplateUpdater
from api.stac.utils import models_to_json, models_to_table
from api.stac.config import OutputFormat, CostMethod

console = Console()

# Template management subapp
app = typer.Typer(
    name="template",
    help="Template management commands",
)

@app.command(name="ls", help="List all templates", hidden=True)
@app.command(name="list", help="List all templates (aliases: ls)")
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

@app.command(name="init", help="Initialize a new template", hidden=True)
@app.command(name="create", help="Create a new template", hidden=True)
@app.command(name="new", help="Create a new template (aliases: init, create)")
def new(
    dataset_id: str = typer.Argument(..., help="Dataset ID"),
    template_name: str = typer.Argument(..., help="Template name"),
    ):
    template_updater = TemplateUpdater(template_name, dataset_id)
    template_updater.commit()
    console.print_json(template_updater.to_json())

@app.command(name="+", hidden=True)
@app.command(name="add", help="Add a parameter to a template (aliases: +)")
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

@app.command(name="-", hidden=True)
@app.command(name="rm", hidden=True)
@app.command(name="remove", help="Remove a parameter from a template (aliases: rm, -)")
def remove(
    template_name: str = typer.Argument(..., help="Template name"),
    parameter_name: str = typer.Argument(..., help="Parameter name"),
):
    template_updater = TemplateUpdater(template_name)
    template_updater.remove_parameter(parameter_name)
    template_updater.commit()
    console.print_json(template_updater.to_json())

@app.command(name="print", help="Show a template", hidden=True)
@app.command(name="show", help="Show a template (aliases: print)")
def show(
    template_name: str = typer.Argument(..., help="Template name"),
    indent: Optional[int] = typer.Option(4, '--indent', '-i', help="JSON indentation"),
    compact: bool = typer.Option(False, "--compact", "-C", help="Compact output (overrides indent)"),
    with_metadata: bool = typer.Option(False, "--metadata", "-M", help="Include template metadata in the output"),
):
    indent = None if compact else indent
    template_updater = TemplateUpdater(template_name)
    console.print_json(template_updater.to_json(indent=indent, with_metadata=with_metadata))

@app.command(name="par", hidden=True)
@app.command(name="params", hidden=True)
@app.command(name="parameters",help="Show the parameters of a template (aliases: params, par)")
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
    method: CostMethod = typer.Option(CostMethod.local, "--method", "-m", help="Cost method"),
):
    template_updater = TemplateUpdater(template_name)
    cost = template_updater.compute_cost(method)
    console.print_json(cost.to_json())

@app.command(name="trash", help="Remove a template", hidden=True)
@app.command(name="purge", help="Remove a template", hidden=True)
@app.command(name="del", help="Delete a template", hidden=True)
@app.command(name="delete", help="Delete a template (aliases: del, purge, trash)")
def delete(
    template_name: str = typer.Argument(..., help="Template name"),
):
    template_updater = TemplateUpdater(template_name)
    template_updater.delete()

@app.command(name="log", help="Show the history of a template", hidden=True)
@app.command(name="hist", help="Show the history of a template", hidden=True)
@app.command(name="history", help="Show the history of a template (aliases: log, hist, history)")
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

@app.command(name="retrieve", help="Download a dataset using a template", hidden=True)
@app.command(name="dl", help="Download a dataset using a template", hidden=True)
@app.command(name="get", help="Download a dataset using a template", hidden=True)
@app.command(name="fetch", help="Download a dataset using a template", hidden=True)
@app.command(name="download", help="Download a dataset using a template (aliases: dl, get, fetch, retrieve)")
def download(
    template_name: str = typer.Argument(..., help="Template name"),
    output_dir: Path = typer.Option(default_output_dir, "--output-dir", "-o", help="Output directory", dir_okay=True),
):
    template_updater = TemplateUpdater(template_name)
    client = Client()
    client.retrieve(template_updater.dataset_id, template_updater.to_dict()).download(output_dir)


@app.command(name="save", help="Save a template to a JSON file", hidden=True)
@app.command(name="export", hidden=True)
@app.command(name="dump", help="Dump a template to a JSON file (aliases: export, save)")
def export(
    template_name: str = typer.Argument(..., help="Template name"),
    output_file: Path = typer.Option(..., "--output-file", "-o", help="Output file", dir_okay=False),
    indent: int = typer.Option(4, "--indent", "-i", help="Indentation level"),
    compact: bool = typer.Option(False, "--compact", "-C", help="Compact output"),
):
    template_updater = TemplateUpdater(template_name)
    indent: Optional[int] = None if compact else indent
    output_file.write_text(template_updater.to_json(indent=indent))


@app.command(name="load", help="Load a template from a JSON file", hidden=True)
@app.command(name="ingest", hidden=True)
@app.command(name="import", help="Import a template from a JSON file (aliases: ingest, load)")
def load(
    template_name: Optional[str] = typer.Option(None, "--name", "-n", help="Template name"),
    input_file: Path = typer.Option(..., "--file", "-f", help="Input file", dir_okay=False),
):
    template_updater = TemplateUpdater.from_json(input_file)
    if template_name:
        template_updater.template_name = template_name
    console.print_json(template_updater.to_json(with_metadata=False))
