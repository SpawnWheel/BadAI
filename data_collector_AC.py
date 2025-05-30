# data_collector_AC.py
import sys
import os
import socket
import struct
import time
from datetime import datetime, timedelta
import json
from PyQt5.QtCore import QThread, pyqtSignal

# --- Assetto Corsa UDP Packet Type IDs ---
# Note: Verify these IDs against AC documentation/headers if issues arise
AC_CAR_INFO = 1
AC_SESSION_INFO = 2
AC_LAP_COMPLETED = 3
# AC_END_SESSION = 4 # Less common, often inferred
AC_CLIENT_EVENT = 5 # E.g., collision with environment/car
AC_REALTIME_UPDATE = 6 # Per-car real-time update
# AC_CLIENT_LOADED = 7
# AC_SESSION_START = 8 # Often part of SESSION_INFO
# AC_ERROR = 9
# AC_DATA_REQUEST = 10
# AC_REALTIME_LAP = 11 # Contains lap timing details

# --- Constants from other collectors (adapt as needed) ---
# Session Types (approximated from AC session index)
SESSION_TYPE_MAP = {
    0: "Practice",
    1: "Qualify",
    2: "Race",
    3: "Hotlap",
    4: "Time Attack",
    5: "Drift",
    6: "Drag",
    # Add others if needed
}

# Session Phases (simplified for AC)
SESSION_PHASE_PRE = "Pre Session"
SESSION_PHASE_SESSION = "Session"
SESSION_PHASE_POST = "Post Session" # e.g., after checkered flag
SESSION_PHASE_FORMATION = "Formation Lap" # Needs specific detection logic if AC supports it via UDP

# Thresholds for detecting a crossing (using normalized position)
UPPER_THRESHOLD = 0.98 # Closer to 1.0 for AC line crossing
LOWER_THRESHOLD = 0.02 # Just after 0.0 for AC line crossing


class DataCollector(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int) # Keep for potential future use

    def __init__(self, host='127.0.0.1', port=9996):
        super().__init__()
        self.udp_host = host
        self.udp_port = port
        self.udp_socket = None
        self.running = False

        # --- State Variables (similar structure to ACC collector) ---
        self.cars = {}  # Holds info about each car, key = car_id
        self.car_ids_to_drivers = {} # Map car_id to driver name for easy lookup
        self.session_info = {}
        self.last_update_time = 0 # Timestamp of last full processing cycle
        self.update_interval = 4 # Seconds between major updates like leaderboard
        self.previous_positions = {}
        self.previous_progress = {}  # Store previous 'adjusted_progress'

        self.race_started = False
        self.session_time_elapsed_ms = 0 # Calculated based on race start detection
        self.race_start_time = None # System time when race session detected as active

        self.current_accidents = {} # Stores detected accidents (car_id: time)
        self.initialization_complete = False # Flag if we received essential session/car info
        self.output_file = None
        self.cars_in_pits = set() # Store car_ids of cars currently in pits
        self.last_position_display = 0 # Session time when positions were last displayed

        self.track_name = "Unknown"
        self.track_config = ""
        self.track_length = 0 # Meters, important for progress calculation if needed
        self.corner_data = []  # Store corner data for the current track

        # Final lap & finishing logic (Needs adaptation for AC UDP)
        self.final_lap_phase = False # True if session timer runs out or leader starts last lap
        self.finished_cars = set() # car_ids of finished cars
        self.leader_finished = False # True when P1 crosses line after final_lap_phase starts
        self.leader_car_id = None # Track the current leader's car_id
        self.race_laps = 0 # Total laps if race is lap-based

        # Per‐car data for lap tracking and progress
        # We primarily rely on AC_LAP_COMPLETED but track progress within lap
        self.car_lap_data = {} # car_id: {'laps': count, 'normalized_pos': float, 'adjusted_progress': float}

        # Session state tracking for file creation
        self.previous_session_type_index = -1
        self.current_session_type_index = -1

        # Accident detection (similar to ACC)
        self.cars_in_accident = {} # car_id: {'time': session_elapsed, 'driver': name}
        self.previous_speeds = {}  # car_id: speed_kmh
        self.accident_speed_threshold = 35  # kph
        self.accident_recovery_threshold = 80  # kph
        self.race_start_immunity = 10.0  # seconds

    def run(self):
        """Main execution loop for data collection."""
        self.running = True
        if not self.setup_udp_socket():
            self.stop()
            return

        self.output_signal.emit("UDP Socket Opened. Waiting for Assetto Corsa data...")

        # Wait for initial session/car info before proceeding
        initial_packets_received = False
        start_wait_time = time.time()
        while self.running and not initial_packets_received and (time.time() - start_wait_time < 20): # Wait up to 20s
            self.receive_and_process_packet()
            if self.cars and self.track_name != "Unknown":
                initial_packets_received = True
                self.initialization_complete = True
                self.output_signal.emit(f"Initial data received. Track: {self.track_name}, Cars: {len(self.cars)}")
                self.setup_output_file() # Setup file once we know the session type
                self.log_pre_race_info()
                self.load_corner_data() # Load corners after track name is known
                self.last_update_time = time.time() # Start periodic updates
            else:
                self.msleep(100) # Small sleep while waiting

        if not self.initialization_complete:
            self.output_signal.emit("Warning: Did not receive initial data from AC. Ensure game is running and UDP is configured correctly.")
            # Optionally continue running to wait for data or stop
            # self.stop()
            # return

        # Main loop after initialization
        while self.running:
            self.receive_and_process_packet()

            current_time = time.time()
            if self.race_started:
                 self.session_time_elapsed_ms = int((current_time - self.race_start_time) * 1000)

            # --- Periodic Tasks ---
            if self.initialization_complete and (current_time - self.last_update_time >= self.update_interval):
                 if self.race_started and not self.final_lap_phase:
                     # Display positions periodically during race
                     elapsed_seconds = self.session_time_elapsed_ms / 1000
                     if elapsed_seconds >= 240 and (elapsed_seconds - self.last_position_display >= 240):
                         self.display_positions("Current positions")
                         self.last_position_display = elapsed_seconds

                     # Update race data (overtakes, check finish conditions)
                     self.update_race_data()

                 elif not self.race_started and self.current_session_type_index == 1: # Qualifying
                     # Display Qualy positions periodically
                     elapsed_seconds = time.time() - start_wait_time # Rough elapsed time for qualy display timing
                     if elapsed_seconds >= 60 and (elapsed_seconds - self.last_position_display >= 60):
                          self.display_positions("Qualifying positions")
                          self.last_position_display = elapsed_seconds


                 self.last_update_time = current_time

            # Small sleep if no packet was processed recently to prevent high CPU usage
            # The recv call has a timeout, so this might not be strictly necessary
            # self.msleep(10)

        self.output_signal.emit("Data collection loop finished.")


    def receive_and_process_packet(self):
        """Receives a single UDP packet and processes it."""
        try:
            data, addr = self.udp_socket.recvfrom(4096) # Buffer size, adjust if needed
            if not data:
                return

            # Unpack the header to get the packet type ID
            if len(data) >= 4: # Minimum size for type ID (usually 4 bytes int)
                packet_type = struct.unpack_from('<I', data, 0)[0] # '<I' = unsigned int, little-endian

                # --- Route to appropriate handler based on type ---
                if packet_type == AC_CAR_INFO:
                    self._handle_car_info(data)
                elif packet_type == AC_SESSION_INFO:
                    self._handle_session_info(data)
                elif packet_type == AC_LAP_COMPLETED:
                    self._handle_lap_completed(data)
                elif packet_type == AC_REALTIME_UPDATE:
                     self._handle_realtime_update(data)
                elif packet_type == AC_CLIENT_EVENT:
                     self._handle_client_event(data) # Handle collisions etc.
                # Add handlers for other relevant packet types if needed

        except socket.timeout:
            # Expected if game isn't sending data
            pass
        except socket.error as e:
            self.output_signal.emit(f"Socket Error: {e}")
            # Consider attempting to reconnect or stopping based on the error
            self.running = False # Stop on socket error
        except struct.error as e:
            self.output_signal.emit(f"Error unpacking UDP packet: {e}. Packet might be corrupted or format incorrect.")
        except Exception as e:
            self.output_signal.emit(f"Error processing UDP packet: {e}")


    def setup_udp_socket(self):
        """Creates and binds the UDP socket."""
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind((self.udp_host, self.udp_port))
            self.udp_socket.settimeout(1.0) # Set a timeout (e.g., 1 second) for recvfrom
            self.output_signal.emit(f"Listening for AC UDP data on {self.udp_host}:{self.udp_port}")
            return True
        except socket.error as e:
            self.output_signal.emit(f"Failed to create or bind UDP socket: {e}")
            self.output_signal.emit("Ensure Assetto Corsa is configured for UDP output and the port is not in use.")
            return False
        except Exception as e:
            self.output_signal.emit(f"An unexpected error occurred during socket setup: {e}")
            return False

    def stop(self):
        """Stops the data collection thread and closes the socket."""
        self.running = False
        if self.udp_socket:
            self.udp_socket.close()
            self.udp_socket = None
            self.output_signal.emit("UDP Socket closed.")
        self.output_signal.emit("Data collection stopped.")
        # Maybe save final state if needed

    # --- Packet Handlers ---

    def _handle_car_info(self, data):
        """Handles AC_CAR_INFO packets (static car details)."""
        # struct definition based on AC UDP documentation/examples
        # Example: <I (type) B (car_id) B (is_player) 50s (driver_name) 50s (car_model) ...
        try:
            # --- IMPORTANT: Adjust struct format string based on actual AC UDP protocol ---
            # This is a placeholder structure - VERIFY IT!
            expected_size = 1 + 1 + 50 + 50 # car_id, is_player, name, model (example!)
            # The first '<I' for packet type is already read. We need car_id onwards.
            # Let's assume type is byte (B), car_id byte (B), player byte (B), name 50s, model 50s
            # struct_format = '<BB50s50s' # B=car_id, B=is_player, 50s=name, 50s=model
            # offset = 4 # Start after the packet type ID

            # --- Revised structure based on common AC Python API examples ---
            # < packet_type (I) car_id (B) is_connected (B) car_model (50w) car_skin (50w) driver_name (50w) driver_team (50w) driver_guid (50w)
            # 'w' indicates UTF-16 / wide character string handling might be needed
            struct_format = '<B B 50s 50s 50s 50s 50s' # Using 's' for now, decode later
            offset = 4 # Start after packet type ID

            if len(data) >= offset + struct.calcsize(struct_format):
                 car_id, is_connected_byte, car_model_b, car_skin_b, driver_name_b, driver_team_b, driver_guid_b = struct.unpack_from(struct_format, data, offset)

                 if is_connected_byte: # Process only connected cars
                     # Decode UTF-16 strings, removing null terminators
                     try:
                         driver_name = driver_name_b.decode('utf-16le', errors='ignore').split('\x00', 1)[0]
                         car_model = car_model_b.decode('utf-16le', errors='ignore').split('\x00', 1)[0]
                         # nationality might not be directly available, team might be
                     except Exception as e:
                         self.output_signal.emit(f"Error decoding car info strings for car {car_id}: {e}")
                         driver_name = f"Car_{car_id}"
                         car_model = "Unknown"

                     if not driver_name: driver_name = f"Car_{car_id}" # Fallback name

                     if car_id not in self.cars:
                         self.cars[car_id] = {'carIndex': car_id} # Use carIndex for consistency
                         self.car_lap_data[car_id] = {'laps': 0, 'normalized_pos': 0.0, 'adjusted_progress': 0.0}

                     self.cars[car_id].update({
                         'driverName': driver_name,
                         'carModel': car_model,
                         # Add team, guid etc. if needed
                         'isActive': True # Assume active if we get info
                     })
                     self.car_ids_to_drivers[car_id] = driver_name
                     # self.output_signal.emit(f"Car Info: ID {car_id}, Driver: {driver_name}, Model: {car_model}")


        except struct.error as e:
            self.output_signal.emit(f"Error unpacking CAR_INFO: {e}")
        except Exception as e:
            self.output_signal.emit(f"Error processing CAR_INFO: {e}")

    def _handle_session_info(self, data):
        """Handles AC_SESSION_INFO packets."""
        try:
            # --- IMPORTANT: Adjust struct format string based on actual AC UDP protocol ---
            # Example structure: <I (type) B (version) B (session_index) B (current_session_index) B (session_count) ... track_name (100w) ... track_length (f) ...
            # Format based on common examples:
            # < I(type) B(ver) B(sess_idx) B(cur_sess_idx) B(sess_cnt) B(server_status) B(runtime_status)
            # 50w(server_name) 50w(track) 50w(track_cfg) 100w(player) ... f(ambient_temp) f(road_temp) ... I(num_cars) ...
            # f(session_duration) f(session_time_left) ... f(track_length) B(lap_based) H(race_laps) ...
            struct_format = '<B B B B B B 50s 50s 50s 100s 50s 50s f f I f f f B H' # Simplified, add/verify fields!
            offset = 4 # After packet type ID

            # This structure needs precise definition based on AC documentation
            # Using placeholders for unpack based on a potential structure:
            (protocol_version, session_index, current_session_index, session_count, server_status, runtime_status,
            server_name_b, track_name_b, track_config_b, player_name_b, team_name_b, car_name_b, # Example strings
            ambient_temp, road_temp, num_cars, session_duration, time_left, track_length, # Example numerics
            is_lap_based, race_laps_total # Example race details
            ) = struct.unpack_from(struct_format, data, offset) # Adjust format and offset

            # Decode strings
            new_track_name = track_name_b.decode('utf-16le', errors='ignore').split('\x00', 1)[0]
            new_track_config = track_config_b.decode('utf-16le', errors='ignore').split('\x00', 1)[0]

            if not self.track_name or self.track_name == "Unknown" or self.track_name != new_track_name:
                 self.track_name = new_track_name
                 self.track_config = new_track_config
                 self.track_length = track_length
                 self.output_signal.emit(f"Track Info: {self.track_name} ({self.track_config}), Length: {self.track_length:.0f}m")
                 self.load_corner_data() # Load corners when track is identified

            self.race_laps = race_laps_total if is_lap_based else 0
            self.current_session_type_index = current_session_index # Store the index

            session_type_str = SESSION_TYPE_MAP.get(current_session_index, "Unknown")
            self.session_info = {
                "sessionType": session_type_str,
                "sessionIndex": current_session_index,
                "timeLeft": time_left,
                "duration": session_duration,
                "ambientTemp": ambient_temp,
                "roadTemp": road_temp,
                "numberOfCars": num_cars,
                "isLapBased": bool(is_lap_based),
                "raceLaps": self.race_laps
            }

            # --- Session Change Detection & File Setup ---
            if self.current_session_type_index != self.previous_session_type_index:
                if self.previous_session_type_index != -1: # Avoid triggering on first ever packet
                    prev_session_name = SESSION_TYPE_MAP.get(self.previous_session_type_index, "Unknown")
                    self.output_signal.emit(f"Session changed from {prev_session_name} to {session_type_str}. Creating new log file.")
                    self._reset_session_state() # Reset flags, positions etc.
                    self.setup_output_file(session_type_str) # New file with session name
                    self.log_event(f"New session started: {session_type_str}")
                else:
                    # First session detected, setup initial file
                    self.setup_output_file(session_type_str)
                    self.log_event(f"Session detected: {session_type_str}")

                self.previous_session_type_index = self.current_session_type_index

            # --- Race Start Detection ---
            # Condition: Session type is Race (index 2) and maybe time_left starts decreasing from duration?
            # Or based on car movement after lights? AC UDP might not have explicit 'Session' phase like ACC.
            # Let's assume race starts if type is Race and cars are moving (handled in realtime update perhaps)
            # A simple start: if session is Race and race_started is False.
            if not self.race_started and current_session_index == 2: # 2 = Race
                self.race_started = True
                self.race_start_time = time.time() # Record system time at start
                 # Adjust elapsed time slightly if time_left is already less than duration
                if session_duration > 0 and time_left > 0:
                    initial_elapsed = session_duration - time_left
                    self.race_start_time -= initial_elapsed # Adjust start time backwards
                    self.session_time_elapsed_ms = int(initial_elapsed * 1000)

                self.log_event("The Race Begins!")
                self.display_positions("Starting Grid") # Log initial grid

            # --- Final Lap Detection ---
            if self.race_started and not self.final_lap_phase:
                 is_timed_race = not self.session_info.get("isLapBased", False) and self.session_info.get("duration", 0) > 0
                 is_lap_race = self.session_info.get("isLapBased", False) and self.session_info.get("raceLaps", 0) > 0

                 if is_timed_race and time_left <= 0.1: # Timer runs out
                     self.final_lap_phase = True
                     self.log_event("Timer expired. Leader is on final lap.")
                 # Lap-based final lap detection happens when leader completes lap N-1 (in LAP_COMPLETED)


        except struct.error as e:
            self.output_signal.emit(f"Error unpacking SESSION_INFO: {e}")
        except Exception as e:
            self.output_signal.emit(f"Error processing SESSION_INFO: {e}")


    def _handle_lap_completed(self, data):
        """Handles AC_LAP_COMPLETED packets."""
        try:
            # --- IMPORTANT: Adjust struct format string based on actual AC UDP protocol ---
            # Format based on common examples: <I(type) B(car_id) I(lap_time_ms) B(cuts)
            struct_format = '<B I B' # car_id (Byte), lap_time (UInt32), cuts (Byte)
            offset = 4 # After packet type ID
            car_id, lap_time_ms, cuts = struct.unpack_from(struct_format, data, offset)

            # Get additional info if available (e.g., AC_REALTIME_LAP packets might follow or be separate)
            # AC_REALTIME_LAP structure might be: <I(type) B(car_id) H(lap) H(sector_idx) f(sector_time) f(lap_time)
            # For now, just use the basic LAP_COMPLETED info

            if car_id in self.cars and car_id in self.car_lap_data:
                driver_name = self.cars[car_id].get('driverName', f"Car {car_id}")
                self.car_lap_data[car_id]['laps'] += 1
                laps_completed = self.car_lap_data[car_id]['laps']

                lap_time_str = self.format_lap_time(lap_time_ms)
                cuts_str = f" ({cuts} cuts)" if cuts > 0 else ""

                # Log the lap completion
                self.log_event(f"Lap {laps_completed} completed by {driver_name}: {lap_time_str}{cuts_str}")

                # --- Lap-based Race Logic ---
                if self.race_started and self.session_info.get("isLapBased", False):
                    total_laps = self.session_info.get("raceLaps", 0)

                    # Check if leader started final lap
                    if not self.final_lap_phase and car_id == self.leader_car_id and laps_completed == total_laps:
                         self.final_lap_phase = True
                         self.log_event(f"Leader {driver_name} is starting the final lap ({laps_completed}/{total_laps})!")

                    # Check if a car finished the race
                    if self.final_lap_phase and car_id not in self.finished_cars:
                        if laps_completed >= total_laps: # >= in case of timing issues
                            is_leader = (car_id == self.leader_car_id)
                            self.finished_cars.add(car_id)
                            finish_position = self.cars[car_id].get('position', '?') # Get current position

                            if is_leader and not self.leader_finished:
                                self.leader_finished = True
                                self.log_event(f"Checkered flag! {driver_name} takes the win!")
                                # Announce finish position here or rely on subsequent cars crossing
                                self.log_event(f"{driver_name} has finished in position {finish_position}.")

                            elif self.leader_finished: # Subsequent finishers
                                self.log_event(f"{driver_name} has finished in position {finish_position}.")


            else:
                 self.output_signal.emit(f"Lap completed for unknown car ID: {car_id}")


        except struct.error as e:
            self.output_signal.emit(f"Error unpacking LAP_COMPLETED: {e}")
        except Exception as e:
            self.output_signal.emit(f"Error processing LAP_COMPLETED: {e}")

    def _handle_realtime_update(self, data):
        """Handles AC_REALTIME_UPDATE packets (per car)."""
        try:
            # --- IMPORTANT: Adjust struct format string based on actual AC UDP protocol ---
            # Based on common examples:
            # < I(type) B(car_id) f(normalized_pos) I(current_time_ms) I(last_time_ms) I(best_time_ms)
            # B(session_restarts) B(completed_laps) f(distance_traveled) f(speed_kmh) f(speed_mph) f(speed_ms)
            # B(is_in_pit) B(is_engine_limiter_on) ... world_pos (fff) ... more physics data ...
            struct_format = '<B f I I I B B f f f f B B f f f' # Simplified: id, norm_pos, cur_t, last_t, best_t, restarts, laps, dist, kmh, mph, ms, in_pit, limiter, wx, wy, wz
            offset = 4

            if len(data) >= offset + struct.calcsize(struct_format):
                (car_id, normalized_pos, current_time_ms, last_time_ms, best_time_ms,
                 session_restarts, completed_laps_udp, distance_traveled, speed_kmh, speed_mph, speed_ms,
                 is_in_pit, is_engine_limiter_on, world_x, world_y, world_z # example unpack
                ) = struct.unpack_from(struct_format, data, offset)

                if car_id in self.cars and car_id in self.car_lap_data:
                    current_car = self.cars[car_id]
                    current_lap_data = self.car_lap_data[car_id]

                    # --- Update Car State ---
                    # Use internal lap count primarily, UDP one as backup/cross-reference
                    current_lap_data['laps'] = max(current_lap_data['laps'], completed_laps_udp)
                    current_lap_data['normalized_pos'] = normalized_pos
                    current_lap_data['adjusted_progress'] = current_lap_data['laps'] + normalized_pos

                    current_car.update({
                        'position': current_car.get('position', 0), # Position updated separately
                        'laps_udp': completed_laps_udp, # Store UDP laps for reference
                        'splinePosition': normalized_pos, # Use AC's normalized pos
                        'currentLapTimeMs': current_time_ms,
                        'lastLapTimeMs': last_time_ms,
                        'bestLapTimeMs': best_time_ms,
                        'speed': speed_kmh,
                        'worldPosition': (world_x, world_y, world_z),
                        'isInPit': bool(is_in_pit)
                    })

                    # --- Pit Lane Logic ---
                    driver_name = current_car.get('driverName', f"Car {car_id}")
                    if bool(is_in_pit) and car_id not in self.cars_in_pits:
                        self.cars_in_pits.add(car_id)
                        self.log_event(f"{driver_name} has entered the pits.")
                    elif not bool(is_in_pit) and car_id in self.cars_in_pits:
                        self.cars_in_pits.remove(car_id)
                        self.log_event(f"{driver_name} has exited the pits.")


                    # --- Accident Detection ---
                    if self.race_started and car_id not in self.finished_cars:
                        session_elapsed = self.session_time_elapsed_ms / 1000
                        if (car_id not in self.cars_in_pits and
                                session_elapsed > self.race_start_immunity):

                             # Check if speed dropped below threshold
                            if (speed_kmh < self.accident_speed_threshold and
                                    car_id not in self.cars_in_accident):

                                corner_name = self.get_corner_name(normalized_pos) if self.corner_data else None
                                location_info = f" at {corner_name}" if corner_name else ""
                                position_info = f" from P{current_car.get('position', '?')}"

                                self.log_event(f"Accident! {driver_name} has stopped{position_info}{location_info}")
                                self.cars_in_accident[car_id] = {
                                    'time': session_elapsed,
                                    'location': corner_name,
                                    'driver': driver_name
                                }

                            # Check if car has recovered
                            elif (car_id in self.cars_in_accident and
                                  speed_kmh > self.accident_recovery_threshold):
                                self.log_event(f"{driver_name} appears to be moving again.")
                                del self.cars_in_accident[car_id]

                    self.previous_speeds[car_id] = speed_kmh


        except struct.error as e:
            self.output_signal.emit(f"Error unpacking REALTIME_UPDATE: {e}")
        except Exception as e:
            self.output_signal.emit(f"Error processing REALTIME_UPDATE: {e}")


    def _handle_client_event(self, data):
        """Handles AC_CLIENT_EVENT packets (e.g., collisions)."""
        try:
            # Structure based on common examples: <I(type) B(event_type) B(car_id) B(other_car_id) f(speed_impact) ...
            # Event Types: 1=Collision with Env, 2=Collision with Car
            struct_format = '<B B B f' # type, car_id, other_car_id, impact_speed
            offset = 4
            event_type, car_id, other_car_id, impact_speed = struct.unpack_from(struct_format, data, offset)

            if car_id in self.cars:
                 driver_name = self.cars[car_id].get('driverName', f"Car {car_id}")
                 impact_kph = impact_speed * 3.6

                 # Simple collision logging - can be refined
                 if event_type == 1: # Collision with Env
                     # Could check impact speed threshold if desired
                     # self.log_event(f"Incident: {driver_name} had contact with the environment (Impact: {impact_kph:.1f} kph).")
                     pass # Avoid spamming for minor contacts, rely on speed drop for accidents
                 elif event_type == 2: # Collision with Car
                     if other_car_id in self.cars:
                         other_driver_name = self.cars[other_car_id].get('driverName', f"Car {other_car_id}")
                         # Could check impact speed threshold
                         # self.log_event(f"Incident: Contact between {driver_name} and {other_driver_name} (Impact: {impact_kph:.1f} kph).")
                         pass # Avoid spamming

        except struct.error as e:
            self.output_signal.emit(f"Error unpacking CLIENT_EVENT: {e}")
        except Exception as e:
            self.output_signal.emit(f"Error processing CLIENT_EVENT: {e}")

    # --- Core Logic Methods (Adapted from ACC) ---

    def log_pre_race_info(self):
        """Logs available pre-race information."""
        try:
            pre_race_info = []
            if self.track_name and self.track_name != "Unknown":
                track_info = f"Track: {self.track_name}"
                if self.track_config: track_info += f" ({self.track_config})"
                pre_race_info.append(track_info)

            if self.session_info.get("sessionType"):
                pre_race_info.append(f"Session Type: {self.session_info['sessionType']}")

            if self.cars:
                car_models = set(car.get('carModel', 'Unknown') for car in self.cars.values() if car.get('isActive'))
                if car_models and car_models != {'Unknown'}:
                    pre_race_info.append(f"Car Classes/Models: {', '.join(sorted(list(car_models)))}") # AC doesn't have strict classes like ACC

            if self.session_info.get("isLapBased") is not None:
                 if self.session_info["isLapBased"]:
                     pre_race_info.append(f"Race Length: {self.session_info['raceLaps']} Laps")
                 elif self.session_info.get("duration", 0) > 0:
                     duration_min = self.session_info["duration"] / 60
                     pre_race_info.append(f"Race Length: {duration_min:.0f} Minutes")


            if len(pre_race_info) > 0:
                info_string = " | ".join(pre_race_info)
                self.log_event(f"Pre-Race Information: {info_string}")
                return True
            else:
                self.output_signal.emit("Waiting for more pre-race information...")
                return False

        except Exception as e:
            self.output_signal.emit(f"Error collecting pre-race information: {str(e)}")
            return False


    def get_sorted_cars(self):
        """Sorts cars by adjusted progress (laps + normalized_pos)."""
        # Filter out inactive cars if necessary
        active_car_ids = [cid for cid, car in self.cars.items() if car.get('isActive')]
        # Get lap data for active cars, default to 0 if missing
        car_data_to_sort = [self.car_lap_data.get(cid, {'adjusted_progress': 0.0, 'carIndex': cid}) for cid in active_car_ids]

        # Add carIndex to lap data if missing, needed for sorting key fallback
        for i, cid in enumerate(active_car_ids):
             if 'carIndex' not in car_data_to_sort[i]:
                 car_data_to_sort[i]['carIndex'] = cid
             # Ensure adjusted_progress exists
             if 'adjusted_progress' not in car_data_to_sort[i]:
                  car_data_to_sort[i]['adjusted_progress'] = self.car_lap_data.get(cid, {}).get('adjusted_progress', 0.0)


        # Sort: highest progress first. Use carIndex as tie-breaker? (Not strictly needed)
        # Ensure the key lambda handles missing 'adjusted_progress' safely
        return sorted(car_data_to_sort, key=lambda x: x.get('adjusted_progress', 0.0), reverse=True)


    def display_positions(self, title="Current positions"):
        """Displays the current leaderboard in the log."""
        sorted_lap_data = self.get_sorted_cars()
        positions = []
        self.leader_car_id = None # Reset leader

        for position, lap_data in enumerate(sorted_lap_data, start=1):
            car_id = lap_data.get('carIndex')
            if car_id is None: continue # Skip if no carIndex somehow

            if car_id not in self.finished_cars:
                driver_name = self.cars.get(car_id, {}).get('driverName', f"Car {car_id}")
                positions.append(f"(P{position}) {driver_name}")
                # Update car's position attribute
                if car_id in self.cars:
                    self.cars[car_id]['position'] = position
                # Set leader
                if position == 1:
                    self.leader_car_id = car_id


        # If race hasn't started but it's Qualifying, use "Qualifying positions"
        if not self.race_started and self.current_session_type_index == 1: # Qualify = 1
             title = "Qualifying positions"


        position_string = f"{title}: " + ", ".join(positions)
        self.log_event(position_string)


    def update_race_data(self):
        """Periodically called during the race to check for overtakes and finish."""
        # Get current order (based on laps + normalized_pos)
        sorted_lap_data = self.get_sorted_cars()

        current_positions = {} # car_id -> position
        current_progress = {} # car_id -> adjusted_progress

        # Update leader and current positions/progress map
        self.leader_car_id = None
        for i, lap_data in enumerate(sorted_lap_data):
            car_id = lap_data.get('carIndex')
            if car_id is None: continue
            pos = i + 1
            progress = lap_data.get('adjusted_progress', 0.0)

            if car_id not in self.finished_cars: # Only consider active racers
                 current_positions[car_id] = pos
                 current_progress[car_id] = progress
                 if car_id in self.cars:
                     self.cars[car_id]['position'] = pos # Update car's position
                 if pos == 1:
                      self.leader_car_id = car_id


        # --- Overtake Detection ---
        # Only detect if we have previous data and race has been running for a bit
        if self.previous_positions and self.session_time_elapsed_ms >= 15000:
             overtakes = self.detect_overtakes(current_positions, current_progress)
             for overtake in overtakes:
                 self.log_event(overtake)


        # Update previous state for next cycle
        # Filter previous state to only include cars still active
        self.previous_positions = {cid: pos for cid, pos in current_positions.items() if cid in self.cars and self.cars[cid].get('isActive')}
        self.previous_progress = {cid: prog for cid, prog in current_progress.items() if cid in self.cars and self.cars[cid].get('isActive')}

        # --- Check Race Finish Conditions (Timed Race) ---
        # Check if leader finished in a timed race (lap-based handled in LAP_COMPLETED)
        if self.final_lap_phase and not self.leader_finished:
            is_timed_race = not self.session_info.get("isLapBased", False)
            if is_timed_race and self.leader_car_id is not None:
                 leader_lap_data = self.car_lap_data.get(self.leader_car_id)
                 if leader_lap_data:
                     # Check if leader crossed the line (normalized pos goes low after being high)
                     # This needs careful tuning based on how AC reports pos near the line
                     # A simpler check might be needed, maybe combined with lap counter increment
                     prev_leader_progress = self.previous_progress.get(self.leader_car_id, 0.0)
                     current_leader_progress = leader_lap_data.get('adjusted_progress', 0.0)

                     # Detect crossing: previous was high (e.g >0.9), current is low (e.g. <0.1)
                     if prev_leader_progress % 1 > UPPER_THRESHOLD and current_leader_progress % 1 < LOWER_THRESHOLD:
                          self.leader_finished = True
                          leader_name = self.cars.get(self.leader_car_id, {}).get('driverName', f"Car {self.leader_car_id}")
                          self.log_event(f"Checkered flag! {leader_name} takes the win!")
                          self.finished_cars.add(self.leader_car_id)
                          self.log_event(f"{leader_name} has finished in position 1.")


        # Check subsequent finishers after leader is done
        if self.leader_finished:
             for car_id, lap_data in self.car_lap_data.items():
                 if car_id not in self.finished_cars and car_id in self.cars and self.cars[car_id].get('isActive'):
                     prev_progress = self.previous_progress.get(car_id, 0.0)
                     current_progress_val = lap_data.get('adjusted_progress', 0.0)
                     # Check if they crossed the line
                     if prev_progress % 1 > UPPER_THRESHOLD and current_progress_val % 1 < LOWER_THRESHOLD:
                         self.finished_cars.add(car_id)
                         driver_name = self.cars.get(car_id, {}).get('driverName', f"Car {car_id}")
                         finish_position = self.cars.get(car_id, {}).get('position', '?')
                         self.log_event(f"{driver_name} has finished in position {finish_position}.")



    def detect_overtakes(self, current_positions, current_progress):
        """Compares current state to previous to find overtakes."""
        overtakes = []
        if not self.previous_positions or not self.race_started:
            return overtakes

        for car_id, current_pos in current_positions.items():
            # Check if car existed previously and is not pitting/finished
            if car_id in self.previous_positions and car_id not in self.cars_in_pits and car_id not in self.finished_cars:
                previous_pos = self.previous_positions[car_id]

                # Position Improved?
                if current_pos < previous_pos:
                    # Check if they *actually* passed based on progress to avoid swaps during pit stops etc.
                    prev_overtaker_prog = self.previous_progress.get(car_id, 0.0)
                    cur_overtaker_prog = current_progress.get(car_id, 0.0)

                    # Find who they likely overtook (the car now in the overtaker's previous position)
                    overtaken_car_id = None
                    for other_id, other_prev_pos in self.previous_positions.items():
                         if other_prev_pos == current_pos and other_id != car_id:
                              # Check if this other car is now behind the overtaker
                              if current_positions.get(other_id, float('inf')) > current_pos:
                                   overtaken_car_id = other_id
                                   break

                    if overtaken_car_id is not None and overtaken_car_id not in self.cars_in_pits:
                        prev_overtaken_prog = self.previous_progress.get(overtaken_car_id, 0.0)
                        cur_overtaken_prog = current_progress.get(overtaken_car_id, 0.0)

                        # Confirm progress crossover: Overtaker was behind, now is ahead
                        if prev_overtaker_prog < prev_overtaken_prog and cur_overtaker_prog > cur_overtaken_prog:
                            try:
                                overtaker_name = self.cars[car_id].get('driverName', f"Car {car_id}")
                                overtaken_name = self.cars[overtaken_car_id].get('driverName', f"Car {overtaken_car_id}")
                            except KeyError:
                                continue # Skip if car info isn't fully populated yet

                            # Check for lapping
                            overtaker_laps = self.car_lap_data.get(car_id, {}).get('laps', 0)
                            overtaken_laps = self.car_lap_data.get(overtaken_car_id, {}).get('laps', 0)

                            corner_name = self.get_corner_name(cur_overtaker_prog % 1) # Use normalized pos
                            location_str = f" at {corner_name}" if corner_name else ""

                            if overtaker_laps > overtaken_laps:
                                overtake_message = f"Overtake! {overtaker_name} laps {overtaken_name}{location_str}."
                            else:
                                overtake_message = f"Overtake! {overtaker_name} passes {overtaken_name} for P{current_pos}{location_str}."

                            overtakes.append(overtake_message)

        return overtakes

    def _reset_session_state(self):
        """Resets variables when a new session starts."""
        self.output_signal.emit("Resetting session state...")
        # self.cars = {} # Keep car info like names? Or reset? Let's keep basic info.
        # Reset dynamic data within cars
        for car_id in self.cars:
            self.cars[car_id].pop('position', None)
            self.cars[car_id].pop('speed', None)
            self.cars[car_id].pop('isInPit', None)
            self.cars[car_id].pop('laps_udp', None)
            self.cars[car_id].pop('splinePosition', None)
            # Keep 'isActive', 'driverName', 'carModel'

        self.car_lap_data.clear()
        self.car_ids_to_drivers.clear() # Rebuild from CAR_INFO in new session
        self.session_info = {}
        self.previous_positions = {}
        self.previous_progress = {}
        self.race_started = False
        self.session_time_elapsed_ms = 0
        self.race_start_time = None
        self.current_accidents = {}
        # self.initialization_complete = False # Keep true if basics like track are known
        self.cars_in_pits = set()
        self.last_position_display = 0
        # Keep track name/config/length
        # self.corner_data = [] # Reloaded by load_corner_data if track changes

        self.final_lap_phase = False
        self.finished_cars = set()
        self.leader_finished = False
        self.leader_car_id = None
        self.race_laps = 0

        self.cars_in_accident = {}
        self.previous_speeds = {}

        # Re-initialize lap data structure for existing cars
        for car_id in self.cars:
             self.car_lap_data[car_id] = {'laps': 0, 'normalized_pos': 0.0, 'adjusted_progress': 0.0}


    # --- Utility Methods (Mostly from ACC, path adjusted) ---

    def load_corner_data(self):
        if not self.track_name or self.track_name == "Unknown":
             return
        # AC track names might have variants (e.g., 'ks_nordschleife - tourist'). Need to normalize.
        # Simple approach: use the base track name before any ' - ' variant part.
        base_track_name = self.track_name.split(' - ')[0]

        # Corner data should be in a subfolder relative to *this* script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        corner_data_folder = os.path.join(script_dir, "CornerData") # Assumes CornerData is sibling to this file

        # Try exact match first, then base name
        potential_files = [
            f"{self.track_name}.json", # e.g., ks_nordschleife - tourist.json
            f"{base_track_name}.json" # e.g., ks_nordschleife.json
        ]

        loaded = False
        for file_name in potential_files:
            corner_file_path = os.path.join(corner_data_folder, file_name)
            if os.path.exists(corner_file_path):
                try:
                    with open(corner_file_path, 'r', encoding='utf-8') as f:
                        self.corner_data = json.load(f)
                    self.output_signal.emit(f"Loaded corner data for track: {self.track_name} (using {file_name})")
                    loaded = True
                    break # Stop after first successful load
                except json.JSONDecodeError:
                     self.output_signal.emit(f"Error decoding JSON from corner file: {corner_file_path}")
                except Exception as e:
                    self.output_signal.emit(f"Error loading corner file {corner_file_path}: {e}")


        if not loaded:
            self.corner_data = [] # Ensure it's empty if load fails
            self.output_signal.emit(f"No valid corner data found for track: {self.track_name}. Looked for {potential_files} in {corner_data_folder}.")


    def get_corner_name(self, normalized_position):
        """Finds corner name for a given normalized spline position (0.0 to 1.0)."""
        if not self.corner_data:
            return None

        for corner in self.corner_data:
            try:
                start = float(corner['start'])
                end = float(corner['end'])
                name = corner['name']

                # Check for wrap-around corners (end < start, e.g., across start/finish)
                if start > end:
                    if normalized_position >= start or normalized_position <= end:
                        return name
                # Normal corners
                elif start <= normalized_position <= end:
                    return name
            except (KeyError, ValueError) as e:
                 self.output_signal.emit(f"Warning: Skipping invalid corner data entry: {corner}. Error: {e}")
                 continue # Skip malformed entries

        return None # No matching corner found

    def format_session_time(self, milliseconds):
        if milliseconds < 0: return "00:00:00"
        total_seconds = int(milliseconds // 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def format_lap_time(self, milliseconds):
        if milliseconds <= 0: return "--:--.---"
        total_seconds = milliseconds / 1000.0
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:06.3f}" # Format like 01:23.456


    def setup_output_file(self, session_name="Session"):
        """Set up output file, using session name."""
         # Ensure "Race Data" directory exists relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, "Race Data")

        try:
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            start_time = datetime.now()
            # Sanitize session name for filename
            safe_session_name = "".join(c for c in session_name if c.isalnum() or c in (' ', '_')).rstrip()
            safe_session_name = safe_session_name.replace(' ', '_') # Replace spaces

            # Sanitize track name
            safe_track_name = "UnknownTrack"
            if self.track_name and self.track_name != "Unknown":
                 safe_track_name = "".join(c for c in self.track_name if c.isalnum() or c in (' ', '_')).rstrip()
                 safe_track_name = safe_track_name.replace(' ', '_')

            filename = start_time.strftime("%Y-%m-%d_%H-%M-%S") + f"_{safe_track_name}_{safe_session_name}.txt"
            self.output_file = os.path.join(output_dir, filename)

            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(f"Assetto Corsa data collection started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Session: {session_name}\n")
                if self.track_name and self.track_name != "Unknown":
                     f.write(f"Track: {self.track_name}{' (' + self.track_config + ')' if self.track_config else ''}\n")
                f.write("\n") # Blank line before events start

            self.output_signal.emit(f"Logging race data to: {self.output_file}")

        except Exception as e:
            self.output_signal.emit(f"Error setting up output file in {output_dir}: {e}")
            self.output_file = None


    def log_event(self, event_text):
        """Logs an event with timestamp to the UI signal and the file."""
        formatted_time = "00:00:00" # Default if race not started
        if self.race_started and self.race_start_time is not None:
             # Calculate elapsed time based on current time and recorded start time
             elapsed_seconds = time.time() - self.race_start_time
             formatted_time = self.format_session_time(int(elapsed_seconds * 1000))
        elif self.session_info.get("sessionType"):
             # Use a generic timestamp if not in race (e.g., for Qualy)
             formatted_time = datetime.now().strftime("%H:%M:%S")


        log_message = f"{formatted_time} - {event_text}"
        self.output_signal.emit(log_message) # Send to UI

        if self.output_file and self.initialization_complete: # Only log to file after init and file setup
            try:
                # Use 'a' mode to append to the file
                with open(self.output_file, 'a', encoding='utf-8') as f:
                    f.write(log_message + '\n')
            except Exception as e:
                # Emit error but avoid recursive logging
                error_msg = f"!!! FAILED TO WRITE TO LOG FILE ({self.output_file}): {e} !!!"
                self.output_signal.emit(error_msg)
                # Consider disabling file logging temporarily if errors persist
                # self.output_file = None

# Example of how to use it (in your main application)
# if __name__ == '__main__':
#     from PyQt5.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget, QPushButton
#     import sys
#
#     class ACLoggerApp(QWidget):
#         def __init__(self):
#             super().__init__()
#             self.setWindowTitle("Assetto Corsa Data Logger")
#             self.log_output = QTextEdit()
#             self.log_output.setReadOnly(True)
#             self.start_button = QPushButton("Start Logging")
#             self.stop_button = QPushButton("Stop Logging")
#             self.stop_button.setEnabled(False)
#
#             layout = QVBoxLayout()
#             layout.addWidget(self.log_output)
#             layout.addWidget(self.start_button)
#             layout.addWidget(self.stop_button)
#             self.setLayout(layout)
#
#             self.data_collector = DataCollector() # Uses default host/port
#             self.data_collector.output_signal.connect(self.log_output.append)
#
#             self.start_button.clicked.connect(self.start_logging)
#             self.stop_button.clicked.connect(self.stop_logging)
#
#         def start_logging(self):
#             self.log_output.clear()
#             self.data_collector.start()
#             self.start_button.setEnabled(False)
#             self.stop_button.setEnabled(True)
#
#         def stop_logging(self):
#             self.data_collector.stop()
#             # Wait briefly for thread to finish? QThread.wait() can be used
#             self.data_collector.wait(2000) # Wait up to 2 seconds
#             self.start_button.setEnabled(True)
#             self.stop_button.setEnabled(False)
#
#         def closeEvent(self, event):
#             # Ensure collector stops when window closes
#             if self.data_collector.isRunning():
#                 self.stop_logging()
#             event.accept()
#
#     app = QApplication(sys.argv)
#     window = ACLoggerApp()
#     window.show()
#     sys.exit(app.exec_())