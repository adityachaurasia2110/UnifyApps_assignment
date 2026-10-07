import requests
url = "http://localhost:8000/api/chat"
payload = {"message": "Show all employees.", "thread_id": "123"}
res = requests.post(url, json=payload)
print(res.status_code)
print(res.text)
