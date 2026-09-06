"""
Firestore Async Client wrapper for AnjurXBot.
Supports native async calls with fallback for credential-free testing environments.
"""
import logging
import inspect
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

        project_id = config.firebase_project_id or "anjurxbot"
        try:
            sa = config.firebase_service_account
            if sa:
                pid = sa.get("project_id") or project_id
                # Initialize firebase-admin SDK if not already done
                if not firebase_admin._apps:
                    cred = credentials.Certificate(sa)
                    firebase_admin.initialize_app(cred, {"projectId": pid})

                # Initialize async Firestore client
                g_cred = service_account.Credentials.from_service_account_info(sa)
                self.client = AsyncClient(credentials=g_cred, project=pid)
                self._is_connected = True
                self._fallback_mode = False
                logger.info(f"Firebase Firestore connected successfully. Project: {pid}")
                return True
            else:
                # Attempt connecting via default Google Cloud environment credentials if project_id is known
                try:
                    self.client = AsyncClient(project=project_id)
                    self._is_connected = True
                    self._fallback_mode = False
                    logger.info(f"Connected to Firestore using environment credentials. Project: {project_id}")
                    return True
                except Exception as adc_err:
                    logger.warning(
                        f"No service account credentials provided for project '{project_id}' ({adc_err}). "
                        "Operating in safe in-memory fallback mode."
                    )
                    self._fallback_mode = True
                    self._is_connected = True
                    return True
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} message=Failed to connect to Firebase: {e}")
            self._fallback_mode = True
            self._is_connected = False
            return False

    async def close(self) -> None:
        """Gracefully close AsyncClient upon service shutdown."""
        if self.client:
            try:
                res = self.client.close()
                if inspect.isawaitable(res):
                    await res
                logger.info("Firestore async client closed gracefully")
            except Exception as e:
                logger.error(f"error_type={type(e).__name__} message=Error closing Firestore client: {e}")
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
                    data = doc.to_dict() or {}
                    data["_id"] = doc.id
                    return data
                return None
            else:
                item = self._memory_db.get(collection, {}).get(str(doc_id))
                if item:
                    item_copy = dict(item)
                    item_copy["_id"] = str(doc_id)
                    return item_copy
                return None
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=get_document collection={collection} doc_id={doc_id} error={e}")
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
            logger.error(f"error_type={type(e).__name__} action=set_document collection={collection} doc_id={doc_id} error={e}")
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
            logger.error(f"error_type={type(e).__name__} action=update_document collection={collection} doc_id={doc_id} error={e}")
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
            logger.error(f"error_type={type(e).__name__} action=delete_document collection={collection} doc_id={doc_id} error={e}")
            return False

    async def list_documents(self, collection: str, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            if not self._fallback_mode and self.client:
                docs = []
                query = self.client.collection(collection).limit(limit)
                async for d in query.stream():
                    data = d.to_dict() or {}
                    data["_id"] = d.id
                    if collection == "groups":
                        try:
                            if d.id.isdigit() or (d.id.startswith("-") and d.id[1:].isdigit()):
                                data.setdefault("group_id", int(d.id))
                                data.setdefault("chat_id", int(d.id))
                        except Exception:
                            pass
                    docs.append(data)
                return docs
            else:
                col = self._memory_db.get(collection, {})
                results = []
                for k, v in list(col.items())[:limit]:
                    item = dict(v)
                    item["_id"] = k
                    if collection == "groups":
                        try:
                            if k.isdigit() or (k.startswith("-") and k[1:].isdigit()):
                                item.setdefault("group_id", int(k))
                                item.setdefault("chat_id", int(k))
                        except Exception:
                            pass
                    results.append(item)
                return results
        except Exception as e:
            logger.error(f"error_type={type(e).__name__} action=list_documents collection={collection} error={e}")
            return []


# Global database manager
db = FirestoreManager()
