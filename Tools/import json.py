import json
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from datetime import timedelta
from collections import defaultdict
import tkinter as tk
from tkinter import filedialog

def ms_to_hms(x, pos):
    """
    Convert milliseconds to HH:MM:SS for axis formatting.
    Matplotlib will call this function for each tick label.
    """
    td = timedelta(milliseconds=x)
    hours, remainder = divmod(td.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

def plot_spline_positions_custom_laps_relative_to_p1(data, p1_index=1):
    """
    1) Detects laps ourselves (ignoring the 'laps' field).
    2) Uses Car p1_index as reference, plotting (CarX - CarP1).
    """
    # ---------------------------------------------------
    # Group data by carIndex
    # ---------------------------------------------------
    cars_data = defaultdict(list)
    for entry in data:
        session_time = entry.get("sessionTime", 0.0)
        car_index = entry.get("carIndex", None)
        spline_position = entry.get("splinePosition", 0.0)
        # We ignore the entry's "laps" field in this approach

        if car_index is not None:
            cars_data[car_index].append({
                "sessionTime": session_time,
                "splinePosition": spline_position
            })

    # ---------------------------------------------------
    # For each car, sort by time and detect laps ourselves
    # ---------------------------------------------------
    processed_data = defaultdict(list)

    for car_idx, entries in cars_data.items():
        # Sort by time
        entries.sort(key=lambda x: x["sessionTime"])

        lap_count = 0
        last_spline = None

        # Decide if we skip the first crossing for cars starting near 0.9
        skip_first_crossing = False
        if entries and entries[0]["splinePosition"] >= 0.9:
            skip_first_crossing = True

        for i, e in enumerate(entries):
            current_spline = e["splinePosition"]

            if i > 0 and last_spline is not None:
                # Detect crossing from >=0.9 down to <=0.1
                if last_spline >= 0.9 and current_spline <= 0.1:
                    if skip_first_crossing:
                        # Ignore this crossing once
                        skip_first_crossing = False
                    else:
                        # Increment our lap count
                        lap_count += 1

            total_position = lap_count + current_spline

            processed_data[car_idx].append({
                "sessionTime": e["sessionTime"],
                "totalPosition": total_position
            })

            last_spline = current_spline

    # ---------------------------------------------------
    # Now plot relative to Car p1_index
    # ---------------------------------------------------
    if p1_index not in processed_data:
        print(f"No data found for carIndex={p1_index}. Check your data or p1_index.")
        return

    p1_entries = processed_data[p1_index]
    # We assume each array for each car has the same length & matching times
    # If they differ, you'd need to do interpolation or matching by time.

    # Times for P1
    p1_times = [pt["sessionTime"] for pt in p1_entries]
    p1_positions = [pt["totalPosition"] for pt in p1_entries]

    plt.figure(figsize=(10, 6))

    # Plot P1 as a (roughly) horizontal line at 0.0
    # (He won't be exactly at the "top," but this is your reference.)
    plt.plot(
        p1_times,
        [0.0]*len(p1_times),
        label=f"Car {p1_index} (Reference)",
        linewidth=2
    )

    # Plot the rest, offset by P1
    for car_idx, entries in processed_data.items():
        if car_idx == p1_index:
            continue  # Already plotted P1

        # We assume same number of points & same ordering:
        times = [e["sessionTime"] for e in entries]
        positions = [e["totalPosition"] for e in entries]
        
        # Calculate offset = this car - P1
        relative_positions = [
            positions[i] - p1_positions[i] for i in range(len(positions))
        ]

        plt.plot(times, relative_positions, label=f"Car {car_idx}")

    # Format the x-axis to display HH:MM:SS
    ax = plt.gca()
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(ms_to_hms))

    plt.xlabel("Session Time (HH:MM:SS)")
    plt.ylabel(f"Position Relative to Car {p1_index} (Lap + Spline)")
    plt.title(f"Custom Lap Detection: Relative to Car {p1_index}")
    plt.legend()
    plt.tight_layout()
    plt.show()

def main():
    # ---------------------------------------------------
    # Use a file dialog instead of manual input
    # ---------------------------------------------------
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        title="Select JSON File",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
    )
    if not file_path:
        print("No file selected. Exiting.")
        return

    # ---------------------------------------------------
    # Load the JSON data
    # ---------------------------------------------------
    with open(file_path, 'r') as f:
        data = json.load(f)

    # ---------------------------------------------------
    # Choose which car index is "P1"
    # ---------------------------------------------------
    p1_index = 1  # change this if your "P1" is actually carIndex=0 or another index

    # ---------------------------------------------------
    # Plot using our custom logic, relative to P1
    # ---------------------------------------------------
    plot_spline_positions_custom_laps_relative_to_p1(data, p1_index=p1_index)

if __name__ == "__main__":
    main()
