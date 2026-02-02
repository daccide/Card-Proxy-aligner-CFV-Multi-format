import glob
import os
import tkinter as tk
from tkinter import filedialog
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PIL import Image
from PIL import ImageFile
import warnings

# --- Parametri ---
CARD_WIDTH_MM = 59
CARD_HEIGHT_MM = 86
BLEED_MM = 0         # metti 0 se non vuoi bleed
MARGIN_MM = 5
GAP_MM = 5
warnings.simplefilter('ignore', Image.DecompressionBombWarning)
Image.MAX_IMAGE_PIXELS = None


# --- Conversione mm → punti PDF ---
def mm_to_pt(mm):
    return mm * 72 / 25.4

# Misure in punti
card_w = mm_to_pt(CARD_WIDTH_MM + 2*BLEED_MM)
card_h = mm_to_pt(CARD_HEIGHT_MM + 2*BLEED_MM)
margin = mm_to_pt(MARGIN_MM)
gap = mm_to_pt(GAP_MM)

PAGE_W, PAGE_H = A4

# --- Disegna crop marks ---
def draw_crop_marks(c, x, y, w, h, mark_len=mm_to_pt(3)):
    c.setLineWidth(0.5)

    # angolo in basso a sinistra
    c.line(x, y, x + mark_len, y)
    c.line(x, y, x, y + mark_len)

    # angolo in basso a destra
    c.line(x + w, y, x + w - mark_len, y)
    c.line(x + w, y, x + w, y + mark_len)

    # angolo in alto a sinistra
    c.line(x, y + h, x + mark_len, y + h)
    c.line(x, y + h, x, y + h - mark_len)

    # angolo in alto a destra
    c.line(x + w, y + h, x + w - mark_len, y + h)
    c.line(x + w, y + h, x + w, y + h - mark_len)

def make_proxy_pdf(image_folder, output_pdf):
    images = sorted(glob.glob(os.path.join(image_folder, "*.*")))
    if not images:
        print("⚠️ Nessuna immagine trovata nella cartella!")
        return

    c = canvas.Canvas(output_pdf, pagesize=A4)

    x = margin
    y = PAGE_H - margin - card_h

    for img_path in images:
        # Inserisci immagine mantenendo qualità
        c.drawImage(img_path, x, y, card_w, card_h, preserveAspectRatio=True, anchor='c')

        # Disegna crop marks alla dimensione TRIM (senza bleed)
        trim_w = mm_to_pt(CARD_WIDTH_MM)
        trim_h = mm_to_pt(CARD_HEIGHT_MM)
        trim_x = x + (card_w - trim_w) / 2
        trim_y = y + (card_h - trim_h) / 2
        draw_crop_marks(c, trim_x, trim_y, trim_w, trim_h)

        # Gestione griglia
        x += card_w + gap
        if x + card_w + margin > PAGE_W:
            x = margin
            y -= card_h + gap
            if y < margin:
                c.showPage()
                x = margin
                y = PAGE_H - margin - card_h

    c.save()
    print(f"✅ PDF creato: {output_pdf}")

# --- MAIN ---
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # nasconde la finestra principale

    # Seleziona cartella immagini
    image_folder = filedialog.askdirectory(title="Scegli la cartella con le immagini")
    if not image_folder:
        print("❌ Nessuna cartella selezionata.")
        exit()

    # Seleziona percorso per salvare PDF
    output_pdf = filedialog.asksaveasfilename(
        title="Scegli dove salvare il PDF",
        defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf")]
    )
    if not output_pdf:
        print("❌ Nessun percorso di salvataggio scelto.")
        exit()

    make_proxy_pdf(image_folder, output_pdf)
