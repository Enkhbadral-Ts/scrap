"""
verify_shilendans_vs_ubeg.py
Шилэн дансны (shilendans_matches.json) датаг
УБЕГ-ын албан ёсны бүртгэлийн сан (LesOutputJson.json) -тай
регистрийн дугаар болон нэрийн нийцлээр тулгаж шалгах скрипт.

Хуучин файлуудыг огт өөрчлөхгүй, шинэ тайлан файл үүсгэнэ.
"""

import json
import re
import pandas as pd
from collections import defaultdict

def norm(s):
    """Нэрийг нормалчилж харьцуулах"""
    if not isinstance(s, str): return ''
    s = s.upper().strip()
    s = re.sub(r'[\"\'«»""/\\,()[\]\-_.]', ' ', s)
    s = re.sub(r'\b(ХХК|ХК|ОНӨААТҮГ|ТӨХК|ТӨҮГ|ББСБ|ЗГҮГ|УТҮГ|НҮТББ|ТББ|ОНӨҮГ|ХЗХ|ААН|ХЯЗГААРЛАГДМАЛ ХАРИУЦЛАГАТАЙ КОМПАНИ|ХУВЬЦААТ КОМПАНИ)\b', ' ', s)
    s = re.sub(r'\s+', '', s)
    return s.strip()

def main():
    print("=" * 60)
    print("ШИЛЭН ДАНС ↔ УБЕГ НИЙЦЛИЙН ТУЛГАЛТ")
    print("=" * 60)

    # 1. УБЕГ-ын сан ачаалах
    print("\n1. УБЕГ-ын сан (LesOutputJson.json) ачаалж байна...")
    with open('LesOutputJson.json', 'r', encoding='utf-8') as f:
        ubeg_raw = json.load(f)['Data']
    print(f"   Нийт хуулийн этгээд: {len(ubeg_raw):,}")

    # Регистрээр index үүсгэх
    ubeg_by_reg = {}
    for row in ubeg_raw:
        reg = str(row[0]).strip()
        name = str(row[1]).strip()
        ubeg_by_reg[reg] = {
            'name': name,
            'form': str(row[3]) if len(row) > 3 else '',
            'date': str(row[2]) if len(row) > 2 else '',
            'full_row': row
        }
    print(f"   Регистрээр индексэд оруулсан: {len(ubeg_by_reg):,}")

    # 2. Шилэн дансны дата ачаалах
    print("\n2. Шилэн дансны дата (shilendans_matches.json) ачаалж байна...")
    with open('shilendans_matches.json', 'r', encoding='utf-8') as f:
        sd_data = json.load(f)
    print(f"   Нийт мөр: {len(sd_data):,}")

    # Регистрээр нэгтгэх (давхардлыг арилгах)
    sd_by_reg = {}
    for d in sd_data:
        reg = str(d['register_no']).strip()
        if reg not in sd_by_reg:
            sd_by_reg[reg] = {
                'sd_name': d.get('receiver_name', ''),
                'sd_search_name': d.get('cleaned_name_search', ''),
                'total_amount': 0,
                'total_tx': 0,
                'state_orgs': []
            }
        sd_by_reg[reg]['total_amount'] += d.get('total_amount', 0)
        sd_by_reg[reg]['total_tx'] += d.get('transaction_count', 0)
        sd_by_reg[reg]['state_orgs'].append(d.get('state_org_name', ''))

    print(f"   Давтагдахгүй компани (регистрээр): {len(sd_by_reg):,}")

    # 3. Тулгалт хийх
    print("\n3. Тулгалт хийж байна...")
    results = []
    
    stat_found = 0
    stat_not_found = 0
    stat_exact_match = 0
    stat_norm_match = 0
    stat_name_mismatch = 0

    for reg, sd_info in sd_by_reg.items():
        row = {
            'регистр': reg,
            'шилэн_дансны_нэр': sd_info['sd_name'],
            'хайлтын_нэр': sd_info['sd_search_name'],
            'нийт_гүйлгээ': sd_info['total_tx'],
            'нийт_дүн': sd_info['total_amount'],
            'төрийн_байгууллагын_тоо': len(set(sd_info['state_orgs'])),
        }

        if reg in ubeg_by_reg:
            stat_found += 1
            ubeg_info = ubeg_by_reg[reg]
            ubeg_name = ubeg_info['name']
            row['УБЕГ_нэр'] = ubeg_name
            row['УБЕГ_хэлбэр'] = ubeg_info['form']
            row['УБЕГ_бүртгэсэн_огноо'] = ubeg_info['date']
            row['регистр_олдсон'] = 'ТИЙМ'

            # Нэрийн нийцлийг шалгах
            sd_norm = norm(sd_info['sd_name'])
            ubeg_norm = norm(ubeg_name)

            if sd_info['sd_name'].strip().upper() == ubeg_name.strip().upper():
                row['нэрийн_нийцэл'] = 'ЯГ ТААРСАН'
                stat_exact_match += 1
            elif sd_norm == ubeg_norm:
                row['нэрийн_нийцэл'] = 'НОРМАЛЧИЛСАН ТААРСАН'
                stat_norm_match += 1
            else:
                row['нэрийн_нийцэл'] = 'ЗӨРҮҮТЭЙ'
                stat_name_mismatch += 1
        else:
            stat_not_found += 1
            row['УБЕГ_нэр'] = ''
            row['УБЕГ_хэлбэр'] = ''
            row['УБЕГ_бүртгэсэн_огноо'] = ''
            row['регистр_олдсон'] = 'ҮГҮЙ'
            row['нэрийн_нийцэл'] = 'ШАЛГАЖ ЧАДААГҮЙ'

        results.append(row)

    # 4. Статистик
    total = len(sd_by_reg)
    print("\n" + "=" * 60)
    print("ТУЛГАЛТЫН ҮР ДҮН")
    print("=" * 60)
    print(f"Шилэн дансны давтагдахгүй компани:     {total:,}")
    print(f"УБЕГ-д регистр олдсон:                  {stat_found:,} ({100*stat_found/total:.1f}%)")
    print(f"  ├─ Нэр яг таарсан:                    {stat_exact_match:,} ({100*stat_exact_match/total:.1f}%)")
    print(f"  ├─ Нормалчилсан таарсан:               {stat_norm_match:,} ({100*stat_norm_match/total:.1f}%)")
    print(f"  └─ Нэр зөрүүтэй:                      {stat_name_mismatch:,} ({100*stat_name_mismatch/total:.1f}%)")
    print(f"УБЕГ-д регистр олдоогүй:                {stat_not_found:,} ({100*stat_not_found/total:.1f}%)")

    # Нэр зөрүүтэй жишээнүүд
    mismatches = [r for r in results if r['нэрийн_нийцэл'] == 'ЗӨРҮҮТЭЙ']
    if mismatches:
        print(f"\n--- Нэр зөрүүтэй жишээнүүд (эхний 15) ---")
        for m in mismatches[:15]:
            print(f"  Регистр: {m['регистр']}")
            print(f"    Шилэн данс: {m['шилэн_дансны_нэр']}")
            print(f"    УБЕГ:        {m['УБЕГ_нэр']}")
            print()

    # УБЕГ-д олдоогүй жишээнүүд
    not_founds = [r for r in results if r['регистр_олдсон'] == 'ҮГҮЙ']
    if not_founds:
        print(f"--- УБЕГ-д олдоогүй жишээнүүд (эхний 10) ---")
        for nf in not_founds[:10]:
            print(f"  Регистр: {nf['регистр']} | Шилэн данс: {nf['шилэн_дансны_нэр']} | Дүн: {nf['нийт_дүн']:,.0f}")

    # 5. Хадгалах
    df = pd.DataFrame(results)
    
    # Дүнгээр буурахаар эрэмбэлэх
    df = df.sort_values('нийт_дүн', ascending=False)

    out_xlsx = '4_Шилэн_данс_УБЕГ_нийцлийн_тайлан.xlsx'
    out_csv = 'shilendans_ubeg_verification.csv'
    out_json = 'shilendans_ubeg_verification.json'

    df.to_excel(out_xlsx, index=False)
    df.to_csv(out_csv, index=False, encoding='utf-8-sig')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Хадгалав: {out_xlsx}")
    print(f"✅ Хадгалав: {out_csv}")
    print(f"✅ Хадгалав: {out_json}")
    print("=" * 60)

if __name__ == '__main__':
    main()
