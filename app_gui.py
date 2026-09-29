import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import sys
import subprocess
import os
import logging
from database import DatabaseManager
from main import LicensePlateSystem
import network_manager


class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)

        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.configure(state='disabled')
            self.text_widget.yview(tk.END)

        self.text_widget.after(0, append)


class AdminDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("VisionGate - Control Panel")
        self.root.geometry("1050x750")

        self.db = DatabaseManager()
        self.system = LicensePlateSystem()
        self._timer_id = None
        self._live_loop_id = None
        self.wifi_active = True

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill='both')

        self.tab_control = ttk.Frame(self.notebook)
        self.tab_plates = ttk.Frame(self.notebook)
        self.tab_users = ttk.Frame(self.notebook)
        self.tab_logs = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_control, text=" Control Panel ")
        self.notebook.add(self.tab_plates, text=" Plates Database ")
        self.notebook.add(self.tab_users, text=" Mobile Users ")
        self.notebook.add(self.tab_logs, text=" Full History ")

        self.build_control_tab()
        self.build_plates_tab()
        self.build_users_tab()
        self.build_logs_tab()

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.system.running = True
        self.system_thread = threading.Thread(target=self.system.run, daemon=True)
        self.system_thread.start()

        self.gui_live_update_loop()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def build_control_tab(self):
        status_frame = tk.Frame(self.tab_control)
        status_frame.pack(pady=5)
        self.lbl_status = tk.Label(status_frame, text="System Status: INACTIVE", font=("Arial", 16, "bold"), fg="red")
        self.lbl_status.pack()

        wifi_frame = tk.Frame(status_frame)
        wifi_frame.pack(pady=5)
        self.lbl_wifi_status = tk.Label(wifi_frame, text="TCP Server: Waiting...", font=("Arial", 12), fg="gray")
        self.lbl_wifi_status.pack(side=tk.LEFT, padx=10)

        self.btn_wifi_toggle = tk.Button(wifi_frame, text="Stop Wi-Fi Hotspot", bg="#c0392b", fg="white",
                                         font=("Arial", 10, "bold"), command=self.toggle_wifi_mode)
        self.btn_wifi_toggle.pack(side=tk.LEFT, padx=10)

        self.lbl_clients = tk.Label(wifi_frame, text="Connected IPs: None", font=("Arial", 11, "bold"), fg="#2980b9")
        self.lbl_clients.pack(side=tk.LEFT, padx=10)

        btn_frame = tk.Frame(self.tab_control)
        btn_frame.pack(pady=5)

        self.btn_start = tk.Button(btn_frame, text="START AI SYSTEM", bg="green", fg="white",
                                   font=("Arial", 12, "bold"), command=self.start_system)
        self.btn_start.pack(side=tk.LEFT, padx=10)
        self.btn_stop = tk.Button(btn_frame, text="STOP AI SYSTEM", bg="darkred", fg="white",
                                  font=("Arial", 12, "bold"), state=tk.DISABLED, command=self.stop_system)
        self.btn_stop.pack(side=tk.LEFT, padx=10)

        manual_frame = tk.LabelFrame(self.tab_control, text=" Manual Barrier Control", font=("Arial", 12))
        manual_frame.pack(pady=5, padx=20, fill="x")

        row1 = tk.Frame(manual_frame)
        row1.pack(pady=5)
        tk.Label(row1, text="Time (sec):").pack(side=tk.LEFT)
        self.spin_time = tk.Spinbox(row1, from_=3, to=60, width=5, font=("Arial", 12))
        self.spin_time.pack(side=tk.LEFT, padx=5)

        self.btn_open_timed = tk.Button(row1, text="Open (Timed)", bg="#3498db", fg="white", font=("Arial", 10, "bold"),
                                        command=self.manual_open_timed)
        self.btn_open_timed.pack(side=tk.LEFT, padx=10)
        self.btn_open_perm = tk.Button(row1, text="Open Permanent", bg="#2980b9", fg="white",
                                       font=("Arial", 10, "bold"), command=self.manual_open_permanent)
        self.btn_open_perm.pack(side=tk.LEFT, padx=10)
        self.btn_close = tk.Button(row1, text="CLOSE NOW", bg="#e67e22", fg="white", font=("Arial", 10, "bold"),
                                   command=lambda: self.manual_close(auto=False))
        self.btn_close.pack(side=tk.LEFT, padx=10)

        self.lbl_barrier_status = tk.Label(manual_frame, text="Barrier is CLOSED!", font=("Consolas", 14, "bold"),
                                           fg="gray")
        self.lbl_barrier_status.pack(pady=5)

        logs_frame = tk.LabelFrame(self.tab_control, text=" Recent Access (Database) ", font=("Arial", 12))
        logs_frame.pack(pady=5, padx=20, fill="both", expand=True)

        self.tree_mini_logs = ttk.Treeview(logs_frame, columns=("time", "plate", "status", "action_by"),
                                           show="headings", height=4)
        for col, txt in zip(("time", "plate", "status", "action_by"),
                            ("Date & Time", "Plate", "Status", "Triggered By")):
            self.tree_mini_logs.heading(col, text=txt)
            self.tree_mini_logs.column(col, width=120)
        self.tree_mini_logs.pack(fill="both", expand=True, padx=5, pady=5)

        sys_console_frame = tk.LabelFrame(self.tab_control, text=" System Output (Live Console) ", font=("Arial", 12))
        sys_console_frame.pack(pady=5, padx=20, fill="both", expand=True)

        self.text_console = tk.Text(sys_console_frame, height=5, state='disabled', bg="black", fg="#00ff00",
                                    font=("Consolas", 10))
        self.text_console.pack(fill="both", expand=True, padx=5, pady=5)

        text_handler = TextHandler(self.text_console)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S'))
        logging.getLogger().addHandler(text_handler)

    def on_tab_changed(self, event):
        idx = self.notebook.index(self.notebook.select())
        if idx == 1:
            self.refresh_plates()
        elif idx == 2:
            self.refresh_users()
        elif idx == 3:
            self.refresh_logs()

    def gui_live_update_loop(self):
        try:
            if self.system.ai_active:
                self.lbl_status.config(text="System Status: ONLINE (Sensors Active)", fg="green")
                self.btn_start.config(state=tk.DISABLED)
                self.btn_stop.config(state=tk.NORMAL)
            else:
                self.lbl_status.config(text="System Status: INACTIVE (AI Paused)", fg="red")
                self.btn_start.config(state=tk.NORMAL)
                self.btn_stop.config(state=tk.DISABLED)

            if hasattr(self.system, 'wifi_server') and getattr(self.system.wifi_server, 'running', False):
                self.lbl_wifi_status.config(text="TCP Server: LISTENING", fg="#27ae60")
            else:
                self.lbl_wifi_status.config(text="TCP Server: OFFLINE", fg="red")

            if self.wifi_active:
                try:
                    output = subprocess.check_output("ip neigh | grep '192.168.4.'", shell=True).decode()
                    ips = [line.split()[0] for line in output.split('\n') if
                           line and ('REACHABLE' in line or 'STALE' in line)]
                    if ips:
                        self.lbl_clients.config(text=f"Connected IPs: {', '.join(set(ips))}")
                    else:
                        self.lbl_clients.config(text="Connected IPs: None")
                except:
                    self.lbl_clients.config(text="Connected IPs: Scanning...")
            else:
                self.lbl_clients.config(text="Connected IPs: Hotspot Offline")

            recent_logs = self.db.get_logs(limit=5)
            self.tree_mini_logs.delete(*self.tree_mini_logs.get_children())
            for l in recent_logs:
                self.tree_mini_logs.insert("", "end", values=(l['time'], l['plate'], l['status'], l['action_by']))
        except Exception:
            pass
        self._live_loop_id = self.root.after(2000, self.gui_live_update_loop)

    def toggle_wifi_mode(self):
        if self.wifi_active:
            try:
                subprocess.run(["nmcli", "connection", "down", "Hotspot"], check=True)
                self.wifi_active = False
                self.btn_wifi_toggle.config(text="Start Wi-Fi Hotspot", bg="#27ae60")
                logging.getLogger(__name__).info("Wi-Fi Hotspot DISABLED manually.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to stop Hotspot: {e}")
        else:
            try:
                subprocess.run(["nmcli", "connection", "up", "Hotspot"], check=True)
                self.wifi_active = True
                self.btn_wifi_toggle.config(text="Stop Wi-Fi Hotspot", bg="#c0392b")
                logging.getLogger(__name__).info("Wi-Fi Hotspot ENABLED manually.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to start Hotspot: {e}")

    def start_system(self):
        self.system.ai_active = True
        if hasattr(self.system.lcd, 'turn_on'): self.system.lcd.turn_on()
        self.system.lcd.clear_and_write("VisionGate", "Waiting for car")
        logging.getLogger(__name__).info("AI System ENABLED via PC Dashboard")

    def stop_system(self):
        self.system.ai_active = False
        if hasattr(self.system.lcd, 'turn_off'): self.system.lcd.turn_off()
        logging.getLogger(__name__).info("AI System DISABLED via PC Dashboard")

    def build_plates_tab(self):
        list_frame = tk.LabelFrame(self.tab_plates, text=" Registered Plates ", font=("Arial", 11))
        list_frame.pack(pady=10, padx=10, fill="both", expand=True)

        self.plates_canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.plates_canvas.yview)
        self.plates_inner_frame = ttk.Frame(self.plates_canvas)

        self.plates_inner_frame.bind(
            "<Configure>",
            lambda e: self.plates_canvas.configure(scrollregion=self.plates_canvas.bbox("all"))
        )

        self.plates_canvas.create_window((0, 0), window=self.plates_inner_frame, anchor="nw")
        self.plates_canvas.configure(yscrollcommand=scrollbar.set)

        self.plates_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")

        form = tk.Frame(self.tab_plates)
        form.pack(pady=10)
        tk.Label(form, text="Plate:").pack(side=tk.LEFT, padx=5)
        self.ent_plate = tk.Entry(form, width=15)
        self.ent_plate.pack(side=tk.LEFT, padx=5)
        tk.Label(form, text="Owner:").pack(side=tk.LEFT, padx=5)
        self.cmb_owner = ttk.Combobox(form, width=18)
        self.cmb_owner.pack(side=tk.LEFT, padx=5)
        tk.Button(form, text="Add New Plate", bg="#27ae60", fg="white", font=("Arial", 9, "bold"),
                  command=self.add_plate_gui).pack(side=tk.LEFT, padx=10)

    def build_users_tab(self):
        form = tk.LabelFrame(self.tab_users, text=" Add New User ", font=("Arial", 11))
        form.pack(pady=10, padx=10, fill="x")
        tk.Label(form, text="User:").pack(side=tk.LEFT, padx=5)
        self.ent_user = tk.Entry(form, width=15)
        self.ent_user.pack(side=tk.LEFT, padx=5)
        tk.Label(form, text="Pass:").pack(side=tk.LEFT, padx=5)
        self.ent_pass = tk.Entry(form, width=15, show="*")
        self.ent_pass.pack(side=tk.LEFT, padx=5)
        self.cmb_role = ttk.Combobox(form, values=["USER", "ADMIN"], width=8, state="readonly")
        self.cmb_role.current(0)
        self.cmb_role.pack(side=tk.LEFT, padx=5)
        tk.Button(form, text="Add User", bg="#27ae60", fg="white", command=self.add_user_gui).pack(side=tk.LEFT,
                                                                                                   padx=20, pady=5)

        list_frame = tk.LabelFrame(self.tab_users, text=" Manage Users ", font=("Arial", 11))
        list_frame.pack(pady=5, padx=10, fill="both", expand=True)
        self.users_canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.users_canvas.yview)
        self.users_inner_frame = ttk.Frame(self.users_canvas)
        self.users_inner_frame.bind("<Configure>",
                                    lambda e: self.users_canvas.configure(scrollregion=self.users_canvas.bbox("all")))
        self.users_canvas.create_window((0, 0), window=self.users_inner_frame, anchor="nw")
        self.users_canvas.configure(yscrollcommand=scrollbar.set)
        self.users_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")
        self.refresh_users()

    def build_logs_tab(self):
        container = tk.Frame(self.tab_logs)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree_logs = ttk.Treeview(container, columns=("time", "plate", "status", "action_by", "image_path"),
                                      show="headings")
        for c, t in zip(("time", "plate", "status", "action_by", "image_path"),
                        ("Date & Time", "Plate", "Status", "Triggered By", "Image Path")):
            self.tree_logs.heading(c, text=t)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.tree_logs.yview)
        self.tree_logs.configure(yscrollcommand=scrollbar.set)
        self.tree_logs.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tree_logs.bind("<Double-1>", self.open_image_viewer)

    def open_image_viewer(self, event):
        sel = self.tree_logs.selection()
        if sel:
            img_path = self.tree_logs.item(sel[0])['values'][4]
            if img_path and img_path != 'None' and os.path.exists(img_path):
                try:
                    os.startfile(img_path) if sys.platform == "win32" else subprocess.run(["xdg-open", img_path])
                except:
                    pass

    def manual_open_timed(self):
        self.cancel_timer()
        self.system.servo.open_barrier()
        self.countdown_step(int(self.spin_time.get()))

    def countdown_step(self, seconds_left):
        if seconds_left > 0:
            self.lbl_barrier_status.config(text=f"OPEN. Closing in: {seconds_left}s", fg="#2980b9")
            self._timer_id = self.root.after(1000, self.countdown_step, seconds_left - 1)
        else:
            self.manual_close(auto=True)

    def manual_open_permanent(self):
        self.cancel_timer()
        self.system.servo.open_barrier()
        self.lbl_barrier_status.config(text="PERMANENTLY OPEN", fg="green")

    def manual_close(self, auto=False):
        self.cancel_timer()
        try:
            if self.system.ultrasonic.get_distance() < 15:
                self.lbl_barrier_status.config(text="OBSTRUCTION!", fg="red")
                if auto: self._timer_id = self.root.after(2000, lambda: self.manual_close(auto=True))
                return
        except:
            pass
        self.system.servo.close_barrier()
        self.lbl_barrier_status.config(text="CLOSED", fg="gray")

    def cancel_timer(self):
        if self._timer_id:
            self.root.after_cancel(self._timer_id)
            self._timer_id = None

    def refresh_plates(self):
        for widget in self.plates_inner_frame.winfo_children():
            widget.destroy()

        all_users = [u['username'] for u in self.db.get_all_users()]
        self.cmb_owner['values'] = all_users
        if all_users and not self.cmb_owner.get():
            self.cmb_owner.current(0)

        header = tk.Frame(self.plates_inner_frame)
        header.pack(fill="x", pady=5)
        tk.Label(header, text="Plate Number", width=20, anchor="w", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(header, text="Owner", width=20, anchor="w", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(header, text="Added By", width=15, anchor="w", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(header, text="Actions", width=20, anchor="center", font=("Arial", 10, "bold")).pack(side=tk.LEFT)

        for p in self.db.get_all_plates():
            row = tk.Frame(self.plates_inner_frame)
            row.pack(fill="x", pady=2)

            tk.Label(row, text=p['plate'], width=20, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=p['owner'], width=20, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=p.get('added_by', 'ADMIN'), width=15, anchor="w").pack(side=tk.LEFT)

            btn_edit = tk.Button(row, text="Edit", bg="#3498db", fg="white", width=6,
                                 command=lambda plt=p['plate'], own=p['owner']: self.edit_plate_popup(plt, own))
            btn_edit.pack(side=tk.LEFT, padx=2)

            btn_del = tk.Button(row, text="Del", bg="#e74c3c", fg="white", width=6,
                                command=lambda plt=p['plate']: self.del_plate_direct(plt))
            btn_del.pack(side=tk.LEFT, padx=2)

    def add_plate_gui(self):
        plate = self.ent_plate.get()
        owner = self.cmb_owner.get()
        if not plate or not owner:
            messagebox.showwarning("Input Error", "Please provide a plate number and select an owner.")
            return
        self.db.add_plate(plate, owner, "PC_ADMIN")
        self.ent_plate.delete(0, tk.END)
        self.refresh_plates()

    def edit_plate_popup(self, old_plate, old_owner):
        new_plate = simpledialog.askstring("Edit Plate", f"Modify plate '{old_plate}':", initialvalue=old_plate)
        if not new_plate: return

        new_owner = simpledialog.askstring("Edit Owner", f"Modify owner for '{new_plate}':", initialvalue=old_owner)
        if not new_owner: return

        if hasattr(self.db, 'update_plate'):
            self.db.update_plate(old_plate, new_plate, new_owner)
            logging.getLogger(__name__).info(f"Plate updated: {old_plate} -> {new_plate}")
            self.refresh_plates()
        else:
            messagebox.showerror("Error", "update_plate method not found in database.py")

    def del_plate_direct(self, plate):
        if messagebox.askyesno("Confirm", f"Delete plate '{plate}' from database?"):
            self.db.delete_plate(plate)
            logging.getLogger(__name__).info(f"Plate deleted: {plate}")
            self.refresh_plates()

    def refresh_users(self):
        for widget in self.users_inner_frame.winfo_children(): widget.destroy()
        users = self.db.get_all_users()

        header_row = tk.Frame(self.users_inner_frame)
        header_row.pack(fill="x", pady=5)
        tk.Label(header_row, text="Username", width=15, anchor="w", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(header_row, text="Role", width=10, anchor="w", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(header_row, text="Status", width=10, anchor="w", font=("Arial", 10, "bold")).pack(side=tk.LEFT)
        tk.Label(header_row, text="Actions", width=30, anchor="center", font=("Arial", 10, "bold")).pack(side=tk.LEFT)

        for u in users:
            row = tk.Frame(self.users_inner_frame)
            row.pack(fill="x", pady=3)

            status_text = "BANNED" if u['is_banned'] == 1 else "ACTIVE"
            status_color = "red" if u['is_banned'] == 1 else "green"

            tk.Label(row, text=u['username'], width=15, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=u['role'], width=10, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=status_text, width=10, anchor="w", fg=status_color, font=("Arial", 9, "bold")).pack(
                side=tk.LEFT)

            btn_reset = tk.Button(row, text="Pass", bg="#f39c12", fg="white",
                                  command=lambda usr=u['username'], r=u['role']: self.reset_pass_direct(usr, r))
            btn_reset.pack(side=tk.LEFT, padx=2)

            btn_ban = tk.Button(row, text="Unban" if u['is_banned'] else "Ban",
                                bg="gray" if u['is_banned'] else "black", fg="white", command=lambda usr=u['username'],
                                                                                                     status=not bool(u[
                                                                                                                         'is_banned']): self.toggle_ban_direct(
                    usr, status))
            btn_ban.pack(side=tk.LEFT, padx=2)

            btn_del = tk.Button(row, text="Del", bg="#e74c3c", fg="white",
                                command=lambda usr=u['username']: self.del_user_direct(usr))
            btn_del.pack(side=tk.LEFT, padx=2)

            if u['username'].lower() == 'admin':
                btn_ban.config(state=tk.DISABLED)
                btn_del.config(state=tk.DISABLED)

    def add_user_gui(self):
        usr, pwd, rol = self.ent_user.get(), self.ent_pass.get(), self.cmb_role.get()
        if usr and pwd:
            self.db.add_user(usr, pwd, rol)
            self.ent_user.delete(0, tk.END)
            self.ent_pass.delete(0, tk.END)
            self.refresh_users()
            self.refresh_plates()

    def reset_pass_direct(self, username, role):
        new_pwd = simpledialog.askstring("Reset", f"New password for '{username}':", show='*')
        if new_pwd:
            self.db.add_user(username, new_pwd, role)
            messagebox.showinfo("Success", "Password updated!")

    def toggle_ban_direct(self, username, ban_status):
        self.db.toggle_user_ban(username, ban_status)
        self.refresh_users()

    def del_user_direct(self, username):
        if messagebox.askyesno("Confirm", f"Delete user '{username}'?"):
            self.db.delete_user(username)
            self.refresh_users()
            self.refresh_plates()

    def refresh_logs(self):
        self.tree_logs.delete(*self.tree_logs.get_children())
        for l in self.db.get_logs(limit=1000):
            self.tree_logs.insert("", "end",
                                  values=(l['time'], l['plate'], l['status'], l['action_by'], l['image_path']))

    def on_closing(self):
        self.cancel_timer()
        if self._live_loop_id:
            self.root.after_cancel(self._live_loop_id)
        if self.system:
            self.system.shutdown()

        self.root.destroy()


if __name__ == "__main__":
    import time
    try:
        network_manager.start_vision_gate_network()
    except Exception as e:
        print(f"Starting network error {e}")

    root = tk.Tk()
    app = AdminDashboard(root)

    try:
        root.mainloop()
    finally:
        print("Interface has been closed, the network will be restored")
        try:
            network_manager.restore_home_network()
        except Exception as e:
            print(f"Error restoring the network: {e}")