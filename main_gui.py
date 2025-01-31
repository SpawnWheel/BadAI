import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
    QHBoxLayout, QPushButton, QLabel, QComboBox, QTextEdit, 
    QFileDialog, QProgressBar, QLineEdit, QFormLayout, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QMenu, QInputDialog, QAbstractItemView, 
    QShortcut, QGroupBox, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QSettings, pyqtSignal, QThread
from PyQt5.QtGui import QColor, QKeySequence
from datetime import datetime, timedelta
import re
from openai import OpenAI

# Import your existing modules
from data_collector_ACC import DataCollector as DataCollectorACC
from data_collector_AMS2 import DataCollector as DataCollectorAMS2
from data_collector_AC import DataCollector as DataCollectorAC
from data_filterer import DataFilterer
from race_commentator import RaceCommentator
from voice_generator import VoiceGenerator


class CSVCreatorWidget(QWidget):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = []
        self.undo_stack = []
        self.next_id = 0
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Top controls frame
        top_frame = QHBoxLayout()
        
        # Offset controls
        offset_label = QLabel("Time Offset (HH:MM:SS):")
        self.offset_entry = QLineEdit()
        apply_offset_button = QPushButton("Apply Offset")
        apply_offset_button.clicked.connect(self.apply_offset)
        
        # WPS controls
        wps_label = QLabel("Words Per Second:")
        self.wps_entry = QLineEdit()
        self.wps_entry.setText('3.7')
        recalculate_button = QPushButton("Recalculate Words")
        recalculate_button.clicked.connect(self.recalculate_words_for_all)
        
        # Add widgets to top frame
        top_frame.addWidget(offset_label)
        top_frame.addWidget(self.offset_entry)
        top_frame.addWidget(apply_offset_button)
        top_frame.addWidget(wps_label)
        top_frame.addWidget(self.wps_entry)
        top_frame.addWidget(recalculate_button)
        top_frame.addStretch()
        
        # Create table
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Time", "Event", "Additional Information", "Words"])
        self.tree.setColumnCount(5)  # Added a column for hidden ID
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        # Set column widths
        self.tree.setColumnWidth(0, 100)  # Time
        self.tree.setColumnWidth(1, 300)  # Event
        self.tree.setColumnWidth(2, 200)  # Additional Information
        self.tree.setColumnWidth(3, 80)   # Words
        self.tree.setColumnHidden(4, True)  # Hide the ID column
        
        # Button frame
        button_frame = QHBoxLayout()
        save_button = QPushButton("Save Text File")
        save_button.clicked.connect(self.save_text_file)
        button_frame.addWidget(save_button)
        button_frame.addStretch()
        
        # Add all layouts to main layout
        layout.addLayout(top_frame)
        layout.addWidget(self.tree)
        layout.addLayout(button_frame)
        
        # Context menu
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        
        # Double click editing
        self.tree.itemDoubleClicked.connect(self.on_double_click)
        
        # Undo shortcut
        undo_shortcut = QShortcut(QKeySequence("Ctrl+Z"), self)
        undo_shortcut.activated.connect(self.undo)

    def load_data(self, text_content):
        """Load data from text content"""
        self.data = []
        lines = text_content.split('\n')
        for line in lines:
            match = re.match(r'(\d{2}:\d{2}:\d{2}) - (.+)', line.strip())
            if match:
                time, event = match.groups()
                row_id = f"ID_{self.next_id}"
                self.next_id += 1
                self.data.append({
                    'ID': row_id,
                    'Time': time,
                    'Event': event,
                    'Additional Information': '',
                    'Words': 0
                })
        
        self.recalculate_words_for_all()

    def recalculate_words_for_all(self):
        self.sort_data()
        self.calculate_word_counts()
        self.update_table()

    def calculate_word_counts(self):
        try:
            wps = float(self.wps_entry.text())
        except ValueError:
            wps = 3.7  # default value

        if len(self.data) == 0:
            return

        for i in range(len(self.data) - 1):
            current_row = self.data[i]
            next_row = self.data[i + 1]

            time_diff = self.time_difference(current_row['Time'], next_row['Time'])

            if next_row.get('is_break'):
                # Limit word count to 80 if next event is a break
                words = min(80, int(time_diff * wps))
            else:
                words = int(time_diff * wps)

            current_row['Words'] = words

        # Handle the last row
        last_row = self.data[-1]
        last_row['Words'] = 100  # Default value

    def time_difference(self, time1, time2):
        t1 = datetime.strptime(time1, "%H:%M:%S")
        t2 = datetime.strptime(time2, "%H:%M:%S")
        return (t2 - t1).total_seconds()

    def show_context_menu(self, position):
        menu = QMenu()
        merge_action = menu.addAction("Merge")
        delete_action = menu.addAction("Delete")
        insert_before_action = menu.addAction("Insert Before")
        insert_after_action = menu.addAction("Insert After")
        add_break_action = menu.addAction("Add Break Before")

        selected_items = self.tree.selectedItems()
        merge_action.setEnabled(len(selected_items) >= 2)

        action = menu.exec_(self.tree.viewport().mapToGlobal(position))
        if action == merge_action:
            self.merge_rows()
        elif action == delete_action:
            self.delete_row()
        elif action == insert_before_action:
            self.insert_row("before")
        elif action == insert_after_action:
            self.insert_row("after")
        elif action == add_break_action:
            self.add_break()

    def add_break(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return

        # Save state for undo
        self.save_state()

        selected_item = selected_items[0]
        selected_index = None
        for i, row in enumerate(self.data):
            if row['ID'] == selected_item.text(4):  # ID stored in hidden column
                selected_index = i
                break

        if selected_index is None:
            return

        # Get the time of the selected event
        selected_event = self.data[selected_index]
        selected_event_time_str = selected_event['Time']
        selected_event_time_obj = datetime.strptime(selected_event_time_str, "%H:%M:%S")
        break_time_obj = selected_event_time_obj - timedelta(seconds=20)

        # Ensure that the break time is after the previous event's time
        if selected_index > 0:
            previous_event_time_obj = datetime.strptime(self.data[selected_index - 1]['Time'], "%H:%M:%S")
            if break_time_obj <= previous_event_time_obj:
                # Adjust the break time to be 1 second after the previous event
                break_time_obj = previous_event_time_obj + timedelta(seconds=1)
        else:
            # If it's the first event, ensure break time is not negative
            min_time = datetime.strptime("00:00:00", "%H:%M:%S")
            if break_time_obj < min_time:
                break_time_obj = min_time

        break_time_str = break_time_obj.strftime("%H:%M:%S")

        # Create new break row
        new_id = f"ID_{self.next_id}"
        self.next_id += 1
        new_row = {
            'ID': new_id,
            'Time': break_time_str,
            'Event': "Welcome back to the action viewers!",
            'Additional Information': "",
            'Words': 0,
            'is_break': True  # Mark this row as a break
        }

        # Insert the break before the selected event
        self.data.insert(selected_index, new_row)

        self.sort_data()
        self.calculate_word_counts()
        self.update_table()

    def merge_rows(self):
        selected_items = self.tree.selectedItems()
        if len(selected_items) < 2:
            return

        # Save state for undo
        self.save_state()

        # Get indices of selected items
        indices = []
        for item in selected_items:
            for i, row in enumerate(self.data):
                if row['ID'] == item.text(4):  # ID stored in hidden column
                    indices.append(i)
                    break

        if len(indices) != len(selected_items):
            return

        # Ensure indices are in order
        indices.sort()
        base_row = self.data[indices[0]]

        # Merge the rows
        merged_event = base_row['Event']
        merged_additional_info = base_row['Additional Information']
        merged_words = base_row['Words']

        for idx in indices[1:]:
            row = self.data[idx]
            merged_event += f" {row['Event']}"
            merged_additional_info += f" {row['Additional Information']}"
            merged_words += row['Words']

        # Update base row and delete the other rows in reverse order
        base_row.update({
            'Event': merged_event.strip(),
            'Additional Information': merged_additional_info.strip(),
            'Words': merged_words
        })

        for idx in reversed(indices[1:]):
            del self.data[idx]

        # After merging
        self.sort_data()
        self.calculate_word_counts()
        self.update_table()

    def delete_row(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return

        # Save state for undo
        self.save_state()

        # Remove selected rows
        indices_to_delete = []
        for item in selected_items:
            for i, row in enumerate(self.data):
                if row['ID'] == item.text(4):
                    indices_to_delete.append(i)
                    break

        for idx in sorted(indices_to_delete, reverse=True):
            del self.data[idx]

        # After deleting
        self.sort_data()
        self.calculate_word_counts()
        self.update_table()

    def insert_row(self, position):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return

        # Save state for undo
        self.save_state()

        selected_item = selected_items[0]
        selected_index = None
        for i, row in enumerate(self.data):
            if row['ID'] == selected_item.text(4):
                selected_index = i
                break

        if selected_index is None:
            return

        # Create new row
        new_id = f"ID_{self.next_id}"
        self.next_id += 1
        new_row = {
            'ID': new_id,
            'Time': self.data[selected_index]['Time'],
            'Event': "New Event",
            'Additional Information': "",
            'Words': 0
        }

        # Insert the row
        if position == "after":
            self.data.insert(selected_index + 1, new_row)
        else:  # before
            self.data.insert(selected_index, new_row)

        # After inserting
        self.sort_data()
        self.calculate_word_counts()
        self.update_table()

    def save_text_file(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Text File", "", "Text Files (*.txt)")
        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                for row in self.data:
                    line = f"{row['Time']} - {row['Event']} {row['Additional Information']} Commentate in {row['Words']} words."
                    f.write(line + '\n')
            QMessageBox.information(self, "Success", "Text file saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while saving: {str(e)}")

    def on_double_click(self, item, column):
        if column in [0, 1, 2]:  # Time, Event, Additional Information
            self.edit_cell(item, column)

    def edit_cell(self, item, column):
        current_value = item.text(column)
        new_value, ok = QInputDialog.getText(self, "Edit Cell", "Enter new value:", text=current_value)
        
        if ok and new_value:
            # Save state for undo
            self.save_state()

            # Update the item
            item.setText(column, new_value)

            # Update data
            for row in self.data:
                if row['ID'] == item.text(4):  # ID stored in hidden column
                    if column == 0:
                        # Time changed, we need to recalc words
                        row['Time'] = new_value
                        self.sort_data()
                        self.calculate_word_counts()
                        self.update_table()
                    elif column == 1:
                        # Event changed, no time change, no need to recalc words
                        row['Event'] = new_value
                        self.update_table()
                    elif column == 2:
                        # Additional info changed, no time change, no need to recalc words
                        row['Additional Information'] = new_value
                        self.update_table()
                    break

    def sort_data(self):
        self.data.sort(key=lambda x: datetime.strptime(x['Time'], "%H:%M:%S"))

    def update_table(self):
        self.tree.clear()
        for row in self.data:
            item = QTreeWidgetItem(self.tree)
            item.setText(0, row['Time'])
            item.setText(1, row['Event'])
            item.setText(2, row['Additional Information'])
            item.setText(3, str(row['Words']))
            item.setText(4, row['ID'])  # Hidden column for ID

            # Highlight break events
            if row.get('is_break'):
                for col in range(4):
                    item.setBackground(col, QColor(255, 228, 181))  # Light orange color

    def save_state(self):
        import copy
        self.undo_stack.append(copy.deepcopy(self.data))

    def undo(self):
        if self.undo_stack:
            self.data = self.undo_stack.pop()
            # After undo, re-sort, recalc words, update table
            self.sort_data()
            self.calculate_word_counts()
            self.update_table()
        else:
            QMessageBox.information(self, "Undo", "Nothing to undo.")

    def apply_offset(self):
        offset_str = self.offset_entry.text().strip()
        if not offset_str:
            QMessageBox.warning(self, "Error", "Please enter a time offset.")
            return

        try:
            offset = datetime.strptime(offset_str, "%H:%M:%S")
            offset_delta = timedelta(hours=offset.hour, minutes=offset.minute, seconds=offset.second)
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid time format. Please use HH:MM:SS.")
            return

        # Save state for undo
        self.save_state()

        # Apply offset
        for row in self.data:
            try:
                time_obj = datetime.strptime(row['Time'], "%H:%M:%S")
                new_time = time_obj + offset_delta
                row['Time'] = new_time.strftime("%H:%M:%S")
            except ValueError:
                QMessageBox.warning(self, "Error", f"Invalid time format in data: {row['Time']}")
                return

        self.sort_data()
        self.calculate_word_counts()
        self.update_table()
        QMessageBox.information(self, "Success", "Time offset applied successfully!")


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
        
        # Load saved selection
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
        
        # Load saved selection
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
        
        # Add all sections to main layout
        layout.addWidget(api_keys_group)
        layout.addWidget(model_selection_group)
        layout.addWidget(save_button)
        layout.addStretch()

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
        
        # Add load file button for CSV creator
        load_csv_layout = QHBoxLayout()
        load_csv_button = QPushButton("Load Existing File")
        load_csv_button.clicked.connect(self.load_existing_file)
        load_csv_layout.addWidget(load_csv_button)
        load_csv_layout.addStretch()

        self.csv_creator = CSVCreatorWidget()
        
        # Add all widgets to layout
        layout.addLayout(input_layout)
        layout.addWidget(csv_creator_label)
        layout.addLayout(load_csv_layout)
        layout.addWidget(self.csv_creator)

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
        # Read the filtered text file and load into CSV creator
        filtered_file_path = self.data_filterer.get_output_path()
        try:
            with open(filtered_file_path, 'r', encoding='utf-8') as file:
                text_content = file.read()
            self.csv_creator.load_data(text_content)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load filtered data: {str(e)}")

    def load_existing_file(self):
        """Load an existing text file into the CSV creator"""
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

    def browse_data_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Race Data File", "", "Text Files (*.txt)")
        if file_name:
            self.data_path_input.setText(file_name)

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

    def browse_commentary_input(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Input File", "", "Text Files (*.txt)")
        if file_name:
            self.commentary_input.setText(file_name)

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
        # Save API keys
        self.settings.setValue("claude_api_key", self.claude_api_key_input.text())
        self.settings.setValue("openai_api_key", self.openai_api_key_input.text())
        self.settings.setValue("eleven_labs_api_key", self.eleven_labs_api_key_input.text())
        
        # Save Data Filterer settings
        self.settings.setValue("data_filterer_api", 
                            "claude" if self.data_filterer_claude_radio.isChecked() else "openai")
        self.settings.setValue("data_filterer_model", self.data_filterer_model_input.text())
        
        # Save Race Commentator settings
        self.settings.setValue("race_commentator_api",
                            "claude" if self.race_commentator_claude_radio.isChecked() else "openai")
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

    def load_prompt(self, filename):
        try:
            with open(filename, 'r') as file:
                return file.read()
        except FileNotFoundError:
            return f"Error: {filename} not found. Please create this file with the desired prompt."

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
