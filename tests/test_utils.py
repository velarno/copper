from pathlib import Path

import pytest

from api.stac.models import CollectionRelType
from api.stac.utils import fetch_collection_links, fetch_collection_data

test_dir = Path(__file__).parent


@pytest.fixture
def collection_links():
    return fetch_collection_links()


@pytest.fixture
def collection_urls(collection_links):
    return [
        link["href"]
        for link in collection_links
        if "href" in link and link["rel"] == "child"
    ]


def test_fetch_collection_links(collection_links):
    links = collection_links
    assert len(links) > 0
    expected_rels = {
        "self",
        "root",
        "child",
        "parent",
        "data",
        "service-desc",
        "service-doc",
        "conformance",
    }
    expected_mime_types = {"text/html", "application/json"}

    rels = set(link["rel"] for link in links)
    mime_types = set(
        link["type"]
        for link in links
        if "type" in link and "openapi" not in link["type"]
    )
    assert not any(rel not in expected_rels for rel in rels)
    assert not any(mime_type not in expected_mime_types for mime_type in mime_types)


def test_fetch_collection_data(collection_urls):
    example_url = collection_urls[0]
    collection_info, links, keywords = fetch_collection_data(example_url)
    assert collection_info is not None
    assert links is not None
    assert keywords is not None
    assert collection_info["collection_id"] is not None
    assert collection_info["title"] is not None
    assert collection_info["description"] is not None
    assert collection_info["published_at"] is not None
    assert collection_info["modified_at"] is not None
    assert collection_info["doi"] is not None

    assert not any(not (isinstance(keyword, str)) for keyword in keywords)

    rels = set(link["rel"] for link in links)

    assert not any(rel not in CollectionRelType for rel in rels)
