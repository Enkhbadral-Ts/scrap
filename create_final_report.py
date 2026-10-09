"""
Эцсийн нэгтгэсэн тайлан:
  - Тендерийн бүх мэдээлэл (2021-2025)
  - Компанийн регистрийн дугаар (opendatalab + shilendans)
  - Шилэн дансны гүйлгээний мэдээлэл
"""
import pandas as pd
import json
import os

def main():
    # 1. Load register number mapping
    print("Loading register mappings...")
    with open('tender_companies_final_clean.json', 'r', encoding='utf-8') as f:
        reg_data = json.load(f)
    
    reg_map = {}  # company_name -> register_no
    method_map = {}
    for r in reg_data:
        name = r['tender_company']
        reg = r.get('register_no', '')
        if reg and str(reg) != 'nan' and reg != '':
            reg_map[name] = str(int(float(reg)))
            method_map[name] = r.get('match_method', '')
    
    print(f"  Register mappings: {len(reg_map)}")
    
    # 2. Load Shilendans transaction data
    print("Loading Shilendans transactions...")
    with open('shilendans_matches.json', 'r', encoding='utf-8') as f:
        sh_data = json.load(f)
    
    # Group by cleaned_name_search
    sh_by_name = {}
    for s in sh_data:
        cn = s.get('cleaned_name_search', '')
        if cn not in sh_by_name:
            sh_by_name[cn] = []
        sh_by_name[cn].append(s)
    print(f"  Shilendans groups: {len(sh_by_name)}")
    
    # 3. Load cleaning map
    with open('company_cleaning_map.json', 'r', encoding='utf-8') as f:
        cleaning_map = json.load(f)
    
    # 4. Process each year
    years = [2021, 2022, 2023, 2024, 2025]
    all_rows = []
    
    for year in years:
        raw_csv = f'all_{year}_winners_raw.csv'
        if not os.path.exists(raw_csv):
            continue
        
        print(f"Processing {raw_csv}...")
        df = pd.read_csv(raw_csv, encoding='utf-8-sig', on_bad_lines='skip')
        
        for _, row in df.iterrows():
            company = str(row.get('company', '')).strip()
            cleaned = cleaning_map.get(company, company)
            
            # Get register number
            register = reg_map.get(company, reg_map.get(cleaned, ''))
            match_method = method_map.get(company, method_map.get(cleaned, ''))
            
            # Get Shilendans summary for this company
            sh_entries = sh_by_name.get(cleaned, [])
            sh_total_amount = sum(s.get('total_amount', 0) or 0 for s in sh_entries)
            sh_total_txns = sum(s.get('transaction_count', 0) or 0 for s in sh_entries)
            sh_orgs = ', '.join(set(s.get('state_org_name', '') for s in sh_entries if s.get('state_org_name')))
            
            all_rows.append({
                'Тендерийн дугаар': row.get('tender_code', ''),
                'Тендерийн нэр': row.get('tender_name', ''),
                'Тендер зарласан огноо': row.get('date', ''),
                'Гэрээний дүн': row.get('amount', ''),
                'Захиалагч': row.get('client', ''),
                'Шалгарсан байгууллага': company,
                'Регистрийн дугаар': register,
                'Таарсан арга': match_method,
                'Шилэн данс - Нийт авсан дүн': sh_total_amount if sh_total_amount else '',
                'Шилэн данс - Гүйлгээний тоо': sh_total_txns if sh_total_txns else '',
                'Шилэн данс - Шилжүүлэгч байгууллагууд': sh_orgs[:200] if sh_orgs else ''
            })
    
    # 5. Create DataFrame and save
    print(f"\nCreating final report with {len(all_rows)} rows...")
    final_df = pd.DataFrame(all_rows)
    
    # Stats
    has_reg = final_df['Регистрийн дугаар'].notna() & (final_df['Регистрийн дугаар'] != '')
    has_sh = final_df['Шилэн данс - Нийт авсан дүн'].notna() & (final_df['Шилэн данс - Нийт авсан дүн'] != '')
    
    print(f"  Регистр олдсон мөр: {has_reg.sum()} / {len(final_df)} ({100*has_reg.sum()/len(final_df):.1f}%)")
    print(f"  Шилэн данс мэдээлэлтэй мөр: {has_sh.sum()} / {len(final_df)}")
    
    output_file = 'FINAL_Tender_Report_2021_2025.xlsx'
    
    # Use xlsxwriter for formatting
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        final_df.to_excel(writer, index=False, sheet_name='Тендерийн тайлан')
    
    print(f"\n✅ Saved: {output_file}")
    print(f"   Мөр: {len(final_df)}")
    print(f"   Багана: {len(final_df.columns)}")
    
    # Also save a summary sheet
    print("\nCreating summary...")
    summary_rows = []
    for company in sorted(reg_map.keys()):
        cleaned = cleaning_map.get(company, company)
        sh_entries = sh_by_name.get(cleaned, [])
        sh_total = sum(s.get('total_amount', 0) or 0 for s in sh_entries)
        
        summary_rows.append({
            'Компанийн нэр': company,
            'Регистрийн дугаар': reg_map.get(company, ''),
            'Таарсан арга': method_map.get(company, ''),
            'Шилэн данс - Нийт дүн': sh_total if sh_total else ''
        })
    
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_excel('Company_Registry_Summary.xlsx', index=False)
    print(f"✅ Saved: Company_Registry_Summary.xlsx ({len(summary_df)} companies)")

if __name__ == "__main__":
    main()
