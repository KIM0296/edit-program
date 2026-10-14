# PRE-G2 synthetic contracts only

No recording, decoded real PCM, annotation original or measured real-data receipt
belongs in this directory. `test_pcm_calibration.py` constructs invented acquisition,
session and annotation records and generates four frames of artificial PCM in memory.

`receipt.schema.json` describes the bounded public receipt envelope. `receipt_json()`
adds a SHA-256 of the canonical receipt content; schema validation alone does not
check the digest. Fractions remain exact numerator/denominator pairs and N/A is null.
All G1-G6 examples have TEST_ONLY_SUPPORT qualification; a gate name does not mean
that gate ran or passed. Real G1 evidence is separately linked in the status document.

Python immutable schemas in tools/pcm_calibration.py are the acquisition, annotation,
split and experiment input contracts. They validate supplied claims only. They do
not read/extract audio, authenticate permissions, establish reviewer independence,
or enforce a trusted storage ledger.

Failures exercised by tests include mutated originals, absent independent extraction,
channel/source-origin mismatch, nonintegral profiles, duplicate recording lineage,
overlapping windows, missing/blindness-disputed annotation, reviewer disagreement,
boundary ambiguity, zero denominators, calibration rejection, validation failure,
holdout insufficiency/reuse, reproduction mismatch and receipt overwrite attempts.

No synthetic result is a threshold recommendation or an editor-quality measurement.
