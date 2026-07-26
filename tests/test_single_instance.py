from __future__ import annotations

from coderadio_tray.single_instance import try_acquire


def test_single_instance_first_acquires(isolated_config_dir, qapp):
    lock = try_acquire()
    assert lock is not None
    lock.unlock()


def test_second_instance_is_rejected(isolated_config_dir, qapp):
    first = try_acquire()
    assert first is not None
    try:
        # A second holder in the same process must fail while the first holds.
        second = try_acquire()
        assert second is None
    finally:
        first.unlock()


def test_lock_released_allows_reacquire(isolated_config_dir, qapp):
    first = try_acquire()
    assert first is not None
    first.unlock()
    second = try_acquire()
    assert second is not None
    second.unlock()
