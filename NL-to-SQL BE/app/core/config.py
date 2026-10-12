import os
from dotenv import load_dotenv


load_dotenv()


GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)


APP_NAME = "AI Data Assistant"


MAX_UPLOAD_SIZE = 200  # MB


MAX_RESULT_ROWS = 1000