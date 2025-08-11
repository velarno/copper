import typer

from rich.console import Console
from api.stac.crud import TemplateUpdater

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
    template_updater = TemplateUpdater(dataset_id, template_name)
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
