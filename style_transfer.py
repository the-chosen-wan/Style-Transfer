# -*- coding: utf-8 -*-
"""style_transfer.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1TLX3JQsF8uShdxFZ4EmNzDDwyNfIEd8Q
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision
import torchvision.transforms as transforms
import numpy as np
from scipy.ndimage.interpolation import map_coordinates
from scipy.ndimage.filters import gaussian_filter
from torch.utils.data import Dataset, DataLoader
import random
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(device)
import os
import math
from PIL import Image
import matplotlib.pyplot as plt
os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
from torchvision import models
from google.colab import drive
from torchsummary import summary
drive.mount('/content/drive',force_remount=True)

imsize = 512
loader = transforms.Compose([transforms.Resize(imsize),transforms.ToTensor()])
unloader = transforms.ToPILImage()

def load(path):
  im = Image.open(path)
  im = loader(im).unsqueeze(0)
  return im.to(device,torch.float)

def show(tensor):
  im = tensor.detach().cpu().clone()
  im = im.squeeze(0)
  im = unloader(im)
  plt.imshow(im)

class Content(nn.Module):
  def __init__(self,tensor):
    super().__init__()
    self.target = tensor.detach()
  
  def forward(self,x):
    self.loss=nn.MSELoss()(x,self.target)
    return x

def GramMatrix(tensor):
  a,b,c,d = tensor.shape
  tensor = tensor.view(a*b,c*d)
  tensor = torch.matmul(tensor,tensor.t())
  return tensor.div(a*b*c*d)

class Style(nn.Module):
  def __init__(self,tensor):
    super().__init__()
    self.target = GramMatrix(tensor.detach())
  
  def forward(self,x):
    self.loss=nn.MSELoss()(GramMatrix(x),self.target)
    return x

cnn = models.vgg19(pretrained=True).features.to(device).eval()
cnn_normalization_mean = torch.tensor([0.485, 0.456, 0.406]).to(device)
cnn_normalization_std = torch.tensor([0.229, 0.224, 0.225]).to(device)

class Norm(nn.Module):
  def __init__(self,mean,std):
    super().__init__()
    self.mean = mean.view(-1,1,1)
    self.std = std.view(-1,1,1)
  
  def forward(self,x):
    return (x-self.mean)/self.std

content=['conv_4','conv_5']
style = ['conv_1','conv_2','conv_3','conv_4','conv_5']

def model_losses(cnn,content_img,style_img,mean,std):
  normalization = Norm(mean,std).to(device)
  model = nn.Sequential(normalization)
  content_loss = []
  style_loss = []

  i=0
  for layer in cnn.children():
    if isinstance(layer,nn.Conv2d):
      i+=1
      name = 'conv_{}'.format(i)
    
    elif isinstance(layer,nn.ReLU):
      name = 'relu_{}'.format(i)
      layer = nn.ReLU(inplace=False)

    elif isinstance(layer,nn.MaxPool2d):
      name = 'pool_{}'.format(i)
    elif isinstance(layer,nn.BatchNorm2d):
      name = 'bn_{}'.format(i)
    
    model.add_module(name,layer)
    if name in content:
      target = model(content_img).detach()
      loss = Content(target)
      model.add_module('content_loss_{}'.format(i),loss)
      content_loss.append(loss)
    
    if name in style:
      target = model(style_img).detach()
      loss = Style(target)
      model.add_module('style_loss_{}'.format(i),loss)
      style_loss.append(loss)

    for i in range(len(model) - 1, -1, -1):
        if isinstance(model[i], Content) or isinstance(model[i], Style):
            break

    model = model[:(i + 1)]

    return model, style_loss, content_loss

def get_optimizer(input_img):
  optim = torch.optim.Adam([input_img],lr=0.0001)
  return optim

def run_style_transfer(cnn,mean,std,content_path,style_path,input_path,num_path=50000,style_weight=1e6,content_weight=100):
  content_img = load(content_path)
  style_img = load(style_path)
  input_img = load(input_path)
  model,style_loss,content_loss = model_losses(cnn,content_img,style_img,mean,std)
  input_img.requires_grad_(True)
  model.requires_grad_(False)

  optim = get_optimizer(input_img)
  run = 0

  while run<=num_path:
    with torch.no_grad():
      input_img.clamp_(0, 1)
    
    optim.zero_grad()
    model(input_img)
    style = 0
    content = 0

    for sl in style_loss:
      style+=sl.loss
    for cl in content_loss:
      content+=cl.loss
    
    style*=style_weight
    content*=content_weight
    total = style+content
    total.backward()
    optim.step()
    run+=1
    if run%10000==0:
      print(run)
  with torch.no_grad():
    input_img.clamp_(0, 1)

  return input_img

content_path = "/content/drive/My Drive/DeepFake/train/real/real00000.jpg"
style_path = "/content/drive/My Drive/starrynight.jpg"
out = run_style_transfer(cnn,cnn_normalization_mean,cnn_normalization_std,content_path,style_path,content_path)

show(out)

