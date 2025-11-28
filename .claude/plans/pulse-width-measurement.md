# Pulse Width Measurement Implementation Plan

## Overview

Add pulse width measurement using 50% threshold crossing to calculate shutter timing from captured waveforms.

## Algorithm

The 50% threshold crossing method:
1. Find the minimum and maximum voltage values in the waveform
2. Calculate the 50% threshold level: `threshold = (max + min) / 2`
3. Find the first rising edge crossing (voltage goes from below to above threshold)
4. Find the first falling edge crossing after the rising edge (voltage goes from above to below threshold)
5. Pulse width = time at falling edge - time at rising edge

## Implementation Steps

### Step 1: Create analysis module

Create `src/shutterscope/analysis.py` with:

```python
@dataclass
class PulseMetrics:
    pulse_width_s: float      # Pulse width in seconds
    rising_edge_time: float   # Time of rising edge crossing
    falling_edge_time: float  # Time of falling edge crossing
    threshold_v: float        # Threshold voltage used
    min_v: float              # Minimum voltage in waveform
    max_v: float              # Maximum voltage in waveform

def measure_pulse_width(waveform: WaveformData) -> PulseMetrics:
    """Measure pulse width using 50% threshold crossing."""
```

The function will:
- Calculate min/max voltages
- Find 50% threshold
- Scan for rising edge crossing
- Scan for falling edge crossing
- Return PulseMetrics dataclass

### Step 2: Update waveform.py for metadata storage

Modify `save_waveform_json()` to accept optional `PulseMetrics`:
- Add `shutter_speed_s` field to JSON output
- Add `shutter_speed_fraction` field (e.g., "1/125")
- Keep backward compatibility (metrics are optional)

Update JSON schema version to 2 (but still read version 1 files).

### Step 3: Update CLI to display and save results

Modify `__main__.py`:
- After downloading waveform, call `measure_pulse_width()`
- Display results in terminal:
  ```
  Shutter speed: 8.05 ms (1/124)
  ```
- Pass metrics to `save_waveform_json()` for storage

### Step 4: Add tests

Create `tests/test_analysis.py`:
- Test with ideal square pulse
- Test with pulse that doesn't start at 0V
- Test edge cases (no pulse found, incomplete pulse)

## File Changes Summary

| File | Change |
|------|--------|
| `src/shutterscope/analysis.py` | New file - pulse measurement logic |
| `src/shutterscope/waveform.py` | Add metrics to JSON output |
| `src/shutterscope/__main__.py` | Call analysis, display results |
| `tests/test_analysis.py` | New file - tests for analysis |

## Output Format

Terminal output:
```
Shutter speed: 8.05 ms (1/124)
```

JSON output (new fields):
```json
{
  "version": 2,
  "capture_time": "...",
  "sample_rate_hz": 10000000,
  "start_time_s": -0.06,
  "samples": [...],
  "shutter_speed_s": 0.00805,
  "shutter_speed_fraction": "1/124"
}
```

## Edge Cases to Handle

1. **No pulse detected**: If no rising edge found, raise an exception or return None
2. **Incomplete pulse**: If rising edge found but no falling edge, report error
3. **Multiple pulses**: Only measure the first complete pulse
4. **Noisy signal**: The simple threshold crossing should work for clean photodiode signals; more sophisticated filtering can be added later if needed
