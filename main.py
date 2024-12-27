from openai import OpenAI
import streamlit as st
import sounddevice as sd
import numpy as np
import json
import websocket
import base64

# Set the title of the Streamlit app
st.title("Roleplaying Chatbot with Realtime API")

# Initialize OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Load character sheet
def load_character_sheet(filepath):
    with open(filepath, "r") as file:
        return json.load(file)

character = load_character_sheet("character.json")  # Adjust filepath as needed

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state["messages"] = []

    # Add character introduction as a system message
    st.session_state["messages"].append({
        "role": "system",
        "content": f"{character['role']} Speak like this: {character['traits']}."
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
        print("WebSocket connection established.")
        
        # Construct instructions using character details
        chat_context = "\n".join(
            f"{msg['role'].capitalize()}: {msg['content']}" for msg in st.session_state["messages"]
        )

        instructions = (
            f"You are {character['name']}, {character['description']}\n"
            f"Your role is: {character['role']}\n"
            f"Personality: {character['personality']}\n"
            f"Respond in a way that reflects your speech pattern: {character['speech_pattern']}\n"
            f"Here is the conversation so far:\n{chat_context}\n"
            f"The user just said: '{user_text}'. Respond naturally as {character['name']}."
        )

        start_message = {
            "type": "response.create",
            "response": {
                "modalities": ["audio", "text"],
                "instructions": instructions
            }
        }
        ws.send(json.dumps(start_message))

    def on_message(ws, message):
        # Initialize a buffer for audio
        if not hasattr(on_message, "audio_buffer"):
            on_message.audio_buffer = bytearray()

        # Decode incoming message
        data = json.loads(message)
        if data.get("type") != "response.audio.delta":
            print("Received message:", json.dumps(data, indent=2))  # Debugging output

        if data.get("type") == "response.audio.delta":
            # Handle audio chunks
            if "delta" in data:
                try:
                    # Decode audio delta (base64)
                    audio_data = base64.b64decode(data["delta"])
                    on_message.audio_buffer.extend(audio_data)
                    print(f"Audio chunk received. Buffer length: {len(on_message.audio_buffer)}")
                except Exception as e:
                    print(f"Error processing audio delta: {e}")
        elif data.get("type") == "response.audio.done":
            # Play the complete audio
            try:
                audio_np = np.frombuffer(on_message.audio_buffer, dtype=np.int16)
                print(f"Playing complete audio. Length: {len(audio_np)}")
                sample_rate = data.get("sample_rate", 24000)  # Default to 24,000 Hz if not provided
                play_audio(audio_np, sample_rate=sample_rate)
                on_message.audio_buffer = bytearray()  # Clear the buffer after playback
            except Exception as e:
                print(f"Error playing complete audio: {e}")
        elif data.get("type") == "response.audio_transcript.done":
            # Use the transcription as the chat text
            transcription = data.get("transcript", "")
            print(f"Final transcription: {transcription}")
            st.session_state["messages"].append({"role": "assistant", "content": transcription})
            with st.chat_message("assistant"):
                st.markdown(transcription)
        else:
            print("No relevant message type detected.")

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
