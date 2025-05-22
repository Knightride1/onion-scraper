"""
Enhanced Proxy Rotation Extension for Comprehensive Pastebin Scanning

This module provides robust proxy rotation specifically designed for large-scale
comprehensive scanning operations.
"""

import random
import time
import requests
import logging
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger("proxy_extension")

class ProxyManager:
    """Advanced proxy management for comprehensive scanning"""
    
    def __init__(self, proxy_list: Optional[List[str]] = None):
        """Initialize with proxy list"""
        self.proxies = proxy_list or []
        self.current_index = 0
        self.failed_proxies = set()
        self.proxy_stats = {}  # Track success/failure rates
        self.lock = threading.Lock()
        
        # Initialize stats
        for proxy in self.proxies:
            self.proxy_stats[proxy] = {"success": 0, "failures": 0, "last_used": 0}
    
    def add_proxies(self, proxy_list: List[str]):
        """Add new proxies to the pool"""
        with self.lock:
            for proxy in proxy_list:
                if proxy not in self.proxies:
                    self.proxies.append(proxy)
                    self.proxy_stats[proxy] = {"success": 0, "failures": 0, "last_used": 0}
    
    def get_best_proxy(self) -> Optional[str]:
        """Get the best performing proxy"""
        with self.lock:
            if not self.proxies:
                return None
            
            # Filter out completely failed proxies
            available_proxies = [p for p in self.proxies if p not in self.failed_proxies]
            
            if not available_proxies:
                # Reset failed proxies and try again
                self.failed_proxies = set()
                available_proxies = self.proxies
            
            # Sort by success rate and last used time
            def proxy_score(proxy):
                stats = self.proxy_stats[proxy]
                total_requests = stats["success"] + stats["failures"]
                if total_requests == 0:
                    return 1.0  # New proxy gets high priority
                
                success_rate = stats["success"] / total_requests
                time_penalty = (time.time() - stats["last_used"]) / 3600  # Hours since last use
                return success_rate + (time_penalty * 0.1)  # Slight bonus for rested proxies
            
            available_proxies.sort(key=proxy_score, reverse=True)
            return available_proxies[0]
    
    def get_random_proxy(self) -> Optional[str]:
        """Get a random working proxy"""
        with self.lock:
            available_proxies = [p for p in self.proxies if p not in self.failed_proxies]
            
            if not available_proxies:
                # Reset and try again
                self.failed_proxies = set()
                available_proxies = self.proxies
            
            if available_proxies:
                return random.choice(available_proxies)
            return None
    
    def mark_success(self, proxy: str):
        """Mark a proxy as successful"""
        with self.lock:
            if proxy in self.proxy_stats:
                self.proxy_stats[proxy]["success"] += 1
                self.proxy_stats[proxy]["last_used"] = time.time()
                
                # Remove from failed list if it was there
                self.failed_proxies.discard(proxy)
    
    def mark_failure(self, proxy: str):
        """Mark a proxy as failed"""
        with self.lock:
            if proxy in self.proxy_stats:
                self.proxy_stats[proxy]["failures"] += 1
                
                # If failure rate is too high, mark as failed
                stats = self.proxy_stats[proxy]
                total = stats["success"] + stats["failures"]
                if total > 10 and stats["failures"] / total > 0.7:
                    self.failed_proxies.add(proxy)
    
    def get_proxy_stats(self) -> Dict:
        """Get statistics about proxy performance"""
        with self.lock:
            return {
                "total_proxies": len(self.proxies),
                "failed_proxies": len(self.failed_proxies),
                "working_proxies": len(self.proxies) - len(self.failed_proxies),
                "proxy_details": dict(self.proxy_stats)
            }
    
    def load_from_file(self, filename: str):
        """Load proxies from file"""
        try:
            with open(filename, 'r') as f:
                proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                self.add_proxies(proxies)
                logger.info(f"Loaded {len(proxies)} proxies from {filename}")
        except Exception as e:
            logger.error(f"Error loading proxies from {filename}: {e}")
    
    def test_proxies(self, test_url: str = "https://httpbin.org/ip", timeout: int = 10) -> List[str]:
        """Test all proxies and return working ones"""
        working_proxies = []
        
        def test_proxy(proxy):
            try:
                proxy_dict = {"http": proxy, "https": proxy}
                response = requests.get(test_url, proxies=proxy_dict, timeout=timeout)
                if response.status_code == 200:
                    return proxy
            except:
                pass
            return None
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(test_proxy, proxy) for proxy in self.proxies]
            
            for future in futures:
                result = future.result()
                if result:
                    working_proxies.append(result)
        
        logger.info(f"Tested {len(self.proxies)} proxies, {len(working_proxies)} are working")
        return working_proxies


class ProxyRotatingRequests:
    """Enhanced HTTP client with intelligent proxy rotation"""
    
    def __init__(self, proxy_manager: ProxyManager):
        """Initialize with proxy manager"""
        self.proxy_manager = proxy_manager
        self.session = requests.Session()
        self.max_retries = 5  # Increased for comprehensive scanning
        self.retry_delay = 2
        self.timeout = 15
        
    def request(self, method: str, url: str, **kwargs) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Make HTTP request with advanced proxy rotation"""
        retries = 0
        last_error = None
        
        # Set default timeout
        kwargs.setdefault("timeout", self.timeout)
        
        while retries < self.max_retries:
            # Get best proxy for this request
            proxy = self.proxy_manager.get_best_proxy()
            if not proxy:
                logger.warning("No working proxies available")
                break
            
            try:
                # Configure proxy
                proxy_dict = {"http": proxy, "https": proxy}
                kwargs["proxies"] = proxy_dict
                
                # Make request
                response = self.session.request(method, url, **kwargs)
                
                # Check response status
                if response.status_code == 200:
                    self.proxy_manager.mark_success(proxy)
                    return response, proxy
                elif response.status_code in (403, 429, 503, 502, 504):
                    # Proxy-related errors
                    self.proxy_manager.mark_failure(proxy)
                    logger.debug(f"Proxy {proxy} failed with status {response.status_code}")
                elif response.status_code == 404:
                    # Content not found - not a proxy issue
                    self.proxy_manager.mark_success(proxy)
                    return response, proxy
                else:
                    # Other errors - might be proxy related
                    self.proxy_manager.mark_failure(proxy)
                
            except requests.exceptions.Timeout:
                self.proxy_manager.mark_failure(proxy)
                logger.debug(f"Proxy {proxy} timed out")
            except requests.exceptions.ConnectionError:
                self.proxy_manager.mark_failure(proxy)
                logger.debug(f"Proxy {proxy} connection error")
            except Exception as e:
                self.proxy_manager.mark_failure(proxy)
                logger.debug(f"Proxy {proxy} error: {e}")
                last_error = e
            
            retries += 1
            if retries < self.max_retries:
                # Progressive backoff
                sleep_time = self.retry_delay * (2 ** (retries - 1))
                time.sleep(min(sleep_time, 30))  # Cap at 30 seconds
        
        logger.warning(f"All retries exhausted for {url}")
        return None, None
    
    def get(self, url: str, **kwargs) -> Tuple[Optional[requests.Response], Optional[str]]:
        """GET request with proxy rotation"""
        return self.request("GET", url, **kwargs)
    
    def post(self, url: str, **kwargs) -> Tuple[Optional[requests.Response], Optional[str]]:
        """POST request with proxy rotation"""
        return self.request("POST", url, **kwargs)


class ExtendedPastebinScraper:
    """Extended scraper with proxy support for comprehensive scanning"""
    
    def __init__(self, base_scraper, proxy_list: Optional[List[str]] = None):
        """Initialize with base scraper and proxy support"""
        self.base_scraper = base_scraper
        self.proxy_manager = ProxyManager(proxy_list)
        self.proxy_client = ProxyRotatingRequests(self.proxy_manager)
        
        # Inherit attributes from base scraper
        self.is_running = getattr(base_scraper, 'is_running', False)
        self.scan_progress = getattr(base_scraper, 'scan_progress', {"processed": 0, "found": 0, "errors": 0})
    
    def load_proxies_from_file(self, filename: str):
        """Load and test proxies from file"""
        self.proxy_manager.load_from_file(filename)
        
        # Test proxies in background
        logger.info("Testing loaded proxies...")
        working_proxies = self.proxy_manager.test_proxies()
        logger.info(f"Proxy test complete: {len(working_proxies)} working proxies")
    
    def scrape_single_paste(self, paste_id: str) -> Optional[Dict]:
        """Scrape single paste using proxy rotation"""
        if hasattr(self.base_scraper, 'processed_ids') and paste_id in self.base_scraper.processed_ids:
            return None
        
        try:
            # Get raw content using proxy
            raw_url = f"https://pastebin.com/raw/{paste_id}"
            response, proxy = self.proxy_client.get(raw_url, headers=self.base_scraper.headers)
            
            if not response:
                logger.debug(f"Failed to get paste {paste_id} - no working proxies")
                return None
            
            if response.status_code == 404:
                # Paste doesn't exist
                if hasattr(self.base_scraper, '_save_processed_id'):
                    self.base_scraper._save_processed_id(paste_id)
                return None
            elif response.status_code != 200:
                logger.debug(f"Unexpected status {response.status_code} for paste {paste_id}")
                return None
            
            content = response.text
            onion_links = self.base_scraper.extract_onion_links(content)
            
            if not onion_links:
                if hasattr(self.base_scraper, '_save_processed_id'):
                    self.base_scraper._save_processed_id(paste_id)
                return None
            
            # Get metadata using proxy
            paste_url = f"https://pastebin.com/{paste_id}"
            meta_response, _ = self.proxy_client.get(paste_url, headers=self.base_scraper.headers)
            
            # Create entry (similar to base scraper)
            import datetime
            
            title = f"Paste {paste_id}"
            date_str = datetime.datetime.now().isoformat()
            
            if meta_response and meta_response.status_code == 200:
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(meta_response.text, 'html.parser')
                    
                    title_element = soup.select_one(".info-top .paste-title")
                    if title_element:
                        title = title_element.text.strip()
                    
                    date_element = soup.select_one(".date span")
                    if date_element and date_element.get('title'):
                        date_str = date_element.get('title')
                        
                except Exception as e:
                    logger.debug(f"Error parsing metadata for {paste_id}: {e}")
            
            entry = {
                "crawledTimeStamp": datetime.datetime.now().isoformat(),
                "pasteDateTimestamp": date_str,
                "sourcePasteUrl": paste_url,
                "sourcePasteTitle": title,
                "onionLinks": [{"onionLink": link} for link in onion_links],
                "pasteId": paste_id,
                "proxy_used": proxy
            }
            
            if hasattr(self.base_scraper, '_save_processed_id'):
                self.base_scraper._save_processed_id(paste_id)
            
            logger.info(f"Found {len(onion_links)} onion links in paste {paste_id} via proxy")
            return entry
            
        except Exception as e:
            logger.error(f"Error scraping paste {paste_id} with proxy: {e}")
            return None
    
    def run_comprehensive_scan(self, duration_hours: Optional[int] = None, max_pastes: Optional[int] = None):
        """Run comprehensive scan with proxy support"""
        logger.info("Starting comprehensive scan with proxy rotation")
        
        # Use base scraper's comprehensive scan but with proxy-enabled methods
        self.base_scraper.scrape_single_paste = self.scrape_single_paste
        self.base_scraper.run_comprehensive_scan(duration_hours, max_pastes)
    
    def run_enumeration_scan(self, start_id: int = 1, max_pastes: Optional[int] = None):
        """Run enumeration scan with proxy support"""
        logger.info("Starting enumeration scan with proxy rotation")
        
        self.base_scraper.scrape_single_paste = self.scrape_single_paste
        self.base_scraper.run_enumeration_scan(start_id, max_pastes)
    
    def run_search_scan(self, search_terms: List[str] = None, max_pastes: Optional[int] = None):
        """Run search scan with proxy support"""
        logger.info("Starting search scan with proxy rotation")
        
        self.base_scraper.scrape_single_paste = self.scrape_single_paste
        self.base_scraper.run_search_scan(search_terms, max_pastes)
    
    def run_hybrid_scan(self, duration_hours: Optional[int] = None, max_pastes: Optional[int] = None):
        """Run hybrid scan with proxy support"""
        logger.info("Starting hybrid scan with proxy rotation")
        
        self.base_scraper.scrape_single_paste = self.scrape_single_paste
        self.base_scraper.run_hybrid_scan(duration_hours, max_pastes)
    
    def stop_scan(self):
        """Stop scan gracefully"""
        if hasattr(self.base_scraper, 'stop_scan'):
            self.base_scraper.stop_scan()
    
    def get_proxy_statistics(self) -> Dict:
        """Get proxy performance statistics"""
        return self.proxy_manager.get_proxy_stats()


# Example usage
if __name__ == "__main__":
    from pastebin_comprehensive_scraper import ComprehensivePastebinScraper
    
    # Initialize base scraper
    base_scraper = ComprehensivePastebinScraper()
    
    # Add proxy support
    extended_scraper = ExtendedPastebinScraper(base_scraper)
    
    # Load proxies
    extended_scraper.load_proxies_from_file("proxies.txt")
    
    # Run comprehensive scan
    try:
        extended_scraper.run_comprehensive_scan(duration_hours=1)
    except KeyboardInterrupt:
        extended_scraper.stop_scan()
        
    # Show proxy stats
    proxy_stats = extended_scraper.get_proxy_statistics()
    print(f"Proxy Statistics: {proxy_stats}")