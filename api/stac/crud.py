import os
import json
import logging
from typing import Any, Dict, List, Optional
from sqlmodel import SQLModel, create_engine, Session, select
from .models import CatalogLink, Collection, Template, TemplateParameter, TemplateHistory

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

def collection_from_id(collection_id: int) -> Collection:
    """Get a collection from an ID."""
    try:
        with Session(engine) as session:
            return session.exec(select(Collection).where(Collection.id == collection_id)).first()
    except Exception as e:
        logger.error(f"Error getting collection from ID: {e}")
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

class TemplateUpdater:
    def init_from_template(self, template: Template):
        self.template = template
        self.collection = collection_from_id(template.collection_id)
        self.template_name = self.template.name
        self.dataset_id = self.collection.collection_id
        self.parameters = self.template.parameters
        self.template_history = self.fetch_history_from_id(self.template.id)

    def init_from_name(self, template_name: str) -> bool:
        """Returns `True` if existing template found, `False` if not and create needed"""
        self.template = self.fetch_by_name(template_name)
        
        if not self.template:
            return False

        self.template_name = template_name
        self.collection = collection_from_id(self.template.collection_id)
        self.dataset_id = self.collection.collection_id
        self.parameters = self.template.parameters
        self.template_history = self.fetch_history_from_id(self.template.id)

        return True

    def create_template(self, template_name: str, dataset_id: str):
        self.collection = collection_from_dataset_id(dataset_id)
        self.template = Template(
            name=template_name,
            collection_id=self.collection.id,
            cost=0
        )
        self.template_name = template_name
        self.dataset_id = dataset_id
        self.template_history = []
        self.parameters = []
        self.template_history = [TemplateHistory(data={})]
        self.commit()


    def __init__(self, template_name: str, dataset_id: Optional[str] = None, template: Optional[Template] = None) -> None:
        self.dataset_id = dataset_id
        self.template_name = template_name
        self.template = None
        self.collection = None
        self.parameters: List[TemplateParameter] = []
        self.template_history: List[TemplateHistory] = []

        if template is not None:
            self.init_from_template(template)
        elif template_name is not None:
            template_exists = self.init_from_name(template_name)

            if not template_exists:
                if not dataset_id:
                    raise ValueError("Dataset ID is required to create a new template")
                self.create_template(template_name, dataset_id)
                return

    @classmethod
    def from_name(cls, template_name: str) -> "TemplateUpdater":
        template = cls.fetch_by_name(template_name)
        if template is None:
            raise ValueError(f"Template {template_name} not found")
        return cls(template.collection_id, template.name)

    @staticmethod
    def fetch_by_name(template_name: str) -> Template:
        with Session(engine) as session:
            return session.exec(select(Template).where(Template.name == template_name)).first()
    
    @staticmethod
    def fetch_history_from_id(template_id: int) -> TemplateHistory:
        with Session(engine) as session:
            return session.exec(select(TemplateHistory).where(TemplateHistory.template_id == template_id)).fetchall()

    def commit(self):
        with Session(engine) as session:
            session.add(self.template)
            session.add_all(self.template.history)
            session.commit()
            session.refresh(self.template)

    def to_dict(self) -> Dict[str, Any]:
        serialized = {}
        for parameter in self.parameters:
            if parameter.name not in serialized:
                serialized[parameter.name] = [parameter.value]
            else:
                serialized[parameter.name].append(parameter.value)
        return serialized

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    def add_parameter(self, parameter_name: str, parameter_value: str):
        self.parameters.append(TemplateParameter(
            name=parameter_name,
            value=parameter_value
        ))
        self.template.parameters.append(self.parameters[-1])
        # TODO: find a good way to store the current state of the template
        self.template_history.append(TemplateHistory(data=self.to_dict()))
        self.commit()

    def from_dict(self, data: Dict[str, Any]):
        # TODO: find a way to set current state from a dict
        raise NotImplementedError("Be patient.")


drop_existing = os.getenv("DROP_EXISTING", "false").lower() == "true"
create_db_and_tables(drop_existing=drop_existing)