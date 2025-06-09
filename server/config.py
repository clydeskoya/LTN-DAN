# Server Configuration
SERVER_URL = "http://localhost:5000"

# Chatbot UI Configuration
CHATBOT_UI_URL = "http://192.168.1.197:3000"

# Audio Configuration
SAMPLE_RATE = 16000
CHANNELS = 1

# Whisper Model Configuration
WHISPER_MODEL_SIZE = "distil-large-v2"  # Valid model options: tiny.en, tiny, base.en, base, small.en, small, medium.en, medium, large-v1, large-v2, large-v3, large, distil-large-v2, distil-medium.en, distil-small.en
WHISPER_DEVICE = "cuda"  # Options: cpu, cuda
WHISPER_COMPUTE_TYPE = "float16"  # Options: int8, float16, float32