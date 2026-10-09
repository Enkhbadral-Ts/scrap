import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def check_url(url):
    if not url:
        return False, ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        r = requests.head(url, timeout=4, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'}, verify=False)
        if r.status_code < 400:
            return True, r.url
    except Exception:
        pass
    # Try GET if HEAD fails
    try:
        r = requests.get(url, timeout=5, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'}, verify=False)
        if r.status_code < 400:
            return True, r.url
    except Exception as e:
        return False, str(e)
    return False, "status code " + str(r.status_code)

if __name__ == "__main__":
    test_urls = [
        "https://ot.mn",
        "https://mak.mn",
        "https://khanbank.com",
        "https://energyresources.mn",
        "https://golomtbank.com",
        "https://tdbm.mn",
        "https://premiumnexus.mn",
        "https://apu.mn",
        "https://petrovis.mn",
        "https://mobicom.mn",
        "https://gs25.mn",
        "https://xacbank.mn",
        "https://khanaltai.mn",
        "https://maxgroup.mn",
        "https://coca-cola.mcs.mn",
        "https://unitel.mn",
        "https://southgobi.com",
        "http://boldtumur.mn",
        "https://boroogold.mn",
        "https://htcm.mn",
        "https://emartmall.mn",
        "https://shunkhlai.mn",
        "https://altanjoloo.mn",
        "https://gobi.mn",
        "https://barloworld.mn"
    ]
    for u in test_urls:
        ok, res = check_url(u)
        print(f"{u} -> {ok} ({res})")
