import unittest

from services.chatgpt_sync import (
    get_cli_proxy_sync_state,
    is_cli_proxy_enabled,
    record_cpa_sync_result,
    set_cli_proxy_sync_enabled,
)


class ChatgptSyncTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
