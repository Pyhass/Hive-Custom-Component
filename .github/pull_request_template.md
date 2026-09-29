## What does this change?

<!-- A short description of the change and why it's needed. -->

## Related issues

<!-- e.g. Fixes #123 -->

## Checklist

<<<<<<< HEAD
- [ ] Tests added or updated, and `script/test` passes
- [ ] `script/lint --check` passes (after `script/lint`, which also regenerates translations)
=======
- [ ] Tests added or updated (`python -m pytest`)
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] If `strings.json` changed: ran `python script/gen_translations.py`
>>>>>>> 1a55d87294f3c1fd059bd190faec008e020cc2cf
- [ ] If this is going into a release: bumped `version` in `manifest.json`
