#!/usr/bin/env python3
"""
egazar_collector.py - egazar.gov.mn газрын нэгж талбар болон эзэмшигчдийн өгөгдөл цуглуулагч
Бүх 21 аймаг болон нийслэлийн 9 дүүргийн газрын датаг GeoServer WFS болон Detail API-аар татаж SQLite-д хадгална.

Онцлогууд:
- Rate Limiting (Token Bucket) - Серверийг унагахгүй, IP block хийлгэхгүй
- Auto Cooldown & Exponential Backoff - HTTP 429 Too Many Requests үед түр амарч өөрөө сэргэнэ
- Incremental Daily Sync - Өдөр тутам шинээр олгогдсон, шилжсэн газруудыг л ялгаж татна
- Cross-matching - burtgel_les.db (270k компани)-тэй шууд тулгана
"""

import sys
import os
import time
import json
import sqlite3
import argparse
import base64
import random
import threading
import urllib.parse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from bs4 import BeautifulSoup

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "egazar.db")

USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
]

AIMAG_LIST = [
    ("011", "Улаанбаатар"),
    ("021", "Дорнод"),
    ("022", "Сүхбаатар"),
    ("023", "Хэнтий"),
    ("041", "Төв"),
    ("042", "Говьсүмбэр"),
    ("043", "Сэлэнгэ"),
    ("044", "Дорноговь"),
    ("045", "Дархан-Уул"),
    ("046", "Өмнөговь"),
    ("048", "Дундговь"),
    ("061", "Орхон"),
    ("062", "Өвөрхангай"),
    ("063", "Булган"),
    ("064", "Баянхонгор"),
    ("065", "Архангай"),
    ("067", "Хөвсгөл"),
    ("081", "Завхан"),
    ("082", "Говь-Алтай"),
    ("083", "Баян-Өлгий"),
    ("084", "Ховд"),
    ("085", "Увс"),
]

UB_DISTRICTS = [
    ("01101", "Багануур"),
    ("01104", "Багахангай"),
    ("01107", "Баянгол"),
    ("01110", "Баянзүрх"),
    ("01113", "Налайх"),
    ("01116", "Сонгинохайрхан"),
    ("01119", "Сүхбаатар"),
    ("01122", "Хан-Уул"),
    ("01125", "Чингэлтэй"),
]


class RateLimiter:
    """Хүсэлтийн хурдыг барьж, 429 алдаа ирвэл бүх урсгалыг түр амраах тооцоолуур"""
    def __init__(self, max_per_second=15):
        self.max_per_second = max(1.0, float(max_per_second))
        self.lock = threading.Lock()
        self.last_check = time.time()
        self.tokens = self.max_per_second
        self.cooldown_until = 0.0

    def wait_for_token(self):
        while True:
            now = time.time()
            with self.lock:
                if now < self.cooldown_until:
                    wait_time = self.cooldown_until - now
                else:
                    elapsed = now - self.last_check
                    self.last_check = now
                    self.tokens = min(self.max_per_second, self.tokens + elapsed * self.max_per_second)
                    if self.tokens >= 1.0:
                        self.tokens -= 1.0
                        return
                    wait_time = (1.0 - self.tokens) / self.max_per_second
            time.sleep(max(0.01, min(1.0, wait_time)))

    def trigger_cooldown(self, seconds=10):
        with self.lock:
            now = time.time()
            target = now + seconds
            if target > self.cooldown_until:
                self.cooldown_until = target
                self.tokens = 0.0
                print(f"\n[!] ⚠️ Серверээс Rate Limit (429/503) ирлээ. Бүх урсгал {seconds:.1f} сек амарч байна...", flush=True)


def init_db(db_path=DB_PATH):
    """SQLite баазын хүснэгт, индексүүдийг үүсгэх"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode = WAL;")
    cur.execute("PRAGMA synchronous = NORMAL;")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS aimags (
            code TEXT PRIMARY KEY,
            name TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS soums (
            code TEXT PRIMARY KEY,
            aimag_code TEXT,
            name TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS parcels (
            parcel_id TEXT PRIMARY KEY,
            soum_code TEXT,
            landuse INTEGER,
            area_m2 REAL,
            address_streetname TEXT,
            description TEXT,
            valid_from TEXT,
            owner_name TEXT,
            org_type TEXT,
            register_no TEXT,
            rights_type TEXT,
            property_cert_no TEXT,
            status TEXT DEFAULT 'pending', -- pending, done, no_detail, error
            updated_at TEXT
        );
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_parcels_soum ON parcels(soum_code);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_parcels_status ON parcels(status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_parcels_landuse ON parcels(landuse);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_parcels_owner ON parcels(owner_name);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_parcels_reg ON parcels(register_no);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_parcels_valid_from ON parcels(valid_from);")

    cur.executemany("INSERT OR IGNORE INTO aimags(code, name) VALUES (?, ?);", AIMAG_LIST)
    cur.executemany("INSERT OR IGNORE INTO soums(code, aimag_code, name) VALUES (?, '011', ?);", UB_DISTRICTS)

    conn.commit()
    conn.close()


class EgazarSession:
    """egazar.gov.mn session ба CSRF токен зохицуулагч"""
    def __init__(self):
        self.session = requests.Session()
        self.ua = random.choice(USER_AGENTS)
        self.session.headers.update({
            'User-Agent': self.ua,
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://egazar.gov.mn/map',
            'Origin': 'https://egazar.gov.mn',
        })
        self.xsrf_token = None
        self.refresh_token()

    def refresh_token(self):
        for _ in range(3):
            try:
                r = self.session.get('https://egazar.gov.mn/map', timeout=15)
                cookie_val = self.session.cookies.get('XSRF-TOKEN')
                if cookie_val:
                    self.xsrf_token = urllib.parse.unquote(cookie_val)
                    self.session.headers.update({
                        'X-XSRF-TOKEN': self.xsrf_token,
                        'X-Requested-With': 'XMLHttpRequest'
                    })
                    return True
            except Exception as e:
                time.sleep(1.0)
        return False


def fetch_geo_parcels(soum_code, till_date=None, cql_extra=None):
    """GeoServer WFS-ээр тухайн сум/дүүргийн бүх нэгж талбарын ID, талбай, зориулалтыг татах"""
    if till_date is None:
        till_date = datetime.now().strftime("%Y-%m-%d")

    base_wfs = "https://geoserver.egazar.gov.mn/geoserver/ows"
    params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": "geoware:geo_view_parcel_soum_egazar",
        "viewparams": f"code:{soum_code};date:{till_date}",
        "propertyName": "parcel_id,area_m2,landuse,address_streetname,description,valid_from",
        "maxFeatures": 100000,
        "outputFormat": "application/json"
    }
    if cql_extra:
        params["cql_filter"] = cql_extra

    headers = {'User-Agent': random.choice(USER_AGENTS)}
    
    try:
        r = requests.get(base_wfs, params=params, headers=headers, timeout=60)
        data = r.json()
        features = data.get('features', [])
    except Exception as e:
        print(f"[!] {soum_code} WFS татахад алдаа: {e}")
        return []

    # Хэрэв 100,000-ын хязгаар тулсан бол landuse-ээр нарийн салгаж авна
    if len(features) >= 100000 and not cql_extra:
        print(f"[*] {soum_code} 100,000 хязгаар тулсан (totalFeatures илүү байна), landuse хуваалтаар гүйцээнэ...")
        extra_features = []
        # Илүү нарийн хуваалт: 6 бүлгээр авна (2 бүлэг хүрэлцэхгүй тохиолдол байна)
        landuse_ranges = [
            "landuse < 1200",
            "landuse >= 1200 AND landuse < 2200",
            "landuse >= 2200 AND landuse < 3200",
            "landuse >= 3200 AND landuse < 5200",
            "landuse >= 5200 AND landuse < 7200",
            "landuse >= 7200",
            "landuse IS NULL",
        ]
        for cql in landuse_ranges:
            p = params.copy()
            p["cql_filter"] = cql
            try:
                r_cql = requests.get(base_wfs, params=p, headers=headers, timeout=120)
                batch = r_cql.json().get('features', [])
                extra_features.extend(batch)
                if len(batch) >= 100000:
                    print(f"  ⚠️  {cql}: {len(batch)} (бас 100K тулсан! Цааш хуваах хэрэгтэй)")
                else:
                    print(f"  ✅ {cql}: {len(batch)}")
            except Exception as e:
                print(f"[!] CQL {cql} алдаа: {e}")
        if extra_features:
            features = extra_features

    results = []
    seen = set()
    for f in features:
        props = f.get('properties', {})
        pid = str(props.get('parcel_id', '')).strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        results.append((
            pid,
            soum_code,
            props.get('landuse'),
            props.get('area_m2'),
            props.get('address_streetname', ''),
            props.get('description', ''),
            props.get('valid_from', ''),
            'pending'
        ))

    return results


def parse_detail_html(html_str):
    """egazar-ын буцаасан base64 HTML-ээс эзэмшигч болон регистрийн мэдээллийг задлах"""
    soup = BeautifulSoup(html_str, 'html.parser')
    info = {
        'owner_name': None,
        'org_type': None,
        'register_no': None,
        'rights_type': None,
        'property_cert_no': None
    }

    for tr in soup.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) >= 2:
            key = tds[0].get_text(strip=True).replace(':', '')
            val = tds[1].get_text(strip=True)
            if 'Иргэн/Хуулийн этгээд' in key:
                info['owner_name'] = val
            elif 'Хуулийн этгээдийн төрөл' in key:
                info['org_type'] = val
            elif 'Регистрийн дугаар' in key:
                info['register_no'] = val
            elif 'Эрхийн төрөл' in key:
                info['rights_type'] = val
            elif 'Эрхийн улсын бүртгэлийн дугаар' in key or 'Гэрчилгээний дугаар' in key:
                info['property_cert_no'] = val

    return info


def fetch_single_detail(session_wrapper, rate_limiter, parcel_id):
    """RateLimiter болон Auto-Cooldown хамгаалалттай нэг нэгж талбарын detail татах"""
    url = "https://egazar.gov.mn/api/parcel/detail/by/id"
    max_retries = 3

    for attempt in range(max_retries):
        rate_limiter.wait_for_token()
        try:
            res = session_wrapper.session.post(url, data={'id': parcel_id}, timeout=8)
            
            # Rate limit / Server overload хамгаалалт
            if res.status_code in (429, 503, 504):
                cooldown_sec = (attempt + 1) * 6.0 + random.uniform(1.0, 3.0)
                rate_limiter.trigger_cooldown(cooldown_sec)
                time.sleep(cooldown_sec)
                continue

            # CSRF сэлгэх
            if res.status_code == 419:
                session_wrapper.refresh_token()
                time.sleep(0.5)
                continue

            if res.status_code == 200:
                data = res.json()
                if data.get('success') and 'html' in data:
                    html = base64.b64decode(data['html']).decode('utf-8', errors='ignore')
                    parsed = parse_detail_html(html)
                    if not parsed['property_cert_no'] and 'returnJson' in data:
                        try:
                            ret = json.loads(base64.b64decode(data['returnJson']).decode('utf-8'))
                            if isinstance(ret, list) and len(ret) > 0:
                                parsed['property_cert_no'] = ret[0].get('property_no')
                        except:
                            pass
                    return parcel_id, parsed, "done"
                else:
                    return parcel_id, {}, "no_detail"
            else:
                if attempt == max_retries - 1:
                    return parcel_id, {}, f"http_{res.status_code}"

        except Exception as e:
            if attempt == max_retries - 1:
                return parcel_id, {}, "error"
            time.sleep(1.0 + random.uniform(0.2, 0.8))

    return parcel_id, {}, "error"


# ==========================================
# CLI Командууд
# ==========================================

def cmd_init_geo(args):
    """GeoServer-ээс бүх нэгж талбарын суурь бүртгэлийг татаж SQLite-д бэлтгэх"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    soums_to_fetch = []
    if args.soum:
        soums_to_fetch = [(args.soum, f"Сум/Дүүрэг {args.soum}")]
    elif args.target == 'ub':
        soums_to_fetch = UB_DISTRICTS
    elif args.target == 'all':
        cur.execute("SELECT code, name FROM soums;")
        soums_to_fetch = cur.fetchall()
        if not soums_to_fetch:
            soums_to_fetch = UB_DISTRICTS

    print(f"\n=======================================================")
    print(f"🗺️  GeoServer WFS: Суурь нэгж талбарын бүртгэл эхэллээ")
    print(f"   Сум / Дүүргийн тоо: {len(soums_to_fetch)}")
    print(f"   Хадгалах сан: {DB_PATH}")
    print(f"=======================================================\n")

    grand_total = 0
    t_start = time.time()

    for code, name in soums_to_fetch:
        t0 = time.time()
        print(f"📥 [{code}] {name} татаж байна...", end=" ", flush=True)
        parcels = fetch_geo_parcels(code)
        
        if parcels:
            cur.executemany("""
                INSERT OR IGNORE INTO parcels(
                    parcel_id, soum_code, landuse, area_m2, address_streetname, description, valid_from, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, parcels)
            conn.commit()
            dt = time.time() - t0
            print(f"✅ {len(parcels):,} нэгж талбар ({dt:.1f}с)")
            grand_total += len(parcels)
        else:
            print("⚠️ Мэдээлэл олдсонгүй")

    conn.close()
    total_time = time.time() - t_start
    print(f"\n🎉 Бүртгэл амжилттай дууслаа! Нийт: {grand_total:,} нэгж талбар ({total_time:.1f} секунд)")
    print(f"👉 Одоо эзэмшигчдийн нэрийг татахын тулд дараах тушаалыг ажиллуулна уу:")
    print(f"   python3 egazar_collector.py fetch-details --target ub --rate-limit 15 --workers 15\n")


def cmd_sync_daily(args):
    """Өдөр тутам шинээр нэмэгдсэн эсвэл өөрчлөгдсөн газруудыг ялгаж татах (Daily Incremental Sync)"""
    init_db()
    days_back = int(args.days or 1)
    since_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    print(f"\n=======================================================")
    print(f"🔄 EGAZAR ӨДӨР ТУТМЫН ШИНЭЧЛЭЛТ ШАЛГАХ (Сүүлийн {days_back} өдөр: {since_date}-ээс хойш)")
    print(f"=======================================================\n")

    cql_filter = f"valid_from >= '{since_date}'"
    new_count_total = 0
    updated_count_total = 0

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    for scode, sname in UB_DISTRICTS:
        parcels = fetch_geo_parcels(scode, cql_extra=cql_filter)
        if parcels:
            # Аль нь шинэ, аль нь хуучин болохыг ялгах
            pids = [p[0] for p in parcels]
            placeholders = ','.join(['?'] * len(pids))
            cur.execute(f"""
                SELECT parcel_id, landuse, area_m2, valid_from
                FROM parcels WHERE parcel_id IN ({placeholders})
            """, pids)
            existing = {}
            for row in cur.fetchall():
                existing[row[0]] = (row[1], row[2], row[3])

            new_parcels = []
            changed_parcels = []
            skipped = 0

            for p in parcels:
                pid = p[0]
                if pid not in existing:
                    new_parcels.append(p)
                else:
                    old_landuse, old_area, old_valid = existing[pid]
                    new_landuse, new_area, new_valid = p[2], p[3], p[6]
                    if (new_landuse != old_landuse or
                        new_area != old_area or
                        new_valid != old_valid):
                        changed_parcels.append(p)
                    else:
                        skipped += 1

            # Шинэ нэгж талбаруудыг оруулах
            if new_parcels:
                cur.executemany("""
                    INSERT INTO parcels(
                        parcel_id, soum_code, landuse, area_m2, address_streetname, description, valid_from, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, new_parcels)

            # Өөрчлөгдсөн нэгж талбаруудыг шинэчлэх
            if changed_parcels:
                cur.executemany("""
                    INSERT INTO parcels(
                        parcel_id, soum_code, landuse, area_m2, address_streetname, description, valid_from, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(parcel_id) DO UPDATE SET
                        landuse=excluded.landuse,
                        area_m2=excluded.area_m2,
                        valid_from=excluded.valid_from,
                        status='pending';
                """, changed_parcels)

            conn.commit()

            n_new = len(new_parcels)
            n_chg = len(changed_parcels)
            if n_new > 0 or n_chg > 0:
                parts = []
                if n_new > 0:
                    parts.append(f"{n_new} шинэ")
                if n_chg > 0:
                    parts.append(f"{n_chg} өөрчлөгдсөн")
                print(f"  • [{scode}] {sname}: {', '.join(parts)}")
                new_count_total += n_new
                updated_count_total += n_chg

    conn.close()

    if new_count_total == 0 and updated_count_total == 0:
        print("  ✅ Шинэчлэлт олдсонгүй — бүх дата хуучнаараа байна.")
    else:
        parts = []
        if new_count_total > 0:
            parts.append(f"🆕 {new_count_total} шинэ")
        if updated_count_total > 0:
            parts.append(f"🔄 {updated_count_total} өөрчлөгдсөн")
        print(f"\n Нийт: {', '.join(parts)} нэгж талбар баазад бүртгэгдлээ.")

    fetch_needed = new_count_total + updated_count_total
    if fetch_needed > 0 and not args.no_fetch:
        print("🚀 Эзэмшигчдийн дэлгэрэнгүйг шууд татаж эхэлж байна...")
        cmd_fetch_details(args)


def cmd_fetch_details(args):
    """Эзэмшигч, маскалсан регистр, гэрчилгээний дугаарыг Rate Limiter хамгаалалттай татах"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    query = "SELECT parcel_id FROM parcels WHERE status = 'pending'"
    params = []

    if getattr(args, 'soum', None):
        query += " AND soum_code = ?"
        params.append(args.soum)
    elif getattr(args, 'target', None) == 'ub':
        placeholders = ','.join(['?'] * len(UB_DISTRICTS))
        query += f" AND soum_code IN ({placeholders})"
        params.extend([d[0] for d in UB_DISTRICTS])

    if getattr(args, 'commercial_only', False):
        query += " AND (landuse BETWEEN 2100 AND 2199 OR landuse < 2000)"

    if getattr(args, 'limit', None):
        query += f" LIMIT {int(args.limit)}"

    cur.execute(query, params)
    pending_pids = [row[0] for row in cur.fetchall()]
    conn.close()

    total_pending = len(pending_pids)
    if total_pending == 0:
        print("✅ Татах дутуу нэгж талбар олдсонгүй! Бүгд бүрэн татагдсан байна.")
        return

    rate_limit = getattr(args, 'rate_limit', 15) or 15
    workers = getattr(args, 'workers', 15) or 15
    rate_limiter = RateLimiter(max_per_second=rate_limit)

    print(f"\n=======================================================")
    print(f"🏢 Эзэмшигч, Регистр татах ажиллагаа эхэллээ")
    print(f"   Нийт татах тоо:        {total_pending:,}")
    print(f"   Хурдны дээд хязгаар:   {rate_limit} хүсэлт/сек (Rate Limit Protection)")
    print(f"   Зэрэгцээ урсгал:       {workers} workers")
    print(f"   Хадгалах сан:          {DB_PATH}")
    print(f"=======================================================\n")

    session_pool = [EgazarSession() for _ in range(max(2, workers // 3))]
    import itertools
    session_cycle = itertools.cycle(session_pool)

    batch = []
    completed = 0
    success_count = 0
    t_start = time.time()
    last_print = time.time()

    write_conn = sqlite3.connect(DB_PATH)
    write_cur = write_conn.cursor()

    def flush_batch(b):
        nonlocal write_conn, write_cur
        if not b:
            return
        write_cur.executemany("""
            UPDATE parcels SET
                owner_name = ?,
                org_type = ?,
                register_no = ?,
                rights_type = ?,
                property_cert_no = ?,
                status = ?,
                updated_at = ?
            WHERE parcel_id = ?;
        """, b)
        write_conn.commit()

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # Chunked submit - санах ойг дүүргэхгүйгээр 500-аар нь явуулна
            CHUNK_SIZE = 1000
            for i in range(0, total_pending, CHUNK_SIZE):
                chunk = pending_pids[i:i+CHUNK_SIZE]
                future_to_pid = {
                    executor.submit(fetch_single_detail, next(session_cycle), rate_limiter, pid): pid
                    for pid in chunk
                }

                for future in as_completed(future_to_pid):
                    pid, parsed, status = future.result()
                    now_str = datetime.now().isoformat()
                    
                    if status == 'done':
                        success_count += 1
                        batch.append((
                            parsed.get('owner_name'),
                            parsed.get('org_type'),
                            parsed.get('register_no'),
                            parsed.get('rights_type'),
                            parsed.get('property_cert_no'),
                            'done',
                            now_str,
                            pid
                        ))
                    else:
                        batch.append((None, None, None, None, None, status, now_str, pid))

                    completed += 1

                    if len(batch) >= 50:
                        flush_batch(batch)
                        batch = []

                    if time.time() - last_print >= 1.0 or completed == total_pending:
                        elapsed = time.time() - t_start
                        speed = completed / elapsed if elapsed > 0 else 0
                        remain = total_pending - completed
                        eta_sec = remain / speed if speed > 0 else 0
                        eta_str = time.strftime('%H:%M:%S', time.gmtime(eta_sec))
                        pct = (completed / total_pending) * 100

                        print(f"\r⏳ [{pct:5.1f}%] {completed:,}/{total_pending:,} | "
                              f"Хурд: {speed:4.1f} req/s | "
                              f"Олдсон: {success_count:,} | "
                              f"Үлдсэн: {eta_str} ", end="", flush=True)
                        last_print = time.time()

            flush_batch(batch)

    except KeyboardInterrupt:
        print("\n\n⚠️ Хэрэглэгч түр зогсоолоо (Ctrl+C). Одоогийн явц найдвартай хадгалагдлаа!")
        flush_batch(batch)
        write_conn.close()
        return

    write_conn.close()
    total_time = time.time() - t_start
    print(f"\n\n🎉 Дууслаа! Нийт {completed:,} нэгж талбарын эзэмшигчийг {total_time/60:.1f} минутад шалгалаа.")


def cmd_stats(args):
    """Датаны статистик мэдээлэл харуулах"""
    if not os.path.exists(DB_PATH):
        print("Баазын файл олдсонгүй. Эхлээд 'init-geo' тушаалыг ажиллуулна уу.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT count(*) FROM parcels;")
    total = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM parcels WHERE status = 'done';")
    done = cur.fetchone()[0]

    cur.execute("SELECT count(*) FROM parcels WHERE status = 'pending';")
    pending = cur.fetchone()[0]

    cur.execute("SELECT count(DISTINCT owner_name) FROM parcels WHERE owner_name IS NOT NULL;")
    unique_owners = cur.fetchone()[0]

    print("\n========================================")
    print("📊 EGAZAR ӨГӨГДЛИЙН САНГИЙН СТАТИСТИК")
    print("========================================")
    print(f" Нийт бүртгэгдсэн нэгж талбар: {total:,}")
    print(f" Эзэмшигч нь татагдсан (done):  {done:,}")
    print(f" Татагдаагүй үлдсэн (pending): {pending:,}")
    print(f" Нийт бие даасан эзэмшигчид:   {unique_owners:,}")
    print("----------------------------------------")
    print("🏢 Дүүрэг тус бүрээр:")
    cur.execute("""
        SELECT p.soum_code, coalesce(s.name, p.soum_code), count(*), sum(case when p.status='done' then 1 else 0 end)
        FROM parcels p
        LEFT JOIN soums s ON p.soum_code = s.code
        GROUP BY p.soum_code
        ORDER BY count(*) DESC;
    """)
    for scode, sname, cnt, d_cnt in cur.fetchall():
        pct = (d_cnt / cnt * 100) if cnt > 0 else 0
        print(f"  • [{scode}] {sname:15} : {cnt:7,} талбар (Татагдсан: {d_cnt:6,} [{pct:4.1f}%])")

    print("\n🏆 Хамгийн олон нэгж талбар эзэмшдэг ТОП 10 (Татсан өгөгдлөөс):")
    cur.execute("""
        SELECT owner_name, org_type, count(*), sum(area_m2)
        FROM parcels
        WHERE owner_name IS NOT NULL AND trim(owner_name) != ''
        GROUP BY owner_name
        ORDER BY count(*) DESC
        LIMIT 10;
    """)
    rows = cur.fetchall()
    if rows:
        for i, (name, otype, cnt, area) in enumerate(rows, 1):
            area_str = f"{area:,.0f} м²" if area else "Тодорхойгүй"
            print(f"  {i}. {name:30} | {cnt:4} нэгж талбар | Нийт: {area_str}")
    else:
        print("  (Одоогоор эзэмшигчийн нэр татагдаагүй байна)")
    print("========================================\n")
    conn.close()


def cmd_search(args):
    """Эзэмшигчийн нэр эсвэл регистрээр хайх"""
    if not os.path.exists(DB_PATH):
        print("Баазын файл олдсонгүй.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    term = f"%{args.query}%"
    cur.execute("""
        SELECT p.parcel_id, coalesce(s.name, p.soum_code), p.owner_name, p.register_no, 
               p.org_type, p.rights_type, p.area_m2, p.description, p.address_streetname
        FROM parcels p
        LEFT JOIN soums s ON p.soum_code = s.code
        WHERE p.owner_name LIKE ? OR p.register_no LIKE ? OR p.parcel_id LIKE ?
        LIMIT 50;
    """, (term, term, term))
    rows = cur.fetchall()
    conn.close()

    print(f"\n🔍 '{args.query}' хайлтын үр дүн ({len(rows)} илэрц):")
    print("--------------------------------------------------------------------------------")
    for r in rows:
        pid, soum, owner, reg, otype, rights, area, desc, addr = r
        print(f"📍 Нэгж талбар: {pid} | {soum} | {area} м² | {rights or 'Эрх тодорхойгүй'}")
        print(f"   Эзэмшигч: {owner} (Регистр: {reg})")
        print(f"   Төрөл/Зориулалт: {desc or otype} | Хаяг: {addr}")
        print("--------------------------------------------------------------------------------")


def cmd_match_companies(args):
    """burtgel_les.db (270k компани)-тэй тулгаж компанийн нэр дээрх газруудыг илрүүлэх"""
    burtgel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "burtgel_les.db")
    if not os.path.exists(burtgel_path):
        print(f"[!] {burtgel_path} олдсонгүй.")
        return
    if not os.path.exists(DB_PATH):
        print(f"[!] {DB_PATH} олдсонгүй.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f"ATTACH DATABASE '{burtgel_path}' AS burtgel;")

    print("\n=======================================================")
    print("🤝 EGAZAR + BURTGEL_LES ТУЛГАЛТ (Компанийн газрууд)")
    print("=======================================================")

    query = """
        SELECT p.parcel_id, coalesce(s.name, p.soum_code) as district, 
               p.owner_name, c.reg_no, c.form, p.rights_type, p.area_m2, p.description
        FROM parcels p
        JOIN burtgel.companies c ON trim(lower(p.owner_name)) = trim(lower(c.name))
        LEFT JOIN soums s ON p.soum_code = s.code
        WHERE p.status = 'done'
        LIMIT 50;
    """
    cur.execute(query)
    matches = cur.fetchall()

    if not matches:
        print("  Одоогоор яг ижил нэртэй шууд илэрц олдсонгүй (эсвэл компанийн газрын detail татагдаагүй байна).")
    else:
        print(f"🎉 Илэрсэн компанийн газрууд ({len(matches)} ш):")
        print("--------------------------------------------------------------------------------")
        for r in matches:
            pid, dist, name, reg, form, rights, area, desc = r
            print(f"🏢 {name} ({form or 'Компани'}, Регистр: {reg})")
            print(f"   📍 Газар: {pid} | {dist} | {area:,.0f} м² | Эрх: {rights}")
            print(f"   📋 Зориулалт: {desc}")
            print("--------------------------------------------------------------------------------")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="egazar.gov.mn газрын өгөгдөл цуглуулагч")
    subparsers = parser.add_subparsers(dest="command")

    # init-geo
    p_init = subparsers.add_parser("init-geo", help="WFS-ээр нэгж талбарын суурь бүртгэл үүсгэх")
    p_init.add_argument("--target", choices=["ub", "all"], default="ub", help="Хамрах хүрээ (ub: Нийслэл, all: Улс даяар)")
    p_init.add_argument("--soum", help="Зөвхөн тодорхой нэг сум/дүүргийн кодоор (жишээ нь: 01119)")

    # fetch-details
    p_fetch = subparsers.add_parser("fetch-details", help="Эзэмшигчийн нэр, регистрийн мэдээллийг татах")
    p_fetch.add_argument("--target", choices=["ub", "all"], default="ub", help="Хамрах хүрээ")
    p_fetch.add_argument("--soum", help="Зөвхөн тодорхой нэг сум/дүүрэг")
    p_fetch.add_argument("--rate-limit", type=float, default=15.0, help="Секундэд илгээх дээд хурд (Default: 15 req/s)")
    p_fetch.add_argument("--workers", type=int, default=15, help="Зэрэгцээ урсгалын тоо (Default: 15)")
    p_fetch.add_argument("--limit", type=int, help="Туршилтаар цөөн тоогоор татах хязгаар")
    p_fetch.add_argument("--commercial-only", action="store_true", help="Зөвхөн ААН, компани, худалдаа үйлчилгээний газруудыг шүүж татах")

    # sync-daily
    p_sync = subparsers.add_parser("sync-daily", help="Өдөр тутам шинэчлэгдсэн нэгж талбаруудыг ялгаж татах")
    p_sync.add_argument("--days", type=int, default=3, help="Сүүлийн хэдэн өдрийн шинэчлэлтийг авах (Default: 3 өдөр)")
    p_sync.add_argument("--rate-limit", type=float, default=15.0, help="Секундэд илгээх дээд хурд (Default: 15 req/s)")
    p_sync.add_argument("--workers", type=int, default=15, help="Зэрэгцээ урсгалын тоо (Default: 15)")
    p_sync.add_argument("--limit", type=int, help="Туршилтаар цөөн тоогоор татах хязгаар")
    p_sync.add_argument("--no-fetch", action="store_true", help="Зөвхөн WFS-ээр ялгаж хадгалах, detail татахгүй байх")

    # stats
    subparsers.add_parser("stats", help="Одоогийн өгөгдлийн сангийн статистик харах")

    # search
    p_search = subparsers.add_parser("search", help="Эзэмшигчийн нэр, регистрээр хайх")
    p_search.add_argument("query", help="Хайх үг")

    # match-companies
    subparsers.add_parser("match-companies", help="burtgel_les.db компаниудтай тулгаж харах")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.command == "init-geo":
        cmd_init_geo(args)
    elif args.command == "fetch-details":
        cmd_fetch_details(args)
    elif args.command == "sync-daily":
        cmd_sync_daily(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "match-companies":
        cmd_match_companies(args)


if __name__ == "__main__":
    main()
