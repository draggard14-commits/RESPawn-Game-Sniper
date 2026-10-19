
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, urljoin
import json
import os
import re
import time

BASE = "https://www.vinted.com"
MAX_PRICE = 10.00
SEEN_FILE = "seen.json"

SEARCHES = [
    "xbox",
    "original xbox",
    "xbox 360",
    "xbox one",
    "xbox series x",
    "playstation",
    "ps1",
    "ps2",
    "ps3",
    "ps4",
    "ps5",
    "nintendo switch",
    "switch games",
    "switch 2",
    "pokemon game",
    "mario game",
    "deadpool game",
    "family guy game",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 16) "
        "AppleWebKit/537.36 "
        "Chrome/130.0.0.0 Mobile Safari/537.36"
    )
}

webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")

try:
    with open(SEEN_FILE, encoding="utf-8") as f:
        seen = set(str(x) for x in json.load(f))
except (FileNotFoundError, ValueError):
    seen = set()

new_seen = set(seen)
first_run = not seen
alerts = 0


def find_image(card):
    for img in card.select("img"):
        candidates = [
            img.get("src"),
            img.get("data-src"),
            img.get("data-original"),
        ]

        for attribute in ("srcset", "data-srcset"):
            srcset = img.get(attribute, "")
            if srcset:
                candidates.extend(
                    part.strip().split(" ")[0]
                    for part in srcset.split(",")
                )

        for candidate in candidates:
            if not candidate:
                continue

            candidate = urljoin(BASE, candidate.strip())

            if candidate.startswith("https://"):
                return candidate

    return None


def send_alert(search, title, price, item_url, image_url):
    embed = {
        "title": title[:250],
        "url": item_url,
        "description": (
            f"Search: {search}\n"
            f"Listed price: ${price:.2f}\n"
            f"[Open Vinted listing]({item_url})"
        ),
        "color": 3066993,
    }

    if image_url:
        embed["image"] = {"url": image_url}
    else:
        embed["description"] += "\nPhoto unavailable"

    payload = {
        "content": "🎯 **RESPawn Game Sniper**",
        "embeds": [embed],
    }

    response = requests.post(
        webhook, json=payload, timeout=15
    )

    if response.status_code == 429:
        try:
            wait = float(
                response.json().get("retry_after", 2)
            )
        except (ValueError, TypeError):
            wait = 2

        time.sleep(min(max(wait, 1), 60))
        response = requests.post(
            webhook, json=payload, timeout=15
        )

    response.raise_for_status()


for search in SEARCHES:
    url = (
        BASE
        + "/catalog?search_text="
        + quote(search)
        + "&order=newest_first"
    )

    try:
        response = requests.get(
            url, headers=HEADERS, timeout=20
        )
        response.raise_for_status()

        soup = BeautifulSoup(
            response.text, "html.parser"
        )

        for link in soup.select('a[href*="/items/"]'):
            href = link.get("href", "").split("?")[0]
            match = re.search(r"/items/(\d+)", href)

            if not match:
                continue

            item_id = match.group(1)

            if item_id in new_seen:
                continue

            card = link.parent
            if card.parent:
                card = card.parent

            details = card.get_text(" ", strip=True)

            price_match = re.search(
                r"\$\s*(\d+(?:\.\d{1,2})?)",
                details
            )

            if not price_match:
                continue

            price = float(price_match.group(1))

            if price > MAX_PRICE:
                continue

            item_url = urljoin(BASE, href)
            image_url = find_image(card)

            img = card.select_one("img")
            title = ""

            if img:
                title = img.get("alt", "").strip()

            if not title:
                title = link.get_text(
                    " ", strip=True
                )

            if not title:
                title = details[:150]

            if not title:
                title = "Vinted game listing"

            if first_run:
                new_seen.add(item_id)
                continue

            if not webhook:
                print("Discord webhook missing")
                continue

            try:
                send_alert(
                    search,
                    title,
                    price,
                    item_url,
                    image_url
                )
                new_seen.add(item_id)
                alerts += 1

                print(
                    f"Alert: {title[:60]} "
                    f"${price:.2f} "
                    f"Photo: {bool(image_url)}"
                )

                time.sleep(0.5)

            except requests.RequestException as error:
                print(
                    f"Discord alert failed for "
                    f"{item_id}: {error}"
                )

        print(f"Checked: {search}")

    except requests.RequestException as error:
        print(
            f"Error checking {search}: {error}"
        )

with open(SEEN_FILE, "w", encoding="utf-8") as f:
    json.dump(sorted(new_seen), f)

print(
    f"Finished. Sent {alerts} alerts. "
    f"Tracking {len(new_seen)} listings."
)
