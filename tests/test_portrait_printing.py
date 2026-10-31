"""CUPS simule : aucun appel reel, aucune impression."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from portrait_printing import PrintError, submit_print


OPTIONS = "PageSize/Media Size: *ExamplePostcard Other\nColorModel/Color: *RGB Gray\n"


class PrintingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.image = Path(self.temp.name) / "portrait avec espaces.png"
        self.image.write_bytes(b"test")
        self.mock = patch("portrait_printing.subprocess.run").start()
        self.addCleanup(patch.stopall)
        self.mock.side_effect = lambda args, **kw: subprocess.CompletedProcess(
            args, 0, OPTIONS if args[0] == "lpoptions" else "request id is SELPHY-42", "")

    def test_arguments_options_receipt_and_persistent_duplicate_guard(self):
        result = submit_print(self.image, "SELPHY", {"PageSize": "ExamplePostcard", "ColorModel": "RGB"})
        args, kwargs = self.mock.call_args
        self.assertEqual(args[0], ["lp", "-d", "SELPHY", "-n", "1", "-o", "fit-to-page",
                                  "-o", "orientation-requested=3", "-o", "PageSize=ExamplePostcard",
                                  "-o", "ColorModel=RGB", str(self.image)])
        self.assertNotIn("shell", kwargs)
        self.assertEqual(kwargs["timeout"], 20)
        self.assertIn("physique non confirmee", result)
        self.assertIn("SELPHY-42", result)
        count = self.mock.call_count
        with self.assertRaises(PrintError):
            submit_print(self.image, "SELPHY", {})
        self.assertEqual(self.mock.call_count, count)

    def test_missing_file_and_unconfigured_queue_do_not_call_cups(self):
        for path, queue in ((self.image.parent / "absent.png", "SELPHY"), (self.image, "")):
            with self.subTest(queue=queue), self.assertRaises(PrintError):
                submit_print(path, queue, {})
        self.mock.assert_not_called()

    def test_missing_command_or_nonexistent_queue(self):
        for failure in (FileNotFoundError(), subprocess.CompletedProcess([], 1, "", "Unknown printer")):
            self.mock.side_effect = failure if isinstance(failure, Exception) else None
            self.mock.return_value = failure
            with self.subTest(failure=failure), self.assertRaises(PrintError):
                submit_print(self.image, "SELPHY", {})
            self.assertFalse(self.image.with_suffix(".cups-submission").exists())

    def test_unknown_option_is_rejected_before_submission(self):
        with self.assertRaises(PrintError):
            submit_print(self.image, "SELPHY", {"PageSize": "InventedPaper"})
        self.assertFalse(any(c.args[0][0] == "lp" for c in self.mock.call_args_list))

    def test_submission_failure_or_timeout_keeps_guard(self):
        for failure in (subprocess.TimeoutExpired("lp", 20),
                        subprocess.CompletedProcess([], 1, "", "Submission failed"), FileNotFoundError()):
            marker = self.image.with_suffix(".cups-submission")
            marker.unlink(missing_ok=True)
            def run(args, **kwargs):
                if args[0] == "lp":
                    if isinstance(failure, Exception):
                        raise failure
                    return failure
                return subprocess.CompletedProcess(args, 0, OPTIONS, "")
            self.mock.side_effect = run
            with self.subTest(failure=failure), self.assertRaises(PrintError):
                submit_print(self.image, "SELPHY", {})
            self.assertTrue(marker.exists())

    def test_simultaneous_submissions_send_only_one_job(self):
        def send():
            try:
                return submit_print(self.image, "SELPHY", {})
            except PrintError:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: send(), range(2)))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(sum(c.args[0][0] == "lp" for c in self.mock.call_args_list), 1)
