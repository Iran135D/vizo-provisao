import requests

url = "http://localhost:5000/api/auth/login"
data = {"username": "Iran Lima", "password": "123456"}

try:
    response = requests.post(url, json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
