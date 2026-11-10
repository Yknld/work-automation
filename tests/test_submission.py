import unittest
from unittest.mock import Mock, patch
from automation import Copilot, CopilotError

class SubmissionTests(unittest.TestCase):
    def setup_client(self, count):
        client=Copilot();client.page=Mock()
        send=client.page.get_by_role.return_value.filter.return_value
        send.count.return_value=count
        send.is_enabled.return_value=True
        return client,send,Mock()

    def test_clicks_once_without_enter(self):
        client,send,editor=self.setup_client(1)
        client.submit_prompt(editor,'fictional prompt')
        editor.fill.assert_called_once_with('fictional prompt')
        send.click.assert_called_once_with(timeout=5000)
        editor.press.assert_not_called()

    def test_ambiguous_send_does_not_submit(self):
        client,send,editor=self.setup_client(2)
        with self.assertRaises(CopilotError):client.submit_prompt(editor,'test')
        send.click.assert_not_called()

    def test_missing_send_times_out_without_enter(self):
        client,send,editor=self.setup_client(0)
        with patch('automation.time.monotonic',side_effect=[0,1,16]):
            with self.assertRaises(CopilotError):client.submit_prompt(editor,'test')
        send.click.assert_not_called();editor.press.assert_not_called()

    def test_cleanup_refuses_unowned_chat(self):
        client=Copilot();client.page=Mock()
        client.page.url='https://m365.cloud.microsoft/chat/conversation/personal'
        with self.assertRaises(CopilotError):client.delete_saved_chat()
        client.page.locator.assert_not_called()

    def test_cleanup_refuses_changed_chat(self):
        client=Copilot();client.page=Mock();client.owned_chat='/chat/conversation/created'
        client.page.url='https://m365.cloud.microsoft/chat/conversation/personal'
        with self.assertRaises(CopilotError):client.delete_saved_chat()
        client.page.locator.assert_not_called()
