"""Injectable clock. Real date by default; SAATHI_TODAY=YYYY-MM-DD or clock.frozen() overrides it for tests and documented simulations."""
import contextlib, datetime as dt, os

_override = None


def today():
    if _override is not None:
        return _override
    env = os.environ.get("SAATHI_TODAY")
    if env:
        return dt.date.fromisoformat(env)
    return dt.datetime.now(dt.timezone.utc).date()


def now_utc():
    if _override is not None:
        return dt.datetime(_override.year, _override.month, _override.day, 12, 0, tzinfo=dt.timezone.utc)
    return dt.datetime.now(dt.timezone.utc)


@contextlib.contextmanager
def frozen(d):
    global _override
    if isinstance(d, str):
        d = dt.date.fromisoformat(d)
    prev, _override = _override, d
    try:
        yield
    finally:
        _override = prev
