import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import csv
import re
from datetime import datetime, timedelta
import threading
import queue

class TextToTextConverter:
    def __init__(self, master):
        self.master = master
        master.title("Text to Text Converter")
        master.geometry("900x700")
        master.minsize(600, 400)  # Set a minimum window size

        self.data = []
        self.undo_stack = []
        self.queue = queue.Queue()
        self.next_id = 0  # Initialize unique ID counter

        # Start the queue processing
        self.master.after(100, self.process_queue)

        # Main frame
        main_frame = ttk.Frame(master)
        main_frame.grid(row=0, column=0, sticky="nsew")
        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1)

        # Top frame for offset input and WPS
        top_frame = ttk.Frame(main_frame)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        top_frame.grid_columnconfigure(6, weight=1)

        # Offset label and entry
        offset_label = ttk.Label(top_frame, text="Time Offset (HH:MM:SS):")
        offset_label.grid(row=0, column=0, padx=(0, 5))

        self.offset_entry = ttk.Entry(top_frame, width=15)
        self.offset_entry.grid(row=0, column=1, padx=(0, 10))

        apply_offset_button = ttk.Button(top_frame, text="Apply Offset", command=self.apply_offset)
        apply_offset_button.grid(row=0, column=2)

        # Words Per Second label and entry
        wps_label = ttk.Label(top_frame, text="Words Per Second:")
        wps_label.grid(row=0, column=3, padx=(10, 5))

        self.wps_entry = ttk.Entry(top_frame, width=10)
        self.wps_entry.grid(row=0, column=4, padx=(0, 10))
        self.wps_entry.insert(0, '3.7')  # default value

        recalculate_button = ttk.Button(top_frame, text="Recalculate Words", command=self.calculate_word_counts)
        recalculate_button.grid(row=0, column=5, padx=(0, 10))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        button_frame.grid_columnconfigure(1, weight=1)

        # Create buttons
        self.load_button = ttk.Button(button_frame, text="Load Text File", command=self.load_file)
        self.load_button.grid(row=0, column=0, padx=(0, 10))

        self.save_button = ttk.Button(button_frame, text="Save Text File", command=self.save_text_file)
        self.save_button.grid(row=0, column=3)

        # Create progress bar
        self.progress = ttk.Progressbar(button_frame, orient="horizontal", length=200, mode="determinate")
        self.progress.grid(row=0, column=1, sticky="ew")

        # Progress label
        self.progress_label = ttk.Label(button_frame, text="")
        self.progress_label.grid(row=0, column=2, sticky="w", padx=10)

        # Make button frame expand horizontally
        button_frame.grid_columnconfigure(1, weight=1)

        # Create table
        self.table_frame = ttk.Frame(main_frame)
        self.table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Create treeview for table
        self.tree = ttk.Treeview(
            self.table_frame,
            columns=("Time", "Event", "Additional Information", "Words"),
            show="headings"
        )
        self.tree.heading("Time", text="Time")
        self.tree.heading("Event", text="Event")
        self.tree.heading("Additional Information", text="Additional Information")
        self.tree.heading("Words", text="Words")

        # Configure columns to stretch
        self.tree.column("Time", minwidth=80, width=100, anchor='w', stretch=False)
        self.tree.column("Event", minwidth=200, width=300, anchor='w', stretch=True)
        self.tree.column("Additional Information", minwidth=150, width=200, anchor='w', stretch=True)
        self.tree.column("Words", minwidth=60, width=80, anchor='center', stretch=False)

        self.tree.grid(row=0, column=0, sticky="nsew")

        # Scrollbar for treeview
        self.scrollbar = ttk.Scrollbar(self.table_frame, orient="vertical", command=self.tree.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=self.scrollbar.set)

        self.table_frame.grid_rowconfigure(0, weight=1)
        self.table_frame.grid_columnconfigure(0, weight=1)

        # Right-click menu
        self.right_click_menu = tk.Menu(master, tearoff=0)
        self.right_click_menu.add_command(label="Merge", command=self.merge_rows)
        self.right_click_menu.add_command(label="Delete", command=self.delete_row)
        self.right_click_menu.add_command(label="Insert Before", command=lambda: self.insert_row("before"))
        self.right_click_menu.add_command(label="Insert After", command=lambda: self.insert_row("after"))

        self.tree.bind("<Button-3>", self.show_right_click_menu)
        self.tree.bind("<Double-1>", self.on_double_click)

        # Bind undo functionality
        self.master.bind("<Control-z>", self.undo_action)

        # Bind the Treeview to adjust columns on resize
        self.tree.bind('<Configure>', self.adjust_column_widths)

    def adjust_column_widths(self, event):
        total_width = self.tree.winfo_width()

        # Fixed widths for non-stretchable columns
        time_width = 100
        words_width = 80

        # Remaining width is distributed among stretchable columns
        remaining_width = total_width - time_width - words_width - 20  # Subtract scrollbar width and padding

        event_width = int(remaining_width * 0.5)
        additional_info_width = remaining_width - event_width

        self.tree.column("Time", width=time_width)
        self.tree.column("Event", width=event_width)
        self.tree.column("Additional Information", width=additional_info_width)
        self.tree.column("Words", width=words_width)

    def process_queue(self):
        try:
            while True:
                func, args = self.queue.get_nowait()
                func(*args)
        except queue.Empty:
            pass
        self.master.after(100, self.process_queue)

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            self.progress_label.config(text="Loading file...")
            self.progress["value"] = 0
            threading.Thread(target=self.load_file_thread, args=(file_path,)).start()

    def load_file_thread(self, file_path):
        try:
            self.data = []
            chunk_size = 1000
            total_lines = sum(1 for _ in open(file_path, 'rb'))
            processed_lines = 0

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                for i, chunk in enumerate(self.read_in_chunks(file, chunk_size)):
                    chunk_data = self.parse_chunk(chunk)
                    self.data.extend(chunk_data)
                    processed_lines += len(chunk)

                    # Update progress
                    if i % 10 == 0 or processed_lines == total_lines:
                        progress = processed_lines / total_lines * 100
                        self.queue.put((self.update_progress, (progress,)))

            self.queue.put((self.update_table, ()))
            self.queue.put((self.progress_label.config, {"text": "File loaded successfully"}))
            self.queue.put((self.calculate_word_counts, ()))
        except Exception as e:
            self.queue.put((messagebox.showerror, ("Error", f"An error occurred while loading the file: {str(e)}")))
        finally:
            self.queue.put((lambda: self.progress_label.config(text=""), ()))

    def update_progress(self, value):
        self.progress["value"] = value
        self.progress_label.config(text=f"Processing: {value:.1f}%")

    def read_in_chunks(self, file_object, chunk_size):
        while True:
            data = file_object.readlines(chunk_size)
            if not data:
                break
            yield data

    def parse_chunk(self, chunk):
        chunk_data = []
        for line in chunk:
            line = ''.join(char if ord(char) < 128 else ' ' for char in line)
            match = re.match(r'(\d{2}:\d{2}:\d{2}) - (.+)', line.strip())
            if match:
                time, event = match.groups()
                row_id = f"ID_{self.next_id}"
                self.next_id += 1
                chunk_data.append({'ID': row_id, 'Time': time, 'Event': event, 'Additional Information': '', 'Words': 0})
        return chunk_data

    def calculate_word_counts(self):
        try:
            wps = float(self.wps_entry.get())
        except ValueError:
            wps = 3.7  # default value if invalid input

        for i in range(len(self.data) - 1):
            time_diff = self.time_difference(self.data[i]['Time'], self.data[i + 1]['Time'])
            self.data[i]['Words'] = int(time_diff * wps)  # Words count

        # Handle the last row
        if self.data:
            self.data[-1]['Words'] = 100  # Default value

        self.update_table()

    def time_difference(self, time1, time2):
        t1 = datetime.strptime(time1, "%H:%M:%S")
        t2 = datetime.strptime(time2, "%H:%M:%S")
        return (t2 - t1).total_seconds()

    def show_right_click_menu(self, event):
        selected_items = self.tree.selection()
        # Update the menu based on selection
        self.right_click_menu.entryconfig("Merge", state="disabled" if len(selected_items) != 2 else "normal")
        try:
            item = self.tree.identify_row(event.y)
            if item:
                # Do not change selection on right-click
                self.right_click_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.right_click_menu.grab_release()

    def merge_rows(self):
        selected_items = self.tree.selection()
        if len(selected_items) != 2:
            messagebox.showerror("Error", "Please select exactly two rows to merge.")
            return

        # Save state for undo
        self.save_state()

        item1, item2 = selected_items

        # Get row IDs
        id1 = item1
        id2 = item2

        # Find indices in self.data
        data_index1 = next(i for i, v in enumerate(self.data) if v['ID'] == id1)
        data_index2 = next(i for i, v in enumerate(self.data) if v['ID'] == id2)

        # Ensure data_index1 is smaller
        if data_index1 > data_index2:
            data_index1, data_index2 = data_index2, data_index1
            id1, id2 = id2, id1
            item1, item2 = item2, item1

        row1 = self.data[data_index1]
        row2 = self.data[data_index2]

        merged_event = f"{row1['Event']} {row2['Event']}"
        merged_additional_info = f"{row1['Additional Information']} {row2['Additional Information']}"

        # Sum the word counts
        merged_words = int(row1['Words']) + int(row2['Words'])

        # Update self.data
        self.data[data_index1]['Event'] = merged_event
        self.data[data_index1]['Additional Information'] = merged_additional_info
        self.data[data_index1]['Words'] = merged_words
        del self.data[data_index2]

        # Update the Treeview
        self.update_table()

        # Recalculate word counts
        self.calculate_word_counts()

    def delete_row(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showerror("Error", "Please select a row to delete.")
            return

        # Save state for undo
        self.save_state()

        for item in selected_items:
            id_ = item  # Since item IDs are row IDs
            index = next(i for i, v in enumerate(self.data) if v['ID'] == id_)
            del self.data[index]
            self.tree.delete(item)

        # Recalculate word counts
        self.calculate_word_counts()

    def insert_row(self, position):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showerror("Error", "Please select a row to insert near.")
            return

        # Save state for undo
        self.save_state()

        selected_item = selected_items[0]
        selected_id = selected_item
        selected_index = self.tree.index(selected_item)
        selected_values = self.tree.item(selected_item)['values']

        # Determine the timecode for the new row
        if position == "before" and selected_index > 0:
            prev_item = self.tree.prev(selected_item)
            timecode = self.tree.item(prev_item)['values'][0]
        else:
            timecode = selected_values[0]

        # Create a new row with default values
        new_id = f"ID_{self.next_id}"
        self.next_id += 1
        new_row = {
            'ID': new_id,
            'Time': timecode,
            'Event': "New Event",
            'Additional Information': "",
            'Words': 0
        }

        # Insert the new row in self.data
        data_index = next(i for i, v in enumerate(self.data) if v['ID'] == selected_id)
        if position == "after":
            self.data.insert(data_index + 1, new_row)
        else:  # "before"
            self.data.insert(data_index, new_row)

        # Recalculate word counts
        self.calculate_word_counts()

        # Update the Treeview
        self.update_table()

        # Start editing the new row
        self.tree.selection_set(new_id)
        self.on_double_click(None)

    def save_text_file(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as txtfile:
                    for row in self.data:
                        time = row['Time']
                        event = row['Event']
                        additional_info = row['Additional Information']
                        words = row['Words']
                        line = f"{time} - {event} {additional_info} Commentate in {words} words."
                        txtfile.write(line + '\n')
                messagebox.showinfo("Success", "Text file saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred while saving the file: {str(e)}")

    def on_double_click(self, event):
        if event:
            item = self.tree.identify('item', event.x, event.y)
            column = self.tree.identify_column(event.x)
        else:
            item = self.tree.selection()[0]
            column = '#1'  # Default to editing the first displayed column

        if item and column:
            column_index = int(column[1:]) - 1  # Adjust to 0-based index

            if column_index in [0, 1, 2]:  # Allow editing Time, Event, Additional Information
                self.edit_cell(item, column_index)

    def edit_cell(self, item, column_index):
        values = self.tree.item(item)['values']
        old_value = values[column_index]

        entrybox = ttk.Entry(self.tree)
        entrybox.insert(0, old_value)

        def save_edit(event=None):
            new_value = entrybox.get()
            values = list(self.tree.item(item)['values'])
            values[column_index] = new_value
            self.tree.item(item, values=values)
            entrybox.destroy()

            # Save state for undo
            self.save_state()

            # Update self.data using the row ID
            row_id = item  # Since we set item IDs to be row IDs
            index = next(i for i, v in enumerate(self.data) if v['ID'] == row_id)

            if column_index == 0:
                self.data[index]['Time'] = new_value
                self.sort_data()
                self.calculate_word_counts()
            elif column_index == 1:
                self.data[index]['Event'] = new_value
            elif column_index == 2:
                self.data[index]['Additional Information'] = new_value

            # Update the table after editing
            self.update_table()

        entrybox.bind('<FocusOut>', save_edit)
        entrybox.bind('<Return>', save_edit)
        entrybox.focus_set()

        # Position the entrybox
        bbox = self.tree.bbox(item, f'#{column_index + 1}')
        if not bbox:
            return  # Cell is not visible
        entrybox.place(x=bbox[0], y=bbox[1], width=bbox[2])

    def sort_data(self):
        try:
            self.data.sort(key=lambda x: datetime.strptime(x['Time'], "%H:%M:%S"))
        except ValueError as e:
            messagebox.showerror("Error", f"Time format error: {str(e)}")

    def update_table(self):
        self.tree.delete(*self.tree.get_children())
        for row in self.data:
            self.tree.insert("", "end", iid=row['ID'], values=(
                row['Time'],
                row['Event'],
                row['Additional Information'],
                row['Words']
            ))

    def save_state(self):
        # Save a deep copy of self.data for undo functionality
        import copy
        self.undo_stack.append(copy.deepcopy(self.data))

    def undo_action(self, event=None):
        if self.undo_stack:
            self.data = self.undo_stack.pop()
            self.update_table()
            self.calculate_word_counts()
        else:
            messagebox.showinfo("Undo", "Nothing to undo.")

    def apply_offset(self):
        offset_str = self.offset_entry.get().strip()
        if not offset_str:
            messagebox.showerror("Error", "Please enter a time offset.")
            return
        try:
            offset = datetime.strptime(offset_str, "%H:%M:%S")
            offset_delta = timedelta(hours=offset.hour, minutes=offset.minute, seconds=offset.second)
        except ValueError:
            messagebox.showerror("Error", "Invalid time format. Please use HH:MM:SS.")
            return

        # Save state for undo
        self.save_state()

        # Apply the offset to all timecodes
        for row in self.data:
            try:
                time_obj = datetime.strptime(row['Time'], "%H:%M:%S")
                new_time = time_obj + offset_delta
                row['Time'] = new_time.strftime("%H:%M:%S")
            except ValueError:
                messagebox.showerror("Error", f"Invalid time format in data: {row['Time']}")
                return

        # Recalculate word counts and update table
        self.sort_data()
        self.calculate_word_counts()
        self.update_table()
        messagebox.showinfo("Success", "Time offset applied successfully!")

if __name__ == "__main__":
    root = tk.Tk()
    app = TextToTextConverter(root)
    root.mainloop()
