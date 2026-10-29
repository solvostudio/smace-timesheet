# SMACE · Timesheet collaboratori

Rendicontazione oraria a commesse mensili per chi lavora su SMACE non a tempo pieno.

- **Commesse**: ogni collaboratore apre la commessa del mese con il suo plafond di ore e registra giorno, attività e ore. Dall'elenco si vedono anche le commesse dei mesi chiusi.
- **Riepilogo**: ore contro plafond per persona e mese, dettaglio delle registrazioni, export Excel.
- **Impostazioni** (solo admin): persone e correzione dei plafond.

Questo repo contiene solo il codice. Online i dati vivono nel repo privato `solvostudio/smace-timesheet-dati` (ramo `dati`); in `data/` ci sono solo dati di esempio per l'avvio locale. Istruzioni per le modifiche in `CLAUDE.md`.

## Secrets (Streamlit Cloud)

Vedi `secrets.example.toml`.
