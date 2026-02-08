# main_api.py
import os
import sys
import webbrowser
import threading
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
import json
from typing import List, Dict

# ========================
# FastAPI 应用定义
# ========================
app = FastAPI(title="Conda 环境管理 API", version="1.0")

# 全局日志存储
log_messages = []

def log(msg: str, error: bool = False):
    level = "ERROR" if error else "INFO"
    entry = f"[{level}] {msg}"
    log_messages.append(entry)
    print(entry)

def run_conda_cmd(args: List[str]) -> str:
    try:
        result = subprocess.run(
            ["conda"] + args,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=True,
            timeout=120
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        raise Exception("命令超时（>120秒）")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else ""
        stdout = e.stdout.strip() if e.stdout else ""
        raise Exception(f"Conda 失败: {stderr or stdout}")
    except FileNotFoundError:
        raise Exception("未找到 conda 命令，请确保已安装并加入 PATH")

def get_python_version_from_env(path: str) -> str:
    python_exe = os.path.join(path, "python.exe") if os.name == 'nt' else os.path.join(path, "bin", "python")
    if not os.path.exists(python_exe):
        return "无 Python"
    try:
        result = subprocess.run([python_exe, "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.startswith("Python "):
            return result.stdout.strip()[7:].split()[0]
    except:
        pass
    return "未知"

@app.get("/envs", response_model=List[Dict[str, str]])
async def list_envs():
    """列出所有非 base 环境及其 Python 版本"""
    try:
        output = run_conda_cmd(["env", "list", "--json"])
        output = output.strip()
        if output.startswith('\ufeff'):
            output = output[1:]
        if '}' in output:
            last_brace = output.rfind('}')
            output = output[:last_brace + 1]
        data = json.loads(output)
        env_paths = data.get("envs", [])

        base_path = None
        for path in env_paths:
            if "/envs/" not in path.replace("\\", "/"):
                base_path = path
                break
        if not base_path and env_paths:
            base_path = env_paths[0]

        envs = []
        for path in env_paths:
            if path == base_path:
                continue
            name = path.split("\\")[-1] if "\\" in path else path.split("/")[-1]
            version = get_python_version_from_env(path)
            envs.append({"name": name, "path": path, "python_version": version})
        return envs
    except Exception as e:
        log(str(e), error=True)
        raise HTTPException(status_code=500, detail=str(e))

class CreateEnvRequest(BaseModel):
    name: str
    python_version: str = "3.12"

def create_env_background(name: str, python_version: str):
    try:
        log(f"开始创建环境: {name} (Python {python_version})")
        run_conda_cmd(["create", "--name", name, f"python={python_version}", "--yes"])
        log(f"✅ 环境 '{name}' 创建成功")
    except Exception as e:
        log(f"❌ 创建失败: {str(e)}", error=True)

@app.post("/envs")
async def create_env(req: CreateEnvRequest, background_tasks: BackgroundTasks):
    try:
        envs = await list_envs()
        if any(env["name"] == req.name for env in envs):
            raise HTTPException(status_code=400, detail=f"环境 '{req.name}' 已存在")
        background_tasks.add_task(create_env_background, req.name, req.python_version)
        return {"message": f"正在后台创建环境: {req.name}"}
    except Exception as e:
        log(str(e), error=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/envs/{name}")
async def delete_env(name: str):
    try:
        log(f"正在删除环境: {name}")
        run_conda_cmd(["env", "remove", "--name", name, "--yes"])
        log(f"✅ 环境 '{name}' 删除成功")
        return {"message": f"环境 '{name}' 已删除"}
    except Exception as e:
        log(str(e), error=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs")
async def get_logs():
    return {"logs": log_messages[-100:]}

# ========================
# 静态文件与首页
# ========================
# 创建 static 目录和 index.html（如果不存在）
STATIC_DIR = "static"
INDEX_FILE = os.path.join(STATIC_DIR, "index.html")

os.makedirs(STATIC_DIR, exist_ok=True)

if not os.path.exists(INDEX_FILE):
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Conda 环境管理</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        button { margin: 5px; padding: 8px 16px; }
        pre { background: #f5f5f5; padding: 10px; border-radius: 4px; }
    </style>
</head>
<body>
    <h2>📦 Conda 环境管理（Web 版）</h2>
    <p>请使用 <a href="/docs">Swagger UI</a> 进行操作，或自行开发前端。</p>
    <h3>已有环境：</h3>
    <button onclick="loadEnvs()">🔄 刷新列表</button>
    <pre id="envList">点击“刷新列表”加载...</pre>

    <script>
        async function loadEnvs() {
            const res = await fetch('/envs');
            const envs = await res.json();
            const text = envs.map(e => `${e.name} (Python ${e.python_version})`).join('\\n');
            document.getElementById('envList').textContent = text || '暂无环境';
        }
    </script>
</body>
</html>
        """)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def index():
    return FileResponse(INDEX_FILE)


# ========================
# 自动启动服务器（双击运行）
# ========================
if __name__ == "__main__":
    # 检查依赖是否安装
    try:
        import uvicorn
    except ImportError:
        print("❌ 未安装 uvicorn 或 fastapi")
        print("请在终端运行以下命令安装：")
        print("pip install fastapi uvicorn")
        input("\n按回车键退出...")
        sys.exit(1)

    HOST = "127.0.0.1"
    PORT = 8000
    URL = f"http://{HOST}:{PORT}"

    def open_browser():
        webbrowser.open(URL)

    print(f"🚀 正在启动 Conda 环境管理 Web 服务...")
    print(f"🌐 访问地址: {URL}")
    print(f"📄 Swagger 文档: {URL}/docs")
    print("（如果浏览器未自动打开，请手动访问上述地址）")

    # 启动浏览器（延迟1秒确保服务已启动）
    threading.Timer(1.0, open_browser).start()

    # 启动 FastAPI 服务
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")