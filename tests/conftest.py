"""Record what the test run saw, so the app's trust badge can tell when it is out of date."""

import pytest

from equal_path.paths import ROOT, STALENESS_WATCHED, TEST_FINGERPRINT, TEST_REPORT
from equal_path.trust import is_full_reported_run, write_fingerprint


@pytest.hookimpl(trylast=True)  # after the junitxml plugin has written the report
def pytest_sessionfinish(session, exitstatus):
    option = session.config.option
    full = is_full_reported_run(
        report=TEST_REPORT,
        from_testpaths=session.config.args_source == pytest.Config.ArgsSource.TESTPATHS,
        keyword=option.keyword,
        markexpr=option.markexpr,
        collectonly=option.collectonly,
        xmlpath=option.xmlpath,
    )
    write_fingerprint(TEST_FINGERPRINT, STALENESS_WATCHED, root=ROOT, report=TEST_REPORT, full_run=full)
