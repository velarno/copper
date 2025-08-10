from typing import Iterable
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

console = Console()

def progress_bar(console: Console = console):
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console
    )

def with_progress(iterable: Iterable, silent: bool = False):
    if silent:
        return iterable
    progress = progress_bar()
    progress.add_task(iterable.__name__)
    for item in iterable:
        progress.update(progress.tasks[0], completed=progress.tasks[0].completed + 1)
        yield item
    progress.stop()