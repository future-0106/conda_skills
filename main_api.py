# # main_api.py
# import os
# import sys
# import webbrowser
# import threading
# import re
# from pathlib import Path
# from fastapi import FastAPI, HTTPException, BackgroundTasks
# from fastapi.staticfiles import StaticFiles
# from fastapi.responses import FileResponse
# from pydantic import BaseModel
# import subprocess
# import json
# from typing import List, Dict
#
# # ========================
# # 全局配置
# # ========================
# app = FastAPI(title="Conda 环境管理 API", version="1.0")
# log_messages = []
#
#
# # 自动定位 conda 路径
# def get_conda_exe_path():
#     python_exe = Path(sys.executable)
#     # Windows
#     if sys.platform == "win32":
#         if "envs" not in str(python_exe.parent):
#             conda_exe = python_exe.parent / "Scripts" / "conda.exe"
#         else:
#             conda_root = python_exe.parent.parent.parent
#             conda_exe = conda_root / "Scripts" / "conda.exe"
#         if conda_exe.exists():
#             return str(conda_exe)
#     # macOS/Linux
#     else:
#         if "envs" not in str(python_exe.parent):
#             conda_exe = python_exe.parent / "bin" / "conda"
#         else:
#             conda_root = python_exe.parent.parent.parent
#             conda_exe = conda_root / "bin" / "conda"
#         if conda_exe.exists():
#             return str(conda_exe)
#     return "conda"
#
#
# CONDA_EXE = get_conda_exe_path()
#
#
# # ========================
# # 通用工具函数
# # ========================
# def log(msg: str, error: bool = False):
#     level = "ERROR" if error else "INFO"
#     entry = f"[{level}] {msg}"
#     log_messages.append(entry)
#     print(entry)
#
#
# def run_conda_cmd(args: List[str]) -> str:
#     """统一执行 conda 命令"""
#     try:
#         result = subprocess.run(
#             [CONDA_EXE] + args,
#             capture_output=True,
#             text=True,
#             encoding='utf-8',
#             errors='replace',
#             check=True,
#             timeout=120
#         )
#         return result.stdout
#     except subprocess.TimeoutExpired:
#         raise Exception("命令执行超时（超过 120 秒）")
#     except subprocess.CalledProcessError as e:
#         stderr = e.stderr.strip() if e.stderr else ""
#         stdout = e.stdout.strip() if e.stdout else ""
#         raise Exception(f"Conda 命令失败: {stderr or stdout}")
#     except FileNotFoundError:
#         raise Exception("未找到 conda 命令，请确保 Anaconda 已正确安装并加入 PATH")
#
#
# def get_python_version_from_env(path: str) -> str:
#     """获取环境的 Python 版本"""
#     python_exe = os.path.join(path, "python.exe") if os.name == 'nt' else os.path.join(path, "bin", "python")
#     if not os.path.exists(python_exe):
#         return "无 Python"
#     try:
#         result = subprocess.run([python_exe, "--version"], capture_output=True, text=True, timeout=5)
#         if result.returncode == 0 and result.stdout.startswith("Python "):
#             return result.stdout.strip()[7:].split()[0]
#     except:
#         pass
#     return "未知"
#
#
# def is_valid_env_name(name: str) -> bool:
#     """验证环境名合法性"""
#     if not name or name.startswith('.'):
#         return False
#     return re.fullmatch(r'[a-zA-Z0-9._-]+', name) is not None
#
#
# def list_all_envs() -> List[Dict[str, str]]:
#     """获取所有非 base 环境"""
#     output = run_conda_cmd(["env", "list", "--json"])
#     output = output.strip()
#     if output.startswith('\ufeff'):
#         output = output[1:]
#     if '}' in output:
#         last_brace = output.rfind('}')
#         output = output[:last_brace + 1]
#     data = json.loads(output)
#     env_paths = data.get("envs", [])
#
#     base_path = None
#     for path in env_paths:
#         if "/envs/" not in path.replace("\\", "/"):
#             base_path = path
#             break
#     if not base_path and env_paths:
#         base_path = env_paths[0]
#
#     envs = []
#     for path in env_paths:
#         if path == base_path:
#             continue
#         name = path.split("\\")[-1] if "\\" in path else path.split("/")[-1]
#         version = get_python_version_from_env(path)
#         envs.append({"name": name, "path": path, "python_version": version})
#     return envs
#
#
# # ========================
# # API 接口定义
# # ========================
# @app.get("/envs", response_model=List[Dict[str, str]])
# async def list_envs():
#     """列出所有非 base 环境及其 Python 版本"""
#     try:
#         envs = list_all_envs()
#         return envs
#     except Exception as e:
#         log(str(e), error=True)
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# # 1. 创建环境
# class CreateEnvRequest(BaseModel):
#     name: str
#     python_version: str = "3.12"
#
#
# def create_env_background(name: str, python_version: str):
#     try:
#         log(f"开始创建环境: {name} (Python {python_version})")
#         run_conda_cmd(["create", "--name", name, f"python={python_version}", "--yes"])
#         log(f"✅ 环境 '{name}' 创建成功")
#     except Exception as e:
#         log(f"❌ 创建失败: {str(e)}", error=True)
#
#
# @app.post("/envs")
# async def create_env(req: CreateEnvRequest, background_tasks: BackgroundTasks):
#     try:
#         # 验证环境名
#         if not is_valid_env_name(req.name):
#             raise HTTPException(status_code=400, detail="环境名只能包含字母、数字、下划线、连字符或点（不能以点开头）")
#
#         # 检查环境是否已存在
#         envs = list_all_envs()
#         if any(env["name"] == req.name for env in envs):
#             raise HTTPException(status_code=400, detail=f"环境 '{req.name}' 已存在")
#
#         background_tasks.add_task(create_env_background, req.name, req.python_version)
#         return {"message": f"正在后台创建环境: {req.name}"}
#     except HTTPException:
#         raise
#     except Exception as e:
#         log(str(e), error=True)
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# # 2. 删除环境
# @app.delete("/envs/{name}")
# async def delete_env(name: str):
#     try:
#         # 验证环境存在
#         envs = list_all_envs()
#         if not any(env["name"] == name for env in envs):
#             raise HTTPException(status_code=400, detail=f"环境 '{name}' 不存在")
#
#         log(f"正在删除环境: {name}")
#         run_conda_cmd(["env", "remove", "--name", name, "--yes"])
#         log(f"✅ 环境 '{name}' 删除成功")
#         return {"message": f"环境 '{name}' 已删除"}
#     except HTTPException:
#         raise
#     except Exception as e:
#         log(str(e), error=True)
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# # 3. 克隆环境
# class CloneEnvRequest(BaseModel):
#     source_env: str
#     new_env: str
#
#
# def clone_env_background(source_env: str, new_env: str):
#     try:
#         log(f"开始克隆环境: {source_env} → {new_env}")
#         run_conda_cmd(["create", "--name", new_env, "--clone", source_env, "--yes"])
#         log(f"✅ 环境克隆成功: {source_env} → {new_env}")
#     except Exception as e:
#         log(f"❌ 克隆失败: {str(e)}", error=True)
#
#
# @app.post("/envs/clone")
# async def clone_env(req: CloneEnvRequest, background_tasks: BackgroundTasks):
#     try:
#         # 验证源环境存在
#         envs = list_all_envs()
#         env_names = [env["name"] for env in envs]
#         if req.source_env not in env_names:
#             raise HTTPException(status_code=400, detail=f"源环境 '{req.source_env}' 不存在")
#
#         # 验证新环境名
#         if not is_valid_env_name(req.new_env):
#             raise HTTPException(status_code=400, detail="新环境名只能包含字母、数字、下划线、连字符或点（不能以点开头）")
#
#         # 验证新环境未存在
#         if req.new_env in env_names:
#             raise HTTPException(status_code=400, detail=f"新环境 '{req.new_env}' 已存在")
#
#         background_tasks.add_task(clone_env_background, req.source_env, req.new_env)
#         return {"message": f"正在后台克隆环境: {req.source_env} → {req.new_env}"}
#     except HTTPException:
#         raise
#     except Exception as e:
#         log(str(e), error=True)
#         raise HTTPException(status_code=500, detail=str(e))
#
#
# @app.get("/logs")
# async def get_logs():
#     """获取最新 100 条日志"""
#     return {"logs": log_messages[-100:]}
#
#
# # ========================
# # 静态文件与首页
# # ========================
# STATIC_DIR = "static"
# INDEX_FILE = os.path.join(STATIC_DIR, "index.html")
#
# os.makedirs(STATIC_DIR, exist_ok=True)
#
# # 自动生成默认 index.html（如果不存在）
# if not os.path.exists(INDEX_FILE):
#     with open(INDEX_FILE, "w", encoding="utf-8") as f:
#         f.write("""
# <!DOCTYPE html>
# <html lang="zh-CN">
# <head>
#   <meta charset="UTF-8" />
#   <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
#   <title>Conda 环境管理</title>
#   <style>
#     :root {
#       --primary: #4e73df; --success: #28a745; --danger: #dc3545; --light: #f8f9fa; --dark: #343a40; --gray: #6c757d;
#     }
#     * { margin: 0; padding: 0; box-sizing: border-box; }
#     body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f7fb; color: #333; padding: 20px; line-height: 1.6; }
#     .page-header { text-align: center; margin-bottom: 24px; }
#     .page-header h1 { color: var(--primary); margin-bottom: 8px; }
#     .container { max-width: 1200px; margin: 0 auto; display: flex; gap: 24px; }
#     .main-content { flex: 2; display: flex; flex-direction: column; gap: 24px; }
#     .log-sidebar { flex: 1; min-width: 300px; align-self: flex-start; }
#     .card { background: white; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); padding: 20px; }
#     .form-group { margin-bottom: 15px; }
#     label { display: block; margin-bottom: 6px; font-weight: 600; }
#     input, select, button { padding: 10px 12px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; width: 100%; }
#     .btn { background: var(--primary); color: white; border: none; cursor: pointer; font-weight: 600; transition: opacity 0.2s; width: auto; }
#     .btn:hover { opacity: 0.9; }
#     .btn-danger { background: var(--danger); }
#     .env-list { list-style: none; }
#     .env-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #eee; }
#     .env-item:last-child { border-bottom: none; }
#     .env-name { font-weight: 600; font-size: 16px; }
#     .env-version { color: var(--gray); font-size: 14px; }
#     .actions { display: flex; gap: 8px; }
#     .log-container { height: 420px; overflow-y: auto; background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 6px; font-family: monospace; font-size: 13px; }
#     .log-entry { margin-bottom: 6px; word-break: break-word; }
#     .log-error { color: #ff5555; }
#     .log-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
#     @media (max-width: 900px) {
#       .container { flex-direction: column; }
#       .log-sidebar { min-width: auto; align-self: stretch; }
#       .log-container { height: 180px; }
#     }
#   </style>
# </head>
# <body>
#   <div class="page-header">
#     <h1>📦 Conda 环境管理</h1>
#     <p>创建、克隆、查看和删除你的 Python 虚拟环境</p>
#   </div>
#
#   <div class="container">
#     <div class="main-content">
#       <!-- 创建环境 -->
#       <div class="card">
#         <h2>✨ 创建新环境</h2>
#         <div class="form-group">
#           <label for="envName">环境名称</label>
#           <input type="text" id="envName" placeholder="例如：my_project" />
#         </div>
#         <div class="form-group">
#           <label for="pythonVersion">Python 版本</label>
#           <select id="pythonVersion">
#             <option value="3.8">3.8</option><option value="3.9">3.9</option><option value="3.10">3.10</option>
#             <option value="3.11">3.11</option><option value="3.12" selected>3.12</option><option value="3.13">3.13</option>
#           </select>
#         </div>
#         <button class="btn" onclick="createEnv()">🚀 创建环境</button>
#       </div>
#
#       <!-- 克隆环境 -->
#       <div class="card">
#         <h2>🔄 克隆环境</h2>
#         <div class="form-group">
#           <label for="sourceEnv">源环境</label>
#           <select id="sourceEnv">
#             <option value="">加载中...</option>
#           </select>
#         </div>
#         <div class="form-group">
#           <label for="newEnvName">新环境名称</label>
#           <input type="text" id="newEnvName" placeholder="例如：my_project_copy" />
#         </div>
#         <button class="btn" onclick="cloneEnv()">📋 克隆环境</button>
#       </div>
#
#       <!-- 环境列表 -->
#       <div class="card">
#         <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
#           <h2>📋 已有环境</h2>
#           <button class="btn" style="padding: 6px 12px; font-size: 14px;" onclick="loadEnvs()">🔄 刷新</button>
#         </div>
#         <ul id="envList" class="env-list">
#           <li>加载中...</li>
#         </ul>
#       </div>
#     </div>
#
#     <!-- 日志侧边栏 -->
#     <div class="log-sidebar">
#       <div class="card">
#         <div class="log-header">
#           <h2>📜 操作日志</h2>
#           <button class="btn" style="padding: 4px 10px; font-size: 12px;" onclick="clearLogs()">🗑️ 清空</button>
#         </div>
#         <div id="logContainer" class="log-container"></div>
#       </div>
#     </div>
#   </div>
#
#   <script>
#     const API_BASE = window.location.origin;
#
#     // 加载环境列表（同时更新克隆的源环境下拉框）
#     async function loadEnvs() {
#       try {
#         const res = await fetch(`${API_BASE}/envs`);
#         if (!res.ok) throw new Error(`HTTP ${res.status}`);
#         const envs = await res.json();
#         const list = document.getElementById('envList');
#         const sourceEnvSelect = document.getElementById('sourceEnv');
#
#         // 更新环境列表
#         if (envs.length === 0) {
#           list.innerHTML = '<li>暂无环境</li>';
#           sourceEnvSelect.innerHTML = '<option value="">暂无环境</option>';
#           return;
#         }
#         list.innerHTML = envs.map(env => `
#           <li class="env-item">
#             <div>
#               <div class="env-name">${escapeHtml(env.name)}</div>
#               <div class="env-version">Python ${escapeHtml(env.python_version)}</div>
#             </div>
#             <div class="actions">
#               <button class="btn btn-danger" onclick="deleteEnv('${escapeHtml(env.name)}')">🗑️ 删除</button>
#             </div>
#           </li>
#         `).join('');
#
#         // 更新克隆的源环境下拉框
#         sourceEnvSelect.innerHTML = envs.map(env => `
#           <option value="${escapeHtml(env.name)}">${escapeHtml(env.name)}</option>
#         `).join('');
#       } catch (err) {
#         document.getElementById('envList').innerHTML = `<li style="color:red">❌ 加载失败: ${err.message}</li>`;
#         document.getElementById('sourceEnv').innerHTML = '<option value="">加载失败</option>';
#       }
#     }
#
#     // 创建环境
#     async function createEnv() {
#       const name = document.getElementById('envName').value.trim();
#       const version = document.getElementById('pythonVersion').value;
#       if (!name) {
#         alert('请输入环境名称');
#         return;
#       }
#       if (!/^[a-zA-Z0-9._-]+$/.test(name)) {
#         alert('环境名称只能包含字母、数字、点、下划线或连字符');
#         return;
#       }
#
#       try {
#         const res = await fetch(`${API_BASE}/envs`, {
#           method: 'POST',
#           headers: { 'Content-Type': 'application/json' },
#           body: JSON.stringify({ name, python_version: version })
#         });
#         if (!res.ok) {
#           const err = await res.json().catch(() => ({}));
#           throw new Error(err.detail || `HTTP ${res.status}`);
#         }
#         const data = await res.json();
#         addLog(data.message);
#         document.getElementById('envName').value = '';
#         loadEnvs(); // 刷新列表
#       } catch (err) {
#         addLog(`❌ 创建失败: ${err.message}`, true);
#       }
#     }
#
#     // 克隆环境
#     async function cloneEnv() {
#       const sourceEnv = document.getElementById('sourceEnv').value;
#       const newEnvName = document.getElementById('newEnvName').value.trim();
#
#       if (!sourceEnv) {
#         alert('请选择源环境');
#         return;
#       }
#       if (!newEnvName) {
#         alert('请输入新环境名称');
#         return;
#       }
#       if (!/^[a-zA-Z0-9._-]+$/.test(newEnvName)) {
#         alert('新环境名称只能包含字母、数字、点、下划线或连字符');
#         return;
#       }
#
#       try {
#         const res = await fetch(`${API_BASE}/envs/clone`, {
#           method: 'POST',
#           headers: { 'Content-Type': 'application/json' },
#           body: JSON.stringify({ source_env: sourceEnv, new_env: newEnvName })
#         });
#         if (!res.ok) {
#           const err = await res.json().catch(() => ({}));
#           throw new Error(err.detail || `HTTP ${res.status}`);
#         }
#         const data = await res.json();
#         addLog(data.message);
#         document.getElementById('newEnvName').value = '';
#         loadEnvs(); // 刷新列表
#       } catch (err) {
#         addLog(`❌ 克隆失败: ${err.message}`, true);
#       }
#     }
#
#     // 删除环境
#     async function deleteEnv(name) {
#       if (!confirm(`确定要删除环境 "${name}" 吗？此操作不可逆！`)) return;
#       try {
#         const res = await fetch(`${API_BASE}/envs/${encodeURIComponent(name)}`, {
#           method: 'DELETE'
#         });
#         if (!res.ok) {
#           const err = await res.json().catch(() => ({}));
#           throw new Error(err.detail || `HTTP ${res.status}`);
#         }
#         const data = await res.json();
#         addLog(data.message);
#         loadEnvs(); // 刷新列表
#       } catch (err) {
#         addLog(`❌ 删除失败: ${err.message}`, true);
#       }
#     }
#
#     // 日志相关
#     function addLog(message, isError = false) {
#       const container = document.getElementById('logContainer');
#       const div = document.createElement('div');
#       div.className = `log-entry${isError ? ' log-error' : ''}`;
#       div.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
#       container.appendChild(div);
#       container.scrollTop = container.scrollHeight;
#     }
#
#     function clearLogs() {
#       document.getElementById('logContainer').innerHTML = '';
#     }
#
#     function escapeHtml(text) {
#       const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
#       return text.replace(/[&<>"']/g, m => map[m]);
#     }
#
#     // 初始化
#     loadEnvs();
#
#     // 轮询日志
#     setInterval(async () => {
#       try {
#         const res = await fetch(`${API_BASE}/logs`);
#         if (res.ok) {
#           const data = await res.json();
#           const container = document.getElementById('logContainer');
#           const existingText = container.innerText;
#           data.logs.forEach(msg => {
#             if (!existingText.includes(msg)) {
#               addLog(msg, msg.includes('[ERROR]'));
#             }
#           });
#         }
#       } catch (e) {}
#     }, 5000);
#   </script>
# </body>
# </html>
#         """)
#
# app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
#
#
# @app.get("/")
# async def index():
#     return FileResponse(INDEX_FILE)
#
#
# # ========================
# # 启动服务
# # ========================
# if __name__ == "__main__":
#     try:
#         import uvicorn
#     except ImportError:
#         print("❌ 未安装 uvicorn 或 fastapi")
#         print("请运行：pip install fastapi uvicorn")
#         input("\n按回车键退出...")
#         sys.exit(1)
#
#     HOST = "127.0.0.1"
#     PORT = 8000
#     URL = f"http://{HOST}:{PORT}"
#
#
#     def open_browser():
#         webbrowser.open(URL)
#
#
#     print(f"🚀 启动 Conda 环境管理 Web 服务...")
#     print(f"🌐 访问地址: {URL}")
#     print(f"📄 Swagger 文档: {URL}/docs")
#     threading.Timer(1.0, open_browser).start()
#
#     uvicorn.run(app, host=HOST, port=PORT, log_level="info")


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
from typing import List, Dict, Optional
import yaml  # 新增依赖


# ========================
# 新增：集成 conda_export_env.py 的核心功能
# ========================
def remove_ansi(text: str) -> str:
    """移除 ANSI 转义序列（如 \x1b[32m）"""
    ansi_escape = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)


def normalize_channel(channel: str) -> str:
    """标准化conda channel路径"""
    return channel.rstrip('/')


def deduplicate_channels(channels):
    """去重conda channels（保留顺序）"""
    seen = set()
    unique = []
    for ch in channels:
        norm = normalize_channel(ch)
        if norm not in seen:
            seen.add(norm)
            unique.append(ch)
    return unique


def generate_md_file(output_md="使用yml之前先看.md"):
    """生成导出环境的使用指南MD文件"""
    md_content = """# Conda环境YAML使用指南    
## 注意：使用生成的yml文件创建的环境，可以写一个测试代码来验证环境是否安装正确
## 使用方法
1. 确保已安装Anaconda/Miniconda
2. 执行创建命令：`conda env create -f {yml_file}`（替换{yml_file}为实际文件名）
3. 激活环境：`conda activate {env_name}`（替换{env_name}为环境名）    


## 常见创建失败原因

| 原因 | 典型表现 | 解决方法 |
|------|----------|----------|
| 包版本冲突 | UnsatisfiableError | 降低/升级冲突包版本，或更换Python版本 |
| Python版本不兼容 | requires a different python version | 调整YAML中的python版本，或选择兼容的包版本 |
| 特殊包源错误 | No matching distribution | 确保PyTorch/Paddle等包使用官方源 |
| 网络问题 | 卡在Solving environment | 切换国内镜像源（如清华源） |
| YAML语法错误 | Invalid YAML | 检查缩进、格式是否正确 |
| 平台不兼容 | No matching distribution | 确认包支持当前操作系统/架构（如ARM/M1） |
"""
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write(md_content)
    return output_md


def export_conda_env(env_name=None, output_file="environment.yml", output_md="env_guide.md"):
    """
    核心导出函数（供外部调用）
    :param env_name: 要导出的环境名，None则导出当前环境
    :param output_file: YAML输出文件名
    :param output_md: MD指南输出文件名
    :return: 字典格式的执行结果
    """
    try:
        # 获取conda执行路径
        conda_exe = get_conda_exe_path()
        cmd = [conda_exe, "env", "export", "--no-builds"]
        if env_name:
            cmd.extend(["--name", env_name])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='replace'
        )

        # 清理ANSI转义序列
        clean_stdout = remove_ansi(result.stdout)

        # 解析YAML
        try:
            env_data = yaml.safe_load(clean_stdout)
        except yaml.YAMLError as e:
            debug_file = "debug_raw_output.txt"
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(result.stdout)
            return {
                "status": "failed",
                "msg": f"YAML解析失败（已保存调试文件）: {str(e)}",
                "debug_file": debug_file
            }

        # 处理channels去重、移除prefix
        if env_data and 'channels' in env_data:
            env_data['channels'] = deduplicate_channels(env_data['channels'])
        if env_data:
            env_data.pop('prefix', None)

        # 生成MD指南
        generate_md_file(output_md)

        # 写入YAML文件
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(
                env_data,
                f,
                default_flow_style=False,
                indent=2,
                sort_keys=False,
                allow_unicode=True
            )

        return {
            "status": "success",
            "msg": f"环境导出成功：{output_file} | 指南文件：{output_md}",
            "yml_file": output_file,
            "md_file": output_md
        }

    except subprocess.CalledProcessError as e:
        # 捕获conda命令执行失败
        return {
            "status": "failed",
            "msg": f"Conda命令执行失败: {e.stderr.strip()}",
            "return_code": e.returncode
        }
    except Exception as e:
        # 捕获其他异常
        return {
            "status": "failed",
            "msg": f"未知错误: {str(e)}"
        }


# ========================
# 全局配置
# ========================
app = FastAPI(title="Conda 环境管理 API", version="1.0")
log_messages = []

# 任务进度管理
task_progress = {}  # {task_id: {"progress": 0-100, "stage": "阶段描述", "status": "running/completed/failed"}}


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
# 原有通用工具函数
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
# 原有API接口 + 新增导出接口
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


def create_env_background(name: str, python_version: str, task_id: str = None):
    try:
        task_progress[task_id] = {"progress": 0, "stage": "正在准备创建环境...", "status": "running"}
        log(f"开始创建环境: {name} (Python {python_version})")
        
        task_progress[task_id] = {"progress": 10, "stage": "正在解析依赖...", "status": "running"}
        
        # 使用 Popen 实时更新进度
        import subprocess
        process = subprocess.Popen(
            [CONDA_EXE, "create", "--name", name, f"python={python_version}", "--yes"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        stage_progress = 20
        for line in process.stdout:
            if "Solving environment" in line:
                task_progress[task_id] = {"progress": stage_progress, "stage": "正在解析依赖...", "status": "running"}
            elif "Verifying" in line:
                stage_progress = 50
                task_progress[task_id] = {"progress": stage_progress, "stage": "正在验证...", "status": "running"}
            elif "Downloading" in line or "Extracting" in line:
                stage_progress = 70
                task_progress[task_id] = {"progress": stage_progress, "stage": "正在下载/解压包...", "status": "running"}
            elif "Executing" in line:
                stage_progress = 85
                task_progress[task_id] = {"progress": stage_progress, "stage": "正在执行...", "status": "running"}
        
        process.wait()
        
        if process.returncode != 0:
            raise Exception("Conda 命令执行失败")
        
        task_progress[task_id] = {"progress": 100, "stage": "创建完成", "status": "completed"}
        log(f"✅ 环境 '{name}' 创建成功")
    except Exception as e:
        task_progress[task_id] = {"progress": 0, "stage": f"创建失败: {str(e)}", "status": "failed"}
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

        import uuid
        task_id = str(uuid.uuid4())
        background_tasks.add_task(create_env_background, req.name, req.python_version, task_id)
        return {"message": f"正在后台创建环境: {req.name}", "task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        log(str(e), error=True)
        raise HTTPException(status_code=500, detail=str(e))


# 2. 删除环境
@app.delete("/envs/{name}")
async def delete_env(name: str, background_tasks: BackgroundTasks):
    try:
        # 验证环境存在
        envs = list_all_envs()
        if not any(env["name"] == name for env in envs):
            raise HTTPException(status_code=400, detail=f"环境 '{name}' 不存在")

        import uuid
        task_id = str(uuid.uuid4())
        background_tasks.add_task(delete_env_background, name, task_id)
        return {"message": f"正在后台删除环境: {name}", "task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        log(str(e), error=True)
        raise HTTPException(status_code=500, detail=str(e))


def delete_env_background(name: str, task_id: str):
    try:
        task_progress[task_id] = {"progress": 0, "stage": "正在删除环境...", "status": "running"}
        log(f"正在删除环境: {name}")
        
        task_progress[task_id] = {"progress": 30, "stage": "正在移除包...", "status": "running"}
        run_conda_cmd(["env", "remove", "--name", name, "--yes"])
        
        task_progress[task_id] = {"progress": 100, "stage": "删除完成", "status": "completed"}
        log(f"✅ 环境 '{name}' 删除成功")
    except Exception as e:
        task_progress[task_id] = {"progress": 0, "stage": f"删除失败: {str(e)}", "status": "failed"}
        log(f"❌ 删除失败: {str(e)}", error=True)


# 3. 克隆环境
class CloneEnvRequest(BaseModel):
    source_env: str
    new_env: str


def clone_env_background(source_env: str, new_env: str, task_id: str = None):
    try:
        task_progress[task_id] = {"progress": 0, "stage": "正在准备克隆环境...", "status": "running"}
        log(f"开始克隆环境: {source_env} → {new_env}")
        
        task_progress[task_id] = {"progress": 10, "stage": "正在复制文件...", "status": "running"}
        
        import subprocess
        process = subprocess.Popen(
            [CONDA_EXE, "create", "--name", new_env, "--clone", source_env, "--yes"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        stage_progress = 20
        for line in process.stdout:
            if "Copying" in line or "Linking" in line:
                stage_progress = min(80, stage_progress + 5)
                task_progress[task_id] = {"progress": stage_progress, "stage": "正在复制/链接文件...", "status": "running"}
        
        process.wait()
        
        if process.returncode != 0:
            raise Exception("Conda 命令执行失败")
        
        task_progress[task_id] = {"progress": 100, "stage": "克隆完成", "status": "completed"}
        log(f"✅ 环境克隆成功: {source_env} → {new_env}")
    except Exception as e:
        task_progress[task_id] = {"progress": 0, "stage": f"克隆失败: {str(e)}", "status": "failed"}
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

        import uuid
        task_id = str(uuid.uuid4())
        background_tasks.add_task(clone_env_background, req.source_env, req.new_env, task_id)
        return {"message": f"正在后台克隆环境: {req.source_env} → {req.new_env}", "task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        log(str(e), error=True)
        raise HTTPException(status_code=500, detail=str(e))


# 新增：导出环境接口
class ExportEnvRequest(BaseModel):
    env_name: Optional[str] = None
    output_file: str = "environment.yml"
    output_md: str = "使用yml之前先看.md"


@app.post("/envs/export")
async def export_env(req: ExportEnvRequest):
    """导出指定环境为YAML文件，并生成使用指南MD文件"""
    try:
        # 验证环境名（如果指定）
        if req.env_name:
            envs = list_all_envs()
            env_names = [env["name"] for env in envs]
            if req.env_name not in env_names:
                raise HTTPException(status_code=400, detail=f"环境 '{req.env_name}' 不存在")

        # 执行导出
        result = export_conda_env(
            env_name=req.env_name,
            output_file=req.output_file,
            output_md=req.output_md
        )

        if result["status"] == "failed":
            log(result["msg"], error=True)
            raise HTTPException(status_code=500, detail=result["msg"])

        log(result["msg"])

        # 读取YAML文件内容并返回
        with open(result["yml_file"], 'r', encoding='utf-8') as f:
            yml_content = f.read()

        return {"yml_content": yml_content}

    except HTTPException:
        raise
    except Exception as e:
        log(str(e), error=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}")
async def get_task_progress(task_id: str):
    """获取任务进度"""
    if task_id in task_progress:
        return task_progress[task_id]
    return {"progress": 0, "stage": "任务不存在或已完成", "status": "unknown"}


@app.get("/logs")
async def get_logs():
    """获取最新 100 条日志"""
    return {"logs": log_messages[-100:]}


# ========================
# 静态文件与首页（新增导出功能UI）
# ========================
STATIC_DIR = "static"
INDEX_FILE = os.path.join(STATIC_DIR, "index.html")

os.makedirs(STATIC_DIR, exist_ok=True)

# 自动生成默认 index.html（包含导出功能）
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
    .btn-success { background: var(--success); }
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
    .progress-container { margin-bottom: 12px; display: none; }
    .progress-container.active { display: block; }
    .progress-bar-wrapper { background: #e9ecef; border-radius: 4px; height: 20px; overflow: hidden; position: relative; }
    .progress-bar { height: 100%; background: linear-gradient(90deg, #4e73df, #6f8feb); transition: width 0.3s ease; border-radius: 4px; }
    .progress-text { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); font-size: 12px; font-weight: 600; color: #333; }
    .progress-stage { font-size: 12px; color: #666; margin-top: 4px; }
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
    <p>创建、克隆、导出、查看和删除你的 Python 虚拟环境</p>
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

      <!-- 导出环境 -->
      <div class="card">
        <h2>📤 导出环境</h2>
        <div class="form-group">
          <label for="exportEnv">要导出的环境（留空则导出当前环境）</label>
          <select id="exportEnv">
            <option value="">当前环境</option>
            <option value="">加载中...</option>
          </select>
        </div>
        <div class="form-group">
          <label for="outputYml">YAML 输出文件名</label>
          <input type="text" id="outputYml" value="environment.yml" placeholder="例如：my_env.yml" />
        </div>
        <div class="form-group">
          <label for="outputMd">MD 指南输出文件名</label>
          <input type="text" id="outputMd" value="使用yml之前先看.md" placeholder="例如：env_guide.md" />
        </div>
        <button class="btn btn-success" onclick="exportEnv()">📥 导出环境</button>
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
        <div id="progressContainer" class="progress-container">
          <div class="progress-bar-wrapper">
            <div id="progressBar" class="progress-bar" style="width: 0%;"></div>
            <span id="progressText" class="progress-text">0%</span>
          </div>
          <div id="progressStage" class="progress-stage">准备中...</div>
        </div>
        <div id="logContainer" class="log-container"></div>
      </div>
    </div>
  </div>

  <script>
    const API_BASE = window.location.origin;

    // 加载环境列表（同时更新克隆/导出的源环境下拉框）
    async function loadEnvs() {
      try {
        const res = await fetch(`${API_BASE}/envs`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const envs = await res.json();
        const list = document.getElementById('envList');
        const sourceEnvSelect = document.getElementById('sourceEnv');
        const exportEnvSelect = document.getElementById('exportEnv');

        // 更新环境列表
        if (envs.length === 0) {
          list.innerHTML = '<li>暂无环境</li>';
          sourceEnvSelect.innerHTML = '<option value="">暂无环境</option>';
          exportEnvSelect.innerHTML = '<option value="">当前环境</option>';
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

        // 更新导出的环境下拉框
        exportEnvSelect.innerHTML = '<option value="">当前环境</option>' + envs.map(env => `
          <option value="${escapeHtml(env.name)}">${escapeHtml(env.name)}</option>
        `).join('');
      } catch (err) {
        document.getElementById('envList').innerHTML = `<li style="color:red">❌ 加载失败: ${err.message}</li>`;
        document.getElementById('sourceEnv').innerHTML = '<option value="">加载失败</option>';
        document.getElementById('exportEnv').innerHTML = '<option value="">当前环境</option><option value="">加载失败</option>';
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
        
        // 启动进度跟踪
        if (data.task_id) {
          startProgressTracking(data.task_id, '创建环境');
        }
        
        document.getElementById('envName').value = '';
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
        
        // 启动进度跟踪
        if (data.task_id) {
          startProgressTracking(data.task_id, '克隆环境');
        }
        
        document.getElementById('newEnvName').value = '';
      } catch (err) {
        addLog(`❌ 克隆失败: ${err.message}`, true);
      }
    }

    // 导出环境
    async function exportEnv() {
      const envName = document.getElementById('exportEnv').value.trim() || null;
      const outputYml = document.getElementById('outputYml').value.trim();
      const outputMd = document.getElementById('outputMd').value.trim();

      if (!outputYml) {
        alert('请输入YAML输出文件名');
        return;
      }
      if (!outputMd) {
        alert('请输入MD指南输出文件名');
        return;
      }

      try {
        const res = await fetch(`${API_BASE}/envs/export`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            env_name: envName,
            output_file: outputYml,
            output_md: outputMd
          })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const data = await res.json();
        addLog(data.message);
        alert(`✅ 导出成功！\nYAML文件: ${data.files.yml}\nMD指南: ${data.files.md}`);
      } catch (err) {
        addLog(`❌ 导出失败: ${err.message}`, true);
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
        
        // 启动进度跟踪
        if (data.task_id) {
          startProgressTracking(data.task_id, '删除环境');
        }
      } catch (err) {
        addLog(`❌ 删除失败: ${err.message}`, true);
      }
    }

    // 进度条相关
    let currentProgressTaskId = null;
    let progressPollingInterval = null;

    function startProgressTracking(taskId, taskType) {
      currentProgressTaskId = taskId;
      const progressContainer = document.getElementById('progressContainer');
      const progressBar = document.getElementById('progressBar');
      const progressText = document.getElementById('progressText');
      const progressStage = document.getElementById('progressStage');
      
      progressContainer.classList.add('active');
      progressBar.style.width = '0%';
      progressText.textContent = '0%';
      progressStage.textContent = `正在${taskType}...`;
      
      // 停止之前的轮询
      if (progressPollingInterval) {
        clearInterval(progressPollingInterval);
      }
      
      // 开始轮询进度
      progressPollingInterval = setInterval(async () => {
        try {
          const res = await fetch(`${API_BASE}/tasks/${taskId}`);
          if (!res.ok) return;
          const data = await res.json();
          
          progressBar.style.width = data.progress + '%';
          progressText.textContent = data.progress + '%';
          progressStage.textContent = data.stage || '处理中...';
          
          // 任务完成或失败
          if (data.status === 'completed') {
            clearInterval(progressPollingInterval);
            progressBar.style.background = 'linear-gradient(90deg, #28a745, #48c764)';
            setTimeout(() => {
              progressContainer.classList.remove('active');
              progressBar.style.background = 'linear-gradient(90deg, #4e73df, #6f8feb)';
              loadEnvs();
            }, 2000);
          } else if (data.status === 'failed') {
            clearInterval(progressPollingInterval);
            progressBar.style.background = 'linear-gradient(90deg, #dc3545, #e4606d)';
            progressStage.textContent = data.stage;
          }
        } catch (e) {
          // 忽略轮询错误
        }
      }, 1000);
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
# 新增：命令行调用导出功能（兼容原有 conda_export_env.py 的使用方式）
# ========================
def cli_export():
    """命令行导出环境（兼容原脚本的参数）"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", "-e")
    parser.add_argument("--output", "-o", default="environment.yml")
    parser.add_argument("--md-output", "-m", default="使用yml之前先看.md")
    args = parser.parse_args()

    result = export_conda_env(
        env_name=args.env,
        output_file=args.output,
        output_md=args.md_output
    )

    print(result["msg"])
    if result["status"] == "failed":
        sys.exit(1)
    sys.exit(0)


# ========================
# 启动服务
# ========================
if __name__ == "__main__":
    # 支持两种运行模式：API服务 / 命令行导出
    if len(sys.argv) > 1 and (sys.argv[1].startswith("--env") or sys.argv[1].startswith("-e") or
                              sys.argv[1].startswith("--output") or sys.argv[1].startswith("-o")):
        # 命令行导出模式（兼容原 conda_export_env.py）
        cli_export()
    else:
        # API服务模式
        try:
            import uvicorn
        except ImportError:
            print("❌ 未安装 uvicorn 或 fastapi")
            print("请运行：pip install fastapi uvicorn pyyaml")
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
        print(f"💡 命令行导出用法: python {sys.argv[0]} --env 环境名 --output 输出.yml")
        threading.Timer(1.0, open_browser).start()

        uvicorn.run(app, host=HOST, port=PORT, log_level="info")