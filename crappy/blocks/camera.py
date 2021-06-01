# coding: utf-8

from sys import platform
import os
try:
  import SimpleITK as Sitk
except ImportError:
  Sitk = None
try:
  import PIL
except ImportError:
  PIL = None


from .block import Block
from ..camera import camera_list
from ..tool import Camera_config
from .._global import OptionalModule

try:
  import cv2
except (ModuleNotFoundError, ImportError):
  cv2 = OptionalModule("opencv-python")

kw = dict([
  ("save_folder", None),
  ("verbose", False),
  ("labels", ['t(s)', 'frame']),
  ("fps_label", False),
  ("img_name", "{self.loops:06d}_{t-self.t0:.6f}"),
  ("ext", "tiff"),
  ("save_period", 1),
  ("save_backend", None),
  ("transform", None),
  ("input_label", None),
  ("config", True)]
)


class Camera(Block):
  """
  Read images from a camera object, save and/or send them to another block.

  Note:
    It can be triggered by an other block, internally,
    or try to run at a given framerate.

  Kwargs:
    - camera (str, {"Ximea","Jai","Webcam",...}, mandatory): See
      crappy.camera.MasterCam.classes for a full list.
    - save_folder (str or None, default: None): directory to save the images.

      Note:
        It will be created if necessary.

        If None, it will not save the images.

    - verbose (bool, default: False): If True, the block will print the number
      of loops/s.
    - labels (list of strings, default: ['t(s)', 'frame']): The labels for
      respectively time and the frame.
    - fps_label: If set, self.max_fps will be set to the value received by
      the block with this label.
    - img_name (string, default: "{self.loops:06d}_{t-self.t0:.6f}"): Template
      for the name of the image to save.

      Note:
        It will be evaluated as a f-string.

    - ext (str, default: "tiff"): Extension of the image.

      Warning!
        Make sure it is supported by the image saving backend.

    - save_period (int, default: 1): Will save only one in x images.
    - save_backend (str, default: None): module to use to save the images
      supported backends: sitk (SimpleITK), cv2 (OpenCV).

      Note:
        If None will try sitk, else cv2.

    - transform (func or None, default: None): Function to be applied on the
      image before sending.

      Warning!
        It will NOT be applied to the saved image.

    - input_label (str or None, default: None): If specified, the image will
      not be read from a camera object but from this label

    - config (bool, default: True): Show the popup for config ?

  """

  def __init__(self,  camera, **kwargs):
    Block.__init__(self)
    self.niceness = -10
    for arg, default in kw.items():
      setattr(self, arg, kwargs.get(arg, default))  # Assign these attributes
      try:
        del kwargs[arg]
        # And remove them (if any) to
        # keep the parameters for the camera
      except KeyError:
        pass
    self.camera_name = camera.capitalize()
    self.cam_kw = kwargs
    assert self.camera_name in camera_list or self.input_label,\
        "{} camera does not exist!".format(self.camera_name)
    if self.save_backend is None:
      if Sitk is None:
        self.save_backend = "cv2"
      else:
        self.save_backend = "sitk"
    assert self.save_backend in ["cv2", "sitk", "pil"],\
        "Unknown saving backend: " + self.save_backend
    self.save = getattr(self, "save_" + self.save_backend)
    self.loops = 0
    self.t0 = 0

  def prepare(self, send_img=True):
    sep = '\\' if 'win' in platform else '/'
    if self.save_folder and not self.save_folder.endswith(sep):
      self.save_folder += sep
    if self.save_folder and not os.path.exists(self.save_folder):
      try:
        os.makedirs(self.save_folder)
      except OSError:
        assert os.path.exists(self.save_folder),\
            "Error creating " + self.save_folder
    self.ext_trigger = bool(
        self.inputs and not (self.fps_label or self.input_label))
    if self.input_label is not None:
      # Exception to the usual inner working of Crappy:
      # We receive data from the link BEFORE the program is started
      self.ref_img = self.inputs[0].recv()[self.input_label]
      self.camera = camera_list['Camera']()
      self.camera.max_fps = 30
      self.camera.get_image = lambda: (0, self.ref_img)
      return
    self.camera = camera_list[self.camera_name]()
    self.camera.open(**self.cam_kw)
    if self.config:
      conf = Camera_config(self.camera)
      conf.main()
    # Sending the first image before the actual start
    if send_img:
      t, img = self.get_img()
      self.send([0, img])

  @staticmethod
  def save_sitk(img, fname):
    image = Sitk.GetImageFromArray(img)
    Sitk.WriteImage(image, fname)

  @staticmethod
  def save_cv2(img, fname):
    cv2.imwrite(fname, img)

  @staticmethod
  def save_pil(img, fname):
    PIL.Image.fromarray(img).save(fname)

  def get_img(self):
    """
    Waits the appropriate time/event to read an image, reads it,
    saves it if asked to, applies the transformation and increases counter.
    """

    if self.input_label:
      data = self.inputs[0].recv()
      return data['t(s)']+self.t0, data[self.input_label]
    if not self.ext_trigger:
      if self.fps_label:
        while self.inputs[0].poll():
          self.camera.max_fps = self.inputs[0].recv()[self.fps_label]
      t, img = self.camera.read_image()  # NOT constrained to max_fps
    else:
      data = self.inputs[0].recv()  # wait for a signal
      if data is None:
        return
      t, img = self.camera.get_image()  # self limiting to max_fps
    self.loops += 1
    if self.save_folder and self.loops % self.save_period == 0:
      self.save(img, self.save_folder +
          eval('f"{}"'.format(self.img_name)) + f".{self.ext}")
    if self.transform:
      img = self.transform(img)
    return t, img

  def loop(self):
    t, img = self.get_img()
    self.send([t-self.t0, img])

  def finish(self):
    if self.input_label is None:
      self.camera.close()
