# ui_highlight_tab.py
import os
import traceback # For error logging if needed
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QLineEdit, QPushButton,
    QLabel, QHBoxLayout, QComboBox, QFileDialog, QMessageBox, QInputDialog
)
from csv_creator_widget import CSVCreatorWidget
from ui_prompt_dialog import PromptEditDialog # Import the dialog

class HighlightReelTab(QWidget):
    """QWidget for the Highlight Reel Creation tab."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.settings = main_window.settings
        self.data_filterer_prompt_manager = main_window.data_filterer_prompt_manager
        self.csv_creator = CSVCreatorWidget() # Instantiate the editor here

        self._setup_ui()
        self.update_data_filterer_prompts() # Initial population

    def _setup_ui(self):
        """Sets up the UI elements for this tab."""
        layout = QVBoxLayout(self)

        # --- Data Input and Filtering Group ---
        filter_group = QGroupBox("Data Input and Filtering")
        filter_layout = QVBoxLayout()

        # File Input Row
        input_layout = QHBoxLayout()
        data_path_label = QLabel("Race Data File:")
        self.data_path_input = QLineEdit()
        self.data_path_input.setPlaceholderText("Select raw data log (.txt) or video log (.txt)")
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_data_file)
        input_layout.addWidget(data_path_label)
        input_layout.addWidget(self.data_path_input)
        input_layout.addWidget(browse_button)
        filter_layout.addLayout(input_layout)

        # Filter Prompt Row
        prompt_layout = QHBoxLayout()
        prompt_label = QLabel("Filter Prompt:")
        self.data_filterer_prompt_combo = QComboBox()
        self.data_filterer_prompt_combo.currentIndexChanged.connect(
            lambda index: self.settings.setValue("data_filterer_selected_prompt", self.data_filterer_prompt_combo.itemData(index)) if index >= 0 else None
        )
        add_prompt_button = QPushButton("Add")
        add_prompt_button.setToolTip("Add a new filter prompt")
        add_prompt_button.clicked.connect(self.add_data_filterer_prompt)
        edit_prompt_button = QPushButton("Edit")
        edit_prompt_button.setToolTip("Edit the selected filter prompt")
        edit_prompt_button.clicked.connect(self.edit_data_filterer_prompt)
        delete_prompt_button = QPushButton("Delete")
        delete_prompt_button.setToolTip("Delete the selected filter prompt")
        delete_prompt_button.clicked.connect(self.delete_data_filterer_prompt)
        prompt_layout.addWidget(prompt_label)
        prompt_layout.addWidget(self.data_filterer_prompt_combo, 1) # Give combo more space
        prompt_layout.addWidget(add_prompt_button)
        prompt_layout.addWidget(edit_prompt_button)
        prompt_layout.addWidget(delete_prompt_button)
        filter_layout.addLayout(prompt_layout)

        # Filter Button Row
        filter_button_layout = QHBoxLayout()
        self.filter_button = QPushButton("Filter Data") # Store button reference
        self.filter_button.clicked.connect(self.filter_data)
        filter_button_layout.addStretch()
        filter_button_layout.addWidget(self.filter_button)
        filter_button_layout.addStretch()
        filter_layout.addLayout(filter_button_layout)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # --- Highlight Reel Editor Group ---
        csv_creator_group = QGroupBox("Highlight Reel Editor")
        csv_creator_layout = QVBoxLayout()

        # Load Existing Button Row
        load_csv_layout = QHBoxLayout()
        load_csv_button = QPushButton("Load Existing Filtered File")
        load_csv_button.clicked.connect(self.load_existing_file)
        load_csv_layout.addWidget(load_csv_button)
        load_csv_layout.addStretch()
        csv_creator_layout.addLayout(load_csv_layout)

        # Add the CSVCreatorWidget (the editor table)
        csv_creator_layout.addWidget(self.csv_creator)

        csv_creator_group.setLayout(csv_creator_layout)
        layout.addWidget(csv_creator_group)

    def browse_data_file(self):
        """Opens dialog to select race data/log file."""
        last_dir = self.settings.value("last_data_browse_dir", "Race Data")
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Race Data/Log File", last_dir, "Text Files (*.txt)")
        if file_name:
             self.data_path_input.setText(file_name)
             self.settings.setValue("last_data_browse_dir", os.path.dirname(file_name))

    def update_data_filterer_prompts(self):
        """Populates the data filterer prompt combobox."""
        current_selection = self.settings.value("data_filterer_selected_prompt", "Default")
        combo_box = self.data_filterer_prompt_combo

        combo_box.blockSignals(True)
        combo_box.clear()
        prompts = self.data_filterer_prompt_manager.list_prompts()

        if not prompts:
             self.data_filterer_prompt_manager.ensure_default_prompt("Default", "data_filterer_prompt.txt")
             prompts = self.data_filterer_prompt_manager.list_prompts()

        selected_index = 0
        for i, name in enumerate(prompts):
            combo_box.addItem(name, name)
            if name == current_selection:
                selected_index = i

        if prompts:
            if 0 <= selected_index < combo_box.count():
                 combo_box.setCurrentIndex(selected_index)
            elif combo_box.count() > 0:
                 combo_box.setCurrentIndex(0)
        else:
             QMessageBox.warning(self, "Prompt Error", "No data filterer prompts found.")

        combo_box.blockSignals(False)

    def add_data_filterer_prompt(self):
        """Adds a new prompt for the data filterer."""
        name, ok = QInputDialog.getText(self, "Add Prompt", "Enter a name for the new prompt:")
        if ok and name and name.strip():
            name = name.strip()
            if name in self.data_filterer_prompt_manager.list_prompts():
                 QMessageBox.warning(self, "Name Exists", f"A prompt named '{name}' already exists.")
                 return
            dialog = PromptEditDialog(name, "", self)
            if dialog.exec_():
                content = dialog.get_content()
                if self.data_filterer_prompt_manager.save_prompt(name, content):
                    self.update_data_filterer_prompts()
                    index = self.data_filterer_prompt_combo.findData(name)
                    if index >= 0: self.data_filterer_prompt_combo.setCurrentIndex(index)
                    QMessageBox.information(self, "Success", f"Prompt '{name}' added.")
                else:
                    QMessageBox.warning(self, "Error", f"Failed to save prompt '{name}'.")
        elif ok:
             QMessageBox.warning(self, "Invalid Name", "Prompt name cannot be empty.")

    def edit_data_filterer_prompt(self):
        """Edits the selected data filterer prompt."""
        current_name = self.data_filterer_prompt_combo.currentData()
        if not current_name:
             QMessageBox.warning(self, "Selection Error", "Select a prompt to edit.")
             return

        content = self.data_filterer_prompt_manager.load_prompt(current_name)
        if content is None:
             QMessageBox.warning(self, "Load Error", f"Could not load prompt '{current_name}'.")
             return

        dialog = PromptEditDialog(current_name, content, self)
        if dialog.exec_():
            new_content = dialog.get_content()
            new_name, ok = QInputDialog.getText(self, "Rename Prompt (Optional)",
                                                "Enter new name (leave blank to keep current):",
                                                QLineEdit.Normal, current_name)
            if not ok: return

            save_name = new_name.strip() if new_name.strip() else current_name

            if save_name != current_name and save_name in self.data_filterer_prompt_manager.list_prompts():
                 QMessageBox.warning(self, "Name Exists", f"A prompt named '{save_name}' already exists.")
                 return

            if self.data_filterer_prompt_manager.save_prompt(save_name, new_content, original_name=current_name):
                self.update_data_filterer_prompts()
                index = self.data_filterer_prompt_combo.findData(save_name)
                if index >= 0: self.data_filterer_prompt_combo.setCurrentIndex(index)
                QMessageBox.information(self, "Success", f"Prompt '{save_name}' updated.")
            else:
                QMessageBox.warning(self, "Error", f"Failed to update prompt '{save_name}'.")

    def delete_data_filterer_prompt(self):
        """Deletes the selected data filterer prompt."""
        current_name = self.data_filterer_prompt_combo.currentData()
        if not current_name:
             QMessageBox.warning(self, "Selection Error", "Select a prompt to delete.")
             return
        if current_name == "Default":
             QMessageBox.warning(self, "Deletion Error", "The 'Default' prompt cannot be deleted.")
             return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Delete prompt '{current_name}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.data_filterer_prompt_manager.delete_prompt(current_name):
                self.update_data_filterer_prompts()
                QMessageBox.information(self, "Success", f"Prompt '{current_name}' deleted.")
            else:
                QMessageBox.warning(self, "Error", f"Failed to delete prompt '{current_name}'.")

    def filter_data(self):
        """Initiates the data filtering process via MainWindow."""
        input_path = self.data_path_input.text()
        if not input_path or not os.path.exists(input_path):
             QMessageBox.warning(self, "Input Error", "Select a valid race data/log file.")
             return

        prompt_name = self.data_filterer_prompt_combo.currentData()
        if not prompt_name:
             QMessageBox.warning(self, "Prompt Missing", "Select a filter prompt.")
             return

        # Let MainWindow handle settings checks and thread start
        self.main_window.start_filtering(input_path, prompt_name)
        # Optionally disable button
        # self.filter_button.setEnabled(False)

    def on_filtering_finished(self, success: bool, output_path: str or None):
        """Called by MainWindow when filtering is done."""
        # self.filter_button.setEnabled(True) # Re-enable button

        if success and output_path and os.path.exists(output_path):
            try:
                with open(output_path, 'r', encoding='utf-8', errors='replace') as file:
                     text_content = file.read()
                self.csv_creator.load_data(text_content)
                self.main_window.update_console(f"Loaded filtered data into editor: {output_path}")
                # Let MainWindow know the output path for the next step
                self.main_window.last_filter_output_path = output_path
                QMessageBox.information(self, "Filtering Complete", f"Filtered data loaded.\nSaved to: {output_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load filtered data: {str(e)}")
                self.main_window.update_console(f"Error loading filtered data: {e}\n{traceback.format_exc()}")
        elif success:
             QMessageBox.warning(self, "Filtering Complete", "Filtering finished, but the output file was not found.")
             self.main_window.update_console("Filtering process completed, but no valid output file was found.")
        else:
             QMessageBox.warning(self, "Filtering Failed", "Filtering process failed. Check console log.")
             self.main_window.update_console("Filtering process failed.")

    def load_existing_file(self):
        """Loads an existing file into the editor."""
        last_dir = self.settings.value("last_filtered_load_dir", "Race Data")
        file_name, _ = QFileDialog.getOpenFileName(self, "Load Filtered/Edited File", last_dir, "Text Files (*.txt)")

        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8', errors='replace') as file:
                     text_content = file.read()
                self.csv_creator.load_data(text_content)
                self.data_path_input.setText(file_name) # Update input path too
                self.settings.setValue("last_filtered_load_dir", os.path.dirname(file_name))
                # Set this as the potential input for commentary
                self.main_window.last_filter_output_path = file_name
                QMessageBox.information(self, "File Loaded", f"Loaded '{os.path.basename(file_name)}'.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")
                self.main_window.update_console(f"Error loading file: {e}\n{traceback.format_exc()}")