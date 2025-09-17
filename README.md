# 📄 README – Card PDF Generator

Questo programma permette di creare un **PDF pronto per la stampa fronte-retro** con:  
- **Carte (immagini)** disposte su griglia in formato A4.  
- **Crop marks** (segni di taglio) per il rifilo.  
- **Loghi sul retro**, posizionati esattamente sotto ogni carta.  
- **Supporto stampa fronte-retro manuale**.  
- **Barra di avanzamento** per seguire la generazione del PDF.  

---

## 🚀 Funzionalità
- Selezione della cartella con le immagini delle carte.  
- Selezione del file immagine da usare come **logo retro**.  
- Salvataggio del PDF finale con **layout automatico** delle carte.  
- Possibilità di scegliere il **flip mode** (short/long) per allineare correttamente fronte e retro.  

---

## 📦 Requisiti

### Installazione pacchetti
Assicurati di avere **Python 3.9+**.  
Installa le librerie necessarie:

```bash
pip install fpdf2 Pillow opencv-python 
```

---

## ▶️ Utilizzo

1. Avvia lo script:

```bash
python main.py
```

2. Il programma chiederà di:  
   - Scegliere la cartella con le **immagini delle carte**.  
   - Scegliere un file **logo retro** (PNG/JPG).  
   - Scegliere dove salvare il **PDF finale**.  

3. Verrà mostrata una **barra di avanzamento** mentre il PDF viene generato.  

4. Una volta pronto, stampa il PDF in modalità **fronte-retro manuale**.  
   - Quando richiesto, reinserisci i fogli nel vassoio.  
   - Se il retro non combacia, prova a cambiare il `flip_mode` da `"short"` a `"long"`.  

---

## ⚠️ Note importanti
- Non tutte le stampanti gestiscono il duplex automatico → in molti casi il fronte-retro è manuale.  
- È consigliato fare una **stampa di prova** con poche carte prima di stampare l’intero set.  
- Puoi modificare le misure (es. dimensioni carte, margini, gap) direttamente nel codice:  

```python
CARD_WIDTH_MM = 59
CARD_HEIGHT_MM = 86
MARGIN_MM = 5
GAP_MM = 5
```

---

## 🖨️ Qualità di stampa
- Il PDF è generato con immagini ad alta risoluzione (fino a 2400 dpi).  
- Per un risultato migliore, usa immagini sorgente di buona qualità (min. 300–600 dpi).  

---

## ✅ Esempio di workflow
1. Metti le immagini delle carte in una cartella `carte/`.  
2. Prepara un logo `logo.png`.  
3. Avvia il programma → scegli cartella `carte/`, poi `logo.png`, poi `output.pdf`.  
4. Stampa `output.pdf` in fronte-retro manuale.  
5. Rifila le carte seguendo i crop marks.  
