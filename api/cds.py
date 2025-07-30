import cdsapi
from pathlib import Path
from typing_extensions import Annotated
import typer
import xarray as xr
import rich
import zipfile

from loading import show_progress_bar, Progress, TaskID
from sea_level_template import SeaLevelRequest


def rich_color_from_string(string: str) -> str:
    if "error" in string:
        return "bold red"
    elif "warning" in string:
        return "bold yellow"
    elif "accepted" in string or "retrieved" in string or "success" in string:
        return "bold green"
    else:
        return "magenta"


def define_progress_info_callback(progress: Progress, task: TaskID, *args, **kwargs):
    def callback(*args, **kwargs):
        if "error" in kwargs:
            progress.update(task, logs=f"[bold red]Error: {kwargs['error']} [/bold red]")
        elif "warning" in kwargs:
            progress.update(task, logs=f"[bold yellow]Warning: {kwargs['warning']} [/bold yellow]")
        elif kwargs:
            progress.update(task, logs=f"{args} {kwargs}")
        else:
            style = rich_color_from_string(args[0])
            progress.update(task, logs=f"[{style}]{args[0]}[/{style}]")
            
    return callback


def define_periods(start_period: int, end_period: int, chunk_size: int | None = None) -> list[list[str]]:
    """Define periods for the CDS API.

    Args:
        start_period (int): Start period.
        end_period (int): End period.
        chunk_size (int | None, optional): Chunk size. Defaults to None.

    Returns:
        list[list[str]]: List of periods.
    """
    periods: list[str] = [str(year) for year in range(start_period, end_period + 1)]
    if chunk_size:
        return [periods[i:i + chunk_size] for i in range(0, len(periods), chunk_size)]
    else:
        return [periods]

app = typer.Typer(
    name="cds",
    help="Manage CDS data",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode="rich",
)

@app.command(
    name="download",
    help="Download CDS data",
    no_args_is_help=True,
)
def download(
    dataset: Annotated[str, typer.Argument(..., help="CDS Dataset name")],
    start_period: Annotated[int, typer.Option("--start-period", "-s", help="Start period")] = 1950,
    end_period: Annotated[int, typer.Option("--end-period", "-e", help="End period")] = 2050,
    output_dir: Annotated[str, typer.Option("--output-dir", "-o", help="Output directory")] = "data",
    chunk_size: Annotated[int, typer.Option("--chunk-size", "-c", help="Chunk size")] = 3,
    temp_dir: Annotated[str, typer.Option("--temp-dir", "-t", help="Temporary directory")] = "/tmp/cds_download/",
    request_type: Annotated[SeaLevelRequest, typer.Option("--request-type", "-r", help="Request type")] = SeaLevelRequest.LARGE,
    ):
    periods = define_periods(start_period, end_period, chunk_size=chunk_size)

    request = request_type.request

    data_dir = Path(output_dir) / dataset
    data_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = Path(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    rich.print(f"[bold blue] 📥 Downloading data to {temp_dir}[/bold blue]")
    progress, task = show_progress_bar(len(periods))
    # TODO: add concurrent downloads
    with progress:
        client = cdsapi.Client(info_callback=define_progress_info_callback(progress, task), progress=False)
        for period in periods:
            request["period"] = period
            progress.update(task, description=f"Downloading period {min(period)} to {max(period)}")
            client.retrieve(dataset, request).download(temp_dir / f"{dataset}-{min(period)}-{max(period)}.zip")
            progress.update(task, advance=1)
    rich.print(f"[bold green] ✅ Data downloaded to {temp_dir}[/bold green]")

@app.command(
    name="extract",
    help="Extract data from downloaded files and save to parquet files",
    no_args_is_help=True,
)
def extract(dataset: Annotated[str, typer.Argument(..., help="CDS Dataset name")],
            temp_dir: Annotated[str, typer.Option("--temp-dir", "-t", help="Temporary directory")] = "/tmp/cds_download/",
            data_dir: Annotated[str, typer.Option("--data-dir", "-d", help="Data directory")] = "data",
            ):
    """Extract data from downloaded files and save to parquet files.

    Args:
        dataset (str): Dataset name.
        temp_dir (Path): Temporary directory.
        data_dir (Path): Data directory.
    """

    temp_dir = Path(temp_dir)
    data_dir = Path(data_dir)

    if not temp_dir.exists():
        rich.print("[bold red]❌ Temporary directory does not exist[/bold red]")
        typer.Exit(1)
    
    data_dir.mkdir(parents=True, exist_ok=True)
    
    downloaded_files = list(temp_dir.glob(f"{dataset}*.zip"))

    if len(downloaded_files) == 0:
        rich.print("[bold red]❌ No data downloaded[/bold red]")
        typer.Exit(1)

    progress, task = show_progress_bar(len(downloaded_files))
    with progress:
        for file in downloaded_files:
            progress.update(task, description=f"Extracting: {file}")
            with zipfile.ZipFile(file, "r") as zip_ref:
                zip_ref.extractall(temp_dir / file.stem)

            nc_files = list((temp_dir / file.stem).glob("*.nc"))

            if len(nc_files) == 0:
                rich.print("[bold red]❌ No data extracted[/bold red]")
                typer.Exit(1)

            for nc_file in nc_files:
                with xr.open_dataset(nc_file) as ds:
                    progress.update(task, description=f"Processing: {nc_file}")
                    df = ds.to_dataframe()
                    time_unique = df.index.get_level_values("time").unique()
                    year = time_unique[0].year
                    df_flat = df.droplevel(level=0).reset_index()
                    df_flat["year"] = year
                    df_flat.to_parquet(data_dir / f"{nc_file.stem}.parquet")
                progress.update(task, advance=1)
        rich.print(f"[bold green] ✅ Data merged to {data_dir}[/bold green]")