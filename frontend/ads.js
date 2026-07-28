/*
 * Loads AD_CONFIG.banner's networks (see app.js) into whichever ad slots
 * exist on this page — #ad-banner-slot on the homepage, #ad-leaderboard-slot
 * and #ad-sticky-slot on every /tools/*.html page. Loaded once, at page
 * load, which is necessarily before any file could have been chosen — the
 * app makes zero network requests of its own accord otherwise, and nothing
 * here re-triggers later, so that stays true regardless of how many ad
 * networks are configured below. Never touches #tool-mount.
 *
 * Dormant by default: AD_CONFIG.banner.networks is empty, so this file
 * loads and does nothing — zero network requests, every .ad-slot collapses
 * to nothing via the .ad-slot:empty rule in app.css. Add a network by
 * pushing {name, scriptUrl} onto that array in app.js; no other code
 * changes needed. Exact script URLs/attributes come from each network's own
 * publisher-integration docs once an account is approved — this loader is
 * intentionally generic (drops in the network's own loader script and lets
 * it find/populate the slot the way that network expects).
 */
(function(){
  if(typeof AD_CONFIG === 'undefined') return;   // app.js didn't load
  if(location.protocol === 'file:') return;       // no installable origin

  const cfg = AD_CONFIG.banner;
  if(!cfg || !cfg.enabled || !Array.isArray(cfg.networks) || !cfg.networks.length) return;

  const slots = ['ad-banner-slot', 'ad-leaderboard-slot', 'ad-sticky-slot']
    .map(id => document.getElementById(id))
    .filter(Boolean);
  if(!slots.length) return;

  cfg.networks.forEach(net => {
    if(!net || !net.scriptUrl) return;
    const s = document.createElement('script');
    s.async = true;
    s.src = net.scriptUrl;
    if(net.name) s.dataset.adNetwork = net.name;
    s.onerror = () => { /* unreachable/blocked — the slot(s) just stay empty */ };
    document.head.appendChild(s);
  });
})();
