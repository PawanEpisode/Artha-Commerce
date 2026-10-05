from config.settings import allowed_hosts, csrf_trusted_origins


def test_production_domain_is_allowed_alongside_vercel(monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "api.example.com")

    hosts = allowed_hosts()

    assert "api.example.com" in hosts
    assert ".vercel.app" in hosts
    assert "localhost" in hosts


def test_production_origin_is_trusted_for_admin_login(monkeypatch):
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "")
    monkeypatch.setenv("VERCEL_PROJECT_PRODUCTION_URL", "arthacommerce-api.meetpawan.com")

    assert csrf_trusted_origins() == ["https://arthacommerce-api.meetpawan.com"]


def test_blank_production_url_is_ignored(monkeypatch):
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "localhost")
    monkeypatch.delenv("VERCEL_PROJECT_PRODUCTION_URL", raising=False)

    assert allowed_hosts() == ["localhost", ".vercel.app"]
