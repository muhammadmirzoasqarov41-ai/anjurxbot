"""
Firestore thin adapter.

This module re-exports the shared FirebaseService singleton and provides a
convenience accessor so the rest of the codebase can do:

    from app.database.firestore import db

instead of reaching into the services layer directly.
The ``db`` object is the raw ``google.cloud.firestore_v1.AsyncClient`` and should only
be used inside the ``FirebaseService`` class itself; other modules should call
the high-level methods on ``firebase_service``.
"""

from app.services.firebase import firebase_service

__all__ = ["firebase_service"]
