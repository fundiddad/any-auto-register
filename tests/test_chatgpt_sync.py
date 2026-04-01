import base64
import json
import unittest

from services.chatgpt_sync import (
    get_cli_proxy_sync_state,
    get_oauth_sync_state,
    is_cli_proxy_enabled,
    record_cpa_sync_result,
    record_oauth_sync_result,
    set_cli_proxy_sync_enabled,
    upload_chatgpt_account_to_cpa,
)


class ChatgptSyncTests(unittest.TestCase):
    @staticmethod
    def _jwt_with_client_id(client_id: str) -> str:
        def _part(data):
            raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
            return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

        return f"{_part({'alg': 'none'})}.{_part({'client_id': client_id})}.sig"

    def test_set_cli_proxy_sync_enabled_marks_account(self):
        extra = {}
        state = set_cli_proxy_sync_enabled(extra, True, message="managed")
        self.assertTrue(state["enabled"])
        self.assertEqual(get_cli_proxy_sync_state(extra)["message"], "managed")
        self.assertTrue(is_cli_proxy_enabled(extra))

    def test_record_cpa_sync_result_tracks_attempt_and_upload(self):
        extra = {}
        state = record_cpa_sync_result(extra, True, "uploaded")
        self.assertTrue(state["uploaded"])
        self.assertEqual(state["last_message"], "uploaded")
        self.assertIn("uploaded_at", state)

    def test_record_oauth_sync_result_marks_phone_required(self):
        extra = {}
        state = record_oauth_sync_result(extra, False, "OAuth 登录被 add_phone 阻断")
        self.assertEqual(state["status"], "phone_required")
        self.assertEqual(get_oauth_sync_state(extra)["status"], "phone_required")

    def test_upload_chatgpt_account_to_cpa_requires_refresh_token(self):
        access_token = self._jwt_with_client_id("app_X8zY6vW2pQ9tR3dE7nK1jL5gH")

        class _Account:
            email = "user@example.com"
            token = access_token

            @staticmethod
            def get_extra():
                return {
                    "access_token": access_token,
                    "refresh_token": "",
                }

        ok, msg = upload_chatgpt_account_to_cpa(_Account())
        self.assertFalse(ok)
        self.assertIn("refresh_token", msg)


if __name__ == "__main__":
    unittest.main()
