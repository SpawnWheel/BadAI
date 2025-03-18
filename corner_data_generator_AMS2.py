def process_participant_data(self, data):
    """Processes the data for each participant with enhanced commentary-friendly information."""
    if self.previous_race_state != data.mRaceState:
        if data.mRaceState == RACESTATE_NOT_STARTED:
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

    if self.initial_event_time_remaining is None and data.mEventTimeRemaining > 0:
        self.initial_event_time_remaining = data.mEventTimeRemaining

    if self.race_start_system_time is not None:
        session_time_elapsed = time.time() - self.race_start_system_time
    else:
        session_time_elapsed = 0

    # Collect track/weather information at the beginning
    if not self.race_started and not hasattr(self, 'environment_info_logged'):
        track_location = data.mTrackLocation.decode('utf-8').strip('\x00')
        track_variation = data.mTrackVariation.decode('utf-8').strip('\x00')

        # Log weather conditions for better commentary context
        weather_info = f"Track: {track_location} {track_variation} | "
        weather_info += f"Conditions: {data.mRainDensity * 100:.0f}% rain, "
        weather_info += f"Air: {data.mAmbientTemperature:.1f}°C, Track: {data.mTrackTemperature:.1f}°C"

        if data.mWindSpeed > 0:
            direction = self._get_wind_direction(data.mWindDirectionX, data.mWindDirectionY)
            weather_info += f", Wind: {data.mWindSpeed:.1f} km/h {direction}"

        self.log_event(f"Race information: {weather_info}")
        self.environment_info_logged = True

    # Output qualifying positions before race starts
    if not self.race_started and not hasattr(self, 'qualifying_positions_output'):
        if data.mNumParticipants > 0:
            # Include car classes in qualifying output
            participants = []
            for i in range(data.mNumParticipants):
                participant_data = data.mParticipantInfo[i]
                if participant_data.mIsActive:
                    participant_name = participant_data.mName.decode('utf-8').strip('\x00')
                    car_name = data.mCarNames[i].decode('utf-8').strip('\x00')
                    car_class = data.mCarClassNames[i].decode('utf-8').strip('\x00')

                    if participant_name != "Safety Car":
                        position = participant_data.mRacePosition
                        participants.append((position, participant_name, car_name, car_class))

            participants.sort()

            # Group drivers by class for more organized presentation
            class_participants = {}
            for pos, name, car, car_class in participants:
                if car_class not in class_participants:
                    class_participants[car_class] = []
                class_participants[car_class].append((pos, name, car))

            # Log qualifying results by class
            for car_class, drivers in class_participants.items():
                participants_str = ", ".join([f"(P{pos}) {name} ({car})" for pos, name, car in drivers])
                self.log_event(f"Qualifying positions ({car_class}): {participants_str}")

            self.qualifying_positions_output = True

    if data.mRaceState == RACESTATE_RACING:
        if not self.race_started:
            self.race_start_system_time = time.time()
            session_time_elapsed = 0
            self.log_event("Race has started!")
            self.race_started = True
            self.last_leaderboard_time = session_time_elapsed

            # Log grid order at race start for drama/context
            self._log_starting_grid(data)
        else:
            session_time_elapsed = time.time() - self.race_start_system_time

    # Check race progress milestones for commentary
    if self.race_started and not self.race_completed:
        laps_in_event = data.mLapsInEvent
        if laps_in_event > 0 and not hasattr(self, 'race_progress_logged'):
            self.race_progress_logged = {}

        if hasattr(self, 'race_progress_logged'):
            # Find leader and their progress
            leader_index = None
            for i in range(data.mNumParticipants):
                if data.mParticipantInfo[i].mIsActive and data.mParticipantInfo[i].mRacePosition == 1:
                    leader_index = i
                    break

            if leader_index is not None:
                leader_lap = data.mParticipantInfo[leader_index].mCurrentLap

                # Log race progress milestones
                milestones = {
                    0.25: "quarter",
                    0.5: "halfway",
                    0.75: "three-quarters"
                }

                for fraction, name in milestones.items():
                    milestone_lap = int(laps_in_event * fraction)
                    if milestone_lap > 0 and leader_lap == milestone_lap and name not in self.race_progress_logged:
                        leader_name = data.mParticipantInfo[leader_index].mName.decode('utf-8').strip('\x00')
                        self.log_event(f"Race {name} complete! {leader_name} leads at lap {leader_lap}/{laps_in_event}")
                        self.race_progress_logged[name] = True

                # Log "X laps to go" for final few laps
                laps_remaining = laps_in_event - leader_lap
                if 1 <= laps_remaining <= 5 and f"laps_remaining_{laps_remaining}" not in self.race_progress_logged:
                    leader_name = data.mParticipantInfo[leader_index].mName.decode('utf-8').strip('\x00')
                    self.log_event(
                        f"{laps_remaining} {'lap' if laps_remaining == 1 else 'laps'} to go! {leader_name} leads the field")
                    self.race_progress_logged[f"laps_remaining_{laps_remaining}"] = True

    # Periodically log leaderboards during the race with more detailed info
    if not self.race_started:
        if session_time_elapsed - self.last_leaderboard_time >= 60:
            self._log_qualifying_positions(data, session_time_elapsed)
            self.last_leaderboard_time = session_time_elapsed
    elif self.race_started and not self.race_completed:
        if session_time_elapsed - self.last_leaderboard_time >= 4 * 60:
            self._log_race_positions(data, session_time_elapsed)
            self.last_leaderboard_time = session_time_elapsed

    if self.race_started and data.mRaceState == RACESTATE_FINISHED and not self.race_completed:
        self.log_event("Race has been completed.")
        self.race_completed = True

    current_positions = {}
    position_to_name = {}
    active_participants = {}
    lap_time_data = {}

    # Gap calculations for positions
    previous_lap_distance = None
    previous_lap = None
    previous_position = None

    # Process each participant
    for i in range(data.mNumParticipants):
        participant_data = data.mParticipantInfo[i]
        participant_name = participant_data.mName.decode('utf-8').strip('\x00')

        if participant_data.mIsActive and participant_name != "Safety Car":
            # Store active participant data
            position = participant_data.mRacePosition
            current_lap = participant_data.mCurrentLap
            lap_distance = participant_data.mCurrentLapDistance

            active_participants[i] = {
                'name': participant_name,
                'position': position,
                'current_lap': current_lap,
                'lap_distance': lap_distance
            }

            current_positions[i] = position
            position_to_name[position] = participant_name

            # Store lap time data for potential fastest lap mentions
            if data.mFastestLapTimes[i] > 0:
                lap_time_data[participant_name] = {
                    'fastest_lap': data.mFastestLapTimes[i],
                    'last_lap': data.mLastLapTimes[i]
                }

            # Calculate gaps between cars - essential for commentary
            if previous_position is not None and position == previous_position + 1:
                # Calculate gap to car ahead
                if previous_lap == current_lap:
                    # Same lap - calculate distance gap
                    distance_gap = previous_lap_distance - lap_distance
                    if distance_gap > 0:
                        # Convert to time gap (approx)
                        if data.mSpeeds[i] > 0:  # Avoid division by zero
                            time_gap = distance_gap / (data.mSpeeds[i] / 3.6)  # Convert km/h to m/s
                            active_participants[i]['gap_ahead'] = f"{time_gap:.1f}s"
                else:
                    # Different lap - calculate lap gap
                    lap_gap = previous_lap - current_lap
                    active_participants[i]['gap_ahead'] = f"{lap_gap} lap{'s' if lap_gap > 1 else ''}"

            # Store for next iteration
            previous_lap_distance = lap_distance
            previous_lap = current_lap
            previous_position = position

            # Check finish status
            prev_finish_status = self.previous_finish_status.get(i, RACESTATE_INVALID)
            current_finish_status = data.mRaceStates[i]

            if current_finish_status != prev_finish_status:
                self.previous_finish_status[i] = current_finish_status
                if current_finish_status == RACESTATE_FINISHED and i not in self.finished_drivers:
                    race_position = participant_data.mRacePosition
                    self.race_finish_positions[participant_name] = race_position

                    if race_position == 1 and not self.race_winner:
                        self.race_winner = participant_name
                        # Add car name and total time for more detailed winner announcement
                        car_name = data.mCarNames[i].decode('utf-8').strip('\x00')
                        total_race_time = session_time_elapsed
                        hours = int(total_race_time // 3600)
                        minutes = int((total_race_time % 3600) // 60)
                        seconds = int(total_race_time % 60)
                        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                        self.log_event(
                            f"{participant_name} has won the race driving the {car_name} with a total time of {time_str}!")
                        if not self.race_completed:
                            self.race_completed = True
                            self.log_event("Race has been completed.")
                    else:
                        # More detailed position finish message
                        if self.race_winner:
                            car_name = data.mCarNames[i].decode('utf-8').strip('\x00')
                            self.log_event(
                                f"{participant_name} has finished the race in position {race_position} with the {car_name}")

                    self.finished_drivers.add(i)
                elif current_finish_status == RACESTATE_RETIRED or current_finish_status == RACESTATE_DNF:
                    # Log retirements and DNFs for commentary
                    status = "retired from" if current_finish_status == RACESTATE_RETIRED else "did not finish"
                    car_name = data.mCarNames[i].decode('utf-8').strip('\x00')
                    self.log_event(f"{participant_name} has {status} the race in the {car_name}")
                elif current_finish_status == RACESTATE_DISQUALIFIED:
                    self.log_event(f"{participant_name} has been disqualified from the race")

            # Get speed from shared memory
            speed_kph = data.mSpeeds[i]

            # Process pit stops - essential for race commentary
            current_pit_mode = data.mPitModes[i]
            prev_pit_mode = self.last_pit_latch.get(i, PIT_MODE_NONE)

            if current_pit_mode != prev_pit_mode:
                self.last_pit_latch[i] = current_pit_mode

                # Different pit status messages
                if current_pit_mode == PIT_MODE_DRIVING_INTO_PITS and prev_pit_mode in [PIT_MODE_NONE,
                                                                                        PIT_MODE_DRIVING_OUT_OF_PITS]:
                    self.log_event(f"{participant_name} is entering the pits from P{position}")
                elif current_pit_mode == PIT_MODE_IN_PIT and prev_pit_mode == PIT_MODE_DRIVING_INTO_PITS:
                    self.log_event(f"{participant_name} has reached the pit box")
                elif current_pit_mode == PIT_MODE_DRIVING_OUT_OF_PITS and prev_pit_mode in [PIT_MODE_IN_PIT,
                                                                                            PIT_MODE_IN_GARAGE]:
                    pit_schedule = data.mPitSchedules[i]
                    # Add context for pit stop reason
                    pit_reason = self._get_pit_stop_reason(pit_schedule)
                    self.log_event(f"{participant_name} is exiting the pits{pit_reason}")

            # Process accidents
            if self.race_started and not self.race_completed and data.mGameState == GAME_INGAME_PLAYING:
                # Check if car has stopped or significantly slowed down
                if speed_kph < self.speed_threshold:
                    if i not in self.stopped_cars:
                        self.stopped_cars[i] = {
                            'time': current_time,
                            'name': participant_name,
                            'reported': False,
                            'position': position,
                            'track_section': self._get_track_section(participant_data),
                            'car_name': data.mCarNames[i].decode('utf-8').strip('\x00')
                        }
                    elif not self.stopped_cars[i]['reported'] and \
                            (current_time - self.stopped_cars[i]['time']) >= self.time_threshold:
                        # Car has been stopped long enough to be considered an accident
                        self.pending_accidents.append({
                            'time': current_time,
                            'name': participant_name,
                            'position': position,
                            'track_section': self.stopped_cars[i]['track_section'],
                            'car_name': self.stopped_cars[i]['car_name']
                        })
                        self.stopped_cars[i]['reported'] = True
                else:
                    # Car is moving again, remove from stopped cars
                    if i in self.stopped_cars:
                        del self.stopped_cars[i]

            # Update previous distance and time
            current_lap = participant_data.mCurrentLap
            current_lap_distance = participant_data.mCurrentLapDistance
            lap_length = data.mTrackLength
            total_distance = current_lap * lap_length + current_lap_distance
            self.previous_distances[i] = total_distance
            self.previous_times[i] = session_time_elapsed

    # Check for fastest lap - important for race commentary
    self._check_fastest_laps(lap_time_data)

    # Process pending accidents
    if self.pending_accidents:
        # Group accidents that occurred within proximity_time of each other
        current_group = []
        self.pending_accidents.sort(key=lambda x: x['time'])

        for accident in self.pending_accidents:
            if not current_group or \
                    accident['time'] - current_group[0]['time'] <= self.proximity_time:
                current_group.append(accident)
            else:
                # Log the current group and start a new one
                self._log_accident_group(current_group)
                current_group = [accident]

        # Log any remaining accidents
        if current_group:
            self._log_accident_group(current_group)

        self.pending_accidents = []

    # Detect and log battles (cars within close range)
    self._detect_battles(active_participants, data)

    # Detect overtakes
    if session_time_elapsed - self.last_overtake_update >= 1.0 and session_time_elapsed >= 15:
        for driver_index, current_pos in current_positions.items():
            prev_pos = self.previous_positions.get(driver_index)
            if prev_pos is not None and prev_pos != current_pos:
                driver_name = active_participants[driver_index]['name']
                if current_pos < prev_pos:  # Gained position
                    for other_index, other_pos in current_positions.items():
                        if other_index != driver_index:
                            other_prev_pos = self.previous_positions.get(other_index)
                            if other_prev_pos is not None:
                                if other_prev_pos == current_pos and other_pos == prev_pos:
                                    other_name = active_participants[other_index]['name']
                                    driver_data = active_participants[driver_index]
                                    other_data = active_participants[other_index]
                                    lap_diff = abs(driver_data['current_lap'] - other_data['current_lap'])

                                    if lap_diff <= 1:
                                        # Add context to overtake - position, corner, car names
                                        driver_car = data.mCarNames[driver_index].decode('utf-8').strip('\x00')
                                        other_car = data.mCarNames[other_index].decode('utf-8').strip('\x00')
                                        track_section = self._get_track_section(data.mParticipantInfo[driver_index])
                                        self.log_event(
                                            f"Overtake! {driver_name} ({driver_car}) overtook {other_name} ({other_car}) for position {current_pos} at {track_section}!"
                                        )
                                    break

        self.previous_positions = current_positions.copy()
        self.last_overtake_update = session_time_elapsed


def _get_wind_direction(self, x, y):
    """Convert wind direction components to cardinal direction."""
    # Calculate angle in degrees
    angle = math.degrees(math.atan2(y, x))
    if angle < 0:
        angle += 360

    # Convert angle to cardinal direction
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    index = round(angle / 22.5) % 16
    return directions[index]


def _get_track_section(self, participant_data):
    """Get track section name based on participant position."""
    # Implement track section mapping based on spline position or coordinates
    # This is a simplified example - would need track-specific mapping
    lap_distance = participant_data.mCurrentLapDistance

    # For example, you could divide the track into sections
    if not hasattr(self, 'track_sections'):
        # Create an ordered dictionary of track sections
        # These would ideally be loaded from a configuration file for each track
        self.track_sections = {
            0.0: "Start/Finish",
            0.1: "Turn 1",
            0.2: "Back Straight",
            0.4: "Hairpin",
            0.6: "Technical Section",
            0.8: "Final Corner"
        }

    # Calculate normalized position around the track
    if hasattr(self, 'track_length') and self.track_length > 0:
        normalized_pos = lap_distance / self.track_length
    else:
        normalized_pos = 0.0

    # Find the appropriate section
    current_section = "unknown section"
    for pos, section in sorted(self.track_sections.items()):
        if normalized_pos >= pos:
            current_section = section
        else:
            break

    return current_section


def _get_pit_stop_reason(self, pit_schedule):
    """Get a string explaining the reason for a pit stop."""
    reasons = {
        PIT_SCHEDULE_PLAYER_REQUESTED: " after driver-requested stop",
        PIT_SCHEDULE_ENGINEER_REQUESTED: " after engineer-requested stop",
        PIT_SCHEDULE_DAMAGE_REQUESTED: " after repairs",
        PIT_SCHEDULE_MANDATORY: " after mandatory pit stop",
        PIT_SCHEDULE_DRIVE_THROUGH: " after drive-through penalty",
        PIT_SCHEDULE_STOP_GO: " after stop-go penalty"
    }

    return reasons.get(pit_schedule, "")


def _check_fastest_laps(self, lap_time_data):
    """Check and log fastest laps set in the race."""
    if not hasattr(self, 'fastest_lap_time') or not hasattr(self, 'fastest_lap_holder'):
        self.fastest_lap_time = float('inf')
        self.fastest_lap_holder = None

    for driver_name, times in lap_time_data.items():
        fastest_lap = times['fastest_lap']
        last_lap = times['last_lap']

        # Check if this is a new overall fastest lap
        if 0 < fastest_lap < self.fastest_lap_time:
            # Format time nicely for commentary
            minutes = int(fastest_lap // 60)
            seconds = fastest_lap % 60
            time_str = f"{minutes}:{seconds:06.3f}" if minutes > 0 else f"{seconds:.3f}"

            # Check if this was just set (comparing to last lap)
            if abs(fastest_lap - last_lap) < 0.001:  # Just set this lap
                self.log_event(f"FASTEST LAP! {driver_name} sets new fastest lap of {time_str}!")

            self.fastest_lap_time = fastest_lap
            self.fastest_lap_holder = driver_name

        # Check if driver just set their personal best but not overall fastest
        elif 0 < fastest_lap < float('inf') and abs(
                fastest_lap - last_lap) < 0.001 and fastest_lap > self.fastest_lap_time:
            minutes = int(fastest_lap // 60)
            seconds = fastest_lap % 60
            time_str = f"{minutes}:{seconds:06.3f}" if minutes > 0 else f"{seconds:.3f}"
            self.log_event(f"Personal best! {driver_name} sets their fastest lap of {time_str}")


def _log_starting_grid(self, data):
    """Log the starting grid with more detail at race start."""
    participants = []
    for i in range(data.mNumParticipants):
        participant_data = data.mParticipantInfo[i]
        if participant_data.mIsActive:
            participant_name = participant_data.mName.decode('utf-8').strip('\x00')
            car_name = data.mCarNames[i].decode('utf-8').strip('\x00')
            car_class = data.mCarClassNames[i].decode('utf-8').strip('\x00')

            if participant_name != "Safety Car":
                position = participant_data.mRacePosition
                participants.append((position, participant_name, car_name, car_class))

    participants.sort()

    # Separate front row for dramatic effect
    if len(participants) >= 2:
        front_row = participants[:2]
        front_row_str = " and ".join([f"{name} ({car})" for _, name, car, _ in front_row])
        self.log_event(f"Front row: {front_row_str}")

    # Rest of grid by class
    class_participants = {}
    for pos, name, car, car_class in participants[2:]:
        if car_class not in class_participants:
            class_participants[car_class] = []
        class_participants[car_class].append((pos, name, car))

    for car_class, drivers in class_participants.items():
        if drivers:
            participants_str = ", ".join([f"P{pos}: {name} ({car})" for pos, name, car in drivers])
            self.log_event(f"Grid positions ({car_class}): {participants_str}")


def _log_qualifying_positions(self, data, session_time_elapsed):
    """Log qualifying positions with more detail."""
    class_participants = {}

    for i in range(data.mNumParticipants):
        participant_data = data.mParticipantInfo[i]
        if participant_data.mIsActive:
            participant_name = participant_data.mName.decode('utf-8').strip('\x00')
            if participant_name != "Safety Car":
                position = participant_data.mRacePosition
                car_name = data.mCarNames[i].decode('utf-8').strip('\x00')
                car_class = data.mCarClassNames[i].decode('utf-8').strip('\x00')

                if car_class not in class_participants:
                    class_participants[car_class] = []
                class_participants[car_class].append((position, participant_name, car_name))

    # Log each class separately for better organization
    for car_class, participants in class_participants.items():
        participants.sort()  # Sort by position
        participants_str = ", ".join([f"P{pos}: {name} ({car})" for pos, name, car in participants])
        self.log_event(f"Qualifying positions ({car_class}): {participants_str}")


def _log_race_positions(self, data, session_time_elapsed):
    """Log race positions with more detail including gaps."""
    class_participants = {}

    # First gather all active participants
    for i in range(data.mNumParticipants):
        participant_data = data.mParticipantInfo[i]
        if participant_data.mIsActive:
            participant_name = participant_data.mName.decode('utf-8').strip('\x00')
            if participant_name != "Safety Car":
                position = participant_data.mRacePosition
                car_name = data.mCarNames[i].decode('utf-8').strip('\x00')
                car_class = data.mCarClassNames[i].decode('utf-8').strip('\x00')
                current_lap = participant_data.mCurrentLap

                # Calculate gap to leader (for more detailed position info)
                gap_to_leader = ""
                if position > 1:
                    for j in range(data.mNumParticipants):
                        if data.mParticipantInfo[j].mIsActive and data.mParticipantInfo[j].mRacePosition == 1:
                            leader_lap = data.mParticipantInfo[j].mCurrentLap
                            lap_diff = leader_lap - current_lap

                            if lap_diff > 0:
                                gap_to_leader = f" +{lap_diff} lap{'s' if lap_diff > 1 else ''}"
                            elif data.mLastLapTimes[i] > 0 and data.mLastLapTimes[j] > 0:
                                time_diff = session_time_elapsed - (data.mLastLapTimes[i] - data.mLastLapTimes[j])
                                gap_to_leader = f" +{time_diff:.1f}s"
                            break

                if car_class not in class_participants:
                    class_participants[car_class] = []
                class_participants[car_class].append((position, participant_name, car_name, gap_to_leader))

    # Log positions by class with gap information
    for car_class, participants in class_participants.items():
        participants.sort()  # Sort by position
        participants_str = ", ".join([f"P{pos}: {name} ({car}){gap}" for pos, name, car, gap in participants])
        self.log_event(f"Positions ({car_class}): {participants_str}")


def _log_accident_group(self, accident_group):
    """Log a group of accidents that occurred close together with enhanced details."""
    if not accident_group:
        return

    # Create unique accident ID based on participants and time
    participants = sorted(acc['name'] for acc in accident_group)
    accident_id = f"{accident_group[0]['time']}_{'_'.join(participants)}"

    # Check if this accident has already been logged
    if accident_id in self.accident_logged:
        return

    # Add more details to accident messages
    if len(participants) == 1:
        accident = accident_group[0]
        track_section = accident.get('track_section', 'on track')
        car_name = accident.get('car_name', '')
        position_info = f" from P{accident['position']}" if 'position' in accident else ""
        accident_msg = f"Incident! {accident['name']} has stopped {track_section}{position_info} in the {car_name}"
    else:
        # Multiple cars involved - likely a collision
        cars_info = []
        track_section = accident_group[0].get('track_section', 'on track')

        for acc in accident_group:
            position_info = f"P{acc['position']}" if 'position' in acc else ""
            car_info = f"{acc['name']} ({position_info})"
            cars_info.append(car_info)

        cars_str = ", ".join(cars_info[:-1]) + " and " + cars_info[-1] if len(cars_info) > 1 else cars_info[0]
        accident_msg = f"Collision {track_section} involving {cars_str}!"

    self.log_event(accident_msg)
    self.accident_logged[accident_id] = True


def _detect_battles(self, active_participants, data):
    """Detect and log close battles between cars."""
    if not hasattr(self, 'last_battle_update'):
        self.last_battle_update = 0
        self.active_battles = {}
        self.reported_battles = set()

    current_time = time.time()
    if self.race_start_system_time:
        session_time = current_time - self.race_start_system_time
    else:
        session_time = 0

    # Only check battles every 10 seconds to avoid spam
    if current_time - self.last_battle_update < 10:
        return

    self.last_battle_update = current_time

    # Build position-indexed dictionary for easier lookup
    position_data = {}
    for index, car_data in active_participants.items():
        position = car_data['position']
        position_data[position] = {
            'index': index,
            'name': car_data['name'],
            'lap': car_data['current_lap'],
            'distance': car_data['lap_distance'],
            'car': data.mCarNames[index].decode('utf-8').strip('\x00') if index < len(data.mCarNames) else "Unknown Car"
        }

    # Check consecutive positions for close battles
    current_battles = {}

    for pos in sorted(position_data.keys()):
        if pos + 1 in position_data:
            car1 = position_data[pos]
            car2 = position_data[pos + 1]

            # Only consider cars on the same lap
            if car1['lap'] == car2['lap']:
                # Calculate distance between cars
                distance_diff = abs(car1['distance'] - car2['distance'])

                # If within 1.5 seconds (approx), consider it a battle
                # Using track length and average speed to estimate time gap
                track_length = data.mTrackLength
                if track_length > 0:
                    # Get speeds
                    speed1 = data.mSpeeds[car1['index']] if car1['index'] < len(
                        data.mSpeeds) else 100  # Default to 100 km/h if not available
                    speed2 = data.mSpeeds[car2['index']] if car2['index'] < len(data.mSpeeds) else 100

                    avg_speed = (speed1 + speed2) / 2
                    if avg_speed > 0:
                        # Convert km/h to m/s
                        avg_speed_ms = avg_speed / 3.6
                        time_gap = distance_diff / avg_speed_ms

                        if time_gap < 1.5:  # Within 1.5 seconds
                            battle_id = f"{car1['name']}_{car2['name']}"
                            current_battles[battle_id] = {
                                'car1': car1,
                                'car2': car2,
                                'gap': time_gap,
                                'position': pos
                            }

    # Update active battles and report new ones
    for battle_id, battle in current_battles.items():
        if battle_id not in self.active_battles:
            # New battle detected
            track_section = self._get_track_section(data.mParticipantInfo[battle['car1']['index']])
            self.log_event(f"Battle brewing! {battle['car1']['name']} ({battle['car1']['car']}) " +
                           f"defends P{battle['position']} from {battle['car2']['name']} " +
                           f"({battle['car2']['car']}) with just {battle['gap']:.1f}s gap at {track_section}!")
            # Add to active battles
            self.active_battles[battle_id] = battle
            self.active_battles[battle_id]['start_time'] = current_time
            self.active_battles[battle_id]['updates'] = 1
        else:
            # Update existing battle
            self.active_battles[battle_id].update(battle)
            self.active_battles[battle_id]['updates'] += 1

            # Only report again if it's been going on for a while (intense battle)
            battle_duration = current_time - self.active_battles[battle_id]['start_time']
            if (battle_duration > 30 and  # Battle lasting over 30 seconds
                    self.active_battles[battle_id]['updates'] % 3 == 0 and  # Don't report every update
                    battle['gap'] < 1.0):  # Close gap

                track_section = self._get_track_section(data.mParticipantInfo[battle['car1']['index']])
                self.log_event(f"Intense battle continues! {battle['car1']['name']} still holding off " +
                               f"{battle['car2']['name']} for P{battle['position']} at {track_section} " +
                               f"- gap now {battle['gap']:.1f}s after {int(battle_duration)}s of pressure!")

    # Remove battles that are no longer active
    to_remove = [battle_id for battle_id in self.active_battles if battle_id not in current_battles]
    for battle_id in to_remove:
        # Report that the battle is over if it lasted long enough to be interesting
        battle = self.active_battles[battle_id]
        battle_duration = current_time - battle['start_time']
        if battle_duration > 20:  # Only mention end of significant battles
            self.log_event(f"Battle over! {battle['car1']['name']} has broken away from {battle['car2']['name']} " +
                           f"in the fight for P{battle['position']} after {int(battle_duration)}s")
        del self.active_battles[battle_id]


def format_time(self, elapsed_seconds):
    """Formats the elapsed time into HH:MM:SS."""
    total_seconds = int(elapsed_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def run(self):
    """Main loop for reading shared memory and processing data with enhanced commentary information."""
    self.output_signal.emit("Starting enhanced AMS2 data collection...")
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