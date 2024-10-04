import sys


def pytest_report_header(config) -> str:
    if sys.version_info[:2] >= (3, 13):
        return f'\nGIL enabled?: {sys._is_gil_enabled()}'
    return ''
