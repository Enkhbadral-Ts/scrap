"""
merge_tender_shilendans.py
tender_companies_ai_verified (8,411 компани) болон
4_Шилэн_данс_УБЕГ_нийцлийн_тайлан (3,797 компани) -ыг нэгтгэж
тендерт шалгарсан компани бүр Шилэн дансаар хэдэн төгрөг авсан болохыг
нэг хүснэгтэд гаргах скрипт.
"""

import json
import pandas as pd

def main():
    print("=" * 60)
    print("ТЕНДЕРТ ШАЛГАРСАН КОМПАНИУД + ШИЛЭН ДАНСНЫ НЭГТГЭЛ")
    print("=" * 60)

    # 1. tender_companies_ai_verified ачаалах
    print("\n1. Тендерт шалгарсан компаниуд ачаалж байна...")
    with open('tender_companies_ai_verified.json', 'r', encoding='utf-8') as f:
        tc = json.load(f)
    df_tc = pd.DataFrame(tc)
    print(f"   Нийт: {len(df_tc)} компани")

    # 2. Шилэн данс УБЕГ тулгалт ачаалах
    print("2. Шилэн дансны УБЕГ тулгалт ачаалж байна...")
    df_sd = pd.read_excel('4_Шилэн_данс_УБЕГ_нийцлийн_тайлан.xlsx')
    df_sd['reg_str'] = df_sd['регистр'].astype(str).str.strip()
    print(f"   Нийт: {len(df_sd)} компани")

    # 3. Регистрийн дугаараар холбох
    print("3. Регистрийн дугаараар холбож байна...")
    df_merged = df_tc.merge(
        df_sd[['reg_str', 'нийт_гүйлгээ', 'нийт_дүн', 'төрийн_байгууллагын_тоо', 'регистр_олдсон', 'нэрийн_нийцэл']].rename(columns={
            'нийт_гүйлгээ': 'шилэн_данс_гүйлгээний_тоо',
            'нийт_дүн': 'шилэн_данс_нийт_дүн',
            'төрийн_байгууллагын_тоо': 'шилэн_данс_төрийн_байгууллага',
            'регистр_олдсон': 'УБЕГ_тулгалт',
            'нэрийн_нийцэл': 'УБЕГ_нэрийн_нийцэл'
        }),
        left_on='регистрийн_дугаар',
        right_on='reg_str',
        how='left'
    )
    df_merged.drop(columns=['reg_str'], inplace=True, errors='ignore')

    # NaN-г цэвэрлэх
    df_merged['шилэн_данс_гүйлгээний_тоо'] = df_merged['шилэн_данс_гүйлгээний_тоо'].fillna(0).astype(int)
    df_merged['шилэн_данс_нийт_дүн'] = df_merged['шилэн_данс_нийт_дүн'].fillna(0)
    df_merged['шилэн_данс_төрийн_байгууллага'] = df_merged['шилэн_данс_төрийн_байгууллага'].fillna(0).astype(int)
    df_merged['УБЕГ_тулгалт'] = df_merged['УБЕГ_тулгалт'].fillna('ОЛДООГҮЙ')
    df_merged['УБЕГ_нэрийн_нийцэл'] = df_merged['УБЕГ_нэрийн_нийцэл'].fillna('')

    # Дүнгээр эрэмбэлэх
    df_merged = df_merged.sort_values('шилэн_данс_нийт_дүн', ascending=False)

    # 4. Статистик
    has_sd = df_merged['шилэн_данс_нийт_дүн'] > 0
    tender_total = pd.to_numeric(df_merged['гэрээний_нийт_дүн'], errors='coerce').sum()
    sd_total = df_merged.loc[has_sd, 'шилэн_данс_нийт_дүн'].sum()

    print("\n" + "=" * 60)
    print("НЭГТГЭЛИЙН ҮР ДҮН")
    print("=" * 60)
    print(f"Нийт тендерт шалгарсан компани:        {len(df_merged):,}")
    print(f"Шилэн дансаар мөнгө авсан компани:     {has_sd.sum():,} ({100*has_sd.sum()/len(df_merged):.1f}%)")
    print(f"Шилэн данс олдоогүй компани:           {(~has_sd).sum():,} ({100*(~has_sd).sum()/len(df_merged):.1f}%)")
    print(f"")
    print(f"Тендерийн гэрээний нийт дүн:           {tender_total:,.0f} ₮")
    print(f"Шилэн дансаар бодитоор авсан нийт дүн: {sd_total:,.0f} ₮")
    print(f"")
    
    # Топ 10
    print("--- ТОП 10 Шилэн дансаар хамгийн их авсан ---")
    top10 = df_merged[has_sd].head(10)
    for i, (_, row) in enumerate(top10.iterrows()):
        print(f"  {i+1}. {row['тендерийн_нэр']} (Рег: {row['регистрийн_дугаар']})")
        print(f"     Тендер: {row['тендерийн_тоо']} удаа, Гэрээ: {row['гэрээний_нийт_дүн']:,.0f} ₮")
        print(f"     Шилэн данс: {row['шилэн_данс_гүйлгээний_тоо']} гүйлгээ, {row['шилэн_данс_нийт_дүн']:,.0f} ₮")
        print()

    # 5. Хадгалах
    out_xlsx = '5_Тендер_Шилэн_данс_УБЕГ_бүрэн_нэгтгэл.xlsx'
    out_csv = 'tender_shilendans_full_merge.csv'
    out_json = 'tender_shilendans_full_merge.json'

    df_merged.to_excel(out_xlsx, index=False)
    df_merged.to_csv(out_csv, index=False, encoding='utf-8-sig')
    
    records = df_merged.to_dict(orient='records')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"✅ Хадгалав: {out_xlsx}")
    print(f"✅ Хадгалав: {out_csv}")
    print(f"✅ Хадгалав: {out_json}")
    print("=" * 60)

if __name__ == '__main__':
    main()
