import os
import json
import logging
import httpx
import polars as pl

from math import prod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from sqlmodel import SQLModel, create_engine, Session, select, col

from .models import (
    CatalogLink,
    Collection,
    CollectionLink,
    CollectionRelType,
    CostEstimate,
    InputParameter,
    InputSchema,
    SchemaConstraints,
    Template,
    TemplateParameter,
    Tables,
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


def collection_from_id(
    collection_id: int, session: Optional[Session] = None
) -> Collection:
    """Get a collection from an ID."""
    logger.info(f"Getting collection from ID: {collection_id}")
    logger.info(f"Session: {session}")
    try:
        if session is None:
            session = Session(engine)
        return session.exec(
            select(Collection).where(Collection.id == collection_id)
        ).first()
    except Exception as e:
        logger.error(f"Error getting collection from ID: {e}")
        raise e


def collection_from_dataset_id(
    dataset_id: str, session: Optional[Session] = None
) -> Collection:
    """Get a collection from a dataset ID."""
    try:
        if session is None:
            session = Session(engine)
        with session:
            return session.exec(
                select(Collection).where(Collection.collection_id == dataset_id)
            ).first()
    except Exception as e:
        logger.error(f"Error getting collection from dataset ID: {e}")
        raise e


def template_parameters_from_id(
    template_id: int, session: Optional[Session] = None
) -> List[TemplateParameter]:
    if session is None:
        session = Session(engine)
    return list(
        session.exec(
            select(TemplateParameter).where(
                TemplateParameter.template_id == template_id
            )
        )
    )


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


def add_metadata(
    state: Dict[str, Any], dataset_id: str, template_name: str
) -> Dict[str, Any]:
    """Add metadata to a template state."""
    return {
        "metadata": {"dataset_id": dataset_id, "template_name": template_name},
        "parameters": state,
    }


def parse_metadata(state: Dict[str, Any]) -> Tuple[dict, dict]:
    """Parse metadata from a template state."""
    metadata = state.pop("metadata")
    parameters = state.pop("parameters")
    return metadata, parameters


# TODO: refactor submodule, clean stuff up


def list_non_null_columns(df: pl.DataFrame) -> list[str]:
    """List columns that do not have null values."""
    null_counts = df.null_count()
    return [column.name for column in null_counts if column.sum() == 0]


def list_non_null_fields(data: dict) -> list[str]:
    """List fields that do not have null values."""
    df = pl.DataFrame(data)
    return list_non_null_columns(df)


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
    constraints_url: Optional[str]
    _constraints: Optional[dict] = None

    def __init__(self, dataset_id: str):
        self.dataset_id = dataset_id
        self.session = Session(engine, expire_on_commit=False)
        self.parameters = self.fetch_parameters()
        self.collection = collection_from_dataset_id(self.dataset_id, self.session)

        if not self.constraints:
            logger.error(f"No constraints found for {self.dataset_id}")
            raise ValueError(f"No constraints found for {self.dataset_id}")

    def refresh(self):
        self.parameters = self.fetch_parameters()
        self.fetch_constraints()

    def fetch_parameters(self) -> List[InputParameter]:
        with self.session as session:
            return session.exec(
                select(InputParameter)
                .join(InputSchema, InputParameter.input_schema_id == InputSchema.id)
                .join(Collection, InputSchema.collection_id == Collection.id)
                .where(Collection.collection_id == self.dataset_id)
            ).fetchall()

    @property
    def input_schema(self) -> Optional[InputSchema]:
        with self.session as session:
            return session.exec(
                select(InputSchema).where(
                    InputSchema.collection_id == self.collection.id
                )
            ).first()

    @property
    def are_mandatory_params_stored(self) -> bool:
        with self.session as session:
            return (
                session.exec(
                    select(InputParameter)
                    .join(InputSchema, InputParameter.input_schema_id == InputSchema.id)
                    .join(Collection, InputSchema.collection_id == Collection.id)
                    .where(Collection.collection_id == self.dataset_id)
                    .where(col(InputParameter.is_mandatory).is_not(None))
                    .limit(1)
                ).one_or_none()
                is not None
            )

    @property
    def constraints_url(self) -> Optional[str]:
        links = self.session.exec(
            select(CollectionLink).where(
                CollectionLink.collection_id == self.collection.id
            )
        ).fetchall()
        for link in links:
            if link.rel == CollectionRelType.constraints:
                return link.url
        return None

    @property
    def constraints(self) -> Optional[dict]:
        # TODO: add a local db store for constraints JSON
        """Constraints on input parameters. Fetches the constraints from the API endpoint, only called if not already fetched."""
        if not self._constraints:
            with self.session:
                logger.info(
                    f"Input schema: {type(self.input_schema)} with constraints: {type(self.input_schema.schema_constraints)}"
                )
                if self.input_schema.schema_constraints:
                    self._constraints = self.input_schema.schema_constraints.constraints
                else:
                    logger.info(
                        f"No constraints found for {self.dataset_id}, fetching from API"
                    )
                    self.fetch_constraints()
        return self._constraints

    def fetch_constraints(self) -> Optional[dict]:
        """Fetches the constraints from the API endpoint, only called if not already fetched."""
        if not self.constraints_url:
            return None
        try:
            client = httpx.Client()
            response = client.get(self.constraints_url)
            self._constraints = response.json()
            with self.session as session:
                session.add(
                    SchemaConstraints(
                        input_schema_id=self.collection.input_schema.id,
                        collection_id=self.collection.id,
                        constraints=self._constraints,
                    )
                )
                session.commit()
            return self._constraints
        except Exception as e:
            logger.error(f"Error fetching constraints: {e}")
            return None

    @property
    def mandatory_parameters(self) -> List[str]:
        """Lists the names of the mandatory parameters if they are stored in the database.
        Else, fetches the constraints from URL, and stores the information as a boolean field.

        """
        if not self.are_mandatory_params_stored:
            logger.info(
                f"Mandatory parameters for {self.dataset_id} not stored, fetching from constraints"
            )
            if not self.constraints:
                raise ValueError(f"No constraints found for {self.dataset_id}")
            mandatory_fields: List[str] = list_non_null_fields(self.constraints)
            with self.session as session:
                input_parameters = session.exec(
                    select(InputParameter)
                    .join(InputSchema, InputParameter.input_schema_id == InputSchema.id)
                    .join(Collection, InputSchema.collection_id == Collection.id)
                    .where(Collection.collection_id == self.dataset_id)
                ).fetchall()
                for param in input_parameters:
                    if param.name in mandatory_fields:
                        param.is_mandatory = True
                    else:
                        param.is_mandatory = False

                session.add_all(input_parameters)
                session.commit()
            self.refresh()
        else:
            logger.info(
                f"Mandatory parameters for {self.dataset_id} stored, fetching from database"
            )

        return [param.name for param in self.parameters if param.is_mandatory]


def state_cost_estimate(data: dict) -> CostEstimate:
    """
    Estimate the cost of a template (in python dict format)
    """
    n_params: Dict[str, int] = {
        key: len(values) if isinstance(values, list) else 1
        for key, values in data.items()
    }
    return CostEstimate(
        cost=max(1, prod(n_params.values())),
        limit=-1,
        request_is_valid=True,
        invalid_reason=None,
    )


class TemplateUpdater:
    """
    A class to help with template operations.
    """

    dataset_id: str
    template_name: str
    template: Template
    collection: Collection
    _session: Optional[Session]

    @property
    def session(self):
        if not self._session:
            self._session = Session(engine, expire_on_commit=False)
        return self._session

    @property
    def parameters(self):
        return self.template.parameters

    @property
    def parameter_names(self) -> List[str]:
        with self._session as session:
            return list(
                session.exec(
                    select(TemplateParameter.name)
                    .where(TemplateParameter.template_id == self.template.id)
                    .distinct()
                ).fetchall()
            )

    @property
    def template_exists(self) -> bool:
        with self._session as session:
            return (
                session.exec(
                    select(Template).where(Template.name == self.template_name)
                ).first()
                is not None
            )

    @property
    def cost(self) -> float:
        return self.template.cost

    @staticmethod
    def list(limit: Optional[int] = None) -> List[Template]:
        with Session(engine, expire_on_commit=False) as session:
            query = select(Template)
            if limit:
                query = query.limit(limit)
            return list(session.exec(query).fetchall())

    def init_from_template(self, template: Template):
        self.template = template
        self.collection = collection_from_id(template.collection_id, self.session)
        self.dataset_id = self.collection.collection_id

        with self._session as session:
            session.merge(self.template)
            session.merge(self.collection)

    def init_from_name(self, template_name: str) -> bool:
        """Returns `True` if existing template found, `False` if not and create needed"""
        with self._session as session:
            self.template = session.exec(
                select(Template).where(Template.name == template_name)
            ).first()
            if not self.template:
                return False
            self.template_name = template_name
            self.collection = session.exec(
                select(Collection).where(Collection.id == self.template.collection_id)
            ).first()
            self.dataset_id = self.collection.collection_id
        return True

    def create_template(self, template_name: str, dataset_id: str):
        with self._session as session:
            self.collection = session.exec(
                select(Collection).where(Collection.collection_id == dataset_id)
            ).first()
            self.template = Template(
                name=template_name, collection_id=self.collection.id, cost=0
            )
            session.add(self.template)
            session.commit()

    @classmethod
    def from_json(cls, path: Optional[Path] = None, json_data: Optional[str] = None):
        if not path and not json_data:
            raise ValueError("Either path or json_data must be provided")

        if path:
            data = json.load(path.open())
        else:
            data = json.loads(json_data) if json_data else {}

        if not data:
            raise ValueError(f"Could not read JSON from file {path}")

        logger.debug(f"Loaded template from JSON: {data}")

        required_keys = ["metadata", "parameters"]
        if any(key not in data for key in required_keys):
            raise ValueError("Invalid JSON data, missing required keys")

        template, session = cls.create_template_from_dict(data)
        instance = cls(template=template, template_name=template.name)
        instance._session = session
        return instance

    def __init__(
        self,
        template_name: str,
        dataset_id: Optional[str] = None,
        template: Optional[Template] = None,
    ) -> None:
        self.dataset_id = dataset_id
        self.template_name = template_name
        self.template = None
        self.collection = None
        self._session = Session(engine, expire_on_commit=False)

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

    @classmethod
    def from_name(cls, template_name: str) -> "TemplateUpdater":
        template: Optional[Template] = cls.fetch_by_name(template_name)
        if template is None:
            raise ValueError(f"Template {template_name} not found")
        return cls(template_name, template.collection_id, template)

    @staticmethod
    def fetch_by_name(
        template_name: str, session: Optional[Session] = None
    ) -> Optional[Template]:
        """
        Fetches a template by its name, if it exists.

        Args:
            template_name: The name of the template to fetch.
            session: The session to use to fetch the template.

        Returns:
            The template if it exists, otherwise `None`.
        """
        if session is None:
            session = Session(engine, expire_on_commit=False)
        with session:
            template: Optional[Template] = session.exec(
                select(Template).where(Template.name == template_name)
            ).first()
        if template is None:
            return None
        return template

    def commit(self):
        with self._session as session:
            session.add(self.template)
            session.add_all(self.parameters)
            session.commit()

    def to_dict(self) -> Dict[str, Any]:
        serialized = {}
        with self._session:
            for parameter in self.parameters:
                if parameter.name not in serialized:
                    serialized[parameter.name] = [parameter.value]
                else:
                    if parameter.value not in serialized[parameter.name]:
                        serialized[parameter.name].append(parameter.value)
            return serialized

    def to_json(self, indent: Optional[int] = None, with_metadata: bool = True) -> str:
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
        metadata = {"dataset_id": self.dataset_id, "template_name": self.template_name}
        result = {"metadata": metadata, "parameters": state} if with_metadata else state
        return json.dumps(result, indent=indent)

    def refresh(self):
        with self._session as session:
            session.merge(self.template)
            session.merge(self.collection)
            session.refresh(self.template, ["parameters", "collection"])
            self.dataset_id = self.collection.collection_id

    def add_parameter_range(self, parameter_name: str, from_value: str, to_value: str):
        with self._session:
            for value in range(int(from_value), int(to_value) + 1):
                self.add_parameter(parameter_name, str(value))

    def add_parameter(self, parameter_name: str, parameter_value: str):
        with self._session as session:
            template = session.get(Template, self.template.id)
            new_parameter = TemplateParameter(
                template=template, name=parameter_name, value=parameter_value
            )
            session.add(new_parameter)
            template.parameters.append(new_parameter)
            session.commit()
            session.refresh(template, ["parameters"])
            self.template = template
            logger.debug(
                f"Added parameter {parameter_name} to template {self.template.name}"
            )

    def update_parameter_value(
        self, parameter_name: str, old_value: str, new_value: str
    ):
        with self._session as session:
            to_update = session.exec(
                select(TemplateParameter).where(
                    TemplateParameter.template_id == self.template.id,
                    TemplateParameter.name == parameter_name,
                    TemplateParameter.value == old_value,
                )
            ).first()
            if to_update is None:
                raise ValueError(f"Parameter {parameter_name} not found")
            to_update.value = new_value
            session.add(to_update)
            session.commit()

    def update_parameter_values(self, parameter_name: str, parameter_values: List[str]):
        with self._session as session:
            to_update = session.exec(
                select(TemplateParameter).where(
                    TemplateParameter.template_id == self.template.id,
                    TemplateParameter.name == parameter_name,
                )
            ).fetchall()
            existing_values = set(param.value for param in to_update)
            new_values = set(parameter_values).difference(existing_values)
            for value in new_values:
                self.add_parameter(parameter_name, value)
            for value in existing_values.difference(parameter_values):
                self.remove_parameter_value(parameter_name, value)

    def get_parameter_values(self, name: str) -> List[str]:
        """Returns all values for parameter name `name`."""
        with self._session:
            return [param.value for param in self.parameters if param.name == name]

    def remove_parameter_value(self, parameter_name: str, parameter_value: str):
        with self._session as session:
            template = session.get(Template, self.template.id)
            to_remove = session.exec(
                select(TemplateParameter).where(
                    TemplateParameter.template_id == template.id,
                    TemplateParameter.name == parameter_name,
                    TemplateParameter.value == parameter_value,
                )
            ).fetchall()
            if to_remove is None:
                raise ValueError(f"Parameter {parameter_name} not found")
            for param in to_remove:
                logger.debug(
                    f"Removing parameter value {param.value} for parameter {param.name} from template {self.template.name}"
                )
                session.delete(param)
                template.parameters.remove(param)
            session.commit()
            session.refresh(template, ["parameters"])
            self.template = template

    def remove_parameter(self, parameter_name: str):
        with self._session as session:
            template = session.get(Template, self.template.id)
            parameters = template.parameters
            parameter_values = [
                param for param in parameters if param.name == parameter_name
            ]
            if not parameter_values:  # TODO: check if this is correct
                raise ValueError(f"Parameter {parameter_name} not found")
            for param in parameter_values:
                session.delete(param)
                template.parameters.remove(param)
            session.commit()
            session.refresh(template, ["parameters"])
            self.template = template
            logger.debug(
                f"Removed parameter {parameter_name} from template {self.template.name}"
            )

    def from_dict(self, data: Dict[str, Any]):
        # TODO: find a way to set current state from a dict
        raise NotImplementedError("Be patient.")

    def allowed_parameters(self, hide_values: bool = False) -> List[SQLModel]:
        with self._session as session:
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

    def compute_cost(
        self, method: CostMethod, commit_update: bool = False
    ) -> CostEstimate:
        match method:
            case CostMethod.local:
                cost_estimate = self._estimate_cost()
            case CostMethod.api:
                cost_estimate = self._fetch_cost()
            case _:
                raise ValueError(f"Invalid cost method: {method}")

        if commit_update:
            with self._session as session:
                session.merge(self.template)
                session.refresh(self.template)
                session.commit()

        return cost_estimate

    def update_cost(self):
        self.compute_cost(CostMethod.local, commit_update=True)
        self.commit()

    def _estimate_cost(self) -> CostEstimate:
        data = self.to_dict()
        return state_cost_estimate(data)

    def _fetch_cost(self) -> CostEstimate:
        client = httpx.Client()
        endpoint = config.cost_endpoint.format(dataset_id=self.dataset_id)
        response = client.post(
            endpoint,
            json={"inputs": self.to_dict()},
            headers=cost_headers(self.dataset_id),
        )
        data = response.json()

        return CostEstimate.from_response(data)

    def delete(self):
        # TODO: when deleting, make sure cascade delete happens on parameters
        with self._session as session:
            logger.debug(f"Deleting template {self.template.name}")
            to_delete = session.exec(
                select(Template).where(Template.id == self.template.id)
            ).fetchall()
            for template in to_delete:
                for parameter in template.parameters:
                    session.delete(parameter)
                session.delete(template)
            session.commit()

    @staticmethod
    def create_template_from_dict(
        data: Dict[str, Any], session: Optional[Session] = None
    ) -> Tuple[Template, Session]:
        metadata, parameters = parse_metadata(data)
        if session is None:
            session = Session(engine, expire_on_commit=False)

        collection = collection_from_dataset_id(metadata["dataset_id"], session)
        template_name = metadata["template_name"]
        existing_parameters = []
        with session:
            existing_template = TemplateUpdater.fetch_by_name(template_name, session)
            if existing_template:
                logger.warning(
                    f"Template with name '{template_name}' already exists, updating it."
                )
                template = existing_template
                existing_parameters = template.parameters
            else:
                template = Template(
                    name=metadata["template_name"],
                    collection_id=collection.id,
                    cost=state_cost_estimate(parameters).cost,
                )
                session.add(template)

            entities = []

            for name, value in parameters.items():
                if name in existing_parameters:
                    # TODO: allow to update parameters, for now just skip
                    logger.warning(f"Parameter {name} already exists, skipping.")
                    continue
                if isinstance(value, list):
                    for v in value:
                        entities.append(
                            TemplateParameter(name=name, value=v, template=template)
                        )
                else:
                    entities.append(
                        TemplateParameter(name=name, value=value, template=template)
                    )

            session.add_all(entities)
            session.commit()
        return template, session

    def fetch_sub_templates(self, prefix: str = "sub") -> List[Template]:
        sub_template_prefix = f"{prefix}_{self.template_name}_"
        with self._session as session:
            return list(
                session.exec(
                    select(Template).where(
                        col(Template.name).like(f"{sub_template_prefix}%")
                    )
                )
            )


drop_existing = os.getenv("DROP_EXISTING", "false").lower() == "true"
create_db_and_tables(drop_existing=drop_existing)
