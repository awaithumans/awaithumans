"""Verifier provider implementations.

One file per provider. Each exports `verify(config, context) ->
VerifierResult`. Lazy-imports its vendor SDK so missing extras only
break the verifier path that uses them, not the whole server."""
