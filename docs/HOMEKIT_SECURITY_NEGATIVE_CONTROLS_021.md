# Security Negative Controls 0.10.21

## Scope

The negative controls are isolated test mutations. They never modify a
production configuration or pairing. The independent oracle tests are in
`tests/test_security_negative_controls_021.py`; they compare synthetic
observations without calling the migration implementation.

## Results

| Control | Mutation | Expected detection | Result |
|---|---|---|---|
| A | Bridge MAC changed | Identity assertion fails | TEST VERIFIED |
| B | Pairing fingerprint replaced | Identity assertion fails; no re-pairing | TEST VERIFIED |
| C | Bridge count increased to three | Bridge-count assertion fails | TEST VERIFIED |
| D | One excluded entity appended to the 25 allowed entities | Published set assertion fails | TEST VERIFIED |
| E | AID or IID changed | Identity assertion fails | TEST VERIFIED |
| F | Expected fault point missing | Fault-point assertion fails | TEST VERIFIED |
| G | Wrong Core commit | Checkout guard exits before pytest | TEST VERIFIED |
| H | One-byte-equivalent patch mutation | SHA-256 verification exits before apply | TEST VERIFIED |

Command:

```text
python -m pytest -q tests/test_security_negative_controls_021.py
```

Result: `10 passed` in `0.19s`.

## Important limitation

Controls A–F are independent oracle tests over synthetic observations; they do
not claim that a real HAP daemon was mutated in those six cases. The normal
experimental Core suite does use real isolated Core processes and aiohomekit
controllers and passed its 68 tests, including the existing multi-bridge,
identity, allowlist, and recovery scenarios. A separate full-Core mutation
campaign for each A–F alteration is NOT VERIFIED by this sprint.

The wrong-Core and tampered-patch controls exercise the actual CI guard path.
They are not accepted as successful migration tests; they pass only because the
guard correctly rejects the unsafe setup.

## Mutation cleanup

Each mutation uses `tmp_path` or a temporary Core directory. The Manager tree
remained clean apart from the intended sprint changes, and no mutation was
committed to the product or Core branch.
