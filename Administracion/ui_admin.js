(function(){
  if (window.__tseAdminModalApplied) return;
  window.__tseAdminModalApplied = true;

  function ensureModal(){
    if (document.getElementById('tseUiModal')) return;
    var toast = document.createElement('div');
    toast.id = 'tseUiToast';
    toast.className = 'tse-ui-toast';
    document.body.appendChild(toast);

    var modal = document.createElement('div');
    modal.id = 'tseUiModal';
    modal.className = 'tse-ui-modal';
    modal.innerHTML =
      '<div class="tse-ui-panel">' +
      '<div id="tseUiTitle" class="tse-ui-title">Mensaje</div>' +
      '<div id="tseUiBody" class="tse-ui-body"></div>' +
      '<div id="tseUiInputWrap" style="display:none">' +
      '<input id="tseUiInput" class="tse-ui-input" type="text">' +
      '</div>' +
      '<div id="tseUiActions" class="tse-ui-actions"></div>' +
      '</div>';
    document.body.appendChild(modal);
  }

  function esc(text){
    return String(text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function showToast(message, title){
    ensureModal();
    var box = document.getElementById('tseUiToast');
    if (!box) return;
    box.innerHTML = '<strong>' + esc(title || 'Aviso') + '</strong><div>' + esc(message || '') + '</div>';
    box.style.display = 'block';
    clearTimeout(showToast._tm);
    showToast._tm = setTimeout(function(){ box.style.display = 'none'; }, 2800);
  }

  function openModal(config){
    ensureModal();
    var modal = document.getElementById('tseUiModal');
    var title = document.getElementById('tseUiTitle');
    var body = document.getElementById('tseUiBody');
    var inputWrap = document.getElementById('tseUiInputWrap');
    var input = document.getElementById('tseUiInput');
    var actions = document.getElementById('tseUiActions');
    var resolver = config.resolve;

    title.textContent = config.title || 'Confirmación';
    body.textContent = config.body || '';
    if (config.useInput) {
      inputWrap.style.display = 'block';
      input.value = config.initialValue || '';
    } else {
      inputWrap.style.display = 'none';
      input.value = '';
    }

    actions.innerHTML = '';
    config.buttons.forEach(function(btn){
      var b = document.createElement('button');
      b.type = 'button';
      b.className = btn.className || '';
      b.textContent = btn.label;
      b.onclick = function(){
        modal.style.display = 'none';
        resolver(btn.value);
      };
      actions.appendChild(b);
    });

    modal.style.display = 'flex';
    if (config.useInput) {
      setTimeout(function(){ input.focus(); }, 0);
    }
  }

  window.uiAlert = function(message, title){
    showToast(message, title);
  };
  window.alert = function(message){
    showToast(message, 'Aviso');
  };
  window.uiConfirm = function(message, title){
    return new Promise(function(resolve){
      openModal({
        title: title || 'Confirmación',
        body: message || '',
        useInput: false,
        buttons: [
          { label: 'Cancelar', value: false, className: 'soft' },
          { label: 'Confirmar', value: true }
        ],
        resolve: resolve
      });
    });
  };
  window.uiPrompt = function(message, initialValue, title){
    return new Promise(function(resolve){
      openModal({
        title: title || 'Entrada',
        body: message || '',
        useInput: true,
        initialValue: initialValue || '',
        buttons: [
          { label: 'Cancelar', value: null, className: 'soft' },
          { label: 'Guardar', value: function(){ return document.getElementById('tseUiInput').value; } }
        ],
        resolve: function(value){
          if (typeof value === 'function') {
            resolve(value());
          } else {
            resolve(value);
          }
        }
      });
    });
  };
})();
