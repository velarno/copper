import typer
from typing import Literal, Optional, Annotated
import logging

from api.stac.client import stac_client
from api.stac.crud import engine, Session, list_items
from api.stac.models import Tables

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="stac",
    help="STAC API commands",
    no_args_is_help=True,
)

# Template management subapp
template_app = typer.Typer(
    name="template",
    help="Template management commands",
)

# @app.command(
#     name="init",
#     help="Initialize the STAC tables",
# )
# def init():
#     con = connect_to_database()
#     if not are_tables_initialized(con):
#         initialize_database()
#         typer.echo("STAC tables initialized")
#     else:
#         typer.echo("Tables are already initialized")


@app.command(
    name="init",
    help="Initialize the STAC tables",
)
def init(
    drop_existing: bool = typer.Option(False, help="Drop existing tables"),
    with_catalog: bool = typer.Option(False, "--catalog", "-K", help="Fetch catalog links from the Copernicus STAC API"),
    with_collections: bool = typer.Option(False, "--collections", "-C", help="Fetch all collections from the Copernicus STAC API"),
    with_schema: bool = typer.Option(False, "--schema", "-S", help="Fetch schema for all collections"),
    with_all: bool = typer.Option(False, "--all", "-A", help="Fetch all collections and schema"),
    limit: int = typer.Option(None, "--limit", "-l", help="Limit the number of collections to fetch"),
    silent: bool = typer.Option(False, "--silent", "-s", help="Do not show progress"),
):
    if with_all:
        with_catalog = with_collections = with_schema = True
    # if downstream data is to be fetched, force upstream to also be true
    if with_collections:
        with_catalog = True
    if with_schema:
        with_collections = with_catalog = True

    with Session(engine) as session:
        # if fetch collections, then catalog is fetched automatically
        if with_catalog:
            catalog_links = stac_client.fetch_catalog_links(session)
        if with_collections:
            stac_client.fetch_all_collections(
                catalog_links=catalog_links,
                session=session,
                with_inputs=with_schema,
                silent=silent,
                limit=limit,
            )
        session.commit()
    
@app.command(
    name="list",
    help="List items from the database (collections, catalog links, input schemas)",
)
def list(
    table: Tables = typer.Argument(..., help="Table to list"),
    limit: int = typer.Option(None, "--limit", "-l", help="Limit the number of items to list"),
    sort: Optional[str] = typer.Option(None, "--sort", "-S", help="Sort by column"),
    order: str = typer.Option("asc", "--order", "-o", help="Sort order"),
):
    for item in list_items(table.table, limit):
        # TODO: pretty print the item
        typer.echo(item)

# # Variable Discovery Commands
# @app.command(
#     name="variables",
#     help="List variables for a collection",
# )
# def variables(
#     collection_id: str = typer.Argument(..., help="Collection ID"),
#     search: Optional[str] = typer.Option(None, "--search", "-s", help="Search term"),
#     detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed information"),
#     constraints: bool = typer.Option(False, "--constraints", "-c", help="Show constraint sets"),
#     refresh: bool = typer.Option(False, "--refresh", "-r", help="Refresh data from API"),
#     output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
# ):
#     """List variables for a collection."""
#     try:
#         # Input validation
#         if not collection_id.strip():
#             typer.echo("Error: Collection ID cannot be empty", err=True)
#             raise typer.Exit(1)
        
#         # Validate output path if provided
#         if output and not validate_file_path(output):
#             typer.echo(f"Error: Invalid or unsafe output path: {output}", err=True)
#             raise typer.Exit(1)
        
#         variables_list = []
#         constraint_sets = []
        
#         if refresh:
#             # Fetch fresh data from API
#             typer.echo(f"Fetching variables from API for collection '{collection_id}'...")
#             try:
#                 with typer.progressbar(length=100, label="Fetching variables") as progress:
#                     progress.update(20)
#                     variables_list = stac_client.fetch_collection_variables(collection_id)
#                     progress.update(50)
                    
#                     if variables_list:
#                         store_variables(collection_id, variables_list)
#                         progress.update(30)
                    
#                     if constraints:
#                         constraint_sets = stac_client.fetch_collection_constraints(collection_id)
#                         if constraint_sets:
#                             store_constraints(collection_id, constraint_sets)
                    
#                 typer.echo(f"✓ Fetched {len(variables_list)} variables from API")
                
#             except Exception as e:
#                 typer.echo(f"Error fetching from API: {e}", err=True)
#                 typer.echo("Falling back to database...", err=True)
#                 variables_list = get_variables(collection_id, search)
#         else:
#             # Try database first
#             try:
#                 variables_list = get_variables(collection_id, search)
#                 if constraints:
#                     constraint_sets = get_constraints(collection_id)
                    
#                 if not variables_list:
#                     typer.echo(f"No variables in database. Use --refresh to fetch from API.", err=True)
                    
#             except STACDatabaseError as e:
#                 typer.echo(f"Database error: {e}", err=True)
#                 raise typer.Exit(1)
        
#         if not variables_list:
#             typer.echo(f"No variables found for collection '{collection_id}'")
#             return
        
#         # Apply search filter if not already applied in database query
#         if search and refresh:
#             variables_list = [v for v in variables_list if 
#                             search.lower() in v.name.lower() or 
#                             search.lower() in (v.description or "").lower()]
        
#         typer.echo(f"Found {len(variables_list)} variables for collection '{collection_id}':")
        
#         for var in variables_list:
#             if detailed:
#                 typer.echo(f"  {var.name}")
#                 typer.echo(f"    Description: {var.description or 'N/A'}")
#                 typer.echo(f"    Units: {var.units or 'N/A'}")
#                 typer.echo(f"    Time Resolution: {var.time_resolution or 'N/A'}")
#                 typer.echo(f"    Statistics: {', '.join(var.available_statistics) or 'N/A'}")
#                 typer.echo(f"    Compatible Variables: {', '.join(var.compatible_variables) or 'N/A'}")
#                 typer.echo()
#             else:
#                 desc = var.description or "No description"
#                 typer.echo(f"  {var.name}: {desc}")
        
#         if constraints and constraint_sets:
#             typer.echo(f"\nFound {len(constraint_sets)} constraint sets:")
#             for constraint in constraint_sets:
#                 typer.echo(f"  {constraint.constraint_set_id}: {len(constraint.variables)} variables")
        
#         if output:
#             try:
#                 data = {
#                     "collection_id": collection_id,
#                     "variables": [var.model_dump() for var in variables_list],
#                     "constraints": [c.model_dump() for c in constraint_sets] if constraints else []
#                 }
                
#                 with open(output, 'w', encoding='utf-8') as f:
#                     json.dump(data, f, indent=2, default=str)
                    
#                 typer.echo(f"✓ Data exported to {output}")
                
#             except Exception as e:
#                 typer.echo(f"Error writing output file: {e}", err=True)
#                 raise typer.Exit(1)
                
#     except STACError as e:
#         typer.echo(f"STAC Error: {e}", err=True)
#         raise typer.Exit(1)
#     except Exception as e:
#         logger.error(f"Unexpected error in variables command: {e}")
#         typer.echo(f"Unexpected error: {e}", err=True)
#         raise typer.Exit(1)