import asyncio

bouncer = asyncio.Semaphore(2)

async def one_call(n):
    async with bouncer:
        print(f'call {n} started')
        await asyncio.sleep(1)
        return f'call {n} done'


async def main():
    results = await asyncio.gather(*[one_call(i) for i in range(50)])
    print(results)

if __name__ == '__main__':
    asyncio.run(main())
