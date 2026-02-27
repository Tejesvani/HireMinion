import sys
import os
import signal
import asyncio

# Add backend directory to path so email_reach package is found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_reach.scrape_emails import run as scrape_run
from email_reach.send_email import run as send_run


# Handle Ctrl+C gracefully
def signal_handler(sig, frame):
    print("\n\n⛔ Interrupted by user. Exiting...")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)


def main():
    mode = "--part"

    if len(sys.argv) > 1:
        mode = sys.argv[1]

    if mode == "--full":
        print("\n🚀 Running FULL mode (scrape + send)\n")
        asyncio.run(scrape_run())
        send_run()

    elif mode == "--part":
        print("\n🚀 Running PART mode (scrape only)\n")
        asyncio.run(scrape_run())

    else:
        print(f"❌ Unknown flag: {mode}")
        print("Usage: python backend/email_orchestrator.py --full | --part")


if __name__ == "__main__":
    main()