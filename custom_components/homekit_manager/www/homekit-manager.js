const PAGE_SIZE = 100;
const WS_INVENTORY = "homekit_manager/inventory";
const WS_YAML_STATUS = "homekit_manager/yaml_status";
const WS_VALIDATE = "homekit_manager/validate_draft";
const WS_PREVIEW = "homekit_manager/preview";
const WS_SAVE = "homekit_manager/save_draft";
const WS_EXPORT = "homekit_manager/export";

class HomeKitManagerPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this.entities = [];
    this.overview = {};
    this.bridge = null;
    this.query = "";
    this.filters = { area_name: "", device_name: "", integration_domain: "", domain: "", device_class: "", entity_category: "", compatibility: "", status: "" };
    this.sort = { key: "entity_id", direction: 1 };
    this.page = 0;
    this.selected = new Set();
    this.draft = new Map();
    this.fingerprint = null;
    this.conflict = false;
    this.detail = null;
    this.yamlStatus = { valid: true, exists: false, is_applied: false };
    this.serverPreview = null;
    this.statusMessage = "Keine Änderungen";
    this.loading = false;
    this.error = null;
    this._loaded = false;
    this._panel = null;
    this._narrow = false;
    this.render();
  }

  connectedCallback() {
    this.render();
  }

  set hass(value) {
    const previous = this._hass;
    this._hass = value;
    this.render();
    if (!this._loaded) {
      this._loaded = true;
      this.refresh();
    } else if (previous && previous.states !== value.states) {
      this.scheduleRefresh();
    }
  }
  get hass() { return this._hass; }

  set panel(value) {
    this._panel = value;
    this.render();
  }
  get panel() { return this._panel; }

  set narrow(value) {
    this._narrow = Boolean(value);
    this.render();
  }
  get narrow() { return this._narrow; }

  scheduleRefresh() {
    if (this._refreshTimer) return;
    this._refreshTimer = setTimeout(() => {
      this._refreshTimer = null;
      this.refresh();
    }, 250);
  }

  async refresh() {
    if (!this._hass || this.loading) return;
    this.loading = true;
    this.error = null;
    this.render();
    try {
      if (typeof this._hass.callWS !== "function") {
        throw new Error("Home-Assistant-WebSocket nicht verfügbar");
      }
      const data = await this._hass.callWS({ type: WS_INVENTORY });
      const next = data.entities || [];
      if (this.fingerprint && data.overview && this.fingerprint !== data.overview.fingerprint) this.conflict = true;
      this.entities = next;
      this.overview = data.overview || {};
      this.fingerprint = this.overview.fingerprint || null;
      this.bridge = (await this._hass.callWS({ type: "homekit_manager/bridges" })).bridges?.[0] || null;
      this.yamlStatus = await this._hass.callWS({ type: WS_YAML_STATUS });
      if (!this.draft.size) this.statusMessage = this.yamlStatus.exists ? "Entwurf gespeichert" : "Keine Änderungen";
    } catch (error) {
      this.error = error?.message || String(error);
    } finally {
      this.loading = false;
      this.render();
    }
  }

  get filtered() {
    const q = this.query.trim().toLowerCase();
    return this.entities.filter((e) => {
      if (q && !(String(e.name || "").toLowerCase().includes(q) || e.entity_id.toLowerCase().includes(q))) return false;
      for (const key of Object.keys(this.filters)) {
        const wanted = this.filters[key];
        if (!wanted) continue;
        if (key === "compatibility" && e.compatibility?.status !== wanted) return false;
        if (key === "status") {
          const status = this.draft.has(e.entity_id) ? (this.draft.get(e.entity_id) === "include" ? "included" : "excluded") : e.homekit?.configured_by_filter === true ? "included" : e.homekit?.configured_by_filter === false ? "excluded" : "unknown";
          if (status !== wanted && !(wanted === "unchanged" && !this.draft.has(e.entity_id))) return false;
        } else if (String(e[key] ?? "none") !== wanted) return false;
      }
      return true;
    }).sort((a, b) => {
      const av = String(this.value(a, this.sort.key) ?? "");
      const bv = String(this.value(b, this.sort.key) ?? "");
      return av.localeCompare(bv, "de", { numeric: true }) * this.sort.direction;
    });
  }

  value(entity, key) {
    if (key === "compatibility") return entity.compatibility?.status;
    if (key === "status") return this.status(entity);
    return entity[key];
  }
  status(entity) {
    if (this.draft.has(entity.entity_id)) return this.draft.get(entity.entity_id) || "unchanged";
    if (entity.homekit?.configured_by_filter === true) return "included";
    if (entity.homekit?.configured_by_filter === false) return "excluded";
    return "unknown";
  }
  setFilter(key, value) {
    this.filters[key] = value;
    this.page = 0;
    this.render();
  }
  toggleSort(key) {
    if (this.sort.key === key) this.sort.direction *= -1;
    else this.sort = { key, direction: 1 };
    this.render();
  }
  setDraft(id, value) {
    const entity = this.entities.find((e) => e.entity_id === id);
    if (!entity || entity.compatibility?.status === "unsupported") return;
    if (!value) this.draft.delete(id); else this.draft.set(id, value);
    this.render();
  }
  applyToSelection(value) {
    for (const id of this.selected) this.setDraft(id, value);
    this.selected.clear();
    this.render();
  }
  selectVisible(compatibleOnly) {
    for (const e of this.filtered) if (!compatibleOnly || e.compatibility?.status !== "unsupported") this.selected.add(e.entity_id);
    this.render();
  }
  discard() {
    this.draft.clear();
    this.selected.clear();
    this.conflict = false;
    this.serverPreview = null;
    this.statusMessage = "Keine Änderungen";
    this.render();
  }
  changes() {
    return [...this.draft.entries()].map(([entity_id, desired]) => {
      const e = this.entities.find((item) => item.entity_id === entity_id);
      const current = e ? (e.homekit?.configured_by_filter === true ? "include" : e.homekit?.configured_by_filter === false ? "exclude" : "unknown") : "removed";
      return { entity_id, current, desired, risk: current === "unknown" || current === "removed" ? "unknown" : "bridge reload and Apple Home placement not guaranteed" };
    });
  }
  async exportDraft() {
    try {
      const result = await this._hass.callWS({ type: WS_EXPORT, document: this.desiredDocument(), format: "yaml" });
      await navigator.clipboard?.writeText(result.content || "");
      this.statusMessage = "Entwurf exportiert";
    } catch (error) {
      this.error = error?.message || String(error);
      this.statusMessage = "Export fehlgeschlagen";
    }
    this.render();
  }

  desiredDocument() {
    const entry = this.bridge?.entry_id;
    return { schema_version: 1, bridges: entry ? { [entry]: { policy: "explicit_overrides", entities: Object.fromEntries(this.draft) } } : {} };
  }

  async validateDraft() {
    try {
      const result = await this._hass.callWS({ type: WS_VALIDATE, document: this.desiredDocument() });
      this.statusMessage = result.warnings?.length ? "Entwurf gespeichert · Hinweise vorhanden" : "Entwurf validiert";
      return result;
    } catch (error) {
      this.statusMessage = "YAML-Datei ungültig";
      this.error = error?.message || String(error);
      return null;
    }
  }

  async previewServer() {
    const result = await this.validateDraft();
    if (!result) return;
    try {
      this.serverPreview = await this._hass.callWS({ type: WS_PREVIEW, document: result.document });
      this.conflict = Boolean(this.serverPreview.summary?.blocked) || (this.fingerprint && this.serverPreview.fingerprint !== this.fingerprint);
      this.statusMessage = this.conflict ? "Konflikt erkannt" : "Entwurf validiert";
    } catch (error) {
      this.error = error?.message || String(error);
    }
    this.render();
  }

  async saveDraft() {
    const result = await this.validateDraft();
    if (!result || this.conflict) return;
    try {
      const request = { type: WS_SAVE, document: result.document };
      if (this.yamlStatus.file_version) request.expected_file_version = this.yamlStatus.file_version;
      if (this.fingerprint) request.expected_fingerprint = this.fingerprint;
      this.yamlStatus = await this._hass.callWS(request);
      this.statusMessage = "Entwurf gespeichert";
      this.serverPreview = null;
    } catch (error) {
      this.conflict = true;
      this.statusMessage = "Konflikt erkannt";
      this.error = error?.message || String(error);
    }
    this.render();
  }

  async loadSaved() {
    await this.refresh();
    const entry = this.bridge?.entry_id;
    const saved = entry ? this.yamlStatus.document?.bridges?.[entry]?.entities || {} : {};
    this.draft = new Map(Object.entries(saved));
    this.statusMessage = "Entwurf gespeichert";
    this.render();
  }

  openNativeOptions() {
    // This is only the documented frontend integration page. The manager
    // never starts or submits a Home Assistant flow programmatically.
    window.open("/config/integrations/integration/homekit", "_blank", "noopener");
  }

  render() {
    const rows = this.filtered;
    const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
    this.page = Math.min(this.page, pages - 1);
    const visible = rows.slice(this.page * PAGE_SIZE, (this.page + 1) * PAGE_SIZE);
    const options = (key) => [...new Set(this.entities.map((e) => e[key] || "none"))].sort();
    const select = (key, label, values) => '<label>' + label + '<select data-filter="' + key + '"><option value="">Alle</option>' + values.map((v) => '<option value="' + this.escape(v) + '"' + (this.filters[key] === v ? " selected" : "") + '>' + this.escape(v) + '</option>').join("") + "</select></label>";
    const row = (e) => {
      const state = this.status(e);
      const disabled = e.compatibility?.status === "unsupported" ? " disabled" : "";
      const checked = this.selected.has(e.entity_id) ? " checked" : "";
      return '<tr data-id="' + this.escape(e.entity_id) + '"><td><input type="checkbox" data-select' + checked + '></td><td><button class="link" data-detail>' + this.escape(e.name || e.entity_id) + '</button></td><td><code>' + this.escape(e.entity_id) + '</code></td><td>' + this.escape(e.area_name || "Kein Bereich") + '</td><td>' + this.escape(e.device_name || "—") + '</td><td>' + this.escape(e.integration_domain || "—") + '</td><td>' + this.escape(e.domain) + '</td><td>' + this.escape(e.device_class || "—") + '</td><td>' + this.escape(e.entity_category || "—") + '</td><td><span class="badge ' + this.escape(e.compatibility?.status || "unknown") + '">' + this.escape(e.compatibility?.status || "unknown") + '</span><small>' + this.escape(e.compatibility?.expected_type || "—") + '</small></td><td>' + this.escape(state) + '</td><td>' + (e.available ? "verfügbar" : "nicht verfügbar") + '</td><td><select data-draft="' + this.escape(e.entity_id) + '"' + disabled + '><option value="">Unverändert</option><option value="include"' + (state === "include" ? " selected" : "") + '>Include</option><option value="exclude"' + (state === "exclude" ? " selected" : "") + '>Exclude</option></select></td></tr>';
    };
    const preview = this.serverPreview?.changes || this.changes();
    const error = this.error ? '<aside class="error" role="alert"><strong>Initialisierung fehlgeschlagen</strong><p>' + this.escape(this.error) + '</p><button class="secondary" data-refresh>Erneut versuchen</button></aside>' : '';
    const loading = this.loading ? '<p class="loading" role="status">Inventardaten werden geladen …</p>' : '';
    this.shadowRoot.innerHTML = '<style>' + this.styles() + '</style><main><header><div><h1>HomeKit Manager</h1><p>Gewünschter Zustand · keine Änderung an der HomeKit-Bridge</p><p class="status">Status: ' + this.escape(this.statusMessage) + (this.yamlStatus.valid === false ? ' · YAML-Datei ungültig' : '') + '</p></div><button class="secondary" data-refresh>Aktualisieren</button></header>' + loading + error + '<section class="summary">' + this.summary("Bridge", this.bridge?.title || "unbekannt") + this.summary("Entitäten", this.overview.total_entities) + this.summary("Kompatibel", this.overview.compatible_entities ?? "unbekannt") + this.summary("Freigegeben", this.overview.configured_entities ?? "unbekannt") + this.summary("Gefiltert", rows.length) + '</section>' + (this.conflict ? '<aside class="warning">Konflikt oder blockierte Änderung erkannt. Neue Vorschau nach Aktualisierung erforderlich.</aside>' : "") + '<section class="filters"><input data-query placeholder="Name oder Entitäts-ID suchen" value="' + this.escape(this.query) + '">' + select("area_name", "Bereich", options("area_name")) + select("device_name", "Gerät", options("device_name")) + select("integration_domain", "Integration", options("integration_domain")) + select("domain", "Domäne", options("domain")) + select("device_class", "Geräteklasse", options("device_class")) + select("entity_category", "Kategorie", options("entity_category")) + select("compatibility", "Kompatibilität", ["supported", "conditionally_supported", "unsupported", "unknown"]) + select("status", "Status", ["included", "excluded", "unchanged", "unknown"]) + '</section><section class="actions"><button data-select-compatible>Kompatible sichtbare auswählen</button><button data-include>Auswahl einschließen</button><button data-exclude>Auswahl ausschließen</button><button data-unchanged>Auswahl zurücksetzen</button><button class="secondary" data-preview>Änderungen prüfen (' + this.changes().length + ')</button><button class="secondary" data-save>Entwurf speichern</button><button class="secondary" data-load>Gespeicherten Entwurf laden</button><button class="secondary" data-discard>Entwurf verwerfen</button><button class="secondary" data-native-options>Offiziellen HomeKit-Dialog öffnen</button><button disabled title="Wird erst in einer späteren Phase aktiviert">Änderungen übernehmen</button></section><p class="hint">Gespeicherte YAML ist ein gewünschter Zustand und wurde nicht an HomeKit übertragen. Der offizielle Dialog wird nur geöffnet; der Manager übergibt keine Flow-Daten automatisch.</p><section class="table-wrap"><table><thead><tr>' + ["Auswahl", "Name", "Entitäts-ID", "Bereich", "Gerät", "Integration", "Domäne", "Geräteklasse", "Kategorie", "Kompatibilität", "Status", "Verfügbarkeit", "Gewünschte Regel"].map((h, i) => '<th data-sort="' + (i === 0 ? "" : ["", "name", "entity_id", "area_name", "device_name", "integration_domain", "domain", "device_class", "entity_category", "compatibility", "status", "", ""][i]) + '">' + h + '</th>').join("") + '</tr></thead><tbody>' + visible.map(row).join("") + '</tbody></table></section><nav class="pager"><button data-prev' + (this.page === 0 ? " disabled" : "") + '>‹</button><span>Seite ' + (this.page + 1) + ' / ' + pages + ' · ' + rows.length + ' Treffer</span><button data-next' + (this.page + 1 >= pages ? " disabled" : "") + '>›</button></nav>' + (this.detail ? this.detailTemplate(this.detail) : "") + '<dialog data-preview-dialog><h2>Serverseitige Änderungsvorschau</h2>' + (preview.length ? '<ul>' + preview.map((c) => '<li><code>' + this.escape(c.entity_id) + '</code>: ' + this.escape(c.current) + ' → ' + this.escape(c.desired) + ' · ' + this.escape(c.action || "unchanged") + ' <span class="warning-text">(' + this.escape(c.reason || c.risk || "") + ')</span></li>').join("") + '</ul>' : '<p>Keine vorgemerkten Änderungen.</p>') + '<button data-close>Schließen</button><button class="secondary" data-export>Entwurf als YAML kopieren</button></dialog></main>';
    this.bind();
  }

  summary(label, value) { return '<div><span>' + label + '</span><strong>' + this.escape(value) + '</strong></div>'; }
  detailTemplate(e) { return '<aside class="detail"><button data-close-detail>Schließen</button><h2>' + this.escape(e.name || e.entity_id) + '</h2><dl>' + [["Entity-ID", e.entity_id], ["Gerät", e.device_name || "—"], ["Integration", e.integration_domain || "—"], ["Bereich", e.area_name || "Kein Bereich"], ["Domäne", e.domain], ["Geräteklasse", e.device_class || "—"], ["Kategorie", e.entity_category || "—"], ["Disabled", e.disabled_by || "nein"], ["Hidden", e.hidden_by || "nein"], ["Verfügbarkeit", e.available ? "verfügbar" : "nicht verfügbar"], ["Kompatibilität", e.compatibility?.status || "unknown"], ["HomeKit-Typ", e.compatibility?.expected_type || "—"], ["Begründung", e.compatibility?.reason || "—"], ["Filterregel", e.homekit?.filter_reason || "unknown"], ["Veröffentlichung", e.homekit?.published || "unknown"]].map(([k, v]) => '<dt>' + k + '</dt><dd>' + this.escape(v) + '</dd>').join("") + '</dl></aside>'; }
  escape(value) { return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
  styles() { return ':host{display:block;color:var(--primary-text-color,#212121);background:var(--primary-background-color,#fafafa);min-height:100vh;font-family:var(--paper-font-body1_-_font-family, sans-serif)}main{max-width:1800px;margin:auto;padding:24px}header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}h1{margin:0;font-size:2rem}h2{margin-top:0}p{color:var(--secondary-text-color,#616161)}button,select,input{font:inherit;color:inherit;background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#ddd);border-radius:8px;padding:8px 10px}button{cursor:pointer}button:disabled{opacity:.5;cursor:not-allowed}.secondary{background:transparent}.link{border:0;background:transparent;padding:0;color:var(--primary-color,#03a9f4);text-align:left}.loading,.error{padding:14px;border-radius:8px}.loading{background:var(--card-background-color,#fff)}.error{background:var(--error-color,#db4437);color:#fff}.error p{color:inherit}.summary{display:grid;grid-template-columns:repeat(5,minmax(120px,1fr));gap:12px;margin:24px 0}.summary div{background:var(--card-background-color,#fff);border-radius:12px;padding:16px}.summary span{display:block;color:var(--secondary-text-color,#616161);font-size:.85rem}.summary strong{font-size:1.6rem}.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:end;margin:16px 0}.filters label{display:flex;flex-direction:column;gap:4px;font-size:.8rem;color:var(--secondary-text-color,#616161)}.filters input{min-width:260px}.actions{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0}.hint{padding:10px 14px;border-left:3px solid var(--primary-color,#03a9f4)}.warning{padding:12px;background:var(--warning-color,#f5c542);color:var(--primary-text-color,#212121);border-radius:8px}.table-wrap{overflow:auto;border:1px solid var(--divider-color,#ddd);border-radius:12px;background:var(--card-background-color,#fff)}table{border-collapse:collapse;width:100%;min-width:1250px}th,td{padding:9px 10px;text-align:left;border-bottom:1px solid var(--divider-color,#ddd);white-space:nowrap}th[data-sort]{cursor:pointer}th{position:sticky;top:0;background:var(--card-background-color,#fff);z-index:1}small{display:block;color:var(--secondary-text-color,#616161)}.badge{display:inline-block;border-radius:999px;padding:3px 7px;font-size:.75rem}.supported{background:var(--success-color,#4caf50)}.conditionally_supported{background:var(--warning-color,#f5c542)}.unsupported{background:var(--error-color,#db4437);color:white}.unknown{background:var(--secondary-text-color,#777);color:var(--primary-background-color,#fff)}.pager{display:flex;justify-content:center;gap:20px;align-items:center;padding:16px}.detail{position:fixed;right:24px;top:24px;bottom:24px;width:min(480px,90vw);overflow:auto;background:var(--card-background-color,#fff);box-shadow:var(--ha-box-shadow,0 4px 16px #0005);border-radius:14px;padding:24px;z-index:4}.detail button{float:right}dt{font-weight:bold;margin-top:12px}dd{margin:3px 0;color:var(--secondary-text-color,#616161)}dialog{color:var(--primary-text-color,#212121);background:var(--card-background-color,#fff);border:1px solid var(--divider-color,#ddd);border-radius:12px;max-width:720px}dialog::backdrop{background:#0008}.warning-text{color:var(--error-color,#db4437)}@media(max-width:700px){main{padding:14px}header{align-items:stretch;flex-direction:column}.summary{grid-template-columns:repeat(2,1fr);margin:16px 0}.filters input{min-width:100%}.actions button{flex:1 1 45%}.detail{right:8px;top:8px;bottom:8px;width:auto}}'; }

  bind() {
    this.shadowRoot.querySelector("[data-refresh]")?.addEventListener("click", () => this.refresh());
    this.shadowRoot.querySelector("[data-query]")?.addEventListener("input", (e) => { this.query = e.target.value; this.page = 0; this.render(); });
    this.shadowRoot.querySelectorAll("[data-filter]").forEach((e) => e.addEventListener("change", (event) => this.setFilter(event.target.dataset.filter, event.target.value)));
    this.shadowRoot.querySelectorAll("[data-sort]").forEach((e) => e.dataset.sort && e.addEventListener("click", () => this.toggleSort(e.dataset.sort)));
    this.shadowRoot.querySelectorAll("[data-select]").forEach((e) => e.addEventListener("change", (event) => { const id = event.target.closest("tr").dataset.id; event.target.checked ? this.selected.add(id) : this.selected.delete(id); }));
    this.shadowRoot.querySelectorAll("[data-draft]").forEach((e) => e.addEventListener("change", (event) => this.setDraft(event.target.dataset.draft, event.target.value)));
    this.shadowRoot.querySelector("[data-select-compatible]")?.addEventListener("click", () => this.selectVisible(true));
    this.shadowRoot.querySelector("[data-include]")?.addEventListener("click", () => this.applyToSelection("include"));
    this.shadowRoot.querySelector("[data-exclude]")?.addEventListener("click", () => this.applyToSelection("exclude"));
    this.shadowRoot.querySelector("[data-unchanged]")?.addEventListener("click", () => this.applyToSelection(""));
    this.shadowRoot.querySelector("[data-discard]")?.addEventListener("click", () => this.discard());
    this.shadowRoot.querySelector("[data-preview]")?.addEventListener("click", async () => { await this.previewServer(); this.shadowRoot.querySelector("[data-preview-dialog]")?.showModal(); });
    this.shadowRoot.querySelector("[data-save]")?.addEventListener("click", () => this.saveDraft());
    this.shadowRoot.querySelector("[data-load]")?.addEventListener("click", () => this.loadSaved());
    this.shadowRoot.querySelector("[data-native-options]")?.addEventListener("click", () => this.openNativeOptions());
    this.shadowRoot.querySelector("[data-close]")?.addEventListener("click", () => this.shadowRoot.querySelector("[data-preview-dialog]").close());
    this.shadowRoot.querySelector("[data-export]")?.addEventListener("click", () => this.exportDraft());
    this.shadowRoot.querySelector("[data-prev]")?.addEventListener("click", () => { this.page--; this.render(); });
    this.shadowRoot.querySelector("[data-next]")?.addEventListener("click", () => { this.page++; this.render(); });
    this.shadowRoot.querySelectorAll("[data-detail]").forEach((e) => e.addEventListener("click", () => { this.detail = this.entities.find((x) => x.entity_id === e.closest("tr").dataset.id); this.render(); }));
    this.shadowRoot.querySelector("[data-close-detail]")?.addEventListener("click", () => { this.detail = null; this.render(); });
  }
}
if (!customElements.get("homekit-manager-panel")) {
  customElements.define("homekit-manager-panel", HomeKitManagerPanel);
}
