"""
Initialize rate limiting database tables.

Run this script to create the usage_quota table.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine
from app.ratelimit.quota import UsageQuota

def init_ratelimit_tables():
    """Initialize rate limiting database tables."""
    print("Creating rate limiting tables...")
    
    try:
        UsageQuota.__table__.create(engine, checkfirst=True)
        print("✓ usage_quota table created successfully")
    except Exception as e:
        print(f"✗ Error creating tables: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = init_ratelimit_tables()
    sys.exit(0 if success else 1)
