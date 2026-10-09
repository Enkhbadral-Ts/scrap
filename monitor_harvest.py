#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
monitor_harvest.py
==================
Тендерийн бүх оролцогчдыг татах явцыг дэлгэц дээр бодит цагаар (real-time)
хянах, статистик үзүүлэлтүүдийг шууд харуулах хяналтын самбар (Live Dashboard).
"""

import os
import sys
import time
import json
import sqlite3
from datetime import datetime

DB_PATH = "tender_bidders.db"
STATUS_PATH = "harvest_status.json"

def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def format_bar(pct, width=40):
    filled = int(width * (pct / 100))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct:5.1f}%"

def get_db_stats():
    if not os.path.exists(DB_PATH):
        return None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*), SUM(CASE WHEN status LIKE '%Шалгарсан%' THEN 1 ELSE 0 END) FROM tender_bidders;")
        total_bidders, total_winners = c.fetchone()
        total_bidders = total_bidders or 0
        total_winners = total_winners or 0
        total_losers = total_bidders - total_winners
        
        c.execute("SELECT COUNT(DISTINCT company_name) FROM tender_bidders;")
        unique_companies = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*), SUM(CASE WHEN status='OK' THEN 1 ELSE 0 END), SUM(CASE WHEN status='ERROR' THEN 1 ELSE 0 END) FROM tender_sync_log;")
        sync_total, sync_ok, sync_err = c.fetchone()
        sync_total = sync_total or 0
        sync_ok = sync_ok or 0
        sync_err = sync_err or 0
        
        # Top 5 most active bidders
        c.execute("""
            SELECT company_name, COUNT(*) as cnt,
                   SUM(CASE WHEN status LIKE '%Шалгарсан%' THEN 1 ELSE 0 END) as win,
                   SUM(CASE WHEN status NOT LIKE '%Шалгарсан%' THEN 1 ELSE 0 END) as lost
            FROM tender_bidders
            GROUP BY company_name
            ORDER BY cnt DESC
            LIMIT 5;
        """)
        top_active = c.fetchall()
        
        # Recent 3 bidders added
        c.execute("""
            SELECT company_name, status, tender_name, offered_price
            FROM tender_bidders
            ORDER BY id DESC
            LIMIT 3;
        """)
        recent_bidders = c.fetchall()
        
        conn.close()
        return {
            "total_bidders": total_bidders,
            "total_winners": total_winners,
            "total_losers": total_losers,
            "unique_companies": unique_companies,
            "sync_total": sync_total,
            "sync_ok": sync_ok,
            "sync_err": sync_err,
            "top_active": top_active,
            "recent_bidders": recent_bidders
        }
    except Exception:
        return None

def main():
    while True:
        status_data = {}
        if os.path.exists(STATUS_PATH):
            try:
                with open(STATUS_PATH, "r", encoding="utf-8") as f:
                    status_data = json.load(f)
            except Exception:
                pass
                
        db_stats = get_db_stats()
        clear_screen()
        
        print("=" * 80)
        print("          ТЕНДЕРИЙН БҮХ ОРОЛЦОГЧДЫГ ТАТАХ ЯВЦЫН ХЯНАЛТ (LIVE MONITOR)")
        print("=" * 80)
        
        updated_at = status_data.get("updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        is_running = status_data.get("is_running", False)
        status_txt = "🟢 ИДЭВХТЭЙ АЖИЛЛАЖ БАЙНА (RUNNING)" if is_running else "⚪ ТҮР ЗОГССОН / ДУУССАН (IDLE)"
        
        print(f"Төлөв: {status_txt} | Шинэчлэгдсэн: {updated_at}")
        print("-" * 80)
        
        pct = status_data.get("progress_percent", 0.0)
        processed = status_data.get("processed_tenders", db_stats["sync_total"] if db_stats else 0)
        total = status_data.get("total_tenders", 131871)
        speed = status_data.get("speed_per_second", 0.0)
        eta = status_data.get("eta", "--:--:--")
        
        print(f"Тендерийн явц:   {format_bar(pct, 35)}  ({processed:,} / {total:,})")
        print(f"Татах хурд:      {speed} хүсэлт/сек  |  Тооцоолсон дуусах хугацаа (ETA): {eta}")
        print("-" * 80)
        
        if db_stats:
            b_total = db_stats["total_bidders"]
            b_win = db_stats["total_winners"]
            b_lost = db_stats["total_losers"]
            uniq = db_stats["unique_companies"]
            err = db_stats["sync_err"]
            
            print(f"Нийт бүртгэгдсэн оролцогчид:  {b_total:,}")
            print(f"  ├─ Шалгарсан (Ялагчид):     {b_win:,} ({b_win/max(1, b_total)*100:.1f}%)")
            print(f"  ├─ Шалгараагүй / Хасагдсан:  {b_lost:,} ({b_lost/max(1, b_total)*100:.1f}%)")
            print(f"  └─ Давхардаагүй компаниуд:   {uniq:,} ААН")
            print(f"Алдаа гарсан тендерүүд:        {err} (Retry системтэй тул дараа нь автоматаар нөхөгдөнө)")
            print("-" * 80)
            
            if db_stats["top_active"]:
                print("Хамгийн олон тендерт оролцсон компаниуд:")
                for r in db_stats["top_active"]:
                    win_pct = (r[2] / max(1, r[1])) * 100
                    print(f"  • {r[0][:30]:<32} Нийт: {r[1]:>3} | Ялсан: {r[2]:>2} | Хасагдсан: {r[3]:>2} (Ялалтын хувь: {win_pct:.0f}%)")
                print("-" * 80)
                
            if db_stats["recent_bidders"]:
                print("Сүүлд нэмэгдсэн бичлэгүүд:")
                for rb in db_stats["recent_bidders"]:
                    price_str = f"{rb[3]:,.0f}₮" if rb[3] else "Үнэгүй"
                    print(f"  • [{rb[1]}] {rb[0]} - {price_str} ({rb[2][:35]}...)")
                    
        print("=" * 80)
        print("Ctrl + C дарж хяналтын самбараас гарна. (Цуглуулах ажиллагаа цаанаа үргэлжилнэ)")
        
        time.sleep(2)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nХяналтын самбар хаагдлаа.")
