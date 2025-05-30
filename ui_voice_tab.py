# ui_voice_tab.py
import os
import sys
import traceback
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QLineEdit, QTextEdit, QFileDialog, QMessageBox
)

class VoiceTab(QWidget):
    """QWidget for the Voice Generation tab."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.settings = main_window.settings

        self._setup_ui()

    def _setup_ui(self):
        """Sets up the UI elements for this tab."""
        layout = QVBoxLayout(self)

        # Commentator Selection
        comm_select_layout = QHBoxLayout()
        commentator_label = QLabel("Select Commentator Voice:")
        self.voice_commentator_combo = QComboBox()
        self.voice_commentator_combo.currentIndexChanged.connect(
            lambda index: self.settings.setValue("voice_commentator", self.voice_commentator_combo.itemData(index)) if index >= 0 else None
        )
        comm_select_layout.addWidget(commentator_label)
        comm_select_layout.addWidget(self.voice_commentator_combo)
        comm_select_layout.addStretch()
        layout.addLayout(comm_select_layout)

        # Input File Selection
        input_layout = QHBoxLayout()
        input_label = QLabel("Input file (Generated Commentary):")
        self.voice_input = QLineEdit()
        self.voice_input.setPlaceholderText("Select commentary text file (.txt) or output from previous step")
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_voice_input)
        input_layout.addWidget(input_label)
        input_layout.addWidget(self.voice_input)
        input_layout.addWidget(browse_button)
        layout.addLayout(input_layout)

        # Generate Button
        self.generate_button = QPushButton("Generate Voice Commentary (using Cartesia)") # Store ref
        self.generate_button.clicked.connect(self.generate_voice)
        layout.addWidget(self.generate_button)

        # Output Display
        output_label = QLabel("Voice Generation Log:")
        self.voice_output = QTextEdit()
        self.voice_output.setReadOnly(True)
        self.voice_output.setPlaceholderText("Voice generation progress and status will appear here...")
        layout.addWidget(output_label)
        layout.addWidget(self.voice_output)

    def update_commentator_combo(self, commentators, current_selection):
        """Populates the commentator combobox."""
        combo_box = self.voice_commentator_combo
        combo_box.blockSignals(True)
        combo_box.clear()
        selected_index = 0

        if commentators:
            for i, metadata in enumerate(commentators):
                display_text = f"{metadata.name} - {metadata.style}"
                combo_box.addItem(display_text, metadata.name)
                if metadata.name == current_selection:
                    selected_index = i

            if combo_box.count() > 0:
                if 0 <= selected_index < combo_box.count():
                    combo_box.setCurrentIndex(selected_index)
                else:
                    combo_box.setCurrentIndex(0)
        combo_box.blockSignals(False)

    def browse_voice_input(self):
        """Opens dialog to select input file for voice generation."""
        last_dir = self.settings.value("last_voice_input_dir", "Race Data")
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Input File for Voice Generation", last_dir, "Text Files (*_commentary.txt *_filled.txt *.txt)")
        if file_name:
             self.voice_input.setText(file_name)
             self.settings.setValue("last_voice_input_dir", os.path.dirname(file_name))

    def generate_voice(self):
        """Initiates voice generation via MainWindow."""
        input_path = self.voice_input.text()

        # Auto-populate from commentary output if empty
        if not input_path and self.main_window.last_commentary_output_path:
            comm_out = self.main_window.last_commentary_output_path
            if comm_out and os.path.exists(comm_out):
                 input_path = comm_out
                 self.voice_input.setText(input_path)
                 self.main_window.update_console(f"Using last commentary output for voice: {input_path}")
            else:
                 QMessageBox.warning(self, "Input Missing", "Select input or run commentary generation (output missing).")
                 return
        elif not input_path:
            QMessageBox.warning(self, "Input Missing", "Select input file or run commentary generation.")
            return

        if not os.path.exists(input_path):
             QMessageBox.warning(self, "File Not Found", f"Input file not found:\n{input_path}")
             return

        voice_comm_name = self.voice_commentator_combo.currentData()
        if not voice_comm_name:
             QMessageBox.warning(self, "Commentator Missing", "Select a commentator voice.")
             return

        # Let MainWindow handle settings checks and thread start
        self.main_window.start_voice_generation(input_path, voice_comm_name)
        self.voice_output.clear()
        # Optionally disable button
        # self.generate_button.setEnabled(False)

    def on_voice_finished(self, success: bool, output_dir: str or None):
        """Called by MainWindow when voice generation is done."""
        # self.generate_button.setEnabled(True) # Re-enable button

        if success and output_dir and os.path.isdir(output_dir):
              self.main_window.update_console(f"Voice output saved in: {output_dir}")
              # Ask user if they want to open the directory
              reply = QMessageBox.question(self, "Open Output Directory?",
                                           f"Voice generation complete.\nAudio files saved in:\n{output_dir}\n\nOpen this directory?",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
              if reply == QMessageBox.Yes:
                  try:
                      if sys.platform == 'win32': os.startfile(os.path.normpath(output_dir))
                      elif sys.platform == 'darwin': os.system(f'open "{output_dir}"')
                      else: os.system(f'xdg-open "{output_dir}"')
                  except Exception as e:
                      self.main_window.update_console(f"Could not open directory: {e}")
                      QMessageBox.warning(self, "Open Error", f"Could not open directory: {e}")
              # Let MainWindow know the output path for the next step (maybe just the dir?)
              self.main_window.last_voice_output_dir = output_dir
              # TODO: Maybe find the *_filled.txt and matching audio for director?
              # self.main_window.update_director_inputs(script_path, audio_path)

        elif success:
             self.main_window.update_console("Voice generation finished, but output directory not found.")
             QMessageBox.warning(self, "Voice Generation Complete", "Finished, but output directory missing.")
        else:
             self.main_window.update_console("Voice generation failed.")
             QMessageBox.warning(self, "Voice Generation Failed", "Voice generation failed. Check console log.")


    def update_output(self, text):
        """Appends text to the voice generation log display."""
        self.voice_output.append(text)
        scrollbar = self.voice_output.verticalScrollBar()
        if scrollbar: scrollbar.setValue(scrollbar.maximum())

    def set_input_path(self, path):
        """Sets the input path text field."""
        if path and os.path.exists(path):
            self.voice_input.setText(path)