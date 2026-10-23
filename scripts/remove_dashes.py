import json
import glob
import os

folder = '/home/dario/.openclaw/workspace/3. gapfeed/data/pristine_gaps/'

def clean_text(text):
    if not isinstance(text, str):
        return text
    # Replace em-dash with a comma or space
    text = text.replace("—", ",")
    # Replace double hyphen with comma
    text = text.replace("--", ",")
    # Replace space hyphen space with comma
    text = text.replace(" - ", ", ")
    return text

def process_dict(d):
    for k, v in d.items():
        if k == 'slug': # DO NOT touch the slug or it will break routing
            continue
        if isinstance(v, str):
            d[k] = clean_text(v)
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, str):
                    v[i] = clean_text(item)
                elif isinstance(item, dict):
                    process_dict(item)
        elif isinstance(v, dict):
            process_dict(v)

for path in glob.glob(os.path.join(folder, "*.json")):
    with open(path, 'r') as f:
        data = json.load(f)
    
    process_dict(data)
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

print("Cleaned up dashes from all JSON files.")