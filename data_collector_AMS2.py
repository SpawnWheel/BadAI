import ctypes
import mmap
import time
from datetime import datetime
import os
from shared_memory_struct import SharedMemory
from PyQt5.QtCore import QThread, pyqtSignal

# Define race and session state constants
RACESTATE_INVALID = 0
RACESTATE_NOT_STARTED = 1
RACESTATE_RACING = 2
RACESTATE_FINISHED = 3
RACESTATE_DISQUALIFIED = 4
RACESTATE_RETIRED = 5
RACESTATE_DNF = 6

SESSION_INVALID = 0
SESSION_PRACTICE = 1
SESSION_TEST = 2
SESSION_QUALIFY = 3
SESSION_FORMATION_LAP = 4
SESSION_RACE = 5
SESSION_TIME_ATTACK = 6

# Game state constants
GAME_EXITED = 0
GAME_FRONT_END = 1
GAME_INGAME_PLAYING = 2
GAME_INGAME_PAUSED = 3
GAME_INGAME_INMENU_TIME_TICKING = 4
GAME_INGAME_RESTARTING = 5
GAME_INGAME_REPLAY = 6
GAME_FRONT_END_REPLAY = 7


class DataCollector(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.shared_memory_file = "$pcars2$"
        self.memory_size = ctypes.sizeof(SharedMemory)
        self.output_file = None
        self.previous_distances = {}
        self.previous_times = {}
        self.accident_logged = {}
        self.last_pit_latch = {}
        self.running = False
        self.file_handle = None
        self.race_started = False
        self.race_completed = False
        self.last_leaderboard_time = 0
        self.previous_positions = {}
        self.last_overtake_update = 0
        self.finished_drivers = set()
        self.previous_finish_status = {}
        self.initial_event_time_remaining = None
        self.race_start_system_time = None
        self.previous_race_state = None  # To detect race state changes
        self.overtake_buffer = {}  # Store recent position changes
        self.overtake_update_interval = 1.0  # Update interval in seconds

    def setup_shared_memory(self):
        """Sets up access to the shared memory file."""
        try:
            self.file_handle = mmap.mmap(-1, self.memory_size, self.shared_memory_file, access=mmap.ACCESS_READ)
            self.output_signal.emit("Shared memory setup complete.")
        except Exception as e:
            self.output_signal.emit(f"Error setting up shared memory: {e}")

    def read_shared_memory(self):
        """Reads data from shared memory."""
        try:
            data = SharedMemory()
            self.file_handle.seek(0)
            ctypes.memmove(ctypes.addressof(data), self.file_handle.read(ctypes.sizeof(data)), ctypes.sizeof(data))
            return data
        except Exception as e:
            self.output_signal.emit(f"Error reading shared memory: {e}")
            return None

    def setup_output_file(self):
        """Sets up the output file for logging race data."""
        try:
            directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Race Data")
            os.makedirs(directory, exist_ok=True)
            start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            self.output_file = os.path.join(directory, f"{start_time}.txt")
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(f"Race data collection started at: {start_time}\n\n")
            self.output_signal.emit(f"Output file setup complete: {self.output_file}")
        except Exception as e:
            self.output_signal.emit(f"Error setting up output file: {e}")

    def calculate_speed(self, current_time, total_distance, participant_index):
        """Calculates the speed in km/h of a participant."""
        prev_time = self.previous_times.get(participant_index)
        prev_distance = self.previous_distances.get(participant_index)

        if prev_time is not None and prev_distance is not None:
            time_diff = current_time - prev_time
            distance_diff = total_distance - prev_distance

            if time_diff > 0 and distance_diff >= 0:
                speed_kph = (distance_diff / time_diff) * 3.6  # Convert m/s to km/h

                if 0 <= speed_kph <= 400:  # Filter unrealistic speeds
                    return speed_kph
        return None

    def log_event(self, event, pit_mode=None):
        """Logs an event to the output file and emits it as a signal."""
        try:
            if pit_mode is not None:
                event += f" (Pit Mode: {pit_mode})"
            self.output_signal.emit(f"Logging event: {event}")
            with open(self.output_file, 'a', encoding='utf-8') as f:
                f.write(event + "\n")
        except Exception as e:
            self.output_signal.emit(f"Error logging event: {e}")

    def output_leaderboard(self, data, session_time_elapsed, label="Current positions"):
        """Outputs the current leaderboard."""
        participants = []
        for i in range(data.mNumParticipants):
            participant_data = data.mParticipantInfo[i]
            participant_name = participant_data.mName.decode('utf-8').strip('\x00')

            if participant_data.mIsActive and participant_name != "Safety Car":
                position = participant_data.mRacePosition
                participants.append((position, participant_name))
        # Sort participants by position
        participants.sort()
        # Build the leaderboard string
        leaderboard_str = f"{label}: "
        for position, name in participants:
            leaderboard_str += f"(P{position}) {name}, "
        leaderboard_str = leaderboard_str.rstrip(', ')  # Remove trailing comma and space

        event = f"{self.format_time(session_time_elapsed)} - {leaderboard_str}"
        self.log_event(event)

    def process_participant_data(self, data):
        """Processes the data for each participant."""
        # Check for race state changes to reset variables
        if self.previous_race_state != data.mRaceState:
            if data.mRaceState == RACESTATE_NOT_STARTED:
                # Reset variables for a new session
                self.race_started = False
                self.race_completed = False
                self.race_start_system_time = None
                self.finished_drivers = set()
                self.previous_finish_status = {}
                self.previous_positions = {}
                self.last_overtake_update = 0
                self.accident_logged = {}
                self.last_leaderboard_time = 0
            self.previous_race_state = data.mRaceState

        current_time = time.time()

        # Initialize initial_event_time_remaining
        if self.initial_event_time_remaining is None and data.mEventTimeRemaining > 0:
            self.initial_event_time_remaining = data.mEventTimeRemaining

        # Calculate session_time_elapsed
        if self.race_start_system_time is not None:
            session_time_elapsed = time.time() - self.race_start_system_time
        else:
            session_time_elapsed = 0

        # Output qualifying positions as soon as data is available
        if not self.race_started and not hasattr(self, 'qualifying_positions_output'):
            if data.mNumParticipants > 0:
                self.output_leaderboard(data, session_time_elapsed, label="Qualifying positions")
                self.qualifying_positions_output = True

        # Check for race start
        if data.mRaceState == RACESTATE_RACING:
            if not self.race_started:
                self.race_start_system_time = time.time()
                session_time_elapsed = 0  # Reset session time at race start
                event = f"{self.format_time(session_time_elapsed)} - Race has started."
                self.log_event(event)
                self.race_started = True
                self.last_leaderboard_time = session_time_elapsed  # Reset the leaderboard timer
            else:
                session_time_elapsed = time.time() - self.race_start_system_time
        else:
            # If the race is not in the RACING state, we don't update session_time_elapsed
            pass

        # Output leaderboard before race starts (every minute)
        if not self.race_started:
            if session_time_elapsed - self.last_leaderboard_time >= 60:
                self.output_leaderboard(data, session_time_elapsed, label="Qualifying positions")
                self.last_leaderboard_time = session_time_elapsed

        # Output leaderboard every four minutes during the race
        elif self.race_started and not self.race_completed:
            if session_time_elapsed - self.last_leaderboard_time >= 4 * 60:
                self.output_leaderboard(data, session_time_elapsed)
                self.last_leaderboard_time = session_time_elapsed

        # Check for race completion
        if self.race_started and data.mRaceState == RACESTATE_FINISHED and not self.race_completed:
            event = f"{self.format_time(session_time_elapsed)} - Race has been completed."
            self.log_event(event)
            self.race_completed = True
            self.race_end_time = session_time_elapsed  # Record the race end time

            # Output final leaderboard
            self.output_leaderboard(data, session_time_elapsed, label="Final positions")

        # Overtake reporting every 1 second, but not during the first 15 seconds
        update_overtakes = session_time_elapsed - self.last_overtake_update >= self.overtake_update_interval and session_time_elapsed >= 15

        # Create current position mapping
        current_positions = {}
        position_to_name = {}
        active_participants = {}

        for i in range(data.mNumParticipants):
            participant_data = data.mParticipantInfo[i]
            participant_name = participant_data.mName.decode('utf-8').strip('\x00')

            if participant_data.mIsActive and participant_name != "Safety Car":
                # Store active participant data
                active_participants[i] = {
                    'name': participant_name,
                    'position': participant_data.mRacePosition,
                    'current_lap': participant_data.mCurrentLap,
                    'lap_distance': participant_data.mCurrentLapDistance
                }

                current_positions[i] = participant_data.mRacePosition
                position_to_name[participant_data.mRacePosition] = participant_name

                # Initialize previous finish status if not already set
                prev_finish_status = self.previous_finish_status.get(i, RACESTATE_INVALID)
                current_finish_status = data.mRaceStates[i]

                # Log driver finishes appropriately
                if current_finish_status != prev_finish_status:
                    self.previous_finish_status[i] = current_finish_status
                    if current_finish_status == RACESTATE_FINISHED and i not in self.finished_drivers:
                        if participant_data.mRacePosition == 1 and not hasattr(self, 'race_winner_reported'):
                            # First place driver has finished
                            finish_event = f"{self.format_time(session_time_elapsed)} - {participant_name} has won the race!"
                            self.log_event(finish_event)
                            self.race_winner_reported = True
                        elif self.race_completed:
                            finish_event = f"{self.format_time(session_time_elapsed)} - {participant_name} has finished the race in position {participant_data.mRacePosition}"
                            self.log_event(finish_event)
                        self.finished_drivers.add(i)

                current_lap = participant_data.mCurrentLap
                current_lap_distance = participant_data.mCurrentLapDistance
                lap_length = data.mTrackLength
                total_distance = current_lap * lap_length + current_lap_distance  # Total distance covered
                speed_kph = self.calculate_speed(session_time_elapsed, total_distance, i)

                # Accident detection only when race is ongoing and game is playing
                if self.race_started and not self.race_completed and data.mGameState == GAME_INGAME_PLAYING:
                    if speed_kph is not None:
                        pit_mode = data.mPitModes[i]

                        # Pit latch logic
                        if pit_mode == 1:  # Entering pits
                            self.last_pit_latch[i] = session_time_elapsed
                        elif pit_mode == 3:  # Exiting pits
                            self.last_pit_latch[i] = None

                        # Initialize previous speed if not exists
                        if not hasattr(self, 'previous_speeds'):
                            self.previous_speeds = {}

                        # Get previous speed
                        prev_speed = self.previous_speeds.get(i, speed_kph)

                        # Calculate speed drop if previous speed exists
                        speed_drop = prev_speed - speed_kph if prev_speed is not None else 0

                        # Record accident if not latched in pits and meets accident criteria
                        if self.last_pit_latch.get(i) is None:
                            # Accident detection conditions:
                            # 1. Speed below 40 km/h and not in first lap
                            # 2. Sudden speed drop (more than 50 km/h)
                            # 3. Not just started the session
                            if ((speed_kph < 40 and current_lap > 1) or (
                                    speed_drop > 50)) and session_time_elapsed >= 3:
                                if not self.accident_logged.get(i, False):
                                    accident_event = f"{self.format_time(session_time_elapsed)} - Possible accident involving: {participant_name} (Speed: {speed_kph:.1f} km/h, Drop: {speed_drop:.1f} km/h)"
                                    self.log_event(accident_event)
                                    self.accident_logged[i] = True
                                    self.last_accident_time = session_time_elapsed  # Track when the accident was logged

                        # Only reset accident logged flag if:
                        # 1. Enough time has passed since the accident (5 seconds)
                        # 2. Speed is back to normal
                        # 3. No sudden speed drops
                        if speed_kph > 70 and speed_drop < 20 and \
                                hasattr(self, 'last_accident_time') and \
                                (session_time_elapsed - self.last_accident_time) > 5:
                            self.accident_logged[i] = False

                        # Update previous speed
                        self.previous_speeds[i] = speed_kph

                # Update previous distance and time
                self.previous_distances[i] = total_distance
                self.previous_times[i] = session_time_elapsed

            else:
                # For inactive participants or safety car, remove from previous positions
                if i in self.previous_positions:
                    del self.previous_positions[i]

        # Detect overtakes with improved logic
        if update_overtakes and self.race_started and not self.race_completed:
            for driver_index, current_pos in current_positions.items():
                prev_pos = self.previous_positions.get(driver_index)

                if prev_pos is not None and prev_pos != current_pos:
                    driver_name = active_participants[driver_index]['name']

                    # Determine if it's a gain or loss in position
                    if current_pos < prev_pos:  # Gained position (lower number is better)
                        # Find who was overtaken
                        for other_index, other_pos in current_positions.items():
                            if other_index != driver_index:
                                other_prev_pos = self.previous_positions.get(other_index)
                                if other_prev_pos is not None:
                                    # Check if other driver moved back as this driver moved forward
                                    if other_prev_pos == current_pos and other_pos == prev_pos:
                                        other_name = active_participants[other_index]['name']

                                        # Additional validation using lap and distance data
                                        driver_data = active_participants[driver_index]
                                        other_data = active_participants[other_index]

                                        # Only log overtake if they're on the same lap or one lap difference
                                        lap_diff = abs(driver_data['current_lap'] - other_data['current_lap'])
                                        if lap_diff <= 1:
                                            overtake_event = f"{self.format_time(session_time_elapsed)} - Overtake! {driver_name} overtook {other_name} for position {current_pos}"
                                            self.log_event(overtake_event)
                                        break

            # Update previous positions
            self.previous_positions = current_positions.copy()

        if update_overtakes and session_time_elapsed >= 15:
            self.last_overtake_update = session_time_elapsed

    def format_time(self, elapsed_seconds):
        """Formats the elapsed time into HH:MM:SS."""
        total_seconds = int(elapsed_seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def run(self):
        """Main loop for reading shared memory and processing data."""
        self.output_signal.emit("Starting data collection...")
        self.running = True
        self.setup_shared_memory()
        self.setup_output_file()

        try:
            while self.running:
                data = self.read_shared_memory()
                if data:
                    self.process_participant_data(data)
                time.sleep(0.2)
        except Exception as e:
            self.output_signal.emit(f"Error in data collection: {e}")
        finally:
            if self.file_handle:
                self.file_handle.close()
            self.output_signal.emit("Data collection stopped.")

    def stop(self):
        """Stops the data collection process."""
        self.running = False


def main():
    collector = DataCollector()
    collector.run()


if __name__ == "__main__":
    main()