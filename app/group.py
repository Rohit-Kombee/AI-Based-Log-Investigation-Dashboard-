"""Error grouping by fingerprint."""
from datetime import datetime
from typing import Optional

from app.db import get_connection
from app.schema import GroupItem, GroupResponse


def get_groups(
    service: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 50,
    since: Optional[str] = None,
) -> GroupResponse:
    """Return grouped errors (by fingerprint/group_id)."""
    with get_connection() as conn:
        conditions = []
        params: list = []
        if service:
            conditions.append("service = ?")
            params.append(service)
        if level:
            conditions.append("level = ?")
            params.append(level)
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        where = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit])

        rows = conn.execute(
            f"""
            SELECT group_id, fingerprint, level, service,
                   COUNT(*) AS cnt,
                   MIN(timestamp) AS first_seen,
                   MAX(timestamp) AS last_seen,
                   (SELECT message FROM logs l2 WHERE l2.group_id = logs.group_id LIMIT 1) AS sample_message
            FROM logs
            WHERE {where}
            GROUP BY group_id
            ORDER BY cnt DESC
            LIMIT ?
            """,
            params,
        ).fetchall()

        groups = [
            GroupItem(
                group_id=row["group_id"],
                fingerprint=row["fingerprint"],
                count=row["cnt"],
                level=row["level"],
                service=row["service"],
                sample_message=row["sample_message"] or "",
                first_seen=datetime.fromisoformat(row["first_seen"]),
                last_seen=datetime.fromisoformat(row["last_seen"]),
            )
            for row in rows
        ]
        return GroupResponse(groups=groups, total_groups=len(groups))
