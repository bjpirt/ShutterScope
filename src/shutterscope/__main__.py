"""CLI entry point for ShutterScope."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from shutterscope.analysis import PulseMeasurementError, measure_pulse_width
from shutterscope.oscilloscope import RigolDS1000Z
from shutterscope.waveform import save_waveform_json, save_waveform_plot

# Default trigger level in volts
DEFAULT_TRIGGER_LEVEL = 0.2
# Default sample interval in seconds (1 microsecond)
DEFAULT_SAMPLE_INTERVAL = 1e-6
# Maximum capture window (1 second covers most mechanical shutters)
MAX_CAPTURE_WINDOW = 1.0
# Margin around pulse when trimming (as fraction of pulse width)
TRIM_MARGIN_FRACTION = 0.1
# Directory for saving captures
CAPTURES_DIR = Path("captures")


def main() -> None:
    """Main entry point for ShutterScope CLI."""
    parser = argparse.ArgumentParser(
        description="Capture waveform data from a Rigol DS1000Z oscilloscope"
    )
    parser.add_argument(
        "address",
        nargs="?",
        help="VISA address (e.g., TCPIP::192.168.1.100::INSTR). "
        "If not provided, auto-discovers via USB.",
    )
    parser.add_argument(
        "--trigger-level",
        type=float,
        default=DEFAULT_TRIGGER_LEVEL,
        help=f"Trigger level in volts (default: {DEFAULT_TRIGGER_LEVEL})",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Save a plot of the waveform to capture.png",
    )
    args = parser.parse_args()

    try:
        if args.address:
            print(f"Connecting to {args.address}...")
            scope = RigolDS1000Z(args.address)
            scope.connect()
        else:
            print("Searching for Rigol DS1000Z oscilloscope...")
            scope = RigolDS1000Z.auto_connect()
    except ConnectionError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print("Connected to oscilloscope")

    # Create captures directory if needed
    CAPTURES_DIR.mkdir(exist_ok=True)

    capture_count = 0
    try:
        scope.configure_timebase(
            max_duration=MAX_CAPTURE_WINDOW,
            sample_interval=DEFAULT_SAMPLE_INTERVAL,
        )
        print("Configured oscilloscope")
        print("Press Ctrl+C to exit\n")

        while True:
            scope.setup_edge_trigger(channel=1, level=args.trigger_level)
            print("Waiting for trigger...")

            scope.wait_for_trigger()
            print("Triggered! Downloading waveform...")
            waveform = scope.get_waveform(channel=1)

            # Measure shutter speed and trim waveform to pulse region
            try:
                metrics = measure_pulse_width(waveform)
                print(
                    f"Shutter speed: {metrics.pulse_width_ms:.2f} ms "
                    f"({metrics.shutter_speed_fraction} s)"
                )
                # Trim to pulse with margin
                margin = metrics.pulse_width_s * TRIM_MARGIN_FRACTION
                waveform = waveform.trim(
                    metrics.rising_edge_time - margin,
                    metrics.falling_edge_time + margin,
                )
            except PulseMeasurementError as e:
                print(f"Warning: Could not measure pulse: {e}")
                metrics = None

            capture_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            filename = CAPTURES_DIR / f"capture_{timestamp}.json"
            save_waveform_json(waveform, str(filename), metrics)
            print(f"Saved {len(waveform.voltages)} samples to {filename}")
            if args.plot:
                plot_filename = CAPTURES_DIR / f"capture_{timestamp}.png"
                save_waveform_plot(waveform, str(plot_filename))
                print(f"Saved plot to {plot_filename}")
            print()

    except KeyboardInterrupt:
        print(f"\nCaptured {capture_count} waveforms")
    finally:
        scope.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    main()
