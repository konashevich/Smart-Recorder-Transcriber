import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, Menu, filedialog
from tkinter import ttk
import speech_recognition as sr
import threading
import pyperclip
import google.generativeai as genai
import requests
import json
import os
from datetime import datetime
import sys

# Define the default settings structure.
# This will be used if settings.json is missing or corrupt.
DEFAULT_SETTINGS = {
    "api_key": "",
    "ai_service": "Gemini",
    "local_model_url": "http://localhost:1234/v1/chat/completions",
    "system_prompt": "You are a helpful assistant that polishes text. Return only the polished text without any comments or preamble.",
    "active_theme": "system" # Default to following the system theme
}

def is_system_dark_theme():
    """Checks if the system is in dark mode (Windows only)."""
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return value == 0
    except (ImportError, FileNotFoundError):
        return False

class SpeechToTextApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart AI Recorder Transcriber")
        self.root.geometry("900x600")

        self.settings_file = "settings.json"
        self.savings_dir = "savings"
        if not os.path.exists(self.savings_dir):
            os.makedirs(self.savings_dir)
        
        self.settings = {}
        
        # --- Variables ---
        self.ai_service_var = tk.StringVar()
        self.system_prompt_var = tk.StringVar()
        self.theme_var = tk.StringVar()
        self.raw_fake_cursor_tag = "raw_fake_cursor"
        self.polished_fake_cursor_tag = "polished_fake_cursor"
        
        # --- Theming ---
        self.style = ttk.Style(self.root)

        self.create_widgets()
        self.create_menu()
        
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = True
        
        self.is_recording = False
        self.stop_listening = None
        
        self.load_settings() # Load settings and apply initial theme
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        self.main_container = ttk.Frame(self.root, padding=10)
        self.main_container.pack(fill=tk.BOTH, expand=tk.YES)

        self.paned_window = ttk.PanedWindow(self.main_container, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=tk.YES)

        self.raw_text_frame = ttk.Frame(self.paned_window, padding=5)
        self.paned_window.add(self.raw_text_frame, weight=1)
        
        self.raw_text_label = ttk.Label(self.raw_text_frame, text="Raw Transcription")
        self.raw_text_label.pack(pady=(0, 5))

        self.raw_text_area = scrolledtext.ScrolledText(self.raw_text_frame, wrap=tk.WORD, height=15, width=45, font=("Arial", 10), blockcursor=False, exportselection=False)
        self.raw_text_area.pack(fill=tk.BOTH, expand=tk.YES)
        self.raw_text_area.bind("<FocusIn>", lambda e: self.hide_fake_cursor(self.raw_text_area, self.raw_fake_cursor_tag))
        self.raw_text_area.bind("<FocusOut>", lambda e: self.show_fake_cursor(self.raw_text_area, self.raw_fake_cursor_tag))

        self.raw_buttons_frame = ttk.Frame(self.raw_text_frame)
        self.raw_buttons_frame.pack(pady=5)
        
        self.copy_raw_button = ttk.Button(self.raw_buttons_frame, text="📋 Copy", command=self.copy_raw_text)
        self.copy_raw_button.pack(side=tk.LEFT, padx=5)
        
        self.delete_raw_button = ttk.Button(self.raw_buttons_frame, text="🗑️ Delete", command=self.delete_raw_text)
        self.delete_raw_button.pack(side=tk.LEFT, padx=5)

        self.polished_text_frame = ttk.Frame(self.paned_window, padding=5)
        self.paned_window.add(self.polished_text_frame, weight=1)

        self.polished_text_label = ttk.Label(self.polished_text_frame, text="Polished Text")
        self.polished_text_label.pack(pady=(0, 5))

        self.polished_text_area = scrolledtext.ScrolledText(self.polished_text_frame, wrap=tk.WORD, height=15, width=45, font=("Arial", 10), blockcursor=False, exportselection=False)
        self.polished_text_area.pack(fill=tk.BOTH, expand=tk.YES)
        self.polished_text_area.bind("<FocusIn>", lambda e: self.hide_fake_cursor(self.polished_text_area, self.polished_fake_cursor_tag))
        self.polished_text_area.bind("<FocusOut>", lambda e: self.show_fake_cursor(self.polished_text_area, self.polished_fake_cursor_tag))

        self.polished_buttons_frame = ttk.Frame(self.polished_text_frame)
        self.polished_buttons_frame.pack(pady=5)

        self.copy_polish_button = ttk.Button(self.polished_buttons_frame, text="📋 Copy", command=self.copy_polished_text)
        self.copy_polish_button.pack(side=tk.LEFT, padx=5)

        self.delete_polish_button = ttk.Button(self.polished_buttons_frame, text="🗑️ Delete", command=self.delete_polished_text)
        self.delete_polish_button.pack(side=tk.LEFT, padx=5)

        self.main_button_frame = ttk.Frame(self.main_container)
        self.main_button_frame.pack(pady=5, fill=tk.X, expand=tk.NO)

        self.record_button = ttk.Button(self.main_button_frame, text="🔴 Listen")
        self.record_button.pack(side=tk.LEFT, padx=5)
        self.record_button.bind("<ButtonPress-1>", self.start_recording)
        self.record_button.bind("<ButtonRelease-1>", self.stop_recording)
        
        self.polish_button = ttk.Button(self.main_button_frame, text="✨ Polish")
        self.polish_button.pack(side=tk.LEFT, padx=5)
        self.polish_button.config(command=self.polish_text)
        
        self.delete_all_button = ttk.Button(self.main_button_frame, text="🗑️ Del All")
        self.delete_all_button.pack(side=tk.RIGHT, padx=5)
        self.delete_all_button.config(command=self.delete_all_text)
        
    def create_menu(self):
        self.menu_bar = Menu(self.root)
        self.root.config(menu=self.menu_bar)
        
        self.file_menu = Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="📂 Open...", command=self.open_file)
        self.file_menu.add_command(label="💾 Save & New", command=self.save_and_new)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.on_closing)

        self.settings_menu = Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Settings", menu=self.settings_menu)
        
        self.theme_menu = Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label="Theme", menu=self.theme_menu)
        self.theme_menu.add_radiobutton(label="Follow System", variable=self.theme_var, value="system", command=self.apply_theme)
        self.theme_menu.add_radiobutton(label="Light", variable=self.theme_var, value="light", command=self.apply_theme)
        self.theme_menu.add_radiobutton(label="Dark", variable=self.theme_var, value="dark", command=self.apply_theme)

        self.settings_menu.add_separator()
        self.settings_menu.add_command(label="Edit AI Prompt...", command=self.edit_prompt_window)
        self.settings_menu.add_command(label="Set Gemini API Key", command=self.set_api_key)
        
        ai_service_menu = Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label="AI Service", menu=ai_service_menu)
        ai_service_menu.add_radiobutton(label="Gemini", variable=self.ai_service_var, value="Gemini", command=self.save_settings)
        ai_service_menu.add_radiobutton(label="Local AI", variable=self.ai_service_var, value="Local", command=self.save_settings)
        
        self.settings_menu.add_command(label="Set Local AI URL", command=self.set_local_model_url)
    
    def apply_theme(self):
        self.save_settings() # Save selection immediately
        theme_name = self.theme_var.get()
        
        if theme_name == 'system':
            theme = 'dark' if is_system_dark_theme() else 'light'
        else:
            theme = theme_name

        self.style.theme_use('default') 
        
        if theme == 'dark':
            self.style.configure('.', background='#2e2e2e', foreground='#ffffff', fieldbackground='#3c3c3c', bordercolor='#6a6a6a')
            self.style.configure('TButton', background='#505050', foreground='#ffffff')
            self.style.map('TButton', background=[('active', '#6a6a6a')])
            text_bg, text_fg, insert_bg = '#3c3c3c', '#ffffff', '#ffffff'
        else: # Light theme
            self.style.configure('.', background='#f0f0f0', foreground='#000000', fieldbackground='#ffffff', bordercolor='#cccccc')
            self.style.configure('TButton', background='#e1e1e1', foreground='#000000')
            self.style.map('TButton', background=[('active', '#d4d4d4')])
            text_bg, text_fg, insert_bg = '#ffffff', '#000000', '#000000'

        for widget in [self.raw_text_area, self.polished_text_area]:
            widget.config(bg=text_bg, fg=text_fg, insertbackground=insert_bg)

    def show_fake_cursor(self, widget, tag_name):
        self.hide_fake_cursor(widget, tag_name) 
        insert_index = widget.index(tk.INSERT)
        widget.tag_config(tag_name, foreground="#808080")
        widget.insert(insert_index, "|", (tag_name,))

    def hide_fake_cursor(self, widget, tag_name):
        # Check if the tag exists before trying to delete
        if widget.tag_ranges(tag_name):
            widget.delete(f"{tag_name}.first", f"{tag_name}.last")

    def edit_prompt_window(self):
        # ... (This function remains largely unchanged)
        pass

    def copy_raw_text(self):
        pyperclip.copy(self.raw_text_area.get(1.0, tk.END))

    def copy_polished_text(self):
        pyperclip.copy(self.polished_text_area.get(1.0, tk.END))

    def delete_raw_text(self):
        self.raw_text_area.delete(1.0, tk.END)

    def delete_polished_text(self):
        self.polished_text_area.delete(1.0, tk.END)

    def delete_all_text(self):
        self.raw_text_area.delete(1.0, tk.END)
        self.polished_text_area.delete(1.0, tk.END)

    def save_and_new(self):
        # ... (This function remains largely unchanged)
        pass

    def open_file(self):
        # ... (This function remains largely unchanged)
        pass

    def load_settings(self):
        """Loads settings from settings.json, creating it if it doesn't exist."""
        try:
            if not os.path.exists(self.settings_file):
                self.settings = DEFAULT_SETTINGS.copy()
                self.save_settings()
            else:
                with open(self.settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                self.settings = DEFAULT_SETTINGS.copy()
                self.settings.update(loaded_settings)
        except (json.JSONDecodeError, IOError):
            messagebox.showerror("Settings Error", "Could not read settings.json. Loading default settings.")
            self.settings = DEFAULT_SETTINGS.copy()
        
        self.ai_service_var.set(self.settings.get("ai_service"))
        self.system_prompt_var.set(self.settings.get("system_prompt"))
        self.theme_var.set(self.settings.get("active_theme"))
        
        api_key = self.settings.get("api_key", "")
        if api_key:
            try:
                genai.configure(api_key=api_key)
            except Exception: pass
        
        self.apply_theme()

    def save_settings(self):
        """Saves the current settings to settings.json."""
        self.settings['active_theme'] = self.theme_var.get()
        self.settings['ai_service'] = self.ai_service_var.get()
        self.settings['system_prompt'] = self.system_prompt_var.get()
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except IOError:
            messagebox.showerror("Settings Error", "Could not save settings to settings.json.")
    
    def on_closing(self):
        self.save_settings()
        self.root.destroy()

    def set_api_key(self):
        api_key = simpledialog.askstring("API Key", "Enter your Google AI API Key:", show='*')
        if api_key:
            try:
                genai.configure(api_key=api_key)
                self.settings["api_key"] = api_key
                self.save_settings()
                messagebox.showinfo("Success", "API Key set successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to configure API key: {e}")

    def set_local_model_url(self):
        new_url = simpledialog.askstring("Local AI URL", "Enter the URL for your local model:", initialvalue=self.settings.get("local_model_url"))
        if new_url:
            self.settings["local_model_url"] = new_url
            self.save_settings()
            messagebox.showinfo("Success", "Local AI URL updated.")

    def start_recording(self, event):
        if self.is_recording:
            return
        self.is_recording = True
        self.record_button.config(text="Listening...")
        self.audio_chunks = []
        self.stop_listening = self.recognizer.listen_in_background(sr.Microphone(), self.audio_callback)

    def stop_recording(self, event):
        if self.is_recording:
            self.is_recording = False 
            if self.stop_listening:
                self.stop_listening(wait_for_stop=False)
            self.record_button.config(text="Transcribing...")
            threading.Thread(target=self.process_recorded_audio, args=(self.audio_chunks[:],), daemon=True).start()
    
    def audio_callback(self, recognizer, audio):
        if self.is_recording:
            self.audio_chunks.append(audio)

    def process_recorded_audio(self, audio_data_list):
        if not audio_data_list:
            self.root.after(0, lambda: self.record_button.config(text="🔴 Listen"))
            return
        
        raw_data = b"".join([audio.get_raw_data() for audio in audio_data_list])
        audio_data = sr.AudioData(raw_data, audio_data_list[0].sample_rate, audio_data_list[0].sample_width)

        try:
            text = self.recognizer.recognize_google(audio_data)
            self.root.after(0, self.insert_transcribed_text, text)
        except sr.UnknownValueError:
            self.root.after(0, lambda: messagebox.showwarning("Speech Recognition", "Could not understand audio"))
        except sr.RequestError as e:
            self.root.after(0, lambda: messagebox.showerror("Speech Recognition", f"Could not request results; {e}"))
        finally:
            self.root.after(0, lambda: self.record_button.config(text="🔴 Listen"))

    def insert_transcribed_text(self, text):
        self.hide_fake_cursor(self.raw_text_area, self.raw_fake_cursor_tag)
        try:
            start = self.raw_text_area.index("sel.first")
            end = self.raw_text_area.index("sel.last")
            self.raw_text_area.delete(start, end)
        except tk.TclError:
            pass
        self.raw_text_area.insert(tk.INSERT, " " + text)
        if self.root.focus_get() != self.raw_text_area:
             self.show_fake_cursor(self.raw_text_area, self.raw_fake_cursor_tag)

    def polish_text(self):
        try:
            text_to_polish = self.raw_text_area.get("sel.first", "sel.last")
        except tk.TclError:
            text_to_polish = self.raw_text_area.get(1.0, tk.END).strip()
        
        if not text_to_polish:
            messagebox.showinfo("Polish Text", "Nothing to polish.")
            return

        threading.Thread(target=self.get_polished_text, args=(text_to_polish,), daemon=True).start()

    def get_polished_text(self, text):
        try:
            prompt = f"{self.system_prompt_var.get()}\n\n{text}"
            
            if self.ai_service_var.get() == "Gemini":
                if not self.settings.get("api_key"):
                    self.root.after(0, lambda: messagebox.showerror("Error", "Please set your Gemini API key in Settings."))
                    return
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(prompt)
                polished_text = response.text
            else: 
                headers = {"Content-Type": "application/json"}
                data = { "model": "local-model", "messages": [{"role": "system", "content": self.system_prompt_var.get()}, {"role": "user", "content": text}], "temperature": 0.7 }
                response = requests.post(self.settings.get("local_model_url"), headers=headers, data=json.dumps(data))
                response.raise_for_status()
                polished_text = response.json()['choices'][0]['message']['content']
            
            self.root.after(0, self.display_polished_text, polished_text)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to polish text: {e}"))

    def display_polished_text(self, text):
        self.hide_fake_cursor(self.polished_text_area, self.polished_fake_cursor_tag)
        try:
            start = self.polished_text_area.index("sel.first")
            end = self.polished_text_area.index("sel.last")
            self.polished_text_area.delete(start, end)
        except tk.TclError:
            pass
        
        self.polished_text_area.insert(tk.INSERT, text)
        pyperclip.copy(text)
        if self.root.focus_get() != self.polished_text_area:
             self.show_fake_cursor(self.polished_text_area, self.polished_fake_cursor_tag)

if __name__ == "__main__":
    # Use the standard tkinter root window
    root = tk.Tk()
    app = SpeechToTextApp(root)
    root.mainloop()
