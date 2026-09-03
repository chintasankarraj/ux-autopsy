from backend.app.api.routes import _url_ok

def test_valid():
    assert _url_ok("https://example.com")

def test_invalid():
    assert not _url_ok("not a url")
