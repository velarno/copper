# Badges for README

Add these badges to your README.md to show the status of your testing workflow:

## Testing Status
```markdown
![Tests](https://github.com/{owner}/{repo}/workflows/Test%20and%20Coverage/badge.svg)
```

## Code Coverage
```markdown
![Codecov](https://codecov.io/gh/{owner}/{repo}/branch/main/graph/badge.svg)
```

## Python Version Support
```markdown
![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
```

## Example README Section
```markdown
## Testing

[![Tests](https://github.com/{owner}/{repo}/workflows/Test%20and%20Coverage/badge.svg)](https://github.com/{owner}/{repo}/actions)
[![Codecov](https://codecov.io/gh/{owner}/{repo}/branch/main/graph/badge.svg)](https://codecov.io/gh/{owner}/{repo})

This project maintains comprehensive test coverage with automated testing on every commit. See [TESTING.md](docs/TESTING.md) for details.
```

## Replace Placeholders
- `{owner}`: Your GitHub username or organization
- `{repo}`: Your repository name

## Badge URLs
- **Tests**: Links to GitHub Actions workflow
- **Codecov**: Links to detailed coverage reports
- **Python versions**: Informational badges
