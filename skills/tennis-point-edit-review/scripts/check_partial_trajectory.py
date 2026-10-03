"""Known synthetic camera/physics tests; not validation of real single-camera accuracy."""
import unittest
try:
    import numpy as np
    from partial_trajectory import acceleration,simulate,project,fit_partial,alternating_holdouts
    AVAILABLE=True
except ImportError:AVAILABLE=False

@unittest.skipUnless(AVAILABLE,'Optional NumPy/SciPy dependency unavailable')
class PartialChecks(unittest.TestCase):
    def setup_case(self):
        self.camera=np.array([[900,960,0,5760],[0,540,-900,5040],[0,1,0,6]],float)
        self.state=np.array([-.5,0.,2.7,2.,27.,-2.])
        self.times=np.linspace(.025,.5,24)
        self.obs=np.c_[self.times,project(self.state,self.times,self.camera)]
        self.options=dict(contact_seconds=0.,initial_state=[0.,0.,2.65,1.,24.,-1.],bounds=([-2,-.5,2,-10,10,-10],[2,.5,3.5,10,50,10]),priors=[{'index':1,'mean':0.,'sigma':.05},{'index':2,'mean':2.7,'sigma':.05}],collision_lower_seconds=.55)
    def test_no_drag_ballistics(self):
        q=simulate([0,0,3,10,20,2],[.1,.5],drag=0)
        np.testing.assert_allclose(q[-1,:3],[5,10,3+1-9.81*.25/2],atol=1e-6)
    def test_spin_force_is_perpendicular(self):
        v=np.array([5.,25.,-2.]);a=acceleration(v,drag=0,lift_vector=(0,.004,0),gravity=0)
        self.assertAlmostEqual(float(a@v),0.,places=9)
    def test_inverse_recovers_known_synthetic_speed(self):
        self.setup_case();r=fit_partial(self.obs,self.camera,**self.options)
        self.assertTrue(r['converged']);self.assertFalse(r['fitAtParameterBoundary'])
        self.assertAlmostEqual(r['launchSpeedKphEstimate'],np.linalg.norm(self.state[3:])*3.6,delta=.15)
        self.assertLess(r['rmsPixels'],.03);self.assertFalse(r['qualityAccepted'])
    def test_alternating_frames_predict_unseen_pixels(self):
        self.setup_case();h=alternating_holdouts(self.obs,self.camera,**self.options)
        self.assertEqual(len(h),2)
        self.assertTrue(all(x['heldOutRmsPixels']<.05 for x in h))
    def test_post_impact_frames_rejected(self):
        self.setup_case();self.options['collision_lower_seconds']=.4
        with self.assertRaises(ValueError):fit_partial(self.obs,self.camera,**self.options)
    def test_bad_camera_and_duplicate_times_rejected(self):
        self.setup_case()
        with self.assertRaises(ValueError):project(self.state,self.times,np.zeros((3,4)))
        self.obs[2,0]=self.obs[1,0]
        with self.assertRaises(ValueError):fit_partial(self.obs,self.camera,**self.options)

if __name__=='__main__':unittest.main()
