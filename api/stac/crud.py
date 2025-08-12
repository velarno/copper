import os
import json
import logging
import httpx

from typing import Any, Dict, List, Optional, Tuple

from sqlmodel import SQLModel, create_engine, Session, select

from .models import (
    CatalogLink, Collection, CollectionLink,
    CostEstimate, InputParameter, InputSchema,
    Keyword, Template, TemplateHistory, TemplateParameter,
    TemplateCostHistory, Tables,
    TemplateHistory
)
from .config import config, cost_headers


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
            collection = session.exec(select(Collection).where(Collection.collection_id == dataset_id)).first()
            if not collection:
                logger.error(f"Collection with dataset ID {dataset_id} not found")
                raise ValueError(f"Collection with dataset ID {dataset_id} not found")
            return collection
    except Exception as e:
        logger.error(f"Error getting collection from dataset ID: {e}")
        raise e

def list_items(table: Tables, limit: Optional[int] = None):
    """
    List items from the database.
    """
    try:
        with Session(engine) as session:
            query = select(table.model)
            if limit:
                query = query.limit(limit)
            result = session.exec(query).fetchall()
            return list(result)
    except Exception as e:
        logger.error(f"Error listing items: {e}")
        raise e

class TemplateUpdater:
    """
    A class to help with template operations.
    """
    dataset_id: str
    template_name: str
    template: Template
    collection: Collection
    parameters: List[TemplateParameter]
    template_history: List[TemplateHistory]
    cost: float
    
    def init_from_template(self, template: Template):
        self.template = template
        self.collection = collection_from_id(template.collection_id)
        self.template_name = self.template.name
        self.dataset_id = self.collection.collection_id
        self.cost = self.template.cost
        self.template_history = self.fetch_history_from_id(self.template.id)

        with Session(engine) as session:
            session.refresh(self.template)
            self.parameters = self.template.parameters

    def init_from_name(self, template_name: str) -> bool:
        """Returns `True` if existing template found, `False` if not and create needed"""
        self.template, self.parameters, self.template_history = self.fetch_by_name(template_name)
        if not self.template:
            return False

        self.template_name = template_name
        self.collection = collection_from_id(self.template.collection_id)
        self.dataset_id = self.collection.collection_id
        self.cost = self.template.cost

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
            try:
                template_exists = self.init_from_name(template_name)
            except ValueError:
                template_exists = False

            if not template_exists:
                if not dataset_id:
                    raise ValueError("Dataset ID is required to create a new template")
                self.create_template(template_name, dataset_id)
                return

    @classmethod
    def from_name(cls, template_name: str) -> "TemplateUpdater":
        template: Optional[Template] = cls.fetch_by_name(template_name)
        if template is None:
            raise ValueError(f"Template {template_name} not found")
        return cls(template_name, template.collection_id, template)

    @staticmethod
    def fetch_by_name(template_name: str) -> Tuple[Template, List[TemplateParameter], List[TemplateHistory]]:
        with Session(engine) as session:
            template: Optional[Template] = session.exec(select(Template).where(Template.name == template_name)).first()
            if template is None:
                raise ValueError(f"Template {template_name} not found")
            return template, template.parameters, template.history
    
    @staticmethod
    def fetch_history_from_id(template_id: int) -> TemplateHistory:
        with Session(engine) as session:
            return session.exec(select(TemplateHistory).where(TemplateHistory.template_id == template_id)).fetchall()

    def fetch_latest_history(self) -> List[TemplateHistory]:
        with Session(engine) as session:
            return session.exec(
                select(TemplateHistory)
                .where(TemplateHistory.template_id == self.template.id)
                .order_by(TemplateHistory.created_at)
                ).fetchall()

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

    def refresh(self, session: Session):
        self.template = session.exec(select(Template).where(Template.name == self.template_name)).first()
        self.collection = session.exec(select(Collection).where(Collection.collection_id == self.dataset_id)).first()
        self.template_history = session.exec(select(TemplateHistory).where(TemplateHistory.template_id == self.template.id)).fetchall()
        self.parameters = session.exec(select(TemplateParameter).where(TemplateParameter.template_id == self.template.id)).fetchall()
    
    def add_parameter(self, parameter_name: str, parameter_value: str):
        with Session(engine) as session:
            self.refresh(session)
            new_parameter = TemplateParameter(
                name=parameter_name,
                value=parameter_value
            )
            self.template.parameters.append(new_parameter)
            self.parameters.append(new_parameter)
            new_history = TemplateHistory(data=self.to_dict(), template_id=self.template.id)
            session.add(new_history)
            self.template_history.append(new_history)
            session.commit()
            self.refresh(session)

    def remove_parameter(self, parameter_name: str):
        with Session(engine) as session:
            self.refresh(session)
            parameter = next((param for param in self.parameters if param.name == parameter_name), None)
            if parameter is None:
                raise ValueError(f"Parameter {parameter_name} not found")
            session.delete(parameter)
            session.commit()
            self.refresh(session)
            self.commit()

    def from_dict(self, data: Dict[str, Any]):
        # TODO: find a way to set current state from a dict
        raise NotImplementedError("Be patient.")

    def allowed_parameters(self) -> List[SQLModel]:
        with Session(engine) as session:
            collection_parameters = session.exec(
                select(InputParameter, InputSchema, Collection)
                .join(InputSchema, InputParameter.input_schema_id == InputSchema.id)
                .join(Collection, InputSchema.collection_id == Collection.id)
                .where(Collection.id == self.collection.id)
            ).fetchall()

            return [param for param, schema, collection in collection_parameters]
    
    def _estimate_cost(self) -> CostEstimate:
        client = httpx.Client()
        endpoint = config.cost_endpoint.format(dataset_id=self.dataset_id)
        response = client.post(endpoint, json={"inputs": self.to_dict()}, headers=cost_headers(self.dataset_id))
        data = response.json()

        return CostEstimate.from_response(data)

    def delete(self):
        with Session(engine) as session:
            session.delete(self.template)
            session.commit()
            self.refresh(session)
            self.commit()
    

        


drop_existing = os.getenv("DROP_EXISTING", "false").lower() == "true"
create_db_and_tables(drop_existing=drop_existing)