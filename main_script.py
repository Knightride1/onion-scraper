"""
Comprehensive Pastebin .onion Link Scraper - Main Script

This tool performs comprehensive scanning of Pastebin to find ALL .onion links
across the entire platform, not just recent archives.

Strategies:
1. API-based comprehensive scanning (if API key available)
2. Systematic paste ID enumeration and scanning
3. Search-based discovery using common dark web terms
4. Archive page deep crawling with historical data
"""

import os
import sys
import argparse
import logging
import json
import time
import random
import string
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Import the components
from pastebin_comprehensive_scraper import ComprehensivePastebinScraper
from proxy_extension import ProxyManager, ExtendedPastebinScraper
from llm_extension import LLMProcessor, LLMEnhancedScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("comprehensive_onion_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("main")

def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """Load configuration from a JSON file"""
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)
        else:
            # Return default config for comprehensive scanning
            return {
                "db_path": "comprehensive_onion_links.json",
                "use_proxies": True,  # Recommended for comprehensive scanning
                "proxy_file": "proxies.txt",
                "use_llm": False,  # Only when specifically needed
                "llm_model": "meta-llama/llama-3.1-70b-versatile",
                "scan_strategy": "comprehensive",  # comprehensive, enumeration, search, or hybrid
                "max_workers": 10,  # Concurrent threads
                "delay_range": [1, 3],  # Random delay between requests
                "batch_size": 1000,  # Process in batches
                "start_paste_id": 1,  # Where to start enumeration
                "search_terms": [
                    "onion", "darkweb", "dark web", "tor", "hidden service",
                    "marketplace", "drugs", "bitcoin", "crypto", "anonymous",
                    ".onion", "deep web", "silk road", "alphabay"
                ],
                "save_interval": 100,  # Save every N discoveries
                "rate_limit_delay": 60,  # Seconds to wait if rate limited
                "max_retries": 3
            }
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}

def save_config(config: Dict[str, Any], config_path: str = "config.json"):
    """Save configuration to a JSON file"""
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Configuration saved to {config_path}")
    except Exception as e:
        logger.error(f"Error saving config: {e}")

def display_stats(scraper):
    """Display current statistics"""
    if hasattr(scraper, 'base_scraper'):
        db = scraper.base_scraper.db
    else:
        db = scraper.db
        
    total_pastes = len(db.get("onion_links", []))
    total_links = sum(len(entry.get("onionLinks", [])) for entry in db.get("onion_links", []))
    unique_links = len(set(
        link["onionLink"] for entry in db.get("onion_links", [])
        for link in entry.get("onionLinks", [])
    ))
    
    print(f"\n=== COMPREHENSIVE SCAN STATISTICS ===")
    print(f"Total pastes with .onion links: {total_pastes}")
    print(f"Total .onion links found: {total_links}")
    print(f"Unique .onion links: {unique_links}")
    
    if hasattr(scraper, 'scan_progress'):
        print(f"Scan progress: {scraper.scan_progress}")
    
    # Show some sample links
    if total_links > 0:
        print(f"\nSample .onion links found:")
        sample_links = []
        for entry in db.get("onion_links", [])[:5]:
            for link in entry.get("onionLinks", [])[:2]:
                sample_links.append(link["onionLink"])
                if len(sample_links) >= 10:
                    break
            if len(sample_links) >= 10:
                break
        
        for i, link in enumerate(sample_links, 1):
            print(f"  {i}. {link}")

def main():
    """Main function for comprehensive Pastebin scanning"""
    parser = argparse.ArgumentParser(description="Comprehensive Pastebin .onion Link Scraper")
    
    # Basic configuration
    parser.add_argument("--db-path", help="Path to the database file", default=None)
    parser.add_argument("--api-key", help="Pastebin API key", default=None)
    
    # Scanning strategy
    parser.add_argument("--strategy", choices=["comprehensive", "enumeration", "search", "hybrid"], 
                       help="Scanning strategy", default=None)
    parser.add_argument("--start-id", type=int, help="Starting paste ID for enumeration", default=None)
    parser.add_argument("--batch-size", type=int, help="Batch size for processing", default=None)
    parser.add_argument("--max-workers", type=int, help="Maximum concurrent workers", default=None)
    
    # Proxy configuration
    parser.add_argument("--use-proxies", help="Use proxy rotation (recommended)", action="store_true")
    parser.add_argument("--proxy-file", help="File containing proxy servers", default=None)
    
    # LLM configuration
    parser.add_argument("--use-llm", help="Use LLM for enhanced detection", action="store_true")
    parser.add_argument("--llm-api-key", help="Groq API key", default=None)
    
    # Execution control
    parser.add_argument("--duration", type=int, help="Run for specified hours", default=None)
    parser.add_argument("--max-pastes", type=int, help="Maximum pastes to process", default=None)
    
    args = parser.parse_args()
    
    # Load and update configuration
    config = load_config()
    
    if args.db_path:
        config["db_path"] = args.db_path
    if args.api_key:
        config["pastebin_api_key"] = args.api_key
    if args.strategy:
        config["scan_strategy"] = args.strategy
    if args.start_id:
        config["start_paste_id"] = args.start_id
    if args.batch_size:
        config["batch_size"] = args.batch_size
    if args.max_workers:
        config["max_workers"] = args.max_workers
    if args.use_proxies:
        config["use_proxies"] = True
    if args.proxy_file:
        config["proxy_file"] = args.proxy_file
    if args.use_llm:
        config["use_llm"] = True
    if args.llm_api_key:
        config["llm_api_key"] = args.llm_api_key
    
    save_config(config)
    
    # Initialize the comprehensive scraper
    logger.info("Initializing comprehensive Pastebin scraper...")
    base_scraper = ComprehensivePastebinScraper(
        api_key=config.get("pastebin_api_key"),
        db_path=config.get("db_path", "comprehensive_onion_links.json"),
        config=config
    )
    
    active_scraper = base_scraper
    
    # Add proxy support (recommended for comprehensive scanning)
    if config.get("use_proxies"):
        logger.info("Enabling proxy support for comprehensive scanning...")
        extended_scraper = ExtendedPastebinScraper(base_scraper)
        
        if config.get("proxy_file") and os.path.exists(config.get("proxy_file")):
            extended_scraper.load_proxies_from_file(config.get("proxy_file"))
        else:
            logger.warning("Proxy support enabled but no proxy file found. This may cause rate limiting.")
            
        active_scraper = extended_scraper
    
    # Add LLM support if specifically requested
    if config.get("use_llm"):
        logger.info("Enabling LLM support...")
        llm_api_key = config.get("llm_api_key") or os.environ.get("GROQ_API_KEY")
        
        if llm_api_key:
            enhanced_scraper = LLMEnhancedScraper(
                active_scraper,
                api_key=llm_api_key,
                model=config.get("llm_model", "meta-llama/llama-3.1-70b-versatile")
            )
            active_scraper = enhanced_scraper
        else:
            logger.warning("LLM support requested but no API key provided.")
    
    # Display initial information
    print("=" * 60)
    print("COMPREHENSIVE PASTEBIN .ONION LINK SCANNER")
    print("=" * 60)
    print(f"Strategy: {config.get('scan_strategy', 'comprehensive')}")
    print(f"Database: {config.get('db_path')}")
    print(f"Proxies: {'Enabled' if config.get('use_proxies') else 'Disabled'}")
    print(f"LLM: {'Enabled' if config.get('use_llm') else 'Disabled'}")
    print(f"Workers: {config.get('max_workers', 10)}")
    print("=" * 60)
    
    # Run based on strategy
    strategy = config.get("scan_strategy", "comprehensive")
    
    try:
        if strategy == "comprehensive":
            logger.info("Starting comprehensive scan of entire Pastebin...")
            active_scraper.run_comprehensive_scan(
                duration_hours=args.duration,
                max_pastes=args.max_pastes
            )
            
        elif strategy == "enumeration":
            logger.info("Starting systematic paste ID enumeration...")
            active_scraper.run_enumeration_scan(
                start_id=config.get("start_paste_id", 1),
                max_pastes=args.max_pastes
            )
            
        elif strategy == "search":
            logger.info("Starting search-based discovery...")
            active_scraper.run_search_scan(
                search_terms=config.get("search_terms", []),
                max_pastes=args.max_pastes
            )
            
        elif strategy == "hybrid":
            logger.info("Starting hybrid scanning approach...")
            active_scraper.run_hybrid_scan(
                duration_hours=args.duration,
                max_pastes=args.max_pastes
            )
        
        # Interactive monitoring
        print("\nScan started! Press 's' for stats, 'q' to quit gracefully...")
        
        while active_scraper.is_running if hasattr(active_scraper, 'is_running') else True:
            try:
                user_input = input().strip().lower()
                if user_input == 's':
                    display_stats(active_scraper)
                elif user_input == 'q':
                    logger.info("Graceful shutdown requested...")
                    if hasattr(active_scraper, 'stop_scan'):
                        active_scraper.stop_scan()
                    break
                elif user_input == 'h':
                    print("Commands: 's' = stats, 'q' = quit, 'h' = help")
            except KeyboardInterrupt:
                logger.info("Interrupt received, stopping scan...")
                if hasattr(active_scraper, 'stop_scan'):
                    active_scraper.stop_scan()
                break
            except EOFError:
                # Handle cases where input is not available
                time.sleep(1)
                continue
                
    except Exception as e:
        logger.error(f"Error during comprehensive scan: {e}")
    
    finally:
        # Final statistics
        display_stats(active_scraper)
        logger.info("Comprehensive scan completed.")

if __name__ == "__main__":
    main()