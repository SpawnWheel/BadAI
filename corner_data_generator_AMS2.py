import threading
import ctypes
import mmap
import os
import json
import time

# Import your AMS2 shared memory structure definition
from shared_memory_struct import SharedMemory

class CornerDataGeneratorAMS2:
    def __init__(self):
        self.shared_memory_file = "$pcars2$"  # The AMS2 shared memory file
        self.memory_size = ctypes.sizeof(SharedMemory)
        self.file_handle = None

        self.track_name = None
        self.player_spline_position = 0.0
        self.corner_data = []
        self.running = False
        self.data_lock = threading.Lock()
        self.thread = None
        
        # Add a flag to track if we're connected to AMS2
        self.is_connected = False

    def start(self):
        """Open shared memory and start the background reading thread."""
        self.running = True
        if not self.setup_shared_memory():
            print("Failed to connect to AMS2. Make sure the game is running.")
            return False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        """Stop the background thread and close shared memory."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join()

        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None

    def setup_shared_memory(self):
        """Open the AMS2 shared memory region for read access."""
        try:
            self.file_handle = mmap.mmap(
                -1, 
                self.memory_size, 
                self.shared_memory_file, 
                access=mmap.ACCESS_READ
            )
            print("Connected to AMS2 shared memory.")
            self.is_connected = True
            return True
        except Exception as e:
            print(f"Error connecting to AMS2: {e}")
            self.is_connected = False
            return False

    def read_shared_memory(self):
        """Reads the shared memory into a new SharedMemory instance."""
        if not self.file_handle:
            return None
        try:
            data = SharedMemory()
            self.file_handle.seek(0)
            ctypes.memmove(
                ctypes.addressof(data),
                self.file_handle.read(self.memory_size),
                self.memory_size
            )
            return data
        except Exception as e:
            print(f"Error reading shared memory: {e}")
            self.is_connected = False
            return None

    def wait_for_track_name(self, timeout=10):
        """Wait for a valid track name to be available, with timeout in seconds."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.track_name and self.track_name != "AMS2_UnknownTrack":
                return True
            time.sleep(0.5)
        return False

    def run(self):
        """Background loop reading the shared memory."""
        consecutive_failures = 0
        while self.running:
            data = self.read_shared_memory()
            if data:
                consecutive_failures = 0
                self.update_track_data(data)
                self.update_player_spline_position(data)
            else:
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    print("Lost connection to AMS2...")
                    self.is_connected = False
                    break
            time.sleep(0.1)

    def update_track_data(self, data):
        """Extracts the track name from mTrackLocation."""
        with self.data_lock:
            try:
                raw_track = data.mTrackLocation
                track_str = raw_track.decode('utf-8').strip('\x00')
                if track_str:
                    if self.track_name != track_str:  # Track name has changed
                        self.track_name = track_str
                        print(f"\nTrack detected: {self.track_name}")
                else:
                    self.track_name = "AMS2_UnknownTrack"
            except Exception as e:
                print(f"Error updating track data: {e}")
                if not self.track_name:
                    self.track_name = "AMS2_UnknownTrack"

    def update_player_spline_position(self, data):
        """Updates the player's spline position."""
        with self.data_lock:
            idx = data.mViewedParticipantIndex
            if (idx is not None and 0 <= idx < data.mNumParticipants):
                p_info = data.mParticipantInfo[idx]
                if p_info.mIsActive and data.mTrackLength > 0:
                    total_distance = (p_info.mCurrentLap * data.mTrackLength) + p_info.mCurrentLapDistance
                    fraction = (total_distance % data.mTrackLength) / data.mTrackLength
                    self.player_spline_position = fraction
                else:
                    self.player_spline_position = 0.0
            else:
                self.player_spline_position = 0.0

    def get_player_spline_position(self):
        with self.data_lock:
            return self.player_spline_position

    def get_track_name(self):
        with self.data_lock:
            return self.track_name

    def add_corner(self, name, start, end):
        """Add a corner definition to our internal list."""
        corner = {
            "name": name,
            "start": start,
            "end": end
        }
        self.corner_data.append(corner)
        print(f"Added corner: {corner}")

    def save_corner_data(self):
        """Save corner data to CornerData/<TrackName>_AMS2.json"""
        track_name = self.get_track_name()
        if not track_name or track_name == "AMS2_UnknownTrack":
            print("ERROR: Cannot save - no valid track name available.")
            return False

        if not self.corner_data:
            print("ERROR: No corner data to save.")
            return False

        try:
            folder_name = "CornerData"
            if not os.path.exists(folder_name):
                os.makedirs(folder_name)

            file_name = f"{track_name}_AMS2.json"
            file_path = os.path.join(folder_name, file_name)

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.corner_data, f, indent=4)

            print(f"\nCorner data successfully saved to {file_path}")
            print(f"Saved {len(self.corner_data)} corners for track: {track_name}")
            return True
        except Exception as e:
            print(f"ERROR saving corner data: {e}")
            return False

def main():
    print("\nCorner Data Generator for AMS2 (Single Participant)")
    print("===================================================\n")
    print("Instructions:")
    print("- Start AMS2 and enter a session so shared memory is populated.")
    print("- Drive around the track (you are the 'viewed participant').")
    print("- When you reach the start of an overtaking location, pause AMS2.")
    print("- Enter 'start' in this script to record the start spline position.")
    print("- Enter a name for that corner or location.")
    print("- Resume driving to the end of the location, pause again, type 'end'.")
    print("- Repeat as needed.")
    print("- 'save' to write out corner data (creates <TrackName>_AMS2.json).")
    print("- 'quit' to exit without saving.\n")

    generator = CornerDataGeneratorAMS2()
    if not generator.start():
        print("Failed to start corner data generator. Exiting.")
        return

    print("\nWaiting for track data...")
    if not generator.wait_for_track_name():
        print("Timeout waiting for track name. Make sure you're in a session.")
        generator.stop()
        return

    track_name = generator.get_track_name()
    if track_name == "AMS2_UnknownTrack":
        print("Could not detect track name. Make sure you're in a session.")
        generator.stop()
        return

    print(f"Ready to record corner data for track: {track_name}\n")

    start_position = None
    corner_name = None

    while True:
        if not generator.is_connected:
            print("Lost connection to AMS2. Please restart the application.")
            break

        cmd = input("Enter command (start/end/save/quit): ").strip().lower()
        
        if cmd == 'start':
            pos = generator.get_player_spline_position()
            if pos is None:
                print("Could not get player's spline position. Try again.")
                continue
            corner_name = input("Enter corner/overtaking location name: ").strip()
            if not corner_name:
                print("Name cannot be empty.")
                continue
            start_position = pos
            print(f"Start position recorded at spline {start_position:.3f}")

        elif cmd == 'end':
            if start_position is None or corner_name is None:
                print("No 'start' recorded yet. Use 'start' first.")
                continue
            pos = generator.get_player_spline_position()
            if pos is None:
                print("Could not get player's spline position. Try again.")
                continue
            end_position = pos
            generator.add_corner(corner_name, start_position, end_position)
            start_position = None
            corner_name = None

        elif cmd == 'save':
            if generator.save_corner_data():
                break
            else:
                print("Would you like to try again? (y/n)")
                if input().lower() != 'y':
                    break

        elif cmd == 'quit':
            print("Exiting without saving.")
            break

        else:
            print("Unknown command. Use 'start', 'end', 'save', or 'quit'.")

    generator.stop()

if __name__ == "__main__":
    main()