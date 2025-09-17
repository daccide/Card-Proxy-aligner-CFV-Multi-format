import os
import tkinter as tk
from tkinter import filedialog, ttk
from fpdf import FPDF
import cv2
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import tempfile

# ---------------- Parametri ----------------
CARD_WIDTH_MM = 59
CARD_HEIGHT_MM = 86
MARGIN_MM = 5
GAP_MM = 5
DPI = 1200  # puoi alzare fino a 2400 o 3000 se serve più dettaglio

PAGE_W = 210  # A4 mm
PAGE_H = 297  # A4 mm

WORKERS = min(8, (os.cpu_count() or 2))  # thread per resize

# ---------- funzioni utili ----------
def mm_to_px(mm, dpi):
    return int(mm / 25.4 * dpi)

CARD_W_PX = mm_to_px(CARD_WIDTH_MM, DPI)
CARD_H_PX = mm_to_px(CARD_HEIGHT_MM, DPI)

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

# Ridimensiona immagine mantenendo aspect ratio fino al target in pixel
def process_image_to_temp(img_path):
    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    h, w = img.shape[:2]
    scale = min(CARD_W_PX / w, CARD_H_PX / h, 1.0)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    if scale < 1.0:
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    else:
        resized = img

    if resized.ndim == 2:  # grayscale
        pil_img = Image.fromarray(resized)
    else:
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    pil_img.save(tmp.name, format="PNG")
    tmp.close()
    return tmp.name

def compute_grid_positions():
    positions = []
    cols = int((PAGE_W - 2*MARGIN_MM + GAP_MM) // (CARD_WIDTH_MM + GAP_MM))
    rows = int((PAGE_H - 2*MARGIN_MM + GAP_MM) // (CARD_HEIGHT_MM + GAP_MM))
    cols = max(1, cols)
    rows = max(1, rows)
    for r in range(rows):
        y = MARGIN_MM + r * (CARD_HEIGHT_MM + GAP_MM)
        for c in range(cols):
            x = MARGIN_MM + c * (CARD_WIDTH_MM + GAP_MM)
            positions.append((x, y))
    return positions

def transform_positions_for_back(positions, flip_mode):
    transformed = []
    for x, y in positions:
        if flip_mode == "long":
            x_m = PAGE_W - x - CARD_WIDTH_MM
            y_m = y
        elif flip_mode == "short":
            x_m = x
            y_m = PAGE_H - y - CARD_HEIGHT_MM
        else:
            x_m, y_m = x, y
        transformed.append((x_m, y_m))
    return transformed

def make_duplex_pdf_with_logo(image_folder, output_pdf, logo_path, flip_mode, progress_var):
    images = list_image_files(image_folder)
    if not images:
        print("⚠️ Nessuna immagine trovata nella cartella!")
        return

    positions = compute_grid_positions()
    slots_per_page = len(positions)
    total_images = len(images)

    temp_files = []
    progress_var.set(0)
    root.update_idletasks()

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(process_image_to_temp, p): p for p in images}
        completed = 0
        for fut in as_completed(futures):
            tmp = fut.result()
            if tmp:
                temp_files.append(tmp)
            completed += 1
            progress_var.set(min(40.0, completed / total_images * 40.0))
            root.update_idletasks()

    temp_files = sorted(temp_files, key=lambda x: images[temp_files.index(x)] if x in temp_files else "")

    pdf = FPDF(unit='mm', format='A4')
    pdf.set_auto_page_break(False)

    chunks = [temp_files[i:i+slots_per_page] for i in range(0, len(temp_files), slots_per_page)]
    back_positions = transform_positions_for_back(positions, flip_mode)

    processed_count = 0
    total_steps = len(chunks) * 2

    for chunk_index, chunk in enumerate(chunks):
        # --- RETRO ---
        pdf.add_page()
        for slot_idx, slot_pos in enumerate(back_positions):
            if slot_idx >= len(chunk):
                break
            x_b, y_b = slot_pos
            pdf.image(logo_path, x=x_b, y=y_b, w=CARD_WIDTH_MM, h=CARD_HEIGHT_MM)

        processed_count += 1
        progress_var.set(45 + (processed_count / total_steps) * 30)
        root.update_idletasks()

        # --- FRONTE ---
        pdf.add_page()
        for slot_idx, slot_pos in enumerate(positions):
            if slot_idx >= len(chunk):
                break
            img_file = chunk[slot_idx]
            x_f, y_f = slot_pos
            pdf.image(img_file, x=x_f, y=y_f, w=CARD_WIDTH_MM, h=CARD_HEIGHT_MM)
            draw_crop_marks(pdf, x_f, y_f, CARD_WIDTH_MM, CARD_HEIGHT_MM)

        processed_count += 1
        progress_var.set(75 + (processed_count / total_steps) * 25)
        root.update_idletasks()

    pdf.output(output_pdf)
    for f in temp_files:
        try:
            os.remove(f)
        except Exception:
            pass

    progress_var.set(100)
    root.update_idletasks()
    print(f"✅ PDF duplex creato: {output_pdf}")

# ------------------- MAIN UI -------------------
root = tk.Tk()
root.withdraw()

image_folder = filedialog.askdirectory(title="Scegli la cartella con le immagini (FRONTE)")
if not image_folder:
    print("❌ Nessuna cartella selezionata.")
    raise SystemExit

logo_path = filedialog.askopenfilename(
    title="Seleziona il logo da usare sul RETRO",
    filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.tiff")]
)
if not logo_path:
    print("❌ Nessun logo selezionato.")
    raise SystemExit

output_pdf = filedialog.asksaveasfilename(
    title="Scegli dove salvare il PDF",
    defaultextension=".pdf",
    filetypes=[("PDF files", "*.pdf")]
)
if not output_pdf:
    print("❌ Nessun percorso di salvataggio scelto.")
    raise SystemExit

# finestra di progresso
progress_win = tk.Toplevel()
progress_win.title("Elaborazione immagini (duplex)...")
progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(progress_win, variable=progress_var, maximum=100, length=480)
progress_bar.pack(padx=20, pady=12)
progress_label = tk.Label(progress_win, text="0%")
progress_label.pack()

def update_label(*args):
    progress_label.config(text=f"{int(progress_var.get())}%")

progress_var.trace("w", update_label)
progress_win.update_idletasks()

# esegui con flip 'short' (default per Brother HL-1210W)
make_duplex_pdf_with_logo(image_folder, output_pdf, logo_path, "long", progress_var)

progress_win.destroy()
root.destroy()
