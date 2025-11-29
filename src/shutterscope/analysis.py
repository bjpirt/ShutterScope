"""Waveform analysis for shutter timing measurement."""

from __future__ import annotations

from dataclasses import dataclass

from shutterscope.oscilloscope import WaveformData


@dataclass
class PulseMetrics:
    """Results from pulse width measurement.

    All times are in seconds, voltages in volts.
    """

    pulse_width_s: float
    rising_edge_time: float
    falling_edge_time: float
    threshold_v: float
    min_v: float
    max_v: float

    @property
    def pulse_width_ms(self) -> float:
        """Pulse width in milliseconds."""
        return self.pulse_width_s * 1000

    @property
    def shutter_speed_fraction(self) -> str:
        """Shutter speed as a fraction (e.g., '1/125').

        Returns the closest standard fraction representation.
        """
        if self.pulse_width_s <= 0:
            return "N/A"
        denominator = round(1 / self.pulse_width_s)
        return f"1/{denominator}"


class PulseMeasurementError(Exception):
    """Raised when pulse measurement fails."""


def measure_pulse_width(waveform: WaveformData) -> PulseMetrics:
    """Measure pulse width using 50% threshold crossing.

    Finds the first complete pulse in the waveform by detecting where the
    signal crosses the 50% threshold level (midpoint between min and max).

    Args:
        waveform: Captured waveform data

    Returns:
        PulseMetrics with timing and voltage information

    Raises:
        PulseMeasurementError: If no complete pulse is found
    """
    voltages = waveform.voltages
    sample_rate = waveform.sample_rate
    start_time = waveform.start_time

    if len(voltages) < 2:
        raise PulseMeasurementError("Waveform too short for pulse detection")

    min_v = min(voltages)
    max_v = max(voltages)
    threshold = (min_v + max_v) / 2

    # Find rising edge: signal goes from below to above threshold
    rising_edge_idx: int | None = None
    for i in range(len(voltages) - 1):
        if voltages[i] <= threshold < voltages[i + 1]:
            rising_edge_idx = i
            break

    if rising_edge_idx is None:
        raise PulseMeasurementError("No rising edge found in waveform")

    # Find falling edge after rising edge: signal goes from above to below threshold
    falling_edge_idx: int | None = None
    for i in range(rising_edge_idx + 1, len(voltages) - 1):
        if voltages[i] > threshold >= voltages[i + 1]:
            falling_edge_idx = i
            break

    if falling_edge_idx is None:
        raise PulseMeasurementError("No falling edge found after rising edge")

    # Interpolate to find precise crossing times
    rising_edge_time = _interpolate_crossing(
        voltages[rising_edge_idx],
        voltages[rising_edge_idx + 1],
        threshold,
        start_time + rising_edge_idx / sample_rate,
        1 / sample_rate,
    )

    falling_edge_time = _interpolate_crossing(
        voltages[falling_edge_idx],
        voltages[falling_edge_idx + 1],
        threshold,
        start_time + falling_edge_idx / sample_rate,
        1 / sample_rate,
    )

    pulse_width = falling_edge_time - rising_edge_time

    return PulseMetrics(
        pulse_width_s=pulse_width,
        rising_edge_time=rising_edge_time,
        falling_edge_time=falling_edge_time,
        threshold_v=threshold,
        min_v=min_v,
        max_v=max_v,
    )


def _interpolate_crossing(
    v1: float, v2: float, threshold: float, t1: float, dt: float
) -> float:
    """Linearly interpolate to find the exact threshold crossing time.

    Args:
        v1: Voltage at sample before crossing
        v2: Voltage at sample after crossing
        threshold: Threshold voltage
        t1: Time at sample before crossing
        dt: Time between samples

    Returns:
        Interpolated time of threshold crossing
    """
    if v2 == v1:
        return t1
    fraction = (threshold - v1) / (v2 - v1)
    return t1 + fraction * dt


@dataclass
class ThreePointMetrics:
    """Metrics from three-point shutter measurement.

    Contains pulse measurements from first, center, and last sensors,
    plus derived timing relationships.
    """

    first: PulseMetrics
    center: PulseMetrics
    last: PulseMetrics
    orientation: str  # "horizontal" or "vertical"

    # Derived timing
    first_to_center_delay_s: float
    center_to_last_delay_s: float
    shutter_travel_time_s: float

    @property
    def first_to_center_delay_ms(self) -> float:
        """First-to-center delay in milliseconds."""
        return self.first_to_center_delay_s * 1000

    @property
    def center_to_last_delay_ms(self) -> float:
        """Center-to-last delay in milliseconds."""
        return self.center_to_last_delay_s * 1000

    @property
    def shutter_travel_time_ms(self) -> float:
        """Total shutter travel time in milliseconds."""
        return self.shutter_travel_time_s * 1000

    @property
    def timing_uniformity(self) -> float:
        """Uniformity index 0-100. 100 = all three pulse widths identical."""
        widths = [
            self.first.pulse_width_s,
            self.center.pulse_width_s,
            self.last.pulse_width_s,
        ]
        mean = sum(widths) / 3
        max_deviation = max(abs(w - mean) for w in widths)
        if mean == 0:
            return 0.0
        return max(0.0, 100.0 * (1 - max_deviation / mean))


def measure_three_point(
    waveforms: dict[int, WaveformData],
    orientation: str = "horizontal",
    first_channel: int = 1,
    center_channel: int = 2,
    last_channel: int = 3,
) -> ThreePointMetrics:
    """Measure three-point shutter timing.

    Analyzes waveforms from three sensors to measure shutter travel
    characteristics across the film plane.

    Args:
        waveforms: Dictionary of channel -> WaveformData
        orientation: "horizontal" or "vertical" shutter travel
        first_channel: Channel number for first sensor (hit first by shutter)
        center_channel: Channel number for center sensor
        last_channel: Channel number for last sensor (hit last by shutter)

    Returns:
        ThreePointMetrics with timing data from all three points

    Raises:
        PulseMeasurementError: If any channel fails pulse detection
    """
    first_metrics = measure_pulse_width(waveforms[first_channel])
    center_metrics = measure_pulse_width(waveforms[center_channel])
    last_metrics = measure_pulse_width(waveforms[last_channel])

    # Calculate timing delays between sensors (rising edge to rising edge)
    first_to_center_delay = (
        center_metrics.rising_edge_time - first_metrics.rising_edge_time
    )
    center_to_last_delay = (
        last_metrics.rising_edge_time - center_metrics.rising_edge_time
    )

    # Total travel time: first sensor rise to last sensor rise
    shutter_travel_time = last_metrics.rising_edge_time - first_metrics.rising_edge_time

    return ThreePointMetrics(
        first=first_metrics,
        center=center_metrics,
        last=last_metrics,
        orientation=orientation,
        first_to_center_delay_s=first_to_center_delay,
        center_to_last_delay_s=center_to_last_delay,
        shutter_travel_time_s=shutter_travel_time,
    )
