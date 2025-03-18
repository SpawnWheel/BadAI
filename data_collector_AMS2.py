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

# Pit mode constants
PIT_MODE_NONE = 0
PIT_MODE_DRIVING_INTO_PITS = 1
PIT_MODE_IN_PIT = 2
PIT_MODE_DRIVING_OUT_OF_PITS = 3
PIT_MODE_IN_GARAGE = 4


class DataCollector(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.shared_memory_file = "$pcars2$"
        self.memory_size = ctypes.sizeof(SharedMemory)
        self.output_file = None
        self.running = False
        self.file_handle = None
        self.race_started = False
        self.race_completed = False
        self.last_leaderboard_time = 0
        self.previous_positions = {}
        self.last_overtake_update = 0
        self.race_start_system_time = None
        self.previous_race_state = None
        self.track_name = None
        self.session_type = None
        self.previous_session_type = None  # Track previous session type for file change
        self.driver_name_map = {}  # Basic name mapping
        self.qualifying_positions_output = False  # Track if qualifying positions have been output

        # Race ending tracking
        self.final_lap_announced = False  # Flag for "Leader is on the Final Lap"
        self.race_winner_announced = False  # Flag for "CHECKERED FLAG" message
        self.finished_drivers = set()  # Set of drivers who have finished
        self.previous_laps = {}  # Track previous laps to detect finish line crosses
        self.timer_ended = False  # Flag for when the timer reaches 0

        # Accident detection variables - USING METERS PER SECOND
        self.cars_in_accident = {}  # Dictionary to track cars in accident state
        self.previous_speeds = {}  # Dictionary to track previous speeds
        self.cars_ready_for_monitoring = set()  # Cars that have reached normal racing speed
        self.speed_offset = 8  # The index offset to get a car's speed from mSpeeds

        # Thresholds in METERS PER SECOND (m/s)
        self.accident_speed_threshold = 5.56  # 20 km/h converted to m/s (20 ÷ 3.6)
        self.accident_recovery_threshold = 19.44  # 70 km/h converted to m/s (70 ÷ 3.6)
        self.race_start_immunity = 10.0  # seconds to ignore accidents after race start
        self.cars_in_pits = set()  # Set to track cars currently in the pits

    def update_accident_settings(self, speed_threshold=None, time_threshold=None, proximity_time=None):
        """Update accident detection thresholds if provided."""
        if speed_threshold is not None:
            # Convert km/h to m/s
            self.accident_speed_threshold = speed_threshold / 3.6

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

    def setup_output_file(self, session_name=None):
        """Sets up a new output file for logging race data."""
        try:
            directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Race Data")
            os.makedirs(directory, exist_ok=True)

            # Create file name with current time and optional session name
            start_time = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            if session_name:
                file_name = f"{start_time}_{session_name}.txt"
            else:
                file_name = f"{start_time}.txt"

            self.output_file = os.path.join(directory, file_name)

            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(f"Race data collection started at: {start_time}\n\n")
                if session_name:
                    f.write(f"Session type: {session_name}\n\n")

            self.output_signal.emit(f"Output file setup complete: {self.output_file}")
        except Exception as e:
            self.output_signal.emit(f"Error setting up output file: {e}")

    def log_event(self, event):
        """Logs an event to the output file and emits it as a signal."""
        try:
            timestamp = self.format_time(
                time.time() - self.race_start_system_time if self.race_start_system_time else 0)
            formatted_event = f"{timestamp} - {event}"
            self.output_signal.emit(formatted_event)

            # Only write to file if one is open
            if self.output_file:
                try:
                    with open(self.output_file, 'a', encoding='utf-8') as f:
                        f.write(formatted_event + "\n")
                except Exception as e:
                    self.output_signal.emit(f"Error writing to log file: {e}")
        except Exception as e:
            self.output_signal.emit(f"Error logging event: {e}")

    def get_car_speed(self, data, car_index):
        """
        Get the speed of a car using the correct index offset.
        Returns speed in meters per second (m/s).
        """
        try:
            if hasattr(data, 'mSpeeds') and car_index + self.speed_offset < len(data.mSpeeds):
                return data.mSpeeds[car_index + self.speed_offset]
            return 0
        except Exception:
            return 0

    def process_participant_data(self, data):
        """Processes the data for each participant with improved accident detection."""
        # Check if session has changed - must happen first
        self.check_session_change(data)

        # Update track info (minimally)
        if self.track_name is None:
            raw_track = data.mTrackLocation.decode('utf-8').strip('\x00')
            if raw_track:
                self.track_name = raw_track
                self.output_signal.emit(f"Track detected: {self.track_name}")

        # Race state transitions
        if self.previous_race_state != data.mRaceState:
            if data.mRaceState == RACESTATE_NOT_STARTED:
                self.race_started = False
                self.race_completed = False
                self.race_start_system_time = None
                self.previous_positions = {}
                self.last_overtake_update = 0
                self.last_leaderboard_time = 0
                self.qualifying_positions_output = False
                self.cars_in_accident = {}  # Reset accident tracking
                self.cars_in_pits = set()  # Reset pit tracking
                self.cars_ready_for_monitoring = set()  # Reset monitoring state

                # Reset race ending flags
                self.final_lap_announced = False
                self.race_winner_announced = False
                self.finished_drivers.clear()
                self.timer_ended = False
            elif data.mRaceState == RACESTATE_RACING and self.previous_race_state != RACESTATE_RACING:
                # KEEP: Race start event
                self.log_event("Race has started!")
                self.race_started = True
                self.race_start_system_time = time.time()
                # Output qualifying positions at race start if not already done
                if not self.qualifying_positions_output:
                    self.output_leaderboard(data, 0, label="Qualifying positions")
                    self.qualifying_positions_output = True
            self.previous_race_state = data.mRaceState

        # Calculate session time
        if self.race_start_system_time is not None:
            session_time_elapsed = time.time() - self.race_start_system_time
        else:
            session_time_elapsed = 0

        # Check for race timer ending
        if self.race_started and not self.final_lap_announced and not self.race_completed:
            # Check if timer has ended
            if 0 <= data.mEventTimeRemaining < 0.5 and not self.timer_ended:
                self.timer_ended = True
                self.log_event("The Leader is on the Final Lap")
                self.final_lap_announced = True
            # Alternative check: chequered flag
            elif data.mHighestFlagColour == 11:  # FLAG_COLOUR_CHEQUERED = 11
                if not self.final_lap_announced:
                    self.log_event("The Leader is on the Final Lap")
                    self.final_lap_announced = True
                    self.timer_ended = True

        # KEEP: Qualifying positions before race start
        if not self.race_started and not self.qualifying_positions_output:
            if data.mNumParticipants > 0:
                self.output_leaderboard(data, session_time_elapsed, label="Qualifying positions")
                self.qualifying_positions_output = True

        if data.mRaceState == RACESTATE_RACING:
            if not self.race_started:
                self.race_start_system_time = time.time()
                session_time_elapsed = 0
                self.race_started = True
                self.last_leaderboard_time = session_time_elapsed
            else:
                session_time_elapsed = time.time() - self.race_start_system_time

        # KEEP: Regular leaderboard updates
        if not self.race_started:
            if session_time_elapsed - self.last_leaderboard_time >= 60:
                self.output_leaderboard(data, session_time_elapsed, label="Qualifying positions")
                self.last_leaderboard_time = session_time_elapsed
        elif self.race_started and not self.race_completed:
            if session_time_elapsed - self.last_leaderboard_time >= 4 * 60:
                self.output_leaderboard(data, session_time_elapsed)
                self.last_leaderboard_time = session_time_elapsed

        if self.race_started and data.mRaceState == RACESTATE_FINISHED and not self.race_completed:
            self.race_completed = True
            # If race state is directly finished, make sure we report the winner if we haven't already
            if not self.race_winner_announced:
                # Find the leader
                leader_index = None
                leader_name = "The Leader"
                for i in range(data.mNumParticipants):
                    if i < len(data.mParticipantInfo) and data.mParticipantInfo[i].mIsActive:
                        if data.mParticipantInfo[i].mRacePosition == 1:
                            leader_index = i
                            try:
                                leader_name = data.mParticipantInfo[i].mName.decode('utf-8').strip('\x00')
                                if not leader_name:
                                    leader_name = f"Car {i}"
                            except:
                                leader_name = f"Car {i}"
                            break

                self.log_event(f"CHECKERED FLAG: {leader_name} has won the race!")
                self.race_winner_announced = True

        current_positions = {}
        position_to_name = {}

        # Process participant data for accident detection and overtake detection
        for i in range(data.mNumParticipants):
            # Skip out of bounds indices
            if i >= len(data.mParticipantInfo):
                continue

            participant_data = data.mParticipantInfo[i]
            if not participant_data.mIsActive:
                continue

            # Get name directly from participant data
            try:
                driver_name = participant_data.mName.decode('utf-8').strip('\x00')
                if not driver_name:
                    driver_name = f"Car {i}"
            except:
                driver_name = f"Car {i}"

            # Update driver name map for backward compatibility
            if driver_name != f"Car {i}":
                self.driver_name_map[i] = driver_name

            # Track current positions for overtake detection
            current_positions[i] = participant_data.mRacePosition
            position_to_name[participant_data.mRacePosition] = driver_name

            # Get car speed using correct offset formula
            current_speed = self.get_car_speed(data, i)

            # Store the current speed for future reference
            if i not in self.previous_speeds:
                self.previous_speeds[i] = current_speed

            # Check if car is in pits
            current_pit_mode = PIT_MODE_NONE
            if i < len(data.mPitModes):
                current_pit_mode = data.mPitModes[i]

            # Update pit status
            if current_pit_mode in [PIT_MODE_DRIVING_INTO_PITS, PIT_MODE_IN_PIT, PIT_MODE_IN_GARAGE]:
                self.cars_in_pits.add(i)
                # Remove from ready for monitoring if they enter pits
                if i in self.cars_ready_for_monitoring:
                    self.cars_ready_for_monitoring.remove(i)
            else:
                if i in self.cars_in_pits:
                    self.cars_in_pits.remove(i)

            # ACCIDENT DETECTION
            # Only process if:
            # 1. Race has started
            # 2. Car is not finished
            # 3. Car is not in pits
            # 4. We're past the immunity period after race start
            if (self.race_started and
                    not self.race_completed and
                    i not in self.finished_drivers and
                    i not in self.cars_in_pits and
                    session_time_elapsed > self.race_start_immunity):

                # First check: is car ready for monitoring (has reached racing speed)?
                if i not in self.cars_ready_for_monitoring:
                    # Car needs to reach recovery threshold speed first
                    if current_speed >= self.accident_recovery_threshold:
                        self.cars_ready_for_monitoring.add(i)

                # Now check for accidents only if car is being monitored
                if i in self.cars_ready_for_monitoring:
                    # Check if speed dropped below threshold
                    if current_speed < self.accident_speed_threshold and i not in self.cars_in_accident:
                        # Report accident
                        self.log_event(f"Accident! {driver_name} is involved in an accident!")

                        # Add to cars in accident dictionary
                        self.cars_in_accident[i] = {
                            'time': session_time_elapsed,
                            'driver': driver_name
                        }

                        # Remove from ready for monitoring - will need to reach recovery speed again
                        self.cars_ready_for_monitoring.remove(i)

                # Check if car has recovered (speed above recovery threshold)
                elif i in self.cars_in_accident and current_speed > self.accident_recovery_threshold:
                    # Car has recovered - add back to monitoring
                    self.cars_ready_for_monitoring.add(i)

                    # Remove from accident tracking
                    del self.cars_in_accident[i]

            # Store current lap for finish line detection
            current_lap = participant_data.mCurrentLap
            previous_lap = getattr(self, 'previous_laps', {}).get(i, 0)

            # Initialize previous_laps if needed
            if not hasattr(self, 'previous_laps'):
                self.previous_laps = {}

            # Race ending detection - check for finish line crossings by lap change
            if self.final_lap_announced and not self.race_completed:
                # Check if this is the leader (position 1)
                is_leader = participant_data.mRacePosition == 1

                # Check if driver's lap incremented (crossed finish line)
                crossed_line = current_lap > previous_lap

                if crossed_line:
                    if is_leader and not self.race_winner_announced:
                        # Leader crossed line after final lap announcement
                        self.race_winner_announced = True
                        self.log_event(f"CHECKERED FLAG: {driver_name} has won the race!")
                        self.finished_drivers.add(i)
                    elif self.race_winner_announced and i not in self.finished_drivers:
                        # Other drivers finishing
                        position = participant_data.mRacePosition
                        self.log_event(f"{driver_name} has finished in position {position}")
                        self.finished_drivers.add(i)

            # Store current lap for next update
            self.previous_laps[i] = current_lap

            # Update the previous speed after all processing
            self.previous_speeds[i] = current_speed

        # KEEP: Detect overtakes
        if session_time_elapsed - self.last_overtake_update >= 1.0 and session_time_elapsed >= 15:
            for driver_index, current_pos in current_positions.items():
                prev_pos = self.previous_positions.get(driver_index)
                if prev_pos is not None and prev_pos != current_pos:
                    # Get overtaking driver's details
                    if driver_index >= len(data.mParticipantInfo):
                        continue

                    # Get overtaker's data directly
                    overtaker_data = data.mParticipantInfo[driver_index]
                    if not overtaker_data.mIsActive:
                        continue

                    try:
                        overtaker_name = overtaker_data.mName.decode('utf-8').strip('\x00')
                        if not overtaker_name:
                            overtaker_name = f"Car {driver_index}"
                    except:
                        overtaker_name = f"Car {driver_index}"

                    if current_pos < prev_pos:  # Gained position
                        for other_index, other_pos in current_positions.items():
                            if other_index != driver_index:
                                other_prev_pos = self.previous_positions.get(other_index)
                                if other_prev_pos is not None and other_prev_pos == current_pos and other_pos == prev_pos:
                                    # Get overtaken driver's data directly
                                    if other_index >= len(data.mParticipantInfo):
                                        continue

                                    other_data = data.mParticipantInfo[other_index]
                                    if not other_data.mIsActive:
                                        continue

                                    try:
                                        other_name = other_data.mName.decode('utf-8').strip('\x00')
                                        if not other_name:
                                            other_name = f"Car {other_index}"
                                    except:
                                        other_name = f"Car {other_index}"

                                    # Calculate lap difference
                                    lap_diff = abs(overtaker_data.mCurrentLap - other_data.mCurrentLap)

                                    # Simple overtake reporting without corners or extra context
                                    if lap_diff > 0:
                                        # Lapping
                                        self.log_event(f"{overtaker_name} laps {other_name} for P{current_pos}")
                                    else:
                                        # Regular overtake
                                        if current_pos == 1:
                                            self.log_event(
                                                f"LEAD CHANGE! {overtaker_name} takes the lead from {other_name}!")
                                        else:
                                            self.log_event(
                                                f"Overtake! {overtaker_name} passes {other_name} for P{current_pos}")
                                    break

            self.previous_positions = current_positions.copy()
            self.last_overtake_update = session_time_elapsed

    def format_time(self, elapsed_seconds):
        """Formats the elapsed time into HH:MM:SS."""
        total_seconds = int(elapsed_seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def check_session_change(self, data):
        """Check if session has changed and create a new file if needed."""
        if data.mSessionState != self.previous_session_type:
            session_names = {
                SESSION_PRACTICE: "Practice",
                SESSION_TEST: "Test",
                SESSION_QUALIFY: "Qualifying",
                SESSION_FORMATION_LAP: "Formation_Lap",
                SESSION_RACE: "Race",
                SESSION_TIME_ATTACK: "Time_Attack"
            }

            # Get session name (for file naming)
            new_session_name = session_names.get(data.mSessionState, "Unknown")
            self.session_type = data.mSessionState

            # If this isn't the initial setup (previous_session_type is not None), create a new file
            if self.previous_session_type is not None:
                self.output_signal.emit(
                    f"Session changed from {session_names.get(self.previous_session_type, 'Unknown')} to {new_session_name}. Creating new output file.")

                # Create new file
                self.setup_output_file(new_session_name)

                # Reset relevant session data
                self.race_started = False
                self.race_completed = False
                self.race_start_system_time = None
                self.previous_positions = {}
                self.last_overtake_update = 0
                self.last_leaderboard_time = 0
                self.qualifying_positions_output = False
                self.cars_in_accident = {}  # Reset accident tracking
                self.cars_in_pits = set()  # Reset pit tracking
                self.cars_ready_for_monitoring = set()  # Reset monitoring state

                # Reset race ending flags
                self.final_lap_announced = False
                self.race_winner_announced = False
                self.finished_drivers.clear()
                self.timer_ended = False

                # Log session change
                self.log_event(f"Session changed to {new_session_name}")

            # Update previous session type
            self.previous_session_type = self.session_type

    def output_leaderboard(self, data, session_time_elapsed, label="Current positions"):
        """Outputs the current leaderboard with minimal information."""
        participants = []

        # Get names directly
        for i in range(data.mNumParticipants):
            participant_data = data.mParticipantInfo[i]

            if not participant_data.mIsActive:
                continue

            # Get name directly
            try:
                driver_name = participant_data.mName.decode('utf-8').strip('\x00')
                if not driver_name or driver_name.strip() == "":
                    driver_name = f"Car {i}"
            except:
                driver_name = f"Car {i}"

            if driver_name == "Safety Car":
                continue

            position = participant_data.mRacePosition
            participants.append((position, driver_name))

        participants.sort()

        # Simple leaderboard format with just positions and names
        leaderboard_str = f"{label}: " + ", ".join(f"(P{pos}) {name}" for pos, name in participants)
        self.log_event(leaderboard_str)

    def run(self):
        """Main loop for reading shared memory and processing data."""
        self.output_signal.emit("Starting data collection...")
        self.running = True
        self.setup_shared_memory()

        # Don't set up output file until we know what session we're in
        data = self.read_shared_memory()
        if data:
            session_names = {
                SESSION_PRACTICE: "Practice",
                SESSION_TEST: "Test",
                SESSION_QUALIFY: "Qualifying",
                SESSION_FORMATION_LAP: "Formation_Lap",
                SESSION_RACE: "Race",
                SESSION_TIME_ATTACK: "Time_Attack"
            }
            session_name = session_names.get(data.mSessionState, "Unknown")
            self.setup_output_file(session_name)
            self.session_type = data.mSessionState
            self.previous_session_type = data.mSessionState  # Initialize both to current session

            # Set track name if available
            if data.mTrackLocation:
                try:
                    self.track_name = data.mTrackLocation.decode('utf-8').strip('\x00')
                except:
                    self.track_name = "Unknown Track"
        else:
            # Fallback in case no data is available
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