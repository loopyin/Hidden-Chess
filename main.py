import asyncio
import client

# Main application entry point
if __name__ == '__main__':
    print("Initializing Hidden Chess...")
    asyncio.run(client.game_loop())
