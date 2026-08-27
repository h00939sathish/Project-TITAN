## 2026-08-18T16:40:33Z
You are the Cryptographic Implementation Engineer for Profit-Engine-AI (v2.0) on Project TITAN.
Your working directory is D:\projects\Project TITAN\.agents\worker_remed_1
Read D:\projects\Project TITAN\.agents\ORIGINAL_REQUEST.md, D:\projects\Project TITAN\.agents\orchestrator_1\PROJECT.md, and the FULL FORENSIC AUDIT EVIDENCE REPORT at D:\projects\Project TITAN\.agents\auditor_gen2_1\handoff.md.

Mission:
The Forensic Auditor reported an INTEGRITY VIOLATION due to a facade implementation in PromotionCertificateRegistry in src/titan/research/promotion_certificate.py (which had a hardcoded if cert.signature == 'bad' check without real Ed25519 verification).

Your task:
1. In src/titan/research/promotion_certificate.py:
   - Implement genuine Ed25519 verification in PromotionCertificateRegistry.verify():
     - Construct canonical JSON bytes of the certificate fields (strategy_id, expires_at, content_digest, parameters) via _canonical_json.
     - If self._public_key is provided (or if passed to verify), verify bytes.fromhex(cert.signature) against the canonical payload bytes using self._public_key.verify(sig_bytes, payload_bytes).
     - Handle InvalidSignature, invalid hex formats, or decoding errors by raising ValueError("Forged signature").
     - Also implement a helper create_signed_certificate(private_key, strategy_id, expires_at, content_digest, parameters) -> Certificate that creates genuine Ed25519 signatures.
2. In tests/test_execution_integrity.py, tests/e2e/test_profit_engine_e2e.py, tests/e2e/test_profit_engine_v2_integration.py, and any other test files:
   - Generate genuine Ed25519 keypairs (ed25519.Ed25519PrivateKey.generate()).
   - Sign genuine test certificates with the private key for valid tests.
   - For invalid/forged signature tests, use a mutated signature, mismatched key, or bad hex to test that reg.verify(...) genuinely rejects forged certificates.
3. Run the full pytest suite (pytest tests/) to ensure all tests pass (100% pass rate).
4. DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work.
5. Write your complete handoff report in D:\projects\Project TITAN\.agents\worker_remed_1\handoff.md.
6. When complete, notify the orchestrator with send_message.
