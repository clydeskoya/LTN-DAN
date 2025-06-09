import requests
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import time
import os
import threading
import queue
from datetime import datetime
from flask import Flask, jsonify, request
import webbrowser

# Replace with your server's IP address if not running locally
SERVER_URL = "http://localhost:5000"
# Replace with your chatbot UI's endpoint
CHATBOT_UI_URL = "http://192.168.1.197:3000"  # Update this to your chatbot UI's URL
SAMPLE_RATE = 16000
CHANNELS = 1

# Global variables for recording control
is_recording = False
audio_queue = queue.Queue()
recording_thread = None
recording_start_time = None

# Flask app for remote control
app = Flask(__name__)

def send_to_chatbot(text, response):
    """Send transcription and response to the chatbot UI."""
    try:
        data = {
            "transcription": text,
            "response": response
        }
        requests.post(f"{CHATBOT_UI_URL}/api/transcription", json=data)
        print("📤 Sent to chatbot UI")
    except Exception as e:
        print(f"❌ Error sending to chatbot UI: {str(e)}")

def record_audio():
    """Record audio continuously and put chunks in the queue."""
    global is_recording, recording_start_time
    recording_start_time = datetime.now()
    print("\n🎤 Recording started at:", recording_start_time.strftime("%H:%M:%S"))
    
    while is_recording:
        # Record a chunk of audio
        audio_data = sd.rec(
            int(1 * SAMPLE_RATE),  # 1 second chunks
            samplerate=SAMPLE_RATE,
            channels=CHANNELS
        )
        sd.wait()
        audio_queue.put(audio_data)
        
        # Show recording duration
        duration = (datetime.now() - recording_start_time).seconds
        print(f"\r⏱️ Recording duration: {duration} seconds", end="", flush=True)

def start_recording():
    """Start the recording thread."""
    global is_recording, recording_thread
    if not is_recording:
        is_recording = True
        recording_thread = threading.Thread(target=record_audio)
        recording_thread.start()
        print("\n✅ Recording started...")
        print("📝 Speak now. Press 2 to stop recording.")
        return True
    return False

def stop_recording():
    """Stop recording and process the audio."""
    global is_recording, recording_thread, recording_start_time
    if is_recording:
        is_recording = False
        if recording_thread:
            recording_thread.join()
        
        duration = (datetime.now() - recording_start_time).seconds
        print(f"\n\n⏱️ Total recording time: {duration} seconds")
        print("🔄 Processing audio...")
        
        # Combine all audio chunks
        print("📦 Combining audio chunks...")
        audio_chunks = []
        while not audio_queue.empty():
            audio_chunks.append(audio_queue.get())
        
        if audio_chunks:
            print("🎵 Saving audio file...")
            # Combine all chunks into one array
            audio_data = np.concatenate(audio_chunks)
            
            # Save to temporary file
            filename = "temp_recording.wav"
            wav.write(filename, SAMPLE_RATE, audio_data)
            
            # Send to server
            print("📡 Sending to server for transcription...")
            try:
                with open(filename, 'rb') as f:
                    files = {'file': f}
                    response = requests.post(f"{SERVER_URL}/transcribe", files=files)
                result = response.json()
                
                # Get transcription and response
                transcription = result.get('text', '')
                ollama_response = result.get('response', '')
                
                # Display results
                print("\n📝 Transcription:")
                print("-----------------")
                print(transcription)
                print("\n🤖 Ollama Response:")
                print("-----------------")
                print(ollama_response)
                
                # Send to chatbot UI
                send_to_chatbot(transcription, ollama_response)
                
            except Exception as e:
                print(f"❌ Error sending audio to server: {str(e)}")
            finally:
                # Clean up temporary file
                if os.path.exists(filename):
                    os.remove(filename)
        
        print("\n✅ Recording stopped.")
        return True
    return False

def check_server_status():
    """Check and display server status."""
    print("\n🔍 Checking server status...")
    try:
        response = requests.get(f"{SERVER_URL}/status")
        status = response.json()
        print("\n📊 Server Status:")
        print("----------------")
        print(f"Status: {status.get('status', 'unknown')}")
        print(f"Whisper Model: {status.get('whisper_model', 'unknown')}")
        print(f"Ollama Model: {status.get('ollama_model', 'unknown')}")
    except Exception as e:
        print(f"❌ Error connecting to server: {str(e)}")

# Flask routes for remote control
@app.route('/start', methods=['POST'])
def api_start_recording():
    if start_recording():
        return jsonify({"status": "success", "message": "Recording started"})
    return jsonify({"status": "error", "message": "Already recording"})

@app.route('/stop', methods=['POST'])
def api_stop_recording():
    if stop_recording():
        return jsonify({"status": "success", "message": "Recording stopped"})
    return jsonify({"status": "error", "message": "No active recording"})

@app.route('/status', methods=['GET'])
def api_get_status():
    return jsonify({
        "is_recording": is_recording,
        "duration": (datetime.now() - recording_start_time).seconds if is_recording else 0
    })

def run_flask_server():
    """Run the Flask server in a separate thread."""
    app.run(host='0.0.0.0', port=5001)

def main():
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask_server)
    flask_thread.daemon = True
    flask_thread.start()
    
    print("\n🎙️ Speech to Text Client")
    print("=====================")
    print("Commands:")
    print("  1: Start recording")
    print("  2: Stop recording and process")
    print("  3: Check server status")
    print("  q: Quit")
    print("=====================")
    print("\n📡 Remote Control API running on http://localhost:5001")
    print("Endpoints:")
    print("  POST /start - Start recording")
    print("  POST /stop  - Stop recording")
    print("  GET  /status - Get recording status")
    print("=====================")
    print(f"\n🤖 Chatbot UI URL: {CHATBOT_UI_URL}")
    print("=====================")
    
    while True:
        command = input("\nEnter command: ").strip().lower()
        
        if command == '1':
            if start_recording():
                print("🎤 Recording... Press 2 to stop")
            else:
                print("⚠️ Already recording!")
                
        elif command == '2':
            if stop_recording():
                print("🔄 Processing complete!")
            else:
                print("⚠️ No active recording to stop!")
            
        elif command == '3':
            check_server_status()
            
        elif command == 'q':
            if is_recording:
                stop_recording()
            print("\n👋 Exiting...")
            break
            
        else:
            print("❌ Invalid command!")

if __name__ == "__main__":
    main()

 