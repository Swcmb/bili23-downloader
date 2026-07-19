# tests/cli/test_render.py
def test_render_table_outputs_headers():
    from cli.render.table import render_table
    render_table([{"title": "A", "duration": "1:00"}], ["title", "duration"])


def test_toast_no_exception():
    from cli.render.toast import toast
    toast("test message", level="info")
    toast("error message", level="error")


def test_progress_render_lifecycle():
    from cli.render.progress import ProgressRender
    p = ProgressRender()
    p.start()
    p.add_task("test", total=100)
    p.update("test", advance=50)
    p.stop()
