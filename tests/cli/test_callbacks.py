# tests/cli/test_callbacks.py
def test_register_callbacks_connects_signals():
    from util.common.signal_bus import signal_bus
    from cli.callbacks import register_callbacks
    before = list(signal_bus.ToastNotification._callbacks)
    register_callbacks()
    after = list(signal_bus.ToastNotification._callbacks)
    assert len(after) > len(before)


def test_toast_signal_emits_to_rich():
    from cli.callbacks import register_callbacks
    register_callbacks()
    from util.common.signal_bus import signal_bus
    signal_bus.ToastNotification.emit("test", "info")
