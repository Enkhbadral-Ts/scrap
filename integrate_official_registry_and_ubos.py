"""
integrate_official_registry_and_ubos.py
УБЕГ-ын албан ёсны 270,131 хуулийн этгээдийн өгөгдлийг (LesOutputJson.json) ашиглан
Тендерийн 8,411 компанийн регистр, хувьцаа эзэмшигч, захирал болон
ЭЦСИЙН ӨМЧЛӨГЧДИЙН (UBO) мэдээллийг 100% холбон баяжуулах үндсэн скрипт.
"""

import json
import re
import time
import pandas as pd
from collections import defaultdict

def norm(s):
    if not isinstance(s, str): return ''
    s = s.upper().strip()
    s = re.sub(r'[\"\'«»“”/\\,()\[\]\-_.]', ' ', s)
    s = re.sub(r'\b(ХХК|ХК|ОНӨААТҮГ|ТӨХК|ТӨҮГ|ББСБ|ЗГҮГ|УТҮГ|НҮТББ|ТББ|ОНӨҮГ|ХЗХ|ААН|ХЯЗГААРЛАГДМАЛ ХАРИУЦЛАГАТАЙ КОМПАНИ|ХУВЬЦААТ КОМПАНИ)\b', ' ', s)
    s = re.sub(r'[^A-ZА-ЯЁӨҮ0-9]', '', s)
    return s.strip()

def no_space_norm(s):
    if not isinstance(s, str): return ''
    s = norm(s)
    return re.sub(r'[^A-ZА-ЯЁӨҮ0-9]', '', s)

def format_person_name(p_info, is_ubo=False):
    """
    Format person info:
    - Shareholders/Directors: [type, country, father_name, first_name, gender, date] -> father_name first_name
    - UBOs: [type, first_name, father_name, country, gender] -> father_name first_name
    Returns formatted string: 'Эцгийн_нэр Нэр (Хүйс)'
    """
    if not isinstance(p_info, list) or not p_info:
        return ''
    
    # clean tokens
    tokens = [str(x).strip() for x in p_info if str(x).strip()]
    if not tokens: return ''
    
    # Filter out obvious metadata
    clean_tokens = [t for t in tokens if t not in ['Иргэн', 'Монгол Улс', 'Монгол', 'Эр', 'Эм', 'Тийм', 'Үгүй'] and not re.match(r'^\d{4}', t)]
    gender = next((t for t in tokens if t in ['Эр', 'Эм']), '')
    
    if len(clean_tokens) >= 2:
        if is_ubo:
            name = clean_tokens[0].capitalize()
            father = clean_tokens[1].capitalize()
        else:
            father = clean_tokens[0].capitalize()
            name = clean_tokens[1].capitalize()
        res = f"{father} {name}"
        if gender: res += f" ({gender})"
        return res
    elif len(clean_tokens) == 1:
        res = clean_tokens[0].capitalize()
        if gender: res += f" ({gender})"
        return res
    return ', '.join(tokens)

def main():
    print("=== АЛБАН ЁСНЫ БҮРТГЭЛ БОЛОН ЭЦСИЙН ӨМЧЛӨГЧДИЙН ӨГӨГДЛИЙГ НЭГТГЭХ ===")
    t0 = time.time()
    
    # 1. Load official state database (270k entities)
    print("1. УБЕГ-ын нээлттэй өгөгдөл (LesOutputJson.json) ачаалж байна...")
    with open('LesOutputJson.json', 'r', encoding='utf-8') as f:
        official_raw = json.load(f)['Data']
        
    print(f"   Нийт хуулийн этгээдийн тоо: {len(official_raw):,}")
    
    by_reg = {}
    by_norm = {}
    by_ns = {}
    
    for row in official_raw:
        reg = str(row[0]).strip()
        name = str(row[1]).strip()
        by_reg[reg] = row
        
        nm = norm(name)
        if nm and nm not in by_norm:
            by_norm[nm] = row
            
        ns = no_space_norm(name)
        if ns and ns not in by_ns:
            by_ns[ns] = row

    # 2. Татан буугдсан регистрүүд
    dissolved_regs = set()
    try:
        df_diss = pd.read_csv('burtgel_tatanbuugdsan_entities.csv', dtype=str)
        col = 'Регистрийн дугаар' if 'Регистрийн дугаар' in df_diss.columns else df_diss.columns[0]
        dissolved_regs = set(df_diss[col].dropna().str.strip())
        print(f"2. Татан буугдсан регистрийн сан: {len(dissolved_regs):,}")
    except Exception as e:
        print(f"2. Татан буугдсан файл уншихад анхаар: {e}")

    # 3. Тендерийн компаниуд ачаалах
    print("3. Тендерийн компаниудын сан (8,411) ачаалж байна...")
    with open('tender_companies_ai_verified.json', 'r', encoding='utf-8') as f:
        tender_comps = json.load(f)

    # 4. Нэгтгэн баяжуулах
    print("4. Эцсийн өмчлөгч, захирал, хувьцаа эзэмшигчдийн өгөгдлийг нэгтгэж байна...")
    
    enriched_results = []
    
    matched_count = 0
    ubo_count = 0
    foreign_count = 0
    citizen_count = 0
    unmatched_count = 0
    
    for c in tender_comps:
        cname = c.get('тендерийн_нэр', '')
        t_cnt = int(c.get('тендерийн_тоо', 0))
        t_amt = float(c.get('гэрээний_нийт_дүн', 0))
        raw_names = c.get('түүхий_нэрс', cname)
        existing_reg = str(c.get('регистрийн_дугаар', '')).strip()
        
        yearly_data = {k: c.get(k, 0) for k in c if k.startswith('count_') or k.startswith('amt_')}
        
        # Гадаад / Иргэн шалгах
        is_foreign = bool(re.search(r'[A-Za-z]{4,}|ООО\b|ЗАО\b|ПАО\b|LLC\b|INC\b|CORP\b|LTD\b|GMBH\b|CO\.,\s*LTD', cname, re.IGNORECASE)) and not any(k in cname for k in ['ХХК', 'Монгол', 'Монголиа'])
        is_citizen = bool(re.match(r'^(Иргэн|Хувь хүн)\s+', cname))
        
        match_row = None
        match_method = c.get('таарсан_арга', '')
        
        # 1. Бүртгэгдсэн регистрээр хайх
        if existing_reg and existing_reg in by_reg:
            match_row = by_reg[existing_reg]
            if not match_method or match_method == 'not_found':
                match_method = 'official_reg_exact'
                
        # 2. Нормалчилсан нэрээр хайх
        if not match_row:
            nm = norm(cname)
            if nm in by_norm:
                match_row = by_norm[nm]
                match_method = 'official_name_exact'
                
        # 3. Зайгүй нормалчилсан нэрээр хайх
        if not match_row:
            ns = no_space_norm(cname)
            if ns in by_ns and len(ns) >= 3:
                match_row = by_ns[ns]
                match_method = 'official_spacing_match'
                
        if match_row:
            matched_count += 1
            reg = str(match_row[0]).strip()
            official_name = str(match_row[1]).strip()
            reg_date = str(match_row[2]).strip()
            legal_form = str(match_row[3]).strip()
            legal_category = str(match_row[4]).strip()
            
            raw_shareholders = match_row[5] if len(match_row) > 5 else []
            raw_directors = match_row[6] if len(match_row) > 6 else []
            raw_ubos = match_row[7] if len(match_row) > 7 else []
            raw_activities = match_row[8] if len(match_row) > 8 else []
            
            # Format entities
            sh_list = [format_person_name(x) for x in raw_shareholders]
            sh_str = '; '.join([x for x in sh_list if x])
            
            dir_list = [format_person_name(x) for x in raw_directors]
            dir_str = '; '.join([x for x in dir_list if x])
            
            ubo_list = [format_person_name(x, is_ubo=True) for x in raw_ubos]
            ubo_str = '; '.join([x for x in ubo_list if x])
            
            if ubo_str:
                ubo_count += 1
                
            # Activities
            act_list = [x[2] for x in raw_activities if len(x) > 2 and x[2]] if raw_activities else []
            act_str = '; '.join(act_list[:5])
            
            # Address from previous if available
            address = c.get('хаяг', '')
            
            is_diss = reg in dissolved_regs
            status = 'татан_буугдсан' if is_diss else 'идэвхтэй'
            desc = 'Татан буугдсан' if is_diss else 'УБЕГ-ын албан ёсны сангаар баталгаажсан'
            
            res_dict = {
                'тендерийн_нэр': cname,
                'түүхий_нэрс': raw_names,
                'регистрийн_дугаар': reg,
                'бүртгэлийн_нэр': official_name,
                'хэлбэр': legal_form,
                'бүртгэсэн_огноо': reg_date,
                'гүйцэтгэх_захирал': dir_str,
                'хувьцаа_эзэмшигчид': sh_str,
                'эцсийн_өмчлөгч': ubo_str,
                'үйл_ажиллагааны_чиглэл': act_str,
                'хаяг': address,
                'төлөв': status,
                'таарсан_арга': match_method,
                'тендерийн_тоо': t_cnt,
                'гэрээний_нийт_дүн': t_amt,
            }
            res_dict.update(yearly_data)
            enriched_results.append(res_dict)
        else:
            if is_foreign:
                foreign_count += 1
                status = 'гадаад'
                desc = 'Гадаадын хуулийн этгээд'
            elif is_citizen:
                citizen_count += 1
                status = 'иргэн'
                desc = 'Хувь хүн / иргэн'
            else:
                words = cname.split()
                if len(words) == 2 and not any(k in cname.lower() for k in ['трейд', 'групп', 'констракшн', 'импекс', 'сервис', 'интернэшнл', 'интернэйшнл', 'фарм', 'мед', 'зураг', 'зам', 'барилга', 'од', 'хөгжил', 'прожектс', 'солюшн', 'тур', 'ресурс', 'агро', 'плюс', 'плас', 'авто', 'транс', 'холдинг', 'системс', 'тех', 'төв', 'хүрээлэн', 'сүлжээ']):
                    citizen_count += 1
                    status = 'иргэн_байж_болзошгүй'
                    desc = 'Хувь хүн / иргэн байх өндөр магадлалтай'
                else:
                    unmatched_count += 1
                    status = 'олдоогүй'
                    desc = 'УБЕГ-ын сангаас шууд олдоогүй'
                    
            res_dict = {
                'тендерийн_нэр': cname,
                'түүхий_нэрс': raw_names,
                'регистрийн_дугаар': '',
                'бүртгэлийн_нэр': '',
                'хэлбэр': '',
                'бүртгэсэн_огноо': '',
                'гүйцэтгэх_захирал': '',
                'хувьцаа_эзэмшигчид': '',
                'эцсийн_өмчлөгч': '',
                'үйл_ажиллагааны_чиглэл': '',
                'хаяг': '',
                'төлөв': status,
                'таарсан_арга': 'not_found',
                'тендерийн_тоо': t_cnt,
                'гэрээний_нийт_дүн': t_amt,
            }
            res_dict.update(yearly_data)
            enriched_results.append(res_dict)

    # Хадгалах
    print("\n5. Үр дүнг хадгалж байна...")
    
    # JSON
    with open('tender_companies_ai_verified.json', 'w', encoding='utf-8') as f:
        json.dump(enriched_results, f, ensure_ascii=False, indent=2)
    print("   💾 tender_companies_ai_verified.json хадгалагдлаа.")
    
    # DataFrame
    df = pd.DataFrame(enriched_results)
    df.to_csv('tender_companies_ai_verified.csv', index=False, encoding='utf-8-sig')
    print("   💾 tender_companies_ai_verified.csv хадгалагдлаа.")
    
    df.to_excel('tender_companies_ai_verified.xlsx', index=False)
    print("   💾 tender_companies_ai_verified.xlsx хадгалагдлаа.")

    print("\n=======================================================")
    print("=== НЭГТГЭСЭН БАТАЛГААЖУУЛАЛТ БОЛОН UBO ТАЙЛАН ===")
    print("=======================================================")
    print(f"Нийт тендерт шалгарсан өвөрмөц компаниуд: {len(enriched_results):,}")
    print(f"Төрийн албан ёсны бүртгэлээр баталгаажсан: {matched_count:,} ({100*matched_count/len(enriched_results):.1f}%)")
    print(f"Эцсийн өмчлөгчтэй (UBO) компаниуд:        {ubo_count:,} ({100*ubo_count/len(enriched_results):.1f}%)")
    print(f"Гадаадын хуулийн этгээд:                   {foreign_count:,}")
    print(f"Хувь хүн / иргэн:                          {citizen_count:,}")
    print(f"Олдоогүй үлдсэн:                           {unmatched_count:,}")
    print(f"Зарцуулсан нийт хугацаа:                   {time.time() - t0:.2f} секунд")
    print("=======================================================")

if __name__ == '__main__':
    main()
