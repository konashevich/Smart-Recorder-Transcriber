import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, Menu, filedialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import speech_recognition as sr
import threading
import pyperclip
import google.generativeai as genai
import requests
import json
import os
from datetime import datetime

class SpeechToTextApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart AI Recorder Transcriber")
        self.root.geometry("900x600")

        self.settings_file = "settings.json"
        self.savings_dir = "savings"
        if not os.path.exists(self.savings_dir):
            os.makedirs(self.savings_dir)

        self.api_key = ""
        self.ai_service = tk.StringVar(value="Gemini")
        self.local_model_url = "http://localhost:1234/v1/chat/completions"
        self.default_prompt = "You are a helpful assistant that polishes text. Return only the polished text without any comments or preamble."
        self.system_prompt = tk.StringVar(value=self.default_prompt)
        
        self.style = self.root.style 

        self.create_widgets()
        self.create_menu()
        
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = True
        
        self.audio_data_chunks = []
        self.is_recording = False
        self.stop_listening = None
        
        self.load_settings()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        main_container = ttk.Frame(self.root, padding=10)
        main_container.pack(fill=BOTH, expand=YES)

        paned_window = ttk.PanedWindow(main_container, orient=HORIZONTAL)
        paned_window.pack(fill=BOTH, expand=YES)

        raw_text_frame = ttk.Frame(paned_window, padding=5)
        paned_window.add(raw_text_frame, weight=1)
        
        raw_text_label = ttk.Label(raw_text_frame, text="Raw Transcription")
        raw_text_label.pack(pady=(0, 5))

        self.raw_text_area = scrolledtext.ScrolledText(raw_text_frame, wrap=tk.WORD, height=15, width=45, font=("Arial", 10), blockcursor=True)
        self.raw_text_area.pack(fill=BOTH, expand=YES)

        raw_buttons_frame = ttk.Frame(raw_text_frame)
        raw_buttons_frame.pack(pady=5)
        
        self.copy_raw_button = ttk.Button(raw_buttons_frame, text="📋 Copy", command=self.copy_raw_text, bootstyle="secondary")
        self.copy_raw_button.pack(side=LEFT, padx=5)
        
        self.delete_raw_button = ttk.Button(raw_buttons_frame, text="🗑️ Delete", command=self.delete_raw_text, bootstyle="secondary")
        self.delete_raw_button.pack(side=LEFT, padx=5)

        polished_text_frame = ttk.Frame(paned_window, padding=5)
        paned_window.add(polished_text_frame, weight=1)

        polished_text_label = ttk.Label(polished_text_frame, text="Polished Text")
        polished_text_label.pack(pady=(0, 5))

        self.polished_text_area = scrolledtext.ScrolledText(polished_text_frame, wrap=tk.WORD, height=15, width=45, font=("Arial", 10), blockcursor=True)
        self.polished_text_area.pack(fill=BOTH, expand=YES)
        
        polished_buttons_frame = ttk.Frame(polished_text_frame)
        polished_buttons_frame.pack(pady=5)

        self.copy_polish_button = ttk.Button(polished_buttons_frame, text="📋 Copy", command=self.copy_polished_text, bootstyle="secondary")
        self.copy_polish_button.pack(side=LEFT, padx=5)

        self.delete_polish_button = ttk.Button(polished_buttons_frame, text="🗑️ Delete", command=self.delete_polished_text, bootstyle="secondary")
        self.delete_polish_button.pack(side=LEFT, padx=5)

        main_button_frame = ttk.Frame(main_container)
        main_button_frame.pack(pady=5, fill=X, expand=NO)

        self.record_button = ttk.Button(main_button_frame, text="🔴 Listen", bootstyle="outline-danger")
        self.record_button.pack(side=LEFT, padx=5)
        self.record_button.bind("<ButtonPress-1>", self.start_recording)
        self.record_button.bind("<ButtonRelease-1>", self.stop_recording)
        
        self.polish_button = ttk.Button(main_button_frame, text="✨ Polish", bootstyle="outline-primary")
        self.polish_button.pack(side=LEFT, padx=5)
        self.polish_button.config(command=self.polish_text)
        
        self.delete_all_button = ttk.Button(main_button_frame, text="🗑️ Del All", bootstyle="outline-danger")
        self.delete_all_button.pack(side=RIGHT, padx=5)
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
        self.theme_menu.add_command(label="Light (Litera)", command=lambda: self.on_theme_change("litera"))
        self.theme_menu.add_command(label="Dark (Cyborg)", command=lambda: self.on_theme_change("cyborg"))
        self.theme_menu.add_command(label="Dark (Darkly)", command=lambda: self.on_theme_change("darkly"))

        self.settings_menu.add_separator()
        self.settings_menu.add_command(label="Edit AI Prompt...", command=self.edit_prompt_window)
        self.settings_menu.add_command(label="Set Gemini API Key", command=self.set_api_key)
        self.ai_service_menu = Menu(self.settings_menu, tearoff=0)
        self.settings_menu.add_cascade(label="AI Service", menu=self.ai_service_menu)
        self.ai_service_menu.add_radiobutton(label="Gemini", variable=self.ai_service, value="Gemini", command=self.save_settings)
        self.ai_service_menu.add_radiobutton(label="Local AI", variable=self.ai_service, value="Local", command=self.save_settings)
        self.settings_menu.add_command(label="Set Local AI URL", command=self.set_local_model_url)

    def edit_prompt_window(self):
        prompt_window = ttk.Toplevel(self.root)
        prompt_window.title("Edit AI System Prompt")
        prompt_window.geometry("500x300")
        
        prompt_label = ttk.Label(prompt_window, text="Enter the system prompt for the AI:", padding=10)
        prompt_label.pack()

        prompt_text = scrolledtext.ScrolledText(prompt_window, wrap=tk.WORD, height=8, width=60)
        prompt_text.pack(pady=5, padx=10, fill=BOTH, expand=YES)
        prompt_text.insert(tk.END, self.system_prompt.get())

        button_frame = ttk.Frame(prompt_window)
        button_frame.pack(pady=10)

        def save_and_close():
            self.system_prompt.set(prompt_text.get(1.0, tk.END).strip())
            self.save_settings()
            prompt_window.destroy()
        
        def reset_prompt():
            prompt_text.delete(1.0, tk.END)
            prompt_text.insert(1.0, self.default_prompt)

        save_button = ttk.Button(button_frame, text="Save", command=save_and_close, bootstyle="success")
        save_button.pack(side=LEFT, padx=10)
        
        reset_button = ttk.Button(button_frame, text="Reset", command=reset_prompt, bootstyle="secondary")
        reset_button.pack(side=LEFT, padx=10)

    def apply_theme_to_scrolledtext(self):
        theme_name = self.style.theme.name
        if theme_name in ['cyborg', 'darkly', 'superhero', 'solar']:
            bg_color = "#3C3C3C"
            fg_color = "#FFFFFF"
        else:
            bg_color = "#FFFFFF"
            fg_color = "#000000"

        for widget in [self.raw_text_area, self.polished_text_area]:
            widget.config(bg=bg_color, fg=fg_color, insertbackground=fg_color)

    def on_theme_change(self, theme_name):
        self.style.theme_use(theme_name)
        self.apply_theme_to_scrolledtext()
        self.save_settings()

    def copy_raw_text(self):
        pyperclip.copy(self.raw_text_area.get(1.0, tk.END))

    def copy_polished_text(self):
        pyperclip.copy(self.polished_text_area.get(1.0, tk.END))

    def delete_raw_text(self):
        self.raw_text_area.delete(1.0, tk.END)

    def delete_polished_text(self):
        self.polished_text_area.delete(1.0, tk.END)

    def delete_all_text(self):
        if messagebox.askyesno("Confirm", "Delete everything in both windows?"):
            self.raw_text_area.delete(1.0, tk.END)
            self.polished_text_area.delete(1.0, tk.END)

    def save_and_new(self):
        raw_text = self.raw_text_area.get(1.0, tk.END).strip()
        if not raw_text:
            if messagebox.askyesno("Confirm", "Editor is empty. Start a new session anyway?"):
                self.raw_text_area.delete(1.0, tk.END)
                self.polished_text_area.delete(1.0, tk.END)
            return

        now = datetime.now().strftime('%Y-%m-%d-%H-%M')
        first_words = "_".join(raw_text.split()[:3]).replace("/", "_").replace("\\", "_")
        filename = os.path.join(self.savings_dir, f"{now}_{first_words or 'transcription'}.json")
        
        data_to_save = { "raw_text": raw_text, "polished_text": self.polished_text_area.get(1.0, tk.END).strip() }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)
            messagebox.showinfo("Saved", f"Session saved to:\n{filename}")
            self.raw_text_area.delete(1.0, tk.END)
            self.polished_text_area.delete(1.0, tk.END)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save file: {e}")

    def open_file(self):
        filepath = filedialog.askopenfilename( initialdir=self.savings_dir, title="Open Transcription", filetypes=(("JSON files", "*.json"), ("All files", "*.*")))
        if not filepath: return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.raw_text_area.delete(1.0, tk.END)
            self.raw_text_area.insert(tk.END, data.get("raw_text", ""))
            
            self.polished_text_area.delete(1.0, tk.END)
            self.polished_text_area.insert(tk.END, data.get("polished_text", ""))
        except Exception as e:
            messagebox.showerror("Open Error", f"Could not open file: {e}")

    def load_settings(self):
        valid_themes = ['litera', 'cyborg', 'darkly']
        theme_to_load = "litera" 

        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    self.api_key = settings.get("api_key", "")
                    self.ai_service.set(settings.get("ai_service", "Gemini"))
                    self.local_model_url = settings.get("local_model_url", "http://localhost:1234/v1/chat/completions")
                    self.system_prompt.set(settings.get("system_prompt", self.default_prompt))
                    
                    saved_theme = settings.get("theme", "litera")
                    if saved_theme in valid_themes:
                        theme_to_load = saved_theme
                    elif saved_theme == "dark":
                        theme_to_load = "cyborg"
                
                if self.api_key: genai.configure(api_key=self.api_key)
            except (json.JSONDecodeError, IOError): pass
        
        self.on_theme_change(theme_to_load)
    
    def save_settings(self):
        settings = {
            "api_key": self.api_key,
            "ai_service": self.ai_service.get(),
            "local_model_url": self.local_model_url,
            "theme": self.style.theme.name,
            "system_prompt": self.system_prompt.get()
        }
        try:
            with open(self.settings_file, 'w') as f: json.dump(settings, f, indent=4)
        except IOError: pass

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
        if self.is_recording:
            return
        self.is_recording = True
        self.record_button.config(bootstyle="danger", text="Listening...")
        
        # Start the recording process in a separate thread
        threading.Thread(target=self.record_audio_thread, daemon=True).start()

    def stop_recording(self, event):
        # This now simply signals the recording thread to stop.
        # The thread itself handles the rest.
        if self.is_recording:
            self.is_recording = False 
            self.record_button.config(text="Transcribing...")

    def record_audio_thread(self):
        """Dedicated thread for capturing audio to prevent GUI freezing."""
        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
            audio_data = []

            while self.is_recording:
                try:
                    # Record small chunks of audio in a non-blocking way
                    # by using a short timeout.
                    audio_chunk = self.recognizer.listen(source, timeout=0.1, phrase_time_limit=5)
                    audio_data.append(audio_chunk)
                except sr.WaitTimeoutError:
                    # This is expected if there's no speech, just continue the loop
                    continue
            
        if audio_data:
            # Once recording stops, process the accumulated audio
            self.root.after(0, self.process_recorded_audio, audio_data)
        else:
            # If no audio was captured, just reset the button
            self.root.after(0, lambda: self.record_button.config(bootstyle="outline-danger", text="🔴 Listen"))

    def process_recorded_audio(self, audio_chunks):
        """Processes the captured audio data."""
        try:
            # Combine the audio data chunks into a single AudioData object
            raw_data = b"".join([chunk.get_raw_data() for chunk in audio_chunks])
            sample_rate = audio_chunks[0].sample_rate
            sample_width = audio_chunks[0].sample_width
            full_audio = sr.AudioData(raw_data, sample_rate, sample_width)
            
            # Perform recognition on the audio data
            text = self.recognizer.recognize_google(full_audio)
            self.insert_transcribed_text(text)
        except sr.UnknownValueError:
            messagebox.showwarning("Speech Recognition", "Could not understand audio")
        except sr.RequestError as e:
            messagebox.showerror("Speech Recognition", f"Could not request results from Google Speech Recognition service; {e}")
        except IndexError:
             # This can happen if audio_chunks is empty but the thread still runs
            pass
        finally:
            # Reset the button state
            self.record_button.config(bootstyle="outline-danger", text="🔴 Listen")

    def insert_transcribed_text(self, text):
        try:
            start = self.raw_text_area.index("sel.first")
            end = self.raw_text_area.index("sel.last")
            self.raw_text_area.delete(start, end)
        except tk.TclError:
            pass
        self.raw_text_area.insert(tk.INSERT, " " + text)

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
            if self.ai_service.get() == "Gemini":
                if not self.api_key:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Please set your Gemini API key in Settings."))
                    return
                prompt = f"{self.system_prompt.get()}\n\n{text}"
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(prompt)
                polished_text = response.text
            else: 
                headers = {"Content-Type": "application/json"}
                data = { "model": "local-model", "messages": [{"role": "system", "content": self.system_prompt.get()}, {"role": "user", "content": text}], "temperature": 0.7 }
                response = requests.post(self.local_model_url, headers=headers, data=json.dumps(data))
                response.raise_for_status()
                polished_text = response.json()['choices'][0]['message']['content']
            
            self.root.after(0, self.display_polished_text, polished_text)

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to polish text: {e}"))

    def display_polished_text(self, text):
        """Inserts polished text at the cursor, replacing selected text if any."""
        try:
            start = self.polished_text_area.index("sel.first")
            end = self.polished_text_area.index("sel.last")
            self.polished_text_area.delete(start, end)
        except tk.TclError:
            pass
        
        self.polished_text_area.insert(tk.INSERT, text)
        pyperclip.copy(text)

if __name__ == "__main__":
    root = ttk.Window(themename="litera")
    app = SpeechToTextApp(root)
    root.mainloop()
