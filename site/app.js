'use strict';
const $ = id => document.getElementById(id);
const euro = n => Number.isFinite(n) ? new Intl.NumberFormat('it-IT', {style:'currency', currency:'EUR'}).format(n) : '—';
const usd = n => Number.isFinite(n) ? new Intl.NumberFormat('it-IT', {style:'currency', currency:'USD'}).format(n) : '—';
const percent = n => Number.isFinite(n) ? new Intl.NumberFormat('it-IT', {style:'percent', maximumFractionDigits:1, signDisplay:'exceptZero'}).format(n) : '—';
const formatTime = value => Number.isFinite(Date.parse(value)) ? new Intl.DateTimeFormat('it-IT', {dateStyle:'medium', timeStyle:'short', timeZone:'Europe/Rome'}).format(new Date(value)) : '—';
const names = {AAPL:'Apple',MSFT:'Microsoft',NVDA:'NVIDIA',GOOGL:'Alphabet',META:'Meta',AMZN:'Amazon',HD:'Home Depot',PG:'Procter & Gamble',KO:'Coca-Cola',JPM:'JPMorgan Chase',V:'Visa',JNJ:'Johnson & Johnson',LLY:'Eli Lilly',CAT:'Caterpillar',GE:'GE Aerospace',XOM:'Exxon Mobil',CVX:'Chevron',LIN:'Linde',NEM:'Newmont',NEE:'NextEra Energy',DUK:'Duke Energy',AMT:'American Tower',PLD:'Prologis'};
let data = {status:'waiting',assets:[]};
let filter = 'all';
let state = {capital:100,holdings:{}};
try { const saved = JSON.parse(localStorage.getItem('osservatorio-portfolio-v1')); if (saved && typeof saved === 'object' && Number.isFinite(saved.capital) && saved.capital > 0 && saved.holdings && typeof saved.holdings === 'object') state = saved; } catch (_) { /* Browser storage is optional. */ }
function save() { try { localStorage.setItem('osservatorio-portfolio-v1', JSON.stringify(state)); } catch (_) { $('portfolio-error').textContent = 'Il browser non consente il salvataggio: i dati restano disponibili fino alla chiusura della pagina.'; } }
function node(tag, className, text) { const el = document.createElement(tag); if (className) el.className = className; if (text !== undefined) el.textContent = text; return el; }
function empty(title, detail) { const box = node('div','empty'); box.append(node('span','','◌'),node('h3','',title),node('p','',detail)); return box; }
function buildHoldingFields() {
  $('holdings-fields').replaceChildren();
  const symbols = [...new Set([...data.assets.map(a=>a.symbol), ...Object.keys(state.holdings)])].sort();
  for (const symbol of symbols) {
    const row = node('div','holding-row'); row.append(node('b','',symbol));
    for (const [key,label] of [['amount','Valore attuale EUR'],['entry','Ingresso medio USD']]) {
      const wrapper = node('div'); const input = node('input'); input.type='number'; input.min='0'; input.step='.01'; input.inputMode='decimal'; input.value=state.holdings[symbol]?.[key] || ''; input.placeholder='0'; input.id=`holding-${symbol}-${key}`;
      const caption = node('label','',label); caption.htmlFor=input.id;
      input.addEventListener('input',()=>{state.holdings[symbol] ||= {}; state.holdings[symbol][key] = input.value === '' ? 0 : Number(input.value); render(); save();});
      wrapper.append(caption,input); row.append(wrapper);
    }
    $('holdings-fields').append(row);
  }
}
function card(asset, p) {
  const el = node('article','card');
  const top = node('div','card-top'); const name = node('div'); name.append(node('h3','asset-name',asset.symbol),node('p','asset-sector',names[asset.symbol] || asset.sector || 'Azione USA')); top.append(name,node('span',`pill ${p.action}`,p.label.toUpperCase()));
  const price = node('div','card-price'); const quote = node('div'); quote.append(node('strong','',usd(asset.reference_price_usd)),node('small','',' / chiusura')); price.append(quote,node('span',`change ${asset.return_20d >= 0 ? 'positive' : 'negative'}`,`${percent(asset.return_20d)} · 20 sedute`));
  const body = node('div','card-body');
  let amount = p.action === 'buy' ? `${euro(p.delta)} da aggiungere` : p.action === 'sell' ? `${euro(-p.delta)} da ridurre` : p.action === 'wait' ? 'Nessuna operazione da valutare ora' : p.action === 'hold' ? `${euro(p.current)} indicati come investiti` : 'Capitale non allocato';
  body.append(node('div','action-amount',amount),node('p','reason',p.reason));
  if (p.actionable || p.action === 'hold') {
    const metrics = node('div','card-metrics');
    for (const [label,value] of [['Obiettivo nel portafoglio',euro(p.target)],['Stop indicativo',usd(p.stop)],['Prezzo per valutare l’uscita',usd(p.objective)],['Peso del modello',percent(asset.target_weight)]]) { const cell=node('div'); cell.append(node('span','',label),node('strong','',value)); metrics.append(cell); }
    body.append(metrics,node('p','levels-note',p.personalEntry ? 'Livelli calcolati sul tuo ingresso. Verifica la quotazione attuale prima di operare.' : 'Livelli ipotetici sulla chiusura disponibile, non su un acquisto effettivo. Nessuna fascia d’ingresso verificata.'));
  }
  const details=node('details'); const summary=node('summary','','Perché questo titolo?  +'); const list=node('ul'); for (const reason of asset.reasons || []) list.append(node('li','',reason)); details.append(summary,list);
  for (const [index,url] of (asset.source_urls || []).entries()) { try { if (new URL(url).protocol !== 'https:') continue; const link=node('a','',`Fonte notizie ${index+1} ↗`); link.href=url; link.target='_blank'; link.rel='noopener noreferrer'; details.append(link); } catch (_) {} }
  el.append(top,price,body,details); return el;
}
function render() {
  const available=AdvisorPlanner.fresh(data);
  const values=Object.values(state.holdings);
  const invested=values.reduce((sum,h)=>sum+Number(h?.amount || 0),0);
  const unknown=Object.keys(state.holdings).some(symbol => Number(state.holdings[symbol]?.amount)>0 && !data.assets.some(a=>a.symbol===symbol));
  const valid=Number.isFinite(state.capital) && state.capital>0 && Number.isFinite(invested) && invested<=state.capital && !unknown && values.every(h=>Number.isFinite(Number(h?.amount || 0)) && Number(h?.amount || 0)>=0 && Number.isFinite(Number(h?.entry || 0)) && Number(h?.entry || 0)>=0);
  $('portfolio-error').textContent = valid ? '' : unknown ? 'Hai una posizione fuori dall’universo analizzato. Il piano è sospeso finché il portafoglio non è interamente rappresentato.' : 'Il capitale deve essere positivo e coprire tutte le posizioni. Usa importi non negativi.';
  const plans=data.assets.map(asset=>({asset,p:AdvisorPlanner.plan(asset,data,state.capital,state.holdings[asset.symbol],available,valid)}));
  const buys=plans.filter(x=>x.p.action==='buy').length, sells=plans.filter(x=>x.p.action==='sell').length;
  const proposed=plans.reduce((sum,x)=>sum+(Number.isFinite(x.p.target)?x.p.target:0),0);
  const feasible=valid && proposed<=state.capital+.01;
  if (!feasible && valid) { $('portfolio-error').textContent='Le posizioni mantenute e i nuovi acquisti supererebbero il capitale: rivedi gli importi prima di procedere.'; for (const item of plans) item.p=AdvisorPlanner.plan(item.asset,data,state.capital,state.holdings[item.asset.symbol],available,false); }
  $('allocated').textContent=available && feasible ? euro(proposed) : '—'; $('cash').textContent=available && feasible ? euro(Math.max(0,state.capital-proposed)) : '—'; $('allocation-bar').style.width=available && feasible ? `${Math.min(100,Math.max(0,100*proposed/state.capital))}%` : '0%';
  const status=data.status==='waiting' ? 'IN ATTESA' : data.status==='unavailable' ? 'ANALISI SOSPESA' : available ? 'ANALISI DISPONIBILE' : 'DATI DA AGGIORNARE';
  $('status-pill').textContent=status; $('status-pill').className=`pill ${available?'ready':'wait'}`;
  $('status-text').textContent=data.status==='waiting' ? 'La prima analisi non è stata ancora pubblicata.' : data.status==='unavailable' ? 'Ultimo ciclo non utilizzabile. Le indicazioni operative sono sospese.' : available ? `Prezzi del ${data.price_date}. Verifica sempre la quotazione sul broker.` : 'L’analisi o i prezzi hanno superato la finestra di validità. Attendi un nuovo ciclo.';
  $('updated-at').textContent=data.decision_at ? `Analisi: ${formatTime(data.decision_at)}` : '';
  $('agent-summary').textContent=available && feasible ? (buys+sells>0 ? `Nel tuo scenario: ${buys} ${buys===1?'acquisto':'acquisti'} e ${sells} ${sells===1?'riduzione':'riduzioni'} da valutare. Parti dalle motivazioni, poi verifica prezzi e liquidità sul broker. Le eventuali riduzioni precedono i nuovi acquisti.` : 'Per il capitale e le posizioni inserite non emergono cambiamenti da valutare. Anche aspettare è una decisione.') : data.status==='waiting' ? 'Il primo piano comparirà dopo un ciclo di analisi. Per ora puoi impostare capitale e posizioni.' : !feasible ? 'Prima di costruire il piano, controlliamo che capitale e posizioni siano coerenti.' : 'Al momento non ho dati abbastanza aggiornati o un’analisi valida per proporti un’operazione. Le indicazioni restano sospese.';
  $('source').textContent=data.price_source || '—'; $('price-date').textContent=data.price_date || '—'; $('risk-flags').textContent=(data.risk_flags || []).join(' · ') || 'Nessun dettaglio disponibile';
  const query=$('search').value.toLowerCase(); const rank={sell:0,buy:1,hold:2,wait:3,skip:4};
  const shown=plans.filter(({asset,p})=>(filter==='all' || (filter==='hold' ? ['hold','wait','skip'].includes(p.action) : filter===p.action)) && `${asset.symbol} ${names[asset.symbol] || ''}`.toLowerCase().includes(query)).sort((a,b)=>rank[a.p.action]-rank[b.p.action] || (b.asset.target_weight || 0)-(a.asset.target_weight || 0));
  $('count').textContent=`${shown.length} titoli`; $('cards').replaceChildren(...shown.map(({asset,p})=>card(asset,p)));
  if (!shown.length) $('cards').append(empty(data.assets.length ? 'Nessun titolo in questa vista' : 'Il piano è in preparazione',data.assets.length ? 'Prova un altro filtro o attendi la prossima analisi.' : 'Non ci sono segnali dimostrativi: qui compariranno soltanto i risultati pubblicati dall’agente.'));
}
async function refresh() {
  $('refresh').disabled=true;
  try { const response=await fetch(`data.json?t=${Date.now()}`,{cache:'no-store'}); if (!response.ok) throw new Error('unavailable'); const result=await response.json(); if (result.schema_version!==1 || !Array.isArray(result.assets)) throw new Error('invalid'); data=result; buildHoldingFields(); }
  catch (_) { data={...data,status:'unavailable'}; }
  finally { $('refresh').disabled=false; render(); }
}
$('capital').value=state.capital;
$('capital').addEventListener('input',()=>{state.capital=Number($('capital').value); render(); save();});
$('reset').addEventListener('click',()=>{state={capital:100,holdings:{}}; $('capital').value=100; buildHoldingFields(); render(); save();});
$('refresh').addEventListener('click',refresh); $('search').addEventListener('input',render);
document.querySelectorAll('[data-filter]').forEach(button=>button.addEventListener('click',()=>{filter=button.dataset.filter; document.querySelectorAll('[data-filter]').forEach(other=>{other.classList.toggle('selected',other===button); other.setAttribute('aria-pressed',String(other===button));}); render();}));
setInterval(render,60000); setInterval(refresh,300000); refresh();
