# csv_creator_widget.py
import re
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QTreeWidget, QTreeWidgetItem, QInputDialog, QMessageBox, QAbstractItemView, QFileDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import QShortcut


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
        offset_label = QLabel("Time Offset (HH:MM:SS):")
        self.offset_entry = QLineEdit()
        apply_offset_button = QPushButton("Apply Offset")
        apply_offset_button.clicked.connect(self.apply_offset)

        wps_label = QLabel("Words Per Second:")
        self.wps_entry = QLineEdit()
        self.wps_entry.setText('3.7')
        recalculate_button = QPushButton("Recalculate Words")
        recalculate_button.clicked.connect(self.recalculate_words_for_all)

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
        self.tree.setColumnWidth(3, 80)  # Words
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
        from PyQt5.QtWidgets import QMenu
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

        indices.sort()
        base_row = self.data[indices[0]]

        merged_event = base_row['Event']
        merged_additional_info = base_row['Additional Information']
        merged_words = base_row['Words']

        for idx in indices[1:]:
            row = self.data[idx]
            merged_event += f" {row['Event']}"
            merged_additional_info += f" {row['Additional Information']}"
            merged_words += row['Words']

        base_row.update({
            'Event': merged_event.strip(),
            'Additional Information': merged_additional_info.strip(),
            'Words': merged_words
        })

        for idx in sorted(indices[1:], reverse=True):
            del self.data[idx]

        self.sort_data()
        self.calculate_word_counts()
        self.update_table()

    def delete_row(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            return

        # Save state for undo
        self.save_state()

        indices_to_delete = []
        for item in selected_items:
            for i, row in enumerate(self.data):
                if row['ID'] == item.text(4):
                    indices_to_delete.append(i)
                    break

        for idx in sorted(indices_to_delete, reverse=True):
            del self.data[idx]

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

        new_id = f"ID_{self.next_id}"
        self.next_id += 1
        new_row = {
            'ID': new_id,
            'Time': self.data[selected_index]['Time'],
            'Event': "New Event",
            'Additional Information': "",
            'Words': 0
        }

        if position == "after":
            self.data.insert(selected_index + 1, new_row)
        else:
            self.data.insert(selected_index, new_row)

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
        if column in [0, 1, 2]:
            self.edit_cell(item, column)

    def edit_cell(self, item, column):
        current_value = item.text(column)
        new_value, ok = QInputDialog.getText(self, "Edit Cell", "Enter new value:", text=current_value)
        if ok and new_value:
            self.save_state()
            item.setText(column, new_value)
            for row in self.data:
                if row['ID'] == item.text(4):
                    if column == 0:
                        row['Time'] = new_value
                        self.sort_data()
                        self.calculate_word_counts()
                        self.update_table()
                    elif column == 1:
                        row['Event'] = new_value
                        self.update_table()
                    elif column == 2:
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
            item.setText(4, row['ID'])
            if row.get('is_break'):
                for col in range(4):
                    item.setBackground(col, QColor(255, 228, 181))

    def save_state(self):
        import copy
        self.undo_stack.append(copy.deepcopy(self.data))

    def undo(self):
        if self.undo_stack:
            self.data = self.undo_stack.pop()
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

        self.save_state()

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
