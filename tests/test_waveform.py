"""Tests for waveform data handling."""

from pathlib import Path

from shutterscope.oscilloscope import WaveformData
from shutterscope.waveform import save_waveform


def test_save_waveform_creates_csv(tmp_path: Path) -> None:
    """Verify CSV file is created with correct header and data."""
    waveform = WaveformData(
        times=[0.0, 1e-6, 2e-6],
        voltages=[0.0, 3.3, 0.0],
        sample_rate=1e6,
    )
    output_file = tmp_path / "test.csv"

    save_waveform(waveform, str(output_file))

    assert output_file.exists()
    content = output_file.read_text()
    lines = content.strip().split("\n")

    assert lines[0] == "time_s,voltage_v"
    assert lines[1] == "0.0,0.0"
    assert lines[2] == "1e-06,3.3"
    assert lines[3] == "2e-06,0.0"


def test_save_waveform_empty_data(tmp_path: Path) -> None:
    """Handle empty waveform data."""
    waveform = WaveformData(times=[], voltages=[], sample_rate=0.0)
    output_file = tmp_path / "empty.csv"

    save_waveform(waveform, str(output_file))

    assert output_file.exists()
    content = output_file.read_text()
    assert content == "time_s,voltage_v\n"
