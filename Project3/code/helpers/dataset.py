#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov 16 12:33:01 2021

@author: lidia
"""
import os
import shutil
import tempfile
import time
import matplotlib.pyplot as plt
import numpy as np
from monai.apps import DecathlonDataset
from monai.config import print_config
from monai.data import DataLoader#, decollate_batch
#from monai.handlers.utils import from_engine
from monai.losses import DiceLoss
from monai.inferers import sliding_window_inference
from monai.metrics import DiceMetric
from monai.networks.nets import SegResNet
from monai.transforms.utility.array import EnsureChannelFirst
from monai.transforms import (
    Resized,
    CropForegroundd,
    CropForeground,
    Activations,
    Activationsd,
    AsDiscrete,
    AsDiscreted,
    Compose,
    Invertd,
    LoadImaged,
    LoadImage,
    MapTransform,
    NormalizeIntensityd,
    Orientationd,
    RandFlipd,
    RandScaleIntensityd,
    RandShiftIntensityd,
    RandSpatialCropd,
    Spacingd,
    EnsureChannelFirstd,
    EnsureTyped,
    EnsureType,
    ConvertToMultiChannelBasedOnBratsClassesd
)
from monai.utils import set_determinism
import sys
from os.path import dirname, abspath



###############################################################################
# Configuration
###############################################################################

set_determinism(seed=43)
parent_dir = dirname(dirname(abspath(__file__)))
#root_dir = os.path.join(parent_dir, 'data', 'BraTs_decathlon', 'Task01_BrainTumour')
root_dir = '/home/lidia/CRAI-NAS/BraTS/BraTs_2016-17'
print(root_dir)

###############################################################################
# Convert labels
###############################################################################

class ConvertToMultiChannelBasedOnBratsClassesd(MapTransform):
    """
    Convert labels to multi channels based on brats classes:
    label 1 is the peritumoral edema
    label 2 is the GD-enhancing tumor
    label 3 is the necrotic and non-enhancing tumor core
    The possible classes are TC (Tumor core), WT (Whole tumor)
    and ET (Enhancing tumor).

    """

    def __call__(self, data):
        d = dict(data)
        for key in self.keys:
            result = []
            # merge label 2 and label 3 to construct TC
            result.append(np.logical_or(d[key] == 2, d[key] == 3))
            # merge labels 1, 2 and 3 to construct WT
            result.append(
                np.logical_or(
                    np.logical_or(d[key] == 2, d[key] == 3), d[key] == 1
                )
            )
            # label 2 is ET
            result.append(d[key] == 2)
            d[key] = np.stack(result, axis=0).astype(np.float32)
        return d
  
###############################################################################
# Define Transforms
###############################################################################
    


train_transform = Compose(
    [
        # load 4 Nifti images and stack them together
        LoadImaged(keys=["image", "label"]),
        EnsureChannelFirstd(keys="image"),
        ConvertToMultiChannelBasedOnBratsClassesd(keys="label"),
        CropForegroundd(keys=["image", "label"], source_key="image"),
        
        Resized(keys=["image", "label"], spatial_size=(224, 224, 144), 
                mode=["trilinear", "nearest"]),
        Orientationd(keys=["image", "label"], axcodes="RAS"),
        RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=0),
        RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=1),
        #RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=2),
        NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True),
        #RandScaleIntensityd(keys="image", factors=0.1, prob=1.0),
        #RandShiftIntensityd(keys="image", offsets=0.1, prob=1.0),
        EnsureTyped(keys=["image", "label"], data_type='tensor'),
    ]
)
val_transform = Compose(
    [
        LoadImaged(keys=["image", "label"]),
        EnsureChannelFirstd(keys="image"),
        ConvertToMultiChannelBasedOnBratsClassesd(keys="label"),
        CropForegroundd(keys=["image", "label"], source_key="image"),
        
        Resized(keys=["image", "label"], spatial_size=(224, 224, 144), 
                mode=["trilinear", "nearest"]),
        Orientationd(keys=["image", "label"], axcodes="RAS"),
        NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True),
        EnsureTyped(keys=["image", "label"], data_type='tensor'),
    ]
)



# train_transform = Compose(
#     [
#      LoadImaged(keys=["image", "label"]),
#      EnsureChannelFirstd(keys="image"),
#      Orientationd(keys=["image", "label"], axcodes="RAS"),
#      CropForegroundd(keys=["image", "label"], source_key="image"),
#     ]
# )
# train_transform = Compose(
#     [
#         # load 4 Nifti images and stack them together
#         LoadImaged(keys=["image", "label"]),
#         EnsureChannelFirstd(keys="image"),
#         ConvertToMultiChannelBasedOnBratsClassesd(keys="label"),
#         Spacingd(
#             keys=["image", "label"],
#             pixdim=(1.0, 1.0, 1.0),
#             mode=("bilinear", "nearest"),
#         ),
#         Orientationd(keys=["image", "label"], axcodes="RAS"),
#         RandSpatialCropd(keys=["image", "label"], roi_size=[224, 224, 144], random_size=False),
#         RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=0),
#         RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=1),
#         RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=2),
#         NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True),
#         RandScaleIntensityd(keys="image", factors=0.1, prob=1.0),
#         RandShiftIntensityd(keys="image", offsets=0.1, prob=1.0),
#         EnsureTyped(keys=["image", "label"]),
#     ]
# )

###############################################################################
# Load Data
###############################################################################

# Import dataset
# here we don't cache any data in case out of memory issue
train_ds = DecathlonDataset(
    root_dir=root_dir,
    task="Task01_BrainTumour",
    transform=train_transform,
    section="training",
    download=False,
    cache_rate=0.0,
    num_workers=4,
)

train_loader = DataLoader(train_ds, batch_size=1, shuffle=True, num_workers=4)
val_ds = DecathlonDataset(
    root_dir=root_dir,
    task="Task01_BrainTumour",
    transform=val_transform,
    section="validation",
    download=False,
    cache_rate=0.0,
    num_workers=4,
)
val_loader = DataLoader(val_ds, batch_size=1, shuffle=False, num_workers=4)


###############################################################################
# Visualize
###############################################################################

# pick one image from DecathlonDataset to visualize and check the 4 channels
print(f"image shape: {train_ds[2]['image'].shape}")
plt.figure("image", (24, 6))
for i in range(4):
    plt.subplot(1, 4, i + 1)
    plt.title(f"image channel {i}")
    plt.imshow(train_ds[2]["image"][i, :, :, 60].detach().cpu(), cmap="gray")
plt.show()
# also visualize the 3 channels label corresponding to this image
print(f"label shape: {train_ds[2]['label'].shape}")
plt.figure("label", (18, 6))
for i in range(3):
    plt.subplot(1, 3, i + 1)
    plt.title(f"label channel {i}")
    plt.imshow(train_ds[2]["label"][i,:, :, 60].detach().cpu())
plt.show()

#check out: https://github.com/cv-lee/BraTs/blob/master/pytorch/dataset.py 
#https://github.com/Project-MONAI/tutorials/blob/master/3d_segmentation/brats_segmentation_3d.ipynb
