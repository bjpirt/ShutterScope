"""Waveform data handling for ShutterScope."""

import matplotlib.pyplot as plt

from shutterscope.oscilloscope import WaveformData


def save_waveform(data: WaveformData, filename: str) -> None:
    """Save waveform data to a CSV file.

    Args:
        data: WaveformData to save
        filename: Path to the output CSV file
    """
    with open(filename, "w") as f:
        f.write("time_s,voltage_v\n")
        for t, v in zip(data.times, data.voltages, strict=True):
            f.write(f"{t:.9g},{v:.6g}\n")


def save_waveform_plot(data: WaveformData, filename: str) -> None:
    """Save a plot of the waveform data to an image file.

    Args:
        data: WaveformData to plot
        filename: Path to the output image file (e.g., .png)
    """
    # Convert times to milliseconds for readability
    times_ms = [t * 1000 for t in data.times]

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
