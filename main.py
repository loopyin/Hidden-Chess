import asyncio
import client
import logging
import os
import datetime

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging
log_filename = f"logs/game_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)

# Main application entry point
# Harmless change requested by user
if __name__ == '__main__':
    logging.info("Initializing Hidden Chess...")
    asyncio.run(client.game_loop())
