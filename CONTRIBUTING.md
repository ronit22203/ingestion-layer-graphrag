# Contributing to MARA Medical Data Ingestion Pipeline

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

Please be respectful and professional in all interactions. We're committed to providing a welcoming environment for all contributors.

## Ways to Contribute

- **Report Bugs**: Found an issue? Open a GitHub issue with details
- **Suggest Enhancements**: Have ideas? Discuss them in Issues
- **Improve Documentation**: Help improve our docs and READMEs
- **Submit Code**: Fix bugs or add features with pull requests
- **Benchmarking**: Help optimize performance

## Getting Started

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR-USERNAME/prod_mara_ingestion.git
cd prod_mara_ingestion
```

### 2. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-description
```

### 3. Set Up Development Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Make Changes

- Write clean, well-documented code
- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation as needed

### 5. Run Tests

```bash
make test
make test-processors
make test-embedder
make test-qdrant
```

### 6. Commit and Push

```bash
git add .
git commit -m "feat: descriptive message" 
git push origin feature/your-feature-name
```

### 7. Submit Pull Request

- Provide clear description of changes
- Link related issues
- Ensure all tests pass

## Commit Message Format

Use conventional commits:
- `feat:` new feature
- `fix:` bug fix
- `docs:` documentation
- `refactor:` code refactoring
- `test:` tests
- `chore:` dependencies

## Code Style

- Follow PEP 8
- Use descriptive names
- Add meaningful comments
- Google-style docstrings

## Testing

- Write tests for new features
- Maintain test coverage
- Run tests before submitting PR

## Recognition

Contributors will be credited in releases. Thank you for improving MARA! 🎉
