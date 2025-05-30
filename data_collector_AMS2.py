# data_collector_AMS2.py
import ctypes
import mmap
import time
from datetime import datetime
import os
import json # <-- Added import
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
        self.output_file_stem = None # <-- Added to store base filename timestamp
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
        self.previous_session_type = None
        self.qualifying_positions_output = False

        # --- Participant Map ---
        self.participant_map = {}
        self.participant_map_captured = False
        self.participant_map_saved = False
        # -----------------------

        # Race ending tracking
        self.final_lap_announced = False
        self.race_winner_announced = False
        self.finished_drivers = set()
        self.previous_laps = {}
        self.timer_ended = False

        # Accident detection variables
        self.cars_in_accident = {}
        self.previous_speeds = {}
        self.cars_ready_for_monitoring = set()
        self.speed_offset = 8 # Offset for mSpeeds array

        # Thresholds in METERS PER SECOND (m/s)
        self.accident_speed_threshold = 5.56 # ~20 km/h
        self.accident_recovery_threshold = 19.44 # ~70 km/h
        self.race_start_immunity = 10.0 # seconds
        self.cars_in_pits = set()

    def update_accident_settings(self, speed_threshold=None, time_threshold=None, proximity_time=None):
        if speed_threshold is not None:
            self.accident_speed_threshold = speed_threshold / 3.6

    def setup_shared_memory(self):
        try:
            self.file_handle = mmap.mmap(-1, self.memory_size, self.shared_memory_file, access=mmap.ACCESS_READ)
            self.output_signal.emit("Shared memory setup complete.")
        except Exception as e:
            self.output_signal.emit(f"Error setting up shared memory: {e}")

    def read_shared_memory(self):
        try:
            data = SharedMemory()
            self.file_handle.seek(0)
            ctypes.memmove(ctypes.addressof(data), self.file_handle.read(ctypes.sizeof(data)), ctypes.sizeof(data))
            return data
        except Exception as e:
            self.output_signal.emit(f"Error reading shared memory: {e}")
            return None

    def setup_output_file(self, session_name=None):
        try:
            directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Race Data")
            os.makedirs(directory, exist_ok=True)

            start_time_dt = datetime.now() # Store datetime object
            self.output_file_stem = start_time_dt.strftime("%Y-%m-%d_%H-%M-%S") # <-- Store timestamp stem

            if session_name:
                file_name = f"{self.output_file_stem}_{session_name}.txt"
            else:
                file_name = f"{self.output_file_stem}.txt"

            self.output_file = os.path.join(directory, file_name)

            with open(self.output_file, 'w', encoding='utf-8') as f:
                start_time_str = start_time_dt.strftime("%Y-%m-%d %H:%M:%S") # Format for log
                f.write(f"Race data collection started at: {start_time_str}\n\n")
                if session_name:
                    f.write(f"Session type: {session_name}\n\n")

            self.output_signal.emit(f"Output file setup complete: {self.output_file}")
        except Exception as e:
            self.output_signal.emit(f"Error setting up output file: {e}")
            self.output_file_stem = None # Ensure stem is None if setup fails

    def log_event(self, event):
        try:
            timestamp = self.format_time(
                time.time() - self.race_start_system_time if self.race_start_system_time else 0)
            formatted_event = f"{timestamp} - {event}"
            self.output_signal.emit(formatted_event)

            if self.output_file:
                try:
                    with open(self.output_file, 'a', encoding='utf-8') as f:
                        f.write(formatted_event + "\n")
                except Exception as e:
                    self.output_signal.emit(f"Error writing to log file: {e}")
        except Exception as e:
            self.output_signal.emit(f"Error logging event: {e}")

    def get_car_speed(self, data, car_index):
        try:
            if hasattr(data, 'mSpeeds') and car_index + self.speed_offset < len(data.mSpeeds):
                return data.mSpeeds[car_index + self.speed_offset]
            return 0
        except Exception:
            return 0

    # --- Added method to capture participant map ---
    def capture_participant_map(self, data):
        if self.participant_map_captured:
            return # Already captured

        self.output_signal.emit("Attempting to capture participant starting grid...")
        temp_map = {}
        found_active = False
        for i in range(data.mNumParticipants):
            if i >= len(data.mParticipantInfo): continue
            participant_data = data.mParticipantInfo[i]
            if not participant_data.mIsActive: continue
            found_active = True

            try:
                driver_name = participant_data.mName.decode('utf-8').strip('\x00')
                if not driver_name or driver_name == "Safety Car": continue
            except:
                continue # Skip if name decoding fails

            position = participant_data.mRacePosition
            # Ensure position is valid (greater than 0)
            if position > 0:
                temp_map[driver_name] = position
            else:
                self.output_signal.emit(f"Warning: Invalid starting position ({position}) for {driver_name}. Skipping.")

        if temp_map and found_active:
            self.participant_map = temp_map
            self.participant_map_captured = True
            self.output_signal.emit(f"Participant starting grid captured ({len(self.participant_map)} drivers).")
            # Log the captured map for verification
            # self.log_event(f"Captured Grid: {json.dumps(self.participant_map)}")
        elif not found_active:
             self.output_signal.emit("No active participants found yet for grid capture.")
        else:
             self.output_signal.emit("Failed to capture valid participant grid positions.")
    # --------------------------------------------

    def process_participant_data(self, data):
        self.check_session_change(data)

        if self.track_name is None:
            raw_track = data.mTrackLocation.decode('utf-8').strip('\x00')
            if raw_track:
                self.track_name = raw_track
                self.output_signal.emit(f"Track detected: {self.track_name}")

        if self.previous_race_state != data.mRaceState:
            if data.mRaceState == RACESTATE_NOT_STARTED:
                self.race_started = False
                self.race_completed = False
                self.race_start_system_time = None
                self.previous_positions = {}
                self.last_overtake_update = 0
                self.last_leaderboard_time = 0
                self.qualifying_positions_output = False
                self.cars_in_accident = {}
                self.cars_in_pits = set()
                self.cars_ready_for_monitoring = set()
                self.final_lap_announced = False
                self.race_winner_announced = False
                self.finished_drivers.clear()
                self.timer_ended = False
                # Don't reset participant map capture flag here, allow capture on transition
            elif data.mRaceState == RACESTATE_RACING and self.previous_race_state != RACESTATE_RACING:
                self.log_event("Race has started!")
                self.race_started = True
                self.race_start_system_time = time.time()
                if not self.qualifying_positions_output:
                    self.output_leaderboard(data, 0, label="Starting Grid") # Changed label
                    self.qualifying_positions_output = True
                # --- Attempt to capture map right at race start ---
                if not self.participant_map_captured:
                    self.capture_participant_map(data)
                # ---------------------------------------------------
            self.previous_race_state = data.mRaceState

        # --- Attempt map capture before race starts if not done yet ---
        if not self.participant_map_captured and data.mRaceState == RACESTATE_NOT_STARTED and data.mSessionState in [SESSION_FORMATION_LAP, SESSION_RACE]:
             self.capture_participant_map(data)
        # -------------------------------------------------------------

        if self.race_start_system_time is not None:
            session_time_elapsed = time.time() - self.race_start_system_time
        else:
            session_time_elapsed = 0

        if self.race_started and not self.final_lap_announced and not self.race_completed:
            if 0 <= data.mEventTimeRemaining < 0.5 and not self.timer_ended:
                self.timer_ended = True
                self.log_event("The Leader is on the Final Lap")
                self.final_lap_announced = True
            elif data.mHighestFlagColour == 11: # FLAG_COLOUR_CHEQUERED
                if not self.final_lap_announced:
                    self.log_event("The Leader is on the Final Lap")
                    self.final_lap_announced = True
                    self.timer_ended = True

        if not self.race_started and not self.qualifying_positions_output:
            if data.mNumParticipants > 0 and data.mSessionState == SESSION_QUALIFY: # Only log qualify in Q
                self.output_leaderboard(data, session_time_elapsed, label="Qualifying positions")
                self.qualifying_positions_output = True

        # --- Reset qualy output flag if session changes from Qualify ---
        if self.session_type != SESSION_QUALIFY and self.previous_session_type == SESSION_QUALIFY:
             self.qualifying_positions_output = False
        # --------------------------------------------------------------

        if data.mRaceState == RACESTATE_RACING:
            if not self.race_started: # Should be handled above, but safety check
                self.race_start_system_time = time.time()
                session_time_elapsed = 0
                self.race_started = True
                self.last_leaderboard_time = session_time_elapsed
            else:
                session_time_elapsed = time.time() - self.race_start_system_time

        if not self.race_started: # Qualy leaderboard
            if session_time_elapsed - self.last_leaderboard_time >= 60:
                 if self.session_type == SESSION_QUALIFY:
                    self.output_leaderboard(data, session_time_elapsed, label="Qualifying positions")
                    self.last_leaderboard_time = session_time_elapsed
        elif self.race_started and not self.race_completed: # Race leaderboard
            if session_time_elapsed - self.last_leaderboard_time >= 4 * 60:
                self.output_leaderboard(data, session_time_elapsed)
                self.last_leaderboard_time = session_time_elapsed

        if self.race_started and data.mRaceState == RACESTATE_FINISHED and not self.race_completed:
            self.race_completed = True
            if not self.race_winner_announced:
                leader_index = None
                leader_name = "The Leader"
                for i in range(data.mNumParticipants):
                    if i < len(data.mParticipantInfo) and data.mParticipantInfo[i].mIsActive:
                        if data.mParticipantInfo[i].mRacePosition == 1:
                            leader_index = i
                            try:
                                leader_name = data.mParticipantInfo[i].mName.decode('utf-8').strip('\x00')
                                if not leader_name: leader_name = f"Car {i}"
                            except: leader_name = f"Car {i}"
                            break
                self.log_event(f"CHECKERED FLAG: {leader_name} has won the race!")
                self.race_winner_announced = True

        current_positions = {}
        position_to_name = {}

        for i in range(data.mNumParticipants):
            if i >= len(data.mParticipantInfo): continue
            participant_data = data.mParticipantInfo[i] # <-- participant_data is defined here
            if not participant_data.mIsActive: continue

            try:
                driver_name = participant_data.mName.decode('utf-8').strip('\x00')
                if not driver_name: driver_name = f"Car {i}"
            except: driver_name = f"Car {i}"

            current_pos_val = participant_data.mRacePosition # <-- Store current position
            current_positions[i] = current_pos_val
            position_to_name[current_pos_val] = driver_name
            current_speed = self.get_car_speed(data, i)

            if i not in self.previous_speeds: self.previous_speeds[i] = current_speed

            current_pit_mode = PIT_MODE_NONE
            if i < len(data.mPitModes): current_pit_mode = data.mPitModes[i]

            if current_pit_mode in [PIT_MODE_DRIVING_INTO_PITS, PIT_MODE_IN_PIT, PIT_MODE_IN_GARAGE]:
                self.cars_in_pits.add(i)
                if i in self.cars_ready_for_monitoring: self.cars_ready_for_monitoring.remove(i)
            else:
                if i in self.cars_in_pits: self.cars_in_pits.remove(i)

            # --- Accident Detection Logic ---
            if (self.race_started and
                    not self.race_completed and
                    i not in self.finished_drivers and
                    i not in self.cars_in_pits and
                    session_time_elapsed > self.race_start_immunity):

                # Check if car needs to be monitored (was above recovery speed)
                if i not in self.cars_ready_for_monitoring:
                    if current_speed >= self.accident_recovery_threshold:
                        self.cars_ready_for_monitoring.add(i)

                # If car is being monitored, check for accident speed
                if i in self.cars_ready_for_monitoring:
                    if current_speed < self.accident_speed_threshold and i not in self.cars_in_accident:
                        # --- Accident detected! Log with position ---
                        # We already have current_pos_val from earlier in the loop
                        self.log_event(f"Accident! P{current_pos_val} {driver_name} is involved in an accident!")
                        # --------------------------------------------
                        self.cars_in_accident[i] = {'time': session_time_elapsed, 'driver': driver_name, 'position': current_pos_val} # Store position too
                        self.cars_ready_for_monitoring.remove(i) # Stop monitoring until recovered

                # If car was in an accident, check if it has recovered speed
                elif i in self.cars_in_accident and current_speed > self.accident_recovery_threshold:
                    # Car recovered, add back to monitoring list
                    self.cars_ready_for_monitoring.add(i)
                    # Remove from the active accident list
                    del self.cars_in_accident[i]
            # --- End Accident Detection ---

            current_lap = participant_data.mCurrentLap
            previous_lap = getattr(self, 'previous_laps', {}).get(i, 0)
            if not hasattr(self, 'previous_laps'): self.previous_laps = {}

            if self.final_lap_announced and not self.race_completed:
                is_leader = participant_data.mRacePosition == 1
                crossed_line = current_lap > previous_lap
                if crossed_line:
                    if is_leader and not self.race_winner_announced:
                        self.race_winner_announced = True
                        self.log_event(f"CHECKERED FLAG: {driver_name} has won the race!")
                        self.finished_drivers.add(i)
                    elif self.race_winner_announced and i not in self.finished_drivers:
                        position = participant_data.mRacePosition
                        self.log_event(f"{driver_name} has finished in position {position}")
                        self.finished_drivers.add(i)

            self.previous_laps[i] = current_lap
            self.previous_speeds[i] = current_speed
        # --- End of participant loop ---

        # --- Overtake Detection Logic ---
        if session_time_elapsed - self.last_overtake_update >= 1.0 and session_time_elapsed >= 15:
            for driver_index, current_pos in current_positions.items():
                prev_pos = self.previous_positions.get(driver_index)
                if prev_pos is not None and prev_pos != current_pos:
                    if driver_index >= len(data.mParticipantInfo): continue
                    overtaker_data = data.mParticipantInfo[driver_index]
                    if not overtaker_data.mIsActive: continue
                    try:
                        overtaker_name = overtaker_data.mName.decode('utf-8').strip('\x00')
                        if not overtaker_name: overtaker_name = f"Car {driver_index}"
                    except: overtaker_name = f"Car {driver_index}"

                    if current_pos < prev_pos: # Position improved (lower number is better)
                        # Find the driver who was overtaken
                        overtaken_index = -1
                        for other_index, other_prev_pos in self.previous_positions.items():
                            # Find someone who was previously in the position the overtaker is now in,
                            # and who is now in the position the overtaker was previously in.
                            if other_index != driver_index and other_prev_pos == current_pos and current_positions.get(other_index) == prev_pos:
                                overtaken_index = other_index
                                break

                        if overtaken_index != -1:
                            if overtaken_index >= len(data.mParticipantInfo): continue
                            other_data = data.mParticipantInfo[overtaken_index]
                            if not other_data.mIsActive: continue
                            try:
                                other_name = other_data.mName.decode('utf-8').strip('\x00')
                                if not other_name: other_name = f"Car {overtaken_index}"
                            except: other_name = f"Car {overtaken_index}"

                            lap_diff = abs(overtaker_data.mCurrentLap - other_data.mCurrentLap)
                            if lap_diff > 0:
                                self.log_event(f"{overtaker_name} laps {other_name} for P{current_pos}")
                            else:
                                if current_pos == 1:
                                    self.log_event(f"LEAD CHANGE! {overtaker_name} takes the lead from {other_name}!")
                                else:
                                    self.log_event(f"Overtake! {overtaker_name} passes {other_name} for P{current_pos}")

            self.previous_positions = current_positions.copy()
            self.last_overtake_update = session_time_elapsed
        # --- End Overtake Detection ---

    def format_time(self, elapsed_seconds):
        total_seconds = int(elapsed_seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    def check_session_change(self, data):
        if data.mSessionState != self.previous_session_type:
            session_names = {
                SESSION_PRACTICE: "Practice", SESSION_TEST: "Test", SESSION_QUALIFY: "Qualifying",
                SESSION_FORMATION_LAP: "Formation_Lap", SESSION_RACE: "Race", SESSION_TIME_ATTACK: "Time_Attack"
            }
            new_session_name = session_names.get(data.mSessionState, "Unknown")
            current_session_type = data.mSessionState

            if self.previous_session_type is not None:
                self.output_signal.emit(f"Session changed from {session_names.get(self.previous_session_type, 'Unknown')} to {new_session_name}. Creating new output file.")
                # --- Save map before changing file ---
                self.save_participant_map()
                # ------------------------------------
                self.setup_output_file(new_session_name) # Creates new file with new stem

                # Reset flags for new session
                self.race_started = False
                self.race_completed = False
                self.race_start_system_time = None
                self.previous_positions = {}
                self.last_overtake_update = 0
                self.last_leaderboard_time = 0
                self.qualifying_positions_output = False
                self.cars_in_accident = {}
                self.cars_in_pits = set()
                self.cars_ready_for_monitoring = set()
                self.final_lap_announced = False
                self.race_winner_announced = False
                self.finished_drivers.clear()
                self.timer_ended = False
                # --- Reset participant map capture/saved flags for new session ---
                self.participant_map_captured = False
                self.participant_map_saved = False
                self.participant_map = {}
                # ---------------------------------------------------------------

                self.log_event(f"Session changed to {new_session_name}")

            self.session_type = current_session_type # Update current session type
            self.previous_session_type = self.session_type # Update previous for next check

    def output_leaderboard(self, data, session_time_elapsed, label="Current positions"):
        participants = []
        for i in range(data.mNumParticipants):
            if i >= len(data.mParticipantInfo): continue # Boundary check
            participant_data = data.mParticipantInfo[i]
            if not participant_data.mIsActive: continue
            try:
                driver_name = participant_data.mName.decode('utf-8').strip('\x00')
                if not driver_name or driver_name.strip() == "" or driver_name == "Safety Car": continue
            except: continue
            position = participant_data.mRacePosition
            # Only include valid positions in the leaderboard
            if position > 0:
                participants.append((position, driver_name))
        participants.sort()
        leaderboard_str = f"{label}: " + ", ".join(f"(P{pos}) {name}" for pos, name in participants)
        self.log_event(leaderboard_str)

    # --- Added method to save the map ---
    def save_participant_map(self):
        if not self.participant_map_captured or self.participant_map_saved:
            return # Nothing to save or already saved

        if not self.output_file_stem:
             self.output_signal.emit("Error: Cannot save participant map, output file stem not set.")
             return

        try:
            directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Race Data")
            map_filename = f"{self.output_file_stem}_participants.json"
            map_filepath = os.path.join(directory, map_filename)

            # Sort map by position before saving for readability
            sorted_map = dict(sorted(self.participant_map.items(), key=lambda item: item[1]))

            with open(map_filepath, 'w', encoding='utf-8') as f:
                json.dump(sorted_map, f, indent=4)

            self.output_signal.emit(f"Participant map saved to: {map_filepath}")
            self.participant_map_saved = True # Mark as saved
            return map_filepath # Return path for potential use

        except Exception as e:
            self.output_signal.emit(f"Error saving participant map: {e}")
            return None
    # ------------------------------------

    def run(self):
        self.output_signal.emit("Starting data collection...")
        self.running = True
        self.setup_shared_memory()

        # Initial file setup based on current state
        data = self.read_shared_memory()
        initial_session_name = "Unknown"
        if data:
            session_names = {
                SESSION_PRACTICE: "Practice", SESSION_TEST: "Test", SESSION_QUALIFY: "Qualifying",
                SESSION_FORMATION_LAP: "Formation_Lap", SESSION_RACE: "Race", SESSION_TIME_ATTACK: "Time_Attack"
            }
            initial_session_name = session_names.get(data.mSessionState, "Unknown")
            self.session_type = data.mSessionState
            self.previous_session_type = data.mSessionState # Important: Init previous state

            if data.mTrackLocation:
                try: self.track_name = data.mTrackLocation.decode('utf-8').strip('\x00')
                except: self.track_name = "Unknown Track"
        else:
            # If no data on start, still need previous state set
            self.session_type = SESSION_INVALID
            self.previous_session_type = SESSION_INVALID

        self.setup_output_file(initial_session_name) # Sets self.output_file_stem

        try:
            while self.running:
                data = self.read_shared_memory()
                if data:
                    self.process_participant_data(data)
                else:
                    # Handle case where memory becomes unreadable (e.g., game closed)
                    # Optionally add a check here to try reconnecting or just sleep
                    pass
                time.sleep(0.2) # Main loop delay
        except Exception as e:
            self.output_signal.emit(f"Error in data collection loop: {e}")
        finally:
            if self.file_handle:
                try:
                    self.file_handle.close()
                    self.output_signal.emit("Shared memory closed.")
                except Exception as e_close:
                     self.output_signal.emit(f"Error closing shared memory: {e_close}")
            # --- Save map when stopping ---
            self.save_participant_map()
            # ------------------------------
            self.output_signal.emit("Data collection stopped.")
            self.running = False # Ensure running flag is false

    def stop(self):
        self.output_signal.emit("Stopping data collection...")
        self.running = False
        # Saving is handled in the finally block of run()
