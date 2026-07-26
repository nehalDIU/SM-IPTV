import hashlib
import os

def calculate_sha256(content: str) -> str:
    """Calculates the SHA-256 hash of a string."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def get_last_hash(file_path: str) -> str:
    """Reads the last saved hash from a file, if it exists."""
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return ""

def save_last_hash(file_path: str, hash_value: str) -> None:
    """Saves the current hash value to a file."""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(hash_value)
