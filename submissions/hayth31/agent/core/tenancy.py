"""
Tenancy Isolation Module (Rule 1: Tenancy isolation before any feature).
Enforces strict organization-scoped row-level security and prevents cross-tenant data leaks.
"""
from typing import Dict, List, Optional, Any, Set
import hashlib
import hmac

class TenancyViolationError(PermissionError):
    """Raised when an operation attempts to cross tenant boundaries."""
    pass

class TenantContext:
    """Thread-safe or scope-bound tenant context."""
    def __init__(self, org_id: str, secret_salt: str = "sydon_cube_salt_2026"):
        if not org_id or not isinstance(org_id, str):
            raise ValueError("Valid org_id is strictly required to establish TenantContext.")
        self.org_id = org_id.strip()
        self._salt = secret_salt.encode("utf-8")

    def validate_record(self, record_org_id: str) -> None:
        """Enforce that a record belongs to this tenant context."""
        if record_org_id != self.org_id:
            raise TenancyViolationError(
                f"Security breach prevented: Tenant '{self.org_id}' cannot access record owned by '{record_org_id}'."
            )

    def secure_asset_token(self, asset_path: str) -> str:
        """
        Generates an HMAC-signed token for an asset path bound to this tenant.
        Prevents guessable image/photo_ref URL tampering across organizations.
        """
        msg = f"{self.org_id}:{asset_path}".encode("utf-8")
        return hmac.new(self._salt, msg, hashlib.sha256).hexdigest()

    def verify_asset_token(self, asset_path: str, token: str) -> bool:
        expected = self.secure_asset_token(asset_path)
        return hmac.compare_digest(expected, token)

class TenantScopedStore:
    """
    In-memory isolated storage partitioned strictly by org_id.
    Guarantees that queries executed with a given TenantContext only ever see that tenant's records.
    """
    def __init__(self):
        # org_id -> collection_name -> id -> record
        self._data: Dict[str, Dict[str, Dict[str, Any]]] = {}

    def insert(self, tenant: TenantContext, collection: str, record_id: str, record: Any, record_org_id: str) -> None:
        tenant.validate_record(record_org_id)
        if tenant.org_id not in self._data:
            self._data[tenant.org_id] = {}
        if collection not in self._data[tenant.org_id]:
            self._data[tenant.org_id][collection] = {}
        self._data[tenant.org_id][collection][record_id] = record

    def get(self, tenant: TenantContext, collection: str, record_id: str) -> Optional[Any]:
        if tenant.org_id not in self._data:
            return None
        return self._data[tenant.org_id].get(collection, {}).get(record_id)

    def list_all(self, tenant: TenantContext, collection: str) -> List[Any]:
        if tenant.org_id not in self._data:
            return []
        return list(self._data[tenant.org_id].get(collection, {}).values())

    def clear_tenant(self, tenant: TenantContext) -> None:
        if tenant.org_id in self._data:
            del self._data[tenant.org_id]
