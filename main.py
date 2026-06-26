import asyncio
import client
import traceback
from debugger import debugger

if __name__ == '__main__':
    print("Initializing Hidden Chess...")
    try:
        asyncio.run(client.game_loop())
    except Exception as e:
        print("Fatal error occurred, saving crash dump...")
        debugger.log_exception(e, "fatal_crash")
        debugger.export()
        traceback.print_exc()
