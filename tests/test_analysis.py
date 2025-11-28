"""Tests for pulse analysis."""

import pytest

from shutterscope.analysis import (
    PulseMeasurementError,
    PulseMetrics,
    measure_pulse_width,
)
from shutterscope.oscilloscope import WaveformData


def test_measure_pulse_width_ideal_square_pulse() -> None:
    """Test measurement of an ideal square pulse."""
    # 100 samples at 1MHz: 20µs low, 60µs high, 20µs low
    voltages = [0.0] * 20 + [3.3] * 60 + [0.0] * 20
    waveform = WaveformData(voltages=voltages, sample_rate=1e6, start_time=0.0)

    metrics = measure_pulse_width(waveform)

    # Pulse should be 60µs = 0.00006s
    assert metrics.pulse_width_s == pytest.approx(60e-6, rel=0.01)
    assert metrics.min_v == 0.0
    assert metrics.max_v == 3.3
    assert metrics.threshold_v == pytest.approx(1.65)


def test_measure_pulse_width_with_offset() -> None:
    """Test measurement when pulse doesn't start at 0V."""
    # Pulse from 1V to 4V
    voltages = [1.0] * 20 + [4.0] * 50 + [1.0] * 30
    waveform = WaveformData(voltages=voltages, sample_rate=1e6, start_time=0.0)

    metrics = measure_pulse_width(waveform)

    # Pulse should be 50µs
    assert metrics.pulse_width_s == pytest.approx(50e-6, rel=0.01)
    assert metrics.threshold_v == pytest.approx(2.5)


def test_measure_pulse_width_with_negative_start_time() -> None:
    """Test that start_time is correctly applied to edge times."""
    voltages = [0.0] * 10 + [3.3] * 80 + [0.0] * 10
    waveform = WaveformData(voltages=voltages, sample_rate=1e6, start_time=-50e-6)

    metrics = measure_pulse_width(waveform)

    # Rising edge crossing is between samples 9 and 10
    # Interpolation: threshold (1.65) is at 50% between 0 and 3.3
    # Time = -50µs + 9µs + 0.5µs = -40.5µs
    assert metrics.rising_edge_time == pytest.approx(-40.5e-6, rel=0.01)
    # Falling edge crossing is between samples 89 and 90
    # Time = -50µs + 89µs + 0.5µs = 39.5µs
    assert metrics.falling_edge_time == pytest.approx(39.5e-6, rel=0.01)
    # Pulse width should still be 80µs
    assert metrics.pulse_width_s == pytest.approx(80e-6, rel=0.01)


def test_measure_pulse_width_no_rising_edge() -> None:
    """Test error when no rising edge is found."""
    # All low signal
    voltages = [0.0] * 100
    waveform = WaveformData(voltages=voltages, sample_rate=1e6, start_time=0.0)

    with pytest.raises(PulseMeasurementError, match="No rising edge"):
        measure_pulse_width(waveform)


def test_measure_pulse_width_no_falling_edge() -> None:
    """Test error when rising edge found but no falling edge."""
    # Signal goes high but never comes back down
    voltages = [0.0] * 20 + [3.3] * 80
    waveform = WaveformData(voltages=voltages, sample_rate=1e6, start_time=0.0)

    with pytest.raises(PulseMeasurementError, match="No falling edge"):
        measure_pulse_width(waveform)


def test_measure_pulse_width_waveform_too_short() -> None:
    """Test error when waveform is too short."""
    waveform = WaveformData(voltages=[0.0], sample_rate=1e6, start_time=0.0)

    with pytest.raises(PulseMeasurementError, match="too short"):
        measure_pulse_width(waveform)


def test_pulse_metrics_pulse_width_ms() -> None:
    """Test pulse_width_ms property."""
    metrics = PulseMetrics(
        pulse_width_s=0.008,
        rising_edge_time=-0.004,
        falling_edge_time=0.004,
        threshold_v=1.65,
        min_v=0.0,
        max_v=3.3,
    )

    assert metrics.pulse_width_ms == 8.0


def test_pulse_metrics_shutter_speed_fraction() -> None:
    """Test shutter_speed_fraction property."""
    # 1/125 second shutter
    metrics = PulseMetrics(
        pulse_width_s=0.008,
        rising_edge_time=-0.004,
        falling_edge_time=0.004,
        threshold_v=1.65,
        min_v=0.0,
        max_v=3.3,
    )

    assert metrics.shutter_speed_fraction == "1/125"


def test_pulse_metrics_shutter_speed_fraction_fast() -> None:
    """Test shutter_speed_fraction for fast shutter."""
    # 1/1000 second shutter
    metrics = PulseMetrics(
        pulse_width_s=0.001,
        rising_edge_time=-0.0005,
        falling_edge_time=0.0005,
        threshold_v=1.65,
        min_v=0.0,
        max_v=3.3,
    )

    assert metrics.shutter_speed_fraction == "1/1000"


def test_pulse_metrics_shutter_speed_fraction_slow() -> None:
    """Test shutter_speed_fraction for slow shutter."""
    # 1/30 second shutter
    metrics = PulseMetrics(
        pulse_width_s=0.0333,
        rising_edge_time=-0.01665,
        falling_edge_time=0.01665,
        threshold_v=1.65,
        min_v=0.0,
        max_v=3.3,
    )

    assert metrics.shutter_speed_fraction == "1/30"
