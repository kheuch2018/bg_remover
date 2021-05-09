# -*- coding: utf-8 -*-
"""bgRemover.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1nPc8l9I02e0JNZ4O5gwjKQDzK_2oKygv
"""

# install dependencies: 
import torch, torchvision
print(torch.__version__, torch.cuda.is_available())
# opencv is pre-installed on colab

# install detectron2: (Colab has CUDA 10.1 + torch 1.8)
# See https://detectron2.readthedocs.io/tutorials/install.html for instructions
import torch
assert torch.__version__.startswith("1.8")   # need to manually install torch 1.8 if Colab changes its default version
# exit(0)  # After installation, you need to "restart runtime" in Colab. This line can also restart runtime

# Some basic setup:
# Setup detectron2 logger
import math
import detectron2
from detectron2.utils.logger import setup_logger

# import some common libraries
import numpy as np
import os, json, cv2, random

# import some common detectron2 utilities
from detectron2 import model_zoo
from detectron2.engine import DefaultPredictor
from detectron2.config import get_cfg
from detectron2.utils.visualizer import Visualizer
from detectron2.data import MetadataCatalog, DatasetCatalog

import cv2
from PIL import Image
import pickle

def read_im(img_path):
  im = cv2.imread(img_path)
  return im

cfg = get_cfg()
# add project-specific config (e.g., TensorMask) here if you're not running a model in detectron2's core library
cfg.merge_from_file(model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.5  # set threshold for this model
# Find a model from detectron2's model zoo. You can use the https://dl.fbaipublicfiles... url as well
cfg.MODEL.WEIGHTS = model_zoo.get_checkpoint_url("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml")
predictor = DefaultPredictor(cfg)
# outputs = predictor(read_im("./cat.jpeg"))

def get_cropped_leaf(img,predictor,return_mapping=False,resize=None):
    #convert to numpy    
    img = np.array(img)[:,:,::-1]
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    
    #get prediction
    outputs = predictor(img)
    
    #get boxes and masks
    ins = outputs["instances"]
    pred_masks = ins.get_fields()["pred_masks"]
    boxes = ins.get_fields()["pred_boxes"]    
    
    #get main leaf mask if the area is >= the mean area of boxes and is closes to the centre 
    
    masker = pred_masks[np.argmin([calculateDistance(x[0], x[1], int(img.shape[1]/2), int(img.shape[0]/2)) for i,x in enumerate(boxes.get_centers()) if (boxes[i].area()>=torch.mean(boxes.area()).to("cpu")).item()])].to("cpu").numpy().astype(np.uint8)

    #mask image
    mask_out = cv2.bitwise_and(img, img, mask=masker)
    
    #find contours and boxes
    contours, hierarchy = cv2.findContours(masker.copy() ,cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contour = contours[np.argmax([cv2.contourArea(x) for x in contours])]
    rotrect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rotrect)
    box = np.int0(box)
    

    #crop image
    cropped = get_cropped(rotrect,box,mask_out)

    #resize
    rotated = MakeLandscape()(Image.fromarray(cropped))
    
    if not resize == None:
        resized = ResizeMe((resize[0],resize[1]))(rotated)
    else:
        resized = rotated
        
    if return_mapping:
        img = cv2.drawContours(img, [box], 0, (0,0,255), 10)
        img = cv2.drawContours(img, contours, -1, (255,150,), 10)
        return resized, ResizeMe((int(resize[0]),int(resize[1])))(Image.fromarray(img))
    
    return resized

#function to crop the image to boxand rotate

def get_cropped(rotrect,box,image):
    
    width = int(rotrect[1][0])
    height = int(rotrect[1][1])

    src_pts = box.astype("float32")
    # corrdinate of the points in box points after the rectangle has been
    # straightened
    dst_pts = np.array([[0, height-1],
                        [0, 0],
                        [width-1, 0],
                        [width-1, height-1]], dtype="float32")

    # the perspective transformation matrix
    M = cv2.getPerspectiveTransform(src_pts, dst_pts)

    # directly warp the rotated rectangle to get the straightened rectangle
    warped = cv2.warpPerspective(image, M, (width, height))
    return warped

def calculateDistance(x1,y1,x2,y2):  
    dist = math.hypot(x2 - x1, y2 - y1)
    return dist  
#image manipulations 

class ResizeMe(object):
    #resize and center image in desired size 
    def __init__(self,desired_size):
        
        self.desired_size = desired_size
        
    def __call__(self,img):
    
        img = np.array(img).astype(np.uint8)
        
        desired_ratio = self.desired_size[1] / self.desired_size[0]
        actual_ratio = img.shape[0] / img.shape[1]

        desired_ratio1 = self.desired_size[0] / self.desired_size[1]
        actual_ratio1 = img.shape[1] / img.shape[0]

        if desired_ratio < actual_ratio:
            img = cv2.resize(img,(int(self.desired_size[1]*actual_ratio1),self.desired_size[1]),None,interpolation=cv2.INTER_AREA)
        elif desired_ratio > actual_ratio:
            img = cv2.resize(img,(self.desired_size[0],int(self.desired_size[0]*actual_ratio)),None,interpolation=cv2.INTER_AREA)
        else:
            img = cv2.resize(img,(self.desired_size[0], self.desired_size[1]),None, interpolation=cv2.INTER_AREA)
            
        h, w, _ = img.shape

        new_img = np.zeros((self.desired_size[1],self.desired_size[0],3))
        
        hh, ww, _ = new_img.shape

        yoff = int((hh-h)/2)
        xoff = int((ww-w)/2)
        
        new_img[yoff:yoff+h, xoff:xoff+w,:] = img

        
        return Image.fromarray(new_img.astype(np.uint8))

class MakeLandscape():
    #flip if needed
    def __init__(self):
        pass
    def __call__(self,img):
        
        if img.height> img.width:
            img = np.array(img)
            img = Image.fromarray(img)
            img.save("black.jpeg")

        return img

def img_with_black_bg(image_path):
  img, img1 = get_cropped_leaf(Image.open(image_path),predictor,return_mapping=True,resize = (512,int(512*.7)))
  img.save('black.png')
  return img

def remove_bg(filepath,output_name):
  src = cv2.imread(filepath, 1)
  tmp = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY)
  _,alpha = cv2.threshold(tmp,0,255,cv2.THRESH_BINARY)
  b, g, r = cv2.split(src)
  rgba = [b,g,r, alpha]
  dst = cv2.merge(rgba,4)
  # dst = cv2.rotate(dst, cv2.ROTATE_90_COUNTERCLOCKWISE)
  cv2.imwrite(output_name, dst)
  return dst

# !wget -O "cat.jpeg" "https://post.greatist.com/wp-content/uploads/2020/08/3180-Pug_green_grass-1200x628-FACEBOOK-1200x628.jpg"


# from IPython.display import Image
# Image('last.png')

# !pip freeze > model_req.txt


app = Flask(__name__)

@app.route('/')
def remove_bg():
    black = img_with_black_bg("./cat.jpeg")

    last = remove_bg("./black.png","last.png")

    return 'Hello, World!'