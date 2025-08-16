import httpx
import time
import logging
from typing import Dict, Any, List, Optional

from .crud import engine, Session
from .models import Collection, Keyword, CollectionLink, InputSchema, CatalogLink
from .exceptions import STACAPIError, STACAuthenticationError, STACRateLimitError
from .config import config

logger = logging.getLogger(__name__)

class StacClient(httpx.Client):
    """Client for interacting with Copernicus STAC API with cost estimation."""
    
    def __init__(self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.base_url = base_url or config.base_url
        self.catalogue_url = config.catalogue_url
        self.collection_route = config.collection_route
        self.retrieve_route = config.retrieve_route
        self.api_key = api_key or config.api_key
        # Set up session with retry strategy
        super().__init__()
        
        # Set authentication if API key is provided
        if self.api_key:
            self.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "copper-stac-client/1.0"
            })
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 60.0 / config.rate_limit  # Convert rate limit to interval
        
        logger.info(f"Initialized STAC client for {self.base_url}")
    
    def _rate_limit(self):
        """Implement rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self._last_request_time = time.time()
    
    def _make_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make HTTP request with error handling and rate limiting."""
        self._rate_limit()
        
        try:
            kwargs.setdefault('timeout', config.timeout)
            response = self.request(method, url, **kwargs)
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited, waiting {retry_after}s")
                time.sleep(retry_after)
                raise STACRateLimitError("Rate limit exceeded", status_code=429)
            
            # Handle authentication errors
            if response.status_code == 401:
                raise STACAuthenticationError("Authentication failed", status_code=401)
            
            if response.status_code == 403:
                raise STACAuthenticationError("Access forbidden", status_code=403)
            
            response.raise_for_status()
            return response
            
        except httpx.TimeoutException as e:
            logger.error(f"Request timeout for {url}: {e}")
            raise STACAPIError(f"Request timeout: {e}") from e
        except httpx.ConnectError as e:
            logger.error(f"Connection error for {url}: {e}")
            raise STACAPIError(f"Connection error: {e}") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for {url}: {e}")
            raise STACAPIError(f"HTTP error: {e}", status_code=response.status_code) from e

    def get_collection_url(self, collection_id: str) -> str:
        return f"{self.base_url}{self.collection_route.format(dataset_id=collection_id)}"
    
    def get_retrieve_url(self, collection_id: str) -> str:
        return f"{self.base_url}{self.retrieve_route.format(dataset_id=collection_id)}"

    def fetch_collection_from_url(self, collection_url: str, session: Optional[Session] = None):
        """Fetch a collection from a URL."""
        response = self._make_request("GET", collection_url)
        data = response.json()
        
        collection = Collection.from_response(data)

        _keywords = data.get("keywords", [])
        _links = data.get("links", [])
        _links = [link for link in _links if link["rel"] != "self"]


        keywords = [Keyword(keyword=keyword, collection=collection) for keyword in _keywords]
        links = [CollectionLink(url=link["href"], rel=link["rel"], mime_type=link.get("type", None), collection=collection) for link in _links]
        if session:
            session.add(collection)
            session.add_all(keywords)
            session.add_all(links)

        return collection

    def fetch_collection_inputs_from_url(self, retrieve_url: str, collection: Collection, session: Optional[Session] = None):
        """Fetch input parameters for a collection from a URL."""
        response = self._make_request("GET", retrieve_url)
        data = response.json()
        logger.info(f"Fetching input parameters for collection {collection.collection_id}")
        logger.info(f"Data: {data}")

        input_schema = InputSchema.create_with_parameters(data, collection)

        if session:
            session.add(input_schema)
            session.add_all(input_schema.parameters)

        return input_schema
    
    def estimate_request_cost(self, collection_id: str, request_data: Dict[str, Any]):
        """Estimate the cost of a request."""
        url = config.cost_endpoint.format(dataset_id=collection_id)
        
        try:
            payload = {
                "collection_id": collection_id,
                "request": request_data
            }
            
            response = self._make_request("POST", url, json=payload)
            response.raise_for_status()
            data = response.json()
            
            return data
            
        except httpx.HTTPStatusError as e:
            print(f"Error estimating cost: {e}")
            raise STACAPIError(f"Error estimating cost: {e}") from e
    
    def fetch_catalog_links(self, session: Optional[Session] = None) -> List[CatalogLink]:
        """Get basic information about a collection."""
        response = self._make_request("GET", self.catalogue_url)
        data = response.json()
        links = data.get("links", [])
        seen_links = set()
        catalog_links = []
        for link in links:
            if link["href"] in seen_links:
                continue
            seen_links.add(link["href"])
            catalog_links.append(CatalogLink(collection_url=link["href"], rel=link["rel"], title=link.get("title", None), mime_type=link.get("type", None)))
        if session:
            session.add_all(catalog_links)
        return catalog_links

    def fetch_all_collections(self,
        catalog_links: List[CatalogLink],
        session: Optional[Session] = None,
        with_inputs: bool = True,
        silent: bool = False,
        limit: Optional[int] = None
        ) -> List[Collection | InputSchema]:
        """Get all collections."""
        entities = []
        children_links = [link for link in catalog_links if link.rel == "child"]
        if limit:
            children_links = children_links[:limit]
        for link in children_links:
            collection = self.fetch_collection_from_url(link.collection_url, session)
            entities.append(collection)
            if with_inputs:
                input_schema = self.fetch_collection_inputs_from_url(collection.retrieve_url, collection, session)
                entities.append(input_schema)
            if session:
                session.add_all(entities)
        return entities
    
    def list_collections(self) -> List[Dict[str, Any]]:
        """List all available collections."""
        url = f"{self.catalogue_url}/collections"
        
        try:
            response = self.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("collections", [])
            
        except httpx.HTTPStatusError as e:
            print(f"Error fetching collections: {e}")
            return []
    
    def search_collections(self, query: str) -> List[Dict[str, Any]]:
        """Search collections by query."""
        url = f"{self.catalogue_url}/search"
        
        try:
            payload = {
                "query": query,
                "limit": 50
            }
            
            response = self.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("features", [])
            
        except httpx.HTTPStatusError as e:
            print(f"Error searching collections: {e}")
            return []


stac_client = StacClient()

if __name__ == "__main__":
    client = StacClient()
    collection_url = "https://cds.climate.copernicus.eu/api/catalogue/v1/collections/derived-reanalysis-energy-moisture-budget"
    with Session(engine) as session:
        catalog_links = client.fetch_catalog_links(session)
        collection = client.fetch_collection_from_url(collection_url, session)
        input_schema = client.fetch_collection_inputs_from_url(collection.retrieve_url, collection, session)
        session.commit()