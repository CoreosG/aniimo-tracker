import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import App


class CallbackDiagnosticsTests(unittest.TestCase):
    def test_repeated_fault_is_throttled_and_rotated_logs_remain_bounded_utf8(self):
        with tempfile.TemporaryDirectory() as directory,patch('sanctum_panel.game_is_foreground',return_value=False):
            app=App(directory,hotkeys=False)
            try:
                error=OSError('Transient window failure')
                app.report_callback_exception(OSError,error,None)
                path=Path(directory)/'diagnostics/runtime.log'
                original=path.read_bytes()
                for _ in range(10):app.report_callback_exception(OSError,error,None)
                self.assertEqual(path.read_bytes(),original)
                for i in range(12):app.report_callback_exception(ValueError,ValueError(str(i)+'ç'*40000),None)
                logs=sorted(path.parent.glob('runtime*.log'))
                self.assertEqual(len(logs),2)
                for log in logs:
                    self.assertLessEqual(log.stat().st_size,262144)
                    log.read_text(encoding='utf-8')
            finally:app.close()
