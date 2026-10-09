# -*- coding: utf-8 -*-
"""
Build Complete Top 300 Enterprise Dataset:
- Phase 1: Cross-reference with UBEG LesOutputJson & Top 100
- Phase 2: Attach verified Vision (Алсын хараа) and Mission (Эрхэм зорилго)
- Phase 3: Generate beautifully styled Excel workbook & Markdown summary
"""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import json
import re
import os
from master_vm_dataset import lookup_verified_vm

def normalize_text(s):
    if not s: return ''
    s = str(s).strip()
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

def clean_url(u):
    if not u: return ''
    u = str(u).strip()
    if not u or 'facebook.com' in u.lower() or 'fb.com' in u.lower():
        return ''
    if not u.startswith('http://') and not u.startswith('https://'):
        u = 'https://' + u
    return u

print("1. Loading Top 100 Verified Data...")
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
        'vis': str(vis).strip() if vis else '-',
        'mis': str(mis).strip() if mis else '-'
    }
    top100_map[clean_key(name)] = entry
    if reg:
        top100_map[f"reg_{reg}"] = entry

print(f"Top 100 indexed: {len(top100_map)} records")

print("2. Loading UBEG LesOutputJson...")
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
    'бидисэк': '2052482',
    'бьюлдингмэйнтэнэнссервисэс': '5892694',
    'бюлдингмэйнтэнэнссервисэс': '5892694',
    'тандэминвэст': '2013916',
    'этрансложистик': '3309665',
    'эрдэнэрэсурсдэвэлопмэнткорпорэишн': '2007908',
    'ачиталкабы': '2003937',
    'блюскаисэкьюритиз': '2057816',
    'виинтэрнэшнл': '6450539',
    'гурил': '2002027',
    'тунгуанмаинсконстракшнмонгол': '6028047',
    'эвроазиакапитал': '2036282',
    'ихбарилга': '2001772',
    'номинбизнэсклуббаруунбус': '6886973',
    'наноинтэрнэшнл': '5138132',
    'монголсэкюритиэс': '2587904',
    'номинбизнэсклубзүүнбус': '6886949',
    'тэнгэрлэгмэдиа': '2866692',
    'хасумандал': '2007410',
    'жиэнбэврэжис': '5258537',
    'мишээл': '4416724',
    'монголианстардистрибьюшн': '5750067',
    'эрдэнэтсуварга': '2007908',
    'хаанбулагинтэрнэшнл': '6195598',
    'ньюкөмпропэрти': '2876094',
    'оюоттолгоирэсурсэс': '5476313',
    'спэишлаизкарьэрконсалтинг': '5350883',
    'силкроуттрэидинг': '5388406',
    'соулсэниорстовэр': '5466820',
    'витафитдистрибьюшн': '2583542',
    'нэмөркрэдитббсб': '5928907',
    'говьинфраструктурпартнэрс': '5495806',
    'алтаи': '2057573',
    'аибиаижи': '5252806',
    'таванбогдинтэрнэшнл': '2074354',
    'манхиинбаянгал': '5118115',
    'тодундраа': '2704781',
    'нэкстэлектроникс': '5337631',
    'тераэкспресс': '5429731',
    'бриллиантсклиник': '5032997',
    'хуавеитэхноложи': '5772184',
    'бидббсб': '2672138',
    'титисиэндти': '5411777',
    'хасумандал': '2003147',
    'соулсэниорстовэр': '5302927'
}

# 3. Load crawled vision/mission data
print("3. Loading Crawled Vision & Mission Data...")
with open('/Users/enkhbadraltsogbayar/Tender data/crawled_vm_results.json', 'r', encoding='utf-8') as f:
    crawled_vm = json.load(f)

# Verified manual corporate vision & mission additions (sourced verbatim from official sites / reports)
VERIFIED_CORPORATE_VM = {
    'Богдбанк ХК': (
        "Дэлхийн шилдэг стандарт, туршлага, шинэ үеийн хандлага боломж, технологийн дэвшлийг ашиглан банк, санхүүгийн бүтээгдэхүүн, үйлчилгээ, үнэ цэнийг төдийгүй ирээдүйдээ, өөртөө, банкандаа итгэх итгэлийг түгээгч банк байна.",
        "Харилцагчид, ажилтнууд, хөрөнгө оруулагчдынхаа сэтгэл ханамжийг тэнцвэртэй, тогтвортой хангаж, үйлчилгээний чанар, хүртээмж, үр ашгийн үзүүлэлтээрээ олон улсын жишигт хүрсэн, харилцааг эрхэмлэсэн, бүтээгдэхүүн үйлчилгээгээр дамжуулан ирээдүйдээ, өөртөө, банкандаа итгэх итгэлийг түгээгч, технологид суурилсан банк байна."
    ),
    'Түмэн Шувуут ХК': (
        "Хөдөө аж ахуйн бүтээгдэхүүнээр дэлхийд тэргүүлнэ.",
        "Эрүүл, экологийн бүтээгдэхүүнээр амьдралын чанарыг дээшлүүлнэ."
    ),
    'Ариг Банк ХК': (
        "Худалдааны салбарт түшиглэсэн дижитал банк болох.",
        "Ухаан, Хүсэл, Уран сэтгэмж бүхий улам шинэлэг хамт олноороо уулзсан бүхний сэтгэлийг хөдөлгөх банк."
    ),
    'Мандал даатгал ХК': (
        "Азийн тавцанд өрсөлдөх даатгал, санхүүгийн олон улсын брэндийг бий болгох.",
        "Өнөөдрөө баталгаажуулсан маргаашийг иргэн бүрд."
    ),
    'Лэндмн ББСБ ХК': (
        "Дэвшилтэт технологи дээр суурилсан, дэлхийн энтэй санхүүгийн үйлчилгээний хөтөч байна.",
        "Санхүүгийн үйлчилгээнд бүрэн хамрагдаж чаддаггүй хүмүүст хүрэх шинэлэг үйлчилгээгээр хэрэглэгчдээ хангасан, нийгмийн хариуцлагыг гүнээ ухамсарласан хамт олон байна."
    ),
    'Ард даатгал ХК': (
        "Даатгуулагчдын эрэлт хэрэгцээ, шаардлагад бүрэн нийцсэн, тэдний амар тайван амьдралын баталгааг хангасан үйлчилгээг үзүүлж, харилцагчдаа амжилтад хөтөлсөн, нийгмийн хариуцлагыг дээдлэгч, ил тод, итгэл төрүүлсэн тэргүүлэгч даатгагч байна.",
        "Даатгуулагчийн хэрэгцээ шаардлагад бүрэн нийцсэн, мэргэжлийн ёс зүйг баримталсан, даатгалын шилдэг үйлчилгээг бид үзүүлнэ."
    ),
    'Ард санхүүгийн нэгдэл ХК': (
        "Бүс нутагтаа тэргүүлэгч финтек нэгдэл болох.",
        "Хөрөнгө Оруулагч Үндэстэнг цогцлооно."
    ),
    'Ард кредит ББСБ ХК': (
        "Бүс нутагтаа тэргүүлэгч финтек нэгдэл болох.",
        "Хөрөнгө Оруулагч Үндэстэнг цогцлооно."
    ),
    'Монос Хүнс ХК': (
        "Эх дэлхийгээ хайрлаж, эрүүл амьдралыг хамтдаа бүтээнэ.",
        "Хүрээлэн буй орчин, оролцогч талуудаа хүндэлсэн, эрүүл амьдралын хэв маягийг дэлгэрүүлэгч, үнэ цэнэ бүтээгч хамт олон байна."
    ),
    'Улаанбаатар БҮК ХК': (
        "Бид бүтээн байгуулалтыг цогцлоож, салбартаа түүчээлнэ.",
        "Бид аюулгүй ажиллагаа, технологийн шийдэл, чанарыг эрхэмлэн, найдвартай бүтээгдэхүүн үйлчилгээгээр хэрэглэгчдийн итгэлийг хүлээнэ."
    ),
    'Газар шим үйлдвэр ХК': (
        "Дэлхийн жишигт хүрнэ.",
        "Хүнээ дээдлэн эрүүл, чанартай хүнс үйлдвэрлэгч, шинийг санаачлагч, тогтвортой хөгжлийг хэрэгжүүлэгч компани байна."
    ),
    'Алтайн зам ХК': (
        "Монгол улсын уул уурхайн үйлдвэрлэлийн салбарын шинэчлэлд манлайлагч байж, тэргүүлэх орон зайг эзэлнэ.",
        "Хөгжигч хүний нөөц, дэвшилтэт техник технологи, оновчтой менежментийн шийдлээр оролцогч талуудын сэтгэл ханамжийг тасралтгүй нэмэгдүүлж, тогтвортой хөгжинө."
    ),
    'Би Ди Сек ХК': (
        "Үндэсний үйлдвэрлэлийг хөрөнгө оруулалт, технологид суурилсан санхүүгийн цогц үйлчилгээгээр дэмжиж, чинээлэг харилцагч, нийгмийн баялаг үнэт зүйлийг бий болгох.",
        "Олон улсын стандартад нийцсэн үйл ажиллагаа явуулах, үндэсний томоохон хувьцаат компаниудыг шинээр бий болгох."
    ),
    'Дархан Сэлэнгийн Цахилгаан Түгээх Сүлжээ ХК': (
        "Эрчим хүчийг дэвшилтэт технологиор хэрэглэгчдэд хүргэнэ.",
        "Чадварлаг хүний нөөцөд тулгуурлан аюулгүй ажиллагааг эрхэмлэж, дэвшилтэт технологийг нэвтрүүлэн, хэрэглэгчээ дээдэлсэн, салбартаа тэргүүлэгч болно."
    ),
    'Багануур ХК': (
        "Монгол улсын нүүрсний салбарын чиг хандлагыг тодорхойлогч байна.",
        "Байгаль орчинд сөрөг нөлөөлөл багатай үйлдвэрлэл явуулж, бүтээгдэхүүн үйлчилгээгээрээ тэргүүлсэн, эдийн засгийн чадавхитай, мэргэшсэн хамт олон бүрдүүлсэн суралцагч компани болно."
    ),
    'Шивээ Овоо ХК': (
        "Эрчим хүчний нүүрсний олборлолтоор Монгол Улсын тэргүүний компани болох.",
        "Байгаль орчинд ээлтэй, аюулгүй үйлдвэрлэл, өндөр бүтээмж бүхий уул уурхайн салбарын жишиг компани байна."
    ),
    'Монгол шуудан ХК': (
        "Дэлхийн дэвшилтэт технологид хүрсэн, чанартай, цогц үйлчилгээгээр хүн бүрийн шуудангийн хэрэгцээг төгс хангах.",
        "Мэргэжлийн, хүртээмжтэй үйлчилгээгээр дамжуулж нийгэм эдийн засгийн тогтвортой хөгжилд хувь нэмэр оруулах."
    ),
    'Монгол базальт ХК': (
        "Галт уулын чулуулгийг чулуун хөвөн болгон хувиргаж, нийгэмд тулгарч буй уур амьсгалын өөрчлөлтийн томоохон сорилтуудыг шийдвэрлэхэд хувь нэмэр оруулах бүтээгдэхүүн үйлдвэрлэж, орчин үеийн амьдралыг баяжуулж, аюулгүй, эрүүл, уур амьсгалд илүү тэсвэртэй, тогтвортой нийгмийг цогцлооно.",
        "Инноваци шингэсэн үйлдвэрлэл технологиороо салбараа манлайлан хөгжүүлж, хүний амьдрах орчинг эрүүл тав тухтай, байгаль дэлхийд ээлтэй, барилга хийцийн эрсдэлгүй, ирээдүй хойчдоо өвлүүлэн үлдээх, ямагт өсөх үнэ цэнэ бүхий баталгаат хөрөнгө оруулалтыг бий болгохыг ямагт эрмэлзэнэ."
    ),
    'Монгол секюритиес ХК': (
        "Дэлхийгээс өгөөж хүртэх гүүр.",
        "Монголын болон гадаадын хөрөнгийн зах зээлийн оролцогчдод мэргэжлийн бүтээгдэхүүн үйлчилгээг хүргэх."
    ),
    'Тандэм инвест ХК': (
        "Санхүүгийн зах зээлд шинэ бүтээгдэхүүн, үйлчилгээг нэвтрүүлж, иргэд болон бизнес эрхлэгчдийг дэмжин ажиллах.",
        "Харилцагчийн эрэлт хэрэгцээнд тулгуурласан бүтээгдэхүүн, үйлчилгээг хүргэх."
    ),
    'Нэкст–Электроникс ХХК': (
        "Дэлхийн жишигт хүрсэн төгс үйлчилгээ, өргөн сонголтыг Монгол орон даяар түгээх тэргүүлэгч худалдааны сүлжээг бий болгоно.",
        "Бид амьдралыг аз жаргалд хөтлөх технологийн дэвшлийг түгээнэ."
    ),
    'Ньюкөм Проперти ХХК': (
        "Олон улсын шилдэг туршлага, шинэлэг технологийг нэвтрүүлэх.",
        "Үл хөдлөх хөрөнгийн үнэ цэнийг бүтээх, хөрөнгө эзэмшигч болон оршин суугчдад ажиллаж амьдрах хамгийн таатай, цэвэр, аюулгүй орчныг бүрдүүлэх."
    ),
    'Нано Интернэшнл ХХК': (
        "NANO VISION 2030 стратегийн хүрээнд бүс нутагтаа тэргүүлэгч дистрибьютор, үнэ цэнэ бүтээгч байгууллага болно.",
        "Дэлхийн шилдэг бүтээгдэхүүнүүдийг үйлдвэрээс гарсан тэр л өндөр чанар, инновацтайгаар хэрэглэгчдэдээ бүхнээс түрүүнд хүргэх."
    )
}

print("4. Processing Top 300 workbook...")
wb300 = openpyxl.load_workbook('/Users/enkhbadraltsogbayar/Downloads/Топ 300.xlsx', data_only=True)
ws300 = wb300.active

def process_entity_row(num, sname, em, web, c_type):
    clean_sname = normalize_text(sname)
    ck = clean_key(sname)
    
    item = {
        'num': num,
        'type': c_type,
        'original_name': sname,
        'official_name': '',
        'reg_no': '',
        'web': clean_url(web) or str(web or '').strip(),
        'email': str(em or '').strip(),
        'sh': '',
        'dr': '',
        'ubo': '',
        'vis': '-',
        'mis': '-',
        'matched': False
    }
    
    # 1. Top 100 check by clean key
    t = top100_map.get(ck)
    if t:
        item['official_name'] = t['name']
        item['reg_no'] = t['reg_no']
        item['web'] = item['web'] or t['web']
        item['sh'] = t['sh']
        item['dr'] = t['dr']
        item['ubo'] = t['ubo']
        if t['vis'] and t['vis'] != '-': item['vis'] = t['vis']
        if t['mis'] and t['mis'] != '-': item['mis'] = t['mis']
        item['matched'] = True
        
    # 2. Manual Reg Map check
    if not item['matched'] and ck in MANUAL_REG_MAP:
        reg_target = MANUAL_REG_MAP[ck]
        if reg_target in les_by_reg:
            p = parse_les(les_by_reg[reg_target])
            item['official_name'] = p['official_name']
            item['reg_no'] = p['reg_no']
            item['sh'] = p['sh']
            item['dr'] = p['dr']
            item['ubo'] = p['ubo']
            item['matched'] = True
            
    # 3. LesOutputJson lookup
    if not item['matched']:
        les_row = les_by_key.get(ck)
        if not les_row:
            les_row = les_by_exact.get(clean_sname.lower())
        if les_row:
            p = parse_les(les_row)
            item['official_name'] = p['official_name']
            item['reg_no'] = p['reg_no']
            item['sh'] = p['sh']
            item['dr'] = p['dr']
            item['ubo'] = p['ubo']
            item['matched'] = True

    # 4. Check Top 100 map by reg if not already filled
    if item['reg_no']:
        reg_key = f"reg_{item['reg_no']}"
        if reg_key in top100_map:
            t_reg = top100_map[reg_key]
            if not item['sh']: item['sh'] = t_reg['sh']
            if not item['dr']: item['dr'] = t_reg['dr']
            if not item['ubo']: item['ubo'] = t_reg['ubo']
            if item['vis'] == '-' and t_reg['vis'] != '-': item['vis'] = t_reg['vis']
            if item['mis'] == '-' and t_reg['mis'] != '-': item['mis'] = t_reg['mis']

    # 5. Master Verified Dataset lookup (by reg, exact name, or clean key)
    if item['vis'] == '-' or item['mis'] == '-':
        v_cand, m_cand, _ = lookup_verified_vm(sname, item['reg_no'], item['official_name'])
        if v_cand and v_cand != '-' and item['vis'] == '-':
            item['vis'] = v_cand
        if m_cand and m_cand != '-' and item['mis'] == '-':
            item['mis'] = m_cand

    # 6. Local verified map
    if item['vis'] == '-' or item['mis'] == '-':
        if sname in VERIFIED_CORPORATE_VM:
            v, m = VERIFIED_CORPORATE_VM[sname]
            if v and item['vis'] == '-': item['vis'] = v
            if m and item['mis'] == '-': item['mis'] = m
        elif ck in VERIFIED_CORPORATE_VM:
            v, m = VERIFIED_CORPORATE_VM[ck]
            if v and item['vis'] == '-': item['vis'] = v
            if m and item['mis'] == '-': item['mis'] = m

    # 7. Crawled results if still empty
    if item['vis'] == '-' or item['mis'] == '-':
        if sname in crawled_vm:
            c_res = crawled_vm[sname]
            if item['vis'] == '-' and c_res.get('vis') and len(c_res['vis']) >= 5:
                v_clean = c_res['vis'].split('\n')[0].strip()
                if len(v_clean) >= 5: item['vis'] = v_clean
            if item['mis'] == '-' and c_res.get('mis') and len(c_res['mis']) >= 5:
                m_clean = c_res['mis'].split('\n')[0].strip()
                if len(m_clean) >= 5: item['mis'] = m_clean

    return item

hhk_list = []
hk_list = []

for r in range(3, ws300.max_row + 1):
    # HHK
    n_hhk = ws300.cell(r, 2).value
    name_hhk = ws300.cell(r, 3).value
    em_hhk = ws300.cell(r, 4).value
    web_hhk = ws300.cell(r, 5).value
    if name_hhk:
        hhk_list.append(process_entity_row(n_hhk, str(name_hhk).strip(), em_hhk, web_hhk, 'ХХК'))
        
    # HK
    n_hk = ws300.cell(r, 7).value
    name_hk = ws300.cell(r, 8).value
    em_hk = ws300.cell(r, 9).value
    web_hk = ws300.cell(r, 10).value
    if name_hk:
        hk_list.append(process_entity_row(n_hk, str(name_hk).strip(), em_hk, web_hk, 'ХК'))

print(f"\nProcessing Summary:")
print(f"ХХК Total: {len(hhk_list)}, Matched UBEG: {sum(1 for x in hhk_list if x['matched'])} / {len(hhk_list)}")
print(f"ХК Total: {len(hk_list)}, Matched UBEG: {sum(1 for x in hk_list if x['matched'])} / {len(hk_list)}")
print(f"Total with Vision: {sum(1 for x in hhk_list+hk_list if x['vis'] != '-')}")
print(f"Total with Mission: {sum(1 for x in hhk_list+hk_list if x['mis'] != '-')}")

# 5. Build Styled Excel Workbook
print("5. Generating Styled Excel Workbook...")
wb_out = openpyxl.Workbook()
# remove default sheet
wb_out.remove(wb_out.active)

# Styles
font_title = Font(name="Arial", size=14, bold=True, color="1F4E79")
font_sub = Font(name="Arial", size=10, italic=True, color="555555")
font_header = Font(name="Arial", size=10, bold=True, color="FFFFFF")
font_body = Font(name="Arial", size=9, bold=False, color="000000")
font_body_bold = Font(name="Arial", size=9, bold=True, color="000000")
font_reg = Font(name="Arial", size=9, bold=True, color="1F4E79")

fill_header = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
fill_zebra = PatternFill(start_color="F2F5F8", end_color="F2F5F8", fill_type="solid")

thin_border_side = Side(border_style="thin", color="D9D9D9")
border_cell = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)

HEADERS = [
    ("Эрэмбэ", 10, align_center),
    ("Компанийн нэр", 30, align_left),
    ("Регистрийн дугаар", 16, align_center),
    ("Улсын бүртгэлийн нэр", 30, align_left),
    ("Албан ёсны вэбсайт", 32, align_left),
    ("И-мэйл хаяг", 26, align_left),
    ("Хувьцаа эзэмшигч", 40, align_left),
    ("Гүйцэтгэх захирал", 26, align_left),
    ("Эцсийн өмчлөгч", 32, align_left),
    ("Алсын хараа", 45, align_left),
    ("Эрхэм зорилго", 50, align_left),
]

def write_sheet(ws, title_text, rows_data):
    # Title rows
    ws.merge_cells("A1:K1")
    ws["A1"] = title_text
    ws["A1"].font = font_title
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28
    
    ws.merge_cells("A2:K2")
    ws["A2"] = "Эх сурвалж: УБЕГ (Олон нийтийн нээлттэй өгөгдөл), Албан ёсны вэбсайтууд · Огноо: 2026 он"
    ws["A2"].font = font_sub
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 18
    
    # Header row
    header_row = 4
    ws.row_dimensions[header_row].height = 26
    for col_idx, (h_name, width, align) in enumerate(HEADERS, start=1):
        cell = ws.cell(header_row, col_idx)
        cell.value = h_name
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_header
        cell.border = border_cell
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width
        
    # Data rows
    curr_row = 5
    for item in rows_data:
        ws.row_dimensions[curr_row].height = 28
        row_vals = [
            item['num'],
            item['original_name'],
            item['reg_no'],
            item['official_name'] or item['original_name'],
            item['web'],
            item['email'],
            item['sh'] or "-",
            item['dr'] or "-",
            item['ubo'] or "-",
            item['vis'] or "-",
            item['mis'] or "-"
        ]
        
        is_zebra = (curr_row % 2 == 0)
        for col_idx, val in enumerate(row_vals, start=1):
            cell = ws.cell(curr_row, col_idx)
            cell.value = val
            cell.font = font_reg if col_idx == 3 else (font_body_bold if col_idx in [1, 2] else font_body)
            cell.alignment = HEADERS[col_idx - 1][2]
            cell.border = border_cell
            if is_zebra:
                cell.fill = fill_zebra
                
        curr_row += 1
        
    ws.freeze_panes = "A5"

# Sheet 1: HHK
ws_hhk = wb_out.create_sheet(title="ТОП 300 ХХК")
write_sheet(ws_hhk, "Монгол Улсын ТОП 300 Хязгаарлагдмал Хариуцлагатай Компани (ХХК) - Бүрэн мэдээлэл", hhk_list)

# Sheet 2: HK
ws_hk = wb_out.create_sheet(title="ТОП 167 ХК")
write_sheet(ws_hk, "Монгол Улсын ТОП 167 Хувьцаат Компани (ХК) - Бүрэн мэдээлэл", hk_list)

# Sheet 3: Unified
all_combined = hhk_list + hk_list
ws_all = wb_out.create_sheet(title="Нэгдсэн жагсаалт (467)")
write_sheet(ws_all, "Монгол Улсын ТОП 300 ААН & Хувьцаат Компаниудын Нэгдсэн Жагсаалт (Нийт 467)", all_combined)

out_path_1 = "/Users/enkhbadraltsogbayar/Tender data/1_Монгол_Улсын_ТОП_300_ААН_Бүрэн_мэдээлэл.xlsx"
out_path_2 = "/Users/enkhbadraltsogbayar/Downloads/1_Монгол_Улсын_ТОП_300_ААН_Бүрэн_мэдээлэл.xlsx"

wb_out.save(out_path_1)
wb_out.save(out_path_2)
print(f"Saved Excel to:\n  1. {out_path_1}\n  2. {out_path_2}")

# 6. Generate Markdown Summary Report
md_lines = [
    "# 📊 Монгол Улсын ТОП 300 ААН & Хувьцаат Компаниудын Бүрэн Мэдээлэл",
    "",
    "Энэхүү судалгааны тайланд `Топ 300.xlsx` файлд тусгагдсан **300 ХХК** болон **167 ХК** (нийт 467 хуулийн этгээд)-ийг УБЕГ-ын албан ёсны сантай тулган регистрийн дугаар, эрх бүхий удирдлага, хувьцаа эзэмшигчдийн мэдээллийг татаж, албан ёсны вэбсайтуудаас баталгаат **Алсын хараа**, **Эрхэм зорилго**-ыг нэгтгэн харуулав.",
    "",
    "## 📈 Ерөнхий статистик",
    "",
    f"- **Нийт боловсруулсан хуулийн этгээд:** 467",
    f"- **Хязгаарлагдмал хариуцлагатай компани (ХХК):** {len(hhk_list)}",
    f"- **Хувьцаат компани (ХК):** {len(hk_list)}",
    f"- **УБЕГ-ын сантай баталгаажсан регистрийн дугаар:** {sum(1 for x in all_combined if x['matched'])} / 467 ({sum(1 for x in all_combined if x['matched'])/len(all_combined)*100:.1f}%)",
    f"- **Алсын хараа тодорхойлогдсон:** {sum(1 for x in all_combined if x['vis'] != '-')}",
    f"- **Эрхэм зорилго тодорхойлогдсон:** {sum(1 for x in all_combined if x['mis'] != '-')}",
    f"- **Дүрэм:** Вэб дээрээ нийтлээгүй байгууллагуудын хувьд зохиож бичилгүйгээр зураас (`-`) хэлбэрээр ил тод үлдээсэн.",
    "",
    "## 📑 Файлын бүтэц (Excel)",
    "",
    "Үүсгэсэн Excel файлд (`1_Монгол_Улсын_ТОП_300_ААН_Бүрэн_мэдээлэл.xlsx`) дараах 3 хуудас агуулагдсан:",
    "1. **`ТОП 300 ХХК`** - 300 ХХК-ийн бүрэн бүртгэл, регистр, холбоо барих, удирдлага, алсын хараа, эрхэм зорилго.",
    "2. **`ТОП 167 ХК`** - 167 ХК-ийн бүрэн бүртгэл, регистр, хувьцаа эзэмшигч, алсын хараа, эрхэм зорилго.",
    "3. **`Нэгдсэн жагсаалт (467)`** - Бүх 467 компанийн нэгдсэн тайлан.",
    "",
    "## 🏆 ТОП 30 Компанийн дээж (Жишээ мэдээлэл)",
    "",
    "| № | Компанийн нэр | Регистр | Вэбсайт | Алсын хараа | Эрхэм зорилго |",
    "|---|---|---|---|---|---|"
]

for item in all_combined[:30]:
    v_snippet = (item['vis'][:60] + '...') if len(item['vis']) > 60 else item['vis']
    m_snippet = (item['mis'][:60] + '...') if len(item['mis']) > 60 else item['mis']
    w_snippet = f"[{item['web'].split('//')[-1][:20]}]({item['web']})" if item['web'] else "-"
    md_lines.append(f"| {item['num']} | **{item['original_name']}** | `{item['reg_no']}` | {w_snippet} | {v_snippet} | {m_snippet} |")

md_content = "\n".join(md_lines)
with open("/Users/enkhbadraltsogbayar/Tender data/ТОП_300_ААН_Бүрэн_мэдээлэл.md", "w", encoding="utf-8") as f:
    f.write(md_content)
print("Saved Markdown report to ТОП_300_ААН_Бүрэн_мэдээлэл.md")
