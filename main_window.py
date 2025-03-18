# main_window.py
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout, QTabWidget, QGroupBox,
    QFormLayout, QLineEdit, QPushButton, QLabel, QHBoxLayout, QComboBox, QTextEdit,
    QFileDialog, QMessageBox, QProgressBar, QRadioButton, QButtonGroup, QCheckBox
)
from PyQt5.QtCore import QSettings, Qt
from commentator_manager import CommentatorManager
from commentator_dialog import CommentatorDialog
from accident_settings_widget import AccidentSettingsWidget

# Import your existing modules for data collection, filtering, commentary, and voice generation.
from data_collector_ACC import DataCollector as DataCollectorACC
from data_collector_AMS2 import DataCollector as DataCollectorAMS2
from data_collector_AC import DataCollector as DataCollectorAC
from data_filterer import DataFilterer
from race_commentator import RaceCommentator
from voice_generator import VoiceGenerator
from csv_creator_widget import CSVCreatorWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bad AI Commentary")
        self.setGeometry(100, 100, 800, 600)

        self.settings = QSettings("BadAICommentary", "SimRacingCommentator")
        self.commentator_manager = CommentatorManager()

        # Apply "Always on Top" based on saved settings
        always_on_top = self.settings.value("always_on_top", False, type=bool)
        if always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Set up tab widget with signal connections for tab switching
        self.setup_tab_widget()  # Use our new method instead

        self.data_collector = None
        self.data_filterer = None
        self.race_commentator = None
        self.voice_generator = None

        # Set up the individual tabs
        self.setup_setup_tab()
        self.setup_highlight_reel_tab()
        self.setup_commentary_tab()
        self.setup_voice_tab()
        self.setup_settings_tab()

        # Refresh commentator combos after all tabs are set up
        self.refresh_commentator_combos()

        self.status_bar = self.statusBar()
        self.progress_bar = QProgressBar()
        self.status_bar.addPermanentWidget(self.progress_bar)

        # Debug output
        print("MainWindow initialization complete")
        print(f"Commentator count: {len(self.commentator_manager.get_all_commentators())}")

    def setup_tab_widget(self):
        """Set up the tab widget and connect tab change signals."""
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)

        self.setup_tab = QWidget()
        self.highlight_reel_tab = QWidget()
        self.commentary_tab = QWidget()
        self.voice_tab = QWidget()
        self.settings_tab = QWidget()

        self.tab_widget.addTab(self.setup_tab, "Let's go racing!")
        self.tab_widget.addTab(self.highlight_reel_tab, "Highlight Reel Creation")
        self.tab_widget.addTab(self.commentary_tab, "Commentary Generation")
        self.tab_widget.addTab(self.voice_tab, "Voice Generation")
        self.tab_widget.addTab(self.settings_tab, "Settings")

        # Connect the tab changed signal
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

    def on_tab_changed(self, index):
        """Handle tab changed event to refresh dynamic content."""
        print(f"Switched to tab {index}")

        # Commentary Generation tab
        if index == 2:  # Commentary tab is index 2
            print("Refreshing commentary tab combos")
            self.refresh_commentator_combos()
        # Voice Generation tab
        elif index == 3:  # Voice tab is index 3
            print("Refreshing voice tab combos")
            self.update_commentator_combos(self.voice_commentator_combo, "voice_commentator")

    def refresh_commentator_combos(self):
        """Refresh all commentator combo boxes."""
        print("Refreshing all commentator combo boxes")

        # Reload the commentator list to ensure we have the latest data
        commentators = self.commentator_manager.get_all_commentators()
        print(f"Found {len(commentators)} commentators")

        # Update the combo boxes
        self.update_commentator_combos(self.main_commentator_combo, "main_commentator")
        # If you have other combos, update them here too

    def setup_setup_tab(self):
        layout = QVBoxLayout(self.setup_tab)
        sim_label = QLabel("Select your sim:")
        self.sim_combo = QComboBox()
        self.sim_combo.addItems(["Assetto Corsa Competizione", "Assetto Corsa", "Automobilista 2"])

        # Add accident settings widget
        self.accident_settings = AccidentSettingsWidget()
        self.accident_settings.hide()  # Hidden by default

        # Connect sim selection to show/hide settings
        self.sim_combo.currentTextChanged.connect(self.on_sim_changed)

        self.start_stop_button = QPushButton("Start")
        self.start_stop_button.clicked.connect(self.toggle_data_collection)

        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)

        layout.addWidget(sim_label)
        layout.addWidget(self.sim_combo)
        layout.addWidget(self.accident_settings)
        layout.addWidget(self.start_stop_button)
        layout.addWidget(self.console_output)

    def on_sim_changed(self, sim_name):
        self.accident_settings.setVisible(sim_name == "Automobilista 2")

    def toggle_data_collection(self):
        if self.start_stop_button.text() == "Start":
            self.start_data_collection()
        else:
            self.stop_data_collection()

    def start_data_collection(self):
        sim = self.sim_combo.currentText()
        if sim == "Assetto Corsa Competizione":
            self.data_collector = DataCollectorACC()
        elif sim == "Assetto Corsa":
            self.data_collector = DataCollectorAC()
        else:
            self.data_collector = DataCollectorAMS2()
            # Update accident detection settings if it's AMS2
            if hasattr(self, 'accident_settings'):
                self.data_collector.update_accident_settings(
                    self.accident_settings.speed_threshold.value(),
                    self.accident_settings.time_threshold.value(),
                    self.accident_settings.proximity_time.value()
                )
                # Connect value changed signals to update collector
                self.accident_settings.speed_threshold.valueChanged.connect(
                    lambda v: self.data_collector.update_accident_settings(
                        v,
                        self.accident_settings.time_threshold.value(),
                        self.accident_settings.proximity_time.value()
                    )
                )
                self.accident_settings.time_threshold.valueChanged.connect(
                    lambda v: self.data_collector.update_accident_settings(
                        self.accident_settings.speed_threshold.value(),
                        v,
                        self.accident_settings.proximity_time.value()
                    )
                )
                self.accident_settings.proximity_time.valueChanged.connect(
                    lambda v: self.data_collector.update_accident_settings(
                        self.accident_settings.speed_threshold.value(),
                        self.accident_settings.time_threshold.value(),
                        v
                    )
                )

        self.data_collector.output_signal.connect(self.update_console)
        self.data_collector.progress_signal.connect(self.update_progress_bar)
        self.data_collector.start()
        self.start_stop_button.setText("Stop")

    def stop_data_collection(self):
        if hasattr(self, 'data_collector') and self.data_collector:
            self.data_collector.stop()
            self.update_console("Data collection stopped.")
        self.start_stop_button.setText("Start")

    def setup_highlight_reel_tab(self):
        layout = QVBoxLayout(self.highlight_reel_tab)

        # Data collection section
        input_layout = QHBoxLayout()
        data_path_label = QLabel("Enter the path to your race data file:")
        self.data_path_input = QLineEdit()
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_data_file)
        filter_button = QPushButton("Filter Data")
        filter_button.clicked.connect(self.filter_data)

        input_layout.addWidget(data_path_label)
        input_layout.addWidget(self.data_path_input)
        input_layout.addWidget(browse_button)
        input_layout.addWidget(filter_button)

        # CSV Creator section
        csv_creator_label = QLabel("Highlight Reel Editor")
        load_csv_layout = QHBoxLayout()
        load_csv_button = QPushButton("Load Existing File")
        load_csv_button.clicked.connect(self.load_existing_file)
        load_csv_layout.addWidget(load_csv_button)
        load_csv_layout.addStretch()

        self.csv_creator = CSVCreatorWidget()

        layout.addLayout(input_layout)
        layout.addWidget(csv_creator_label)
        layout.addLayout(load_csv_layout)
        layout.addWidget(self.csv_creator)

    def setup_commentary_tab(self):
        layout = QVBoxLayout(self.commentary_tab)

        # Main commentator selection
        main_commentator_layout = QVBoxLayout()
        main_commentator_label = QLabel("Commentator:")
        self.main_commentator_combo = QComboBox()
        # We'll populate it directly instead of using update_commentator_combos
        # Get all commentators
        commentators = self.commentator_manager.get_all_commentators()
        print(f"Setup tab found {len(commentators)} commentators")

        # Add them to the combo box
        for metadata in commentators:
            display_text = f"{metadata.name} - {metadata.style}"
            self.main_commentator_combo.addItem(display_text, metadata.name)
            print(f"Added commentator: {display_text}")

        # If empty, add a default
        if self.main_commentator_combo.count() == 0:
            self.main_commentator_combo.addItem("Geoff - Default", "Geoff")
            print("Added default Geoff commentator")

        # Set the saved selection if available
        saved_commentator = self.settings.value("main_commentator", "Geoff")
        for i in range(self.main_commentator_combo.count()):
            if self.main_commentator_combo.itemData(i) == saved_commentator:
                self.main_commentator_combo.setCurrentIndex(i)
                print(f"Set selected commentator to {saved_commentator}")
                break

        # Connect index changed signal
        self.main_commentator_combo.currentIndexChanged.connect(
            lambda: self.settings.setValue("main_commentator", self.main_commentator_combo.currentData())
        )

        main_commentator_layout.addWidget(main_commentator_label)
        main_commentator_layout.addWidget(self.main_commentator_combo)

        layout.addLayout(main_commentator_layout)

        # Rest of the existing commentary tab setup
        input_label = QLabel("Input file:")
        self.commentary_input = QLineEdit()
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_commentary_input)

        generate_button = QPushButton("Generate Commentary")
        generate_button.clicked.connect(self.generate_commentary)

        self.commentary_output = QTextEdit()
        self.commentary_output.setReadOnly(True)

        layout.addWidget(input_label)
        layout.addWidget(self.commentary_input)
        layout.addWidget(browse_button)
        layout.addWidget(generate_button)
        layout.addWidget(self.commentary_output)

        print(f"Commentary tab setup complete, combo box has {self.main_commentator_combo.count()} items")

    def setup_voice_tab(self):
        layout = QVBoxLayout(self.voice_tab)

        # Add commentator selection
        commentator_layout = QVBoxLayout()
        commentator_label = QLabel("Select Commentator Voice:")
        self.voice_commentator_combo = QComboBox()

        # Get all commentators
        commentators = self.commentator_manager.get_all_commentators()
        print(f"Voice tab found {len(commentators)} commentators")

        # Add them to the combo box
        for metadata in commentators:
            display_text = f"{metadata.name} - {metadata.style}"
            self.voice_commentator_combo.addItem(display_text, metadata.name)
            print(f"Added voice commentator: {display_text}")

        # If empty, add a default
        if self.voice_commentator_combo.count() == 0:
            self.voice_commentator_combo.addItem("Geoff - Default", "Geoff")
            print("Added default Geoff voice commentator")

        # Set the saved selection if available
        saved_commentator = self.settings.value("voice_commentator", "Geoff")
        for i in range(self.voice_commentator_combo.count()):
            if self.voice_commentator_combo.itemData(i) == saved_commentator:
                self.voice_commentator_combo.setCurrentIndex(i)
                print(f"Set selected voice commentator to {saved_commentator}")
                break

        # Connect index changed signal
        self.voice_commentator_combo.currentIndexChanged.connect(
            lambda: self.settings.setValue("voice_commentator", self.voice_commentator_combo.currentData())
        )

        commentator_layout.addWidget(commentator_label)
        commentator_layout.addWidget(self.voice_commentator_combo)

        input_label = QLabel("Input file:")
        self.voice_input = QLineEdit()
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_voice_input)

        generate_button = QPushButton("Generate Voice Commentary")
        generate_button.clicked.connect(self.generate_voice)

        self.voice_output = QTextEdit()
        self.voice_output.setReadOnly(True)

        layout.addLayout(commentator_layout)
        layout.addWidget(input_label)
        layout.addWidget(self.voice_input)
        layout.addWidget(browse_button)
        layout.addWidget(generate_button)
        layout.addWidget(self.voice_output)

        print(f"Voice tab setup complete, combo box has {self.voice_commentator_combo.count()} items")

    def setup_settings_tab(self):
        layout = QVBoxLayout(self.settings_tab)

        # API Keys Section
        api_keys_group = QGroupBox("API Keys")
        api_keys_layout = QFormLayout()

        self.claude_api_key_input = QLineEdit()
        self.claude_api_key_input.setEchoMode(QLineEdit.Password)
        self.claude_api_key_input.setText(self.settings.value("claude_api_key", ""))

        self.openai_api_key_input = QLineEdit()
        self.openai_api_key_input.setEchoMode(QLineEdit.Password)
        self.openai_api_key_input.setText(self.settings.value("openai_api_key", ""))

        self.eleven_labs_api_key_input = QLineEdit()
        self.eleven_labs_api_key_input.setEchoMode(QLineEdit.Password)
        self.eleven_labs_api_key_input.setText(self.settings.value("eleven_labs_api_key", ""))

        api_keys_layout.addRow("Claude API Key:", self.claude_api_key_input)
        api_keys_layout.addRow("OpenAI API Key:", self.openai_api_key_input)
        api_keys_layout.addRow("ElevenLabs API Key:", self.eleven_labs_api_key_input)
        api_keys_group.setLayout(api_keys_layout)

        # Model Selection Section
        model_selection_group = QGroupBox("Model Selection")
        model_selection_layout = QVBoxLayout()

        # Data Filterer Settings
        data_filterer_group = QGroupBox("Data Filterer")
        data_filterer_layout = QVBoxLayout()

        self.data_filterer_api_group = QButtonGroup()
        self.data_filterer_claude_radio = QRadioButton("Claude")
        self.data_filterer_openai_radio = QRadioButton("OpenAI")
        self.data_filterer_api_group.addButton(self.data_filterer_claude_radio)
        self.data_filterer_api_group.addButton(self.data_filterer_openai_radio)

        if self.settings.value("data_filterer_api", "claude") == "claude":
            self.data_filterer_claude_radio.setChecked(True)
        else:
            self.data_filterer_openai_radio.setChecked(True)

        self.data_filterer_model_input = QLineEdit()
        self.data_filterer_model_input.setText(self.settings.value("data_filterer_model", "claude-3-5-sonnet-20241022"))

        data_filterer_layout.addWidget(self.data_filterer_claude_radio)
        data_filterer_layout.addWidget(self.data_filterer_openai_radio)
        data_filterer_layout.addWidget(QLabel("Model:"))
        data_filterer_layout.addWidget(self.data_filterer_model_input)
        data_filterer_group.setLayout(data_filterer_layout)

        # Race Commentator Settings
        race_commentator_group = QGroupBox("Race Commentator")
        race_commentator_layout = QVBoxLayout()

        self.race_commentator_api_group = QButtonGroup()
        self.race_commentator_claude_radio = QRadioButton("Claude")
        self.race_commentator_openai_radio = QRadioButton("OpenAI")
        self.race_commentator_api_group.addButton(self.race_commentator_claude_radio)
        self.race_commentator_api_group.addButton(self.race_commentator_openai_radio)

        if self.settings.value("race_commentator_api", "claude") == "claude":
            self.race_commentator_claude_radio.setChecked(True)
        else:
            self.race_commentator_openai_radio.setChecked(True)

        self.race_commentator_model_input = QLineEdit()
        self.race_commentator_model_input.setText(
            self.settings.value("race_commentator_model", "claude-3-5-sonnet-20241022"))

        race_commentator_layout.addWidget(self.race_commentator_claude_radio)
        race_commentator_layout.addWidget(self.race_commentator_openai_radio)
        race_commentator_layout.addWidget(QLabel("Model:"))
        race_commentator_layout.addWidget(self.race_commentator_model_input)
        race_commentator_group.setLayout(race_commentator_layout)

        model_selection_layout.addWidget(data_filterer_group)
        model_selection_layout.addWidget(race_commentator_group)
        model_selection_group.setLayout(model_selection_layout)

        # Commentator Management Section
        commentator_group = QGroupBox("Commentator Management")
        commentator_layout = QVBoxLayout()

        # Commentator list
        self.commentator_list = QComboBox()
        self.update_commentator_list()

        # Buttons
        commentator_buttons_layout = QHBoxLayout()
        add_commentator_button = QPushButton("Add Commentator")
        add_commentator_button.clicked.connect(self.add_commentator)
        edit_commentator_button = QPushButton("Edit Commentator")
        edit_commentator_button.clicked.connect(self.edit_commentator)
        delete_commentator_button = QPushButton("Delete Commentator")
        delete_commentator_button.clicked.connect(self.delete_commentator)

        commentator_buttons_layout.addWidget(add_commentator_button)
        commentator_buttons_layout.addWidget(edit_commentator_button)
        commentator_buttons_layout.addWidget(delete_commentator_button)

        commentator_layout.addWidget(self.commentator_list)
        commentator_layout.addLayout(commentator_buttons_layout)
        commentator_group.setLayout(commentator_layout)

        # Always on Top Toggle
        self.always_on_top_checkbox = QCheckBox("Always on Top")
        self.always_on_top_checkbox.setChecked(self.settings.value("always_on_top", False, type=bool))
        self.always_on_top_checkbox.stateChanged.connect(self.toggle_always_on_top)

        # Save Button
        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)

        layout.addWidget(api_keys_group)
        layout.addWidget(model_selection_group)
        layout.addWidget(commentator_group)
        layout.addWidget(self.always_on_top_checkbox)
        layout.addWidget(save_button)
        layout.addStretch()

    def toggle_always_on_top(self, state):
        if state == Qt.Checked:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()

    def update_commentator_list(self):
        """Update the list of available commentators in the combo box."""
        self.commentator_list.clear()
        for metadata in self.commentator_manager.get_all_commentators():
            display_text = f"{metadata.name} - {metadata.style}"
            self.commentator_list.addItem(display_text, metadata.name)

    def update_commentator_combos(self, combo_box, settings_key):
        """Update a commentator combo box and set its saved selection."""
        if not combo_box:
            return

        try:
            combo_box.blockSignals(True)  # Prevent signal emissions during update
            combo_box.clear()

            last_selected = self.settings.value(settings_key, "Geoff")
            selected_index = 0

            # Get commentators and ensure we have at least one
            commentators = self.commentator_manager.get_all_commentators()

            # Debug output - helpful to check what's happening
            print(f"Found {len(commentators)} commentators")
            for c in commentators:
                print(f"  - {c.name} ({c.style})")

            if not commentators:
                # This should not happen with our fixed get_all_commentators,
                # but as a fallback, add a default
                combo_box.addItem("Geoff - Default", "Geoff")
            else:
                # Add each commentator to the dropdown
                for i, metadata in enumerate(commentators):
                    display_text = f"{metadata.name} - {metadata.style}"
                    combo_box.addItem(display_text, metadata.name)

                    # Set the selected index if this matches the saved selection
                    if metadata.name == last_selected:
                        selected_index = i

                # Make sure we have a valid index
                if selected_index >= 0 and selected_index < combo_box.count():
                    combo_box.setCurrentIndex(selected_index)
        except Exception as e:
            print(f"Error updating combo box: {str(e)}")
            # Always ensure we have at least one item in the dropdown
            if combo_box.count() == 0:
                combo_box.addItem("Geoff - Default", "Geoff")
        finally:
            combo_box.blockSignals(False)  # Re-enable signals

            # Reconnect the selection change handler
            try:
                combo_box.currentIndexChanged.disconnect()  # Remove any existing connections
            except (TypeError, RuntimeError):
                pass  # No connections existed or other disconnect error

            # Connect the signal handler
            combo_box.currentIndexChanged.connect(
                lambda: self.settings.setValue(settings_key, combo_box.currentData())
            )

    def add_commentator(self):
        """Open dialog to add a new commentator."""
        dialog = CommentatorDialog(self)
        if dialog.exec_():
            data = dialog.get_data()
            success = self.commentator_manager.create_commentator(
                data['name'],
                data['personality'],
                data['style'],
                data['examples'],
                data['voice_id'],
                data['main_prompt'],
                data['second_pass_prompt']
            )
            if success:
                self.update_commentator_list()
                self.update_commentator_combos(self.main_commentator_combo, "main_commentator")
                self.update_commentator_combos(self.second_commentator_combo, "second_commentator")
                QMessageBox.information(self, "Success", "Commentator added successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to add commentator. Name may already exist.")

    def edit_commentator(self):
        """Open dialog to edit the selected commentator."""
        current_name = self.commentator_list.currentData()
        if not current_name:
            QMessageBox.warning(self, "Error", "Please select a commentator to edit.")
            return

        try:
            # Get metadata first and verify it exists
            metadata = self.commentator_manager.get_commentator_metadata(current_name)
            if not metadata:
                QMessageBox.warning(self, "Error", "Could not load commentator data.")
                return

            # Create dialog but don't show it yet
            dialog = CommentatorDialog(self, metadata)

            # Load prompts safely with error handling
            try:
                main_prompt = self.commentator_manager.get_prompt(current_name, second_pass=False)
                second_pass_prompt = self.commentator_manager.get_prompt(current_name, second_pass=True)

                if main_prompt:
                    dialog.main_prompt_edit.setText(main_prompt)
                if second_pass_prompt:
                    dialog.second_pass_prompt_edit.setText(second_pass_prompt)
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Could not load all prompt data: {str(e)}")

            # Show dialog and get result
            if dialog.exec_():
                data = dialog.get_data()

                # Verify data integrity before update
                if not all(key in data for key in ['name', 'personality', 'style', 'examples', 'voice_id']):
                    QMessageBox.warning(self, "Error", "Invalid commentator data format.")
                    return

                # Update with error handling
                try:
                    success = self.commentator_manager.update_commentator(
                        current_name,
                        data['name'],
                        data['personality'],
                        data['style'],
                        data['examples'],
                        data['voice_id'],
                        data.get('main_prompt', ''),
                        data.get('second_pass_prompt', '')
                    )

                    if success:
                        # Update UI elements safely
                        self.update_commentator_list()
                        self.update_commentator_combos(self.main_commentator_combo, "main_commentator")
                        self.update_commentator_combos(self.voice_commentator_combo, "voice_commentator")
                        QMessageBox.information(self, "Success", "Commentator updated successfully!")
                    else:
                        QMessageBox.warning(self, "Error", "Failed to update commentator.")
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to update commentator: {str(e)}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(e)}")
        finally:
            # Ensure dialog is properly closed
            if 'dialog' in locals():
                dialog.deleteLater()

    def delete_commentator(self):
        """Delete the selected commentator."""
        current_name = self.commentator_list.currentData()
        if not current_name:
            QMessageBox.warning(self, "Error", "Please select a commentator to delete.")
            return

        if current_name.lower() == "geoff":
            QMessageBox.warning(self, "Error", "Cannot delete the default commentator.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete the commentator '{current_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success = self.commentator_manager.delete_commentator(current_name)
            if success:
                self.update_commentator_list()
                self.update_commentator_combos(self.main_commentator_combo, "main_commentator")
                self.update_commentator_combos(self.second_commentator_combo, "second_commentator")
                QMessageBox.information(self, "Success", "Commentator deleted successfully!")
            else:
                QMessageBox.warning(self, "Error", "Failed to delete commentator.")

    def browse_data_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Race Data File", "", "Text Files (*.txt)")
        if file_name:
            self.data_path_input.setText(file_name)

    def load_existing_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Text File", "", "Text Files (*.txt)")
        if file_name:
            try:
                with open(file_name, 'r', encoding='utf-8') as file:
                    text_content = file.read()
                self.csv_creator.load_data(text_content)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def update_console(self, text):
        self.console_output.append(text)

    def filter_data(self):
        input_path = self.data_path_input.text()
        settings = self.get_data_filterer_settings()

        if settings["api"] == "claude" and not settings["claude_key"]:
            QMessageBox.warning(self, "API Key Missing", "Please enter your Claude API key in the Settings tab.")
            return
        elif settings["api"] == "openai" and not settings["openai_key"]:
            QMessageBox.warning(self, "API Key Missing", "Please enter your OpenAI API key in the Settings tab.")
            return

        if not input_path:
            QMessageBox.warning(self, "Input Missing", "Please select a race data file.")
            return

        try:
            self.data_filterer = DataFilterer(input_path, settings)
            self.data_filterer.progress_signal.connect(self.update_progress_bar)
            self.data_filterer.output_signal.connect(self.update_console)
            self.data_filterer.finished.connect(self.on_filtering_finished)
            self.data_filterer.start()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start data filtering: {str(e)}")

    def on_filtering_finished(self):
        filtered_file_path = self.data_filterer.get_output_path()
        try:
            with open(filtered_file_path, 'r', encoding='utf-8') as file:
                text_content = file.read()
            self.csv_creator.load_data(text_content)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load filtered data: {str(e)}")

    def browse_commentary_input(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Input File", "", "Text Files (*.txt)")
        if file_name:
            self.commentary_input.setText(file_name)

    def browse_voice_input(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Input File", "", "Text Files (*.txt)")
        if file_name:
            self.voice_input.setText(file_name)

    def generate_commentary(self):
        input_path = self.commentary_input.text()
        if not input_path:
            input_path = self.data_filterer.get_output_path() if hasattr(self, 'data_filterer') else None

        if not input_path:
            QMessageBox.warning(self, "Input Missing", "Please select an input file.")
            return

        # Get selected commentator data
        main_commentator = self.main_commentator_combo.currentData()
        if not main_commentator:
            QMessageBox.warning(self, "Error", "Please select a commentator.")
            return

        main_metadata = self.commentator_manager.get_commentator_metadata(main_commentator)
        if not main_metadata:
            QMessageBox.warning(self, "Error", "Could not load commentator data.")
            return

        # Get the main prompt
        main_prompt = self.commentator_manager.get_prompt(main_commentator, second_pass=False)

        settings = self.get_race_commentator_settings()
        settings.update({
            'main_prompt': main_prompt,
            'main_voice_id': main_metadata.voice_id
        })

        try:
            self.race_commentator = RaceCommentator(input_path, settings)
            self.race_commentator.output_signal.connect(self.update_commentary_output)
            self.race_commentator.progress_signal.connect(self.update_progress_bar)
            self.race_commentator.start()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start commentary generation: {str(e)}")

    def generate_voice(self):
        input_path = self.voice_input.text()
        if not input_path:
            input_path = self.race_commentator.get_output_path() if hasattr(self, 'race_commentator') else None

        if not input_path:
            QMessageBox.warning(self, "Input Missing", "Please select an input file.")
            return

        eleven_labs_api_key = self.get_eleven_labs_api_key()
        if not eleven_labs_api_key:
            QMessageBox.warning(self, "API Key Missing", "Please enter your ElevenLabs API key in the Settings tab.")
            return

        # Get the selected commentator's voice ID
        selected_commentator = self.voice_commentator_combo.currentData()
        if not selected_commentator:
            QMessageBox.warning(self, "Error", "Please select a commentator.")
            return

        metadata = self.commentator_manager.get_commentator_metadata(selected_commentator)
        if not metadata:
            QMessageBox.warning(self, "Error", "Could not load commentator data.")
            return

        self.voice_generator = VoiceGenerator(input_path, eleven_labs_api_key, metadata.voice_id)
        self.voice_generator.output_signal.connect(self.update_voice_output)
        self.voice_generator.progress_signal.connect(self.update_progress_bar)
        self.voice_generator.start()

    def update_commentary_output(self, text):
        self.commentary_output.append(text)

    def update_voice_output(self, text):
        self.voice_output.append(text)

    def update_progress_bar(self, value):
        self.progress_bar.setValue(value)

    def save_settings(self):
        self.settings.setValue("claude_api_key", self.claude_api_key_input.text())
        self.settings.setValue("openai_api_key", self.openai_api_key_input.text())
        self.settings.setValue("eleven_labs_api_key", self.eleven_labs_api_key_input.text())

        self.settings.setValue("data_filterer_api",
                               "claude" if self.data_filterer_claude_radio.isChecked() else "openai")
        self.settings.setValue("data_filterer_model", self.data_filterer_model_input.text())

        self.settings.setValue("race_commentator_api",
                               "claude" if self.race_commentator_claude_radio.isChecked() else "openai")
        self.settings.setValue("race_commentator_model", self.race_commentator_model_input.text())

        # Save the Always on Top setting
        self.settings.setValue("always_on_top", self.always_on_top_checkbox.isChecked())

        QMessageBox.information(self, "Settings Saved", "Your settings have been saved successfully!")

    def get_claude_api_key(self):
        return self.settings.value("claude_api_key", "")

    def get_openai_api_key(self):
        return self.settings.value("openai_api_key", "")

    def get_eleven_labs_api_key(self):
        return self.settings.value("eleven_labs_api_key", "")

    def get_data_filterer_settings(self):
        return {
            "api": "claude" if self.data_filterer_claude_radio.isChecked() else "openai",
            "model": self.data_filterer_model_input.text(),
            "claude_key": self.get_claude_api_key(),
            "openai_key": self.get_openai_api_key()
        }

    def get_race_commentator_settings(self):
        return {
            "api": "claude" if self.race_commentator_claude_radio.isChecked() else "openai",
            "model": self.race_commentator_model_input.text(),
            "claude_key": self.get_claude_api_key(),
            "openai_key": self.get_openai_api_key()
        }


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())