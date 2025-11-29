"""Waveform data handling for ShutterScope."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt

from shutterscope.oscilloscope import WaveformData

if TYPE_CHECKING:
    from shutterscope.analysis import PulseMetrics, ThreePointMetrics

# Current JSON schema version
WAVEFORM_JSON_VERSION = 1


def save_waveform_json(
    data: WaveformData, filename: str, metrics: PulseMetrics | None = None
) -> None:
    """Save waveform data to a JSON file.

    Args:
        data: WaveformData to save
        filename: Path to the output JSON file
        metrics: Optional pulse metrics to include in the file
    """
    output: dict[str, object] = {
        "version": WAVEFORM_JSON_VERSION,
        "capture_time": datetime.now(UTC).isoformat(),
        "sample_rate_hz": data.sample_rate,
        "start_time_s": data.start_time,
        "samples": [round(v, 6) for v in data.voltages],
    }

    if metrics is not None:
        output["shutter_speed_s"] = metrics.pulse_width_s
        output["shutter_speed_fraction"] = metrics.shutter_speed_fraction

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
    ax.set_title("Single-Point Shutter Measurement")
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color="k", linewidth=0.5)
    ax.axvline(x=0, color="r", linewidth=0.5, linestyle="--", label="Trigger")
    ax.legend()

    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)


def save_three_point_plot(
    waveforms: dict[int, WaveformData],
    filename: str,
    channel_labels: dict[int, str] | None = None,
) -> None:
    """Save a plot of three-point waveform data to an image file.

    Args:
        waveforms: Dictionary of channel -> WaveformData
        filename: Path to the output image file (e.g., .png)
        channel_labels: Optional labels for each channel (default: First/Center/Last)
    """
    if channel_labels is None:
        channel_labels = {1: "First", 2: "Center", 3: "Last"}

    # Define colors to match Rigol DS1000Z channel colors (darkened for visibility)
    colors = {1: "#D4AA00", 2: "#00CCCC", 3: "#CC00CC"}  # Dark Yellow, Cyan, Magenta

    fig, ax = plt.subplots(figsize=(12, 5))

    for channel, waveform in sorted(waveforms.items()):
        times_ms = [t * 1000 for t in waveform.get_times()]
        label = channel_labels.get(channel, f"Channel {channel}")
        color = colors.get(channel)
        ax.plot(times_ms, waveform.voltages, linewidth=0.8, label=label, color=color)

    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Voltage (V)")
    ax.set_title("Three-Point Shutter Measurement")
    ax.grid(True, alpha=0.3)
    ax.axhline(y=0, color="k", linewidth=0.5)
    ax.axvline(x=0, color="r", linewidth=0.5, linestyle="--", label="Trigger")
    ax.legend(loc="upper right")

    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    plt.close(fig)


def save_three_point_json(
    waveforms: dict[int, WaveformData],
    filename: str,
    metrics: ThreePointMetrics | None = None,
) -> None:
    """Save three-point waveform data to a JSON file.

    Args:
        waveforms: Dictionary of channel -> WaveformData
        filename: Path to the output JSON file
        metrics: Optional three-point metrics to include in the file
    """
    output: dict[str, object] = {
        "version": WAVEFORM_JSON_VERSION,
        "mode": "three_point",
        "capture_time": datetime.now(UTC).isoformat(),
        "channels": {},
    }

    # Add each channel's waveform data
    channel_labels = {1: "first", 2: "center", 3: "last"}
    channels_data: dict[str, dict[str, object]] = {}
    for channel, waveform in waveforms.items():
        channels_data[str(channel)] = {
            "label": channel_labels.get(channel, f"channel_{channel}"),
            "sample_rate_hz": waveform.sample_rate,
            "start_time_s": waveform.start_time,
            "samples": [round(v, 6) for v in waveform.voltages],
        }
    output["channels"] = channels_data

    # Add measurements if available
    if metrics is not None:
        output["orientation"] = metrics.orientation
        output["measurements"] = {
            "first": {
                "pulse_width_s": metrics.first.pulse_width_s,
                "shutter_speed_fraction": metrics.first.shutter_speed_fraction,
            },
            "center": {
                "pulse_width_s": metrics.center.pulse_width_s,
                "shutter_speed_fraction": metrics.center.shutter_speed_fraction,
            },
            "last": {
                "pulse_width_s": metrics.last.pulse_width_s,
                "shutter_speed_fraction": metrics.last.shutter_speed_fraction,
            },
            "first_to_center_delay_s": metrics.first_to_center_delay_s,
            "center_to_last_delay_s": metrics.center_to_last_delay_s,
            "shutter_travel_time_s": metrics.shutter_travel_time_s,
            "shutter_velocity_m_per_s": metrics.shutter_velocity_m_per_s,
            "timing_uniformity": metrics.timing_uniformity,
        }

    with open(filename, "w") as f:
        json.dump(output, f)
