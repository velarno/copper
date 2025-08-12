import typer

from rich.console import Console
from api.stac.crud import TemplateUpdater
from api.stac.utils import models_to_json

console = Console()

# Template management subapp
app = typer.Typer(
    name="template",
    help="Template management commands",
)

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
    parameter_value: str = typer.Argument(..., help="Parameter value"),
):
    template_updater = TemplateUpdater(template_name)
    template_updater.add_parameter(parameter_name, parameter_value)
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
):
    template_updater = TemplateUpdater(template_name)
    console.print_json(models_to_json(template_updater.allowed_parameters()))

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
    console.print_json(models_to_json(history))