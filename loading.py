from rich.progress import Progress, SpinnerColumn, TextColumn, TaskID, BarColumn

def show_progress_bar(total_steps: int, text: str = "Processing...") -> tuple[Progress, TaskID]:
    """Display a progress bar with the given text and total steps.

    Args:
        total_steps (int): The total number of steps.
        text (str): The text to display in the progress bar.

    Returns:
        tuple[Progress, TaskID]: The progress bar and the task ID.
    """
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("[progress.completed]{task.completed}/{task.total}"),
        TextColumn("[progress.elapsed]{task.elapsed:0.0f}s"),
        TextColumn("{task.fields[logs]}"),
        transient=True,
    ) as progress:
        task = progress.add_task(text, total=total_steps, logs="")
        return progress, task

def show_spinner(text: str = "Loading...") -> tuple[Progress, TaskID]:
    """Display a spinner with the given text."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(text, total=None)
        return progress, task




