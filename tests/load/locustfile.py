# FILE: backend/tests/load/locustfile.py
from locust import HttpUser, task, between, StopUser  # StopUser directly from locust

class WebsiteUser(HttpUser):
    """
    Simulates a real user: logs in, then performs typical actions.
    """
    wait_time = between(1, 5)

    def on_start(self):
        """Create a test user dynamically (or use a fixed one) and authenticate."""
        # Option 1: Use a fixed test user (ensure it exists in the database)
        self.email = "loadtest@example.com"
        self.password = "password123"

        # Attempt to log in
        response = self.client.post("/api/login/", json={
            "email": self.email,
            "password": self.password
        })

        if response.status_code != 200:
            # If login fails, maybe create the user (for local testing)
            # This is simplified; in production you'd seed the database.
            print(f"Login failed with status {response.status_code}")
            raise StopUser()

        data = response.json()
        # Assume token is returned under 'access' or 'token'
        self.token = data.get('access') or data.get('token')
        self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @task(3)
    def software_list(self):
        with self.client.get("/api/software/", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Software list failed: {response.status_code}")

    @task(2)
    def software_detail(self):
        # Fetch first software ID from list (simplified)
        software_list = self.client.get("/api/software/").json()
        if software_list and software_list.get('results'):
            first_id = software_list['results'][0]['id']
            with self.client.get(f"/api/software/{first_id}/", catch_response=True) as response:
                if response.status_code != 200:
                    response.failure(f"Software detail failed: {response.status_code}")

    @task(1)
    def download_redirect(self):
        # Attempt to hit a download endpoint (if you have one)
        with self.client.get("/api/distribution/file/some-uuid/", catch_response=True) as response:
            if response.status_code not in [200, 302, 404]:
                response.failure(f"Unexpected status: {response.status_code}")