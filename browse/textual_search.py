from typing import Optional
from rich.text import Text
from rich.panel import Panel
from rapidfuzz.fuzz import ratio, token_set_ratio
from browse.datasets import get_all_datasets
from textual.app import App, ComposeResult
from textual.widgets import Input, DataTable, Static, Footer
from textual.containers import Container
from rich.align import Align

class DatasetSearchApp(App):
    CSS_PATH = None
    BINDINGS = [
        ("q", "action_quit", "Quit"),
        ("ctrl+enter", "action_open_url", "Open in browser"),
        ("up", "action_cursor_up", "Up"),
        ("down", "action_cursor_down", "Down"),
    ]

    def __init__(self, group: Optional[str] = None, query: Optional[str] = None):
        super().__init__()
        self.group = group
        self.query = query or ""
        self.datasets = get_all_datasets(group)
        self.filtered = self.datasets
        self.selected_idx = 0

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Type to search datasets...", value=self.query, id="search_input")
        yield Container(
            DataTable(id="results_table"),
            Static("", id="details_panel"),
            id="main_container",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#results_table", DataTable).add_column("S", width=3)
        self.query_one("#results_table", DataTable).add_column("Enum")
        self.query_one("#results_table", DataTable).add_column("Name")
        self.query_one("#results_table", DataTable).add_column("Shortname")
        self.query_one("#results_table", DataTable).add_column("Description")
        self.query_one("#results_table", DataTable).add_row("[grey50]...[/]", "", "Loading datasets...", "", "")
        self.set_timer(0.1, self.load_and_show_results)
        self.update_commands_panel()

    def load_and_show_results(self):
        self.datasets = get_all_datasets()
        self.update_results()

    def update_results(self):
        query = self.query_one("#search_input", Input).value.strip()
        scored = self.fuzzy_search(query)
        self.filtered = [d for score, d in scored]
        self.filtered_scores = [score for score, d in scored]
        table = self.query_one("#results_table", DataTable)
        table.clear(columns=True)
        table.add_column("S", width=3)
        table.add_column("Enum")
        table.add_column("Name")
        table.add_column("Shortname")
        table.add_column("Description")
        for i, (score, d) in enumerate(scored):
            score_str = str(int(round(score))).rjust(2)
            if score >= 70:
                cell_style = "black on green"
            elif score >= 50:
                cell_style = "black on orange3"
            elif score >= 30:
                cell_style = "black on yellow"
            else:
                cell_style = "white on grey37"
            table.add_row(
                Text(score_str, style=cell_style),
                Text(d["enum_name"], style=cell_style),
                Text(d["name"], style=cell_style),
                Text(d["shortname"], style=cell_style),
                Text(d["description"], style=cell_style),
            )
        if self.filtered:
            table.cursor_coordinate = (0, 0)
            self.selected_idx = 0
            self.show_details(0)
        else:
            self.query_one("#details_panel", Static).update("No results.")

    def fuzzy_search(self, text: str):
        if not text:
            return [(100, d) for d in self.datasets]
        results = []
        for d in self.datasets:
            name_score = ratio(text.lower(), d["name"].replace("_", " ").lower())
            shortname_score = ratio(text.lower(), d["shortname"].replace("_", " ").lower())
            desc_score = token_set_ratio(text.lower(), d["description"].lower())
            enum_score = ratio(text.lower(), d["enum_name"].replace("_", " ").lower())
            score = (3*name_score + 2*shortname_score + desc_score + 0.5*enum_score) / 6.5
            results.append((score, d))
        results.sort(reverse=True, key=lambda x: x[0])
        filtered = [(score, d) for score, d in results if score > 20]
        if len(filtered) < 20:
            filtered = results[:20]
        return filtered

    def on_input_changed(self, event: Input.Changed):
        self.update_results()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted):
        self.selected_idx = event.cursor_row
        self.show_details(self.selected_idx)

    def show_details(self, idx: int):
        if not self.filtered:
            self.query_one("#details_panel", Static).update("No results.")
            return
        d = self.filtered[idx]
        panel = Panel(
            Align.left(
                Text(f"[b]{d['name']}[/b]\n[magenta]{d['shortname']}[/magenta]\n[cyan]{d['enum_name']}[/cyan]\n\n{d['description']}\n\n[blue]{d['url']}[/blue]")
            ),
            title="Dataset Details",
            border_style="green",
        )
        self.query_one("#details_panel", Static).update(panel)

    def action_cursor_up(self):
        table = self.query_one("#results_table", DataTable)
        if self.selected_idx > 0:
            self.selected_idx -= 1
            table.cursor_coordinate = (self.selected_idx, 0)
            self.show_details(self.selected_idx)

    def action_cursor_down(self):
        table = self.query_one("#results_table", DataTable)
        if self.selected_idx < len(self.filtered) - 1:
            self.selected_idx += 1
            table.cursor_coordinate = (self.selected_idx, 0)
            self.show_details(self.selected_idx)

    def action_open_url(self):
        if not self.filtered:
            return
        d = self.filtered[self.selected_idx]
        url = d.get("url")
        if url:
            import webbrowser
            webbrowser.open(url)

    def action_quit(self):
        self.exit()

    def update_commands_panel(self):
        # Styled command bar, inspired by Textual docs example
        commands = [
            ("[b][blue]q[/][/b]", "Quit"),
            ("[b][green]Enter[/][/b]", "Open in browser"),
            ("[b][yellow]↑/↓[/][/b]", "Move"),
            ("[b][magenta]Type[/][/b]", "Search"),
        ]
        bar = " │ ".join(f"{key} {desc}" for key, desc in commands)
        panel = f"\n{'─'*len(bar)}\n{bar}\n{'─'*len(bar)}"
        self.query_one("#commands_panel", Static).update(panel)

def main(group: Optional[str] = None, query: Optional[str] = None):
    app = DatasetSearchApp(group=group, query=query)
    app.run()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Browse Copernicus datasets with Textual TUI.")
    parser.add_argument("--group", type=str, default=None, help="Filter by group/module name (e.g. reanalysis, satellite, sea_level)")
    parser.add_argument("--query", type=str, default=None, help="Initial search query")
    args = parser.parse_args()
    main(group=args.group, query=args.query) 