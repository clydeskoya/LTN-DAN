import whisper
import numpy as np
import requests
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from datetime import datetime
import socket
import time

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize Whisper model
print("📝 Loading Whisper model...")
model = whisper.load_model("base")
print("✅ Whisper model loaded!")

# Define Ollama model and host
OLLAMA_MODEL = "qwen2.5:7b"
# Use environment variable for Ollama host if set, or try to auto-detect
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Display startup configuration
print(f"🔧 Configuration:")
print(f"  - Whisper Model: base")
print(f"  - Ollama Model: {OLLAMA_MODEL}")
print(f"  - Ollama Host: {OLLAMA_HOST}")

# Track transcription requests for status endpoint
transcription_history = []

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    # Save the uploaded file temporarily
    temp_path = "temp_upload.wav"
    file.save(temp_path)
    
    try:
        # Transcribe using Whisper
        result = model.transcribe(temp_path)
        text = result["text"].strip()
        print(f"Transcription: {text}")
        
        # Create request record
        request_record = {
            "timestamp": datetime.now().isoformat(),
            "transcription": text,
            "ollama_response": None,
            "status": "processing"
        }
        
        # Send to Ollama if we have text
        if text:
            try:
                print(f"🔄 Sending to Ollama at {OLLAMA_HOST}")
                print(f"📝 Prompt: {text}")
                
                # Basic prompt with no formatting requirements
                ollama_payload = {
                    "model": OLLAMA_MODEL,
                    "prompt": text,
                    "stream": False
                }
                
                # Make the API request to Ollama with verbose logging
                ollama_url = f"{OLLAMA_HOST}/api/generate"
                print(f"🔗 Request URL: {ollama_url}")
                print(f"📦 Request payload: {json.dumps(ollama_payload)}")
                
                # Attempt to connect to Ollama with retries
                max_retries = 3
                retry_delay = 2  # seconds
                
                for attempt in range(max_retries):
                    try:
                        print(f"🔄 Attempt {attempt + 1} of {max_retries}")
                        ollama_response = requests.post(
                            ollama_url,
                            json=ollama_payload,
                            timeout=60
                        )
                        print(f"📊 Response status code: {ollama_response.status_code}")
                        break
                    except requests.exceptions.RequestException as e:
                        print(f"❌ Request failed: {str(e)}")
                        if attempt < max_retries - 1:
                            print(f"⏳ Retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            raise
                
                # Process the response
                if ollama_response.status_code == 200:
                    # Log raw response for debugging
                    print(f"📄 Raw response: {ollama_response.text[:200]}...")
                    
                    # Parse the JSON response
                    try:
                        ollama_result = ollama_response.json()
                        response_text = ollama_result.get("response", "")
                        print(f"💬 Response text: {response_text[:100]}...")
                        
                        # Update request record
                        request_record["ollama_response"] = response_text
                        request_record["status"] = "completed"
                        
                        # Add to history (limit to last 10 entries)
                        transcription_history.append(request_record)
                        if len(transcription_history) > 10:
                            transcription_history.pop(0)
                        
                        return jsonify({
                            "text": text,
                            "response": response_text
                        })
                    except json.JSONDecodeError as je:
                        print(f"❌ JSON decode error: {je}")
                        print(f"📄 Response that couldn't be parsed: {ollama_response.text[:200]}...")
                        
                        # Update request record
                        request_record["status"] = "error"
                        request_record["error"] = f"Failed to parse Ollama response: {str(je)}"
                        transcription_history.append(request_record)
                        
                        return jsonify({
                            "text": text,
                            "error": f"Failed to parse Ollama response: {str(je)}"
                        })
                else:
                    error_msg = f"Ollama error: {ollama_response.status_code}"
                    print(f"❌ {error_msg}")
                    try:
                        print(f"📄 Error response: {ollama_response.text}")
                    except:
                        pass
                    
                    # Update request record
                    request_record["status"] = "error"
                    request_record["error"] = error_msg
                    transcription_history.append(request_record)
                    
                    return jsonify({
                        "text": text,
                        "error": error_msg
                    })
                    
            except Exception as e:
                error_msg = f"Failed to get response from Ollama: {str(e)}"
                print(f"❌ {error_msg}")
                
                # Update request record
                request_record["status"] = "error"
                request_record["error"] = error_msg
                transcription_history.append(request_record)
                
                return jsonify({
                    "text": text,
                    "error": error_msg
                })
        
        # Add to history for cases where we had no text
        if not text:
            request_record["status"] = "completed_no_text"
            transcription_history.append(request_record)
            
        return jsonify({"text": text})
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error during transcription: {error_msg}")
        
        # Record the error in history
        transcription_history.append({
            "timestamp": datetime.now().isoformat(),
            "status": "error",
            "error": error_msg
        })
        return jsonify({'error': error_msg}), 500
        
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.route('/status', methods=['GET'])
def get_status():
    # Check connection to Ollama service
    ollama_status = "unknown"
    models_found = []
    
    try:
        ollama_url = f"{OLLAMA_HOST}/api/tags"
        print(f"🔍 Checking Ollama status at: {ollama_url}")
        
        response = requests.get(ollama_url, timeout=5)
        print(f"📊 Ollama status response code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                models = data.get("models", [])
                for model in models:
                    models_found.append(model.get("name"))
                
                if models_found:
                    ollama_status = f"connected (models: {', '.join(models_found)})"
                else:
                    ollama_status = "connected (no models found)"
            except json.JSONDecodeError:
                ollama_status = "connected (invalid response format)"
        else:
            ollama_status = f"error: status code {response.status_code}"
    except Exception as e:
        ollama_status = f"error: {str(e)}"
        print(f"❌ Error checking Ollama status: {str(e)}")
    
    # Return enhanced status information
    status_response = {
        "status": "running",
        "whisper_model": "base",
        "ollama_model": OLLAMA_MODEL,
        "ollama_host": OLLAMA_HOST,
        "ollama_connection": ollama_status,
        "ollama_models": models_found,
        "recent_requests": transcription_history,
        "server_time": datetime.now().isoformat()
    }
    
    return jsonify(status_response)

@app.route('/test_ollama', methods=['GET'])
def test_ollama():
    """Test endpoint that attempts to connect to Ollama"""
    try:
        # Try both APIs to see which works
        apis_to_try = [
            {"name": "tags API", "url": f"{OLLAMA_HOST}/api/tags", "method": "get"},
            {"name": "generate API", "url": f"{OLLAMA_HOST}/api/generate", "method": "post", "payload": {"model": OLLAMA_MODEL, "prompt": "hello", "stream": False}}
        ]
        
        results = []
        for api in apis_to_try:
            try:
                print(f"🧪 Testing {api['name']} at {api['url']}")
                
                if api["method"] == "get":
                    response = requests.get(api["url"], timeout=5)
                else:
                    response = requests.post(api["url"], json=api.get("payload", {}), timeout=10)
                
                print(f"📊 {api['name']} response code: {response.status_code}")
                
                result = {
                    "api": api["name"],
                    "url": api["url"],
                    "status_code": response.status_code,
                    "success": response.status_code == 200
                }
                
                # Try to parse response as JSON
                try:
                    result["response"] = response.json()
                except:
                    result["response"] = response.text[:200] + "..." if len(response.text) > 200 else response.text
                
                results.append(result)
                
            except Exception as e:
                print(f"❌ Error testing {api['name']}: {str(e)}")
                results.append({
                    "api": api["name"],
                    "url": api["url"],
                    "error": str(e),
                    "success": False
                })
        
        return jsonify({
            "ollama_host": OLLAMA_HOST,
            "test_results": results,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "ollama_host": OLLAMA_HOST,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    # Print startup banner
    print("\n" + "="*50)
    print("🚀 Speech-to-Text Server Starting")
    print("="*50)
    
    print("\n📡 Testing Ollama connection on startup")
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if response.status_code == 200:
            print(f"✅ Successfully connected to Ollama at {OLLAMA_HOST}")
            try:
                models = response.json().get("models", [])
                if models:
                    print(f"📚 Available models: {', '.join([model.get('name') for model in models])}")
                else:
                    print(f"⚠️ No models found in Ollama")
            except:
                print(f"⚠️ Could not parse models from Ollama response")
        else:
            print(f"⚠️ Ollama responded with status code {response.status_code}")
    except Exception as e:
        print(f"❌ Failed to connect to Ollama: {str(e)}")
        print(f"ℹ️ Make sure Ollama is running at {OLLAMA_HOST}")
        print(f"⚠️ The server will start anyway, but transcription might not work")
    
    print("\n💡 Debugging tips:")
    print("  - Set OLLAMA_HOST environment variable to override the Ollama API URL")
    print("  - Check the /status endpoint for detailed system status")
    print("  - Use the /test_ollama endpoint to debug Ollama connectivity")
    print("\n" + "="*50)
    
    app.run(host='0.0.0.0', port=5000, debug=True) 