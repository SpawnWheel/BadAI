# ui_director_tab.py
import os
import re
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QLineEdit, QTextEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout,
    QSpinBox
)

class AutoDirectorTab(QWidget):
    """QWidget for the Auto Director tab."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.settings = main_window.settings

        self._setup_ui()

    def _setup_ui(self):
        """Sets up the UI elements for this tab."""
        layout = QVBoxLayout(self)

        # Game Selection
        game_select_layout = QHBoxLayout()
        game_select_label = QLabel("Select Game:")
        self.director_game_combo = QComboBox()
        self.director_game_combo.addItems(["Automobilista 2"]) # Only AMS2 for now
        game_select_layout.addWidget(game_select_label)
        game_select_layout.addWidget(self.director_game_combo)
        game_select_layout.addStretch()
        layout.addLayout(game_select_layout)

        # Input Files Group
        file_group = QGroupBox("Input Files")
        file_layout = QFormLayout()

        # Script Input
        self.director_script_input = QLineEdit()
        self.director_script_input.setPlaceholderText("Select final commentary script (e.g., *_filled.txt)")
        browse_script_button = QPushButton("Browse...")
        browse_script_button.clicked.connect(self.browse_director_script)
        script_layout = QHBoxLayout()
        script_layout.addWidget(self.director_script_input)
        script_layout.addWidget(browse_script_button)
        file_layout.addRow("Commentary Script (.txt):", script_layout)

        # Audio Input
        self.director_audio_input = QLineEdit()
        self.director_audio_input.setPlaceholderText("Select combined audio file (.mp3, .wav)") # User combines manually
        browse_audio_button = QPushButton("Browse...")
        browse_audio_button.clicked.connect(self.browse_director_audio)
        audio_layout = QHBoxLayout()
        audio_layout.addWidget(self.director_audio_input)
        audio_layout.addWidget(browse_audio_button)
        file_layout.addRow("Full Audio File:", audio_layout)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # Settings Group
        settings_group = QGroupBox("Settings")
        settings_layout = QFormLayout()
        self.director_preroll_spinbox = QSpinBox()
        self.director_preroll_spinbox.setRange(0, 30)
        self.director_preroll_spinbox.setValue(3)
        self.director_preroll_spinbox.setSuffix(" seconds")
        settings_layout.addRow("Audio Start Pre-roll:", self.director_preroll_spinbox)
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Control Button
        control_layout = QHBoxLayout()
        self.director_start_stop_button = QPushButton("Start Auto Director")
        self.director_start_stop_button.setStyleSheet("QPushButton { padding: 10px; font-size: 16px; }")
        self.director_start_stop_button.clicked.connect(self.toggle_auto_director)
        control_layout.addStretch()
        control_layout.addWidget(self.director_start_stop_button)
        control_layout.addStretch()
        layout.addLayout(control_layout)

        # Status Display Group
        status_group = QGroupBox("Status / Countdown")
        status_layout = QVBoxLayout()
        self.director_status_output = QTextEdit()
        self.director_status_output.setReadOnly(True)
        self.director_status_output.setMinimumHeight(100)
        self.director_status_output.setPlaceholderText("Auto Director status...")
        status_layout.addWidget(self.director_status_output)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        layout.addStretch()

    def browse_director_script(self):
        """Opens dialog to select the final commentary script."""
        last_dir = self.settings.value("last_director_script_dir", "Race Data")
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Final Commentary Script", last_dir, "Text Files (*_filled.txt *.txt)")
        if file_name:
            self.director_script_input.setText(file_name)
            self.settings.setValue("last_director_script_dir", os.path.dirname(file_name))
            # Auto-populate audio only if user hasn't set one? Maybe not.
            # self.auto_find_audio(file_name) # Optional auto-find logic

    def browse_director_audio(self):
        """Opens dialog to select the combined audio file."""
        start_dir = os.path.dirname(self.director_script_input.text()) if self.director_script_input.text() else ""
        if not start_dir: start_dir = self.settings.value("last_director_audio_dir", "Race Data")

        file_name, _ = QFileDialog.getOpenFileName(self, "Select Combined Audio File", start_dir, "Audio Files (*.mp3 *.wav *.ogg)")
        if file_name:
            self.director_audio_input.setText(file_name)
            self.settings.setValue("last_director_audio_dir", os.path.dirname(file_name))

    def toggle_auto_director(self):
        """Starts or stops the Auto Director via MainWindow."""
        if self.director_start_stop_button.text() == "Start Auto Director":
            self.start_auto_director()
        else:
            self.stop_auto_director()

    def find_participant_map(self, script_path):
        """Attempts to automatically find the participant map."""
        participant_map_path = None
        script_dir = os.path.dirname(script_path)
        script_base = os.path.splitext(os.path.basename(script_path))[0]
        timestamp_pattern = r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})" # Adjusted for typical data collector output
        match = re.search(timestamp_pattern, script_base)

        if match:
            original_base_timestamp = match.group(1)
            # Look for map based on the original raw data timestamp
            # Strip suffixes like _commentary, _filtered, _filled
            original_base = script_base.split('_commentary')[0].split('_filtered')[0].split('_filled')[0]
            map_filename_pattern = f"{original_base}_participants.json" # Match the exact original log name + _participants.json

            # Search priority: Same dir, ../Race Data, ./Race Data
            paths_to_check = [
                os.path.join(script_dir, map_filename_pattern),
                os.path.abspath(os.path.join(script_dir, "..", "Race Data", map_filename_pattern)),
                os.path.join("Race Data", map_filename_pattern)
            ]
            for p in paths_to_check:
                if os.path.exists(p):
                    participant_map_path = p
                    print(f"Found participant map automatically: {participant_map_path}")
                    break

            # Wider search if still not found (look for ANY map with the timestamp)
            if not participant_map_path:
                 wider_map_pattern = f"{original_base_timestamp}_participants.json" # Fallback based only on timestamp
                 search_dirs = [script_dir, os.path.abspath(os.path.join(script_dir, "..")), "."]
                 for sdir in search_dirs:
                      race_data_dir_search = os.path.join(sdir, "Race Data")
                      if os.path.isdir(race_data_dir_search):
                           try:
                               for fname in os.listdir(race_data_dir_search):
                                    # Check if timestamp is present AND it ends correctly
                                    if original_base_timestamp in fname and fname.endswith("_participants.json"):
                                         potential_map = os.path.join(race_data_dir_search, fname)
                                         if os.path.exists(potential_map):
                                             participant_map_path = potential_map
                                             print(f"Found participant map via wider search: {participant_map_path}")
                                             break
                           except OSError as e: print(f"Could not search {race_data_dir_search}: {e}")
                      if participant_map_path: break
        else:
             print(f"Could not extract timestamp from script base: {script_base}")


        # Manual selection if not found
        if not participant_map_path:
             QMessageBox.warning(self, "Map Not Found", "Could not automatically find participant map.\nPlease select manually.")
             browse_dir = script_dir if script_dir else "Race Data"
             map_path_browse, _ = QFileDialog.getOpenFileName(self, "Select Participant Map File", browse_dir, "JSON Files (*_participants.json *.json)")
             if map_path_browse and os.path.exists(map_path_browse):
                 participant_map_path = map_path_browse
             else:
                 self.update_status("Participant map selection cancelled.")
                 return None # Indicate failure to find map
        return participant_map_path


    def start_auto_director(self):
        """Validates inputs and tells MainWindow to start the director."""
        game = self.director_game_combo.currentText()
        script_path = self.director_script_input.text()
        audio_path = self.director_audio_input.text()
        pre_roll = self.director_preroll_spinbox.value()

        if not script_path or not os.path.exists(script_path):
            QMessageBox.warning(self, "Input Error", "Select a valid script file.")
            return
        if not audio_path or not os.path.exists(audio_path):
            QMessageBox.warning(self, "Input Error", "Select a valid audio file.")
            return

        participant_map_path = self.find_participant_map(script_path)
        if not participant_map_path:
             return # Error message shown in find_participant_map

        # Clear status and tell MainWindow to start
        self.director_status_output.clear()
        self.update_status(f"Starting {game} Auto Director...")
        self.update_status(f"Script: {os.path.basename(script_path)}")
        self.update_status(f"Audio: {os.path.basename(audio_path)}")
        self.update_status(f"Map: {os.path.basename(participant_map_path)}")
        self.update_status(f"Pre-roll: {pre_roll}s")

        success = self.main_window.start_auto_director(
            game, script_path, audio_path, participant_map_path, pre_roll
        )
        if success:
            self.set_controls_state(running=True)
        else:
             # Error message should be shown by MainWindow or start_auto_director itself
             self.update_status("Failed to start director (check console).")


    def stop_auto_director(self):
        """Tells MainWindow to stop the director."""
        self.update_status("Sending stop signal...")
        # Disable button immediately
        self.director_start_stop_button.setEnabled(False)
        self.director_start_stop_button.setText("Stopping...")
        self.main_window.stop_auto_director()

    def update_status(self, text):
        """Appends status messages to the output box."""
        self.director_status_output.append(text)
        scrollbar = self.director_status_output.verticalScrollBar()
        if scrollbar: scrollbar.setValue(scrollbar.maximum())

    def set_controls_state(self, running: bool):
        """Updates button text and enabled state."""
        if running:
            self.director_start_stop_button.setText("Stop Auto Director")
            self.director_start_stop_button.setEnabled(True)
            # Optionally disable inputs
            self.director_script_input.setEnabled(False)
            self.director_audio_input.setEnabled(False)
            self.director_game_combo.setEnabled(False)
            self.director_preroll_spinbox.setEnabled(False)
        else:
            self.director_start_stop_button.setText("Start Auto Director")
            self.director_start_stop_button.setEnabled(True)
             # Re-enable inputs
            self.director_script_input.setEnabled(True)
            self.director_audio_input.setEnabled(True)
            self.director_game_combo.setEnabled(True)
            self.director_preroll_spinbox.setEnabled(True)

    def update_inputs(self, script_path=None, audio_path=None):
        """Method for MainWindow to potentially auto-fill inputs."""
        if script_path and os.path.exists(script_path):
            self.director_script_input.setText(script_path)
        if audio_path and os.path.exists(audio_path):
            self.director_audio_input.setText(audio_path)