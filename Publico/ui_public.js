(function(){
  if (window.__uxPublicApplied) return;
  window.__uxPublicApplied = true;

  function qs(sel, root){ return (root || document).querySelector(sel); }
  function qsa(sel, root){ return Array.from((root || document).querySelectorAll(sel)); }

  var skip = document.createElement('a');
  skip.className = 'ux-skip-link';
  skip.href = '#main-content';
  skip.textContent = 'Saltar al contenido';
  document.body.prepend(skip);

  var main = qs('main');
  if (!main) {
    main = qs('.wrap') || qs('.container') || qs('#app') || qs('section');
  }
  if (main) {
    if (!main.id) main.id = 'main-content';
    main.setAttribute('role', 'main');
  }

  var header = qs('header');
  if (header) header.setAttribute('role', 'banner');

  qsa('input, textarea, select').forEach(function(el){
    if (el.type === 'hidden' || el.type === 'checkbox' || el.type === 'radio') return;
    var hasAria = !!el.getAttribute('aria-label');
    if (!hasAria) {
      var label = '';
      if (el.id) {
        var forLabel = qs('label[for="' + el.id + '"]');
        if (forLabel) label = (forLabel.textContent || '').trim();
      }
      if (!label) label = (el.getAttribute('placeholder') || '').trim();
      if (!label) label = 'Campo de formulario';
      el.setAttribute('aria-label', label);
    }
  });

  qsa('button').forEach(function(btn){
    if (!btn.getAttribute('aria-label')) {
      var t = (btn.textContent || '').trim();
      if (t) btn.setAttribute('aria-label', t);
    }
  });

  var lastKnownPublicVersion = null;
  var versionUpdatePending = false;
  var versionPromptShown = false;
  var pendingPublicVersion = null;
  var ackedPublicVersion = null;
  var publicVersionStream = null;
  var pollTimer = null;
  var pollMs = 5000;

  function loadAckedVersion(){
    if (ackedPublicVersion !== null) return ackedPublicVersion;
    try{
      ackedPublicVersion = String(localStorage.getItem("tsev_public_version_ack") || "");
    }catch(_e){
      ackedPublicVersion = "";
    }
    return ackedPublicVersion;
  }

  function saveAckedVersion(version){
    ackedPublicVersion = String(version || "");
    try{
      if (ackedPublicVersion) {
        localStorage.setItem("tsev_public_version_ack", ackedPublicVersion);
      } else {
        localStorage.removeItem("tsev_public_version_ack");
      }
    }catch(_e){}
  }

  function ensureUpdatePrompt(){
    if (document.getElementById("publicUpdatePrompt")) return;
    var style = document.createElement("style");
    style.textContent =
      ".public-update-prompt{position:fixed;inset:0;background:rgba(0,0,0,.35);display:none;align-items:center;justify-content:center;padding:24px;z-index:9999;}"+
      ".public-update-card{background:#fff;border-radius:14px;padding:18px 20px;max-width:420px;width:100%;box-shadow:0 18px 40px rgba(0,0,0,.22);text-align:center;font-weight:700;color:#111;}"+
      ".public-update-card p{margin:0 0 12px 0;font-size:1rem;}"+
      ".public-update-actions{display:flex;gap:10px;justify-content:center;flex-wrap:wrap;}"+
      ".public-update-btn{border:0;border-radius:10px;padding:10px 14px;font-weight:800;cursor:pointer;}"+
      ".public-update-btn.ok{background:#f3d044;color:#111;}"+
      ".public-update-btn.no{background:#e5e7eb;color:#111;}";
    document.head.appendChild(style);
    var overlay = document.createElement("div");
    overlay.id = "publicUpdatePrompt";
    overlay.className = "public-update-prompt";
    overlay.innerHTML =
      "<div class=\"public-update-card\">"+
      "<p>Hay una nueva versión disponible de la web. ¿Quieres recargar la página?</p>"+
      "<div class=\"public-update-actions\">"+
      "<button class=\"public-update-btn ok\" type=\"button\" data-action=\"ok\">Vale</button>"+
      "<button class=\"public-update-btn no\" type=\"button\" data-action=\"no\">No</button>"+
      "</div></div>";
    document.body.appendChild(overlay);
    overlay.addEventListener("click", function(ev){
      var btn = ev.target && ev.target.getAttribute ? ev.target : null;
      var action = btn && btn.getAttribute("data-action");
      if(!action) return;
      if(action === "ok"){
        triggerPublicVersionUpdate();
      }else{
        overlay.style.display = "none";
      }
    });
  }

  function showUpdatePrompt(version){
    if (versionPromptShown) return;
    versionPromptShown = true;
    pendingPublicVersion = version || null;
    ensureUpdatePrompt();
    var overlay = document.getElementById("publicUpdatePrompt");
    if(overlay) overlay.style.display = "flex";
  }

  function triggerPublicVersionUpdate(){
    if (versionUpdatePending) return;
    versionUpdatePending = true;
    if (pendingPublicVersion) {
      saveAckedVersion(pendingPublicVersion);
    }
    try{
      var url = new URL(window.location.href);
      url.searchParams.set("v", String(Date.now()));
      window.location.replace(url.toString());
    }catch(_e){
      window.location.reload();
    }
  }

  function applyActivePublicVersion(activeVersion){
    var v = String(activeVersion || "").trim();
    if(!v) return;

    var footer = document.getElementById("footerVersion");
    if(footer){
      footer.textContent = "Versión: " + v;
      footer.setAttribute("data-version", v);
    }

    if(loadAckedVersion() && loadAckedVersion() === v) return;
    if(lastKnownPublicVersion === null){
      lastKnownPublicVersion = v;
      return;
    }
    if(v !== lastKnownPublicVersion){
      lastKnownPublicVersion = v;
      versionPromptShown = false;
      showUpdatePrompt(v);
    }
  }

  function pollPublicVersion(){
    if (versionUpdatePending) return;
    var ts = Date.now();
    fetch("/web/versions/public?ts=" + ts, { cache:"no-store", credentials:"omit" })
      .then(function(res){ return res.ok ? res.json() : null; })
      .then(function(data){
        if (!data || !data.public || !data.public.version) return;
        applyActivePublicVersion(data.public.version);
      })
      .catch(function(){});
  }
  function resetPublicVersionPolling(ms){
    pollMs = Math.max(2000, Number(ms || 0) || 0);
    try{
      if(pollTimer) clearInterval(pollTimer);
    }catch(_e){}
    pollTimer = setInterval(pollPublicVersion, pollMs);
  }

  function initPublicVersionStream(){
    if(!window.EventSource) return false;
    try{
      publicVersionStream = new EventSource("/web/versions/stream?target=public");
    }catch(_e){
      publicVersionStream = null;
      return false;
    }
    publicVersionStream.addEventListener("versions", function(ev){
      try{
        var data = JSON.parse(ev.data || "{}");
        if(data && data.public && data.public.version){
          applyActivePublicVersion(data.public.version);
          if(pollMs !== 60000) resetPublicVersionPolling(60000);
        }
      }catch(_e){}
    });
    publicVersionStream.addEventListener("error", function(){
      if(pollMs !== 5000) resetPublicVersionPolling(5000);
    });
    return true;
  }

  function initCookieBanner(){
    var CONSENT_KEY = "tse_cookie_consent_v1";
    var banner = document.getElementById("cookieBanner");
    if(!banner) return;
    var acceptBtn = document.getElementById("cookieAccept");
    var rejectBtn = document.getElementById("cookieReject");
    var configBtn = document.getElementById("cookieConfig");
    var overlay = document.getElementById("cookieConfigOverlay");
    var configSave = document.getElementById("cookieConfigSave");
    var configCancel = document.getElementById("cookieConfigCancel");

    function getConsent(){
      try{ return localStorage.getItem(CONSENT_KEY) || ""; }catch(_e){ return ""; }
    }
    function setConsent(value){
      try{ localStorage.setItem(CONSENT_KEY, value); }catch(_e){}
      try{ window.dispatchEvent(new Event("cookie-consent-changed")); }catch(_e){}
    }
    function hideBanner(){
      banner.classList.add("hidden");
      banner.setAttribute("aria-hidden", "true");
    }
    function showBanner(){
      banner.classList.remove("hidden");
      banner.setAttribute("aria-hidden", "false");
    }
    function isCookiesPage(){
      try{ return /\/cookies\.html$/i.test(window.location.pathname || ""); }catch(_e){ return false; }
    }

    (function applyInitial(){
      var consent = getConsent();
      if(isCookiesPage()){
        hideBanner();
      }else if(consent === "accepted" || consent === "custom" || consent === "rejected"){
        hideBanner();
      }else{
        showBanner();
      }
    })();

    if(acceptBtn){
      acceptBtn.addEventListener("click", function(){
        setConsent("accepted");
        hideBanner();
      });
    }
    if(rejectBtn){
      rejectBtn.addEventListener("click", function(){
        setConsent("rejected");
        hideBanner();
      });
    }
    if(configBtn){
      configBtn.addEventListener("click", function(){
        if(overlay) overlay.classList.add("show");
      });
    }
    if(configCancel){
      configCancel.addEventListener("click", function(){
        if(overlay) overlay.classList.remove("show");
      });
    }
    if(configSave){
      configSave.addEventListener("click", function(){
        setConsent("custom");
        if(overlay) overlay.classList.remove("show");
        hideBanner();
      });
    }
  }

  initCookieBanner();
  resetPublicVersionPolling(5000);
  initPublicVersionStream();
  pollPublicVersion();

  window.TSEPublicHeaderSearch = (function(){
    var activeController = null;

    function qs(sel, root){
      return (root || document).querySelector(sel);
    }

    function normalizeText(value){
      return String(value || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLowerCase()
        .trim();
    }

    function escapeHtml(value){
      return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    async function fetchJson(url){
      var res = await fetch(url, {
        method: 'GET',
        cache: 'no-store',
        credentials: 'omit',
        headers: { 'Accept': 'application/json' },
      });
      if(!res.ok){
        throw new Error('HTTP_' + res.status);
      }
      return res.json();
    }

    function buildSearchEntry(b){
      var normalizedName = normalizeText(b && b.name);
      var normalizedCategory = normalizeText(b && b.category);
      var normalizedDescription = normalizeText(b && b.initial_phrase);
      var tokens = Array.from(new Set([
        normalizedName,
        normalizedCategory,
        normalizedDescription,
      ].join(' ').split(/[^a-z0-9]+/).filter(Boolean)));
      return {
        normalizedName: normalizedName,
        normalizedCategory: normalizedCategory,
        tokens: tokens,
      };
    }

    function buildSuggestionsFromBusinesses(query, businesses, limit){
      var normalizedQuery = normalizeText(query);
      if(normalizedQuery.length < 2) return [];
      var suggestions = [];
      var seen = new Set();
      (Array.isArray(businesses) ? businesses : []).forEach(function(business){
        var entry = buildSearchEntry(business);
        if(entry.normalizedCategory && entry.normalizedCategory.startsWith(normalizedQuery)){
          var catKey = 'category:' + entry.normalizedCategory;
          if(!seen.has(catKey)){
            seen.add(catKey);
            suggestions.push({
              label: business.category || '',
              meta: 'Categoria',
              kind: 'Categoria',
              query: business.category || '',
            });
          }
        }
        var businessMatch = entry.normalizedName.startsWith(normalizedQuery) || entry.tokens.some(function(token){ return token.startsWith(normalizedQuery); });
        if(businessMatch){
          var bizKey = 'business:' + entry.normalizedName;
          if(!seen.has(bizKey)){
            seen.add(bizKey);
            suggestions.push({
              label: business.name || '',
              meta: business.category || 'Negocio',
              kind: 'Negocio',
              query: business.name || '',
              businessId: business.public_id || business.id || business.business_id || '',
            });
          }
        }
      });
      return suggestions.slice(0, Math.max(1, Number(limit) || 6));
    }

    function getDefaultSelectors(config){
      return {
        form: config.formSelector || '#headerSearchForm',
        input: config.inputSelector || '#searchInput',
        suggestions: config.suggestionsSelector || '#searchSuggestions',
        clear: config.clearButtonSelector || '#searchClearBtn',
        submit: config.submitButtonSelector || '#searchSubmitBtn',
      };
    }

    function createController(config){
      var options = config || {};
      var selectors = getDefaultSelectors(options);
      var form = qs(selectors.form);
      var input = qs(selectors.input);
      var suggestionsEl = qs(selectors.suggestions);
      var clearBtn = qs(selectors.clear);
      var submitBtn = qs(selectors.submit);
      var remoteSuggestUrl = options.remoteSuggestUrl || '/search/businesses/suggest';
      var businessesUrl = options.businessesUrl || '';
      var limit = Math.max(1, Number(options.limit) || 6);
      var minChars = Math.max(1, Number(options.minChars) || 2);
      var timer = null;
      var requestToken = 0;
      var businessesCache = null;
      var businessesPromise = null;
      var destroyed = false;

      function updateButtons(){
        if(!input) return;
        var hasQuery = !!String(input.value || '').trim();
        if(clearBtn){
          clearBtn.hidden = false;
          clearBtn.style.visibility = hasQuery ? 'visible' : 'hidden';
          clearBtn.style.pointerEvents = hasQuery ? 'auto' : 'none';
        }
        if(submitBtn){
          submitBtn.hidden = false;
          submitBtn.style.visibility = hasQuery ? 'visible' : 'hidden';
          submitBtn.style.pointerEvents = hasQuery ? 'auto' : 'none';
        }
      }

      function hideSuggestions(){
        if(!suggestionsEl) return;
        suggestionsEl.hidden = true;
        suggestionsEl.innerHTML = '';
      }

      function renderSuggestions(items){
        if(!suggestionsEl) return;
        if(!Array.isArray(items) || !items.length){
          hideSuggestions();
          return;
        }
        var businessItems = [];
        var categoryItems = [];
        items.forEach(function(item){
          var normalizedKind = normalizeText(item && item.kind);
          var isCategory = normalizedKind === 'categoria' || normalizedKind === 'categoría';
          if(isCategory){
            categoryItems.push(item);
          }else{
            businessItems.push(item);
          }
        });
        function renderSuggestionButton(item, index, variantClass){
          return '<button type="button" class="search-suggestion-btn ' + variantClass + '" data-index="' + index + '" data-query="' + escapeHtml(item.query || item.label || '') + '" data-business-id="' + escapeHtml(item.businessId || '') + '">' +
            '<span class="search-suggestion-main">' +
              '<span class="search-suggestion-title">' + escapeHtml(item.label || '') + '</span>' +
              '<span class="search-suggestion-meta">' + escapeHtml(item.meta || '') + '</span>' +
            '</span>' +
            '<span class="search-suggestion-kind ' + variantClass + '">' + escapeHtml(item.kind || 'Sugerencia') + '</span>' +
          '</button>';
        }
        function renderSuggestionGroup(title, groupItems, variantClass, emptyMessage){
          return '<section class="search-suggestion-group">' +
            '<h4 class="search-suggestion-group-title">' + escapeHtml(title) + '</h4>' +
            (
              groupItems.length
                ? groupItems.map(function(item, index){ return renderSuggestionButton(item, index, variantClass); }).join('')
                : '<div class="search-suggestion-empty">' + escapeHtml(emptyMessage) + '</div>'
            ) +
          '</section>';
        }
        suggestionsEl.innerHTML =
          renderSuggestionGroup('Negocios', businessItems, 'is-business', 'No hay resultados para esa búsqueda') +
          renderSuggestionGroup('Categorías', categoryItems, 'is-category', 'No hay resultados para esa búsqueda');
        suggestionsEl.hidden = false;
      }

      async function loadBusinesses(){
        if(typeof options.getBusinesses === 'function'){
          try{
            var custom = options.getBusinesses();
            return Array.isArray(custom) ? custom : await custom;
          }catch(_e){
            return [];
          }
        }
        if(businessesCache) return businessesCache;
        if(businessesPromise) return businessesPromise;
        if(!businessesUrl) return [];
        businessesPromise = fetchJson(businessesUrl).then(function(data){
          var list = Array.isArray(data) ? data.filter(function(item){ return item && item.active !== false; }) : [];
          businessesCache = list;
          businessesPromise = null;
          return list;
        }).catch(function(){
          businessesPromise = null;
          businessesCache = [];
          return [];
        });
        return businessesPromise;
      }

      function mapRemoteItems(items){
        return items.slice(0, limit).map(function(item){
          return {
            label: item.label || item.query || item.name || '',
            meta: item.meta || item.category || 'Sugerencia',
            kind: item.kind || 'Meili',
            query: item.query || item.label || item.name || '',
            businessId: item.businessId || item.public_id || item.place_public_id || item.id || item.business_id || item.place_id || '',
          };
        });
      }

      async function resolveLocalSuggestions(query){
        var businesses = [];
        try{
          businesses = await loadBusinesses();
        }catch(_e){
          businesses = [];
        }
        return buildSuggestionsFromBusinesses(query, businesses, limit);
      }

      async function resolveSuggestions(query){
        var normalizedQuery = normalizeText(query);
        if(normalizedQuery.length < minChars) return [];
        try{
          var url = new URL(remoteSuggestUrl, window.location.href);
          url.searchParams.set('q', query);
          url.searchParams.set('limit', String(limit));
          var data = await fetchJson(url.toString());
          var items = Array.isArray(data && data.items) ? data.items : [];
          if(items.length){
            return mapRemoteItems(items);
          }
          return resolveLocalSuggestions(query);
        }catch(_e){
          return resolveLocalSuggestions(query);
        }
      }

      async function queueSuggestions(){
        if(destroyed || !input) return;
        var query = String(input.value || '').trim();
        if(!query){
          hideSuggestions();
          return;
        }
        var currentToken = ++requestToken;
        var items = await resolveSuggestions(query);
        if(destroyed || currentToken !== requestToken) return;
        renderSuggestions(items);
      }

      function submitQuery(query){
        if(typeof options.onSubmit === 'function'){
          options.onSubmit(String(query || '').trim());
        }
      }

      function onDocumentClick(ev){
        var insideSearch = ev.target && ev.target.closest ? ev.target.closest('.header-search') : null;
        if(!insideSearch){
          hideSuggestions();
        }
      }

      function destroy(){
        destroyed = true;
        if(timer) clearTimeout(timer);
        hideSuggestions();
        if(input){
          input.removeEventListener('input', onInput);
          input.removeEventListener('focus', onFocus);
          input.removeEventListener('keydown', onKeydown);
        }
        if(clearBtn) clearBtn.removeEventListener('click', onClear);
        if(form) form.removeEventListener('submit', onSubmit);
        if(suggestionsEl) suggestionsEl.removeEventListener('click', onSuggestionsClick);
        document.removeEventListener('click', onDocumentClick);
      }

      function onInput(){
        updateButtons();
        if(timer) clearTimeout(timer);
        var query = String(input.value || '').trim();
        if(!query){
          hideSuggestions();
          if(typeof options.onEmptyQuery === 'function'){
            options.onEmptyQuery();
          }
          return;
        }
        timer = setTimeout(queueSuggestions, 220);
      }

      function onFocus(){
        var query = String(input.value || '').trim();
        if(!query) return;
        queueSuggestions();
      }

      function onKeydown(ev){
        if(ev.key === 'Escape'){
          input.value = '';
          updateButtons();
          hideSuggestions();
          if(typeof options.onClear === 'function'){
            options.onClear('escape');
          }
          input.blur();
        }
        if(ev.key === 'Enter'){
          ev.preventDefault();
          submitQuery(input.value);
        }
      }

      function onClear(){
        input.value = '';
        updateButtons();
        hideSuggestions();
        if(typeof options.onClear === 'function'){
          options.onClear('clear-button');
        }
        input.focus();
      }

      function onSubmit(ev){
        ev.preventDefault();
        submitQuery(input.value);
      }

      function onSuggestionsClick(ev){
        var btn = ev.target && ev.target.closest ? ev.target.closest('.search-suggestion-btn') : null;
        if(!btn) return;
        var businessId = String(btn.dataset.businessId || '').trim();
        if(businessId){
          window.location.href = '/negocio.html?id=' + encodeURIComponent(businessId);
          return;
        }
        submitQuery(btn.dataset.query || btn.textContent || '');
      }

      if(!form || !input || !suggestionsEl) return null;
      updateButtons();
      input.addEventListener('input', onInput);
      input.addEventListener('focus', onFocus);
      input.addEventListener('keydown', onKeydown);
      if(clearBtn) clearBtn.addEventListener('click', onClear);
      form.addEventListener('submit', onSubmit);
      suggestionsEl.addEventListener('click', onSuggestionsClick);
      document.addEventListener('click', onDocumentClick);

      return {
        refresh: queueSuggestions,
        hide: hideSuggestions,
        destroy: destroy,
        updateButtons: updateButtons,
      };
    }

    return {
      init: function(config){
        if(activeController && activeController.destroy){
          activeController.destroy();
        }
        activeController = createController(config || {});
        return activeController;
      }
    };
  })();

})();

