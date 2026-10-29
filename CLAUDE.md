# SMACE · Timesheet collaboratori

Istruzioni per Claude quando lavora su questo repo, di solito su richiesta dell'admin dello strumento (area AFC & Operations di SMACE), che non è una sviluppatrice: spiegale le modifiche in italiano semplice, senza gergo tecnico, e chiedile conferma prima di cambiare qualcosa che tocca i dati.

## Cos'è

App Streamlit per la rendicontazione oraria di chi lavora su SMACE non a tempo pieno. Ogni collaboratore apre a inizio mese la sua **commessa** (persona + mese + plafond di ore del suo contratto) e dentro registra giorno, attività (testo libero) e ore. Il plafond avvisa ma non blocca: lo sforamento si conferma fuori dallo strumento, come l'approvazione della fattura di fine mese. L'admin vede tutto e gestisce le persone.

## Struttura

- `app.py`: interfaccia (accesso, Commesse, Riepilogo con export Excel, Impostazioni solo admin).
- `ts/calcoli.py`: ore, plafond, stati. Funzioni pure, coperte da `tests/`.
- `ts/store.py`: lettura e scrittura delle tabelle CSV (`persone`, `commesse`, `registrazioni`). In locale scrive in `data/`, che contiene solo dati di esempio; online scrive sul ramo `dati` del repo **privato** `solvostudio/smace-timesheet-dati` tramite API GitHub.
- `ts/theme.py`: palette e stile SMACE, condivisi con il Financial Plan.

## Regole

- **Questo repo è pubblico: qui solo codice.** Mai committare dati veri, nomi di collaboratori, password o token. Le ore vere stanno nel repo privato `solvostudio/smace-timesheet-dati`, ramo `dati`: non modificarlo, ribasarlo o cancellarlo. Le colonne delle tabelle si cambiano solo aggiornando `TABELLE` in `ts/store.py` in modo compatibile con i CSV già esistenti (aggiungere colonne va bene, rinominarle o toglierle no).
- Ogni push su `main` ripubblica l'app online da sola, quindi prima di consegnare una modifica esegui i test:
  - `pip install -r requirements.txt pytest`
  - `python -m pytest -q tests`
  - una prova dell'interfaccia con `streamlit.testing.v1.AppTest` sul flusso toccato.
- Password e token stanno nei secrets di Streamlit, mai nel repo. Una persona nuova aggiunta in Impostazioni può entrare solo dopo che le è stata assegnata una password nei secrets: dillo all'admin quando serve.
- Stile del codice: italiano per nomi e commenti, funzioni brevi, nessuna dipendenza nuova senza motivo.

## Avvio locale

```
pip install -r requirements.txt
streamlit run app.py
```

Senza secrets l'app usa i CSV in `data/` e non chiede password.
