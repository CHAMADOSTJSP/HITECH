"""Testes do núcleo do VoltGuard.

Execute com as dependências de requirements.txt instaladas:
    python -m unittest discover -s tests -v
Usa um SQLite temporário; não toca em nenhum banco real.
"""
import asyncio
import hashlib
import hmac
import os
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SECRET_KEY"] = "k" * 48
os.environ.pop("RENDER", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

main.limiter.enabled = False  # o limite de cadastro (5/h) atrapalharia a suíte
client = TestClient(main.app)
PASSWORD = "senha-super-segura-1"


def uid() -> str:
    return uuid.uuid4().hex[:8]


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_org():
    """Cria uma organização e devolve (tenant, usuário CEO, token)."""
    tenant, user = f"ORG-{uid().upper()}", f"ceo_{uid()}"
    r = client.post("/api/tenant/register", json={"tenant_id": tenant, "username": user, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return tenant, user, login(user)


def login(user: str, password: str = PASSWORD) -> str:
    r = client.post("/api/token", json={"username": user, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def add_panel(token: str, panel_id: str = None):
    panel_id = panel_id or f"P-{uid().upper()}"
    r = client.post("/api/panels/add", headers=bearer(token),
                    json={"id": panel_id, "name": "Quadro teste", "location": "Sala 1"})
    assert r.status_code == 200, r.text
    return panel_id


def create_user(ceo_token: str, role: str):
    name = f"u_{uid()}"
    r = client.post("/api/users", headers=bearer(ceo_token), json={"username": name, "role": role, "password": PASSWORD})
    assert r.status_code == 201, r.text
    return name, login(name)


def panels(token: str) -> dict:
    r = client.get("/api/panels", headers=bearer(token))
    assert r.status_code == 200, r.text
    return {p["id"]: p for p in r.json()["panels"]}


class CoreTests(unittest.TestCase):
    def test_health(self):
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_short_password_rejected(self):
        r = client.post("/api/tenant/register", json={"tenant_id": f"ORG-{uid().upper()}", "username": f"x_{uid()}", "password": "curta"})
        self.assertEqual(r.status_code, 400)

    def test_new_panel_has_no_invented_readings(self):
        _, _, token = register_org()
        pid = add_panel(token)
        p = panels(token)[pid]
        self.assertIsNone(p["current"])
        self.assertIsNone(p["temperature"])
        self.assertEqual(p["status"], "SEM_DADOS")

    def test_executive_report_survives_panel_without_data(self):
        _, _, token = register_org()
        add_panel(token)
        r = client.get("/api/export/executive-report", headers=bearer(token))
        self.assertEqual(r.status_code, 200)

    def test_reserved_demo_markers_rejected_for_real_panels(self):
        _, _, token = register_org()
        r = client.post("/api/panels/add", headers=bearer(token),
                        json={"id": f"P-{uid().upper()}", "name": "x", "location": "y", "component": main.DEMO_COMPONENT})
        self.assertEqual(r.status_code, 422)
        r = client.post("/api/panels/add", headers=bearer(token),
                        json={"id": f"P-{uid().upper()}", "name": "x", "location": "y", "gateway_qr": "DEMO-1"})
        self.assertEqual(r.status_code, 422)

    def test_force_failure_only_on_demo_panels(self):
        _, _, token = register_org()
        real = add_panel(token)
        r = client.post("/api/demo/force-failure", headers=bearer(token), json={"panel_id": real})
        self.assertEqual(r.status_code, 409)
        demo = next(p for p in panels(token).values() if p["component"] == main.DEMO_COMPONENT)
        r = client.post("/api/demo/force-failure", headers=bearer(token), json={"panel_id": demo["id"]})
        self.assertEqual(r.status_code, 200, r.text)

    def test_tenant_isolation(self):
        _, _, token_a = register_org()
        _, _, token_b = register_org()
        pid = add_panel(token_a)
        self.assertNotIn(pid, panels(token_b))
        r = client.get(f"/api/panels/{pid}/alarm-rules", headers=bearer(token_b))
        self.assertEqual(r.status_code, 404)
        r = client.post("/api/telemetry", headers=bearer(token_b), json={"panel_id": pid, "temperature": 90, "current": 10})
        self.assertEqual(r.status_code, 404)


class DeviceAndAlarmTests(unittest.TestCase):
    def setUp(self):
        _, _, self.token = register_org()
        self.panel = add_panel(self.token)
        r = client.post("/api/devices/credentials", headers=bearer(self.token), json={"panel_id": self.panel, "name": "gw"})
        self.assertEqual(r.status_code, 201, r.text)
        self.device = r.json()["device_token"]

    def send(self, temperature, current=100):
        return client.post("/api/device/telemetry", headers=bearer(self.device),
                           json={"panel_id": self.panel, "temperature": temperature, "current": current})

    def alarm_statuses(self):
        rows = client.get("/api/alarms", headers=bearer(self.token)).json()
        return [a["status"] for a in rows if a["panel_id"] == self.panel and a["alarm_type"] == "HIGH_TEMPERATURE"]

    def test_alarm_opens_holds_with_hysteresis_and_clears(self):
        r = self.send(90)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["active_alarms"], 1)
        self.assertEqual(self.alarm_statuses(), ["ACTIVE"])
        self.assertEqual(panels(self.token)[self.panel]["status"], "CRITICO")
        # 84 °C está abaixo do limite (85), mas acima do ponto de normalização (82): o alarme permanece.
        self.send(84)
        self.assertEqual(self.alarm_statuses(), ["ACTIVE"])
        self.send(80)
        self.assertEqual(self.alarm_statuses(), ["CLEARED"])
        self.assertEqual(panels(self.token)[self.panel]["status"], "NORMAL")

    def test_repeated_reading_does_not_duplicate_alarm(self):
        self.send(95)
        self.send(96)
        self.assertEqual(len(self.alarm_statuses()), 1)

    def test_revoked_or_wrong_panel_token_rejected(self):
        other = add_panel(self.token)
        r = client.post("/api/device/telemetry", headers=bearer(self.device),
                        json={"panel_id": other, "temperature": 50, "current": 10})
        self.assertEqual(r.status_code, 403)
        cred = client.get("/api/devices/credentials", headers=bearer(self.token)).json()[0]["id"]
        client.post(f"/api/devices/credentials/{cred}/revoke", headers=bearer(self.token))
        self.assertEqual(self.send(50).status_code, 401)

    def test_invalid_readings_rejected(self):
        self.assertEqual(self.send(999).status_code, 422)
        self.assertEqual(self.send(50, current=-1).status_code, 422)

    def test_history_retention_prunes_old_samples(self):
        self.send(50)
        with main.SessionLocal() as db:
            db.add(main.PanelHistoryModel(panel_id=self.panel, tenant_id="X", timestamp="2000-01-01T00:00:00Z", temperature=1.0))
            db.commit()
            removed = main.prune_old_history(db)
        self.assertGreaterEqual(removed, 1)


class UserManagementTests(unittest.TestCase):
    def setUp(self):
        self.tenant, self.ceo_name, self.ceo = register_org()

    def test_only_ceo_manages_users(self):
        _, tech = create_user(self.ceo, "Técnico de Campo")
        self.assertEqual(client.get("/api/users", headers=bearer(tech)).status_code, 403)
        self.assertEqual(client.post("/api/users", headers=bearer(tech),
                                     json={"username": f"z_{uid()}", "role": "Gerente", "password": PASSWORD}).status_code, 403)

    def test_invalid_role_and_weak_password_rejected(self):
        r = client.post("/api/users", headers=bearer(self.ceo), json={"username": f"z_{uid()}", "role": "Admin", "password": PASSWORD})
        self.assertEqual(r.status_code, 422)
        r = client.post("/api/users", headers=bearer(self.ceo), json={"username": f"z_{uid()}", "role": "Gerente", "password": "curta"})
        self.assertEqual(r.status_code, 400)

    def test_technician_cannot_post_manual_telemetry(self):
        _, tech = create_user(self.ceo, "Técnico de Campo")
        pid = add_panel(self.ceo)
        r = client.post("/api/telemetry", headers=bearer(tech), json={"panel_id": pid, "temperature": 50, "current": 10})
        self.assertEqual(r.status_code, 403)

    def test_deactivated_user_loses_access_immediately(self):
        name, token = create_user(self.ceo, "Gerente")
        self.assertEqual(client.get("/api/panels", headers=bearer(token)).status_code, 200)
        r = client.patch(f"/api/users/{name}", headers=bearer(self.ceo), json={"is_active": False})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(client.get("/api/panels", headers=bearer(token)).status_code, 401)
        r = client.post("/api/token", json={"username": name, "password": PASSWORD})
        self.assertEqual(r.status_code, 401)

    def test_role_change_applies_to_existing_token(self):
        name, token = create_user(self.ceo, "Gerente")
        body = {"panel_id": "NAO-EXISTE", "temperature": 50, "current": 10}
        self.assertEqual(client.post("/api/telemetry", headers=bearer(token), json=body).status_code, 404)
        client.patch(f"/api/users/{name}", headers=bearer(self.ceo), json={"role": "Técnico de Campo"})
        self.assertEqual(client.post("/api/telemetry", headers=bearer(token), json=body).status_code, 403)

    def test_ceo_cannot_demote_or_disable_self(self):
        r = client.patch(f"/api/users/{self.ceo_name}", headers=bearer(self.ceo), json={"role": "Gerente"})
        self.assertEqual(r.status_code, 409)
        r = client.patch(f"/api/users/{self.ceo_name}", headers=bearer(self.ceo), json={"is_active": False})
        self.assertEqual(r.status_code, 409)

    def test_organization_keeps_at_least_one_ceo(self):
        second, token2 = create_user(self.ceo, "CEO")
        r = client.patch(f"/api/users/{self.ceo_name}", headers=bearer(token2), json={"role": "Gerente"})
        self.assertEqual(r.status_code, 200, r.text)
        # Agora só o segundo CEO resta; ele não pode se rebaixar (e ninguém mais pode fazê-lo).
        r = client.patch(f"/api/users/{second}", headers=bearer(token2), json={"role": "Gerente"})
        self.assertEqual(r.status_code, 409)

    def test_cannot_touch_users_of_other_organization(self):
        _, _, other_ceo = register_org()
        name, _ = create_user(self.ceo, "Gerente")
        r = client.patch(f"/api/users/{name}", headers=bearer(other_ceo), json={"is_active": False})
        self.assertEqual(r.status_code, 404)


class WebhookTests(unittest.TestCase):
    def test_signing_secret_is_per_tenant_and_ceo_only(self):
        self.assertEqual(main.webhook_secret_for("A"), main.webhook_secret_for("A"))
        self.assertNotEqual(main.webhook_secret_for("A"), main.webhook_secret_for("B"))
        tenant, _, ceo = register_org()
        r = client.get("/api/tenant/webhook/secret", headers=bearer(ceo))
        self.assertEqual(r.json()["signing_secret"], main.webhook_secret_for(tenant))
        _, tech = create_user(ceo, "Técnico de Campo")
        self.assertEqual(client.get("/api/tenant/webhook/secret", headers=bearer(tech)).status_code, 403)

    def test_delivery_is_signed_and_retried(self):
        class FakeResponse:
            def __init__(self, code):
                self.status_code = code

        class FakeClient:
            calls = []
            codes = [500, 200]

            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, content=None, headers=None):
                FakeClient.calls.append((url, content, headers))
                return FakeResponse(FakeClient.codes[len(FakeClient.calls) - 1])

        event = {"event": "ALARM_OPENED", "event_id": "evt1", "organization_id": "T", "alarm_id": 1,
                 "panel_id": "P", "alarm_type": "HIGH_TEMPERATURE", "severity": "CRITICAL", "message": "m", "occurred_at": "x"}

        async def no_sleep(_):
            return None

        with patch.object(main, "_load_webhook_url", return_value="https://exemplo.com/hook"), \
                patch.object(main, "validate_webhook_url", side_effect=lambda u: u), \
                patch.object(main.httpx, "AsyncClient", FakeClient), \
                patch.object(main.asyncio, "sleep", no_sleep):
            asyncio.run(main.deliver_alarm_webhooks("T", [event]))

        self.assertEqual(len(FakeClient.calls), 2)  # 1ª tentativa 500, 2ª 200
        _, body, headers = FakeClient.calls[-1]
        expected = hmac.new(main.webhook_secret_for("T").encode(), body, hashlib.sha256).hexdigest()
        self.assertEqual(headers["X-VoltGuard-Signature"], f"sha256={expected}")

    def test_real_alarm_queues_webhook(self):
        _, _, token = register_org()
        pid = add_panel(token)
        cred = client.post("/api/devices/credentials", headers=bearer(token), json={"panel_id": pid, "name": "gw"}).json()
        with patch.object(main, "deliver_alarm_webhooks") as deliver:
            r = client.post("/api/device/telemetry", headers=bearer(cred["device_token"]),
                            json={"panel_id": pid, "temperature": 95, "current": 10})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(deliver.call_count, 1)
            events = deliver.call_args[0][1]
            self.assertEqual(events[0]["alarm_type"], "HIGH_TEMPERATURE")


if __name__ == "__main__":
    unittest.main()
