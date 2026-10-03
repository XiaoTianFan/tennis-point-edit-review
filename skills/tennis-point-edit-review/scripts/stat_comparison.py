"""Explicit per-metric direction; compare raw fractions, never rendered strings."""
from fractions import Fraction
from math import isfinite

LOWER={'doubleFaults','servePlusOneErrors','UE','FE'}
NEUTRAL={'errorNet','errorOut','errorMoving','errorStationary','ueMoving','ueStationary','deep','near','inside','netApproaches'}
HIGHER={'scoreGames','pointsWon','servicePointsWon','held','broken','breakSaved','breakConverted',
        'aces','firstServeIn','secondServeIn','firstServeWon','secondServeWon','servePlusOneWon',
        'fastestServeLaunchKph','firstServeMeanLaunchKph','secondServeMeanLaunchKph',
        'returnIn','returnFirstIn','returnSecondIn','returnFirstWon','returnSecondWon','returnWinners',
        'shortWinRate','mediumWinRate','longWinRate','winners','netWon'}

def direction(key):
    if key in LOWER:return 'lower'
    if key in NEUTRAL:return 'neutral'
    if key in HIGHER:return 'higher'
    raise ValueError('Define comparison semantics before adding a metric: '+key)

def number(v):
    if v is None:return None
    if isinstance(v,dict):
        n,d=v.get('numerator'),v.get('denominator')
        if n is None or d is None or d<=0:return None
        if n<0 or n>d:raise ValueError('Invalid rate')
        return Fraction(n,d)
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v):return None
    return Fraction(str(v))

def compare(key,a,b,display_a=None,display_b=None):
    rule=direction(key)
    if rule=='neutral':return None
    av,bv=number(a),number(b)
    if av is None or bv is None or av==bv:return None
    if display_a is not None and display_a==display_b:return None
    better_a=av>bv if rule=='higher' else av<bv
    return 'A' if better_a else 'B'
