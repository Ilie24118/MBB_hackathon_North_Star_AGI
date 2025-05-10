import os

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure the API key (replace with your actual key or use environment variables)

### GO TO https://aistudio.google.com/apikey AND GRAB YOURS!
api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    print("Error: GOOGLE_API_KEY environment variable not set.")
    exit()

genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-2.0-flash")

"""
prompt = "I want a pub witch a cozy    We have this pub in Antwerp: Blauwmoezel give me a short summary of it and the vibe. Give the in 5 bullets points the vibe. Only the name."

response = model.generate_content(prompt)

print(f"Prompt: {prompt}\n")
print(f"Response: {response.text}")

"""
