/* Pure planner; all position values are supplied by the user, in EUR. */
(function (root) {
  'use strict';
  function fresh(data, now = Date.now()) {
    const decision = Date.parse(data.decision_at);
    const price = Date.parse(data.price_date + 'T00:00:00Z');
    const maxAge = Number(data.max_price_age_hours);
    return data.status === 'ready' && Number.isFinite(decision) && Number.isFinite(price) &&
      decision <= now + 300000 && now - decision <= 26 * 3600000 &&
      maxAge > 0 && price <= now && now - price <= maxAge * 3600000;
  }
  function plan(asset, data, capital, holding = {}, available = false, portfolioValid = true) {
    const current = Number(holding.amount || 0);
    const entry = Number(holding.entry || 0);
    const price = asset.reference_price_usd;
    const weight = asset.target_weight;
    const rules = data.rules || {};
    const minimum = rules.minimum_position_eur ?? 20;
    const threshold = Math.max(.01, capital * (rules.min_weight_change ?? .02));
    let target = capital * weight;
    const small = target > 0 && target < minimum;
    if (small) target = current;
    let delta = target - current;
    let action = 'wait';
    let label = 'Attendi';
    let reason = 'Serve un’analisi recente prima di valutare operazioni.';
    const valid = portfolioValid && Number.isFinite(capital) && capital > 0 &&
      Number.isFinite(current) && current >= 0 && Number.isFinite(entry) && entry >= 0 &&
      typeof weight === 'number' && Number.isFinite(weight) && weight >= 0 && weight <= 1 &&
      typeof price === 'number' && Number.isFinite(price) && price > 0;
    if (available && valid) {
      if (small) { action = current > 0 ? 'hold' : 'skip'; label = current > 0 ? 'Mantieni' : 'Non comprare'; reason = 'Importo obiettivo inferiore alla soglia minima: costi troppo rilevanti.'; }
      else if (delta >= threshold) { action = 'buy'; label = 'Valuta acquisto'; reason = 'Il peso obiettivo supera quanto hai indicato come già investito.'; }
      else if (delta <= -threshold) { action = 'sell'; label = target === 0 ? 'Valuta uscita' : 'Valuta riduzione'; reason = 'Quanto hai indicato come investito supera il peso obiettivo del modello.'; }
      else { action = current > 0 ? 'hold' : 'skip'; label = current > 0 ? 'Mantieni' : 'Non comprare'; reason = current > 0 ? 'Scostamento sotto la soglia di ribilanciamento.' : 'Nessuna allocazione proposta dal modello.'; }
    } else if (!valid) reason = 'Controlla capitale, posizioni e disponibilità dei dati prima di procedere.';
    const base = entry > 0 ? entry : price;
    const stop = base * (1 - (rules.stop_loss_pct ?? .02));
    const fees = 2 * (rules.commission_per_order_eur ?? 1);
    const targetAmount = Math.max(current, target);
    const gain = fees + targetAmount * (rules.minimum_net_profit_pct ?? .02) / Math.max(.01, 1 - (rules.estimated_tax_rate ?? .26));
    const objective = base * (1 + Math.max(rules.take_profit_pct ?? .04, targetAmount > 0 ? gain / targetAmount : 0));
    if (available && valid && current > 0 && entry > 0 && (price <= stop || price >= objective)) {
      action = 'sell'; label = 'Valuta uscita'; target = 0; delta = -current;
      reason = price <= stop ? 'La chiusura disponibile è sotto lo stop calcolato sul tuo prezzo d’ingresso.' : 'La chiusura disponibile ha raggiunto l’obiettivo indicativo sul tuo ingresso.';
    }
    return { action, label, reason, current, target, delta, stop, objective, personalEntry: entry > 0,
      actionable: available && valid && ['buy', 'sell'].includes(action) };
  }
  const api = { fresh, plan };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.AdvisorPlanner = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
