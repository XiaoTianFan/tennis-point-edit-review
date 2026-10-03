"""Classify an already observed single point's service sequence; no vision/scoring inference."""
import copy

NON_CONTACT = frozenset(('toss_catch', 'aborted_toss', 'practice_swing', 'serve_miss'))

def audit_attempts(events, initial_serve=1):
    """Explicit observations only. A missed service swing is a fault, but has no speed.

    Inputs: unique eventId, kind (serve/serve_miss/toss_catch/aborted_toss/
    practice_swing); serve additionally needs outcome=in/fault/let.
    Called separately per point. Stops at a serve in or a second fault.
    """
    if type(initial_serve) is not int or initial_serve not in (1, 2):
        raise ValueError('Resolve the starting serve opportunity')
    number=initial_serve;closed=False;seen=set();out=[]
    for event in events:
        key=event['eventId'];kind=event['kind']
        if not isinstance(key,str) or not key or key in seen:
            raise ValueError('Unique non-empty actual event IDs required')
        if closed:raise ValueError('Point service sequence already finished')
        seen.add(key)
        if kind not in NON_CONTACT | {'serve'}:raise ValueError('Unresolved event kind')
        r=copy.deepcopy(event)
        contact=kind=='serve'
        result=event.get('outcome') if contact else ('fault' if kind=='serve_miss' else None)
        if contact and result not in ('in','fault','let'):raise ValueError('Resolve serve outcome')
        if not contact and event.get('outcome') not in (None,result):
            raise ValueError('Non-contact outcome conflicts with event classification')
        fault=result=='fault';double=fault and number==2
        r.update(serveNumber=number,eventType='let' if result=='let' else kind,
                 actualContact=contact,speedApplicable=contact,
                 countsAsServeOpportunity=result in ('in','fault'),
                 serviceFault=fault,doubleFault=double,
                 included=contact and result!='let')
        if not contact:r['launchSpeedKphEstimate']=None
        closed=double or result=='in'
        r['serviceSequenceEnded']=closed
        if fault and number==1:number=2
        out.append(r)
    return out

def require_speed_eligible(record):
    """Reject contradictory included records; excluded misses may keep a null speed."""
    if not record.get('included',True):return False
    if record.get('eventType') in NON_CONTACT or record.get('speedApplicable') is False:
        raise ValueError('Exclude non-contact attempts from speed, retaining scoring opportunities separately')
    if record.get('eventType')=='let' and record.get('includeLetsInSpeedScope') is not True:
        raise ValueError('Let-speed inclusion requires an explicit alternative statistical scope')
    if record.get('method')=='partial_trajectory_model' and record.get('qualityAccepted') is not True:
        raise ValueError('Partial-trajectory candidate must pass evidence and stability screening before aggregation')
    return True
