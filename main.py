import typer

from browse.commands import app as browse
from api.commands import app as api

cli = typer.Typer(
    name="copper",
    help="Copernicus Data Fetcher & Browser",
    add_completion=True,
    rich_markup_mode="rich",
)

cli.add_typer(browse, name="browse", help="Browse Copernicus datasets (data & metadata)")
cli.add_typer(browse, name="br", hidden=True)
cli.add_typer(api, name="api", help="Interact with Copernicus APIs and download data")

@cli.callback(invoke_without_command=True)
def default():
  typer.echo("Use --help to see available commands")
  raise typer.Exit(0)

if __name__ == "__main__":
  cli()