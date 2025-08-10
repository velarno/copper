import os
import logging
from typing import List, Optional
from sqlmodel import SQLModel, create_engine, Session, select
from .models import CatalogLink, Collection, Keyword, CollectionLink

## SQLITE ENGINE

logger = logging.getLogger(__name__)

enable_echo = os.getenv("ENABLE_ECHO", "false").lower() == "true"
sqlite_file_name = "database.db"  
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, echo=enable_echo)

def create_db_and_tables(drop_existing: bool = False):
    """Create the database and tables."""
    if drop_existing:
        SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

def drop_table(table_name: str):
    """Drop a table."""
    SQLModel.metadata.drop_all(engine, [table_name])

def insert_catalog_links(catalog_links: List[CatalogLink]):
    """Insert catalog links into the database."""
    try:
        with Session(engine) as session:
            session.add_all(catalog_links)
            session.commit()
    except Exception as e:
        logger.error(f"Error inserting catalog links: {e}")
        raise e

def insert_collections(collections: List[Collection]):
    """Insert collections into the database."""
    try:
        with Session(engine) as session:
            session.add_all(collections)
            session.commit()
    except Exception as e:
        logger.error(f"Error inserting collections: {e}")
        raise e

def collection_from_dataset_id(dataset_id: str) -> Collection:
    """Get a collection from a dataset ID."""
    try:
        with Session(engine) as session:
            return session.exec(select(Collection).where(Collection.collection_id == dataset_id)).first()
    except Exception as e:
        logger.error(f"Error getting collection from dataset ID: {e}")
        raise e

def list_items(table: SQLModel, limit: Optional[int] = None):
    """
    List items from the database.
    """
    try:
        with Session(engine) as session:
            query = select(table)
            if limit:
                query = query.limit(limit)
            result = session.exec(query).fetchall()
            return result
    except Exception as e:
        logger.error(f"Error listing items: {e}")
        raise e

drop_existing = os.getenv("DROP_EXISTING", "false").lower() == "true"
create_db_and_tables(drop_existing=drop_existing)