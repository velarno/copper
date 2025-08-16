import json
import enum
from dataclasses import dataclass
from sqlmodel import SQLModel, Relationship, Enum, Column, Field, JSON, select, Session
from sqlmodel.sql.expression import SelectOfScalar
import logging
from typing import Optional, Dict, Any, List, Literal, TypedDict, Union, TypeVar
from datetime import datetime

logger = logging.getLogger(__name__)

retrieve_url_pattern = r'https://cds.climate.copernicus.eu/api/retrieve/v1/processes/{dataset_id}'

Entity = TypeVar("Entity", bound=SQLModel)

class CatalogRelType(enum.Enum):
    child = "child"
    parent = "parent"
    self = "self"
    root = "root"

class CollectionRelType(enum.Enum):
    self = "self"
    root = "root"
    parent = "parent"
    license = "license"
    form = "form"
    constraints = "constraints"
    retrieve = "retrieve"
    costing_api = "costing_api"
    messages = "messages"
    layout = "layout"
    related = "related"

class ParamType(enum.Enum):
    enum = "enum"
    array = "array"
    number = "number"
    string = "string"
    boolean = "boolean"

## TYPES

VariableType = Literal["string", "integer","boolean"]
ArrayType = Literal["array"]

## MODELS

class CatalogLink(SQLModel, table=True):
    __tablename__ = "catalog_link"
    id: Optional[int] = Field(default=None, primary_key=True)
    collection_url: str = Field(..., description="Collection URL", unique=True)
    rel: CatalogRelType = Field(sa_column=Column(Enum(CatalogRelType)), description="Relative link to the collection")
    title: Optional[str] = Field(None, description="Collection title")
    mime_type: Optional[str] = Field(None, description="MIME type of the collection")
    created_at: datetime = Field(..., description="Creation timestamp", default_factory=datetime.now)
    updated_at: datetime = Field(..., description="Last update timestamp", default_factory=datetime.now)

class Collection(SQLModel, table=True):
    __tablename__ = "collection"
    id: Optional[int] = Field(default=None, primary_key=True)
    # TODO: disambiguate this vs collection.id FK in other tables, maybe call it dataset_id ?
    collection_id: str = Field(..., description="Collection identifier")
    title: str = Field(..., description="Collection title")
    description: str = Field(..., description="Collection description")
    created_at: datetime = Field(..., description="Creation timestamp", default_factory=datetime.now)
    updated_at: datetime = Field(..., description="Last update timestamp", default_factory=datetime.now)
    doi: Optional[str] = Field(None, description="DOI of the collection")

    keywords: List["Keyword"] = Relationship(back_populates="collection", sa_relationship_kwargs={"lazy": "selectin"})
    links: List["CollectionLink"] = Relationship(back_populates="collection", sa_relationship_kwargs={"lazy": "selectin"})
    input_schema: Optional["InputSchema"] = Relationship(back_populates="collection", sa_relationship_kwargs={"lazy": "selectin"})

    @classmethod
    def from_response(cls, data: Dict[str, Any]) -> "Collection":
        return cls(
            collection_id=data["id"],
            title=data["title"],
            description=data["description"],
            created_at=datetime.fromisoformat(data["published"]),
            updated_at=datetime.fromisoformat(data["updated"]),
            doi=data.get("doi", None)
        )

    @property
    def retrieve_url(self) -> str:
        return retrieve_url_pattern.format(dataset_id=self.collection_id)

class Keyword(SQLModel, table=True):
    __tablename__ = "keyword"
    id: Optional[int] = Field(default=None, primary_key=True)
    collection_id: int = Field(default=None, foreign_key="collection.id")
    keyword: str = Field(..., description="Keyword")
    created_at: datetime = Field(..., description="Creation timestamp", default_factory=datetime.now)
    updated_at: datetime = Field(..., description="Last update timestamp", default_factory=datetime.now)
    collection: Optional[Collection] = Relationship(back_populates="keywords", sa_relationship_kwargs={"lazy": "selectin"})

class CollectionLink(SQLModel, table=True):
    __tablename__ = "collection_link"
    id: Optional[int] = Field(default=None, primary_key=True)
    collection_id: int = Field(default=None, foreign_key="collection.id")
    url: str = Field(..., description="URL of the collection link")
    rel: CollectionRelType = Field(sa_column=Column(Enum(CollectionRelType)), description="Relative link to the collection")
    mime_type: Optional[str] = Field(None, description="MIME type of the collection link")
    title: Optional[str] = Field(None, description="Title of the collection link")
    created_at: datetime = Field(..., description="Creation timestamp", default_factory=datetime.now)

    collection: Optional[Collection] = Relationship(back_populates="links", sa_relationship_kwargs={"lazy": "selectin"})

class StacEnumType(TypedDict):
    type: VariableType
    enum: List[str]

class StacArrayType(TypedDict):
    type: ArrayType
    items: StacEnumType

@dataclass
class SingleEnumVariable:
    title: str
    name: str
    schema: StacEnumType
    choice: str = "one_or_many"

    @property
    def type(self) -> VariableType:
        return self.schema["type"]

    @property
    def values(self) -> List[str]:
        return self.schema["enum"]
    
@dataclass
class SingleArrayVariable:
    """
    A variable that can take many values, possible choices are stored as array of strings.
    """
    title: str
    name: str
    schema: StacArrayType
    choice: str = "one_or_many"

    @property
    def items(self) -> StacEnumType:
        return self.schema["items"]

    @property
    def values(self) -> List[str]:
        return self.items["enum"]

    @property
    def type(self) -> VariableType:
        return self.items["type"]

@dataclass
class NumberArrayVariable:
    """
    A variable that is an array of numbers. Not to be confused with a variable that has multiple allowed
    values, documented in the schema as an enum array.
    """
    title: str
    name: str
    schema: StacArrayType
    choice: str = "one"

    @property
    def values(self) -> List[float]:
        return self.schema["default"]

    @property
    def type(self) -> VariableType:
        return self.schema["items"]["type"]

    @property
    def dimensions(self) -> List[str]:
        return [self.schema["minItems"], self.schema["maxItems"]]

StacVariable = Union[SingleArrayVariable, SingleEnumVariable, NumberArrayVariable]


def infer_type(name: str, json_schema: Dict[str, Any]) -> StacVariable:
    if "schema" in json_schema:
        if "enum" in json_schema["schema"]:
            return SingleEnumVariable(name=name, title=json_schema["title"], schema=json_schema["schema"])
        elif "default" in json_schema["schema"]:
            return NumberArrayVariable(name=name, title=json_schema["title"], schema=json_schema["schema"])
        elif "items" in json_schema["schema"]:
            return SingleArrayVariable(name=name, title=json_schema["title"], schema=json_schema["schema"])
        else:
            raise ValueError("Unsupported input data", json_schema)
    raise ValueError("Invalid input data", json_schema)

def parse_dataset_inputs(json_data: Dict[str, Any]) -> List[SingleArrayVariable | SingleEnumVariable]:
    """Parse the dataset inputs from the JSON data.
    
    Args:
        json_data: The JSON data to parse. Usually, the values of the "inputs" key of the response data.

    Returns:
        A list of SingleArrayVariable or SingleEnumVariable objects.
    """
    inputs = []
    for name, value in json_data.items():
        logger.info(f"Parsing input {name} with value {value}")
        inputs.append(infer_type(name, value))
    return inputs

class InputSchema(SQLModel, table=True):
    __tablename__ = "input_schema"
    id: Optional[int] = Field(default=None, primary_key=True)
    collection_id: int = Field(..., foreign_key="collection.id", description="Collection identifier")
    created_at: datetime = Field(..., description="Creation timestamp", default_factory=datetime.now)
    updated_at: datetime = Field(..., description="Last update timestamp", default_factory=datetime.now)

    collection: Optional["Collection"] = Relationship(back_populates="input_schema", sa_relationship_kwargs={"lazy": "selectin"})
    parameters: List["InputParameter"] = Relationship(back_populates="input_schema", sa_relationship_kwargs={"lazy": "selectin"})

    @classmethod
    def create_with_parameters(cls, response_data: Dict[str, Any], collection: Collection):
        """Create an input schema with parameters from the response data."""
        if "inputs" in response_data:
            inputs = response_data["inputs"]
        else:
            inputs = response_data

        input_schema = cls(collection=collection)
        for input_var in parse_dataset_inputs(inputs):
            input_schema.parameters.append(
                InputParameter(
                    title=input_var.title,
                    name=input_var.name,
                    type=input_var.type,
                    values=input_var.values,
                    choice=input_var.choice
                )
            )
        return input_schema

class InputParameter(SQLModel, table=True):
    __tablename__ = "input_parameter"
    id: Optional[int] = Field(default=None, primary_key=True)
    input_schema_id: int = Field(..., foreign_key="input_schema.id", description="Input schema identifier")
    name: str = Field(..., description="Parameter name")
    title: str = Field(..., description="Parameter name")
    type: ParamType = Field(sa_column=Column(Enum(ParamType)), description="Parameter type")
    values: List[str] = Field(sa_column=Column(JSON), description="Parameter values")
    choice: str = Field(..., description="Choice of the variable")
    constraints: List["InputParameterConstraint"] = Relationship(back_populates="input_parameter")
    input_schema: Optional["InputSchema"] = Relationship(back_populates="parameters", sa_relationship_kwargs={"lazy": "selectin"})

class InputParameterConstraint(SQLModel, table=True):
    __tablename__ = "input_parameter_constraint"
    id: Optional[int] = Field(default=None, primary_key=True)
    input_parameter_id: int = Field(..., foreign_key="input_parameter.id", description="Input parameter identifier")
    constraint: str = Field(..., description="Constraint")
    created_at: datetime = Field(..., description="Creation timestamp", default_factory=datetime.now)
    updated_at: datetime = Field(..., description="Last update timestamp", default_factory=datetime.now)
    input_parameter: Optional["InputParameter"] = Relationship(back_populates="constraints", sa_relationship_kwargs={"lazy": "selectin"})

__tables__ = [
    Collection,
    CatalogLink,
    InputSchema,
    Keyword,
    CollectionLink,
    InputParameter,
    InputParameterConstraint,
]

@dataclass
class TableFilter:
    filter_string: str
    table_name: Optional[str] = None
    field: Optional[str] = None
    value: Optional[str] = None
    is_valid: bool = False

class Tables(enum.Enum):
    collection = "collection"
    catalog_link = "catalog_link"
    input_schema = "input_schema"
    keyword = "keyword"
    collection_link = "collection_link"
    input_parameter = "input_parameter"
    input_parameter_constraint = "input_parameter_constraint"
    template = "template"
    template_parameter = "template_parameter"
    template_history = "template_history"
    template_cost_history = "template_cost_history"

    @staticmethod
    def from_name(name: str) -> Optional["Tables"]:
        return next((table for table in Tables if table.value == name), None)

    @property
    def model(self) -> SQLModel:
        return next(table for table in __tables__ if table.__tablename__ == self.value)

    @property
    def relationship_names(self) -> List[str]:
        return [str(rel) for rel in self.model.__sqlmodel_relationships__]

    @property
    def immediate_parent(self) -> Optional["Tables"]:
        parent_names = self.relationship_names
        if not parent_names:
            return None
        parent = Tables.from_name(parent_names[0])
        if not parent:
            return None
        return parent
    
    @property
    def parent_foreign_key(self) -> Optional[str]:
        parent: Optional[Tables] = self.immediate_parent
        if not parent:
            return None
        candidate_column = f"{parent.table_name}_id"
        if candidate_column in self.fields:
            return candidate_column
        return None

    @property
    def parent_identifier(self) -> Optional[int]:
        parent: Optional[Tables] = self.immediate_parent
        if not parent:
            return None
        return getattr(self.model, self.parent_foreign_key)

    @property
    def parent_join(self) -> Optional[SelectOfScalar]:
        parent: Optional[Tables] = self.immediate_parent
        if not parent:
            return None
        return select(self.model, parent.model).join(parent.model, self.parent_identifier == parent.model.id)

    @property
    def table_name(self) -> str:
        return self.model.__tablename__

    @property
    def fields(self) -> List[str]:
        return [field for field in self.model.__fields__]

    def validate_filter_string(self, expression: str) -> TableFilter:
        """Validate a filter string for a table. Filters are of the form `table.field=value`.
        
        Args:
            expression: The filter string to validate.

        Returns:
            A TableFilter object.
        """
        expression = expression.strip()
        filter = TableFilter(filter_string=expression)
        if not expression.startswith(self.table_name):
            return filter
        allowed_expressions = [f"{self.table_name}.{field}" for field in self.fields]
        matching_expression = next((expr for expr in allowed_expressions if expression.startswith(expr)), None)
        if not matching_expression:
            return filter
        remainder = expression[len(matching_expression):].strip()
        if not remainder.startswith("="):
            return filter
        filter.value = remainder[1:].strip()
        filter.field = matching_expression.removeprefix(self.table_name + ".").strip()
        filter.table_name = self.table_name
        filter.is_valid = True
        return filter

    def apply_filter(self, filter: TableFilter, session: Session) -> List[SQLModel]:
        """Apply a filter to a table. Returns a sequence of SQLModel objects.
        
        Args:
            filter: The filter to apply.
        """
        if not filter.is_valid:
            return []
        query = select(self.model)
        if filter.field:
            query = query.where(getattr(self.model, filter.field) == filter.value)
        return list(session.exec(query).fetchall())


class Template(SQLModel, table=True):
    __tablename__ = "template"
    id: Optional[int] = Field(default=None, primary_key=True)
    collection_id: int = Field(..., foreign_key="collection.id", description="Collection identifier")
    name: str = Field(..., description="Template name")
    created_at: datetime = Field(..., description="Creation timestamp", default_factory=datetime.now)
    updated_at: datetime = Field(..., description="Last update timestamp", default_factory=datetime.now)
    cost: Optional[float] = Field(default=0, description="Cost of the template")

    parameters: List["TemplateParameter"] = Relationship(back_populates="template", sa_relationship_kwargs={"lazy": "selectin"})
    history: List["TemplateHistory"] = Relationship(back_populates="template", sa_relationship_kwargs={"lazy": "selectin"})

class TemplateParameter(SQLModel, table=True):
    __tablename__ = "template_parameter"
    id: Optional[int] = Field(default=None, primary_key=True)
    template_id: int = Field(..., foreign_key="template.id", description="Template identifier", ondelete="CASCADE")
    name: str = Field(..., description="Parameter name")
    value: str = Field(..., description="Parameter value")
    created_at: datetime = Field(..., description="Creation timestamp", default_factory=datetime.now)
    template: Optional["Template"] = Relationship(back_populates="parameters", sa_relationship_kwargs={"lazy": "selectin"})

class TemplateHistory(SQLModel, table=True):
    __tablename__ = "template_history"
    id: Optional[int] = Field(default=None, primary_key=True)
    template_id: int = Field(..., foreign_key="template.id", description="Template identifier", ondelete="CASCADE")
    data: Dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(..., description="Creation timestamp", default_factory=datetime.now)
    template: Optional["Template"] = Relationship(back_populates="history", sa_relationship_kwargs={"lazy": "selectin"})
    cost_history: Optional["TemplateCostHistory"] = Relationship(back_populates="history", sa_relationship_kwargs={"lazy": "selectin"})

class TemplateCostHistory(SQLModel, table=True):
    __tablename__ = "template_cost_history"
    id: Optional[int] = Field(default=None, primary_key=True)
    history_id: int = Field(..., foreign_key="template_history.id", description="History identifier", ondelete="CASCADE")
    cost: float = Field(..., description="Cost of the template")
    limit: float = Field(..., description="Limit of the template")
    request_is_valid: bool = Field(..., description="Whether the request is valid")
    invalid_reason: Optional[str] = Field(None, description="Reason the request is invalid")
    history: Optional["TemplateHistory"] = Relationship(back_populates="cost_history", sa_relationship_kwargs={"lazy": "selectin"})

@dataclass
class CostEstimate:
    cost: float
    limit: float
    request_is_valid: bool
    invalid_reason: Optional[str] = None

    @classmethod
    def from_response(cls, response: Dict[str, Any]) -> "CostEstimate":
        return cls(
            cost=response["cost"],
            limit=response["limit"],
            request_is_valid=response["request_is_valid"],
            invalid_reason=response["invalid_reason"]
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            attr : getattr(self, attr)
            for attr in self.__dataclass_fields__
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())