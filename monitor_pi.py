#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monitor_pi.py
=============
Raspberry Pi 4 болон CM5 дээрх тендерийн 24/7 таталтын явцыг
Mac компьютерээсээ шууд хянах, SQLite баазыг татаж авах хэрэгсэл.
"""

import sys
import json
import time
import subprocess
import argparse

TARGETS = {
    "pi4": {
        "title": "Raspberry Pi 4 (MobiCom Hotspot 24/7)",
        "host": "100.70.235.57",
        "user": "root",
        "dir": "/root/tender_harvester",
        "key": "/Users/enkhbadraltsogbayar/.ssh/id_ed25519_vps",
    },
    "cm5": {
        "title": "Raspberry Pi Compute Module 5 (NVMe SSD)",
        "host": "100.104.239.29",
        "user": "maaraa",
        "dir": "/home/maaraa/tender_harvester",
        "key": "/Users/enkhbadraltsogbayar/.ssh/id_ed25519_vps",
    }
}

def get_status(cfg):
    cmd = [
        "ssh", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no",
        "-i", cfg["key"], f"{cfg['user']}@{cfg['host']}",
        f"cat {cfg['dir']}/harvest_status.json 2>/dev/null"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and res.stdout.strip():
        try:
            return json.loads(res.stdout.strip())
        except Exception:
            return None
    return None

def sync_db(cfg):
    print(f"🔄 {cfg['title']} төхөөрөмжөөс tender_bidders.db баазыг Mac луу татаж байна...")
    cmd = [
        "rsync", "-avz", "--progress",
        "-e", f"ssh -i {cfg['key']} -o StrictHostKeyChecking=no",
        f"{cfg['user']}@{cfg['host']}:{cfg['dir']}/tender_bidders.db", "."
    ]
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("✅ Баазыг амжилттай татаж нэгтгэлээ!")
    else:
        print("❌ Татахад алдаа гарлаа!")

def format_bar(pct, width=25):
    filled = int(width * (pct / 100))
    return f"[{'█' * filled}{'░' * (width - filled)}] {pct:5.1f}%"

def main():
    parser = argparse.ArgumentParser(description="Monitor Pi4 / CM5 Tender Harvester")
    parser.add_argument("--cm5", action="store_true", help="CM5 төхөөрөмжийг хянах")
    parser.add_argument("--sync", action="store_true", help="Баазыг Mac луу татаж авах")
    parser.add_argument("--watch", action="store_true", default=True, help="Тасралтгүй харах")
    args = parser.parse_args()

    cfg = TARGETS["cm5"] if args.cm5 else TARGETS["pi4"]

    if args.sync:
        sync_db(cfg)
        return

    print(f"🍓 {cfg['title']} — 24/7 Тендер таталтын хяналт:")
    print("=" * 80)

    try:
        while True:
            st = get_status(cfg)
            if not st:
                sys.stdout.write("\033[K")
                print(f"⏳ {cfg['title']}-аас хариу хүлээж байна (сервис түр завсарласан эсвэл эхлээгүй)...")
            else:
                pct = st.get("progress_percent", 0.0)
                done = st.get("processed_tenders", 0)
                total = st.get("total_tenders", 103523)
                speed = st.get("speed_per_second", 0.0)
                eta = st.get("eta", "--:--:--")
                err = st.get("total_errors", 0)
                is_running = st.get("is_running", False)
                bidders = st.get("total_bidders", 0)
                winners = st.get("total_winners", 0)
                losers = st.get("total_losers", 0)
                updated_at = st.get("updated_at", "")

                status_emoji = "🟢 24/7 АЖИЛЛАЖ БАЙНА" if is_running else "⚪ ТҮР ЗОГССОН"

                sys.stdout.write("\033[K")
                line1 = (
                    f"Явц: {format_bar(pct, 25)} | "
                    f"Тендер: {done:,}/{total:,} | "
                    f"Хурд: {speed:3.1f}/с | ETA: {eta} | {status_emoji}\n"
                )
                line2 = (
                    f"👥 Нийт оролцогчид: {bidders:,} | "
                    f"🟢 Шалгарсан: {winners:,} | "
                    f"🔴 Хасагдсан: {losers:,} | "
                    f"⚠️ Алдаа: {err} | {updated_at}\n"
                )
                sys.stdout.write(line1)
                sys.stdout.write(line2)

            time.sleep(3)
            sys.stdout.write("\033[F\033[F")
            sys.stdout.flush()

    except KeyboardInterrupt:
        print("\nХяналтыг зогсоолоо.")

if __name__ == "__main__":
    main()
