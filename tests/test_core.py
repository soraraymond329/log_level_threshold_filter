import logging
import unittest

from log_level_threshold_filter import LogLevelThresholdFilter


def _record(level):
    """Build a LogRecord with a given level and deterministic fields.

    Avoids any reliance on wall-clock time by letting the logging module set
    its own ``created``; we never assert on it.
    """
    return logging.LogRecord(
        name="test.logger",
        level=level,
        pathname="some/path.py",
        lineno=1,
        msg="hi",
        args=None,
        exc_info=None,
    )


class ConstructionTests(unittest.TestCase):
    def test_defaults_are_warning_to_error(self):
        f = LogLevelThresholdFilter()
        self.assertEqual(f.min_level, logging.WARNING)
        self.assertEqual(f.max_level, logging.ERROR)

    def test_accepts_int_bounds(self):
        f = LogLevelThresholdFilter(logging.INFO, logging.CRITICAL)
        self.assertEqual(f.min_level, logging.INFO)
        self.assertEqual(f.max_level, logging.CRITICAL)

    def test_accepts_str_bounds(self):
        f = LogLevelThresholdFilter("WARNING", "ERROR")
        self.assertEqual(f.min_level, logging.WARNING)
        self.assertEqual(f.max_level, logging.ERROR)

    def test_mixed_int_and_str_bounds(self):
        f = LogLevelThresholdFilter(min_level=20, max_level="ERROR")
        self.assertEqual(f.min_level, 20)
        self.assertEqual(f.max_level, logging.ERROR)

    def test_min_above_max_raises(self):
        with self.assertRaises(ValueError):
            LogLevelThresholdFilter(logging.ERROR, logging.WARNING)

    def test_min_equal_max_ok(self):
        f = LogLevelThresholdFilter(logging.WARNING, logging.WARNING)
        self.assertTrue(f.filter(_record(logging.WARNING)))

    def test_unknown_level_name_raises(self):
        with self.assertRaises(ValueError):
            LogLevelThresholdFilter("BOGUS", logging.ERROR)
        with self.assertRaises(ValueError):
            LogLevelThresholdFilter(logging.WARNING, "NOPE")

    def test_bool_rejected_as_int(self):
        # bool subclasses int; True == 1, which would be a nonsensical level.
        with self.assertRaises(TypeError):
            LogLevelThresholdFilter(True, logging.ERROR)
        with self.assertRaises(TypeError):
            LogLevelThresholdFilter(logging.WARNING, False)

    def test_non_str_non_int_rejected(self):
        with self.assertRaises(TypeError):
            LogLevelThresholdFilter(1.5, logging.ERROR)
        with self.assertRaises(TypeError):
            LogLevelThresholdFilter(logging.WARNING, None)


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.f = LogLevelThresholdFilter(logging.WARNING, logging.ERROR)

    def test_accepts_warning(self):
        self.assertTrue(self.f.filter(_record(logging.WARNING)))

    def test_accepts_error(self):
        self.assertTrue(self.f.filter(_record(logging.ERROR)))

    def test_rejects_debug(self):
        self.assertFalse(self.f.filter(_record(logging.DEBUG)))

    def test_rejects_info(self):
        self.assertFalse(self.f.filter(_record(logging.INFO)))

    def test_rejects_critical(self):
        self.assertFalse(self.f.filter(_record(logging.CRITICAL)))

    def test_rejects_below_warning(self):
        # INFO is 20, WARNING is 30.
        self.assertFalse(self.f.filter(_record(25)))


class CustomLevelTests(unittest.TestCase):
    def test_accepts_registered_level_between_bounds(self):
        # 35 sits between WARNING(30) and ERROR(40).
        self.assertTrue(
            LogLevelThresholdFilter(logging.WARNING, logging.ERROR).filter(
                _record(35)
            )
        )

    def test_rejects_custom_level_outside_bounds(self):
        self.assertFalse(
            LogLevelThresholdFilter(logging.WARNING, logging.ERROR).filter(
                _record(45)
            )
        )


class IntegrationWithHandlerTests(unittest.TestCase):
    def test_works_as_handler_filter(self):
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        records_seen = []
        handler.emit = lambda record: records_seen.append(record.levelno)
        handler.addFilter(LogLevelThresholdFilter(logging.WARNING, logging.ERROR))

        logger = logging.getLogger("test.integration")
        logger.setLevel(logging.DEBUG)
        logger.handlers = [handler]
        logger.propagate = False

        logger.debug("ignored")
        logger.warning("kept")
        logger.error("kept")
        logger.critical("ignored")

        self.assertEqual(records_seen, [logging.WARNING, logging.ERROR])


if __name__ == "__main__":
    unittest.main()
