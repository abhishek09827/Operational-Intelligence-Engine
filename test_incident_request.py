import requests
import json
import sys

# The sample logs provided by the user
logs = """2026-02-07T10:12:11.342Z INFO  [user-service] Starting request processing request_id=abc123
2026-02-07T10:12:12.019Z ERROR [user-service] Failed to acquire connection from poolorg.postgresql.util.PSQLException: FATAL: sorry, too many clients already
    at org.postgresql.core.v3.ConnectionFactoryImpl.openConnectionImpl(ConnectionFactoryImpl.java:292)"""

url = "http://localhost:8000/api/v1/incident/analyze"
payload = {"logs": logs}
headers = {"Content-Type": "application/json"}

try:
    print(f"Sending request to {url}...")
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        print("\n--- ANALYSIS RESULT ---\n")
        print(f"Status: {result.get('status')}")
        print(f"Root Cause:\n{result.get('root_cause')}")
        print(f"\nID: {result.get('id')}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"Request failed: {e}")
