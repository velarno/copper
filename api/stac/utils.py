import json
import logging
import requests
from typing import List, Union

from .client import stac_client
from rich.table import Table
from sqlmodel import SQLModel

COPERNICUS_STAC_URL = r"https://cds.climate.copernicus.eu/api/catalogue/v1/"

logger = logging.getLogger(__name__)


def fetch_collection_links() -> list[dict]:
    url = COPERNICUS_STAC_URL
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    return data.get("links", [])


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


def models_to_json(
    models: Union[List[SQLModel], SQLModel], hide_values: bool = False
) -> str:
    """Convert SQLModel instances to JSON string. Accepts either a single model or a list of models."""
    if isinstance(models, list):
        return json.dumps(
            [
                model.model_dump(mode="json", exclude_none=hide_values)
                for model in models
            ]
        )
    else:
        try:
            return json.dumps(models.model_dump(mode="json", exclude_none=hide_values))
        except Exception as e:
            logger.error(f"Error converting models to JSON: {e}")
            raise e


def models_to_table(models: Union[List[SQLModel], SQLModel]) -> Table:
    """Convert SQLModel instances to Rich table. Accepts either a single model or a list of models."""
    if isinstance(models, list):
        table = Table(title="Models")
        if not models:
            return table
        # TODO: make this more generic, not hardcoded
        fields = [field for field in models[0].model_fields if field != "values"]
        for field in fields:
            table.add_column(field)
        for model in models:
            row = model.model_dump(mode="json")
            table.add_row(*[str(row[field]) for field in fields])
        return table
    else:
        table = Table(title=models.__class__.__name__)
        for field in models.model_fields:
            table.add_column(field)
        row = models.model_dump(mode="json")
        table.add_row(*[str(row[field]) for field in models.model_fields])
        return table
