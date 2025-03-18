import os
import shutil
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class CommentatorMetadata:
    name: str
    personality: str
    style: str
    examples: list[str]
    voice_id: str


class CommentatorManager:
    def __init__(self):
        self.base_dir = "Commentators"
        self._ensure_base_directory()
        self._ensure_default_commentator()

    def _ensure_base_directory(self):
        """Create the base Commentators directory if it doesn't exist."""
        os.makedirs(self.base_dir, exist_ok=True)

    def _ensure_default_commentator(self):
        """Set up the default Geoff commentator if it doesn't exist."""
        geoff_dir = os.path.join(self.base_dir, "Geoff")
        if not os.path.exists(geoff_dir):
            os.makedirs(geoff_dir)

            # Copy existing prompt files
            source_files = {
                "race_commentator_prompt.txt": "prompt.txt",
                "second_commentator.txt": "second_pass_prompt.txt"
            }

            for source, dest in source_files.items():
                if os.path.exists(source):
                    shutil.copy2(source, os.path.join(geoff_dir, dest))

            # Create metadata file
            self._create_metadata_file(
                geoff_dir,
                "Geoff",
                "Overly enthusiastic and awkward racing commentator",
                "Comedic with technical knowledge",
                [
                    "OH MY GOODNESS folks, look at that perfectly executed apex entry!",
                    "You know what I always say about downforce - if you're not forcing down, you're forcing up.",
                    "I feel God in this paddock tonight."
                ],
                "Mw9TampTt4PGYMa0FYBO"  # Default voice ID
            )
        else:
            # Ensure the metadata file exists even if the directory already exists
            metadata_path = os.path.join(geoff_dir, "metadata.txt")
            if not os.path.exists(metadata_path):
                self._create_metadata_file(
                    geoff_dir,
                    "Geoff",
                    "Overly enthusiastic and awkward racing commentator",
                    "Comedic with technical knowledge",
                    [
                        "OH MY GOODNESS folks, look at that perfectly executed apex entry!",
                        "You know what I always say about downforce - if you're not forcing down, you're forcing up.",
                        "I feel God in this paddock tonight."
                    ],
                    "Mw9TampTt4PGYMa0FYBO"  # Default voice ID
                )

    def _create_metadata_file(self, commentator_dir: str, name: str, personality: str,
                              style: str, examples: list[str], voice_id: str):
        """Create a metadata file for a commentator."""
        metadata_path = os.path.join(commentator_dir, "metadata.txt")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            f.write(f"[NAME]\n{name}\n\n")
            f.write(f"[PERSONALITY]\n{personality}\n\n")
            f.write(f"[STYLE]\n{style}\n\n")
            f.write("[EXAMPLES]\n")
            for example in examples:
                f.write(f"{example}\n")
            f.write(f"\n[VOICE_ID]\n{voice_id}\n")

    def create_commentator(self, name: str, personality: str, style: str,
                           examples: list[str], voice_id: str,
                           main_prompt: str, second_pass_prompt: str) -> bool:
        """Create a new commentator with the given details."""
        dir_name = name.replace(" ", "_")
        commentator_dir = os.path.join(self.base_dir, dir_name)

        if os.path.exists(commentator_dir):
            return False

        os.makedirs(commentator_dir)

        # Create metadata file
        self._create_metadata_file(commentator_dir, name, personality, style, examples, voice_id)

        # Create prompt files
        with open(os.path.join(commentator_dir, "prompt.txt"), 'w', encoding='utf-8') as f:
            f.write(main_prompt)

        with open(os.path.join(commentator_dir, "second_pass_prompt.txt"), 'w', encoding='utf-8') as f:
            f.write(second_pass_prompt)

        return True

    def update_commentator(self, original_name: str, name: str, personality: str,
                           style: str, examples: list[str], voice_id: str,
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
        self._create_metadata_file(current_dir, name, personality, style, examples, voice_id)

        # Update prompts if provided
        if main_prompt is not None:
            with open(os.path.join(current_dir, "prompt.txt"), 'w', encoding='utf-8') as f:
                f.write(main_prompt)

        if second_pass_prompt is not None:
            with open(os.path.join(current_dir, "second_pass_prompt.txt"), 'w', encoding='utf-8') as f:
                f.write(second_pass_prompt)

        return True

    def delete_commentator(self, name: str) -> bool:
        """Delete a commentator. Cannot delete the default Geoff commentator."""
        if name.lower() == "geoff":
            return False

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
                'voice_id': ''
            }

            current_section = None

            with open(metadata_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('[') and line.endswith(']'):
                        current_section = line[1:-1].lower()
                    elif line and current_section:
                        if current_section == 'examples':
                            metadata['examples'].append(line)
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
                voice_id=metadata['voice_id']
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
                self._ensure_default_commentator()

            # List directories in the base directory
            for dir_name in os.listdir(self.base_dir):
                dir_path = os.path.join(self.base_dir, dir_name)
                if os.path.isdir(dir_path):
                    metadata = self.get_commentator_metadata(dir_name)
                    if metadata:
                        commentators.append(metadata)

            # If no commentators found, create and add default
            if not commentators:
                self._ensure_default_commentator()
                geoff_metadata = self.get_commentator_metadata("Geoff")
                if geoff_metadata:
                    commentators.append(geoff_metadata)
        except Exception as e:
            print(f"Error getting commentators: {e}")
            # Always ensure we have at least a default commentator
            geoff = CommentatorMetadata(
                name="Geoff",
                personality="Overly enthusiastic and awkward racing commentator",
                style="Comedic with technical knowledge",
                examples=[
                    "OH MY GOODNESS folks, look at that perfectly executed apex entry!",
                    "You know what I always say about downforce - if you're not forcing down, you're forcing up.",
                    "I feel God in this paddock tonight."
                ],
                voice_id="Mw9TampTt4PGYMa0FYBO"
            )
            commentators.append(geoff)

        return commentators