from asyncio import run
from .haproxy_collector import main

if __name__ == "__main__":
    run(main())
