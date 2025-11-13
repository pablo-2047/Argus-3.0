# Create: tools/export_sherlock_sites.py
import json
import sys
sys.path.insert(0, 'sherlock/sherlock')

from sites import SitesInformation

sites_data = SitesInformation()
output = {}

for site_name, site_info in sites_data.items():
    if 'url' in site_info:
        output[site_name] = {
            'url': site_info['url'],
            'errorType': site_info.get('errorType', 'status_code')
        }

with open('sherlock_sites.json', 'w') as f:
    json.dump(output, f, indent=2)

print(f"Exported {len(output)} sites")