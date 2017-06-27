#coding: utf-8
from __future__ import print_function

from time import time

from .actuator import Actuator

class Fake_motor(Actuator):
  def __init__(self,**kwargs):
    for arg,default in [("inertia",.5), # Inertia of the motor
                        ("torque",0), # Counter torque on the axis
                        ("kv",1000), # t/min/V
                        ("rv",.4), # Solid friction
                        ("fv",2e-5), # Fluid friction
                        ]:
      setattr(self,arg,kwargs.pop(arg,default))
    assert not kwargs,"Fake_motor got invalid kwarg(s): "+str(kwargs)

  def open(self):
    self.rpm = 0
    self.pos = 0
    self.u = 0 # V
    self.t = time()

  def stop(self):
    self.set_speed(0)

  def close(self):
    pass

  def update(self):
    """
    Will update the motor rpm
    Supposes u is constant for the interval dt
    """
    t1 = time()
    dt = t1-self.t
    self.t = t1
    F = self.u*self.kv-self.torque-self.rpm*(1+self.rv+self.rpm*self.fv)
    drpm = F/self.inertia*dt
    self.pos += dt*(self.rpm+drpm/2)
    self.rpm += drpm

  def get_speed(self):
    """
    Return the motor speed (rpm)
    """
    self.update()
    return self.rpm

  def get_pos(self):
    """
    Returns the motor position
    """
    self.update()
    return self.pos

  def set_speed(self,u):
    """
    Sets the motor cmd in volts
    """
    self.update()
    self.u = u