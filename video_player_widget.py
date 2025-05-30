# --- START OF FILE video_player_widget.py ---

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel, QStyle,
    QSizePolicy, QLineEdit
)
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QTimer

class VideoPlayerWidget(QWidget):
    # Signal to emit when an event is logged (for display purposes)
    event_logged_signal = pyqtSignal(str)
    # Signal to indicate video loaded status
    video_loaded_signal = pyqtSignal(bool, str) # bool: success, str: message/filepath

    def __init__(self, parent=None):
        super().__init__(parent)
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.video_widget = QVideoWidget()

        # --- Make video widget expandable ---
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_widget.setMinimumSize(400, 300) # Set a reasonable minimum size
        # ------------------------------------

        # Event logging state
        self.logged_events = []
        self.is_paused_for_log = False
        self.log_timestamp_ms = 0

        # --- UI Elements ---
        # Play/Pause Button
        self.play_button = QPushButton()
        self.play_button.setEnabled(False)
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.toggle_play_pause)

        # Stop Button
        self.stop_button = QPushButton()
        self.stop_button.setEnabled(False)
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_button.clicked.connect(self.stop_video)

        # Position Slider (Timeline)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.set_position)
        self.position_slider.setEnabled(False)

        # Time Labels
        self.current_time_label = QLabel("00:00:00")
        self.total_time_label = QLabel("00:00:00")

        # Event Input LineEdit (controlled by spacebar)
        self.event_input = QLineEdit()
        self.event_input.setPlaceholderText("Press Space to pause and log event...")
        self.event_input.setEnabled(False) # Disabled until spacebar pause
        self.event_input.returnPressed.connect(self.submit_event) # Log on Enter

        # --- Layouts ---
        control_layout = QHBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.addWidget(self.play_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.current_time_label)
        control_layout.addWidget(self.position_slider)
        control_layout.addWidget(self.total_time_label)

        layout = QVBoxLayout()
        # --- Set stretch factor for video widget to take maximum space ---
        layout.addWidget(self.video_widget, 1) # Add stretch factor of 1
        # ----------------------------------------------------------------
        layout.addLayout(control_layout)
        layout.addWidget(self.event_input) # Place input below controls

        self.setLayout(layout)

        # Set video output
        self.media_player.setVideoOutput(self.video_widget)

        # --- Connect Signals ---
        self.media_player.stateChanged.connect(self.handle_state_changed)
        self.media_player.positionChanged.connect(self.update_position)
        self.media_player.durationChanged.connect(self.update_duration)
        self.media_player.error.connect(self.handle_error)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status)

        # Allow widget to receive key presses
        self.setFocusPolicy(Qt.StrongFocus)
        self.video_widget.setFocusPolicy(Qt.NoFocus) # Prevent video widget stealing focus

    def load_video(self, file_path):
        """Loads a video file into the player."""
        self.stop_video() # Stop any current playback
        self.logged_events = [] # Clear previous logs
        self.is_paused_for_log = False
        self.event_input.setEnabled(False)
        self.event_input.setPlaceholderText("Press Space to pause and log event...")

        if file_path:
            media_content = QMediaContent(QUrl.fromLocalFile(file_path))
            if media_content.isNull():
                 self.handle_error("Cannot create QMediaContent. Invalid file path or format?")
                 self.video_loaded_signal.emit(False, f"Error: Invalid file path or format '{file_path}'")
                 return False

            self.media_player.setMedia(media_content)
            if self.media_player.media().isNull():
                self.handle_error("Media is null after setting.")
                self.video_loaded_signal.emit(False, f"Error: Could not set media for '{file_path}'")
                return False

            # Enable buttons after media is set, state change will confirm load success
            # self.play_button.setEnabled(True) # Enablement handled by media status change
            # self.stop_button.setEnabled(True)
            # self.position_slider.setEnabled(True)
            # Emit signal after setting media, status change will confirm loading
            # We'll rely on handle_media_status to emit the final success signal
            return True
        else:
            self.video_loaded_signal.emit(False, "Error: No file path provided.")
            return False

    def toggle_play_pause(self):
        """Toggles video playback between play and pause."""
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
        else:
            # If paused for logging, don't resume via button, only via event submission
            if not self.is_paused_for_log:
                self.media_player.play()

    def stop_video(self):
        """Stops video playback and resets position."""
        self.media_player.stop()
        # Icon is handled by stateChanged signal

    def set_position(self, position):
        """Sets the playback position."""
        if not self.media_player.isSeekable(): return
        # Only set position if the slider movement wasn't triggered by playback
        # Check difference to avoid setting during normal playback updates
        if abs(self.media_player.position() - position) > 500: # Threshold to detect user drag
            self.media_player.setPosition(position)


    def update_position(self, position):
        """Updates the slider position and current time label."""
        if not self.position_slider.isSliderDown(): # Only update if user isn't dragging
             # Check if the new position differs significantly from the slider's current value
             # This prevents feedback loops where setting the value triggers the signal again
             if abs(self.position_slider.value() - position) > 100:
                 self.position_slider.setValue(position)
        self.current_time_label.setText(self.format_time(position))

    def update_duration(self, duration):
        """Updates the slider range and total time label."""
        print(f"Video Duration Detected: {duration} ms") # Debug print
        self.position_slider.setRange(0, duration)
        self.total_time_label.setText(self.format_time(duration))
        # Enable slider only if duration is valid and media is seekable
        self.position_slider.setEnabled(duration > 0 and self.media_player.isSeekable())

    def handle_state_changed(self, state):
        """Updates the play/pause button icon based on playback state."""
        if state == QMediaPlayer.PlayingState:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            # Ensure input is disabled when playing
            if not self.is_paused_for_log:
                 self.event_input.setEnabled(False)
                 self.event_input.setPlaceholderText("Press Space to pause and log event...")
        else: # Paused, Stopped, etc.
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

        # If stopped, ensure log state is reset
        if state == QMediaPlayer.StoppedState:
             self.is_paused_for_log = False
             self.event_input.setEnabled(False)
             self.event_input.clear()
             self.event_input.setPlaceholderText("Press Space to pause and log event...")


    def handle_media_status(self, status):
        """Handles media status changes, like loaded or errors."""
        print(f"Media Status Changed: {status}") # Debug print
        if status == QMediaPlayer.LoadedMedia:
            # Media is loaded and ready (duration known, seekable)
            self.play_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.position_slider.setEnabled(self.media_player.isSeekable())
            file_name = "Unknown Video"
            try:
                url = self.media_player.media().canonicalUrl()
                if url.isLocalFile():
                    file_name = os.path.basename(url.toLocalFile())
            except Exception:
                pass # Ignore errors getting filename
            self.video_loaded_signal.emit(True, f"Video '{file_name}' loaded successfully.")
        elif status == QMediaPlayer.EndOfMedia:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            # Optionally stop or loop here
        elif status == QMediaPlayer.InvalidMedia:
            self.handle_error("Invalid media file.")
            self.video_loaded_signal.emit(False, "Error: Invalid media file.")
        elif status == QMediaPlayer.LoadingMedia:
             self.play_button.setEnabled(False)
             self.stop_button.setEnabled(False)
             self.position_slider.setEnabled(False)
        elif status == QMediaPlayer.StalledMedia or status == QMediaPlayer.BufferingMedia:
             print("Media stalled or buffering...") # Debug info
        elif status == QMediaPlayer.BufferedMedia:
             print("Media buffered.") # Debug info
             # Might be ready to enable controls here if not already enabled by LoadedMedia
             if not self.play_button.isEnabled():
                 self.play_button.setEnabled(True)
                 self.stop_button.setEnabled(True)
                 self.position_slider.setEnabled(self.media_player.isSeekable())


    def handle_error(self, error_string=""):
        """Handles media player errors."""
        # Use the provided error string or get from player
        msg = error_string if error_string else self.media_player.errorString()
        print(f"Video Player Error: {msg}") # Log to console
        self.play_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.position_slider.setEnabled(False)
        self.current_time_label.setText("Error")
        # Optionally show a message box to the user

    def keyPressEvent(self, event):
        """Handles key presses, specifically the spacebar for logging."""
        media_state = self.media_player.state()
        # Allow logging if playing OR if paused/stopped but media is loaded/seekable
        can_log_now = (media_state == QMediaPlayer.PlayingState or
                       ((media_state == QMediaPlayer.PausedState or media_state == QMediaPlayer.StoppedState) and
                        self.media_player.isSeekable()))

        if event.key() == Qt.Key_Space:
            if can_log_now and not self.is_paused_for_log: # Check if not already paused for logging
                # Store timestamp *before* potentially pausing if stopped
                self.log_timestamp_ms = self.media_player.position()
                if media_state == QMediaPlayer.PlayingState:
                    self.media_player.pause() # Pause if it was playing

                self.is_paused_for_log = True
                self.event_input.setEnabled(True)
                self.event_input.setPlaceholderText(f"Log event at {self.format_time(self.log_timestamp_ms)}...")
                # ******** FIX: Set focus to the input field ********
                self.event_input.setFocus()
                # ***************************************************
                self.event_input.clear()
                event.accept() # Mark event as handled
            elif self.is_paused_for_log:
                 # If already paused for log, space does nothing until Enter
                 event.ignore()
            else:
                 event.ignore() # Ignore space if cannot log (e.g., no media loaded/seekable)
        else:
            # Allow other key events to pass through
            event.ignore()

    def submit_event(self):
        """Logs the event from the input field and resumes playback."""
        if not self.is_paused_for_log:
            return # Only submit if paused for logging

        event_text = self.event_input.text().strip()
        timestamp_str = self.format_time(self.log_timestamp_ms)

        if event_text:
            log_entry = f"{timestamp_str} - {event_text}"
            self.logged_events.append(log_entry)
            self.event_logged_signal.emit(log_entry) # Emit signal for display
            print(f"Logged: {log_entry}") # Console log
        else:
            # Logged empty event, just resume
             self.event_logged_signal.emit(f"{timestamp_str} - (Resumed without logging)")
             print(f"Resumed at {timestamp_str} without logging event.")

        # Reset state and resume playback
        self.is_paused_for_log = False
        self.event_input.setEnabled(False)
        self.event_input.clear()
        self.event_input.setPlaceholderText("Press Space to pause and log event...")
        # Set focus back to this widget to capture space again
        self.setFocus()
        # Play only if the player is not already playing (e.g., if user double-submits quickly)
        if self.media_player.state() != QMediaPlayer.PlayingState:
             self.media_player.play()

    def get_logged_events(self):
        """Returns the list of logged events."""
        return self.logged_events

    def format_time(self, ms):
        """Formats milliseconds into HH:MM:SS string."""
        if ms < 0: ms = 0
        # Round to nearest second for display consistency
        total_seconds = round(ms / 1000.0)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# --- END OF FILE video_player_widget.py ---