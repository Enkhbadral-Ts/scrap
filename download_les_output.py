"""
download_les_output.py
opendata.gov.mn-ээс УБЕГ-ын 'Хуулийн этгээдийн улсын бүртгэлийн нээлттэй өгөгдөл' (LesOutputJson.json ~456 MB)
файлыг бүрэн татаж авах найдвартай скрипт.
"""

import sys
import time
import urllib.request
import os

URL = 'https://opendata.gov.mn/api/v1/media/20260918/92/92f7f4a71f62ad91abd5a391229022c79d4d0727'
TARGET = 'LesOutputJson.json'
TMP_TARGET = 'LesOutputJson.json.tmp'

def main():
    print(f"=== ТАТАЖ ЭХЭЛЖ БАЙНА: {TARGET} ===")
    print(f"URL: {URL}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    existing_bytes = 0
    if os.path.exists(TMP_TARGET):
        existing_bytes = os.path.getsize(TMP_TARGET)
        print(f"Өмнө нь татсан хэмжээ: {existing_bytes / (1024*1024):.1f} MB (үргэлжлүүлэн татна)")
        headers['Range'] = f'bytes={existing_bytes}-'
        
    req = urllib.request.Request(URL, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            content_range = resp.headers.get('Content-Range')
            content_length = resp.headers.get('Content-Length')
            
            if resp.status == 206 and content_range:
                # Partial content
                total_bytes = int(content_range.split('/')[-1])
                mode = 'ab'
            elif resp.status == 200:
                total_bytes = int(content_length) if content_length else 456504443
                mode = 'wb'
                existing_bytes = 0
            else:
                total_bytes = 456504443
                mode = 'wb'
                
            print(f"Нийт хэмжээ: {total_bytes / (1024*1024):.1f} MB")
            
            downloaded = existing_bytes
            start_time = time.time()
            last_print_time = start_time
            last_downloaded = downloaded
            
            chunk_size = 256 * 1024 # 256 KB
            
            with open(TMP_TARGET, mode) as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    now = time.time()
                    if now - last_print_time >= 5.0:
                        speed = (downloaded - last_downloaded) / (now - last_print_time) / (1024*1024)
                        pct = (downloaded / total_bytes) * 100 if total_bytes else 0
                        rem_sec = (total_bytes - downloaded) / (speed * 1024 * 1024) if speed > 0 else 0
                        print(f"  ⬇️  {downloaded / (1024*1024):.1f} MB / {total_bytes / (1024*1024):.1f} MB ({pct:.1f}%) | Хурд: {speed:.2f} MB/s | Үлдсэн: {rem_sec/60:.1f} мин")
                        last_print_time = now
                        last_downloaded = downloaded
                        
        # Дууссан тул нэрийг солих
        if os.path.exists(TARGET):
            os.remove(TARGET)
        os.rename(TMP_TARGET, TARGET)
        
        elapsed = time.time() - start_time
        print(f"\n✅ АМЖИЛТТАЙ ТАТАЖ ДУУСЛАА!")
        print(f"Файлын нэр: {TARGET}")
        print(f"Эцсийн хэмжээ: {os.path.getsize(TARGET) / (1024*1024):.1f} MB ({os.path.getsize(TARGET):,} байт)")
        print(f"Зарцуулсан хугацаа: {elapsed/60:.1f} минут")
        
    except Exception as e:
        print(f"\n❌ Алдаа гарлаа: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
