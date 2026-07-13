import json
import random
import time
from pathlib import Path

import requests


COMFY_URL = "http://127.0.0.1:8188"
WORKFLOW_PATH = Path("workflows/txt2img_basic_api.json")


def load_workflow() -> dict:
    if not WORKFLOW_PATH.exists():
        raise FileNotFoundError(f"找不到工作流：{WORKFLOW_PATH.resolve()}")

    with WORKFLOW_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def fill_workflow(workflow: dict) -> dict:
    # 正面提示詞
    workflow["11"]["inputs"]["text"] = (
        "a realistic photo of a young Chinese woman, "
        "Han Chinese facial features, three-quarter body shot, "
        "medium-long shot, from head to knees, natural standing pose, "
        "soft daylight, realistic skin texture, photorealistic"
    )

    # 負面提示詞
    workflow["10"]["inputs"]["text"] = (
        "close-up, extreme close-up, headshot, face-only shot, "
        "anime, cartoon, blurry, low quality, deformed face, "
        "extra arms, extra hands, bad anatomy"
    )

    # 解析度
    workflow["14"]["inputs"]["width"] = 576
    workflow["14"]["inputs"]["height"] = 1024
    workflow["14"]["inputs"]["batch_size"] = 1

    # 採樣設定
    workflow["13"]["inputs"]["seed"] = random.randint(1, 2**63 - 1)
    workflow["13"]["inputs"]["steps"] = 25
    workflow["13"]["inputs"]["cfg"] = 5
    workflow["13"]["inputs"]["sampler_name"] = "dpmpp_2m"
    workflow["13"]["inputs"]["scheduler"] = "karras"
    workflow["13"]["inputs"]["denoise"] = 1

    return workflow


def submit_workflow(workflow: dict) -> str:
    response = requests.post(
        f"{COMFY_URL}/prompt",
        json={"prompt": workflow},
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()

    if "prompt_id" not in data:
        raise RuntimeError(f"ComfyUI 拒絕工作流：{data}")

    return data["prompt_id"]


def wait_for_result(prompt_id: str, timeout_seconds: int = 1800) -> dict:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        response = requests.get(
            f"{COMFY_URL}/history/{prompt_id}",
            timeout=30,
        )
        response.raise_for_status()

        history = response.json()

        if prompt_id in history:
            return history[prompt_id]

        time.sleep(2)

    raise TimeoutError("生圖超過 30 分鐘仍未完成")


def print_output_files(history: dict) -> None:
    outputs = history.get("outputs", {})
    found = False

    for node_id, node_output in outputs.items():
        for image in node_output.get("images", []):
            found = True
            print(
                "生成完成：",
                f"節點={node_id}",
                f"檔名={image.get('filename')}",
                f"子資料夾={image.get('subfolder', '')}",
                f"類型={image.get('type', 'output')}",
            )

    if not found:
        print("工作已完成，但沒有找到圖片輸出：")
        print(json.dumps(history, ensure_ascii=False, indent=2))


def main() -> None:
    workflow = load_workflow()
    workflow = fill_workflow(workflow)

    print("正在送出工作流……")
    prompt_id = submit_workflow(workflow)
    print(f"已加入佇列，prompt_id：{prompt_id}")

    history = wait_for_result(prompt_id)
    print_output_files(history)


if __name__ == "__main__":
    main()