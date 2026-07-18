import base64
import json
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

from services.database import get_conn


TASK_TIMEOUT_SECONDS = 30 * 60
PENDING_TASK_TIMEOUT_SECONDS = 24 * 60 * 60


def init_local_ai_task_tables() -> None:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS local_ai_tasks (
            id BIGSERIAL PRIMARY KEY,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            payload_json TEXT NOT NULL,
            result_bytes BYTEA,
            result_mime_type TEXT,
            error_message TEXT,
            cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
            worker_id TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            claimed_at TIMESTAMP,
            heartbeat_at TIMESTAMP,
            completed_at TIMESTAMP
        )
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_local_ai_tasks_status_id
        ON local_ai_tasks(status, id)
        """)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_local_ai_task(task_type: str, payload: Dict[str, Any]) -> int:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO local_ai_tasks (task_type, payload_json)
            VALUES (%s, %s)
            RETURNING id
            """,
            (
                str(task_type),
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            ),
        )
        task_id = int(cursor.fetchone()[0])
        conn.commit()
        return task_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cancel_local_ai_task(task_id: int) -> None:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE local_ai_tasks
            SET cancel_requested=TRUE,
                status=CASE WHEN status='pending' THEN 'canceled' ELSE status END,
                completed_at=CASE WHEN status='pending' THEN CURRENT_TIMESTAMP ELSE completed_at END
            WHERE id=%s AND status IN ('pending','in_progress')
            """,
            (int(task_id),),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def claim_next_local_ai_task(worker_id: str) -> Optional[Dict[str, Any]]:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE local_ai_tasks
            SET status='in_progress',
                worker_id=%s,
                claimed_at=CURRENT_TIMESTAMP,
                heartbeat_at=CURRENT_TIMESTAMP
            WHERE id = (
                SELECT id
                FROM local_ai_tasks
                WHERE status='pending'
                ORDER BY id ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, task_type, payload_json
        """, (str(worker_id or "local-worker"),))
        row = cursor.fetchone()
        conn.commit()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "task_type": row[1],
            "payload": json.loads(row[2] or "{}"),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def heartbeat_local_ai_task(task_id: int, worker_id: str = "") -> Dict[str, Any]:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE local_ai_tasks
            SET heartbeat_at=CURRENT_TIMESTAMP
            WHERE id=%s AND status='in_progress'
            RETURNING cancel_requested
            """,
            (int(task_id),),
        )
        row = cursor.fetchone()
        conn.commit()
        return {"ok": bool(row), "cancel_requested": bool(row and row[0])}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def complete_local_ai_task(task_id: int, image_bytes: bytes, mime_type: str) -> None:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE local_ai_tasks
            SET status='completed',
                result_bytes=%s,
                result_mime_type=%s,
                completed_at=CURRENT_TIMESTAMP,
                heartbeat_at=CURRENT_TIMESTAMP
            WHERE id=%s AND status='in_progress'
            """,
            (bytes(image_bytes), str(mime_type or "image/png"), int(task_id)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fail_local_ai_task(task_id: int, message: str, *, canceled: bool = False) -> None:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE local_ai_tasks
            SET status=%s,
                error_message=%s,
                completed_at=CURRENT_TIMESTAMP,
                heartbeat_at=CURRENT_TIMESTAMP
            WHERE id=%s AND status IN ('pending','in_progress')
            """,
            ("canceled" if canceled else "failed", str(message or "")[:1000], int(task_id)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_local_ai_task_result(task_id: int) -> Dict[str, Any]:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT status, result_bytes, result_mime_type, error_message, cancel_requested
            FROM local_ai_tasks
            WHERE id=%s
            """,
            (int(task_id),),
        )
        row = cursor.fetchone()
        if not row:
            return {"ok": False, "done": True, "message": "找不到本機任務"}
        status, result_bytes, mime_type, error_message, cancel_requested = row
        if status == "completed" and result_bytes is not None:
            return {
                "ok": True,
                "done": True,
                "bytes": bytes(result_bytes),
                "mime_type": mime_type or "image/png",
            }
        if status == "failed":
            return {"ok": False, "done": True, "message": error_message or "本機 worker 執行失敗"}
        if status == "canceled":
            return {"ok": False, "done": True, "canceled": True, "message": "使用者已取消生圖"}
        return {"ok": True, "done": False, "cancel_requested": bool(cancel_requested)}
    finally:
        conn.close()


def wait_for_local_ai_task_result(
    task_id: int,
    *,
    timeout_seconds: int,
    poll_seconds: int,
    cancel_check: Optional[Callable[[], bool]] = None,
    progress_callback: Optional[Callable[[], None]] = None,
) -> Dict[str, Any]:
    started = time.monotonic()
    while True:
        if progress_callback:
            try:
                progress_callback()
            except Exception:
                pass

        if cancel_check and cancel_check():
            cancel_local_ai_task(task_id)
            return {"ok": False, "canceled": True, "message": "使用者已取消生圖"}

        if time.monotonic() - started > int(timeout_seconds or TASK_TIMEOUT_SECONDS):
            fail_local_ai_task(task_id, f"AI 匝道等待超過 {timeout_seconds} 秒")
            return {"ok": False, "message": f"AI 匝道等待超過 {timeout_seconds} 秒"}

        result = fetch_local_ai_task_result(task_id)
        if result.get("done"):
            return result
        time.sleep(max(1, int(poll_seconds or 2)))


def cleanup_old_local_ai_tasks() -> None:
    """避免 BYTEA 結果長期留在 DB；成功/失敗任務一天後清理。"""
    conn = get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM local_ai_tasks
            WHERE completed_at IS NOT NULL
              AND completed_at < %s
            """,
            (datetime.utcnow() - timedelta(days=1),),
        )
        cursor.execute(
            """
            UPDATE local_ai_tasks
            SET status='failed',
                error_message='本機 worker 超時未回報',
                completed_at=CURRENT_TIMESTAMP
            WHERE status='in_progress'
              AND heartbeat_at < %s
            """,
            (datetime.utcnow() - timedelta(seconds=TASK_TIMEOUT_SECONDS),),
        )
        cursor.execute(
            """
            UPDATE local_ai_tasks
            SET status='failed',
                error_message='AI 匝道等待超過一天未連線',
                completed_at=CURRENT_TIMESTAMP
            WHERE status='pending'
              AND created_at < %s
            """,
            (datetime.utcnow() - timedelta(seconds=PENDING_TASK_TIMEOUT_SECONDS),),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def encode_result_bytes(image_bytes: bytes) -> str:
    return base64.b64encode(bytes(image_bytes)).decode("ascii")


def decode_result_bytes(value: str) -> bytes:
    return base64.b64decode(str(value or ""), validate=True)
