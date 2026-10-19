import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
import json
import os
import re

SEARCHES = [
    "pokemon game",
    "mario game",
    "deadpool game",
    "family guy game",
    "xbox game",
    "playstation game",
    "ps1 game",
    "nintendo switch game",
]

MAX_PRICE = 10.00
SEEN_FILE = "seen.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 16) AppleWebKit/537.36 Chrome/130.0.0.0 Mobile Safari/537.36"
}

webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")

try:
    with open(SEEN_FILE) as f:
        seen = set(json.load(f))
except (FileNotFoundError, ValueError):
    seen = set()

new_seen = set(seen)
alerts = 0

for search in SEARCHES:
    url = (
        "https://www.vinted.com/catalog"
        "?search_text=" + quote(search) +
        "&order=newest_first"
    )

    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for link in soup.select('a[href*="/items/"]'):
            href = link.get("href", "").split("?")[0]
            match = re.search(r"/items/(\d+)", href)

            if not match:
                continue

            item_id = match.group(1)
            if item_id in new_seen:
                continue

            title = link.get_text(" ", strip=True)
            details = link.parent.parent.get_text(" ", strip=True)

            price_match = re.search(r"\$(\d+(?:\.\d{2})?)", details)
            if not price_match:
                continue

            price = float(price_match.group(1))
            if price > MAX_PRICE:
                continue

            new_seen.add(item_id)

            if not seen:
                continue

            if webhook:
                message = {
                    "content": (
                        "🎯 **RESPawn Vinted Alert**\n"
                        f"Search: {search}\n"
                        f"Item: {title[:150]}\n"
                        f"Listed price: ${price:.2f}\n"
                        f"{urljoin('https://www.vinted.com', href)}"
                    )
                }
                result = requests.post(webhook, json=message, timeout=15)
                result.raise_for_status()
                alerts += 1

        print(f"Checked: {search}")

    except requests.RequestException as error:
        print(f"Error checking {search}: {error}")

with open(SEEN_FILE, "w") as f:
    json.dump(sorted(new_seen), f)

print(f"Finished. Sent {alerts} alerts.")
