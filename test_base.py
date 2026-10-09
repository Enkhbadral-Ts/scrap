from curl_cffi import requests
s = requests.Session(impersonate="chrome120")
base_resp = s.get("https://user.tender.gov.mn/mn/result/detail/1746497359235", timeout=10)
print(base_resp.status_code)
print(base_resp.text[:500])
