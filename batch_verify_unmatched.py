"""
batch_verify_unmatched.py
Тендерийн бүртгэлгүй үлдсэн бүх компаниудыг opendatalab.mn болон Шилэн дансны сангаас
нэг бүрчлэн хайж, хиймэл оюуны нарийвчилсан шүүлтүүрээр баталгаажуулан регистрийн дугаарыг зоох скрипт.
"""

import json
import re
import sys
import time
import argparse
import urllib.parse
import pandas as pd
from collections import defaultdict
from curl_cffi import requests as cf_requests

ORG_FORMS = [
    'ТӨРИЙН ӨМЧИТ АЖ АХУЙН ТООЦООТОЙ ҮЙЛДВЭРИЙН ГАЗАР',
    'ТӨРИЙН БАЙГУУЛЛАГА АЛБАН ГАЗАР УЛСЫН ТӨСӨВТ ҮЙЛДВЭРИЙН ГАЗАР',
    'ГАДААДЫН ХӨРӨНГӨ ОРУУЛАЛТТАЙ ХЯЗГААРЛАГДМАЛ ХАРИУЦЛАГАТАЙ КОМПАНИ',
    'ХЯЗГААРЛАГДМАЛ ХАРИУЦЛАГАТАЙ КОМПАНИ',
    'ХУВЬЦААТ КОМПАНИ',
    'ҮЙЛДВЭРЧНИЙ ЭВЛЭЛИЙН БАЙГУУЛЛАГА',
    'ХОЛБОО НҮТББ',
    'ХОЛБОО',
    'НҮТББ',
    'ТББ',
    'ХОРШОО',
    'НӨХӨРЛӨЛ',
    'ХХК', 'ХК', 'ОНӨААТҮГ', 'ТӨХК', 'ТӨҮГ', 'ББСБ', 'ЗГҮГ', 'УТҮГ', 'ОНӨҮГ', 'ХЗХ', 'ААН'
]

pat_org = r'\b(' + '|'.join(re.escape(x) for x in sorted(ORG_FORMS, key=len, reverse=True)) + r')\b'

PREFIXES = [
    'эрхэм', 'баян', 'алтан', 'хаан', 'эрдэнэ', 'мөнх', 'шинэ', 'цагаан', 'улаан', 'өндөр',
    'гурван', 'дөрвөн', 'түмэн', 'их', 'өргөө', 'од', 'зам', 'төгс', 'бат', 'болд',
    'билэгт', 'энх', 'дэлгэр', 'саруул', 'халиун', 'орхон', 'суварга', 'тунгалаг', 'номин',
    'мөнгөн', 'транс', 'техно', 'мастер', 'интер', 'медикал', 'фарм', 'агро', 'хүнс'
]

def norm(s):
    if not isinstance(s, str): return ''
    s = s.upper().strip()
    s = re.sub(r'[\"\'«»“”/\\,()\[\]\-_.]', ' ', s)
    s = re.sub(pat_org, ' ', s)
    s = re.sub(r'[^A-ZА-ЯЁӨҮ0-9]', '', s)
    return s.strip()

def clean_company_name(s):
    if not isinstance(s, str): return ''
    s = re.sub(r'[\"\'«»“”/\\,()\[\]]', ' ', s).strip()
    s = re.sub(pat_org, ' ', s, flags=re.IGNORECASE).strip()
    return re.sub(r'\s+', ' ', s).strip()

def get_candidate_queries(name):
    clean = clean_company_name(name)
    queries = [name, clean]
    
    # 1. No space version
    if ' ' in clean:
        queries.append(clean.replace(' ', ''))
        
    # 2. Hyphen variations
    if '-' in name:
        queries.append(name.replace('-', ' '))
        queries.append(name.replace('-', ''))
        
    # 3. Common spelling variations
    if 'интернэшнл' in name.lower():
        queries.append(re.sub(r'интернэшнл', 'интернэйшнл', name, flags=re.IGNORECASE))
    elif 'интернэйшнл' in name.lower():
        queries.append(re.sub(r'интернэйшнл', 'интернэшнл', name, flags=re.IGNORECASE))
        
    words = clean.split()
    # 4. Compound word split / merge
    if len(words) == 1:
        low = clean.lower()
        for p in PREFIXES:
            if low.startswith(p) and len(low) > len(p) + 2:
                split_val = clean[:len(p)] + ' ' + clean[len(p):]
                queries.append(split_val)
                queries.append(clean[:len(p)])
                queries.append(clean[len(p):])
                break
    elif len(words) >= 3:
        queries.append(words[0] + words[1] + ' ' + ' '.join(words[2:]))
        queries.append(' '.join(words[:2]) + ' ' + words[2])
        queries.append(words[0] + ' ' + words[1] + words[2])
    elif len(words) == 2:
        queries.append(words[0] + words[1])
        queries.append(words[0])
        queries.append(words[1])
        
    # 5. Distinctive long words
    for w in words:
        if len(w) >= 4 and w.lower() not in ['монгол', 'монголиа', 'трейд', 'групп', 'инженеринг', 'холдинг', 'сервис']:
            queries.append(w)
            
    seen = set()
    uniq = []
    for q in queries:
        q_s = q.strip()
        if q_s and q_s not in seen:
            seen.add(q_s)
            uniq.append(q_s)
    return uniq

def search_opendatalab(queries, expected_cname):
    target_norm = norm(expected_cname)
    
    for q in queries:
        url = f'https://www.opendatalab.mn/search?type=org&query={urllib.parse.quote(q)}'
        try:
            r = cf_requests.get(url, impersonate='chrome120', verify=False, timeout=8)
            if r.status_code != 200:
                continue
            pattern = r'<a href=\"/search/(\d{7})\">\s*<h6>(.*?)</h6>\s*<p class=\"type\">.*?</p>\s*<p class=\"body\">(.*?)</p>'
            matches = re.findall(pattern, r.text, re.DOTALL)
            for reg, raw_title, raw_body in matches:
                title = re.sub(r'<.*?>', '', raw_title).strip()
                body = re.sub(r'<.*?>', '', raw_body).strip()
                
                t_norm = norm(title)
                
                # Strict verification
                if target_norm == t_norm:
                    director = ''
                    address = ''
                    if 'захирал:' in body.lower():
                        parts = re.split(r'захирал:\s*', body, flags=re.IGNORECASE)
                        if len(parts) > 1:
                            subparts = parts[1].split(',', 1)
                            director = subparts[0].strip()
                            if len(subparts) > 1:
                                address = subparts[1].strip()
                    else:
                        address = body
                        
                    return {
                        'register_no': reg,
                        'name': title,
                        'director': director,
                        'address': address,
                        'source': 'opendatalab_search'
                    }
        except Exception:
            pass
        time.sleep(0.04)
    return None

def search_shilendans(queries, expected_cname):
    target_norm = norm(expected_cname)
    
    for q in queries:
        url = f"https://back.shilendans.gov.mn/proxy/gap-integration-service/integrationECopyCredits/getBeltgenNiiluulegch?page=0&size=10&startDate=2021/01/01&endDate=2025/12/31&supplierType=&ezaType=&registerNo=&orgName={urllib.parse.quote(q)}"
        try:
            r = cf_requests.get(url, impersonate='chrome120', verify=False, timeout=8)
            if r.status_code == 200:
                data = r.json()
                items = data.get('content', [])
                for it in items:
                    rec_name = it.get('name', '')
                    reg = it.get('register', '')
                    if not reg or len(reg) != 7 or not reg.isdigit():
                        continue
                    r_norm = norm(rec_name)
                    if target_norm == r_norm:
                        return {
                            'register_no': reg,
                            'name': rec_name,
                            'director': '',
                            'address': '',
                            'source': 'shilendans_search'
                        }
        except Exception:
            pass
        time.sleep(0.04)
    return None

def main():
    parser = argparse.ArgumentParser(description="Batch verify unmatched tender winner companies")
    parser.add_argument('--min-tenders', type=int, default=1, help="Minimum tender count to process (e.g. 5, 2, 1)")
    parser.add_argument('--max-tenders', type=int, default=999999, help="Maximum tender count to process")
    parser.add_argument('--limit', type=int, default=0, help="Limit number of companies to process (0 = all in range)")
    args = parser.parse_args()

    print("=== АЛБАН ЁСНЫ РЕГИСТРГҮЙ КОМПАНИУДЫГ ШАЛГАЖ БАТАЛГААЖУУЛАХ ===")
    
    # 1. Үндсэн өгөгдлүүд ачаалах
    with open('tender_companies_ai_verified.json', 'r', encoding='utf-8') as f:
        verified_data = json.load(f)
        
    dissolved_regs = set()
    try:
        df_diss = pd.read_csv('burtgel_tatanbuugdsan_entities.csv', dtype=str)
        dissolved_regs = set(df_diss['register_no'].dropna().str.strip())
        print(f"  Татан буугдсан регистрийн тоо: {len(dissolved_regs):,}")
    except Exception as e:
        print(f"  Анхаар: Татан буугдсан файл уншихад алдаа гарлаа: {e}")

    # Бэлтгэл: шалгах шаардлагатай компаниудыг ялгах (тендерийн тоогоор ихээс бага руу)
    targets = []
    for idx, item in enumerate(verified_data):
        reg = item.get('регистрийн_дугаар', '').strip()
        t_cnt = item.get('тендерийн_тоо', 0)
        if (not reg) and (args.min_tenders <= t_cnt <= args.max_tenders):
            targets.append((idx, item))

    # Ихээс бага руу эрэмбэлэх
    targets.sort(key=lambda x: x[1].get('тендерийн_тоо', 0), reverse=True)

    print(f"Шалгах компани: {len(targets)} (тендерийн тоо: {args.min_tenders} - {args.max_tenders})")
    if args.limit > 0:
        targets = targets[:args.limit]
        print(f"  Хязгаарласан тоо: {len(targets)}")

    matched_count = 0
    foreign_count = 0
    citizen_count = 0
    not_found_count = 0

    save_counter = 0

    for step_num, (orig_idx, item) in enumerate(targets, 1):
        cname = item['тендерийн_нэр']
        t_cnt = item['тендерийн_тоо']
        
        # Гадаад хуулийн этгээд эсэх
        is_foreign = bool(re.search(r'[A-Za-z]{4,}|ООО\b|ЗАО\b|ПАО\b|LLC\b|INC\b|CORP\b|LTD\b|GMBH\b|CO\.,\s*LTD', cname, re.IGNORECASE))
        if is_foreign and not any(k in cname for k in ['ХХК', 'Монгол', 'Монголиа']):
            verified_data[orig_idx]['төлөв'] = 'гадаад'
            verified_data[orig_idx]['тайлбар'] = 'Гадаадын хуулийн этгээд'
            foreign_count += 1
            print(f"[{step_num}/{len(targets)}] 🌐 [{cname}] ({t_cnt} tenders) -> Гадаад хуулийн этгээд")
            continue

        # Иргэн хувь хүн эсэх
        is_explicit_citizen = bool(re.match(r'^(Иргэн|Хувь хүн)\s+', cname))
        if is_explicit_citizen:
            verified_data[orig_idx]['төлөв'] = 'иргэн'
            verified_data[orig_idx]['тайлбар'] = 'Хувь хүн / иргэн'
            citizen_count += 1
            print(f"[{step_num}/{len(targets)}] 👤 [{cname}] ({t_cnt} tenders) -> Иргэн")
            continue

        # Хайх хувилбарууд үүсгэх
        queries = get_candidate_queries(cname)
        
        # 1. OpenDataLab search
        res = search_opendatalab(queries, cname)
        
        # 2. Shilendans search
        if not res:
            res = search_shilendans(queries, cname)

        if res:
            reg = res['register_no']
            mname = res['name']
            director = res.get('director', '')
            address = res.get('address', '')
            source = res.get('source', '')
            
            is_diss = reg in dissolved_regs
            status = 'татан_буугдсан' if is_diss else 'идэвхтэй'
            desc = 'Татан буугдсан' if is_diss else ('OpenDataLab хайлтаар баталгаажсан' if source == 'opendatalab_search' else 'Шилэн дансны бүртгэлээр баталгаажсан')

            verified_data[orig_idx]['регистрийн_дугаар'] = reg
            verified_data[orig_idx]['бүртгэлийн_нэр'] = mname
            if director: verified_data[orig_idx]['захирал'] = director
            if address: verified_data[orig_idx]['хаяг'] = address
            verified_data[orig_idx]['төлөв'] = status
            verified_data[orig_idx]['таарсан_арга'] = source
            verified_data[orig_idx]['тайлбар'] = desc
            
            matched_count += 1
            save_counter += 1
            print(f"[{step_num}/{len(targets)}] ✅ [{cname}] ({t_cnt} tenders) -> {reg} | {mname} ({status})")
        else:
            # Монгол хүний нэр байх магадлал (2 үгтэй, албан нэршлийн түлхүүр үггүй)
            words = cname.split()
            if len(words) == 2 and not any(k in cname.lower() for k in ['трейд', 'групп', 'констракшн', 'импекс', 'сервис', 'интернэшнл', 'интернэйшнл', 'фарм', 'мед', 'зураг', 'зам', 'барилга', 'од', 'хөгжил', 'прожектс', 'солюшн', 'тур', 'ресурс', 'агро', 'плюс', 'плас', 'авто', 'транс', 'холдинг', 'системс', 'тех', 'төв', 'хүрээлэн', 'сүлжээ']):
                verified_data[orig_idx]['төлөв'] = 'иргэн_байж_болзошгүй'
                verified_data[orig_idx]['тайлбар'] = 'Хувь хүн / иргэн байх өндөр магадлалтай'
                citizen_count += 1
                print(f"[{step_num}/{len(targets)}] 👤? [{cname}] ({t_cnt} tenders) -> Иргэн байж болзошгүй")
            else:
                verified_data[orig_idx]['төлөв'] = 'олдоогүй'
                verified_data[orig_idx]['тайлбар'] = 'Бүртгэлээс шууд олдоогүй'
                not_found_count += 1
                print(f"[{step_num}/{len(targets)}] ❌ [{cname}] ({t_cnt} tenders) -> Олдоогүй")

        # Хадгалах (25 өөрчлөлт тутамд)
        if save_counter >= 25:
            save_checkpoint(verified_data)
            save_counter = 0

    # Эцсийн хадгалалт
    save_checkpoint(verified_data)
    print("\n=== БАТАЛГААЖУУЛАЛТЫН ТАЙЛАН ===")
    print(f"Нийт боловсруулсан: {len(targets)}")
    print(f"Шинээр регистр олдсон: {matched_count}")
    print(f"Гадаад хуулийн этгээд: {foreign_count}")
    print(f"Иргэн / хувь хүн: {citizen_count}")
    print(f"Олдоогүй: {not_found_count}")

def save_checkpoint(data):
    with open('tender_companies_ai_verified.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    df = pd.DataFrame(data)
    df.to_csv('tender_companies_ai_verified.csv', index=False, encoding='utf-8-sig')
    df.to_excel('tender_companies_ai_verified.xlsx', index=False)
    print("   💾 [Файлууд шинэчлэн хадгалагдлаа]")

if __name__ == '__main__':
    main()
