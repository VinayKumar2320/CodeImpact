from app.core.config import Settings


def test_default_settings():
    settings = Settings()
    assert settings.PROJECT_NAME == "CodeImpact"
    assert settings.API_V1_STR == "/api/v1"
    assert isinstance(settings.BACKEND_CORS_ORIGINS, list)
    assert len(settings.BACKEND_CORS_ORIGINS) >= 1


def test_cors_origins_parsing():
    settings = Settings(BACKEND_CORS_ORIGINS="http://localhost:3000, http://example.com")
    assert "http://localhost:3000" in settings.BACKEND_CORS_ORIGINS
    assert "http://example.com" in settings.BACKEND_CORS_ORIGINS
