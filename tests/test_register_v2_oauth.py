import sys
import types
import unittest
from unittest.mock import MagicMock, patch

# ???????? selectolax stub??? import register_v2 ?????????
fake_selectolax = types.ModuleType("selectolax")
fake_selectolax_parser = types.ModuleType("selectolax.parser")
fake_selectolax_parser.HTMLParser = object
sys.modules.setdefault("selectolax", fake_selectolax)
sys.modules.setdefault("selectolax.parser", fake_selectolax_parser)

from platforms.chatgpt.register_v2 import EmailServiceAdapter, RegistrationEngineV2


class RegisterV2OAuthTests(unittest.TestCase):
    def test_fetch_oauth_tokens_reuses_registration_session_and_returns_refresh_token(self):
        engine = RegistrationEngineV2(email_service=MagicMock(), callback_logger=lambda _: None)
        chatgpt_client = MagicMock()
        chatgpt_client.session = object()
        chatgpt_client.device_id = "device-1"
        chatgpt_client.ua = "ua"
        chatgpt_client.sec_ch_ua = "sec-ch-ua"
        chatgpt_client.impersonate = "chrome136"
        adapter = MagicMock(spec=EmailServiceAdapter)

        with patch("platforms.chatgpt.register_v2.OAuthClient") as oauth_cls:
            oauth_client = oauth_cls.return_value
            oauth_client.oauth_client_id = "app_EMoamEEZ73f0CkXaXp7hrann"
            oauth_client.login_and_get_tokens.return_value = {
                "access_token": "new-at",
                "refresh_token": "rt-1",
                "id_token": "id-1",
            }

            ok, data = engine._fetch_oauth_tokens(
                chatgpt_client=chatgpt_client,
                email_addr="user@example.com",
                password="pass",
                email_service_adapter=adapter,
            )

        self.assertTrue(ok)
        self.assertEqual(data["refresh_token"], "rt-1")
        self.assertEqual(data["client_id"], "app_EMoamEEZ73f0CkXaXp7hrann")
        self.assertIs(oauth_client.session, chatgpt_client.session)
        oauth_client.login_and_get_tokens.assert_called_once()

    def test_fetch_oauth_tokens_requires_refresh_token(self):
        engine = RegistrationEngineV2(email_service=MagicMock(), callback_logger=lambda _: None)
        chatgpt_client = MagicMock()
        chatgpt_client.session = object()
        chatgpt_client.device_id = "device-1"
        chatgpt_client.ua = "ua"
        chatgpt_client.sec_ch_ua = "sec-ch-ua"
        chatgpt_client.impersonate = "chrome136"
        adapter = MagicMock(spec=EmailServiceAdapter)

        with patch("platforms.chatgpt.register_v2.OAuthClient") as oauth_cls:
            oauth_client = oauth_cls.return_value
            oauth_client.login_and_get_tokens.return_value = {"access_token": "only-at"}
            oauth_client.last_error = ""

            ok, message = engine._fetch_oauth_tokens(
                chatgpt_client=chatgpt_client,
                email_addr="user@example.com",
                password="pass",
                email_service_adapter=adapter,
            )

        self.assertFalse(ok)
        self.assertIn("refresh_token", message)


if __name__ == "__main__":
    unittest.main()
