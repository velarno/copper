import json
import requests
from typing import List

from multimethod import multimethod

from storage.datasets import connect_to_database
from .client import stac_client
from display import with_progress
from sqlmodel import SQLModel
from rich.table import Table

COPERNICUS_STAC_URL = r"https://cds.climate.copernicus.eu/api/catalogue/v1/"

def fetch_collection_links() -> list[dict]:
    url = COPERNICUS_STAC_URL
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    return data.get("links", [])

def store_collection_links(links: list[dict]):
    con = connect_to_database()
    for link in links:
        con.execute(
            "INSERT INTO stac_catalogue_links (rel, mimetype, collection_url, title) VALUES (?, ?, ?, ?)",
            (link["rel"], link["type"], link["href"], link["title"] if "title" in link else None)
            )
    con.commit()
    con.close()

def fetch_collection_data(collection_url: str) -> tuple[dict, list[dict], list[dict]]:
    url = collection_url
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    links = data.get("links", [])
    keywords = data.get("keywords", [])
    collection_info = {
        "collection_id": data.get("id"),
        "title": data.get("title"),
        "description": data.get("description"),
        "published_at": data.get("published"),
        "modified_at": data.get("updated"),
        "doi": data.get("sci:doi", ""),
    }
    return collection_info, links, keywords

@with_progress
def fetch_all_collections(silent: bool = False) -> list[dict]:
    con = connect_to_database()
    collections = con.execute("SELECT * FROM stac_catalogue_links where rel = 'child'").fetchall()
    for collection in with_progress(collections, silent=silent):
        collection_info, links, keywords = fetch_collection_data(collection[3])
        store_collection_data(collection_info, links, keywords)
    return collections

def store_collection_data(collection_info: dict, links: list[dict], keywords: list[dict]):
    con = connect_to_database()
    collection_query = con.execute(
        "INSERT OR REPLACE INTO stac_collections (collection_id, title, description, published_at, modified_at, doi) VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
        (collection_info["collection_id"], collection_info["title"], collection_info["description"], collection_info["published_at"], collection_info["modified_at"], collection_info["doi"])
    )
    collection_id = collection_query.fetchone()[0]

    for keyword in keywords:
        con.execute(
            "INSERT INTO stac_keywords (keyword, collection_id) VALUES (?, ?)",
            (keyword, collection_id)
        )
    for link in links:
        con.execute(
            "INSERT INTO stac_links (url, mimetype, title, collection_id) VALUES (?, ?, ?, ?)",
            (link["href"], link["type"] if "type" in link else None, link["title"] if "title" in link else None, collection_id)
        )
    con.commit()
    con.close()

# New costings-related utility functions
def fetch_collection_variables(collection_id: str) -> list[dict]:
    """Fetch variables for a collection using the STAC client."""
    variables = stac_client.fetch_collection_variables(collection_id)
    return [var.model_dump() for var in variables]

def fetch_collection_constraints(collection_id: str) -> list[dict]:
    """Fetch constraint sets for a collection using the STAC client."""
    constraints = stac_client.fetch_collection_constraints(collection_id)
    return [constraint.model_dump() for constraint in constraints]

def get_collection_info(collection_id: str) -> dict:
    """Get basic information about a collection."""
    return stac_client.get_collection_info(collection_id) or {}

def list_available_collections() -> list[dict]:
    """List all available collections."""
    return stac_client.list_collections()

def search_collections(query: str) -> list[dict]:
    """Search collections by query."""
    return stac_client.search_collections(query)

def estimate_request_cost(collection_id: str, request_data: dict) -> dict:
    """Estimate the cost of a request."""
    cost_estimate = stac_client.estimate_request_cost(collection_id, request_data)
    return cost_estimate.model_dump()

def validate_request(collection_id: str, request_data: dict) -> dict:
    """Validate a request against collection constraints."""
    validation_result = stac_client.validate_request(collection_id, request_data)
    return validation_result.model_dump()

def get_collection_variables_from_db(collection_id: str, search: str = None) -> list[dict]:
    """Get variables for a collection from the database."""
    from .database import get_variables
    variables = get_variables(collection_id, search)
    return [var.model_dump() for var in variables]

def get_collection_constraints_from_db(collection_id: str) -> list[dict]:
    """Get constraint sets for a collection from the database."""
    from .database import get_constraints
    constraints = get_constraints(collection_id)
    return [constraint.model_dump() for constraint in constraints]

@multimethod
def models_to_json(models: List[SQLModel], hide_values: bool = False) -> str:
    return json.dumps([model.model_dump(mode="json", exclude_none=hide_values) for model in models])

@models_to_json.register
def models_to_json(model: SQLModel, hide_values: bool = False) -> str:
    return json.dumps(model.model_dump(mode="json", exclude_none=hide_values))

@multimethod
def models_to_table(models: List[SQLModel]) -> Table:
    table = Table(title="Models")
    # TODO: make this more generic, not hardcoded
    fields = [field for field in models[0].model_fields if field != "values"]
    for field in fields:
        table.add_column(field)
    for model in models:
        row = model.model_dump(mode="json")
        table.add_row(*[str(row[field]) for field in fields])
    return table

@models_to_table.register
def models_to_table(model: SQLModel) -> Table:
    table = Table(title=model.__class__.__name__)
    for field in model.model_fields:
        table.add_column(field)
    row = model.model_dump(mode="json")
    table.add_row(*[str(row[field]) for field in model.model_fields])
    return table