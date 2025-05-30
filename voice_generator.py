# voice_generator.py
import os
import re
import inspect
import requests
import traceback # Added for detailed error logging
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal # Removed QSettings import
from mutagen.mp3 import MP3
from cartesia import Cartesia
from second_pass_commentator import SecondPassCommentator


class VoiceGenerator(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, input_path, api_key, voice_id=None, speed="normal", emotion=None, model_id="sonic-2", commentary_api_settings=None):
        super().__init__()
        self.input_path = input_path
        self.base_output_dir = "audio_output"
        self.api_key = api_key
        self.voice_id = voice_id if voice_id else "default-cartesia-voice-id"
        self.speed = speed
        self.emotion = emotion if emotion else []
        self.model_id = model_id
        self.commentary_api_settings = commentary_api_settings if commentary_api_settings else {}
        self.audio_segments = [] # Stores info about first pass audio
        self.output_dir = None # Path for the *single* audio output directory
        # self.output_dir_filled = None # REMOVED - Using single directory now
        self.client = None

        try:
            if self.api_key:
                 self.client = Cartesia(api_key=self.api_key)
            else:
                 # Cannot emit signal directly here before thread starts reliably
                 print("[VoiceGen Init] Error: Cartesia API Key is missing.")
        except Exception as e:
             print(f"[VoiceGen Init] Error initializing Cartesia client: {e}")
             self.client = None

    def run(self):
        # Ensure output_signal is connected before emitting
        # self.output_signal.emit("Starting voice commentary generation...")
        # self.progress_signal.emit(0)

        if not self.client:
            # Use print as fallback if signals aren't ready
            print("Error: Cartesia client not initialized. Aborting voice generation.")
            # self.output_signal.emit("Error: Cartesia client not initialized. Aborting.")
            return

        try:
            # Ensure signals can be emitted now
            self.output_signal.emit("Starting voice commentary generation...")
            self.progress_signal.emit(0)

            os.makedirs(self.base_output_dir, exist_ok=True)
            # --- Create SINGLE timestamped subdirectory for ALL audio ---
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            self.output_dir = os.path.join(self.base_output_dir, timestamp)
            os.makedirs(self.output_dir, exist_ok=True)
            self.output_signal.emit(f"Saving ALL audio segments to: {self.output_dir}")
            # ------------------------------------------------------------

            total_lines = self.count_lines()
            if total_lines == 0:
                 self.output_signal.emit("Warning: Input file has no timecoded commentary lines. Stopping.")
                 self.progress_signal.emit(100)
                 return
            processed_lines = 0

            # --- First pass voice generation ---
            self.output_signal.emit("Generating initial voice segments...")
            with open(self.input_path, 'r', encoding='utf-8', errors='replace') as file:
                for line in file:
                    match = re.match(r'(\d{2}:\d{2}:\d{2}) - (.+)', line.strip())
                    if match:
                        time_code, text = match.groups()
                        # Save to the single output directory, no suffix needed for first pass
                        audio_duration = self.generate_audio(text, time_code, target_dir=self.output_dir) # No suffix here
                        self.audio_segments.append({
                            'time_code': time_code,
                            'start_time': self.timecode_to_seconds(time_code),
                            'text': text,
                            # Base filename without suffix for tracking
                            'audio_file': f"Commentary_{time_code.replace(':', '')}.mp3",
                            'audio_duration': audio_duration
                        })
                        processed_lines += 1
                        progress = int((processed_lines / total_lines) * 50)
                        self.progress_signal.emit(progress)
            self.output_signal.emit("Initial voice segments generated.")
            # -----------------------------------

            # --- Create script for second pass ---
            second_pass_path = self.create_new_script()
            if not second_pass_path:
                 self.output_signal.emit("Error: Failed to create script for second pass. Aborting second pass.")
                 self.progress_signal.emit(100)
                 return
            # -------------------------------------

            # --- Validate settings for second pass ---
            if not self.commentary_api_settings: # Redundant check, but safe
                 self.output_signal.emit("Error: Commentary API settings missing, cannot run second pass.")
                 self.progress_signal.emit(100)
                 return
            # (Validation logic for api_type, model, key_present remains the same)
            api_type = self.commentary_api_settings.get('api')
            model = self.commentary_api_settings.get('model')
            key_present = False
            if api_type == 'claude' and self.commentary_api_settings.get('claude_key'): key_present = True
            elif api_type == 'openai' and self.commentary_api_settings.get('openai_key'): key_present = True
            elif api_type == 'gemini' and self.commentary_api_settings.get('google_key'): key_present = True
            if not api_type or not model or not key_present:
                 self.output_signal.emit(f"Error: Incomplete commentary settings for second pass. Skipping.")
                 self.progress_signal.emit(100)
                 return
            # -----------------------------------------

            # --- Run second pass TEXT generation ---
            self.output_signal.emit("\nStarting second pass commentary TEXT generation...")
            self.progress_signal.emit(50)
            second_pass = SecondPassCommentator(second_pass_path, self.commentary_api_settings)
            second_pass.output_signal.connect(self.output_signal.emit)
            second_pass.progress_signal.connect(lambda p: self.progress_signal.emit(50 + p // 4))
            second_pass.start()
            self.output_signal.emit("[VoiceGen Run] Waiting for SecondPassCommentator thread to finish...")
            second_pass.wait()
            self.output_signal.emit("[VoiceGen Run] SecondPassCommentator thread finished.")
            filled_commentary_path = second_pass.get_output_path()
            self.output_signal.emit(f"[VoiceGen Run] Path returned by second_pass.get_output_path(): {filled_commentary_path}")
            if filled_commentary_path: self.output_signal.emit(f"[VoiceGen Run] Checking existence of path: {os.path.exists(filled_commentary_path)}")
            # -------------------------------------

            # --- Second pass VOICE generation (if text file exists) ---
            if filled_commentary_path and os.path.exists(filled_commentary_path):
                self.output_signal.emit("\nStarting voice generation for FILLED commentary lines...")
                self.progress_signal.emit(75)

                # --- NO LONGER NEED SEPARATE DIRECTORY ---
                # filled_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                # self.output_dir_filled = os.path.join(self.base_output_dir, f"{filled_timestamp}_filled")
                # os.makedirs(self.output_dir_filled, exist_ok=True)
                # self.output_signal.emit(f"Saving filled audio segments to: {self.output_dir_filled}") # No longer true
                # ----------------------------------------

                processed_lines_filled = 0
                try:
                     with open(filled_commentary_path, 'r', encoding='utf-8', errors='replace') as file:
                        lines_in_filled_file = file.readlines()
                        # Count only lines that *don't* have the placeholder - these are the ones we generate audio for
                        total_lines_to_generate_filled = sum(1 for line in lines_in_filled_file if re.match(r'\d{2}:\d{2}:\d{2} - ', line) and "<COMMENTATE HERE" not in line)

                        if total_lines_to_generate_filled == 0:
                             self.output_signal.emit("Warning: Filled commentary file contains no valid lines requiring voice generation. Skipping.")
                        else:
                            self.output_signal.emit(f"Generating voice for {total_lines_to_generate_filled} filled/new lines...")
                            for line in lines_in_filled_file:
                                match = re.match(r'(\d{2}:\d{2}:\d{2}) - (.+)', line.strip())
                                if match:
                                    time_code, text = match.groups()
                                    # --- Check if this line was a placeholder that got filled ---
                                    # We only generate audio for lines that *don't* contain the original placeholder text
                                    # (assuming the AI replaced it correctly).
                                    # A simple check: if the text *doesn't* look like the placeholder, generate audio.
                                    # A more robust check would compare against the original script, but this is simpler.
                                    if "<COMMENTATE HERE" not in text:
                                        # --- Generate audio with suffix, saving to the *original* output dir ---
                                        audio_duration = self.generate_audio(
                                            text,
                                            time_code,
                                            target_dir=self.output_dir, # Save to the same dir
                                            filename_suffix="_filled"   # Add suffix
                                        )
                                        # --- (Optional: track filled segments if needed later) ---
                                        # self.audio_segments_filled.append({ ... })
                                        # --------------------------------------------------------
                                        processed_lines_filled += 1
                                        progress = int(75 + (processed_lines_filled / total_lines_to_generate_filled) * 25)
                                        self.progress_signal.emit(progress)
                                    # else: # Line still contains placeholder, skip voice gen for it
                                    #     self.output_signal.emit(f"Skipping voice gen for placeholder line: {time_code}")

                            self.output_signal.emit(f"\nFilled voice commentary generated and saved to {self.output_dir}")
                except Exception as e:
                     self.output_signal.emit(f"Error processing filled commentary file '{filled_commentary_path}': {e}")
                     self.output_signal.emit(traceback.format_exc())
            else:
                self.output_signal.emit(f"\nWarning: Filled commentary file ('{filled_commentary_path}') not found or text generation failed. Skipping second pass voice generation.")
            # ----------------------------------------------------

            self.output_signal.emit("\nVoice generation process complete.")
            self.progress_signal.emit(100)

        except Exception as e:
            self.output_signal.emit(f"An error occurred during voice generation run: {str(e)}")
            self.output_signal.emit(traceback.format_exc())
            self.progress_signal.emit(0)

    # --- MODIFIED generate_audio ---
    # Added filename_suffix parameter
    def generate_audio(self, text, time_code, target_dir=None, filename_suffix=""):
        output_directory = target_dir if target_dir else self.output_dir
        if not output_directory:
             self.output_signal.emit(f"Error: Output directory not set for timecode {time_code}. Skipping.")
             return 0

        text = re.sub(r'\s+', ' ', text).strip()
        if not text: return 0
        if not self.client:
            self.output_signal.emit(f"Error: Cartesia client not available for timecode {time_code}. Skipping.")
            return 0

        try:
            voice_params = {"id": self.voice_id, "mode": "id"}
            exp_controls = {}
            if self.speed and self.speed != "normal": exp_controls["speed"] = self.speed
            if self.emotion: exp_controls["emotion"] = self.emotion
            if exp_controls: voice_params["experimental_controls"] = exp_controls
            output_format_params = {"container": "mp3", "sample_rate": 44100}

            # --- Make API Request ---
            response = requests.post(
                "https://api.cartesia.ai/tts/bytes",
                headers={
                    "Cartesia-Version": "2024-05-10",
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "transcript": text, "model_id": self.model_id, "voice": voice_params,
                    "language": "en", "output_format": output_format_params
                }
            )
            # --- Handle Response ---
            if response.status_code != 200:
                raise Exception(f"Cartesia API request failed ({response.status_code}): {response.text}")
            audio_bytes = response.content
            if not audio_bytes: raise Exception("Cartesia API returned empty audio content.")

            # --- Construct Filename with Suffix ---
            time_code_safe = time_code.replace(':', '')
            output_filename = f"Commentary_{time_code_safe}{filename_suffix}.mp3" # Add suffix here
            output_path = os.path.join(output_directory, output_filename)
            # --------------------------------------

            os.makedirs(output_directory, exist_ok=True)
            with open(output_path, "wb") as f: f.write(audio_bytes)
            audio_duration = self.get_audio_duration(output_path)
            # self.output_signal.emit(f"Saved: {output_filename} ({audio_duration:.2f}s)") # Less verbose log
            return audio_duration

        except Exception as e:
            self.output_signal.emit(f"Error generating audio for time {time_code} (suffix: '{filename_suffix}'): {str(e)}")
            # Avoid printing full traceback for common API errors unless debugging needed
            if "Cartesia API request failed" not in str(e):
                 self.output_signal.emit(traceback.format_exc())
            return 0
    # --- END MODIFIED generate_audio ---

    def count_lines(self):
        """Counts only lines starting with a timecode in the input file."""
        try:
            if not self.input_path or not os.path.exists(self.input_path): return 0
            with open(self.input_path, 'r', encoding='utf-8', errors='replace') as file:
                return sum(1 for line in file if re.match(r'\d{2}:\d{2}:\d{2} - ', line))
        except Exception as e:
            self.output_signal.emit(f"Error counting lines in {self.input_path}: {e}")
            return 0

    def get_audio_duration(self, file_path):
        """Gets the duration of an MP3 file using mutagen."""
        try:
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0: return 0
            audio = MP3(file_path)
            if audio.info and audio.info.length > 0: return audio.info.length
            else: return 0 # Don't log warning for every file missing info
        except Exception: # Catch broad mutagen exceptions
            # self.output_signal.emit(f"Warning getting duration for {os.path.basename(file_path)}: {e}")
            return 0 # Return 0 if duration can't be read

    def create_new_script(self):
        """Creates the script with placeholders for the second commentator."""
        if not self.audio_segments:
             self.output_signal.emit("No audio segments generated in first pass. Cannot create second pass script.")
             return None

        self.audio_segments.sort(key=lambda x: x['start_time'])
        new_script_lines = []
        previous_segment_end_time = 0.0
        min_gap_for_placeholder = 2.0
        max_words_for_placeholder = 180
        min_words_for_placeholder = 8
        words_per_second_estimate = 3.7 # Can be tuned

        for i, segment in enumerate(self.audio_segments):
            gap_duration = segment['start_time'] - previous_segment_end_time
            if gap_duration >= min_gap_for_placeholder:
                estimated_words = int(gap_duration * words_per_second_estimate)
                words_to_request = max(min_words_for_placeholder, min(max_words_for_placeholder, estimated_words))
                placeholder_start_time = previous_segment_end_time + 0.5
                placeholder_timecode = self.seconds_to_timecode(placeholder_start_time)
                placeholder_line = f"{placeholder_timecode} - <COMMENTATE HERE IN {words_to_request} WORDS>"
                new_script_lines.append(placeholder_line)

            original_line = f"{segment['time_code']} - {segment['text']}"
            new_script_lines.append(original_line)
            # Use duration, fallback to estimate if needed
            current_segment_duration = segment['audio_duration'] if segment['audio_duration'] > 0 else (len(segment['text']) / (words_per_second_estimate * 5)) # Rough fallback estimate
            previous_segment_end_time = segment['start_time'] + current_segment_duration

        try:
             input_dir = os.path.dirname(self.input_path)
             if not input_dir or not os.path.isdir(input_dir): input_dir = os.getcwd()
             base_filename = os.path.splitext(os.path.basename(self.input_path))[0]
             new_script_filename = f"{base_filename}_second_commentator.txt"
             new_script_path = os.path.join(input_dir, new_script_filename)

             with open(new_script_path, 'w', encoding='utf-8') as f:
                 f.write('\n'.join(new_script_lines))
             self.output_signal.emit(f"Script for second pass saved: {new_script_path}")
             return new_script_path
        except Exception as e:
             self.output_signal.emit(f"Error creating second pass script file: {e}")
             self.output_signal.emit(traceback.format_exc())
             return None

    def timecode_to_seconds(self, timecode):
        """Converts HH:MM:SS timecode string to seconds."""
        try:
            parts = list(map(int, timecode.split(':')))
            if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
            elif len(parts) == 2: return parts[0] * 60 + parts[1]
            else: return 0
        except (ValueError, TypeError): return 0

    def seconds_to_timecode(self, seconds):
        """Converts seconds to HH:MM:SS timecode string."""
        seconds = max(0, float(seconds))
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def get_output_dir(self):
        """Returns the path to the single output directory used."""
        # Now always returns the single directory path or the base fallback
        if self.output_dir and os.path.isdir(self.output_dir):
             return os.path.abspath(self.output_dir)
        else:
             # Return the base directory if specific one wasn't created or found
             return os.path.abspath(self.base_output_dir)