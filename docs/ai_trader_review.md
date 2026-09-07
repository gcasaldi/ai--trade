# Verifica AI-Trader — 7 settembre 2026

## Esito

Il campione pubblico contiene operazioni buy/sell reali nel senso di record pubblicati dalla piattaforma, non eseguiti verificati presso un broker. Non dimostra un vantaggio economico rispetto al nostro agente. Non sostituire il motore sulla base di questo campione.

Revisione upstream esaminata: `d03ff6c056b32ced735adf7c19ed8175adb1c8df`.
Il backend riceve le operazioni dagli agenti esterni; nel percorso esaminato non genera un piano di investimento per il nostro capitale.

Fonti: [README](https://github.com/HKUDS/AI-Trader), [implementazione segnali](https://github.com/HKUDS/AI-Trader/blob/d03ff6c056b32ced735adf7c19ed8175adb1c8df/service/server/routes_signals.py), [guida agenti](https://github.com/HKUDS/AI-Trader/blob/d03ff6c056b32ced735adf7c19ed8175adb1c8df/docs/README_AGENT.md).

## Evidenze salvate

Gli snapshot grezzi e i report per singolo agente sono conservati solo localmente, esclusi da Git: contengono identificativi e contenuti di terzi non necessari alla pubblicazione. Questo documento riporta soltanto i risultati aggregati. Per riprodurre il campione originale serve lo snapshot locale; un nuovo download può restituire dati diversi.

`outputs/ai_trader_review/2026-09-07/snapshot.json`: 100 operazioni azionarie scaricate dal feed pubblico, con URL e orario di acquisizione. Il dominio documentato `api.ai4trade.ai` non si risolveva in questa sessione; `ai4trade.ai/api/signals/feed` ha risposto.

La prima analisi era sui cinque ETF di `configs/default.yaml`. La verifica del workflow `.github/workflows/us-market-alerts.yml` ha poi identificato `configs/live_stub.yaml` come configurazione usata dai messaggi: 23 azioni, non ETF. Il report pertinente e' `outputs/ai_trader_review/2026-09-07/live_universe/audit.json`.

Su quelle 100 operazioni:

- 64 dichiarano di essere copie; non sono conferme indipendenti.
- 54 sono fuori dall'universo azionario del bot.
- 2 hanno azioni diverse da buy/sell.
- 10 passano i filtri preliminari con finestra di 96 ore.

I conteggi dei motivi si sovrappongono. La finestra di 96 ore e' una sensibilita' esplicita rispetto al filtro iniziale di 24 ore, non un controllo del calendario di borsa e non una validazione di attualita'. Nessuna operazione viene classificata eseguibile. La ricerca aggiuntiva per ETF e' conservata in `etf_search.json`, ma non rappresenta il portafoglio attivo.

## Riproduzione senza rete

Dalla radice del repository:

```powershell
python scripts/audit_ai_trader.py --snapshot outputs/ai_trader_review/2026-09-07/snapshot.json --output outputs/ai_trader_review/replay --as-of 2026-09-07T11:24:02.576453+00:00 --max-age-hours 96 --symbols AAPL MSFT NVDA GOOGL META AMZN HD PG KO JPM V JNJ LLY CAT GE XOM CVX LIN NEM NEE DUK AMT PLD
python -m unittest discover -s tests -p test_ai_trader_audit.py
```

Omettendo `--snapshot` si acquisisce un nuovo campione pubblico. Specificare sempre strumenti e directory di output; usare una directory distinta per conservare ciascuna acquisizione. Nessuna credenziale richiesta, nessun invio di messaggi o ordine. Il contenuto del feed viene trattato come dato, non come istruzione.

## Confronto economico ancora da completare

Non e' presente `outputs/last_decision.json` in questo checkout. Non sono disponibili qui posizioni effettive, saldo e prezzi contemporanei ai due piani. Il semplice `run --execute=False` puo' comunque inviare avvisi nell'orchestratore esistente, quindi non e' stato avviato per questa analisi.

Per decidere una sostituzione serve prima scegliere un agente/provider specifico di AI-Trader e fissare regole per ingresso, uscita, scadenza e dimensionamento. Registrare prospetticamente entrambi i piani con identico capitale, strumenti, prezzi, costi e orari; confrontare risultati netti, drawdown e turnover con un benchmark. Quantita' pubblicate da provider diversi non possono essere sommate in un portafoglio coerente. Nessun rendimento comparativo e' stato calcolato o promesso da questo audit.
