# backend/app/ai/rag/utils.py
import re
from datetime import datetime
from typing import Optional

def normalize_clinical_date(raw_date: Optional[str]) -> Optional[str]:
    """
    Normalizes varied clinical date formats into standard ISO YYYY-MM-DD for PostgreSQL DATE.
    Returns None if unparseable, empty, or an unknown placeholder (e.g., 'Unknown Date', 'N/A').
    
    Supports common Indian clinical date formats:
    - 26/01/2024, 26-01-2024, 26.01.2024
    - 2024-01-26, 2024/01/26
    - 26 Jan 2024, 26-Jan-2024, 26 January 2024
    - 26/01/24, 26-01-24
    """
    if not raw_date or not isinstance(raw_date, str):
        return None

    cleaned = raw_date.strip()
    if cleaned.lower() in ("unknown", "unknown date", "n/a", "na", "none", "null", ""):
        return None

    # Strip any trailing time or timestamps if present (e.g., "2024-01-26T10:00:00")
    if "t" in cleaned.lower():
        cleaned = re.split(r"[tT\s]", cleaned)[0].strip()

    # List of common format patterns to check
    patterns = [
        "%Y-%m-%d",      # 2024-01-26 (ISO)
        "%d/%m/%Y",      # 26/01/2024
        "%d-%m-%Y",      # 26-01-2024
        "%d.%m.%Y",      # 26.01.2024
        "%Y/%m/%d",      # 2024/01/26
        "%d %b %Y",      # 26 Jan 2024
        "%d-%b-%Y",      # 26-Jan-2024
        "%d %B %Y",      # 26 January 2024
        "%d-%B-%Y",      # 26-January-2024
        "%b %d, %Y",     # Jan 26, 2024
        "%B %d, %Y",     # January 26, 2024
        "%d/%m/%y",      # 26/01/24
        "%d-%m-%y",      # 26-01-24
        "%d.%m.%y",      # 26.01.24
    ]

    for fmt in patterns:
        try:
            parsed = datetime.strptime(cleaned, fmt)
            # Basic sanity check on clinical years (e.g. between 1900 and 2100)
            if 1900 <= parsed.year <= 2100:
                return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Fallback to python-dateutil if installed
    try:
        from dateutil import parser
        parsed = parser.parse(cleaned, dayfirst=True)
        if 1900 <= parsed.year <= 2100:
            return parsed.strftime("%Y-%m-%d")
    except Exception:
        pass

    return None
