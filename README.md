# Pastebin .onion Link Scraper

A comprehensive tool for scraping and analyzing .onion links from Pastebin with optional proxy rotation and LLM-enhanced detection capabilities.

## Features

- **Basic Scraping**: Extract .onion links from Pastebin archive and API
- **Proxy Rotation**: Avoid rate limiting and IP bans with proxy support
- **LLM Enhancement**: Use AI to detect obfuscated links and classify them (optional)
- **Scheduled Operation**: Run continuously with configurable intervals
- **JSON Database**: Store results in structured format with metadata

## Setup Instructions

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the project directory:

```bash
# Optional: Pastebin API key for enhanced scraping
PASTEBIN_API_KEY=your_pastebin_api_key_here

# Optional: Groq API key for LLM features
GROQ_API_KEY=your_groq_api_key_here
```

### 3. Proxy Configuration (Optional)

If using proxy rotation, create a `proxies.txt` file with one proxy per line:

```
http://proxy1.example.com:8080
http://proxy2.example.com:8080
socks5://proxy3.example.com:1080
```

### 4. Configuration File

The tool will automatically create a `config.json` file with default settings:

```json
{
  "db_path": "onion_links.json",
  "use_proxies": false,
  "proxy_file": "proxies.txt",
  "use_llm": false,
  "llm_model": "meta-llama/llama-3.1-70b-versatile",
  "scrape_interval_minutes": 30,
  "api_scrape_interval_hours": 2
}
```

## Usage

### Basic Usage (Recommended)

Run the scraper with basic functionality only:

```bash
python main_script.py
```

This will:
1. Perform an initial scrape
2. Show an interactive menu with options
3. NOT use LLM or proxy features (most reliable)

### Single Run Mode

Execute one scrape and exit:

```bash
python main_script.py --once
```

### Daemon Mode

Run continuously in the background:

```bash
python main_script.py --daemon
```

### Advanced Options

Enable proxy rotation:
```bash
python main_script.py --use-proxies --proxy-file proxies.txt
```

Enable LLM features (only if needed):
```bash
python main_script.py --use-llm --llm-api-key your_groq_api_key
```

Set custom interval:
```bash
python main_script.py --interval 15  # 15 minutes
```

### Command Line Options

```
--db-path PATH          Path to database file (default: onion_links.json)
--api-key KEY          Pastebin API key
--use-proxies          Enable proxy rotation
--proxy-file FILE      File containing proxy servers
--use-llm              Enable LLM features (use sparingly)
--llm-api-key KEY      Groq API key for LLM
--llm-model MODEL      LLM model to use
--interval MINUTES     Scraping interval in minutes
--once                 Run once and exit
--daemon               Run as daemon process
```

## Project Structure

```
├── main_script.py              # Main entry point
├── pastebin_onion_scraper.py   # Core scraper functionality
├── proxy_extension.py          # Proxy rotation support
├── llm_extension.py           # LLM enhancement features
├── requirements.txt           # Python dependencies
├── .env                      # Environment variables (create this)
├── config.json              # Configuration (auto-generated)
├── proxies.txt             # Proxy list (optional)
├── onion_links.json       # Database file (auto-generated)
└── onion_scraper.log     # Log file (auto-generated)
```

## Database Structure

The tool stores results in JSON format:

```json
{
  "onion_links": [
    {
      "crawledTimeStamp": "2024-01-01T10:00:00",
      "pasteDateTimestamp": "2024-01-01T09:30:00",
      "sourcePasteUrl": "https://pastebin.com/abc123",
      "sourcePasteTitle": "Example Paste",
      "onionLinks": [
        {
          "onionLink": "http://example.onion",
          "classification": {
            "category": "marketplace",
            "confidence": 0.8,
            "description": "Likely a marketplace"
          }
        }
      ]
    }
  ]
}
```

## Important Notes

### LLM Usage Recommendations

- **Use LLM features sparingly** - They consume API credits and add complexity
- LLM is only beneficial when:
  - You suspect heavily obfuscated content
  - You need content classification
  - Basic regex extraction is insufficient
- For most use cases, **basic scraping is sufficient and more reliable**

### Rate Limiting

- Default delays are included to avoid rate limiting
- With proxies: 1-3 second random delays
- Without proxies: 2 second fixed delays
- Pastebin API has its own rate limits

### Legal and Ethical Considerations

- This tool is for research and educational purposes
- Respect Pastebin's terms of service
- Be mindful of the content you're scraping
- Consider the legal implications in your jurisdiction

## Troubleshooting

### Common Issues

1. **No results found**: 
   - Check internet connection
   - Verify Pastebin is accessible
   - Try with different time intervals

2. **Rate limiting errors**:
   - Increase delay intervals
   - Use proxy rotation
   - Consider using Pastebin API key

3. **LLM errors**:
   - Verify Groq API key is correct
   - Check API quotas and limits
   - Try different model if available

4. **Import errors**:
   - Ensure all dependencies are installed
   - Check Python version (3.7+ recommended)

### Logs

Check `onion_scraper.log` for detailed error information and operation logs.

## API Keys

### Pastebin API Key (Optional)
- Sign up at https://pastebin.com/api
- Provides access to trending pastes and higher rate limits

### Groq API Key (Optional, for LLM features)
- Sign up at https://console.groq.com
- Required only if using `--use-llm` flag
- Free tier available with rate limits

## Performance Tips

1. **Start with basic mode** - Most reliable and efficient
2. **Use proxies only if rate limited** - Adds complexity but helps with scale
3. **Enable LLM only when necessary** - Costs API credits and processing time
4. **Monitor logs** - Watch for errors and rate limiting
5. **Adjust intervals** - Longer intervals are more polite but slower

## Security Notes

- Store API keys in `.env` file, not in code
- Be cautious with proxy sources
- The tool finds .onion links but doesn't access them
- Consider running in isolated environment for security
