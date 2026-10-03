"""Generate an anonymous synthetic event-timing study through real solvers."""
import json
import sys
from pathlib import Path
from launch_speed import reconstruct
from speed_evidence import estimate_endpoint


def build():
    def parameter(value, bounds, basis):
        return {"value": value, "range": bounds, "basis": basis}
    def event(kind, t):
        return {"kind": kind, "verified": True, "estimateSeconds": t,
                "bracketSeconds": [t - .01, t + .01], "note": "Synthetic event bracket"}
    evidence = {
        "eventType": "let", "ballIdentityVerified": True, "crossesEarlierCollision": False,
        "contact": event("racket_contact", 10), "endpoint": event("first_net_impact", 10.7),
        "horizontalDistanceMetres": parameter(12, [11, 13], "Synthetic court geometry"),
        "contactHeightMetres": parameter(2.7, [2.45, 2.95], "Synthetic contact height"),
        "endpointHeightMetres": parameter(.94, [.89, .99], "Synthetic net contact"),
        "dragPerM": parameter(.020, [.012, .028], "Illustrative physical prior"),
        "liftPerM": parameter(0, [-.004, .004], "Illustrative unknown-spin perturbation"),
    }
    return {"schema": "tennis-speed-study/synthetic-v1", "synthetic": True,
            "warning": "Synthetic regression example, not a real-footage accuracy benchmark",
            "input": evidence, "corrected": estimate_endpoint(evidence),
            "rejectedEarlierEndpointHypothesis": {
                "assumedFlightSeconds": .4,
                "unvalidatedNumericalSpeed": reconstruct(12, .4, 2.7, .94)["launchSpeedKphEstimate"],
                "reason": "Hypothesized endpoint 10.40 is outside observed bracket 10.69-10.71"}}


if __name__ == "__main__":
    destination = Path(sys.argv[1])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
