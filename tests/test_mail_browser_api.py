import unittest
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.mail_browser import router
from core.luckmail.models import (
    PageResult,
    PurchaseItem,
    TokenMailDetail,
    TokenMailItem,
    TokenMailList,
    UserInfo,
)


class MailBrowserApiTests(unittest.TestCase):
    def setUp(self):
        # 单独挂载 router，避免测试时触发主应用的启动副作用。
        app = FastAPI()
        app.include_router(router, prefix="/api")
        self.client = TestClient(app)

    def _mock_client(self):
        fake_client = mock.MagicMock()
        fake_client.__enter__.return_value = fake_client
        fake_client.__exit__.return_value = None
        return fake_client

    def test_profile_returns_unconfigured_when_api_key_is_missing(self):
        with mock.patch(
            "api.mail_browser.config_store.get",
            side_effect=lambda key, default="": default if key == "luckmail_base_url" else "",
        ):
            response = self.client.get("/api/mail-browser/profile")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["configured"])

    def test_purchases_endpoint_returns_purchase_items(self):
        fake_client = self._mock_client()
        fake_client.user.get_purchases.return_value = PageResult(
            list=[
                PurchaseItem(
                    id=1,
                    email_address="demo@example.com",
                    token="tok_demo",
                    project_name="openai",
                    price="1.0000",
                    tag_name="主力号",
                )
            ],
            total=1,
            page=1,
            page_size=20,
        )

        with mock.patch(
            "api.mail_browser.config_store.get",
            side_effect=lambda key, default="": "demo-key" if key == "luckmail_api_key" else default,
        ), mock.patch("api.mail_browser.LuckMailClient", return_value=fake_client):
            response = self.client.get("/api/mail-browser/purchases", params={"keyword": "demo"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["email_address"], "demo@example.com")
        self.assertEqual(payload["items"][0]["token"], "tok_demo")

    def test_mail_endpoints_return_mail_list_and_detail(self):
        fake_client = self._mock_client()
        fake_client.user.get_token_mails.return_value = TokenMailList(
            email_address="demo@example.com",
            project="openai",
            mails=[
                TokenMailItem(
                    message_id="msg-1",
                    from_addr="no-reply@example.com",
                    subject="Welcome",
                    body="plain body",
                    html_body="<p>plain body</p>",
                    received_at="2026-04-01 12:00:00",
                )
            ],
        )
        fake_client.user.get_token_mail_detail.return_value = TokenMailDetail(
            message_id="msg-1",
            from_addr="no-reply@example.com",
            to="demo@example.com",
            subject="Welcome",
            body_text="plain body",
            body_html="<p>plain body</p>",
            received_at="2026-04-01 12:00:00",
            verification_code="123456",
        )

        with mock.patch(
            "api.mail_browser.config_store.get",
            side_effect=lambda key, default="": "demo-key" if key == "luckmail_api_key" else default,
        ), mock.patch("api.mail_browser.LuckMailClient", return_value=fake_client):
            mails_response = self.client.get("/api/mail-browser/mails", params={"token": "tok_demo"})
            detail_response = self.client.get(
                "/api/mail-browser/mail-detail",
                params={"token": "tok_demo", "message_id": "msg-1"},
            )

        self.assertEqual(mails_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(mails_response.json()["mails"][0]["subject"], "Welcome")
        self.assertEqual(detail_response.json()["verification_code"], "123456")


if __name__ == "__main__":
    unittest.main()
