import os

# Provide minimal env vars so Settings can be instantiated during test collection.
# These values are never used to make real API calls — all tests mock at the
# client/embed model boundary.
os.environ.setdefault("GITHUB_TOKEN", "test-github-token")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
