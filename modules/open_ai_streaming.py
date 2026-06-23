import asyncio
import os

import httpx

OPENAI_KEY = os.environ.get('OPENAI_API_KEY')   # your key, read from the environment (Day 09)
OPENAI_URL = 'https://api.openai.com/v1/chat/completions'

async def stream_ai_reply(question):
    headers = {'Authorization': f'Bearer {OPENAI_KEY}'}   # the auth header from Day 09
    body = {
        'model': 'gpt-4o-mini',
        'messages': [{'role': 'user', 'content': question}],
        'stream': True,                  # ask OpenAI to send the answer piece by piece
    }
    #   timeout=30.0  ->  AI replies are slow, so allow up to 30 seconds (same as Day 09)
    async with httpx.AsyncClient(timeout=30.0) as client:
        # client.stream('POST', ...) keeps the connection open so we can read pieces as they arrive.
        async with client.stream('POST', OPENAI_URL, headers=headers, json=body) as resp:
            # 'async for' is the async cousin of a normal 'for' - it hands us each line the MOMENT
            # it arrives over the network, instead of waiting for the whole reply.
            async for line in resp.aiter_lines():
                if not line.startswith('data: '):
                    continue # skip lines that aren't data
                #print(line)
                chunk = line[len('data: '):]          # remove the 'data: ' prefix
                if chunk == '[DONE]':                 # OpenAI sends this to mean 'finished'
                    break
                import json as _json
                # dig out the little piece of text this chunk carries (may be empty on some chunks)
                delta = _json.loads(chunk)['choices'][0]['delta']
                if 'content' in delta:
                    print(delta['content'], end='', flush=True)   # end='' so the words join up live
                    asyncio.sleep(0.5)
    print('\n(done)')

async def start():
    if OPENAI_KEY:
        await stream_ai_reply('List 3 quick benefits of a standing desk.')
    else:
        print('(skipped - no OPENAI_API_KEY set)')

asyncio.run(start())
