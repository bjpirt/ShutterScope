"""Tests for waveform data handling."""

import json
from pathlib import Path

from shutterscope.oscilloscope import WaveformData
from shutterscope.waveform import (
    load_waveform_json,
    save_waveform_csv,
    save_waveform_json,
)


def test_save_waveform_json(tmp_path: Path) -> None:
    """Verify JSON file is created with correct structure."""
    waveform = WaveformData(
        voltages=[0.0, 3.3, 0.0],
        sample_rate=1e6,
        start_time=0.0,
    )
    output_file = tmp_path / "test.json"

    save_waveform_json(waveform, str(output_file))

    assert output_file.exists()
    data = json.loads(output_file.read_text())

    assert data["version"] == 1
    assert data["sample_rate_hz"] == 1e6
    assert data["start_time_s"] == 0.0
    assert data["samples"] == [0.0, 3.3, 0.0]
    assert "capture_time" in data


def test_load_waveform_json(tmp_path: Path) -> None:
    """Verify JSON file can be loaded back into WaveformData."""
    waveform = WaveformData(
        voltages=[0.0, 3.3, 0.0],
        sample_rate=1e6,
        start_time=-0.001,
    )
    output_file = tmp_path / "test.json"

    save_waveform_json(waveform, str(output_file))
    loaded = load_waveform_json(str(output_file))

    assert loaded.voltages == waveform.voltages
    assert loaded.sample_rate == waveform.sample_rate
    assert loaded.start_time == waveform.start_time


def test_save_waveform_csv(tmp_path: Path) -> None:
    """Verify CSV file is created with correct header and data."""
    waveform = WaveformData(
        voltages=[0.0, 3.3, 0.0],
        sample_rate=1e6,
        start_time=0.0,
    )
    output_file = tmp_path / "test.csv"

    save_waveform_csv(waveform, str(output_file))

    assert output_file.exists()
    content = output_file.read_text()
    lines = content.strip().split("\n")

    assert lines[0] == "time_s,voltage_v"
    assert lines[1] == "0,0"
    assert lines[2] == "1e-06,3.3"
    assert lines[3] == "2e-06,0"


def test_waveform_get_times() -> None:
    """Verify time reconstruction from sample_rate and start_time."""
    waveform = WaveformData(
        voltages=[0.0, 1.0, 2.0],
        sample_rate=1e6,
        start_time=-1e-6,
    )

    times = waveform.get_times()

    assert len(times) == 3
    assert times[0] == -1e-6
    assert times[1] == 0.0
    assert times[2] == 1e-6
