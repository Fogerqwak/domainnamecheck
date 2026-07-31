import asyncio
import aiohttp

INPUT = "startup_names.txt"
OUTPUT = "available_ai.txt"

CONCURRENT = 30


async def check(session, name):
    url = f"https://rdap.nic.ai/domain/{name}.ai"

    try:
        async with session.get(url, timeout=10) as r:
            text = await r.text()

            if r.status == 404:
                return name

            if "Domain not found" in text:
                return name

    except:
        pass

    return None


async def main():
    names = [x.strip().lower() for x in open(INPUT)]

    connector = aiohttp.TCPConnector(limit=CONCURRENT)

    async with aiohttp.ClientSession(connector=connector) as session:

        tasks = [check(session, n) for n in names]

        results = await asyncio.gather(*tasks)

    results = [x for x in results if x]

    with open(OUTPUT, "w") as f:
        f.write("\n".join(results))

    print(len(results), "available .ai")


asyncio.run(main())
