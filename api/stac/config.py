"""
Configuration management for the STAC module.
"""

from typing import Optional, List
from pathlib import Path
from sqlmodel import SQLModel
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
import logging
import os
import json
import enum
from rich.table import Table

class CostMethod(enum.Enum):
    local = "local"
    """Use a local approximation of the cost (multiplies the number of parameters)"""
    api = "api"
    """Use an official STAC API endpoint to fetch the cost (costing endpoint), which is more accurate but slower"""

class OutputFormat(enum.Enum):
    json = "json"
    table = "table"

    @staticmethod
    def to_json(items: List[SQLModel | str]) -> str:
        return json.dumps([
            item.model_dump(mode="json")
            if isinstance(item, SQLModel) 
            else item
            for item in items
        ])
    
    @staticmethod
    def to_table(items: List[SQLModel]) -> Table:
        table: Table = Table(title=items[0].__tablename__)
        headers: List[str] = [field for field in items[0].__fields__]
        for header in headers:
            table.add_column(header)
        for item in items:
            values = item.model_dump()
            table.add_row(*[str(values[field]) for field in headers])
        return table

class STACConfig(BaseSettings):
    """Configuration settings for STAC module."""
    
    # API Configuration
    base_url: str = Field(
        default="https://cds.climate.copernicus.eu/api",
        description="Base URL for Copernicus API"
    )
    catalogue_url: Optional[str] = Field(
        default=None,
        description="Catalogue URL (auto-generated if not provided)"
    )
    api_key: Optional[str] = Field(
        default=os.getenv("CDS_API_KEY", None),
        description="API key for authentication"
    )
    collection_route: str = Field(
        default=r"/catalogue/v1/collections/{dataset_id}",
        description="Collection endpoint"
    )
    retrieve_route: str = Field(
        default=r"/retrieve/v1/processes/{dataset_id}",
        description="Retrieve endpoint"
    )
    cost_route: str = Field(
        default=r"/retrieve/v1/processes/{dataset_id}/costing",
        description="Cost estimate endpoint"
    )
    
    # Request Configuration
    timeout: int = Field(default=60, ge=1, le=300, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=0, le=10, description="Maximum retry attempts")
    retry_delay: float = Field(default=1.0, ge=0.1, le=60.0, description="Delay between retries")
    rate_limit: int = Field(default=10, ge=1, le=100, description="Requests per minute")
    
    # Database Configuration
    database_path: Optional[str] = Field(
        default=None,
        description="Database file path"
    )
    connection_pool_size: int = Field(
        default=5, ge=1, le=50,
        description="Database connection pool size"
    )
    
    # Optimization Configuration
    default_budget_limit: float = Field(
        default=400.0, ge=0,
        description="Default budget limit for templates"
    )
    optimization_cache_size: int = Field(
        default=1000, ge=10, le=10000,
        description="Optimization results cache size"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    log_file: Optional[str] = Field(
        default="/tmp/copper.log",
        description="Log file path"
    )
    
    # Security Configuration
    max_file_size: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        ge=1024, le=100 * 1024 * 1024,
        description="Maximum file size for uploads"
    )
    allowed_file_extensions: list = Field(
        default=[".json", ".yaml", ".yml"],
        description="Allowed file extensions"
    )

    @property
    def cost_endpoint(self) -> str:
        return f"{self.base_url}{self.cost_route}?request_origin=ui"
    
    @field_validator('catalogue_url')
    def set_catalogue_url(cls, v, info):
        if v is None:
            base_url = info.data.get('base_url', 'https://cds.climate.copernicus.eu/api')
            return f"{base_url}/catalogue/v1/"
        return v
    
    @field_validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        env_level = os.getenv('LOG_LEVEL', None)
        if env_level:
            return env_level.upper()
        return v.upper()

# Global configuration instance
config = STACConfig()


def cost_headers(dataset_id: str) -> dict[str, str]:
    """
    Costing headers for the Copernicus API.
    """
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:141.0) Gecko/20100101 Firefox/141.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Content-Type": "application/json; charset=utf-8",
        "Origin": "https://cds.climate.copernicus.eu",
        "Sec-GPC": "1",
        "Connection": "keep-alive",
        "Referer": f"https://cds.climate.copernicus.eu/datasets/{dataset_id}?tab=download",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

def setup_logging():
    """Set up logging configuration."""
    log_level = getattr(logging, config.log_level)
    
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)
    
    # File handler if specified
    if config.log_file:
        file_handler = logging.FileHandler(config.log_file)
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True
    )
    
    return logging.getLogger(__name__)


def validate_file_path(file_path: Path) -> bool:
    """Validate file path for security."""
    try:
        # Resolve to absolute path and check for path traversal
        resolved_path = file_path.resolve()
        
        # Check file size
        if resolved_path.exists() and resolved_path.stat().st_size > config.max_file_size:
            return False
        
        # Check file extension
        if resolved_path.suffix.lower() not in config.allowed_file_extensions:
            return False
        
        # Ensure path doesn't escape working directory
        cwd = Path.cwd().resolve()
        if not str(resolved_path).startswith(str(cwd)):
            return False
        
        return True
    except (OSError, ValueError):
        return False


logger = setup_logging()