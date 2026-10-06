# Q-Break

Q-Break is a prototype quantum breach-testing tool. It runs genuine Grover and Shor circuits on a classical simulator against miniature symmetric and RSA encryption examples. Breaching production AES or RSA requires large, fault-tolerant quantum hardware that does not exist yet; this project demonstrates the attack and verification workflow without claiming a present-day speed advantage.

## Backend development

Requires Python 3.11.

```bash
pip install -e "backend[dev]"
cd backend
pytest
uvicorn qbreak.api.main:app --reload
```

The health endpoint is available at `http://localhost:8000/api/health`.
