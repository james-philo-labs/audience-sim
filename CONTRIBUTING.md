# Contributing

Start with the credential-free quick start and `npm test`. Browser changes also need `npm run test:browser`. Use original or authorized small fixtures. Keep model calls out of tests and CI.

A useful report includes the commit, command, fresh run status, expected contract, observed failure and a minimal shareable fixture. State whether it is authored, replayed, model-produced or human-measured. Include a counterexample or valid alternative when changing a verifier. Do not post raw private requests, provider keys, proprietary media or identifiable reader data.

Preserve failed attempts and censoring. Do not change a fixture's result to make a regression pass. A schema or citation fix needs a test showing what it rejects and what remains valid. Changes to exposure, persona projection, clocks, forecast origin, budget or uncertainty need a versioned contract note; do not pool old and new study cells as one comparison.

Propose broad provider, memory or population features before implementation. The next measurement is predictive validity against real readers; adding a dashboard or more synthetic personas does not substitute for it. Public availability does not imply a reuse license; see the repository's licensing statement.

After deliberately reviewing the public diff and any new asset provenance, run `python3 scripts/seal_public.py` to refresh the explicit public inventory, then `npm run check:public`. Do not use resealing to conceal a failed check or to add run archives. The inventory records exact source bytes; local timestamps and run directories do not belong in it.
