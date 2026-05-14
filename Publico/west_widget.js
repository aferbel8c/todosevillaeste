(function(){
  const LOCAL_IP = "192.168.0.40";
  const PUBLIC_HOST = "todosevillaeste.es";
  const currentHost = window.location.hostname;
  const isLocalHost = currentHost === "localhost" || currentHost === "127.0.0.1" || currentHost === LOCAL_IP;
  const AGENT_API_BASE = isLocalHost ? `${window.location.protocol}//${LOCAL_IP}:8000` : "https://todosevillaeste.es";
  const ASSISTANT_REQUEST_TIMEOUT_MS = 195000;
  const ASSISTANT_TOGGLE_SLIDE_LEAD_MS = 120;
  const ASSISTANT_NUDGE_SHOW_DELAY_MS = 9000;
  const ASSISTANT_NUDGE_AUTO_HIDE_DELAY_MS = 5000;

  let assistantBusy = false;
  let assistantAbortController = null;
  let assistantAbortReason = "";
  let assistantRenderCancelled = false;
  let assistantCurrentMessageEl = null;
  let assistantIntroShown = false;
  let assistantIntroRenderPromise = null;
  let assistantSessionChatId = null;
  let assistantConversation = [];
  let assistantHydratingState = false;
  let assistantFooterOffsetRaf = null;
  let assistantFooterResizeObserver = null;
  const ASSISTANT_STORAGE_KEY = "tsev_west_chat_v1";

  function assistantSleep(ms){ return new Promise((resolve) => setTimeout(resolve, ms)); }

  function ensureWidgetMarkup(){
    if(document.getElementById("assistantToggle")) return;
    const wrapper = document.createElement("div");
    wrapper.innerHTML = `
<button id="assistantToggle" class="assistant-toggle" type="button" aria-label="Abrir asistente West" title="Abrir asistente West">
  <span class="assistant-toggle-art" aria-hidden="true">
    <span class="assistant-toggle-layer exterior">
      <img class="assistant-toggle-exterior" src="/icono/west_exterior.png?v=20260424-2" alt="">
    </span>
    <span class="assistant-toggle-layer interior">
      <img class="assistant-toggle-interior" src="/icono/west_interior.png?v=20260424-2" alt="">
    </span>
  </span>
</button>
<div id="assistantNudge" class="assistant-nudge" aria-hidden="true">
  Soy West, estoy aqui para ayudarte
  <button id="assistantNudgeClose" class="assistant-nudge-close" type="button" aria-label="Cerrar aviso de West" title="Cerrar">×</button>
</div>
<section id="assistantPanel" class="assistant-panel" aria-label="Chat asistente">
  <div class="assistant-head">
    <div class="assistant-head-copy">
      <div class="assistant-title">Asistente West</div>
      <div id="assistantStatus" class="assistant-status" data-tone="ready">Listo para ayudarte.</div>
    </div>
    <div class="assistant-head-actions">
      <button id="assistantCancel" class="assistant-cancel" type="button" hidden>Cancelar</button>
      <button id="assistantClose" class="assistant-close" type="button" aria-label="Cerrar chat" title="Cerrar"></button>
    </div>
  </div>
  <div id="assistantList" class="assistant-list"></div>
  <div id="assistantSuggestions" class="assistant-suggestions"></div>
  <form id="assistantForm" class="assistant-form">
    <div class="assistant-input-row">
      <input id="assistantInput" class="assistant-input" type="text" maxlength="800" placeholder="Pregunta a West" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" inputmode="text">
      <button id="assistantSend" class="assistant-send" type="submit" aria-label="Enviar mensaje" title="Enviar">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.4 20.6 21 12 3.4 3.4l2.1 6.8 9.3 1.8-9.3 1.8-2.1 6.8Z"></path></svg>
      </button>
    </div>
  </form>
</section>`;
    document.body.appendChild(wrapper);
  }

  function refs(){
    return {
      panel: document.getElementById("assistantPanel"),
      toggle: document.getElementById("assistantToggle"),
      closeBtn: document.getElementById("assistantClose"),
      cancelBtn: document.getElementById("assistantCancel"),
      form: document.getElementById("assistantForm"),
      list: document.getElementById("assistantList"),
      input: document.getElementById("assistantInput"),
      send: document.getElementById("assistantSend"),
      status: document.getElementById("assistantStatus"),
      suggestions: document.getElementById("assistantSuggestions"),
      nudge: document.getElementById("assistantNudge"),
      nudgeClose: document.getElementById("assistantNudgeClose")
    };
  }

  function getAssistantChatId(){
    if(!assistantSessionChatId){
      assistantSessionChatId = `web-${Date.now()}-${Math.random().toString(36).slice(2,10)}`;
      assistantPersistConversation();
    }
    return assistantSessionChatId;
  }

  function assistantPersistConversation(){
    if(assistantHydratingState) return;
    try{
      localStorage.setItem(ASSISTANT_STORAGE_KEY, JSON.stringify({
        chatId: assistantSessionChatId || "",
        messages: assistantConversation.slice(-80).map((entry) => ({
          role: entry && entry.role === "user" ? "user" : "bot",
          text: String(entry && entry.text || ""),
          error: !!(entry && entry.error),
          pending: !!(entry && entry.pending)
        }))
      }));
    }catch(_e){}
  }

  function assistantRestoreConversation(){
    const { list } = refs();
    if(!list) return;
    let raw = null;
    try{
      raw = localStorage.getItem(ASSISTANT_STORAGE_KEY);
    }catch(_e){
      raw = null;
    }
    if(!raw) return;
    let parsed = null;
    try{
      parsed = JSON.parse(raw);
    }catch(_e){
      parsed = null;
    }
    const messages = Array.isArray(parsed && parsed.messages) ? parsed.messages : [];
    assistantSessionChatId = String(parsed && parsed.chatId || "").trim() || null;
    if(!messages.length) return;
    assistantHydratingState = true;
    assistantConversation = [];
    list.innerHTML = "";
    messages.forEach((entry) => {
      assistantAddMessage(entry && entry.role === "user" ? "user" : "bot", entry && entry.text || "", {
        error: !!(entry && entry.error),
        pending: false
      });
    });
    assistantHydratingState = false;
    assistantIntroShown = true;
    assistantCurrentMessageEl = null;
    assistantScrollToBottom();
  }

  function assistantSetStatus(text, tone){
    const { status } = refs();
    if(!status) return;
    status.textContent = text || "";
    status.dataset.tone = tone || "ready";
  }

  function assistantSetSendButtonVisual(send, busy){
    if(!send) return;
    if(busy){
      send.classList.add("is-stop");
      send.innerHTML = '<span class="assistant-stop-icon" aria-hidden="true"></span>';
      send.setAttribute("aria-label", "Detener respuesta");
      send.setAttribute("title", "Detener");
      return;
    }
    send.classList.remove("is-stop");
    send.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.4 20.6 21 12 3.4 3.4l2.1 6.8 9.3 1.8-9.3 1.8-2.1 6.8Z"></path></svg>';
    send.setAttribute("aria-label", "Enviar mensaje");
    send.setAttribute("title", "Enviar");
  }

  function assistantScrollToBottom(){
    const { list } = refs();
    if(list) list.scrollTop = list.scrollHeight;
  }

  function escapeAssistantHtml(text){
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function assistantLinkifyText(text){
    const escaped = escapeAssistantHtml(text);
    const withLinks = escaped.replace(/\bhttps?:\/\/[^\s<]+[^\s<\.,;:!?)]/gi, (url) => `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`);
    return withLinks.replace(/\n/g, "<br>");
  }

  function assistantSetMessageContent(target, text, role){
    if(!target) return;
    const cleanText = String(text || "");
    if(role === "bot"){
      target.innerHTML = assistantLinkifyText(cleanText);
      return;
    }
    target.textContent = cleanText;
  }

  function assistantAddMessage(role, text, options){
    const { list } = refs();
    if(!list) return null;
    const item = document.createElement("div");
    item.className = `assistant-msg ${role === "user" ? "user" : "bot"}`;
    if(options && options.pending) item.classList.add("pending");
    if(options && options.error) item.classList.add("error");
    item.dataset.role = role === "user" ? "user" : "bot";
    item.dataset.assistantMessageId = String(assistantConversation.length);
    assistantSetMessageContent(item, text || "", item.dataset.role);
    list.appendChild(item);
    assistantConversation.push({
      role: item.dataset.role,
      text: String(text || ""),
      pending: !!(options && options.pending),
      error: !!(options && options.error)
    });
    assistantPersistConversation();
    assistantScrollToBottom();
    return item;
  }

  function assistantUpdateMessage(target, text, options){
    if(!target) return;
    target.classList.toggle("pending", !!(options && options.pending));
    target.classList.toggle("error", !!(options && options.error));
    assistantSetMessageContent(target, text || "", target.dataset.role || "bot");
    const messageIndex = Number(target.dataset.assistantMessageId);
    if(Number.isInteger(messageIndex) && assistantConversation[messageIndex]){
      assistantConversation[messageIndex] = {
        role: assistantConversation[messageIndex].role === "user" ? "user" : "bot",
        text: String(text || ""),
        pending: !!(options && options.pending),
        error: !!(options && options.error)
      };
      assistantPersistConversation();
    }
    assistantScrollToBottom();
  }

  async function assistantRenderChunkProgressively(state, chunk){
    if(!state || !state.target || !chunk) return;
    const parts = String(chunk).match(/\S+\s*|\n/g) || [String(chunk)];
    for(const part of parts){
      if(state.cancelled || assistantRenderCancelled || assistantAbortReason === "cancel" || assistantAbortReason === "hidden") return;
      state.rendered += part;
      assistantUpdateMessage(state.target, state.rendered, { pending: false });
      const visible = part.replace(/\s+/g, "");
      const delay = part === "\n" ? 70 : Math.max(26, Math.min(68, visible.length * 8));
      await assistantSleep(delay);
    }
  }

  async function assistantDrainRenderQueue(state){
    if(!state || state.running) return;
    state.running = true;
    try{
      while(state.queue.length){
        const next = state.queue.shift();
        await assistantRenderChunkProgressively(state, next);
      }
    } finally {
      state.running = false;
    }
  }

  async function assistantRenderMessageTokenByToken(target, text){
    if(!target) return;
    const state = { target, rendered:"", queue:[String(text || "")], running:false, cancelled:false };
    await assistantDrainRenderQueue(state);
  }

  function assistantRefreshControls(){
    const { input, send, cancelBtn } = refs();
    const canInteract = !assistantBusy;
    if(input) input.disabled = !canInteract;
    if(send){
      const hasText = !!(input && input.value.trim());
      send.disabled = assistantBusy ? false : !hasText;
      assistantSetSendButtonVisual(send, assistantBusy);
    }
    if(cancelBtn){
      cancelBtn.hidden = !assistantBusy;
      cancelBtn.disabled = !assistantBusy;
    }
  }

  function setAssistantBusy(busy){
    assistantBusy = !!busy;
    assistantRefreshControls();
  }

  async function assistantEnsureIntro(){
    if(assistantIntroShown) return assistantIntroRenderPromise;
    assistantIntroShown = true;
    const introMsg = assistantAddMessage("bot", "");
    assistantIntroRenderPromise = assistantRenderMessageTokenByToken(introMsg, "Â¡Hola! Soy West, el asistente de Todo Sevilla Este. Â¿En quÃ© puedo ayudarte?")
      .finally(() => { assistantIntroRenderPromise = null; });
    return assistantIntroRenderPromise;
  }

  function normalizeAssistantError(text){
    const clean = String(text || "").trim();
    if(!clean) return "No se pudo completar la respuesta.";
    if(/^Error:\s*/i.test(clean)) return clean.replace(/^Error:\s*/i, "").trim() || "No se pudo completar la respuesta.";
    return clean;
  }

  function abortAssistantConnection(message, reason){
    const finalReason = reason || "cancel";
    assistantAbortReason = finalReason;
    assistantRenderCancelled = true;
    if(assistantAbortController){
      try{ assistantAbortController.abort(); }catch(_e){}
    }
    if(message && assistantCurrentMessageEl){
      assistantUpdateMessage(assistantCurrentMessageEl, message, { error: finalReason === "timeout" });
      assistantCurrentMessageEl = null;
    }else if(message){
      assistantAddMessage("bot", message, { error: finalReason === "timeout" });
    }
    if(message){
      assistantSetStatus(message, finalReason === "timeout" ? "error" : "ready");
    }
    setAssistantBusy(false);
  }

  async function sendAssistantMessage(text){
    if(assistantBusy) return;
    const clean = String(text || "").trim();
    if(!clean) return;
    await assistantEnsureIntro();
    assistantAddMessage("user", clean);
    const botMsg = assistantAddMessage("bot", "Pensando...", { pending: true });
    assistantCurrentMessageEl = botMsg;
    assistantAbortReason = "";
    assistantRenderCancelled = false;
    setAssistantBusy(true);
    assistantSetStatus("Consultando al asistente...", "working");
    const controller = new AbortController();
    assistantAbortController = controller;
    const timeoutId = setTimeout(() => {
      assistantAbortReason = "timeout";
      controller.abort();
    }, ASSISTANT_REQUEST_TIMEOUT_MS);

    try{
      const res = await fetch(`${AGENT_API_BASE}/agents/public/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: clean, chat_id: getAssistantChatId() }),
        signal: controller.signal
      });
      if(!res.ok){
        const data = await res.json().catch(() => ({}));
        const msg = typeof data.detail === "string" ? data.detail : "No se pudo obtener respuesta del asistente.";
        assistantUpdateMessage(botMsg, `Error: ${msg}`, { error: true });
        assistantSetStatus("No se pudo completar la consulta.", "error");
        return;
      }
      if(!res.body){
        assistantUpdateMessage(botMsg, "Sin respuesta.", { error: true });
        assistantSetStatus("La IA no devolviÃ³ contenido.", "error");
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let full = "";
      let sawContent = false;
      const renderState = { target: botMsg, queue: [], rendered: "", running: false, cancelled: false };
      while(true){
        const { done, value } = await reader.read();
        if(done) break;
        const piece = decoder.decode(value, { stream: true }).replace(/\u200b/g, "");
        if(!piece) continue;
        if(!sawContent){
          sawContent = true;
          assistantSetStatus("Respondiendo...", "working");
        }
        full += piece;
        renderState.queue.push(piece);
        assistantDrainRenderQueue(renderState);
      }
      full += decoder.decode().replace(/\u200b/g, "");
      while(renderState.running || renderState.queue.length){
        await assistantSleep(10);
      }
      const finalText = full.trim() || "Sin respuesta.";
      if(/^Error:/i.test(finalText)){
        assistantUpdateMessage(botMsg, `Error: ${normalizeAssistantError(finalText)}`, { error: true });
        assistantSetStatus("No se pudo completar la consulta.", "error");
        return;
      }
      if(renderState.rendered !== finalText){
        assistantUpdateMessage(botMsg, finalText, { pending: false });
      }
      assistantSetStatus("Respuesta lista.", "ready");
    }catch(err){
      if(err && err.name === "AbortError"){
        let msg = "Respuesta cancelada.";
        if(assistantAbortReason === "timeout"){
          msg = "La respuesta estÃ¡ tardando mÃ¡s de lo normal. Intenta una pregunta mÃ¡s concreta o vuelve a probar en unos segundos.";
        }else if(assistantAbortReason === "hidden"){
          msg = "El asistente se ha ocultado temporalmente.";
        }
        assistantUpdateMessage(botMsg, msg, { error: assistantAbortReason === "timeout" });
        assistantSetStatus(msg, assistantAbortReason === "timeout" ? "error" : "ready");
      }else{
        assistantUpdateMessage(botMsg, "No hay conexiÃ³n con el asistente en este momento.", { error: true });
        assistantSetStatus("No se pudo contactar con el asistente.", "error");
      }
    }finally{
      clearTimeout(timeoutId);
      assistantAbortController = null;
      assistantAbortReason = "";
      assistantRenderCancelled = false;
      assistantCurrentMessageEl = null;
      setAssistantBusy(false);
    }
  }

  function updateAssistantFooterOffset(){
    const footer = document.querySelector(".site-footer");
    const root = document.documentElement;
    if(!root) return;
    if(!footer){
      root.style.setProperty("--assistant-footer-offset", "0px");
      return;
    }
    const footerRect = footer.getBoundingClientRect();
    const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;
    const overlap = Math.max(0, viewportHeight - footerRect.top);
    const safeGap = overlap > 0 ? overlap + 16 : 0;
    root.style.setProperty("--assistant-footer-offset", `${Math.round(safeGap)}px`);
  }

  function scheduleAssistantFooterOffsetUpdate(){
    if(assistantFooterOffsetRaf) return;
    assistantFooterOffsetRaf = requestAnimationFrame(() => {
      assistantFooterOffsetRaf = null;
      updateAssistantFooterOffset();
    });
  }

  function startAssistantFooterOffsetSync(){
    scheduleAssistantFooterOffsetUpdate();
    setTimeout(scheduleAssistantFooterOffsetUpdate, 120);
    setTimeout(scheduleAssistantFooterOffsetUpdate, 420);
    setTimeout(scheduleAssistantFooterOffsetUpdate, 900);
    window.addEventListener("load", scheduleAssistantFooterOffsetUpdate, { once: true });

    if(typeof ResizeObserver === "function" && !assistantFooterResizeObserver){
      assistantFooterResizeObserver = new ResizeObserver(() => {
        scheduleAssistantFooterOffsetUpdate();
      });
      const footer = document.querySelector(".site-footer");
      if(footer) assistantFooterResizeObserver.observe(footer);
      if(document.body) assistantFooterResizeObserver.observe(document.body);
    }
  }

  function initFrontendAssistant(){
    const { panel, toggle, closeBtn, cancelBtn, form, input, suggestions, nudge, nudgeClose } = refs();
    if(!panel || !toggle || !closeBtn || !form || !input || !suggestions) return;
    assistantRestoreConversation();

    let assistantNudgeShown = false;
    let assistantNudgeShowTimer = null;
    let assistantNudgeHideTimer = null;

    const hideAssistantNudge = () => {
      if(assistantNudgeShowTimer){ clearTimeout(assistantNudgeShowTimer); assistantNudgeShowTimer = null; }
      if(assistantNudgeHideTimer){ clearTimeout(assistantNudgeHideTimer); assistantNudgeHideTimer = null; }
      if(nudge){
        nudge.classList.remove("show");
        nudge.setAttribute("aria-hidden", "true");
      }
    };
    const dismissAssistantNudgeByInteraction = (event) => {
      if(event){
        try{ event.preventDefault(); }catch(_e){}
        try{ event.stopPropagation(); }catch(_e){}
      }
      assistantNudgeShown = true;
      hideAssistantNudge();
    };

    const showAssistantNudge = () => {
      if(!nudge || assistantNudgeShown || panel.classList.contains("open") || toggle.classList.contains("is-hidden")) return;
      assistantNudgeShown = true;
      nudge.classList.add("show");
      nudge.setAttribute("aria-hidden", "false");
      assistantNudgeHideTimer = setTimeout(() => {
        hideAssistantNudge();
      }, ASSISTANT_NUDGE_AUTO_HIDE_DELAY_MS);
    };

    const scheduleAssistantNudge = () => {
      if(!nudge || assistantNudgeShown) return;
      if(assistantNudgeShowTimer) clearTimeout(assistantNudgeShowTimer);
      assistantNudgeShowTimer = setTimeout(showAssistantNudge, ASSISTANT_NUDGE_SHOW_DELAY_MS);
    };

    const setAssistantToggleVisibility = (visible) => {
      toggle.classList.toggle("is-hidden", !visible);
      if(!visible) hideAssistantNudge();
    };

    const openPanel = async () => {
      hideAssistantNudge();
      setAssistantToggleVisibility(false);
      await assistantSleep(ASSISTANT_TOGGLE_SLIDE_LEAD_MS);
      panel.classList.add("open");
      await assistantEnsureIntro();
      assistantSetStatus(assistantBusy ? "Respondiendo..." : "Listo para ayudarte.", assistantBusy ? "working" : "ready");
      assistantScrollToBottom();
      setTimeout(() => input.focus(), 40);
    };

    const closePanel = () => {
      abortAssistantConnection("", "cancel");
      panel.classList.remove("open");
      setTimeout(() => {
        setAssistantToggleVisibility(true);
      }, ASSISTANT_TOGGLE_SLIDE_LEAD_MS);
    };

    toggle.addEventListener("click", async () => {
      hideAssistantNudge();
      if(panel.classList.contains("open")) closePanel();
      else await openPanel();
    });
    closeBtn.addEventListener("click", closePanel);
    if(nudgeClose){
      nudgeClose.addEventListener("click", dismissAssistantNudgeByInteraction);
    }
    if(nudge){
      nudge.addEventListener("click", dismissAssistantNudgeByInteraction);
      nudge.addEventListener("pointerup", dismissAssistantNudgeByInteraction);
      nudge.addEventListener("touchend", dismissAssistantNudgeByInteraction, { passive:false });
    }
    if(cancelBtn){
      cancelBtn.addEventListener("click", () => {
        abortAssistantConnection("Respuesta cancelada.", "cancel");
      });
    }
    input.addEventListener("keydown", (event) => {
      if(event.key === "Enter" && !event.shiftKey && assistantBusy){
        event.preventDefault();
      }
    });
    input.addEventListener("input", assistantRefreshControls);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if(assistantBusy){
        abortAssistantConnection("Respuesta cancelada.", "cancel");
        return;
      }
      const text = input.value;
      input.value = "";
      assistantRefreshControls();
      await sendAssistantMessage(text);
    });
    suggestions.addEventListener("click", async (event) => {
      const trigger = event.target.closest("[data-assistant-prompt]");
      if(!trigger || trigger.disabled) return;
      await sendAssistantMessage(trigger.dataset.assistantPrompt || "");
    });

    assistantRefreshControls();
    setAssistantToggleVisibility(!panel.classList.contains("open"));
    scheduleAssistantNudge();
    startAssistantFooterOffsetSync();
    window.addEventListener("scroll", scheduleAssistantFooterOffsetUpdate, { passive: true });
    window.addEventListener("resize", scheduleAssistantFooterOffsetUpdate, { passive: true });
  }

  function boot(){
    ensureWidgetMarkup();
    initFrontendAssistant();
  }

  if(document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  }else{
    boot();
  }
})();

