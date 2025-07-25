import requests
import json
import re
import time
from chatbridge.chatbridge import *
from camoufox.async_api import AsyncCamoufox
from fastapi import FastAPI
import uvicorn
import asyncio
import httpx

token_list = []


async def get_token():
    async with AsyncCamoufox(os="linux", headless=True) as browser:
        url_with_slash = "https://sophnet.com/#/playground/chat?model=DeepSeek-R1-0528"
        page = await browser.new_page()
        await page.goto(url_with_slash, timeout=60000)
        cookies = await page.context.cookies()
        token = ""
        for cookie in cookies:
            if cookie.get("name") == "anonymous-token":
                token = cookie.get("value", "")
                break

        if token:
            # 清理 token 字符串
            cleaned_token = re.sub(r'{"anonymousToken:([^}]+)}', r"\1", token)
            cleaned_token = re.sub(r"%22", '"', cleaned_token).replace("%2C", ",")
            token = json.loads(cleaned_token).get("anonymousToken", "")
            print(f"Token: {token}")
            await page.get_by_placeholder("请输入内容").fill("i am liu")
            button = page.locator(
                "button.me-1.mb-px.flex.h-8.w-8.items-center.justify-center"
            )
            await button.click()
            await asyncio.sleep(2)
            return token
        else:
            print("Anonymous token not found.")


app = FastAPI(title="sophnet2api")


@app.get("/v1/models")
@async_get_model_list
async def get_models():
    global token_list
    if len(token_list) == 0:
        token_list.append(await get_token())
    token = token_list[0]
    url = "https://sophnet.com/api/public/playground/models?projectUuid=Ar79PWUQUAhjJOja2orHs"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "sec-ch-ua-platform": '"Windows"',
        "authorization": f"Bearer anon-{token}",
    }
    try:
        # 使用 httpx 异步请求
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)

        model_list = []
        model_lists = response.json().get("result", [])
        for model in model_lists:
            model_name = model.get("displayName", "")
            model_list.append((model_name, "DeepSeek"))
        print(f"Model List: {model_list}")
        return model_list
    except Exception as e:
        print(f"An error occurred: {e}")
        token_list.clear()
        return {"error": str(e)}


@app.post("/v1/chat/completions")
@async_chatCompletions(1)
async def chat(prompt: str, res: ChatResponse, new_session: bool):
    global token_list
    print(prompt, res.model, new_session, res)
    if len(token_list) == 0:
        token_list.append(await get_token())
    token = token_list[0]
    url = f"https://sophnet.com/api/open-apis/projects/Ar79PWUQUAhjJOja2orHs/chat/completions"

    payload = {
        "temperature": 1,
        "top_p": 1,
        "frequency_penalty": res.frequency_penalty,
        "presence_penalty": res.presence_penalty,
        "max_tokens": res.max_tokens,
        "webSearchEnable": False,
        "stop": [],
        "stream": "True",
        "model_id": res.model,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": f"{prompt}"}]}
        ],
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
        "Accept": "text/event-stream, text/event-stream",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Content-Type": "application/json",
        "accept-language": "en-US,en;q=0.5",
        "authorization": f"Bearer anon-{token}",
    }
    try:
        response = requests.post(
            url, data=json.dumps(payload), headers=headers, stream=True
        )
        content = ""
        response.raise_for_status()  # Check for HTTP errors
        for line in response.iter_lines():
            # print(line)
            if b"[DONE]" in line:
                print("Stream ended.")
                break
            # content +=
            line = line.decode().replace("data: ", "")
            if line.strip() and not line.startswith("[DONE]"):
                try:
                    data = json.loads(line)
                    if "choices" in data and len(data["choices"]) > 0:
                        content += data["choices"][0]["delta"].get("content", "")
                except json.JSONDecodeError:
                    print(f"Error decoding JSON: {line}")
        print(f"Response content: {content}")
        return content
    except Exception as e:
        token_list.clear()
        return {"error": str(e)}


def main():
    uvicorn.run("sophnet2api:app", host="0.0.0.0", port=10007, reload=True)


if __name__ == "__main__":
    main()
