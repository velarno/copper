import typer

from browse.datasets import app as datasets
from api.cds import app as cds

cli = typer.Typer(
    name="cds-data-fetcher",
    help="CDS Data Fetcher",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)

cli.add_typer(datasets, name="datasets")
cli.add_typer(cds, name="cds")


@cli.callback()
def default():
  pass

if __name__ == "__main__":
    cli()