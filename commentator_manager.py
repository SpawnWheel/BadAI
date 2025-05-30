import os
import shutil
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class CommentatorMetadata:
    name: str
    personality: str
    style: str
    examples: list[str]
    voice_id: str
    voice_speed: str = "normal"
    voice_emotions: list[str] = field(default_factory=list)
    voice_intensity: str = "medium"


class CommentatorManager:
    def __init__(self):
        self.base_dir = "Commentators"
        self._ensure_base_directory()

    def _ensure_base_directory(self):
        """Create the base Commentators directory if it doesn't exist."""
        os.makedirs(self.base_dir, exist_ok=True)

    def _create_metadata_file(self, commentator_dir: str, name: str, personality: str,
                              style: str, examples: list[str], voice_id: str,
                              voice_speed: str = "normal", voice_emotions: list[str] = None,
                              voice_intensity: str = "medium"):
        """Create a metadata file for a commentator."""
        metadata_path = os.path.join(commentator_dir, "metadata.txt")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            f.write(f"[NAME]\n{name}\n\n")
            f.write(f"[PERSONALITY]\n{personality}\n\n")
            f.write(f"[STYLE]\n{style}\n\n")
            f.write("[EXAMPLES]\n")
            for example in examples:
                f.write(f"{example}\n")
            f.write(f"\n[VOICE_ID]\n{voice_id}\n\n")
            f.write(f"[VOICE_SPEED]\n{voice_speed}\n\n")

            f.write("[VOICE_EMOTIONS]\n")
            if voice_emotions:
                for emotion in voice_emotions:
                    f.write(f"{emotion}\n")
            f.write("\n")

            f.write(f"[VOICE_INTENSITY]\n{voice_intensity}\n")

    def create_commentator(self, name: str, personality: str, style: str,
                           examples: list[str], voice_id: str,
                           voice_speed: str = "normal", voice_emotions: list[str] = None,
                           voice_intensity: str = "medium",
                           main_prompt: str = None, second_pass_prompt: str = None) -> bool:
        """Create a new commentator with the given details."""
        dir_name = name.replace(" ", "_")
        commentator_dir = os.path.join(self.base_dir, dir_name)

        if os.path.exists(commentator_dir):
            return False

        os.makedirs(commentator_dir)

        # Create metadata file
        self._create_metadata_file(
            commentator_dir, name, personality, style, examples, voice_id,
            voice_speed, voice_emotions, voice_intensity
        )

        # Create prompt files
        with open(os.path.join(commentator_dir, "prompt.txt"), 'w', encoding='utf-8') as f:
            f.write(main_prompt if main_prompt else "")

        with open(os.path.join(commentator_dir, "second_pass_prompt.txt"), 'w', encoding='utf-8') as f:
            f.write(second_pass_prompt if second_pass_prompt else "")

        return True

    def update_commentator(self, original_name: str, name: str, personality: str,
                           style: str, examples: list[str], voice_id: str,
                           voice_speed: str = "normal", voice_emotions: list[str] = None,
                           voice_intensity: str = "medium",
                           main_prompt: Optional[str] = None,
                           second_pass_prompt: Optional[str] = None) -> bool:
        """Update an existing commentator's details."""
        original_dir = os.path.join(self.base_dir, original_name.replace(" ", "_"))
        if not os.path.exists(original_dir):
            return False

        # If name has changed, rename the directory
        new_dir = os.path.join(self.base_dir, name.replace(" ", "_"))
        if original_dir != new_dir:
            os.rename(original_dir, new_dir)
            current_dir = new_dir
        else:
            current_dir = original_dir

        # Update metadata
        self._create_metadata_file(
            current_dir, name, personality, style, examples, voice_id,
            voice_speed, voice_emotions, voice_intensity
        )

        # Update prompts if provided
        if main_prompt is not None:
            with open(os.path.join(current_dir, "prompt.txt"), 'w', encoding='utf-8') as f:
                f.write(main_prompt)

        if second_pass_prompt is not None:
            with open(os.path.join(current_dir, "second_pass_prompt.txt"), 'w', encoding='utf-8') as f:
                f.write(second_pass_prompt)

        return True

    def delete_commentator(self, name: str) -> bool:
        """Delete a commentator."""
        dir_path = os.path.join(self.base_dir, name.replace(" ", "_"))
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
            return True
        return False

    def get_commentator_metadata(self, name: str) -> Optional[CommentatorMetadata]:
        """Get metadata for a specific commentator."""
        try:
            dir_path = os.path.join(self.base_dir, name.replace(" ", "_"))
            metadata_path = os.path.join(dir_path, "metadata.txt")

            if not os.path.exists(metadata_path):
                return None

            metadata = {
                'name': '',
                'personality': '',
                'style': '',
                'examples': [],
                'voice_id': '',
                'voice_speed': 'normal',
                'voice_emotions': [],
                'voice_intensity': 'medium'
            }

            current_section = None

            with open(metadata_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('[') and line.endswith(']'):
                        current_section = line[1:-1].lower()
                    elif line and current_section:
                        if current_section == 'examples' or current_section == 'voice_emotions':
                            metadata[current_section].append(line)
                        else:
                            metadata[current_section] = line

            # Validate that we have required fields
            if not metadata['name']:
                metadata['name'] = name  # Use directory name as fallback

            return CommentatorMetadata(
                name=metadata['name'],
                personality=metadata['personality'],
                style=metadata['style'],
                examples=metadata['examples'],
                voice_id=metadata['voice_id'],
                voice_speed=metadata['voice_speed'],
                voice_emotions=metadata['voice_emotions'],
                voice_intensity=metadata['voice_intensity']
            )
        except Exception as e:
            print(f"Error loading metadata for {name}: {e}")
            return None

    def get_prompt(self, name: str, second_pass: bool = False) -> Optional[str]:
        """Get the prompt for a commentator."""
        try:
            dir_path = os.path.join(self.base_dir, name.replace(" ", "_"))
            file_name = "second_pass_prompt.txt" if second_pass else "prompt.txt"
            prompt_path = os.path.join(dir_path, file_name)

            if not os.path.exists(prompt_path):
                return None

            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error loading prompt for {name}: {e}")
            return None

    def get_all_commentators(self) -> List[CommentatorMetadata]:
        """Get metadata for all available commentators."""
        commentators = []
        try:
            # Check if directory exists
            if not os.path.exists(self.base_dir):
                self._ensure_base_directory()

            # List directories in the base directory
            for dir_name in os.listdir(self.base_dir):
                dir_path = os.path.join(self.base_dir, dir_name)
                if os.path.isdir(dir_path):
                    metadata = self.get_commentator_metadata(dir_name)
                    if metadata:
                        commentators.append(metadata)

        except Exception as e:
            print(f"Error getting commentators: {e}")

        return commentators