import pandas as pd
import json

def create_registry_mapping():
    # 1. Load cleaning map (Original Name -> Cleaned Name)
    with open('company_cleaning_map.json', 'r', encoding='utf-8') as f:
        cleaning_map = json.load(f)
        
    # 2. Load Shilendans matches (which contain register_no)
    with open('shilendans_matches.json', 'r', encoding='utf-8') as f:
        matches = json.load(f)
        
    # Create a mapping of Cleaned Name -> Register No
    # A cleaned name might have matched multiple state orgs, but the register_no is the same
    name_to_register = {}
    for match in matches:
        cleaned_name = match.get('cleaned_name_search')
        reg_no = match.get('register_no')
        if cleaned_name and reg_no:
            name_to_register[cleaned_name] = reg_no
            
    # 3. Create the final list
    rows = []
    for original_name, cleaned_name in cleaning_map.items():
        reg_no = name_to_register.get(cleaned_name, '')
        rows.append({
            'Тендерт бичигдсэн нэр (Original)': original_name,
            'Цэвэрлэсэн нэр (Cleaned)': cleaned_name,
            'Регистрийн дугаар (Шилэн данснаас)': reg_no
        })
        
    df = pd.DataFrame(rows)
    
    # Sort by cleaned name for readability
    df = df.sort_values('Цэвэрлэсэн нэр (Cleaned)')
    
    # Save to Excel
    output_file = 'Tender_Winners_with_Registry.xlsx'
    df.to_excel(output_file, index=False)
    
    # Also save unique cleaned companies with their registry numbers
    unique_rows = []
    for cleaned_name, reg_no in name_to_register.items():
        unique_rows.append({
            'Компанийн нэр': cleaned_name,
            'Регистрийн дугаар': reg_no
        })
    df_unique = pd.DataFrame(unique_rows).sort_values('Компанийн нэр')
    df_unique.to_excel('Unique_Cleaned_Companies_Registry.xlsx', index=False)
    
    print(f"Created {output_file} with {len(df)} rows.")
    print(f"Created Unique_Cleaned_Companies_Registry.xlsx with {len(df_unique)} unique companies.")

if __name__ == "__main__":
    create_registry_mapping()
