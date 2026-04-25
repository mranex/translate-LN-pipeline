import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import sys
import os
import json

class TranslationPipelineGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Light Novel Translation Pipeline FINAL - Control Panel")
        self.root.geometry("1150x800")
        
        # Thiết lập Dark Mode
        self.bg_color = "#1e1e1e"
        self.fg_color = "#d4d4d4"
        self.frame_bg = "#252526"
        self.btn_bg = "#333333"
        self.root.configure(bg=self.bg_color)
        
        self.refresh_job = None
        self.setup_ui()
        
        # Khởi tạo tiến độ ban đầu
        self.root.after(500, self.check_progress)
        self.start_auto_refresh()

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, foreground=self.fg_color, font=("Segoe UI", 10))
        style.configure("TButton", background=self.btn_bg, foreground=self.fg_color, font=("Segoe UI", 9))
        style.configure("Highlight.TButton", background="#005a9e", foreground="white", font=("Segoe UI", 9, "bold")) 
        style.configure("Editor.TButton", background="#0078d4", foreground="white", font=("Segoe UI", 10, "bold")) 
        style.map("TButton", background=[("active", "#4d4d4d")])
        style.map("Highlight.TButton", background=[("active", "#0062ad")])
        style.map("Editor.TButton", background=[("active", "#005a9e")])
        style.configure("TLabelframe", background=self.frame_bg, foreground=self.fg_color)
        style.configure("TLabelframe.Label", background=self.frame_bg, foreground="#569cd6", font=("Segoe UI", 10, "bold"))
        style.configure("TSeparator", background="#444444")

        # --- Top Frame: Input Volume & Utils ---
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(top_frame, text="Volume:").pack(side=tk.LEFT, padx=(0, 5))
        self.vol_entry = ttk.Entry(top_frame, width=8)
        self.vol_entry.pack(side=tk.LEFT, padx=5)
        self.vol_entry.insert(0, "1")
        
        ttk.Separator(top_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        
        ttk.Label(top_frame, text="Auto-refresh (s):").pack(side=tk.LEFT, padx=5)
        self.refresh_entry = ttk.Entry(top_frame, width=5)
        self.refresh_entry.pack(side=tk.LEFT, padx=5)
        self.refresh_entry.insert(0, "30")
        
        ttk.Button(top_frame, text="Cập nhật", command=self.start_auto_refresh).pack(side=tk.LEFT, padx=5)
        
        # Nút Mở Editor đưa lên trên cùng vì dùng chung cho mọi Phase
        ttk.Button(top_frame, text="📝 MỞ EDITOR FINAL", style="Editor.TButton", command=self.open_editor).pack(side=tk.LEFT, padx=20)
        
        ttk.Button(top_frame, text="🗑 Xoá log tiến độ", command=self.clear_progress_logs).pack(side=tk.RIGHT, padx=5)
        ttk.Button(top_frame, text="📊 Check Ngay", command=self.check_progress).pack(side=tk.RIGHT, padx=5)

        # --- Middle Frame: Control Buttons ---
        ctrl_frame = ttk.Frame(self.root)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=5)
        ctrl_frame.columnconfigure(0, weight=1)
        ctrl_frame.columnconfigure(1, weight=1)
        ctrl_frame.columnconfigure(2, weight=1)

        # ==========================================
        # Phase 1 & 2: Volume Canon Prep
        # ==========================================
        phase_1_2 = ttk.LabelFrame(ctrl_frame, text="Phase 1 & 2: Volume Canon")
        phase_1_2.grid(row=0, column=0, sticky="nsew", padx=5)
        
        ttk.Label(phase_1_2, text="-- Chuẩn bị Dữ liệu thô --").pack(pady=(5,2))
        ttk.Button(phase_1_2, text="1. Glossary Prep", command=lambda: self.run_cmd(f"python -m src.main glossary-prep --volumes {self.get_vol()}")).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(phase_1_2, text="2. Relationship Prep", command=lambda: self.run_cmd(f"python -m src.main relationship-prep --volume {self.get_vol()}")).pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Separator(phase_1_2, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Label(phase_1_2, text="-- Sau khi lưu Editor --").pack(pady=(2,2))
        ttk.Button(phase_1_2, text="3. Approve Glossary", command=lambda: self.run_cmd(f"python -m src.main approve-glossary --volume {self.get_vol()} --overwrite")).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(phase_1_2, text="4. Approve Relationships", command=lambda: self.run_cmd(f"python -m src.main approve-relationships --volume {self.get_vol()} --overwrite")).pack(fill=tk.X, padx=5, pady=2)

        # ==========================================
        # Phase 1C -> 3B: Segment Data & Labeling
        # ==========================================
        phase_seg = ttk.LabelFrame(ctrl_frame, text="Phase 1C-3B: Segment & Labeling")
        phase_seg.grid(row=0, column=1, sticky="nsew", padx=5)
        
        ttk.Label(phase_seg, text="-- Phân bổ dữ liệu Segment --").pack(pady=(5,2))
        ttk.Button(phase_seg, text="1. Build Segment Glossary", command=lambda: self.run_cmd(f"python -m src.main build-segment-glossary --volume {self.get_vol()}")).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(phase_seg, text="2. Build Segment Pronouns", command=lambda: self.run_cmd(f"python -m src.main build-segment-pronouns --volume {self.get_vol()}")).pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Separator(phase_seg, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Label(phase_seg, text="-- Ngữ cảnh & Dán nhãn thoại --").pack(pady=(2,2))
        ttk.Button(phase_seg, text="3. Build Context", command=lambda: self.run_cmd(f"python -m src.main build-context --volume {self.get_vol()}")).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(phase_seg, text="4. Label Dialogue (AI)", style="Highlight.TButton", command=lambda: self.run_cmd(f"python -m src.main label-dialogue --volume {self.get_vol()}")).pack(fill=tk.X, padx=5, pady=2)

        # ==========================================
        # Phase 4: Translate & QA Optional
        # ==========================================
        phase_4 = ttk.LabelFrame(ctrl_frame, text="Phase 4: Translate & Assemble")
        phase_4.grid(row=0, column=2, sticky="nsew", padx=5)
        
        ttk.Button(phase_4, text="▶ RUN FULL TRANSLATION FLOW", style="Highlight.TButton", command=lambda: self.run_cmd(f"python -m src.main run-translation --volume {self.get_vol()}")).pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(phase_4, text="(Hoặc chạy lẻ từng bước)").pack(pady=(2,2))
        ttk.Button(phase_4, text="1. Translate", command=lambda: self.run_cmd(f"python -m src.main translate --volume {self.get_vol()}")).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(phase_4, text="2. Assemble", command=lambda: self.run_cmd(f"python -m src.main assemble --volume {self.get_vol()}")).pack(fill=tk.X, padx=5, pady=2)
        
        ttk.Separator(phase_4, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5, pady=8)
        
        ttk.Label(phase_4, text="-- QA/Fix Optional --").pack(pady=(2,2))
        ttk.Button(phase_4, text="QA Segment", command=lambda: self.run_cmd(f"python -m src.main qa --volume {self.get_vol()}")).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(phase_4, text="Fix Segment", command=lambda: self.run_cmd(f"python -m src.main fix --volume {self.get_vol()}")).pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(phase_4, text="Assemble (Fixed)", command=lambda: self.run_cmd(f"python -m src.main assemble --volume {self.get_vol()} --fixed")).pack(fill=tk.X, padx=5, pady=2)

        # --- Bottom Frame: Console Output ---
        log_frame = ttk.LabelFrame(self.root, text="System Log & Output")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.console = scrolledtext.ScrolledText(log_frame, bg="#1e1e1e", fg="#ce9178", font=("Consolas", 10), wrap=tk.WORD)
        self.console.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.console.tag_config("progress_tag", foreground="#4ec9b0") 

    def get_vol(self):
        val = self.vol_entry.get().strip()
        return val if val else "1"

    def log_message(self, message, is_progress=False):
        tag = "progress_tag" if is_progress else None
        self.console.insert(tk.END, message, tag)
        self.console.see(tk.END)

    def clear_progress_logs(self):
        self.console.config(state=tk.NORMAL)
        self.console.tag_remove("progress_tag", "1.0", tk.END) 
        ranges = self.console.tag_ranges("progress_tag")
        for i in range(len(ranges)-2, -1, -2):
            self.console.delete(ranges[i], ranges[i+1])
        self.log_message("\n[HỆ THỐNG] Đã dọn dẹp log tiến độ.\n")

    def start_auto_refresh(self):
        if self.refresh_job:
            self.root.after_cancel(self.refresh_job)
        try:
            sec = int(self.refresh_entry.get().strip())
            if sec < 5: sec = 5 
        except:
            sec = 30
            
        def loop():
            self.check_progress()
            self.refresh_job = self.root.after(sec * 1000, loop)
            
        loop()

    def run_cmd(self, cmd):
        self.log_message(f"\n[{'='*60}]\n>>> LỆNH: {cmd}\n[{'='*60}]\n")
        
        def task():
            try:
                process = subprocess.Popen(
                    cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8'
                )
                for line in process.stdout:
                    self.root.after(0, self.log_message, line)
                process.wait()
                self.root.after(0, self.log_message, f"\n[X] Hoàn thành lệnh. Mã thoát: {process.returncode}\n")
                self.root.after(500, self.check_progress)
            except Exception as e:
                self.root.after(0, self.log_message, f"\n[LỖI]: {str(e)}\n")

        threading.Thread(target=task, daemon=True).start()

    def open_editor(self):
        """Mở Editor Final tại thư mục gốc (.) theo chuẩn mới"""
        editor_script = "ln_pipeline_final_editor.py"
        
        if not os.path.exists(editor_script):
            self.log_message(f"\n[LỖI] Không tìm thấy file '{editor_script}' trong thư mục hiện tại.\n")
            return
            
        # Gọi Editor với tham số '.' (current directory)
        cmd = f'"{sys.executable}" {editor_script} .'
        
        # Chạy trong background không block luồng UI
        subprocess.Popen(cmd, shell=True)
        self.log_message(f"\n[HỆ THỐNG] Đang mở {editor_script}...\n")

    def check_progress(self):
        file_path = "progress.json"
        if not os.path.exists(file_path): return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            updated_at = data.get("updated_at", "N/A").split(".")[0]
            completed = data.get("completed", {})

            report = f"\n--- 📊 BÁO CÁO TIẾN ĐỘ ({updated_at}) ---\n"
            for step, items in completed.items():
                count = len(items)
                sample = next(iter(items)) if items else ""
                unit = "segments" if "_" in sample else "volumes"
                report += f" • {step.upper().ljust(25)}: {count} {unit}\n"
            report += "-----------------------------------------------\n"
            
            self.log_message(report, is_progress=True)

        except:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = TranslationPipelineGUI(root)
    root.mainloop()