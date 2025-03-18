import os
import re
import tkinter as tk
from tkinter import filedialog

from pydub import AudioSegment

# ------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------
MAX_TIMELINE_SECONDS = 24 * 3600  # 24 hours, for example


# ------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------
def parse_hhmmss_from_filename(filename):
    """
    Extracts the 'HHMMSS' portion from a filename like "Commentary_000303.mp3"
    and returns the total number of seconds as an integer.
    """
    # Get the part after the underscore and before the extension
    # Example: "Commentary_000303.mp3" -> "000303"
    basename = os.path.basename(filename)
    match = re.search(r'_(\d{6})\.mp3$', basename)
    if not match:
        return None  # or raise an error if strictly required

    hhmmss_str = match.group(1)  # e.g. "000303"
    # Parse HHMMSS
    hours = int(hhmmss_str[0:2])
    minutes = int(hhmmss_str[2:4])
    seconds = int(hhmmss_str[4:6])
    total_seconds = hours * 3600 + minutes * 60 + seconds
    return total_seconds


def place_on_timeline(file_offsets):
    """
    Given a list of tuples (file_path, offset_in_seconds),
    returns a single AudioSegment with all audio placed accordingly.
    Truncates any audio that extends beyond MAX_TIMELINE_SECONDS.
    """
    # Determine how long the final timeline must be
    # We'll figure out the maximum needed point in time.
    max_needed = 0
    segments_info = []

    for fp, offset_sec in file_offsets:
        audio = AudioSegment.from_mp3(fp)
        audio_duration = len(audio) / 1000.0  # pydub length is in milliseconds
        end_time = offset_sec + audio_duration
        if end_time > max_needed:
            max_needed = end_time

        segments_info.append((audio, offset_sec))

    # If we want to cap to 24 hours (or any limit), do so:
    if max_needed > MAX_TIMELINE_SECONDS:
        max_needed = MAX_TIMELINE_SECONDS

    # Create a silent AudioSegment with enough length in ms
    timeline = AudioSegment.silent(duration=int(max_needed * 1000))

    # Overlay each audio segment
    for audio, offset_sec in segments_info:
        start_ms = int(offset_sec * 1000)
        end_ms = start_ms + len(audio)

        # If the audio extends beyond our max timeline, we truncate
        if end_ms > len(timeline):
            overlap_ms = end_ms - len(timeline)
            if overlap_ms > 0:
                audio = audio[:(len(audio) - overlap_ms)]

        # Overlay the truncated (or full) audio on the timeline
        timeline = timeline.overlay(audio, position=start_ms)

    return timeline


# ------------------------------------------------------
# MAIN SCRIPT
# ------------------------------------------------------
def main():
    root = tk.Tk()
    root.withdraw()  # hide the main tkinter window

    # Ask the user to select multiple MP3 files
    mp3_paths = filedialog.askopenfilenames(
        title="Select MP3 Files (Press CTRL or SHIFT to select multiple)",
        filetypes=[("MP3 Files", "*.mp3")]
    )
    if not mp3_paths:
        print("No files selected. Exiting.")
        return

    # Build a list of (filepath, offset_seconds)
    file_offsets = []
    for mp3_path in mp3_paths:
        offset_sec = parse_hhmmss_from_filename(mp3_path)
        if offset_sec is not None:
            file_offsets.append((mp3_path, offset_sec))
        else:
            print(f"Skipping {mp3_path}: No valid HHMMSS found in filename.")

    # Sort by offset so that the earliest times go first (optional)
    file_offsets.sort(key=lambda x: x[1])

    # Create a single timeline
    timeline = place_on_timeline(file_offsets)

    # Export the result
    output_path = "combined_commentary.mp3"
    timeline.export(output_path, format="mp3")
    print(f"Exported combined timeline to: {output_path}")


if __name__ == "__main__":
    main()
