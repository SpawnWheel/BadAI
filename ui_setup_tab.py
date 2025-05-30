# ui_setup_tab.py
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QTextEdit, QFileDialog, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt
# Import the Video Player Widget
from video_player_widget import VideoPlayerWidget
from datetime import datetime # Needed for video log filename

class SetupTab(QWidget):
    """QWidget for the Setup/Data Collection/Video tab."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window # Reference to MainWindow for calling methods/accessing state
        self.settings = main_window.settings # Access settings directly

        # --- Video Logging State ---
        self.is_video_logging_active = False
        # ---------------------------

        self._setup_ui()

    def _setup_ui(self):
        """Sets up the UI elements for this tab."""
        layout = QVBoxLayout(self)

        # --- Source Selection ---
        sim_select_layout = QHBoxLayout()
        sim_label = QLabel("Select Source:")
        self.sim_combo = QComboBox()
        self.sim_combo.addItems(["Video", "Automobilista 2", "Assetto Corsa Competizione", "Assetto Corsa"])
        self.sim_combo.currentIndexChanged.connect(self.on_source_changed)
        sim_select_layout.addWidget(sim_label)
        sim_select_layout.addWidget(self.sim_combo)
        sim_select_layout.addStretch()
        layout.addLayout(sim_select_layout)

        # --- Main Action Button ---
        self.action_button = QPushButton("Load Video File") # Initial text for video mode
        self.action_button.clicked.connect(self.toggle_action)
        layout.addWidget(self.action_button)

        # --- Video Player Section (Initially Hidden) ---
        self.video_player_container = QWidget()
        video_layout = QVBoxLayout(self.video_player_container)
        video_layout.setContentsMargins(0,0,0,0)

        self.video_player_widget = VideoPlayerWidget()
        self.video_player_widget.event_logged_signal.connect(self.main_window.update_video_log_display) # Connect to MainWindow's handler
        self.video_player_widget.video_loaded_signal.connect(self.on_video_loaded) # Connect to internal handler first
        # Make the video player widget itself expandable within its container
        self.video_player_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.video_log_display = QTextEdit()
        self.video_log_display.setReadOnly(True)
        self.video_log_display.setPlaceholderText("Logged video events will appear here...")
        self.video_log_display.setFixedHeight(150) # Keep log display height fixed

        # Add video player with stretch factor to take most space
        video_layout.addWidget(self.video_player_widget, 1) # Stretch factor 1
        video_layout.addWidget(QLabel("Logged Events:"))
        video_layout.addWidget(self.video_log_display) # Log display takes fixed height

        self.video_player_container.setVisible(False) # Start hidden
        # Give the container expansion capability too
        self.video_player_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.video_player_container)
        # ----------------------------------------------

        # --- Live Data Console Output (Initially Visible) ---
        self.console_output_container = QWidget()
        console_layout = QVBoxLayout(self.console_output_container)
        console_layout.setContentsMargins(0,0,0,0)
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setPlaceholderText("Live data collection output will appear here...")
        console_layout.addWidget(self.console_output)
        self.console_output_container.setVisible(True) # Start visible
        # Give console expansion capability
        self.console_output_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.console_output_container)
        # ------------------------------------------------

        # Set stretch factor for the containers in the main layout
        layout.setStretchFactor(self.video_player_container, 1) # Give video container priority to expand
        layout.setStretchFactor(self.console_output_container, 1) # Give console container priority to expand

        # Initialize view based on default combo selection
        self.on_source_changed(self.sim_combo.currentIndex())

    # --- Getters for MainWindow ---
    def get_console_output_widget(self):
        return self.console_output

    def get_video_log_display_widget(self):
        return self.video_log_display

    # --- Event Handlers ---
    def on_source_changed(self, index):
        """Handles changes in the source selection combobox."""
        selected_source = self.sim_combo.itemText(index)

        # --- Stop any active session before switching ---
        # Let MainWindow handle stopping threads
        if self.main_window.data_collector and self.main_window.data_collector.isRunning():
            self.main_window.stop_data_collection()
        if self.is_video_logging_active:
             self.stop_video_log_session(ask_save=True)

        # --- Configure UI based on selected source ---
        if selected_source == "Video":
            self.action_button.setText("Load Video File")
            self.console_output_container.setVisible(False)
            self.video_player_container.setVisible(True)
            self.action_button.setEnabled(True)
            self.main_window.switch_main_console(self.console_output) # Keep general logs going to console_output
        else: # Live Sim Data
            self.action_button.setText("Start Data Collection")
            self.console_output_container.setVisible(True)
            self.video_player_container.setVisible(False)
            self.action_button.setEnabled(True)
            self.main_window.switch_main_console(self.console_output) # Main console for live data

    def toggle_action(self):
        """Handles clicks on the main action button (Load/Start/Stop/Save)."""
        selected_source = self.sim_combo.currentText()
        button_text = self.action_button.text()

        if selected_source == "Video":
            if button_text == "Load Video File":
                self.browse_and_load_video()
            elif button_text == "Save Log & Stop":
                self.stop_video_log_session(ask_save=False) # User explicitly clicked save
            elif button_text == "Loading...":
                 pass # Do nothing if already loading
        else: # Live Sim Data
            if button_text == "Start Data Collection":
                self.main_window.start_data_collection(selected_source) # Pass source to main window
            elif button_text == "Stop Data Collection":
                self.main_window.stop_data_collection()

    def browse_and_load_video(self):
        """Opens a file dialog to select and load a video."""
        video_formats = "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv);;All Files (*)"
        last_dir = self.settings.value("last_video_dir", os.path.expanduser("~"))
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Video File", last_dir, video_formats)

        if file_path:
             self.settings.setValue("last_video_dir", os.path.dirname(file_path))
             self.main_window.update_console(f"Attempting to load video: {file_path}")
             self.action_button.setEnabled(False)
             self.action_button.setText("Loading...")
             self.main_window.app.processEvents() # Update UI via main app instance

             self.video_player_widget.load_video(file_path)

    def on_video_loaded(self, success, message):
        """Slot to handle the video_loaded_signal from VideoPlayerWidget."""
        self.main_window.update_console(message) # Log success or failure message
        if success:
            self.action_button.setText("Save Log & Stop")
            self.action_button.setEnabled(True)
            self.is_video_logging_active = True # Set logging active state
            self.video_log_display.clear() # Clear previous log display
            self.sim_combo.setEnabled(False) # Prevent switching source during logging
            self.video_player_widget.setFocus()
        else:
            QMessageBox.critical(self, "Video Load Error", message)
            self.action_button.setText("Load Video File") # Reset button on failure
            self.action_button.setEnabled(True)
            self.is_video_logging_active = False # Ensure logging is not active
            self.sim_combo.setEnabled(True) # Re-enable source switching

    def stop_video_log_session(self, ask_save=False, closing_app=False):
        """Stops the video logging session, optionally asking to save."""
        if not self.is_video_logging_active: return

        self.video_player_widget.stop_video()

        should_save = False
        events = self.video_player_widget.get_logged_events()
        if not events:
            self.main_window.update_console("No video events were logged.")
            ask_save = False
            should_save = False
        elif ask_save:
             reply = QMessageBox.question(self, "Save Log?",
                                          "Do you want to save the logged video events?",
                                          QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                                          QMessageBox.Save)
             if reply == QMessageBox.Save: should_save = True
             elif reply == QMessageBox.Cancel and not closing_app:
                 self.main_window.update_console("Video log stop cancelled by user, but session ended.")
                 pass
             elif reply == QMessageBox.Cancel and closing_app: pass
        else:
             should_save = bool(events)

        if should_save:
             self.save_video_log()

        # Reset UI and state
        self.is_video_logging_active = False
        self.action_button.setText("Load Video File")
        self.action_button.setEnabled(True)
        self.sim_combo.setEnabled(True)

    def save_video_log(self):
        """Saves the logged events from the video player to a file."""
        events = self.video_player_widget.get_logged_events()
        if not events: return

        base_filename = "video_log"
        try:
            media = self.video_player_widget.media_player.media()
            if media and not media.isNull() and media.canonicalUrl().isLocalFile():
                video_path = media.canonicalUrl().toLocalFile()
                base_filename = os.path.splitext(os.path.basename(video_path))[0]
        except Exception as e:
            print(f"Could not get video filename for log saving: {e}")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{base_filename}_{timestamp}.txt"
        race_data_dir = "Race Data"
        os.makedirs(race_data_dir, exist_ok=True)
        last_dir = self.settings.value("last_log_save_dir", race_data_dir)
        default_path = os.path.join(last_dir, log_filename)

        self.main_window.update_console(f"Opening save dialog. Suggested path: {default_path}")
        save_path, _ = QFileDialog.getSaveFileName(self, "Save Video Log As", default_path, "Text Files (*.txt)")

        if save_path:
            self.settings.setValue("last_log_save_dir", os.path.dirname(save_path))
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(events))
                self.main_window.update_console(f"Video event log saved to: {save_path}")
                QMessageBox.information(self, "Log Saved", f"Video log saved successfully to:\n{save_path}")
            except Exception as e:
                self.main_window.update_console(f"Error saving video log to {save_path}: {e}")
                QMessageBox.critical(self, "Save Error", f"Failed to save video log:\n{e}")
        else:
            self.main_window.update_console("Video log saving cancelled.")

    def update_button_state(self, collecting: bool):
        """Updates the action button text and combo state for live data."""
        source = self.sim_combo.currentText()
        if source != "Video":
            self.action_button.setText("Stop Data Collection" if collecting else "Start Data Collection")
            self.sim_combo.setEnabled(not collecting)
            self.action_button.setEnabled(True) # Should always be enabled unless error

    def is_video_mode_active(self):
        """Returns True if the video source is selected."""
        return self.sim_combo.currentText() == "Video"

    def get_selected_source(self):
        """Returns the text of the currently selected source."""
        return self.sim_combo.currentText()