import requests
import os
from dotenv import load_dotenv

load_dotenv()

USER_ID = os.getenv("THREADS_USER_ID")
TOKEN = os.getenv("THREADS_ACCESS_TOKEN")

r = requests.post(
    f"https://graph.threads.net/v1.0/{USER_ID}/threads",
    params={
        "media_type": "TEXT",
        "text": "API 테스트 포스팅입니다",
        "access_token": TOKEN
    }
)
print(r.json())
