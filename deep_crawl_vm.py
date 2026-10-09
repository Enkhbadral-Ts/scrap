# -*- coding: utf-8 -*-
"""
Deep crawler to search and extract Vision & Mission from company websites
for Top 300 HHK and 167 HK.
"""
import json
import re
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings()

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'mn,en-US,en;q=0.7'
}

def clean_url(u):
    if not u: return ''
    u = str(u).strip()
    if not u or 'facebook.com' in u.lower() or 'fb.com' in u.lower():
        return ''
    if not u.startswith('http://') and not u.startswith('https://'):
        u = 'https://' + u
    return u

def clean_extracted(text):
    if not text: return ''
    # remove excessive whitespace
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    # remove leading punctuation
    text = re.sub(r'^[\:\-\–\.\s\"\'\(\)]+', '', text)
    return text.strip()

def extract_vm_from_html(html):
    if not html: return '', ''
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'nav', 'footer', 'header']):
        tag.decompose()
        
    text = soup.get_text(separator='\n')
    lines = [re.sub(r'\s+', ' ', l).strip() for l in text.split('\n') if l.strip()]
    full_text = '\n'.join(lines)
    
    vis = ''
    mis = ''
    
    # 1. Vision regex
    v_matches = re.finditer(r'(?:алсын\s*хараа|бидний\s*алсын\s*хараа|vision)[\s\:\-\–\.\n]+([^\n]+(?:\n[^\n]+){0,2})', full_text, re.IGNORECASE)
    for m in v_matches:
        cand = m.group(1).strip()
        # split by next keywords
        cand = re.split(r'(?:эрхэм\s*зорилго|үнэт\s*зүйл|зорилт|бидний\s*үнэт|бидний\s*эрхэм|mission|core\s*values)', cand, flags=re.IGNORECASE)[0]
        cand = clean_extracted(cand)
        if 15 <= len(cand) <= 400 and not any(bad in cand.lower() for bad in ['menu', 'copyright', 'нүүр хуудас', 'бүх эрх', 'илүү дэлгэрэнгүй']):
            vis = cand
            break
            
    # 2. Mission regex
    m_matches = re.finditer(r'(?:эрхэм\s*зорилго|бидний\s*эрхэм\s*зорилго|mission)[\s\:\-\–\.\n]+([^\n]+(?:\n[^\n]+){0,2})', full_text, re.IGNORECASE)
    for m in m_matches:
        cand = m.group(1).strip()
        cand = re.split(r'(?:алсын\s*хараа|үнэт\s*зүйл|зорилт|бидний\s*үнэт|бидний\s*алсын|vision|core\s*values)', cand, flags=re.IGNORECASE)[0]
        cand = clean_extracted(cand)
        if 15 <= len(cand) <= 400 and not any(bad in cand.lower() for bad in ['menu', 'copyright', 'нүүр хуудас', 'бүх эрх', 'илүү дэлгэрэнгүй']):
            mis = cand
            break
            
    return vis, mis

def crawl_target(item):
    name = item['name']
    url = clean_url(item.get('web'))
    res = {'name': name, 'num': item.get('num'), 'reg': item.get('reg'), 'web': url, 'vis': '', 'mis': '', 'source': ''}
    if not url:
        return res
        
    session = requests.Session()
    session.headers.update(headers)
    try:
        r = session.get(url, timeout=10, verify=False)
        if r.status_code == 200:
            v, m = extract_vm_from_html(r.text)
            if v: res['vis'] = v
            if m: res['mis'] = m
            if v or m: res['source'] = url
            
            # Check subpages if not both found
            if not (res['vis'] and res['mis']):
                soup = BeautifulSoup(r.text, 'html.parser')
                domain = urlparse(url).netloc
                candidate_links = []
                for a in soup.find_all('a', href=True):
                    href = a['href'].strip()
                    atext = a.get_text().strip().lower()
                    h_lower = href.lower()
                    if any(k in h_lower or k in atext for k in [
                        'about', 'tuhai', 'тухай', 'taniltsuulga', 'танилцуулга',
                        'vision', 'mission', 'зорилго', 'алсын-хараа', 'company', 'бидний'
                    ]):
                        full_sub = urljoin(url, href)
                        if urlparse(full_sub).netloc == domain and full_sub != url and full_sub not in candidate_links:
                            candidate_links.append(full_sub)
                            
                for sub in candidate_links[:5]:
                    try:
                        sr = session.get(sub, timeout=8, verify=False)
                        if sr.status_code == 200:
                            sv, sm = extract_vm_from_html(sr.text)
                            if not res['vis'] and sv: 
                                res['vis'] = sv
                                res['source'] = sub
                            if not res['mis'] and sm: 
                                res['mis'] = sm
                                res['source'] = sub
                            if res['vis'] and res['mis']:
                                break
                    except Exception:
                        pass
    except Exception as e:
        pass
        
    return res

if __name__ == '__main__':
    with open('/Users/enkhbadraltsogbayar/Tender data/missing_hk.json') as f:
        hk = json.load(f)
    with open('/Users/enkhbadraltsogbayar/Tender data/missing_hhk.json') as f:
        hhk = json.load(f)
        
    all_targets = hk + hhk
    targets_with_web = [x for x in all_targets if clean_url(x.get('web'))]
    print(f"Total targets with web: {len(targets_with_web)}")
    
    results = []
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = {executor.submit(crawl_target, t): t for t in targets_with_web}
        done = 0
        found = 0
        for f in as_completed(futures):
            done += 1
            res = f.result()
            if res['vis'] or res['mis']:
                found += 1
                print(f"[{done}/{len(targets_with_web)}] FOUND: {res['name']}")
                if res['vis']: print(f"   Vis: {res['vis']}")
                if res['mis']: print(f"   Mis: {res['mis']}")
            results.append(res)
            
    print(f"\nFinished crawling. Found statements for {found} companies out of {len(targets_with_web)} websites.")
    with open('/Users/enkhbadraltsogbayar/Tender data/deep_crawled_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
