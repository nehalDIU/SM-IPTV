import os
from typing import List, Dict, Any, Tuple
from supabase import create_client, Client, ClientOptions
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from app.logger import logger
from app.parser import CATEGORY_MAP

class SupabaseImporter:
    def __init__(self, supabase_url: str, supabase_key: str, admin_secret_token: str = None):
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be provided.")
        
        token = (admin_secret_token or os.getenv("ADMIN_SECRET_TOKEN") or "").strip() or "GoLiveAdminSecret2026"
        headers = {"x-admin-token": token}

        options = ClientOptions(headers=headers)
        self.client: Client = create_client(supabase_url, supabase_key, options=options)
        
        # Explicitly update headers on Postgrest client to guarantee x-admin-token is sent in all table queries
        self.client.postgrest.headers.update(headers)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        before_sleep=before_sleep_log(logger, 20),
        reraise=True
    )
    def ensure_categories_exist(self, channels: List[Dict[str, Any]]) -> None:
        """
        Ensures all referenced categories exist and are set active in the 'categories' table.
        """
        needed_categories: Dict[str, Dict[str, Any]] = {}

        # Add predefined categories
        for _, info in CATEGORY_MAP.items():
            needed_categories[info["id"]] = {
                "id": info["id"],
                "name": info["name"],
                "sort_order": info["sort_order"],
                "active": True
            }

        # Add any dynamic categories from parsed channels
        for channel in channels:
            cat_id = channel["category"]
            cat_name = channel.get("category_name", cat_id.capitalize())
            if cat_id not in needed_categories:
                needed_categories[cat_id] = {
                    "id": cat_id,
                    "name": cat_name,
                    "sort_order": 50,
                    "active": True
                }

        # Query existing categories from Supabase
        response = self.client.table("categories").select("id, name, active").execute()
        existing_cats = {cat["id"]: cat for cat in (response.data or [])}

        for cat_id, cat_data in needed_categories.items():
            if cat_id not in existing_cats:
                logger.info(f"Creating missing category in DB: [sync]{cat_data['name']}[/sync] (ID: {cat_id})")
                self.client.table("categories").insert({
                    "id": cat_id,
                    "name": cat_data["name"],
                    "sort_order": cat_data["sort_order"],
                    "active": True
                }).execute()
            else:
                if not existing_cats[cat_id].get("active"):
                    logger.info(f"Activating category in DB: [sync]{cat_data['name']}[/sync]")
                    self.client.table("categories").update({"active": True}).eq("id", cat_id).execute()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        before_sleep=before_sleep_log(logger, 20),
        reraise=True
    )
    def sync_channels(self, channels: List[Dict[str, Any]]) -> Tuple[int, int, int]:
        """
        Syncs channels per category. Returns (total_inserted, total_updated, total_deleted).
        """
        if not channels:
            logger.warning("No channels provided to sync.")
            return 0, 0, 0

        channels_by_category: Dict[str, List[Dict[str, Any]]] = {}
        for ch in channels:
            cat_id = ch["category"]
            if cat_id not in channels_by_category:
                channels_by_category[cat_id] = []
            channels_by_category[cat_id].append(ch)

        total_inserted = 0
        total_updated = 0
        total_deleted = 0

        for cat_id, cat_channels in channels_by_category.items():
            logger.info(f"Syncing [sync]{len(cat_channels)}[/sync] channels for category [sync]{cat_id}[/sync]...")

            response = self.client.table("channels").select("*").eq("category", cat_id).execute()
            existing_channels = response.data or []
            existing_dict = {c["id"]: c for c in existing_channels}

            to_insert = []
            to_update = []
            incoming_ids = set()

            for ch in cat_channels:
                ch_id = ch["id"]
                incoming_ids.add(ch_id)

                db_payload = {
                    "id": ch_id,
                    "name": ch["name"],
                    "logo": ch["logo"],
                    "category": ch["category"],
                    "country": ch["country"],
                    "language": ch["language"],
                    "is_live": ch["is_live"],
                    "is_trending": ch["is_trending"],
                    "quality": ch["quality"],
                    "stream_url": ch["stream_url"],
                    "headers": ch["headers"],
                    "sort_order": ch["sort_order"]
                }

                if ch_id not in existing_dict:
                    to_insert.append(db_payload)
                else:
                    existing = existing_dict[ch_id]
                    if (existing.get("stream_url") != db_payload["stream_url"] or
                        existing.get("logo") != db_payload["logo"] or
                        existing.get("name") != db_payload["name"]):
                        to_update.append(db_payload)

            to_delete_ids = [ch_id for ch_id in existing_dict if ch_id not in incoming_ids]

            if to_insert:
                logger.info(f"  Inserting {len(to_insert)} new channels in '{cat_id}'...")
                for i in range(0, len(to_insert), 50):
                    self.client.table("channels").insert(to_insert[i:i+50]).execute()
                total_inserted += len(to_insert)

            if to_update:
                logger.info(f"  Updating {len(to_update)} existing channels in '{cat_id}'...")
                for item in to_update:
                    self.client.table("channels").update(item).eq("id", item["id"]).execute()
                total_updated += len(to_update)

            if to_delete_ids:
                logger.info(f"  Deleting {len(to_delete_ids)} stale channels in '{cat_id}'...")
                for i in range(0, len(to_delete_ids), 50):
                    self.client.table("channels").delete().in_("id", to_delete_ids[i:i+50]).execute()
                total_deleted += len(to_delete_ids)

        return total_inserted, total_updated, total_deleted
