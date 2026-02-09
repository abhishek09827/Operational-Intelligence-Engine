from locust import HttpUser, task, between
import json

class OpsPilotUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def analyze_logs(self):
        headers = {'Content-Type': 'application/json'}
        payload = {
            "logs": "[2024-05-21 10:15:32,456] ERROR [app.db.session] Database connection failed: FATAL: password authentication failed"
        }
        self.client.post("/api/v1/incident/analyze", data=json.dumps(payload), headers=headers)

