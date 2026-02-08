#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conda 环境创建工具（GUI 版）
- 支持选择 Python 版本
- 实时显示日志
- 列出已有环境及其 Python 版本
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import threading
import json
import os


class CondaEnvCreator:
    def __init__(self, root):
        self.root = root
        self.root.title("✨ 创建 Conda 环境")
        self.root.geometry("650x550")
        self.root.minsize(600, 450)

        self.existing_envs = set()
        self.create_widgets()
        self.load_existing_envs()

    def create_widgets(self):
        # 左侧：输入区域
        left_frame = ttk.Frame(self.root)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 环境名称
        ttk.Label(left_frame, text="环境名称:").pack(anchor=tk.W, pady=(0, 5))
        self.name_entry = ttk.Entry(left_frame, width=30)
        self.name_entry.pack(fill=tk.X, pady=(0, 10))

        # Python 版本
        ttk.Label(left_frame, text="Python 版本:").pack(anchor=tk.W, pady=(0, 5))
        version_frame = ttk.Frame(left_frame)
        version_frame.pack(fill=tk.X, pady=(0, 10))
        self.version_var = tk.StringVar(value="3.12")
        versions = ["3.8", "3.9", "3.10", "3.11", "3.12", "3.13"]
        for v in versions:
            ttk.Radiobutton(version_frame, text=v, variable=self.version_var, value=v).pack(side=tk.LEFT, padx=5)

        # 按钮
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 15))
        self.create_btn = ttk.Button(btn_frame, text="🚀 创建环境", command=self.create_env)
        self.create_btn.pack(side=tk.LEFT)
        self.refresh_btn = ttk.Button(btn_frame, text="🔄 刷新列表", command=self.load_existing_envs)
        self.refresh_btn.pack(side=tk.LEFT, padx=(10, 0))

        # 日志区域
        log_frame = ttk.LabelFrame(left_frame, text="操作日志")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_text = tk.Text(log_frame, height=8, state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # 右侧：已有环境列表
        right_frame = ttk.Frame(self.root)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(0, 10), pady=10)

        ttk.Label(right_frame, text="已有虚拟环境:").pack(anchor=tk.W, pady=(0, 5))
        listbox_frame = ttk.Frame(right_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True)
        self.env_listbox = tk.Listbox(listbox_frame, selectmode=tk.SINGLE)
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=self.env_listbox.yview)
        self.env_listbox.config(yscrollcommand=scrollbar.set)
        self.env_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def log(self, message, error=False):
        self.log_text.config(state='normal')
        color = 'red' if error else 'black'
        self.log_text.insert(tk.END, message + "\n", ("error" if error else "normal"))
        self.log_text.tag_config("error", foreground="red")
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def run_conda_cmd(self, args):
        try:
            result = subprocess.run(
                ["conda"] + args,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=True,
                timeout=60
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            raise Exception("命令执行超时（超过 60 秒）")
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            stdout = e.stdout.strip() if e.stdout else ""
            msg = f"Conda 命令失败:\nSTDERR: {stderr}\nSTDOUT: {stdout}"
            raise Exception(msg)
        except FileNotFoundError:
            raise Exception("未找到 conda 命令，请确保 Anaconda 已正确安装并加入 PATH")

    def load_existing_envs(self):
        """启动后台线程加载环境列表"""
        self.log("正在加载已有环境列表...")
        self.env_listbox.delete(0, tk.END)
        self.env_listbox.insert(tk.END, "⏳ 加载中，请稍候...")

        thread = threading.Thread(target=self._load_envs_in_background, daemon=True)
        thread.start()

    def _load_envs_in_background(self):
        try:
            # 1. 获取所有环境路径
            output = self.run_conda_cmd(["env", "list", "--json"])
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

            # 2. 构建环境名和路径映射
            env_names = []
            name_to_path = {}
            for path in env_paths:
                if path == base_path:
                    continue
                name = path.split("\\")[-1] if "\\" in path else path.split("/")[-1]
                env_names.append(name)
                name_to_path[name] = path

            # 3. 查询每个环境的 Python 版本（直接调用 python.exe，更快更安全）
            python_versions = {}
            for name in env_names:
                path = name_to_path[name]
                # 构造 python 可执行文件路径
                if os.name == 'nt':  # Windows
                    python_exe = os.path.join(path, "python.exe")
                else:  # macOS / Linux
                    python_exe = os.path.join(path, "bin", "python")

                if os.path.exists(python_exe):
                    try:
                        result = subprocess.run(
                            [python_exe, "--version"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0 and result.stdout.startswith("Python "):
                            version = result.stdout.strip()[7:].split()[0]  # 如 "3.12"
                            python_versions[name] = version
                        else:
                            python_versions[name] = "未知"
                    except Exception:
                        python_versions[name] = "无法获取"
                else:
                    python_versions[name] = "无 Python"

            # 4. 回到主线程更新 UI
            def update_ui():
                self.env_listbox.delete(0, tk.END)
                for name in sorted(env_names):
                    version = python_versions.get(name, "未知")
                    display_text = f"{name} (Python {version})"
                    self.env_listbox.insert(tk.END, display_text)
                self.log(f"✅ 成功加载 {len(env_names)} 个已有环境")

            self.root.after(0, update_ui)

        except Exception as e:
            def show_error():
                self.env_listbox.delete(0, tk.END)
                self.env_listbox.insert(tk.END, "❌ 加载失败")
                self.log(f"❌ 加载已有环境失败: {str(e)}", error=True)
            self.root.after(0, show_error)

    def create_env(self):
        env_name = self.name_entry.get().strip()
        python_version = self.version_var.get()

        if not env_name:
            messagebox.showwarning("输入错误", "请输入环境名称！")
            return

        if env_name in self.existing_envs:
            messagebox.showwarning("名称冲突", f"环境 '{env_name}' 已存在！")
            return

        confirm = messagebox.askyesno("确认创建", f"确定要创建环境吗？\n名称: {env_name}\nPython: {python_version}")
        if not confirm:
            return

        self.create_btn.config(state='disabled')
        self.refresh_btn.config(state='disabled')

        thread = threading.Thread(
            target=self._create_env_in_background,
            args=(env_name, python_version),
            daemon=True
        )
        thread.start()

    def _create_env_in_background(self, env_name, python_version):
        try:
            self.run_conda_cmd(["create", "--name", env_name, f"python={python_version}", "--yes"])
            self.root.after(0, lambda: self.log(f"✅ 环境 '{env_name}' 创建成功！"))
            self.root.after(0, self.load_existing_envs)  # 刷新列表
        except Exception as e:
            self.root.after(0, lambda: self.log(f"❌ 创建失败: {str(e)}", error=True))
        finally:
            self.root.after(0, lambda: self.create_btn.config(state='normal'))
            self.root.after(0, lambda: self.refresh_btn.config(state='normal'))


