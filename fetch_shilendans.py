import asyncio
import aiohttp
import json
import urllib.parse
import os

async def fetch_supplier_data(session, cleaned_name, semaphore):
    async with semaphore:
        url = f"https://back.shilendans.gov.mn/proxy/gap-integration-service/integrationECopyCredits/getBeltgenNiiluulegch?page=0&size=10&startDate=2021/01/01&endDate=2025/12/31&supplierType=&ezaType=&registerNo=&orgName={urllib.parse.quote(cleaned_name)}"
        try:
            async with session.get(url, ssl=False, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    suppliers = data.get('content', [])
                    results = []
                    for supplier in suppliers:
                        reg_no = supplier.get('register')
                        receiver_name = supplier.get('name')
                        
                        if not reg_no:
                            continue
                            
                        # Fetch state orgs for this supplier
                        org_url = f"https://back.shilendans.gov.mn/proxy/gap-integration-service/integrationECopyCredits/getSupplierOne?page=0&size=100&startDate=2021/01/01&endDate=2025/12/31&registerNo={urllib.parse.quote(reg_no)}"
                        async with session.get(org_url, ssl=False, timeout=10) as org_response:
                            if org_response.status == 200:
                                org_data = await org_response.json()
                                state_orgs = org_data.get('content', [])
                                
                                for org in state_orgs:
                                    results.append({
                                        'cleaned_name_search': cleaned_name,
                                        'receiver_name': receiver_name,
                                        'register_no': reg_no,
                                        'state_org_name': org.get('name'),
                                        'total_amount': org.get('transactionAmount', 0),
                                        'transaction_count': org.get('transactionCount', 0)
                                    })
                    return results
        except Exception as e:
            # print(f"Error for {cleaned_name}: {e}")
            pass
        return []

async def main():
    with open('company_cleaning_map.json', 'r', encoding='utf-8') as f:
        cleaning_map = json.load(f)
        
    unique_cleaned_names = list(set(cleaning_map.values()))
    print(f"Total unique cleaned names to search: {len(unique_cleaned_names)}")
    
    semaphore = asyncio.Semaphore(50) # 50 concurrent requests
    
    all_results = []
    
    connector = aiohttp.TCPConnector(limit=50, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for name in unique_cleaned_names:
            if name and len(name.strip()) > 1:
                tasks.append(fetch_supplier_data(session, name, semaphore))
                
        print(f"Created {len(tasks)} tasks. Starting to fetch...")
        
        # We use asyncio.as_completed to show progress
        completed = 0
        total = len(tasks)
        for coro in asyncio.as_completed(tasks):
            res = await coro
            if res:
                all_results.extend(res)
            completed += 1
            if completed % 100 == 0:
                print(f"Progress: {completed}/{total} - Found {len(all_results)} matched records so far...")
                # save intermediate
                with open('shilendans_matches.json', 'w', encoding='utf-8') as f:
                    json.dump(all_results, f, ensure_ascii=False, indent=2)
                    
    with open('shilendans_matches.json', 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"Done! Total matches found: {len(all_results)}")

if __name__ == "__main__":
    asyncio.run(main())
