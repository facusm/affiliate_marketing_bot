import os
import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.getenv("ELEVENLABS_API_KEY")

response = httpx.get(
    "https://api.elevenlabs.io/v1/voices",
    headers={"xi-api-key": API_KEY or ""}
)
response.raise_for_status()

voices = response.json()["voices"]
premade = [v for v in voices if v.get("category") == "premade"]

print(f"--- Voces premade ({len(premade)} encontradas) ---\n")
for v in premade:
    print(f"  {v['name']:<25} {v['voice_id']}")
