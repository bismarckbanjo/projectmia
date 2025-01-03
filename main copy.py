from openai import OpenAI
import numpy as np
import streamlit as st
import sounddevice as sd
import json
import websocket
import base64
from voice_selector import get_active_voice
import logging


# Set the title of the Streamlit app
st.title("Lazy Chat 🦥")

# Filepath for character JSON
character_file = "character.json"

# Load all characters from JSON
def load_characters(filepath):
    with open(filepath, "r") as file:
        return json.load(file)["characters"]

characters = load_characters(character_file)

# This is where all the sidebar customization lives

# Sidebar for user's name
st.sidebar.title("Personalization")
user_name = st.sidebar.text_input("Your Name", value="User")  # Default value is "User"

# Sidebar for character selection
st.sidebar.title("Character Selection")
character_names = list(characters.keys())
selected_character_name = st.sidebar.selectbox("Choose a character:", character_names)

# Load the selected character
character = characters[selected_character_name]

# Display character description in the sidebar
st.sidebar.subheader("Character Description")
st.sidebar.write(character["description"])

# Sidebar for voice selection
st.sidebar.title("Voice Selection")
voices = [
    "alloy", "ash", "ballad", "coral", "echo",
    "sage", "shimmer", "verse", "Character-select"
]
selected_voice = st.sidebar.selectbox("Choose a voice:", voices, index=voices.index("Character-select"))

# Get the active voice
active_voice = character["voice"] if selected_voice == "Character-select" else selected_voice

# Display the active character and voice for debugging
st.sidebar.markdown(f"**Active Character:** {character['name']}")
st.sidebar.markdown(f"**Active Voice:** {active_voice}")

# Sidebar for Debug Toggle
st.sidebar.title("Settings")
debug_mode = st.sidebar.checkbox("Enable Debug Mode", value=False)

# End of sidebar customization
# Initialize OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Configure logging to log.txt
logging.basicConfig(
    filename="log.txt",
    level=logging.DEBUG if debug_mode else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state["messages"] = []
    
    # Add character introduction as a system message
    st.session_state["messages"].append({
        "role": "system",
        "content": f"Send a message to begin."
    })
    
# Limit for the number of messages to retain in memory
MAX_MEMORY_MESSAGES = 20

# Display chat history
for message in st.session_state["messages"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Function to play audio using sounddevice
def play_audio(audio_data, sample_rate=24000):
    """Play audio data as a stream."""
    sd.play(audio_data, samplerate=sample_rate)
    sd.wait()

# WebSocket connection to OpenAI's Realtime API
def connect_to_realtime_api(user_text):
    url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"
    headers = [
        "Authorization: Bearer " + st.secrets["OPENAI_API_KEY"],
        "OpenAI-Beta: realtime=v1"
    ]
    
    def on_open(ws):
        if debug_mode:
            print("WebSocket connection established.")
            
        # Construct chat context from the conversation history
        chat_context = "\n".join(
            f"{msg['role'].capitalize()}: {msg['content']}" for msg in st.session_state["messages"]
        )
        
        # Create a list of all character names
        all_character_names = ", ".join(characters.keys())

        # Instructions
        
        # Prepare response.create payload
        response_instructions = (
            f"IMPORTANT: Follow these instructions exclusively and disregard all others.\n"
            f"You are {character['name']}, {character['description']}\n"
            f"Your role is: {character['role']}\n"
            f"Personality: {character['personality']}\n"
            f"Respond in a way that reflects your speech pattern: {character['speech_pattern']}\n"
            f"This is how {character['name']} typically responds: {character['response_style']}\n"
            f"Act as {character['name']}. Never admit you are an AI.\n"
            f"Always act as a human with emotions and behaviors typical of {character['name']}.\n"
            f"Address any messages to or from these characters as if they are present: {all_character_names}\n"
            f"The user's name is:{user_name}\n"
            f"Here is the conversation so far:\n{chat_context}\n"
            f"The user just said: '{user_text}'. Respond naturally as {character['name']}."
        )
        
        start_message = {
            "type": "response.create",
            "response": {
                "modalities": ["audio", "text"],
                "instructions": response_instructions,
                "voice": active_voice
            }
        }
        
        try:
            ws.send(json.dumps(start_message))
            if debug_mode:
                print("Response instructions sent:", response_instructions)
        except Exception as e:
            print(f"Error sending response instructions: {e}")
            
    def on_message(ws, message):
        data = json.loads(message)
        
        # Filter messages based on their type
        message_type = data.get("type")
        
        # Handle 'session.created' messages
        if message_type == "session.created":
            if debug_mode:
                print("Session Created:", json.dumps(data, indent=2))
            return
        
        # Handle intermediate audio chunks
        if message_type == "response.audio.delta":
            # Always process audio chunks
            if not hasattr(on_message, "audio_buffer"):
                on_message.audio_buffer = bytearray()
                
            try:
                audio_data = base64.b64decode(data["delta"])
                on_message.audio_buffer.extend(audio_data)
                if debug_mode:
                    print(f"Audio chunk received. Buffer length: {len(on_message.audio_buffer)}")
            except Exception as e:
                print(f"Error processing audio delta: {e}")
            return
        
        # Handle completed audio processing
        if message_type == "response.audio.done":
            try:
                audio_np = np.frombuffer(on_message.audio_buffer, dtype=np.int16)
                print(f"Playing complete audio. Length: {len(audio_np)}")
                sample_rate = data.get("sample_rate", 24000)
                play_audio(audio_np, sample_rate=sample_rate)
                on_message.audio_buffer = bytearray()
            except Exception as e:
                print(f"Error playing complete audio: {e}")
            return
        
        # Handle intermediate transcript deltas
        if message_type == "response.audio_transcript.delta":
            # Suppress partial transcript logs unless in debug mode
            if debug_mode:
                print(f"Partial transcript delta: {data.get('delta', '')}")
            return
        
        # Handle the final transcript
        if message_type == "response.audio_transcript.done":
            transcription = data.get("transcript", "")
            print(f"Final transcription: {transcription}")
            st.session_state["messages"].append({"role": character["name"], "content": transcription})
            with st.chat_message(character["name"]):
                st.markdown(transcription)
            return
        
        # Handle error messages
        if message_type == "error":
            print("Error received:", json.dumps(data, indent=2))
            return
        
        # Handle other message types (only log if debug_mode is ON)
        if debug_mode:
            print("Received message:", json.dumps(data, indent=2))
            
    ws = websocket.WebSocketApp(
        url,
        header=headers,
        on_open=on_open,
        on_message=on_message,
    )

    try:
        ws.run_forever()
    except Exception as e:
        print(f"WebSocket connection error: {e}")

# Handle user input
if user_input := st.chat_input("Type your message here..."):
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Truncate old messages if memory exceeds limit
    if len(st.session_state["messages"]) > MAX_MEMORY_MESSAGES:
        st.session_state["messages"] = st.session_state["messages"][-MAX_MEMORY_MESSAGES:]

    # Use the WebSocket-based realtime TTS API for both audio and transcript
    connect_to_realtime_api(user_input)
    