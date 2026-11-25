"""SQLite-backed Access-Code (Redeem Card) Billing & Ledger Store for Hosted Official AI."""

from __future__ import annotations

import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class BillingError(Exception):
    """Raised when an access code cannot be redeemed or lacks credits."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def normalize_access_code(raw: str) -> str:
    return (raw or "").strip().upper()


def default_billing_db_path(repo_root: Path) -> Path:
    env_path = os.environ.get("BILLING_DB_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return repo_root / "data" / "billing.db"


class BillingStore:
    """Thread-safe SQLite store for prepaid access codes and credit ledger entries."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS access_codes (
                    code TEXT PRIMARY KEY,
                    label TEXT NOT NULL DEFAULT '',
                    credits_total INTEGER NOT NULL,
                    credits_left INTEGER NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    last_used_at REAL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    action TEXT NOT NULL,
                    delta INTEGER NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL
                )
                """
            )
            self._conn.commit()

    def _generate_unique_code(self, prefix: str = "PRO") -> str:
        clean_prefix = "".join(ch for ch in (prefix or "PRO").upper() if ch.isalnum())[:8] or "PRO"
        for _ in range(20):
            seg1 = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
            seg2 = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
            candidate = f"{clean_prefix}-{seg1}-{seg2}"
            row = self._conn.execute("SELECT 1 FROM access_codes WHERE code = ?", (candidate,)).fetchone()
            if row is None:
                return candidate
        raise RuntimeError("Failed to allocate unique access code.")

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        now = time.time()
        expires_at = row["expires_at"]
        expired = bool(expires_at is not None and float(expires_at) <= now)
        active = bool(row["active"])
        credits_left = int(row["credits_left"])
        return {
            "code": str(row["code"]),
            "label": str(row["label"] or ""),
            "credits_total": int(row["credits_total"]),
            "credits_left": credits_left,
            "active": active,
            "expired": expired,
            "valid": active and not expired and credits_left > 0,
            "created_at": float(row["created_at"]),
            "expires_at": float(expires_at) if expires_at is not None else None,
            "last_used_at": float(row["last_used_at"]) if row["last_used_at"] is not None else None,
        }

    def create_codes(
        self,
        count: int = 1,
        credits: int = 5,
        prefix: str = "PRO",
        label: str = "",
        valid_days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        n = max(1, min(100, int(count)))
        c = max(1, min(10000, int(credits)))
        now = time.time()
        expires_at = (now + int(valid_days) * 86400.0) if (valid_days is not None and int(valid_days) > 0) else None
        clean_label = (label or "").strip()[:80]
        created: List[Dict[str, Any]] = []

        with self._lock:
            for _ in range(n):
                code = self._generate_unique_code(prefix=prefix)
                self._conn.execute(
                    """
                    INSERT INTO access_codes (code, label, credits_total, credits_left, active, created_at, expires_at, last_used_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?, NULL)
                    """,
                    (code, clean_label, c, c, now, expires_at),
                )
                self._conn.execute(
                    """
                    INSERT INTO usage_logs (code, action, delta, detail, created_at)
                    VALUES (?, 'grant', ?, ?, ?)
                    """,
                    (code, c, clean_label or f"credits={c}", now),
                )
                row = self._conn.execute("SELECT * FROM access_codes WHERE code = ?", (code,)).fetchone()
                if row is not None:
                    created.append(self._row_to_dict(row))
            self._conn.commit()
        return created

    def get_code(self, raw_code: str) -> Optional[Dict[str, Any]]:
        code = normalize_access_code(raw_code)
        if not code:
            return None
        with self._lock:
            row = self._conn.execute("SELECT * FROM access_codes WHERE code = ?", (code,)).fetchone()
            return self._row_to_dict(row) if row is not None else None

    def validate_for_use(self, raw_code: str, amount: int = 1) -> Dict[str, Any]:
        code = normalize_access_code(raw_code)
        if not code:
            raise BillingError("invalid_code", "请输入有效的官方 AI 兑换码。")
        with self._lock:
            row = self._conn.execute("SELECT * FROM access_codes WHERE code = ?", (code,)).fetchone()
            if row is None:
                raise BillingError("invalid_code", "兑换码不存在，请核对是否输入完整。")
            info = self._row_to_dict(row)
        if not info["active"]:
            raise BillingError("revoked", "该兑换码已被停用，请联系站长核实。")
        if info["expired"]:
            raise BillingError("expired", "该兑换码已过有效期，请更换或续期。")
        if info["credits_left"] < max(1, int(amount)):
            raise BillingError("insufficient_credits", f"该兑换码剩余次数不足（剩余 {info['credits_left']} 次）。")
        return info

    def consume(self, raw_code: str, amount: int = 1, action: str = "plan_deck", detail: str = "") -> Dict[str, Any]:
        cost = max(1, int(amount))
        code = normalize_access_code(raw_code)
        if not code:
            raise BillingError("invalid_code", "请先输入官方 AI 兑换码。")

        now = time.time()
        with self._lock:
            row = self._conn.execute("SELECT * FROM access_codes WHERE code = ?", (code,)).fetchone()
            if row is None:
                raise BillingError("invalid_code", "兑换码不存在，请核对是否输入完整。")
            info = self._row_to_dict(row)
            if not info["active"]:
                raise BillingError("revoked", "该兑换码已被停用，请联系站长核实。")
            if info["expired"]:
                raise BillingError("expired", "该兑换码已过有效期，请更换或续期。")
            if info["credits_left"] < cost:
                raise BillingError("insufficient_credits", f"兑换码剩余次数不足（剩余 {info['credits_left']} 次，本次需要 {cost} 次）。")

            cur = self._conn.execute(
                """
                UPDATE access_codes
                SET credits_left = credits_left - ?, last_used_at = ?
                WHERE code = ?
                  AND active = 1
                  AND credits_left >= ?
                  AND (expires_at IS NULL OR expires_at > ?)
                """,
                (cost, now, code, cost, now),
            )
            if cur.rowcount != 1:
                raise BillingError("insufficient_credits", "兑换码扣减失败，请重试或检查剩余次数。")

            self._conn.execute(
                """
                INSERT INTO usage_logs (code, action, delta, detail, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (code, action, -cost, detail[:200], now),
            )
            updated = self._conn.execute("SELECT * FROM access_codes WHERE code = ?", (code,)).fetchone()
            self._conn.commit()
            assert updated is not None
            res = self._row_to_dict(updated)
            res["cost"] = cost
            return res

    def refund(self, raw_code: str, amount: int = 1, detail: str = "generation_failed") -> Optional[Dict[str, Any]]:
        amt = max(1, int(amount))
        code = normalize_access_code(raw_code)
        if not code:
            return None
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                """
                UPDATE access_codes
                SET credits_left = MIN(credits_total, credits_left + ?)
                WHERE code = ?
                """,
                (amt, code),
            )
            if cur.rowcount == 0:
                return None
            self._conn.execute(
                """
                INSERT INTO usage_logs (code, action, delta, detail, created_at)
                VALUES (?, 'refund', ?, ?, ?)
                """,
                (code, amt, detail[:200], now),
            )
            row = self._conn.execute("SELECT * FROM access_codes WHERE code = ?", (code,)).fetchone()
            self._conn.commit()
            return self._row_to_dict(row) if row is not None else None

    def set_active(self, raw_code: str, active: bool) -> bool:
        code = normalize_access_code(raw_code)
        if not code:
            return False
        now = time.time()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE access_codes SET active = ? WHERE code = ?",
                (1 if active else 0, code),
            )
            if cur.rowcount == 0:
                return False
            self._conn.execute(
                """
                INSERT INTO usage_logs (code, action, delta, detail, created_at)
                VALUES (?, ?, 0, '', ?)
                """,
                (code, "enable" if active else "revoke", now),
            )
            self._conn.commit()
            return True

    def list_codes(self, limit: int = 100) -> List[Dict[str, Any]]:
        lim = max(1, min(500, int(limit)))
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM access_codes ORDER BY created_at DESC LIMIT ?",
                (lim,),
            ).fetchall()
            return [self._row_to_dict(r) for r in rows]
