"""CLI entry point for ShutterScope."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from shutterscope.analysis import (
    PulseMeasurementError,
    measure_pulse_width,
    measure_three_point,
)
from shutterscope.oscilloscope import RigolDS1000Z
from shutterscope.waveform import (
    save_three_point_json,
    save_three_point_plot,
    save_waveform_json,
    save_waveform_plot,
)

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


def _capture_single_point(
    scope: RigolDS1000Z, args: argparse.Namespace, timestamp: str
) -> None:
    """Capture and process single-point measurement."""
    print("Triggered! Downloading waveform...")
    waveform = scope.get_waveform(channel=1)

    # Measure shutter speed and trim waveform to pulse region
    try:
        metrics = measure_pulse_width(waveform)
        print(
            f"Shutter speed: {metrics.pulse_width_ms:.2f} ms "
            f"({metrics.shutter_speed_fraction})"
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

    filename = CAPTURES_DIR / f"capture_{timestamp}.json"
    save_waveform_json(waveform, str(filename), metrics)
    print(f"Saved {len(waveform.voltages)} samples to {filename}")

    if args.plot:
        plot_filename = CAPTURES_DIR / f"capture_{timestamp}.png"
        save_waveform_plot(waveform, str(plot_filename))
        print(f"Saved plot to {plot_filename}")


def _capture_three_point(
    scope: RigolDS1000Z, args: argparse.Namespace, timestamp: str
) -> None:
    """Capture and process three-point measurement."""
    print("Triggered! Downloading waveforms...")
    waveforms = scope.get_waveforms([1, 2, 3])

    try:
        metrics = measure_three_point(waveforms, orientation=args.orientation)
        print(f"\nThree-Point Shutter Measurement ({args.orientation}):")
        print(
            f"  First:  {metrics.first.pulse_width_ms:.2f} ms "
            f"({metrics.first.shutter_speed_fraction})"
        )
        print(
            f"  Center: {metrics.center.pulse_width_ms:.2f} ms "
            f"({metrics.center.shutter_speed_fraction})"
        )
        print(
            f"  Last:   {metrics.last.pulse_width_ms:.2f} ms "
            f"({metrics.last.shutter_speed_fraction})"
        )
        print()
        print(f"  Travel Time:      {metrics.shutter_travel_time_ms:.2f} ms")
        print(f"  First→Center:     {metrics.first_to_center_delay_ms:.2f} ms")
        print(f"  Center→Last:      {metrics.center_to_last_delay_ms:.2f} ms")
        print(f"  Uniformity:       {metrics.timing_uniformity:.1f}%")

        # Trim all waveforms to pulse region with margin
        # Use the earliest rising edge and latest falling edge across all channels
        earliest_rise = min(
            metrics.first.rising_edge_time,
            metrics.center.rising_edge_time,
            metrics.last.rising_edge_time,
        )
        latest_fall = max(
            metrics.first.falling_edge_time,
            metrics.center.falling_edge_time,
            metrics.last.falling_edge_time,
        )
        pulse_duration = latest_fall - earliest_rise
        margin = pulse_duration * TRIM_MARGIN_FRACTION
        trim_start = earliest_rise - margin
        trim_end = latest_fall + margin

        waveforms = {
            ch: wf.trim(trim_start, trim_end) for ch, wf in waveforms.items()
        }
    except PulseMeasurementError as e:
        print(f"Warning: Could not measure pulse: {e}")
        metrics = None

    filename = CAPTURES_DIR / f"capture_{timestamp}.json"
    save_three_point_json(waveforms, str(filename), metrics)
    print(f"Saved to {filename}")

    if args.plot:
        plot_filename = CAPTURES_DIR / f"capture_{timestamp}.png"
        save_three_point_plot(waveforms, str(plot_filename))
        print(f"Saved plot to {plot_filename}")


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
    parser.add_argument(
        "--three-point",
        action="store_true",
        help="Use three-point measurement mode (channels 1, 2, 3)",
    )
    parser.add_argument(
        "--orientation",
        choices=["horizontal", "vertical"],
        default="horizontal",
        help="Shutter travel direction (default: horizontal)",
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

    # Determine channels and trigger based on mode
    if args.three_point:
        channels = [1, 2, 3]
        trigger_channel = 3  # Last sensor (falling edge)
        mode_str = f"3-channel mode, {args.orientation}"
    else:
        channels = [1]
        trigger_channel = 1
        mode_str = "single-channel mode"

    capture_count = 0
    try:
        scope.configure_timebase(
            max_duration=MAX_CAPTURE_WINDOW,
            sample_interval=DEFAULT_SAMPLE_INTERVAL,
            channels=channels,
        )
        print(f"Configured oscilloscope ({mode_str})")
        print("Press Ctrl+C to exit\n")

        while True:
            scope.setup_edge_trigger(channel=trigger_channel, level=args.trigger_level)
            print("Waiting for trigger...")

            scope.wait_for_trigger()
            timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

            if args.three_point:
                _capture_three_point(scope, args, timestamp)
            else:
                _capture_single_point(scope, args, timestamp)

            capture_count += 1
            print()

    except KeyboardInterrupt:
        print(f"\nCaptured {capture_count} waveforms")
    finally:
        scope.disconnect()
        print("Disconnected")


if __name__ == "__main__":
    main()
