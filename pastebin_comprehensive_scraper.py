"""
Comprehensive Pastebin .onion Link Scraper

This module implements multiple strategies to scan the ENTIRE Pastebin platform
for .onion links, not just recent pastes.

Strategies:
1. Systematic paste ID enumeration (brute force approach)
2. Search-based discovery using dark web related terms
3. API-based comprehensive scanning (if API key available)
4. Hybrid approach combining multiple methods
"""

import json
import os
import re
import time
import datetime
import logging
import requests
import random
import string
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Set
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("comprehensive_scraper")

class ComprehensivePastebinScraper:
    """Comprehensive scraper for finding ALL .onion links on Pastebin"""
    
    def __init__(self, api_key: Optional[str] = None, db_path: str = "comprehensive_onion_links.json", config: Dict = None):
        """Initialize the comprehensive scraper"""
        self.api_key = api_key
        self.db_path = db_path
        self.config = config or {}
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        # URL patterns
        self.base_url = "https://pastebin.com"
        self.raw_url_template = "https://pastebin.com/raw/{}"
        self.paste_url_template = "https://pastebin.com/{}"
        self.search_url = "https://pastebin.com/search"
        
        # Regex for .onion detection
        self.onion_pattern = re.compile(r'(?:https?://)?(?:[a-zA-Z2-7]{16,56}\.onion)(?:/\S*)?', re.IGNORECASE)
        
        # Database and state
        self.db = self._load_db()
        self.processed_ids = self._load_processed_ids()
        self.is_running = False
        self.scan_progress = {"processed": 0, "found": 0, "errors": 0}
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Rate limiting
        self.last_request_time = 0
        self.request_delay = self.config.get("delay_range", [1, 3])
        
    def _load_db(self) -> Dict:
        """Load existing database or create new one"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error loading database from {self.db_path}. Creating new database.")
                return {"onion_links": [], "metadata": {"scan_sessions": []}}
        else:
            return {"onion_links": [], "metadata": {"scan_sessions": []}}
    
    def _save_db(self):
        """Save database to disk"""
        with self.lock:
            try:
                with open(self.db_path, 'w') as f:
                    json.dump(self.db, f, indent=2)
                logger.debug(f"Database saved to {self.db_path}")
            except Exception as e:
                logger.error(f"Error saving database: {e}")
    
    def _load_processed_ids(self) -> Set[str]:
        """Load set of already processed paste IDs"""
        processed_file = f"{self.db_path}.processed"
        if os.path.exists(processed_file):
            try:
                with open(processed_file, 'r') as f:
                    return set(line.strip() for line in f)
            except Exception as e:
                logger.error(f"Error loading processed IDs: {e}")
        return set()
    
    def _save_processed_id(self, paste_id: str):
        """Save processed paste ID to avoid reprocessing"""
        processed_file = f"{self.db_path}.processed"
        try:
            with open(processed_file, 'a') as f:
                f.write(f"{paste_id}\n")
            self.processed_ids.add(paste_id)
        except Exception as e:
            logger.error(f"Error saving processed ID: {e}")
    
    def _rate_limit(self):
        """Apply rate limiting between requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Random delay between min and max
        delay = random.uniform(self.request_delay[0], self.request_delay[1])
        
        if time_since_last < delay:
            sleep_time = delay - time_since_last
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def extract_onion_links(self, content: str) -> List[str]:
        """Extract .onion links from content"""
        matches = self.onion_pattern.findall(content)
        links = []
        for link in matches:
            if not link.startswith(('http://', 'https://')):
                link = f"http://{link}"
            links.append(link)
        return list(set(links))  # Remove duplicates
    
    def scrape_single_paste(self, paste_id: str) -> Optional[Dict]:
        """Scrape a single paste by ID"""
        if paste_id in self.processed_ids:
            return None
            
        try:
            self._rate_limit()
            
            # Get raw content
            raw_url = self.raw_url_template.format(paste_id)
            response = requests.get(raw_url, headers=self.headers, timeout=10)
            
            if response.status_code == 404:
                # Paste doesn't exist or is private
                self._save_processed_id(paste_id)
                return None
            elif response.status_code == 403:
                # Rate limited or blocked
                logger.warning(f"Rate limited or blocked for paste {paste_id}")
                time.sleep(self.config.get("rate_limit_delay", 60))
                return None
            elif response.status_code != 200:
                logger.warning(f"Unexpected status {response.status_code} for paste {paste_id}")
                return None
            
            content = response.text
            onion_links = self.extract_onion_links(content)
            
            if not onion_links:
                self._save_processed_id(paste_id)
                return None
            
            # Get paste metadata
            paste_url = self.paste_url_template.format(paste_id)
            meta_response = requests.get(paste_url, headers=self.headers, timeout=10)
            
            title = f"Paste {paste_id}"
            date_str = datetime.datetime.now().isoformat()
            
            if meta_response.status_code == 200:
                try:
                    soup = BeautifulSoup(meta_response.text, 'html.parser')
                    
                    # Extract title
                    title_element = soup.select_one(".info-top .paste-title")
                    if title_element:
                        title = title_element.text.strip()
                    
                    # Extract date
                    date_element = soup.select_one(".date span")
                    if date_element and date_element.get('title'):
                        date_str = date_element.get('title')
                        
                except Exception as e:
                    logger.debug(f"Error parsing metadata for {paste_id}: {e}")
            
            # Create entry
            entry = {
                "crawledTimeStamp": datetime.datetime.now().isoformat(),
                "pasteDateTimestamp": date_str,
                "sourcePasteUrl": paste_url,
                "sourcePasteTitle": title,
                "onionLinks": [{"onionLink": link} for link in onion_links],
                "pasteId": paste_id
            }
            
            # Update statistics
            with self.lock:
                self.scan_progress["found"] += len(onion_links)
            
            self._save_processed_id(paste_id)
            logger.info(f"Found {len(onion_links)} onion links in paste {paste_id}")
            
            return entry
            
        except Exception as e:
            logger.error(f"Error scraping paste {paste_id}: {e}")
            with self.lock:
                self.scan_progress["errors"] += 1
            return None
    
    def add_entry(self, entry: Dict):
        """Add entry to database"""
        if not entry:
            return
            
        with self.lock:
            # Check if paste already exists
            for existing in self.db["onion_links"]:
                if existing.get("pasteId") == entry.get("pasteId"):
                    # Update existing entry
                    existing_links = [l["onionLink"] for l in existing.get("onionLinks", [])]
                    new_links = [l for l in entry["onionLinks"] if l["onionLink"] not in existing_links]
                    if new_links:
                        existing["onionLinks"].extend(new_links)
                    return
            
            # Add new entry
            self.db["onion_links"].append(entry)
            
            # Save periodically
            if len(self.db["onion_links"]) % self.config.get("save_interval", 100) == 0:
                self._save_db()
    
    def generate_paste_ids(self, start_id: int = 1, strategy: str = "sequential") -> str:
        """Generate paste IDs using different strategies"""
        if strategy == "sequential":
            # Sequential numeric IDs (oldest method)
            current_id = start_id
            while self.is_running:
                yield str(current_id)
                current_id += 1
                
        elif strategy == "alphanumeric":
            # Modern alphanumeric IDs (8 characters)
            chars = string.ascii_letters + string.digits
            while self.is_running:
                paste_id = ''.join(random.choices(chars, k=8))
                yield paste_id
                
        elif strategy == "mixed":
            # Mix of sequential and random
            current_id = start_id
            while self.is_running:
                if random.random() < 0.7:  # 70% sequential
                    yield str(current_id)
                    current_id += 1
                else:  # 30% random
                    chars = string.ascii_letters + string.digits
                    paste_id = ''.join(random.choices(chars, k=8))
                    yield paste_id
    
    def search_pastebin(self, search_term: str, max_pages: int = 50) -> List[str]:
        """Search Pastebin for specific terms and extract paste IDs"""
        paste_ids = []
        
        try:
            for page in range(1, max_pages + 1):
                if not self.is_running:
                    break
                    
                self._rate_limit()
                
                # Pastebin search (note: this may be limited)
                search_params = {
                    'q': search_term,
                    'page': page
                }
                
                response = requests.get(self.search_url, params=search_params, headers=self.headers, timeout=10)
                
                if response.status_code != 200:
                    logger.warning(f"Search failed for term '{search_term}', page {page}")
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract paste links from search results
                paste_links = soup.select("a[href^='/']")
                page_ids = []
                
                for link in paste_links:
                    href = link.get('href', '')
                    if len(href) > 1 and href.startswith('/') and len(href) <= 10:
                        paste_id = href[1:]  # Remove leading '/'
                        if paste_id not in self.processed_ids:
                            page_ids.append(paste_id)
                
                if not page_ids:
                    # No more results
                    break
                    
                paste_ids.extend(page_ids)
                logger.info(f"Search '{search_term}' page {page}: found {len(page_ids)} paste IDs")
                
        except Exception as e:
            logger.error(f"Error searching for term '{search_term}': {e}")
        
        return paste_ids
    
    def run_enumeration_scan(self, start_id: int = 1, max_pastes: Optional[int] = None):
        """Run systematic paste ID enumeration"""
        self.is_running = True
        logger.info(f"Starting enumeration scan from ID {start_id}")
        
        # Record scan session
        session_info = {
            "start_time": datetime.datetime.now().isoformat(),
            "strategy": "enumeration",
            "start_id": start_id,
            "max_pastes": max_pastes
        }
        
        max_workers = self.config.get("max_workers", 10)
        batch_size = self.config.get("batch_size", 1000)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            paste_id_gen = self.generate_paste_ids(start_id, "mixed")
            
            batch = []
            processed_count = 0
            
            for paste_id in paste_id_gen:
                if not self.is_running:
                    break
                    
                if max_pastes and processed_count >= max_pastes:
                    break
                
                batch.append(paste_id)
                
                if len(batch) >= batch_size:
                    # Process batch
                    futures = {executor.submit(self.scrape_single_paste, pid): pid for pid in batch}
                    
                    for future in as_completed(futures):
                        if not self.is_running:
                            break
                            
                        result = future.result()
                        if result:
                            self.add_entry(result)
                        
                        processed_count += 1
                        self.scan_progress["processed"] = processed_count
                        
                        if processed_count % 100 == 0:
                            logger.info(f"Processed {processed_count} pastes, found {self.scan_progress['found']} onion links")
                    
                    batch = []
        
        # Final save
        self._save_db()
        session_info["end_time"] = datetime.datetime.now().isoformat()
        session_info["processed"] = processed_count
        session_info["found"] = self.scan_progress["found"]
        
        self.db["metadata"]["scan_sessions"].append(session_info)
        self._save_db()
        
        logger.info(f"Enumeration scan completed. Processed {processed_count} pastes.")
    
    def run_search_scan(self, search_terms: List[str] = None, max_pastes: Optional[int] = None):
        """Run search-based discovery"""
        self.is_running = True
        
        if not search_terms:
            search_terms = [
                "onion", "darkweb", "dark web", "tor", "hidden service",
                ".onion", "deep web", "marketplace", "silk road"
            ]
        
        logger.info(f"Starting search-based scan with {len(search_terms)} terms")
        
        all_paste_ids = set()
        
        # Collect paste IDs from searches
        for term in search_terms:
            if not self.is_running:
                break
                
            logger.info(f"Searching for term: '{term}'")
            paste_ids = self.search_pastebin(term)
            all_paste_ids.update(paste_ids)
            
            if max_pastes and len(all_paste_ids) >= max_pastes:
                all_paste_ids = list(all_paste_ids)[:max_pastes]
                break
        
        logger.info(f"Collected {len(all_paste_ids)} unique paste IDs from searches")
        
        # Process collected paste IDs
        max_workers = self.config.get("max_workers", 10)
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.scrape_single_paste, pid): pid for pid in all_paste_ids}
            
            for future in as_completed(futures):
                if not self.is_running:
                    break
                    
                result = future.result()
                if result:
                    self.add_entry(result)
                
                processed_count += 1
                self.scan_progress["processed"] = processed_count
                
                if processed_count % 50 == 0:
                    logger.info(f"Processed {processed_count}/{len(all_paste_ids)} search results")
        
        self._save_db()
        logger.info(f"Search scan completed. Processed {processed_count} pastes.")
    
    def run_comprehensive_scan(self, duration_hours: Optional[int] = None, max_pastes: Optional[int] = None):
        """Run comprehensive scan using all strategies"""
        self.is_running = True
        start_time = time.time()
        
        logger.info("Starting comprehensive scan of entire Pastebin")
        
        # Start with search-based discovery for quick wins
        logger.info("Phase 1: Search-based discovery")
        self.run_search_scan(max_pastes=max_pastes//4 if max_pastes else None)
        
        if not self.is_running:
            return
        
        # Then systematic enumeration
        logger.info("Phase 2: Systematic enumeration")
        remaining_pastes = None
        if max_pastes:
            remaining_pastes = max_pastes - self.scan_progress["processed"]
            
        if remaining_pastes is None or remaining_pastes > 0:
            self.run_enumeration_scan(max_pastes=remaining_pastes)
        
        # Check duration limit
        if duration_hours:
            elapsed_hours = (time.time() - start_time) / 3600
            if elapsed_hours >= duration_hours:
                logger.info(f"Duration limit of {duration_hours} hours reached")
                self.is_running = False
        
        self._save_db()
        logger.info("Comprehensive scan completed")
    
    def run_hybrid_scan(self, duration_hours: Optional[int] = None, max_pastes: Optional[int] = None):
        """Run hybrid approach alternating between strategies"""
        self.is_running = True
        start_time = time.time()
        
        logger.info("Starting hybrid scan approach")
        
        search_terms = self.config.get("search_terms", [
            "onion", "darkweb", "tor", ".onion", "hidden service"
        ])
        
        # Alternate between search and enumeration
        search_batch_size = 100
        enum_batch_size = 1000
        current_enum_id = self.config.get("start_paste_id", 1)
        
        while self.is_running:
            # Duration check
            if duration_hours:
                elapsed_hours = (time.time() - start_time) / 3600
                if elapsed_hours >= duration_hours:
                    break
            
            # Paste count check
            if max_pastes and self.scan_progress["processed"] >= max_pastes:
                break
            
            # Search phase
            logger.info("Hybrid phase: Search-based discovery")
            term = random.choice(search_terms)
            search_ids = self.search_pastebin(term, max_pages=5)
            
            # Process search results
            for paste_id in search_ids[:search_batch_size]:
                if not self.is_running:
                    break
                result = self.scrape_single_paste(paste_id)
                if result:
                    self.add_entry(result)
                self.scan_progress["processed"] += 1
            
            # Enumeration phase
            logger.info("Hybrid phase: Systematic enumeration")
            enum_gen = self.generate_paste_ids(current_enum_id, "sequential")
            
            for i, paste_id in enumerate(enum_gen):
                if i >= enum_batch_size or not self.is_running:
                    break
                    
                result = self.scrape_single_paste(paste_id)
                if result:
                    self.add_entry(result)
                self.scan_progress["processed"] += 1
                current_enum_id += 1
            
            # Save progress periodically
            if self.scan_progress["processed"] % 500 == 0:
                self._save_db()
                logger.info(f"Hybrid scan progress: {self.scan_progress}")
        
        self._save_db()
        logger.info("Hybrid scan completed")
    
    def stop_scan(self):
        """Stop the current scan gracefully"""
        logger.info("Stopping scan...")
        self.is_running = False
        self._save_db()
    
    def get_statistics(self) -> Dict:
        """Get current scan statistics"""
        total_pastes = len(self.db.get("onion_links", []))
        total_links = sum(len(entry.get("onionLinks", [])) for entry in self.db.get("onion_links", []))
        unique_links = len(set(
            link["onionLink"] for entry in self.db.get("onion_links", [])
            for link in entry.get("onionLinks", [])
        ))
        
        return {
            "total_pastes_with_onions": total_pastes,
            "total_onion_links": total_links,
            "unique_onion_links": unique_links,
            "scan_progress": self.scan_progress,
            "processed_ids_count": len(self.processed_ids)
        }


# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Comprehensive Pastebin Scanner")
    parser.add_argument("--strategy", choices=["enumeration", "search", "comprehensive", "hybrid"], 
                       default="comprehensive")
    parser.add_argument("--max-pastes", type=int, help="Maximum pastes to process")
    parser.add_argument("--duration", type=int, help="Duration in hours")
    parser.add_argument("--workers", type=int, default=10, help="Number of worker threads")
    
    args = parser.parse_args()
    
    config = {
        "max_workers": args.workers,
        "save_interval": 50,
        "delay_range": [1, 2]
    }
    
    scraper = ComprehensivePastebinScraper(config=config)
    
    try:
        if args.strategy == "enumeration":
            scraper.run_enumeration_scan(max_pastes=args.max_pastes)
        elif args.strategy == "search":
            scraper.run_search_scan(max_pastes=args.max_pastes)
        elif args.strategy == "comprehensive":
            scraper.run_comprehensive_scan(args.duration, args.max_pastes)
        elif args.strategy == "hybrid":
            scraper.run_hybrid_scan(args.duration, args.max_pastes)
            
    except KeyboardInterrupt:
        print("\nStopping scan...")
        scraper.stop_scan()
    
    # Show final stats
    stats = scraper.get_statistics()
    print(f"\nFinal Statistics:")
    print(f"Pastes with .onion links: {stats['total_pastes_with_onions']}")
    print(f"Total .onion links found: {stats['total_onion_links']}")
    print(f"Unique .onion links: {stats['unique_onion_links']}")
    print(f"Total pastes processed: {stats['scan_progress']['processed']}")