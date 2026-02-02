import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from fpdf import FPDF
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile
from pathlib import Path
import json
import threading

# ---------------- Parametri ----------------
CARD_WIDTH_MM = 59
CARD_HEIGHT_MM = 86
GAP_MM = 5
PAGE_W = 210  # A4 mm
PAGE_H = 297  # A4 mm

CONFIG_FILE = "../card_printer_config.json"


# ---------- funzioni utili ----------
def mm_to_px(mm, dpi):
    return int(mm / 25.4 * dpi)


def draw_crop_marks(pdf, x, y, w, h, mark_len=3):
    pdf.set_line_width(0.1)
    pdf.line(x, y, x + mark_len, y)
    pdf.line(x, y, x, y + mark_len)
    pdf.line(x + w, y, x + w - mark_len, y)
    pdf.line(x + w, y, x + w, y + mark_len)
    pdf.line(x, y + h, x + mark_len, y + h)
    pdf.line(x, y + h, x, y + h - mark_len)
    pdf.line(x + w, y + h, x + w - mark_len, y + h)
    pdf.line(x + w, y + h, x + w, y + h - mark_len)


def list_image_files(folder):
    exts = (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif")
    return sorted([entry.path for entry in os.scandir(folder) if entry.is_file() and entry.name.lower().endswith(exts)])


def process_image_to_temp(img_path, target_w, target_h):
    try:
        pil_img = Image.open(img_path)

        if pil_img.mode == 'RGBA':
            pass
        elif pil_img.mode not in ('RGB', 'L'):
            pil_img = pil_img.convert('RGB')

        w, h = pil_img.size
        scale = min(target_w / w, target_h / h, 1.0)

        if scale < 1.0:
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            pil_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        pil_img.save(tmp.name, format="PNG", compress_level=6, optimize=False)
        tmp.close()
        return tmp.name
    except Exception as e:
        print(f"⚠️ Errore processing {img_path}: {e}")
        return None


def compute_grid_positions(page_w, page_h, card_w, card_h, gap):
    positions = []
    cols = int((page_w + gap) // (card_w + gap))
    rows = int((page_h + gap) // (card_h + gap))
    cols = max(1, cols)
    rows = max(1, rows)

    grid_w = cols * card_w + (cols - 1) * gap
    grid_h = rows * card_h + (rows - 1) * gap

    x_start = (page_w - grid_w) / 2
    y_start = (page_h - grid_h) / 2

    for r in range(rows):
        y = y_start + r * (card_h + gap)
        for c in range(cols):
            x = x_start + c * (card_w + gap)
            positions.append((x, y))
    return positions


def make_pdf(image_folder, output_pdf, logo_path, progress_callback,
             dpi, card_w, card_h, gap, show_crop_marks, workers, include_back):
    images = list_image_files(image_folder)
    if not images:
        return False, "Nessuna immagine trovata!"

    card_w_px = mm_to_px(card_w, dpi)
    card_h_px = mm_to_px(card_h, dpi)

    positions = compute_grid_positions(PAGE_W, PAGE_H, card_w, card_h, gap)
    slots_per_page = len(positions)
    total_images = len(images)

    temp_files = [None] * len(images)
    progress_callback(0, f"Elaborazione {total_images} immagini...")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        future_to_idx = {ex.submit(process_image_to_temp, images[i], card_w_px, card_h_px): i
                         for i in range(len(images))}
        completed = 0
        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            tmp = fut.result()
            if tmp:
                temp_files[idx] = tmp
            completed += 1
            progress_callback(min(50.0, completed / total_images * 50.0),
                              f"Processate {completed}/{total_images} immagini")

    temp_files = [f for f in temp_files if f is not None]

    pdf = FPDF(unit='mm', format='A4')
    pdf.set_auto_page_break(False)
    pdf.set_compression(True)

    chunks = [temp_files[i:i + slots_per_page] for i in range(0, len(temp_files), slots_per_page)]

    if include_back:
        processed_count = 0
        total_steps = len(chunks) * 2

        for chunk in chunks:
            # RETRO
            pdf.add_page()
            for slot_idx, slot_pos in enumerate(positions):
                if slot_idx >= len(chunk):
                    break
                x_f, y_f = slot_pos
                x_b = PAGE_W - x_f - card_w
                y_b = y_f
                pdf.image(logo_path, x=x_b, y=y_b, w=card_w, h=card_h)

            processed_count += 1
            progress_callback(50 + (processed_count / total_steps) * 25,
                              f"Creazione PDF: pagina {processed_count}/{total_steps}")

            # FRONTE
            pdf.add_page()
            for slot_idx, slot_pos in enumerate(positions):
                if slot_idx >= len(chunk):
                    break
                img_file = chunk[slot_idx]
                x_f, y_f = slot_pos
                pdf.image(img_file, x=x_f, y=y_f, w=card_w, h=card_h)
                if show_crop_marks:
                    draw_crop_marks(pdf, x_f, y_f, card_w, card_h)

            processed_count += 1
            progress_callback(75 + (processed_count / total_steps) * 25,
                              f"Creazione PDF: pagina {processed_count}/{total_steps}")

        mode_msg = "duplex"
    else:
        processed_count = 0
        total_steps = len(chunks)

        for chunk in chunks:
            pdf.add_page()
            for slot_idx, slot_pos in enumerate(positions):
                if slot_idx >= len(chunk):
                    break
                img_file = chunk[slot_idx]
                x_f, y_f = slot_pos
                pdf.image(img_file, x=x_f, y=y_f, w=card_w, h=card_h)
                if show_crop_marks:
                    draw_crop_marks(pdf, x_f, y_f, card_w, card_h)

            processed_count += 1
            progress_callback(50 + (processed_count / total_steps) * 45,
                              f"Creazione PDF: pagina {processed_count}/{total_steps}")

        mode_msg = "solo fronte"

    progress_callback(95, "Salvataggio PDF...")
    pdf.output(output_pdf)

    for f in temp_files:
        try:
            os.remove(f)
        except:
            pass

    progress_callback(100, "Completato!")
    return True, f"PDF creato ({mode_msg}): {len(chunks)} pagine, {len(temp_files)} carte"


# =============== INTERFACCIA GRAFICA ===============

class CardPrinterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🎴 Card Printer Pro - Vanguard Edition")
        self.root.geometry("700x850")
        self.root.resizable(False, False)

        # Variabili
        self.image_folder = tk.StringVar()
        self.logo_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.dpi_var = tk.IntVar(value=1200)
        self.card_width_var = tk.DoubleVar(value=59)
        self.card_height_var = tk.DoubleVar(value=86)
        self.gap_var = tk.DoubleVar(value=5)
        self.show_crop_var = tk.BooleanVar(value=True)
        self.include_back_var = tk.BooleanVar(value=True)
        self.workers_var = tk.IntVar(value=os.cpu_count() or 4)

        # Trace per aggiornamento automatico
        self.card_width_var.trace_add('write', lambda *args: self.update_info())
        self.card_height_var.trace_add('write', lambda *args: self.update_info())
        self.gap_var.trace_add('write', lambda *args: self.update_info())

        self.load_config()
        self.create_ui()

    def create_ui(self):
        style = ttk.Style()
        style.theme_use('clam')

        # Header
        header = tk.Frame(self.root, bg='#2c3e50', height=80)
        header.pack(fill='x')
        header.pack_propagate(False)

        title = tk.Label(header, text="🎴 Card Printer Pro",
                         font=('Arial', 24, 'bold'), bg='#2c3e50', fg='white')
        title.pack(pady=20)

        # Main container
        main = tk.Frame(self.root, padx=20, pady=20)
        main.pack(fill='both', expand=True)

        # === SEZIONE FILE ===
        file_frame = ttk.LabelFrame(main, text="📁 File e Cartelle", padding=15)
        file_frame.pack(fill='x', pady=(0, 15))

        tk.Label(file_frame, text="Cartella Immagini (Fronte):").grid(row=0, column=0, sticky='w', pady=5)
        tk.Entry(file_frame, textvariable=self.image_folder, width=40, state='readonly').grid(row=0, column=1, padx=5)
        ttk.Button(file_frame, text="Sfoglia...", command=self.browse_images).grid(row=0, column=2)

        self.logo_label = tk.Label(file_frame, text="Logo Retro:")
        self.logo_label.grid(row=1, column=0, sticky='w', pady=5)
        self.logo_entry = tk.Entry(file_frame, textvariable=self.logo_path, width=40, state='readonly')
        self.logo_entry.grid(row=1, column=1, padx=5)
        self.logo_button = ttk.Button(file_frame, text="Sfoglia...", command=self.browse_logo)
        self.logo_button.grid(row=1, column=2)

        tk.Label(file_frame, text="File PDF Output:").grid(row=2, column=0, sticky='w', pady=5)
        tk.Entry(file_frame, textvariable=self.output_path, width=40, state='readonly').grid(row=2, column=1, padx=5)
        ttk.Button(file_frame, text="Sfoglia...", command=self.browse_output).grid(row=2, column=2)

        # === SEZIONE MODALITÀ STAMPA ===
        mode_frame = ttk.LabelFrame(main, text="🖨️ Modalità Stampa", padding=15)
        mode_frame.pack(fill='x', pady=(0, 15))

        duplex_check = ttk.Checkbutton(mode_frame, text="Includi retro (modalità duplex)",
                                       variable=self.include_back_var,
                                       command=self.toggle_back_mode)
        duplex_check.pack(anchor='w', pady=5)

        self.mode_info = tk.Label(mode_frame, text="", fg='#27ae60', font=('Arial', 9))
        self.mode_info.pack(anchor='w', pady=5)
        self.update_mode_info()

        # === SEZIONE IMPOSTAZIONI ===
        settings_frame = ttk.LabelFrame(main, text="⚙️ Impostazioni Avanzate", padding=15)
        settings_frame.pack(fill='x', pady=(0, 15))

        dpi_frame = tk.Frame(settings_frame)
        dpi_frame.pack(fill='x', pady=5)
        tk.Label(dpi_frame, text="DPI Qualità:").pack(side='left')
        ttk.Scale(dpi_frame, from_=600, to=2400, variable=self.dpi_var,
                  orient='horizontal', length=300, command=self.update_dpi_label).pack(side='left', padx=10)
        self.dpi_label = tk.Label(dpi_frame, text="1200 DPI", font=('Arial', 10, 'bold'))
        self.dpi_label.pack(side='left')

        dims_frame = tk.Frame(settings_frame)
        dims_frame.pack(fill='x', pady=5)
        tk.Label(dims_frame, text="Dimensioni Carta (mm):").pack(side='left')
        tk.Label(dims_frame, text="L:").pack(side='left', padx=(20, 2))
        ttk.Spinbox(dims_frame, from_=30, to=100, textvariable=self.card_width_var,
                    width=6, format="%.1f").pack(side='left')
        tk.Label(dims_frame, text="A:").pack(side='left', padx=(10, 2))
        ttk.Spinbox(dims_frame, from_=30, to=150, textvariable=self.card_height_var,
                    width=6, format="%.1f").pack(side='left')
        tk.Label(dims_frame, text="Gap:").pack(side='left', padx=(10, 2))
        ttk.Spinbox(dims_frame, from_=0, to=20, textvariable=self.gap_var,
                    width=6, format="%.1f").pack(side='left')

        workers_frame = tk.Frame(settings_frame)
        workers_frame.pack(fill='x', pady=5)
        tk.Label(workers_frame, text="Thread Elaborazione:").pack(side='left')
        ttk.Spinbox(workers_frame, from_=1, to=32, textvariable=self.workers_var,
                    width=6).pack(side='left', padx=10)
        tk.Label(workers_frame, text=f"(CPU: {os.cpu_count()} core)").pack(side='left')

        ttk.Checkbutton(settings_frame, text="Mostra segni di taglio",
                        variable=self.show_crop_var).pack(anchor='w', pady=5)

        # === SEZIONE INFO ===
        info_frame = ttk.LabelFrame(main, text="ℹ️ Informazioni", padding=15)
        info_frame.pack(fill='x', pady=(0, 15))

        self.info_text = tk.Text(info_frame, height=4, wrap='word', state='disabled',
                                 bg='#ecf0f1', relief='flat')
        self.info_text.pack(fill='x')
        self.update_info()

        # === PROGRESS BAR ===
        progress_frame = tk.Frame(main)
        progress_frame.pack(fill='x', pady=(0, 15))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                            maximum=100, length=660)
        self.progress_bar.pack(fill='x')

        self.progress_label = tk.Label(progress_frame, text="Pronto", fg='#7f8c8d')
        self.progress_label.pack(pady=5)

        # === BOTTONI AZIONE ===
        buttons_frame = tk.Frame(main)
        buttons_frame.pack(fill='x')

        self.generate_btn = ttk.Button(buttons_frame, text="🚀 Genera PDF",
                                       command=self.generate_pdf_thread,
                                       style='Accent.TButton')
        self.generate_btn.pack(side='left', fill='x', expand=True, padx=(0, 5))

        ttk.Button(buttons_frame, text="💾 Salva Impostazioni",
                   command=self.save_config).pack(side='left', fill='x', expand=True, padx=5)

        ttk.Button(buttons_frame, text="ℹ️ Info",
                   command=self.show_about).pack(side='left', padx=(5, 0))

        # Style per bottone principale
        style = ttk.Style()
        style.configure('Accent.TButton', font=('Arial', 12, 'bold'))

    def toggle_back_mode(self):
        if self.include_back_var.get():
            self.logo_label.config(state='normal')
            self.logo_entry.config(state='readonly')
            self.logo_button.config(state='normal')
        else:
            self.logo_label.config(state='disabled')
            self.logo_entry.config(state='disabled')
            self.logo_button.config(state='disabled')
        self.update_mode_info()
        self.update_info()

    def update_mode_info(self):
        if self.include_back_var.get():
            self.mode_info.config(text="✓ Stampa duplex: ogni foglio avrà fronte (carte) e retro (logo)",
                                  fg='#27ae60')
        else:
            self.mode_info.config(text="○ Solo fronte: verranno stampate solo le carte (senza retro)",
                                  fg='#e67e22')

    def update_dpi_label(self, value):
        self.dpi_label.config(text=f"{int(float(value))} DPI")
        self.update_info()

    def update_info(self):
        try:
            dpi = self.dpi_var.get()
            card_w = self.card_width_var.get()
            card_h = self.card_height_var.get()
            gap = self.gap_var.get()

            positions = compute_grid_positions(PAGE_W, PAGE_H, card_w, card_h, gap)
            cards_per_page = len(positions)

            card_w_px = mm_to_px(card_w, dpi)
            card_h_px = mm_to_px(card_h, dpi)

            mode = "Duplex (fronte-retro)" if self.include_back_var.get() else "Solo fronte"

            info = f"📏 Risoluzione carta: {card_w_px}x{card_h_px} px\n"
            info += f"📄 Carte per pagina: {cards_per_page}\n"
            info += f"🖨️ Modalità: {mode}\n"
            info += f"⚡ Motore: Pillow-SIMD (alta velocità)"

            self.info_text.config(state='normal')
            self.info_text.delete(1.0, 'end')
            self.info_text.insert(1.0, info)
            self.info_text.config(state='disabled')
        except:
            pass

    def browse_images(self):
        folder = filedialog.askdirectory(title="Seleziona cartella immagini")
        if folder:
            self.image_folder.set(folder)
            if not self.output_path.get():
                default_output = os.path.join(folder, "carte_stampabili.pdf")
                self.output_path.set(default_output)

    def browse_logo(self):
        file = filedialog.askopenfilename(
            title="Seleziona logo retro",
            filetypes=[("Immagini", "*.png *.jpg *.jpeg *.bmp *.tiff")]
        )
        if file:
            self.logo_path.set(file)

    def browse_output(self):
        file = filedialog.asksaveasfilename(
            title="Salva PDF come",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")]
        )
        if file:
            self.output_path.set(file)

    def progress_callback(self, value, message):
        self.progress_var.set(value)
        self.progress_label.config(text=message)
        self.root.update_idletasks()

    def generate_pdf_worker(self):
        """Funzione worker che gira in un thread separato"""
        try:
            success, message = make_pdf(
                self.image_folder.get(),
                self.output_path.get(),
                self.logo_path.get(),
                self.progress_callback,
                self.dpi_var.get(),
                self.card_width_var.get(),
                self.card_height_var.get(),
                self.gap_var.get(),
                self.show_crop_var.get(),
                self.workers_var.get(),
                self.include_back_var.get()
            )

            # Usa after per mostrare il messaggio nel thread principale
            if success:
                self.root.after(0, lambda: messagebox.showinfo("✅ Successo!", message))
            else:
                self.root.after(0, lambda: messagebox.showerror("❌ Errore", message))

        except Exception as e:
            error_msg = f"Errore durante la generazione:\n{str(e)}"
            self.root.after(0, lambda: messagebox.showerror("❌ Errore", error_msg))
        finally:
            # Riabilita il bottone nel thread principale
            self.root.after(0, lambda: self.generate_btn.config(state='normal'))

    def generate_pdf_thread(self):
        """Avvia la generazione in un thread separato"""
        # Validazione
        if not self.image_folder.get():
            messagebox.showerror("Errore", "Seleziona la cartella immagini!")
            return
        if self.include_back_var.get() and not self.logo_path.get():
            messagebox.showerror("Errore", "Seleziona il logo per il retro o disabilita la modalità duplex!")
            return
        if not self.output_path.get():
            messagebox.showerror("Errore", "Specifica il file PDF di output!")
            return

        # Disabilita bottone
        self.generate_btn.config(state='disabled')

        # Avvia thread
        thread = threading.Thread(target=self.generate_pdf_worker, daemon=True)
        thread.start()

    def save_config(self):
        config = {
            'dpi': self.dpi_var.get(),
            'card_width': self.card_width_var.get(),
            'card_height': self.card_height_var.get(),
            'gap': self.gap_var.get(),
            'show_crop': self.show_crop_var.get(),
            'include_back': self.include_back_var.get(),
            'workers': self.workers_var.get(),
            'last_logo': self.logo_path.get(),
            'last_folder': self.image_folder.get()
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
            messagebox.showinfo("💾 Salvato", "Impostazioni salvate con successo!")
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile salvare: {e}")

    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                self.dpi_var.set(config.get('dpi', 1200))
                self.card_width_var.set(config.get('card_width', 59))
                self.card_height_var.set(config.get('card_height', 86))
                self.gap_var.set(config.get('gap', 5))
                self.show_crop_var.set(config.get('show_crop', True))
                self.include_back_var.set(config.get('include_back', True))
                self.workers_var.set(config.get('workers', os.cpu_count() or 4))
                self.logo_path.set(config.get('last_logo', ''))
                self.image_folder.set(config.get('last_folder', ''))
        except:
            pass

    def show_about(self):
        about_text = """
🎴 Card Printer Pro - Vanguard Edition
Versione 2.1 (Pillow-SIMD)

Funzionalità:
- Stampa duplex automatica o solo fronte
- Supporto alta risoluzione (fino a 2400 DPI)
- Elaborazione parallela multi-thread
- Segni di taglio opzionali
- Configurazione salvabile
- Interfaccia non bloccante

Motore: Pillow-SIMD (veloce e compatibile)
Creato per la community di Vanguard! 🃏
        """
        messagebox.showinfo("Info", about_text)


# =============== AVVIO APP ===============
if __name__ == "__main__":
    root = tk.Tk()
    app = CardPrinterApp(root)
    root.mainloop()