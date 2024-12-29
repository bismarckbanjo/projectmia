import json

def load_character(filepath):
    """Load character data from a JSON file."""
    with open(filepath, "r") as file:
        return json.load(file)

def get_active_voice(character_file, selected_voice):
    """
    Determine the active voice based on user selection or default character voice.
    
    Parameters:
    - character_file: Path to the character JSON file.
    - selected_voice: The user-selected voice from the interface.

    Returns:
    - A string representing the active voice.
    """
    character = load_character(character_file)
    return character["voice"] if selected_voice == "Character-select" else selected_voice.lower()