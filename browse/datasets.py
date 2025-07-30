import typer
import json
from rich.console import Console
from rich.table import Table
from rich import box
from typing import Optional
from enum import Enum

import asyncio
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn


from browse.utils import write_datasets_to_temp, ensure_playwright_installed, scrape_datasets
from storage.datasets import (
    connect_to_database, list_datasets, search_datasets,
    fetch_dataset_by_id, initialize_database, seed_dataset_from_file
)

class OutputFormat(Enum):
    table = "table"
    json = "json"
    csv = "csv"
    tsv = "tsv"

app = typer.Typer()
console = Console()

@app.command()
def list(
    db_path: str = typer.Option("datasets.db", "--db-path", help="Path to DuckDB database")
):
    """List all available Copernicus datasets from the DuckDB database."""
    con = connect_to_database(db_path)
    datasets = list_datasets(con)
    table = Table(title="Copernicus Datasets", box=box.SIMPLE, show_lines=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold yellow")
    table.add_column("Description", style="white")
    for d in datasets:
        # d: (id, rel_link, abs_link, title, description, tags, created_at, updated_at)
        table.add_row(d[0], d[3] or "", d[4] or "")
    console.print(table)

@app.command()
def search(
    query: str = typer.Argument(..., help="Full-text search query"),
    db_path: str = typer.Option("datasets.db", "--db-path", help="Path to DuckDB database"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max results to show"),
    format: OutputFormat = typer.Option(OutputFormat.table, "--format", "-f", help="Output format"),
    limit_description: int = typer.Option(60, "--limit-description", "-L", help="Limit description to this number of characters"),
    ):
    """Full-text search Copernicus datasets using DuckDB FTS."""
    con = connect_to_database(db_path)
    results = search_datasets(con, query, limit=limit)
    if format == OutputFormat.table:
        table = Table(title=f"Search Results for '{query}'", box=box.ROUNDED, show_lines=True)
        table.add_column("Score", style="dim", width=5)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Title", style="bold yellow")
        table.add_column("Description", style="white")
        for row in results:
            table.add_row(str(round(row.score, 2)), row.id, row.title, row.description[:limit_description] + "..." if row.description else "")
        console.print(table)
    elif format == OutputFormat.json:
        json_results = [r.as_dict() for r in results]
        console.print(json.dumps(json_results, indent=2))
    elif format == OutputFormat.csv:
        console.print("Not yet supported")
        typer.Exit(1)
    elif format == OutputFormat.tsv:
        console.print("Not yet supported")
        typer.Exit(1)
    else:
        raise typer.BadParameter(f"Invalid output format: {format}")

@app.command()
def view(
    dataset_id: str = typer.Argument(..., help="Dataset ID (as in the database)"),
    db_path: str = typer.Option("datasets.db", "--db-path", help="Path to DuckDB database")
):
    """Show details and open the dataset's Copernicus web page in your browser."""
    con = connect_to_database(db_path)
    d = fetch_dataset_by_id(con, dataset_id)
    if not d:
        console.print(f"[red]Dataset not found: {dataset_id}[/red]")
        raise typer.Exit(1)
    url = d.abs_link
    if url:
        url = (
            url + "?tab=overview" if not url.endswith("?tab=overview")
            else url
        )
        console.print(f"[green]Opened:[/green] {url} (tab=overview)")
        typer.launch(url)
    else:
        console.print("[red]No URL available for this dataset.[/red]")

@app.command()
def init(
    initial_timeout: Optional[int] = typer.Option(15000, "--initial-timeout", '-I', help="Initial timeout (in ms)for the browser to load the page"),
    timeout_scroll: Optional[int] = typer.Option(500, "--timeout-scroll", '-S', help="Timeout (in ms) for the browser to scroll the page"),
    window_scroll_step: Optional[int] = typer.Option(700, "--window-scroll-step", '-W', help="Window scroll step (in px) to browse the infinite scroll page"),
    db_path: Optional[str] = typer.Option("datasets.db", "--db-path", '-D', help="Path to the local database"),
):
    """Scrape all Copernicus CDS datasets and show progress."""
    ensure_playwright_installed()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Starting scraping...", total=None)
        datasets = asyncio.run(scrape_datasets(progress, task, initial_timeout, timeout_scroll, window_scroll_step))
        progress.update(task, description=f"Done! {len(datasets)} datasets scraped.")
        progress.stop()

    datasets_file = write_datasets_to_temp(datasets)
    console.print(f"[green]Found {len(datasets)} datasets[/green] -> {datasets_file}")
    task = progress.add_task("Seeding local database...", total=None)
    con = initialize_database(db_path)
    seed_dataset_from_file(con, datasets_file)
    progress.update(task, description=f"Done! {len(datasets)} datasets seeded to {db_path}.")
    progress.stop()

if __name__ == "__main__":
    app()