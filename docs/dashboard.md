# Osservatorio — GitHub Pages

La pagina in `site/` visualizza l'analisi del motore esistente. AI-Trader resta una ricerca separata. Non vengono eseguiti ordini dal sito e non sono presenti credenziali nel browser.

Repository pubblico: [gcasaldi/ai--trade](https://github.com/gcasaldi/ai--trade). Indirizzo Pages: [Osservatorio](https://gcasaldi.github.io/ai--trade/).

## Dati privati

Credenziali e destinatari del bot vanno configurati nel `.env` locale o nei GitHub Actions secrets, mai nel codice. `.env.*` (eccetto `.env.example`), chiavi private, database locali, stato degli avvisi e snapshot AI-Trader sono esclusi da Git. La pagina pubblica soltanto l'export del modello; le posizioni inserite dall'utente restano nel suo browser.

## Aggiornamento

Il ciclo configurato in `configs/live_stub.yaml` esporta `outputs/dashboard.json` con campi espliciti: pesi obiettivo, data dei prezzi, variazione e volatilità a 20 sedute, fonti di notizie disponibili e controlli del modello. Non esporta configurazione completa, destinatari Telegram, stato del conto o registro delle operazioni simulate.

Il workflow US Market Telegram Alerts carica soltanto quel file come artifact `dashboard-public`. Al completamento, `pages.yml` pubblica HTML, CSS, JavaScript e `data.json`. Un ciclo fallito sospende le indicazioni. In assenza di un primo export compare uno stato di attesa. La pagina rilegge i dati ogni cinque minuti e ricalcola la freschezza ogni minuto.

Per un'analisi manuale senza messaggi né ordini, eseguire il workflow **Investment Dashboard Pages** con `refresh_analysis=true`. Il comando sottostante è:

```bash
uv run python scripts/run_daily.py --config configs/live_stub.yaml --dry-run --no-alerts
```

GitHub Pages deve essere abilitato con sorgente GitHub Actions. Il sito pubblica risultati del modello; i repository privati richiedono un piano GitHub che supporti Pages. Il repository non deve essere reso pubblico per tentare di aggirare questo requisito.

## Semantica del piano

- Il capitale inserito comprende liquidità e valore attuale delle posizioni, in EUR.
- Gli importi personali e gli ingressi in USD sono salvati esclusivamente in localStorage e si possono azzerare. Nessuna conversione valutaria o sincronizzazione broker è implicita.
- Gli acquisti e le riduzioni sono differenze tra allocazioni obiettivo e importi inseriti. Senza posizioni inserite, un peso zero significa non comprare, non vendere.
- I livelli di stop/obiettivo sono indicativi e derivano dalle regole del modello. Se manca l'ingresso effettivo, vengono chiaramente etichettati come ipotetici sulla chiusura.
- Non sono verificati prezzi di esecuzione né quantità acquistabili. Le commissioni e l'aliquota configurata sono stime, non risultati realizzati.
- Un'analisi più vecchia di 26 ore o prezzi oltre la soglia configurata (48 ore nel live) bloccano le proposte. Il controllo è conservativo a ore solari, non un calendario delle festività di borsa.
- Prezzi rettificati giornalieri non equivalgono a quotazioni live. Il sito non promette una ricerca esaustiva delle notizie o rendimenti migliori.

## Verifica locale

```bash
python scripts/build_pages.py
node --test tests/test_dashboard_planner.cjs
python -m unittest discover -s tests -p test_dashboard.py
python -m http.server 8000 --directory _site
```

Il test browser opzionale `tests/browser_dashboard_smoke.py` richiede Playwright e Chrome. Usa dati sintetici intercettati solo nel browser del test; non li scrive nell'export pubblico.
