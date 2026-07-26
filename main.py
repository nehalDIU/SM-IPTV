import os
import sys
from dotenv import load_dotenv
from app.logger import logger
from app.sync import run_sync

def main():
    # Force UTF-8 output encoding for compatibility across all terminals
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    # Load environment variables
    load_dotenv()

    # Read configuration
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    default_m3u_url = "https://raw.githubusercontent.com/sm-monirulislam/SM-Live-TV/refs/heads/main/Combined_Live_TV.m3u"
    m3u_url = os.getenv("M3U_URL", default_m3u_url)

    # Validate required credentials
    has_errors = False
    if not supabase_url:
        logger.error("[error]Error: SUPABASE_URL environment variable is not set.[/error]")
        has_errors = True
    if not supabase_key:
        logger.error("[error]Error: SUPABASE_SERVICE_ROLE_KEY environment variable is not set.[/error]")
        has_errors = True
        
    if has_errors:
        logger.error("Please set the missing variables in environment or .env file.")
        sys.exit(1)

    logger.info("==================================================")
    logger.info("     Starting SM IPTV Supabase Sync Service      ")
    logger.info("==================================================")
    logger.info(f"M3U Source: [info]{m3u_url}[/info]")
    
    # Save hash file in project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    hash_filename = os.getenv("HASH_FILE", "last_hash.txt")
    hash_file_path = os.path.join(script_dir, hash_filename)

    # Execute synchronization
    success = run_sync(
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        m3u_url=m3u_url,
        hash_file_path=hash_file_path
    )

    if success:
        logger.info("SM IPTV Sync execution finished successfully.")
        sys.exit(0)
    else:
        logger.error("SM IPTV Sync execution failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
