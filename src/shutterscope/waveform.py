"""Waveform data handling for ShutterScope."""

import json
from datetime import UTC, datetime

import matplotlib.pyplot as plt

from shutterscope.oscilloscope import WaveformData

# Current JSON schema version
WAVEFORM_JSON_VERSION = 1


def save_waveform_json(data: WaveformData, filename: str) -> None:
    """Save waveform data to a JSON file.

    Args:
        data: WaveformData to save
        filename: Path to the output JSON file
    """
    output = {
        "version": WAVEFORM_JSON_VERSION,
        "capture_time": datetime.now(UTC).isoformat(),
        "sample_rate_hz": data.sample_rate,
        "start_time_s": data.start_time,
        "samples": [round(v, 6) for v in data.voltages],
    }
    with open(filename, "w") as f:
        json.dump(output, f)


def load_waveform_json(filename: str) -> WaveformData:
    """Load waveform data from a JSON file.

    Args:
        filename: Path to the input JSON file

    Returns:
        WaveformData reconstructed from the file
    """
    with open(filename) as f:
        data = json.load(f)

    if data.get("version") != WAVEFORM_JSON_VERSION:
        raise ValueError(f"Unsupported waveform file version: {data.get('version')}")

    return WaveformData(
        voltages=data["samples"],
        sample_rate=data["sample_rate_hz"],
        start_time=data["start_time_s"],
    )


def save_waveform_csv(data: WaveformData, filename: str) -> None:
    """Save waveform data to a CSV file.

    Args:
        data: WaveformData to save
        filename: Path to the output CSV file
    """
    times = data.get_times()
    with open(filename, "w") as f:
        f.write("time_s,voltage_v\n")
        for t, v in zip(times, data.voltages, strict=True):
            f.write(f"{t:.9g},{v:.6g}\n")


def save_waveform_plot(data: WaveformData, filename: str) -> None:
    """Save a plot of the waveform data to an image file.

    Args:
        data: WaveformData to plot
        filename: Path to the output image file (e.g., .png)
    """
    # Convert times to milliseconds for readability
    times_ms = [t * 1000 for t in data.get_times()]

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(times_ms, data.voltages, linewidth=0.5)
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title("Captured Waveform")
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color="k", linewidth=0.5)
    ax.axvline(x=0, color="r", linewidth=0.5, linestyle="--", label="Trigger")
    ax.legend()

    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)
