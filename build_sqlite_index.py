#!/usr/bin/env python3
"""
build_sqlite_index.py
Converts LesOutputJson.json into an optimized, indexed SQLite database.

INCREMENTAL MODE (default):
  - Шинэ компани/хүнийг INSERT, өөрчлөгдсөнийг UPDATE хийнэ
  - FTS5 индексийг дахин бүтээнэ (DROP + CREATE)
  - Бааз хэзээ ч устахгүй, тасалдал үгүй

FULL REBUILD MODE (--rebuild flag):
  - Хуучин бааз устгаад шинээр бүтээнэ (temp файлаар атомаар солино)
"""

import json
import os
import re
import sqlite3
import sys
import time

DB_PATH = os.environ.get("DB_PATH", "burtgel_les.db")
JSON_PATH = os.environ.get("JSON_PATH", "LesOutputJson.json")

def normalize_fts(text):
    """FTS5-д зориулж normalize: жижиг үсэг, зураас арилгах"""
    if not text:
        return ""
    t = text.lower().strip()
    t = t.replace("-", "").replace("\u2013", "").replace("\u2014", "")
    t = re.sub(r'\s+', ' ', t)
    return t

def get_counts(db_path):
    """Одоогийн баазын компани, хүний тоог авах"""
    if not os.path.exists(db_path):
        return 0, 0
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM companies")
        companies = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM company_people")
        people = cur.fetchone()[0]
        conn.close()
        return companies, people
    except:
        return 0, 0

def ensure_schema(cur):
    """Хүснэгтүүд байхгүй бол үүсгэнэ"""
    cur.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        reg_no TEXT PRIMARY KEY,
        name TEXT,
        name_lower TEXT,
        reg_date TEXT,
        form TEXT,
        type TEXT,
        address TEXT,
        activities TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS company_people (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reg_no TEXT,
        role TEXT,
        father_name TEXT,
        first_name TEXT,
        full_name TEXT,
        father_lower TEXT,
        first_lower TEXT,
        full_lower TEXT,
        gender TEXT,
        reg_date TEXT
    );
    """)

def ensure_indexes(cur):
    """B-Tree индексүүдийг нэмнэ (байвал алгасна)"""
    indexes = [
        ("idx_people_full_lower", "company_people(full_lower)"),
        ("idx_people_first_lower", "company_people(first_lower)"),
        ("idx_people_father_lower", "company_people(father_lower)"),
        ("idx_people_reg_no", "company_people(reg_no)"),
        ("idx_companies_name_lower", "companies(name_lower)"),
        ("idx_companies_reg", "companies(reg_no)"),
    ]
    for idx_name, idx_def in indexes:
        cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {idx_def};")

def rebuild_fts5(cur, conn, companies_batch, people_batch):
    """FTS5 индексийг дахин бүтээх (DROP + CREATE)"""
    print("Building FTS5 full-text search indexes...")
    fts_t0 = time.time()

    # Drop existing FTS5 tables
    for tbl in ["fts_people", "fts_companies"]:
        cur.execute(f"DROP TABLE IF EXISTS {tbl}")
    conn.commit()

    # FTS5 for people search
    cur.execute("""
        CREATE VIRTUAL TABLE fts_people USING fts5(
            people_id,
            reg_no UNINDEXED,
            full_text,
            first_text,
            father_text,
            role UNINDEXED,
            tokenize='unicode61 remove_diacritics 2'
        )
    """)
    fts_people_batch = []
    for pb in people_batch:
        reg_no, role, father, first, full = pb[0], pb[1], pb[2], pb[3], pb[4]
        fts_people_batch.append((
            str(len(fts_people_batch) + 1),
            reg_no,
            normalize_fts(full),
            normalize_fts(first),
            normalize_fts(father),
            role
        ))
    cur.executemany("INSERT INTO fts_people(people_id, reg_no, full_text, first_text, father_text, role) VALUES (?, ?, ?, ?, ?, ?)", fts_people_batch)
    conn.commit()
    print(f"  fts_people: {len(fts_people_batch):,} rows")

    # FTS5 for company name search
    cur.execute("""
        CREATE VIRTUAL TABLE fts_companies USING fts5(
            reg_no UNINDEXED,
            name,
            tokenize='unicode61 remove_diacritics 2'
        )
    """)
    fts_comp_batch = [(cb[0], normalize_fts(cb[1])) for cb in companies_batch]
    cur.executemany("INSERT INTO fts_companies(reg_no, name) VALUES (?, ?)", fts_comp_batch)
    conn.commit()
    print(f"  fts_companies: {len(fts_comp_batch):,} rows")
    print(f"FTS5 indexes built in {time.time() - fts_t0:.2f}s.")

def parse_entities(entities):
    """JSON өгөгдлөөс companies, people batch үүсгэнэ"""
    companies_batch = []
    people_batch = []

    for row in entities:
        reg_no = str(row[0]).strip()
        name = str(row[1]).strip() if len(row) > 1 else ""
        name_lower = name.lower()
        reg_date = str(row[2]).strip() if len(row) > 2 else ""
        form = str(row[3]).strip() if len(row) > 3 else ""
        c_type = str(row[4]).strip() if len(row) > 4 else ""
        address = str(row[5]).strip() if len(row) > 5 and isinstance(row[5], str) else ""

        shareholders = row[5] if len(row) > 5 and isinstance(row[5], list) else []
        directors = row[6] if len(row) > 6 and isinstance(row[6], list) else []
        ubos = row[7] if len(row) > 7 and isinstance(row[7], list) else []
        activities_list = row[8] if len(row) > 8 and isinstance(row[8], list) else []

        acts = [a[2] for a in activities_list if len(a) > 2 and a[0] == "Тийм"]
        activities_str = "; ".join(acts)

        companies_batch.append((reg_no, name, name_lower, reg_date, form, c_type, address, activities_str))

        for sh in shareholders:
            father = str(sh[2]).strip() if len(sh) > 2 and sh[2] else ""
            first = str(sh[3]).strip() if len(sh) > 3 and sh[3] else ""
            gender = str(sh[4]).strip() if len(sh) > 4 and sh[4] else ""
            sh_date = str(sh[5]).strip() if len(sh) > 5 and sh[5] else ""
            full = f"{father} {first}".strip()
            if full:
                people_batch.append((reg_no, "Хувьцаа эзэмшигч", father, first, full, father.lower(), first.lower(), full.lower(), gender, sh_date))

        for dr in directors:
            pos = str(dr[0]).strip() if len(dr) > 0 and dr[0] else "Удирдах албан тушаалтан"
            father = str(dr[2]).strip() if len(dr) > 2 and dr[2] else ""
            first = str(dr[3]).strip() if len(dr) > 3 and dr[3] else ""
            gender = str(dr[4]).strip() if len(dr) > 4 and dr[4] else ""
            dr_date = str(dr[5]).strip() if len(dr) > 5 and dr[5] else ""
            full = f"{father} {first}".strip()
            if full:
                people_batch.append((reg_no, pos, father, first, full, father.lower(), first.lower(), full.lower(), gender, dr_date))

        for ubo in ubos:
            father = str(ubo[1]).strip() if len(ubo) > 1 and ubo[1] else ""
            first = str(ubo[2]).strip() if len(ubo) > 2 and ubo[2] else ""
            gender = str(ubo[4]).strip() if len(ubo) > 4 and ubo[4] else ""
            full = f"{father} {first}".strip()
            if full:
                people_batch.append((reg_no, "Эцсийн өмчлөгч (UBO)", father, first, full, father.lower(), first.lower(), full.lower(), gender, ""))

    return companies_batch, people_batch


def incremental_update(conn, cur, companies_batch, people_batch):
    """
    Incremental update: UPSERT компани, хүмүүсийг reg_no-оор шинэчилнэ.
    Бааз хэзээ ч устахгүй.
    """
    t0 = time.time()

    # 1. Companies: UPSERT (INSERT OR REPLACE)
    cur.executemany(
        "INSERT OR REPLACE INTO companies VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        companies_batch
    )

    # 2. People: reg_no-оор хуучин бичлэгийг устгаад шинээр оруулна
    reg_nos_in_batch = set(cb[0] for cb in companies_batch)
    batch_size = 500
    reg_list = list(reg_nos_in_batch)
    for i in range(0, len(reg_list), batch_size):
        chunk = reg_list[i:i+batch_size]
        placeholders = ",".join(["?"] * len(chunk))
        cur.execute(f"DELETE FROM company_people WHERE reg_no IN ({placeholders})", chunk)

    cur.executemany(
        "INSERT INTO company_people (reg_no, role, father_name, first_name, full_name, father_lower, first_lower, full_lower, gender, reg_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        people_batch
    )

    conn.commit()
    print(f"Incremental update: {len(companies_batch):,} companies, {len(people_batch):,} people in {time.time() - t0:.2f}s.")


def full_rebuild(companies_batch, people_batch):
    """
    Full rebuild: temp файлд бүтээгээд атомаар солино.
    --rebuild flag-тай ажиллуулахад л хэрэглэнэ.
    """
    TEMP_DB = DB_PATH + ".tmp"
    if os.path.exists(TEMP_DB):
        os.remove(TEMP_DB)

    conn = sqlite3.connect(TEMP_DB)
    cur = conn.cursor()
    cur.execute("PRAGMA synchronous = OFF;")
    cur.execute("PRAGMA journal_mode = MEMORY;")
    cur.execute("PRAGMA cache_size = 100000;")

    ensure_schema(cur)

    t0 = time.time()
    cur.executemany("INSERT OR REPLACE INTO companies VALUES (?, ?, ?, ?, ?, ?, ?, ?)", companies_batch)
    cur.executemany("INSERT INTO company_people (reg_no, role, father_name, first_name, full_name, father_lower, first_lower, full_lower, gender, reg_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", people_batch)
    conn.commit()
    print(f"Full insert: {len(companies_batch):,} companies, {len(people_batch):,} people in {time.time() - t0:.2f}s.")

    print("Building indexes...")
    idx_t0 = time.time()
    ensure_indexes(cur)
    conn.commit()
    print(f"Indexes built in {time.time() - idx_t0:.2f}s.")

    rebuild_fts5(cur, conn, companies_batch, people_batch)

    conn.close()

    # Атомаар солих
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    os.rename(TEMP_DB, DB_PATH)


def main():
    start_time = time.time()
    force_rebuild = "--rebuild" in sys.argv

    print(f"Reading {JSON_PATH}...")
    if not os.path.exists(JSON_PATH):
        print(f"Error: {JSON_PATH} not found!")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    entities = data.get("Data", [])
    total = len(entities)
    print(f"Loaded {total:,} entities in {time.time() - start_time:.2f}s.")

    old_companies, old_people = get_counts(DB_PATH)

    # JSON-оос batch үүсгэх
    companies_batch, people_batch = parse_entities(entities)

    if force_rebuild or not os.path.exists(DB_PATH):
        # FULL REBUILD: Бааз байхгүй эсвэл --rebuild flag
        print("Mode: FULL REBUILD")
        full_rebuild(companies_batch, people_batch)
    else:
        # INCREMENTAL: Байгаа баазыг шинэчилнэ
        print("Mode: INCREMENTAL UPDATE")
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("PRAGMA synchronous = NORMAL;")
        cur.execute("PRAGMA journal_mode = WAL;")
        cur.execute("PRAGMA cache_size = 100000;")

        ensure_schema(cur)
        incremental_update(conn, cur, companies_batch, people_batch)

        print("Ensuring indexes...")
        idx_t0 = time.time()
        ensure_indexes(cur)
        conn.commit()
        print(f"Indexes verified in {time.time() - idx_t0:.2f}s.")

        # FTS5 дахин бүтээх
        rebuild_fts5(cur, conn, companies_batch, people_batch)

        conn.close()

    new_companies = len(companies_batch)
    new_people = len(people_batch)
    diff_c = new_companies - old_companies
    diff_p = new_people - old_people

    db_size = os.path.getsize(DB_PATH) / (1024 * 1024)
    print(f"Done! Database: {DB_PATH} ({db_size:.1f} MB) in total {time.time() - start_time:.2f}s.")

    if old_companies > 0:
        sign_c = "+" if diff_c >= 0 else ""
        sign_p = "+" if diff_p >= 0 else ""
        print(f"DIFF: {sign_c}{diff_c} companies, {sign_p}{diff_p} people (old: {old_companies:,}/{old_people:,} → new: {new_companies:,}/{new_people:,})")

if __name__ == "__main__":
    main()
