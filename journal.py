import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import simpledialog
from tkinter import filedialog
import os
import shutil
from datetime import datetime
import subprocess
import re
import json
import platformdirs

APP_NAME = "Journa1.0"
APP_AUTHOR = "Journa"
USER_DATA_DIR = platformdirs.user_data_dir(APP_NAME, APP_AUTHOR)
SETTINGS_FILE = os.path.join(USER_DATA_DIR, "settings.json")
PREFS_FILE = os.path.join(USER_DATA_DIR, "prefs.json")

os.makedirs(USER_DATA_DIR, exist_ok=True)


class JournalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Journa")
        self.root.geometry("800x600")

        # Set application icon if available
        icon_path = "journa.ico"
        if os.path.exists(icon_path):
            try:
                self.root.iconbitmap(icon_path)
                self.root.iconbitmap(default=icon_path)
            except tk.TclError:
                pass  # Skip if icon cannot be set

        # Migrate old preferences if necessary
        old_prefs = ".prefs.json"
        if os.path.exists(old_prefs) and not os.path.exists(PREFS_FILE):
            shutil.move(old_prefs, PREFS_FILE)

        # Load preferences (opacity)
        self.saved_alpha = 0.95
        if os.path.exists(PREFS_FILE):
            try:
                with open(PREFS_FILE, "r") as f:
                    data = json.load(f)
                    self.saved_alpha = data.get("opacity", 0.95)
            except (json.JSONDecodeError, IOError):
                pass

        # Set initial window opacity
        self.root.attributes('-alpha', self.saved_alpha)

        # Dark mode colors
        self.bg_color = "#2b2b2b"
        self.fg_color = "#ffffff"
        self.button_bg = "#3c3c3c"
        self.select_bg = "#4a4a4a"
        self.header_bg = "#1e1e1e"
        self.header_fg = "#dddddd"

        self.root.configure(bg=self.bg_color)

        # Migrate old Trunks directory if necessary
        old_trunk_root = "Trunks"
        self.default_trunk_root = os.path.join(USER_DATA_DIR, "Trunks")
        if os.path.exists(old_trunk_root) and not os.path.exists(self.default_trunk_root):
            if messagebox.askyesno("Migrate Old Data", "Found old Trunks in current directory. Move to AppData?"):
                shutil.move(old_trunk_root, self.default_trunk_root)

        # Load settings
        self.settings = self._load_settings()

        # Set trunk root based on settings
        self.trunk_root = os.path.join(self.settings.get("save_dir", USER_DATA_DIR), "Trunks")

        # Setup storage directories
        self._setup_storage()

        # Font defaults
        self.font_family = "Arial"
        self.font_size = 12

        # In-memory flag for unsaved notes
        self.in_memory = False

        # Current open file
        self.current_file = None

        # Autosave timer
        self.save_timer = None

        # Fullscreen state
        self.fullscreen = False

        # Drag and drop state
        self.dragged_item = None
        self.drag_start_y = None

        # Build UI components
        self._build_ui()

        # Bind events
        self._bind_events()

        # Load the treeview
        self.load_tree()

    def _load_settings(self):
        """Load application settings from JSON file."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"save_dir": USER_DATA_DIR}

    def _save_settings(self):
        """Save application settings to JSON file."""
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except IOError:
            messagebox.showerror("Error", "Failed to save settings.")

    def _setup_storage(self):
        """Setup the storage directories for trunks, journals, and unsaved notes."""
        os.makedirs(self.trunk_root, exist_ok=True)
        self.unsaved_trunk = os.path.join(self.trunk_root, "unsaved")
        os.makedirs(self.unsaved_trunk, exist_ok=True)
        self.unsaved_journal = os.path.join(self.unsaved_trunk, "notes")
        os.makedirs(self.unsaved_journal, exist_ok=True)
        self.unsaved_notes_dir = os.path.join(self.unsaved_journal, ".notes")
        os.makedirs(self.unsaved_notes_dir, exist_ok=True)

    def _build_ui(self):
        """Build the main UI components."""
        # Collapse button for left panel
        self.collapse_btn = tk.Button(self.root, text="<", command=self.toggle_left, bg=self.button_bg, fg=self.fg_color, width=2)
        self.collapse_btn.pack(side="left", fill="y")

        # Left panel (collapsible)
        self.left_frame = tk.Frame(self.root, bg=self.bg_color, width=250)
        self.left_frame.pack(side="left", fill="y")

        # Treeview style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=self.bg_color, foreground=self.fg_color, fieldbackground=self.bg_color, rowheight=25)
        style.map("Treeview", background=[('selected', self.select_bg)], foreground=[('selected', self.fg_color)])
        style.configure("Treeview.Heading", background=self.button_bg, foreground=self.fg_color)

        # Treeview for hierarchy
        self.tree = ttk.Treeview(self.left_frame, show="tree", style="Treeview")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        # Context menu
        self.menu = tk.Menu(self.root, tearoff=0)

        # Management buttons
        btn_frame = tk.Frame(self.left_frame, bg=self.bg_color)
        btn_frame.pack(fill="x", pady=5, padx=10)

        self.new_trunk_btn = tk.Button(btn_frame, text="New Trunk", command=self.new_trunk, bg=self.button_bg, fg=self.fg_color, padx=10, pady=5)
        self.new_trunk_btn.pack(side="left", padx=5)

        self.new_journal_btn = tk.Button(btn_frame, text="New Journal", command=self.new_journal, bg=self.button_bg, fg=self.fg_color, padx=10, pady=5)
        self.new_journal_btn.pack(side="left", padx=5)

        self.new_note_btn = tk.Button(btn_frame, text="New Note", command=self.new_note, bg=self.button_bg, fg=self.fg_color, padx=10, pady=5)
        self.new_note_btn.pack(side="left", padx=5)

        self.delete_btn = tk.Button(btn_frame, text="Delete", command=self.delete_item, bg=self.button_bg, fg=self.fg_color, padx=10, pady=5)
        self.delete_btn.pack(side="left", padx=5)

        # Right container
        self.right_container = tk.Frame(self.root, bg=self.bg_color)
        self.right_container.pack(side="left", fill="both", expand=True)

        # Header ribbon
        self.header_frame = tk.Frame(self.right_container, bg=self.header_bg, height=30)
        self.header_frame.pack(side="top", fill="x")

        # Header label for note name
        self.header_label = tk.Label(self.header_frame, text="Untitled", bg=self.header_bg, fg=self.header_fg, font=("Arial", 14, "bold"), padx=10)
        self.header_label.pack(side="left", pady=5)

        # Options toggle button
        self.options_toggle = tk.Button(self.header_frame, text="▼", command=self.toggle_options, bg=self.button_bg, fg=self.fg_color, width=2)
        self.options_toggle.pack(side="right")

        # Options frame (initially hidden)
        self.options_frame = tk.Frame(self.header_frame, bg=self.header_bg)

        opacity_label = tk.Label(self.options_frame, text="Opacity:", bg=self.header_bg, fg=self.header_fg)
        opacity_label.pack(side="left", padx=5)

        self.opacity_scale = tk.Scale(self.options_frame, from_=50, to=100, orient="horizontal", length=100, bg=self.header_bg, fg=self.header_fg, troughcolor=self.button_bg, command=self.set_opacity)
        self.opacity_scale.set(self.saved_alpha * 100)
        self.opacity_scale.pack(side="left")

        font_label = tk.Label(self.options_frame, text="Font:", bg=self.header_bg, fg=self.header_fg)
        font_label.pack(side="left", padx=5)

        self.font_combo = ttk.Combobox(self.options_frame, values=["Arial", "Times New Roman", "Courier New", "Verdana", "Helvetica"], state="readonly")
        self.font_combo.set(self.font_family)

        self.font_combo.pack(side="left", padx=5)

        size_label = tk.Label(self.options_frame, text="Size:", bg=self.header_bg, fg=self.header_fg)
        size_label.pack(side="left", padx=5)

        self.size_scale = tk.Scale(self.options_frame, from_=8, to=24, orient="horizontal", length=100, bg=self.header_bg, fg=self.header_fg, troughcolor=self.button_bg, command=self.change_font_size)
        self.size_scale.set(self.font_size)
        self.size_scale.pack(side="left")

        change_dir_btn = tk.Button(self.options_frame, text="Change Save Dir", command=self.change_save_dir, bg=self.button_bg, fg=self.fg_color)
        change_dir_btn.pack(side="left", padx=5)

        # Right writing panel
        self.right_frame = tk.Frame(self.right_container, bg=self.bg_color)
        self.right_frame.pack(side="top", fill="both", expand=True)

        self.text = tk.Text(self.right_frame, bg=self.bg_color, fg=self.fg_color, insertbackground=self.fg_color, font=(self.font_family, self.font_size), wrap="word", padx=10, pady=10)
        self.text.pack(fill="both", expand=True)

    def _bind_events(self):
        """Bind all necessary events."""
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Button-3>", self.popup)
        self.tree.bind("<Button-1>", self.start_drag)
        self.tree.bind("<B1-Motion>", self.on_drag)
        self.tree.bind("<ButtonRelease-1>", self.drop)
        self.text.bind("<KeyRelease>", self.schedule_save)
        self.root.bind("<F11>", self.toggle_fullscreen)
        self.root.bind("<FocusIn>", self.refresh_on_focus)
        self.font_combo.bind("<<ComboboxSelected>>", self.change_font_family)
        self.header_label.bind("<Double-Button-1>", self.rename_note)
        self.header_label.bind("<Button-3>", self.rename_note)

    def _save_prefs(self):
        """Save preferences to JSON file."""
        data = {"opacity": self.saved_alpha}
        try:
            with open(PREFS_FILE, "w") as f:
                json.dump(data, f)
        except IOError:
            pass  # Silently fail for now

    def change_save_dir(self):
        """Change the save directory and optionally migrate data."""
        old_trunk_root = self.trunk_root
        new_save_dir = filedialog.askdirectory(title="Select New Save Directory")
        if not new_save_dir:
            return
        new_trunk_root = os.path.join(new_save_dir, "Trunks")
        migrate = messagebox.askyesno("Migrate Data?", "Move existing data to the new location?")
        if migrate:
            os.makedirs(new_trunk_root, exist_ok=True)
            for item in os.listdir(old_trunk_root):
                src = os.path.join(old_trunk_root, item)
                dst = os.path.join(new_trunk_root, item)
                if os.path.exists(dst):
                    messagebox.showwarning("Conflict", f"Item {item} exists in target, skipping.")
                    continue
                try:
                    shutil.move(src, dst)
                except shutil.Error:
                    messagebox.showerror("Error", f"Failed to move {item}.")
        self.settings["save_dir"] = new_save_dir
        self._save_settings()
        self.trunk_root = new_trunk_root
        self._setup_storage()
        if self.current_file:
            if migrate:
                self.current_file = self.current_file.replace(old_trunk_root, new_trunk_root, 1)
            if not os.path.exists(self.current_file):
                if messagebox.askyesno("Keep Current Note?", "Current note not found in new location. Keep in memory?"):
                    self.in_memory = True
                    self.header_label.config(text=f"In-Memory: {self.header_label.cget('text')}")
                else:
                    self.current_file = None
                    self.text.delete("1.0", tk.END)
                    self.header_label.config(text="Untitled")
        self.load_tree()

    def change_font_family(self, event):
        """Change the font family of the text editor."""
        self.font_family = self.font_combo.get()
        self.text.config(font=(self.font_family, self.font_size))
        self._save_meta()

    def change_font_size(self, val):
        """Change the font size of the text editor."""
        self.font_size = int(float(val))
        self.text.config(font=(self.font_family, self.font_size))
        self._save_meta()

    def _meta_path(self):
        """Get the path to the metadata file for the current note."""
        if self.current_file:
            return self.current_file + ".meta"
        return None

    def _save_meta(self):
        """Save font metadata for the current note."""
        if self.current_file and not self.in_memory:
            meta_path = self._meta_path()
            data = {"font_family": self.font_family, "font_size": self.font_size}
            try:
                with open(meta_path, "w") as f:
                    json.dump(data, f)
            except IOError:
                pass

    def _load_meta(self):
        """Load font metadata for the current note."""
        if self.current_file:
            meta_path = self._meta_path()
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r") as f:
                        data = json.load(f)
                        self.font_family = data.get("font_family", "Arial")
                        self.font_size = data.get("font_size", 12)
                except (json.JSONDecodeError, IOError):
                    self.font_family = "Arial"
                    self.font_size = 12
            else:
                self.font_family = "Arial"
                self.font_size = 12
            self.text.config(font=(self.font_family, self.font_size))
            self.font_combo.set(self.font_family)
            self.size_scale.set(self.font_size)

    def get_item_type(self, iid):
        """Determine the type of the selected tree item (trunk, journal, note)."""
        if not iid:
            return None
        parent = self.tree.parent(iid)
        if not parent:
            return "trunk"
        elif self.tree.item(iid).get('values'):
            return "note"
        return "journal"

    def start_drag(self, event):
        """Start drag operation for notes."""
        iid = self.tree.identify_row(event.y)
        if iid and self.get_item_type(iid) == "note":
            self.dragged_item = iid
            self.drag_start_y = event.y

    def on_drag(self, event):
        """Placeholder for drag motion."""
        pass

    def drop(self, event):
        """Handle drop operation for moving notes between journals."""
        if not self.dragged_item or self.drag_start_y is None:
            return
        if abs(event.y - self.drag_start_y) <= 10:  # Drag threshold
            self.dragged_item = None
            self.drag_start_y = None
            return
        drop_iid = self.tree.identify_row(event.y)
        if not drop_iid or drop_iid == self.dragged_item:
            self.dragged_item = None
            self.drag_start_y = None
            return
        if self.get_item_type(self.dragged_item) != "note":
            self.dragged_item = None
            self.drag_start_y = None
            return
        drop_parent = self.tree.parent(drop_iid)
        if not drop_parent:  # Dropped on trunk
            self.dragged_item = None
            self.drag_start_y = None
            return
        drop_journal_iid = drop_parent if self.get_item_type(drop_iid) == "note" else drop_iid
        if self.tree.parent(drop_journal_iid) == "":  # Not a journal
            self.dragged_item = None
            self.drag_start_y = None
            return
        if self.tree.parent(self.dragged_item) == drop_journal_iid:
            self.dragged_item = None
            self.drag_start_y = None
            return
        self._move_note_to_journal(self.dragged_item, drop_journal_iid)
        self.dragged_item = None
        self.drag_start_y = None

    def _move_note_to_journal(self, note_iid, journal_iid):
        """Move a note to a different journal."""
        journal_item = self.tree.item(journal_iid)
        trunk_iid = self.tree.parent(journal_iid)
        trunk_item = self.tree.item(trunk_iid)
        src_file = self.tree.item(note_iid)['values'][0]
        src_dir = os.path.dirname(src_file)
        trunk_name = trunk_item['text'].lower().replace(" ", "_")
        journal_name = journal_item['text'].lower().replace(" ", "_")
        dest_dir = os.path.join(self.trunk_root, trunk_name, journal_name, ".notes")
        if src_dir == dest_dir:
            return
        base_file = os.path.basename(src_file)
        dest_file = os.path.join(dest_dir, base_file)
        base, ext = os.path.splitext(base_file)
        counter = 2
        new_base = base
        while os.path.exists(dest_file):
            new_base = f"{base}_{counter}"
            dest_file = os.path.join(dest_dir, new_base + ext)
            counter += 1
        try:
            shutil.move(src_file, dest_file)
            src_meta = src_file + ".meta"
            if os.path.exists(src_meta):
                shutil.move(src_meta, dest_file + ".meta")
            if self.current_file == src_file:
                self.current_file = dest_file
                if new_base != base:
                    new_display = self._format_display(new_base)
                    self.header_label.config(text=new_display)
        except shutil.Error:
            messagebox.showerror("Error", "Failed to move note.")
        self.load_tree()

    def refresh_on_focus(self, event):
        """Refresh tree and handle deleted files on window focus."""
        if event.widget != self.root:
            return
        if self.current_file and not os.path.exists(self.current_file) and not self.in_memory:
            if messagebox.askyesno("File Deleted", "The current note has been deleted from disk. Keep an in-memory version (unsaved)?"):
                self.in_memory = True
                self.header_label.config(text=f"In-Memory Note: {self.header_label.cget('text')}")
            else:
                self.text.delete("1.0", tk.END)
                self.current_file = None
                self.in_memory = False
                self.header_label.config(text="Untitled")
        self.load_tree()

    def _format_display(self, file_base):
        """Format file base name for display."""
        match = re.search(r"_(\d+)$", file_base)
        if match:
            num = match.group(1)
            try:
                num_int = int(num)
                if num_int < 100:
                    base_part = file_base[:match.start()]
                    base_display = base_part.replace("_", " ").title()
                    return f"{base_display} ({num_int})"
            except ValueError:
                pass
        return file_base.replace("_", " ").title()

    def popup(self, event):
        """Show context menu for tree items."""
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.menu.delete(0, tk.END)
            self.menu.add_command(label="Open in Explorer", command=self.open_location)
            item_type = self.get_item_type(iid)
            if item_type == "note":
                self.menu.add_command(label="Move to Journal...", command=self.move_note_context)
            elif item_type == "journal":
                self.menu.add_command(label="Move to Trunk...", command=self.move_journal_context)
            try:
                self.menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.menu.grab_release()

    def _get_target_journal(self):
        """Open dialog to select target journal for moving notes."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Target Journal")
        tree = ttk.Treeview(dialog, show="tree")
        tree.pack(fill="both", expand=True)
        for trunk_iid in self.tree.get_children():
            trunk_text = self.tree.item(trunk_iid)['text']
            new_trunk_id = tree.insert("", "end", text=trunk_text, open=False)
            for journal_iid in self.tree.get_children(trunk_iid):
                journal_text = self.tree.item(journal_iid)['text']
                tree.insert(new_trunk_id, "end", text=journal_text)
        target = None

        def ok():
            nonlocal target
            sel = tree.focus()
            if sel and tree.parent(sel) and not tree.get_children(sel):
                journal_text = tree.item(sel)['text']
                trunk_text = tree.item(tree.parent(sel))['text']
                target = (trunk_text, journal_text)
            dialog.destroy()

        tk.Button(dialog, text="OK", command=ok).pack(pady=10)
        dialog.grab_set()
        self.root.wait_window(dialog)
        return target

    def _get_target_trunk(self):
        """Open dialog to select target trunk for moving journals."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Target Trunk")
        tree = ttk.Treeview(dialog, show="tree")
        tree.pack(fill="both", expand=True)
        for trunk_iid in self.tree.get_children():
            trunk_text = self.tree.item(trunk_iid)['text']
            tree.insert("", "end", text=trunk_text)
        target = None

        def ok():
            nonlocal target
            sel = tree.focus()
            if sel and not tree.parent(sel) and not tree.get_children(sel):
                target = tree.item(sel)['text']
            dialog.destroy()

        tk.Button(dialog, text="OK", command=ok).pack(pady=10)
        dialog.grab_set()
        self.root.wait_window(dialog)
        return target

    def move_note_context(self):
        """Move selected note to another journal via context menu."""
        selected = self.tree.focus()
        if not selected or self.get_item_type(selected) != "note":
            return
        current_journal_id = self.tree.parent(selected)
        current_trunk_id = self.tree.parent(current_journal_id)
        current_trunk_text = self.tree.item(current_trunk_id)['text']
        current_journal_text = self.tree.item(current_journal_id)['text']
        target = self._get_target_journal()
        if not target:
            return
        target_trunk_text, target_journal_text = target
        if target_trunk_text == current_trunk_text and target_journal_text == current_journal_text:
            return
        target_trunk_name = target_trunk_text.lower().replace(" ", "_")
        target_journal_name = target_journal_text.lower().replace(" ", "_")
        dest_dir = os.path.join(self.trunk_root, target_trunk_name, target_journal_name, ".notes")
        src_file = self.tree.item(selected)['values'][0]
        src_dir = os.path.dirname(src_file)
        if src_dir == dest_dir:
            return
        base_file = os.path.basename(src_file)
        dest_file = os.path.join(dest_dir, base_file)
        base, ext = os.path.splitext(base_file)
        counter = 2
        new_base = base
        while os.path.exists(dest_file):
            new_base = f"{base}_{counter}"
            dest_file = os.path.join(dest_dir, new_base + ext)
            counter += 1
        try:
            shutil.move(src_file, dest_file)
            src_meta = src_file + ".meta"
            if os.path.exists(src_meta):
                shutil.move(src_meta, dest_file + ".meta")
            if self.current_file == src_file:
                self.current_file = dest_file
                if new_base != base:
                    new_display = self._format_display(new_base)
                    self.header_label.config(text=new_display)
        except shutil.Error:
            messagebox.showerror("Error", "Failed to move note.")
        self.load_tree()

    def move_journal_context(self):
        """Move selected journal to another trunk via context menu."""
        selected = self.tree.focus()
        if not selected or self.get_item_type(selected) != "journal":
            return
        current_trunk_id = self.tree.parent(selected)
        current_trunk_text = self.tree.item(current_trunk_id)['text']
        target_trunk_text = self._get_target_trunk()
        if not target_trunk_text or target_trunk_text == current_trunk_text:
            return
        journal_text = self.tree.item(selected)['text']
        journal_name = journal_text.lower().replace(" ", "_")
        target_trunk_name = target_trunk_text.lower().replace(" ", "_")
        dest_path = os.path.join(self.trunk_root, target_trunk_name, journal_name)
        if os.path.exists(dest_path):
            messagebox.showwarning("Warning", "Journal with same name exists in target trunk.")
            return
        current_trunk_name = current_trunk_text.lower().replace(" ", "_")
        src_path = os.path.join(self.trunk_root, current_trunk_name, journal_name)
        notes_path = os.path.join(src_path, ".notes")
        if self.current_file and os.path.dirname(self.current_file) == notes_path:
            self.save_current()
            self.current_file = None
            self.text.delete("1.0", tk.END)
            self.header_label.config(text="Untitled")
        try:
            shutil.move(src_path, dest_path)
        except shutil.Error:
            messagebox.showerror("Error", "Failed to move journal.")
        self.load_tree()

    def open_location(self):
        """Open the location of the selected item in file explorer."""
        selected = self.tree.focus()
        if not selected:
            return
        item_type = self.get_item_type(selected)
        item = self.tree.item(selected)
        if item_type == "note":
            file_path = item['values'][0]
            dir_path = os.path.dirname(file_path)
            if os.name == 'nt':
                subprocess.call(['explorer', '/select,', file_path])
            else:
                subprocess.call(['xdg-open', dir_path])
        elif item_type == "journal":
            journal_text = item['text']
            journal_name = journal_text.lower().replace(" ", "_")
            trunk_id = self.tree.parent(selected)
            trunk_text = self.tree.item(trunk_id)['text']
            trunk_name = trunk_text.lower().replace(" ", "_")
            dir_path = os.path.join(self.trunk_root, trunk_name, journal_name)
            if os.name == 'nt':
                os.startfile(dir_path)
            else:
                subprocess.call(['xdg-open', dir_path])
        elif item_type == "trunk":
            trunk_text = item['text']
            trunk_name = trunk_text.lower().replace(" ", "_")
            dir_path = os.path.join(self.trunk_root, trunk_name)
            if os.name == 'nt':
                os.startfile(dir_path)
            else:
                subprocess.call(['xdg-open', dir_path])

    def toggle_options(self):
        """Toggle visibility of options frame."""
        if self.options_frame.winfo_viewable():
            self.options_frame.pack_forget()
            self.options_toggle.config(text="▼")
        else:
            self.options_frame.pack(side="right", before=self.options_toggle, padx=10)
            self.options_toggle.config(text="▲")

    def set_opacity(self, val):
        """Set window opacity."""
        if self.fullscreen:
            return
        alpha = float(val) / 100
        self.root.attributes('-alpha', alpha)
        self.saved_alpha = alpha
        self._save_prefs()

    def toggle_left(self):
        """Toggle visibility of left panel."""
        if self.left_frame.winfo_viewable():
            self.left_frame.pack_forget()
            self.collapse_btn.config(text=">")
        else:
            self.left_frame.pack(side="left", fill="y", after=self.collapse_btn)
            self.collapse_btn.config(text="<")

    def toggle_fullscreen(self, event=None):
        """Toggle fullscreen mode."""
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.saved_alpha = self.root.attributes('-alpha')
            self.root.attributes('-alpha', 1.0)
        else:
            self.root.attributes('-alpha', self.saved_alpha)
        self.root.attributes("-fullscreen", self.fullscreen)

    def load_tree(self):
        """Load and populate the treeview with trunks, journals, and notes."""
        self.tree.delete(*self.tree.get_children())
        for trunk_name in sorted(os.listdir(self.trunk_root)):
            trunk_path = os.path.join(self.trunk_root, trunk_name)
            if os.path.isdir(trunk_path):
                display_trunk = trunk_name.replace("_", " ").title()
                trunk_id = self.tree.insert("", "end", text=display_trunk, open=False)
                for journal_name in sorted(os.listdir(trunk_path)):
                    journal_path = os.path.join(trunk_path, journal_name)
                    if os.path.isdir(journal_path):
                        display_journal = journal_name.replace("_", " ").title()
                        journal_id = self.tree.insert(trunk_id, "end", text=display_journal, open=False)
                        notes_dir = os.path.join(journal_path, ".notes")
                        if os.path.exists(notes_dir):
                            for file_name in sorted(f for f in os.listdir(notes_dir) if f.endswith(".txt")):
                                file_base = file_name[:-4]
                                display_text = self._format_display(file_base)
                                file_path = os.path.join(notes_dir, file_name)
                                self.tree.insert(journal_id, "end", text=display_text, values=(file_path,))

    def on_select(self, event):
        """Handle selection in treeview."""
        self.save_current()
        selected = self.tree.focus()
        if not selected:
            return
        item_type = self.get_item_type(selected)
        item = self.tree.item(selected)
        if item_type == "note":
            if self.in_memory:
                if not messagebox.askyesno("Discard In-Memory?", "Discard the in-memory note?"):
                    self.tree.selection_remove(selected)
                    return
                self.in_memory = False
            self.current_file = item['values'][0]
            self._load_meta()
            try:
                with open(self.current_file, "r") as f:
                    content = f.read()
                self.text.delete("1.0", tk.END)
                self.text.insert("1.0", content)
            except IOError:
                messagebox.showerror("Error", "Failed to load note.")
            self.header_label.config(text=item['text'])
        else:
            if self.in_memory:
                if not messagebox.askyesno("Discard In-Memory?", "Discard the in-memory note?"):
                    self.tree.selection_remove(selected)
                    return
                self.in_memory = False
            self.current_file = None
            self.font_family = "Arial"
            self.font_size = 12
            self.text.config(font=(self.font_family, self.font_size))
            self.font_combo.set(self.font_family)
            self.size_scale.set(self.font_size)
            self.text.delete("1.0", tk.END)
            self.header_label.config(text="Untitled")

    def schedule_save(self, event=None):
        """Schedule autosave after inactivity."""
        if self.save_timer:
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(2000, self.save_current)

    def save_current(self):
        """Save the current note content."""
        if self.in_memory:
            return
        content = self.text.get("1.0", tk.END).strip()
        if not content:
            return
        if not self.current_file:
            # Save to unsaved notes
            now = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            note_base = f"note_{now}"
            filename = f"{note_base}.txt"
            self.current_file = os.path.join(self.unsaved_notes_dir, filename)
            display_name = self._format_display(note_base)
            for trunk_iid in self.tree.get_children():
                if self.tree.item(trunk_iid)['text'] == "Unsaved":
                    for journal_iid in self.tree.get_children(trunk_iid):
                        if self.tree.item(journal_iid)['text'] == "Notes":
                            self.tree.insert(journal_iid, "end", text=display_name, values=(self.current_file,))
                            break
                    break
            self.header_label.config(text=display_name)
        try:
            with open(self.current_file, "w") as f:
                f.write(content)
        except IOError:
            messagebox.showerror("Error", "Failed to save note.")

    def new_trunk(self):
        """Create a new trunk."""
        name = simpledialog.askstring("New Trunk", "Enter trunk name:")
        if name:
            base = name.strip().lower().replace(" ", "_")
            path = os.path.join(self.trunk_root, base)
            if os.path.exists(path):
                messagebox.showwarning("Warning", "Trunk already exists.")
                return
            try:
                os.mkdir(path)
                self.load_tree()
            except OSError:
                messagebox.showerror("Error", "Failed to create trunk.")

    def new_journal(self):
        """Create a new journal in the selected trunk."""
        selected = self.tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Select a trunk first.")
            return
        item_type = self.get_item_type(selected)
        if item_type == "note":
            journal_id = self.tree.parent(selected)
            trunk_id = self.tree.parent(journal_id)
        elif item_type == "journal":
            trunk_id = self.tree.parent(selected)
        elif item_type == "trunk":
            trunk_id = selected
        else:
            return
        trunk_item = self.tree.item(trunk_id)
        trunk_name = trunk_item['text'].lower().replace(" ", "_")
        name = simpledialog.askstring("New Journal", "Enter journal name:")
        if name:
            base = name.strip().lower().replace(" ", "_")
            path = os.path.join(self.trunk_root, trunk_name, base)
            if os.path.exists(path):
                messagebox.showwarning("Warning", "Journal already exists.")
                return
            try:
                os.mkdir(path)
                notes_path = os.path.join(path, ".notes")
                os.mkdir(notes_path)
                self.load_tree()
            except OSError:
                messagebox.showerror("Error", "Failed to create journal.")

    def new_note(self):
        """Create a new note in the selected journal."""
        selected = self.tree.focus()
        if not selected:
            messagebox.showwarning("Warning", "Select a journal first.")
            return
        item_type = self.get_item_type(selected)
        if item_type != "journal":
            messagebox.showwarning("Warning", "Select a journal.")
            return
        journal_id = selected
        journal_item = self.tree.item(journal_id)
        journal_name = journal_item['text'].lower().replace(" ", "_")
        trunk_id = self.tree.parent(journal_id)
        trunk_item = self.tree.item(trunk_id)
        trunk_name = trunk_item['text'].lower().replace(" ", "_")
        name = simpledialog.askstring("New Note", "Enter note name:")
        if name:
            dir_path = os.path.join(self.trunk_root, trunk_name, journal_name, ".notes")
            base = name.strip().lower().replace(" ", "_")
            filename = base + ".txt"
            counter = 2
            while os.path.exists(os.path.join(dir_path, filename)):
                filename = f"{base}_{counter}.txt"
                counter += 1
            file_path = os.path.join(dir_path, filename)
            try:
                open(file_path, "w").close()
                self.load_tree()
            except IOError:
                messagebox.showerror("Error", "Failed to create note.")

    def rename_note(self, event=None):
        """Rename the current note."""
        if not self.current_file or self.header_label.cget("text") == "Untitled":
            return
        current_display = self.header_label.cget("text")
        new_display = simpledialog.askstring("Rename Note", "Enter new note name:", initialvalue=current_display)
        if not new_display or new_display == current_display:
            return
        dir_path = os.path.dirname(self.current_file)
        base = new_display.strip().lower().replace(" ", "_")
        filename = base + ".txt"
        counter = 2
        display_final = new_display
        while os.path.exists(os.path.join(dir_path, filename)):
            filename = f"{base}_{counter}.txt"
            display_final = f"{new_display} ({counter})"
            counter += 1
        old_meta = self.current_file + ".meta"
        content = self.text.get("1.0", tk.END).strip()
        try:
            os.remove(self.current_file)
            new_file = os.path.join(dir_path, filename)
            with open(new_file, "w") as f:
                f.write(content)
            if os.path.exists(old_meta):
                shutil.move(old_meta, new_file + ".meta")
            self.current_file = new_file
            selected = self.tree.focus()
            self.tree.item(selected, text=display_final, values=(new_file,))
            self.header_label.config(text=display_final)
        except (IOError, shutil.Error):
            messagebox.showerror("Error", "Failed to rename note.")

    def delete_item(self):
        """Delete the selected item (trunk, journal, or note)."""
        selected = self.tree.focus()
        if not selected:
            return
        item_type = self.get_item_type(selected)
        item = self.tree.item(selected)
        if item_type == "note":
            file_path = item['values'][0]
            if not messagebox.askyesno("Delete Note", "Are you sure you want to delete this note?"):
                return
            try:
                os.remove(file_path)
                meta = file_path + ".meta"
                if os.path.exists(meta):
                    os.remove(meta)
                if self.current_file == file_path:
                    self.text.delete("1.0", tk.END)
                    self.current_file = None
                    self.header_label.config(text="Untitled")
            except OSError:
                messagebox.showerror("Error", "Failed to delete note.")
            self.load_tree()
        elif item_type == "journal":
            journal_text = item['text']
            journal_name = journal_text.lower().replace(" ", "_")
            trunk_id = self.tree.parent(selected)
            trunk_text = self.tree.item(trunk_id)['text']
            trunk_name = trunk_text.lower().replace(" ", "_")
            if trunk_name == "unsaved" and journal_name == "notes":
                messagebox.showwarning("Warning", "Cannot delete 'Unsaved Notes' journal.")
                return
            path = os.path.join(self.trunk_root, trunk_name, journal_name)
            if not messagebox.askyesno("Delete Journal", "Are you sure you want to delete this journal and all its notes?"):
                return
            try:
                shutil.rmtree(path)
                self.text.delete("1.0", tk.END)
                self.current_file = None
                self.header_label.config(text="Untitled")
            except shutil.Error:
                messagebox.showerror("Error", "Failed to delete journal.")
            self.load_tree()
        elif item_type == "trunk":
            trunk_text = item['text']
            trunk_name = trunk_text.lower().replace(" ", "_")
            if trunk_name == "unsaved":
                messagebox.showwarning("Warning", "Cannot delete 'Unsaved' trunk.")
                return
            path = os.path.join(self.trunk_root, trunk_name)
            if not messagebox.askyesno("Delete Trunk", "Are you sure you want to delete this trunk and all its journals and notes?"):
                return
            try:
                shutil.rmtree(path)
                self.text.delete("1.0", tk.END)
                self.current_file = None
                self.header_label.config(text="Untitled")
            except shutil.Error:
                messagebox.showerror("Error", "Failed to delete trunk.")
            self.load_tree()


if __name__ == "__main__":
    root = tk.Tk()
    app = JournalApp(root)
    root.mainloop()