# Contributing to SimLeagues

First off, thank you for considering contributing to SimLeagues! It's people like you that make SimLeagues such a great tool for the sim racing community.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Process](#development-process)
- [Coding Standards](#coding-standards)
- [Commit Guidelines](#commit-guidelines)
- [Pull Request Process](#pull-request-process)
- [Bug Reports](#bug-reports)
- [Feature Requests](#feature-requests)

## Code of Conduct

This project and everyone participating in it is governed by our commitment to providing a welcoming and inspiring community for all. Please be respectful and constructive in your interactions.

### Our Standards

- Using welcoming and inclusive language
- Being respectful of differing viewpoints and experiences
- Gracefully accepting constructive criticism
- Focusing on what is best for the community
- Showing empathy towards other community members

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally
```bash
   git clone https://github.com/YOUR-USERNAME/simleagues-backend.git
   cd simleagues-backend
```
3. **Set up your development environment**
```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements/development.txt
```
4. **Create a branch** for your changes
```bash
   git checkout -b feature/your-feature-name
```

## Development Process

### Setting Up Pre-commit Hooks

We use pre-commit hooks to ensure code quality:
```bash
pip install pre-commit
pre-commit install
```

### Running Tests

Always run tests before submitting a PR:
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=apps --cov-report=html

# Run specific test file
pytest apps/leagues/tests/test_models.py
```

### Running the Development Server
```bash
python manage.py runserver
```

## Coding Standards

### Python Style Guide

We follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) with some modifications:

- **Line length**: 88 characters (Black default)
- **Imports**: Organized using `isort`
- **Formatting**: Automated with `black`
- **Linting**: Checked with `flake8`

### Code Quality Tools

Run these before committing:
```bash
# Format code
black .

# Sort imports
isort .

# Lint code
flake8 .

# Type checking (if using type hints)
mypy apps/
```

### Django Best Practices

- Use Django's built-in features when possible
- Follow Django's model, view, serializer naming conventions
- Keep views thin, move logic to models or services
- Write docstrings for all public functions and classes
- Use `select_related()` and `prefetch_related()` to avoid N+1 queries

### Example Code Structure
```python
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class League(models.Model):
    """
    Represents a racing league organization.
    
    A league can have multiple championships and manages
    its own members with different permission levels.
    """
    name = models.CharField(max_length=200)
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'League'
        verbose_name_plural = 'Leagues'
    
    def __str__(self):
        return self.name
    
    def get_active_championships(self):
        """Return all active championships for this league."""
        return self.championships.filter(status='ACTIVE')
```

## Commit Guidelines

We follow [Conventional Commits](https://www.conventionalcommits.org/) specification:

### Commit Message Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation only changes
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code change that neither fixes a bug nor adds a feature
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **chore**: Changes to build process or auxiliary tools

### Examples
```bash
feat(leagues): add league creation endpoint

Implement POST /api/leagues/ endpoint with proper validation
and permission checks. Only authenticated users can create leagues.

Closes #123

---

fix(races): correct points calculation for DNF drivers

DNF drivers were incorrectly receiving points. Updated the
calculation logic to award 0 points for DNF status.

Fixes #456

---

docs(api): update championship endpoints documentation

Added examples and clarified query parameters for the
championships list endpoint.
```

## Pull Request Process

1. **Update documentation** if you're changing functionality
2. **Add tests** for new features
3. **Ensure all tests pass** and coverage doesn't decrease
4. **Update the CHANGELOG.md** with details of changes (if applicable)
5. **Request review** from maintainers

### PR Title Format

Use the same format as commit messages:
```
feat(leagues): add league invitation system
```

### PR Description Template
```markdown
## Description
Brief description of what this PR does.

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Related Issues
Closes #(issue number)

## How Has This Been Tested?
Describe the tests you ran to verify your changes.

## Checklist
- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published
```

## Bug Reports

### Before Submitting a Bug Report

- Check the [documentation](https://github.com/flodell/simleagues-backend/wiki)
- Search [existing issues](https://github.com/flodell/simleagues-backend/issues) to avoid duplicates
- Collect information about the bug:
  - Stack trace
  - OS, Platform and Version
  - Python and Django versions
  - Steps to reproduce

### Bug Report Template
```markdown
**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Environment:**
 - OS: [e.g. Ubuntu 22.04]
 - Python version: [e.g. 3.11.5]
 - Django version: [e.g. 5.0.1]
 - Browser (if applicable): [e.g. Chrome 120]

**Additional context**
Add any other context about the problem here.
```

## Feature Requests

We welcome feature requests! Please provide:

1. **Clear description** of the feature
2. **Use case**: Why is this feature needed?
3. **Proposed solution**: How would you implement it?
4. **Alternatives**: What alternatives have you considered?
5. **Additional context**: Screenshots, mockups, etc.

### Feature Request Template
```markdown
**Is your feature request related to a problem?**
A clear description of what the problem is. Ex. I'm always frustrated when [...]

**Describe the solution you'd like**
A clear and concise description of what you want to happen.

**Describe alternatives you've considered**
A clear and concise description of any alternative solutions or features you've considered.

**Additional context**
Add any other context, screenshots, or mockups about the feature request here.
```

## Development Setup Details

### Database Migrations
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Check for migration issues
python manage.py makemigrations --check
```

### Creating Test Data
```bash
# Load fixtures
python manage.py loaddata fixtures/test_data.json

# Or create custom management command
python manage.py create_test_data
```

### Working with Branches

- `main`: Production-ready code
- `develop`: Integration branch for features
- `feature/*`: New features
- `bugfix/*`: Bug fixes
- `hotfix/*`: Urgent production fixes

## Questions?

Feel free to open an issue with the `question` label or reach out to the maintainers on [GitHub Discussions](https://github.com/flodell/simleagues-backend/discussions).

## License

By contributing, you agree that your contributions will be licensed under the MIT License. See the [LICENSE](https://github.com/flodell/simleagues-backend/LICENSE) file for details.

---

Thank you for contributing to SimLeagues! 🏁
```