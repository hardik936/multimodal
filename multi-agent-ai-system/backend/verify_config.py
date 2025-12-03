"""
Verification script to check if API keys are properly configured.
"""
import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings

def verify_configuration():
    """Verify that all required API keys and settings are configured."""
    
    print("=" * 60)
    print("Configuration Verification")
    print("=" * 60)
    
    issues = []
    warnings = []
    
    # Check GROQ API Key (required for the multi-agent system)
    print("\n1. GROQ API Configuration:")
    if settings.GROQ_API_KEY:
        print(f"   [OK] GROQ_API_KEY is set (length: {len(settings.GROQ_API_KEY)})")
        print(f"   [OK] GROQ_MODEL: {settings.GROQ_MODEL}")
        print(f"   [OK] GROQ_RATE_LIMIT: {settings.GROQ_RATE_LIMIT} req/min")
    else:
        print("   [FAIL] GROQ_API_KEY is NOT set")
        issues.append("GROQ_API_KEY is required for the multi-agent system to work")
    
    # Check OpenAI API Key (optional fallback)
    print("\n2. OpenAI API Configuration (Optional):")
    if settings.OPENAI_API_KEY:
        print(f"   [OK] OPENAI_API_KEY is set (length: {len(settings.OPENAI_API_KEY)})")
    else:
        print("   [WARN] OPENAI_API_KEY is not set (this is optional)")
        warnings.append("OPENAI_API_KEY is not set - this is optional but may be needed for fallback")
    
    # Check Database
    print("\n3. Database Configuration:")
    print(f"   [OK] DATABASE_URL: {settings.DATABASE_URL}")
    
    # Check JWT Secret
    print("\n4. JWT Authentication:")
    if settings.SECRET_KEY:
        print(f"   [OK] SECRET_KEY is set (length: {len(settings.SECRET_KEY)})")
    else:
        print("   [FAIL] SECRET_KEY is NOT set")
        issues.append("SECRET_KEY is required for JWT authentication")
    
    # Check other settings
    print("\n5. Other Settings:")
    print(f"   [OK] ENVIRONMENT: {settings.ENVIRONMENT}")
    print(f"   [OK] DEBUG: {settings.DEBUG}")
    print(f"   [OK] UPLOAD_DIR: {settings.UPLOAD_DIR}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if issues:
        print(f"\n[ERROR] Found {len(issues)} critical issue(s):")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
    
    if warnings:
        print(f"\n[WARNING] Found {len(warnings)} warning(s):")
        for i, warning in enumerate(warnings, 1):
            print(f"   {i}. {warning}")
    
    if not issues and not warnings:
        print("\n[SUCCESS] All configurations are properly set!")
    elif not issues:
        print("\n[SUCCESS] All critical configurations are set (warnings can be ignored)")
    
    print("\n" + "=" * 60)
    
    if issues:
        print("\nTo fix the issues, add the following to your .env file:")
        print("   (located at: backend/.env)")
        print()
        if "GROQ_API_KEY" in str(issues):
            print("   GROQ_API_KEY=your_groq_api_key_here")
        if "SECRET_KEY" in str(issues):
            print("   SECRET_KEY=your_secret_key_here")
        print()
        return False
    
    return True

if __name__ == "__main__":
    success = verify_configuration()
    sys.exit(0 if success else 1)
