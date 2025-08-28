import typer

from api.stac.commands import app as stac
from api.templates.commands import app as templates

cli = typer.Typer(
    name="copper",
    help="Copernicus Data Fetcher & Browser",
    add_completion=True,
    rich_markup_mode="rich",
)
cli.add_typer(stac, name="stac", help="Interact with Copernicus STAC API")
cli.add_typer(templates, name="template", help="Manage templates (alias: `tpl`)")
cli.add_typer(templates, name="tpl", help="Manage templates", hidden=True)

if __name__ == "__main__":
    cli()
