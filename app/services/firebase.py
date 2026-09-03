"""
Firebase Firestore service layer.

Wraps the firebase-admin SDK so the rest of the application never touches
the SDK directly. All Firestore operations live here and can be extended
incrementally as new features are added.

Planned public methods (stubs marked with TODO):
  Groups   : get_group, create_group, update_group, delete_group
  Users    : get_user, create_user, update_user
  Settings : get_settings, update_settings
"""

from __future__ import annotations

import inspect
from typing import Any, Optional

import firebase_admin
from firebase_admin import credentials
from google.cloud.firestore_v1 import AsyncClient  # type: ignore[import]

from app.config import settings
from app.utils.logger import logger


class FirebaseService:
    """
    Singleton-style service that manages the Firestore connection and exposes
    high-level CRUD helpers for every domain entity.

    Instantiate once at startup (done in ``app/bot.py``) and share the
    reference via dependency injection or module-level import.
    """

    def __init__(self) -> None:
        self._app: Optional[firebase_admin.App] = None
        self._db: Optional[Any] = None  # google.cloud.firestore.AsyncClient

    # ------------------------------------------------------------------ #
    # Initialisation / teardown
    # ------------------------------------------------------------------ #

    def initialize(self) -> None:
        """
        Authenticate with Firebase and open the Firestore connection.

        Reads credentials exclusively from *settings* (no JSON file on disk
        required in production). The private key is stored as a raw string in
        the environment variable; literal ``\\n`` sequences are replaced with
        real newline characters so the PEM block is valid.

        Raises:
            RuntimeError: If Firebase initialisation fails for any reason.
        """
        if self._app is not None:
            logger.warning("FirebaseService.initialize() called more than once — skipping.")
            return

        try:
            private_key = settings.firebase_private_key.replace("\\n", "\n")

            service_account_info: dict[str, Any] = {
                "type": "service_account",
                "project_id": settings.firebase_project_id,
                "private_key_id": settings.firebase_private_key_id,
                "private_key": private_key,
                "client_email": settings.firebase_client_email,
                "client_id": settings.firebase_client_id,
                "auth_uri": settings.firebase_auth_uri,
                "token_uri": settings.firebase_token_uri,
                "auth_provider_x509_cert_url": settings.firebase_auth_provider_cert_url,
                "client_x509_cert_url": settings.firebase_client_cert_url,
            }

            cred = credentials.Certificate(service_account_info)
            self._app = firebase_admin.initialize_app(cred)
            # All repository services are async; use the native async client.
            self._db = AsyncClient(
                project=settings.firebase_project_id,
                credentials=cred.get_credential(),
            )

            logger.info("Firebase connected successfully. Project: %s", settings.firebase_project_id)

        except Exception as exc:
            logger.error("Firebase initialisation failed: %s", exc)
            raise RuntimeError(f"Firebase initialisation failed: {exc}") from exc

    async def close(self) -> None:
        """Close the Firestore transport and delete the Firebase app."""
        if self._app is not None:
            if self._db is not None:
                result = self._db.close()
                if inspect.isawaitable(result):
                    await result
            firebase_admin.delete_app(self._app)
            self._app = None
            self._db = None
            logger.info("Firebase connection closed.")

    @property
    def db(self) -> Any:
        """
        Return the raw Firestore client.

        Raises:
            RuntimeError: If :meth:`initialize` has not been called yet.
        """
        if self._db is None:
            raise RuntimeError(
                "FirebaseService is not initialised. Call initialize() first."
            )
        return self._db

    # ------------------------------------------------------------------ #
    # Groups
    # ------------------------------------------------------------------ #

    async def get_group(self, group_id: int) -> Optional[dict[str, Any]]:
        """Fetch a group document by its Telegram chat ID."""
        doc = await self.db.collection("groups").document(str(group_id)).get()
        return doc.to_dict() if doc.exists else None

    async def create_group(self, group_id: int, data: dict[str, Any]) -> None:
        """Create a new group document. Raises if the document already exists."""
        ref = self.db.collection("groups").document(str(group_id))
        await ref.set(data)
        logger.info("Group %s created in Firestore.", group_id)

    async def update_group(self, group_id: int, data: dict[str, Any]) -> None:
        """Merge *data* into an existing group document."""
        ref = self.db.collection("groups").document(str(group_id))
        flattened: dict[str, Any] = {}

        def flatten(value: dict[str, Any], prefix: str = "") -> None:
            for key, item in value.items():
                path = f"{prefix}.{key}" if prefix else key
                if isinstance(item, dict) and item:
                    flatten(item, path)
                else:
                    flattened[path] = item

        flatten(data)
        await ref.set(flattened, merge=True)
        logger.info("Group %s updated in Firestore.", group_id)

    async def delete_group(self, group_id: int) -> None:
        """Delete a group document permanently."""
        await self.db.collection("groups").document(str(group_id)).delete()
        logger.info("Group %s deleted from Firestore.", group_id)

    async def list_groups(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        Return up to *limit* group documents from Firestore.

        Each dict includes an '_id' key with the document ID string.
        """
        results: list[dict[str, Any]] = []
        try:
            async for doc in self.db.collection("groups").limit(limit).stream():
                data = doc.to_dict()
                if data:
                    data["_id"] = doc.id
                    results.append(data)
        except Exception as exc:
            logger.error("Failed to list groups: %s", exc)
        return results

    # ------------------------------------------------------------------ #
    # Users
    # ------------------------------------------------------------------ #

    async def get_user(self, user_id: int) -> Optional[dict[str, Any]]:
        """Fetch a user document by Telegram user ID."""
        doc = await self.db.collection("users").document(str(user_id)).get()
        return doc.to_dict() if doc.exists else None

    async def create_user(self, user_id: int, data: dict[str, Any]) -> None:
        """Create a new user document."""
        ref = self.db.collection("users").document(str(user_id))
        await ref.set(data)
        logger.info("User %s created in Firestore.", user_id)

    async def update_user(self, user_id: int, data: dict[str, Any]) -> None:
        """Merge *data* into an existing user document."""
        ref = self.db.collection("users").document(str(user_id))
        await ref.set(data, merge=True)
        logger.info("User %s updated in Firestore.", user_id)

    async def list_users(self, limit: int = 100) -> list[dict[str, Any]]:
        """Return a bounded, display-ready list of users."""
        results: list[dict[str, Any]] = []
        try:
            async for doc in self.db.collection("users").limit(limit).stream():
                data = doc.to_dict() or {}
                data["_id"] = doc.id
                results.append(data)
        except Exception as exc:
            logger.error("Failed to list users: %s", exc)
        return results

    # ------------------------------------------------------------------ #
    # Global settings
    # ------------------------------------------------------------------ #

    async def get_settings(self) -> Optional[dict[str, Any]]:
        """Fetch the global bot-settings document."""
        doc = await self.db.collection("config").document("settings").get()
        return doc.to_dict() if doc.exists else None

    async def update_settings(self, data: dict[str, Any]) -> None:
        """Merge *data* into the global settings document."""
        ref = self.db.collection("config").document("settings")
        await ref.set(data, merge=True)
        logger.info("Global settings updated in Firestore.")


# ------------------------------------------------------------------ #
# Module-level singleton — shared across the entire application
# ------------------------------------------------------------------ #
firebase_service: FirebaseService = FirebaseService()
