#!/usr/bin/env python3
"""Run the Autonomous Scientific Research Platform.

Usage:
    python run.py [--host HOST] [--port PORT] [--reload] [--workers N]

Examples:
    python run.py                      # Run with defaults (localhost:8000)
    python run.py --port 8080          # Run on port 8080
    python run.py --reload             # Run with auto-reload for development
    python run.py --workers 4          # Run with 4 worker processes
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="Run the Autonomous Scientific Research Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                      Run with defaults (localhost:8000)
  python run.py --port 8080          Run on port 8080
  python run.py --host 0.0.0.0       Listen on all interfaces
  python run.py --reload             Enable auto-reload (development)
  python run.py --workers 4          Run with 4 worker processes
        """,
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes (development mode)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default="info",
        help="Logging level (default: info)",
    )

    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print("Error: uvicorn is not installed.")
        print("Install it with: pip install uvicorn[standard]")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║     Autonomous Scientific Research Platform                  ║
║                                                              ║
║     Starting server at http://{args.host}:{args.port:<5}                    ║
║                                                              ║
║     API Docs:   http://{args.host}:{args.port}/docs               ║
║     ReDoc:      http://{args.host}:{args.port}/redoc              ║
║     OpenAPI:    http://{args.host}:{args.port}/openapi.json       ║
╚══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "platform.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
