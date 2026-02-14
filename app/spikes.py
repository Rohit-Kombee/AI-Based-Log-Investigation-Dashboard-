"""Spike detection: identify sudden increases in error volume."""
from datetime import datetime, timedelta
from typing import Optional

from app.db import get_connection
from app.schema import SpikeItem, SpikesResponse


def get_spikes(
    window_minutes: int = 5,
    ratio_threshold: float = 2.0,
    baseline_windows: int = 6,
    service: Optional[str] = None,
    level: Optional[str] = None,
) -> SpikesResponse:
    """
    Compare recent window count to baseline average per group.
    If current count >= ratio_threshold * baseline_avg, report as spike.
    """
    now = datetime.utcnow()
    cur_start = now - timedelta(minutes=window_minutes)
    base_start = cur_start - timedelta(minutes=window_minutes * max(baseline_windows, 1))
    cur_start_s = cur_start.isoformat()
    base_start_s = base_start.isoformat()

    with get_connection() as conn:
        params: list = [cur_start_s]
        params_base: list = [max(baseline_windows, 1), base_start_s, cur_start_s]
        w_cur = "timestamp >= ?"
        w_base = "timestamp >= ? AND timestamp < ?"
        if service:
            w_cur += " AND service = ?"
            w_base += " AND service = ?"
            params.append(service)
            params_base.append(service)
        if level:
            w_cur += " AND level = ?"
            w_base += " AND level = ?"
            params.append(level)
            params_base.append(level)
        params_base.append(ratio_threshold)

        rows = conn.execute(
            """
            WITH cur AS (
                SELECT group_id, service, level, COUNT(*) AS cnt
                FROM logs
                WHERE """ + w_cur + """
                GROUP BY group_id
            ),
            base AS (
                SELECT group_id, CAST(COUNT(*) AS REAL) / ? AS avg_cnt
                FROM logs
                WHERE """ + w_base + """
                GROUP BY group_id
            )
            SELECT cur.group_id, cur.service, cur.level, cur.cnt,
                   COALESCE(base.avg_cnt, 0) AS baseline_avg,
                   CASE WHEN COALESCE(base.avg_cnt, 0) > 0
                        THEN cur.cnt / base.avg_cnt ELSE 999.0 END AS ratio
            FROM cur
            LEFT JOIN base ON cur.group_id = base.group_id
            WHERE base.avg_cnt > 0 AND cur.cnt >= ? * base.avg_cnt
            ORDER BY ratio DESC
            """,
            params + params_base,
        ).fetchall()

        spikes = [
            SpikeItem(
                group_id=row["group_id"],
                service=row["service"],
                level=row["level"],
                window_start=cur_start_s,
                count=row["cnt"],
                baseline_avg=row["baseline_avg"],
                ratio=round(row["ratio"], 2),
            )
            for row in rows
        ]
        return SpikesResponse(spikes=spikes)
