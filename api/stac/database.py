
from typing import List
from contextlib import contextmanager
import logging
import duckdb

from storage.datasets import connect_to_database
from .models import SingleArrayVariable, SingleEnumVariable
from .exceptions import STACDatabaseError

logger = logging.getLogger(__name__)


def _ensure_tables_exist():
    """Ensure costings tables exist, create them if they don't."""
    try:
        con = connect_to_database()
        try:
            # Check if stac_input_parameters table exists using DuckDB syntax
            result = con.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name = 'stac_input_parameters'
            """).fetchone()
            
            if not result:
                logger.info("Costings tables not found, creating them...")
                con.close()  # Close before calling initialize
                initialize_costings_tables()
                return
                
            # If input parameters table exists, assume all costings tables exist
            logger.debug("Costings tables already exist")
        finally:
            con.close()
            
    except Exception as e:
        logger.warning(f"Could not check table existence, attempting to create: {e}")
        try:
            initialize_costings_tables()
        except Exception as init_error:
            logger.error(f"Failed to initialize costings tables: {init_error}")
            raise STACDatabaseError(f"Cannot initialize required tables: {init_error}") from init_error


@contextmanager
def get_database_connection():
    """Context manager for database connections with proper error handling."""
    con = None
    try:
        con = connect_to_database()
        yield con
        con.commit()
    except Exception as e:
        if con:
            try:
                con.rollback()
            except Exception as rollback_error:
                logger.debug(f"Rollback failed (may be normal): {rollback_error}")
        logger.error(f"Database operation failed: {e}")
        raise STACDatabaseError(f"Database operation failed: {e}") from e
    finally:
        if con:
            con.close()

def drop_table(table_name: str, con: duckdb.DuckDBPyConnection):
    """Drop a table and its associated sequences."""
    con.execute(f"DROP TABLE IF EXISTS {table_name}")
    con.execute(f"DROP SEQUENCE IF EXISTS seq_{table_name}_id")
    
def create_sequence(table_name: str, con: duckdb.DuckDBPyConnection):
    """Create a sequence for a table."""
    con.execute(f"CREATE SEQUENCE seq_{table_name}_id START 1")


def initialize_costings_tables(drop_existing: bool = False):
    """Initialize the costings-related tables in the database."""
    try:
        con = connect_to_database()
        try:
            if drop_existing:
                drop_table("stac_template_history", con)
                drop_table("stac_templates", con)
                drop_table("stac_constraints", con)
                drop_table("stac_input_parameters", con)
                drop_table("stac_input_values", con)
            
            # Create sequences for auto-incrementing IDs
            create_sequence("stac_input_parameters", con)
            create_sequence("stac_input_values", con)
            create_sequence("stac_constraints", con)
            create_sequence("stac_templates", con)
            create_sequence("stac_template_history", con)
            
            # Create input parameters table with indexes
            con.execute("""
                CREATE TABLE stac_input_parameters (
                    id INTEGER PRIMARY KEY DEFAULT nextval('seq_stac_input_parameters_id'),
                    collection_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(collection_id, title)
                )
            """)

            con.execute("""
                CREATE TABLE stac_input_values (
                    id INTEGER PRIMARY KEY DEFAULT nextval('seq_stac_input_values_id'),
                    input_parameter_id INTEGER NOT NULL,
                    value VARCHAR NOT NULL,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(input_parameter_id, value)
                )
            """)
            
            # Create constraints table with indexes
            con.execute("""
                CREATE TABLE stac_constraints (
                    id INTEGER PRIMARY KEY DEFAULT nextval('seq_stac_constraints_id'),
                    collection_id TEXT NOT NULL,
                    constraint_set_id TEXT NOT NULL,
                    variables TEXT,
                    daily_statistics TEXT,
                    frequencies TEXT,
                    time_zones TEXT,
                    years TEXT,
                    months TEXT,
                    days TEXT,
                    product_types TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(collection_id, constraint_set_id)
                )
            """)
            
            # Create input schemas table for storing dataset input specifications
            con.execute("""
                CREATE TABLE stac_input_schemas (
                    id INTEGER PRIMARY KEY DEFAULT nextval('seq_stac_input_schemas_id'),
                    collection_id TEXT NOT NULL UNIQUE,
                    schema_data TEXT NOT NULL,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create input parameters table for individual parameter details
            con.execute("""
                CREATE TABLE stac_input_parameters (
                    id INTEGER PRIMARY KEY DEFAULT nextval('seq_stac_input_parameters_id'),
                    collection_id TEXT NOT NULL,
                    parameter_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    schema_type TEXT NOT NULL,
                    items_type TEXT,
                    enum_values TEXT,
                    required BOOLEAN DEFAULT FALSE,
                    description TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(collection_id, parameter_name)
                )
            """)
            
            # Create templates table with constraints
            con.execute("""
                CREATE TABLE stac_templates (
                    id INTEGER PRIMARY KEY DEFAULT nextval('seq_stac_templates_id'),
                    template_name TEXT UNIQUE NOT NULL,
                    collection_id TEXT NOT NULL,
                    template_data TEXT NOT NULL,
                    variables TEXT,
                    estimated_cost REAL CHECK (estimated_cost >= 0),
                    budget_limit REAL DEFAULT 400.0 CHECK (budget_limit > 0),
                    is_within_budget BOOLEAN,
                    is_valid BOOLEAN,
                    validation_errors TEXT,
                    constraint_set_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create template history table
            con.execute("""
                CREATE TABLE stac_template_history (
                    id INTEGER PRIMARY KEY DEFAULT nextval('seq_stac_template_history_id'),
                    template_id INTEGER NOT NULL,
                    action TEXT NOT NULL CHECK (action IN ('create', 'update', 'validate', 'estimate', 'optimize')),
                    old_data TEXT,
                    new_data TEXT,
                    cost_estimate REAL CHECK (cost_estimate >= 0),
                    validation_result TEXT,
                    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_input_parameters_collection ON stac_input_parameters(collection_id)",
                "CREATE INDEX IF NOT EXISTS idx_input_parameters_title ON stac_input_parameters(title)",
                "CREATE INDEX IF NOT EXISTS idx_input_values_input_parameter ON stac_input_values(input_parameter_id)",
                "CREATE INDEX IF NOT EXISTS idx_input_values_value ON stac_input_values(value)",
                "CREATE INDEX IF NOT EXISTS idx_constraints_collection ON stac_constraints(collection_id)",
                "CREATE INDEX IF NOT EXISTS idx_templates_collection ON stac_templates(collection_id)",
                "CREATE INDEX IF NOT EXISTS idx_templates_valid ON stac_templates(is_valid)",
                "CREATE INDEX IF NOT EXISTS idx_templates_budget ON stac_templates(is_within_budget)",
                "CREATE INDEX IF NOT EXISTS idx_history_template ON stac_template_history(template_id)",
            ]
            
            for index_sql in indexes:
                con.execute(index_sql)
            
            con.commit()
            logger.info("Costings tables initialized successfully")
        finally:
            con.close()
            
    except Exception as e:
        logger.error(f"Failed to initialize costings tables: {e}")
        raise STACDatabaseError(f"Failed to initialize costings tables: {e}") from e

def store_input_parameters(collection_id: str, input_parameters: List[SingleArrayVariable | SingleEnumVariable]) -> None:
    """Store input parameters for a collection."""
    con = connect_to_database()
    for input_parameter in input_parameters:
        con.execute("""
            INSERT INTO stac_input_parameters (collection_id, title, schema_type, items_type, enum_values, required, description) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (collection_id, input_parameter.title, input_parameter.schema_type, input_parameter.items_type, input_parameter.enum_values, input_parameter.required, input_parameter.description))
    con.commit()
    con.close()

# # Template Operations
# def create_template(template: Template) -> int:
#     """Create a new template and return its ID."""
#     try:
#         # Validate template data
#         if not template.name or not template.collection_id:
#             raise STACValidationError("Template name and collection_id are required")
        
#         with get_database_connection() as con:
#             result = con.execute("""
#                 INSERT INTO stac_templates (
#                     template_name, collection_id, template_data, variables,
#                     estimated_cost, budget_limit, is_within_budget, is_valid,
#                     validation_errors, constraint_set_id
#                 ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#                 RETURNING id
#             """, (
#                 template.name, template.collection_id, json.dumps(template.template_data),
#                 json.dumps(template.variables), template.estimated_cost, template.budget_limit,
#                 template.is_within_budget, template.is_valid, json.dumps(template.validation_errors),
#                 template.constraint_set_id
#             ))
            
#             template_id = result.fetchone()[0]
#             logger.info(f"Created template '{template.name}' with ID {template_id}")
#             return template_id
            
#     except json.JSONEncodeError as e:
#         raise STACValidationError(f"Invalid JSON in template data: {e}") from e
#     except Exception as e:
#         logger.error(f"Failed to create template '{template.name}': {e}")
#         raise STACDatabaseError(f"Failed to create template: {e}") from e


# def get_template(template_id: int) -> Optional[Template]:
#     """Get a template by ID."""
#     try:
#         if not isinstance(template_id, int) or template_id <= 0:
#             raise STACValidationError("Invalid template_id")
            
#         with get_database_connection() as con:
#             result = con.execute("""
#                 SELECT id, template_name, collection_id, template_data, variables,
#                        estimated_cost, budget_limit, is_within_budget, is_valid,
#                        validation_errors, constraint_set_id, created_at, updated_at
#                 FROM stac_templates WHERE id = ?
#             """, (template_id,))
            
#             row = result.fetchone()
            
#             if not row:
#                 return None
            
#             return Template(
#                 id=row[0], name=row[1], collection_id=row[2],
#                 template_data=json.loads(row[3]), variables=json.loads(row[4]),
#                 estimated_cost=row[5], budget_limit=row[6], is_within_budget=row[7],
#                 is_valid=row[8], validation_errors=json.loads(row[9]),
#                 constraint_set_id=row[10], created_at=row[11], updated_at=row[12]
#             )
#     except ValueError as e:  # JSONDecodeError is a subclass of ValueError
#         logger.error(f"Invalid JSON in template {template_id}: {e}")
#         raise STACDatabaseError(f"Template data corruption: {e}") from e
#     except Exception as e:
#         logger.error(f"Failed to get template {template_id}: {e}")
#         raise STACDatabaseError(f"Failed to get template: {e}") from e


# def get_template_by_name(name: str) -> Optional[Template]:
#     """Get a template by name."""
#     try:
#         if not isinstance(name, str) or not name.strip():
#             raise STACValidationError("Template name must be a non-empty string")
        
#         # Ensure tables exist before querying
#         _ensure_tables_exist()
        
#         with get_database_connection() as con:
#             result = con.execute("""
#                 SELECT id, template_name, collection_id, template_data, variables,
#                        estimated_cost, budget_limit, is_within_budget, is_valid,
#                        validation_errors, constraint_set_id, created_at, updated_at
#                 FROM stac_templates WHERE template_name = ?
#             """, (name,))
            
#             row = result.fetchone()
            
#             if not row:
#                 return None
            
#             return Template(
#                 id=row[0], name=row[1], collection_id=row[2],
#                 template_data=json.loads(row[3]), variables=json.loads(row[4]),
#                 estimated_cost=row[5], budget_limit=row[6], is_within_budget=row[7],
#                 is_valid=row[8], validation_errors=json.loads(row[9] or '[]'),
#                 constraint_set_id=row[10], created_at=row[11], updated_at=row[12]
#             )
#     except ValueError as e:  # JSONDecodeError is a subclass of ValueError
#         logger.error(f"Invalid JSON in template '{name}': {e}")
#         raise STACDatabaseError(f"Template data corruption: {e}") from e
#     except Exception as e:
#         logger.error(f"Failed to get template '{name}': {e}")
#         raise STACDatabaseError(f"Failed to get template: {e}") from e


# def list_templates(filters: Optional[Dict[str, Any]] = None) -> List[Template]:
#     """List templates with optional filtering."""
#     try:
#         # Ensure tables exist before querying
#         _ensure_tables_exist()
        
#         with get_database_connection() as con:
#             query = """
#                 SELECT id, template_name, collection_id, template_data, variables,
#                        estimated_cost, budget_limit, is_within_budget, is_valid,
#                        validation_errors, constraint_set_id, created_at, updated_at
#                 FROM stac_templates
#             """
#             params = []
            
#             if filters:
#                 conditions = []
#                 if "collection_id" in filters:
#                     conditions.append("collection_id = ?")
#                     params.append(filters["collection_id"])
#                 if "variable" in filters:
#                     conditions.append("variables LIKE ?")
#                     params.append(f"%{filters['variable']}%")
#                 if filters.get("valid_only"):
#                     conditions.append("is_valid = TRUE")
#                 if filters.get("within_budget"):
#                     conditions.append("is_within_budget = TRUE")
                
#                 if conditions:
#                     query += " WHERE " + " AND ".join(conditions)
            
#             query += " ORDER BY created_at DESC"
            
#             result = con.execute(query, params)
#             rows = result.fetchall()
            
#             templates = []
#             for row in rows:
#                 try:
#                     templates.append(Template(
#                         id=row[0], name=row[1], collection_id=row[2],
#                         template_data=json.loads(row[3]), variables=json.loads(row[4]),
#                         estimated_cost=row[5], budget_limit=row[6], is_within_budget=row[7],
#                         is_valid=row[8], validation_errors=json.loads(row[9] or '[]'),
#                         constraint_set_id=row[10], created_at=row[11], updated_at=row[12]
#                     ))
#                 except (ValueError, TypeError) as e:  # JSONDecodeError is a subclass of ValueError
#                     logger.warning(f"Failed to parse template data for row {row[0]}: {e}")
#                     continue
            
#             logger.info(f"Retrieved {len(templates)} templates")
#             return templates
            
#     except Exception as e:
#         logger.error(f"Failed to list templates: {e}")
#         raise STACDatabaseError(f"Failed to list templates: {e}") from e


# def update_template(template_id: int, updates: Dict[str, Any]) -> Optional[Template]:
#     """Update a template and return the updated template."""
#     # Define allowed columns to prevent SQL injection
#     ALLOWED_COLUMNS = {
#         'template_name', 'collection_id', 'template_data', 'variables',
#         'estimated_cost', 'budget_limit', 'is_within_budget', 'is_valid',
#         'validation_errors', 'constraint_set_id', 'input_schemas', 'input_parameters'
#     }
    
#     try:
#         if not updates:
#             raise STACValidationError("No updates provided")
        
#         # Validate template_id
#         if not isinstance(template_id, int) or template_id <= 0:
#             raise STACValidationError("Invalid template_id")
        
#         # Validate column names
#         invalid_columns = set(updates.keys()) - ALLOWED_COLUMNS
#         if invalid_columns:
#             raise STACValidationError(f"Invalid columns: {invalid_columns}")
        
#         with get_database_connection() as con:
#             # Build secure parameterized query
#             set_clauses = []
#             params = []
            
#             for key, value in updates.items():
#                 if key in ["template_data", "variables", "validation_errors"]:
#                     set_clauses.append(f"{key} = ?")
#                     try:
#                         params.append(json.dumps(value))
#                     except (TypeError, ValueError) as e:
#                         raise STACValidationError(f"Invalid JSON for {key}: {e}") from e
#                 else:
#                     set_clauses.append(f"{key} = ?")
#                     params.append(value)
            
#             set_clauses.append("updated_at = CURRENT_TIMESTAMP")
#             params.append(template_id)
            
#             query = f"UPDATE stac_templates SET {', '.join(set_clauses)} WHERE id = ?"
#             result = con.execute(query, params)
            
#             if result.rowcount == 0:
#                 logger.warning(f"No template found with ID {template_id}")
#                 return None
            
#             logger.info(f"Updated template {template_id}")
#             return get_template(template_id)
            
#     except Exception as e:
#         logger.error(f"Failed to update template {template_id}: {e}")
#         raise STACDatabaseError(f"Failed to update template: {e}") from e


# def delete_template(template_id: int) -> bool:
#     """Delete a template and return success status."""
#     try:
#         if not isinstance(template_id, int) or template_id <= 0:
#             raise STACValidationError("Invalid template_id")
            
#         with get_database_connection() as con:
#             result = con.execute("DELETE FROM stac_templates WHERE id = ?", (template_id,))
#             deleted = result.rowcount > 0
            
#             if deleted:
#                 logger.info(f"Deleted template {template_id}")
#             else:
#                 logger.warning(f"No template found with ID {template_id}")
                
#             return deleted
            
#     except Exception as e:
#         logger.error(f"Failed to delete template {template_id}: {e}")
#         raise STACDatabaseError(f"Failed to delete template: {e}") from e


# def add_template_history(history: TemplateHistory) -> int:
#     """Add a template history entry and return its ID."""
#     con = connect_to_database()
    
#     result = con.execute("""
#         INSERT INTO stac_template_history (
#             template_id, action, old_data, new_data, cost_estimate, validation_result
#         ) VALUES (?, ?, ?, ?, ?, ?)
#         RETURNING id
#     """, (
#         history.template_id, history.action,
#         json.dumps(history.old_data) if history.old_data else None,
#         json.dumps(history.new_data) if history.new_data else None,
#         history.cost_estimate,
#         json.dumps(history.validation_result) if history.validation_result else None
#     ))
    
#     history_id = result.fetchone()[0]
#     con.commit()
#     con.close()
    
#     return history_id

# def get_variables(collection_id: str, search: Optional[str] = None) -> List[Variable]:
#     """Get variables for a collection with optional search."""
#     try:
#         if not isinstance(collection_id, str) or not collection_id.strip():
#             raise STACValidationError("collection_id must be a non-empty string")
        
#         # Ensure tables exist before querying
#         _ensure_tables_exist()
        
#         with get_database_connection() as con:
#             query = """
#                 SELECT id, collection_id, variable_name, description, units,
#                        available_statistics, time_resolution, compatible_variables,
#                        temporal_constraints, discovered_at
#                 FROM stac_variables WHERE collection_id = ?
#             """
#             params = [collection_id]
            
#             if search:
#                 query += " AND (variable_name LIKE ? OR description LIKE ?)"
#                 params.extend([f"%{search}%", f"%{search}%"])
            
#             result = con.execute(query, params)
#             rows = result.fetchall()
            
#             variables = []
#             for row in rows:
#                 try:
#                     variables.append(Variable(
#                         id=row[0], collection_id=row[1], name=row[2], description=row[3],
#                         units=row[4], available_statistics=json.loads(row[5] or '[]'),
#                         time_resolution=row[6], compatible_variables=json.loads(row[7] or '[]'),
#                         temporal_constraints=json.loads(row[8] or '{}'), discovered_at=row[9]
#                     ))
#                 except (ValueError, TypeError) as e:  # JSONDecodeError is a subclass of ValueError
#                     logger.warning(f"Failed to parse variable data for row {row[0]}: {e}")
#                     continue
            
#             logger.info(f"Retrieved {len(variables)} variables for collection '{collection_id}'")
#             return variables
            
#     except Exception as e:
#         logger.error(f"Failed to get variables for collection '{collection_id}': {e}")
#         raise STACDatabaseError(f"Failed to get variables: {e}") from e


# def get_variable_by_name(collection_id: str, name: str) -> Optional[Variable]:
#     """Get a specific variable by name for a collection."""
#     variables = get_variables(collection_id)
#     for variable in variables:
#         if variable.name == name:
#             return variable
#     return None


# # Constraint Operations
# def store_constraints(collection_id: str, constraints: List[ConstraintSet]) -> None:
#     """Store constraint sets for a collection."""
#     con = connect_to_database()
    
#     for constraint in constraints:
#         con.execute("""
#             INSERT OR REPLACE INTO stac_constraints (
#                 collection_id, constraint_set_id, variables, daily_statistics,
#                 frequencies, time_zones, years, months, days, product_types
#             ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
#         """, (
#             collection_id, constraint.constraint_set_id, json.dumps(constraint.variables),
#             json.dumps(constraint.daily_statistics), json.dumps(constraint.frequencies),
#             json.dumps(constraint.time_zones), json.dumps(constraint.years),
#             json.dumps(constraint.months), json.dumps(constraint.days),
#             json.dumps(constraint.product_types)
#         ))
    
#     con.commit()
#     con.close()


# def get_constraints(collection_id: str) -> List[ConstraintSet]:
#     """Get all constraint sets for a collection."""
#     try:
#         if not isinstance(collection_id, str) or not collection_id.strip():
#             raise STACValidationError("collection_id must be a non-empty string")
        
#         # Ensure tables exist before querying
#         _ensure_tables_exist()
        
#         with get_database_connection() as con:
#             result = con.execute("""
#                 SELECT id, collection_id, constraint_set_id, variables, daily_statistics,
#                        frequencies, time_zones, years, months, days, product_types, discovered_at
#                 FROM stac_constraints WHERE collection_id = ?
#             """, (collection_id,))
            
#             rows = result.fetchall()
            
#             constraints = []
#             for row in rows:
#                 try:
#                     constraints.append(ConstraintSet(
#                         id=row[0], collection_id=row[1], constraint_set_id=row[2],
#                         variables=json.loads(row[3] or '[]'), daily_statistics=json.loads(row[4] or '[]'),
#                         frequencies=json.loads(row[5] or '[]'), time_zones=json.loads(row[6] or '[]'),
#                         years=json.loads(row[7] or '[]'), months=json.loads(row[8] or '[]'),
#                         days=json.loads(row[9] or '[]'), product_types=json.loads(row[10] or '[]'),
#                         discovered_at=row[11]
#                     ))
#                 except (ValueError, TypeError) as e:  # JSONDecodeError is a subclass of ValueError
#                     logger.warning(f"Failed to parse constraint data for row {row[0]}: {e}")
#                     continue
            
#             logger.info(f"Retrieved {len(constraints)} constraints for collection '{collection_id}'")
#             return constraints
            
#     except Exception as e:
#         logger.error(f"Failed to get constraints for collection '{collection_id}': {e}")
#         raise STACDatabaseError(f"Failed to get constraints: {e}") from e


# # def get_constraint_set(collection_id: str, constraint_set_id: str) -> Optional[ConstraintSet]:
# #     """Get a specific constraint set."""
# #     constraints = get_constraints(collection_id)
# #     for constraint in constraints:
# #         if constraint.constraint_set_id == constraint_set_id:
# #             return constraint
# #     return None 