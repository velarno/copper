import os
import enum
from dataclasses import dataclass
from sqlmodel import SQLModel, Relationship, Enum, Column, Field, JSON
import logging
from typing import Optional, Dict, Any, List, Literal, TypedDict, Union
from datetime import datetime

logger = logging.getLogger(__name__)

retrieve_url_pattern = r'https://cds.climate.copernicus.eu/api/retrieve/v1/processes/{dataset_id}'

        

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

class ParamType(enum.Enum):
    enum = "enum"
    array = "array"

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
    collection_id: str = Field(..., description="Collection identifier")
    title: str = Field(..., description="Collection title")
    description: str = Field(..., description="Collection description")
    created_at: datetime = Field(..., description="Creation timestamp", default_factory=datetime.now)
    updated_at: datetime = Field(..., description="Last update timestamp", default_factory=datetime.now)
    doi: Optional[str] = Field(None, description="DOI of the collection")

    keywords: List["Keyword"] = Relationship(back_populates="collection")
    links: List["CollectionLink"] = Relationship(back_populates="collection")
    input_schema: Optional["InputSchema"] = Relationship(back_populates="collection")

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
    collection: Optional[Collection] = Relationship(back_populates="keywords")

class CollectionLink(SQLModel, table=True):
    __tablename__ = "collection_link"
    id: Optional[int] = Field(default=None, primary_key=True)
    collection_id: int = Field(default=None, foreign_key="collection.id")
    url: str = Field(..., description="URL of the collection link")
    rel: CollectionRelType = Field(sa_column=Column(Enum(CollectionRelType)), description="Relative link to the collection")
    mime_type: Optional[str] = Field(None, description="MIME type of the collection link")
    title: Optional[str] = Field(None, description="Title of the collection link")
    created_at: datetime = Field(..., description="Creation timestamp", default_factory=datetime.now)

    collection: Optional[Collection] = Relationship(back_populates="links")

class StacEnumType(TypedDict):
    type: VariableType
    enum: List[str]

class StacArrayType(TypedDict):
    type: ArrayType
    items: StacEnumType

@dataclass
class SingleEnumVariable:
    title: str
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


def infer_type(json_schema: Dict[str, Any]) -> StacVariable:
    if "schema" in json_schema:
        if "enum" in json_schema["schema"]:
            return SingleEnumVariable(title=json_schema["title"], schema=json_schema["schema"])
        elif "default" in json_schema["schema"]:
            return NumberArrayVariable(title=json_schema["title"], schema=json_schema["schema"])
        elif "items" in json_schema["schema"]:
            return SingleArrayVariable(title=json_schema["title"], schema=json_schema["schema"])
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
        inputs.append(infer_type(value))
    return inputs

class InputSchema(SQLModel, table=True):
    __tablename__ = "input_schema"
    id: Optional[int] = Field(default=None, primary_key=True)
    collection_id: int = Field(..., foreign_key="collection.id", description="Collection identifier")
    created_at: datetime = Field(..., description="Creation timestamp", default_factory=datetime.now)
    updated_at: datetime = Field(..., description="Last update timestamp", default_factory=datetime.now)

    collection: Optional["Collection"] = Relationship(back_populates="input_schema")
    parameters: List["InputParameter"] = Relationship(back_populates="input_schema")

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
    title: str = Field(..., description="Parameter name")
    type: ParamType = Field(sa_column=Column(Enum(ParamType)), description="Parameter type")
    values: List[str] = Field(sa_column=Column(JSON), description="Parameter values")
    choice: str = Field(..., description="Choice of the variable")
    
    input_schema: Optional["InputSchema"] = Relationship(back_populates="parameters")


__tables__ = [
    Collection,
    CatalogLink,
    InputSchema,
    Keyword,
    CollectionLink,
    InputParameter,
]


class Tables(enum.Enum):
    collections = "collection"
    catalog_links = "catalog_link"
    input_schemas = "input_schema"
    keywords = "keyword"
    collection_links = "collection_link"
    parameters = "input_parameter"

    @property
    def table(self) -> SQLModel:
        return next(table for table in __tables__ if table.__tablename__ == self.value)

# class CollectionInputSchema(BaseModel):
#     """Model for complete collection input schemas."""
#     id: Optional[int] = None
#     collection_id: str = Field(..., description="Collection identifier")
#     schema_data: Dict[str, Any] = Field(default_factory=dict, description="Raw schema data")
#     input_parameters: List[SingleArrayVariable | SingleEnumVariable] = Field(default_factory=list, description="Parsed input parameters")
#     discovered_at: Optional[datetime] = Field(None, description="Discovery timestamp")
#     updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


# class ConstraintSet(BaseModel):
#     """Model for STAC constraint sets."""
#     id: Optional[int] = None
#     collection_id: str = Field(..., description="Collection identifier")
#     constraint_set_id: str = Field(..., description="Constraint set identifier")
#     variables: List[str] = Field(default_factory=list, description="Available variables")
#     daily_statistics: List[str] = Field(default_factory=list, description="Daily statistics")
#     frequencies: List[str] = Field(default_factory=list, description="Available frequencies")
#     time_zones: List[str] = Field(default_factory=list, description="Available time zones")
#     years: List[str] = Field(default_factory=list, description="Available years")
#     months: List[str] = Field(default_factory=list, description="Available months")
#     days: List[str] = Field(default_factory=list, description="Available days")
#     product_types: List[str] = Field(default_factory=list, description="Available product types")
#     discovered_at: Optional[datetime] = Field(None, description="Discovery timestamp")


# class Template(BaseModel):
#     """Model for STAC request templates."""
#     id: Optional[int] = None
#     name: str = Field(..., min_length=1, max_length=255, description="Template name")
#     collection_id: str = Field(..., min_length=1, max_length=255, description="Collection identifier")
#     template_data: Dict[str, Any] = Field(default_factory=dict, description="Template request data")
#     variables: List[str] = Field(default_factory=list, min_items=0, max_items=50, description="Template variables")
#     estimated_cost: Optional[float] = Field(None, ge=0, description="Estimated cost (must be non-negative)")
#     budget_limit: float = Field(400.0, gt=0, description="Budget limit (must be positive)")
#     is_within_budget: Optional[bool] = Field(None, description="Whether within budget")
#     is_valid: Optional[bool] = Field(None, description="Whether template is valid")
#     validation_errors: List[str] = Field(default_factory=list, max_items=100, description="Validation errors")
#     constraint_set_id: Optional[str] = Field(None, max_length=255, description="Constraint set identifier")
#     created_at: Optional[datetime] = Field(None, description="Creation timestamp")
#     updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    
#     @field_validator('name')
#     def validate_name(cls, v):
#         if not re.match(r'^[a-zA-Z0-9_-]+$', v):
#             raise ValueError('Template name can only contain alphanumeric characters, underscores, and hyphens')
#         return v
    
#     @field_validator('collection_id')
#     def validate_collection_id(cls, v):
#         if not re.match(r'^[a-zA-Z0-9_-]+$', v):
#             raise ValueError('Collection ID can only contain alphanumeric characters, underscores, and hyphens')
#         return v
    
#     @field_validator('variables')
#     def validate_variables(cls, v):
#         if v:
#             for var in v:
#                 if not isinstance(var, str) or not var.strip():
#                     raise ValueError('All variables must be non-empty strings')
#         return v
    
#     @field_validator('created_at', 'updated_at', mode='before')
#     def ensure_timezone_aware(cls, v):
#         if v and isinstance(v, datetime) and v.tzinfo is None:
#             return v.replace(tzinfo=timezone.utc)
#         return v
    
#     @model_validator(mode='after')
#     def validate_budget_relationship(self):
#         estimated_cost = self.estimated_cost
#         budget_limit = self.budget_limit
#         is_within_budget = self.is_within_budget
        
#         if estimated_cost is not None and budget_limit is not None:
#             if is_within_budget is None:
#                 self.is_within_budget = estimated_cost <= budget_limit
#             elif is_within_budget != (estimated_cost <= budget_limit):
#                 raise ValueError('is_within_budget value inconsistent with estimated_cost and budget_limit')
        
#         return self


# class TemplateHistory(BaseModel):
#     """Model for template history tracking."""
#     id: Optional[int] = None
#     template_id: int = Field(..., description="Template identifier")
#     action: str = Field(..., description="Action performed", pattern="^(create|update|validate|estimate)$")
#     old_data: Optional[Dict[str, Any]] = Field(None, description="Previous template data")
#     new_data: Optional[Dict[str, Any]] = Field(None, description="New template data")
#     cost_estimate: Optional[float] = Field(None, description="Cost estimate")
#     validation_result: Optional[Dict[str, Any]] = Field(None, description="Validation result")
#     performed_at: Optional[datetime] = Field(None, description="Action timestamp")


# class CostEstimate(BaseModel):
#     """Model for cost estimation results."""
#     template_name: str = Field(..., min_length=1, description="Template name")
#     estimated_cost: float = Field(..., ge=0, description="Estimated cost (must be non-negative)")
#     budget_limit: float = Field(..., gt=0, description="Budget limit (must be positive)")
#     is_within_budget: bool = Field(..., description="Whether within budget")
#     breakdown: Dict[str, Any] = Field(default_factory=dict, description="Cost breakdown")
#     warnings: List[str] = Field(default_factory=list, max_items=50, description="Cost warnings")
#     estimated_at: datetime = Field(
#         default_factory=lambda: datetime.now(timezone.utc), 
#         description="Estimation timestamp"
#     )
    
#     @model_validator(mode='after')
#     def validate_cost_relationship(self):
#         estimated_cost = self.estimated_cost
#         budget_limit = self.budget_limit
#         is_within_budget = self.is_within_budget
        
#         if estimated_cost is not None and budget_limit is not None:
#             expected_within_budget = estimated_cost <= budget_limit
#             if is_within_budget != expected_within_budget:
#                 raise ValueError('is_within_budget value inconsistent with estimated_cost and budget_limit')
        
#         return self


# class ValidationResult(BaseModel):
#     """Model for request validation results."""
#     template_name: str = Field(..., description="Template name")
#     is_valid: bool = Field(..., description="Whether request is valid")
#     errors: List[str] = Field(default_factory=list, description="Validation errors")
#     warnings: List[str] = Field(default_factory=list, description="Validation warnings")
#     constraint_violations: List[str] = Field(default_factory=list, description="Constraint violations")
#     suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")
#     validated_at: datetime = Field(default_factory=datetime.now, description="Validation timestamp")


# class OptimizationResult(BaseModel):
#     """Model for request optimization results."""
#     template_name: str = Field(..., description="Template name")
#     original_cost: float = Field(..., description="Original cost")
#     optimized_cost: float = Field(..., description="Optimized cost")
#     savings: float = Field(..., description="Cost savings")
#     optimization_strategy: str = Field(..., description="Strategy used")
#     changes: Dict[str, Any] = Field(default_factory=dict, description="Changes made")
#     is_within_budget: bool = Field(..., description="Whether within budget")
#     optimized_at: datetime = Field(default_factory=datetime.now, description="Optimization timestamp")