import httpx
import asyncio

async def test_stream():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            async with client.stream('GET', 'http://127.0.0.1:8000/stream') as response:
                print(f'Status: {response.status_code}')
                print(f'Headers: {dict(response.headers)}')
                print('\nStreaming chunks:')
                async for chunk in response.aiter_text():
                    print(repr(chunk), end='')
            print('\n\n✅ Stream completed successfully!')
        except Exception as e:
            print(f'❌ Error: {e}')

if __name__ == '__main__':
    asyncio.run(test_stream())
