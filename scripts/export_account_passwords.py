#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sqlite3
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "account_manager.db"


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="导出账号库中的账号密码到 CSV 或 TXT 文件。"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"数据库路径，默认: {DEFAULT_DB_PATH}",
    )
    parser.add_argument(
        "--platform",
        default="",
        help="按平台过滤，例如 chatgpt / grok / cursor",
    )
    parser.add_argument(
        "--status",
        default="",
        help="按状态过滤，例如 registered / trial / subscribed",
    )
    parser.add_argument(
        "--format",
        choices=("csv", "txt"),
        default="csv",
        help="导出格式，默认 csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="输出文件路径；不传则自动生成到项目根目录",
    )
    parser.add_argument(
        "--include-token",
        action="store_true",
        help="导出时额外包含 token 列",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只检查并显示导出数量，不写入文件",
    )
    return parser


def normalize_output_path(args: argparse.Namespace) -> Path:
    """根据格式和时间生成默认输出路径。"""
    if args.output is not None:
        return args.output.resolve()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = ".csv" if args.format == "csv" else ".txt"
    return (ROOT / f"accounts_passwords_{timestamp}{suffix}").resolve()


def load_rows(
    db_path: Path,
    platform: str,
    status: str,
    include_token: bool,
) -> list[sqlite3.Row]:
    """从 SQLite 中读取账号记录。"""
    if not db_path.exists():
        raise FileNotFoundError(f"数据库文件不存在: {db_path}")

    columns = ["platform", "email", "password", "status", "created_at"]
    if include_token:
        columns.insert(3, "token")

    sql = f"SELECT {', '.join(columns)} FROM accounts"
    where_parts: list[str] = []
    params: list[str] = []

    if platform.strip():
        where_parts.append("platform = ?")
        params.append(platform.strip())
    if status.strip():
        where_parts.append("status = ?")
        params.append(status.strip())

    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    sql += " ORDER BY platform ASC, email ASC"

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return list(conn.execute(sql, params).fetchall())
    finally:
        conn.close()


def export_csv(output_path: Path, rows: list[sqlite3.Row]) -> None:
    """将账号记录导出为 CSV。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else [
        "platform",
        "email",
        "password",
        "status",
        "created_at",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def export_txt(output_path: Path, rows: list[sqlite3.Row]) -> None:
    """将账号记录导出为 TXT，每行一条。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        for row in rows:
            row_dict = dict(row)
            # TXT 走简单结构，方便肉眼查看和后续脚本处理。
            parts = [
                str(row_dict.get("platform", "") or ""),
                str(row_dict.get("email", "") or ""),
                str(row_dict.get("password", "") or ""),
            ]
            if "token" in row_dict:
                parts.append(str(row_dict.get("token", "") or ""))
            parts.extend(
                [
                    str(row_dict.get("status", "") or ""),
                    str(row_dict.get("created_at", "") or ""),
                ]
            )
            file.write("\t".join(parts) + "\n")


def print_summary(
    rows: list[sqlite3.Row],
    db_path: Path,
    platform: str,
    status: str,
    output_path: Path | None,
    dry_run: bool,
) -> None:
    """输出本次导出的概要信息。"""
    print(f"数据库: {db_path.resolve()}")
    print(f"平台过滤: {platform or '全部'}")
    print(f"状态过滤: {status or '全部'}")
    print(f"记录数量: {len(rows)}")
    if dry_run:
        print("模式: dry-run（未写入文件）")
        return
    if output_path is not None:
        print(f"导出文件: {output_path}")


def main() -> int:
    """脚本主入口。"""
    parser = build_parser()
    args = parser.parse_args()

    try:
        rows = load_rows(
            db_path=args.db.resolve(),
            platform=args.platform,
            status=args.status,
            include_token=args.include_token,
        )
    except Exception as exc:
        print(f"导出失败: {exc}")
        return 1

    output_path = None if args.dry_run else normalize_output_path(args)
    print_summary(
        rows=rows,
        db_path=args.db,
        platform=args.platform,
        status=args.status,
        output_path=output_path,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        return 0

    try:
        if args.format == "csv":
            export_csv(output_path, rows)
        else:
            export_txt(output_path, rows)
    except Exception as exc:
        print(f"写入失败: {exc}")
        return 1

    print("导出完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
