import os
import re
from PyQt5.QtCore import QThread, pyqtSignal
import anthropic
from voice_generator import VoiceGenerator

class SecondPassCommentator(QThread):
    output_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, input_path, claude_api_key, eleven_labs_api_key):
        super().__init__()
        self.input_path = input_path
        self.claude_api_key = claude_api_key
        self.eleven_labs_api_key = eleven_labs_api_key
        self.client = anthropic.Anthropic(api_key=claude_api_key)
        self.system_prompt = self.load_prompt("second_commentator.txt")
        
    def run(self):
        self.output_signal.emit("Starting second pass commentary generation...")
        self.progress_signal.emit(0)
        
        try:
            # Process continues until no more <> tags are found
            current_input = self.input_path
            iteration = 1
            
            while True:
                # Check if there are any <> tags in the current file
                with open(current_input, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if not re.search(r'<.+>', content):
                        break
                
                self.output_signal.emit(f"\nStarting iteration {iteration}...")
                
                # Generate new commentary
                commentary = self.get_ai_commentary(content)
                
                # Create new output file
                base_name = os.path.splitext(current_input)[0]
                new_output = f"{base_name}_pass{iteration}.txt"
                
                # Write the new commentary
                with open(new_output, 'w', encoding='utf-8') as f:
                    f.write(commentary)
                
                # Run through voice generator
                voice_gen = VoiceGenerator(new_output, self.eleven_labs_api_key)
                voice_gen.output_signal.connect(lambda x: self.output_signal.emit(f"Voice Generator: {x}"))
                voice_gen.progress_signal.connect(self.progress_signal.emit)
                voice_gen.run()
                
                # Update current input to the voice generator's output file
                current_input = voice_gen.get_output_dir()
                iteration += 1
                
                self.progress_signal.emit((iteration * 25) % 100)  # Cycle progress bar
            
            self.output_signal.emit("All commentary passes completed!")
            self.progress_signal.emit(100)
            
        except Exception as e:
            self.output_signal.emit(f"An error occurred: {str(e)}")

    def load_prompt(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                return file.read()
        except FileNotFoundError:
            return f"Error: {filename} not found. Please create this file with the desired prompt."

    def get_ai_commentary(self, race_events):
        messages = [
            {
                "role": "user",
                "content": (
                    f"Here's the race commentary that needs filling in:\n\n{race_events}\n\n"
                    "Please provide commentary for each section marked with <>, maintaining the exact original format and timecodes."
                )
            }
        ]

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=8000,
            temperature=0.99,
            system=self.system_prompt,
            messages=messages
        )

        return response.content[0].text
