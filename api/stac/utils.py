
import requests
import json

from storage.datasets import connect_to_database

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

def fetch_all_collections() -> list[dict]:
    con = connect_to_database()
    collections = con.execute("SELECT * FROM stac_catalogue_links where rel = 'child'").fetchall()
    for collection in collections:
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