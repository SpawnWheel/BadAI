import traceback
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QFormLayout, QLineEdit, QPushButton,
    QLabel, QHBoxLayout, QComboBox, QTextEdit, QMessageBox, QRadioButton,
    QButtonGroup, QCheckBox, QInputDialog
)
from PyQt5.QtCore import Qt
from commentator_dialog import CommentatorDialog # Import the dialog
from cartesia import Cartesia # For fetching voices

class SettingsTab(QWidget):
    """QWidget for the Settings tab."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.settings = main_window.settings
        self.commentator_manager = main_window.commentator_manager

        self._setup_ui()
        self.load_settings() # Load initial values into fields

    def _setup_ui(self):
        """Sets up the UI elements for this tab."""
        layout = QVBoxLayout(self)

        # API Keys Group
        api_keys_group = QGroupBox("API Keys")
        api_keys_layout = QFormLayout()
        self.claude_api_key_input = QLineEdit(); self.claude_api_key_input.setEchoMode(QLineEdit.Password)
        self.openai_api_key_input = QLineEdit(); self.openai_api_key_input.setEchoMode(QLineEdit.Password)
        self.google_api_key_input = QLineEdit(); self.google_api_key_input.setEchoMode(QLineEdit.Password)
        self.cartesia_api_key_input = QLineEdit(); self.cartesia_api_key_input.setEchoMode(QLineEdit.Password)
        api_keys_layout.addRow("Claude API Key:", self.claude_api_key_input)
        api_keys_layout.addRow("OpenAI API Key:", self.openai_api_key_input)
        api_keys_layout.addRow("Google API Key:", self.google_api_key_input)
        api_keys_layout.addRow("Cartesia API Key:", self.cartesia_api_key_input)
        api_keys_group.setLayout(api_keys_layout)

        # Model Selection Group
        model_selection_group = QGroupBox("Model Selection")
        model_selection_layout = QVBoxLayout()

        # Data Filterer Models
        data_filterer_group = QGroupBox("Data Filterer")
        data_filterer_layout = QVBoxLayout()
        data_filterer_api_radio_layout = QHBoxLayout()
        self.data_filterer_api_group = QButtonGroup(self)
        self.data_filterer_claude_radio = QRadioButton("Claude"); self.data_filterer_openai_radio = QRadioButton("OpenAI"); self.data_filterer_gemini_radio = QRadioButton("Gemini")
        self.data_filterer_api_group.addButton(self.data_filterer_claude_radio); self.data_filterer_api_group.addButton(self.data_filterer_openai_radio); self.data_filterer_api_group.addButton(self.data_filterer_gemini_radio)
        data_filterer_api_radio_layout.addWidget(self.data_filterer_claude_radio); data_filterer_api_radio_layout.addWidget(self.data_filterer_openai_radio); data_filterer_api_radio_layout.addWidget(self.data_filterer_gemini_radio); data_filterer_api_radio_layout.addStretch()
        self.data_filterer_model_input = QLineEdit()
        data_filterer_layout.addLayout(data_filterer_api_radio_layout); data_filterer_layout.addWidget(QLabel("Model Name:")); data_filterer_layout.addWidget(self.data_filterer_model_input)
        data_filterer_group.setLayout(data_filterer_layout)

        # Race Commentator Models
        race_commentator_group = QGroupBox("Race Commentator")
        race_commentator_layout = QVBoxLayout()
        race_commentator_api_radio_layout = QHBoxLayout()
        self.race_commentator_api_group = QButtonGroup(self)
        self.race_commentator_claude_radio = QRadioButton("Claude"); self.race_commentator_openai_radio = QRadioButton("OpenAI"); self.race_commentator_gemini_radio = QRadioButton("Gemini")
        self.race_commentator_api_group.addButton(self.race_commentator_claude_radio); self.race_commentator_api_group.addButton(self.race_commentator_openai_radio); self.race_commentator_api_group.addButton(self.race_commentator_gemini_radio)
        race_commentator_api_radio_layout.addWidget(self.race_commentator_claude_radio); race_commentator_api_radio_layout.addWidget(self.race_commentator_openai_radio); race_commentator_api_radio_layout.addWidget(self.race_commentator_gemini_radio); race_commentator_api_radio_layout.addStretch()
        self.race_commentator_model_input = QLineEdit()
        race_commentator_layout.addLayout(race_commentator_api_radio_layout); race_commentator_layout.addWidget(QLabel("Model Name:")); race_commentator_layout.addWidget(self.race_commentator_model_input)
        race_commentator_group.setLayout(race_commentator_layout)

        # Cartesia Voice Settings
        cartesia_group = QGroupBox("Cartesia Voice Settings")
        cartesia_layout = QFormLayout()
        self.cartesia_model_combo = QComboBox()
        self.cartesia_model_combo.addItems(["sonic-english", "glow-english", "nova-english"]) # Add more if needed
        cartesia_layout.addRow("Voice Model:", self.cartesia_model_combo)
        fetch_voices_button = QPushButton("Fetch Available Voices"); fetch_voices_button.clicked.connect(self.fetch_cartesia_voices)
        cartesia_layout.addRow("", fetch_voices_button)
        self.cartesia_voices_text = QTextEdit(); self.cartesia_voices_text.setReadOnly(True); self.cartesia_voices_text.setFixedHeight(100); self.cartesia_voices_text.setPlaceholderText("Enter API key and click fetch...")
        cartesia_layout.addRow("Available Voices:", self.cartesia_voices_text)
        cartesia_group.setLayout(cartesia_layout)

        model_selection_layout.addWidget(data_filterer_group)
        model_selection_layout.addWidget(race_commentator_group)
        model_selection_layout.addWidget(cartesia_group)
        model_selection_group.setLayout(model_selection_layout)

        # Commentator Management Group
        commentator_group = QGroupBox("Commentator Management")
        commentator_layout = QVBoxLayout()
        self.commentator_list = QComboBox() # Dropdown for edit/delete
        commentator_buttons_layout = QHBoxLayout()
        add_commentator_button = QPushButton("Add"); add_commentator_button.clicked.connect(self.add_commentator)
        edit_commentator_button = QPushButton("Edit"); edit_commentator_button.clicked.connect(self.edit_commentator)
        delete_commentator_button = QPushButton("Delete"); delete_commentator_button.clicked.connect(self.delete_commentator)
        commentator_buttons_layout.addWidget(add_commentator_button); commentator_buttons_layout.addWidget(edit_commentator_button); commentator_buttons_layout.addWidget(delete_commentator_button); commentator_buttons_layout.addStretch()
        commentator_layout.addWidget(QLabel("Select commentator to Edit/Delete:"))
        commentator_layout.addWidget(self.commentator_list)
        commentator_layout.addLayout(commentator_buttons_layout)
        commentator_group.setLayout(commentator_layout)

        # Other Settings
        self.always_on_top_checkbox = QCheckBox("Always on Top")
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

    def load_settings(self):
        """Loads settings from QSettings into the UI fields."""
        self.claude_api_key_input.setText(self.settings.value("claude_api_key", ""))
        self.openai_api_key_input.setText(self.settings.value("openai_api_key", ""))
        self.google_api_key_input.setText(self.settings.value("google_api_key", ""))
        self.cartesia_api_key_input.setText(self.settings.value("cartesia_api_key", ""))

        saved_df_api = self.settings.value("data_filterer_api", "gemini")
        if saved_df_api == "claude": self.data_filterer_claude_radio.setChecked(True)
        elif saved_df_api == "openai": self.data_filterer_openai_radio.setChecked(True)
        else: self.data_filterer_gemini_radio.setChecked(True)
        self.data_filterer_model_input.setText(self.settings.value("data_filterer_model", "gemini-1.5-flash-latest"))

        saved_rc_api = self.settings.value("race_commentator_api", "gemini")
        if saved_rc_api == "claude": self.race_commentator_claude_radio.setChecked(True)
        elif saved_rc_api == "openai": self.race_commentator_openai_radio.setChecked(True)
        else: self.race_commentator_gemini_radio.setChecked(True)
        self.race_commentator_model_input.setText(self.settings.value("race_commentator_model", "gemini-1.5-flash-latest"))

        current_cartesia_model = self.settings.value("cartesia_model", "sonic-english")
        index = self.cartesia_model_combo.findText(current_cartesia_model)
        if index >= 0: self.cartesia_model_combo.setCurrentIndex(index)
        else: self.cartesia_model_combo.setCurrentIndex(0) # Default if not found

        self.always_on_top_checkbox.setChecked(self.settings.value("always_on_top", False, type=bool))

        # Populate commentator list (MainWindow should trigger this initially and on changes)
        # self.update_commentator_list() # Let main window handle the initial call

    def save_settings(self):
        """Saves UI fields back to QSettings."""
        try:
            self.settings.setValue("claude_api_key", self.claude_api_key_input.text())
            self.settings.setValue("openai_api_key", self.openai_api_key_input.text())
            self.settings.setValue("google_api_key", self.google_api_key_input.text())
            self.settings.setValue("cartesia_api_key", self.cartesia_api_key_input.text())

            df_api = "gemini"
            if self.data_filterer_claude_radio.isChecked(): df_api = "claude"
            elif self.data_filterer_openai_radio.isChecked(): df_api = "openai"
            self.settings.setValue("data_filterer_api", df_api)
            self.settings.setValue("data_filterer_model", self.data_filterer_model_input.text())

            rc_api = "gemini"
            if self.race_commentator_claude_radio.isChecked(): rc_api = "claude"
            elif self.race_commentator_openai_radio.isChecked(): rc_api = "openai"
            self.settings.setValue("race_commentator_api", rc_api)
            self.settings.setValue("race_commentator_model", self.race_commentator_model_input.text())

            self.settings.setValue("cartesia_model", self.cartesia_model_combo.currentText())
            self.settings.setValue("always_on_top", self.always_on_top_checkbox.isChecked())

            # No need to save combo selections here, they are saved on change

            self.settings.sync()
            QMessageBox.information(self, "Settings Saved", "Settings saved successfully.")
            # Notify main window if needed, e.g., if API keys changed mid-session
            # self.main_window.on_settings_saved()

        except Exception as e:
             QMessageBox.critical(self, "Save Error", f"Error saving settings: {str(e)}")
             print(f"Save Settings Error: {e}\n{traceback.format_exc()}")

    def toggle_always_on_top(self, state):
        """Calls MainWindow method to toggle the flag."""
        self.main_window.set_always_on_top(state == Qt.Checked)

    def fetch_cartesia_voices(self):
        """Fetches and displays Cartesia voices."""
        api_key = self.cartesia_api_key_input.text()
        if not api_key:
            QMessageBox.warning(self, "API Key Missing", "Enter Cartesia API key.")
            return

        try:
            client = Cartesia(api_key=api_key)
            self.cartesia_voices_text.setText("Fetching...")
            self.main_window.app.processEvents() # Allow UI update

            voices = client.voices.list()
            if not voices:
                self.cartesia_voices_text.setText("No voices found or API key invalid.")
                return

            voice_text = f"Found {len(voices)} Voices:\n\n" + "=" * 40 + "\n\n"
            for voice in voices:
                v_id = getattr(voice, 'id', 'N/A')
                v_name = getattr(voice, 'name', 'N/A')
                v_desc = getattr(voice, 'description', '')
                voice_text += f"ID: {v_id}\nName: {v_name}\n"
                if v_desc: voice_text += f"Description: {v_desc}\n"
                voice_text += "\n" + "-" * 40 + "\n\n"
            self.cartesia_voices_text.setText(voice_text)

        except Exception as e:
            error_message = f"Error fetching voices: {str(e)}"
            self.cartesia_voices_text.setText(error_message)
            QMessageBox.critical(self, "Cartesia API Error", error_message)
            print(f"Cartesia Fetch Error: {e}\n{traceback.format_exc()}")

    def update_commentator_list(self, commentators):
        """Populates the commentator list dropdown."""
        combo_box = self.commentator_list
        current_data = combo_box.currentData() # Preserve selection if possible
        combo_box.blockSignals(True)
        combo_box.clear()
        selected_index = -1

        if commentators:
            for i, metadata in enumerate(commentators):
                display_text = f"{metadata.name} - {metadata.style}"
                combo_box.addItem(display_text, metadata.name)
                if current_data is not None and metadata.name == current_data:
                    selected_index = i

            if combo_box.count() > 0:
                if selected_index != -1 and 0 <= selected_index < combo_box.count():
                    combo_box.setCurrentIndex(selected_index)
                else:
                    combo_box.setCurrentIndex(0)
        combo_box.blockSignals(False)


    def add_commentator(self):
        """Opens dialog to add a new commentator."""
        dialog = CommentatorDialog(self)
        if dialog.exec_():
            data = dialog.get_data()
            if not data.get('name', '').strip():
                 QMessageBox.warning(self, "Invalid Input", "Commentator name needed.")
                 return

            success = self.commentator_manager.create_commentator(
                name=data['name'], personality=data['personality'], style=data['style'],
                examples=data['examples'], voice_id=data['voice_id'],
                voice_speed=data['voice_speed'], voice_emotions=data['voice_emotions'],
                voice_intensity=data['voice_intensity'], main_prompt=data['main_prompt'],
                second_pass_prompt=data['second_pass_prompt']
            )

            if success:
                self.main_window.refresh_all_commentator_data() # Tell main window to update everything
                QMessageBox.information(self, "Success", f"Commentator '{data['name']}' added.")
            else:
                QMessageBox.warning(self, "Error", f"Failed to add commentator '{data['name']}'. Already exists?")

    def edit_commentator(self):
        """Opens dialog to edit the selected commentator."""
        current_name = self.commentator_list.currentData()
        if not current_name:
            QMessageBox.warning(self, "Selection Error", "Select commentator to edit.")
            return

        dialog = None
        try:
            metadata = self.commentator_manager.get_commentator_metadata(current_name)
            if not metadata:
                QMessageBox.warning(self, "Load Error", f"Cannot load metadata for '{current_name}'.")
                return

            main_prompt = self.commentator_manager.get_prompt(current_name, False) or ""
            second_pass_prompt = self.commentator_manager.get_prompt(current_name, True) or ""

            dialog = CommentatorDialog(self, existing_metadata=metadata)
            dialog.main_prompt_edit.setText(main_prompt)
            dialog.second_pass_prompt_edit.setText(second_pass_prompt)

            if dialog.exec_():
                data = dialog.get_data()
                new_name = data.get('name', '').strip()
                if not new_name:
                     QMessageBox.warning(self, "Invalid Input", "Commentator name needed.")
                     return

                success = self.commentator_manager.update_commentator(
                    original_name=current_name, name=new_name,
                    personality=data['personality'], style=data['style'],
                    examples=data['examples'], voice_id=data['voice_id'],
                    voice_speed=data['voice_speed'], voice_emotions=data['voice_emotions'],
                    voice_intensity=data['voice_intensity'], main_prompt=data['main_prompt'],
                    second_pass_prompt=data['second_pass_prompt']
                )

                if success:
                    self.main_window.refresh_all_commentator_data() # Update everywhere
                    # Reselect potentially renamed item
                    QTimer.singleShot(0, lambda: self.select_commentator_in_list(new_name)) # Delay selection slightly
                    QMessageBox.information(self, "Success", f"Commentator '{new_name}' updated.")
                else:
                    QMessageBox.warning(self, "Update Error", f"Failed to update '{new_name}'. Name conflict?")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error editing commentator: {str(e)}")
            print(f"Edit Commentator Error: {e}\n{traceback.format_exc()}")
        finally:
            if dialog: dialog.deleteLater()

    def delete_commentator(self):
        """Deletes the selected commentator."""
        current_name = self.commentator_list.currentData()
        if not current_name:
            QMessageBox.warning(self, "Selection Error", "Select commentator to delete.")
            return

        reply = QMessageBox.question(self, "Confirm Deletion",
                                     f"Delete commentator '{current_name}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            if self.commentator_manager.delete_commentator(current_name):
                self.main_window.refresh_all_commentator_data() # Update everywhere
                QMessageBox.information(self, "Success", f"Commentator '{current_name}' deleted.")
            else:
                QMessageBox.warning(self, "Deletion Error", f"Failed to delete '{current_name}'.")

    def select_commentator_in_list(self, name_to_select):
        """Finds and selects a commentator by name in the settings list."""
        index = self.commentator_list.findData(name_to_select)
        if index >= 0:
            self.commentator_list.setCurrentIndex(index)