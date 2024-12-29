import json
import base64
import numpy as np
from typing import Callable

def handle_audio_chunk(audio_buffer, delta):
    """Handles audio chunks by decoding and appending to the buffer."""
    try:
        audio_data = base64.b64decode(delta)
        audio_buffer.extend(audio_data)
        print(f"Audio chunk received. Buffer length: {len(audio_buffer)}")
    except Exception as e:
        print(f"Error processing audio delta: {e}")

def handle_audio_complete(audio_buffer, play_audio_func, sample_rate=24000):
    """Handles the completion of audio and plays it."""
    try:
        audio_np = np.frombuffer(audio_buffer, dtype=np.int16)
        logging.debug(f"Playing complete audio. Length: {len(audio_np)}")
        play_audio_func(audio_np, sample_rate=sample_rate)
        audio_buffer.clear()  # Clear the buffer
        logging.debug("Audio buffer cleared after playback.")
    except Exception as e:
        logging.error(f"Error playing complete audio: {e}")
        
def handle_transcription(data, session_messages):
    """Handles the transcription response and updates session messages."""
    transcription = data.get("transcript", "")
    logging.debug(f"Received transcription: {transcription}")
    
    # Append transcription to session messages
    session_messages.append({"role": "assistant", "content": transcription})
    logging.debug(f"Session messages updated: {session_messages}")
    
    # Return transcription for display in the chat
    return transcription

def on_message(ws, message, session_messages, play_audio_func: Callable):
    """Handles WebSocket messages."""
    # Initialize a buffer for audio if not already present
    if not hasattr(on_message, "audio_buffer"):
        on_message.audio_buffer = bytearray()

    # Decode incoming message
    data = json.loads(message)
    if data.get("type") != "response.audio.delta":
        print("Received message:", json.dumps(data, indent=2))  # Debugging output

    if data.get("type") == "response.audio.delta" and "delta" in data:
        handle_audio_chunk(on_message.audio_buffer, data["delta"])
    elif data.get("type") == "response.audio.done":
        handle_audio_complete(on_message.audio_buffer, play_audio_func, sample_rate=data.get("sample_rate", 24000))
    elif data.get("type") == "response.audio_transcript.done":
        transcription = handle_transcription(data, session_messages)
        with st.chat_message("assistant"):  # Display transcription immediately
            st.markdown(transcription)
        
    else:
        print("No relevant message type detected.")
        