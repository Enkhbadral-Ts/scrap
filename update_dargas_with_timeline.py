"""
update_dargas_with_timeline.py
Дарга нарын тендерийн файлыг шинэчлэх:
- ХОМ мэдүүлэг ямар жилүүдэд гаргасан
- Тендер авсан жилүүдэд дарга байсан уу
- Хувьцаа мэдүүлгийн өөрчлөлт (жил бүрээр)
- Хугацааны нийцлийн үнэлгээ
"""

import json
import pandas as pd
from collections import defaultdict

def main():
    print("=" * 70)
    print("  ДАРГА НАРЫН ТЕНДЕРИЙН ФАЙЛ ШИНЭЧЛЭХ (Хугацааны задаргаа)")
    print("=" * 70)
    
    # 1. Load full XACXOM (all years)
    print("\n1. Loading XACXOM бүх жилийн мэдүүлэг...")
    with open('xacxom_declarations_all_years.json', 'r', encoding='utf-8') as f:
        xdata = json.load(f)
    print(f"   => {len(xdata):,} мэдүүлэг")
    
    # Build person -> year -> declaration mapping
    # Key: (last_name_lower, first_name_lower) -> {year: declaration_data}
    person_year_map = defaultdict(dict)
    person_all_years = defaultdict(set)
    person_stocks_by_year = defaultdict(dict)
    
    for d in xdata:
        ln = d.get('search_last_name', '').strip().lower()
        fn = d.get('search_first_name', '').strip().lower()
        yr = d.get('year')
        org = d.get('search_organization', '')
        pos = d.get('search_position', '')
        stocks = d.get('stock_owner_name', '')
        
        if not ln or not fn or not yr:
            continue
        
        key = (ln, fn)
        person_year_map[key][yr] = {
            'org': org, 'pos': pos, 'stocks': stocks,
            'owner_total': d.get('owner_total', 0),
            'rank': d.get('rank', ''),
        }
        person_all_years[key].add(yr)
        person_stocks_by_year[key][yr] = str(stocks).strip() if stocks else ''
    
    print(f"   => {len(person_year_map):,} хүний жилийн мэдээлэл")
    
    # 2. Load tender detail (File 2)
    print("\n2. Loading тендерийн дэлгэрэнгүй (File 2)...")
    df2 = pd.read_excel('2_Дарга_нарын_тендерийн_дэлгэрэнгүй.xlsx')
    print(f"   => {len(df2):,} тендерийн мөр")
    
    # 3. Load File 1 (summary)
    print("\n3. Loading дарга нарын нэгтгэл (File 1)...")
    df1 = pd.read_excel('1_Дарга_нарын_тендерийн_нэгтгэл.xlsx')
    print(f"   => {len(df1):,} тохиолдол")
    
    # 4. Build tender years per (person, company_reg)
    tender_detail_by_person = defaultdict(list)
    for _, r in df2.iterrows():
        name = str(r.get('албан_тушаалтан', ''))
        parts = name.split()
        if len(parts) < 2:
            continue
        reg = str(r.get('компанийн_регистр', ''))
        tender_detail_by_person[(name, reg)].append({
            'year': r.get('тендерийн_он'),
            'date': r.get('тендерийн_огноо', ''),
            'tender_name': r.get('тендерийн_нэр (Ямар тендер шалгарсан)', ''),
            'client': r.get('захиалагч_байгууллага (Хаанаас зарласан)', ''),
            'amount': r.get('гэрээний_дүн_төгрөг', 0),
            'self_dealing': r.get('өөрийн_байгууллагын_тендер_эсэх', ''),
        })
    
    # 5. Enrich File 1 with timeline analysis
    print("\n4. Хугацааны задаргаа хийж байна...")
    
    new_cols = {
        'ХОМ_мэдүүлсэн_жилүүд': [],
        'Тендер_авсан_жилүүд': [],
        'Дарга_байх_үед_авсан_тендерүүд': [],
        'Дарга_биш_үед_авсан_тендерүүд': [],
        'Дарга_байх_үеийн_дүн': [],
        'Дарга_биш_үеийн_дүн': [],
        'Хувьцаа_өөрчлөлт': [],
        'Хугацааны_үнэлгээ': [],
        'Сүүлийн_мэдүүлэг_он': [],
        '2025_онд_ажиллаж_буй_эсэх': [],
    }
    
    for _, r in df1.iterrows():
        name = str(r.get('албан_тушаалтан', ''))
        parts = name.split()
        reg = str(r.get('компанийн_регистр', ''))
        
        if len(parts) < 2:
            for col in new_cols:
                new_cols[col].append('')
            continue
        
        ln = parts[0].lower()
        fn = parts[1].lower()
        key = (ln, fn)
        
        # ХОМ мэдүүлсэн жилүүд
        xacxom_years = sorted(person_all_years.get(key, set()))
        new_cols['ХОМ_мэдүүлсэн_жилүүд'].append(', '.join(str(y) for y in xacxom_years) if xacxom_years else 'Олдсонгүй')
        
        # Тендер авсан жилүүд
        tenders = tender_detail_by_person.get((name, reg), [])
        tender_years = sorted(set(t['year'] for t in tenders if t.get('year')))
        new_cols['Тендер_авсан_жилүүд'].append(', '.join(str(y) for y in tender_years) if tender_years else '')
        
        # Дарга байх үед авсан vs биш үед авсан
        during_tenure = []
        outside_tenure = []
        during_amount = 0
        outside_amount = 0
        
        for t in tenders:
            t_year = t.get('year')
            if not t_year:
                continue
            if t_year in xacxom_years:
                # Тухайн онд ХОМ мэдүүлэг гаргасан = дарга байсан
                during_tenure.append(f"{t_year}: {t['tender_name']} ({t['amount']:,.0f}₮)")
                during_amount += t.get('amount', 0)
            else:
                outside_tenure.append(f"{t_year}: {t['tender_name']} ({t['amount']:,.0f}₮)")
                outside_amount += t.get('amount', 0)
        
        new_cols['Дарга_байх_үед_авсан_тендерүүд'].append(' | '.join(during_tenure) if during_tenure else 'Байхгүй')
        new_cols['Дарга_биш_үед_авсан_тендерүүд'].append(' | '.join(outside_tenure) if outside_tenure else 'Байхгүй')
        new_cols['Дарга_байх_үеийн_дүн'].append(during_amount)
        new_cols['Дарга_биш_үеийн_дүн'].append(outside_amount)
        
        # Хувьцаа өөрчлөлт (жил бүрээр)
        stocks_history = []
        for yr in sorted(person_stocks_by_year.get(key, {}).keys()):
            st = person_stocks_by_year[key][yr]
            if st and st != '-':
                stocks_history.append(f"{yr}: {st[:60]}")
        new_cols['Хувьцаа_өөрчлөлт'].append(' | '.join(stocks_history) if stocks_history else '')
        
        # Сүүлийн мэдүүлгийн он
        last_year = max(xacxom_years) if xacxom_years else None
        new_cols['Сүүлийн_мэдүүлэг_он'].append(last_year if last_year else '')
        
        # 2025 онд ажиллаж буй эсэх
        has_2025 = 2025 in xacxom_years
        new_cols['2025_онд_ажиллаж_буй_эсэх'].append('ТИЙМ' if has_2025 else 'ҮГҮЙ')
        
        # Хугацааны үнэлгээ
        if not xacxom_years or not tender_years:
            assessment = 'МЭДЭЭЛЭЛ ДУТМАГ'
        elif all(ty in xacxom_years for ty in tender_years):
            assessment = '✅ БҮХ ТЕНДЕР ДАРГА БАЙХ ҮЕДЭЭ АВСАН'
        elif any(ty in xacxom_years for ty in tender_years):
            during_count = sum(1 for ty in tender_years if ty in xacxom_years)
            outside_count = len(tender_years) - during_count
            assessment = f'⚠️ ХЭСЭГЧЛЭН ({during_count} он дарга байхдаа, {outside_count} он дарга биш үед)'
        else:
            # Тендерийн он нь ХОМ мэдүүлгийн онтой огт давхцахгүй
            if last_year and min(tender_years) > last_year:
                assessment = f'❌ СОЛИГДСОН БАЙЖ МАГАДГҮЙ (сүүлийн мэдүүлэг {last_year}, тендер {min(tender_years)}+)'
            elif last_year and max(tender_years) < min(xacxom_years):
                assessment = f'ℹ️ ТЕНДЕР НЬ ӨМНӨХ ҮЕД ({max(tender_years)} он, дарга {min(xacxom_years)}+)'
            else:
                assessment = '❓ ХОМ МЭДҮҮЛГИЙН ОН ТААРАХГҮЙ'
        
        new_cols['Хугацааны_үнэлгээ'].append(assessment)
    
    # Add new columns to df1
    for col, vals in new_cols.items():
        df1[col] = vals
    
    # 6. Save updated file
    output_file = '1_Дарга_нарын_тендерийн_нэгтгэл_ШИНЭЧИЛСЭН.xlsx'
    df1.to_excel(output_file, index=False)
    print(f"\n   => {output_file} ({len(df1)} мөр)")
    
    # 7. Statistics
    print(f"\n{'='*70}")
    print(f"  СТАТИСТИК")
    print(f"{'='*70}")
    
    assessments = df1['Хугацааны_үнэлгээ'].value_counts()
    for a, cnt in assessments.items():
        print(f"  {a}: {cnt}")
    
    # Show critical self-dealing cases with timeline
    critical = df1[df1['шалгалтын_статус'].str.contains('100% БАТАЛГААЖСАН ЗӨРЧИЛ', na=False)]
    print(f"\n{'='*70}")
    print(f"  13 НОЦТОЙ ТОХИОЛДЛЫН ХУГАЦААНЫ ЗАДАРГАА")
    print(f"{'='*70}")
    for _, r in critical.iterrows():
        name = r['албан_тушаалтан']
        print(f"\n  {name} ({r['албан_тушаал']} @ {r['ажилладаг_байгууллага']})")
        print(f"    ХОМ мэдүүлсэн: {r['ХОМ_мэдүүлсэн_жилүүд']}")
        print(f"    Тендер авсан: {r['Тендер_авсан_жилүүд']}")
        print(f"    2025 ажиллаж буй: {r['2025_онд_ажиллаж_буй_эсэх']}")
        print(f"    Дарга байхдаа авсан дүн: {r['Дарга_байх_үеийн_дүн']:,.0f}₮")
        print(f"    Дарга биш үеийн дүн: {r['Дарга_биш_үеийн_дүн']:,.0f}₮")
        print(f"    => {r['Хугацааны_үнэлгээ']}")

if __name__ == "__main__":
    main()
