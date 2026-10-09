from curl_cffi import requests
inv_id = "1634288435992"
s = requests.Session(impersonate="chrome120")
base_resp = s.get(f"https://user.tender.gov.mn/mn/result/detail/{inv_id}", timeout=10)
print("Base status:", base_resp.status_code)
print("Base text:", base_resp.text[:200])
