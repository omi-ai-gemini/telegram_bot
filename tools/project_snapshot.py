from pathlib import Path
import ast
import os


# =========================
# 專案快照工具
# 執行後會產生：
# 1. project_tree.txt
# 2. file_summary.txt
# 3. project_map.md
# =========================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = PROJECT_ROOT / "_snapshot"

IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "node_modules",
    "_snapshot",
}

IGNORE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".zip",
    ".rar",
    ".7z",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".mp4",
    ".mov",
    ".mp3",
    ".wav",
    ".ttf",
    ".otf",
}

SCAN_EXTENSIONS = {
    ".py",
    ".html",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".css",
    ".js",
}

MAX_PREVIEW_LINES = 80


# =========================
# 判斷是否忽略檔案 / 資料夾
# =========================
def should_ignore(path: Path) -> bool:

    parts = set(path.parts)

    if parts & IGNORE_DIRS:
        return True

    if path.suffix.lower() in IGNORE_EXTENSIONS:
        return True

    return False


# =========================
# 取得所有需要掃描的檔案
# =========================
def get_project_files():

    files = []

    for path in PROJECT_ROOT.rglob("*"):

        if should_ignore(path):
            continue

        if path.is_file() and path.suffix.lower() in SCAN_EXTENSIONS:
            files.append(path)

    return sorted(files)


# =========================
# 產生資料夾樹
# =========================
def generate_tree():

    lines = []

    for path in sorted(PROJECT_ROOT.rglob("*")):

        if should_ignore(path):
            continue

        relative = path.relative_to(PROJECT_ROOT)
        depth = len(relative.parts) - 1

        prefix = "  " * depth

        if path.is_dir():
            lines.append(f"{prefix}📁 {path.name}/")
        else:
            lines.append(f"{prefix}📄 {path.name}")

    return "\n".join(lines)


# =========================
# 分析 Python 檔案
# =========================
def analyze_python_file(path: Path):

    result = {
        "imports": [],
        "functions": [],
        "classes": [],
        "routes": [],
    }

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

    except Exception as e:
        return {
            "error": f"無法解析 Python：{e}"
        }

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                result["imports"].append(f"{module}.{alias.name}")

        elif isinstance(node, ast.FunctionDef):
            result["functions"].append(node.name)

            for decorator in node.decorator_list:
                route_text = extract_route_from_decorator(decorator)

                if route_text:
                    result["routes"].append({
                        "function": node.name,
                        "route": route_text
                    })

        elif isinstance(node, ast.ClassDef):
            result["classes"].append(node.name)

    return result


# =========================
# 從 Flask decorator 抓 route
# 例如：
# @app.route("/webhook/<bot_id>", methods=["POST"])
# @setting_bp.route("/setting/persona", methods=["GET"])
# =========================
def extract_route_from_decorator(decorator):

    if not isinstance(decorator, ast.Call):
        return None

    func = decorator.func

    if not isinstance(func, ast.Attribute):
        return None

    if func.attr != "route":
        return None

    if not decorator.args:
        return None

    first_arg = decorator.args[0]

    if isinstance(first_arg, ast.Constant):
        return first_arg.value

    return None


# =========================
# 產生單檔摘要
# =========================
def summarize_file(path: Path):

    relative = path.relative_to(PROJECT_ROOT)
    suffix = path.suffix.lower()

    lines = []
    lines.append(f"# {relative}")
    lines.append("")

    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        lines.append(f"讀取失敗：{e}")
        return "\n".join(lines)

    file_lines = content.splitlines()

    lines.append(f"- 類型：{suffix}")
    lines.append(f"- 行數：{len(file_lines)}")
    lines.append("")

    if suffix == ".py":

        analysis = analyze_python_file(path)

        if "error" in analysis:
            lines.append(f"- 解析錯誤：{analysis['error']}")
            lines.append("")
            return "\n".join(lines)

        if analysis["imports"]:
            lines.append("## imports")
            for item in sorted(set(analysis["imports"])):
                lines.append(f"- {item}")
            lines.append("")

        if analysis["classes"]:
            lines.append("## classes")
            for item in analysis["classes"]:
                lines.append(f"- {item}")
            lines.append("")

        if analysis["functions"]:
            lines.append("## functions")
            for item in analysis["functions"]:
                lines.append(f"- {item}")
            lines.append("")

        if analysis["routes"]:
            lines.append("## routes")
            for item in analysis["routes"]:
                lines.append(f"- {item['route']} → {item['function']}")
            lines.append("")

    lines.append("## preview")
    lines.append("```text")

    for line in file_lines[:MAX_PREVIEW_LINES]:
        lines.append(line)

    if len(file_lines) > MAX_PREVIEW_LINES:
        lines.append("...")
        lines.append(f"... 已省略 {len(file_lines) - MAX_PREVIEW_LINES} 行")

    lines.append("```")
    lines.append("")

    return "\n".join(lines)


# =========================
# 產生 project_map.md
# =========================
def generate_project_map(files):

    lines = []

    lines.append("# Project Map")
    lines.append("")
    lines.append("這份檔案由 `tools/project_snapshot.py` 自動產生。")
    lines.append("")
    lines.append("用途：讓 ChatGPT 快速理解目前專案架構，不用每次上傳所有單檔。")
    lines.append("")

    lines.append("## 專案根目錄")
    lines.append("")
    lines.append(f"```text\n{PROJECT_ROOT}\n```")
    lines.append("")

    lines.append("## 主要檔案列表")
    lines.append("")

    for path in files:
        relative = path.relative_to(PROJECT_ROOT)
        lines.append(f"- `{relative}`")

    lines.append("")

    lines.append("## Python 路由總覽")
    lines.append("")

    for path in files:

        if path.suffix.lower() != ".py":
            continue

        analysis = analyze_python_file(path)

        if "error" in analysis:
            continue

        if not analysis.get("routes"):
            continue

        relative = path.relative_to(PROJECT_ROOT)
        lines.append(f"### `{relative}`")

        for item in analysis["routes"]:
            lines.append(f"- `{item['route']}` → `{item['function']}`")

        lines.append("")

    lines.append("## Python 函式總覽")
    lines.append("")

    for path in files:

        if path.suffix.lower() != ".py":
            continue

        analysis = analyze_python_file(path)

        if "error" in analysis:
            continue

        relative = path.relative_to(PROJECT_ROOT)
        functions = analysis.get("functions", [])

        if not functions:
            continue

        lines.append(f"### `{relative}`")

        for func in functions:
            lines.append(f"- `{func}()`")

        lines.append("")

    return "\n".join(lines)


# =========================
# 主程式
# =========================
def main():

    print("=== Project Snapshot Start ===")
    print("PROJECT_ROOT:", PROJECT_ROOT)

    OUTPUT_DIR.mkdir(exist_ok=True)

    files = get_project_files()

    # =========================
    # 產生 project_tree.txt
    # =========================
    tree_text = generate_tree()
    tree_path = OUTPUT_DIR / "project_tree.txt"
    tree_path.write_text(tree_text, encoding="utf-8")

    # =========================
    # 產生 file_summary.txt
    # =========================
    summary_parts = []

    for path in files:
        summary_parts.append(summarize_file(path))
        summary_parts.append("\n" + "=" * 80 + "\n")

    summary_path = OUTPUT_DIR / "file_summary.txt"
    summary_path.write_text("\n".join(summary_parts), encoding="utf-8")

    # =========================
    # 產生 project_map.md
    # =========================
    project_map_text = generate_project_map(files)
    project_map_path = OUTPUT_DIR / "project_map.md"
    project_map_path.write_text(project_map_text, encoding="utf-8")

    print("已產生：")
    print(tree_path)
    print(summary_path)
    print(project_map_path)
    print("=== Project Snapshot Done ===")


if __name__ == "__main__":
    main()