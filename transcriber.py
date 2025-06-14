import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, Menu, filedialog, ttk
import speech_recognition as sr
import threading
import pyperclip
import google.generativeai as genai
import requests
import json
import os
from datetime import datetime

# --- Theme Colors ---
THEMES = {
    "light": {
        "bg": "#F0F0F0",
        "fg": "#000000",
        "text_bg": "#FFFFFF",
        "text_fg": "#000000",
        "button_bg": "#E1E1E1",
        "button_fg": "#000000",
        "trough_color": "#F0F0F0"
    },
    "dark": {
        "bg": "#2E2E2E",
        "fg": "#FFFFFF",
        "text_bg": "#3C3C3C",
        "text_fg": "#FFFFFF",
        "button_bg": "#505050",
        "button_fg": "#FFFFFF",
        "trough_color": "#2E2E2E"
    }
}

class SpeechToTextApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Speech to Text Notepad")
        self.root.geometry("900x600")

        # Style object for ttk widgets
        self.style = ttk.Style(self.root)

        self.settings_file = "settings.json"
        self.savings_dir = "savings"
        if not os.path.exists(self.savings_dir):
            os.makedirs(self.savings_dir)

        self.raw_text_history = []
        self.api_key = ""
        self.ai_service = tk.StringVar(value="Gemini")
        self.local_model_url = "http://localhost:1234/v1/chat/completions"
        self.theme_var = tk.StringVar(value="light")

        self.create_widgets()
        self.create_menu()
        self.load_settings()

        # Recording state and resources
        self.recognizer = sr.Recognizer()
        self.is_recording = False
        self.stop_listening = None
        self.audio_data = []
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def apply_theme(self):
        theme_name = self.theme_var.get()
        theme_colors = THEMES.get(theme_name, THEMES["light"])
            
        self.root.config(bg=theme_colors["bg"])
        
        # Configure ttk style for scrollbars
        self.style.configure("TScrollbar",
            gripcount=0,
            background=theme_colors["button_bg"],
            darkcolor=theme_colors["bg"],
            lightcolor=theme_colors["bg"],
            troughcolor=theme_colors["trough_color"],
            bordercolor=theme_colors["bg"],
            arrowcolor=theme_colors["fg"]
        )
        self.style.map("TScrollbar", background=[('active', theme_colors["fg"])])

        # Apply to all relevant widgets
        for widget in self.root.winfo_children():
            self.configure_widget_theme(widget, theme_colors)

    def configure_widget_theme(self, widget, colors):
        widget_type = widget.winfo_class()
        
        try:
            widget.config(bg=colors["bg"], fg=colors["fg"])
        except tk.TclError:
            try:
                widget.config(bg=colors["bg"])
            except tk.TclError:
                pass

        if widget_type in ("TFrame", "Frame", "Labelframe"):
             for child in widget.winfo_children():
                self.configure_widget_theme(child, colors)

        elif widget_type == "ScrolledText":
            widget.config(bg=colors["text_bg"], fg=colors["text_fg"], insertbackground=colors["fg"])
        
        elif widget_type in ("Button", "TButton"):
             widget.config(bg=colors["button_bg"], fg=colors["fg"], activebackground=colors["fg"], activeforeground=colors["bg"])
             
        elif widget_type in ("Label", "TLabel", "Radiobutton", "TRadiobutton", "Menu"):
            widget.config(bg=colors["bg"], fg=colors["fg"])


    def create_widgets(self):
        self.text_frame_container = tk.Frame(self.root)
        self.text_frame_container.pack(pady=10, padx=10, fill="both", expand=True)

        self.raw_text_frame = tk.Frame(self.text_frame_container)
        self.raw_text_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        self.raw_text_label = tk.Label(self.raw_text_frame, text="Raw Transcription")
        self.raw_text_label.pack()

        self.raw_text_area = scrolledtext.ScrolledText(self.raw_text_frame, wrap=tk.WORD, height=15, width=45, font=("Arial", 10))
        self.raw_text_area.pack(fill="both", expand=True)

        self.raw_buttons_frame = tk.Frame(self.raw_text_frame)
        self.raw_buttons_frame.pack(pady=5)
        
        self.copy_raw_button = tk.Button(self.raw_buttons_frame, text="📋 Copy", command=self.copy_raw_text)
        self.copy_raw_button.pack(side="left", padx=5)
        
        self.delete_raw_button = tk.Button(self.raw_buttons_frame, text="🗑️ Delete", command=self.delete_raw_text)
        self.delete_raw_button.pack(side="left", padx=5)

        self.polished_text_frame = tk.Frame(self.text_frame_container)
        self.polished_text_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self.polished_text_label = tk.Label(self.polished_text_frame, text="Polished Text")
        self.polished_text_label.pack()

        self.polished_text_area = scrolledtext.ScrolledText(self.polished_text_frame, wrap=tk.WORD, height=15, width=45, font=("Arial", 10))
        self.polished_text_area.pack(fill="both", expand=True)
        
        self.polished_buttons_frame = tk.Frame(self.polished_text_frame)
        self.polished_buttons_frame.pack(pady=5)

        self.copy_polish_button = tk.Button(self.polished_buttons_frame, text="📋 Copy", command=self.copy_polished_text)
        self.copy_polish_button.pack(side="left", padx=5)

        self.delete_polish_button = tk.Button(self.polished_buttons_frame, text="🗑️ Delete", command=self.delete_polished_text)
        self.delete_polish_button.pack(side="left", padx=5)

        self.main_button_frame = tk.Frame(self.root)
        self.main_button_frame.pack(pady=5)

        self.record_button = tk.Button(self.main_button_frame, text="🔴 Listen", font=("Arial", 10, "bold"))
        self.record_button.pack(side="left", padx=5)
        self.record_button.bind("<ButtonPress-1>", self.start_recording)
        self.record_button.bind("<ButtonRelease-1>", self.stop_recording)

        self.delete_last_button = tk.Button(self.main_button_frame, text="⌫ Del Last", command=self.delete_last_entry)
        self.delete_last_button.pack(side="left", padx=5)
        
        self.polish_button = tk.Button(self.main_button_frame, text="✨ Polish", command=self.polish_text)
        self.polish_button.pack(side="left", padx=5)
        
        self.delete_all_button = tk.Button(self.main_button_frame, text="🗑️ Del All", command=self.delete_all_text)
        self.delete_all_button.pack(side="left", padx=5)
        
    def create_menu(self):
        menu_bar = Menu(self.root)
        self.root.config(menu=menu_bar)
        
        file_menu = Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="📂 Open...", command=self.open_file)
        file_menu.add_command(label="💾 Save & New", command=self.save_and_new)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)

        settings_menu = Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Settings", menu=settings_menu)
        
        theme_menu = Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="Theme", menu=theme_menu)
        theme_menu.add_radiobutton(label="Light", variable=self.theme_var, value="light", command=self.on_theme_change)
        theme_menu.add_radiobutton(label="Dark", variable=self.theme_var, value="dark", command=self.on_theme_change)

        settings_menu.add_separator()
        settings_menu.add_command(label="Set Gemini API Key", command=self.set_api_key)
        ai_service_menu = Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="AI Service", menu=ai_service_menu)
        ai_service_menu.add_radiobutton(label="Gemini", variable=self.ai_service, value="Gemini", command=self.save_settings)
        ai_service_menu.add_radiobutton(label="Local AI", variable=self.ai_service, value="Local", command=self.save_settings)
        settings_menu.add_command(label="Set Local AI URL", command=self.set_local_model_url)
    
    def on_theme_change(self):
        self.apply_theme()
        self.save_settings()

    def copy_raw_text(self):
        pyperclip.copy(self.raw_text_area.get(1.0, tk.END))
        messagebox.showinfo("Copied", "Raw transcription copied to clipboard.")

    def copy_polished_text(self):
        pyperclip.copy(self.polished_text_area.get(1.0, tk.END))

    def delete_raw_text(self):
        if messagebox.askyesno("Confirm", "Delete the entire raw transcription?"):
            self.raw_text_history.clear()
            self.update_raw_text()

    def delete_polished_text(self):
        if messagebox.askyesno("Confirm", "Delete the entire polished text?"):
            self.polished_text_area.delete(1.0, tk.END)

    def delete_all_text(self):
        if messagebox.askyesno("Confirm", "Delete everything in both windows?"):
            self.raw_text_history.clear()
            self.update_raw_text()
            self.polished_text_area.delete(1.0, tk.END)

    def save_and_new(self):
        raw_text = self.raw_text_area.get(1.0, tk.END).strip()
        if not raw_text:
            if messagebox.askyesno("Confirm", "Editor is empty. Start a new session anyway?"):
                self.raw_text_history.clear()
                self.update_raw_text()
                self.polished_text_area.delete(1.0, tk.END)
            return

        now = datetime.now().strftime('%Y-%m-%d-%H-%M')
        first_words = "_".join(raw_text.split()[:3]).replace("/", "_").replace("\\", "_")
        filename = os.path.join(self.savings_dir, f"{now}_{first_words or 'transcription'}.json")
        
        data_to_save = {
            "raw_text": raw_text,
            "polished_text": self.polished_text_area.get(1.0, tk.END).strip()
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)
            messagebox.showinfo("Saved", f"Session saved to:\n{filename}")
            self.raw_text_history.clear()
            self.update_raw_text()
            self.polished_text_area.delete(1.0, tk.END)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save file: {e}")

    def open_file(self):
        filepath = filedialog.askopenfilename(
            initialdir=self.savings_dir,
            title="Open Transcription",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        if not filepath: return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.raw_text_history.clear()
            raw_text = data.get("raw_text", "")
            self.raw_text_history = [raw_text] if raw_text else []
            self.update_raw_text()
            
            self.polished_text_area.delete(1.0, tk.END)
            self.polished_text_area.insert(tk.END, data.get("polished_text", ""))
        except Exception as e:
            messagebox.showerror("Open Error", f"Could not open file: {e}")

    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.api_key = settings.get("api_key", "")
                    self.ai_service.set(settings.get("ai_service", "Gemini"))
                    self.local_model_url = settings.get("local_model_url", "http://localhost:1234/v1/chat/completions")
                    self.theme_var.set(settings.get("theme", "light"))
                
                if self.api_key:
                    genai.configure(api_key=self.api_key)
                
                self.apply_theme()
            except (json.JSONDecodeError, IOError) as e:
                messagebox.showerror("Settings Error", f"Could not load settings file: {e}")
                self.apply_theme()
        else:
            self.apply_theme()
    
    def save_settings(self):
        settings = {
            "api_key": self.api_key,
            "ai_service": self.ai_service.get(),
            "local_model_url": self.local_model_url,
            "theme": self.theme_var.get()
        }
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(settings, f, indent=4)
        except IOError as e:
            messagebox.showerror("Settings Error", f"Could not save settings: {e}")

    def on_closing(self):
        self.save_settings()
        self.root.destroy()

    def set_api_key(self):
        self.api_key = simpledialog.askstring("API Key", "Enter your Google AI API Key:", show='*')
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                messagebox.showinfo("Success", "API Key set successfully.")
                self.save_settings()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to configure API key: {e}")

    def set_local_model_url(self):
        new_url = simpledialog.askstring("Local AI URL", "Enter the URL for your local model:", initialvalue=self.local_model_url)
        if new_url:
            self.local_model_url = new_url
            messagebox.showinfo("Success", "Local AI URL updated.")
            self.save_settings()

    def start_recording(self, event):
        if self.is_recording: return
        self.is_recording = True
        self.audio_data = []
        self.record_button.config(text="Listening...")
        try:
            self.stop_listening = self.recognizer.listen_in_background(sr.Microphone(), lambda r,a: self.audio_data.append(a), phrase_time_limit=10)
        except Exception as e:
            messagebox.showerror("Error", f"Could not start microphone: {e}")
            self.is_recording = False
            self.record_button.config(text="🔴 Listen")

    def stop_recording(self, event):
        if not self.is_recording: return
        self.record_button.config(text="Transcribing...")
        if self.stop_listening: self.stop_listening(wait_for_stop=False)
        self.is_recording = False
        if self.audio_data:
            threading.Thread(target=self.process_recorded_audio).start()
        else:
            self.record_button.config(text="🔴 Listen")

    def process_recorded_audio(self):
        try:
            if not self.audio_data: return
            full_audio = sr.AudioData(b"".join([a.get_raw_data() for a in self.audio_data]), self.audio_data[0].sample_rate, self.audio_data[0].sample_width)
            text = self.recognizer.recognize_google(full_audio)
            if text: self.root.after(0, self.add_new_transcription, text)
        except sr.UnknownValueError:
            self.root.after(0, lambda: messagebox.showwarning("Speech Recognition", "Could not understand audio"))
        except sr.RequestError as e:
            self.root.after(0, lambda: messagebox.showerror("Speech Recognition", f"Could not request results; {e}"))
        except IndexError: pass
        finally:
            self.root.after(0, lambda: self.record_button.config(text="🔴 Listen"))

    def add_new_transcription(self, text):
        self.raw_text_history.append(text)
        self.update_raw_text()

    def update_raw_text(self):
        self.raw_text_area.delete(1.0, tk.END)
        self.raw_text_area.insert(tk.END, " ".join(self.raw_text_history))

    def delete_last_entry(self):
        if self.raw_text_history:
            self.raw_text_history.pop()
            self.update_raw_text()

    def polish_text(self):
        raw_text = self.raw_text_area.get(1.0, tk.END).strip()
        if not raw_text:
            messagebox.showinfo("Polish Text", "Nothing to polish.")
            return

        self.polished_text_area.delete(1.0, tk.END)
        self.polished_text_area.insert(tk.END, "Polishing...")
        threading.Thread(target=self.get_polished_text, args=(raw_text,)).start()

    def get_polished_text(self, text):
        try:
            if self.ai_service.get() == "Gemini":
                if not self.api_key:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Please set your Gemini API key in Settings."))
                    self.root.after(0, self.clear_polishing_message)
                    return
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(f"Polish the following text, return only the polished text without any comments or preamble:\n\n{text}")
                polished_text = response.text
            else: # Local AI
                headers = {"Content-Type": "application/json"}
                data = { "model": "local-model", "messages": [{"role": "system", "content": "You are a helpful assistant that polishes text."}, {"role": "user", "content": f"Polish the following text, return only the polished text without any comments or preamble:\n\n{text}"}], "temperature": 0.7 }
                response = requests.post(self.local_model_url, headers=headers, data=json.dumps(data))
                response.raise_for_status()
                polished_text = response.json()['choices'][0]['message']['content']

            self.root.after(0, self.display_polished_text, polished_text)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to polish text: {e}"))
            self.root.after(0, self.clear_polishing_message)

    def clear_polishing_message(self):
        self.polished_text_area.delete(1.0, tk.END)

    def display_polished_text(self, text):
        self.polished_text_area.delete(1.0, tk.END)
        self.polished_text_area.insert(tk.END, text)
        pyperclip.copy(text)

if __name__ == "__main__":
    root = tk.Tk()
    app = SpeechToTextApp(root)
    root.mainloop()
