import os
import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("🔍 DEBUG ENVIRONMENT")
    print(f"PORT = {os.environ.get('PORT', 'NOT SET')}")
    print("=" * 50)
    
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting on port {port}")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
