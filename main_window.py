# main_window.py
import sys
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QWidget, QVBoxLayout, QTabWidget, QGroupBox,
    QFormLayout, QLineEdit, QPushButton, QLabel, QHBoxLayout, QComboBox, QTextEdit,
    QFileDialog, QMessageBox, QProgressBar, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import QSettings
from csv_creator_widget import CSVCreatorWidget

# Import your existing modules for data collection, filtering, commentary, and voice generation.
from data_collector_ACC import DataCollector as DataCollectorACC
from data_collector_AMS2 import DataCollector as DataCollectorAMS2
from data_collector_AC import DataCollector as DataCollectorAC
from data_filterer import DataFilterer
from race_commentator import RaceCommentator
from voice_generator import VoiceGenerator

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bad AI Commentary")
        self.setGeometry(100, 100, 800, 600)

        self.settings = QSettings("BadAICommentary", "SimRacingCommentator")

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

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

        self.setup_setup_tab()
        self.setup_highlight_reel_tab()
        self.setup_commentary_tab()
        self.setup_voice_tab()
        self.setup_settings_tab()

        self.status_bar = self.statusBar()
        self.progress_bar = QProgressBar()
        self.status_bar.addPermanentWidget(self.progress_bar)

    def setup_setup_tab(self):
        layout = QVBoxLayout(self.setup_tab)
        sim_label = QLabel("Select your sim:")
        self.sim_combo = QComboBox()
        self.sim_combo.addItems(["Assetto Corsa Competizione", "Assetto Corsa", "Automobilista 2"])

        self.start_stop_button = QPushButton("Start")
        self.start_stop_button.clicked.connect(self.toggle_data_collection)

        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)

        layout.addWidget(sim_label)
        layout.addWidget(self.sim_combo)
        layout.addWidget(self.start_stop_button)
        layout.addWidget(self.console_output)

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

    def setup_voice_tab(self):
        layout = QVBoxLayout(self.voice_tab)
        input_label = QLabel("Input file:")
        self.voice_input = QLineEdit()
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_voice_input)

        generate_button = QPushButton("Generate Voice Commentary")
        generate_button.clicked.connect(self.generate_voice)

        self.voice_output = QTextEdit()
        self.voice_output.setReadOnly(True)

        layout.addWidget(input_label)
        layout.addWidget(self.voice_input)
        layout.addWidget(browse_button)
        layout.addWidget(generate_button)
        layout.addWidget(self.voice_output)

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
        self.race_commentator_model_input.setText(self.settings.value("race_commentator_model", "claude-3-5-sonnet-20241022"))

        race_commentator_layout.addWidget(self.race_commentator_claude_radio)
        race_commentator_layout.addWidget(self.race_commentator_openai_radio)
        race_commentator_layout.addWidget(QLabel("Model:"))
        race_commentator_layout.addWidget(self.race_commentator_model_input)
        race_commentator_group.setLayout(race_commentator_layout)

        model_selection_layout.addWidget(data_filterer_group)
        model_selection_layout.addWidget(race_commentator_group)
        model_selection_group.setLayout(model_selection_layout)

        # Save Button
        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)

        layout.addWidget(api_keys_group)
        layout.addWidget(model_selection_group)
        layout.addWidget(save_button)
        layout.addStretch()

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

        self.data_collector.output_signal.connect(self.update_console)
        self.data_collector.progress_signal.connect(self.update_progress_bar)
        self.data_collector.start()
        self.start_stop_button.setText("Stop")

    def stop_data_collection(self):
        if hasattr(self, 'data_collector'):
            self.data_collector.stop()
            self.update_console("Data collection stopped.")
        self.start_stop_button.setText("Start")

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

    def generate_commentary(self):
        input_path = self.commentary_input.text()
        if not input_path:
            input_path = self.data_filterer.get_output_path() if hasattr(self, 'data_filterer') else None

        if not input_path:
            QMessageBox.warning(self, "Input Missing", "Please select an input file.")
            return

        settings = self.get_race_commentator_settings()

        if settings["api"] == "claude" and not settings["claude_key"]:
            QMessageBox.warning(self, "API Key Missing", "Please enter your Claude API key in the Settings tab.")
            return
        elif settings["api"] == "openai" and not settings["openai_key"]:
            QMessageBox.warning(self, "API Key Missing", "Please enter your OpenAI API key in the Settings tab.")
            return

        try:
            self.race_commentator = RaceCommentator(input_path, settings)
            self.race_commentator.output_signal.connect(self.update_commentary_output)
            self.race_commentator.progress_signal.connect(self.update_progress_bar)
            self.race_commentator.start()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start commentary generation: {str(e)}")

    def update_commentary_output(self, text):
        self.commentary_output.append(text)

    def browse_voice_input(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Input File", "", "Text Files (*.txt)")
        if file_name:
            self.voice_input.setText(file_name)

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

        self.voice_generator = VoiceGenerator(input_path, eleven_labs_api_key)
        self.voice_generator.output_signal.connect(self.update_voice_output)
        self.voice_generator.progress_signal.connect(self.update_progress_bar)
        self.voice_generator.start()

    def update_voice_output(self, text):
        self.voice_output.append(text)

    def update_progress_bar(self, value):
        self.progress_bar.setValue(value)

    def save_settings(self):
        self.settings.setValue("claude_api_key", self.claude_api_key_input.text())
        self.settings.setValue("openai_api_key", self.openai_api_key_input.text())
        self.settings.setValue("eleven_labs_api_key", self.eleven_labs_api_key_input.text())

        self.settings.setValue("data_filterer_api", "claude" if self.data_filterer_claude_radio.isChecked() else "openai")
        self.settings.setValue("data_filterer_model", self.data_filterer_model_input.text())

        self.settings.setValue("race_commentator_api", "claude" if self.race_commentator_claude_radio.isChecked() else "openai")
        self.settings.setValue("race_commentator_model", self.race_commentator_model_input.text())

        QMessageBox.information(self, "Settings Saved", "Your settings have been saved successfully.")

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
