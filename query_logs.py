#!/usr/bin/env python3
import json
import sqlite3

# 连接到数据库
conn = sqlite3.connect("./hf_downloader.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 检查 system_logs 表是否存在
cursor.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='system_logs';"
)
if not cursor.fetchone():
    print("system_logs 表不存在，可能是因为还没有生成任何系统日志。")
    exit(0)

# 查询最近的系统日志
cursor.execute("SELECT * FROM system_logs ORDER BY created_at DESC LIMIT 5;")
logs = cursor.fetchall()

if not logs:
    print("没有找到系统日志记录。")
else:
    print(f"找到 {len(logs)} 条系统日志记录：\n")
    for log in logs:
        log_id = log["id"]
        log_type = log["log_type"]
        message = log["message"]
        created_at = log["created_at"]

        print(f"ID: {log_id}")
        print(f"类型: {log_type}")
        print(f"消息: {message}")
        print(f"时间: {created_at}")

        if log["details"]:
            try:
                details = json.loads(log["details"])
                print("详情:")
                print(json.dumps(details, indent=2, ensure_ascii=False))
            except:
                print(f"详情: {log['details']}")

        print("-" * 50)

# 关闭连接
conn.close()
