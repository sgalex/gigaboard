#!/usr/bin/env python
"""Development server runner for GigaBoard Backend"""
import os
import uvicorn

os.environ["PYTHONUNBUFFERED"] = "1"

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
