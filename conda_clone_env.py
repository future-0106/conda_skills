import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import sys
import os
import re
from pathlib import Path


def remove_ansi_escape(text: str) -> str:
    """移除 ANSI 转义序列（如 \x1b[32m, \x1b[0m）"""
    ansi_escape = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)


class CondaCloneApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📦 Conda 环境克隆工具")
        self.root.geometry("620x520")
        self.root.resizable(True, True)

        # 自动定位 conda 路径
        self.conda_exe = self.get_conda_exe_path()
        if not self.conda_exe or (not os.path.exists(self.conda_exe) and self.conda_exe != "conda"):
            messagebox.showerror("错误", "未找到 conda 命令！请确保 Conda 已正确安装。")
            self.root.destroy()
            return

        self.create_widgets()
        self.load_environments()

    def get_conda_exe_path(self):
        """自动推断 conda 可执行文件路径（兼容 Windows / macOS / Linux）"""
        python_exe = Path(sys.executable)

        # Windows: base 环境
        if sys.platform == "win32":
            if "envs" not in str(python_exe.parent):
                conda_exe = python_exe.parent / "Scripts" / "conda.exe"
            else:
                conda_root = python_exe.parent.parent.parent
                conda_exe = conda_root / "Scripts" / "conda.exe"
            if conda_exe.exists():
                return str(conda_exe)
        else:
            # Unix-like: base 环境
            if "envs" not in str(python_exe.parent):
                conda_exe = python_exe.parent / "bin" / "conda"
            else:
                conda_root = python_exe.parent.parent.parent
                conda_exe = conda_root / "bin" / "conda"
            if conda_exe.exists():
                return str(conda_exe)

        # 备用：依赖 PATH
        return "conda"

    def run_conda_cmd(self, args):
        """安全执行 conda 命令"""
        try:
            cmd = [self.conda_exe] + args
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return -1, "", str(e)

    def load_environments(self):
        """加载 Conda 环境列表（使用 --envs 避免颜色码）"""
        self.env_combo['values'] = ["加载中..."]
        self.root.update_idletasks()

        code, out, err = self.run_conda_cmd(["info", "--envs"])
        if code != 0:
            messagebox.showerror("错误", f"无法获取环境列表:\n{err}")
            self.env_combo['values'] = []
            return

        # 清理 ANSI（虽然 --envs 通常无颜色，但保险起见）
        clean_out = remove_ansi_escape(out)

        envs = []
        for line in clean_out.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if parts:
                    env_name = parts[0]
                    # 跳过 base（可选）
                    if env_name != "base":
                        envs.append(env_name)
        envs.sort()
        self.env_combo['values'] = envs if envs else ["无可用环境"]
        if envs:
            self.env_combo.current(0)
        else:
            self.env_var.set("无可用环境")

    def clone_environment(self):
        old_env = self.env_var.get().strip()
        new_env = self.new_name_var.get().strip()

        if old_env in ("加载中...", "无可用环境"):
            messagebox.showwarning("输入错误", "请选择一个有效的源环境！")
            return
        if not new_env:
            messagebox.showwarning("输入错误", "请输入新环境名称！")
            return
        if not self.is_valid_env_name(new_env):
            messagebox.showwarning(
                "输入错误",
                "环境名只能包含字母、数字、下划线、连字符或点（不能以点开头，且不能包含空格）"
            )
            return

        # 禁用按钮防止重复点击
        self.clone_btn.config(state="disabled")
        self.log_text.delete(1.0, tk.END)
        self.log_text.insert(tk.END, f"正在克隆环境 '{old_env}' → '{new_env}'...\n")
        self.root.update_idletasks()

        # 执行克隆命令
        code, out, err = self.run_conda_cmd([
            "create", "--name", new_env, "--clone", old_env, "--yes"
        ])

        if code == 0:
            self.log_text.insert(tk.END, "✅ 克隆成功！\n")
            messagebox.showinfo("成功", f"环境 '{new_env}' 已创建！")
            self.load_environments()  # 刷新列表
        else:
            self.log_text.insert(tk.END, "❌ 克隆失败！\n")
            if err.strip():
                self.log_text.insert(tk.END, f"错误: {err}\n")
            if out.strip():
                self.log_text.insert(tk.END, f"输出: {out}\n")
            messagebox.showerror("失败", "克隆失败，请查看下方日志。")

        self.clone_btn.config(state="normal")

    @staticmethod
    def is_valid_env_name(name):
        """验证环境名是否合法"""
        if not name or name.startswith('.'):
            return False
        import re
        return re.fullmatch(r'[a-zA-Z0-9._-]+', name) is not None

    def create_widgets(self):
        # 源环境选择
        frame1 = ttk.Frame(self.root, padding="10")
        frame1.pack(fill=tk.X)

        ttk.Label(frame1, text="选择源环境:", font=("Microsoft YaHei", 10)).pack(anchor=tk.W)
        self.env_var = tk.StringVar()
        self.env_combo = ttk.Combobox(frame1, textvariable=self.env_var, state="readonly", width=50)
        self.env_combo.pack(pady=5, fill=tk.X)

        # 新环境名称
        frame2 = ttk.Frame(self.root, padding="10")
        frame2.pack(fill=tk.X)

        ttk.Label(frame2, text="新环境名称:", font=("Microsoft YaHei", 10)).pack(anchor=tk.W)
        self.new_name_var = tk.StringVar()
        ttk.Entry(frame2, textvariable=self.new_name_var, width=50).pack(pady=5, fill=tk.X)

        # 克隆按钮
        frame3 = ttk.Frame(self.root, padding="10")
        frame3.pack(fill=tk.X)
        self.clone_btn = ttk.Button(frame3, text="🚀 克隆环境", command=self.clone_environment)
        self.clone_btn.pack(pady=10)

        # 日志区域
        frame4 = ttk.Frame(self.root, padding="10")
        frame4.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame4, text="操作日志:", font=("Microsoft YaHei", 10)).pack(anchor=tk.W)
        self.log_text = scrolledtext.ScrolledText(
            frame4, height=10, wrap=tk.WORD,
            font=("Consolas", 9), bg="#f8f8f8"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # 底部提示
        ttk.Label(
            self.root,
            text="注意：不要克隆当前正在使用的环境 | 支持中文环境名（不推荐）",
            foreground="gray",
            font=("Microsoft YaHei", 8)
        ).pack(side=tk.BOTTOM, pady=5)


# if __name__ == "__main__":
#     root = tk.Tk()
#     # 设置高 DPI 兼容（Windows）
#     try:
#         from ctypes import windll
#
#         windll.shcore.SetProcessDpiAwareness(1)
#     except:
#         pass
#     app = CondaCloneApp(root)
#     root.mainloop()