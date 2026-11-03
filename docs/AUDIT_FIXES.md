# Integration audit and corrections

This file records changes made while combining the three uploaded contributions.

## Corrections applied

1. Removed accidental `cat > ... <<'PY'` / `TXT` / `MD` shell heredoc wrappers from
   Member 1's controller, topology, requirements and setup guide. Those wrappers
   are terminal commands and must not be inside the files themselves.
2. Corrected Member 4's pipeline to preserve the detector's result dictionary
   and publish only `result["alerts"]`. A baseline sample or ordinary telemetry
   no longer gets reported as a false alert.
3. Updated Member 2's `--detector` server handler to use the shared pipeline.
4. Added `integration/stats_receiver.py` to receive Ryu flow-statistics UDP
   messages on port 9998 and pass them to the detector.
5. Separated the controller control listener from the telemetry service:
   control UDP port is now 10000; host telemetry remains UDP 9999.
6. Updated the Ryu forwarding match to include IPv4 source/destination fields
   for IPv4 flows, and exports `ipv4_src`/`ipv4_dst` so the optional response
   policy can identify a source host.
7. Added an opt-in, timed block/unblock mode to the statistics receiver.
   It is disabled unless `--auto-block` is explicitly supplied.
8. Updated the root README and integration/setup documents with the combined
   folder structure, port plan and run sequence.
9. Added `.gitignore` rules for Python bytecode, cache folders and local venvs.

## Local verification

Command:

    python3 -m unittest discover -s tests -v

Result: **22 tests passed**.

Command:

    python3 -m compileall -q controller mininet monitoring telemetry integration tests

Result: compilation completed successfully.

## Not verified

The preparation environment did not run Ryu, Open vSwitch or Mininet. The team
must verify the controller imports and starts under the Ubuntu VM's Python
version, confirm both switches connect, test `pingall`, receive real flow
statistics, and verify the actual OpenFlow block/unblock behavior. Ryu 4.34 is
pinned in the provided requirements and may need environment-specific
compatibility work; do not silently change the version.

Performance measurements and final demo evidence must be collected from actual
Mininet runs. No performance values are fabricated in this package.
