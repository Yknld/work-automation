import unittest
from automation import Completion

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

    def test_fast_reply_with_completion_control(self):
        c=Completion([])
        self.assertIsNone(c.update(['answer'],False,0,completed=True))
        self.assertEqual(c.update(['answer'],False,3,completed=True),'answer')

    def test_old_reply_with_copy_is_not_new(self):
        c=Completion(['old'])
        self.assertIsNone(c.update(['old'],False,10,completed=True))

    def test_completion_control_does_not_override_streaming(self):
        c=Completion([])
        c.update(['answer'],True,0,completed=True)
        self.assertIsNone(c.update(['answer'],True,10,completed=True))
