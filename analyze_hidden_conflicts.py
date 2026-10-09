"""
analyze_hidden_conflicts_v3.py
v2 дээр нэмэлт ухаалаг шүүлтүүд:

SCORING SYSTEM (0-100 оноо):
  +30  Нэр XACXOM-д зөвхөн 1 удаа таардаг (homonym биш)
  +20  Хүйс таарч байна (УБЕГ SH/Dir хүйс ↔ нэрийн хүйсийн таамаг)
  +15  Газар зүйн нийцэл (аймаг таарч байна)
  +15  Албан тушаал өндөр (дарга, захирал, засаг дарга, сайд, УИХ)
  +10  Мэдүүлээгүй (ХОМ-д тухайн компани дурдагдаагүй)
  +10  Дүн их (Шилэн дансаар 100 сая+)
  +5   Эцсийн өмчлөгч (BO) - хамгийн нуугдмал
  -20  Нэр XACXOM-д 3+ удаа таардаг (homonym өндөр эрсдэл)
"""

import json
import re
import pandas as pd
import time
from collections import defaultdict, Counter

def clean_name(n):
    if not isinstance(n, str): return ''
    # Зураас, цэгтэй тэмдэгтүүдийг хасах (цэнд-аюуш → цэндаюуш)
    s = n.strip().lower()
    s = s.replace('-', '').replace('.', '').replace(' ', '')
    # Гэхдээ Овог, Нэр нь тусдаа ирдэг тул хоорондын зай хэрэггүй
    return s

def norm_company(s):
    if not isinstance(s, str): return ''
    s = s.upper().strip()
    s = re.sub(r'[\"\'«»""/\\,\(\)\[\]\-_.]', ' ', s)
    s = re.sub(r'\b(ХХК|ХК|ОНӨААТҮГ|ТӨХК|ТӨҮГ|ББСБ|ЗГҮГ|УТҮГ|НҮТББ|ТББ|ОНӨҮГ|ХЗХ|ААН|ХЯЗГААРЛАГДМАЛ ХАРИУЦЛАГАТАЙ КОМПАНИ|ХУВЬЦААТ КОМПАНИ)\b', ' ', s)
    s = re.sub(r'\s+', '', s)
    return s.strip()

SELF_DEALING_STOP_WORDS = {
    'аймгийн', 'сумын', 'засаг', 'даргын', 'тамгын', 'газар', 'газрын',
    'төв', 'нийслэлийн', 'дүүргийн', 'хорооны', 'улсын', 'монгол',
    'эрүүл', 'мэндийн', 'боловсролын', 'сургуулийн', 'цэцэрлэгийн',
    'цэргийн', 'дугаар', 'анги', 'ангийн', 'хэлтэс', 'хэлтсийн',
    'даатгалын', 'сангийн', 'үндэсний', 'ерөнхий',
}

AIMAGS = {
    'архангай': 'Архангай', 'баян-өлгий': 'Баян-Өлгий', 'баянхонгор': 'Баянхонгор',
    'булган': 'Булган', 'говь-алтай': 'Говь-Алтай', 'говьсүмбэр': 'Говьсүмбэр',
    'дархан': 'Дархан-Уул', 'дорноговь': 'Дорноговь', 'дорнод': 'Дорнод',
    'дундговь': 'Дундговь', 'завхан': 'Завхан', 'орхон': 'Орхон',
    'өвөрхангай': 'Өвөрхангай', 'өмнөговь': 'Өмнөговь', 'сүхбаатар': 'Сүхбаатар',
    'сэлэнгэ': 'Сэлэнгэ', 'увс': 'Увс', 'ховд': 'Ховд',
    'хөвсгөл': 'Хөвсгөл', 'хэнтий': 'Хэнтий',
    'баянгол': 'Улаанбаатар', 'чингэлтэй': 'Улаанбаатар', 'сүхбаатар дүүрэг': 'Улаанбаатар',
    'хан-уул': 'Улаанбаатар', 'сонгинохайрхан': 'Улаанбаатар', 'багануур': 'Улаанбаатар',
    'баянзүрх': 'Улаанбаатар', 'налайх': 'Улаанбаатар',
}

# Монгол эмэгтэй нэрсийн нийтлэг дагаврууд
FEMALE_SUFFIXES = ['маа', 'маа', 'цэцэг', 'чимэг', 'туяа', 'зул', 'сүрэн', 'лхам', 'жаргал']
MALE_SUFFIXES = ['бат', 'болд', 'баяр', 'сүрэн', 'дорж', 'жав', 'хүү', 'ганбаатар']

def guess_gender(first_name):
    """Нэрээс хүйсийг таамаглах"""
    fn = first_name.lower().strip()
    for s in FEMALE_SUFFIXES:
        if fn.endswith(s):
            return 'Эм'
    for s in MALE_SUFFIXES:
        if fn.endswith(s):
            return 'Эр'
    return None

def extract_aimag(text):
    """Текстээс аймгийн нэр олох"""
    if not text: return set()
    t = text.lower()
    found = set()
    for key, name in AIMAGS.items():
        if key in t:
            found.add(name)
    return found

def is_high_ranking(position):
    """Өндөр албан тушаалтан эсэх"""
    if not position: return False
    pos = position.lower()
    high_kw = ['сайд', 'уих', 'ерөнхийлөгч', 'засаг дарга', 'газрын дарга',
               'захирал', 'хэлтсийн дарга', 'албаны дарга', 'дэд дарга',
               'орлогч дарга', 'тамгын газрын дарга', 'ерөнхий менежер']
    return any(k in pos for k in high_kw)

def is_self_dealing_v2(org_a, org_b):
    a = clean_name(org_a)
    b = clean_name(org_b)
    if not a or not b or a == '-' or b == '-': return False
    if len(a) > 10 and len(b) > 10:
        if a in b or b in a:
            return True
    words_a = set([w for w in a.split() if len(w) > 3 and w not in SELF_DEALING_STOP_WORDS])
    words_b = set([w for w in b.split() if len(w) > 3 and w not in SELF_DEALING_STOP_WORDS])
    if not words_a or not words_b: return False
    if len(words_a.intersection(words_b)) >= 2:
        return True
    return False

def main():
    print("=" * 70)
    print("  УХААЛАГ ШҮҮЛТТЭЙ БҮРЭН ШАЛГАЛТ (v4 - Бүх жилийн дата)")
    print("=" * 70)
    
    start_time = time.time()
    
    # ===== 1. Тендерийн компаниуд =====
    print("\n1. Loading tender + shilendans data...")
    with open('tender_companies_ai_verified.json', 'r', encoding='utf-8') as f:
        av_data = json.load(f)
    all_tender_regs = {}
    for t in av_data:
        reg = str(t.get('регистрийн_дугаар', '')).strip()
        if not reg or reg == 'None': continue
        # Тендерийн оны задаргаа
        tender_years = set()
        for yr in range(2021, 2026):
            cnt = t.get(f'count_{yr}', 0)
            if cnt and cnt > 0:
                tender_years.add(yr)
        all_tender_regs[reg] = {
            'name': t.get('тендерийн_нэр') or t.get('бүртгэлийн_нэр', ''),
            'total_tenders': t.get('тендерийн_тоо', 0),
            'total_amount': t.get('гэрээний_нийт_дүн', 0),
            'tender_years': tender_years,
        }

    with open('shilendans_matches.json', 'r', encoding='utf-8') as f:
        sd_data = json.load(f)
    sd_by_reg = defaultdict(lambda: {'sd_amount': 0, 'state_orgs': set()})
    for row in sd_data:
        reg = str(row.get('register_no', '')).strip()
        if not reg or reg == 'None': continue
        sd_by_reg[reg]['sd_amount'] += row.get('total_amount', 0)
        org = row.get('state_org_name')
        if org: sd_by_reg[reg]['state_orgs'].add(org)

    for reg, info in sd_by_reg.items():
        if reg in all_tender_regs:
            all_tender_regs[reg]['sd_amount'] = info['sd_amount']
            all_tender_regs[reg]['state_orgs'] = info['state_orgs']
        else:
            all_tender_regs[reg] = {'name': '', 'total_tenders': 0, 'total_amount': 0,
                                     'sd_amount': info['sd_amount'], 'state_orgs': info['state_orgs']}
    for reg in all_tender_regs:
        all_tender_regs[reg].setdefault('sd_amount', 0)
        all_tender_regs[reg].setdefault('state_orgs', set())
    print(f"   => Нийт компани: {len(all_tender_regs):,}")

    # ===== 2. УБЕГ =====
    print("\n2. Loading УБЕГ (SH + Dir + BO + Gender)...")
    with open('LesOutputJson.json', 'r', encoding='utf-8') as f:
        ubeg_data = json.load(f)['Data']

    person_to_company = defaultdict(list)
    person_gender_ubeg = {}  # (last, first) -> gender from UBEG
    co_shareholder_map = defaultdict(set)

    for row in ubeg_data:
        reg = str(row[0]).strip()
        if reg not in all_tender_regs: continue
        c_name = row[1]
        persons_in_company = set()

        # Index 5: SH [Ангилал, Улсын нэр, Овог, Нэр, Хүйс, Огноо]
        if len(row) > 5 and row[5]:
            for sh in row[5]:
                if isinstance(sh, list) and len(sh) >= 4 and sh[0] == "Иргэн":
                    last = clean_name(sh[2]); first = clean_name(sh[3])
                    if last and first and len(last) > 1 and len(first) > 1:
                        key = (last, first)
                        person_to_company[key].append({'reg': reg, 'name': c_name, 'role': 'Хувьцаа эзэмшигч'})
                        persons_in_company.add(key)
                        if len(sh) >= 5 and sh[4] in ('Эр', 'Эм'):
                            person_gender_ubeg[key] = sh[4]

        # Index 6: Dir [Албан тушаал, Улсын нэр, Овог, Нэр, Хүйс, Огноо]
        if len(row) > 6 and row[6]:
            for d in row[6]:
                if isinstance(d, list) and len(d) >= 4:
                    last = clean_name(d[2]); first = clean_name(d[3])
                    if last and first and len(last) > 1 and len(first) > 1:
                        key = (last, first)
                        person_to_company[key].append({'reg': reg, 'name': c_name, 'role': 'Гүйцэтгэх захирал'})
                        persons_in_company.add(key)
                        if len(d) >= 5 and d[4] in ('Эр', 'Эм'):
                            person_gender_ubeg[key] = d[4]

        # Index 7: BO [Ангилал, Овог, Нэр, Улсын нэр, Хүйс]
        if len(row) > 7 and row[7]:
            for bo in row[7]:
                if isinstance(bo, list) and len(bo) >= 3 and bo[0] == "Иргэн":
                    last = clean_name(bo[1]); first = clean_name(bo[2])
                    if last and first and len(last) > 1 and len(first) > 1:
                        key = (last, first)
                        person_to_company[key].append({'reg': reg, 'name': c_name, 'role': 'Эцсийн өмчлөгч'})
                        persons_in_company.add(key)
                        if len(bo) >= 5 and bo[4] in ('Эр', 'Эм'):
                            person_gender_ubeg[key] = bo[4]

        for pk in persons_in_company:
            co_shareholder_map[reg].add(pk)

    # Dedup
    for key in person_to_company:
        by_reg = {}
        for c in person_to_company[key]:
            r = c['reg']
            if r not in by_reg: by_reg[r] = c
            else:
                if c['role'] not in by_reg[r]['role']:
                    by_reg[r]['role'] = f"{by_reg[r]['role']} + {c['role']}"
        person_to_company[key] = list(by_reg.values())

    print(f"   => Тендерийн компанитай холбоотой хүн: {len(person_to_company):,}")
    print(f"   => Хүйсийн мэдээлэлтэй: {len(person_gender_ubeg):,}")

    # ===== 3. XACXOM (бүх жилийн дата) =====
    print("\n3. Loading XACXOM (бүх жилийн дата)...")
    import os
    xacxom_file = 'xacxom_declarations_all_years.json' if os.path.exists('xacxom_declarations_all_years.json') else 'xacxom_declarations.json'
    with open(xacxom_file, 'r', encoding='utf-8') as f:
        xacxom_data = json.load(f)
    print(f"   => {len(xacxom_data):,} мэдүүлэг ({xacxom_file})")

    # Нэрийн давтамж (homonym detector) — UNIQUE хүн тоолох, жил бүрийн давтагдлыг тооллогүй
    xacxom_unique_people = set()
    xacxom_name_freq = Counter()
    for d in xacxom_data:
        fn = clean_name(d.get('search_first_name'))
        ln = clean_name(d.get('search_last_name'))
        if fn and ln:
            xacxom_unique_people.add((ln, fn))
    for key in xacxom_unique_people:
        xacxom_name_freq[key] = 1
    # Давхардсан нэрийг тоолох (жил бүрийг тоолохгүй, зөвхөн хүн тоолох)
    name_to_uids = defaultdict(set)
    for d in xacxom_data:
        fn = clean_name(d.get('search_first_name'))
        ln = clean_name(d.get('search_last_name'))
        uid = d.get('aid_user_num', '')
        if fn and ln and uid:
            name_to_uids[(ln, fn)].add(uid)
    for key, uids in name_to_uids.items():
        xacxom_name_freq[key] = len(uids)
    print(f"   => {len(xacxom_unique_people):,} өвөрмөц хүн")

    # ХОМ-т мэдүүлсэн компаниуд (бүх жилээр нэгтгэх)
    xacxom_declared = {}
    for dec in xacxom_data:
        stocks = dec.get('stock_owner_name')
        if not stocks or str(stocks).strip() in ['-', '', 'None']: continue
        fn = clean_name(dec.get('search_first_name'))
        ln = clean_name(dec.get('search_last_name'))
        if not fn or not ln: continue
        key = (ln, fn)
        if key not in xacxom_declared: xacxom_declared[key] = set()
        for s in str(stocks).split(','):
            nc = norm_company(s.strip())
            if nc and len(nc) > 2: xacxom_declared[key].add(nc)

    # ХОМ мэдүүлгийн жилүүд (хүн бүрээр)
    xacxom_person_years = defaultdict(set)
    xacxom_person_active_2025 = {}
    for d in xacxom_data:
        fn = clean_name(d.get('search_first_name'))
        ln = clean_name(d.get('search_last_name'))
        yr = d.get('year')
        if fn and ln and yr:
            key = (ln, fn)
            xacxom_person_years[key].add(yr)
            if yr == 2025:
                xacxom_person_active_2025[key] = True

    # ===== 4. MATCHING + SCORING =====
    print("\n4. Matching + Scoring...")
    results = []
    seen_pairs = {}  # (person_key, reg) -> best score to dedup across years

    for dec in xacxom_data:
        first = clean_name(dec.get('search_first_name'))
        last = clean_name(dec.get('search_last_name'))
        if not first or not last: continue

        key = (last, first)
        if key not in person_to_company: continue

        official_org = dec.get('search_organization', '')
        official_pos = dec.get('search_position', '')
        dec_year = dec.get('year')
        declared_companies = xacxom_declared.get(key, set())
        person_years = xacxom_person_years.get(key, set())

        for c_info in person_to_company[key]:
            reg = c_info['reg']
            t_info = all_tender_regs[reg]
            company_name = c_info['name']

            # === SCORING ===
            score = 0
            score_reasons = []

            # 1. Нэрийн давхцал (homonym)
            name_freq = xacxom_name_freq.get(key, 0)
            if name_freq == 1:
                score += 30
                score_reasons.append("+30 Нэр ганцаарчилсан")
            elif name_freq == 2:
                score += 15
                score_reasons.append("+15 Нэр 2 удаа давхцсан")
            elif name_freq >= 3:
                score -= 20
                score_reasons.append("-20 Нэр 3+ удаа давхцсан (homonym)")

            # 2. Хүйсийн нийцэл
            ubeg_gender = person_gender_ubeg.get(key)
            guessed_gender = guess_gender(first)
            if ubeg_gender and guessed_gender:
                if ubeg_gender == guessed_gender:
                    score += 20
                    score_reasons.append(f"+20 Хүйс таарсан ({ubeg_gender})")
                else:
                    score -= 30
                    score_reasons.append(f"-30 Хүйс ТААРУУЛААГҮЙ ({ubeg_gender} vs {guessed_gender})")

            # 3. Газар зүйн нийцэл
            official_aimags = extract_aimag(official_org)
            company_aimags = set()
            for org in t_info.get('state_orgs', set()):
                company_aimags.update(extract_aimag(org))
            if official_aimags and company_aimags:
                if official_aimags & company_aimags:
                    score += 15
                    common_a = official_aimags & company_aimags
                    score_reasons.append(f"+15 Аймаг таарсан ({', '.join(common_a)})")

            # 4. Албан тушаал
            if is_high_ranking(official_pos):
                score += 15
                score_reasons.append("+15 Өндөр албан тушаалтан")

            # 5. Мэдүүлээгүй
            nc = norm_company(company_name)
            already_declared = nc in declared_companies if nc else False
            if not already_declared:
                score += 10
                score_reasons.append("+10 ХОМ-д мэдүүлээгүй")

            # 6. Дүн их
            sd_amt = t_info.get('sd_amount', 0)
            if sd_amt >= 100_000_000:
                score += 10
                score_reasons.append(f"+10 Дүн их (100M+)")
            elif sd_amt >= 1_000_000_000:
                score += 15
                score_reasons.append(f"+15 Дүн маш их (1B+)")

            # 7. Эцсийн өмчлөгч
            if 'Эцсийн өмчлөгч' in c_info['role']:
                score += 5
                score_reasons.append("+5 Эцсийн өмчлөгч")

            # 8. ХУГАЦААНЫ НИЙЦЭЛ (ШИНЭ!)
            tender_years = t_info.get('tender_years', set())
            if person_years and tender_years:
                overlap = person_years & tender_years
                if overlap:
                    score += 15
                    score_reasons.append(f"+15 Дарга байхдаа тендер авсан ({', '.join(str(y) for y in sorted(overlap))})")
                else:
                    score -= 15
                    score_reasons.append(f"-15 Хугацаа давхцахгүй (ХОМ:{sorted(person_years)}, Тендер:{sorted(tender_years)})")
            
            # 9. 2025 онд идэвхтэй
            is_active_2025 = xacxom_person_active_2025.get(key, False)

            # Self-dealing
            is_sd = False
            matched_orgs = []
            for org in t_info.get('state_orgs', set()):
                if is_self_dealing_v2(official_org, org):
                    is_sd = True
                    matched_orgs.append(org)
            if is_sd:
                score += 25
                score_reasons.append("+25 Self-Dealing сэжиг!")

            # Нэгдмэл сонирхол
            co_shareholders = co_shareholder_map.get(reg, set())
            co_sh_officials = []
            for co_key in co_shareholders:
                if co_key == key: continue
                if co_key in xacxom_declared:
                    co_sh_officials.append(f"{co_key[0].capitalize()} {co_key[1].capitalize()}")

            # Итгэлийн зэрэг
            if score >= 60: confidence = '🔴 МАSH ӨНДӨР'
            elif score >= 40: confidence = '🟠 ӨНДӨР'
            elif score >= 20: confidence = '🟡 ДУНД'
            else: confidence = '⚪ БАГА'

            # Dedup: нэг хүн + нэг компани = нэг мөр (хамгийн өндөр оноо)
            dedup_key = (key, reg)
            if dedup_key in seen_pairs:
                if score <= seen_pairs[dedup_key]:
                    continue  # skip lower score
            seen_pairs[dedup_key] = score

            # Хугацааны тодорхойлолт
            tender_yrs = t_info.get('tender_years', set())
            overlap_yrs = person_years & tender_yrs if person_years and tender_yrs else set()
            if person_years and tender_yrs:
                if all(ty in person_years for ty in tender_yrs):
                    timeline = '✅ Бүх тендер дарга байхдаа'
                elif overlap_yrs:
                    timeline = f'⚠️ Хэсэгчлэн ({len(overlap_yrs)} он давхцсан)'
                else:
                    last_yr = max(person_years) if person_years else 0
                    timeline = f'❌ Давхцахгүй (ХОМ→{last_yr})'
            else:
                timeline = ''

            results.append({
                'ОНОО': score,
                'Итгэлийн зэрэг': confidence,
                'Албан тушаалтны овог': dec.get('search_last_name'),
                'Албан тушаалтны нэр': dec.get('search_first_name'),
                'Ажилладаг байгууллага': official_org,
                'Албан тушаал': official_pos,
                'УБЕГ Компанийн регистр': reg,
                'УБЕГ Компанийн нэр': company_name,
                'УБЕГ Дахь үүрэг': c_info['role'],
                'Тендерийн тоо': t_info.get('total_tenders', 0),
                'Тендерийн нийт дүн': t_info.get('total_amount', 0),
                'Шилэн дансаар авсан дүн': sd_amt,
                'Тендер олгосон байгууллагууд': " | ".join(t_info.get('state_orgs', set())),
                'ХОМ-д мэдүүлсэн эсэх': 'МЭДҮҮЛСЭН' if already_declared else 'МЭДҮҮЛЭЭГҮЙ',
                'Self-Dealing': 'ТИЙМ' if is_sd else '',
                'Давхацсан байгууллагууд': " | ".join(matched_orgs) if is_sd else "",
                'Нэгдмэл сонирхолтой ХОМ мэдүүлэгчид': " | ".join(co_sh_officials) if co_sh_officials else "",
                'Нэрийн давхцал (XACXOM)': name_freq,
                'ХОМ мэдүүлсэн жилүүд': ', '.join(str(y) for y in sorted(person_years)) if person_years else '',
                'Тендер авсан жилүүд': ', '.join(str(y) for y in sorted(tender_yrs)) if tender_yrs else '',
                'Хугацааны нийцэл': timeline,
                '2025 идэвхтэй': 'ТИЙМ' if is_active_2025 else 'ҮГҮЙ',
                'Оноо задаргаа': " | ".join(score_reasons),
            })

    df = pd.DataFrame(results)
    df.sort_values('ОНОО', ascending=False, inplace=True)

    # ===== СТАТИСТИК =====
    print(f"\n{'='*70}")
    print(f"  СТАТИСТИК")
    print(f"{'='*70}")
    print(f"  Нийт тохиолдол: {len(df):,}")
    print(f"  🔴 МАШ ӨНДӨР (60+): {len(df[df['ОНОО'] >= 60]):,}")
    print(f"  🟠 ӨНДӨР (40-59):   {len(df[(df['ОНОО'] >= 40) & (df['ОНОО'] < 60)]):,}")
    print(f"  🟡 ДУНД (20-39):    {len(df[(df['ОНОО'] >= 20) & (df['ОНОО'] < 40)]):,}")
    print(f"  ⚪ БАГА (<20):      {len(df[df['ОНОО'] < 20]):,}")

    # ===== Export =====
    print(f"\n6. Exporting...")
    df.to_excel('6_Нуугдмал_ашиг_сонирхол_v3_SCORED.xlsx', index=False)
    print(f"   => 6_Нуугдмал_ашиг_сонирхол_v3_SCORED.xlsx ({len(df):,} мөр)")

    high = df[df['ОНОО'] >= 40]
    if len(high) > 0:
        high.to_excel('6c_Өндөр_эрсдэлтэй_тохиолдлууд.xlsx', index=False)
        print(f"   => 6c_Өндөр_эрсдэлтэй_тохиолдлууд.xlsx ({len(high):,} мөр)")

    critical = df[df['ОНОО'] >= 60]
    if len(critical) > 0:
        critical.to_excel('6d_Маш_өндөр_эрсдэлтэй.xlsx', index=False)
        print(f"   => 6d_Маш_өндөр_эрсдэлтэй.xlsx ({len(critical):,} мөр)")

    # ===== 7. File 1 merge: ХОМ stock_owner_name-аар олдсон тохиолдлуудыг нэмэх =====
    import os
    f1_path = '1_Дарга_нарын_тендерийн_нэгтгэл.xlsx'
    if os.path.exists(f1_path):
        print(f"\n7. Merging File 1 (ХОМ stock_owner_name matches)...")
        df1 = pd.read_excel(f1_path)
        
        # v3 дэх (Овог, Нэр, Регистр) хослолуудыг index-лэх
        existing_keys = set()
        for _, r in df.iterrows():
            ln = str(r['Албан тушаалтны овог']).strip().lower()
            fn = str(r['Албан тушаалтны нэр']).strip().lower()
            reg = str(r['УБЕГ Компанийн регистр']).strip()
            existing_keys.add((ln, fn, reg))
        
        added = 0
        for _, r1 in df1.iterrows():
            name = str(r1.get('албан_тушаалтан', ''))
            parts = name.split()
            if len(parts) < 2: continue
            ln = parts[0].strip().lower()
            fn = parts[1].strip().lower()
            reg = str(r1.get('компанийн_регистр', '')).strip()
            
            if (ln, fn, reg) not in existing_keys:
                # File 1-д олдсон ч v3-д байхгүй → нэмэх
                f1_score = int(r1.get('итгэлцлийн_оноо', 0))
                f1_status = str(r1.get('шалгалтын_төлөв', ''))
                is_sd = bool(r1.get('өөрийн_байгууллагаас_авсан_эсэх', False))
                
                new_row = {
                    'ОНОО': f1_score,
                    'Итгэлийн зэрэг': '🔵 FILE1' if f1_score >= 60 else '🔵 FILE1 (бага)',
                    'Албан тушаалтны овог': parts[0],
                    'Албан тушаалтны нэр': parts[1] if len(parts) > 1 else '',
                    'Ажилладаг байгууллага': r1.get('ажилладаг_байгууллага', ''),
                    'Албан тушаал': r1.get('албан_тушаал', ''),
                    'УБЕГ Компанийн регистр': reg,
                    'УБЕГ Компанийн нэр': r1.get('холбогдсон_компани', ''),
                    'УБЕГ Дахь үүрэг': r1.get('компани_дахь_үүрэг', ''),
                    'Тендерийн тоо': r1.get('компанийн_нийт_тендерийн_тоо', 0),
                    'Тендерийн нийт дүн': r1.get('компанийн_нийт_гэрээний_дүн', 0),
                    'Шилэн дансаар авсан дүн': 0,
                    'Тендер олгосон байгууллагууд': '',
                    'ХОМ-д мэдүүлсэн эсэх': 'МЭДҮҮЛСЭН' if r1.get('хасхом_д_мэдүүлсэн_эсэх') else 'МЭДҮҮЛЭЭГҮЙ',
                    'Self-Dealing': 'ТИЙМ' if is_sd else '',
                    'Давхацсан байгууллагууд': str(r1.get('өөрийн_байгууллагын_тендерүүд', '')) if is_sd else '',
                    'Нэгдмэл сонирхолтой ХОМ мэдүүлэгчид': '',
                    'Нэрийн давхцал (XACXOM)': 0,
                    'Оноо задаргаа': f'FILE1: {f1_status}',
                }
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                existing_keys.add((ln, fn, reg))
                added += 1
        
        print(f"   => File 1-ээс нэмсэн: {added} тохиолдол (v3-д байхгүй байсан)")
        
        # Re-sort
        df.sort_values('ОНОО', ascending=False, inplace=True)
        df.to_excel('6_Нуугдмал_ашиг_сонирхол_v3_SCORED.xlsx', index=False)
        print(f"   => Шинэчлэгдсэн: 6_Нуугдмал_ашиг_сонирхол_v3_SCORED.xlsx ({len(df):,} мөр)")

    print(f"\nНийт хугацаа: {time.time() - start_time:.1f} сек")

    # Top 10 print
    print(f"\n{'='*70}")
    print(f"  ТОП 10 ХАМГИЙН СЭЖИГТЭЙ")
    print(f"{'='*70}")
    for _, r in df.head(10).iterrows():
        print(f"\n  [{r['ОНОО']}] {r['Албан тушаалтны овог']} {r['Албан тушаалтны нэр']}")
        print(f"    {r['Албан тушаал']} @ {r['Ажилладаг байгууллага']}")
        print(f"    → {r['УБЕГ Компанийн нэр']} ({r['УБЕГ Дахь үүрэг']})")
        amt = r['Шилэн дансаар авсан дүн']
        if amt > 0:
            print(f"    ₮ {amt:,.0f}")
        sd = r.get('Self-Dealing', '')
        if sd == 'ТИЙМ':
            print(f"    ⚠️ SELF-DEALING: {r['Давхацсан байгууллагууд']}")
        print(f"    Оноо: {r['Оноо задаргаа']}")

if __name__ == "__main__":
    main()
