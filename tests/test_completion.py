import unittest
from copilot_bridge import Completion

class CompletionTests(unittest.TestCase):
    def test_old_reply_is_never_returned(self):
        c=Completion(['old'])
        self.assertIsNone(c.update(['old'],True,0))
        self.assertIsNone(c.update(['old'],False,10))
    def test_requires_generation_and_settling(self):
        c=Completion([])
        self.assertIsNone(c.update(['new'],False,0))
        self.assertIsNone(c.update(['new'],False,10))
        self.assertIsNone(c.update(['new'],True,11))
        self.assertEqual(c.update(['new'],False,12),'new')
    def test_stream_changes_reset_timer(self):
        c=Completion([])
        c.update(['partial'],True,0)
        self.assertIsNone(c.update(['complete'],False,5))
        self.assertIsNone(c.update(['complete'],False,7))
        self.assertEqual(c.update(['complete'],False,8),'complete')
    def test_empty_reply_is_not_success(self):
        c=Completion([])
        c.update([''],True,0)
        self.assertIsNone(c.update([''],False,10))
