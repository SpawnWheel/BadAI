# main_window.py
import sys
import os
import shutil
import re
import json
import traceback
import google.generativeai as genai # Keep if used by any backend module
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout, QTabWidget, QGroupBox,
    QFormLayout, QLineEdit, QPushButton, QLabel, QHBoxLayout, QComboBox, QTextEdit,
    QFileDialog, QMessageBox, QProgressBar, QRadioButton, QButtonGroup, QCheckBox,
    QDialog, QInputDialog, QDialogButtonBox, QSpinBox, QSizePolicy
)
from PyQt5.QtCore import QSettings, Qt, QTimer, QElapsedTimer
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

import pygame # Keep for init and audio

# Backend Modules
from commentator_manager import CommentatorManager
from prompt_manager import PromptManager
from data_collector_ACC import DataCollector as DataCollectorACC
from data_collector_AMS2 import DataCollector as DataCollectorAMS2
from data_collector_AC import DataCollector as DataCollectorAC
from data_filterer import DataFilterer
from race_commentator import RaceCommentator
from voice_generator import VoiceGenerator
from ams2_director import AMS2Director
from cartesia import Cartesia

# UI Modules
from ui_setup_tab import SetupTab
from ui_highlight_tab import HighlightReelTab
from ui_commentary_tab import CommentaryTab
from ui_voice_tab import VoiceTab
from ui_director_tab import AutoDirectorTab
from ui_settings_tab import SettingsTab
from ui_prompt_dialog import PromptEditDialog # Keep the dialog import if used by highlight tab

# --- Application Version ---
VERSION = "23.01" # Update as needed
# -------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Bad AI Commentary - v{VERSION}")
        self.setGeometry(100, 100, 1000, 800)
        self.app = QApplication.instance() # Reference to the application instance

        # --- Initialize Pygame ---
        try:
            pygame.init()
            if not pygame.mixer.get_init():
                 pygame.mixer.init()
        except Exception as e:
            print(f"ERROR: Failed to initialize pygame: {e}")
            QMessageBox.critical(self, "Pygame Error", f"Failed to initialize Pygame: {e}")
        # -------------------------

        self.settings = QSettings("BadAICommentary", "SimRacingCommentator")
        self.commentator_manager = CommentatorManager()
        self.data_filterer_prompt_manager = PromptManager("DataFilterer")
        # Ensure default prompt exists if none are found
        self.data_filterer_prompt_manager.ensure_default_prompt("Default", "data_filterer_prompt.txt")

        # --- State Variables ---
        self.current_console_widget = None # Track which QTextEdit receives general logs
        self.last_filter_output_path = None # Store path from filterer
        self.last_commentary_output_path = None # Store path from commentary
        self.last_voice_output_dir = None # Store dir from voice gen

        # --- Thread Placeholders ---
        self.data_collector = None
        self.data_filterer = None
        self.race_commentator = None
        self.voice_generator = None
        self.ams2_director = None
        # ---------------------------

        self._apply_always_on_top()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        self._setup_tab_widget()
        self._setup_status_bar()

        # --- Initial Population ---
        self.refresh_all_commentator_data() # Populates all commentator lists/combos
        self.refresh_all_prompt_data() # Populates filterer prompt list

        # --- Initialize main console ---
        # Setup tab is created first, use its console initially
        if hasattr(self, 'setup_tab') and self.setup_tab:
             self.switch_main_console(self.setup_tab.get_console_output_widget())
        else:
             print("Warning: SetupTab not initialized before console switch.")

        print("MainWindow initialization complete")

    def _apply_always_on_top(self):
        """Applies the always-on-top setting from QSettings."""
        always_on_top = self.settings.value("always_on_top", False, type=bool)
        if always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        # Don't call self.show() here, happens later

    def set_always_on_top(self, enabled: bool):
        """Sets or clears the always-on-top flag."""
        if enabled:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show() # Re-show to apply changes

    def _setup_status_bar(self):
        """Initializes the status bar and progress bar."""
        self.status_bar = self.statusBar()
        self.progress_bar = QProgressBar()
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.progress_bar.setValue(0) # Start at 0

    def _setup_tab_widget(self):
        """Creates and populates the main tab widget."""
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)

        # Instantiate tab widgets, passing self (MainWindow)
        self.setup_tab = SetupTab(self)
        self.highlight_reel_tab = HighlightReelTab(self)
        self.commentary_tab = CommentaryTab(self)
        self.voice_tab = VoiceTab(self)
        self.auto_director_tab = AutoDirectorTab(self)
        self.settings_tab = SettingsTab(self)

        # Add tabs
        self.tab_widget.addTab(self.setup_tab, "Let's go racing!")
        self.tab_widget.addTab(self.highlight_reel_tab, "Highlight Reel Creation")
        self.tab_widget.addTab(self.commentary_tab, "Commentary Generation")
        self.tab_widget.addTab(self.voice_tab, "Voice Generation")
        self.tab_widget.addTab(self.auto_director_tab, "Auto Director")
        self.tab_widget.addTab(self.settings_tab, "Settings")

        self.tab_widget.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        """Refreshes relevant UI elements when switching tabs."""
        # Currently, refreshes happen on data change rather than tab switch
        # but we can add tab-specific actions here if needed.
        widget = self.tab_widget.widget(index)
        # Example: Ensure focus is set correctly
        # if isinstance(widget, SetupTab) and widget.is_video_mode_active():
        #     widget.video_player_widget.setFocus()
        pass

    def refresh_all_commentator_data(self):
        """Fetches commentator data and updates all relevant UI elements."""
        try:
            commentators = self.commentator_manager.get_all_commentators()
            main_selection = self.settings.value("main_commentator", "")
            voice_selection = self.settings.value("voice_commentator", "")

            # Update combos in tabs that have them
            if hasattr(self, 'commentary_tab') and self.commentary_tab:
                 self.commentary_tab.update_commentator_combo(commentators, main_selection)
            if hasattr(self, 'voice_tab') and self.voice_tab:
                 self.voice_tab.update_commentator_combo(commentators, voice_selection)
            if hasattr(self, 'settings_tab') and self.settings_tab:
                 self.settings_tab.update_commentator_list(commentators) # Update list in settings tab
        except Exception as e:
            self.update_console(f"Error refreshing commentator lists: {e}")
            traceback.print_exc()

    def refresh_all_prompt_data(self):
        """Updates the data filterer prompt list."""
        if hasattr(self, 'highlight_reel_tab') and self.highlight_reel_tab:
            self.highlight_reel_tab.update_data_filterer_prompts()

    # --- Console Switching ---
    def switch_main_console(self, text_edit_widget: QTextEdit):
        """Sets the target QTextEdit for general update_console messages."""
        self.current_console_widget = text_edit_widget
        # print(f"Switched main console output to: {text_edit_widget}") # Debug

    # --- Thread Start Methods (called by Tabs) ---

    def start_data_collection(self, sim_name: str):
        """Starts the appropriate data collector."""
        if self.setup_tab.is_video_logging_active:
             QMessageBox.warning(self, "Action Blocked", "Stop video logging first.")
             return
        if self.data_collector and self.data_collector.isRunning():
             self.update_console("Data collector is already running.")
             return

        self.update_console(f"Starting data collection for {sim_name}...")
        try:
            if sim_name == "Assetto Corsa Competizione": CollectorClass = DataCollectorACC
            elif sim_name == "Automobilista 2": CollectorClass = DataCollectorAMS2
            elif sim_name == "Assetto Corsa": CollectorClass = DataCollectorAC
            else: raise ValueError(f"Unknown sim: {sim_name}")

            self.data_collector = CollectorClass()
            self.data_collector.output_signal.connect(self.update_console)
            self.data_collector.progress_signal.connect(self.update_progress_bar)
            self.data_collector.finished.connect(self.on_data_collector_finished)
            self.data_collector.start()

            self.setup_tab.update_button_state(collecting=True) # Update UI
            self.update_console(f"{sim_name} data collector started.")

        except Exception as e:
             self.update_console(f"Error starting data collector: {e}\n{traceback.format_exc()}")
             QMessageBox.critical(self, "Error", f"Failed to start data collector:\n{e}")
             self.setup_tab.update_button_state(collecting=False) # Reset UI on error

    def stop_data_collection(self):
        """Stops the currently running data collector."""
        if self.data_collector and self.data_collector.isRunning():
            try:
                self.update_console("Stopping data collection...")
                self.data_collector.stop()
                # Don't wait here, cleanup in finished signal or closeEvent
                self.update_console("Stop signal sent.")
            except Exception as e:
                self.update_console(f"Error stopping collector: {e}")
        # Always update UI state, even if thread wasn't running (cleans up button)
        self.setup_tab.update_button_state(collecting=False)


    def start_filtering(self, input_path: str, prompt_name: str):
        """Starts the data filtering process."""
        if self.data_filterer and self.data_filterer.isRunning():
            QMessageBox.warning(self, "Busy", "Filtering process already running.")
            return

        settings = self.get_data_filterer_settings()
        if not self._check_api_key(settings["api"], settings): return

        prompt_content = self.data_filterer_prompt_manager.load_prompt(prompt_name)
        if prompt_content is None:
             QMessageBox.warning(self, "Prompt Error", f"Cannot load prompt: {prompt_name}.")
             return

        try:
            self.data_filterer = DataFilterer(input_path, settings, prompt_content)
            self.data_filterer.progress_signal.connect(self.update_progress_bar)
            self.data_filterer.output_signal.connect(self.update_console) # Filterer logs go to main console
            self.data_filterer.finished.connect(self.on_filtering_finished)
            self.data_filterer.start()
            self.update_console(f"Filtering '{os.path.basename(input_path)}' using prompt: '{prompt_name}'...")
            # Let the tab manage its button state
            self.highlight_reel_tab.filter_button.setEnabled(False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed starting filtering: {str(e)}")
            self.update_console(f"Error starting filter thread: {e}\n{traceback.format_exc()}")
            self.highlight_reel_tab.filter_button.setEnabled(True) # Ensure enabled on error

    def start_commentary_generation(self, input_path: str, commentator_name: str):
        """Starts the commentary generation process."""
        if self.race_commentator and self.race_commentator.isRunning():
             QMessageBox.warning(self, "Busy", "Commentary generation already running.")
             return

        main_meta = self.commentator_manager.get_commentator_metadata(commentator_name)
        if not main_meta:
             QMessageBox.warning(self, "Metadata Error", f"Cannot load metadata for '{commentator_name}'.")
             return
        main_prompt = self.commentator_manager.get_prompt(commentator_name, second_pass=False)
        if main_prompt is None:
             QMessageBox.warning(self, "Prompt Error", f"Cannot load main prompt for '{commentator_name}'.")
             return

        settings = self.get_race_commentator_settings()
        if not self._check_api_key(settings["api"], settings): return

        settings.update({
            'main_prompt': main_prompt, 'main_voice_id': main_meta.voice_id,
            'commentator_name': main_meta.name, 'commentator_style': main_meta.style,
            'commentator_personality': main_meta.personality, 'commentator_examples': main_meta.examples,
        })

        try:
            self.race_commentator = RaceCommentator(input_path, settings)
            self.race_commentator.output_signal.connect(self.commentary_tab.update_output) # Send output direct to tab
            self.race_commentator.progress_signal.connect(self.update_progress_bar)
            self.race_commentator.finished.connect(self.on_commentary_finished)
            self.race_commentator.start()
            self.update_console(f"Generating commentary for '{os.path.basename(input_path)}' using '{commentator_name}'...")
            self.commentary_tab.generate_button.setEnabled(False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed starting commentary: {str(e)}")
            self.update_console(f"Error starting commentary thread: {e}\n{traceback.format_exc()}")
            self.commentary_tab.generate_button.setEnabled(True)


    def start_voice_generation(self, input_path: str, commentator_name: str):
        """Starts the voice generation process."""
        if self.voice_generator and self.voice_generator.isRunning():
             QMessageBox.warning(self, "Busy", "Voice generation already running.")
             return

        cartesia_key = self.get_cartesia_api_key()
        if not cartesia_key:
             QMessageBox.warning(self, "API Key Missing", "Enter Cartesia API key in Settings.")
             return

        metadata = self.commentator_manager.get_commentator_metadata(commentator_name)
        if not metadata:
             QMessageBox.warning(self, "Metadata Error", f"Cannot load metadata for '{commentator_name}'.")
             return
        if not metadata.voice_id:
             QMessageBox.warning(self, "Voice ID Missing", f"'{commentator_name}' has no Cartesia Voice ID.")
             return

        cartesia_model = self.settings.value("cartesia_model", "sonic-english")
        commentary_api_settings = self.get_race_commentator_settings() # For second pass
        commentary_api_settings['claude_key'] = self.get_claude_api_key()
        commentary_api_settings['openai_key'] = self.get_openai_api_key()
        commentary_api_settings['google_key'] = self.get_google_api_key()
        second_pass_prompt = self.commentator_manager.get_prompt(commentator_name, second_pass=True)
        if second_pass_prompt: commentary_api_settings['second_pass_prompt'] = second_pass_prompt
        # Check API key for second pass ONLY if second pass prompt exists
        if second_pass_prompt and not self._check_api_key(commentary_api_settings['api'], commentary_api_settings):
            QMessageBox.warning(self, "API Key Missing", f"Second pass requires {commentary_api_settings['api'].capitalize()} key (set in Settings).")
            return

        try:
            self.voice_generator = VoiceGenerator(
                input_path=input_path, api_key=cartesia_key, voice_id=metadata.voice_id,
                speed=metadata.voice_speed, emotion=metadata.voice_emotions,
                model_id=cartesia_model, commentary_api_settings=commentary_api_settings
            )
            self.voice_generator.output_signal.connect(self.voice_tab.update_output) # Output direct to tab
            self.voice_generator.progress_signal.connect(self.update_progress_bar)
            self.voice_generator.finished.connect(self.on_voice_finished)
            self.voice_generator.start()
            self.update_console(f"Generating voice using '{commentator_name}' (ID: {metadata.voice_id}, Model: {cartesia_model})...");
            self.voice_tab.generate_button.setEnabled(False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed starting voice gen: {str(e)}")
            self.update_console(f"Error starting voice gen thread: {e}\n{traceback.format_exc()}")
            self.voice_tab.generate_button.setEnabled(True)

    def start_auto_director(self, game: str, script_path: str, audio_path: str, map_path: str, pre_roll: int) -> bool:
        """Starts the Auto Director thread."""
        if self.ams2_director and self.ams2_director.isRunning():
            QMessageBox.warning(self, "Already Running", "Auto Director already running.")
            return False

        if game == "Automobilista 2":
            if not pygame or not pygame.get_init() or not pygame.mixer.get_init():
                 QMessageBox.critical(self, "Pygame Error", "Pygame Mixer not initialized. Cannot start AMS2 Director.")
                 return False
            try:
                self.ams2_director = AMS2Director(script_path, audio_path, map_path, pre_roll)
                self.ams2_director.output_signal.connect(self.auto_director_tab.update_status)
                self.ams2_director.countdown_signal.connect(self.auto_director_tab.update_status)
                self.ams2_director.finished_signal.connect(self.on_director_finished)
                self.ams2_director.start()
                self.update_console(f"AMS2 Director thread started.")
                return True # Success
            except Exception as e:
                QMessageBox.critical(self, "Initialization Error", f"Failed to initialize AMS2Director: {e}")
                self.update_console(f"Error initializing director: {e}\n{traceback.format_exc()}")
                return False # Failure
        else:
            QMessageBox.information(self, "Not Implemented", f"Director for {game} not implemented.")
            return False

    def stop_auto_director(self):
        """Signals the Auto Director thread to stop."""
        if self.ams2_director and self.ams2_director.isRunning():
            self.update_console("Sending stop signal to Auto Director...")
            self.ams2_director.stop()
            # Button state managed by tab now based on finished signal
        else:
            self.update_console("Director not running.")
            # Ensure button state is correct if out of sync
            self.auto_director_tab.set_controls_state(running=False)


    # --- Thread Finished Slots ---

    def on_data_collector_finished(self):
        self.update_console("Data collection thread finished.")
        # Button state should be updated already by stop_data_collection or error handling
        self.data_collector = None # Clean up instance
        self.progress_bar.setValue(0) # Reset progress

    def on_filtering_finished(self):
        self.update_console("Filtering thread finished.")
        output_path = None
        success = False
        if self.data_filterer:
            output_path = self.data_filterer.get_output_path()
            # TODO: Add a success status check to DataFilterer if possible
            success = bool(output_path and os.path.exists(output_path))
            if not success:
                 # Try to get error message if filterer provides one
                 error_msg = getattr(self.data_filterer, 'error_message', 'Unknown filtering error.')
                 self.update_console(f"Filtering failed: {error_msg}")
            else:
                self.last_filter_output_path = output_path # Store on success

        # Notify the Highlight tab
        self.highlight_reel_tab.on_filtering_finished(success, output_path)
        # Update commentary input if successful
        if success and output_path:
             self.commentary_tab.set_input_path(output_path)
        self.data_filterer = None # Clean up instance
        self.progress_bar.setValue(0) # Reset progress
        self.highlight_reel_tab.filter_button.setEnabled(True) # Re-enable button

    def on_commentary_finished(self):
        self.update_console("Commentary generation thread finished.")
        output_path = None
        success = False
        if self.race_commentator:
             output_path = self.race_commentator.get_output_path()
             # TODO: Check success status from RaceCommentator
             success = bool(output_path and os.path.exists(output_path))
             if not success:
                  error_msg = getattr(self.race_commentator, 'error_message', 'Unknown commentary error.')
                  self.update_console(f"Commentary generation failed: {error_msg}")
             else:
                self.last_commentary_output_path = output_path # Store on success

        # Notify the Commentary tab
        self.commentary_tab.on_commentary_finished(success, output_path)
        # Update voice input if successful
        if success and output_path:
            self.voice_tab.set_input_path(output_path)
            # Maybe auto-populate director script path too?
            self.auto_director_tab.update_inputs(script_path=output_path)
        self.race_commentator = None # Clean up instance
        self.progress_bar.setValue(0) # Reset progress
        self.commentary_tab.generate_button.setEnabled(True) # Re-enable button

    def on_voice_finished(self):
        self.update_console("Voice generation thread finished.")
        output_dir = None
        success = False
        if self.voice_generator:
             output_dir = self.voice_generator.get_output_dir()
             # TODO: Check success status from VoiceGenerator
             success = bool(output_dir and os.path.isdir(output_dir))
             if not success:
                  error_msg = getattr(self.voice_generator, 'error_message', 'Unknown voice generation error.')
                  self.update_console(f"Voice generation failed: {error_msg}")
             else:
                self.last_voice_output_dir = output_dir # Store on success

        # Notify the Voice tab
        self.voice_tab.on_voice_finished(success, output_dir)
        # TODO: Auto-populate director audio path if combined audio is created?
        # combined_audio = find_combined_audio(output_dir) # Needs implementation
        # if combined_audio: self.auto_director_tab.update_inputs(audio_path=combined_audio)
        self.voice_generator = None # Clean up instance
        self.progress_bar.setValue(0) # Reset progress
        self.voice_tab.generate_button.setEnabled(True) # Re-enable button

    def on_director_finished(self):
        """Called when the Auto Director thread finishes or is stopped."""
        self.update_console("Director thread finished.")
        stopped_by_user = False
        if self.ams2_director and hasattr(self.ams2_director, '_stop_requested'):
             stopped_by_user = self.ams2_director._stop_requested

        if stopped_by_user:
            self.auto_director_tab.update_status("Director stopped by user.")
        else:
            self.auto_director_tab.update_status("Director finished sequence.")

        # Clean up thread instance and reset button via tab method
        self.ams2_director = None
        self.auto_director_tab.set_controls_state(running=False)
        self.progress_bar.setValue(0) # Reset progress


    # --- Signal Handlers for UI Updates ---

    def update_console(self, text):
        """Appends text to the currently active console/log display."""
        if self.current_console_widget:
            try:
                if not isinstance(text, str): text = str(text)
                self.current_console_widget.append(text)
                scrollbar = self.current_console_widget.verticalScrollBar()
                if scrollbar: scrollbar.setValue(scrollbar.maximum())
            except Exception as e:
                 print(f"Error updating console UI: {e}")
        else:
            print(f"Console log (UI target missing): {text}") # Fallback

    def update_video_log_display(self, text):
        """Appends event to the dedicated video log display in SetupTab."""
        if hasattr(self.setup_tab, 'video_log_display') and self.setup_tab.video_log_display:
            log_widget = self.setup_tab.video_log_display
            log_widget.append(text)
            scrollbar = log_widget.verticalScrollBar()
            if scrollbar: scrollbar.setValue(scrollbar.maximum())
        else:
            print(f"Video Log (UI not ready/missing): {text}")

    def update_progress_bar(self, value):
        """Updates the progress bar in the status bar."""
        self.progress_bar.setValue(value)

    # --- Settings Getters ---
    def get_claude_api_key(self): return self.settings.value("claude_api_key", "")
    def get_openai_api_key(self): return self.settings.value("openai_api_key", "")
    def get_google_api_key(self): return self.settings.value("google_api_key", "")
    def get_cartesia_api_key(self): return self.settings.value("cartesia_api_key", "")

    def get_data_filterer_settings(self):
        # Read directly from settings saved by SettingsTab
        return {
            "api": self.settings.value("data_filterer_api", "gemini"),
            "model": self.settings.value("data_filterer_model", "gemini-1.5-flash-latest"),
            "claude_key": self.get_claude_api_key(),
            "openai_key": self.get_openai_api_key(),
            "google_key": self.get_google_api_key()
        }

    def get_race_commentator_settings(self):
        # Read directly from settings saved by SettingsTab
        return {
            "api": self.settings.value("race_commentator_api", "gemini"),
            "model": self.settings.value("race_commentator_model", "gemini-1.5-flash-latest"),
            "claude_key": self.get_claude_api_key(),
            "openai_key": self.get_openai_api_key(),
            "google_key": self.get_google_api_key()
        }

    def _check_api_key(self, api_name, settings_dict):
        """Checks if the required API key exists in the settings dict."""
        # --- FIX: Handle Gemini's specific key name ---
        if api_name == "gemini":
            key_name = "google_key"
        else:
            # For Claude and OpenAI, the key name matches the api_name
            key_name = f"{api_name}_key"
        # ---------------------------------------------

        # Now check using the correctly determined key_name
        if key_name in settings_dict and settings_dict[key_name]:
            # Key found and is not empty
            return True
        else:
            # Key not found or is empty
            # --- FIX: Improve error message for Gemini ---
            # Make the error message more specific for the user
            display_name = "Google (for Gemini)" if api_name == "gemini" else api_name.capitalize()
            QMessageBox.warning(self, "API Key Missing",
                                f"Please enter your {display_name} API key in the Settings tab.")
            # ---------------------------------------------
            return False


    # --- Application Closing ---
    def closeEvent(self, event):
        """Ensure threads and pygame are stopped cleanly on exit."""
        print("Close event triggered.")
        if hasattr(self,'setup_tab') and self.setup_tab and self.setup_tab.is_video_logging_active:
             self.setup_tab.stop_video_log_session(ask_save=True, closing_app=True)

        self.stop_data_collection() # Signal collector to stop
        self.stop_auto_director() # Signal director to stop

        threads_to_stop = [
            ("Data Collector", self.data_collector),
            ("Data Filterer", self.data_filterer),
            ("Race Commentator", self.race_commentator),
            ("Voice Generator", self.voice_generator),
            ("Auto Director", self.ams2_director),
        ]

        for name, thread in threads_to_stop:
             if thread and thread.isRunning():
                 print(f"Waiting for {name} to finish...")
                 if hasattr(thread, 'stop'): # Signal stop if available
                     try: thread.stop()
                     except: pass # Ignore errors if stop method changed/missing
                 thread.wait(2000) # Wait up to 2 seconds
                 if thread.isRunning(): print(f"Warning: {name} did not stop gracefully.")
                 else: print(f"{name} stopped.")

        if pygame and pygame.get_init():
            try:
                if pygame.mixer.get_init():
                     pygame.mixer.music.stop()
                     pygame.mixer.quit()
                pygame.quit()
                print("Pygame quit.")
            except Exception as e:
                print(f"Error quitting pygame: {e}")

        print("Exiting application.")
        event.accept()


# --- Main execution block ---
# This part is usually in main.py, but included here for completeness
# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#
#     # Check Multimedia Availability
#     test_player = QMediaPlayer()
#     if test_player.availability() == QMediaPlayer.AvailabilityUnavailable:
#          QMessageBox.critical(None, "Multimedia Error",
#                               "Qt Multimedia unavailable. Video playback may fail.\n"
#                               "Install necessary plugins (GStreamer/Media Feature Pack/etc).")
#     del test_player
#
#     window = MainWindow()
#     window.show()
#     sys.exit(app.exec_())