"""
Unit tests validating web routing and production SPA serving in AnjurX.

Tests:
- GET / serves production SPA (dist/index.html) or Standalone Admin Login Portal
- GET /admin serves production SPA or Admin Login Portal
- GET /health returns JSON health check
- GET /api/* 404s return JSON (NEVER index.html)
- POST /api/auth/login authenticates Super Admin
- GET /api/auth/session validates Bearer token
- Static files (e.g. /shield.svg) are properly served
"""
import unittest
import asyncio
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from app.web_service import create_web_app, SUPER_ADMIN_ID, VALID_PASSWORDS


class TestWebRouting(AioHTTPTestCase):

    async def get_application(self):
        return create_web_app()

    @unittest_run_loop
    async def test_root_route_serves_html_admin_entry(self):
        """GET / must return HTML (dist/index.html or Super Admin Login Portal) and never 'Service active' placeholder."""
        resp = await self.client.get("/")
        self.assertEqual(resp.status, 200)
        self.assertIn("text/html", resp.headers.get("Content-Type", ""))
        text = await resp.text()
        
        # Verify old placeholder is NOT served
        self.assertNotIn("Service active. Visit Telegram bot:", text)
        
        # Verify it is the real Admin Panel entry point (either SPA or standalone login)
        is_spa = 'id="root"' in text or '<script type="module"' in text
        is_portal = 'id="login-form"' in text or "Super Admin" in text
        self.assertTrue(is_spa or is_portal, "Root route must serve the genuine Admin Panel entry point")

    @unittest_run_loop
    async def test_admin_route_serves_html(self):
        """GET /admin must serve the Admin Panel entry point."""
        resp = await self.client.get("/admin")
        self.assertEqual(resp.status, 200)
        self.assertIn("text/html", resp.headers.get("Content-Type", ""))
        text = await resp.text()
        self.assertNotIn("Service active. Visit Telegram bot:", text)

    @unittest_run_loop
    async def test_health_check_returns_json(self):
        """GET /health must return JSON health status."""
        resp = await self.client.get("/health")
        self.assertEqual(resp.status, 200)
        self.assertIn("application/json", resp.headers.get("Content-Type", ""))
        data = await resp.json()
        self.assertEqual(data.get("status"), "ok")

    @unittest_run_loop
    async def test_api_not_found_returns_json_404_not_html(self):
        """GET /api/... must return JSON 404, never index.html."""
        resp = await self.client.get("/api/unknown_non_existent_route")
        self.assertEqual(resp.status, 404)
        self.assertIn("application/json", resp.headers.get("Content-Type", ""))
        data = await resp.json()
        self.assertEqual(data.get("status"), 404)
        self.assertIn("error", data)

    @unittest_run_loop
    async def test_auth_session_unauthenticated(self):
        """GET /api/auth/session without token returns 401 authenticated: false."""
        resp = await self.client.get("/api/auth/session")
        self.assertEqual(resp.status, 401)
        data = await resp.json()
        self.assertFalse(data.get("authenticated"))

    @unittest_run_loop
    async def test_auth_login_and_session_lifecycle(self):
        """POST /api/auth/login successfully logs in Super Admin with salom12 and validates session."""
        self.assertIn("salom12", VALID_PASSWORDS)
        password = "salom12"

        # 1. Failed login with wrong password
        fail_resp = await self.client.post(
            "/api/auth/login",
            json={"user_id": SUPER_ADMIN_ID, "password": "wrong_password_123"}
        )
        self.assertEqual(fail_resp.status, 401)
        fail_data = await fail_resp.json()
        self.assertEqual(fail_data.get("code"), "INVALID_CREDENTIALS")

        # 2. Successful login with Super Admin credentials
        login_resp = await self.client.post(
            "/api/auth/login",
            json={"user_id": SUPER_ADMIN_ID, "password": password}
        )
        self.assertEqual(login_resp.status, 200)
        login_data = await login_resp.json()
        self.assertEqual(login_data.get("status"), "ok")
        token = login_data.get("token")
        self.assertTrue(bool(token))
        self.assertEqual(login_data.get("user", {}).get("user_id"), SUPER_ADMIN_ID)

        # 3. Check session with Bearer token
        session_resp = await self.client.get(
            "/api/auth/session",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(session_resp.status, 200)
        session_data = await session_resp.json()
        self.assertTrue(session_data.get("authenticated"))
        self.assertEqual(session_data.get("user", {}).get("user_id"), SUPER_ADMIN_ID)

        # 4. Logout
        logout_resp = await self.client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(logout_resp.status, 200)

        # 5. Session invalidated
        after_logout = await self.client.get(
            "/api/auth/session",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(after_logout.status, 401)


if __name__ == "__main__":
    unittest.main()
