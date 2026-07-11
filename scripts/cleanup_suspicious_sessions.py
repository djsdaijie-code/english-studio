from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def suspicious_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    return connection.execute(
        """
        SELECT id, created_at, practice_type, active_seconds, correct_characters, wpm, cpm, app_version
        FROM practice_sessions
        WHERE (
            LOWER(COALESCE(app_version, '')) LIKE '%acceptance%'
            OR LOWER(COALESCE(app_version, '')) LIKE '%runtime%'
            OR LOWER(COALESCE(app_version, '')) LIKE '%phase%'
            OR LOWER(COALESCE(app_version, '')) LIKE '%qa%'
            OR LOWER(COALESCE(app_version, '')) LIKE '%test%'
            OR LOWER(COALESCE(app_version, '')) LIKE '%automation%'
        )
        OR (
            completed = 1
            AND (
                active_seconds < 1
                OR wpm > 300
                OR cpm > 1800
            )
        )
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()


def main() -> int:
    parser = argparse.ArgumentParser(description="清理明显异常或验收标签的练习记录。默认仅预览。")
    parser.add_argument("database", type=Path, help="SQLite 数据库路径")
    parser.add_argument("--apply", action="store_true", help="确认执行删除")
    args = parser.parse_args()

    connection = sqlite3.connect(args.database)
    try:
        rows = suspicious_rows(connection)
        if not rows:
            print("未发现可清理的可疑记录。")
            return 0

        print("以下记录会被视为可疑记录：")
        for row in rows:
            print(
                f"id={row['id']} created_at={row['created_at']} "
                f"type={row['practice_type']} active={row['active_seconds']:.1f}s "
                f"chars={row['correct_characters']} wpm={row['wpm']:.1f} "
                f"cpm={row['cpm']:.1f} app_version={row['app_version']}"
            )

        if not args.apply:
            print("\n当前为预览模式。确认无误后追加 --apply 执行删除。")
            return 0

        ids = [row["id"] for row in rows]
        placeholders = ", ".join("?" for _ in ids)
        connection.execute(f"DELETE FROM practice_sessions WHERE id IN ({placeholders})", ids)
        connection.commit()
        print(f"\n已删除 {len(ids)} 条可疑记录。")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
