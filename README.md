# ShutterScope

This is a camera shutter tester that uses an Oscilloscope as the measurement device with a photodiode as the sensor. It supports the Rigol ds1000z range of oscilloscopes and connects via VISA to set up a trigger to capture the sensor data, extract it from the oscilloscope and analyse the shutter speed on the computer.

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv
```

### Install dependencies

```bash
uv sync
```

### Run the application

```bash
# Auto-discover oscilloscope via USB
uv run python -m shutterscope

# Connect via ethernet using VISA address
uv run python -m shutterscope TCPIP::192.168.1.100::INSTR

# Show help
uv run python -m shutterscope --help
```

### Development

```bash
uv run pytest       # Run tests
uv run mypy src     # Type check
uv run ruff check   # Lint
uv run ruff format  # Format
```
