import requests
import os
from dotenv import load_dotenv

load_dotenv()

USER_ID = os.getenv("THREADS_USER_ID")
TOKEN = os.getenv("THREADS_ACCESS_TOKEN")
CONTAINER_ID = "17902396659449576"

r = requests.post(
    f"https://graph.threads.net/v1.0/{USER_ID}/threads_publish",
    params={
        "creation_id": CONTAINER_ID,
        "access_token": TOKEN
    }
)
print(r.json())
