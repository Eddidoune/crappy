﻿# coding: utf-8

import cv2
import sys
import os
try:
  import SimpleITK as sitk
except ImportError:
  print("[Warning] SimpleITK is not installed, cannot save images!")

from ..tool.videoextenso import LostSpotError,Video_extenso as VE
from ..tool.videoextensoConfig import VE_config
from .masterblock import MasterBlock
from ..camera import Camera


class Video_extenso(MasterBlock):
  """
  Measure the deformation for the video of dots on the sample

  This requires the user to select the ROI to make the spot detection.
  Once done, it will return the deformation (in %) along X and Y axis.
  It also returns a list of tuples, which are the coordinates (in pixel)
  of the barycenters of the spots.
  Optionally, it can save images.
  Args:
    - camera ("str",default="XimeaCV"): The name of the camera class to use
    - save_folder (str or None, default=None): If given, the images will be
      saved in this folder.
    - save_period (int, default=1): If saving, will only save one out of
      save_period images.
    - labels (list, default=['t(s)', 'Coord(px)', 'Eyy(%)', 'Exx(%)']):
      The labels of the output
    - show_fps (bool default=False): If True, the block will print the FPS
      in the terminal every 2 seconds
    - stop (bool default=True): If True, the block will stop the Crappy
      program when the spots are lost, else it will just stop sending data

  """
  def __init__(self,**kwargs):
    MasterBlock.__init__(self)
    self.niceness = -5
    default_labels = ['t(s)', 'Coord(px)', 'Eyy(%)', 'Exx(%)']
    for arg,default in [("camera","XimeaCV"),
                        ("save_folder",None),
                        ("save_period",1),
                        ("labels",default_labels),
                        ("show_fps",True),
                        ("show_image",False),
                        ("wait_l0",False),
                        ("end",True),
                        ]:
      try:
        setattr(self,arg,kwargs[arg])
        del kwargs[arg]
      except KeyError:
        setattr(self,arg,default)
    self.ve_kwargs = {}
    for arg in ['white_spots','update_thresh','num_spots',
        'safe_mode','border','min_area']:
      if arg in kwargs:
        self.ve_kwargs[arg] = kwargs[arg]
        del kwargs[arg]
    self.cam_kwargs = kwargs

  def prepare(self):
    if self.save_folder and not os.path.exists(self.save_folder):
      try:
        os.makedirs(self.save_folder)
      except OSError:
        assert os.path.exists(self.save_folder),\
            "Error creating "+self.save_folder
    self.cam = Camera.classes[self.camera]()
    self.cam.open(**self.cam_kwargs)
    self.ve = VE(**self.ve_kwargs)
    config = VE_config(self.cam,self.ve)
    config.main()
    self.ve.start_tracking()
    if self.show_image:
      try:
        flags = cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO
      except AttributeError:
        flags = cv2.WINDOW_NORMAL
      cv2.namedWindow("Videoextenso",flags)
    self.loops = 0
    self.last_fps_print = 0
    self.last_fps_loops = 0

  def loop(self):
    self.loops += 1
    t,img = self.cam.read_image()
    if self.inputs and self.inputs[0].poll():
      self.inputs[0].clear()
      self.wait_l0 = False
      print("[VE block] resetting L0")
      self.ve.save_length()
    try:
      d = self.ve.get_def(img)
    except LostSpotError:
      print("[VE block] Lost spots, terminating")
      self.ve.stop_tracking()
      if self.end:
        raise
      else:
        self.loop = self.lost_loop
        return
    #print("DEBUG",self.ve.spot_list)
    if self.save_folder and not self.loops%self.save_period:
      self.save_img(t,img)
    if self.show_image:
      boxes = [r['bbox'] for r in self.ve.spot_list]
      for miny,minx,maxy,maxx in boxes:
        img[miny:miny+1,minx:maxx] = 255
        img[maxy:maxy+1,minx:maxx] = 255
        img[miny:maxy,minx:minx+1] = 255
        img[miny:maxy,maxx:maxx+1] = 255
      cv2.imshow("Videoextenso",img)
      cv2.waitKey(5)
    if self.show_fps:
      if t - self.last_fps_print > 2:
        sys.stdout.write("\rFPS: %.2f"%((self.loops - self.last_fps_loops)/
                              (t - self.last_fps_print)))
        sys.stdout.flush()
        self.last_fps_print = t
        self.last_fps_loops = self.loops

    centers = [(r['y'],r['x']) for r in self.ve.spot_list]
    if not self.wait_l0:
      self.send([t-self.t0,centers]+d)
    else:
      self.send([t-t0,[(0,0)]*4,0,0])

  def save_img(self,t,img):
    image = sitk.GetImageFromArray(img)
    sitk.WriteImage(image,
             self.save_folder + "img_%.6d_%.5f.tiff" % (
             self.loops, t-self.t0))

  def lost_loop(self):
    self.loops += 1
    t,img = self.cam.read_image()
    if self.save_folder and not self.loops%self.save_period:
      self.save_img(t,img)
    if self.show_image:
      cv2.imshow("Videoextenso",img)
      cv2.waitKey(5)

  def finish(self):
    self.ve.stop_tracking()
    if self.show_image:
      cv2.destroyAllWindows()
