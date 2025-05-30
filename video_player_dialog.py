# video_player_dialog.py (or add to main_window.py)
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QMessageBox, QTextEdit, QLabel
from PyQt5.QtCore import pyqtSignal, Qt
from video_player_widget import VideoPlayerWidget # Assuming video_player_widget.py exists
import os

class VideoPlayerDialog(QDialog):
    # Signal when the dialog is closing, passing logged events
    dialog_closing_signal = pyqtSignal(list)
    # Signal to log messages to the main window's console
    log_message_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Event Logger")
        self.setGeometry(150, 150, 700, 550) # Initial size, resizable
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinMaxButtonsHint) # Add min/max buttons

        self.video_player_widget = VideoPlayerWidget(self)

        # Add the log display *inside* the dialog now
        self.video_log_display = QTextEdit(self)
        self.video_log_display.setReadOnly(True)
        self.video_log_display.setPlaceholderText("Logged video events will appear here...")
        self.video_log_display.setFixedHeight(100) # Keep log display smaller

        layout = QVBoxLayout(self)
        layout.addWidget(self.video_player_widget)
        layout.addWidget(QLabel("Logged Events:", self))
        layout.addWidget(self.video_log_display)

        # Connect internal signals
        self.video_player_widget.event_logged_signal.connect(self.update_log_display_local)
        # Forward video loaded signal to log message
        self.video_player_widget.video_loaded_signal.connect(self.handle_video_loaded_status)

        self.video_file_path = None

    def load_and_show(self, file_path):
        self.log_message_signal.emit(f"Dialog: Attempting to load video: {file_path}")
        self.video_file_path = file_path # Store for potential saving reference
        if self.video_player_widget.load_video(file_path):
            self.show()
            self.video_player_widget.setFocus() # Focus player for spacebar immediately
            return True
        else:
            self.log_message_signal.emit(f"Dialog: Failed to load video '{file_path}'.")
            # Error should be handled by video_player_widget's signal
            return False

    def handle_video_loaded_status(self, success, message):
        """Forwards status to main log and handles errors."""
        self.log_message_signal.emit(message) # Log success/failure to main console
        if not success:
            QMessageBox.critical(self, "Video Load Error", message)
            # Close the dialog if loading failed catastrophically after opening attempt
            self.reject() # Close dialog

    def update_log_display_local(self, text):
        """Updates the QTextEdit within this dialog."""
        self.video_log_display.append(text)
        scrollbar = self.video_log_display.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def get_logged_events(self):
        """Public method to retrieve events."""
        return self.video_player_widget.get_logged_events()

    def get_video_file_path(self):
        """Public method to retrieve video file path."""
        return self.video_file_path

    def closeEvent(self, event):
        """Override close event to stop video and emit signal."""
        print("VideoPlayerDialog closeEvent triggered")
        self.video_player_widget.stop_video() # Ensure video stops
        logged_events = self.get_logged_events()
        self.dialog_closing_signal.emit(logged_events) # Emit signal with events
        super().closeEvent(event)

    def reject(self): # Also handle closing via Esc key or system button
        print("VideoPlayerDialog reject triggered")
        self.close()