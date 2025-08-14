import os
import json
import logging
import httpx
import pandas as pd

from math import prod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import SQLModel, create_engine, Session, select

from .models import (
    CatalogLink, Collection, CollectionLink, CollectionRelType,
    CostEstimate, InputParameter, InputSchema,
    Keyword, Template, TemplateHistory, TemplateParameter,
    TemplateCostHistory, Tables,
    TemplateHistory
)
from .config import config, cost_headers, CostMethod


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


class CollectionBrowser:
    """
    A class to browse a collection.
    Allows to fetch relevant information from a collection.

    - Collection parameters
    - Constraints URL
    - Mandatory parameters
    - Input Schema
    - ... (to be added)
    # TODO: make this the main class for collection operations
    """
    collection: Collection
    session: Session
    parameters: List[InputParameter]
    dataset_id: str

    def __init__(self, dataset_id: str):
        self.dataset_id = dataset_id
        self.session = Session(engine)
        self.parameters = self.fetch_parameters()
        self.collection = collection_from_dataset_id(self.dataset_id)

    def refresh(self):
        self.parameters = self.fetch_parameters()

    def fetch_parameters(self) -> List[InputParameter]:
        with self.session as session:
            return session.exec(
                select(InputParameter)
                .join(InputSchema, InputParameter.input_schema_id == InputSchema.id)
                .join(Collection, InputSchema.collection_id == Collection.id)
                .where(Collection.collection_id == self.dataset_id)
                ).fetchall()
        
    @property
    def constraints_url(self) -> Optional[str]:
        links = self.session.exec(select(CollectionLink).where(CollectionLink.collection_id == self.collection.id)).fetchall()
        for link in links:
            if link.rel == CollectionRelType.constraints:
                return link.url
        return None

    @property
    def mandatory_parameters(self) -> List[str]:
        if not self.constraints_url:
            return []

        client = httpx.Client()
        response = client.get(self.constraints_url)
        json_data = response.json()
        data = pd.DataFrame(json_data)
        return (
            data.isna().sum()
            .reset_index(name="count_null")
            .rename(columns={"index": "parameter"})
            .query("count_null == 0")
            .parameter.tolist()
        )


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

    @staticmethod
    def list(limit: Optional[int] = None) -> List[Template]:
        with Session(engine) as session:
            query = select(Template)
            if limit:
                query = query.limit(limit)
            return list(session.exec(query).fetchall())
    
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
        
    @classmethod
    def from_json(cls, path: Optional[Path] = None, json_data: Optional[str] = None):
        if not path and not json_data:
            raise ValueError("Either path or json_data must be provided")

        if path:
            data = json.load(path.open())
        else:
            data = json.loads(json_data) if json_data else {}
        
        required_keys = ["metadata", "parameters"]
        if any(key not in data for key in required_keys):
            raise ValueError("Invalid JSON data, missing required keys")

        metadata, parameters = data["metadata"], data["parameters"]
        instance = cls(metadata['template_name'], metadata['dataset_id'])
        instance.parameters = [TemplateParameter(name=pname, value=pval) for pname, pdata in parameters.items() for pval in pdata]
        instance.template_history = [TemplateHistory(**history) for history in data['history']] if 'history' in data else []
        instance.commit()
        return instance
        

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
                if parameter.value not in serialized[parameter.name]:
                    serialized[parameter.name].append(parameter.value)
        return serialized

    def to_json(self, indent: Optional[int] = None) -> str:
        """
        Return a JSON string with the template state and metadata.
        The format is:
        {
            "dataset_id": "...",
            "template_name": "...",
            "parameters": [
                {
                    "name": "...",
                    "value": "..."
                },
                ...
            ]
        }
        """
        state = self.to_dict()
        metadata = {
            "dataset_id": self.dataset_id,
            "template_name": self.template_name
        }
        return json.dumps({"metadata": metadata, "parameters": state}, indent=indent)

    def refresh(self, session: Session):
        self.template = session.exec(select(Template).where(Template.name == self.template_name)).first()
        self.collection = session.exec(select(Collection).where(Collection.collection_id == self.dataset_id)).first()
        self.template_history = session.exec(select(TemplateHistory).where(TemplateHistory.template_id == self.template.id)).fetchall()
        self.parameters = session.exec(select(TemplateParameter).where(TemplateParameter.template_id == self.template.id)).fetchall()
    
    def add_parameter_range(self, parameter_name: str, from_value: str, to_value: str):
        with Session(engine) as session:
            self.refresh(session)
            for value in range(int(from_value), int(to_value) + 1):
                self.add_parameter(parameter_name, str(value))

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

    def update_parameter(self, parameter_name: str, old_value: str, new_value: str):
        with Session(engine) as session:
            self.refresh(session)
            to_update = session.exec(select(TemplateParameter).where(TemplateParameter.template_id == self.template.id, TemplateParameter.name == parameter_name, TemplateParameter.value == old_value)).first()
            if to_update is None:
                raise ValueError(f"Parameter {parameter_name} not found")
            to_update.value = new_value
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

    def allowed_parameters(self, hide_values: bool = False) -> List[SQLModel]:
        with Session(engine) as session:
            collection_parameters = session.exec(
                select(InputParameter, InputSchema, Collection)
                .join(InputSchema, InputParameter.input_schema_id == InputSchema.id)
                .join(Collection, InputSchema.collection_id == Collection.id)
                .where(Collection.id == self.collection.id)
            ).fetchall()
            if hide_values:
                params = []
                for param, schema, collection in collection_parameters:
                    delattr(param, "values")
                    params.append(param)
                return params
            return [param for param, schema, collection in collection_parameters]

    def compute_cost(self, method: CostMethod) -> CostEstimate:
        match method:
            case CostMethod.local:
                return self._estimate_cost()
            case CostMethod.api:
                return self._fetch_cost()
            case _:
                raise ValueError(f"Invalid cost method: {method}")

    def _estimate_cost(self) -> CostEstimate:
        data = self.to_dict()
        n_params: Dict[str, int] = {
            key : len(values) if isinstance(values, list) else 1
            for key, values in data.items()
        }
        return CostEstimate(
            cost=prod(n_params.values()),
            limit=-1,
            request_is_valid=True,
            invalid_reason=None
        )
    
    def _fetch_cost(self) -> CostEstimate:
        client = httpx.Client()
        endpoint = config.cost_endpoint.format(dataset_id=self.dataset_id)
        response = client.post(endpoint, json={"inputs": self.to_dict()}, headers=cost_headers(self.dataset_id))
        data = response.json()

        return CostEstimate.from_response(data)

    def delete(self):
        with Session(engine) as session:
            session.delete(self.template)
            session.commit()

drop_existing = os.getenv("DROP_EXISTING", "false").lower() == "true"
create_db_and_tables(drop_existing=drop_existing)