import sys
import os
import ctypes
from PyQt5.QtCore import QThread, pyqtSignal
from datetime import datetime, timedelta
import json
import threading

class SPageFilePhysics(ctypes.Structure):
    _fields_ = [
        ('packetId', ctypes.c_int),
        ('gas', ctypes.c_float),
        ('brake', ctypes.c_float),
        ('fuel', ctypes.c_float),
        ('gear', ctypes.c_int),
        ('rpms', ctypes.c_int),
        ('steerAngle', ctypes.c_float),
        ('speedKmh', ctypes.c_float),
        ('velocity', ctypes.c_float * 3),
        ('accG', ctypes.c_float * 3),
        ('wheelSlip', ctypes.c_float * 4),
        ('wheelLoad', ctypes.c_float * 4),
        ('wheelsPressure', ctypes.c_float * 4),
        ('wheelAngularSpeed', ctypes.c_float * 4),
        ('tyreWear', ctypes.c_float * 4),
        ('tyreDirtyLevel', ctypes.c_float * 4),
        ('tyreCoreTemperature', ctypes.c_float * 4),
        ('camberRAD', ctypes.c_float * 4),
        ('suspensionTravel', ctypes.c_float * 4),
        ('drs', ctypes.c_float),
        ('tc', ctypes.c_float),
        ('heading', ctypes.c_float),
        ('pitch', ctypes.c_float),
        ('roll', ctypes.c_float),
        ('cgHeight', ctypes.c_float),
        ('carDamage', ctypes.c_float * 5),
        ('numberOfTyresOut', ctypes.c_int),
        ('pitLimiterOn', ctypes.c_int),
        ('abs', ctypes.c_float),
        ('kersCharge', ctypes.c_float),
        ('kersInput', ctypes.c_float),
        ('autoShifterOn', ctypes.c_int),
        ('rideHeight', ctypes.c_float * 2),
        ('turboBoost', ctypes.c_float),
        ('ballast', ctypes.c_float),
        ('airDensity', ctypes.c_float),
        ('airTemp', ctypes.c_float),
        ('roadTemp', ctypes.c_float),
        ('localAngularVel', ctypes.c_float * 3),
        ('finalFF', ctypes.c_float),
        ('performanceMeter', ctypes.c_float),
        ('engineBrake', ctypes.c_int),
        ('ersRecoveryLevel', ctypes.c_int),
        ('ersPowerLevel', ctypes.c_int),
        ('ersHeatCharging', ctypes.c_int),
        ('ersIsCharging', ctypes.c_int),
        ('kersCurrentKJ', ctypes.c_float),
        ('drsAvailable', ctypes.c_int),
        ('drsEnabled', ctypes.c_int),
        ('brakeTemp', ctypes.c_float * 4),
        ('clutch', ctypes.c_float),
        ('tyreTempI', ctypes.c_float * 4),
        ('tyreTempM', ctypes.c_float * 4),
        ('tyreTempO', ctypes.c_float * 4),
        ('isAIControlled', ctypes.c_int),
        ('tyreContactPoint', (ctypes.c_float * 3) * 4),
        ('tyreContactNormal', (ctypes.c_float * 3) * 4),
        ('tyreContactHeading', (ctypes.c_float * 3) * 4),
        ('brakeBias', ctypes.c_float),
        ('localVelocity', ctypes.c_float * 3),
    ]

class SPageFileGraphic(ctypes.Structure):
    _fields_ = [
        ('packetId', ctypes.c_int),
        ('status', ctypes.c_int),
        ('session', ctypes.c_int),
        ('currentTime', ctypes.c_wchar * 15),
        ('lastTime', ctypes.c_wchar * 15),
        ('bestTime', ctypes.c_wchar * 15),
        ('split', ctypes.c_wchar * 15),
        ('completedLaps', ctypes.c_int),
        ('position', ctypes.c_int),
        ('iCurrentTime', ctypes.c_int),
        ('iLastTime', ctypes.c_int),
        ('iBestTime', ctypes.c_int),
        ('sessionTimeLeft', ctypes.c_float),
        ('distanceTraveled', ctypes.c_float),
        ('isInPit', ctypes.c_int),
        ('currentSectorIndex', ctypes.c_int),
        ('lastSectorTime', ctypes.c_int),
        ('numberOfLaps', ctypes.c_int),
        ('tyreCompound', ctypes.c_wchar * 33),
        ('replayTimeMultiplier', ctypes.c_float),
        ('normalizedCarPosition', ctypes.c_float),
        ('carCoordinates', ctypes.c_float * 3),
        ('penaltyTime', ctypes.c_float),
        ('flag', ctypes.c_int),
        ('idealLineOn', ctypes.c_int),
        ('isInPitLane', ctypes.c_int),
        ('surfaceGrip', ctypes.c_float),
        ('mandatoryPitDone', ctypes.c_int),
        ('windSpeed', ctypes.c_float),
        ('windDirection', ctypes.c_float),
        ('isSetupMenuVisible', ctypes.c_int),
        ('mainDisplayIndex', ctypes.c_int),
        ('secondaryDisplayIndex', ctypes.c_int),
        ('TC', ctypes.c_int),
        ('TCCut', ctypes.c_int),
        ('EngineMap', ctypes.c_int),
        ('ABS', ctypes.c_int),
        ('fuelXLap', ctypes.c_float),
        ('rainLights', ctypes.c_int),
        ('flashingLights', ctypes.c_int),
        ('lightsStage', ctypes.c_int),
        ('exhaustTemperature', ctypes.c_float),
        ('wiperLV', ctypes.c_int),
        ('DriverStintTotalTimeLeft', ctypes.c_int),
        ('DriverStintTimeLeft', ctypes.c_int),
        ('rainTyres', ctypes.c_int),
        ('sessionIndex', ctypes.c_int),
        ('usedFuel', ctypes.c_float),
        ('deltaLapTime', ctypes.c_wchar * 15),
        ('iDeltaLapTime', ctypes.c_int),
        ('estimatedLapTime', ctypes.c_wchar * 15),
        ('iEstimatedLapTime', ctypes.c_int),
        ('isDeltaPositive', ctypes.c_int),
        ('iSplit', ctypes.c_int),
        ('isValidLap', ctypes.c_int),
        ('fuelEstimatedLaps', ctypes.c_float),
        ('trackStatus', ctypes.c_wchar * 33),
        ('missingMandatoryPits', ctypes.c_int),
        ('Clock', ctypes.c_float),
        ('directionLightsLeft', ctypes.c_int),
        ('directionLightsRight', ctypes.c_int),
        ('globalYellow', ctypes.c_int),
        ('globalYellow1', ctypes.c_int),
        ('globalYellow2', ctypes.c_int),
        ('globalYellow3', ctypes.c_int),
        ('globalWhite', ctypes.c_int),
        ('globalGreen', ctypes.c_int),
        ('globalChequered', ctypes.c_int),
        ('globalRed', ctypes.c_int),
        ('mfdTyreSet', ctypes.c_int),
        ('mfdFuelToAdd', ctypes.c_float),
        ('mfdTyrePressureLF', ctypes.c_float),
        ('mfdTyrePressureRF', ctypes.c_float),
        ('mfdTyrePressureLR', ctypes.c_float),
        ('mfdTyrePressureRR', ctypes.c_float),
        ('trackGripStatus', ctypes.c_int),
        ('rainIntensity', ctypes.c_int),
        ('rainIntensityIn10min', ctypes.c_int),
        ('rainIntensityIn30min', ctypes.c_int),
        ('currentTyreSet', ctypes.c_int),
        ('strategyTyreSet', ctypes.c_int),
    ]

class SPageFileStatic(ctypes.Structure):
    _fields_ = [
        ('smVersion', ctypes.c_wchar * 15),
        ('acVersion', ctypes.c_wchar * 15),
        ('numberOfSessions', ctypes.c_int),
        ('numCars', ctypes.c_int),
        ('carModel', ctypes.c_wchar * 33),
        ('track', ctypes.c_wchar * 33),
        ('playerName', ctypes.c_wchar * 33),
        ('playerSurname', ctypes.c_wchar * 33),
        ('playerNick', ctypes.c_wchar * 33),
        ('sectorCount', ctypes.c_int),
        ('maxTorque', ctypes.c_float),
        ('maxPower', ctypes.c_float),
        ('maxRpm', ctypes.c_int),
        ('maxFuel', ctypes.c_float),
        ('suspensionMaxTravel', ctypes.c_float * 4),
        ('tyreRadius', ctypes.c_float * 4),
        ('maxTurboBoost', ctypes.c_float),
        ('deprecated_1', ctypes.c_float),
        ('deprecated_2', ctypes.c_float),
        ('penaltiesEnabled', ctypes.c_int),
        ('aidFuelRate', ctypes.c_float),
        ('aidTireRate', ctypes.c_float),
        ('aidMechanicalDamage', ctypes.c_float),
        ('aidAllowTyreBlankets', ctypes.c_int),
        ('aidStability', ctypes.c_float),
        ('aidAutoClutch', ctypes.c_int),
        ('aidAutoBlip', ctypes.c_int),
        ('hasDRS', ctypes.c_int),
        ('hasERS', ctypes.c_int),
        ('hasKERS', ctypes.c_int),
        ('kersMaxJ', ctypes.c_float),
        ('engineBrakeSettingsCount', ctypes.c_int),
        ('ersPowerControllerCount', ctypes.c_int),
        ('trackSPlineLength', ctypes.c_float),
        ('trackConfiguration', ctypes.c_wchar * 33),
        ('ersMaxJ', ctypes.c_float),
        ('isTimedRace', ctypes.c_int),
        ('hasExtraLap', ctypes.c_int),
        ('carSkin', ctypes.c_wchar * 33),
        ('reversedGridPositions', ctypes.c_int),
        ('PitWindowStart', ctypes.c_int),
        ('PitWindowEnd', ctypes.c_int),
        ('isOnline', ctypes.c_int),
        ('dryTyresName', ctypes.c_wchar * 33),
        ('wetTyresName', ctypes.c_wchar * 33),
    ]

class DataCollector(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.running = False
        self.cars = {}
        self.session_info = {}
        self.last_update_time = 0
        self.update_interval = 4
        self.previous_positions = {}
        self.previous_progress = {}
        self.race_started = False
        self.session_time_ms = 0
        self.race_start_time = None
        self.current_accidents = {}
        self.initialization_complete = False
        self.output_file = None
        self.cars_in_pits = set()
        self.last_position_display = 0
        self.final_lap_phase = False
        self.finished_cars = set()
        self.leader_finished = False
        self.leader_car_index = None
        self.total_laps = None
        self.start_line_crossed = set()
        self.qualifying_reported = False
        self.spline_data = []
        self.track_name = "Unknown"
        self.corner_data = []
        self.graphics = None
        self.physics = None
        self.static = None
        self.lock = threading.Lock()

    def run(self):
        self.running = True
        self.setup_shared_memory()

        self.output_signal.emit("Initializing data collection...")

        # Wait until initialization is complete
        while not self.initialization_complete and self.running:
            self.read_shared_memory()
            self.msleep(500)

        if self.initialization_complete:
            self.setup_output_file()
            self.output_signal.emit(f"Data collection initialized for track: {self.track_name}. Starting race monitoring...")

            # Load corner data for the track
            self.load_corner_data()

            # Display the leaderboard as soon as we have the necessary data
            self.display_positions()

        while self.running:
            self.read_shared_memory()
            self.msleep(self.update_interval * 1000)
            if self.race_started:
                self.update_race_data()

        # Save spline data to a JSON file when the race ends
        self.save_spline_data()

    def stop(self):
        self.running = False
        self.output_signal.emit("Data collection stopped.")

    def setup_shared_memory(self):
        # Access the shared memory
        try:
            self.graphics = self.map_shared_memory("Local\\acpmf_graphics", SPageFileGraphic)
            self.physics = self.map_shared_memory("Local\\acpmf_physics", SPageFilePhysics)
            self.static = self.map_shared_memory("Local\\acpmf_static", SPageFileStatic)
            self.initialization_complete = True
        except Exception as e:
            self.output_signal.emit(f"Error accessing shared memory: {e}")
            self.initialization_complete = False

    def map_shared_memory(self, name, data_type):
        # Map the shared memory and return a ctypes object
        FILE_MAP_READ = 0x0004
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
        PAGE_READONLY = 0x02

        kernel32 = ctypes.windll.kernel32
        OpenFileMapping = kernel32.OpenFileMappingW
        OpenFileMapping.restype = ctypes.c_void_p
        MapViewOfFile = kernel32.MapViewOfFile
        MapViewOfFile.restype = ctypes.c_void_p

        file_handle = OpenFileMapping(FILE_MAP_READ, False, name)
        if file_handle == 0:
            raise Exception(f"Could not open file mapping: {name}")

        map_ptr = MapViewOfFile(file_handle, FILE_MAP_READ, 0, 0, ctypes.sizeof(data_type))
        if map_ptr == 0:
            raise Exception(f"Could not map view of file: {name}")

        return data_type.from_address(map_ptr)

    def read_shared_memory(self):
        with self.lock:
            if self.graphics is None or self.physics is None or self.static is None:
                return

            # Read session info
            self.session_info = {
                "sessionType": self.graphics.session,
                "sessionPhase": self.graphics.status,
            }
            self.session_time_ms = self.graphics.iCurrentTime  # Already in milliseconds

            if not self.race_started and self.graphics.status == 2 and self.graphics.session == 2:
                self.race_started = True
                self.race_start_time = datetime.now() - timedelta(milliseconds=self.session_time_ms)
                self.log_event("The Race Begins!")

            if self.race_started and not self.final_lap_phase:
                elapsed_time = self.session_time_ms / 1000
                if elapsed_time >= 240 and (elapsed_time - self.last_position_display) >= 240:
                    self.display_positions()
                    self.last_position_display = elapsed_time

            # Read track name
            self.track_name = self.static.track
            # Load corner data after receiving track name
            self.load_corner_data()

            # Update cars data
            self.update_cars_data()

    def load_corner_data(self):
        # Load corner data from the CornerData folder based on the track name
        if self.corner_data:
            return  # Already loaded

        corner_data_folder = "CornerData"
        corner_file_name = f"{self.track_name}.json"
        corner_file_path = os.path.join(corner_data_folder, corner_file_name)

        if os.path.exists(corner_file_path):
            with open(corner_file_path, 'r') as f:
                self.corner_data = json.load(f)
            self.output_signal.emit(f"Loaded corner data for track: {self.track_name}")
        else:
            self.output_signal.emit(f"No corner data found for track: {self.track_name}. Overtake locations will not include corner names.")

    def update_cars_data(self):
        # Update cars data from shared memory
        car_index = 0  # Assetto Corsa only provides data for the player's car in shared memory
        if car_index not in self.cars:
            self.cars[car_index] = {'carIndex': car_index, 'previous_spline': 0, 'laps': 0}

        current_car = self.cars[car_index]
        current_car.update({
            'position': self.graphics.position,
            'driverName': self.static.playerName,
            'laps': self.graphics.completedLaps,
            'splinePosition': self.graphics.normalizedCarPosition,
            'location': 'Track' if not self.graphics.isInPitLane else 'Pitlane',
        })

        # Calculate adjusted progress
        current_car['adjusted_progress'] = current_car.get('laps', 0) + current_car.get('splinePosition', 0)

        # Store spline data for each update cycle
        self.spline_data.append({
            'sessionTime': self.session_time_ms,
            'carIndex': car_index,
            'splinePosition': self.graphics.normalizedCarPosition,
            'laps': self.graphics.completedLaps,
        })

        # Pit entry/exit logging
        if car_index not in self.finished_cars:
            if current_car['location'] == "Pitlane" and car_index not in self.cars_in_pits:
                self.cars_in_pits.add(car_index)
                driver_name = current_car.get('driverName', f"Car {car_index}")
                self.log_event(f"{driver_name} has entered the pits.")
            elif current_car['location'] != "Pitlane" and car_index in self.cars_in_pits:
                self.cars_in_pits.remove(car_index)
                driver_name = current_car.get('driverName', f"Car {car_index}")
                self.log_event(f"{driver_name} has exited the pits.")

    def update_race_data(self):
        sorted_cars = self.get_sorted_cars()

        current_positions = {car['carIndex']: i+1 for i, car in enumerate(sorted_cars) if car['carIndex'] not in self.cars_in_pits and car['carIndex'] not in self.finished_cars}

        current_progress = {car['carIndex']: car['adjusted_progress'] for car in sorted_cars}

        overtakes = self.detect_overtakes(current_positions, current_progress) if self.session_time_ms >= 15000 else []

        self.previous_positions = current_positions
        self.previous_progress = current_progress

        for overtake in overtakes:
            self.log_event(overtake)

        # Accidents detection would need to be implemented based on available data
        # For now, we will skip this part due to limitations in shared memory data

    def get_sorted_cars(self):
        # Since Assetto Corsa shared memory provides data for the player's car only,
        # we cannot get data for other cars directly.
        # For demonstration, we'll just return the player's car.
        return sorted(self.cars.values(), key=lambda x: -x.get('adjusted_progress', 0))

    def display_positions(self):
        sorted_cars = self.get_sorted_cars()
        positions = []
        for position, car in enumerate(sorted_cars, start=1):
            if car['carIndex'] not in self.finished_cars:
                driver_name = car.get('driverName', f"Car {car['carIndex']}")
                positions.append(f"(P{position}) {driver_name}")
        position_string = "Current positions: " + ", ".join(positions)
        self.log_event(position_string)

    def detect_overtakes(self, current_positions, current_progress):
        overtakes = []
        if not self.previous_positions or not self.race_started:
            return overtakes

        for car_index, current_pos in current_positions.items():
            if car_index in self.previous_positions and car_index not in self.finished_cars:
                previous_pos = self.previous_positions[car_index]
                if current_pos < previous_pos:
                    overtaker = self.cars[car_index].get('driverName', f"Car {car_index}")

                    # Since we have no data about other cars, we cannot identify who was overtaken
                    overtake_message = f"Overtake! {overtaker} moved up to position {current_pos}"
                    overtakes.append(overtake_message)
            else:
                continue
        return overtakes

    def get_corner_name(self, spline_position):
        if not self.corner_data:
            return None  # No corner data available

        for corner in self.corner_data:
            start = corner['start']
            end = corner['end']
            # Handle cases where end < start due to track loop (e.g., end of lap)
            if start <= end:
                if start <= spline_position <= end:
                    return corner['name']
            else:
                # The corner wraps around the end/start line
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
                with open(self.output_file, 'a', encoding='utf-8', errors='replace') as f:
                    f.write(log_message + '\n')

    def save_spline_data(self):
        spline_file = os.path.join("Race Data", "spline_data.json")
        with open(spline_file, 'w') as f:
            json.dump(self.spline_data, f)
        self.output_signal.emit(f"Spline data saved to {spline_file}")

    def get_output_file_path(self):
        return self.output_file
