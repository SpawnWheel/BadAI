# ams2_director.py
import os
import re
import time
import json
import sys
import traceback # Import traceback for detailed error logging
from PyQt5.QtCore import QThread, pyqtSignal

# --- Define Constants ---
# General interval, used by press_key for things like ENTER or if pydirectinput was working
KEY_PRESS_INTERVAL = 0.005
# Specific delays for the fast pyKey navigation method (found via keyboard_speed_test.py)
NAV_HOLD_DURATION = 0.001       # How long pyKey holds the key down during navigation
NAV_INTER_PRESS_DELAY = 0.001   # How long pyKey waits between nav key presses
NAVIGATION_LEAD_TIME_SECONDS = 1.5 # How many seconds *before* the timestamp to start navigating
UP_PRESSES_TO_RESET = 35 # Presses to ensure we're at the top of the list

# --- Choose Keyboard Simulation Library (Optimized) ---
# We now know pydirectinput is problematic on this system, but keep detection
# in case it works for others or gets fixed. pyKey is preferred if pydirectinput fails.
keyboard_lib_name = "None"
# Declare placeholder functions
press_key = lambda key: print(f"Keyboard sim disabled: Tried to press {key}")
key_down = lambda key: print(f"Keyboard sim disabled: Tried to hold {key}")
key_up = lambda key: print(f"Keyboard sim disabled: Tried to release {key}")
using_fast_pykey_nav = False # Flag to indicate if we should use the specific pyKey nav logic

try:
    # Attempt pydirectinput first (might work for others)
    import pydirectinput
    print("Trying pydirectinput for keyboard simulation...")
    # pydirectinput.FAILSAFE = False
    KEY_UP = 'up'
    KEY_DOWN = 'down'
    KEY_ENTER = 'ENTER' # pydirectinput usually uses lowercase 'enter'
    # Redefine functions for pydirectinput
    def press_key(key): pydirectinput.press(key, interval=KEY_PRESS_INTERVAL)
    def key_down(key): pydirectinput.keyDown(key)
    def key_up(key): pydirectinput.keyUp(key)
    print(f"Using pydirectinput. Press interval set to: {KEY_PRESS_INTERVAL}s")
    print(f" -> Enter key mapped to: '{KEY_ENTER}'")
    keyboard_lib_name = "pydirectinput"
    # NOTE: We know this might be slow on the user's system, but keep the code path.

except ImportError:
    print("pydirectinput not found or failed to import. Trying pyKey...")
    try:
        from pyKey import pressKey, releaseKey
        print("Attempting to use pyKey...")
        KEY_UP = 'UP'
        KEY_DOWN = 'DOWN'
        # *** CHANGE HERE: Try capitalized 'Enter' for pyKey ***
        KEY_ENTER = 'ENTER'

        # Redefine functions for pyKey
        # General press_key uses the standard interval (for Enter etc.)
        def press_key(key):
            pressKey(key)
            time.sleep(KEY_PRESS_INTERVAL)
            releaseKey(key)

        # Map key_down/key_up directly for the navigation logic
        def key_down(key): pressKey(key)
        def key_up(key): releaseKey(key)

        print(f"Using pyKey.")
        print(f" -> Navigation will use fast down/up method with {NAV_HOLD_DURATION}s hold, {NAV_INTER_PRESS_DELAY}s delay.")
        print(f" -> Enter key mapped to: '{KEY_ENTER}'") # Log the mapped key
        keyboard_lib_name = "pyKey"
        using_fast_pykey_nav = True # Enable the specific pyKey navigation logic

    except ImportError:
        print("ERROR: Neither pydirectinput nor pyKey found.")
        print("Please install pyKey: pip install pykey") # Recommend pyKey now
        KEY_UP = 'up'; KEY_DOWN = 'down'; KEY_ENTER = 'ENTER' # Default fallback names
        keyboard_lib_name = "None"


# --- Pygame for Audio ---
try:
    import pygame
    print("Pygame module loaded.")
except ImportError:
    print("ERROR: Pygame not found. Audio playback will be disabled.")
    print("Please install pygame: pip install pygame")
    pygame = None


class AMS2Director(QThread):
    output_signal = pyqtSignal(str)
    countdown_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, commentary_script_path, audio_file_path, participant_mapping_path=None, pre_roll_seconds=3):
        super().__init__()
        self.commentary_script_path = commentary_script_path
        self.audio_file_path = audio_file_path
        self.participant_mapping_path = participant_mapping_path
        self.pre_roll_seconds_audio = pre_roll_seconds
        self.schedule = []
        self.running = False
        self._stop_requested = False
        self.participant_mapping = {}

        if self.participant_mapping_path:
             try: self.load_participant_mapping()
             except Exception as e: self.output_signal.emit(f"Error loading participant map: {e}")

        if pygame:
            try:
                if hasattr(pygame, 'mixer') and not pygame.mixer.get_init():
                    pygame.mixer.init()
                    self.output_signal.emit("Pygame mixer initialized by AMS2Director.")
                elif hasattr(pygame, 'mixer') and pygame.mixer.get_init():
                    self.output_signal.emit("Pygame mixer already initialized.")
                elif not hasattr(pygame, 'mixer'):
                     self.output_signal.emit("Pygame missing mixer module. Audio disabled.")
            except Exception as e:
                 self.output_signal.emit(f"Error initializing pygame mixer: {e}. Audio might fail.")
                 self.output_signal.emit(traceback.format_exc())
        else:
             self.output_signal.emit("Pygame module not loaded. Audio disabled.")


    def timecode_to_seconds(self, timecode):
        try:
            parts = list(map(int, timecode.split(':')))
            if len(parts) == 3:
                h, m, s = parts
                return h * 3600 + m * 60 + s
            elif len(parts) == 2:
                m, s = parts
                return m * 60 + s
            else:
                raise ValueError("Invalid number of parts in timecode")
        except (ValueError, TypeError):
            self.output_signal.emit(f"Error: Invalid timecode format or type '{timecode}'")
            return None

    def load_participant_mapping(self):
        if not self.participant_mapping_path:
            self.output_signal.emit("No participant mapping file provided. Skipping load.")
            return

        try:
            with open(self.participant_mapping_path, 'r', encoding='utf-8') as f:
                self.participant_mapping = json.load(f)
            if not self.participant_mapping:
                 self.output_signal.emit("Warning: Participant mapping file is empty or invalid JSON structure.")
            else:
                 self.output_signal.emit(f"Loaded participant mapping for context: {len(self.participant_mapping)} drivers.")

        except FileNotFoundError:
            self.output_signal.emit(f"Warning: Participant mapping file not found at {self.participant_mapping_path}")
        except json.JSONDecodeError:
            self.output_signal.emit(f"Warning: Participant mapping file is not valid JSON: {self.participant_mapping_path}")
            self.participant_mapping = {}
        except Exception as e:
            self.output_signal.emit(f"Warning: Error loading participant mapping: {str(e)}")
            self.output_signal.emit(traceback.format_exc())
            self.participant_mapping = {}


    def parse_script_and_schedule(self):
        """Parses the script expecting 'HH:MM:SS - P<pos>[, Optional Text]' format."""
        self.schedule = []
        try:
            with open(self.commentary_script_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            found_event = False
            for line_num, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith('#'): continue

                match = re.match(r'(\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*P(\d+)(?:,|\s*-)?\s*(.*)', line, re.IGNORECASE)

                if match:
                    time_code, position_str, description = match.groups()
                    enter_press_time_seconds = self.timecode_to_seconds(time_code)
                    if enter_press_time_seconds is None:
                        self.output_signal.emit(f"Warning: Skipping line {line_num+1} due to invalid timecode: {line}")
                        continue

                    try:
                        target_position = int(position_str)
                        if target_position <= 0: raise ValueError("Position must be positive")
                    except ValueError:
                        self.output_signal.emit(f"Warning: Skipping line {line_num+1} due to invalid position number '{position_str}': {line}")
                        continue

                    navigation_start_time = max(0, enter_press_time_seconds - NAVIGATION_LEAD_TIME_SECONDS)
                    self.schedule.append((navigation_start_time, enter_press_time_seconds, target_position, description.strip()))
                    found_event = True
                else:
                     self.output_signal.emit(f"Warning: Skipping line {line_num+1} - doesn't match format 'TIME - P<pos>[, text]': {line}")

            if not found_event:
                self.output_signal.emit("Error: No valid P<position> events found in the commentary script.")
                return False

            self.schedule.sort(key=lambda x: (x[0], x[1]))
            self.output_signal.emit(f"Parsed commentary script. Scheduled {len(self.schedule)} camera switches.")
            for i, event in enumerate(self.schedule[:5]):
                nav_t, enter_t, pos, desc = event
                self.output_signal.emit(f"  Event {i+1}: Navigate at {self.format_time(nav_t)}, Select P{pos} at {self.format_time(enter_t)} ({desc})")
            if len(self.schedule) > 5: self.output_signal.emit("  ...")
            return True

        except FileNotFoundError:
            self.output_signal.emit(f"Error: Commentary script not found at {self.commentary_script_path}")
            return False
        except Exception as e:
            self.output_signal.emit(f"Error parsing commentary script: {str(e)}")
            self.output_signal.emit(traceback.format_exc())
            return False

    def run(self):
        self._stop_requested = False
        self.running = True
        self.output_signal.emit("Starting Auto Director Sequence...")

        if not self.parse_script_and_schedule():
            self.output_signal.emit("Director initialization failed: Script parsing error.")
            self.running = False; self.finished_signal.emit(); return

        # Audio Setup
        audio_loaded = False
        audio_start_offset = self.pre_roll_seconds_audio
        audio_started = False
        playback_started_flag = False # Track if pygame.mixer.music.play() was called
        if pygame and hasattr(pygame, 'mixer') and pygame.mixer.get_init():
            try:
                pygame.mixer.music.load(self.audio_file_path)
                self.output_signal.emit(f"Audio file loaded: {os.path.basename(self.audio_file_path)}")
                audio_loaded = True
            except Exception as e:
                self.output_signal.emit(f"Error loading audio file '{self.audio_file_path}': {str(e)}")
                audio_loaded = False
        else:
            self.output_signal.emit("Pygame mixer not available/init. Cannot play audio.")
            audio_loaded = False

        # Countdown
        self.output_signal.emit("Get ready! Ensure AMS2 window is focused.")
        for i in range(5, 0, -1):
            if self._stop_requested: self.output_signal.emit("Stopped during countdown."); self.running = False; self.finished_signal.emit(); return
            self.countdown_signal.emit(f"Starting in {i}...")
            time.sleep(1)
        self.countdown_signal.emit("Starting Now!")
        if self._stop_requested: self.running = False; self.finished_signal.emit(); return

        # Main Loop
        start_time = time.time()
        next_schedule_index = 0
        last_navigated_pos = -1
        navigation_done_for_current_event = False

        try:
            while self.running:
                if self._stop_requested: break
                current_time = time.time()
                elapsed_time = current_time - start_time

                # Audio Handling
                if audio_loaded and not audio_started and elapsed_time >= audio_start_offset:
                    if pygame and hasattr(pygame, 'mixer') and pygame.mixer.get_init():
                        try:
                            pygame.mixer.music.play()
                            playback_started_flag = True # Set flag here
                            audio_started = True
                            self.output_signal.emit(f"Audio playback started (Offset: {audio_start_offset}s).")
                        except Exception as e:
                            self.output_signal.emit(f"Error starting audio playback: {e}")
                            playback_started_flag = False
                            audio_loaded = False # Stop trying if it failed once
                    else:
                        self.output_signal.emit("Audio mixer unavailable before playback. Disabling.")
                        audio_loaded = False

                # Camera Switch Scheduling
                if next_schedule_index < len(self.schedule):
                    nav_start_time, enter_press_time, target_pos, description = self.schedule[next_schedule_index]

                    # 1. Navigate
                    if elapsed_time >= nav_start_time and not navigation_done_for_current_event:
                        self.output_signal.emit(f"[{self.format_time(elapsed_time)}] Pre-navigating to P{target_pos} for event at {self.format_time(enter_press_time)}...")
                        if self.navigate_to_position(target_pos):
                             navigation_done_for_current_event = True
                             last_navigated_pos = target_pos
                             self.output_signal.emit(f"[{self.format_time(elapsed_time)}] Navigation complete. Waiting for {self.format_time(enter_press_time)} to select.")
                        else:
                            if self._stop_requested: break
                            self.output_signal.emit("Error/stop during navigation. Stopping director.")
                            break

                    # 2. Select
                    if elapsed_time >= enter_press_time and navigation_done_for_current_event:
                        self.output_signal.emit(f"[{self.format_time(elapsed_time)}] Selecting P{target_pos} ({description})")
                        if self.select_current_position():
                             next_schedule_index += 1
                             navigation_done_for_current_event = False
                             last_navigated_pos = -1

                             if next_schedule_index < len(self.schedule):
                                 next_nav_t, next_enter_t, next_p, next_d = self.schedule[next_schedule_index]
                                 self.output_signal.emit(f"  Next: Nav @ {self.format_time(next_nav_t)}, Select P{next_p} @ {self.format_time(next_enter_t)} ({next_d})")

                             else:
                                 self.output_signal.emit("  Last camera switch executed.")
                        else:
                             if self._stop_requested: break
                             self.output_signal.emit("Error/stop during selection. Stopping director.")
                             break

                # End Conditions Check
                all_switches_done = next_schedule_index >= len(self.schedule)
                audio_finished = False
                if audio_loaded and audio_started:
                    if pygame and hasattr(pygame, 'mixer') and pygame.mixer.get_init():
                        try: audio_finished = not pygame.mixer.music.get_busy()
                        except Exception: audio_finished = True
                    else: audio_finished = True
                no_audio_or_audio_finished = not audio_loaded or (audio_loaded and audio_started and audio_finished)

                if all_switches_done and no_audio_or_audio_finished:
                    if audio_loaded and audio_started and audio_finished: self.output_signal.emit("Audio playback finished.")
                    elif not audio_loaded: self.output_signal.emit("All camera switches complete (No audio loaded).")
                    else: self.output_signal.emit("All camera switches complete.")
                    break

                time.sleep(0.02) # Main loop sleep

        except Exception as e:
             self.output_signal.emit(f"FATAL Error during director execution: {str(e)}")
             self.output_signal.emit(traceback.format_exc())
        finally:
            # Cleanup
            if pygame and hasattr(pygame, 'mixer') and pygame.mixer.get_init() and playback_started_flag:
                try: pygame.mixer.music.stop()
                except Exception: pass
                self.output_signal.emit("Audio playback stopped.")

            status = "Stopped" if self._stop_requested else "Finished"
            self.output_signal.emit(f"Auto Director {status}.")
            self.running = False
            self.finished_signal.emit()


    # ========================================================================
    # === REVISED NAVIGATION FUNCTION (Conditional Logic) ====================
    # ========================================================================
    def navigate_to_position(self, target_position):
        """
        Simulates keyboard presses for navigation.
        Uses specific fast key_down/key_up method for pyKey if detected,
        otherwise falls back to the standard press_key (for pydirectinput or None).
        """
        global using_fast_pykey_nav # Access the flag set during library init

        if not isinstance(target_position, int) or target_position <= 0:
            self.output_signal.emit(f"Error: Invalid target position ({target_position}) for navigation.")
            return False

        self.output_signal.emit(f"Navigating... (Ensure AMS2 has focus!) Library: {keyboard_lib_name}")
        if using_fast_pykey_nav:
             self.output_signal.emit(f" -> Using pyKey fast down/up method.")
        elif keyboard_lib_name == "pydirectinput":
             self.output_signal.emit(f" -> Using pydirectinput press method (Interval: {KEY_PRESS_INTERVAL}s).")

        time.sleep(0.15) # Pause before starting intense key presses

        try:
            # --- 1. Reset to top of the list ---
            self.output_signal.emit(f"Sending {UP_PRESSES_TO_RESET}x '{KEY_UP}'...")
            for i in range(UP_PRESSES_TO_RESET):
                if self._stop_requested: self.output_signal.emit("Navigation stopped by user."); return False

                if using_fast_pykey_nav:
                    key_down(KEY_UP)
                    time.sleep(NAV_HOLD_DURATION)
                    key_up(KEY_UP)
                    time.sleep(NAV_INTER_PRESS_DELAY)
                else:
                    # Use standard press_key for pydirectinput or None
                    press_key(KEY_UP)
                    # time.sleep(0.001) # Optional extra delay if needed

            time.sleep(0.05) # Short pause after resetting

            # --- 2. Navigate down to target ---
            downs_needed = target_position - 1
            if downs_needed > 0:
                self.output_signal.emit(f"Sending {downs_needed}x '{KEY_DOWN}'...")
                for i in range(downs_needed):
                    if self._stop_requested: self.output_signal.emit("Navigation stopped by user."); return False

                    if using_fast_pykey_nav:
                        key_down(KEY_DOWN)
                        time.sleep(NAV_HOLD_DURATION)
                        key_up(KEY_DOWN)
                        time.sleep(NAV_INTER_PRESS_DELAY)
                    else:
                        # Use standard press_key for pydirectinput or None
                        press_key(KEY_DOWN)
                        # time.sleep(0.001) # Optional extra delay if needed

            self.output_signal.emit("Navigation inputs sent.")
            return True

        except Exception as e:
            exc_type, exc_value, _ = sys.exc_info()
            self.output_signal.emit(f"Error during keyboard navigation: {exc_type.__name__} - {exc_value}")
            self.output_signal.emit(f"(Library: {keyboard_lib_name}, Method: {'pyKey fast' if using_fast_pykey_nav else 'press_key'})")
            self.output_signal.emit("Please ensure AMS2 is focused and the keyboard library is working.")
            self.output_signal.emit(traceback.format_exc())
            return False


    # ========================================================================
    # === SELECT FUNCTION (Uses standard press_key) ==========================
    # ========================================================================
    def select_current_position(self):
        """Simulates pressing ENTER using the standard press_key abstraction."""
        self.output_signal.emit(f"Sending '{KEY_ENTER}'...")
        try:
            press_key(KEY_ENTER) # Single press, standard method is fine
            time.sleep(0.02)
            self.output_signal.emit("Selection complete.")
            return True
        except Exception as e:
            exc_type, exc_value, _ = sys.exc_info()
            self.output_signal.emit(f"Error during keyboard selection (Enter): {exc_type.__name__} - {exc_value}")
            self.output_signal.emit(f"(Library: {keyboard_lib_name})")
            self.output_signal.emit(traceback.format_exc())
            return False


    # ========================================================================
    # === OTHER METHODS (Unchanged) ==========================================
    # ========================================================================
    def stop(self):
        self._stop_requested = True
        self.output_signal.emit("Stop request received. Finishing current action...")

    def format_time(self, seconds):
        """Formats seconds into HH:MM:SS"""
        try:
            if seconds is None: return "??:??:??"
            int_seconds = int(seconds)
            h = int_seconds // 3600
            m = (int_seconds % 3600) // 60
            s = int_seconds % 60
            return f"{h:02d}:{m:02d}:{s:02d}"
        except (TypeError, ValueError):
             return "??:??:??"

# --- END OF FILE ams2_director.py ---