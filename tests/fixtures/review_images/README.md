# Review images fixtures

Real Qwen-image-2.0 1024×1024 PNG outputs for tests that need actual pixel data
through the visual review pipeline (`visual_mode=True`). Replaces the pre-2026-04-22
`b"VISUAL_A" * 4` / `b"fake-source-image-bytes"` byte markers that only proved
"an `image_url` block was constructed", not that the pipeline correctly surfaces
visual judgment.

## Contents

| File | Subject | Source |
|---|---|---|
| `tavern_door_v1.png` | Oak tavern door, iron banding, morning light (1.43 MB) | Qwen run `a2_mesh` cand_0, 2026-04-22 |
| `tavern_door_v2.png` | Similar oak door, variation in wood texture (1.42 MB) | Same run, cand_1 |
| `tavern_door_v3.png` | Same archetype, added support stand (1.39 MB) | Same run, cand_2 |

All three are legitimate 1024×1024 PNGs with similar subject. The tests assign
different FakeAdapter-programmed scores per fixture to verify the review pipeline
correctly routes the winner — the FIXTURE FILE does not dictate quality; the
TEST PROGRAM does.

## Usage

```python
from tests.fixtures import load_review_image

bytes_good = load_review_image("tavern_door_v1")  # bytes, ready for repo.put()
```

See `tests/fixtures/__init__.py` for the helper.

## Why real PNGs, not synthesized bytes

- `visual_mode=True` passes image bytes through `compress_for_vision` (Pillow) —
  synthesized non-image bytes would crash at decode
- Real PNG 1024×1024 exercises the TBD-006 compression path (768px JPEG@80 @
  `_attach_image_bytes`); synthesized bytes would bypass it
- Codex review (2026-04-22) flagged that the old marker bytes (`VISUAL_A/B/C`,
  `ORIGINAL_/REVISED_`, `fake-source-image-bytes`) reduced visual review tests
  to "count image_url blocks" assertions — zero evidence of visual judgment
  actually working

## Regenerating

If Qwen prompts change or you want fresh fixtures:

```bash
# Generates 3 real 1024×1024 PNGs, ~$0.08 total
PYTHONPATH=src python -m framework.run \
    --task examples/image_to_3d_pipeline.json \
    --live-llm --run-id fixture_regen \
    --artifact-root ./artifacts

# Copy outputs
cp artifacts/<YYYY-MM-DD>/fixture_regen/*cand*_0.png tests/fixtures/review_images/tavern_door_v1.png
cp artifacts/<YYYY-MM-DD>/fixture_regen/*cand*_1.png tests/fixtures/review_images/tavern_door_v2.png
cp artifacts/<YYYY-MM-DD>/fixture_regen/*cand*_2.png tests/fixtures/review_images/tavern_door_v3.png
```

## Repo size budget

4.35 MB total. If fixture set grows past ~20 MB total, consider git LFS.
Currently NOT using LFS — these are checked in as regular PNG blobs.
