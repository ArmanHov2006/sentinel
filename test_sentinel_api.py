"""Test script for Sentinel API endpoints."""
import httpx
import asyncio
import json
import sys

async def test_health():
    """Test the health endpoint."""
    print("=" * 60)
    print("Testing Health Endpoint")
    print("=" * 60)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get("http://127.0.0.1:8001/health")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
            if response.status_code == 200:
                data = response.json()
                assert data["status"] == "healthy"
                print("[PASS] Health endpoint works correctly!")
            else:
                print("[FAIL] Health endpoint returned non-200 status")
        except Exception as e:
            print(f"[FAIL] Error: {e}")
            return False
    return True

async def test_chat_completion_non_streaming():
    """Test non-streaming chat completion."""
    print("\n" + "=" * 60)
    print("Testing Chat Completion (Non-Streaming)")
    print("=" * 60)
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            payload = {
                "model": "gpt-4",
                "messages": [
                    {"role": "user", "content": "Hello, this is a test message"}
                ],
                "temperature": 0.7,
                "stream": False
            }
            response = await client.post(
                "http://127.0.0.1:8001/v1/chat/completions",
                json=payload
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Response ID: {data.get('id')}")
                print(f"Model: {data.get('model')}")
                print(f"Content: {data['choices'][0]['message']['content']}")
                print(f"Usage: {data['usage']}")
                assert data["object"] == "chat.completion"
                assert len(data["choices"]) > 0
                assert "You said:" in data["choices"][0]["message"]["content"]
                print("[PASS] Non-streaming chat completion works correctly!")
            else:
                print(f"[FAIL] Status {response.status_code}: {response.text}")
        except Exception as e:
            print(f"[FAIL] Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    return True

async def test_chat_completion_streaming():
    """Test streaming chat completion."""
    print("\n" + "=" * 60)
    print("Testing Chat Completion (Streaming)")
    print("=" * 60)
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            payload = {
                "model": "gpt-4",
                "messages": [
                    {"role": "user", "content": "Say hello"}
                ],
                "stream": True
            }
            print("Sending request...")
            async with client.stream(
                "POST",
                "http://127.0.0.1:8001/v1/chat/completions",
                json=payload
            ) as response:
                print(f"Status: {response.status_code}")
                print(f"Content-Type: {response.headers.get('content-type')}")
                print("\nStreaming chunks:")
                chunk_count = 0
                content_received = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        if data_str == "[DONE]":
                            print(f"\n[DONE] signal received")
                            break
                        try:
                            chunk_data = json.loads(data_str)
                            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                delta = chunk_data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    print(content, end="", flush=True)
                                    content_received += content
                                    chunk_count += 1
                        except json.JSONDecodeError:
                            pass
                
                print(f"\n\nTotal chunks received: {chunk_count}")
                print(f"Total content length: {len(content_received)}")
                if chunk_count > 0 and content_received:
                    print("[PASS] Streaming chat completion works correctly!")
                else:
                    print("[FAIL] No content received in stream")
        except Exception as e:
            print(f"[FAIL] Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    return True

async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("SENTINEL API TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Test 1: Health endpoint
    results.append(await test_health())
    
    # Test 2: Non-streaming chat completion
    results.append(await test_chat_completion_non_streaming())
    
    # Test 3: Streaming chat completion
    results.append(await test_chat_completion_streaming())
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    if passed == total:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
