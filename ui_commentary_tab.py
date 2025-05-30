# ui_commentary_tab.py
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QLineEdit, QTextEdit, QFileDialog, QMessageBox
)

class CommentaryTab(QWidget):
    """QWidget for the Commentary Generation tab."""
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
        main_commentator_label = QLabel("Main Commentator:")
        self.main_commentator_combo = QComboBox()
        self.main_commentator_combo.currentIndexChanged.connect(
            lambda index: self.settings.setValue("main_commentator", self.main_commentator_combo.itemData(index)) if index >= 0 else None
        )
        comm_select_layout.addWidget(main_commentator_label)
        comm_select_layout.addWidget(self.main_commentator_combo)
        comm_select_layout.addStretch()
        layout.addLayout(comm_select_layout)

        # Input File Selection
        input_layout = QHBoxLayout()
        input_label = QLabel("Input file (Filtered/Edited):")
        self.commentary_input = QLineEdit()
        self.commentary_input.setPlaceholderText("Select filtered data (.txt) or output from editor")
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_commentary_input)
        input_layout.addWidget(input_label)
        input_layout.addWidget(self.commentary_input)
        input_layout.addWidget(browse_button)
        layout.addLayout(input_layout)

        # Generate Button
        self.generate_button = QPushButton("Generate Commentary") # Store button reference
        self.generate_button.clicked.connect(self.generate_commentary)
        layout.addWidget(self.generate_button)

        # Output Display
        output_label = QLabel("Generated Commentary:")
        self.commentary_output = QTextEdit()
        self.commentary_output.setReadOnly(True)
        self.commentary_output.setPlaceholderText("Generated commentary text will appear here...")
        layout.addWidget(output_label)
        layout.addWidget(self.commentary_output)

    def update_commentator_combo(self, commentators, current_selection):
        """Populates the commentator combobox."""
        combo_box = self.main_commentator_combo
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

    def browse_commentary_input(self):
        """Opens dialog to select input file for commentary."""
        last_dir = self.settings.value("last_commentary_input_dir", "Race Data")
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Input File for Commentary", last_dir, "Text Files (*_filtered.txt *.txt)")
        if file_name:
             self.commentary_input.setText(file_name)
             self.settings.setValue("last_commentary_input_dir", os.path.dirname(file_name))

    def generate_commentary(self):
        """Initiates commentary generation via MainWindow."""
        input_path = self.commentary_input.text()

        # Auto-populate from filterer output if empty
        if not input_path and self.main_window.last_filter_output_path:
             filter_out = self.main_window.last_filter_output_path
             if filter_out and os.path.exists(filter_out):
                 input_path = filter_out
                 self.commentary_input.setText(input_path)
                 self.main_window.update_console(f"Using last filter output for commentary: {input_path}")
             else:
                 QMessageBox.warning(self, "Input Missing", "Select input or run filter (output missing).")
                 return
        elif not input_path:
             QMessageBox.warning(self, "Input Missing", "Select input file or run filter first.")
             return

        if not os.path.exists(input_path):
             QMessageBox.warning(self, "File Not Found", f"Input file not found:\n{input_path}")
             return

        main_comm_name = self.main_commentator_combo.currentData()
        if not main_comm_name:
             QMessageBox.warning(self, "Commentator Missing", "Select a main commentator.")
             return

        # Let MainWindow handle settings checks and thread start
        self.main_window.start_commentary_generation(input_path, main_comm_name)
        self.commentary_output.clear()
        # Optionally disable button
        # self.generate_button.setEnabled(False)

    def on_commentary_finished(self, success: bool, output_path: str or None):
        """Called by MainWindow when commentary generation is done."""
        # self.generate_button.setEnabled(True) # Re-enable button

        if success and output_path and os.path.exists(output_path):
              self.main_window.update_console(f"Commentary saved to: {output_path}")
              # Let MainWindow know for the next step
              self.main_window.last_commentary_output_path = output_path
              QMessageBox.information(self, "Commentary Complete", f"Commentary finished.\nSaved to: {output_path}")
        elif success:
             self.main_window.update_console("Commentary generation finished, but the output file was not found.")
             QMessageBox.warning(self, "Commentary Complete", "Commentary finished, but output file missing.")
        else:
             self.main_window.update_console("Commentary generation failed.")
             QMessageBox.warning(self, "Commentary Failed", "Commentary generation failed. Check console log.")

    def update_output(self, text):
        """Appends text to the commentary output display."""
        self.commentary_output.append(text)
        scrollbar = self.commentary_output.verticalScrollBar()
        if scrollbar: scrollbar.setValue(scrollbar.maximum())

    def set_input_path(self, path):
        """Sets the input path text field."""
        if path and os.path.exists(path):
            self.commentary_input.setText(path)
        else:
            # Optionally clear if path invalid, or leave as is
            pass