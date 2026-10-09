# -*- coding: utf-8 -*-
"""
Interactive Company & Tender Search CLI
Usage:
    python3 search_company.py <Компанийн нэр эсвэл Регистрийн дугаар>
    python3 search_company.py "Содмонгол"
    python3 search_company.py 2577739 --export
"""

import sys
import os
import argparse
import pandas as pd

REPORT_FILE = "/Users/enkhbadraltsogbayar/Tender data/FINAL_Tender_Report_2021_2025_With_Details.xlsx"

def search(query, export=False):
    if not os.path.exists(REPORT_FILE):
        print(f"Алдаа: Тайлангийн файл олдсонгүй: {REPORT_FILE}")
        return

    print(f"🔍 '{query}' утгаар хайж байна...")
    
    # 1. Search in Sheet 1 (Company Master)
    df_s1 = pd.read_excel(REPORT_FILE, sheet_name=0, dtype={'Регистрийн дугаар': str})
    
    q_str = str(query).strip()
    match_s1 = df_s1[
        df_s1['Компанийн нэр'].astype(str).str.contains(q_str, case=False, na=False) |
        df_s1['Регистрийн дугаар'].astype(str).str.contains(q_str, case=False, na=False) |
        df_s1['Бүртгэлийн нэр'].astype(str).str.contains(q_str, case=False, na=False) |
        df_s1['Эцсийн өмчлөгч (UBO)'].astype(str).str.contains(q_str, case=False, na=False)
    ]
    
    if len(match_s1) == 0:
        print(f"❌ '{query}' гэсэн нэр, регистр, эцсийн өмчлөгчтэй компани олдсонгүй.")
        return

    print(f"\n✅ Нийт {len(match_s1)} компани олдлоо:\n" + "="*80)
    
    # Load Sheet 2 for details
    df_s2 = pd.read_excel(REPORT_FILE, sheet_name=1, header=1, dtype={'Регистрийн дугаар': str})
    
    for _, comp in match_s1.iterrows():
        comp_name = comp['Компанийн нэр']
        print(f"\n🏢 【 №{comp['№']} 】 {comp_name} (РД: {comp['Регистрийн дугаар']})")
        print(f"   • Албан ёсны нэр: {comp['Бүртгэлийн нэр']} | Хэлбэр: {comp['Компанийн хэлбэр']}")
        print(f"   • Эцсийн өмчлөгч (UBO): {comp['Эцсийн өмчлөгч (UBO)']}")
        print(f"   • Хувьцаа эзэмшигчид: {comp['Хувьцаа эзэмшигчид']}")
        print(f"   • Гүйцэтгэх захирал: {comp['Гүйцэтгэх захирал']}")
        print(f"   • Үйл ажиллагааны чиглэл: {comp['Үйл ажиллагааны чиглэл']}")
        print(f"   • Хаяг: {comp['Албан ёсны хаяг']}")
        print(f"   🏆 ШАЛГАРСАН ТЕНДЕР: {comp['Шалгарсан нийт тендерийн тоо']} ширхэг | ГЭРЭЭНИЙ НИЙТ ДҮН: {comp['Гэрээний нийт дүн (₮)']:,.0f} ₮")
        print("   📅 Жил жилийн задаргаа:")
        for y in [2021, 2022, 2023, 2024, 2025]:
            cnt = comp.get(f'{y} он: Тоо', 0)
            amt = comp.get(f'{y} он: Дүн (₮)', 0.0)
            print(f"      - {y} он: {cnt:3d} тендер | {amt:16,.0f} ₮")
        
        # Details from Sheet 2
        comp_tenders = df_s2[df_s2['Шалгарсан компани'] == comp_name].sort_values(by=['Тендерийн он', 'Зарласан огноо'])
        
        if len(comp_tenders) > 0:
            print(f"\n   📑 Авсан сүүлийн 5 тендер (Нийт {len(comp_tenders)} тендерээс):")
            for _, t in comp_tenders.tail(5).iterrows():
                dur = f"{t['⏱ Зарласнаас хаагдсан (хоног)']} хоног" if pd.notna(t['⏱ Зарласнаас хаагдсан (хоног)']) else "тодорхойгүй"
                disc = f"{t['📉 Үнийн бууралт (%)']*100:.1f}%" if pd.notna(t['📉 Үнийн бууралт (%)']) else "-"
                print(f"      [{t['Тендерийн он']}] {t['Тендерийн дугаар']} | {t['Тендерийн нэр'][:45]}...")
                print(f"         Хугацаа: {dur} (Зарласан: {str(t['Зарласан огноо'])[:10]} -> Хаагдсан: {str(t['Санал хүлээн авах (хаагдсан)'])[:10]})")
                print(f"         Төсөв: {t['Нийт төсөвт өртөг (₮)']:,.0f} ₮ -> Гэрээ: {t['Гэрээний үнэ / дүн (₮)']:,.0f} ₮ (Бууралт: {disc})")
                print(f"         Захиалагч: {t['Захиалагч байгууллага']}")

        if export:
            out_filename = f"Tender_{comp_name.replace(' ', '_')}_{comp['Регистрийн дугаар']}.xlsx"
            out_path = os.path.join(os.path.dirname(REPORT_FILE), out_filename)
            with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
                pd.DataFrame([comp]).to_excel(writer, sheet_name='Компанийн карт', index=False)
                comp_tenders.to_excel(writer, sheet_name='Тендерийн задаргаа', index=False)
            print(f"\n   💾 Тухайн компанийн дэлгэрэнгүйг Excel болгон хадгалав: {out_filename}")

        print("-" * 80)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Компани ба түүний авсан тендерүүдийг хайх")
    parser.add_argument("query", type=str, help="Компанийн нэр, регистрийн дугаар, эсвэл эзэмшигчийн нэр")
    parser.add_argument("--export", action="store_true", help="Олдсон компанийн тендерүүдийг тусад нь Excel файл болгож хадгалах")
    args = parser.parse_args()
    
    search(args.query, export=args.export)
