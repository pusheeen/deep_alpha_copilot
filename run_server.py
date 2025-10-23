#!/usr/bin/env python
"""Simple script to run the FastAPI server"""
import uvicorn

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 Starting deepAlpha Copilot Server")
    print("="*60)
    print(f"\n📊 Access the UI at: http://localhost:8000")
    print(f"📚 API docs at: http://localhost:8000/docs")
    print("\nPress CTRL+C to stop the server\n")
    print("="*60 + "\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

