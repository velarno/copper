import typer
from typing import Optional

import api.stac.utils as stac_utils
from storage.datasets import connect_to_database, are_tables_initialized, initialize_database

app = typer.Typer(
    name="stac",
    help="STAC API commands",
    no_args_is_help=True,
)

@app.command(
    name="init",
    help="Initialize the STAC tables",
)
def init():
    con = connect_to_database()
    if not are_tables_initialized(con):
        initialize_database()
        typer.echo("STAC tables initialized")
    else:
        typer.echo("Tables are already initialized")

@app.command(
    name="fetch",
    help="Fetch links from the Copernicus STAC API (catalogue endpoint)",
)
def fetch(
    dry_run: bool = typer.Option(False, help="Dry run, do not store data in the database"),
    ):
    con = connect_to_database()
    if not are_tables_initialized(con):
        typer.echo("Tables are not initialized, run `copper stac init` or `copper datasets init` first")
        raise typer.Exit(1)
    links = stac_utils.fetch_collection_links()
    if not dry_run:
        stac_utils.store_collection_links(links)
    else:
        typer.echo(f"Found {len(links)} links")
        for link in links:
            typer.echo(f"  {link['rel']}: {link['href']}")

@app.command(
    name="fetch-collections",
    help="Fetch collection data from the Copernicus STAC API",
)
def fetch_collection(
    collection_url: Optional[str] = typer.Option(None, "--collection-url", "-c", help="Collection URL"),
    fetch_all: bool = typer.Option(False, "--all", "-A", help="Fetch all collections"),
    dry_run: bool = typer.Option(False, help="Dry run, do not store data in the database"),
):
    if fetch_all:
        stac_utils.fetch_all_collections()
    else:
        collection_info, links, keywords = stac_utils.fetch_collection_data(collection_url)
        if not dry_run:
            stac_utils.store_collection_data(collection_info, links, keywords)