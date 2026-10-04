"""Extract a SHORT native-frame evidence window; detections are candidates, not calls."""
import argparse,json
from pathlib import Path
import cv2
import numpy as np
from media_probe import identity

def candidate_mask(frame,diff,roi,hsv_low,hsv_high,threshold):
    """Return filtering diagnostics, not ball-presence or event judgments."""
    x,y,rw,rh=roi
    mask=cv2.inRange(cv2.cvtColor(frame,cv2.COLOR_BGR2HSV),np.array(hsv_low),np.array(hsv_high))
    counts={'afterColor':int(np.count_nonzero(mask))}
    mask[diff<threshold]=0
    counts['afterMotion']=int(np.count_nonzero(mask))
    mask[:y]=0;mask[y+rh:]=0;mask[:,:x]=0;mask[:,x+rw:]=0
    counts['afterRoi']=int(np.count_nonzero(mask))
    return mask,counts

def evidence(source,start,end,out,roi=None,hsv_low=(18,42,80),hsv_high=(62,255,255),threshold=12,
             candidates_enabled=True,max_area=None,max_span=None):
    if not 0<=start<end or end-start>15: raise ValueError("Use a 0–15 second window; split longer intervals")
    if len(hsv_low)!=3 or len(hsv_high)!=3 or any(not 0<=a<=b<=m for a,b,m in zip(hsv_low,hsv_high,(179,255,255))):
        raise ValueError('Invalid OpenCV HSV range')
    if not 0<=threshold<=255 or any(v is not None and (not np.isfinite(v) or v<=0) for v in (max_area,max_span)):
        raise ValueError('Invalid motion/component limits')
    out=Path(out)
    if out.exists() and any(out.iterdir()): raise ValueError('Use a new or empty evidence directory')
    out.mkdir(parents=True,exist_ok=True)
    fingerprint=identity(source)
    cap=cv2.VideoCapture(str(source))
    if not cap.isOpened(): raise ValueError("Cannot open source")
    fps=cap.get(cv2.CAP_PROP_FPS); cap.set(cv2.CAP_PROP_POS_MSEC,max(0,start-.2)*1000)
    previous=None; records=[]; last_time=-1
    try:
        while True:
            ok,frame=cap.read()
            if not ok: break
            t=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
            if t>=end: break
            if not np.isfinite(t) or t<=last_time: raise ValueError("Decoder timestamps unreliable; use a PTS-aware extraction path")
            last_time=t
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            if previous is None: previous=gray; continue
            diff=cv2.absdiff(gray,previous); previous=gray
            if t<start: continue
            h,w=frame.shape[:2]
            pixel_scale=(w*h/(1920*1080))**.5
            x,y,rw,rh=roi if roi else (0,0,w,h)
            if x<0 or y<0 or rw<=0 or rh<=0 or x+rw>w or y+rh>h: raise ValueError("ROI outside source frame")
            candidates=[] if candidates_enabled else None
            counts={}
            marked=frame.copy()
            # Retain a small compression/quantization floor on low-resolution footage.
            area_limit=max_area if max_area is not None else max(64,190*pixel_scale**2)
            span_limit=max_span if max_span is not None else max(12,35*pixel_scale)
            if candidates_enabled:
                mask,counts=candidate_mask(frame,diff,(x,y,rw,rh),hsv_low,hsv_high,threshold)
                n,labels,stats,centres=cv2.connectedComponentsWithStats(mask)
                for j in range(1,n):
                    bx,by,bw,bh,area=stats[j];cx,cy=centres[j]
                    if 1<=area<=area_limit and bw<=span_limit and bh<=span_limit:
                        candidates.append([round(float(cx),2),round(float(cy),2),int(area)])
                        cv2.circle(marked,(round(cx),round(cy)),9,(0,160,255),1)
                counts.update(components=n-1,accepted=len(candidates),sizeRejected=n-1-len(candidates))
            name=f"{len(records):05d}"
            if not cv2.imwrite(str(out/(name+"-raw.png")),frame): raise ValueError('Cannot write raw frame')
            raw=frame[y:y+rh,x:x+rw];delta=cv2.cvtColor(cv2.convertScaleAbs(diff[y:y+rh,x:x+rw],alpha=4),cv2.COLOR_GRAY2BGR)
            annotated=marked[y:y+rh,x:x+rw]
            strip=np.hstack([raw,delta,annotated])
            scale=min(1,1800/strip.shape[1]);strip=cv2.resize(strip,(round(strip.shape[1]*scale),round(strip.shape[0]*scale)))
            bar=np.full((28,strip.shape[1],3),245,np.uint8)
            cv2.putText(bar,f"{t:.6f}s | raw / difference / candidates",(7,20),cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,0),1)
            if not cv2.imwrite(str(out/(name+"-compare.jpg")),np.vstack([bar,strip])): raise ValueError('Cannot write comparison')
            records.append({"timeSeconds":t,"decoderFrameIndex":round(cap.get(cv2.CAP_PROP_POS_FRAMES))-1,"raw":name+"-raw.png","comparison":name+"-compare.jpg","candidates":candidates,
                            "filterCounts":counts,"componentLimits":{"area":area_limit,"span":span_limit}})
    finally: cap.release()
    if not records: raise ValueError("No frames extracted")
    stat=Path(fingerprint['path']).stat()
    if (stat.st_size,stat.st_mtime_ns)!=(fingerprint['size'],fingerprint['mtimeNs']): raise ValueError('Source changed during extraction')
    manifest={"source":str(source),"sourceIdentity":fingerprint,"nominalFps":fps,"timestampSource":"decoder POS_MSEC, verify against source PTS for VFR","window":[start,end],"roi":roi,"candidatesAreNotVerdicts":True,"records":records,
              "visualReview":"not_performed","detector":{"enabled":candidates_enabled,"hsvLow":hsv_low,"hsvHigh":hsv_high,"motionThreshold":threshold,"maxArea":max_area,"maxSpan":max_span}}
    (out/"evidence.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("source");p.add_argument("start",type=float);p.add_argument("end",type=float);p.add_argument("output");p.add_argument("--roi",help="x,y,width,height")
    p.add_argument('--hsv-low',default='18,42,80');p.add_argument('--hsv-high',default='62,255,255')
    p.add_argument('--motion-threshold',type=float,default=12);p.add_argument('--max-area',type=float);p.add_argument('--max-span',type=float)
    p.add_argument('--no-candidates',action='store_true');a=p.parse_args()
    d=evidence(a.source,a.start,a.end,a.output,list(map(int,a.roi.split(","))) if a.roi else None,
               tuple(map(int,a.hsv_low.split(','))),tuple(map(int,a.hsv_high.split(','))),a.motion_threshold,
               not a.no_candidates,a.max_area,a.max_span)
    print(json.dumps({"frames":len(d["records"]),"output":a.output}))






