"""Extract a SHORT native-frame evidence window; detections are candidates, not calls."""
import argparse,json
from pathlib import Path
import cv2
import numpy as np

def evidence(source,start,end,out,roi=None,hsv_low=(18,42,80),hsv_high=(62,255,255),threshold=12):
    if not 0<=start<end or end-start>15: raise ValueError("Use a 0–15 second window; split longer intervals")
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    cap=cv2.VideoCapture(str(source))
    if not cap.isOpened(): raise ValueError("Cannot open source")
    fps=cap.get(cv2.CAP_PROP_FPS); cap.set(cv2.CAP_PROP_POS_MSEC,max(0,start-.2)*1000)
    previous=None; records=[]; last_time=-1
    try:
        while True:
            ok,frame=cap.read()
            if not ok: break
            t=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            if t>end: break
            if t<=last_time: raise ValueError("Decoder timestamps unreliable; use a PTS-aware extraction path")
            last_time=t
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            if previous is None: previous=gray; continue
            diff=cv2.absdiff(gray,previous); previous=gray
            if t<start: continue
            h,w=frame.shape[:2]
            pixel_scale=(w*h/(1920*1080))**.5
            x,y,rw,rh=roi if roi else (0,0,w,h)
            if x<0 or y<0 or rw<=0 or rh<=0 or x+rw>w or y+rh>h: raise ValueError("ROI outside source frame")
            mask=cv2.inRange(cv2.cvtColor(frame,cv2.COLOR_BGR2HSV),np.array(hsv_low),np.array(hsv_high))
            mask[diff<threshold]=0
            mask[:y]=0;mask[y+rh:]=0;mask[:,:x]=0;mask[:,x+rw:]=0
            n,labels,stats,centres=cv2.connectedComponentsWithStats(mask); candidates=[]
            marked=frame.copy()
            for j in range(1,n):
                bx,by,bw,bh,area=stats[j];cx,cy=centres[j]
                # Retain a small compression/quantization floor on low-resolution footage.
                if 1<=area<=max(64,190*pixel_scale**2) and bw<=max(12,35*pixel_scale) and bh<=max(12,35*pixel_scale):
                    candidates.append([round(float(cx),2),round(float(cy),2),int(area)])
                    cv2.circle(marked,(round(cx),round(cy)),9,(0,160,255),1)
            name=f"{len(records):05d}"
            cv2.imwrite(str(out/(name+"-raw.png")),frame)
            raw=frame[y:y+rh,x:x+rw];delta=cv2.cvtColor(cv2.convertScaleAbs(diff[y:y+rh,x:x+rw],alpha=4),cv2.COLOR_GRAY2BGR)
            annotated=marked[y:y+rh,x:x+rw]
            strip=np.hstack([raw,delta,annotated])
            scale=min(1,1800/strip.shape[1]);strip=cv2.resize(strip,(round(strip.shape[1]*scale),round(strip.shape[0]*scale)))
            bar=np.full((28,strip.shape[1],3),245,np.uint8)
            cv2.putText(bar,f"{t:.6f}s | raw / difference / candidates",(7,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,0),1)
            cv2.imwrite(str(out/(name+"-compare.jpg")),np.vstack([bar,strip]))
            records.append({"timeSeconds":t,"decoderFrameIndex":round(cap.get(cv2.CAP_PROP_POS_FRAMES))-1,"raw":name+"-raw.png","comparison":name+"-compare.jpg","candidates":candidates})
    finally: cap.release()
    if not records: raise ValueError("No frames extracted")
    manifest={"source":str(source),"nominalFps":fps,"timestampSource":"decoder POS_MSEC, verify against source PTS for VFR","window":[start,end],"roi":roi,"candidatesAreNotVerdicts":True,"records":records}
    (out/"evidence.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("source");p.add_argument("start",type=float);p.add_argument("end",type=float);p.add_argument("output");p.add_argument("--roi",help="x,y,width,height");a=p.parse_args()
    d=evidence(a.source,a.start,a.end,a.output,list(map(int,a.roi.split(","))) if a.roi else None)
    print(json.dumps({"frames":len(d["records"]),"output":a.output}))






