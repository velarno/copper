import typer

from browse.commands import app as browse
from api.commands import app as api
from api.stac.commands import app as stac
from api.templates.commands import app as templates

cli = typer.Typer(
    name="copper",
    help="Copernicus Data Fetcher & Browser",
    add_completion=True,
    rich_markup_mode="rich",
)

cli.add_typer(browse, name="browse", help="Browse Copernicus datasets, data & metadata (alias: `br`)")
cli.add_typer(browse, name="br", hidden=True)
cli.add_typer(api, name="api", help="Interact with Copernicus APIs and download data")
cli.add_typer(stac, name="stac", help="Interact with Copernicus STAC API")
cli.add_typer(templates, name="template", help="Manage templates (alias: `tpl`)")
cli.add_typer(templates, name="tpl", help="Manage templates", hidden=True)

if __name__ == "__main__":
  cli()