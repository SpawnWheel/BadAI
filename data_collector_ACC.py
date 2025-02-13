import sys
import os
from PyQt5.QtCore import QThread, pyqtSignal
from datetime import datetime, timedelta
import json

# Adjust the path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from accapi.client import AccClient


class DataCollector(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.client = AccClient()
        self.running = False
        self.cars = {}  # Holds info about each car
        self.session_info = {}
        self.last_update_time = 0
        self.update_interval = 4
        self.previous_positions = {}
        self.previous_progress = {}  # Store previous custom "adjusted_progress"
        self.race_started = False
        self.session_time_ms = 0
        self.race_start_time = None
        self.current_accidents = {}
        self.initialization_complete = False
        self.output_file = None
        self.cars_in_pits = set()
        self.last_position_display = 0
        self.track_data = None
        self.weather_data = None

        # Final lap & finishing logic
        self.final_lap_phase = False
        self.finished_cars = set()
        self.leader_finished = False
        self.leader_car_index = None
        self.total_laps = None

        self.start_line_crossed = set()
        self.qualifying_reported = False

        # Spline data logging
        self.spline_data = []  # Store spline data for each update cycle

        # Track/corner data
        self.track_name = "Unknown"
        self.corner_data = []  # Store corner data for the current track

        # Per‐car data for custom lap detection with a "just_crossed_line" flag
        self.custom_laps = {}

        # Thresholds for detecting a crossing
        self.UPPER_THRESHOLD = 0.9
        self.LOWER_THRESHOLD = 0.1

    def run(self):
        """Main execution loop for data collection."""
        self.running = True
        self.setup_client()
        self.start_client()

        self.output_signal.emit("Initializing data collection...")

        # Give the client some time to connect and receive initial data
        initialization_attempts = 0
        max_attempts = 20  # 10 seconds total (20 * 500ms)

        while initialization_attempts < max_attempts and self.running:
            if self.track_name != "Unknown" and self.cars:
                self.initialization_complete = True
                break
            self.msleep(500)
            initialization_attempts += 1

        if not self.initialization_complete:
            self.output_signal.emit("Warning: Could not fully initialize, but continuing with limited data...")
            self.initialization_complete = True  # Continue anyway

        if self.running:
            self.setup_output_file()

            # Attempt to log pre-race information
            pre_race_logged = False
            pre_race_attempts = 0
            while not pre_race_logged and pre_race_attempts < 5 and self.running:
                pre_race_logged = self.log_pre_race_info()
                if not pre_race_logged:
                    self.msleep(1000)
                    pre_race_attempts += 1

            self.output_signal.emit(
                f"Data collection initialized for track: {self.track_name}. Starting race monitoring...")

            # Load corner data for the track
            self.load_corner_data()

            # Display the leaderboard as soon as we have the necessary data
            self.display_positions()

        while self.running:
            self.msleep(self.update_interval * 1000)
            if self.race_started:
                self.update_race_data()

        # Save spline data to a JSON file when the race ends
        if hasattr(self, 'spline_data'):
            self.save_spline_data()

    def log_pre_race_info(self):
        """Logs comprehensive pre-race information including track, weather, and session details."""
        try:
            # Basic race information
            pre_race_info = []

            # Track Information - only add if we have a valid track name
            if self.track_name and self.track_name != "Unknown":
                pre_race_info.append(f"Track: {self.track_name}")

            # Session Information - check if dictionary exists and has required keys
            if self.session_info and isinstance(self.session_info, dict):
                if 'sessionType' in self.session_info:
                    pre_race_info.append(f"Session Type: {self.session_info['sessionType']}")

            # Car Classes - safely handle potentially empty cars dictionary
            if self.cars:
                car_classes = set()
                for car in self.cars.values():
                    if isinstance(car, dict):  # Ensure car is a dictionary
                        if car.get('isActive', False) and 'carClass' in car:
                            car_classes.add(car['carClass'])

                if car_classes:
                    pre_race_info.append(f"Car Classes: {', '.join(sorted(car_classes))}")

            # Only proceed if we have enough information
            if len(pre_race_info) > 0:
                # Join all information with separators
                info_string = " | ".join(pre_race_info)

                # Log the pre-race information
                self.log_event(f"Pre-Race Information: {info_string}")
                return True
            else:
                self.output_signal.emit("Waiting for more race information...")
                return False

        except Exception as e:
            self.output_signal.emit(f"Error collecting pre-race information: {str(e)}")
            return False

    def stop(self):
        self.running = False
        self.stop_client()
        self.output_signal.emit("Data collection stopped.")

    def setup_client(self):
        self.client.onRealtimeUpdate.subscribe(self.on_realtime_update)
        self.client.onRealtimeCarUpdate.subscribe(self.on_realtime_car_update)
        self.client.onEntryListCarUpdate.subscribe(self.on_entry_list_car_update)
        self.client.onBroadcastingEvent.subscribe(self.on_broadcasting_event)
        self.client.onTrackDataUpdate.subscribe(self.on_track_data_update)

    def start_client(self):
        self.client.start(
            url="localhost",
            port=9000,
            password="asd",
            commandPassword="",
            displayName="Python ACC Data Collector",
            updateIntervalMs=500
        )

    def stop_client(self):
        if self.client.isAlive:
            self.client.stop()

    def on_realtime_update(self, event):
        update = event.content
        self.session_info = {
            "sessionType": update.sessionType,
            "sessionPhase": update.sessionPhase,
        }
        self.session_time_ms = update.sessionTimeMs

        if not self.initialization_complete:
            if update.sessionType == "Race" and update.sessionPhase != "Pre Session":
                self.initialization_complete = True
                if self.session_time_ms == 0:
                    self.output_signal.emit("Waiting for the race to start.")
                else:
                    self.output_signal.emit(
                        f"Joined ongoing race. Current session time: {self.format_session_time(self.session_time_ms)}"
                    )

        # Detect race start
        if not self.race_started and update.sessionType == "Race" and update.sessionPhase == "Session":
            self.race_started = True
            self.race_start_time = datetime.now() - timedelta(milliseconds=self.session_time_ms)
            self.log_event("The Race Begins!")

        # Periodic position displays
        if self.race_started and not self.final_lap_phase:
            elapsed_time = self.session_time_ms / 1000
            if elapsed_time >= 240 and (elapsed_time - self.last_position_display) >= 240:
                self.display_positions()
                self.last_position_display = elapsed_time

        # Detect final lap
        if update.sessionPhase == "Session Over" and not self.final_lap_phase:
            self.final_lap_phase = True
            self.log_event("Leader is on final lap")

        # If in final lap, check when the leader actually finishes
        if self.final_lap_phase and not self.leader_finished:
            self.check_race_finish()

    def on_track_data_update(self, event):
        track_data = event.content
        self.track_name = track_data.trackName
        self.track_data = track_data
        # Load corner data after receiving track name
        self.load_corner_data()

    def load_corner_data(self):
        # Load corner data from the CornerData folder based on the track name
        corner_data_folder = "CornerData"
        corner_file_name = f"{self.track_name}.json"
        corner_file_path = os.path.join(corner_data_folder, corner_file_name)

        if os.path.exists(corner_file_path):
            with open(corner_file_path, 'r') as f:
                self.corner_data = json.load(f)
            self.output_signal.emit(f"Loaded corner data for track: {self.track_name}")
        else:
            self.output_signal.emit(f"No corner data found for track: {self.track_name}. Overtake locations will not include corner names.")

    def on_realtime_car_update(self, event):
        car = event.content

        # Initialize the dictionary for this car if needed
        if car.carIndex not in self.cars:
            self.cars[car.carIndex] = {
                'carIndex': car.carIndex,
                'previous_spline': 0,
                'laps': 0
            }

        current_car = self.cars[car.carIndex]
        current_car.update({
            'position': car.position,
            'driverName': current_car.get('driverName', f'Car {car.carIndex}'),
            'laps': car.laps,  # We'll still store it, but won't use it for adjusted_progress
            'splinePosition': car.splinePosition,
            'location': car.location,
        })

        # -------------------------------
        # CUSTOM LAP DETECTION LOGIC
        # -------------------------------
        if car.carIndex not in self.custom_laps:
            # Initialize custom lap counters and flags
            skip_first = (car.splinePosition >= self.UPPER_THRESHOLD)
            self.custom_laps[car.carIndex] = {
                'lap_count': 0,
                'last_spline': None,
                'skip_first_crossing': skip_first,
                'just_crossed_line': False
            }

        custom_car = self.custom_laps[car.carIndex]
        last_spline = custom_car['last_spline']
        current_spline = car.splinePosition

        if last_spline is not None:
            # Has the car gone from >= UPPER_THRESHOLD down to <= LOWER_THRESHOLD?
            if last_spline >= self.UPPER_THRESHOLD and current_spline <= self.LOWER_THRESHOLD:
                # Only increment if we haven't already counted it
                if not custom_car['just_crossed_line']:
                    if custom_car['skip_first_crossing']:
                        # Skip this one time
                        custom_car['skip_first_crossing'] = False
                    else:
                        custom_car['lap_count'] += 1
                    # Mark that we've accounted for this crossing
                    custom_car['just_crossed_line'] = True

        # If the car is now above LOWER_THRESHOLD, reset the just_crossed_line flag
        if current_spline > self.LOWER_THRESHOLD:
            custom_car['just_crossed_line'] = False

        # Update last_spline
        custom_car['last_spline'] = current_spline

        # -------------------------------
        # Use OUR lap_count for adjusted progress
        # -------------------------------
        adjusted_progress = custom_car['lap_count'] + current_spline
        current_car['adjusted_progress'] = adjusted_progress

        # -------------------------------
        # Store spline data for each cycle
        # -------------------------------
        self.spline_data.append({
            'sessionTime': self.session_time_ms,
            'carIndex': car.carIndex,
            'splinePosition': current_spline,
            'laps': car.laps  # from ACC, just for reference
        })

        # Pit entry/exit logging
        if car.carIndex not in self.finished_cars:
            if car.location in ["Pitlane", "Pit Entry"] and car.carIndex not in self.cars_in_pits:
                self.cars_in_pits.add(car.carIndex)
                driver_name = current_car.get('driverName', f"Car {car.carIndex}")
                self.log_event(f"{driver_name} has entered the pits.")
            elif car.location not in ["Pitlane", "Pit Entry"] and car.carIndex in self.cars_in_pits:
                self.cars_in_pits.remove(car.carIndex)
                driver_name = current_car.get('driverName', f"Car {car.carIndex}")
                self.log_event(f"{driver_name} has exited the pits.")

        # -------------------------------
        # CHECK IF A CAR HAS FINISHED AFTER THE LEADER
        # -------------------------------
        # Once leader_finished == True, the checkered is out for everyone.
        # Any car crossing the line (just_crossed_line=True) that is not yet finished is deemed finished.
        if self.leader_finished:
            if custom_car['just_crossed_line'] and car.carIndex not in self.finished_cars:
                # Mark this car as finished and announce final position
                sorted_cars = self.get_sorted_cars()
                # Find the position of the finishing car
                finish_position = None
                for i, c in enumerate(sorted_cars, start=1):
                    if c['carIndex'] == car.carIndex:
                        finish_position = i
                        break
                driver_name = current_car.get('driverName', f"Car {car.carIndex}")
                self.log_event(f"{driver_name} has finished in position {finish_position}.")
                self.finished_cars.add(car.carIndex)

    def on_entry_list_car_update(self, event):
        car = event.content
        if car.carIndex not in self.cars:
            self.cars[car.carIndex] = {
                'carIndex': car.carIndex,
                'previous_spline': 0,
                'laps': 0
            }
        if car.drivers:
            driver = car.drivers[0]
            self.cars[car.carIndex]['driverName'] = f"{driver.firstName} {driver.lastName}"
            self.cars[car.carIndex]['driverSurname'] = driver.lastName
            self.cars[car.carIndex]['nationality'] = driver.nationality

    def on_broadcasting_event(self, event):
        event_content = event.content
        event_type = event_content.type
        if event_type == "Session Over":
            self.log_event("Leader is on final lap")
            self.final_lap_phase = True
        elif event_type == "Accident":
            accident_time = self.format_session_time(self.session_time_ms)
            car_index = event_content.carIndex

            if car_index not in self.finished_cars:
                try:
                    driver = self.cars[car_index].get('driverName', f'Car {car_index}')
                except KeyError:
                    driver = f'Unknown Car {car_index}'

                if accident_time not in self.current_accidents:
                    self.current_accidents[accident_time] = []

                self.current_accidents[accident_time].append(driver)

    def check_race_finish(self):
        """
        Called after 'Leader is on final lap' to detect exactly when
        the leader crosses the line for the final time.
        """
        sorted_cars = self.get_sorted_cars()
        leader = sorted_cars[0]
        # Using ACC's laps + splinePosition to detect the checkered
        if leader['splinePosition'] > 0.99 and not self.leader_finished:
            self.leader_finished = True
            self.total_laps = leader['laps']
            self.log_event(f"Checkered flag! {leader['driverName']} takes the win!")
            # Now, each subsequent car is flagged as it crosses the line in on_realtime_car_update()

    def get_sorted_cars(self):
        """
        Sort the cars by our custom adjusted_progress. The highest progress is P1.
        """
        return sorted(self.cars.values(), key=lambda x: -x.get('adjusted_progress', 0))

    def get_qualifying_order(self):
        return sorted(self.cars.values(), key=lambda x: x.get('position', float('inf')))

    def report_qualifying_results(self):
        qualifying_order = self.get_qualifying_order()
        result_string = "Qualifying results: " + ", ".join(
            f"(P{car.get('position', i+1)}) {car.get('driverName', f'Car {car['carIndex']}')} ({car.get('nationality', 'Unknown')})"
            for i, car in enumerate(qualifying_order)
        )
        self.log_event(result_string)

    def display_positions(self):
        """
        Display the current (or qualifying) positions in the log.
        Before the race starts -> 'Qualifying positions',
        After the race starts -> 'Current positions'.
        """
        sorted_cars = self.get_sorted_cars()
        positions = []
        for position, car in enumerate(sorted_cars, start=1):
            if car['carIndex'] not in self.finished_cars:
                driver_name = car.get('driverName', f"Car {car['carIndex']}")
                positions.append(f"(P{position}) {driver_name}")

        if not self.race_started:
            title = "Qualifying positions"
        else:
            title = "Current positions"

        position_string = f"{title}: " + ", ".join(positions)
        self.log_event(position_string)

    def update_race_data(self):
        """
        Called periodically while the race is ongoing.
        Detect overtakes and process accidents.
        """
        sorted_cars = self.get_sorted_cars()

        # Build current_positions (1-based) for non-finished, non-pitting cars
        current_positions = {
            car['carIndex']: i+1
            for i, car in enumerate(sorted_cars)
            if car['carIndex'] not in self.cars_in_pits and car['carIndex'] not in self.finished_cars
        }

        # Build current_progress from our custom adjusted_progress
        current_progress = {car['carIndex']: car['adjusted_progress'] for car in sorted_cars}

        # Only detect overtakes after 15 seconds to prevent false positives at the start
        overtakes = self.detect_overtakes(current_positions, current_progress) if self.session_time_ms >= 15000 else []

        self.previous_positions = current_positions
        self.previous_progress = current_progress

        # Announce overtakes
        for overtake in overtakes:
            self.log_event(overtake)

        # Announce accidents
        accidents = self.current_accidents
        self.current_accidents = {}  # Clear after processing
        for accident_time, drivers in accidents.items():
            drivers_str = ", ".join(drivers)
            self.log_event(f"Accident involving: {drivers_str}")

    def detect_overtakes(self, current_positions, current_progress):
        """
        Compare current positions/progress vs previous to detect overtakes.
        Also detect if an overtake is actually lapping.
        """
        overtakes = []
        if not self.previous_positions or not self.race_started:
            return overtakes

        for car_index, current_pos in current_positions.items():
            if car_index in self.previous_positions and car_index not in self.finished_cars:
                previous_pos = self.previous_positions[car_index]
                # If current position < previous position, they've moved up
                if current_pos < previous_pos:
                    try:
                        overtaker = self.cars[car_index].get('driverName', f"Car {car_index}")
                    except KeyError:
                        overtaker = f"Unknown Car {car_index}"

                    # Figure out who was overtaken (someone at position = current_pos + 1)
                    for other_index, other_pos in current_positions.items():
                        if other_index != car_index and other_index not in self.finished_cars:
                            if other_pos == current_pos + 1:
                                # Check if we truly passed them (based on adjusted_progress)
                                prev_overtaker_prog = self.previous_progress.get(car_index, 0)
                                prev_overtaken_prog = self.previous_progress.get(other_index, 0)
                                cur_overtaker_prog = current_progress.get(car_index, 0)
                                cur_overtaken_prog = current_progress.get(other_index, 0)

                                if prev_overtaker_prog < prev_overtaken_prog and cur_overtaker_prog > cur_overtaken_prog:
                                    try:
                                        overtaken = self.cars[other_index].get('driverName', f"Car {other_index}")
                                    except KeyError:
                                        overtaken = f"Unknown Car {other_index}"

                                    # Determine the corner name
                                    corner_name = self.get_corner_name(cur_overtaker_prog % 1)

                                    # Check if it's actually a lapping pass
                                    overtaker_lap_count = self.custom_laps[car_index]['lap_count']
                                    overtaken_lap_count = self.custom_laps[other_index]['lap_count']

                                    if overtaker_lap_count > overtaken_lap_count:
                                        # Lapping pass
                                        overtake_message = f"Overtake! {overtaker} overtook {overtaken} who is being lapped"
                                    else:
                                        overtake_message = f"Overtake! {overtaker} overtook {overtaken} for position {current_pos}"

                                    if corner_name:
                                        overtake_message += f" at {corner_name}."
                                    else:
                                        overtake_message += "."

                                    overtakes.append(overtake_message)
            else:
                # This car wasn't in previous_positions or just started
                continue

        return overtakes

    def get_corner_name(self, spline_position):
        """
        Find which corner (if any) the given spline_position is in,
        based on self.corner_data.
        """
        if not self.corner_data:
            return None  # No corner data available

        for corner in self.corner_data:
            start = corner['start']
            end = corner['end']
            # Normal range corner
            if start <= end:
                if start <= spline_position <= end:
                    return corner['name']
            else:
                # The corner wraps around 1.0 -> 0.0
                if spline_position >= start or spline_position <= end:
                    return corner['name']

        return None  # No matching corner found

    def format_session_time(self, milliseconds):
        seconds = int(milliseconds // 1000)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"

    def setup_output_file(self):
        if not os.path.exists("Race Data"):
            os.makedirs("Race Data")

        start_time = datetime.now()
        filename = start_time.strftime("%Y-%m-%d_%H-%M-%S") + ".txt"
        self.output_file = os.path.join("Race Data", filename)

        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(f"Race data collection started at: {start_time}\n\n")

    def log_event(self, event):
        formatted_time = self.format_session_time(self.session_time_ms)
        log_message = f"{formatted_time} - {event}"

        self.output_signal.emit(log_message)

        if self.output_file:
            try:
                with open(self.output_file, 'a', encoding='utf-8') as f:
                    f.write(log_message + '\n')
            except UnicodeEncodeError:
                # If there's an encoding issue, replace bad chars
                with open(self.output_file, 'a', encoding='utf-8', errors='replace') as f:
                    f.write(log_message + '\n')

    def save_spline_data(self):
        spline_file = os.path.join("Race Data", "spline_data.json")
        with open(spline_file, 'w') as f:
            json.dump(self.spline_data, f)
        self.output_signal.emit(f"Spline data saved to {spline_file}")

    def get_output_file_path(self):
        return self.output_file
