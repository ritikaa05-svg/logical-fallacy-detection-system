import asyncio

import aiohttp

from backend.app.config import settings


async def test_api(model_id):
    print(f"\nTesting Model: {model_id}")
    token = settings.HUGGINGFACE_API_TOKEN
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"inputs": "The earth is flat. Why is this wrong?", "parameters": {"max_new_tokens": 20}}

    async with aiohttp.ClientSession() as session:
        api_url = f"https://api-inference.huggingface.co/models/{model_id}"
        async with session.post(api_url, json=payload, headers=headers) as response:
            print(f"Status: {response.status}")
            try:
                res = await response.json()
                print(f"Response: {res}")
            except:
                print(f"Text: {await response.text()}")


if __name__ == "__main__":
    models = [
        "meta-llama/Llama-3.2-3B-Instruct",
        "mistralai/Mistral-7B-Instruct-v0.3",
        "google/gemma-2b-it",
        "openai-community/gpt2",
    ]
    for m in models:
        asyncio.run(test_api(m))
