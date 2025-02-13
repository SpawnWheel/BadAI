import os
import re
import requests
from datetime import datetime
from PyQt5.QtCore import QThread, pyqtSignal, QSettings
from mutagen.mp3 import MP3


class VoiceGenerator(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, input_path, api_key):
        super().__init__()
        self.input_path = input_path
        self.base_output_dir = "audio_output"  # Base directory
        self.chunk_size = 1024
        self.xi_api_key = api_key
        self.voice_id = "Mw9TampTt4PGYMa0FYBO"  # Default voice ID
        self.tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"
        self.audio_segments = []

    def run(self):
        self.output_signal.emit("Starting voice commentary generation...")
        self.progress_signal.emit(0)

        try:
            # Create the base output directory if it doesn't exist
            os.makedirs(self.base_output_dir, exist_ok=True)

            # Get API settings from QSettings
            settings = QSettings("BadAICommentary", "SimRacingCommentator")

            # Create a timestamped subdirectory within the base output directory
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            self.output_dir = os.path.join(self.base_output_dir, timestamp)
            os.makedirs(self.output_dir, exist_ok=True)

            total_lines = self.count_lines()
            processed_lines = 0

            with open(self.input_path, 'r', encoding='utf-8', errors='replace') as file:
                for line in file:
                    match = re.match(r'(\d{2}:\d{2}:\d{2}) - (.+)', line.strip())
                    if match:
                        time_code, text = match.groups()
                        audio_duration = self.generate_audio(text, time_code)

                        # Store segment information
                        self.audio_segments.append({
                            'time_code': time_code,
                            'start_time': self.timecode_to_seconds(time_code),
                            'text': text,
                            'audio_file': f"Commentary_{time_code.replace(':', '')}.mp3",
                            'audio_duration': audio_duration
                        })

                        processed_lines += 1
                        progress = int((processed_lines / total_lines) * 100)
                        self.progress_signal.emit(progress)

            # Calculate gaps and generate the new script with added events
            second_pass_path = self.create_new_script()

            # Initialize settings for second pass
            api_settings = {
                "api": settings.value("race_commentator_api", "claude"),
                "model": settings.value("race_commentator_model", "claude-3-5-sonnet-20241022"),
                "claude_key": settings.value("claude_api_key", ""),
                "openai_key": settings.value("openai_api_key", "")
            }

            # Run second pass commentary
            self.output_signal.emit("\nStarting second pass commentary generation...")

            from second_pass_commentator import SecondPassCommentator
            second_pass = SecondPassCommentator(second_pass_path, api_settings)
            second_pass.output_signal.connect(self.output_signal.emit)
            second_pass.progress_signal.connect(self.progress_signal.emit)
            second_pass.start()
            second_pass.wait()  # Wait for completion

            filled_commentary_path = second_pass.get_output_path()
            if filled_commentary_path and os.path.exists(filled_commentary_path):
                self.output_signal.emit("\nStarting voice generation for filled commentary...")

                # Create a new subdirectory for the second pass audio
                second_pass_timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                self.output_dir = os.path.join(self.base_output_dir, f"{second_pass_timestamp}_filled")
                os.makedirs(self.output_dir, exist_ok=True)

                # Reset audio segments for the second pass
                self.audio_segments = []
                processed_lines = 0

                # Read and process the filled commentary
                with open(filled_commentary_path, 'r', encoding='utf-8', errors='replace') as file:
                    total_lines = sum(1 for line in file if re.match(r'\d{2}:\d{2}:\d{2} - ', line))
                    file.seek(0)  # Reset file pointer to beginning

                    for line in file:
                        match = re.match(r'(\d{2}:\d{2}:\d{2}) - (.+)', line.strip())
                        if match:
                            time_code, text = match.groups()
                            audio_duration = self.generate_audio(text, time_code)

                            # Store segment information
                            self.audio_segments.append({
                                'time_code': time_code,
                                'start_time': self.timecode_to_seconds(time_code),
                                'text': text,
                                'audio_file': f"Commentary_{time_code.replace(':', '')}.mp3",
                                'audio_duration': audio_duration
                            })

                            processed_lines += 1
                            progress = int((processed_lines / total_lines) * 100)
                            self.progress_signal.emit(progress)

            self.output_signal.emit("\nVoice generation complete for both initial and filled commentary!")
            self.progress_signal.emit(100)

        except Exception as e:
            self.output_signal.emit(f"An error occurred: {str(e)}")

    def count_lines(self):
        with open(self.input_path, 'r', encoding='utf-8', errors='replace') as file:
            return sum(1 for line in file if re.match(r'\d{2}:\d{2}:\d{2} - ', line))

    def generate_audio(self, text, time_code):
        # Remove line breaks and extra spaces from the text
        text = re.sub(r'\s+', ' ', text).strip()

        headers = {
            "Accept": "application/json",
            "xi-api-key": self.xi_api_key
        }
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.7,
                "similarity_boost": 0.8,
                "style": 0.4,
                "use_speaker_boost": True
            }
        }

        response = requests.post(self.tts_url, headers=headers, json=data, stream=True)

        if response.ok:
            output_path = os.path.join(self.output_dir, f"Commentary_{time_code.replace(':', '')}.mp3")

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    f.write(chunk)

            # Get the duration of the audio using mutagen
            audio_duration = self.get_audio_duration(output_path)

            self.output_signal.emit(f"Audio saved: {output_path}")
            return audio_duration
        else:
            self.output_signal.emit(f"Error generating audio for time {time_code}: {response.text}")
            return 0

    def get_audio_duration(self, file_path):
        try:
            audio = MP3(file_path)
            return audio.info.length  # duration in seconds
        except Exception as e:
            self.output_signal.emit(f"Error getting duration for {file_path}: {str(e)}")
            return 0

    def create_new_script(self):
        # Sort segments by start time
        self.audio_segments.sort(key=lambda x: x['start_time'])

        # Initialize new script content
        new_script = []
        previous_end_time = None

        for segment in self.audio_segments:
            if previous_end_time is not None:
                gap = segment['start_time'] - previous_end_time
                if gap > 0:
                    words = int(gap * 3)  # Calculate words based on gap

                    # Only add commentary request if within word limits
                    if 8 <= words <= 180:
                        time_code = self.seconds_to_timecode(previous_end_time)
                        new_script.append(f"{time_code} - <COMMENTATE HERE IN {words} WORDS>")

            # Append the original script
            new_script.append(f"{segment['time_code']} - {segment['text']}")
            previous_end_time = segment['start_time'] + segment['audio_duration']

        # Save the new script file
        base_filename = os.path.splitext(os.path.basename(self.input_path))[0]
        new_script_filename = f"{base_filename}_second_commentator.txt"
        new_script_path = os.path.join(os.path.dirname(self.input_path), new_script_filename)

        with open(new_script_path, 'w', encoding='utf-8') as f:
            for line in new_script:
                f.write(line + '\n')

        self.output_signal.emit(f"New script file saved: {new_script_path}")
        return new_script_path

    def timecode_to_seconds(self, timecode):
        h, m, s = map(int, timecode.split(':'))
        return h * 3600 + m * 60 + s

    def seconds_to_timecode(self, seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def get_output_dir(self):
        return os.path.abspath(self.output_dir)

    def set_voice(self, voice_id):
        self.voice_id = voice_id
        self.tts_url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"