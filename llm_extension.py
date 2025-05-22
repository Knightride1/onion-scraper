"""
LLM Integration Extension for Pastebin Onion Link Scraper

This module integrates LLM capabilities to enhance the scraper with:
1. Intelligent content analysis to detect potential .onion links in obfuscated content
2. Classification of onion links by likely category/purpose
3. Smart filtering of false positives

Uses Groq API for LLM processing.
"""

import os
import json
import logging
import time
from typing import List, Dict, Any, Tuple, Optional
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("llm_extension")

class LLMProcessor:
    """Class for processing content with an LLM using Groq API"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "meta-llama/llama-3.1-70b-versatile"):
        """Initialize the LLM processor with API key and model"""
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")
        self.model = model
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
    def _make_llm_request(self, messages: List[Dict], temperature: float = 0.1, 
                         max_tokens: int = 500, response_format: Optional[Dict] = None) -> Optional[str]:
        """Make a request to the LLM API"""
        if not self.api_key:
            logger.warning("No API key provided for LLM processing")
            return None
            
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            if response_format:
                payload["response_format"] = response_format
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload
            )
            
            if response.status_code != 200:
                logger.error(f"LLM API error: {response.status_code} - {response.text}")
                return None
                
            # Parse the response
            response_data = response.json()
            return response_data["choices"][0]["message"]["content"].strip()
            
        except Exception as e:
            logger.error(f"Error making LLM request: {e}")
            return None
        
    def extract_hidden_onion_links(self, content: str) -> List[str]:
        """Use LLM to find potentially obfuscated .onion links"""
        # Only use LLM if content seems to have potential indicators
        # Check for common obfuscation patterns first
        potential_indicators = [
            '.onion', 'darkweb', 'dark web', 'tor', 'hidden service',
            'marketplace', 'drugs', 'bitcoin', 'crypto', 'anonymous'
        ]
        
        if not any(indicator.lower() in content.lower() for indicator in potential_indicators):
            return []  # No need for LLM processing
            
        messages = [
            {"role": "system", "content": "You are an expert at identifying obfuscated or encoded .onion URLs in text. "
                                        "Extract any potential .onion links from the text, even if they are somewhat hidden "
                                        "or obfuscated. Only return actual .onion links that are likely to be valid. "
                                        "A valid .onion address consists of 16 or 56 base32 characters (a-z, 2-7) followed by .onion. "
                                        "Return only the links, one per line. If none found, return 'NONE'."},
            {"role": "user", "content": content[:2000]}  # Limit content size
        ]
        
        llm_output = self._make_llm_request(messages)
        if not llm_output or llm_output.upper() == "NONE":
            return []
            
        # Extract links from the LLM output
        import re
        onion_pattern = re.compile(r'(?:https?://)?(?:[a-zA-Z2-7]{16,56}\.onion)(?:/\S*)?', re.IGNORECASE)
        matches = onion_pattern.findall(llm_output)
        
        # Clean and normalize links
        links = []
        for link in matches:
            # Ensure links start with http if they don't already
            if not link.startswith(('http://', 'https://')):
                link = f"http://{link}"
            links.append(link)
        
        return links
    
    def classify_onion_link(self, link: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Attempt to classify an onion link by likely category/purpose"""
        if not self.api_key:
            return {"category": "unknown", "confidence": 0.0, "description": "No API key provided"}
            
        # Prepare prompt with or without context
        prompt_text = f"Classify this .onion link without visiting it: {link}"
        if context:
            prompt_text += f"\n\nContext from the paste where this link was found:\n{context[:1000]}..."
            
        messages = [
            {"role": "system", "content": "You are an expert at classifying dark web .onion links based on their URL structure "
                                        "and contextual information. Classify the provided .onion link into one of these categories: "
                                        "marketplace, forum, blog, search_engine, email, cryptocurrency, hosting, social_network, "
                                        "library, technical_service, or unknown. Return a JSON object with the fields: "
                                        "category, confidence (0.0-1.0), and description. "
                                        "DO NOT visit or open the link. Make your classification based purely on the URL structure and "
                                        "any provided context."},
            {"role": "user", "content": prompt_text}
        ]
        
        llm_output = self._make_llm_request(
            messages, 
            temperature=0.3, 
            response_format={"type": "json_object"}
        )
        
        if not llm_output:
            return {"category": "unknown", "confidence": 0.0, "description": "API error"}
            
        try:
            classification_data = json.loads(llm_output)
            # Ensure the expected fields are present
            return {
                "category": classification_data.get("category", "unknown"),
                "confidence": float(classification_data.get("confidence", 0.0)),
                "description": classification_data.get("description", "No description provided")
            }
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM output as JSON: {llm_output}")
            return {"category": "unknown", "confidence": 0.0, "description": "JSON parsing error"}
    
    def filter_false_positives(self, links: List[str], context: str) -> List[str]:
        """Filter out likely false positive onion links using LLM judgment"""
        if not self.api_key or not links:
            return links
            
        # Only use LLM filtering if we have many links or suspicious context
        if len(links) <= 3:
            return links  # Trust regex for small numbers
            
        links_str = "\n".join(links)
        messages = [
            {"role": "system", "content": "You are an expert at identifying valid .onion URLs. "
                                        "You will be presented with a list of potential .onion links extracted from text. "
                                        "Analyze each link and determine if it's likely a real .onion address or a false positive. "
                                        "Return only the list of links that are likely valid .onion addresses, one per line. "
                                        "If none are valid, return 'NONE'."},
            {"role": "user", "content": f"Here are potential .onion links extracted from a paste:\n\n{links_str}\n\n"
                                      f"Context from the paste:\n{context[:1000]}"}
        ]
        
        llm_output = self._make_llm_request(messages)
        
        if not llm_output or llm_output.upper() == "NONE":
            return []
            
        # Extract the filtered links
        filtered_lines = [line.strip() for line in llm_output.split('\n') if line.strip()]
        
        # Ensure all links are properly formatted
        formatted_links = []
        for link in filtered_lines:
            if not link.startswith(('http://', 'https://')):
                link = f"http://{link}"
            formatted_links.append(link)
            
        return formatted_links
        

class LLMEnhancedScraper:
    """Enhanced scraper that uses LLM for improved link detection and classification"""
    
    def __init__(self, base_scraper, api_key: Optional[str] = None, model: str = "meta-llama/llama-3.1-70b-versatile"):
        """Initialize with a base scraper and LLM settings"""
        self.base_scraper = base_scraper
        self.llm_processor = LLMProcessor(api_key, model)
        
    def enhanced_extract_onion_links(self, content: str) -> List[str]:
        """Extract onion links with both regex and LLM approaches"""
        # First use the basic regex extraction
        if hasattr(self.base_scraper, 'extract_onion_links'):
            regex_links = self.base_scraper.extract_onion_links(content)
        else:
            # Fallback regex if method doesn't exist
            import re
            onion_pattern = re.compile(r'(?:https?://)?(?:[a-zA-Z2-7]{16,56}\.onion)(?:/\S*)?', re.IGNORECASE)
            matches = onion_pattern.findall(content)
            regex_links = []
            for link in matches:
                if not link.startswith(('http://', 'https://')):
                    link = f"http://{link}"
                regex_links.append(link)
        
        # Use LLM only if we have API key and content seems suspicious
        llm_links = []
        if self.llm_processor.api_key:
            llm_links = self.llm_processor.extract_hidden_onion_links(content)
        
        # Combine and deduplicate
        all_links = list(set(regex_links + llm_links))
        
        # Apply LLM filtering only if beneficial
        if len(all_links) > 3 and self.llm_processor.api_key:
            filtered_links = self.llm_processor.filter_false_positives(all_links, content)
            return filtered_links
        else:
            return all_links
    
    def enhanced_scrape_paste(self, paste_key: str) -> int:
        """Scrape a paste with enhanced link extraction"""
        paste_url = f"https://pastebin.com/raw/{paste_key}"
        try:
            # Get headers from base scraper or use default
            headers = getattr(self.base_scraper, 'headers', {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            
            response = requests.get(paste_url, headers=headers)
            if response.status_code == 200:
                content = response.text
                
                # Use enhanced extraction
                onion_links = self.enhanced_extract_onion_links(content)
                
                if not onion_links:
                    return 0
                    
                # Get paste metadata
                meta_url = f"https://pastebin.com/{paste_key}"
                meta_response = requests.get(meta_url, headers=headers)
                
                from bs4 import BeautifulSoup
                import datetime
                
                soup = BeautifulSoup(meta_response.text, 'html.parser')
                
                # Extract title
                title_element = soup.select_one(".info-top .paste-title")
                title = title_element.text.strip() if title_element else f"Unnamed Paste ({paste_key})"
                
                # Extract date
                date_element = soup.select_one(".date span")
                date_str = date_element.get('title', datetime.datetime.now().isoformat()) if date_element else datetime.datetime.now().isoformat()
                
                # Enhance with classification data only if LLM is available
                classified_links = []
                for link in onion_links:
                    if self.llm_processor.api_key:
                        classification = self.llm_processor.classify_onion_link(link, content[:2000])
                        classified_links.append({
                            "onionLink": link,
                            "classification": classification
                        })
                    else:
                        classified_links.append({
                            "onionLink": link
                        })
                
                # Add the enhanced entry to the database
                self.add_enhanced_entry(meta_url, title, date_str, classified_links)
                return len(onion_links)
            return 0
        except Exception as e:
            logger.error(f"Error in enhanced scraping of paste {paste_key}: {e}")
            return 0
            
    def add_enhanced_entry(self, source_paste_url: str, source_paste_title: str, 
                          paste_datetime: str, classified_links: List[Dict]):
        """Add an enhanced entry with classification data to the database"""
        if not classified_links:
            return
            
        # Get the database from base scraper
        base_db = getattr(self.base_scraper, 'db', {"onion_links": []})
        if "onion_links" not in base_db:
            base_db["onion_links"] = []
            
        # Check if we already have this paste
        for entry in base_db["onion_links"]:
            if entry["sourcePasteUrl"] == source_paste_url:
                # Update existing entry with any new links
                existing_links = [l["onionLink"] for l in entry.get("onionLinks", [])]
                new_links = [link for link in classified_links if link["onionLink"] not in existing_links]
                
                if new_links:
                    # Make sure onionLinks exists
                    if "onionLinks" not in entry:
                        entry["onionLinks"] = []
                    
                    entry["onionLinks"].extend(new_links)
                    logger.info(f"Updated {source_paste_url} with {len(new_links)} new classified onion links")
                return
        
        # If we get here, this is a new paste
        import datetime
        new_entry = {
            "crawledTimeStamp": datetime.datetime.now().isoformat(),
            "pasteDateTimestamp": paste_datetime,
            "sourcePasteUrl": source_paste_url,
            "onionLinks": classified_links,
            "sourcePasteTitle": source_paste_title
        }
        base_db["onion_links"].append(new_entry)
        logger.info(f"Added new paste {source_paste_url} with {len(classified_links)} classified onion links")
        
        # Save the database
        if hasattr(self.base_scraper, '_save_db'):
            self.base_scraper._save_db()
        
    def run_enhanced_scraper(self):
        """Run the scraper with LLM enhancements"""
        logger.info("Starting enhanced scraper with LLM capabilities")
        
        # First run an initial scrape
        self.enhanced_scrape_archive()
        
        # Set up a scheduler
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError:
            logger.error("APScheduler not installed. Running in single-shot mode.")
            return
            
        scheduler = BackgroundScheduler()
        
        # Schedule enhanced archive scraping every 30 minutes
        scheduler.add_job(self.enhanced_scrape_archive, 'interval', minutes=30)
        
        scheduler.start()
        logger.info("Scheduled enhanced scraping tasks started")
        
        try:
            # Keep the script running
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            logger.info("Enhanced scheduler shut down")
            
    def enhanced_scrape_archive(self):
        """Scrape the archive page with enhanced link extraction"""
        try:
            logger.info("Starting enhanced archive page scrape")
            archive_url = getattr(self.base_scraper, 'archive_url', "https://pastebin.com/archive")
            headers = getattr(self.base_scraper, 'headers', {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            
            response = requests.get(archive_url, headers=headers)
            if response.status_code == 200:
                from bs4 import BeautifulSoup
                
                soup = BeautifulSoup(response.text, 'html.parser')
                paste_links = soup.select("table.archive-table tr td:nth-child(1) a")
                
                total_onions = 0
                for link in paste_links:
                    paste_key = link.get('href').strip('/')
                    # Don't process too quickly to avoid rate limiting
                    time.sleep(2)
                    total_onions += self.enhanced_scrape_paste(paste_key)
                
                logger.info(f"Enhanced archive scrape complete. Found {total_onions} onion links")
                return total_onions
            else:
                logger.error(f"Failed to access archive page: {response.status_code}")
                return 0
        except Exception as e:
            logger.error(f"Error during enhanced archive scrape: {e}")
            return 0


# Example usage
if __name__ == "__main__":
    import os
    from pastebin_onion_scraper import PastebinOnionScraper
    
    # Get the Groq API key from environment
    api_key = os.environ.get("GROQ_API_KEY")
    
    # Initialize the base scraper
    base_scraper = PastebinOnionScraper()
    
    # Initialize the LLM-enhanced scraper
    enhanced_scraper = LLMEnhancedScraper(base_scraper, api_key)
    
    # Run the enhanced scraper
    enhanced_scraper.run_enhanced_scraper()