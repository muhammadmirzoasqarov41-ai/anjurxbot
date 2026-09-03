import os


_REQUIRED_ENV = {
    "BOT_TOKEN": "test-token",
    "ADMIN_IDS": "123",
    "FIREBASE_PROJECT_ID": "test-project",
    "FIREBASE_PRIVATE_KEY_ID": "test-key-id",
    "FIREBASE_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\\ntest\\n-----END PRIVATE KEY-----\\n",
    "FIREBASE_CLIENT_EMAIL": "test@example.invalid",
    "FIREBASE_CLIENT_ID": "123",
    "FIREBASE_CLIENT_X509_CERT_URL": "https://example.invalid/cert",
}

for key, value in _REQUIRED_ENV.items():
    os.environ.setdefault(key, value)
