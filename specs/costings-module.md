# Copernicus STAC Costings Module Design Specification

## Common names & Variables

```bash
CDS_URL="https://cds.climate.copernicus.eu/api"
CDS_COL="/catalogue/v1/collections"
```

## Overview

The STAC Costings Module is a comprehensive tool for interacting with Copernicus Climate Data Store (CDS) APIs to validate requests, check costs, and manage budget constraints. This module extends the existing STAC functionality to include cost estimation, request validation, and template management with local DuckDB storage.

## Architecture Changes

### Module Structure
```
api/
├── stac/
│   ├── __init__.py
│   ├── commands.py          # CLI commands (existing + new costings commands)
│   ├── utils.py             # Utility functions (existing + new costings utils)
│   ├── models.py            # Pydantic models for data structures
│   ├── client.py            # API client for Copernicus endpoints
│   ├── optimizer.py         # Request optimization logic
│   └── database.py          # Database operations for templates and costings
```

### Database Schema

#### Collections Table (existing)
```sql
CREATE TABLE stac_collections (
    id INTEGER PRIMARY KEY,
    collection_id TEXT UNIQUE,
    title TEXT,
    description TEXT,
    published_at TEXT,
    modified_at TEXT,
    doi TEXT
);
```

#### Variables Table (new)
```sql
CREATE TABLE stac_variables (
    id INTEGER PRIMARY KEY,
    collection_id TEXT,
    variable_name TEXT,
    description TEXT,
    units TEXT,
    available_statistics TEXT,  -- JSON array
    time_resolution TEXT,
    compatible_variables TEXT,  -- JSON array
    temporal_constraints TEXT,  -- JSON object
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES stac_collections(collection_id)
);
```

#### Constraints Table (new)
```sql
CREATE TABLE stac_constraints (
    id INTEGER PRIMARY KEY,
    collection_id TEXT,
    constraint_set_id TEXT,
    variables TEXT,  -- JSON array
    daily_statistics TEXT,  -- JSON array
    frequencies TEXT,  -- JSON array
    time_zones TEXT,  -- JSON array
    years TEXT,  -- JSON array
    months TEXT,  -- JSON array
    days TEXT,  -- JSON array
    product_types TEXT,  -- JSON array
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES stac_collections(collection_id)
);
```

#### Templates Table (new)
```sql
CREATE TABLE stac_templates (
    id INTEGER PRIMARY KEY,
    template_name TEXT UNIQUE,
    collection_id TEXT,
    template_data TEXT,  -- JSON object
    variables TEXT,  -- JSON array
    estimated_cost REAL,
    budget_limit REAL DEFAULT 400.0,
    is_within_budget BOOLEAN,
    is_valid BOOLEAN,
    validation_errors TEXT,  -- JSON array
    constraint_set_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES stac_collections(collection_id),
    FOREIGN KEY (constraint_set_id) REFERENCES stac_constraints(constraint_set_id)
);
```

#### Template History Table (new)
```sql
CREATE TABLE stac_template_history (
    id INTEGER PRIMARY KEY,
    template_id INTEGER,
    action TEXT,  -- 'create', 'update', 'validate', 'estimate'
    old_data TEXT,  -- JSON object (previous state)
    new_data TEXT,  -- JSON object (new state)
    cost_estimate REAL,
    validation_result TEXT,  -- JSON object
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id) REFERENCES stac_templates(id)
);
```

## CLI Commands

### Template Management

#### Create New Template
```bash
# Create a new template for a dataset
copper stac template new <dataset_id> <template_name>

# Create with initial variables
copper stac template new <dataset_id> <template_name> --variables "temp,humidity" --year "2023"

# Create with full template data
copper stac template new <dataset_id> <template_name> --template-file request.json
```

#### List Templates
```bash
# List all templates
copper stac template list

# Filter by dataset
copper stac template list --dataset <dataset_id>

# Filter by variable
copper stac template list --variable "temperature"

# Filter by validation status
copper stac template list --valid-only

# Filter by budget status
copper stac template list --within-budget
```

#### Template Operations
```bash
# Add variables to template
copper stac template add <template_name> --variables "pressure,wind"

# Remove variables from template
copper stac template remove <template_name> --variables "pressure"

# Update template parameters
copper stac template update <template_name> --year "2024" --month "01"

# Validate template
copper stac template validate <template_name>

# Estimate cost for template
copper stac template estimate <template_name> --budget 100.0

# Optimize template
copper stac template optimize <template_name> --budget 50.0 --strategy constraint-based

# Show template details
copper stac template show <template_name>

# Delete template
copper stac template delete <template_name>
```

### Variable Discovery

#### List Variables
```bash
# List all variables for a dataset
copper stac variables <dataset_id>

# Search variables by name or description
copper stac variables <dataset_id> --search "temperature"

# Show detailed variable information
copper stac variables <dataset_id> --detailed

# Show constraint sets
copper stac variables <dataset_id> --constraints

# Export variables to file
copper stac variables <dataset_id> --output variables.json
```

### Cost Estimation

#### Estimate Costs
```bash
# Estimate cost for a template
copper stac estimate <template_name>

# Estimate cost for a file
copper stac estimate <dataset_id> --template request.json

# Check against budget
copper stac estimate <template_name> --budget 100.0

# Get detailed breakdown
copper stac estimate <template_name> --detailed

# Test variations
copper stac estimate <template_name> --test-variations
```

### Request Validation

#### Validate Requests
```bash
# Validate a template
copper stac validate <template_name>

# Validate a file
copper stac validate <dataset_id> --template request.json

# Show constraint sets
copper stac validate <template_name> --show-constraints

# Export validation results
copper stac validate <template_name> --output validation.json
```

### Request Optimization

#### Optimize Requests
```bash
# Optimize a template
copper stac optimize <template_name> --budget 50.0

# Optimize with specific strategy
copper stac optimize <template_name> --budget 50.0 --strategy time-based

# Show optimization analysis
copper stac optimize <template_name> --budget 50.0 --analyze

# Export optimized requests
copper stac optimize <template_name> --budget 50.0 --output optimized.json
```

## Data Models

### Template Model
```python
class Template(BaseModel):
    id: Optional[int] = None
    name: str
    collection_id: str
    template_data: Dict[str, Any]
    variables: List[str]
    estimated_cost: Optional[float] = None
    budget_limit: float = 400.0
    is_within_budget: Optional[bool] = None
    is_valid: Optional[bool] = None
    validation_errors: List[str] = []
    constraint_set_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
```

### Template History Model
```python
class TemplateHistory(BaseModel):
    id: Optional[int] = None
    template_id: int
    action: str  # 'create', 'update', 'validate', 'estimate'
    old_data: Optional[Dict[str, Any]] = None
    new_data: Optional[Dict[str, Any]] = None
    cost_estimate: Optional[float] = None
    validation_result: Optional[Dict[str, Any]] = None
    performed_at: Optional[datetime] = None
```

### Variable Model (Enhanced)
```python
class Variable(BaseModel):
    id: Optional[int] = None
    collection_id: str
    name: str
    description: Optional[str] = None
    units: Optional[str] = None
    available_statistics: List[str] = []
    time_resolution: Optional[str] = None
    compatible_variables: List[str] = []
    temporal_constraints: Dict[str, Any] = {}
    discovered_at: Optional[datetime] = None
```

### Constraint Set Model (Enhanced)
```python
class ConstraintSet(BaseModel):
    id: Optional[int] = None
    collection_id: str
    constraint_set_id: str
    variables: List[str]
    daily_statistics: List[str]
    frequencies: List[str]
    time_zones: List[str]
    years: List[str]
    months: List[str]
    days: List[str]
    product_types: List[str]
    discovered_at: Optional[datetime] = None
```

## Database Operations

### Template Operations
- `create_template(template: Template) -> int`
- `get_template(template_id: int) -> Template`
- `get_template_by_name(name: str) -> Template`
- `list_templates(filters: Dict[str, Any]) -> List[Template]`
- `update_template(template_id: int, updates: Dict[str, Any]) -> Template`
- `delete_template(template_id: int) -> bool`
- `add_template_history(history: TemplateHistory) -> int`

### Variable Operations
- `store_variables(collection_id: str, variables: List[Variable]) -> None`
- `get_variables(collection_id: str, search: Optional[str] = None) -> List[Variable]`
- `get_variable_by_name(collection_id: str, name: str) -> Optional[Variable]`

### Constraint Operations
- `store_constraints(collection_id: str, constraints: List[ConstraintSet]) -> None`
- `get_constraints(collection_id: str) -> List[ConstraintSet]`
- `get_constraint_set(collection_id: str, constraint_set_id: str) -> Optional[ConstraintSet]`

## Implementation Plan

### Phase 1: Database Schema and Models
1. Create new database tables for variables, constraints, templates, and history
2. Implement Pydantic models for all data structures
3. Create database operations module
4. Add database migration utilities

### Phase 2: Template Management
1. Implement template CRUD operations
2. Add template validation and cost estimation
3. Create template history tracking
4. Implement template listing and filtering

### Phase 3: Variable Discovery
1. Integrate variable discovery with database storage
2. Add variable search and filtering
3. Implement constraint set storage and retrieval
4. Add variable compatibility checking

### Phase 4: Cost Estimation and Optimization
1. Integrate cost estimation with template management
2. Add request optimization with database storage
3. Implement budget tracking and alerts
4. Add cost history and trends

### Phase 5: CLI Integration
1. Update existing STAC commands to use new database
2. Add new template management commands
3. Integrate with existing STAC commands
4. Maintain consistent command structure

### Phase 6: Testing and Documentation
1. Add comprehensive unit tests
2. Add integration tests for all commands
3. Add performance tests for database operations
4. Update documentation and examples

## Migration Strategy

### Existing STAC Module
- Keep existing STAC functionality intact
- Add new costings functionality as additional commands
- Use existing database connection and utilities
- Maintain backward compatibility

### Database Migration
- Add new tables to existing schema
- Migrate any existing data if needed
- Add indexes for performance
- Add foreign key constraints

### Command Structure
- Use `copper stac` as the base command
- Add subcommands for template management
- Integrate with existing STAC commands
- Maintain consistent command structure

## Future Enhancements

### Advanced Features
- Template versioning and branching
- Template sharing and collaboration
- Cost prediction and trends
- Automated optimization suggestions

### Performance Improvements
- Database query optimization
- Caching for frequently accessed data
- Background processing for large operations
- Parallel processing for multiple requests

### User Experience
- Interactive template builder
- Template templates and presets
- Cost visualization and reporting
- Integration with external tools 