import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.models.base import Base # Import Base from models.base, ensuring app.models is imported in main or here to register User
import app.models # Register all models
from app.main import app

# Setup in-memory DB for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_register_user():
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123", "full_name": "Test User"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data

def test_login_user():
    # Register explicitly to ensure user exists
    client.post(
        "/api/v1/auth/register",
        json={"email": "test-login@example.com", "password": "password123", "full_name": "Test Login User"},
    )
    
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "test-login@example.com", "password": "password123"},
    )
    print(f"Login Response: {response.status_code} {response.text}")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_get_me():
    # Login to get token
    login_res = client.post(
        "/api/v1/auth/token",
        data={"username": "test@example.com", "password": "password123"},
    )
    token = login_res.json()["access_token"]
    
    response = client.get(
        "/api/v1/auth/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"

def test_login_fake_user():
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "fake@example.com", "password": "password123"},
    )
    assert response.status_code == 401

def test_unauthorized_access():
    response = client.get("/api/v1/workflows")
    # Should be 401 because we protected it
    assert response.status_code == 401
