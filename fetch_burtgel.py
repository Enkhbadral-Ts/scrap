"""
opendata.burtgel.gov.mn - Хуулийн этгээдийн бүртгэлийн мэдээлэл татах
Endpoint: /les/table (DataTables server-side JSON API)
  - Татан буугдсан хуулийн этгээд: 17,577 ширхэг
  - reCAPTCHA шаардлагагүй
  
Мөн /les хуудас дээрх хайлтын form нь reCAPTCHA шаарддаг тул 
нийт 270,099 идэвхтэй хуулийн этгээдийг бөөнөөр татах боломжгүй.
Зөвхөн татан буугдсан 17,577-г энэ скрипт татна.
"""

import json
import time
import urllib.request

def fetch_all_dissolved():
    """Fetch all dissolved legal entities from les/table endpoint"""
    all_data = []
    page_size = 5000
    start = 0
    draw = 1
    
    while True:
        url = f"https://opendata.burtgel.gov.mn/les/table?draw={draw}&start={start}&length={page_size}"
        print(f"Fetching start={start}, length={page_size}...")
        
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        
        total = data['recordsTotal']
        rows = data['data']
        all_data.extend(rows)
        
        print(f"  Got {len(rows)} rows. Total so far: {len(all_data)}/{total}")
        
        if len(all_data) >= total or len(rows) == 0:
            break
            
        start += page_size
        draw += 1
        time.sleep(0.5)
    
    return all_data, total

def main():
    print("=== Татан буугдсан хуулийн этгээдийн жагсаалт татах ===")
    data, total = fetch_all_dissolved()
    
    # Save as JSON
    output = {
        'source': 'opendata.burtgel.gov.mn/les/table',
        'description': 'Татан буугдсан хуулийн этгээдийн жагсаалт',
        'total': total,
        'columns': ['register_no', 'name', 'type', 'dissolved_date'],
        'data': data
    }
    
    with open('burtgel_dissolved_entities.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\nDone! Saved {len(data)} dissolved entities to burtgel_dissolved_entities.json")
    
    # Also save as CSV for easy Excel viewing
    import csv
    with open('burtgel_dissolved_entities.csv', 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Регистрийн дугаар', 'Оноосон нэр', 'Хэлбэр', 'Татан буугдсан огноо'])
        for row in data:
            writer.writerow(row)
    
    print(f"Also saved CSV: burtgel_dissolved_entities.csv")

if __name__ == "__main__":
    main()
