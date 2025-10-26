# Poetry Development Setup

This project uses Poetry with dependency groups to manage dependencies for different components.

## Prerequisites

### Python Version Management with pyenv

This project requires Python 3.11+. We recommend using `pyenv` to manage Python versions:

1. **Install pyenv** (if not already installed):

   ```bash
   # macOS with Homebrew
   brew install pyenv

   # Or using the installer
   curl https://pyenv.run | bash
   ```

2. **Install and set Python version**:

   ```bash
   # Install Python 3.12 (or check .python-version file for required version)
   pyenv install 3.12

   # The project already has a .python-version file that specifies Python 3.12
   # pyenv will automatically use this version when you're in the project directory

   # Verify version
   python --version  # Should show Python 3.12.x
   ```

   The project includes a `.python-version` file that pyenv automatically reads to use the correct Python version.

3. **Add to your shell profile** (if not already done):

   ```bash
   # For zsh (macOS default)
   echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
   echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
   echo 'eval "$(pyenv init -)"' >> ~/.zshrc

   # Reload shell
   source ~/.zshrc
   ```

## Quick Start

1. **Install Poetry** (if not already installed):

   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

2. **Configure Poetry to use pyenv Python**:

   ```bash
   # Poetry will automatically detect the Python version from .python-version file
   poetry env use $(pyenv which python)
   ```

3. **Install all dependencies**:

   ```bash
   poetry install --with fastapi-app,batch-worker,batch-worker-lambda,dev
   ```

4. **Activate the virtual environment**:
   ```bash
   poetry shell
   ```

## Dependency Groups

Each dependency group maps directly to a project folder:

- **fastapi-app**: Dependencies for the FastAPI web application
- **batch-worker**: Dependencies for the batch processing worker
- **batch-worker-lambda**: Dependencies for the Lambda batch worker
- **dev**: Development tools (pytest, black, mypy, etc.)

## Installing Dependencies by Component

Install only what you need for specific development:

```bash
# For FastAPI app development
poetry install --with fastapi-app,dev

# For batch worker development
poetry install --with batch-worker,dev

# For Lambda worker development
poetry install --with batch-worker-lambda,dev

# For full development (everything)
poetry install --with fastapi-app,batch-worker,batch-worker-lambda,dev

# Production install for specific component
poetry install --only fastapi-app
poetry install --only batch-worker
poetry install --only batch-worker-lambda
```

## Adding New Dependencies

Add dependencies to the appropriate group that matches the folder:

```bash
# Add to fastapi-app group
poetry add --group fastapi-app requests

# Add to batch-worker group
poetry add --group batch-worker numpy

# Add to batch-worker-lambda group
poetry add --group batch-worker-lambda pillow

# Add dev dependency
poetry add --group dev pytest-cov
```

## Syncing requirements.txt Files

After adding dependencies, sync the requirements.txt files for Docker builds:

```bash
python sync_requirements.py
```

This will update:

- `fastapi-app/requirements.txt` (from fastapi-app group)
- `batch-worker/requirements.txt` (from batch-worker group)
- `batch-worker-lambda/requirements.txt` (from batch-worker-lambda group)

## Running Components

With Poetry virtual environment activated:

```bash
# Run FastAPI app
cd fastapi-app && python main.py

# Run batch worker
cd batch-worker && python worker.py

# Run tests
pytest

# Format code
black .
isort .

# Type checking
mypy .
```

## Docker Builds

The Docker builds will use the generated requirements.txt files, so make sure to run `python sync_requirements.py` after any dependency changes.

## Troubleshooting

### Python Version Issues

If Poetry can't find the right Python version:

```bash
# Check current Python version
python --version

# Check available pyenv versions
pyenv versions

# Set local Python version
pyenv local 3.12

# Tell Poetry to use the pyenv Python
poetry env use $(pyenv which python)

# Recreate virtual environment if needed
poetry env remove python
poetry install --with fastapi-app,batch-worker,batch-worker-lambda,dev
```

### Poetry Environment Issues

```bash
# Show current environment info
poetry env info

# List all Poetry environments
poetry env list

# Remove and recreate environment
poetry env remove python
poetry install --with fastapi-app,batch-worker,batch-worker-lambda,dev
```

### Dependency Conflicts

```bash
# Update lock file
poetry lock

# Update all dependencies
poetry update

# Check for dependency issues
poetry check
```
