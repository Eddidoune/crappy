#coding: utf-8


from time import time

from .path import Path


class Ramp(Path):
  """
  Will make a ramp from previous value until condition is reached,

  Args:
    - speed (in unit/s): The speed of the ramp.
    - condition (str): Representing the condition to end this path.
      See Path.parse_condition for more detail.
    - cmd: If specified, will be the starting value of the ramp.

  """
  def __init__(self,time,cmd,condition,speed):
    Path.__init__(self,time,cmd)
    self.condition = self.parse_condition(condition)
    self.speed = speed

  def get_cmd(self,data):
    if self.condition(data):
      raise StopIteration
    return (time() - self.t0)*self.speed+self.cmd
