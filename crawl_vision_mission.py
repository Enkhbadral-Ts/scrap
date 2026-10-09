# -*- coding: utf-8 -*-
"""
High-performance crawler for extracting official Vision and Mission
from companies in Top 300.
"""
import openpyxl
import json
import re
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings()

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'mn,en-US,en;q=0.5'
}

def clean_url(u):
    if not u: return ''
    u = str(u).strip()
    if not u or 'facebook.com' in u.lower() or 'fb.com' in u.lower():
        return ''
    if not u.startswith('http://') and not u.startswith('https://'):
        u = 'https://' + u
    return u

def extract_vm_from_text(text):
    if not text: return '', ''
    
    # Split into clean lines
    lines = [re.sub(r'\s+', ' ', l).strip() for l in text.split('\n') if l.strip()]
    full_text = '\n'.join(lines)
    
    vis = ''
    mis = ''
    
    # Vision patterns
    # Matches "Алсын хараа:", "Бидний алсын хараа:", etc.
    v_patterns = [
        r'(?:алсын хараа|бидний алсын хараа|vision)[:\s\-\–\.]+([^\n\r]+(?:\n[^\n\r]+){0,2})',
        r'алсын хараа\s*\n+([^\n\r]+(?:\n[^\n\r]+){0,2})'
    ]
    for vp in v_patterns:
        m = re.search(vp, full_text, re.IGNORECASE)
        if m:
            cand = m.group(1).strip()
            # Clean if followed by other headings
            cand = re.split(r'(?:эрхэм зорилго|үнэт зүйл|үүрэг|зорилт|бидний|mission|values)', cand, flags=re.IGNORECASE)[0].strip()
            cand = re.sub(r'^[\:\-\–\.\s]+', '', cand).strip()
            if 10 <= len(cand) <= 350 and not any(bad in cand.lower() for bad in ['menu', 'copyright', 'нүүр хуудас', 'бүх эрх']):
                vis = cand
                break

    # Mission patterns
    # Matches "Эрхэм зорилго:", "Бидний эрхэм зорилго:", etc.
    m_patterns = [
        r'(?:эрхэм зорилго|бидний эрхэм зорилго|mission)[:\s\-\–\.]+([^\n\r]+(?:\n[^\n\r]+){0,2})',
        r'эрхэм зорилго\s*\n+([^\n\r]+(?:\n[^\n\r]+){0,2})'
    ]
    for mp in m_patterns:
        m = re.search(mp, full_text, re.IGNORECASE)
        if m:
            cand = m.group(1).strip()
            cand = re.split(r'(?:алсын хараа|үнэт зүйл|үүрэг|зорилт|бидний|vision|values)', cand, flags=re.IGNORECASE)[0].strip()
            cand = re.sub(r'^[\:\-\–\.\s]+', '', cand).strip()
            if 10 <= len(cand) <= 350 and not any(bad in cand.lower() for bad in ['menu', 'copyright', 'нүүр хуудас', 'бүх эрх']):
                mis = cand
                break
                
    return vis, mis

def crawl_company_site(name, base_url):
    u = clean_url(base_url)
    if not u:
        return '', ''
        
    try:
        r = requests.get(u, headers=headers, timeout=8, verify=False)
        if r.status_code != 200:
            return '', ''
            
        soup = BeautifulSoup(r.text, 'html.parser')
        # Remove script and style elements
        for s in soup(['script', 'style', 'nav', 'footer']):
            s.decompose()
            
        text = soup.get_text()
        vis, mis = extract_vm_from_text(text)
        if vis and mis:
            return vis, mis
            
        # Look for subpages
        domain = urlparse(u).netloc
        subpages = set()
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            atext = a.get_text().strip().lower()
            h_lower = href.lower()
            if any(k in h_lower or k in atext for k in [
                'about', 'tuhai', 'тухай', 'taniltsuulga', 'танилцуулга',
                'vision', 'mission', 'зорилго', 'алсын-хараа', 'company', 'бидний'
            ]):
                full_sub = urljoin(u, href)
                if urlparse(full_sub).netloc == domain and full_sub != u:
                    subpages.add(full_sub)
                    
        # Check up to 3 candidate subpages
        for sub in list(subpages)[:3]:
            try:
                sr = requests.get(sub, headers=headers, timeout=8, verify=False)
                if sr.status_code == 200:
                    ssoup = BeautifulSoup(sr.text, 'html.parser')
                    for s in ssoup(['script', 'style', 'nav', 'footer']):
                        s.decompose()
                    stext = ssoup.get_text()
                    s_vis, s_mis = extract_vm_from_text(stext)
                    if not vis and s_vis: vis = s_vis
                    if not mis and s_mis: mis = s_mis
                    if vis and mis: break
            except Exception:
                pass
                
        return vis, mis
    except Exception:
        return '', ''

if __name__ == '__main__':
    # Load resolved step 1
    with open('/Users/enkhbadraltsogbayar/Tender data/top300_resolved_step1.json', 'r', encoding='utf-8') as f:
        entities = json.load(f)
        
    print(f"Loaded {len(entities)} resolved entities.")
    to_crawl = [e for e in entities if not (e.get('vis') and e.get('mis')) and clean_url(e.get('web'))]
    print(f"Entities to crawl website for: {len(to_crawl)}")
    
    results = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_map = {
            executor.submit(crawl_company_site, e['original_name'], e['web']): e
            for e in to_crawl
        }
        done_cnt = 0
        found_cnt = 0
        for f in as_completed(future_map):
            e = future_map[f]
            done_cnt += 1
            try:
                v, m = f.result()
                if v or m:
                    found_cnt += 1
                    print(f"[{done_cnt}/{len(to_crawl)}] FOUND for {e['original_name']}:")
                    if v: print(f"   Vis: {v[:80]}...")
                    if m: print(f"   Mis: {m[:80]}...")
                results[e['original_name']] = {'vis': v, 'mis': m}
            except Exception as exc:
                results[e['original_name']] = {'vis': '', 'mis': ''}
                
    print(f"\nCrawling complete. Found vision/mission for {found_cnt} websites.")
    with open('/Users/enkhbadraltsogbayar/Tender data/crawled_vm_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("Saved results to crawled_vm_results.json")
