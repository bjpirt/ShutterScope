# Three-Point Shutter Testing

## Overview

Add support for three sensors to measure shutter timing across the film plane. This enables measurement of shutter travel time, timing uniformity, and individual exposure times at left edge, center, and right edge positions.

## What Three-Point Testing Measures

- **Individual pulse widths** at each sensor location (exposure time at that point)
- **Shutter travel time** - time for curtain to traverse the frame
- **Timing uniformity** - whether all parts of the frame receive equal exposure
- **First/second curtain timing** - compare leading and trailing edge delays

## Hardware Considerations

### Rigol DS1000Z Capabilities
- 4 analog channels with synchronized sampling
- Trigger on one channel, all channels capture simultaneously
- Memory depth with 3 channels: 4M points each (reduced from 12M single-channel)
- At 1µs sample interval: ~4 seconds capture window (more than sufficient)

### Triggering Strategy
- Trigger on the last sensor's falling edge (same as current single-sensor mode)
- Which sensor is "last" depends on shutter orientation (horizontal vs vertical travel)
- All channels capture with identical timing reference
- Pre-trigger data contains the complete shutter travel sequence across all sensors

### Shutter Orientation
Focal plane shutters travel either horizontally or vertically:
- **Horizontal travel**: Common in older cameras, curtains move left-to-right or right-to-left
- **Vertical travel**: Common in modern cameras, curtains move top-to-bottom

The `--orientation` parameter determines:
1. Which sensor triggers (the one the shutter reaches last)
2. How to interpret timing data (travel direction)

### Sensor Positions
Define as constants in `analysis.py`:
```python
# Sensor spacing for 35mm film (mm)
# Horizontal travel: across 36mm frame width
HORIZONTAL_SENSOR_SPACING_MM = 36.0
# Vertical travel: across 24mm frame height
VERTICAL_SENSOR_SPACING_MM = 24.0
```

These enable velocity calculations when combined with timing data. The spacing depends on orientation since 35mm film frames are 36mm wide × 24mm tall.

## Implementation Plan

### Phase 1: Multi-Channel Capture

#### Step 1.1: Add `get_waveforms()` to oscilloscope

Add method to `RigolDS1000Z` class in `oscilloscope.py`:

```python
def get_waveforms(self, channels: list[int]) -> dict[int, WaveformData]:
    """Retrieve waveform data from multiple channels.

    All channels are captured with synchronized timing from the same trigger.

    Args:
        channels: List of channel numbers (1-4)

    Returns:
        Dictionary mapping channel number to WaveformData
    """
```

Implementation notes:
- Query memory depth once (shared across channels)
- Sample rate and x_origin are identical for all channels
- Each channel has its own preamble (y scaling) and offset
- Download channels sequentially (could optimize later)

#### Step 1.2: Update Protocol

Add to `OscilloscopeProtocol`:

```python
def get_waveforms(self, channels: list[int]) -> dict[int, WaveformData]:
    """Retrieve waveform data from multiple channels."""
    ...
```

#### Step 1.3: Configure multiple channels

Update `configure_timebase()` to accept optional channels parameter:

```python
def configure_timebase(
    self,
    max_duration: float,
    sample_interval: float = 1e-6,
    channels: list[int] | None = None,
) -> None:
```

Configure vertical scale and display for each specified channel.

### Phase 2: Three-Point Analysis

#### Step 2.1: Add `ThreePointMetrics` dataclass

Add to `analysis.py`:

```python
# Sensor spacing for 35mm film (mm)
HORIZONTAL_SENSOR_SPACING_MM = 36.0  # Frame width
VERTICAL_SENSOR_SPACING_MM = 24.0    # Frame height

@dataclass
class ThreePointMetrics:
    """Metrics from three-point shutter measurement."""

    first: PulseMetrics   # First sensor hit by shutter
    center: PulseMetrics
    last: PulseMetrics    # Last sensor hit by shutter
    orientation: str      # "horizontal" or "vertical"

    # Derived timing
    first_to_center_delay_s: float  # Rising edge delay
    center_to_last_delay_s: float   # Rising edge delay
    shutter_travel_time_s: float    # First rise to last rise

    @property
    def sensor_spacing_mm(self) -> float:
        """Get sensor spacing based on orientation."""
        if self.orientation == "vertical":
            return VERTICAL_SENSOR_SPACING_MM
        return HORIZONTAL_SENSOR_SPACING_MM

    @property
    def first_to_center_delay_ms(self) -> float:
        return self.first_to_center_delay_s * 1000

    @property
    def center_to_last_delay_ms(self) -> float:
        return self.center_to_last_delay_s * 1000

    @property
    def shutter_travel_time_ms(self) -> float:
        return self.shutter_travel_time_s * 1000

    @property
    def shutter_velocity_mm_per_s(self) -> float:
        """Calculate shutter curtain velocity in mm/s."""
        if self.shutter_travel_time_s <= 0:
            return 0.0
        return self.sensor_spacing_mm / self.shutter_travel_time_s

    @property
    def shutter_velocity_m_per_s(self) -> float:
        """Calculate shutter curtain velocity in m/s."""
        return self.shutter_velocity_mm_per_s / 1000

    @property
    def timing_uniformity(self) -> float:
        """Uniformity index 0-100. 100 = all three pulse widths identical."""
        widths = [self.first.pulse_width_s, self.center.pulse_width_s, self.last.pulse_width_s]
        mean = sum(widths) / 3
        max_deviation = max(abs(w - mean) for w in widths)
        if mean == 0:
            return 0.0
        return max(0.0, 100.0 * (1 - max_deviation / mean))
```

#### Step 2.2: Add `measure_three_point()` function

```python
def measure_three_point(
    waveforms: dict[int, WaveformData],
    left_channel: int = 1,
    center_channel: int = 2,
    right_channel: int = 3,
) -> ThreePointMetrics:
    """Measure three-point shutter timing.

    Args:
        waveforms: Dictionary of channel -> WaveformData
        left_channel: Channel number for left sensor
        center_channel: Channel number for center sensor
        right_channel: Channel number for right sensor

    Returns:
        ThreePointMetrics with timing data from all three points

    Raises:
        PulseMeasurementError: If any channel fails pulse detection
    """
```

### Phase 3: CLI and Output

#### Step 3.1: Add `--three-point` flag

Update `__main__.py`:

```python
parser.add_argument(
    "--three-point",
    action="store_true",
    help="Use three-point measurement mode (channels 1, 2, 3)",
)
parser.add_argument(
    "--orientation",
    choices=["horizontal", "vertical"],
    default="horizontal",
    help="Shutter travel direction: horizontal (left-right) or vertical (top-bottom)",
)
```

#### Step 3.2: Three-point capture loop

When `--three-point` is enabled:
- Configure channels 1, 2, 3
- Determine trigger channel based on orientation:
  - Horizontal: trigger on channel 3 (right sensor, last to complete)
  - Vertical: trigger on channel 1 or 3 depending on travel direction
- Download all three waveforms
- Run `measure_three_point()` analysis with orientation
- Display comprehensive timing report including travel velocity

#### Step 3.3: Update JSON output

Extend waveform JSON for three-point captures:

```json
{
    "version": 1,
    "capture_time": "2025-01-15T10:30:00+00:00",
    "mode": "three_point",
    "channels": {
        "1": {
            "label": "left",
            "sample_rate_hz": 1000000,
            "start_time_s": -0.5,
            "samples": [...]
        },
        "2": {
            "label": "center",
            ...
        },
        "3": {
            "label": "right",
            ...
        }
    },
    "measurements": {
        "left": {"pulse_width_s": 0.008, "shutter_speed_fraction": "1/125"},
        "center": {"pulse_width_s": 0.008, "shutter_speed_fraction": "1/125"},
        "right": {"pulse_width_s": 0.008, "shutter_speed_fraction": "1/125"},
        "left_to_center_delay_s": 0.00001,
        "center_to_right_delay_s": 0.00001,
        "shutter_travel_time_s": 0.00002,
        "timing_uniformity": 99.5
    }
}
```

#### Step 3.4: Three-point plot

Create visualization showing:
- All three waveforms on same time axis
- Vertical lines marking rising/falling edges
- Annotations showing delays between channels

### Phase 4: Testing

#### Step 4.1: Update MockOscilloscope

Add `get_waveforms()` method that returns test data for multiple channels with realistic timing offsets.

#### Step 4.2: Unit tests for three-point analysis

- Test `measure_three_point()` with synthetic waveforms
- Test timing calculations with known delays
- Test uniformity calculation
- Test error handling when channels have no pulse

#### Step 4.3: Integration tests

- Test full three-point capture flow with mock
- Test JSON save/load round-trip
- Test plot generation

## File Changes Summary

| File | Changes |
|------|---------|
| `src/shutterscope/oscilloscope.py` | Add `get_waveforms()` method, update `configure_timebase()` |
| `src/shutterscope/analysis.py` | Add `ThreePointMetrics`, `measure_three_point()` |
| `src/shutterscope/waveform.py` | Add multi-channel JSON save/load, three-point plot |
| `src/shutterscope/__main__.py` | Add `--three-point` flag, three-point capture loop |
| `tests/conftest.py` | Update MockOscilloscope with `get_waveforms()` |
| `tests/test_analysis.py` | Add three-point measurement tests |
| `tests/test_oscilloscope.py` | Add multi-channel tests |

## Console Output Example

```
Searching for Rigol DS1000Z oscilloscope...
Connected to oscilloscope
Configured oscilloscope (3-channel mode, horizontal)
Press Ctrl+C to exit

Waiting for trigger...
Triggered! Downloading waveforms...

Three-Point Shutter Measurement (horizontal):
  First:  8.02 ms (1/125 s)
  Center: 8.01 ms (1/125 s)
  Last:   8.00 ms (1/125 s)

  Travel Time:     15.2 µs
  First→Center:    7.5 µs
  Center→Last:     7.7 µs
  Curtain Velocity: 2.37 m/s
  Uniformity:      99.8%

Saved to captures/capture_2025-01-15T10:30:00.json
```

## Future Enhancements

- Configurable channel assignments (`--channels 1,2,4`)
- Sensor spacing input for velocity calculation
- CSV export for spreadsheet analysis
- Comparison mode (overlay multiple captures)
- Statistical analysis across multiple measurements
