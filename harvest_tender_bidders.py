#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harvest_tender_bidders.py
=========================
Төрийн худалдан авах ажиллагааны цахим системээс (user.tender.gov.mn)
тендерт оролцсон БҮХ компаниуд (Шалгарсан, Шалгараагүй, Хасагдсан, Татгалзсан)
болон хасагдсан үндэслэл, шалтгаан, үнийн саналуудыг алдаагүй, үнэн зөв,
тасарсан ч үргэлжлэх горимоор татан SQLite өгөгдлийн санд хадгалах скрипт.
"""

import sys
import os
import re
import json
import time
import sqlite3
import argparse
import threading
import queue
import concurrent.futures
import subprocess
import random
from datetime import datetime
from bs4 import BeautifulSoup
from curl_cffi import requests

DB_PATH = "tender_bidders.db"
STATUS_JSON_PATH = "harvest_status.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

SESSION_GEN = 0
thread_local = threading.local()

def get_session():
    global SESSION_GEN
    if not hasattr(thread_local, "session") or getattr(thread_local, "gen", -1) != SESSION_GEN:
        thread_local.session = requests.Session(impersonate="chrome120")
        thread_local.gen = SESSION_GEN
    return thread_local.session

def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path, timeout=60.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    cursor.execute("PRAGMA cache_size = -64000;") # 64MB cache
    
    # 1. Sync log table for checkpointing and error tracking
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tender_sync_log (
        inv_id TEXT PRIMARY KEY,
        year INTEGER,
        tender_code TEXT,
        tender_name TEXT,
        client TEXT,
        status TEXT, -- 'OK', 'EMPTY', 'ERROR'
        bidders_count INTEGER DEFAULT 0,
        winners_count INTEGER DEFAULT 0,
        losers_count INTEGER DEFAULT 0,
        error_message TEXT,
        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 2. All tender bidders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tender_bidders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        inv_id TEXT,
        year INTEGER,
        tender_code TEXT,
        tender_name TEXT,
        client TEXT,
        tender_date TEXT,
        lot_name TEXT,
        company_name TEXT,
        entity_id TEXT,
        offered_price REAL,
        discount TEXT,
        guarantee TEXT,
        status TEXT, -- 'Шалгарсан', 'Шалгараагүй', 'Хасагдсан', 'Татгалзсан'
        reason TEXT, -- Үнэлгээний үндэслэл / шалтгаан
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # Indexes for fast querying
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bidders_inv_id ON tender_bidders(inv_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bidders_company ON tender_bidders(company_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bidders_entity ON tender_bidders(entity_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bidders_status ON tender_bidders(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bidders_year ON tender_bidders(year);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_status ON tender_sync_log(status);")
    
    conn.commit()
    conn.close()

def get_processed_ids(db_path=DB_PATH):
    if not os.path.exists(db_path):
        return set()
    conn = sqlite3.connect(db_path, timeout=60.0)
    cursor = conn.cursor()
    cursor.execute("SELECT inv_id FROM tender_sync_log WHERE status IN ('OK', 'EMPTY');")
    processed = {row[0] for row in cursor.fetchall()}
    conn.close()
    return processed

def parse_bidder_row(row, tender_meta):
    if not isinstance(row, list) or len(row) < 4:
        return None
    raw_comp = row[0].strip() if isinstance(row[0], str) else ""
    if not raw_comp or "Санал ирүүлсэн оролцогч байхгүй" in raw_comp:
        return None
        
    lot_name = row[1].strip() if len(row) > 1 and isinstance(row[1], str) else ""
    
    # entity link / id
    link_html = row[3] if len(row) > 3 and isinstance(row[3], str) else ""
    entity_id = ""
    em = re.search(r'/mn/bidder/entity/(\d+)', link_html)
    if em:
        entity_id = em.group(1)
        
    # offered price
    amt_html = row[4] if len(row) > 4 and isinstance(row[4], str) else ""
    amt_clean = re.sub(r'[^\d.]', '', BeautifulSoup(amt_html, 'html.parser').text if '<' in amt_html else amt_html)
    offered_price = float(amt_clean) if amt_clean else None
    
    # discount
    disc_html = row[5] if len(row) > 5 and isinstance(row[5], str) else ""
    discount = BeautifulSoup(disc_html, 'html.parser').text.strip() if '<' in disc_html else disc_html.strip()
    
    # guarantee
    guar_html = row[6] if len(row) > 6 and isinstance(row[6], str) else ""
    guarantee = BeautifulSoup(guar_html, 'html.parser').text.strip() if '<' in guar_html else guar_html.strip()
    
    # status
    st_html = row[7] if len(row) > 7 and isinstance(row[7], str) else ""
    status = BeautifulSoup(st_html, 'html.parser').text.strip() if '<' in st_html else st_html.strip()
    if not status:
        status = "Тодорхойгүй"
        
    # reason / evaluation note
    reason = row[8].strip() if len(row) > 8 and isinstance(row[8], str) else ""
    
    return {
        "inv_id": str(tender_meta.get("inv_id", "")),
        "year": tender_meta.get("year", 0),
        "tender_code": str(tender_meta.get("tender_code", "")),
        "tender_name": str(tender_meta.get("tender_name", "")),
        "client": str(tender_meta.get("client", "")),
        "tender_date": str(tender_meta.get("date", "")),
        "lot_name": lot_name,
        "company_name": raw_comp,
        "entity_id": entity_id,
        "offered_price": offered_price,
        "discount": discount,
        "guarantee": guarantee,
        "status": status,
        "reason": reason
    }

import random

pause_lock = threading.Lock()
pause_event = threading.Event()
pause_event.set()
AUTO_ROTATE_CELLULAR = False

def rotate_cellular_ip():
    global SESSION_GEN
    try:
        sys.stdout.write("\n🔄 [AUTO-IP ROTATE] 4G Модемийг Airplane горимд шилжүүлж шинэ IP авч байна...\n")
        sys.stdout.flush()
        subprocess.run(['sudo', 'qmicli', '-p', '-d', '/dev/cdc-wdm0', '--dms-set-operating-mode=low-power'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        time.sleep(4)
        subprocess.run(['sudo', 'qmicli', '-p', '-d', '/dev/cdc-wdm0', '--dms-set-operating-mode=online'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        time.sleep(5)
        subprocess.run(['sudo', 'nmcli', 'connection', 'up', 'MobiCom'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        time.sleep(2)
        new_ip = subprocess.getoutput('curl --max-time 10 -s -4 https://icanhazip.com || curl --max-time 10 -s -4 https://api.ipify.org').strip()
        SESSION_GEN += 1
        sys.stdout.write(f"✅ [NEW IP] Шинэ IP амжилттай авлаа: {new_ip}\n")
        sys.stdout.flush()
        return True
    except Exception as e:
        sys.stdout.write(f"⚠️  [IP ROTATE ERROR] {e}\n")
        sys.stdout.flush()
        return False

def handle_rate_limit(code, msg=""):
    with pause_lock:
        if pause_event.is_set():
            pause_event.clear()
            sys.stdout.write(f"\n⚠️  [RATE LIMIT / PROTECTION {code}] Серверээс түр шалгалт/хязгаарлалт илэрлээ!\n")
            sys.stdout.flush()
            if AUTO_ROTATE_CELLULAR:
                # 403 илэрмэгц шууд модемоороо шинэ IP авна
                rotate_cellular_ip()
                time.sleep(3)
            else:
                cooldown = 120
                sys.stdout.write(f"{cooldown} сек амрааж байна...\n")
                sys.stdout.write("💡 [ЗӨВЛӨМЖ] Хэрэв Мобайл дата ашиглаж байгаа бол утсан дээрээ Нислэгийн горим (Airplane mode)-ыг 3 сек асаагаад унтраавал шууд шинэ IP авна.\n")
                sys.stdout.flush()
                time.sleep(cooldown)
            pause_event.set()
            sys.stdout.write("✅ [RESUMED] Шинэ IP дээр таталтыг шууд үргэлжлүүлж байна.\n")
            sys.stdout.flush()

def fetch_single_tender(tender_meta, retries=10):
    inv_id = str(tender_meta["inv_id"]).strip()
    url = "https://user.tender.gov.mn/mn/result/detail/bidderList"
    payload = {
        "invitationId": inv_id,
        "groupBy": "tender"
    }
    
    req_headers = {
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Origin': 'https://user.tender.gov.mn',
        'Referer': f'https://user.tender.gov.mn/mn/result/detail?invitationId={inv_id}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    for attempt in range(retries):
        # Wait if paused due to rate limiting
        pause_event.wait()
        # Random jitter to look human and avoid traffic spikes
        time.sleep(random.uniform(0.5, 1.5))
        
        try:
            s = get_session()
            r = s.post(url, data=payload, headers=req_headers, timeout=20)
            
            if r.status_code in [403, 429]:
                # 403 эсвэл 429 бол блок / лимит тул шууд IP сэлгээд дахин оролдоно
                handle_rate_limit(r.status_code, "Cloudflare / Rate Limit")
                time.sleep(3 + attempt * 2)
                continue
            elif r.status_code != 200:
                time.sleep(2 + attempt * 2)
                continue
                
            resp_json = r.json()
            raw_rows = resp_json.get("data", [])
            
            parsed_bidders = []
            for row in raw_rows:
                b = parse_bidder_row(row, tender_meta)
                if b:
                    parsed_bidders.append(b)
                    
            winners_count = sum(1 for b in parsed_bidders if "Шалгарсан" in b["status"])
            losers_count = len(parsed_bidders) - winners_count
            
            return {
                "inv_id": inv_id,
                "status": "OK" if parsed_bidders else "EMPTY",
                "bidders": parsed_bidders,
                "bidders_count": len(parsed_bidders),
                "winners_count": winners_count,
                "losers_count": losers_count,
                "error": None
            }
        except Exception:
            time.sleep(2)
            
    return {
        "inv_id": inv_id,
        "status": "ERROR",
        "bidders": [],
        "bidders_count": 0,
        "winners_count": 0,
        "losers_count": 0,
        "error": f"Failed after {retries} retries"
    }


def db_writer_thread(write_queue, stop_event, db_path=DB_PATH):
    """
    Dedicated single-thread SQLite writer to eliminate any lock contention
    and maximize high-throughput batch inserts.
    """
    conn = sqlite3.connect(db_path, timeout=60.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = NORMAL;")
    
    batch_sync = []
    batch_bidders = []
    last_commit_time = time.time()
    
    while not stop_event.is_set() or not write_queue.empty():
        try:
            item = write_queue.get(timeout=0.2)
            meta = item["meta"]
            res = item["res"]
            
            batch_sync.append((
                res["inv_id"],
                meta.get("year", 0),
                meta.get("tender_code", ""),
                meta.get("tender_name", ""),
                meta.get("client", ""),
                res["status"],
                res["bidders_count"],
                res["winners_count"],
                res["losers_count"],
                res["error"]
            ))
            
            for b in res["bidders"]:
                batch_bidders.append((
                    b["inv_id"],
                    b["year"],
                    b["tender_code"],
                    b["tender_name"],
                    b["client"],
                    b["tender_date"],
                    b["lot_name"],
                    b["company_name"],
                    b["entity_id"],
                    b["offered_price"],
                    b["discount"],
                    b["guarantee"],
                    b["status"],
                    b["reason"]
                ))
                
            write_queue.task_done()
            
            # Commit when batch reaches 100 items or 2 seconds elapsed
            if len(batch_sync) >= 100 or (time.time() - last_commit_time > 2.0 and batch_sync):
                cursor.executemany("""
                INSERT OR REPLACE INTO tender_sync_log (
                    inv_id, year, tender_code, tender_name, client,
                    status, bidders_count, winners_count, losers_count, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, batch_sync)
                
                if batch_bidders:
                    cursor.executemany("""
                    INSERT INTO tender_bidders (
                        inv_id, year, tender_code, tender_name, client, tender_date,
                        lot_name, company_name, entity_id, offered_price, discount,
                        guarantee, status, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, batch_bidders)
                    
                conn.commit()
                batch_sync.clear()
                batch_bidders.clear()
                last_commit_time = time.time()
                
        except queue.Empty:
            if batch_sync:
                cursor.executemany("""
                INSERT OR REPLACE INTO tender_sync_log (
                    inv_id, year, tender_code, tender_name, client,
                    status, bidders_count, winners_count, losers_count, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, batch_sync)
                if batch_bidders:
                    cursor.executemany("""
                    INSERT INTO tender_bidders (
                        inv_id, year, tender_code, tender_name, client, tender_date,
                        lot_name, company_name, entity_id, offered_price, discount,
                        guarantee, status, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, batch_bidders)
                conn.commit()
                batch_sync.clear()
                batch_bidders.clear()
                last_commit_time = time.time()
                
    # Final flush
    if batch_sync:
        cursor.executemany("""
        INSERT OR REPLACE INTO tender_sync_log (
            inv_id, year, tender_code, tender_name, client,
            status, bidders_count, winners_count, losers_count, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, batch_sync)
        if batch_bidders:
            cursor.executemany("""
            INSERT INTO tender_bidders (
                inv_id, year, tender_code, tender_name, client, tender_date,
                lot_name, company_name, entity_id, offered_price, discount,
                guarantee, status, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, batch_bidders)
        conn.commit()
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Harvest all tender participants from tender.gov.mn")
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025, 2023, 2022, 2021],
                        help="Years to process (e.g. 2024 2025). Default: 2021 to 2025")
    parser.add_argument("--workers", type=int, default=2, help="Number of concurrent workers (default: 2)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tenders to process (for testing)")
    parser.add_argument("--auto-rotate-cellular", action="store_true", help="Automatically rotate cellular 4G IP on 403 / Cloudflare challenge")
    args = parser.parse_args()
    
    global AUTO_ROTATE_CELLULAR
    if args.auto_rotate_cellular:
        AUTO_ROTATE_CELLULAR = True
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 4G SIM Auto-IP Rotation is ENABLED.")
        
    init_db(DB_PATH)
    processed_ids = get_processed_ids(DB_PATH)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Database initialized. Found {len(processed_ids):,} already processed tenders.")
    
    # Load all tenders for selected years
    all_tenders = []
    for y in args.years:
        cache_file = f"tenders_{y}_links_cache.json"
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                items = json.load(f)
                for item in items:
                    item["year"] = y
                    all_tenders.append(item)
        else:
            print(f"Warning: {cache_file} not found. Skipping year {y}.")
            
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Loaded {len(all_tenders):,} tenders from cache files for years: {args.years}")
    
    # Filter pending tenders
    pending = [t for t in all_tenders if str(t["inv_id"]).strip() not in processed_ids]
    if args.limit:
        pending = pending[:args.limit]
        
    total_to_process = len(pending)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Remaining to harvest: {total_to_process:,} tenders.")
    
    if total_to_process == 0:
        print("All tenders are already harvested! Exiting.")
        return
        
    write_queue = queue.Queue(maxsize=2000)
    stop_event = threading.Event()
    writer_thread = threading.Thread(target=db_writer_thread, args=(write_queue, stop_event, DB_PATH), daemon=True)
    writer_thread.start()
    
    start_time = time.time()
    done_count = 0
    total_bidders = 0
    total_winners = 0
    total_losers = 0
    total_errors = 0
    
    def worker_task(meta):
        res = fetch_single_tender(meta)
        write_queue.put({"meta": meta, "res": res})
        return res
        
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting harvester with {args.workers} workers...")
    print("-" * 80)
    
    last_status_write = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(worker_task, meta): meta for meta in pending}
        
        for future in concurrent.futures.as_completed(futures):
            done_count += 1
            try:
                res = future.result()
                if res["status"] == "ERROR":
                    total_errors += 1
                else:
                    total_bidders += res["bidders_count"]
                    total_winners += res["winners_count"]
                    total_losers += res["losers_count"]
            except Exception as e:
                total_errors += 1
                
            elapsed = time.time() - start_time
            speed = done_count / elapsed if elapsed > 0 else 0
            rem_sec = (total_to_process - done_count) / speed if speed > 0 else 0
            eta_m, eta_s = divmod(int(rem_sec), 60)
            eta_h, eta_m = divmod(eta_m, 60)
            eta_str = f"{eta_h:02d}:{eta_m:02d}:{eta_s:02d}"
            pct = (done_count / total_to_process) * 100
            
            # Print live progress every 20 items or at completion
            if done_count % 20 == 0 or done_count == total_to_process:
                status_line = (
                    f"\r[{pct:5.1f}%] {done_count:,}/{total_to_process:,} | "
                    f"Speed: {speed:4.1f}/s | ETA: {eta_str} | "
                    f"Bidders: {total_bidders:,} (Win:{total_winners:,}, Lost:{total_losers:,}) | "
                    f"Err: {total_errors}"
                )
                sys.stdout.write(status_line)
                sys.stdout.flush()
                
            # Periodic auto-cooling every 300 tenders
            if done_count > 0 and done_count % 300 == 0:
                cooling_time = 10 if AUTO_ROTATE_CELLULAR else 60
                sys.stdout.write(f"\n❄️  [AUTO-COOLING] 300 тендер амжилттай татлаа ({cooling_time} сек амралт)...\n")
                sys.stdout.flush()
                time.sleep(cooling_time)
                
            # Update harvest_status.json every 5 seconds for external monitoring
            if time.time() - last_status_write > 5.0 or done_count == total_to_process:
                last_status_write = time.time()
                status_payload = {
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "total_tenders": total_to_process,
                    "processed_tenders": done_count,
                    "progress_percent": round(pct, 2),
                    "speed_per_second": round(speed, 1),
                    "eta": eta_str,
                    "elapsed_seconds": round(elapsed, 1),
                    "total_bidders": total_bidders,
                    "total_winners": total_winners,
                    "total_losers": total_losers,
                    "total_errors": total_errors,
                    "is_running": done_count < total_to_process
                }
                with open(STATUS_JSON_PATH, "w", encoding="utf-8") as sf:
                    json.dump(status_payload, sf, indent=2, ensure_ascii=False)
                    
    print("\n" + "=" * 80)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Scraping requests completed. Finalizing database writes...")
    stop_event.set()
    writer_thread.join()
    
    elapsed_total = time.time() - start_time
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ALL DONE!")
    print(f"Total time elapsed: {int(elapsed_total // 60)}m {int(elapsed_total % 60)}s")
    print(f"Tenders processed: {done_count:,}")
    print(f"Total Bidders recorded: {total_bidders:,}")
    print(f"  - Winners: {total_winners:,}")
    print(f"  - Losers / Disqualified: {total_losers:,}")
    print(f"Errors: {total_errors}")
    print(f"Saved into SQLite database: {DB_PATH}")

if __name__ == "__main__":
    main()
