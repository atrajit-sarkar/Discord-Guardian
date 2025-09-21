from __future__ import annotations
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, date
from typing import Optional, Dict, Any, List, Tuple

from google.cloud import firestore

logger = logging.getLogger(__name__)

@dataclass
class UserProfile:
    user_id: str
    username: str
    hearts: int
    flagged_count: int
    last_daily_bonus: Optional[str]  # ISO date string 'YYYY-MM-DD'
    role: Optional[str]


class Store:
    def __init__(self, collection: str):
        self.db = firestore.Client()
        self.collection = collection

    def _user_doc(self, user_id: str):
        return self.db.collection(self.collection).document(user_id)

    def get_or_create_user(self, user_id: str, username: str, heart_start: int, guild_id: Optional[str] = None) -> UserProfile:
        doc_ref = self._user_doc(user_id)
        snap = doc_ref.get()
        if snap.exists:
            data = snap.to_dict() or {}
            return UserProfile(
                user_id=user_id,
                username=data.get("username", username),
                hearts=int(data.get("hearts", heart_start)),
                flagged_count=int(data.get("flagged_count", 0)),
                last_daily_bonus=data.get("last_daily_bonus"),
                role=data.get("role"),
            )
        now = datetime.now(timezone.utc)
        profile = {
            "user_id": user_id,
            "guild_id": guild_id,
            "username": username,
            "hearts": int(heart_start),
            "flagged_count": 0,
            "last_daily_bonus": None,
            "role": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        doc_ref.set(profile)
        return UserProfile(user_id=user_id, username=username, hearts=heart_start, flagged_count=0, last_daily_bonus=None, role=None)

    def update_user(self, user_id: str, fields: Dict[str, Any]) -> None:
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._user_doc(user_id).set(fields, merge=True)

    def add_hearts(self, user_id: str, amount: int) -> int:
        doc_ref = self._user_doc(user_id)

        @firestore.transactional
        def do_txn(transaction, ref):
            snap = ref.get(transaction=transaction)
            data = snap.to_dict() or {}
            hearts = int(data.get("hearts", 0)) + amount
            if hearts < 0:
                hearts = 0
            transaction.set(ref, {"hearts": hearts, "updated_at": datetime.now(timezone.utc).isoformat()}, merge=True)
            return hearts

        transaction = self.db.transaction()
        return do_txn(transaction, doc_ref)

    def increment_flag(self, user_id: str) -> int:
        doc_ref = self._user_doc(user_id)

        @firestore.transactional
        def do_txn(transaction, ref):
            snap = ref.get(transaction=transaction)
            data = snap.to_dict() or {}
            count = int(data.get("flagged_count", 0)) + 1
            transaction.set(ref, {"flagged_count": count, "updated_at": datetime.now(timezone.utc).isoformat()}, merge=True)
            return count

        transaction = self.db.transaction()
        return do_txn(transaction, doc_ref)

    def record_flag(self, user_id: str, flag: Dict[str, Any]) -> None:
        # store flagged message details in subcollection 'flags'
        self._user_doc(user_id).collection("flags").add({
            **flag,
            "ts": datetime.now(timezone.utc).isoformat()
        })

    def apply_daily_bonus_if_due(self, user_id: str, bonus: int) -> Optional[int]:
        today = date.today().isoformat()
        doc_ref = self._user_doc(user_id)

        @firestore.transactional
        def do_txn(transaction, ref):
            snap = ref.get(transaction=transaction)
            data = snap.to_dict() or {}
            last = data.get("last_daily_bonus")
            if last == today:
                return None
            new_hearts = int(data.get("hearts", 0)) + bonus
            transaction.set(ref, {"hearts": new_hearts, "last_daily_bonus": today, "updated_at": datetime.now(timezone.utc).isoformat()}, merge=True)
            return new_hearts

        transaction = self.db.transaction()
        return do_txn(transaction, doc_ref)

    def delete_user(self, user_id: str) -> None:
        """Delete a user document and its 'flags' subcollection."""
        doc_ref = self._user_doc(user_id)
        # Delete flags subcollection documents (batch)
        flags_col = doc_ref.collection("flags")
        batch = self.db.batch()
        count = 0
        for doc in flags_col.stream():
            batch.delete(doc.reference)
            count += 1
            if count % 400 == 0:  # keep batch size safe (<500)
                batch.commit()
                batch = self.db.batch()
        if count % 400 != 0:
            batch.commit()
        # Delete the user doc
        doc_ref.delete()

    # Convenience getters
    def get_user_hearts(self, user_id: str) -> int:
        snap = self._user_doc(user_id).get()
        data = snap.to_dict() or {}
        return int(data.get("hearts", 0))

    def top_users_by_guild(self, guild_id: str, limit: int = 10) -> List[Tuple[str, Dict[str, Any]]]:
        # returns list of (doc_id, data) ordered by hearts desc for a guild
        q = (
            self.db.collection(self.collection)
            .where("guild_id", "==", guild_id)
            .order_by("hearts", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        out: List[Tuple[str, Dict[str, Any]]] = []
        for doc in q.stream():
            out.append((doc.id, doc.to_dict() or {}))
        return out
