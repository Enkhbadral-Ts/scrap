#!/usr/bin/env python3
"""
normalize_land_data.py - Газрын санг Улсын бүртгэлийн сантай (burtgel_les.db) хөндлөн шалгаж жигдрүүлэх
- Компаниудын нэрийг тулган регистрийн дугаарыг бүрэн тайлах (unmask)
- Тухайн газрыг эзэмшигч компанийн гүйцэтгэх захирал, хувьцаа эзэмшигчдийг автоматаар холбож хадгалах
- Хайлтын хурдыг нэмэгдүүлэх өндөр түвшний индексүүдийг бэлтгэх
"""

import sqlite3
import os
import re
import json
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EGAZAR_DB = os.path.join(SCRIPT_DIR, "egazar.db")
BURTGEL_DB = os.path.join(SCRIPT_DIR, "burtgel_les.db")


def normalize_and_crossmatch():
    t0 = time.time()
    print("=======================================================")
    print("🔄 Газрын өгөгдлийг Улсын бүртгэлийн сантай жигдрүүлж байна")
    print(f"   Газрын сан: {EGAZAR_DB}")
    print(f"   Бүртгэлийн сан: {BURTGEL_DB}")
    print("=======================================================\n")

    if not os.path.exists(EGAZAR_DB) or not os.path.exists(BURTGEL_DB):
        print("[!] Өгөгдлийн сангийн файл олдсонгүй!")
        return

    # 1. Шинэ багануудыг egazar.db-д нэмэх
    e_conn = sqlite3.connect(EGAZAR_DB)
    e_cur = e_conn.cursor()
    e_cur.execute("PRAGMA journal_mode = WAL;")

    for col in [
        ("matched_reg_no", "TEXT"),
        ("matched_name", "TEXT"),
        ("matched_form", "TEXT"),
        ("matched_people", "TEXT"),
        ("owner_lower", "TEXT")
    ]:
        try:
            e_cur.execute(f"ALTER TABLE parcels ADD COLUMN {col[0]} {col[1]};")
            print(f"  + Багана нэмэгдлээ: {col[0]}")
        except Exception:
            pass  # аль хэдийн үүссэн

    e_conn.commit()

    # 2. burtgel_les.db-ээс компаниудыг санах ойд бэлтгэх
    print("\n📦 Улсын бүртгэлийн компаниудыг санах ойд ачаалж байна...")
    b_conn = sqlite3.connect(BURTGEL_DB)
    b_cur = b_conn.cursor()

    b_cur.execute("SELECT reg_no, name, name_lower, form FROM companies;")
    comp_by_name = {}
    comp_by_prefix = {}
    for reg_no, name, name_lower, form in b_cur.fetchall():
        nl = name_lower.strip()
        comp_by_name[nl] = (reg_no, name, form)
        prefix = reg_no[:4]
        if prefix not in comp_by_prefix:
            comp_by_prefix[prefix] = []
        comp_by_prefix[prefix].append((reg_no, name, nl, form))

    print(f"✅ {len(comp_by_name):,} компани санах ойд ачаалагдлаа ({time.time()-t0:.2f}с)")

    # 3. Эзэмшигчдийн нэрсийг тулгаж match үүсгэх
    print("\n🔍 Газрын сангийн компаниудтай хөндлөн шалгалт хийж байна...")
    e_cur.execute("""
        SELECT DISTINCT owner_name, register_no 
        FROM parcels 
        WHERE status = 'done' AND owner_name IS NOT NULL AND trim(owner_name) != '';
    """)
    distinct_owners = e_cur.fetchall()
    print(f"   Нийт {len(distinct_owners):,} бие даасан эзэмшигч шалгана.")

    match_map = {}  # (oname, oreg) -> (matched_reg, matched_name, matched_form)
    matched_count = 0

    for oname, oreg in distinct_owners:
        clean = re.sub(r'[\"\'„“\(\)]', '', oname)
        clean = re.sub(r'\s*(ХХК|ХК|ББН|ББСБ|ТӨХК|ОНӨААТҮГ|ОНӨҮГ|ХХО).*', '', clean).strip().lower()

        matched = comp_by_name.get(clean) or comp_by_name.get(clean.replace('компани', '').strip())

        if not matched and oreg and len(oreg) >= 4 and oreg[:4].isdigit():
            prefix = oreg[:4]
            candidates = comp_by_prefix.get(prefix, [])
            for c in candidates:
                if clean in c[2] or c[2] in clean:
                    matched = (c[0], c[1], c[3])
                    break

        if matched:
            match_map[(oname, oreg)] = matched
            matched_count += 1

    print(f"✅ Нийт {matched_count:,} компани амжилттай тулгагдаж регистр нь бүрэн тайлагдлаа!")

    # 4. Тулгагдсан компаниудын удирдлага, хувьцаа эзэмшигчдийг авах
    matched_reg_set = set(m[0] for m in match_map.values())
    print(f"\n👥 {len(matched_reg_set):,} компанийн захирал, хувьцаа эзэмшигчдийн мэдээллийг холбож байна...")

    reg_to_people = {}
    CHUNK = 900
    reg_list = list(matched_reg_set)
    for i in range(0, len(reg_list), CHUNK):
        chunk = reg_list[i:i+CHUNK]
        placeholders = ','.join(['?'] * len(chunk))
        b_cur.execute(f"""
            SELECT reg_no, role, first_name, father_name 
            FROM company_people 
            WHERE reg_no IN ({placeholders});
        """, chunk)
        for r_no, role, first, father in b_cur.fetchall():
            if r_no not in reg_to_people:
                reg_to_people[r_no] = []
            if len(reg_to_people[r_no]) < 4:  # эхний 4 гол хүнийг авна
                name_str = f"{father[0]}.{first}" if father and len(father) > 0 else first
                reg_to_people[r_no].append({"role": role, "name": name_str})

    b_conn.close()

    # 5. egazar.db-г шинэчлэн бичих
    print("\n💾 egazar.db-д тулгагдсан өгөгдлийг суулгаж байна...")
    update_batch = []
    for (oname, oreg), (m_reg, m_name, m_form) in match_map.items():
        people_json = json.dumps(reg_to_people.get(m_reg, []), ensure_ascii=False)
        update_batch.append((m_reg, m_name, m_form, people_json, oname.lower().strip(), oname, oreg))

    e_cur.executemany("""
        UPDATE parcels SET
            matched_reg_no = ?,
            matched_name = ?,
            matched_form = ?,
            matched_people = ?,
            owner_lower = ?
        WHERE owner_name = ? AND (register_no = ? OR register_no IS NULL);
    """, update_batch)

    # Мөн компани биш иргэдийн owner_lower-ийг бөглөх (Python .lower() кирилл дэмждэг)
    rows_to_lower = e_cur.execute("""
        SELECT parcel_id, owner_name FROM parcels 
        WHERE owner_lower IS NULL AND owner_name IS NOT NULL;
    """).fetchall()
    if rows_to_lower:
        lower_batch = [(name.lower(), pid) for pid, name in rows_to_lower]
        e_cur.executemany("UPDATE parcels SET owner_lower = ? WHERE parcel_id = ?", lower_batch)
        print(f"   📝 {len(lower_batch)} иргэний нэрийг жижиг үсгээр бөгллөө")

    e_conn.commit()

    # 6. Индексүүдийг шинэчлэх
    print("⚡ Хайлтыг хурдасгах индексүүдийг үүсгэж байна...")
    e_cur.execute("CREATE INDEX IF NOT EXISTS idx_parcels_owner_lower ON parcels(owner_lower);")
    e_cur.execute("CREATE INDEX IF NOT EXISTS idx_parcels_matched_reg ON parcels(matched_reg_no);")
    e_cur.execute("CREATE INDEX IF NOT EXISTS idx_parcels_matched_name ON parcels(matched_name);")
    e_cur.execute("CREATE INDEX IF NOT EXISTS idx_parcels_cert ON parcels(property_cert_no);")
    e_cur.execute("CREATE INDEX IF NOT EXISTS idx_parcels_rights ON parcels(rights_type);")
    e_cur.execute("CREATE INDEX IF NOT EXISTS idx_parcels_org ON parcels(org_type);")

    e_conn.commit()
    e_conn.close()

    total_time = time.time() - t0
    print(f"\n🎉 Амжилттай дууслаа! ({total_time:.1f} секунд)")


if __name__ == "__main__":
    normalize_and_crossmatch()
