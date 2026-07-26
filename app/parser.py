import re
from typing import List, Dict, Any, Tuple

# Mapping of M3U group-title values to Supabase category IDs and Category Metadata
CATEGORY_MAP = {
    "SM All TV": {"id": "sm-all-tv", "name": "SM All TV", "sort_order": 21},
    "IPTV_BDIX": {"id": "iptv-bdix", "name": "IPTV BDIX", "sort_order": 22},
    "SM_IPTV": {"id": "sm-iptv", "name": "SM IPTV", "sort_order": 23},
    "Cartoon": {"id": "kids", "name": "Kids", "sort_order": 2},
    "Toffee": {"id": "toffee", "name": "Toffee", "sort_order": 10},
    "Fancode": {"id": "fancode", "name": "FanCode", "sort_order": 19},
    "Tapmad": {"id": "tapmad", "name": "Tapmad", "sort_order": 20},
}

KIDS_KEYWORDS = ["kid", "cartoon", "disney", "nick", "pogo", "sonic", "anime", "baby", "doraemon", "motu patlu", "gopal"]

def get_category_info(group_title: str, channel_name: str) -> Tuple[str, str, int]:
    """
    Determines category_id, category_name, and sort_order based on group-title and channel name.
    """
    # Check exact group mapping
    if group_title in CATEGORY_MAP:
        info = CATEGORY_MAP[group_title]
        return info["id"], info["name"], info["sort_order"]
    
    # Check if group title or channel name indicates Kids category
    combined_str = f"{group_title} {channel_name}".lower()
    if any(k in combined_str for k in KIDS_KEYWORDS):
        return "kids", "Kids", 2

    # Default fallback category
    clean_id = re.sub(r'[^a-z0-9]+', '-', group_title.lower()).strip('-') or "uncategorized"
    return clean_id, group_title or "Uncategorized", 50


def parse_m3u_playlist(m3u_content: str) -> List[Dict[str, Any]]:
    """
    Parses an M3U playlist and returns a list of channel dicts structured for Supabase.
    Ensures every channel ID generated is strictly unique to prevent batch insertion conflicts.
    """
    channels = []
    lines = m3u_content.splitlines()
    
    current_extinf = None
    sort_counter = 1
    seen_ids = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('#EXTINF:'):
            current_extinf = line
        elif (line.startswith('http://') or line.startswith('https://')) and current_extinf:
            stream_url = line
            
            # Extract channel display name
            title_match = re.search(r',(.+)$', current_extinf)
            channel_name = title_match.group(1).strip() if title_match else "Unknown Channel"
            
            # Extract group-title
            group_matches = list(re.finditer(r'group-title="([^"]+)"', current_extinf))
            group_title = group_matches[-1].group(1) if group_matches else "Uncategorized"
            
            # Extract tvg-logo
            logo_match = re.search(r'tvg-logo="([^"]+)"', current_extinf)
            logo_url = logo_match.group(1) if logo_match else ""

            # Determine Category
            category_id, category_name, _ = get_category_info(group_title, channel_name)

            # Generate base channel ID
            base_id = f"{category_id}-{re.sub(r'[^a-z0-9]+', '-', channel_name.lower()).strip('-')}"
            channel_id = base_id
            counter = 2
            while channel_id in seen_ids:
                channel_id = f"{base_id}-{counter}"
                counter += 1
            seen_ids.add(channel_id)

            channels.append({
                "id": channel_id,
                "name": channel_name,
                "logo": logo_url,
                "category": category_id,
                "category_name": category_name,
                "group_title": group_title,
                "stream_url": stream_url,
                "is_live": True,
                "is_trending": False,
                "country": "BD",
                "language": "bn",
                "quality": "HD",
                "headers": {},
                "sort_order": sort_counter
            })
            
            sort_counter += 1
            current_extinf = None

    return channels
