# Testing Workflow

This document describes the testing setup and workflow for the Copper project.

## Overview

The project uses a comprehensive testing approach with:
- **pytest** for running tests
- **pytest-cov** for code coverage reporting
- **pre-commit hooks** for automated quality checks
- **GitHub Actions** for continuous integration

## Test Structure

Tests are located in the `tests/` directory and follow pytest conventions:
- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`

## Running Tests Locally

### Basic Test Execution
```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=api --cov-report=html

# Run specific test file
uv run pytest tests/test_template.py

# Run specific test function
uv run pytest tests/test_template.py::test_load_json_template
```

### Coverage Reports
```bash
# Generate coverage report
uv run coverage run -m pytest

# View coverage report
uv run coverage report

# Generate HTML coverage report
uv run coverage html

# Open HTML report in browser
open htmlcov/index.html
```

## Pre-commit Hooks

Pre-commit hooks automatically run quality checks before each commit, including:
- Code formatting (black, isort)
- Linting (flake8)
- Running tests
- Checking coverage threshold (50% minimum)

### Setup
```bash
# Install pre-commit hooks
./scripts/setup-pre-commit.sh

# Or manually:
uv add --group dev pre-commit
pre-commit install
```

### Usage
```bash
# Run hooks on staged files
pre-commit run

# Run hooks on all files
pre-commit run --all-files

# Skip hooks for a commit (use with caution)
git commit --no-verify
```

## GitHub Actions

The CI/CD pipeline automatically runs on:
- Every push to `main` and `develop` branches
- Every pull request

### What Gets Tested
- Tests run on Python 3.10, 3.11, and 3.12
- Code coverage is measured and reported
- Coverage reports are uploaded as artifacts
- Coverage summaries are posted on pull requests

### Coverage Threshold
- **Minimum coverage**: 50%
- **Coverage reports**: HTML, XML, and terminal output
- **Coverage upload**: Automatically uploaded to Codecov

## Adding New Tests

### Test File Structure
```python
import pytest
from your_module import YourClass

def test_something():
    """Test description."""
    # Arrange
    obj = YourClass()

    # Act
    result = obj.method()

    # Assert
    assert result == expected_value
```

### Test Categories
Use pytest markers to categorize tests:
```python
@pytest.mark.unit
def test_unit_function():
    pass

@pytest.mark.integration
def test_integration_function():
    pass

@pytest.mark.slow
def test_slow_function():
    pass
```

### Running Specific Test Categories
```bash
# Run only unit tests
uv run pytest -m unit

# Run integration tests
uv run pytest -m integration

# Skip slow tests
uv run pytest -m "not slow"
```

## Coverage Configuration

Coverage is configured in `pyproject.toml` and `pytest.ini`:

- **Source**: `api/` directory
- **Exclusions**: Test files, cache directories, migrations
- **Threshold**: 50% minimum coverage
- **Reports**: HTML, XML, and terminal output

## Troubleshooting

### Common Issues

1. **Pre-commit fails on coverage**
   - Ensure tests are passing
   - Check if new code is covered by tests
   - Verify coverage threshold is met

2. **GitHub Actions fail**
   - Check the Actions tab for detailed logs
   - Ensure all dependencies are properly specified
   - Verify Python version compatibility

3. **Coverage reports not generating**
   - Ensure `pytest-cov` is installed
   - Check coverage configuration in `pyproject.toml`
   - Verify source paths are correct

### Debugging Tests
```bash
# Run tests with verbose output
uv run pytest -v

# Run tests with print statements
uv run pytest -s

# Run tests with debugger
uv run pytest --pdb

# Run tests and stop on first failure
uv run pytest -x
```

## Best Practices

1. **Write tests first** (TDD approach)
2. **Keep tests simple and focused**
3. **Use descriptive test names**
4. **Test both success and failure cases**
5. **Maintain high test coverage**
6. **Run tests before committing**
7. **Use appropriate pytest markers**
8. **Keep tests fast and reliable**

## Continuous Improvement

- Monitor coverage trends over time
- Add tests for new features
- Refactor tests when code changes
- Use test results to identify code quality issues
- Regularly review and update testing strategy
