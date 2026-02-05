# Contributing to LUMO

First off, thank you for considering contributing to LUMO! 🎉

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues. When you create a bug report, include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples**
- **Describe the behavior you observed and what you expected**
- **Include screenshots if applicable**
- **Note your environment** (OS, Python version, browser)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear and descriptive title**
- **Provide a detailed description of the proposed enhancement**
- **Explain why this enhancement would be useful**
- **List any similar features in other applications**

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Follow the existing code style** (PEP 8 for Python)
3. **Write meaningful commit messages**
4. **Include tests** if adding new features
5. **Update documentation** as needed
6. **Ensure all tests pass** before submitting

#### Pull Request Process

1. Update the README.md with details of changes if needed
2. Update the requirements.txt if you add dependencies
3. Update version numbers following [SemVer](https://semver.org/)
4. The PR will be merged once reviewed and approved

## Development Setup

```bash
# Clone your fork
git clone https://github.com/your-username/lumo.git
cd lumo

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your keys
# Run development server
python app.py
```

## Coding Standards

### Python Style Guide

- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use 4 spaces for indentation
- Maximum line length: 100 characters
- Use meaningful variable and function names
- Add docstrings to all functions and classes

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**

```
feat(auth): add Google OAuth login
fix(movies): resolve search pagination bug
docs(readme): update installation instructions
```

## Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test
pytest tests/test_auth.py
```

## Security

If you discover a security vulnerability, please email security@lumo.example.com instead of using the issue tracker.

## Questions?

Feel free to open an issue with the `question` label or reach out to the maintainers.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to LUMO! 🎬
