import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = "ajev16nienaudlc5sg4t"  # это твой folder_id из консоли Yandex Cloud

url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

headers = {
    "Authorization": f"Api-Key {API_KEY}",
    "Content-Type": "application/json"
}

prompt = "Оцени, сколько примерно времени займет решение проблемы 'сломана скамейка у подъезда' в часах."

data = {
    "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
    "completionOptions": {
        "stream": False,
        "temperature": 0.3,
        "maxTokens": 100
    },
    "messages": [
        {"role": "user", "text": prompt}
    ]
}

response = requests.post(url, headers=headers, json=data)
result = response.json()

print(result["result"]["alternatives"][0]["message"]["text"])
