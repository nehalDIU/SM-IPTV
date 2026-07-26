import time
import requests
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log
from app.logger import logger, console
from app.parser import parse_m3u_playlist
from app.importer import SupabaseImporter
from app.utils import calculate_sha256, get_last_hash, save_last_hash

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=16),
    before_sleep=before_sleep_log(logger, 20),
    reraise=True
)
def download_playlist(url: str) -> str:
    """
    Downloads M3U playlist content from the given URL.
    Retries up to 5 times on failure with exponential backoff.
    """
    logger.info(f"Downloading playlist from: [download]{url}[/download]...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IPTV"
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    content = response.text
    if not content:
        raise ValueError("Downloaded playlist content is empty.")
    
    logger.info(f"[success]Successfully downloaded playlist[/success] ({len(content.encode('utf-8'))} bytes).")
    return content

def run_sync(
    supabase_url: str,
    supabase_key: str,
    m3u_url: str,
    hash_file_path: str = "last_hash.txt"
) -> bool:
    """
    Orchestrates downloading M3U, parsing, category setup, and syncing to Supabase.
    """
    start_time = time.time()
    
    try:
        # Step 1: Download M3U playlist
        try:
            m3u_content = download_playlist(m3u_url)
        except Exception as e:
            logger.error(f"[error]Failed to download M3U playlist:[/error] {e}")
            return False

        # Step 2: Hash Check
        current_hash = calculate_sha256(m3u_content)
        last_hash = get_last_hash(hash_file_path)
        
        logger.info(f"Current Playlist SHA256: [info]{current_hash[:8]}...[/info]")
        if last_hash:
            logger.info(f"Last Playlist SHA256:    [info]{last_hash[:8]}...[/info]")
        
        if last_hash == current_hash:
            logger.info("[success]Playlist hash is unchanged. Database is already in sync. Exiting early.[/success]")
            duration = time.time() - start_time
            logger.info(f"Sync duration: {duration:.2f} seconds.")
            return True

        # Step 3: Parse Channels
        try:
            channels = parse_m3u_playlist(m3u_content)
        except Exception as e:
            logger.error(f"[error]Failed to parse M3U playlist:[/error] {e}")
            return False
            
        if not channels:
            logger.warning("[warning]Parsed playlist did not yield any valid channels. Aborting sync.[/warning]")
            return False

        logger.info(f"[success]Parsed {len(channels)} channels from M3U playlist.[/success]")

        # Step 4: Supabase Category Verification & Channel Sync
        try:
            importer = SupabaseImporter(supabase_url=supabase_url, supabase_key=supabase_key)
            
            # Step 4a: Verify/Create missing categories
            importer.ensure_categories_exist(channels)
            
            # Step 4b: Compare and Sync channels
            inserted, updated, deleted = importer.sync_channels(channels)
            
        except Exception as e:
            logger.error(f"[error]Supabase Database Sync Error:[/error] {e}", exc_info=True)
            return False

        # Step 5: Save new hash
        save_last_hash(hash_file_path, current_hash)

        # Step 6: Log summary
        duration = time.time() - start_time
        logger.info("")
        console.print("[success]==================================================[/success]")
        console.print(f"[success]  SM IPTV Sync Completed Successfully!  [/success]")
        console.print(f"  - Total Parsed Channels: [bold cyan]{len(channels)}[/bold cyan]")
        console.print(f"  - Inserted: [bold green]{inserted}[/bold green]")
        console.print(f"  - Updated:  [bold yellow]{updated}[/bold yellow]")
        console.print(f"  - Deleted:  [bold red]{deleted}[/bold red]")
        console.print(f"  - Duration: [bold cyan]{duration:.2f} seconds[/bold cyan]")
        console.print("[success]==================================================[/success]")
        
        return True

    except Exception as e:
        logger.error(f"[error]An unexpected error occurred in sync service:[/error] {e}", exc_info=True)
        return False
