# Q-Break status

## Merged baseline

- Agent 3 skeleton is committed locally on `main` and tagged `skeleton`.
- Shared encoding, simulator configuration, health endpoint, tests, and CI are present.
- Push is pending repository access for the GitHub credential available on the development machine.

## Agent 3 API branch

- All API schemas and routes are implemented with strict attacker-input separation.
- Mock services keep frontend development unblocked until the Grover and Shor modules merge.
- Real-module orchestration, evidence generation, and verification checks are wired to the locked interfaces.
- Docker and Render configuration enable key size 4 and modulus 15.

## Production

- No deployment URL yet. The GitHub branch must be pushed before Render can build it.

## Known issues

- Python and Docker are unavailable in the current local environment, so executable validation is delegated to GitHub Actions after push.
- Grover, MiniAES, Shor, MiniRSA, and the React frontend are owned by the other agents and are not yet merged.
