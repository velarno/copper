import duckdb
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from storage.models import DatasetResult

sql_scripts_path = Path(__file__).parent / "sql"

RESULT_FIELDS = ['score', 'id', 'rel_link', 'abs_link', 'title', 'description', 'tags', 'created_at', 'updated_at']

def connect_to_database(db_path: str = 'datasets.db'):
    """Connect to DuckDB database."""
    con = duckdb.connect(db_path)
    con.install_extension('fts')
    con.load_extension('fts')
    con.install_extension('httpfs')
    con.load_extension('httpfs')
    return con

def execute_sql_script(con, script_path: Path):
    """Execute a SQL script."""
    with open(script_path, 'r') as file:
        con.execute(file.read())

def are_tables_initialized(con) -> bool:
    """Check if the tables are initialized."""
    tables = ["datasets", "stac_catalogue_links", "stac_collections", "stac_keywords", "stac_links"]
    # DuckDB does not have a 'table_exists' pragma; use duckdb_tables system table instead
    existing_tables = set(row[0] for row in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'").fetchall())
    return all(table_name in existing_tables for table_name in tables)

def result_as_dict(result: tuple, fields: List[str] = RESULT_FIELDS, without_score: bool = False) -> Dict[str, Any]:
    """Convert a tuple to a dictionary with the specified fields."""
    if without_score:
        return {field: result[i] for i, field in enumerate(fields[1:])}
    else:
        return {field: result[i] for i, field in enumerate(fields)}

def initialize_database(db_path: str = 'datasets.db'):
    """Initialize DuckDB with required extensions and create datasets table."""
    # Connect to DuckDB database
    con = connect_to_database(db_path)
    
    # Create datasets table with full-text search capabilities
    execute_sql_script(con, sql_scripts_path / "datasets.sql")
    
    # Create full-text search index
    execute_sql_script(con, sql_scripts_path / "fts_index.sql")

    # Create STAC links table
    execute_sql_script(con, sql_scripts_path / "stac.sql")
    
    return con

def insert_dataset(con, dataset_dict):
    """Insert a single dataset into the database."""
    created_at = datetime.now()
    updated_at = datetime.now()
    con.execute("""
        INSERT INTO datasets (id, rel_link, abs_link, title, description, tags, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        dataset_dict['id'],
        dataset_dict['rel_link'],
        dataset_dict['abs_link'],
        dataset_dict['title'],
        dataset_dict['description'],
        dataset_dict['tags'],
        created_at,
        updated_at
    ])

def seed_dataset_from_file(con, file_path: str):
    """Seed datasets from a JSON file."""
    results = con.execute(f"""
        INSERT INTO datasets (id, rel_link, abs_link, title, description, tags, created_at, updated_at)
        SELECT *, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM read_json('{file_path}')
    """)
    return results.fetchall()

def search_datasets(con, query, limit=None) -> List[DatasetResult]:
    """Search datasets using full-text search."""
    # create fts index if not exists
    con.execute("""
        PRAGMA create_fts_index(datasets, 'id', 'title', overwrite=1)
    """)
    
    results = con.execute(f"""
        SELECT 
            fts_main_datasets.match_bm25(d.id, ?) AS score,
            d.id,
            d.rel_link,
            d.abs_link,
            d.title,
            d.description,
            d.tags,
            d.created_at,
            d.updated_at
        FROM datasets d
        WHERE score > 0 
        ORDER BY score DESC
        {f"LIMIT {limit}" if limit else ""}
    """, [query]).fetchall()

    return [DatasetResult(**result_as_dict(row)) for row in results]

def get_all_datasets_from_db(con) -> List[DatasetResult]:
    """Retrieve all datasets from the database."""
    results = con.execute("SELECT * FROM datasets ORDER BY id").fetchall()
    return [DatasetResult(**result_as_dict(row)) for row in results]

def list_datasets(con, only_ids=False) -> List[DatasetResult]:
    """List all datasets from the database."""
    results = con.execute(f"""
        SELECT
            {"id" if only_ids else "*"}
        FROM datasets
        ORDER BY id
    """).fetchall()
    return [DatasetResult(**result_as_dict(row, without_score=True)) for row in results]

def fetch_dataset_by_id(con, id: str) -> Optional[DatasetResult]:
    """Fetch a dataset by its ID."""
    results = con.execute("""
        SELECT NULL, * FROM datasets WHERE id = ?
    """, [id]).fetchone()
    return DatasetResult(**result_as_dict(results)) if results else None