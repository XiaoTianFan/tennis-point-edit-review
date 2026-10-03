"""Compute chord / flight-time estimates from measured inputs, never radar launch speed."""
import argparse,json,math
from pathlib import Path

def estimate(sample):
    c=sample["contactCourtMetres"];b=sample["bounceCourtMetres"]
    if len(c)!=3 or len(b)!=3: raise ValueError("Provide independent 3D endpoints [x,y,z]; bounce z=0")
    if c[2]<=0 or b[2]!=0: raise ValueError("Contact height and ground bounce must be explicit")
    dt=sample["bounceTimeSeconds"]-sample["contactTimeSeconds"]
    epsilon=sample["timeToleranceSeconds"]; distance_error=sample["distanceToleranceMetres"]
    if epsilon<0 or distance_error<0 or dt<=epsilon: raise ValueError("Invalid timing or error interval")
    distance=math.dist(c,b)
    low=3.6*max(0,distance-distance_error)/(dt+epsilon)
    high=3.6*(distance+distance_error)/(dt-epsilon)
    return {"pointId":sample["pointId"],"serveNumber":sample["serveNumber"],"flightSeconds":dt,"distanceMetres":distance,"meanFlightKphEstimate":3.6*distance/dt,"intervalKph":[low,high],"method":"straight-line endpoints / flight time; not launch/radar speed; geometric and timing interval only"}

def court_point(pixel, pixel_corners, court_corners):
    import cv2,numpy as np
    if len(pixel_corners)!=4 or len(court_corners)!=4: raise ValueError("Four corresponding GROUND points required")
    H=cv2.getPerspectiveTransform(np.float32(pixel_corners),np.float32(court_corners))
    return cv2.perspectiveTransform(np.float32([[pixel]]),H)[0,0].tolist()

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("samples");a=p.parse_args()
    data=json.loads(Path(a.samples).read_text(encoding="utf-8-sig"))
    results=[estimate(s) for s in data["samples"] if s.get("validServe") is True and not s.get("let")]
    print(json.dumps({"samples":results,"coverage":data.get("coverage"),"warning":"Only measured valid serves; document sample selection and court calibration separately"},ensure_ascii=False,indent=2))






