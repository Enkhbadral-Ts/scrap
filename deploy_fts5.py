#!/usr/bin/env python3
"""
deploy_fts5.py — VPS дээр ажиллах скрипт.
1. burtgel_les.db дээр FTS5 индекс нэмнэ
2. egazar.db дээр FTS5 индекс нэмнэ
3. server.js дээр бүртгэл + газар хайлтыг FTS5 руу шилжүүлнэ
"""
import sqlite3, time, re, os, sys

def normalize(text):
    if not text: return ""
    t = text.lower().strip()
    t = t.replace("-", "").replace("\u2013", "").replace("\u2014", "")
    t = re.sub(r'\s+', ' ', t)
    return t

# ═══════════════════════════════════════════════════
# 1. БҮРТГЭЛ DB — FTS5 нэмэх
# ═══════════════════════════════════════════════════
def add_fts5_burtgel(db_path):
    print(f"\n{'='*60}")
    print(f"📋 БҮРТГЭЛ FTS5: {db_path}")
    print(f"{'='*60}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Check if FTS5 already exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fts_people'")
    if cur.fetchone():
        print("  ⚠️  fts_people аль хэдийн байна, устгаад дахин бүтээнэ...")
        cur.execute("DROP TABLE fts_people")
        cur.execute("DROP TABLE IF EXISTS fts_companies")
        conn.commit()
    
    t0 = time.time()
    
    # FTS5 for people
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
    
    cur.execute("SELECT id, reg_no, full_name, first_name, father_name, role FROM company_people")
    batch = []
    for row in cur.fetchall():
        batch.append((
            str(row["id"]), row["reg_no"],
            normalize(row["full_name"] or ""),
            normalize(row["first_name"] or ""),
            normalize(row["father_name"] or ""),
            row["role"] or ""
        ))
    cur.executemany("INSERT INTO fts_people(people_id, reg_no, full_text, first_text, father_text, role) VALUES (?,?,?,?,?,?)", batch)
    conn.commit()
    print(f"  ✅ fts_people: {len(batch):,} мөр ({time.time()-t0:.1f}с)")
    
    # FTS5 for companies
    t1 = time.time()
    cur.execute("""
        CREATE VIRTUAL TABLE fts_companies USING fts5(
            reg_no UNINDEXED,
            name,
            tokenize='unicode61 remove_diacritics 2'
        )
    """)
    cur.execute("SELECT reg_no, name FROM companies")
    cbatch = [(r["reg_no"], normalize(r["name"] or "")) for r in cur.fetchall()]
    cur.executemany("INSERT INTO fts_companies(reg_no, name) VALUES (?,?)", cbatch)
    conn.commit()
    print(f"  ✅ fts_companies: {len(cbatch):,} мөр ({time.time()-t1:.1f}с)")
    
    # Quick test
    cur.execute("SELECT full_text FROM fts_people WHERE fts_people MATCH '\"лувсаннамсрай\"* \"оюунэрдэнэ\"*' LIMIT 5")
    results = cur.fetchall()
    print(f"  🧪 Тест 'лувсаннамсрай оюун-эрдэнэ': {len(results)} олдсон")
    
    conn.close()
    print(f"  ⏱️  Нийт: {time.time()-t0:.1f}с")

# ═══════════════════════════════════════════════════
# 2. ГАЗАР DB — FTS5 нэмэх
# ═══════════════════════════════════════════════════
def add_fts5_egazar(db_path):
    print(f"\n{'='*60}")
    print(f"🗺️  ГАЗАР FTS5: {db_path}")
    print(f"{'='*60}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Check if FTS5 already exists
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fts_parcels'")
    if cur.fetchone():
        print("  ⚠️  fts_parcels аль хэдийн байна, устгаад дахин бүтээнэ...")
        cur.execute("DROP TABLE fts_parcels")
        conn.commit()
    
    t0 = time.time()
    
    cur.execute("""
        CREATE VIRTUAL TABLE fts_parcels USING fts5(
            parcel_id UNINDEXED,
            owner_text,
            address_text,
            matched_name_text,
            tokenize='unicode61 remove_diacritics 2'
        )
    """)
    
    cur.execute("SELECT parcel_id, owner_name, address_streetname, matched_name FROM parcels")
    batch = []
    for row in cur.fetchall():
        batch.append((
            row["parcel_id"],
            normalize(row["owner_name"] or ""),
            normalize(row["address_streetname"] or ""),
            normalize(row["matched_name"] or "")
        ))
    cur.executemany("INSERT INTO fts_parcels(parcel_id, owner_text, address_text, matched_name_text) VALUES (?,?,?,?)", batch)
    conn.commit()
    print(f"  ✅ fts_parcels: {len(batch):,} мөр ({time.time()-t0:.1f}с)")
    
    # Quick test
    cur.execute("SELECT owner_text FROM fts_parcels WHERE fts_parcels MATCH '\"батбаяр\"*' LIMIT 5")
    results = cur.fetchall()
    print(f"  🧪 Тест 'батбаяр': {len(results)} олдсон")
    
    conn.close()
    print(f"  ⏱️  Нийт: {time.time()-t0:.1f}с")

# ═══════════════════════════════════════════════════
# 3. SERVER.JS — хайлтыг FTS5 руу шилжүүлэх
# ═══════════════════════════════════════════════════
def patch_server_js(server_path):
    print(f"\n{'='*60}")
    print(f"🔧 SERVER.JS PATCH: {server_path}")
    print(f"{'='*60}")
    
    with open(server_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # --- A. normalizeFts function (бүртгэл хайлтын өмнө нэмэх) ---
    if "normalizeFts" not in content:
        normalize_fn = '''
// FTS5 normalize: remove hyphens, lowercase for Mongolian name matching
function normalizeFts(text) {
  if (!text) return "";
  return text.toLowerCase().trim()
    .replace(/[-\\u2013\\u2014]/g, "")
    .replace(/\\s+/g, " ");
}
'''
        # Insert before "// Search API" or "app.get(\"/api/burtgel/search\""
        insert_marker = '// Search API'
        if insert_marker in content:
            content = content.replace(insert_marker, normalize_fn + "\n" + insert_marker)
            print("  ✅ normalizeFts() функц нэмсэн")
        else:
            print("  ⚠️  '// Search API' олдсонгүй, гараар нэмнэ үү")
    else:
        print("  ✅ normalizeFts() аль хэдийн байна")
    
    # --- B. Бүртгэл хайлтыг FTS5 болгох ---
    old_burtgel = '''// Search API
app.get("/api/burtgel/search", async (req, res) => {'''
    
    # Find the entire burtgel search handler
    burtgel_start = content.find('app.get("/api/burtgel/search"')
    if burtgel_start == -1:
        print("  ❌ Бүртгэл хайлтын route олдсонгүй!")
        return
    
    # Find the end of this handler (next app.get or app.post)
    burtgel_end = content.find('\n\n// Company detail', burtgel_start)
    if burtgel_end == -1:
        burtgel_end = content.find('\napp.get("/api/burtgel/company', burtgel_start)
    if burtgel_end == -1:
        # Try finding the closing });
        # Count braces to find the end
        depth = 0
        i = content.find('{', burtgel_start)
        while i < len(content):
            if content[i] == '{': depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    # Check for );
                    rest = content[i:i+10].strip()
                    if rest.startswith('});'):
                        burtgel_end = i + 3
                        break
            i += 1
    
    if burtgel_end == -1:
        print("  ❌ Бүртгэл хайлтын handler-ийн төгсгөл олдсонгүй!")
        return
    
    # Check for "// Search API" label before the route
    label_pos = content.rfind('// Search API', 0, burtgel_start)
    if label_pos != -1 and burtgel_start - label_pos < 200:
        burtgel_start = label_pos
    
    old_handler = content[burtgel_start:burtgel_end]
    
    new_burtgel = '''// Search API — FTS5 powered (sub-millisecond, hyphen-tolerant)
app.get("/api/burtgel/search", async (req, res) => {
  const q = (req.query.q || "").trim();
  const filter = (req.query.filter || "all").toLowerCase();
  const limit = Math.min(Math.max(parseInt(req.query.limit) || 50, 1), 100);
  const offset = Math.max(parseInt(req.query.offset) || 0, 0);

  if (q.length < 2) {
    return res.json({ error: "Query хамгийн багадаа 2 тэмдэгт байна.", companies: [], total_companies: 0, total_matches: 0, duration_ms: 0 });
  }

  const t0 = Date.now();
  try {
    const db = getBurtgelDb();
    let flatRows = [];

    let roleFilter = "";
    if (filter === "shareholder") roleFilter = " AND p.role = 'Хувьцаа эзэмшигч'";
    else if (filter === "director") roleFilter = " AND (p.role LIKE '%захирал%' OR p.role LIKE '%Захирал%')";
    else if (filter === "ubo") roleFilter = " AND p.role LIKE '%өмчлөгч%'";

    const baseSql = `SELECT p.reg_no, p.role, p.father_name, p.first_name, p.gender, p.reg_date AS role_date,
                          c.name AS company_name, c.form, c.reg_date AS comp_date, c.activities
                   FROM company_people p
                   JOIN companies c ON p.reg_no = c.reg_no`;

    if (/^\\d{6,8}$/.test(q)) {
      flatRows = db.prepare(`${baseSql} WHERE p.reg_no = ?${roleFilter} LIMIT ? OFFSET ?`).all(q, limit, offset);
    } else {
      const normalized = normalizeFts(q);
      const parts = normalized.split(/\\s+/).filter(p => p.length >= 2);
      if (parts.length === 0) {
        return res.json({ query: q, filter, total_companies: 0, total_matches: 0, duration_ms: Date.now() - t0, companies: [] });
      }

      const ftsTerm = parts.map(p => `"${p}"*`).join(" ");

      // 1. FTS5 компанийн нэрээр хайх
      try {
        const compRegs = db.prepare("SELECT reg_no FROM fts_companies WHERE fts_companies MATCH ? LIMIT ?").all(ftsTerm, limit);
        if (compRegs.length > 0) {
          const placeholders = compRegs.map(() => "?").join(",");
          const cParams = compRegs.map(r => r.reg_no);
          cParams.push(limit);
          flatRows = db.prepare(`${baseSql} WHERE p.reg_no IN (${placeholders})${roleFilter} LIMIT ?`).all(...cParams);
        }
      } catch (ftsErr) {
        console.warn("FTS5 company fallback:", ftsErr.message);
        const ql = q.toLowerCase();
        flatRows = db.prepare(`${baseSql} WHERE (c.name_lower LIKE ? OR c.name_lower LIKE ?)${roleFilter} LIMIT ? OFFSET ?`).all(`${ql}%`, `% ${ql}%`, limit, offset);
      }

      // 2. FTS5 хүний нэрээр хайх
      if (flatRows.length < limit) {
        try {
          const pRows = db.prepare(`
            SELECT fp.reg_no, fp.role, fp.father_text AS father_name, fp.first_text AS first_name,
                   '' AS gender, '' AS role_date,
                   c.name AS company_name, c.form, c.reg_date AS comp_date, c.activities
            FROM fts_people fp
            JOIN companies c ON fp.reg_no = c.reg_no
            WHERE fts_people MATCH ?
            LIMIT ?
          `).all(ftsTerm, limit - flatRows.length);
          flatRows.push(...pRows);
        } catch (ftsErr) {
          console.warn("FTS5 people fallback:", ftsErr.message);
          const ql = q.toLowerCase();
          const fParts = ql.split(/\\s+/);
          let conditions = [];
          let params = [];
          for (const p of fParts) {
            conditions.push("(p.full_lower LIKE ? OR p.full_lower LIKE ?)");
            params.push(`${p}%`, `% ${p}%`);
          }
          const pSql = `${baseSql} WHERE (${conditions.join(" AND ")})${roleFilter} LIMIT ? OFFSET ?`;
          params.push(limit - flatRows.length, offset);
          const pRows = db.prepare(pSql).all(...params);
          flatRows.push(...pRows);
        }
      }
    }

    // Давхардал хасах
    const seen = new Set();
    flatRows = flatRows.filter(r => {
      const key = `${r.reg_no}_${r.father_name}_${r.first_name}_${r.role}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    const companyMap = {};
    for (const r of flatRows) {
      if (!companyMap[r.reg_no]) {
        companyMap[r.reg_no] = { reg_no: r.reg_no, name: r.company_name, form: r.form, reg_date: r.comp_date, activities: r.activities, roles: [] };
      }
      companyMap[r.reg_no].roles.push({ role: r.role, father: r.father_name, first: r.first_name, gender: r.gender, date: r.role_date });
    }

    const companies = Object.values(companyMap);
    const durationMs = Date.now() - t0;

    logSearch(req, "Бүртгэл", q, companies.length, durationMs);
    res.json({ query: q, filter, total_companies: companies.length, total_matches: flatRows.length, has_more: flatRows.length >= limit, offset, limit, duration_ms: durationMs, companies });
  } catch (err) {
    console.error("Burtgel search error:", err.message);
    res.status(500).json({ error: err.message, companies: [], total_companies: 0, total_matches: 0, duration_ms: Date.now() - t0 });
  }
});'''
    
    content = content[:burtgel_start] + new_burtgel + content[burtgel_end:]
    print(f"  ✅ Бүртгэл хайлт FTS5 руу шилжүүлсэн ({len(old_handler)} → {len(new_burtgel)} тэмдэгт)")
    
    # --- C. Газар хайлтыг FTS5 болгох ---
    # Find the text search section in gazar handler
    old_gazar_search = '''conditions.push("(owner_name LIKE ? OR owner_lower LIKE ? OR matched_name LIKE ? OR address_streetname LIKE ? OR property_cert_no LIKE ?)");
        params.push("%" + q + "%", "%" + ql + "%", "%" + ql + "%", "%" + ql + "%", "%" + ql + "%");'''
    
    new_gazar_search = '''// FTS5 хайлт: owner, address, matched_name
        let ftsParcelIds = null;
        try {
          const norm = normalizeFts(q);
          const gParts = norm.split(/\\s+/).filter(p => p.length >= 2);
          if (gParts.length > 0) {
            const gFts = gParts.map(p => `"${p}"*`).join(" ");
            const ftsRows = db.prepare("SELECT parcel_id FROM fts_parcels WHERE fts_parcels MATCH ? LIMIT 500").all(gFts);
            if (ftsRows.length > 0) {
              ftsParcelIds = ftsRows.map(r => r.parcel_id);
              const ph = ftsParcelIds.map(() => "?").join(",");
              conditions.push(`parcel_id IN (${ph})`);
              params.push(...ftsParcelIds);
            } else {
              conditions.push("1=0"); // No results
            }
          }
        } catch (ftsErr) {
          // FTS5 fallback to LIKE
          console.warn("FTS5 gazar fallback:", ftsErr.message);
          conditions.push("(owner_name LIKE ? OR owner_lower LIKE ? OR matched_name LIKE ? OR address_streetname LIKE ? OR property_cert_no LIKE ?)");
          params.push("%" + q + "%", "%" + ql + "%", "%" + ql + "%", "%" + ql + "%", "%" + ql + "%");
        }'''
    
    if old_gazar_search in content:
        content = content.replace(old_gazar_search, new_gazar_search)
        print("  ✅ Газар хайлт FTS5 руу шилжүүлсэн")
    else:
        print("  ⚠️  Газар хайлтын LIKE pattern олдсонгүй (гараар шалгах хэрэгтэй)")
    
    with open(server_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  💾 {server_path} хадгалсан ({len(content):,} bytes)")

# ═══════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════
if __name__ == "__main__":
    base = "/root/khuuli-bot"
    
    burtgel_db = os.path.join(base, "data", "burtgel_les.db")
    egazar_db = os.path.join(base, "data", "egazar.db")
    server_js = os.path.join(base, "server.js")
    
    print("🚀 FTS5 Deploy эхэллээ...")
    print(f"   Бүртгэл DB: {burtgel_db}")
    print(f"   Газар DB:   {egazar_db}")
    print(f"   Server:     {server_js}")
    
    add_fts5_burtgel(burtgel_db)
    add_fts5_egazar(egazar_db)
    patch_server_js(server_js)
    
    print(f"\n{'='*60}")
    print("✅ БҮГД АМЖИЛТТАЙ! pm2 restart хийнэ үү:")
    print("   pm2 restart khuuli-bot")
    print(f"{'='*60}")
