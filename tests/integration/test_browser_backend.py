"""Browser to authenticated WebSocket to real HA storage, entirely isolated."""
import asyncio
import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from aiohttp import web
from homeassistant.components import frontend
from homeassistant.components.http import HomeAssistantView
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.parametrize("browser_name", ["chromium", "webkit"])
async def test_browser_uses_registered_panel_and_real_backend(hass, enable_custom_integrations, hass_client, hass_access_token, browser_name):
    root = Path(__file__).resolve().parents[2]
    if not shutil.which("node") or not (root / "node_modules/playwright").exists():
        pytest.skip("Install the pinned npm development dependencies to run browser/backend E2E")
    native = MockConfigEntry(domain="homekit", title="Audit Bridge", data={"name": "Audit Bridge"}, options={"homekit_mode": "bridge", "filter": {"include_entities": ["light.audit_lamp"]}})
    native.add_to_hass(hass)
    before = deepcopy(dict(native.options))
    hass.states.async_set("light.audit_lamp", "on", {"friendly_name": "Audit Lamp"})
    flow = await hass.config_entries.flow.async_init("homekit_manager", context={"source": "user"})
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    registration = hass.data[frontend.DATA_PANELS]["homekit_manager"].config["_panel_custom"]
    # Use the real backend registration; a Python/JS tag mismatch fails here.
    html = """<!doctype html><html lang="de"><meta name="viewport" content="width=device-width,initial-scale=1"><body style="margin:0"><script type="module">
    import MODULE;
    const pending=new Map();let counter=0;const ws=new WebSocket(location.origin.replace(/^http/,'ws')+'/api/websocket');
    ws.onmessage=event=>{const message=JSON.parse(event.data);if(message.type==='auth_required'){ws.send(JSON.stringify({type:'auth',access_token:TOKEN}));}
    else if(message.type==='auth_ok'){const panel=document.createElement(NAME);document.body.append(panel);panel.hass={states:{},callWS:request=>new Promise((resolve,reject)=>{const id=++counter;pending.set(id,{resolve,reject});ws.send(JSON.stringify({...request,id}));})};}
    else if(message.type==='result'){const entry=pending.get(message.id);pending.delete(message.id);if(entry){message.success?entry.resolve(message.result):entry.reject(new Error(message.error?.message||'Backend error'));}}};
    </script></body></html>""".replace("MODULE", json.dumps(registration["module_url"])).replace("TOKEN", json.dumps(hass_access_token)).replace("NAME", json.dumps(registration["name"]))
    class TestPanel(HomeAssistantView):
        url = "/hkm-test"
        name = "test:homekit_manager"
        requires_auth = False
        async def get(self, request):
            return web.Response(text=html, content_type="text/html")
    hass.http.register_view(TestPanel())
    client = await hass_client()
    url = str(client.make_url("/hkm-test"))
    process = await asyncio.create_subprocess_exec("node", str(root / "tests/frontend/backend_e2e.mjs"), url, browser_name, cwd=root, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(process.communicate(), timeout=75)
    except asyncio.TimeoutError:
        process.kill(); await process.wait(); raise
    assert process.returncode == 0, out.decode() + err.decode()
    assert "real HA backend: ok" in out.decode()
    assert dict(native.options) == before
    manager = hass.data["homekit_manager"]["coordinator"]
    snapshot = await manager.async_yaml_status()
    assert snapshot["valid"] and snapshot["exists"]
    assert snapshot["document"]["bridges"][native.entry_id]["entities"]["light.audit_lamp"] == "exclude"
    assert manager.activation_status()["state"] == "unknown"
