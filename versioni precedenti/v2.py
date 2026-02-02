import os
import tkinter as tk
from tkinter import filedialog, ttk
from fpdf import FPDF
import cv2
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import tempfile

# --- Parametri ---
CARD_WIDTH_MM = 59
CARD_HEIGHT_MM = 86
MARGIN_MM = 5
GAP_MM = 5
DPI = 1200

PAGE_W = 210  # A4 mm
PAGE_H = 297  # A4 mm

# --- Conversione mm → pixel per alta qualità ---
def mm_to_px(mm, dpi):
    return int(mm / 25.4 * dpi)

CARD_W_PX = mm_to_px(CARD_WIDTH_MM, DPI)
CARD_H_PX = mm_to_px(CARD_HEIGHT_MM, DPI)

# --- Disegna crop marks ---
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

# --- Ridimensiona immagine in memoria ---
def process_image(img_path):
    img = cv2.imread(img_path)
    if img is None:
        return None

    h, w = img.shape[:2]
    scale = min(CARD_W_PX / w, CARD_H_PX / h, 1.0)
    new_w = int(w * scale)
    new_h = int(h * scale)
    if scale < 1.0:
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    else:
        resized = img

    rgb_image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb_image)
    # Salva in file temporaneo perché FPDF non supporta BytesIO
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    pil_img.save(tmp_file.name, format='PNG')
    tmp_file.close()
    return tmp_file.name

# --- Creazione PDF con barra di avanzamento ---
def make_pdf(image_folder, output_pdf, progress_var):
    images = [entry.path for entry in os.scandir(image_folder)
              if entry.is_file() and entry.name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff"))]
    images.sort()
    if not images:
        print("⚠️ Nessuna immagine trovata nella cartella!")
        return

    temp_files = []
    total = len(images)
    progress_var.set(0)

    # Ridimensionamento in parallelo
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(process_image, path): path for path in images}
        for i, future in enumerate(as_completed(futures), 1):
            tmp_file = future.result()
            if tmp_file:
                temp_files.append(tmp_file)
            progress_var.set(i / total * 50)  # metà barra per preparazione immagini
            root.update_idletasks()

    pdf = FPDF(unit='mm', format='A4')
    pdf.set_auto_page_break(False)

    x = MARGIN_MM
    y = PAGE_H - MARGIN_MM - CARD_HEIGHT_MM
    pdf.add_page()

    # Inserimento immagini nel PDF
    for i, img_path in enumerate(temp_files, 1):
        pdf.image(img_path, x=x, y=y, w=CARD_WIDTH_MM, h=CARD_HEIGHT_MM)
        draw_crop_marks(pdf, x, y, CARD_WIDTH_MM, CARD_HEIGHT_MM)

        x += CARD_WIDTH_MM + GAP_MM
        if x + CARD_WIDTH_MM + MARGIN_MM > PAGE_W:
            x = MARGIN_MM
            y -= CARD_HEIGHT_MM + GAP_MM
            if y < MARGIN_MM:
                pdf.add_page()
                x = MARGIN_MM
                y = PAGE_H - MARGIN_MM - CARD_HEIGHT_MM

        progress_var.set(50 + i / len(temp_files) * 50)  # seconda metà della barra
        root.update_idletasks()

    pdf.output(output_pdf)
    for f in temp_files:
        os.remove(f)
    progress_var.set(100)
    root.update_idletasks()
    print(f"✅ PDF ad alta qualità 1200 DPI creato: {output_pdf}")

# --- MAIN ---
root = tk.Tk()
root.withdraw()

image_folder = filedialog.askdirectory(title="Scegli la cartella con le immagini")
if not image_folder:
    print("❌ Nessuna cartella selezionata.")
    exit()

output_pdf = filedialog.asksaveasfilename(
    title="Scegli dove salvare il PDF",
    defaultextension=".pdf",
    filetypes=[("PDF files", "*.pdf")]
)
if not output_pdf:
    print("❌ Nessun percorso di salvataggio scelto.")
    exit()

# Barra di avanzamento
progress_win = tk.Toplevel()
progress_win.title("Elaborazione immagini...")
progress_var = tk.DoubleVar()
progress_bar = ttk.Progressbar(progress_win, variable=progress_var, maximum=100, length=400)
progress_bar.pack(padx=20, pady=20)
progress_label = tk.Label(progress_win, text="0%")
progress_label.pack()

def update_label(*args):
    progress_label.config(text=f"{int(progress_var.get())}%")

progress_var.trace("w", update_label)
progress_win.update_idletasks()

make_pdf(image_folder, output_pdf, progress_var)

progress_win.destroy()
root.destroy()
