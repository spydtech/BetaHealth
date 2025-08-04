import re
import json

from all_products import ALL_PRODUCTS

def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower().strip()).strip('-')

updated = []
seen_ids = set()

for p in ALL_PRODUCTS:
    title_slug = slugify(p['title'])
    category_slug = slugify(p['category'])
    new_id = f"{category_slug}-{title_slug}"

    # Ensure unique id in case multiple with same title & category
    suffix = 1
    original_id = new_id
    while new_id in seen_ids:
        suffix += 1
        new_id = f"{original_id}-{suffix}"

    p['id'] = new_id
    seen_ids.add(new_id)
    updated.append(p)

# Output updated list to replace all_products.py
with open("updated_all_products.py", "w") as f:
    f.write("ALL_PRODUCTS = ")
    json.dump(updated, f, indent=4)
