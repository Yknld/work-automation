import unittest
from spreadsheet_jobs import cooldown, throttle_settings

class FakeStop:
    def __init__(self, cancel=False):self.now=0;self.cancel=cancel;self.stopped=False
    def is_set(self):return self.stopped
    def wait(self, seconds):
        self.now+=seconds;self.stopped=self.cancel
        return self.stopped

class ThrottleTests(unittest.TestCase):
    def test_defaults_and_settings(self):
        self.assertEqual(throttle_settings({}),(100,900))
        self.assertEqual(throttle_settings({'pause_every':25,'pause_minutes':.5}),(25,30))
        for config in [{'pause_every':0},{'pause_minutes':-1},{'pause_minutes':float('nan')}]:
            with self.assertRaises(ValueError):throttle_settings(config)
    def test_countdown_finishes(self):
        stop=FakeStop();messages=[]
        self.assertTrue(cooldown(65,stop,messages.append,clock=lambda:stop.now))
        self.assertEqual(stop.now,65)
        self.assertIn('01:05',messages[0]);self.assertIn('continuing',messages[-1])
    def test_stop_cancels_break(self):
        stop=FakeStop(True)
        self.assertFalse(cooldown(900,stop,lambda _:None,clock=lambda:stop.now))
        self.assertEqual(stop.now,30)
