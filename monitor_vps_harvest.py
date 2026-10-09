#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monitor_vps_harvest.py
======================
Токио дахь VPS (minii_server) дээр ажиллаж буй тендерийн оролцогчдын
таталтын явцыг бодит цаг хугацаанд дэлгэц дээр харуулах, баазыг татаж авах скрипт.
"""

import sys
import json
import time
import subprocess
import argparse

def get_vps_status():
    cmd = ["ssh", "minii_server", "cat /root/tender_harvester/harvest_status.json 2>/dev/null"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        try:
            return json.loads(res.stdout.strip())
        except Exception:
            return None
    return None

def sync_db_to_local():
    print("🔄 VPS дээрх сүүлийн үеийн tender_bidders.db баазыг локал компьютер луу татаж байна...")
    cmd = ["rsync", "-avz", "--progress", "minii_server:/root/tender_harvester/tender_bidders.db", "."]
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("✅ Амжилттай татаж авлаа!")
    else:
        print("❌ Алдаа гарлаа!")

def main():
    parser = argparse.ArgumentParser(description="Monitor VPS tender harvest")
    parser.add_argument("--sync", action="store_true", help="Sync database from VPS to local")
    parser.add_argument("--watch", action="store_true", help="Watch progress continuously")
    args = parser.parse_args()

    if args.sync:
        sync_db_to_local()
        return

    print("📡 VPS (Tokyo) Тендерийн оролцогчдыг татах процессын төлөв:")
    print("=" * 80)

    try:
        while True:
            st = get_vps_status()

            if not st:
                print("⚠️  Сервер дээр процесс ажиллаагүй эсвэл холболт амжилтгүй байна.")
            else:
                pct = st.get("progress_percent", 0)
                done = st.get("processed_tenders", 0)
                total = st.get("total_tenders", 0)
                speed = st.get("speed_per_second", 0)
                eta = st.get("eta", "N/A")
                err = st.get("total_errors", 0)
                is_running = st.get("is_running", False)
                bidders = st.get("total_bidders", 0)
                winners = st.get("total_winners", 0)
                losers = st.get("total_losers", 0)

                status_emoji = "🟢 Ажиллаж байна" if is_running else "⏹️ Дууссан"

                sys.stdout.write("\033[K")
                line1 = (
                    f"[{pct:5.2f}%] Тендер: {done:,}/{total:,} | "
                    f"Хурд: {speed:4.1f}/сек | Үлдсэн хугацаа: {eta} | {status_emoji}\n"
                )
                line2 = (
                    f"👥 Шинээр бүртгэсэн: {bidders:,} | "
                    f"🔴 Хасагдсан: {losers:,} | "
                    f"🟢 Шалгарсан: {winners:,} | "
                    f"⚠️ Алдаа: {err}\n"
                )
                sys.stdout.write(line1)
                sys.stdout.write(line2)

            if not args.watch:
                break
            time.sleep(3)
            sys.stdout.write("\033[F\033[F")
            sys.stdout.flush()

    except KeyboardInterrupt:
        print("\nХяналтыг зогсоолоо.")

if __name__ == "__main__":
    main()
