# -*- coding: utf-8 -*-
# backfill dragon_king_daily from speech_stats (04:00 cycle)

import argparse
import asyncio
import datetime as dt
from typing import List, Optional, Sequence, Tuple

import asyncpg

from utils.yaml import BotConfig


CREATE_DRAGON_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dragon_king_daily (
    group_id BIGINT NOT NULL,
    stat_date DATE NOT NULL,
    user_id BIGINT NOT NULL,
    display_name TEXT NOT NULL,
    total INTEGER NOT NULL,
    streak_days INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (group_id, stat_date)
)
"""

CREATE_DRAGON_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_dragon_king_daily_group_user_date
ON dragon_king_daily (group_id, user_id, stat_date DESC)
"""

# 说明：
# - stat_date 定义：把消息 hour 先按群时区转本地，再减 4 小时后取 date
# - 每个 (group_id, stat_date) 取 total 最大者为龙王；并列时 display_name 升序
WINNERS_SQL = """
WITH tz_map AS (
    SELECT g.group_id,
           COALESCE(sj.timezone, 'Asia/Shanghai') AS timezone
    FROM (
        SELECT DISTINCT group_id
        FROM speech_stats
        WHERE ($1::BIGINT[] IS NULL OR group_id = ANY($1))
    ) g
    LEFT JOIN scheduled_jobs sj
      ON sj.group_id = g.group_id
     AND sj.job_name = 'stats.dragon_king'
),
daily AS (
    SELECT
        ss.group_id,
        ((ss.hour AT TIME ZONE tz_map.timezone) - INTERVAL '4 hour')::date AS stat_date,
        ss.user_id,
        MAX(ss.display_name) AS display_name,
        SUM(ss.count)::int AS total
    FROM speech_stats ss
    JOIN tz_map ON tz_map.group_id = ss.group_id
    WHERE ($1::BIGINT[] IS NULL OR ss.group_id = ANY($1))
    GROUP BY
        ss.group_id,
        ((ss.hour AT TIME ZONE tz_map.timezone) - INTERVAL '4 hour')::date,
        ss.user_id
),
ranked AS (
    SELECT
        group_id, stat_date, user_id, display_name, total,
        ROW_NUMBER() OVER (
            PARTITION BY group_id, stat_date
            ORDER BY total DESC, display_name ASC
        ) AS rn
    FROM daily
    WHERE ($2::DATE IS NULL OR stat_date >= $2)
      AND ($3::DATE IS NULL OR stat_date <= $3)
)
SELECT group_id, stat_date, user_id, display_name, total
FROM ranked
WHERE rn = 1 AND total > 0
ORDER BY group_id, stat_date
"""

UPSERT_SQL = """
INSERT INTO dragon_king_daily (group_id, stat_date, user_id, display_name, total, streak_days)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (group_id, stat_date)
DO UPDATE SET
    user_id = EXCLUDED.user_id,
    display_name = EXCLUDED.display_name,
    total = EXCLUDED.total,
    streak_days = EXCLUDED.streak_days
"""

INSERT_MISSING_SQL = """
INSERT INTO dragon_king_daily (group_id, stat_date, user_id, display_name, total, streak_days)
VALUES ($1, $2, $3, $4, $5, $6)
ON CONFLICT (group_id, stat_date)
DO NOTHING
"""


def parse_date(date_str: Optional[str]) -> Optional[dt.date]:
    if not date_str:
        return None
    return dt.datetime.strptime(date_str, "%Y-%m-%d").date()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill dragon_king_daily from speech_stats (04:00 cycle)."
    )
    parser.add_argument(
        "--group-id",
        dest="group_ids",
        action="append",
        type=int,
        help="指定群组ID，可重复传参，例如 --group-id -1001 --group-id -1002",
    )
    parser.add_argument(
        "--from-date",
        type=str,
        default=None,
        help="起始统计日(含)，格式 YYYY-MM-DD",
    )
    parser.add_argument(
        "--to-date",
        type=str,
        default=None,
        help="结束统计日(含)，格式 YYYY-MM-DD",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="仅补缺失记录（不更新已存在记录）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只计算不落库",
    )
    return parser.parse_args()


def build_rows_with_streak(
    winners: Sequence[asyncpg.Record],
) -> List[Tuple[int, dt.date, int, str, int, int]]:
    result: List[Tuple[int, dt.date, int, str, int, int]] = []

    last_group_id: Optional[int] = None
    last_date: Optional[dt.date] = None
    last_user_id: Optional[int] = None
    streak = 0

    for row in winners:
        group_id = int(row["group_id"])
        stat_date = row["stat_date"]
        user_id = int(row["user_id"])
        display_name = str(row["display_name"])
        total = int(row["total"])

        if (
            last_group_id == group_id
            and last_date is not None
            and stat_date == last_date + dt.timedelta(days=1)
            and last_user_id == user_id
        ):
            streak += 1
        else:
            streak = 1

        result.append((group_id, stat_date, user_id, display_name, total, streak))

        last_group_id = group_id
        last_date = stat_date
        last_user_id = user_id

    return result


async def main() -> None:
    args = parse_args()
    from_date = parse_date(args.from_date)
    to_date = parse_date(args.to_date)

    if from_date and to_date and from_date > to_date:
        raise ValueError("--from-date 不能晚于 --to-date")

    group_ids = args.group_ids if args.group_ids else None

    conn = await asyncpg.connect(
        host=BotConfig["database"]["host"],
        port=BotConfig["database"]["port"],
        user=BotConfig["database"]["user"],
        password=BotConfig["database"]["password"],
        database=BotConfig["database"]["dbname"],
    )

    try:
        await conn.execute(CREATE_DRAGON_TABLE_SQL)
        await conn.execute(CREATE_DRAGON_INDEX_SQL)

        winners = await conn.fetch(WINNERS_SQL, group_ids, from_date, to_date)
        rows = build_rows_with_streak(winners)

        group_count = len({int(r[0]) for r in rows})
        print(f"[INFO] winners rows: {len(rows)}, groups: {group_count}")

        if args.dry_run:
            print("[DRY-RUN] 不写入数据库。")
            return

        sql = INSERT_MISSING_SQL if args.missing_only else UPSERT_SQL

        # 建议放事务，保证批处理一致性
        async with conn.transaction():
            await conn.executemany(sql, rows)

        mode = "missing-only" if args.missing_only else "upsert"
        print(f"[OK] backfill completed, mode={mode}, rows={len(rows)}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
