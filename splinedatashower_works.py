import json
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from datetime import timedelta
from collections import defaultdict

def ms_to_hms(x, pos):
    """
    Convert milliseconds to HH:MM:SS for axis formatting.
    Matplotlib will call this function for each tick label.
    """
    td = timedelta(milliseconds=x)
    hours, remainder = divmod(td.total_seconds(), 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

def plot_spline_positions_custom_laps(data):
    """
    Uses custom lap detection (ignoring the laps field) and plots:
    myLapCount + splinePosition vs. sessionTime
    for each car.
    """
    # Group data by carIndex
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

    # For each car, sort entries by sessionTime and detect laps
    processed_data = defaultdict(list)
    
    for car_index, entries in cars_data.items():
        # Sort by time
        entries.sort(key=lambda x: x["sessionTime"])
        
        lap_count = 0
        last_spline = None
        
        # Decide if we skip the first crossing 
        # (e.g., if the initial position is ≥ 0.9)
        skip_first_crossing = False
        if entries and entries[0]["splinePosition"] >= 0.9:
            skip_first_crossing = True
        
        for i, e in enumerate(entries):
            current_spline = e["splinePosition"]
            
            if i > 0 and last_spline is not None:
                # Detect crossing from >=0.9 down to <=0.1
                if last_spline >= 0.9 and current_spline <= 0.1:
                    if skip_first_crossing:
                        # Ignore first crossing
                        skip_first_crossing = False
                    else:
                        # Increment lap count
                        lap_count += 1
            
            total_position = lap_count + current_spline
            processed_data[car_index].append({
                "sessionTime": e["sessionTime"],
                "totalPosition": total_position
            })
            
            last_spline = current_spline

    # Now plot each car's data
    plt.figure(figsize=(10, 6))
    
    for car_index, entries in processed_data.items():
        times_ms = [e["sessionTime"] for e in entries]
        positions = [e["totalPosition"] for e in entries]
        plt.plot(times_ms, positions, label=f"Car {car_index}")

    # Format the x-axis to display HH:MM:SS
    ax = plt.gca()
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(ms_to_hms))

    plt.xlabel("Session Time (HH:MM:SS)")
    plt.ylabel("Custom Lap Count + Spline Position")
    plt.title("Spline Position (with Custom Lap Detection) Over Time")
    plt.legend()
    plt.tight_layout()
    plt.show()

def main():
    # Ask for the location of the JSON file
    file_path = input("Enter the path to the JSON file containing the spline data: ")
    
    # Load the JSON data
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    # Plot using our custom lap detection approach
    plot_spline_positions_custom_laps(data)

if __name__ == "__main__":
    main()
