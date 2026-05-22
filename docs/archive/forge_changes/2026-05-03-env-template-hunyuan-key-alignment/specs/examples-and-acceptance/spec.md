# Spec delta — examples-and-acceptance (env-template-hunyuan-key-alignment)

## ADDED Requirements

### Requirement: .env.example MUST list the env var names that are actually read at runtime

The system SHALL keep `.env.example` template in sync with the env var names that
runtime code (`config/models.yaml` + `src/framework/run.py` + provider workers)
actually reads at startup. Specifically, for any provider listed in the template,
the variable names commented in `.env.example` MUST match the names appearing in
`config/models.yaml::providers.<provider>.api_key_env` and any direct `os.environ.
get("...")` lookup in `src/framework/run.py`. Cross-references SHOULD be added as
inline comments next to the placeholder so future env-var renames are easy to audit.

#### Scenario: Hunyuan 3D mesh provider env var alignment

- **GIVEN** a fresh user copies `.env.example` to `.env` and fills in the Hunyuan
  3D mesh provider section
- **WHEN** they run `python -m framework.run --task <bundle> --live-llm`
- **THEN** the env var name they configured MUST be `HUNYUAN_3D_KEY` (matching
  `config/models.yaml:95 api_key_env: HUNYUAN_3D_KEY` and `src/framework/run.py:100
  os.environ.get("HUNYUAN_3D_KEY")`)
- **AND** template MUST NOT show TC3-HMAC-SHA256-style three-segment placeholders
  (`HUNYUAN_3D_SECRET_ID` / `HUNYUAN_3D_SECRET_KEY` / `HUNYUAN_3D_REGION`) which
  no longer correspond to any runtime read path
- **AND** template SHOULD inline a comment cross-referencing the runtime read
  location so future renames are surfaced

#### Scenario: Existing .env files configured with old TC3 fields are not broken

- **GIVEN** a `.env` file already configured with the old TC3-HMAC-SHA256 fields
  (`HUNYUAN_3D_SECRET_ID/SECRET_KEY/REGION`)
- **WHEN** runtime starts
- **THEN** those env vars are NOT read by any current code path
- **AND** they SHALL NOT cause any error (they are simply ignored as unrecognized
  env vars)
- **AND** Hunyuan 3D mesh provider falls back to FakeMeshWorker / Tripo3D /
  provider auth failure (existing behavior; outside this change's scope)
