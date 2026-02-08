"""
Anaconda 虚拟环境管理器（GUI 版）
功能：
  - 列出所有非 base 环境
  - 勾选要删除的环境
  - 一键安全删除
  - 实时显示操作日志
  - 删除单个环境：conda remove -n name_env --all -y
  - 删除多个环境：conda remove -n name_env -n name_env1 -n name_env2 --all -y
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import sys
import json
import threading


class CondaEnvManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Conda 虚拟环境管理器")
        self.root.geometry("700x500")
        self.root.minsize(600, 400)

        # 存储环境列表
        self.envs = []
        self.check_vars = []

        self.create_widgets()
        self.load_envs()

    def create_widgets(self):
        # 顶部按钮
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=5)

        self.refresh_btn = ttk.Button(top_frame, text="🔄 刷新环境列表", command=self.load_envs)
        self.refresh_btn.pack(side=tk.LEFT)

        self.delete_btn = ttk.Button(top_frame, text="🗑️ 删除选中环境", command=self.delete_selected)
        self.delete_btn.pack(side=tk.RIGHT)

        # 环境列表区域
        list_frame = ttk.LabelFrame(self.root, text="虚拟环境列表（base 环境已自动排除）")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Canvas + Scrollbar 支持滚动
        canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 日志区域
        log_frame = ttk.LabelFrame(self.root, text="操作日志")
        log_frame.pack(fill=tk.BOTH, expand=False, padx=10, pady=5, ipady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def log(self, message, error=False):
        self.log_text.config(state='normal')
        color = 'red' if error else 'black'
        self.log_text.insert(tk.END, message + "\n", color)
        self.log_text.tag_config('red', foreground='red')
        self.log_text.tag_config('black', foreground='black')
        self.log_text.see(tk.END)
        self.log_text.config(state='disabled')

    def run_conda_cmd(self, args):
        try:
            result = subprocess.run(
                ["conda"] + args,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # 关键！替换非法字符
                check=True,
                timeout=30
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            stdout = e.stdout.strip() if e.stdout else ""
            msg = f"Conda 命令失败\nSTDOUT: {stdout}\nSTDERR: {stderr}"
            raise Exception(msg)
        except FileNotFoundError:
            raise Exception("未找到 conda 命令")

    def get_conda_envs(self):
        # 只使用 conda env list --json，更简洁可靠
        try:
            output = self.run_conda_cmd(["env", "list", "--json"])
            # 安全清理输出
            output = output.strip()
            if output.startswith('\ufeff'):  # 移除 UTF-8 BOM
                output = output[1:]
            # 尝试修复常见问题：移除末尾多余内容（如 conda 的警告）
            if '}' in output:
                last_brace = output.rfind('}')
                if last_brace != -1:
                    output = output[:last_brace + 1]
            data = json.loads(output)
            env_paths = data["envs"]
        except json.JSONDecodeError as e:
            # 调试：打印前 200 和后 200 字符
            snippet = output[:200] + "..." + output[-200:] if len(output) > 400 else output
            raise Exception(f"JSON 解析失败（位置 {e.pos}）:\n{snippet}")

        # 获取 base 路径（通常是第一个）
        base_path = None
        for path in env_paths:
            if "envs" not in path.replace("\\", "/").split("/"):
                base_path = path
                break
        if not base_path:
            base_path = env_paths[0] if env_paths else ""

        # 构建环境列表（跳过 base）
        envs = []
        for path in env_paths:
            if path == base_path:
                continue
            name = path.split("\\")[-1] if "\\" in path else path.split("/")[-1]
            envs.append({"name": name, "path": path})
        return envs

    def load_envs(self):
        self.log("正在加载 Conda 环境列表...")
        try:
            self.envs = self.get_conda_envs()
            self.display_envs()
            self.log(f"✅ 成功加载 {len(self.envs)} 个虚拟环境")
        except Exception as e:
            self.log(f"❌ 加载失败: {str(e)}", error=True)
            messagebox.showerror("错误", f"无法加载环境列表:\n{str(e)}")

    def display_envs(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.check_vars.clear()

        if not self.envs:
            label = ttk.Label(self.scrollable_frame, text="暂无虚拟环境", foreground="gray")
            label.pack(pady=20)
            return

        for env in self.envs:
            # ✅ 显式设置为 False，确保初始为空白
            var = tk.BooleanVar(value=False)
            self.check_vars.append(var)

            frame = ttk.Frame(self.scrollable_frame)
            frame.pack(fill=tk.X, padx=5, pady=2)

            # 使用 ttk.Checkbutton，它会自动显示 ✓ 或 ☐
            cb = ttk.Checkbutton(frame, text=f"{env['name']}", variable=var)
            cb.pack(side=tk.LEFT)

            path_label = ttk.Label(frame, text=env['path'], foreground="gray", font=("Arial", 8))
            path_label.pack(side=tk.LEFT, padx=(10, 0))

    def delete_selected(self):
        selected = [
            env for env, var in zip(self.envs, self.check_vars) if var.get()
        ]
        if not selected:
            messagebox.showwarning("提示", "请先勾选要删除的环境！")
            return

        msg = f"确定要删除以下 {len(selected)} 个环境吗？\n\n" + \
              "\n".join([env['name'] for env in selected])
        if not messagebox.askyesno("确认删除", msg):
            return

        # 在后台线程执行删除，避免界面卡死
        thread = threading.Thread(target=self._delete_in_background, args=(selected,))
        thread.daemon = True
        thread.start()

    def _delete_in_background(self, selected_envs):
        self.root.after(0, lambda: self.delete_btn.config(state='disabled'))
        self.root.after(0, lambda: self.refresh_btn.config(state='disabled'))

        for env in selected_envs:
            self.root.after(0, lambda e=env: self.log(f"正在删除 {e['name']} ..."))
            try:
                self.run_conda_cmd(["env", "remove", "--name", env["name"], "--yes"])
                self.root.after(0, lambda e=env: self.log(f"✅ {e['name']} 删除成功"))
            except Exception as e:
                self.root.after(0, lambda e=env, err=str(e): self.log(f"❌ {e['name']} 删除失败: {err}", error=True))

        self.root.after(0, self.load_envs)
        self.root.after(0, lambda: self.delete_btn.config(state='normal'))
        self.root.after(0, lambda: self.refresh_btn.config(state='normal'))


