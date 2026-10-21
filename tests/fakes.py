"""Dobles de prueba del puerto DocumentRepository."""

from datetime import UTC, datetime

from pdf_persistence.domain.errors import DuplicateChecksumError
from pdf_persistence.domain.models import StoredDocument


class FakeRepository:
    """Doble en memoria del puerto DocumentRepository."""

    def __init__(self) -> None:
        self.documents: dict[str, StoredDocument] = {}
        self.fail_mode: Exception | None = None
        self.indexes_ensured = False
        self.closed = False

    def _check_fail(self) -> None:
        if self.fail_mode:
            raise self.fail_mode

    async def insert(self, document: StoredDocument) -> None:
        self._check_fail()
        if document.checksum in self.documents:
            raise DuplicateChecksumError(document.checksum)
        self.documents[document.checksum] = document

    async def find_by_checksum(
        self, checksum: str, include_deleted: bool = False
    ) -> StoredDocument | None:
        self._check_fail()
        document = self.documents.get(checksum)
        if document is None:
            return None
        if document.deleted and not include_deleted:
            return None
        return document

    async def list_active(
        self, limit: int, offset: int
    ) -> tuple[list[StoredDocument], int]:
        self._check_fail()
        active = sorted(
            (d for d in self.documents.values() if not d.deleted),
            key=lambda d: d.created_at,
        )
        return active[offset : offset + limit], len(active)

    async def update_fields(self, checksum: str, fields: dict) -> StoredDocument | None:
        self._check_fail()
        document = self.documents.get(checksum)
        if document is None or document.deleted:
            return None
        updated = StoredDocument(
            **{**document.__dict__, **fields, "updated_at": datetime.now(UTC)}
        )
        self.documents[checksum] = updated
        return updated

    async def soft_delete(self, checksum: str) -> bool:
        self._check_fail()
        document = self.documents.get(checksum)
        if document is None or document.deleted:
            return False
        self.documents[checksum] = StoredDocument(
            **{**document.__dict__, "deleted": True, "deleted_at": datetime.now(UTC)}
        )
        return True

    async def ping(self) -> bool:
        self._check_fail()
        return True

    async def ensure_indexes(self) -> None:
        self._check_fail()
        self.indexes_ensured = True

    async def aclose(self) -> None:
        self.closed = True
