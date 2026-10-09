#!/usr/bin/env python3
"""
search_burtgel.py
Ultra-fast search utility for Mongolian National Company Registry (burtgel_les.db).
Response time: ~1-5 milliseconds.

Usage:
    python3 search_burtgel.py "Энхбаяр Цолмон"
    python3 search_burtgel.py --person "Цолмон"
    python3 search_burtgel.py --company "Техбокс"
    python3 search_burtgel.py --reg "6246109"
"""

import sys
import sqlite3
import time
import argparse

DB_PATH = "burtgel_les.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def search_by_person(query, exact=False):
    conn = get_conn()
    cur = conn.cursor()
    t0 = time.time()

    parts = query.strip().split()
    if len(parts) == 2:
        p1, p2 = parts[0].lower(), parts[1].lower()
        # Match both (p1 p2) or (p2 p1)
        sql = """
        SELECT p.reg_no, p.role, p.father_name, p.first_name, p.full_name, p.gender, p.reg_date as role_date,
               c.name as company_name, c.form, c.reg_date as comp_date, c.activities
        FROM company_people p
        JOIN companies c ON p.reg_no = c.reg_no
        WHERE (p.father_lower = ? AND p.first_lower = ?)
           OR (p.father_lower = ? AND p.first_lower = ?)
           OR p.full_lower = ? OR p.full_lower = ?
        """
        cur.execute(sql, (p1, p2, p2, p1, f"{p1} {p2}", f"{p2} {p1}"))
    else:
        q = query.strip().lower()
        if exact:
            sql = """
            SELECT p.reg_no, p.role, p.father_name, p.first_name, p.full_name, p.gender, p.reg_date as role_date,
                   c.name as company_name, c.form, c.reg_date as comp_date, c.activities
            FROM company_people p
            JOIN companies c ON p.reg_no = c.reg_no
            WHERE p.first_lower = ? OR p.full_lower = ?
            """
            cur.execute(sql, (q, q))
        else:
            sql = """
            SELECT p.reg_no, p.role, p.father_name, p.first_name, p.full_name, p.gender, p.reg_date as role_date,
                   c.name as company_name, c.form, c.reg_date as comp_date, c.activities
            FROM company_people p
            JOIN companies c ON p.reg_no = c.reg_no
            WHERE p.first_lower LIKE ? OR p.full_lower LIKE ?
            LIMIT 50
            """
            cur.execute(sql, (f"%{q}%", f"%{q}%"))

    rows = cur.fetchall()
    duration_ms = (time.time() - t0) * 1000
    conn.close()
    return rows, duration_ms

def search_by_company(name_query):
    conn = get_conn()
    cur = conn.cursor()
    t0 = time.time()
    q = name_query.strip().lower()
    sql = """
    SELECT reg_no, name, reg_date, form, type, activities
    FROM companies
    WHERE name_lower LIKE ?
    LIMIT 50
    """
    cur.execute(sql, (f"%{q}%",))
    rows = cur.fetchall()
    duration_ms = (time.time() - t0) * 1000
    conn.close()
    return rows, duration_ms

def search_by_reg(reg_no):
    conn = get_conn()
    cur = conn.cursor()
    t0 = time.time()
    cur.execute("SELECT * FROM companies WHERE reg_no = ?", (reg_no.strip(),))
    comp = cur.fetchone()
    if comp:
        cur.execute("SELECT role, father_name, first_name, full_name, gender, reg_date FROM company_people WHERE reg_no = ?", (reg_no.strip(),))
        people = cur.fetchall()
    else:
        people = []
    duration_ms = (time.time() - t0) * 1000
    conn.close()
    return comp, people, duration_ms

def format_person_results(rows, duration_ms, query):
    print(f"\n🔍 Хүний нэрээр хайсан үр дүн: '{query}' (Хугацаа: {duration_ms:.2f} мс, Олдсон: {len(rows)})")
    print("=" * 80)
    if not rows:
        print("Илэрц олдсонгүй.")
        return

    # Group by company
    companies = {}
    for r in rows:
        reg = r["reg_no"]
        if reg not in companies:
            companies[reg] = {
                "name": r["company_name"],
                "reg_no": reg,
                "form": r["form"],
                "comp_date": r["comp_date"],
                "activities": r["activities"],
                "roles": []
            }
        companies[reg]["roles"].append({
            "role": r["role"],
            "father": r["father_name"],
            "first": r["first_name"],
            "gender": r["gender"],
            "role_date": r["role_date"]
        })

    for idx, (reg, comp) in enumerate(companies.items(), 1):
        print(f"\n{idx}. 🏢 {comp['name']} ({comp['form']})")
        print(f"   • Регистрийн дугаар: {comp['reg_no']}")
        print(f"   • Байгуулагдсан огноо: {comp['comp_date']}")
        print(f"   • Хамаарал / Албан тушаал:")
        for role in comp["roles"]:
            gender_txt = f", хүйс: {role['gender']}" if role['gender'] else ""
            date_txt = f", огноо: {role['role_date']}" if role['role_date'] else ""
            print(f"     - {role['role']}: {role['father']} {role['first']}{gender_txt}{date_txt}")
        if comp['activities']:
            acts = comp['activities'].split("; ")
            print(f"   • Үйл ажиллагааны чиглэл: {', '.join(acts[:3])}{' ...' if len(acts)>3 else ''}")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Монгол Улсын Хуулийн этгээдийн улсын бүртгэлээс хурдан хайх")
    parser.add_argument("query", nargs="?", default="", help="Хайх нэр, компани эсвэл регистр")
    parser.add_argument("--person", "-p", help="Хүний нэрээр хайх")
    parser.add_argument("--company", "-c", help="Компанийн нэрээр хайх")
    parser.add_argument("--reg", "-r", help="Регистрийн дугаараар хайх")
    parser.add_argument("--exact", action="store_true", help="Яг таг тохирох нэрээр хайх")

    args = parser.parse_args()

    if args.reg:
        comp, people, dur = search_by_reg(args.reg)
        print(f"\n🔍 Регистрээр хайсан үр дүн: '{args.reg}' ({dur:.2f} мс)")
        if comp:
            print(f"Компани: {comp['name']} ({comp['form']})")
            print(f"Бүртгэсэн: {comp['reg_date']}, Төрөл: {comp['type']}")
            print(f"Чиглэл: {comp['activities']}")
            print("Холбоотой хүмүүс:")
            for p in people:
                print(f" - {p['role']}: {p['father_name']} {p['first_name']} ({p['gender']})")
        else:
            print("Олдсонгүй.")
    elif args.company:
        rows, dur = search_by_company(args.company)
        print(f"\n🔍 Компанийн нэрээр хайсан үр дүн: '{args.company}' ({dur:.2f} мс, Олдсон: {len(rows)})")
        for r in rows:
            print(f"• [{r['reg_no']}] {r['name']} ({r['form']}) - {r['reg_date']}")
    elif args.person:
        rows, dur = search_by_person(args.person, exact=args.exact)
        format_person_results(rows, dur, args.person)
    elif args.query:
        # Auto detect
        if args.query.isdigit() and len(args.query) in (7, 8):
            comp, people, dur = search_by_reg(args.query)
            if comp:
                print(f"\n🔍 Регистрээр олдсон: {comp['name']} ({dur:.2f} мс)")
                for p in people:
                    print(f" - {p['role']}: {p['father_name']} {p['first_name']}")
            else:
                rows, dur = search_by_person(args.query)
                format_person_results(rows, dur, args.query)
        else:
            rows, dur = search_by_person(args.query)
            if rows:
                format_person_results(rows, dur, args.query)
            else:
                # Try company
                c_rows, dur = search_by_company(args.query)
                if c_rows:
                    print(f"\n🔍 Компанийн нэрээр олдсон үр дүн: ({dur:.2f} мс, {len(c_rows)} компани)")
                    for r in c_rows:
                        print(f"• [{r['reg_no']}] {r['name']} ({r['form']}) - {r['reg_date']}")
                else:
                    print("Олдсонгүй.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
