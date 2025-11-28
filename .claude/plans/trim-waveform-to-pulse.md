# Trim Waveform to Pulse Region

## Overview

Instead of storing the full 1.2M samples, detect the pulse first and then trim the waveform data to just the pulse region plus 10% margin on each side.

## Current Flow

1. Configure timebase based on `--max-shutter`
2. Wait for trigger
3. Download full memory (~1.2M samples)
4. Measure pulse width
5. Save full waveform to JSON

## Proposed Flow

1. Configure timebase (keep for display/trigger setup)
2. Wait for trigger
3. Download full memory
4. Measure pulse width
5. **Trim waveform to pulse ± 10% margin**
6. Save trimmed waveform to JSON

## Implementation

### Option A: Trim in `__main__.py` after measurement

Add a helper function to create a trimmed copy of the waveform:

```python
def trim_waveform_to_pulse(
    waveform: WaveformData,
    metrics: PulseMetrics,
    margin_fraction: float = 0.1
) -> WaveformData:
    """Create a new waveform containing only the pulse region with margins."""
```

**Pros:** Simple, keeps analysis module focused on measurement
**Cons:** Logic split across files

### Option B: Add trim function to `analysis.py`

Keep pulse-related operations together in the analysis module.

**Pros:** All pulse logic in one place
**Cons:** Analysis module starts doing data transformation

### Option C: Add method to `WaveformData` class

```python
@dataclass
class WaveformData:
    def trim(self, start_time: float, end_time: float) -> WaveformData:
        """Return a new WaveformData trimmed to the specified time range."""
```

Then in `__main__.py`:
```python
margin = metrics.pulse_width_s * 0.1
trimmed = waveform.trim(
    metrics.rising_edge_time - margin,
    metrics.falling_edge_time + margin
)
```

**Pros:** Generic, reusable, keeps WaveformData self-contained
**Cons:** Adds complexity to the dataclass

## Recommendation

**Option C** - Add a `trim()` method to `WaveformData`. This is the most flexible approach:
- Generic enough to be useful for other purposes
- Keeps the dataclass responsible for its own data operations
- Clean API in `__main__.py`

## Implementation Steps

### Step 1: Add `trim()` method to `WaveformData` in `oscilloscope.py`

```python
def trim(self, start_time: float, end_time: float) -> WaveformData:
    """Return a new WaveformData trimmed to the specified time range.

    Args:
        start_time: Start of trim window in seconds
        end_time: End of trim window in seconds

    Returns:
        New WaveformData containing only samples within the time range
    """
    # Calculate sample indices from times
    start_idx = max(0, int((start_time - self.start_time) * self.sample_rate))
    end_idx = min(len(self.voltages), int((end_time - self.start_time) * self.sample_rate))

    return WaveformData(
        voltages=self.voltages[start_idx:end_idx],
        sample_rate=self.sample_rate,
        start_time=self.start_time + start_idx / self.sample_rate,
    )
```

### Step 2: Update `__main__.py` to trim after measurement

```python
# After measuring pulse width
if metrics is not None:
    margin = metrics.pulse_width_s * 0.1
    waveform = waveform.trim(
        metrics.rising_edge_time - margin,
        metrics.falling_edge_time + margin
    )
```

### Step 3: Add tests for trim functionality

- Test basic trimming
- Test edge cases (trim before start, after end)
- Test that sample_rate and timing are preserved

### Step 4: Remove `--max-shutter` flag and simplify timebase config

Since we're auto-detecting the pulse and trimming:
- Remove `--max-shutter` CLI argument
- Use a fixed generous timebase (e.g., 1 second total capture window)
- The scope will capture everything, we trim to the actual pulse

Update `configure_timebase()` to use a fixed duration or make it parameterless with sensible defaults.

### Step 5: Update README

Remove references to `--max-shutter` from documentation.

## File Changes

| File | Change |
|------|--------|
| `src/shutterscope/oscilloscope.py` | Add `trim()` method to `WaveformData` |
| `src/shutterscope/__main__.py` | Trim waveform after measurement, remove `--max-shutter` |
| `tests/test_oscilloscope.py` | Add tests for `trim()` method |
| `README.md` | Remove `--max-shutter` documentation |

## Expected Output

Before: `Saved 1200000 samples to capture.json`
After: `Saved 8800 samples to capture.json` (for an 8ms pulse at 1MHz with 10% margins)

This reduces file size from ~15MB to ~100KB for typical shutter measurements.
