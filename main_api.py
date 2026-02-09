# main_api.py
import os
import sys
import webbrowser
import threading
import re
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
import json
from typing import List, Dict

# ========================
# 全局配置
# ========================
app = FastAPI(title="Conda 环境管理 API", version="1.0")
log_messages = []


# 自动定位 conda 路径
def get_conda_exe_path():
    python_exe = Path(sys.executable)
    # Windows
    if sys.platform == "win32":
        if "envs" not in str(python_exe.parent):
            conda_exe = python_exe.parent / "Scripts" / "conda.exe"
        else:
            conda_root = python_exe.parent.parent.parent
            conda_exe = conda_root / "Scripts" / "conda.exe"
        if conda_exe.exists():
            return str(conda_exe)
    # macOS/Linux
    else:
        if "envs" not in str(python_exe.parent):
            conda_exe = python_exe.parent / "bin" / "conda"
        else:
            conda_root = python_exe.parent.parent.parent
            conda_exe = conda_root / "bin" / "conda"
        if conda_exe.exists():
            return str(conda_exe)
    return "conda"


CONDA_EXE = get_conda_exe_path()


# ========================
# 通用工具函数
# ========================
def log(msg: str, error: bool = False):
    level = "ERROR" if error else "INFO"
    entry = f"[{level}] {msg}"
    log_messages.append(entry)
    print(entry)


def run_conda_cmd(args: List[str]) -> str:
    """统一执行 conda 命令"""
    try:
        result = subprocess.run(
            [CONDA_EXE] + args,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=True,
            timeout=120
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        raise Exception("命令执行超时（超过 120 秒）")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else ""
        stdout = e.stdout.strip() if e.stdout else ""
        raise Exception(f"Conda 命令失败: {stderr or stdout}")
    except FileNotFoundError:
        raise Exception("未找到 conda 命令，请确保 Anaconda 已正确安装并加入 PATH")


def get_python_version_from_env(path: str) -> str:
    """获取环境的 Python 版本"""
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


def is_valid_env_name(name: str) -> bool:
    """验证环境名合法性"""
    if not name or name.startswith('.'):
        return False
    return re.fullmatch(r'[a-zA-Z0-9._-]+', name) is not None


def list_all_envs() -> List[Dict[str, str]]:
    """获取所有非 base 环境"""
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


# ========================
# API 接口定义
# ========================
@app.get("/envs", response_model=List[Dict[str, str]])
async def list_envs():
    """列出所有非 base 环境及其 Python 版本"""
    try:
        envs = list_all_envs()
        return envs
    except Exception as e:
        log(str(e), error=True)
        raise HTTPException(status_code=500, detail=str(e))


# 1. 创建环境
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
        # 验证环境名
        if not is_valid_env_name(req.name):
            raise HTTPException(status_code=400, detail="环境名只能包含字母、数字、下划线、连字符或点（不能以点开头）")

        # 检查环境是否已存在
        envs = list_all_envs()
        if any(env["name"] == req.name for env in envs):
            raise HTTPException(status_code=400, detail=f"环境 '{req.name}' 已存在")

        background_tasks.add_task(create_env_background, req.name, req.python_version)
        return {"message": f"正在后台创建环境: {req.name}"}
    except HTTPException:
        raise
    except Exception as e:
        log(str(e), error=True)
        raise HTTPException(status_code=500, detail=str(e))


# 2. 删除环境
@app.delete("/envs/{name}")
async def delete_env(name: str):
    try:
        # 验证环境存在
        envs = list_all_envs()
        if not any(env["name"] == name for env in envs):
            raise HTTPException(status_code=400, detail=f"环境 '{name}' 不存在")

        log(f"正在删除环境: {name}")
        run_conda_cmd(["env", "remove", "--name", name, "--yes"])
        log(f"✅ 环境 '{name}' 删除成功")
        return {"message": f"环境 '{name}' 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        log(str(e), error=True)
        raise HTTPException(status_code=500, detail=str(e))


# 3. 克隆环境
class CloneEnvRequest(BaseModel):
    source_env: str
    new_env: str


def clone_env_background(source_env: str, new_env: str):
    try:
        log(f"开始克隆环境: {source_env} → {new_env}")
        run_conda_cmd(["create", "--name", new_env, "--clone", source_env, "--yes"])
        log(f"✅ 环境克隆成功: {source_env} → {new_env}")
    except Exception as e:
        log(f"❌ 克隆失败: {str(e)}", error=True)


@app.post("/envs/clone")
async def clone_env(req: CloneEnvRequest, background_tasks: BackgroundTasks):
    try:
        # 验证源环境存在
        envs = list_all_envs()
        env_names = [env["name"] for env in envs]
        if req.source_env not in env_names:
            raise HTTPException(status_code=400, detail=f"源环境 '{req.source_env}' 不存在")

        # 验证新环境名
        if not is_valid_env_name(req.new_env):
            raise HTTPException(status_code=400, detail="新环境名只能包含字母、数字、下划线、连字符或点（不能以点开头）")

        # 验证新环境未存在
        if req.new_env in env_names:
            raise HTTPException(status_code=400, detail=f"新环境 '{req.new_env}' 已存在")

        background_tasks.add_task(clone_env_background, req.source_env, req.new_env)
        return {"message": f"正在后台克隆环境: {req.source_env} → {req.new_env}"}
    except HTTPException:
        raise
    except Exception as e:
        log(str(e), error=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs")
async def get_logs():
    """获取最新 100 条日志"""
    return {"logs": log_messages[-100:]}


# ========================
# 静态文件与首页
# ========================
STATIC_DIR = "static"
INDEX_FILE = os.path.join(STATIC_DIR, "index.html")

os.makedirs(STATIC_DIR, exist_ok=True)

# 自动生成默认 index.html（如果不存在）
if not os.path.exists(INDEX_FILE):
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write("""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Conda 环境管理</title>
  <style>
    :root {
      --primary: #4e73df; --success: #28a745; --danger: #dc3545; --light: #f8f9fa; --dark: #343a40; --gray: #6c757d;
    }
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f7fb; color: #333; padding: 20px; line-height: 1.6; }
    .page-header { text-align: center; margin-bottom: 24px; }
    .page-header h1 { color: var(--primary); margin-bottom: 8px; }
    .container { max-width: 1200px; margin: 0 auto; display: flex; gap: 24px; }
    .main-content { flex: 2; display: flex; flex-direction: column; gap: 24px; }
    .log-sidebar { flex: 1; min-width: 300px; align-self: flex-start; }
    .card { background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); padding: 20px; }
    .form-group { margin-bottom: 15px; }
    label { display: block; margin-bottom: 6px; font-weight: 600; }
    input, select, button { padding: 10px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; width: 100%; }
    .btn { background: var(--primary); color: white; border: none; cursor: pointer; font-weight: 600; transition: opacity 0.2s; width: auto; }
    .btn:hover { opacity: 0.9; }
    .btn-danger { background: var(--danger); }
    .env-list { list-style: none; }
    .env-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #eee; }
    .env-item:last-child { border-bottom: none; }
    .env-name { font-weight: 600; font-size: 16px; }
    .env-version { color: var(--gray); font-size: 14px; }
    .actions { display: flex; gap: 8px; }
    .log-container { height: 420px; overflow-y: auto; background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 13px; }
    .log-entry { margin-bottom: 6px; word-break: break-word; }
    .log-error { color: #ff5555; }
    .log-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
    @media (max-width: 900px) {
      .container { flex-direction: column; }
      .log-sidebar { min-width: auto; align-self: stretch; }
      .log-container { height: 180px; }
    }
  </style>
</head>
<body>
  <div class="page-header">
    <h1>📦 Conda 环境管理</h1>
    <p>创建、克隆、查看和删除你的 Python 虚拟环境</p>
  </div>

  <div class="container">
    <div class="main-content">
      <!-- 创建环境 -->
      <div class="card">
        <h2>✨ 创建新环境</h2>
        <div class="form-group">
          <label for="envName">环境名称</label>
          <input type="text" id="envName" placeholder="例如：my_project" />
        </div>
        <div class="form-group">
          <label for="pythonVersion">Python 版本</label>
          <select id="pythonVersion">
            <option value="3.8">3.8</option><option value="3.9">3.9</option><option value="3.10">3.10</option>
            <option value="3.11">3.11</option><option value="3.12" selected>3.12</option><option value="3.13">3.13</option>
          </select>
        </div>
        <button class="btn" onclick="createEnv()">🚀 创建环境</button>
      </div>

      <!-- 克隆环境 -->
      <div class="card">
        <h2>🔄 克隆环境</h2>
        <div class="form-group">
          <label for="sourceEnv">源环境</label>
          <select id="sourceEnv">
            <option value="">加载中...</option>
          </select>
        </div>
        <div class="form-group">
          <label for="newEnvName">新环境名称</label>
          <input type="text" id="newEnvName" placeholder="例如：my_project_copy" />
        </div>
        <button class="btn" onclick="cloneEnv()">📋 克隆环境</button>
      </div>

      <!-- 环境列表 -->
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
          <h2>📋 已有环境</h2>
          <button class="btn" style="padding: 6px 12px; font-size: 14px;" onclick="loadEnvs()">🔄 刷新</button>
        </div>
        <ul id="envList" class="env-list">
          <li>加载中...</li>
        </ul>
      </div>
    </div>

    <!-- 日志侧边栏 -->
    <div class="log-sidebar">
      <div class="card">
        <div class="log-header">
          <h2>📜 操作日志</h2>
          <button class="btn" style="padding: 4px 10px; font-size: 12px;" onclick="clearLogs()">🗑️ 清空</button>
        </div>
        <div id="logContainer" class="log-container"></div>
      </div>
    </div>
  </div>

  <script>
    const API_BASE = window.location.origin;

    // 加载环境列表（同时更新克隆的源环境下拉框）
    async function loadEnvs() {
      try {
        const res = await fetch(`${API_BASE}/envs`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const envs = await res.json();
        const list = document.getElementById('envList');
        const sourceEnvSelect = document.getElementById('sourceEnv');

        // 更新环境列表
        if (envs.length === 0) {
          list.innerHTML = '<li>暂无环境</li>';
          sourceEnvSelect.innerHTML = '<option value="">暂无环境</option>';
          return;
        }
        list.innerHTML = envs.map(env => `
          <li class="env-item">
            <div>
              <div class="env-name">${escapeHtml(env.name)}</div>
              <div class="env-version">Python ${escapeHtml(env.python_version)}</div>
            </div>
            <div class="actions">
              <button class="btn btn-danger" onclick="deleteEnv('${escapeHtml(env.name)}')">🗑️ 删除</button>
            </div>
          </li>
        `).join('');

        // 更新克隆的源环境下拉框
        sourceEnvSelect.innerHTML = envs.map(env => `
          <option value="${escapeHtml(env.name)}">${escapeHtml(env.name)}</option>
        `).join('');
      } catch (err) {
        document.getElementById('envList').innerHTML = `<li style="color:red">❌ 加载失败: ${err.message}</li>`;
        document.getElementById('sourceEnv').innerHTML = '<option value="">加载失败</option>';
      }
    }

    // 创建环境
    async function createEnv() {
      const name = document.getElementById('envName').value.trim();
      const version = document.getElementById('pythonVersion').value;
      if (!name) {
        alert('请输入环境名称');
        return;
      }
      if (!/^[a-zA-Z0-9._-]+$/.test(name)) {
        alert('环境名称只能包含字母、数字、点、下划线或连字符');
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/envs`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, python_version: version })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        addLog(data.message);
        document.getElementById('envName').value = '';
        loadEnvs(); // 刷新列表
      } catch (err) {
        addLog(`❌ 创建失败: ${err.message}`, true);
      }
    }

    // 克隆环境
    async function cloneEnv() {
      const sourceEnv = document.getElementById('sourceEnv').value;
      const newEnvName = document.getElementById('newEnvName').value.trim();

      if (!sourceEnv) {
        alert('请选择源环境');
        return;
      }
      if (!newEnvName) {
        alert('请输入新环境名称');
        return;
      }
      if (!/^[a-zA-Z0-9._-]+$/.test(newEnvName)) {
        alert('新环境名称只能包含字母、数字、点、下划线或连字符');
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/envs/clone`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source_env: sourceEnv, new_env: newEnvName })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        addLog(data.message);
        document.getElementById('newEnvName').value = '';
        loadEnvs(); // 刷新列表
      } catch (err) {
        addLog(`❌ 克隆失败: ${err.message}`, true);
      }
    }

    // 删除环境
    async function deleteEnv(name) {
      if (!confirm(`确定要删除环境 "${name}" 吗？此操作不可逆！`)) return;
      try {
        const res = await fetch(`${API_BASE}/envs/${encodeURIComponent(name)}`, {
          method: 'DELETE'
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        addLog(data.message);
        loadEnvs(); // 刷新列表
      } catch (err) {
        addLog(`❌ 删除失败: ${err.message}`, true);
      }
    }

    // 日志相关
    function addLog(message, isError = false) {
      const container = document.getElementById('logContainer');
      const div = document.createElement('div');
      div.className = `log-entry${isError ? ' log-error' : ''}`;
      div.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
      container.appendChild(div);
      container.scrollTop = container.scrollHeight;
    }

    function clearLogs() {
      document.getElementById('logContainer').innerHTML = '';
    }

    function escapeHtml(text) {
      const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
      return text.replace(/[&<>"']/g, m => map[m]);
    }

    // 初始化
    loadEnvs();

    // 轮询日志
    setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/logs`);
        if (res.ok) {
          const data = await res.json();
          const container = document.getElementById('logContainer');
          const existingText = container.innerText;
          data.logs.forEach(msg => {
            if (!existingText.includes(msg)) {
              addLog(msg, msg.includes('[ERROR]'));
            }
          });
        }
      } catch (e) {}
    }, 5000);
  </script>
</body>
</html>
        """)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(INDEX_FILE)


# ========================
# 启动服务
# ========================
if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("❌ 未安装 uvicorn 或 fastapi")
        print("请运行：pip install fastapi uvicorn")
        input("\n按回车键退出...")
        sys.exit(1)

    HOST = "127.0.0.1"
    PORT = 8000
    URL = f"http://{HOST}:{PORT}"


    def open_browser():
        webbrowser.open(URL)


    print(f"🚀 启动 Conda 环境管理 Web 服务...")
    print(f"🌐 访问地址: {URL}")
    print(f"📄 Swagger 文档: {URL}/docs")
    threading.Timer(1.0, open_browser).start()

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")