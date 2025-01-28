import tkinter as tk
from tkinter import filedialog, messagebox
import time
import os
import sys

##########################
# Parsing / Utility
##########################

def parse_time_to_seconds(timestr):
    """Parse HH:MM:SS into integer seconds."""
    h, m, s = timestr.split(':')
    return int(h)*3600 + int(m)*60 + int(s)

def parse_event_line(line):
    """Parse a line 'HH:MM:SS - Description' into (seconds, description)."""
    line = line.strip()
    if not line:
        return None
    parts = line.split(' - ', 1)
    if len(parts) < 2:
        return None
    time_str, description = parts
    return (parse_time_to_seconds(time_str), description)

def load_events_from_file(filename):
    """Read each line, parse into (seconds, description), sort by time."""
    events = []
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            parsed = parse_event_line(line)
            if parsed:
                events.append(parsed)
    events.sort(key=lambda e: e[0])
    return events

def beep(different=False):
    """
    Produce a beep. If on Windows, you can use winsound.Beep().
    Otherwise, we just print the ASCII bell character.
    """
    if different:
        print("!!! BEEP (Different) !!!\a")
    else:
        print("Beep!\a")

##########################
# Tkinter GUI
##########################

class RaceTimerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Race Timer (Always on Top)")
        self.root.geometry("800x600")

        # Force the window to be on top
        self.root.attributes("-topmost", True)

        self.events = []          # List of (second, description)
        self.current_time = 0     # How many seconds since race start
        self.paused = True        # Start paused (or in "not started" mode)
        self.countdown_active = False
        self.countdown_time = 10

        # UI Elements
        self.create_widgets()

    def create_widgets(self):
        # Frame for file loading
        file_frame = tk.Frame(self.root)
        file_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        btn_load = tk.Button(file_frame, text="Load Events File", command=self.load_file)
        btn_load.pack(side=tk.LEFT, padx=5)

        # Countdown / Timer Label
        self.countdown_label = tk.Label(self.root, text="", font=("Arial", 14), fg="red")
        self.countdown_label.pack(pady=5)

        self.timer_label = tk.Label(self.root, text="Current Time: 0 s", font=("Arial", 14, "bold"))
        self.timer_label.pack(pady=5)

        # Control buttons
        controls_frame = tk.Frame(self.root)
        controls_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        self.btn_start = tk.Button(controls_frame, text="Start Countdown", command=self.start_countdown)
        self.btn_start.pack(side=tk.LEFT, padx=2)

        self.btn_pause = tk.Button(controls_frame, text="Pause/Unpause", command=self.toggle_pause, state=tk.DISABLED)
        self.btn_pause.pack(side=tk.LEFT, padx=2)

        self.btn_rewind = tk.Button(controls_frame, text="Rewind 10s", command=self.rewind_10s, state=tk.DISABLED)
        self.btn_rewind.pack(side=tk.LEFT, padx=2)

        self.btn_ffwd = tk.Button(controls_frame, text="FFwd 10s", command=self.ffwd_10s, state=tk.DISABLED)
        self.btn_ffwd.pack(side=tk.LEFT, padx=2)

        self.btn_stop = tk.Button(controls_frame, text="Stop", command=self.stop_race, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=2)

        # Text area for displaying past/future events
        self.events_text = tk.Text(self.root, width=100, height=25)
        self.events_text.pack(padx=5, pady=5)

    def load_file(self):
        """Open a file dialog to load events."""
        filename = filedialog.askopenfilename(title="Select events file", 
                                              filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if not filename:
            return  # user canceled
        try:
            self.events = load_events_from_file(filename)
            messagebox.showinfo("Success", f"Loaded {len(self.events)} events from:\n{os.path.basename(filename)}")
            # Enable start button
            self.btn_start.config(state=tk.NORMAL)
            self.current_time = 0
            self.paused = True
            self.timer_label.config(text=f"Current Time: {self.current_time} s")
            self.update_events_text()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def start_countdown(self):
        """Start the 10-second countdown before the race."""
        if not self.events:
            messagebox.showwarning("No Events", "Please load an events file first.")
            return

        # Disable start button while countdown is active
        self.btn_start.config(state=tk.DISABLED)
        self.btn_pause.config(state=tk.DISABLED)
        self.btn_rewind.config(state=tk.DISABLED)
        self.btn_ffwd.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.DISABLED)

        self.countdown_time = 10
        self.countdown_active = True
        self.paused = True
        self.update_countdown_label()  # Start the countdown cycle

    def update_countdown_label(self):
        """Update the countdown label each second until 0."""
        if not self.countdown_active:
            return

        if self.countdown_time > 0:
            # beep logic at 5s and each second from 5..1
            if self.countdown_time <= 5:
                beep()  # beep
            self.countdown_label.config(text=f"Countdown: {self.countdown_time}...")
            self.countdown_time -= 1
            self.root.after(1000, self.update_countdown_label)
        else:
            # Final beep
            beep(different=True)
            self.countdown_label.config(text="Countdown: 0. GO!")
            self.countdown_active = False
            self.paused = False
            # Enable race controls
            self.btn_pause.config(state=tk.NORMAL)
            self.btn_rewind.config(state=tk.NORMAL)
            self.btn_ffwd.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.NORMAL)
            # Clear the label after a short delay
            self.root.after(1000, lambda: self.countdown_label.config(text=""))

            # Start race time updates
            self.update_race_time()

    def update_race_time(self):
        """Update the race timer every second (if not paused)."""
        # If the race has been 'stopped', don't continue
        if self.stopped:
            return

        if not self.paused:
            self.current_time += 1

        self.timer_label.config(text=f"Current Time: {self.current_time} s")
        self.update_events_text()

        # Schedule the next update in 1 second
        self.root.after(1000, self.update_race_time)

    def update_events_text(self):
        """
        Display the past 10s of events and next 20s of events in the text box.
        Instead of actual HH:MM:SS, show how many seconds ago or in the future.
        """
        text_lines = []
        past_window_start = self.current_time - 10
        future_window_end = self.current_time + 20

        past_events = []
        future_events = []

        for (ev_time, ev_desc) in self.events:
            if past_window_start <= ev_time < self.current_time:
                seconds_ago = self.current_time - ev_time
                past_events.append((seconds_ago, ev_desc))
            elif self.current_time <= ev_time <= future_window_end:
                seconds_future = ev_time - self.current_time
                future_events.append((seconds_future, ev_desc))

        # Sort ascending
        past_events.sort(key=lambda x: x[0])
        future_events.sort(key=lambda x: x[0])

        text_lines.append("---- Past 10 seconds ----")
        for (sec_ago, desc) in past_events:
            text_lines.append(f"{sec_ago} seconds ago: {desc}")

        text_lines.append("---- Next 20 seconds ----")
        for (sec_future, desc) in future_events:
            text_lines.append(f"In {sec_future} seconds: {desc}")

        # Update the text box
        self.events_text.delete("1.0", tk.END)
        self.events_text.insert(tk.END, "\n".join(text_lines))

    def toggle_pause(self):
        """Pause / Unpause the race."""
        self.paused = not self.paused
        if self.paused:
            self.countdown_label.config(text="=== PAUSED ===", fg="blue")
        else:
            self.countdown_label.config(text="")
        # No need to do anything else, the update_race_time will handle it.

    def rewind_10s(self):
        """Rewind the current race time by 10 seconds (min 0)."""
        self.current_time = max(0, self.current_time - 10)
        self.update_events_text()

    def ffwd_10s(self):
        """Fast-forward the current race time by 10 seconds."""
        self.current_time += 10
        self.update_events_text()

    def stop_race(self):
        """Stop the race completely."""
        self.paused = True
        self.stopped = True
        self.countdown_label.config(text="=== STOPPED ===", fg="red")
        # Disable control buttons
        self.btn_pause.config(state=tk.DISABLED)
        self.btn_rewind.config(state=tk.DISABLED)
        self.btn_ffwd.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.DISABLED)
    
    @property
    def stopped(self):
        return getattr(self, "_stopped", False)

    @stopped.setter
    def stopped(self, val):
        self._stopped = val


def main():
    root = tk.Tk()
    app = RaceTimerApp(root)
    # Initially, race is "stopped" (or not started), so we set:
    app.stopped = False

    root.mainloop()

if __name__ == "__main__":
    main()
