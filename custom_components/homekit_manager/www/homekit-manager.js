const PAGE_SIZE = 80;
const INVENTORY_BATCH_SIZE = 500;
const WS = {
  inventory: "homekit_manager/inventory", bridges: "homekit_manager/bridges", selectBridge: "homekit_manager/select_bridge",
  diagnostics: "homekit_manager/diagnostics",
  history: "homekit_manager/history", historyRestore: "homekit_manager/history_restore", rules: "homekit_manager/rules_preview",
  yaml: "homekit_manager/yaml_status", mode: "homekit_manager/mode_status", activation: "homekit_manager/activation_status",
  validate: "homekit_manager/validate_draft", preview: "homekit_manager/preview",
  save: "homekit_manager/save_draft", apply: "homekit_manager/apply_options_diff", export: "homekit_manager/export",
  operationPlan: "homekit_manager/operation_plan", operationApply: "homekit_manager/operation_apply", operationStatus: "homekit_manager/operation_status", operationReconcile: "homekit_manager/operation_reconcile",
  testModeEnable: "homekit_manager/test_write_mode_enable", testModeDisable: "homekit_manager/test_write_mode_disable",
  devicePreview: "homekit_manager/device_preview", performance: "homekit_manager/performance",
  migrationPlan: "homekit_manager/migration_plan", migrationStatus: "homekit_manager/migration_status",
  managementStatus: "homekit_manager/management_status",
};

class HomeKitManagerPanel extends HTMLElement {
  constructor() {
    super(); this.attachShadow({ mode: "open" });
    Object.assign(this, { _hass: null, _loaded: false, _narrow: false, renderCount: 0, entities: [], bridges: [], bridge: null,
      overview: {}, diagnostics: { findings: [], summary: {} }, historyEntries: [], rulesPreview: null,
      performance: null, devicePreview: null, yamlStatus: {}, modeStatus: {}, activationStatus: { state: "unknown" }, managementStatus: { state: "unknown" }, migrationPlan: null, migrationStatus: { state: "unknown", stale: true },
      view: "home", settingsView: "configuration", groupMode: "areas", selectionMode: false, expanded: new Set(), query: "", page: 0,
      filters: { status: "", compatibility: "", domain: "", integration: "", area: "", availability: "", published: "", changed: "" },
      selected: new Set(), draft: new Map(), fingerprint: null, serverPreview: null, error: null, loading: false, statusMessage: "Keine Änderungen", expandedBridges: new Set(), activationMessage: "", actionMenuOpen: false, diagnosticFilter: "", filtersOpen: false });
    this.operationPlan = null; this.operationStatus = null;
    Object.assign(this, { action: "", statusTone: "neutral", expandedAreas: new Set(), areaPages: new Map(), draftFingerprint: null, conflict: false, dialog: null, lastFetchAt: null, _subscription: null, _pendingRevision: 0, _seenRevision: 0, _refreshQueued: false, _passiveRenderPending: false, _passiveRenderControl: null });
    this.filters.device = "";
    this.render();
  }
  connectedCallback() { if (!this.shadowRoot.innerHTML) this.render(); this.subscribeUpdates(); }
  disconnectedCallback() { this._subscription?.(); this._subscription = null; }
  async subscribeUpdates() {
    const connection = this._hass?.connection;
    if (!connection?.subscribeEvents || this._subscription || this._subscribing) return;
    this._subscribing = true;
    try { this._subscription = await connection.subscribeEvents(event => this.onInventoryUpdated(event), "homekit_manager_updated"); }
    catch (error) { this.error = `Live-Aktualisierung nicht bestätigt: ${error.message || error}`; this.render(); }
    finally { this._subscribing = false; }
  }
  set hass(value) { this._hass = value; this.subscribeUpdates(); if (!this._loaded) { this._loaded = true; this.refresh(); } else this.updateConnectionState(); }
  get hass() { return this._hass; } set panel(value) { this._panel = value; } get panel() { return this._panel; }
  onInventoryUpdated(event) {
    const revision = Number(event?.data?.revision ?? event?.revision);
    if (Number.isFinite(revision)) this._pendingRevision = Math.max(this._pendingRevision, revision);
    else this._refreshQueued = true;
    if (!this.loading) this.refresh(false);
  }
  set narrow(value) { const next = Boolean(value); if (next !== this._narrow) { this._narrow = next; this.render(true); } } get narrow() { return this._narrow; }
  async refresh(force = true) {
    if (!this._hass) return false;
    if (this.loading) { this._refreshQueued = true; return false; }
    let succeeded = false;
    this.loading = true; this.error = null; if (force) this.render();
    try {
      const inventory = await this._hass.callWS({ type: WS.inventory, refresh: force, include_context: true, offset: 0, limit: INVENTORY_BATCH_SIZE });
      const entities = [...(inventory.entities || [])];
      const total = Number.isInteger(inventory.total) ? inventory.total : entities.length;
      if (total < entities.length) throw new Error("Inventar-Seitenzahl ist ungültig.");
      for (let offset = entities.length; offset < total; offset = entities.length) {
        const page = await this._hass.callWS({ type: WS.inventory, offset, limit: INVENTORY_BATCH_SIZE });
        if (page.fingerprint !== inventory.fingerprint || page.snapshot_revision !== inventory.snapshot_revision || page.total !== total || page.offset !== offset || !page.entities?.length) {
          throw new Error("Inventar hat sich während des Seitenabrufs geändert. Bitte erneut aktualisieren.");
        }
        entities.push(...page.entities);
      }
      const [bridges, diagnostics, history, yaml, mode, activation, migrationPlan, migrationStatus, managementStatus] = inventory.context || await Promise.all(
        [WS.bridges, WS.diagnostics, WS.history, WS.yaml, WS.mode, WS.activation, WS.migrationPlan, WS.migrationStatus, WS.managementStatus].map(type => this._hass.callWS({ type }))
      );
      if (this.draft.size && this.draftFingerprint && this.draftFingerprint !== inventory.overview?.fingerprint) this.conflict = true;
      if (this.operationPlan && this.operationPlan.inventory_fingerprint !== inventory.overview?.fingerprint) this.conflict = true;
      Object.assign(this, { entities, overview: inventory.overview || {}, bridges: bridges.bridges || [], diagnostics, historyEntries: history.entries || [], yamlStatus: yaml, modeStatus: mode, activationStatus: activation || { state: "unknown" }, migrationPlan, migrationStatus, managementStatus });
      this._seenRevision = Math.max(this._seenRevision, Number(this.overview.refresh_count) || 0);
      this.fingerprint = yaml.fingerprint || this.overview.fingerprint || null;
      this.bridge = this.bridges.find(item => item.entry_id === this.overview.selected_bridge_id) || (this.bridges.length === 1 ? this.bridges[0] : null);
      this.lastFetchAt = new Date().toISOString();
      succeeded = true;
      return true;
    } catch (error) { this.error = error?.message || String(error); return false; }
    finally {
      this.loading = false; this.render(!force);
      const retry = this._refreshQueued || this._pendingRevision > this._seenRevision;
      this._refreshQueued = false;
      if (retry && succeeded) queueMicrotask(() => this.refresh(false));
    }
  }
  async selectBridge(entryId) {
    if (!entryId || entryId === this.bridge?.entry_id) return;
    if (this.draft.size) { this.error = "Bitte den Entwurf zuerst speichern oder verwerfen, bevor du die Bridge wechselst."; this.render(); return; }
    try { await this._hass.callWS({ type: WS.selectBridge, entry_id: entryId }); this.serverPreview = null; this.operationPlan = null; this.operationStatus = null; await this.refresh(); } catch (error) { this.error = error?.message || String(error); this.render(); }
  }
  async loadSettingsData() {
    if (this.settingsView !== "performance") return;
    await this.runAction("Messwerte laden", async () => { this.performance = await this._hass.callWS({ type: WS.performance }); this.statusMessage = "Backend-Messwerte geladen"; });
  }
  async previewEntity(entityId) { try { this.devicePreview = await this._hass.callWS({ type: WS.devicePreview, entity_id: entityId }); this.settingsView = "preview"; this.view = "settings"; } catch (error) { this.error = error?.message || String(error); } this.render(); }
  async restoreHistory(index) {
    if (this.draft.size && !await this.requestConfirmation("Historie als Entwurf laden", "Der aktuelle Entwurf wird ersetzt. HomeKit bleibt unverändert.", "Entwurf laden")) return;
    try { const result = await this._hass.callWS({ type: WS.historyRestore, index }); const bridgeId = result.bridge_id || (result.document?.bridges ? Object.keys(result.document.bridges)[0] : null);
      if (bridgeId && bridgeId === this.bridge?.entry_id) { const entities = result.document.bridges[bridgeId].entities || {}; this.draft = new Map(Object.entries(entities).map(([id, value]) => [id, value === "include" ? "included" : "excluded"])); this.draftFingerprint = this.fingerprint; this.conflict = false; this.serverPreview = null; this.statusMessage = "Historie als Entwurf wiederhergestellt"; this.view = "changes"; }
      else this.error = "Der Historieneintrag gehört zu einer anderen oder nicht mehr vorhandenen Bridge.";
    } catch (error) { this.error = error?.message || String(error); } this.render();
  }
  updateConnectionState() { const node = this.shadowRoot.querySelector("[data-connection]"); if (node) node.textContent = this._hass ? "Verbunden" : "Nicht verbunden"; }
  escape(value) { return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]); }
  currentStatus(entity) { const value = entity?.homekit?.current_status ?? entity?.homekit?.configured_by_filter; return value === true || value === "included" ? "included" : value === false || value === "excluded" ? "excluded" : "unknown"; }
  plannedStatus(entity) { return this.draft.has(entity.entity_id) ? this.draft.get(entity.entity_id) : this.currentStatus(entity); }
  status(entity) { return this.draft.has(entity.entity_id) && this.draft.get(entity.entity_id) !== this.currentStatus(entity) ? "planned" : this.currentStatus(entity); }
  statusLabel(value) { return ({ included: "Eingeschlossen", include: "Eingeschlossen", excluded: "Ausgeschlossen", exclude: "Ausgeschlossen", unknown: "Unbekannt", no_state: "Ohne aktuellen State", disabled: "Deaktiviert", planned: "Vorgemerkt", mixed: "Gemischt", empty: "Keine Entitäten", supported: "Unterstützt", conditionally_supported: "Bedingt unterstützt", unsupported: "Nicht unterstützt", available: "Verfügbar", unavailable: "Nicht verfügbar", yes: "Ja", no: "Nein" })[value] || value; }
  changes() { const byId = new Map(this.entities.map(item => [item.entity_id, item])); return [...this.draft].map(([entity_id, desired]) => { const entity = byId.get(entity_id); return { entity_id, desired, current: entity ? this.currentStatus(entity) : "unknown", name: entity?.name || entity_id }; }).filter((item) => item.desired !== item.current); }
  desiredDocument() { const entry = this.bridge?.entry_id; const entities = Object.fromEntries([...this.draft].map(([id, value]) => [id, value === "included" ? "include" : value === "excluded" ? "exclude" : value])); return { schema_version: 1, bridges: entry ? { [entry]: { policy: "explicit_overrides", entities } } : {} }; }
  selectView(view) { this.view = view; if (view === "settings") this.settingsView = "general"; this.render(); }
  setSettingsView(view) { this.settingsView = view; this.view = "settings"; this.render(); this.loadSettingsData(); }
  setFilter(key, value) { this.filters[key] = value; this.page = 0; this.filtersOpen = true; this.render(); }
  setDraft(id, value, render = true) {
    const entity = this.entities.find(item => item.entity_id === id);
    if (!entity || this.currentStatus(entity) === "unknown" || (value === "included" && value !== this.currentStatus(entity) && entity.compatibility?.status === "unsupported")) return;
    if (!this.draft.size) this.draftFingerprint = this.fingerprint;
    const current = this.currentStatus(entity);
    if (!value || value === current) this.draft.delete(id); else this.draft.set(id, value);
    this.serverPreview = null;
    this.operationPlan = null; this.operationStatus = null;
    this.statusMessage = `${this.changes().length} Änderung(en) als Entwurf vorgemerkt`;
    this.statusTone = "neutral";
    if (render) this.render();
  }
  async runScopeAction(kind, key, value) {
    const hierarchy = this.hierarchy();
    const scope = kind === "area" ? hierarchy.areas.find(item => item.key === key) : hierarchy.devices.find(item => item.id === key);
    if (!scope || !["included", "excluded"].includes(value)) return;
    const deviceCount = new Set(scope.members.map(item => item.device_id).filter(Boolean)).size;
    await this.planSelection(scope.members.map(item => item.entity_id), value, { label: scope.name, deviceCount });
  }
  async planSelection(ids, value, scope = null) {
    const byId = new Map(this.entities.map(item => [item.entity_id, item]));
    const members = ids.map(id => byId.get(id)).filter(Boolean);
    const eligible = members.filter(item => this.currentStatus(item) !== "unknown" && !(value === "included" && value !== this.currentStatus(item) && item.compatibility?.status === "unsupported"));
    const newlyChanged = eligible.filter(item => this.plannedStatus(item) !== value).length;
    const alreadyCorrect = eligible.length - newlyChanged;
    const deviceCount = scope?.deviceCount ?? new Set(members.map(item => item.device_id).filter(Boolean)).size;
    const message = `${scope?.label || this.bridge?.title || "Auswahl"}: ${this.statusLabel(value)}. Geräte: ${deviceCount}; Entitäten: ${members.length}; neu zu ändern: ${newlyChanged}; bereits so eingestellt: ${alreadyCorrect}; nicht bearbeitbar: ${members.length - eligible.length}. Es entsteht nur ein Entwurf; die aktive HomeKit-Konfiguration bleibt unverändert.`;
    if (!await this.requestConfirmation("Mehrfachänderung vormerken", message, "Nur im Entwurf vormerken")) return;
    if (!this.draft.size && eligible.length) this.draftFingerprint = this.fingerprint;
    eligible.forEach(item => { if (value === this.currentStatus(item)) this.draft.delete(item.entity_id); else this.draft.set(item.entity_id, value); });
    this.serverPreview = null; this.operationPlan = null; this.operationStatus = null;
    this.statusMessage = `${this.changes().length} Änderung(en) als Entwurf vorgemerkt`;
    this.selected.clear(); this.render();
  }
  async applyToSelection(value) { await this.planSelection([...this.selected], value); }
  discard() { this.draft.clear(); this.selected.clear(); this.draftFingerprint = null; this.conflict = false; this.serverPreview = null; this.operationPlan = null; this.operationStatus = null; this.statusMessage = "Entwurf verworfen"; this.statusTone = "neutral"; this.render(); }
  async validateDraft() { try { return await this._hass.callWS({ type: WS.validate, document: this.desiredDocument() }); } catch (error) { this.error = error?.message || String(error); this.render(); return null; } }
  async previewServer() {
    await this.runAction("Vorschau erstellen", async () => {
      const result = await this._hass.callWS({ type: WS.validate, document: this.desiredDocument() });
      this.serverPreview = await this._hass.callWS({ type: WS.preview, document: result.document });
      this.conflict = Boolean(this.serverPreview.summary?.blocked);
      this.draftFingerprint = this.serverPreview.fingerprint || this.fingerprint;
      this.statusMessage = this.conflict ? "Vorschau enthält blockierte Änderungen" : "Entwurf validiert · Vorschau bestätigt";
      if (this.conflict) this.statusTone = "warning";
    });
  }
  async saveDraft() {
    if (this.conflict) { this.error = "Der Systemstand hat sich geändert. Bitte die Vorschau erneut prüfen."; this.render(); return; }
    await this.runAction("Entwurf speichern", async () => {
      const document = this.desiredDocument();
      const validated = await this._hass.callWS({ type: WS.validate, document });
      const saved = await this._hass.callWS({ type: WS.save, document: validated.document, ...(this.yamlStatus.file_version ? { expected_file_version: this.yamlStatus.file_version } : {}), expected_fingerprint: this.draftFingerprint || this.fingerprint });
      if (!saved.valid || !saved.exists) throw new Error("Die Speicherung wurde nicht bestätigt.");
      this.yamlStatus = saved; this.fingerprint = saved.fingerprint || this.fingerprint; this.draftFingerprint = this.fingerprint;
      this.operationPlan = null; this.operationStatus = null;
      this.historyEntries = (await this._hass.callWS({ type: WS.history })).entries || [];
      this.statusMessage = saved.history_error || "Entwurf gespeichert · HomeKit unverändert";
      if (saved.history_error) this.statusTone = "warning";
    });
  }
  async planOperation() {
    if (!this.bridge?.entry_id || !this.fingerprint || this.conflict) { this.error = "Bridge-Kontext oder Inventarstand ist nicht eindeutig."; this.render(); return; }
    await this.runAction("Änderung planen", async () => {
      const result = await this._hass.callWS({ type: WS.operationPlan, document: this.desiredDocument(), entry_id: this.bridge.entry_id, expected_fingerprint: this.fingerprint });
      this.operationPlan = { ...result, inventory_fingerprint: this.fingerprint };
      this.operationStatus = result;
      this.overview.operation_policy = result.operation_policy || this.overview.operation_policy;
      this.statusMessage = "Änderungsplan validiert · Quelle und Revision gebunden";
    });
  }
  supportsApply() { return Boolean(this.overview.operation_policy?.enabled && this.operationPlan?.apply_enabled && this.operationPlan?.state === "validated" && this.operationPlan?.entry_id === this.bridge?.entry_id && this.operationPlan?.inventory_fingerprint === this.fingerprint && !this.conflict); }
  async reconcileOperation() {
    if (!this.operationPlan?.operation_id) return;
    await this.runAction("Vorgang lesend abgleichen", async () => {
      this.operationStatus = await this._hass.callWS({ type: WS.operationReconcile, operation_id: this.operationPlan.operation_id });
      this.statusMessage = `Vorgangsstatus: ${this.operationStatus.state || "unbekannt"}`;
    });
  }
  async applyDraft() {
    if (!this.supportsApply()) { this.statusMessage = this.overview.operation_policy?.reason || "HomeKit-Anwendung ist serverseitig gesperrt."; this.statusTone = "neutral"; this.render(); return; }
    const plan = this.operationPlan;
    const exactDiff = this.changes().map(item => `${item.entity_id}: ${this.statusLabel(item.current)} → ${this.statusLabel(item.desired)}`).join("; ");
    if (!await this.requestConfirmation("HomeKit-Änderung anwenden", `Operation ${plan.operation_id} für ${this.bridge?.title || plan.entry_id} (${plan.entry_id}, Quelle ${plan.source}). Konkreter Diff: ${exactDiff}.`, "Genau diese Änderung anwenden")) return;
    await this.runAction("HomeKit-Änderung anwenden", async () => {
      try {
        const result = await this._hass.callWS({ type: WS.operationApply, operation_id: plan.operation_id, entry_id: plan.entry_id, source_revision: plan.source_revision, expected_fingerprint: plan.inventory_fingerprint, confirmed_operation_id: plan.operation_id });
        this.operationStatus = result;
        if (result.state !== "verified") throw new Error("Die Nachverifikation wurde nicht bestätigt.");
        this.operationPlan = null; this.draft.clear(); this.draftFingerprint = null;
        await this.refresh(false);
        this.statusMessage = "HomeKit-Konfigurationswerte vom Backend verifiziert; Apple Home nicht bestätigt";
      } catch (error) {
        try { this.operationStatus = await this._hass.callWS({ type: WS.operationStatus, operation_id: plan.operation_id }); }
        catch { this.operationStatus = { state: "unknown_outcome", automatic_retry: false }; }
        this.operationPlan = null;
        throw error;
      }
    });
  }
  async exportDraft() {
    await this.runAction("Export erstellen", async () => {
      const result = await this._hass.callWS({ type: WS.export, document: this.desiredDocument(), format: "yaml" });
      if (typeof result.content !== "string") throw new Error("Der Export enthält keine Datei.");
      const url = URL.createObjectURL(new Blob([result.content], { type: "application/yaml" }));
      const link = document.createElement("a"); link.href = url; link.download = "homekit-manager-entwurf.yaml"; link.click();
      URL.revokeObjectURL(url); this.statusMessage = "YAML-Datei zum Download bereitgestellt";
    });
  }
  async loadSaved() {
    if (this.draft.size && !await this.requestConfirmation("Gespeicherten Entwurf laden", "Die aktuelle Auswahl wird durch den gespeicherten Entwurf ersetzt.", "Entwurf laden")) return;
    await this.runAction("Entwurf laden", async () => {
      if (!await this.refresh(false)) throw new Error(this.error || "Entwurf konnte nicht gelesen werden");
      if (!this.yamlStatus.valid) throw new Error(this.yamlStatus.error || "Gespeicherter Entwurf ungültig");
      const saved = this.yamlStatus.document?.bridges?.[this.bridge?.entry_id]?.entities || {};
      this.draft = new Map(Object.entries(saved).map(([id, value]) => [id, value === "include" ? "included" : "excluded"]));
      this.draftFingerprint = this.fingerprint; this.conflict = false; this.serverPreview = null;
      this.statusMessage = this.draft.size ? "Gespeicherten Entwurf geladen" : "Für diese Bridge ist kein Entwurf gespeichert";
    });
  }
  async runAction(label, callback) {
    if (this.action) return;
    this.action = label; this.error = null; this.statusTone = "success"; this.render();
    try { await callback(); }
    catch (error) { this.error = error?.message || String(error); this.statusTone = "error"; }
    finally { this.action = ""; this.render(); }
  }
  requestConfirmation(title, message, label) {
    return new Promise(resolve => { this._dialogResolve = resolve; this.dialog = { title, message, label }; this.render(); });
  }
  finishConfirmation(confirmed) { const resolve = this._dialogResolve; this._dialogResolve = null; this.dialog = null; this.render(); resolve?.(confirmed); }
  formatTime(value) { if (!value) return "Noch nicht bestätigt"; const date = new Date(value); return Number.isNaN(date.getTime()) ? "Unbekannt" : date.toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" }); }
  counts(members) { return { entities: members.length, devices: new Set(members.map(item => item.device_id).filter(Boolean)).size, included: members.filter(item => this.currentStatus(item) === "included").length, compatible: members.filter(item => item.compatibility?.status === "supported").length, unavailable: members.filter(item => !item.available).length, unassigned: members.filter(item => !item.device_id).length }; }
  matches(entity) {
    const query = this.query.trim().toLocaleLowerCase("de");
    if (query && ![entity.name, entity.entity_id, entity.device_name, entity.area_name].filter(Boolean).join(" ").toLocaleLowerCase("de").includes(query)) return false;
    return Object.entries(this.filters).every(([key, wanted]) => {
      if (!wanted) return true;
      if (key === "status") return wanted === "planned" ? this.status(entity) === "planned" : this.currentStatus(entity) === wanted;
      if (key === "changed") return (this.status(entity) === "planned") === (wanted === "yes");
      if (key === "availability") return (entity.availability_status || (entity.available ? "available" : "unavailable")) === wanted;
      if (key === "published") return (entity.homekit?.published || "unknown") === wanted;
      if (key === "compatibility") return entity.compatibility?.status === wanted;
      if (key === "area") return (entity.area_name || "Ohne Bereich") === wanted;
      if (key === "device") return (entity.device_name || "Ohne Gerät") === wanted;
      if (key === "integration") return (entity.integration_domain || "") === wanted;
      return entity[key] === wanted;
    });
  }
  get filtered() { return this.entities.filter((entity) => this.matches(entity)).sort((a, b) => String(a.name || a.entity_id).localeCompare(String(b.name || b.entity_id), "de", { numeric: true })); }
  chip(label, value, tone = "") { return `<span class="chip ${tone}">${this.escape(label)}: ${this.escape(value)}</span>`; }
  badge(value) { return `<span class="state state-${value}">${this.statusLabel(value)}</span>`; }
  filterOptions(key, values, label) { return `<label>${this.escape(label)}<select data-filter="${key}"><option value="">Alle</option>${[...new Set(values)].filter(Boolean).sort().map(value => `<option value="${this.escape(value)}"${this.filters[key] === value ? " selected" : ""}>${this.escape(this.statusLabel(value))}</option>`).join("")}</select></label>`; }
  entityRow(entity) {
    const current = this.currentStatus(entity), desired = this.plannedStatus(entity), label = entity.name || entity.entity_id;
    const next = desired === "included" ? "excluded" : "included";
    const blocked = current === "unknown" || (next === "included" && next !== current && entity.compatibility?.status === "unsupported");
    return `<article class="entity-row"><div class="entity-copy"><strong>${this.escape(label)}</strong><code>${this.escape(entity.entity_id)}</code><small>${this.escape(entity.device_name || "Ohne Gerät")} · ${this.escape(entity.area_name || "Ohne Bereich")} · ${this.escape(entity.domain || entity.entity_id.split(".")[0])}</small><div class="entity-meta"><span>${this.escape(this.statusLabel(entity.compatibility?.status || "unknown"))}</span><span class="${entity.available ? "" : "text-warning"}">${this.statusLabel(entity.availability_status || (entity.available ? "available" : "unavailable"))}</span>${entity.homekit?.configured_by_filter === true && entity.homekit?.registry_eligible === false ? `<span class="text-warning">Core-Registry-Sperre</span>` : ""}</div></div><div class="entity-actions">${this.selectionMode ? `<input type="checkbox" data-select="${this.escape(entity.entity_id)}" aria-label="${this.escape(label)} auswählen"${this.selected.has(entity.entity_id) ? " checked" : ""}>` : ""}${desired !== current ? `<span class="muted">Aktuell</span>${this.badge(current)}<span class="muted">Entwurf</span>${this.badge(desired)}` : this.badge(current)}<button class="toggle ${desired === "included" ? "on" : ""}" role="switch" aria-checked="${desired === "included"}" aria-label="${this.escape(label)} im Entwurf einschließen" data-entity-toggle="${this.escape(entity.entity_id)}"${blocked ? " disabled" : ""}><span></span></button></div><details class="technical" data-detail-key="entity:${this.escape(entity.entity_id)}"><summary>Technische Details</summary><p>${this.escape(entity.compatibility?.reason || "Core-Abbildung vorhanden; Veröffentlichung in Apple Home nicht nachgewiesen.")}</p><dl class="definition-list"><div><dt>Entity-Registry</dt><dd>${entity.registry_entry_present === false ? "Kein Eintrag" : "Eintrag vorhanden"}</dd></div><div><dt>Aktueller State</dt><dd>${entity.state_present === false ? "Kein State" : this.escape(entity.state || "Unbekannt")}</dd></div><div><dt>Gerätereferenz</dt><dd>${this.escape(entity.device_registry_status || "Unbekannt")}</dd></div><div><dt>Bereichsquelle</dt><dd>${this.escape(entity.area_source || "Unbekannt")}</dd></div><div><dt>Deaktiviert durch</dt><dd>${this.escape(entity.disabled_by || entity.device_disabled_by || "Nein")}</dd></div><div><dt>Versteckt durch</dt><dd>${this.escape(entity.hidden_by || "Nein")}</dd></div><div><dt>Entity-Kategorie</dt><dd>${this.escape(entity.entity_category || "Keine")}</dd></div><div><dt>Integration</dt><dd>${this.escape(entity.integration_domain || "Unbekannt")}</dd></div><div><dt>Filterregel</dt><dd>${this.escape(entity.homekit?.filter_reason || "Unbekannt")}</dd></div><div><dt>Core-Registry-Gate</dt><dd>${entity.homekit?.registry_eligible === true ? "Erlaubt" : entity.homekit?.registry_eligible === false ? "Gesperrt" : "Unbekannt"}</dd></div><div><dt>Laufzeitkandidat</dt><dd>${entity.homekit?.runtime_candidate === true ? "Ja" : entity.homekit?.runtime_candidate === false ? "Nein" : "Unbekannt"}</dd></div><div><dt>HAP-Publikation</dt><dd>${this.escape(entity.homekit?.published || "Nicht nachweisbar")}</dd></div></dl><button data-entity-preview="${this.escape(entity.entity_id)}">Service-Vorschau</button></details></article>`;
  }
  hierarchy() {
    const areaMap = new Map(), deviceMap = new Map(), seen = new Set();
    for (const entity of this.entities) {
      if (!entity.entity_id || seen.has(entity.entity_id)) continue;
      seen.add(entity.entity_id);
      const hasDevice = Boolean(entity.device_id);
      const deviceAreaKnown = Object.prototype.hasOwnProperty.call(entity, "device_area_id");
      const areaId = hasDevice && deviceAreaKnown ? entity.device_area_id : entity.area_id;
      const areaName = hasDevice && deviceAreaKnown ? entity.device_area_name : entity.area_name;
      const name = areaName || "Ohne Bereich", inferredAreaKey = areaId ? `area:${areaId}` : `name:${name}`;
      const deviceKey = hasDevice ? `device:${entity.device_id}` : `entity:${entity.entity_id}`;
      const areaKey = deviceMap.get(deviceKey)?.areaKey || inferredAreaKey;
      if (!areaMap.has(areaKey)) areaMap.set(areaKey, { key: areaKey, name, devices: [], members: [] });
      const area = areaMap.get(areaKey);
      if (!deviceMap.has(deviceKey)) {
        const device = { id: deviceKey, device_id: entity.device_id || null, name: entity.device_name || entity.name || entity.entity_id, areaKey, members: [] };
        deviceMap.set(deviceKey, device); area.devices.push(device);
      }
      deviceMap.get(deviceKey).members.push(entity); area.members.push(entity);
    }
    const compare = (a, b) => String(a.name).localeCompare(String(b.name), "de", { numeric: true }) || String(a.id || a.key).localeCompare(String(b.id || b.key));
    const areas = [...areaMap.values()].sort(compare);
    for (const area of areas) area.devices.sort(compare);
    return { areas, devices: [...deviceMap.values()].sort(compare) };
  }
  deviceGroups() { return this.hierarchy().devices; }
  aggregateState(members, planned = true) {
    if (!members.length) return "empty";
    const states = members.map(entity => planned ? this.plannedStatus(entity) : this.currentStatus(entity));
    if (states.every(state => state === "unknown")) return "empty";
    if (states.every(state => state === "included")) return "included";
    if (states.every(state => state === "excluded")) return "excluded";
    return "mixed";
  }
  aggregateBadges(members) {
    const current = this.aggregateState(members, false), planned = this.aggregateState(members);
    return current === planned ? this.badge(current) : `<span class="muted">Aktuell</span>${this.badge(current)}<span class="muted">Entwurf</span>${this.badge(planned)}`;
  }
  scopeActions(kind, key, label) {
    return `<button data-scope-kind="${kind}" data-scope-key="${this.escape(key)}" data-scope-value="included" aria-label="Alle Entitäten in ${this.escape(label)} einschließen">Alles einschließen</button><button data-scope-kind="${kind}" data-scope-key="${this.escape(key)}" data-scope-value="excluded" aria-label="Alle Entitäten in ${this.escape(label)} ausschließen">Alles ausschließen</button>`;
  }
  deviceRow(device, visibleMembers = device.members) {
    const open = this.expanded.has(device.id);
    return `<article class="device-row" data-device-id="${this.escape(device.id)}"><div class="device-head"><div class="entity-copy"><strong>${this.escape(device.name)}</strong><small>${device.members.length} Entität(en)${device.device_id ? "" : " · ohne Gerätezuordnung"}</small></div><div class="actions">${this.aggregateBadges(device.members)}${this.scopeActions("device", device.id, device.name)}${this.selectionMode ? `<button data-select-group="${this.escape(device.id)}">Gerät auswählen</button>` : ""}<button data-expand="${this.escape(device.id)}" aria-expanded="${open}" aria-label="Entitäten von ${this.escape(device.name)} ${open ? "schließen" : "öffnen"}">${open ? "Schließen" : "Entitäten"}</button></div></div>${open ? `<div class="entity-list">${visibleMembers.map(entity => this.entityRow(entity)).join("")}</div>` : ""}</article>`;
  }
  devicesTemplate() {
    const filtered = this.filtered, hierarchy = this.hierarchy();
    const visibleDevices = hierarchy.devices.filter(device => device.members.some(entity => this.matches(entity)));
    const visibleAreas = hierarchy.areas.map(area => ({ ...area, visibleDevices: area.devices.filter(device => device.members.some(entity => this.matches(entity))) })).filter(area => area.visibleDevices.length);
    const pageTotal = this.groupMode === "entities" ? filtered.length : visibleDevices.length;
    const pages = Math.max(1, Math.ceil(pageTotal / PAGE_SIZE)); this.page = Math.min(this.page, pages - 1);
    const pager = `<div class="pager"><button data-page="${this.page - 1}"${this.page === 0 ? " disabled" : ""} aria-label="Vorherige Seite">Zurück</button><span>Seite ${this.page + 1} von ${pages} · ${pageTotal} Treffer</span><button data-page="${this.page + 1}"${this.page >= pages - 1 ? " disabled" : ""} aria-label="Nächste Seite">Weiter</button></div>`;
    let body = this.groupMode === "entities" ? `<section class="surface entity-list">${filtered.slice(this.page * PAGE_SIZE, (this.page + 1) * PAGE_SIZE).map(entity => this.entityRow(entity)).join("")}</section>${pager}` : "";
    if (this.groupMode === "devices") body = visibleDevices.slice(this.page * PAGE_SIZE, (this.page + 1) * PAGE_SIZE).map(device => this.deviceRow(device, device.members.filter(entity => this.matches(entity)))).join("") + pager;
    if (this.groupMode === "areas") body = visibleAreas.map(area => {
      const counts = this.counts(area.members), open = this.expandedAreas.has(area.key), page = this.areaPages.get(area.key) || 0;
      const devices = area.visibleDevices, pageCount = Math.max(1, Math.ceil(devices.length / 40));
      const shown = devices.slice(page * 40, (page + 1) * 40);
      return `<section class="area-card" data-area-node="${this.escape(area.key)}"><button class="area-heading" data-area="${this.escape(area.name)}" data-area-key="${this.escape(area.key)}" aria-expanded="${open}"><span><strong>${this.escape(area.name)}</strong><small>${counts.devices} Geräte · ${counts.entities} Entitäten${counts.unassigned ? ` · ${counts.unassigned} ohne Gerät` : ""}</small></span><span aria-hidden="true">${open ? "−" : "+"}</span></button><div class="area-controls">${this.aggregateBadges(area.members)}${this.scopeActions("area", area.key, area.name)}${this.selectionMode ? `<button data-select-area="${this.escape(area.key)}">Bereich auswählen</button>` : ""}</div><dl class="area-metrics"><div><dt>Eingeschlossen</dt><dd>${counts.included}</dd></div><div><dt>Unterstützt</dt><dd>${counts.compatible}</dd></div><div><dt>Ohne verfügbaren Status</dt><dd class="${counts.unavailable ? "text-warning" : ""}">${counts.unavailable}</dd></div></dl>${open ? `<div class="area-content">${shown.map(device => this.deviceRow(device, device.members.filter(entity => this.matches(entity)))).join("")}${devices.length > 40 ? `<div class="pager"><button data-area-page="${this.escape(area.key)}" data-offset="${page - 1}"${page === 0 ? " disabled" : ""}>Zurück</button><span>${page + 1} / ${pageCount}</span><button data-area-page="${this.escape(area.key)}" data-offset="${page + 1}"${page + 1 >= pageCount ? " disabled" : ""}>Weiter</button></div>` : ""}</div>` : ""}</section>`;
    }).join("");
    const activeFilters = Object.values(this.filters).filter(Boolean).length, values = key => this.entities.map(item => item[key]);
    return `${this.pageHeading("Geräte", "Bereiche, Geräte und Entitäten", "Sammelaktionen gelten für den vollständigen Bereich oder das vollständige Gerät, auch bei aktiver Suche.")}<div class="toolbar"><div class="segmented">${[["areas", "Bereiche"], ["devices", "Geräte"], ["entities", "Entitäten"]].map(([id, label]) => `<button data-group="${id}" aria-pressed="${this.groupMode === id}">${label}</button>`).join("")}</div><button data-selection aria-pressed="${this.selectionMode}">${this.selectionMode ? "Auswahl beenden" : "Mehrfachauswahl"}</button></div><label class="search"><span class="sr-only">Namen, Entity-IDs, Geräte oder Bereiche suchen</span><input type="search" data-query aria-label="Entitäten suchen" placeholder="Name, Entity-ID, Gerät oder Bereich" value="${this.escape(this.query)}"></label><details class="filters surface"${this.filtersOpen ? " open" : ""}><summary>Filter${activeFilters ? ` · ${activeFilters} aktiv` : ""}</summary><div class="filter-grid">${this.filterOptions("domain", values("domain"), "Domain")}${this.filterOptions("area", values("area_name").map(value => value || "Ohne Bereich"), "Bereich")}${this.filterOptions("device", values("device_name").map(value => value || "Ohne Gerät"), "Gerät")}${this.filterOptions("status", ["included", "excluded", "unknown", "planned"], "HomeKit-Konfiguration")}${this.filterOptions("compatibility", ["supported", "conditionally_supported", "unsupported", "unknown"], "Kompatibilität")}${this.filterOptions("availability", ["available", "unavailable", "unknown", "no_state", "disabled"], "Verfügbarkeit")}${this.filterOptions("integration", values("integration_domain"), "Integration")}</div><button data-reset-filters>Filter zurücksetzen</button></details><p class="muted">Status: ${["available", "unavailable", "unknown", "no_state", "disabled"].map(status => `${this.statusLabel(status)} ${filtered.filter(entity => (entity.availability_status || (entity.available ? "available" : "unavailable")) === status).length}`).join(" · ")}</p><p class="muted result-count">${filtered.length} von ${this.entities.length} Entitäten · Kennzahlen beziehen sich auf die aktuellen Treffer.</p>${this.selectionMode ? `<section class="selection-bar"><strong>${this.selected.size} ausgewählt</strong><button data-include>Einschließen</button><button data-exclude>Ausschließen</button><button data-clear>Zurücksetzen</button></section>` : ""}${filtered.length ? body : `<div class="empty"><strong>Keine Treffer</strong><p>Suche oder Filter anpassen.</p></div>`}`;
  }
  groupPager(total) { const pages = Math.max(1, Math.ceil(total / PAGE_SIZE)); return `<div class="pager"><button data-page="${this.page - 1}"${this.page === 0 ? " disabled" : ""}>Zurück</button><span>${Math.min(this.page + 1, pages)} / ${pages}</span><button data-page="${this.page + 1}"${(this.page + 1) * PAGE_SIZE >= total ? " disabled" : ""}>Weiter</button></div>`; }
  pageHeading(eyebrow, title, text) { return `<section class="page-head"><p class="eyebrow">${this.escape(eyebrow)}</p><h2>${this.escape(title)}</h2><p>${this.escape(text)}</p></section>`; }
  stateTile(label, value, tone = "neutral") { return `<div class="status-tile"><small>${this.escape(label)}</small><strong class="tone-${tone}">${this.escape(value)}</strong></div>`; }
  bridgeCard(bridge) {
    const open = this.expandedBridges.has(bridge.entry_id), selected = bridge.entry_id === this.bridge?.entry_id;
    const state = bridge.state === "loaded" ? "Geladen" : bridge.state ? "Nicht geladen" : "Unbekannt";
    return `<article class="bridge-card"><div class="device-head"><div class="entity-copy"><strong>${this.escape(bridge.title || "Unbenannte Bridge")}</strong><small>${state}${selected ? " · Ausgewählte Bridge" : ""}</small></div><div class="actions">${!selected ? `<button data-bridge-card="${this.escape(bridge.entry_id)}">Auswählen</button>` : ""}<button data-bridge-expand="${this.escape(bridge.entry_id)}" aria-expanded="${open}">Details</button></div></div>${open ? `<dl class="definition-list"><div><dt>Entry-ID</dt><dd><code>${this.escape(bridge.entry_id)}</code></dd></div><div><dt>Nativer Modus</dt><dd>${this.escape(bridge.mode || "Unbekannt")}</dd></div><div><dt>Native Quelle</dt><dd><code>${this.escape(bridge.source || "unknown")}</code></dd></div><div><dt>Port</dt><dd>${this.escape(bridge.port ?? "Unbekannt")}</dd></div></dl><details class="technical" data-detail-key="bridge:${this.escape(bridge.entry_id)}"><summary>Konfigurationswerte anzeigen</summary><p>Gespeicherte Entry-Werte; sensible Felder sind ausgeblendet. YAML-Kommentare und Quelldatei gehören nicht zu diesen Werten.</p><pre class="config-values">${this.escape(JSON.stringify({ data: bridge.data || {}, options: bridge.options || {} }, null, 2))}</pre></details>` : ""}</article>`;
  }
  sourceCard() { const source = this.managementStatus.configuration_source; const label = this.overview.snapshot_stale ? "Unbekannt" : source === "home_assistant" ? "Native Home-Assistant-Konfiguration" : source === "yaml" ? "YAML-Konfiguration" : "Unbekannt"; return `<div class="source-option selected"><strong>${this.escape(label)}</strong><small>Quelle dieser Bridge · bleibt bei Änderungen erhalten</small></div>`; }
  managementCard() {
    const policy = this.overview.operation_policy || {};
    return `<p class="lock-note">${this.escape(policy.reason || "HomeKit-Schreiben ist gesperrt.")}</p><p class="muted">HomeKit Manager zeigt und plant Änderungen für die ausgewählte Bridge. Die Konfigurationsquelle bleibt erhalten.</p>`;
  }
  testWriteModeCard() {
    const mode = this.overview.test_write_mode || {};
    const bridge = this.bridge;
    const supported = Boolean(bridge?.source === "user" && bridge?.mode === "bridge" && bridge?.state === "loaded" && ["2026.10.4", "2026.11.0b0"].includes(this.overview.core_version) && !this.overview.snapshot_stale);
    const activeHere = mode.enabled && mode.entry_id === bridge?.entry_id;
    const detail = mode.enabled ? `Aktiv für Entry ${mode.entry_id} bis ${this.formatTime(mode.expires_at)}. Nach Core-Neustart deaktiviert.` : "Deaktiviert. Nach bewusster Admin-Aktivierung 60 Minuten nur für eine native Bridge und Filteränderungen gültig.";
    return `<section class="notice${mode.enabled ? " warning" : ""}" aria-label="Produktiver Filter-Testmodus"><strong>Produktiver Filter-Testmodus</strong><p>${this.escape(detail)}</p><p>Keine separate Grant-Datei erforderlich. Vor jedem Apply sind ein aktueller Plan, der konkrete Diff und eine eigene Bestätigung nötig. Pairing-Erhalt in Apple Home wird dadurch nicht garantiert.</p>${mode.enabled ? `<button data-test-mode-disable>Testmodus sofort widerrufen</button>` : `<button data-test-mode-enable${supported ? "" : " disabled"}>Testmodus für diese Bridge aktivieren</button>`}${!supported && !mode.enabled ? `<p>Nur eine geladene native Bridge mit Core 2026.10.4 oder 2026.11.0b0 ist für Filteränderungen freigegeben.</p>` : ""}</section>`;
  }
  async enableTestWriteMode() {
    const bridge = this.bridge;
    if (!bridge || !this.fingerprint) return;
    if (!await this.requestConfirmation("Produktiven Filter-Testmodus aktivieren", `Bridge ${bridge.title || bridge.entry_id}, Entry-ID ${bridge.entry_id}, Quelle user. 60 Minuten lang können Admins validierte Filteränderungen nach eigener Apply-Bestätigung ausführen. Die Freigabe endet bei Widerruf, Ablauf oder Core-Neustart.`, "Testmodus für diese Bridge aktivieren")) return;
    await this.runAction("Testmodus aktivieren", async () => {
      await this._hass.callWS({ type: WS.testModeEnable, entry_id: bridge.entry_id, expected_fingerprint: this.fingerprint, confirmed_entry_id: bridge.entry_id });
      this.operationPlan = null;
      await this.refresh(false);
      this.statusMessage = "Testmodus befristet aktiviert · neuen Änderungsplan validieren";
    });
  }
  async disableTestWriteMode() {
    await this.runAction("Testmodus widerrufen", async () => {
      await this._hass.callWS({ type: WS.testModeDisable });
      this.operationPlan = null;
      await this.refresh(false);
      this.statusMessage = "Testmodus widerrufen";
    });
  }
  homeTemplate() {
    const bridge = this.bridge, stale = this.overview.snapshot_stale || !this.lastFetchAt;
    const available = !stale && bridge?.state === "loaded";
    const source = stale ? "Unbekannt" : this.managementStatus.configuration_source_label || "Unbekannt";
    const writeStatus = this.overview.test_write_mode?.enabled && this.overview.test_write_mode.entry_id === bridge?.entry_id ? "Testmodus aktiv" : this.overview.operation_policy?.enabled ? "Befristet freigegeben" : "Gesperrt";
    return `${this.pageHeading("HomeKit", "Deine Bridge im Überblick", "Bridge, Konfigurationsquelle und offene Entwürfe auf einen Blick.")}<section class="status-grid" aria-label="Systemübersicht">${this.stateTile("Bridge", available ? "Geladen" : stale || !bridge ? "Unbekannt" : "Nicht geladen", available ? "success" : "neutral")}${this.stateTile("Konfigurationsquelle", source)}${this.stateTile("Schreiben", writeStatus)}${this.stateTile("Offene Änderungen", this.changes().length, this.changes().length ? "warning" : "neutral")}</section><section class="surface"><div class="section-heading"><h3>HomeKit-Bridges</h3><span class="muted">${this.bridges.length} erkannt</span></div>${this.bridges.map(item => this.bridgeCard(item)).join("") || `<div class="empty">Keine Bridge bestätigt. Accessory-Instanzen werden separat erkannt und nicht als Bridge behandelt.</div>`}${this.overview.accessories ? `<p class="muted">${this.overview.accessories} separate Accessory-Instanz(en) · keine Bridge-Ziele</p>` : ""}</section><section class="surface"><h3>Konfigurationsquelle und Schreibstatus</h3><p class="muted">Die Bridge behält ihre bestehende Konfigurationsquelle. Entwürfe ändern diese Quelle nicht.</p><div class="source-options">${this.sourceCard()}</div>${this.managementCard()}</section><section class="surface"><div class="section-heading"><h3>Entitäten und Entwürfe</h3><button data-nav="devices">Geräte öffnen</button></div><dl class="definition-list"><div><dt>Entitäten im Inventar</dt><dd>${this.overview.total_entities ?? this.entities.length}</dd></div><div><dt>Durch Bridge-Filter eingeschlossen</dt><dd>${this.overview.configured_entities ?? "Unbekannt"}</dd></div><div><dt>Ohne verfügbaren Status</dt><dd>${this.overview.unavailable_entities ?? "Unbekannt"}</dd></div></dl><p class="muted">Geräte-IDs aus Entitäten: ${this.overview.device_reconciliation?.referenced_device_count ?? "Unbekannt"} · davon in der nativen Registry gelistet: ${this.overview.device_reconciliation?.registered_referenced_device_count ?? "Unbekannt"}. Synthetische Composite-IDs: ${this.overview.device_reconciliation?.composite_reference_ids?.length ?? "Unbekannt"}; fehlende Referenzen: ${this.overview.device_reconciliation?.missing_reference_ids?.length ?? "Unbekannt"}.</p><p class="muted">Ein Filtertreffer ist kein Nachweis der Veröffentlichung in Apple Home.</p>${this.changes().length ? `<button class="primary" data-nav="changes">${this.changes().length} Änderung(en) prüfen</button>` : `<p class="muted">Keine offenen Änderungen.</p>`}</section>`;
  }
  changesTemplate() {
    const changes = this.changes(), state = this.activationStatus.state || "unknown";
    const labels = { validated: "Entwurf validiert", prepared: "Änderung vorbereitet", activating: "Anwendung läuft", saved: "Optionen gespeichert, Aktivierung unbestätigt", active: "Anwendung bestätigt", failed: "Anwendung fehlgeschlagen", unknown: "Ergebnis unbekannt" };
    const stateLabel = state === "unknown" && !this.activationStatus.has_operation
      ? "Keine Anwendung protokolliert" : labels[state] || "Unbekannt";
    const tone = state === "active" && this.activationStatus.has_operation ? "success" : state === "failed" ? "error" : "neutral";
    const previewById = new Map((this.serverPreview?.changes || []).map(item => [item.entity_id, item]));
    return `${this.pageHeading("Änderungen", "Dein geplanter Zustand", "Vorschau und Entwurfsspeicherung verändern keine produktive HomeKit-Konfiguration.")}<section class="surface activation-card"><div class="section-heading"><h3>Anwendungsstatus</h3><span class="state tone-${tone}" data-activation-state="${this.escape(state)}">${this.escape(stateLabel)}</span></div><p>${this.escape(this.activationStatus.message || (this.activationStatus.has_operation ? "Gespeicherter Vorgangsstatus" : "Es liegt kein persistenter Nachweis einer früheren Anwendung vor."))}</p><p class="muted">Eine geladene Bridge allein bestätigt keine frühere Anwendung. Unbekannte Vorgänge werden nicht automatisch wiederholt.</p><button data-refresh>Status lesend prüfen</button><details class="technical"><summary>Vorgangsdaten</summary><dl class="definition-list"><div><dt>Request-ID</dt><dd><code>${this.escape(this.activationStatus.request_id || "Nicht vorhanden")}</code></dd></div><div><dt>Letzte Meldung</dt><dd>${this.formatTime(this.activationStatus.updated_at)}</dd></div><div><dt>Aktueller Bridge-Zustand</dt><dd>${this.escape(this.activationStatus.observations?.bridge_state || "Unbekannt")}</dd></div></dl></details></section>${this.conflict ? `<aside class="notice warning" role="alert">Der aktuelle Zustand oder die Vorschau enthält einen Konflikt. Bitte die Vorschau erneut prüfen.</aside>` : ""}<section class="surface changes-surface"><div class="section-heading"><h3>Geplante Änderungen</h3><span class="muted">${changes.length}</span></div>${changes.length ? changes.map(item => { const planned = previewById.get(item.entity_id); return `<article class="change-row"><div class="entity-copy"><strong>${this.escape(item.name)}</strong><code>${this.escape(item.entity_id)}</code><small>Bridge: ${this.escape(this.bridge?.title || "Nicht ausgewählt")}</small></div><dl class="change-states"><div><dt>Bisher</dt><dd>${this.statusLabel(item.current)}</dd></div><div><dt>Geplant</dt><dd>${this.statusLabel(item.desired)}</dd></div></dl>${planned?.blocked || planned?.risk === "high" ? `<p class="text-warning">${this.escape(planned.reason || "Zusätzliche Prüfung erforderlich")}</p>` : ""}</article>`; }).join("") : `<div class="empty"><strong>Keine Änderungen vorgemerkt</strong><p>Wähle unter Geräte die gewünschten Entitäten aus.</p><button data-nav="devices">Geräte öffnen</button></div>`}</section><section class="surface operation-card"><div class="section-heading"><h3>Validierter Änderungsplan</h3><span class="state">${this.escape(this.operationStatus?.state || "Noch nicht geplant")}</span></div><p class="muted">Der Plan bindet Bridge, Quelle und Revision. Sicherung und Nachverifikation erfolgen erst beim erlaubten Apply; Apple Home bleibt ungeprüft.</p>${this.operationPlan ? `<dl class="definition-list"><div><dt>Operation-ID</dt><dd><code>${this.escape(this.operationPlan.operation_id)}</code></dd></div><div><dt>Quelle</dt><dd>${this.escape(this.operationPlan.source)}</dd></div><div><dt>Betroffene Entitäten</dt><dd>${this.operationPlan.changed_entities?.length || 0}</dd></div></dl>` : ""}<button data-operation-plan${changes.length && !this.conflict ? "" : " disabled"}>Plan validieren</button>${this.operationPlan?.operation_id ? `<button data-operation-reconcile>Vorgang lesend abgleichen</button>` : ""}</section><section class="notice lock-note"><button data-apply${this.supportsApply() ? "" : " disabled"} title="${this.escape(this.overview.operation_policy?.reason || "HomeKit-Schreibpfad gesperrt")}">${this.supportsApply() ? "Änderung anwenden" : "Änderung anwenden · gesperrt"}</button><p>${this.escape(this.overview.operation_policy?.reason || "Der Schreibpfad ist im Backend gesperrt. Verwaltung und Vorschau heben diese Sperre nicht auf.")}</p></section><footer class="sticky-actions" aria-label="Änderungsaktionen"><span class="footer-count">${changes.length} vorgemerkt</span><button class="primary" data-save${changes.length ? "" : " disabled"}>Entwurf speichern</button><button data-preview${changes.length ? "" : " disabled"}>Vorschau</button><button data-action-menu aria-expanded="${this.actionMenuOpen}">Weitere</button>${this.actionMenuOpen ? `<div class="action-menu"><button data-export>YAML exportieren</button><button data-load>Entwurf laden</button><button data-discard${changes.length ? "" : " disabled"}>Verwerfen</button></div>` : ""}</footer>`;
  }
  settingsTemplate() {
    const tabs = [["general", "Allgemein"], ["configuration", "Konfiguration"], ["diagnostics", "Diagnose"], ["rules", "Regeln"], ["history", "Historie"], ["performance", "Performance"]];
    let body;
    if (this.settingsView === "configuration") body = `<h3>Konfigurationsquelle</h3><p class="muted">Aktive Bridge-Konfiguration und Manager-Entwürfe sind getrennte Daten.</p><div class="source-options">${this.sourceCard()}</div>${this.managementCard()}${this.testWriteModeCard()}<dl class="definition-list"><div><dt>Gespeicherter Entwurf</dt><dd>${!this.yamlStatus.valid ? "Ungültig" : this.yamlStatus.exists ? "Vorhanden" : "Nicht vorhanden"}</dd></div><div><dt>Letzte Entwurfsspeicherung</dt><dd>${this.formatTime(this.yamlStatus.last_modified)}</dd></div></dl><p class="lock-note">Änderungen bewahren die bestehende Konfigurationsquelle der Bridge.</p>`;
    else if (this.settingsView === "diagnostics") {
      const findings = this.diagnostics.grouped_findings || this.diagnostics.findings || [];
      body = `<h3>Backend und Diagnose</h3><dl class="definition-list"><div><dt>Letzter Datenabruf</dt><dd>${this.formatTime(this.lastFetchAt)}</dd></div><div><dt>Letzter vollständiger Backend-Stand</dt><dd>${this.formatTime(this.overview.last_updated)}</dd></div><div><dt>Aktualisierung</dt><dd>${this.overview.snapshot_stale ? "Letzter Abruf fehlgeschlagen" : this.lastFetchAt ? "Bestätigt" : "Nicht geprüft"}</dd></div></dl>${this.overview.last_error ? `<p class="notice error">${this.escape(this.overview.last_error)}</p>` : ""}<label>Problemtyp<select data-diagnostic-filter><option value="">Alle</option>${[...new Map(findings.map(item => [item.code, item.title])).entries()].map(([code, title]) => `<option value="${this.escape(code)}"${this.diagnosticFilter === code ? " selected" : ""}>${this.escape(title)}</option>`).join("")}</select></label>${findings.filter(item => !this.diagnosticFilter || item.code === this.diagnosticFilter).map(item => `<details class="finding"><summary><strong>${this.escape(item.title)}</strong><span>${item.count || 1} betroffen</span></summary><p>${this.escape(item.detail)}</p><p>${this.escape(item.recommendation || "Keine weitere Empfehlung")}</p><ul>${(item.entity_ids || (item.entity_id ? [item.entity_id] : [])).map(id => `<li><code>${this.escape(id)}</code></li>`).join("")}</ul></details>`).join("") || `<p class="muted">${this.lastFetchAt ? "Keine Befunde im letzten Backend-Stand." : "Diagnose noch nicht bestätigt."}</p>`}`;
    } else if (this.settingsView === "rules") {
      const filter = this.bridge?.filter;
      const labels = { include_entities: "Eingeschlossene Entitäten", exclude_entities: "Ausgeschlossene Entitäten", include_domains: "Eingeschlossene Domains", exclude_domains: "Ausgeschlossene Domains", include_entity_globs: "Einschlussmuster", exclude_entity_globs: "Ausschlussmuster" };
      body = `<h3>Native Filterregeln</h3><p class="muted">Aktuelle Regeln der ausgewählten Bridge. Diese Ansicht ändert keine Regeln.</p>${filter ? Object.entries(labels).map(([key, label]) => `<details class="rule-group"><summary>${label} · ${(filter[key] || []).length}</summary>${(filter[key] || []).length ? `<ul>${filter[key].map(value => `<li><code>${this.escape(value)}</code></li>`).join("")}</ul>` : `<p class="muted">Keine expliziten Einträge.</p>`}</details>`).join("") : `<p class="muted">Filterzustand unbekannt.</p>`}<p class="lock-note">Accessory-Modus, unterstützte Core-Funktionen und ausgeblendete Entitäten können die Zuordnung zusätzlich einschränken.</p>`;
    } else if (this.settingsView === "history") body = `<h3>Entwurfshistorie</h3><p class="muted">Eine Wiederherstellung erzeugt nur einen Entwurf.</p>${this.historyEntries.length ? this.historyEntries.map((entry, index) => `<article class="history-row"><div><strong>Gespeicherter Entwurf</strong><small>${this.formatTime(entry.timestamp)}</small><small>Bridge: ${this.escape(this.bridges.find(item => item.entry_id === entry.bridge_id)?.title || "Nicht mehr vorhanden")}</small></div><button data-history-restore="${index}">Als Entwurf laden</button></article>`).join("") : `<div class="empty">Noch keine Entwürfe gespeichert.</div>`}`;
    else if (this.settingsView === "performance") body = `<h3>Aktualisierung und Messwerte</h3><p class="muted">Backend-Messungen des letzten vollständigen Inventaraufbaus. Keine Langzeitmessung.</p><button data-performance>Messwerte aktualisieren</button><dl class="definition-list"><div><dt>Entitäten</dt><dd>${this.performance?.entity_count ?? this.entities.length}</dd></div><div><dt>Backend-Refresh</dt><dd>${(this.performance?.refresh_duration_ms ?? this.overview.refresh_duration_ms) != null ? `${this.performance?.refresh_duration_ms ?? this.overview.refresh_duration_ms} ms` : "Nicht gemessen"}</dd></div><div><dt>CPU-Zeit letzter Refresh</dt><dd>${this.performance?.refresh_cpu_ms ?? this.overview.refresh_cpu_ms ?? "Nicht gemessen"} ms</dd></div><div><dt>Verarbeitete Ereignisse</dt><dd>${this.performance?.events_seen ?? this.overview.events_seen ?? "Nicht gemessen"}</dd></div><div><dt>Ignorierte identische Zustände</dt><dd>${this.performance?.events_ignored ?? this.overview.events_ignored ?? "Nicht gemessen"}</dd></div><div><dt>Vollständige Aktualisierungen</dt><dd>${this.performance?.refresh_count ?? this.overview.refresh_count ?? "Nicht gemessen"}</dd></div><div><dt>Letzte Aktualisierung</dt><dd>${this.formatTime(this.performance?.last_updated || this.overview.last_updated)}</dd></div></dl>`;
    else if (this.settingsView === "preview") body = `<h3>Service-Vorschau</h3><p class="lock-note">Simulation der Core-Zuordnung, keine Apple-Home-Veröffentlichung.</p><dl class="definition-list"><div><dt>Entität</dt><dd>${this.escape(this.devicePreview?.title || "Unbekannt")}</dd></div><div><dt>Erwarteter Typ</dt><dd>${this.escape(this.devicePreview?.service_type || "Nicht eindeutig")}</dd></div></dl><details class="technical"><summary>Erweiterte Daten</summary><pre>${this.escape(JSON.stringify(this.devicePreview, null, 2))}</pre></details>`;
    else body = `<h3>Integration</h3><dl class="definition-list"><div><dt>Version</dt><dd>${this.escape(this.overview.integration_version || "Nicht gemeldet")}</dd></div><div><dt>Backend</dt><dd>${this.lastFetchAt && !this.overview.snapshot_stale ? "Erreichbar" : "Nicht bestätigt"}</dd></div><div><dt>Home Assistant Core</dt><dd>${this.escape(this.overview.core_version || "Nicht gemeldet")}</dd></div><div><dt>Erkannte Bridges</dt><dd>${this.bridges.length}</dd></div><div><dt>Separate Accessories</dt><dd>${this.overview.accessories ?? "Nicht gemeldet"}</dd></div></dl><details class="technical"><summary>Kennzahlen verstehen</summary><p>Geräte sind eindeutige Device-Registry-IDs. Entitäten ohne Gerät werden separat gezählt. Eine Geräte-ID kann durch Entity-Bereichszuordnungen in mehreren Bereichen vorkommen. Bereichs-Gerätezahlen dürfen deshalb nicht als globale Gerätesumme addiert werden.</p><p>Eingeschlossen, unterstützt und nicht verfügbar sind überlappende Teilmengen aller aktuellen Treffer. Ein Filtertreffer bestätigt keine Veröffentlichung in Apple Home.</p></details>`;
    return `${this.pageHeading("Einstellungen", "Verwaltung und Diagnose", "Aktuelle Systemdaten und vorhandene Funktionen.")}<nav class="settings-nav" aria-label="Einstellungsbereiche">${tabs.map(([id, label]) => `<button data-settings-view="${id}" aria-current="${this.settingsView === id ? "page" : "false"}">${label}</button>`).join("")}</nav><section class="surface settings-content">${body}</section>`;
  }
  render(passive = false) {
    const focused = this.shadowRoot.activeElement;
    if (passive && focused?.tagName === "SELECT") {
      this._passiveRenderPending = true;
      if (this._passiveRenderControl !== focused) {
        this._passiveRenderControl = focused;
        focused.addEventListener("blur", () => {
          this._passiveRenderControl = null;
          if (this._passiveRenderPending) setTimeout(() => { if (this._passiveRenderPending) this.render(); }, 0);
        }, { once: true });
      }
      return;
    }
    this._passiveRenderPending = false;
    this._passiveRenderControl = null;
    this.renderCount += 1;
    const active = this.shadowRoot.activeElement;
    const queryFocused = active?.hasAttribute?.("data-query");
    const selectFocused = active?.tagName === "SELECT" ? (active.hasAttribute("data-filter") ? `[data-filter="${active.dataset.filter}"]` : active.hasAttribute("data-diagnostic-filter") ? "[data-diagnostic-filter]" : null) : null;
    const start = queryFocused ? active.selectionStart : null, end = queryFocused ? active.selectionEnd : null;
    const openDetails = new Set([...this.shadowRoot.querySelectorAll("details[data-detail-key][open]")].map(node => node.dataset.detailKey));
    const content = this.view === "home" ? this.homeTemplate() : this.view === "devices" ? this.devicesTemplate() : this.view === "changes" ? this.changesTemplate() : this.settingsTemplate();
    this.shadowRoot.innerHTML = `<style>${this.styles()}</style><main aria-busy="${Boolean(this.loading || this.action)}"><header class="app-header"><div><h1>HomeKit Manager</h1><p>Konfiguration sicher verwalten</p></div><button class="icon-button" data-refresh aria-label="Aktualisieren"${this.loading ? " disabled" : ""}>${this.loading ? "…" : "↻"}</button></header><nav class="main-nav" role="tablist" aria-label="Hauptbereiche">${[["home", "HomeKit"], ["devices", "Geräte"], ["changes", "Änderungen"], ["settings", "Einstellungen"]].map(([id, label]) => `<button id="nav-${id}" role="tab" data-nav="${id}" aria-selected="${this.view === id}" aria-controls="main-view" tabindex="${this.view === id ? 0 : -1}">${label}</button>`).join("")}</nav><div class="feedback" aria-live="polite">${this.action ? `<p class="notice" role="status">${this.escape(this.action)} …</p>` : `<p class="status-line tone-${this.statusTone || "neutral"}" role="status">${this.escape(this.statusMessage)}</p>`}${this.error ? `<aside class="notice error" role="alert"><strong>Aktion nicht bestätigt</strong><p>${this.escape(this.error)}</p><button data-refresh>Erneut lesend prüfen</button></aside>` : ""}${this.overview.snapshot_stale ? `<aside class="notice warning" role="alert">Die angezeigten Daten stammen vom letzten vollständigen Stand. Der aktuelle Abruf ist fehlgeschlagen.</aside>` : ""}</div><section id="main-view" role="tabpanel" aria-labelledby="nav-${this.view}">${content}</section>${this.dialog ? `<dialog aria-labelledby="confirm-title"><h2 id="confirm-title">${this.escape(this.dialog.title)}</h2><p>${this.escape(this.dialog.message)}</p><div class="dialog-actions"><button data-confirm-cancel>Abbrechen</button><button class="primary" data-confirm-accept>${this.escape(this.dialog.label)}</button></div></dialog>` : ""}</main>`;
    this.bind();
    this.shadowRoot.querySelectorAll("details[data-detail-key]").forEach(node => { if (openDetails.has(node.dataset.detailKey)) node.open = true; });
    if (queryFocused) { const query = this.shadowRoot.querySelector("[data-query]"); query?.focus(); if (start != null) query?.setSelectionRange(start, end); }
    if (selectFocused) this.shadowRoot.querySelector(selectFocused)?.focus();
    if (this.action) this.shadowRoot.querySelectorAll("button:not([data-nav]), input, select").forEach(node => { node.disabled = true; });
    const dialog = this.shadowRoot.querySelector("dialog"); if (dialog && !dialog.open) dialog.showModal();
  }
  bind() {
    const all = (selector, event, callback) => this.shadowRoot.querySelectorAll(selector).forEach(node => node.addEventListener(event, callback));
    const one = (selector, event, callback) => this.shadowRoot.querySelector(selector)?.addEventListener(event, callback);
    all("[data-nav]", "click", event => this.selectView(event.currentTarget.dataset.nav));
    all(".main-nav [data-nav]", "keydown", event => { const ids = ["home", "devices", "changes", "settings"], index = ids.indexOf(this.view); const next = event.key === "ArrowRight" ? (index + 1) % 4 : event.key === "ArrowLeft" ? (index + 3) % 4 : event.key === "Home" ? 0 : event.key === "End" ? 3 : null; if (next != null) { event.preventDefault(); this.selectView(ids[next]); this.shadowRoot.querySelector(`#nav-${ids[next]}`)?.focus(); } });
    all("[data-refresh]", "click", () => this.refresh());
    all("[data-settings-view]", "click", event => this.setSettingsView(event.currentTarget.dataset.settingsView));
    one("[data-performance]", "click", () => this.loadSettingsData());
    one("[data-query]", "input", event => { this.query = event.target.value; this.page = 0; this.render(); });
    all("[data-filter]", "change", event => this.setFilter(event.target.dataset.filter, event.target.value));
    one(".filters", "toggle", event => { this.filtersOpen = event.target.open; });
    one("[data-reset-filters]", "click", () => { Object.keys(this.filters).forEach(key => { this.filters[key] = ""; }); this.page = 0; this.render(); });
    all("[data-group]", "click", event => { this.groupMode = event.currentTarget.dataset.group; this.page = 0; this.render(); });
    one("[data-selection]", "click", () => { this.selectionMode = !this.selectionMode; this.render(); });
    all("[data-select]", "change", event => { event.target.checked ? this.selected.add(event.target.dataset.select) : this.selected.delete(event.target.dataset.select); this.render(); });
    all("[data-select-area]", "click", event => { const area = this.hierarchy().areas.find(item => item.key === event.currentTarget.dataset.selectArea); area?.members.forEach(item => this.selected.add(item.entity_id)); this.render(); });
    all("[data-select-group]", "click", event => { const group = this.deviceGroups().find(item => item.id === event.currentTarget.dataset.selectGroup); group?.members.forEach(item => this.selected.add(item.entity_id)); this.render(); });
    all("[data-area]", "click", event => { const area = event.currentTarget.dataset.areaKey; this.expandedAreas.has(area) ? this.expandedAreas.delete(area) : this.expandedAreas.add(area); this.render(); });
    all("[data-area-page]", "click", event => { this.areaPages.set(event.currentTarget.dataset.areaPage, Number(event.currentTarget.dataset.offset)); this.render(); });
    all("[data-page]", "click", event => { this.page = Number(event.currentTarget.dataset.page); this.render(); });
    all("[data-expand]", "click", event => { const id = event.currentTarget.dataset.expand; this.expanded.has(id) ? this.expanded.delete(id) : this.expanded.add(id); this.render(); });
    all("[data-scope-kind]", "click", event => this.runScopeAction(event.currentTarget.dataset.scopeKind, event.currentTarget.dataset.scopeKey, event.currentTarget.dataset.scopeValue));
    all("[data-entity-toggle]", "click", event => { const entity = this.entities.find(item => item.entity_id === event.currentTarget.dataset.entityToggle); if (entity) this.setDraft(entity.entity_id, this.plannedStatus(entity) === "included" ? "excluded" : "included"); });
    all("[data-entity-preview]", "click", event => this.previewEntity(event.currentTarget.dataset.entityPreview));
    one("[data-include]", "click", () => this.applyToSelection("included")); one("[data-exclude]", "click", () => this.applyToSelection("excluded")); one("[data-clear]", "click", () => this.applyToSelection(""));
    all("[data-history-restore]", "click", event => this.restoreHistory(Number(event.currentTarget.dataset.historyRestore)));
    all("[data-bridge-card]", "click", event => this.selectBridge(event.currentTarget.dataset.bridgeCard));
    all("[data-bridge-expand]", "click", event => { const id = event.currentTarget.dataset.bridgeExpand; this.expandedBridges.has(id) ? this.expandedBridges.delete(id) : this.expandedBridges.add(id); this.render(); });

    one("[data-diagnostic-filter]", "change", event => { this.diagnosticFilter = event.target.value; this.render(); });
    one("[data-action-menu]", "click", () => { this.actionMenuOpen = !this.actionMenuOpen; this.render(); });
    one("[data-test-mode-enable]", "click", () => this.enableTestWriteMode());
    one("[data-test-mode-disable]", "click", () => this.disableTestWriteMode());
    one("[data-operation-plan]", "click", () => this.planOperation());
    one("[data-operation-reconcile]", "click", () => this.reconcileOperation());
    one("[data-apply]", "click", () => this.applyDraft());
    one("[data-save]", "click", () => this.saveDraft()); one("[data-preview]", "click", () => this.previewServer()); one("[data-export]", "click", () => this.exportDraft()); one("[data-load]", "click", () => this.loadSaved()); one("[data-discard]", "click", async () => { if (await this.requestConfirmation("Entwurf verwerfen", "Die ungespeicherten Vormerkungen werden verworfen. Ein gespeicherter Entwurf bleibt erhalten.", "Verwerfen")) this.discard(); });
    one("[data-confirm-accept]", "click", () => this.finishConfirmation(true)); one("[data-confirm-cancel]", "click", () => this.finishConfirmation(false)); one("dialog", "cancel", event => { event.preventDefault(); this.finishConfirmation(false); });
  }
  styles() { return `
:host{--space:4px;--radius:16px;--fg:var(--primary-text-color,#202124);--muted:var(--secondary-text-color,#62666c);--surface:var(--card-background-color,#fff);--bg:var(--primary-background-color,#f5f6f8);--line:var(--divider-color,#dfe2e7);--accent:var(--primary-color,#0277bd);display:block;color:var(--fg);background:var(--bg);min-height:100vh;font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif);line-height:1.5}
*{box-sizing:border-box}main{max-width:1120px;margin:0 auto;padding:24px 24px 40px;min-width:0}button,input,select{font:inherit;color:inherit;max-width:100%;min-width:0}button{min-height:44px;border:1px solid var(--line);border-radius:10px;padding:9px 14px;background:var(--surface);cursor:pointer;font-weight:500}button:hover:not(:disabled){background:color-mix(in srgb,var(--accent) 7%,var(--surface))}button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:3px}button:disabled{cursor:not-allowed;opacity:.5}.primary{background:var(--accent);border-color:var(--accent);color:var(--text-primary-color,#fff)}.primary:hover:not(:disabled){background:var(--accent);filter:brightness(.94)}input,select{min-height:44px;border:1px solid var(--line);border-radius:10px;padding:9px 12px;background:var(--surface);width:100%}label{display:grid;gap:6px;font-size:.875rem;color:var(--muted)}h1,h2,h3,p,dl{margin:0}h1{font-size:1.35rem;letter-spacing:-.025em}h2{font-size:clamp(1.4rem,4vw,1.85rem);letter-spacing:-.025em;line-height:1.2}h3{font-size:1rem;line-height:1.4}p+p{margin-top:8px}small{font-size:.8rem}.muted,small,dt{color:var(--muted)}code{font-size:.78rem;overflow-wrap:anywhere;word-break:break-word}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.78rem;max-width:100%}.app-header,.section-heading,.device-head,.management-row{display:flex;justify-content:space-between;align-items:center;gap:16px}.app-header p{color:var(--muted);font-size:.8rem;margin-top:2px}.icon-button{width:44px;flex-shrink:0;padding:0;font-size:1.2rem}.main-nav{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;margin:22px 0 12px;border-bottom:1px solid var(--line)}.main-nav button{border:0;border-bottom:3px solid transparent;border-radius:8px 8px 0 0;background:transparent;padding:10px 4px;white-space:nowrap;font-size:.9rem}.main-nav button[aria-selected=true]{color:var(--accent);border-bottom-color:var(--accent);background:color-mix(in srgb,var(--accent) 6%,transparent);font-weight:700}.page-head{display:grid;gap:8px;margin:20px 0}.page-head p{color:var(--muted);max-width:70ch;font-size:.9rem}.eyebrow{text-transform:uppercase;letter-spacing:.08em;font-size:.68rem!important;font-weight:700;color:var(--accent)!important}.surface,.area-card{border-radius:var(--radius);background:var(--surface);padding:20px;margin:16px 0;border:1px solid color-mix(in srgb,var(--line) 65%,transparent)}.surface>h3{margin-bottom:12px}.surface>.muted{margin:8px 0 16px}.section-heading{margin-bottom:16px}.section-heading>span{font-size:.8rem}.status-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:16px 0}.status-tile{padding:16px;background:var(--surface);border-radius:12px;min-width:0}.status-tile small,.status-tile strong{display:block;overflow-wrap:anywhere}.status-tile small{font-size:.75rem;margin-bottom:6px}.status-tile strong{font-size:1rem;line-height:1.3}.tone-success,.state-confirmed{color:var(--success-color,#2e7d32)}.tone-warning,.text-warning{color:var(--warning-color,#b96a00)}.tone-error{color:var(--error-color,#c62828)}.tone-neutral{color:var(--muted)}.state{display:inline-flex;padding:4px 9px;border-radius:99px;font-size:.72rem;line-height:1.5;max-width:100%;background:var(--secondary-background-color,#eef0f3);white-space:normal}.state-included{color:var(--accent)}.state-planned{color:var(--accent);background:color-mix(in srgb,var(--accent) 10%,transparent)}.state-unknown,.state-neutral,.state-mixed{color:var(--muted)}.source-options{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:12px 0 20px}.source-option{padding:12px;border-radius:10px;background:var(--secondary-background-color,#f2f4f6);display:grid;gap:4px;min-width:0}.source-option.selected{box-shadow:inset 3px 0 var(--accent)}.source-option small{font-size:.75rem}.management-row{border-top:1px solid var(--line);padding-top:16px;margin-bottom:8px}.management-row strong{display:block;font-size:.95rem}.management-row p{font-size:.8rem;margin-top:4px}.lock-note{font-size:.85rem;color:var(--muted);margin-top:12px}.lock-note p{margin-top:8px}.bridge-card{border-bottom:1px solid var(--line);padding:12px 0}.bridge-card:last-child{border-bottom:0}.definition-list{margin-top:12px}.definition-list>div{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;padding:10px 0;border-bottom:1px solid var(--line);font-size:.85rem}.definition-list>div:last-child{border-bottom:0}dd{margin:0;text-align:right;overflow-wrap:anywhere}.actions,.toolbar,.segmented,.selection-bar,.entity-actions,.pager{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.toolbar{justify-content:space-between;margin:16px 0}.segmented{padding:3px;border-radius:12px;background:var(--secondary-background-color,#e9edf1);gap:2px;flex-wrap:nowrap}.segmented button{border:0;background:transparent;border-radius:9px;min-height:38px;padding:7px 12px;font-size:.85rem}.segmented button[aria-pressed=true]{background:var(--surface);color:var(--accent);box-shadow:0 1px 3px #0001}.search{width:100%;margin:12px 0}.search input{font-size:.9rem}.filters{padding:12px 16px;margin:12px 0}.filters summary{cursor:pointer;font-size:.85rem;font-weight:600;min-height:24px}.filter-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:16px 0}.filter-grid label{font-size:.75rem}.result-count{font-size:.78rem;margin:12px 0}.area-card{padding:0;overflow:hidden}.area-heading{width:100%;display:flex;align-items:center;justify-content:space-between;border:0;border-radius:0;background:transparent;padding:16px;text-align:left;gap:12px}.area-heading strong{display:block;font-size:1rem}.area-heading small{font-weight:400;font-size:.78rem;display:block;margin-top:3px}.area-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));padding:0 16px 16px;gap:8px}.area-metrics>div{display:flex;flex-direction:column;gap:4px;min-width:0}.area-metrics dt{font-size:.69rem;overflow-wrap:anywhere}.area-metrics dd{text-align:left;font-size:1.05rem;font-weight:650}.area-content{padding:0 16px 16px;border-top:1px solid var(--line)}.area-content .device-row{padding-left:12px;border-left:2px solid var(--line)}.device-row .entity-list{padding-left:16px;border-left:2px solid var(--line)}.area-controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:0 16px 12px}.area-controls button{font-size:.78rem;min-height:38px}.area-select{margin:0 16px 16px;font-size:.8rem}.device-row{padding:14px 0;border-bottom:1px solid var(--line)}.device-row:last-child{border-bottom:0}.entity-copy{min-width:0;flex:1}.entity-copy strong{display:block;overflow-wrap:anywhere;font-size:.9rem}.entity-copy code,.entity-copy small{display:block;margin-top:4px}.entity-row{position:relative;display:flex;flex-wrap:wrap;align-items:flex-start;gap:12px;padding:16px 0;border-bottom:1px solid var(--line)}.entity-row:last-child{border-bottom:0}.entity-actions{justify-content:flex-end;max-width:100%}.entity-actions input{width:24px;height:24px;min-height:24px;accent-color:var(--accent)}.entity-meta{display:flex;gap:8px;flex-wrap:wrap;font-size:.72rem;color:var(--muted);margin-top:8px}.entity-list{min-width:0}.technical{width:100%;font-size:.78rem;color:var(--muted);margin-top:10px}.technical summary{cursor:pointer;min-height:32px;display:list-item;padding:5px 0}.technical p{margin:8px 0}.config-values{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.72rem}.toggle{width:52px;height:44px;position:relative;padding:0;border:0;flex-shrink:0;background:transparent}.toggle:before{content:"";position:absolute;left:3px;top:11px;width:46px;height:24px;border-radius:99px;background:var(--disabled-color,#b8bec6)}.toggle span{position:absolute;left:5px;top:13px;width:20px;height:20px;background:#fff;border-radius:50%;z-index:1}.toggle.on:before{background:var(--accent)}.toggle.on span{transform:translateX(22px)}.selection-bar{padding:12px;background:color-mix(in srgb,var(--accent) 7%,var(--surface));border-radius:12px;margin:12px 0}.selection-bar strong{font-size:.8rem;flex-basis:100%}.pager{justify-content:center;margin:16px 0;font-size:.75rem}.pager span{text-align:center}.pager button{font-size:.8rem}.change-row{padding:16px 0;border-bottom:1px solid var(--line)}.change-states{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.change-states div{padding:10px 12px;border-radius:9px;background:var(--secondary-background-color,#f3f4f6)}.change-states dt{font-size:.72rem}.change-states dd{text-align:left;font-size:.85rem;margin-top:3px}.change-row>.text-warning{font-size:.8rem;margin-top:12px}.activation-card>p{font-size:.85rem;margin:8px 0}.sticky-actions{position:relative;background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:16px}.footer-count{font-size:.75rem;color:var(--muted);margin-right:auto}.sticky-actions button{font-size:.8rem}.action-menu{display:flex;flex-basis:100%;gap:8px;flex-wrap:wrap;padding-top:8px;border-top:1px solid var(--line)}.settings-nav{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;margin:16px 0}.settings-nav button{font-size:.78rem;padding:8px 6px}.settings-nav button[aria-current=page]{color:var(--accent);border-color:var(--accent);background:color-mix(in srgb,var(--accent) 6%,var(--surface))}.settings-content h3{margin-bottom:12px}.finding,.rule-group{padding:12px 0;border-bottom:1px solid var(--line)}.finding summary{display:flex;justify-content:space-between;gap:12px;cursor:pointer}.finding summary strong{font-size:.85rem}.finding summary span{font-size:.75rem;color:var(--muted);white-space:nowrap}.finding p,.rule-group p{font-size:.85rem;margin-top:12px}.finding ul,.rule-group ul{padding-left:20px}.finding li,.rule-group li{margin-top:6px}.history-row{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:14px 0;border-bottom:1px solid var(--line)}.history-row small{display:block}.history-row strong{font-size:.9rem}.feedback{margin:8px 0}.status-line{font-size:.75rem;min-height:20px}.notice{padding:12px 14px;border-radius:10px;background:var(--secondary-background-color,#eef0f3);font-size:.85rem;margin:12px 0;overflow-wrap:anywhere}.notice.error{border-left:3px solid var(--error-color,#c62828)}.notice.warning{border-left:3px solid var(--warning-color,#b96a00)}.notice p{margin:6px 0 10px}.empty{text-align:center;padding:28px 16px;color:var(--muted);font-size:.9rem}.empty p{margin:8px 0 16px}dialog{width:min(460px,calc(100vw - 32px));padding:24px;border:1px solid var(--line);border-radius:16px;background:var(--surface);color:var(--fg)}dialog h2{font-size:1.25rem}dialog p{font-size:.9rem;margin:16px 0;overflow-wrap:anywhere}dialog::backdrop{background:#0008}.dialog-actions{display:flex;justify-content:flex-end;gap:8px;flex-wrap:wrap}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
@media(max-width:700px){main{padding:16px 14px 28px}.main-nav{gap:0;margin-top:16px}.main-nav button{font-size:.75rem;padding:10px 1px;white-space:normal;overflow-wrap:anywhere}.status-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.status-tile{padding:12px}.status-tile strong{font-size:.9rem}.surface{padding:16px}.page-head{margin:16px 0}.filter-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.segmented{width:100%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr))}.segmented button{padding:7px}.toolbar>button{font-size:.8rem}.device-head{flex-wrap:wrap;gap:8px}.device-head>.actions{justify-content:flex-start}.device-head .actions button{font-size:.75rem;padding:7px 10px}.entity-row>.entity-copy{flex-basis:100%}.entity-actions{width:100%;justify-content:space-between}.management-row{align-items:flex-start}.management-row>.state{flex-shrink:0}.source-options{gap:8px}.source-option{padding:10px}.source-option strong{font-size:.85rem}.source-option small{font-size:.7rem}.settings-nav{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.settings-nav button{font-size:.75rem}.sticky-actions{padding:10px;gap:6px;align-items:stretch;padding-bottom:max(10px,env(safe-area-inset-bottom))}.footer-count{flex-basis:100%;margin:0}.sticky-actions>button{flex:1;padding:8px 5px;font-size:.75rem;line-height:1.25;white-space:normal}.action-menu button{flex:1 1 auto}.history-row{align-items:flex-start;flex-direction:column;gap:10px}.definition-list>div{gap:12px;font-size:.8rem}.section-heading{gap:8px;flex-wrap:wrap}.section-heading>button{font-size:.8rem}.activation-card .section-heading>.state{font-size:.7rem}.area-metrics dt{font-size:.66rem}}
@media(max-width:360px){.main-nav{grid-template-columns:.9fr .8fr 1.15fr 1.4fr}.main-nav button{font-size:.75rem;padding-inline:0;letter-spacing:-.01em}.app-header h1{font-size:1.2rem}.filter-grid{grid-template-columns:1fr}.area-metrics{gap:5px}.area-metrics dt{font-size:.63rem}.sticky-actions>button{font-size:.7rem}}
`; }

}

if (!customElements.get("homekit-manager-panel")) customElements.define("homekit-manager-panel", HomeKitManagerPanel);
