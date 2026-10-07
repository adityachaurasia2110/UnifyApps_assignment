import requests
import os
api_key = os.environ.get("GOOGLE_API_KEY")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
res = requests.get(url)
models = res.json().get('models', [])
for m in models:
    if "flash" in m['name'].lower():
        print(m['name'])
