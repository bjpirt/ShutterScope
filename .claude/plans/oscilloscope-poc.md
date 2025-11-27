# ShutterScope Proof of Concept Plan

## Goal
Implement initial PoC to connect to a Rigol DS1000Z oscilloscope, set up a trigger on channel 1, wait for trigger, and download waveform data to a file.

## Architecture

### File Structure
```
src/shutterscope/
├── __init__.py
├── __main__.py          # CLI entry point
├── oscilloscope.py      # Protocol + RigolDS1000Z implementation
└── waveform.py          # Waveform data handling
tests/
├── conftest.py          # Shared fixtures (MockOscilloscope)
├── test_oscilloscope.py
└── test_waveform.py
```

### Component Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                      __main__.py                            │
│  - Discovers oscilloscope via find_device()                 │
│  - Orchestrates: connect → trigger → wait → capture → save  │
└─────────────────────────┬───────────────────────────────────┘
                          │ uses
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  OscilloscopeProtocol                       │
│  (typing.Protocol - defines interface)                      │
│  - connect() / disconnect()                                 │
│  - setup_edge_trigger(channel, level, slope)                │
│  - wait_for_trigger(timeout) -> bool                        │
│  - get_waveform(channel) -> WaveformData                    │
└─────────────────────────┬───────────────────────────────────┘
                          │ implemented by
          ┌───────────────┴───────────────┐
          ▼                               ▼
┌─────────────────────┐       ┌─────────────────────┐
│   RigolDS1000Z      │       │  MockOscilloscope   │
│   (production)      │       │  (testing)          │
│                     │       │                     │
│ - Uses pyvisa       │       │ - Returns fake data │
│ - Sends SCPI cmds   │       │ - No hardware needed│
│ - USB connection    │       │                     │
└─────────────────────┘       └─────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      waveform.py                            │
│  - WaveformData dataclass (times, voltages, sample_rate)    │
│  - save_waveform(data, filename) -> writes CSV              │
└─────────────────────────────────────────────────────────────┘
```

### Dependency Injection Pattern

The `OscilloscopeProtocol` enables swapping implementations without changing calling code:

```python
# Production: real hardware
scope: OscilloscopeProtocol = RigolDS1000Z(resource_string)

# Testing: mock implementation
scope: OscilloscopeProtocol = MockOscilloscope()
```

### Testing Strategy

| Component | What to Test | How |
|-----------|--------------|-----|
| `WaveformData` | Dataclass creation | Unit test with sample data |
| `save_waveform()` | CSV output format | Unit test with temp file, verify contents |
| `RigolDS1000Z.find_device()` | Device discovery logic | Mock `pyvisa.ResourceManager` |
| `RigolDS1000Z` SCPI commands | Correct command strings sent | Mock the VISA instrument, verify `write()`/`query()` calls |
| `wait_for_trigger()` | Polling + timeout logic | Mock instrument returning different statuses |
| CLI integration | End-to-end flow | Integration test with `MockOscilloscope` |

**Key testing principle**: Tests use `MockOscilloscope` (implements `OscilloscopeProtocol`) so no real hardware is needed. The mock returns predictable `WaveformData` for assertions.

**Constants**: Trigger level is defined as `DEFAULT_TRIGGER_LEVEL = 1.0` constant. Tests don't assert on this value, allowing it to be changed without breaking tests.

## Implementation Steps

### Step 1: Define OscilloscopeProtocol (oscilloscope.py)

```python
from typing import Protocol
from dataclasses import dataclass

@dataclass
class WaveformData:
    times: list[float]
    voltages: list[float]
    sample_rate: float

class OscilloscopeProtocol(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def setup_edge_trigger(self, channel: int, level: float, slope: str = "POS") -> None: ...
    def wait_for_trigger(self, timeout: float = 10.0) -> bool: ...
    def get_waveform(self, channel: int) -> WaveformData: ...
```

### Step 2: Implement RigolDS1000Z class (oscilloscope.py)

Key SCPI commands needed:
- `*IDN?` - Identify device (check for "RIGOL" and "DS1" in response)
- `:TRIGger:MODE EDGE` - Set edge trigger mode
- `:TRIGger:EDGe:SOURce CHANn` - Set trigger source
- `:TRIGger:EDGe:LEVel <level>` - Set trigger level
- `:TRIGger:EDGe:SLOPe POS|NEG` - Set trigger slope
- `:TRIGger:SWEep SINGle` - Single trigger mode
- `:TRIGger:STATus?` - Query trigger status (returns TD when triggered)
- `:WAVeform:SOURce CHANn` - Set waveform source
- `:WAVeform:MODE NORMal` - Set waveform mode
- `:WAVeform:FORMat ASCii` - ASCII format for simplicity
- `:WAVeform:DATA?` - Get waveform data
- `:WAVeform:XINCrement?` - Get time increment
- `:WAVeform:XORigin?` - Get time origin

```python
class RigolDS1000Z:
    @classmethod
    def auto_connect(cls) -> "RigolDS1000Z":
        """Find first Rigol DS1000Z on VISA bus and return connected instance.

        Raises ConnectionError if no device found.
        """
        rm = pyvisa.ResourceManager()
        for resource in rm.list_resources():
            try:
                instr = rm.open_resource(resource)
                idn = instr.query("*IDN?")
                if "RIGOL" in idn and "DS1" in idn:
                    instance = cls(resource)
                    instance._instrument = instr
                    return instance
                instr.close()
            except Exception:
                pass
        raise ConnectionError("No Rigol DS1000Z oscilloscope found")

    def __init__(self, resource: str) -> None:
        self._resource = resource
        self._instrument: pyvisa.Resource | None = None
```

### Step 3: Implement waveform saving (waveform.py)

Simple CSV format for PoC:
```python
def save_waveform(data: WaveformData, filename: str) -> None:
    with open(filename, "w") as f:
        f.write("time_s,voltage_v\n")
        for t, v in zip(data.times, data.voltages):
            f.write(f"{t},{v}\n")
```

### Step 4: Update CLI (__main__.py)

The CLI stays thin - device discovery is handled by `RigolDS1000Z.auto_connect()`:

```python
def main() -> None:
    # Auto-discover and connect (raises if not found)
    scope = RigolDS1000Z.auto_connect()

    try:
        # Setup trigger on channel 1
        scope.setup_edge_trigger(channel=1, level=DEFAULT_TRIGGER_LEVEL)

        # Wait for trigger
        print("Waiting for trigger...")
        if scope.wait_for_trigger(timeout=30.0):
            waveform = scope.get_waveform(channel=1)
            save_waveform(waveform, "capture.csv")
            print("Saved waveform to capture.csv")
        else:
            print("Trigger timeout")
    finally:
        scope.disconnect()
```

### Step 5: Create tests with mock oscilloscope

```python
class MockOscilloscope:
    def connect(self) -> None: pass
    def disconnect(self) -> None: pass
    def setup_edge_trigger(self, channel: int, level: float, slope: str = "POS") -> None: pass
    def wait_for_trigger(self, timeout: float = 10.0) -> bool: return True
    def get_waveform(self, channel: int) -> WaveformData:
        return WaveformData(times=[0.0, 0.001], voltages=[0.0, 1.0], sample_rate=1000.0)
```

## SCPI Command Reference

Based on [Rigol DS1000Z Programming Guide](https://www.batronix.com/files/Rigol/Oszilloskope/_DS&MSO1000Z/MSO_DS1000Z_ProgrammingGuide_EN.pdf):

| Command | Description |
|---------|-------------|
| `*IDN?` | Query device identity |
| `:TRIGger:MODE EDGE` | Set trigger mode to edge |
| `:TRIGger:EDGe:SOURce CHAN1` | Trigger on channel 1 |
| `:TRIGger:EDGe:LEVel 1.0` | Set trigger level to 1V |
| `:TRIGger:EDGe:SLOPe POSitive` | Trigger on rising edge |
| `:TRIGger:SWEep SINGle` | Single acquisition mode |
| `:TRIGger:STATus?` | Returns WAIT, RUN, AUTO, TD (triggered), STOP |
| `:SINGle` | Arm single trigger |
| `:WAVeform:SOURce CHAN1` | Set waveform source |
| `:WAVeform:MODE NORMal` | Normal mode (screen data) |
| `:WAVeform:FORMat ASCii` | ASCII format |
| `:WAVeform:DATA?` | Get waveform data |

## Files to Modify

1. `src/shutterscope/__init__.py` - Export public API
2. `src/shutterscope/__main__.py` - Replace placeholder with CLI
3. `src/shutterscope/oscilloscope.py` - New file: Protocol + implementation
4. `src/shutterscope/waveform.py` - New file: Waveform data handling
5. `tests/conftest.py` - New file: Shared fixtures
6. `tests/test_oscilloscope.py` - New file: Oscilloscope tests
7. `tests/test_waveform.py` - New file: Waveform tests
8. `pyproject.toml` - Remove snakesay dependency if present

## Design Decisions

- **Trigger level**: Hardcoded as a constant for easy editing, tests won't depend on specific value
- **Output format**: CSV with `time_s,voltage_v` columns
- **Trigger slope**: Rising edge (POS) default
- **Connection**: USB via VISA for now; structure code to allow future LAN support
