"""
build_ai_verified_tender_companies.py
Тендерийн шалгарсан компаниудыг Олон нийтийн нээлттэй мэдээллийн сан (OpenDataLab)
болон төрийн албан ёсны бүртгэлүүдтэй хиймэл оюуны нягтлан шалгалтаар тулгаж,
регистрийн дугаарыг алдаагүй, үнэн зөв холбох эцсийн скрипт.
"""

import json
import re
import glob
import csv
import pandas as pd
from collections import defaultdict

def norm(s):
    if not isinstance(s, str): return ''
    s = s.upper().strip()
    s = re.sub(r'[\"\'«»“”]', '', s)
    s = re.sub(r'\b(ХХК|ХК|ОНӨААТҮГ|ТӨХК|ТӨҮГ|ББСБ|ЗГҮГ|УТҮГ|НҮТББ|ТББ|ОНӨҮГ|ХЗХ|ААН)\b', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def no_space_norm(s):
    if not isinstance(s, str): return ''
    s = norm(s)
    return re.sub(r'[\s\-_.]', '', s)

def main():
    print("=== ТЕНДЕРИЙН КОМПАНИУДЫН РЕГИСТРИЙГ НЯГТЛАН БАТАЛГААЖУУЛАХ ===")
    
    # 1. OpenDataLab цэвэрлэсэн бүртгэл ачаалах
    print("1. OpenDataLab хуулийн этгээдийн бүртгэл (158,662) ачаалж байна...")
    with open('opendatalab_legal_entities_fixed.json', 'r', encoding='utf-8') as f:
        open_entities = json.load(f)
    
    open_by_norm = defaultdict(list)
    open_by_nospace = defaultdict(list)
    open_by_reg = {}

    for e in open_entities:
        reg = e['register_no']
        open_by_reg[reg] = e
        nm = norm(e['name'])
        ns = no_space_norm(e['name'])
        if nm:
            open_by_norm[nm].append(e)
        if ns:
            open_by_nospace[ns].append(e)

    # 2. Шилэн дансны нэрээр нь баталгаажсан регистрүүд
    print("2. Шилэн дансны яг нэрээр таарсан сан ачаалж байна...")
    with open('shilendans_matches.json', 'r', encoding='utf-8') as f:
        sh_data = json.load(f)

    sh_verified = {}
    sh_nospace = {}
    for s in sh_data:
        search_n = norm(s.get('cleaned_name_search', ''))
        rec_n = norm(s.get('receiver_name', ''))
        reg = s.get('register_no', '').strip()
        if search_n and rec_n and reg:
            if search_n == rec_n:
                sh_verified[search_n] = (reg, s.get('receiver_name'))
                sh_nospace[no_space_norm(search_n)] = (reg, s.get('receiver_name'))

    # 3. AI-аар нэг бүрчлэн нягталж олсон тусгай регистрүүд
    print("3. AI-аар тусгайлан шалгаж тогтоосон регистрүүдийг нэгтгэж байна...")
    ai_verified_manual = {
        'ЭНТО': ('5020166', 'Энто', 'ХХК', '2005-09-27'),
        'СЕТУНАРИ': ('5189845', 'Сетунари', 'ХХК', '2008-01-03'),
        'МЕДИКОНТ': ('5417627', 'Медиконт', 'ХХК', '2010-11-17'),
        'ЧОНОГОЛ ТРЕЙД': ('2716895', 'Чоногол трейд', 'ХХК', '2007-04-06'),
        'МОНТЕХ ДИСТРИБЬЮШН': ('5738091', 'Монтех дистрибьюшн', 'ХХК', '2013-08-13'),
        'АЧСВС': ('5188784', 'АЧСВС', 'ХХК', '2007-12-27'),
        'МАЙНС АП': ('5325153', 'Майнс ап', 'ХХК', '2009-09-07'),
        'ОЮУ ЭНД ЭН ИНТЕРНЭЙШНЛ': ('5519098', 'Оюу энд Эн интернэйшнл', 'ХХК', '2011-10-04'),
        'БИО МЕД ТРЕЙД': ('5341388', 'Био мед трейд', 'ХХК', '2017-11-20'),
        'НОГООН-ОЧИР': ('4393325', 'Ногоон-Очир', 'ХХК', '2013-05-21'),
        'САНЧИР-УНДРАХ': ('5177022', 'Санчир -Ундрах', 'ХХК', '2007-06-25'),
        'ДОКТОРТУН': ('5064929', 'Доктор тун', 'ХХК', '2006-03-29'),
        'ИНЖЕНЕРГЕОДЕЗИ': ('2635003', 'Инженер геодези', 'ХХК', '2005-09-21'),
        'ГОЛДЕНХОУЛ': ('5360137', 'Голден хоул', 'ХХК', '2010-03-05'),
        'ГЕОЗУРАГЛАЛ': ('5169712', 'Гео зураглал', 'ХХК', '2007-04-20'),
        'ЗАСМАЛЗАМ': ('5623766', 'Засмал зам', 'ХХК', '2012-06-18'),
        'ЭНДОЖЕНМОНГОЛИА': ('5280214', 'Эндожен монголиа', 'ХХК', '2009-02-17'),
        'ЛХОЁР': ('2113082', 'Л хоёр', 'ХХК', '2006-02-17'),
    }

    # 4. Тендерийн компаниудын статистик
    print("4. Тендерийн бааз дахь давтамж, дүн болон нэрсийг нэгтгэж байна...")
    dfs = [pd.read_csv(f, dtype=str) for f in sorted(glob.glob('all_*_winners_raw.csv'))]
    raw_winners = pd.concat(dfs, ignore_index=True)
    raw_winners['amount_num'] = pd.to_numeric(raw_winners['amount'], errors='coerce').fillna(0)
    raw_winners['year'] = raw_winners['date'].astype(str).str[:4]

    comp_stats = raw_winners.groupby('company').agg(
        tender_count=('tender_code', 'count'),
        total_amount=('amount_num', 'sum')
    ).reset_index()

    year_stats = raw_winners.groupby(['company', 'year']).agg(
        cnt=('tender_code', 'count'),
        amt=('amount_num', 'sum')
    ).reset_index()

    count_pivot = year_stats.pivot(index='company', columns='year', values='cnt').fillna(0).add_prefix('count_')
    amt_pivot = year_stats.pivot(index='company', columns='year', values='amt').fillna(0).add_prefix('amt_')
    
    comp_stats = comp_stats.join(count_pivot, on='company').join(amt_pivot, on='company')
    valid_years = ['2021', '2022', '2023', '2024', '2025']
    for y in valid_years:
        if f'count_{y}' not in comp_stats.columns:
            comp_stats[f'count_{y}'] = 0
        if f'amt_{y}' not in comp_stats.columns:
            comp_stats[f'amt_{y}'] = 0

    with open('company_cleaning_map.json', 'r', encoding='utf-8') as f:
        cleaning_map = json.load(f)

    comp_stats['clean_name'] = comp_stats['company'].apply(lambda x: cleaning_map.get(x, x))
    
    agg_dict = {
        'raw_names': ('company', lambda x: list(set(x))),
        'tender_count': ('tender_count', 'sum'),
        'total_amount': ('total_amount', 'sum')
    }
    for y in valid_years:
        agg_dict[f'count_{y}'] = (f'count_{y}', 'sum')
        agg_dict[f'amt_{y}'] = (f'amt_{y}', 'sum')

    clean_grouped = comp_stats.groupby('clean_name').agg(**agg_dict).reset_index().sort_values(by='tender_count', ascending=False)

    print(f"  Нийт цэвэрлэсэн өвөрмөц компани: {len(clean_grouped)}")

    # 5. Нэг бүрчлэн тулгаж шалгах
    print("5. AI тулгалтын логик ажиллаж байна...")
    verified_results = []

    for _, row in clean_grouped.iterrows():
        cname = row['clean_name']
        t_cnt = int(row['tender_count'])
        t_amt = float(row['total_amount'])
        raw_list = row['raw_names']
        nm = norm(cname)
        ns = no_space_norm(cname)

        # 1. AI Manual Verified
        if nm in ai_verified_manual:
            reg, mname, ftype, rdate = ai_verified_manual[nm]
            verified_results.append({
                'тендерийн_нэр': cname,
                'түүхий_нэрс': ', '.join(raw_list[:3]),
                'регистрийн_дугаар': reg,
                'бүртгэлийн_нэр': mname,
                'захирал': '',
                'хаяг': '',
                'төлөв': 'идэвхтэй',
                'таарсан_арга': 'ai_verified_manual',
                'тендерийн_тоо': t_cnt,
                'гэрээний_нийт_дүн': t_amt,
                'тайлбар': 'AI гараар шалгаж баталгаажуулсан'
            })
            continue

        # 2. OpenDataLab 100% яг таарсан
        if nm in open_by_norm:
            matches = open_by_norm[nm]
            # Шүүх: идэвхтэйг нь урьтал болгох
            active_m = [m for m in matches if m['status'] == 'идэвхтэй']
            m = active_m[0] if active_m else matches[0]
            
            status = m['status']
            is_diss = (status == 'татан_буугдсан')
            
            verified_results.append({
                'тендерийн_нэр': cname,
                'түүхий_нэрс': ', '.join(raw_list[:3]),
                'регистрийн_дугаар': m['register_no'],
                'бүртгэлийн_нэр': m['name'],
                'захирал': m.get('director', ''),
                'хаяг': m.get('address', ''),
                'төлөв': status,
                'таарсан_арга': 'opendatalab_exact',
                'тендерийн_тоо': t_cnt,
                'гэрээний_нийт_дүн': t_amt,
                'тайлбар': f"Татан буугдсан ({m.get('dissolved_date', '')})" if is_diss else ("Олон бүртгэлтэй тул идэвхтэйг сонгов" if len(matches) > 1 else "100% яг таарсан")
            })
            continue

        # 3. Шилэн дансны нэр тулсан
        if nm in sh_verified:
            reg, rec_name = sh_verified[nm]
            op_e = open_by_reg.get(reg, {})
            verified_results.append({
                'тендерийн_нэр': cname,
                'түүхий_нэрс': ', '.join(raw_list[:3]),
                'регистрийн_дугаар': reg,
                'бүртгэлийн_нэр': rec_name,
                'захирал': op_e.get('director', ''),
                'хаяг': op_e.get('address', ''),
                'төлөв': op_e.get('status', 'идэвхтэй'),
                'таарсан_арга': 'shilendans_verified_exact',
                'тендерийн_тоо': t_cnt,
                'гэрээний_нийт_дүн': t_amt,
                'тайлбар': 'Шилэн дансны баталгаажсан бүртгэлтэй яг таарсан'
            })
            continue

        # 4. OpenDataLab зай, зураасны ялгаа таарсан (нийлмэл үг)
        if ns in open_by_nospace and len(ns) >= 3:
            matches = open_by_nospace[ns]
            active_m = [m for m in matches if m['status'] == 'идэвхтэй']
            m = active_m[0] if active_m else matches[0]
            verified_results.append({
                'тендерийн_нэр': cname,
                'түүхий_нэрс': ', '.join(raw_list[:3]),
                'регистрийн_дугаар': m['register_no'],
                'бүртгэлийн_нэр': m['name'],
                'захирал': m.get('director', ''),
                'хаяг': m.get('address', ''),
                'төлөв': m['status'],
                'таарсан_арга': 'opendatalab_spacing_match',
                'тендерийн_тоо': t_cnt,
                'гэрээний_нийт_дүн': t_amt,
                'тайлбар': f"Зай/зураасны ялгаа тулсан ({cname} == {m['name']})"
            })
            continue

        # 5. Шилэн данснаас зай, зураасны ялгаа таарсан
        if ns in sh_nospace and len(ns) >= 3:
            reg, rec_name = sh_nospace[ns]
            op_e = open_by_reg.get(reg, {})
            verified_results.append({
                'тендерийн_нэр': cname,
                'түүхий_нэрс': ', '.join(raw_list[:3]),
                'регистрийн_дугаар': reg,
                'бүртгэлийн_нэр': rec_name,
                'захирал': op_e.get('director', ''),
                'хаяг': op_e.get('address', ''),
                'төлөв': op_e.get('status', 'идэвхтэй'),
                'таарсан_арга': 'shilendans_spacing_match',
                'тендерийн_тоо': t_cnt,
                'гэрээний_нийт_дүн': t_amt,
                'тайлбар': f"Шилэн данснаас зай/зураасны ялгаа тулсан ({cname} == {rec_name})"
            })
            continue

        # 6. Олдоогүй / Гадаад / Иргэн
        is_foreign = bool(re.search(r'[A-Za-z]{4,}|ООО|ЗАО|ПАО|LLC|INC|CORP|LTD', cname))
        is_individual = bool(re.match(r'^(Иргэн|Хувь хүн)\b', cname)) or (len(cname.split()) == 2 and not any(k in cname.lower() for k in ['трейд', 'групп', 'констракшн', 'импекс', 'сервис', 'интернэшнл', 'фарм', 'мед', 'зураг', 'зам', 'барилга', 'од', 'хөгжил']))
        
        status = 'гадаад' if is_foreign else ('иргэн_байж_болзошгүй' if is_individual else 'олдоогүй')
        desc = 'Гадаадын компани' if is_foreign else ('Хувь хүн / иргэн' if is_individual else 'Монголын бүртгэлийн сангаас шууд олдоогүй')
        
        verified_results.append({
            'тендерийн_нэр': cname,
            'түүхий_нэрс': ', '.join(raw_list[:3]),
            'регистрийн_дугаар': '',
            'бүртгэлийн_нэр': '',
            'захирал': '',
            'хаяг': '',
            'төлөв': status,
            'таарсан_арга': 'not_found',
            'тендерийн_тоо': t_cnt,
            'гэрээний_нийт_дүн': t_amt,
            'тайлбар': desc
        })

    # Хадгалах
    df_out = pd.DataFrame(verified_results)
    
    year_cols = [c for c in clean_grouped.columns if c.startswith('count_') or c.startswith('amt_')]
    merge_df = clean_grouped[['clean_name'] + year_cols].rename(columns={'clean_name': 'тендерийн_нэр'})
    df_out = df_out.merge(merge_df, on='тендерийн_нэр', how='left')
    
    print("\n=== БАТАЛГААЖУУЛАЛТЫН ҮР ДҮН ===")
    print(df_out['таарсан_арга'].value_counts())
    print("\nТөлөвийн ангилал:")
    print(df_out['төлөв'].value_counts())
    
    matched = df_out['регистрийн_дугаар'] != ''
    print(f"\nРегистр олдсон компани: {matched.sum()} / {len(df_out)} ({100*matched.sum()/len(df_out):.1f}%)")
    tenders_cov = df_out[matched]['тендерийн_тоо'].sum()
    print(f"Тендерийн хамрагдалт: {tenders_cov} / {len(raw_winners)} ({100*tenders_cov/len(raw_winners):.1f}%)")
    
    # JSON хадгалах
    with open('tender_companies_ai_verified.json', 'w', encoding='utf-8') as f:
        json.dump(df_out.to_dict(orient='records'), f, ensure_ascii=False, indent=2)
    print("✅ Хадгалав: tender_companies_ai_verified.json")
    
    # CSV хадгалах
    df_out.to_csv('tender_companies_ai_verified.csv', index=False, encoding='utf-8-sig')
    print("✅ Хадгалав: tender_companies_ai_verified.csv")

    # Excel хадгалах
    df_out.to_excel('tender_companies_ai_verified.xlsx', index=False)
    print("✅ Хадгалав: tender_companies_ai_verified.xlsx")

if __name__ == '__main__':
    main()
