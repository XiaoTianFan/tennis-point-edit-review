"""Validate human/agent observations; never infer pressure from movement or score."""

def validate_error_assessment(point):
    a=point['errorAssessment'];classification=a.get('classification')
    if classification not in ('UE','FE','unknown'):raise ValueError('Invalid error classification')
    if not a.get('reviewed') or not a.get('evidence') or not a.get('reason'):
        raise ValueError('Incoming-shot review and evidence required')
    if a.get('opponentPressure')!={'UE':'not_evidenced','FE':'imposed','unknown':'unclear'}[classification]:
        raise ValueError('Pressure assessment contradicts classification')
    if a.get('basis')!='incoming_ball_and_available_response':
        raise ValueError('Do not derive pressure from motion, score or result alone')
    expected='OTHER' if classification=='unknown' else classification
    if point['ending']!=expected or point.get('terminalError') is not True:
        raise ValueError('Point ending and error assessment conflict')
    return classification

def review_coverage(points):
    errors=[p for p in points if p.get('statsIncluded') is True and
            (p['ending'] in ('UE','FE') or (p['ending']=='OTHER' and p.get('terminalError') is True))]
    for p in errors:validate_error_assessment(p)
    return {'reviewedErrors':len(errors),'unclassifiedErrors':sum(p['ending']=='OTHER' for p in errors)}
