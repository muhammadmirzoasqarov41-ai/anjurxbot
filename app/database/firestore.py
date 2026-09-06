"""
Firestore Async Client wrapper for AnjurXBot.
Supports native async calls with fallback for credential-free testing environments.
"""
import logging
from typing import Optional, Dict, Any, List
from google.oauth2 import service_account
from google.cloud.firestore import AsyncClient
import firebase_admin
from firebase_admin import credentials

from app.config import config

logger = logging.getLogger("anjurxbot.firestore")


class FirestoreManager:
    _instance: Optional["FirestoreManager"] = None
    client: Optional[AsyncClient] = None
    _is_connected: bool = False
    _fallback_mode: bool = False
    _memory_db: Dict[str, Dict[str, Any]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirestoreManager, cls).__new__(cls)
            cls._instance._memory_db = {
                "groups": {},
                "users": {},
                "moderation_logs": {},
            }
        return cls._instance

    async def connect(self) -> bool:
        """Initialize connection to Firebase and Firestore AsyncClient."""
        if self._is_connected and self.client:
            return True

        try:
            sa = config.firebase_service_account
            if sa:
                # Initialize firebase-admin SDK if not already done
                if not firebase_admin._apps:
                    cred = credentials.Certificate(sa)
                    firebase_admin.initialize_app(cred)

                # Initialize async Firestore client
                g_cred = service_account.Credentials.from_service_account_info(sa)
                project_id = sa.get("project_id") or config.firebase_project_id
                self.client = AsyncClient(credentials=g_cred, project=project_id)
                self._is_connected = True
                self._fallback_mode = False
                logger.info("Firebase connected successfully")
                return True
            else:
                # Fallback in-memory mode for development / unit test environments
                logger.warning("No Firebase credentials provided. Operating in safe in-memory fallback mode.")
                self._fallback_mode = True
                self._is_connected = True
                return True
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} message=Failed to connect to Firebase")
            self._fallback_mode = True
            self._is_connected = False
            return False

    async def close(self) -> None:
        """Gracefully close AsyncClient upon service shutdown."""
        if self.client:
            try:
                self.client.close()
                logger.info("Firestore async client closed gracefully")
            except Exception as e:
                logger.error(f"error_type={type(e).__name__} message=Error closing Firestore client")
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    # Document operations
    async def get_document(self, collection: str, doc_id: str) -> Optional[Dict[str, Any]]:
        try:
            if not self._fallback_mode and self.client:
                doc_ref = self.client.collection(collection).document(str(doc_id))
                doc = await doc_ref.get()
                if doc.exists:
                    return doc.to_dict()
                return None
            else:
                return self._memory_db.get(collection, {}).get(str(doc_id))
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=get_document collection={collection}")
            return None

    async def set_document(self, collection: str, doc_id: str, data: Dict[str, Any], merge: bool = True) -> bool:
        try:
            if not self._fallback_mode and self.client:
                doc_ref = self.client.collection(collection).document(str(doc_id))
                await doc_ref.set(data, merge=merge)
                return True
            else:
                col = self._memory_db.setdefault(collection, {})
                if merge and str(doc_id) in col:
                    col[str(doc_id)].update(data)
                else:
                    col[str(doc_id)] = dict(data)
                return True
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=set_document collection={collection}")
            return False

    async def update_document(self, collection: str, doc_id: str, data: Dict[str, Any]) -> bool:
        try:
            if not self._fallback_mode and self.client:
                doc_ref = self.client.collection(collection).document(str(doc_id))
                await doc_ref.update(data)
                return True
            else:
                col = self._memory_db.setdefault(collection, {})
                if str(doc_id) in col:
                    col[str(doc_id)].update(data)
                    return True
                return False
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=update_document collection={collection}")
            return False

    async def delete_document(self, collection: str, doc_id: str) -> bool:
        try:
            if not self._fallback_mode and self.client:
                doc_ref = self.client.collection(collection).document(str(doc_id))
                await doc_ref.delete()
                return True
            else:
                self._memory_db.get(collection, {}).pop(str(doc_id), None)
                return True
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=delete_document collection={collection}")
            return False

    async def list_documents(self, collection: str, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            if not self._fallback_mode and self.client:
                docs = []
                query = self.client.collection(collection).limit(limit)
                async for d in query.stream():
                    data = d.to_dict() or {}
                    data["_id"] = d.id
                    docs.append(data)
                return docs
            else:
                col = self._memory_db.get(collection, {})
                results = []
                for k, v in list(col.items())[:limit]:
                    item = dict(v)
                    item["_id"] = k
                    results.append(item)
                return results
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=list_documents collection={collection}")
            return []


# Global database manager
db = FirestoreManager()
