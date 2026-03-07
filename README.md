**webmap** is a lightweight web crawler designed to discover files with extensions on target websites.

### Installation
```bash
# Install dependencies
pip install playwright tqdm

# Install Chromium (required for playwright)
playwright install chromium
```

### Requirements
```bash
playwright>=1.40.0
tqdm>=4.66.0
```
### Usage
```bash
python webmap.py -u https://target.com
```

### Example Output
```bash
webmap starting → https://target.com
stop and save with ctrl+c 

    1 Visiting page: https://target.com
      → .js         https://target.com/static/js/bundle.js
      → .css        https://target.com/css/main.css
      → .svg        https://target.com/assets/icon.svg
    2 Visiting page: https://target.com/about
      → .json       https://target.com/api/config.json
...

--- Scanning Has Been Stopped ---
Total Visited Pages: 47
Total Requests: 47
Total Number of Files Found: 128
.js          →     56
.json        →     12
.css         →     18
.svg         →     32
.woff2       →     10
Report Saved → extensions_found.json
```
Note: The tool continues scanning until it is stopped with Ctrl+C or until there are no more targets to scan.

### Ethical & Legal Warning
**Use only on targets you have explicit permission for.**  
**Unauthorized scanning is illegal. Always stay in-scope for bug bounty programs or your own assets.**
