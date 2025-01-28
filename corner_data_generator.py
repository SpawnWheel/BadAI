import threading
import sys
import os
import json
import time
import keyboard  # You'll need to: pip install keyboard

# Import ACCAPI client
from accapi.client import AccClient

class CornerDataGenerator:
    def __init__(self):
        self.client = AccClient()
        self.track_name = None
        self.player_car_index = None
        self.player_spline_position = 0.0
        self.cars = {}
        self.corner_data = []
        self.running = False
        self.data_lock = threading.Lock()

    def start(self):
        self.running = True
        self.setup_client()
        self.start_client()
        # Start the thread to receive data
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def stop(self):
        self.running = False
        self.stop_client()
        if self.thread.is_alive():
            self.thread.join()

    def run(self):
        while self.running:
            time.sleep(0.1)

    def setup_client(self):
        self.client.onTrackDataUpdate.subscribe(self.on_track_data_update)
        self.client.onEntryListCarUpdate.subscribe(self.on_entry_list_car_update)
        self.client.onRealtimeCarUpdate.subscribe(self.on_realtime_car_update)

    def start_client(self):
        self.client.start(
            url="localhost",
            port=9000,
            password="asd",
            commandPassword="",
            displayName="Python Corner Data Generator",
            updateIntervalMs=100
        )

    def stop_client(self):
        if self.client.isAlive:
            self.client.stop()

    def on_track_data_update(self, event):
        track_data = event.content
        with self.data_lock:
            self.track_name = track_data.trackName
        print(f"Track detected: {self.track_name}")

    def on_entry_list_car_update(self, event):
        car = event.content
        with self.data_lock:
            self.cars[car.carIndex] = car

    def on_realtime_car_update(self, event):
        car = event.content
        with self.data_lock:
            if car.carIndex == self.player_car_index:
                self.player_spline_position = car.splinePosition

    def get_player_spline_position(self):
        with self.data_lock:
            return self.player_spline_position

    def get_track_name(self):
        with self.data_lock:
            return self.track_name

    def add_corner(self, name, start, end):
        corner = {
            "name": name,
            "start": start,
            "end": end
        }
        self.corner_data.append(corner)
        print(f"Added corner: {corner}")

    def save_corner_data(self):
        track_name = self.get_track_name()
        if not track_name:
            print("Track name not available. Cannot save corner data.")
            return

        # Get the directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Create path for CornerData folder within script directory
        corner_data_folder = os.path.join(script_dir, "CornerData")
        
        try:
            # Create directory with explicit permissions
            os.makedirs(corner_data_folder, exist_ok=True)
            
            # Create the file path
            corner_file_name = f"{track_name}.json"
            corner_file_path = os.path.join(corner_data_folder, corner_file_name)

            # Save the data
            with open(corner_file_path, 'w') as f:
                json.dump(self.corner_data, f, indent=4)

            print(f"\nCorner data saved to {corner_file_path}")
        except PermissionError as e:
            print(f"Permission error: {e}")
            print("Try running the script as administrator or saving to a different location")
            # Fallback to user's documents folder if script directory is not writable
            documents_path = os.path.expanduser("~/Documents/CornerData")
            try:
                os.makedirs(documents_path, exist_ok=True)
                corner_file_path = os.path.join(documents_path, f"{track_name}.json")
                with open(corner_file_path, 'w') as f:
                    json.dump(self.corner_data, f, indent=4)
                print(f"\nCorner data saved to fallback location: {corner_file_path}")
            except Exception as e:
                print(f"Failed to save to fallback location: {e}")

def main():
    print("\nCorner Data Generator")
    print("=====================\n")
    print("Controls:")
    print("- Press 's' to mark the start of a corner")
    print("- Press 'e' to mark the end of a corner (you will then be prompted for a name)")
    print("- Press 'q' to save and quit")
    print("\nInstructions:")
    print("1. Drive around the track")
    print("2. When at the start of a corner, press 's' (no name required yet)")
    print("3. Continue driving until the end of the corner, then press 'e'")
    print("   - You will be prompted to enter the corner's name.")
    print("4. Repeat for as many corners as you like.")
    print("5. Press 'q' at any time to save and quit.\n")

    generator = CornerDataGenerator()
    generator.start()

    # Wait until the car list is available
    while not generator.cars:
        time.sleep(0.1)

    # Now prompt the user to select their car index
    print("\nAvailable Cars:")
    with generator.data_lock:
        for carIndex, car in generator.cars.items():
            driver_name = "Unknown"
            if car.drivers:
                driver = car.drivers[0]
                driver_name = f"{driver.firstName} {driver.lastName}"
            print(f"Car Index: {carIndex}, Driver: {driver_name}")

    while generator.player_car_index is None:
        car_index_input = input("Enter your Car Index: ").strip()
        try:
            car_index = int(car_index_input)
            with generator.data_lock:
                if car_index in generator.cars:
                    generator.player_car_index = car_index
                    print(f"Player car set to index {generator.player_car_index}")
                else:
                    print("Invalid Car Index. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    print("\nReady to record corner data! Press 's' to start, 'e' to end, 'q' to save and quit.")
    
    start_position = None

    def on_key_press(event):
        nonlocal start_position
        
        if event.name == 's' and not event.event_type == 'up':
            spline_position = generator.get_player_spline_position()
            if spline_position is None:
                print("Unable to retrieve spline position. Please try again.")
                return
            start_position = spline_position
            print(f"Start position recorded at spline {start_position}")
            
        elif event.name == 'e' and not event.event_type == 'up':
            if start_position is None:
                print("No start position recorded. Press 's' first.")
                return
            spline_position = generator.get_player_spline_position()
            if spline_position is None:
                print("Unable to retrieve spline position. Please try again.")
                return
            end_position = spline_position

            # Prompt for name here (after pressing 'e')
            name = input("Enter the corner name: ").strip()
            if not name:
                print("Corner name cannot be empty. Please try again.")
                return

            generator.add_corner(name, start_position, end_position)
            start_position = None  # reset for next corner
            
        elif event.name == 'q' and not event.event_type == 'up':
            generator.save_corner_data()
            generator.stop()
            print("Data saved. Exiting...")
            os._exit(0)

    keyboard.hook(on_key_press)
    
    # Keep the main thread running
    while True:
        time.sleep(0.1)

if __name__ == "__main__":
    main()
