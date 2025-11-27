# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ShutterScope is a camera shutter tester that uses an oscilloscope as the measurement device with a photodiode sensor. It supports Rigol DS1000Z oscilloscopes and connects via VISA to capture and analyze shutter speed data.

## Development Commands

```bash
# Use uv for package management
uv sync                      # Install dependencies
uv run python -m shutterscope  # Run the application
uv run pytest                # Run tests
uv run pytest tests/test_foo.py::test_name  # Run single test
uv run mypy src              # Type check
uv run ruff check src        # Lint
uv run ruff format src       # Format
```

## Architecture

- `src/shutterscope/` - Main package
  - `__main__.py` - CLI entry point
  - `shutterscope.py` - Core shutter testing logic

The application will:
1. Connect to oscilloscope via VISA
2. Configure trigger for photodiode sensor capture
3. Extract waveform data from oscilloscope
4. Analyze the waveform to calculate shutter speed

## Code Style Requirements

### Type Hints
- All functions must have complete type annotations (parameters and return types)
- Use modern syntax: `list[str]` not `List[str]`, `dict[str, int]` not `Dict[str, int]`
- Use `|` for unions: `str | None` not `Optional[str]`
- Complex types should use `TypedDict` or `dataclass`

### Dependency Injection Pattern
Use `Protocol` for interfaces to enable dependency injection and testability:

```python
from typing import Protocol

class OscilloscopeProtocol(Protocol):
    def connect(self, address: str) -> None: ...
    def capture_waveform(self) -> list[float]: ...

class ShutterAnalyzer:
    def __init__(self, oscilloscope: OscilloscopeProtocol) -> None:
        self._oscilloscope = oscilloscope
```

This allows injecting mock implementations in tests without modifying production code.

### Testing
- Use pytest with fixtures for dependency injection
- Test files mirror source structure: `src/shutterscope/foo.py` → `tests/test_foo.py`
- Use `unittest.mock.MagicMock` or concrete test doubles implementing Protocol interfaces
- Fixtures for common dependencies go in `conftest.py`

Example test pattern:
```python
class MockOscilloscope:
    def connect(self, address: str) -> None:
        pass
    def capture_waveform(self) -> list[float]:
        return [0.0, 1.0, 1.0, 0.0]

@pytest.fixture
def oscilloscope() -> OscilloscopeProtocol:
    return MockOscilloscope()

def test_analyzer(oscilloscope: OscilloscopeProtocol) -> None:
    analyzer = ShutterAnalyzer(oscilloscope)
    # ...
```

## Quality Gates

Before considering any task complete, all of the following must pass:

```bash
uv run ruff check src tests  # No lint errors
uv run ruff format --check src tests  # Code is formatted
uv run mypy src  # No type errors
uv run pytest  # All tests pass
```

## Tool Configuration

All configuration lives in `pyproject.toml`. Key settings:

- **mypy**: strict mode with `disallow_untyped_defs = true`
- **ruff**: handles both linting and formatting (replaces black, isort, flake8)
- **pytest**: with coverage reporting
