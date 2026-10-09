# -*- coding: utf-8 -*-
"""
Resolve all 467 entities from Top 300 with UBEG LesOutputJson and previous Top 100 data.
"""
import openpyxl
import json
import re

def normalize_text(s):
    if not s: return ''
    s = str(s).strip()
    # Normalize unicode dashes, quotes, and odd chars
    s = re.sub(r'[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]', '-', s)
    s = re.sub(r'[\u201c\u201d\u201e\u00ab\u00bb\"]', '', s)
    s = re.sub(r'[\u2018\u2019\']', '', s)
    s = s.replace('җ', 'ж')
    return s.strip()

def clean_key(s):
    if not s: return ''
    s = normalize_text(s).lower()
    s = s.replace('е', 'э').replace('й', 'и').replace('ё', 'о')
    s = re.sub(r'/(гхо|гхоххк|ххк|хк)/?', '', s)
    s = re.sub(r'[\(\)\,\.\'\-\_]', ' ', s)
    s = re.sub(r'\b(ххк|хк|хх|төүг|групп|корпораци|компани|llc|jsc|holding|холдинг|нэгдэл)\b', ' ', s)
    return re.sub(r'\s+', '', s)

# 1. Load Top 100
print("1. Loading Top 100...")
wb100 = openpyxl.load_workbook('/Users/enkhbadraltsogbayar/Tender data/1_Монгол_Улсын_ТОП_100_ААН_2025_Бүрэн_мэдээлэл.xlsx', data_only=True)
ws100 = wb100.active

top100_map = {}
for r in range(2, ws100.max_row + 1):
    rank = ws100.cell(r, 1).value
    name = ws100.cell(r, 2).value
    reg = ws100.cell(r, 3).value
    web = ws100.cell(r, 4).value
    sh = ws100.cell(r, 5).value
    dr = ws100.cell(r, 6).value
    ubo = ws100.cell(r, 7).value
    vis = ws100.cell(r, 8).value
    mis = ws100.cell(r, 9).value
    
    entry = {
        'rank': rank, 'name': str(name).strip() if name else '',
        'reg_no': str(reg).strip() if reg else '',
        'web': str(web).strip() if web else '',
        'sh': str(sh).strip() if sh else '',
        'dr': str(dr).strip() if dr else '',
        'ubo': str(ubo).strip() if ubo else '',
        'vis': str(vis).strip() if vis else '',
        'mis': str(mis).strip() if mis else ''
    }
    top100_map[clean_key(name)] = entry
    if reg:
        top100_map[f"reg_{reg}"] = entry

# 2. Load LesOutputJson
print("2. Loading LesOutputJson...")
with open('/Users/enkhbadraltsogbayar/Tender data/LesOutputJson.json', 'r', encoding='utf-8') as f:
    les_data = json.load(f)['Data']

les_by_key = {}
les_by_exact = {}
les_by_reg = {}

for row in les_data:
    reg = str(row[0]).strip()
    raw_name = str(row[1]).strip()
    les_by_reg[reg] = row
    
    ek = normalize_text(raw_name).lower()
    if ek not in les_by_exact:
        les_by_exact[ek] = row
        
    ck = clean_key(raw_name)
    if ck not in les_by_key:
        les_by_key[ck] = row

def parse_les(row):
    reg = str(row[0])
    name = str(row[1])
    form = str(row[3])
    sh_list = []
    for sh in row[5]:
        if len(sh) >= 4 and (sh[2] or sh[3]):
            sh_list.append(f"{sh[2]} {sh[3]}".strip())
    dr_list = []
    for dr in row[6]:
        if len(dr) >= 4 and (dr[2] or dr[3]):
            dr_list.append(f"{dr[2]} {dr[3]}".strip())
    ubo_list = []
    for ub in row[7]:
        if len(ub) >= 3 and (ub[1] or ub[2]):
            ubo_list.append(f"{ub[1]} {ub[2]}".strip())
            
    return {
        'reg_no': reg,
        'official_name': name,
        'form': form,
        'sh': ', '.join(dict.fromkeys(sh_list)),
        'dr': ', '.join(dict.fromkeys(dr_list)),
        'ubo': ', '.join(dict.fromkeys(ubo_list))
    }

# Specific manual overrides for known aliases/typos
MANUAL_REG_MAP = {
    'бидисекхк': '2052482',
    'бьюлдингмэйнтэнэнссервисэсхх': '5892694',
    'бюлдингмэйнтэнэнссервисэсхх': '5892694',
    'тандэминвестхк': '2013916',
    'этрансложистикхк': '3309665',
    'эрдэнэресурсдевелопменткорпорэйшнхк': '2007908',
    'алтайнэгдэлхк': '3490777',
    'ачиталкабыхк': '2003937',
    'блюскайсекьюритизхк': '2057816',
    'виинтернэшнлххк': '6450539',
    'гурилхк': '2002027',
    'тунгуанмайнсконстракшнмонголххк': '6028047',
    'евроазиакапиталхолдингхк': '2036282',
    'ихбарилгахк': '2001772',
    'номинбизнесклуббаруунбусххк': '6886973',
    'наноинтернэшнлххк': '5138132',
    'монголсекюритиесхк': '2587904',
    'номинбизнесклубзүүнбусххк': '6886949',
    'тэнгэрлэгмедиагруппхк': '2866692',
    'титисиэндтиххк/гхо/': '5411777',
    'хасумандалхк': '2007410',
    'жиэнбэврежиххк': '5258537',
    'жиэнбэврежисххк': '5258537',
    'мишээлгруппххк': '4416724',
    'монголианстардистрибьюшнххк': '5750067',
    'эрдэнэтсуваргахк': '2007908',
    'хаанбулагинтернэшнлххк': '6195598',
    'ньюкөмпропертиххк': '2876094',
    'оюоттолгойресурсесххк': '5476313',
    'спейшлайзкарьерконсалтингххк': '5350883',
    'мбисиазиапасификххк': '5027292',
    'силкроуттрейдингххк': '5388406',
    'азифармаххк': '2603848',
    'соулсэниорстоверххк': '5466820',
    'витафитдистрибьюшнххк': '2583542',
    'немөркредитббсбххк': '5928907',
    'нөмөркредитббсбххк': '5928907',
    'говинфраструктурпартнерсххк': '5495806',
    'алтайхолдингххк': '2057573',
    'айбиайжиххк': '5252806',
    'таванордххк': '6403077',
    'таванбогдинтернэшнлххк': '2074354',
    'манхийнбаянгалххк': '5118115',
    'мөнхийнбаянгалххк': '5118115',
    'цагаануулынмагнитххк': '5096502',
    'тодундрааххк': '2704781',
    'нэкстэлектрониксххк': '5337631',
    'тераэкспрессххк': '5429731',
    'бриллиантсклиникххк': '5032997',
    'хуавейтехнолоҗиххк': '5772184',
    'этрансложистикххк': '3309665',
    'бидббсбххк': '2672138'
}

# 3. Read Top 300
print("3. Processing Top 300...")
wb300 = openpyxl.load_workbook('/Users/enkhbadraltsogbayar/Downloads/Топ 300.xlsx', data_only=True)
ws300 = wb300.active

all_resolved = []
unresolved = []

for r in range(3, ws300.max_row + 1):
    for c_type, n_col, name_col, em_col, web_col in [('ХХК', 2, 3, 4, 5), ('ХК', 7, 8, 9, 10)]:
        num = ws300.cell(r, n_col).value
        name = ws300.cell(r, name_col).value
        em = ws300.cell(r, em_col).value
        web = ws300.cell(r, web_col).value
        
        if not name:
            continue
            
        sname = str(name).strip()
        clean_sname = normalize_text(sname)
        ck = clean_key(sname)
        
        res_entry = {
            'col_type': c_type,
            'num': num,
            'original_name': sname,
            'email': str(em or '').strip(),
            'web': str(web or '').strip(),
            'reg_no': '',
            'official_name': '',
            'sh': '', 'dr': '', 'ubo': '',
            'vis': '', 'mis': '',
            'match_source': ''
        }
        
        # 1. Top 100 check
        if ck in top100_map:
            t = top100_map[ck]
            res_entry['reg_no'] = t['reg_no']
            res_entry['official_name'] = t['name']
            res_entry['web'] = res_entry['web'] or t['web']
            res_entry['sh'] = t['sh']
            res_entry['dr'] = t['dr']
            res_entry['ubo'] = t['ubo']
            res_entry['vis'] = t['vis']
            res_entry['mis'] = t['mis']
            res_entry['match_source'] = 'Top 100 Verified'
            all_resolved.append(res_entry)
            continue
            
        # 2. Manual override
        if ck in MANUAL_REG_MAP:
            reg_target = MANUAL_REG_MAP[ck]
            if reg_target in les_by_reg:
                p = parse_les(les_by_reg[reg_target])
                res_entry['reg_no'] = p['reg_no']
                res_entry['official_name'] = p['official_name']
                res_entry['sh'] = p['sh']
                res_entry['dr'] = p['dr']
                res_entry['ubo'] = p['ubo']
                res_entry['match_source'] = 'Manual UBEG'
                all_resolved.append(res_entry)
                continue
                
        # 3. Les by clean_key
        les_row = les_by_key.get(ck)
        if not les_row:
            les_row = les_by_exact.get(clean_sname.lower())
            
        if les_row:
            p = parse_les(les_row)
            res_entry['reg_no'] = p['reg_no']
            res_entry['official_name'] = p['official_name']
            res_entry['sh'] = p['sh']
            res_entry['dr'] = p['dr']
            res_entry['ubo'] = p['ubo']
            res_entry['match_source'] = 'UBEG LesOutputJson'
            all_resolved.append(res_entry)
        else:
            unresolved.append(res_entry)

print(f"\nRESOLUTION COMPLETED:")
print(f"Total resolved: {len(all_resolved)} / 467 ({len(all_resolved)/467*100:.1f}%)")
print(f"Unresolved remaining: {len(unresolved)}")

if unresolved:
    for u in unresolved:
        print(f"STILL UNRESOLVED: [{u['col_type']} #{u['num']}] {u['original_name']}")

# Save resolved dataset to JSON for Phase 2
with open('/Users/enkhbadraltsogbayar/Tender data/top300_resolved_step1.json', 'w', encoding='utf-8') as f:
    json.dump(all_resolved, f, ensure_ascii=False, indent=2)
print("Saved resolved entities to top300_resolved_step1.json")
