#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec  2 14:12:47 2021

@author: lidia
"""

import warnings
warnings.filterwarnings("ignore") 

# I need to use this to get past "RuntimeError: received 0 items of ancdata" 
# while training, which would pop up at seemingly random epochs. This is 
# probably hardware dependent, so might not be needed in other builds.  
import resource
rlimit = resource.getrlimit(resource.RLIMIT_NOFILE)
resource.setrlimit(resource.RLIMIT_NOFILE, (2048, rlimit[1]))

import os
import time
import matplotlib.pyplot as plt
import numpy as np
from monai.apps import DecathlonDataset
from monai.data import DataLoader, decollate_batch
from monai.losses import DiceLoss
from monai.metrics import DiceMetric
from monai.networks.nets import DynUNet
from monai.transforms import (
    Resized,
    CropForegroundd,
    Activations,
    AsDiscrete,
    Compose,
    LoadImaged,
    NormalizeIntensityd,
    Orientationd,
    RandFlipd,
    RandScaleIntensityd,
    RandShiftIntensityd,
    SpatialPadd,
    EnsureChannelFirstd,
    EnsureTyped,
    EnsureType,
    RandAffined,
)
from monai.utils import set_determinism
import torch
import pickle
from transform import ConvertToMultiChannelBasedOnBratsClassesd

"""
Set up a UNet segmentation model and train. Validation is done after each batch.
The current best model is automatically saved. 
To use: Set the path to the training and test data, where to save the trained
model and where to save the figures to. Choose learning rate and whether to 
use augmentation.

"""


###############################################################################
# Configuration of paths and model
###############################################################################

set_determinism(seed=42)

data_dir = '/home/lidia/CRAI-NAS/BraTS/BraTs_2016-17'
model_dir = '/mnt/CRAI-NAS/all/lidfer/Segmentering/saved_models/DynUnet_2deepsup_1e3'
save_figures = "/home/lidia/Projects/fys-stk4155/Project3/figures"

lr = 5e-4
augmentation = False 


###############################################################################
# Define Transforms
###############################################################################
    
# Tranform used on data before training WITHOUT augmentation
train_transform_without = Compose([
        # Load images, set first dim to channel, resize and normalize
        LoadImaged(keys=["image", "label"]),
        EnsureChannelFirstd(keys="image"),
        ConvertToMultiChannelBasedOnBratsClassesd(keys="label"),
        Orientationd(keys=["image", "label"], axcodes="RAS"),
        CropForegroundd(keys=["image", "label"], source_key="image"),
        SpatialPadd(keys=["image", "label"], spatial_size=(128,128,128)),
        Resized(keys=["image", "label"], spatial_size=(128,128,128), align_corners=[False,None],
                mode=["trilinear", "nearest"]),
        NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True),
        # Convert to tensor
        EnsureTyped(keys=["image", "label"], data_type='tensor'),
    ])

# Tranform used on data before training WITH augmentation
train_transform_with = Compose([
        # Load images, set first dim to channel, resize and normalize
        LoadImaged(keys=["image", "label"]),
        EnsureChannelFirstd(keys="image"),
        ConvertToMultiChannelBasedOnBratsClassesd(keys="label"),
        Orientationd(keys=["image", "label"], axcodes="RAS"),
        CropForegroundd(keys=["image", "label"], source_key="image"),
        SpatialPadd(keys=["image", "label"], spatial_size=(128,128,128)),
        Resized(keys=["image", "label"], spatial_size=(128,128,128), align_corners=[False,None],
                mode=["trilinear", "nearest"]),
        NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True),
        
        # Data augmentation
        RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=0),
        RandFlipd(keys=["image", "label"], prob=0.5, spatial_axis=1),
        RandScaleIntensityd(keys="image", factors=(-0.1, 0.1), prob=1.0),
        RandShiftIntensityd(keys="image", offsets=(-0.1, 0.1), prob=1.0),
        RandAffined(keys=["image", "label"], prob=1, 
                    rotate_range=(0,0,np.pi),
                    shear_range=(0.2,0.2),
                    padding_mode ='zeros'),
        
        # Convert to tensor
        EnsureTyped(keys=["image", "label"], data_type='tensor'),
    ])

# Tranform used on data before validation (does not include augmentation)
val_transform = Compose([       
        # Load images, set first dim to channel, resize and normalize
        LoadImaged(keys=["image", "label"]),
        EnsureChannelFirstd(keys="image"),
        ConvertToMultiChannelBasedOnBratsClassesd(keys="label"),
        Orientationd(keys=["image", "label"], axcodes="RAS"),
        CropForegroundd(keys=["image", "label"], source_key="image"),
        SpatialPadd(keys=["image", "label"], spatial_size=(128,128,128)),
        Resized(keys=["image", "label"], spatial_size=(128,128,128), align_corners=[False,None],
                mode=["trilinear", "nearest"]),
        NormalizeIntensityd(keys="image", nonzero=True, channel_wise=True),
        
        # Convert to tensor
        EnsureTyped(keys=["image", "label"], data_type='tensor'),
    ])


###############################################################################
# Load Data
###############################################################################

# Import train and test datasets

if augmentation: 
    transform = train_transform_with
else: 
    transform = train_transform_without
    
train_ds = DecathlonDataset(
    root_dir=data_dir,
    task="Task01_BrainTumour",
    transform=transform,
    section="training",
    download=False,
    cache_rate=0.0,
    num_workers=4,
)

val_ds = DecathlonDataset(
    root_dir=data_dir,
    task="Task01_BrainTumour",
    transform=val_transform,
    section="validation",
    download=False,
    cache_rate=0.0,
    num_workers=4,
)

# Make loaders
train_loader = DataLoader(train_ds, batch_size=3, shuffle=True, num_workers=4)
val_loader = DataLoader(val_ds, batch_size=3, shuffle=False, num_workers=4)
print('Done making datasets')


###############################################################################
# Visualize inputs to model after augmentation for chosen patient
###############################################################################

pat = 45
data = train_ds[pat]
# pick one image from DecathlonDataset to visualize and check the 4 channels
print(f"image shape: {data['image'].shape}")
plt.figure("image", (24, 6))

# Plot all channels of input to model 
fig, ax = plt.subplots(1, 4, figsize=(10,17), squeeze=True)
for i in range(4):
    ax[i].imshow(data["image"][i, :, :, 70].detach().cpu(), cmap="gray")
    ax[i].set_xticks([]) 
    ax[i].set_yticks([]) 
ax[0].set_title('Flair')
ax[1].set_title('T1')
ax[2].set_title('T1c')
ax[3].set_title('T2')

plt.tight_layout()
plt.savefig(os.path.join(save_figures, f'training_data_{pat}'))
plt.show()

# Plot all channels of label
blue_cmap = plt.cm.Blues
fig, ax = plt.subplots(1, 3, figsize=(8,15), squeeze=True)
for i in range(3):
    ax[i].imshow(data["label"][i,:, :, 70].detach().cpu(), cmap="gray")
    ax[i].set_xticks([]) 
    ax[i].set_yticks([]) 
ax[0].set_title('Tumor Core')
ax[1].set_title('Whole Tumor')
ax[2].set_title('Enhanced Tumor')


plt.tight_layout()
plt.savefig(os.path.join(save_figures, f'training_labels_{pat}'))
plt.show()


###############################################################################
# Model
###############################################################################

max_epochs = 300
val_interval = 1
VAL_AMP = True  #Use automatic precision package from torch

# standard PyTorch program style: create SegResNet, DiceLoss and Adam optimizer
device = torch.device("cuda:1")

model = DynUNet(
    spatial_dims=3,
    in_channels=4,
    out_channels=3,
    kernel_size= [[3, 3, 3], [3, 3, 3], [3, 3, 3], [3, 3, 3], [3, 3, 3], [3, 3, 3]],
    strides= [[1, 1, 1], [2, 2, 2], [2, 2, 2], [2, 2, 2], [2, 2, 2], [2, 2, 2]],
    upsample_kernel_size= [[2, 2, 2], [2, 2, 2], [2, 2, 2], [2, 2, 2], [2, 2, 2]],
    norm_name="instance",
    deep_supervision=True,
    deep_supr_num=2,
).to(device)

loss_function = DiceLoss(smooth_nr=0, smooth_dr=1e-6, squared_pred=True, 
                         to_onehot_y=False, sigmoid=True)
optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=75, gamma=0.05)

# will compute mean dice on the decollated `predictions` and `labels`, which are 
# list of `channel-first` tensors
dice_metric = DiceMetric(include_background=True, reduction="mean")
dice_metric_batch = DiceMetric(include_background=True, reduction="mean_batch")

post_trans = Compose([
    EnsureType(data_type='tensor'), 
    Activations(sigmoid=True), 
    AsDiscrete(threshold_values=0.5),
    ])

# use automatic precion package to accelerate training
scaler = torch.cuda.amp.GradScaler()
# enable cuDNN benchmark, in order to pick most efficient algorithm for training
torch.backends.cudnn.benchmark = True


###############################################################################
# Train and validate
###############################################################################

best_metric = -1
best_metric_epoch = -1
best_metrics_epochs_and_time = [[], [], []]
epoch_loss_values = []
deep_epoch_loss_values = []

# dice average scores for all labels averaged, tumor core, whole tumor and 
# enhancing tumor
metric_values = []
metric_values_tc = []
metric_values_wt = []
metric_values_et = []

total_start = time.time()
# Train
for epoch in range(max_epochs):
    epoch_start = time.time()
    print("-" * 50)
    print(f"epoch {epoch + 1}/{max_epochs}")
    model.train()
    epoch_loss = 0
    epoch_losses = None
    step = 0
    
    # Iterate through all data to train
    for batch_data in train_loader:
        step_start = time.time()
        step += 1
        inputs, labels = (
            batch_data["image"].to(device),
            batch_data["label"].to(device),
        )

        optimizer.zero_grad()
        # Using amp, get output and loss
        with torch.cuda.amp.autocast():
            feature_maps = model(inputs)
            feature_maps = torch.unbind(feature_maps, dim=1)

            # calculate loss from deep supervision
            losses = []
            loss = 0
            for feature_map in feature_maps: 
                loss_layer = loss_function(feature_map, labels)
                loss += loss_layer
                losses.append( loss_layer.item())

        # Backpropagation and update of learnable parameters
        scaler.scale(loss).backward()   #compute gradients
        scaler.step(optimizer)  #update parameters
        scaler.update()
        # Add loss from this iteration
        epoch_loss += loss.item()
        if not epoch_losses: epoch_losses = [0]*len(feature_maps)
        epoch_losses = [sum(x) for x in (zip(epoch_losses, losses))]
        if step % 60 == 0:
            print(
                f"{step}/{len(train_ds) // train_loader.batch_size}"
                f", train_loss: {loss.item():.4f}"
                f", step time: {(time.time() - step_start):.4f}"
            )
    lr_scheduler.step()
    epoch_loss /= step
    epoch_loss_values.append(epoch_loss)
    deep_epoch_loss_values.append(epoch_losses)
    print(f"epoch {epoch + 1} average loss: {epoch_loss:.4f}")

    # Validate
    if (epoch + 1) % val_interval == 0:
        model.eval()
        with torch.no_grad():

            for val_data in val_loader:
                val_inputs, val_labels = (
                    val_data["image"].to(device),
                    val_data["label"].to(device),
                )
                # Get model prediction
                with torch.cuda.amp.autocast():
                    val_outputs = model(val_inputs)
                val_outputs = [post_trans(i) for i in decollate_batch(val_outputs)]
                dice_metric(y_pred=val_outputs, y=val_labels)
                dice_metric_batch(y_pred=val_outputs, y=val_labels)

            # append the final mean dice result (averaged over channels and all volumes)
            metric = dice_metric.aggregate().item()
            metric_values.append(metric)
            # append the mean dice result for each channel (averages over all volumes but not channels)
            metric_batch = dice_metric_batch.aggregate()
            metric_tc = metric_batch[0].item()
            metric_values_tc.append(metric_tc)
            metric_wt = metric_batch[1].item()
            metric_values_wt.append(metric_wt)
            metric_et = metric_batch[2].item()
            metric_values_et.append(metric_et)
            # reset the status for next validation round
            dice_metric.reset()
            dice_metric_batch.reset()

            if metric > best_metric:
                best_metric = metric
                best_metric_epoch = epoch + 1
                best_metrics_epochs_and_time[0].append(best_metric)
                best_metrics_epochs_and_time[1].append(best_metric_epoch)
                best_metrics_epochs_and_time[2].append(time.time() - total_start)
                torch.save(
                    model.state_dict(),
                    os.path.join(model_dir, "best_metric_model.pth"),
                )
                print("saved new best metric model")
            print(
                f"current epoch: {epoch + 1} current mean dice: {metric:.4f}"
                f" tc: {metric_tc:.4f} wt: {metric_wt:.4f} et: {metric_et:.4f}"
                f"\nbest mean dice: {best_metric:.4f}"
                f" at epoch: {best_metric_epoch}"
            )
    print(f"time consuming of epoch {epoch + 1} is: {(time.time() - epoch_start):.4f}")
    
torch.save(
    model.state_dict(),
    os.path.join(model_dir, "last_metric_model.pth"),
)

total_time = time.time() - total_start
print(f'Total training time: {total_time//3600}h {(total_time%3600)//60}min')


###############################################################################
# Save metrics 
###############################################################################

# make dictionary
metrics_dict = {'loss': epoch_loss_values,
                'deep losses': deep_epoch_loss_values,
                'dice': metric_values,
                'dice wt': metric_values_wt,
                'dice tc': metric_values_tc,
                'dice et': metric_values_et,
                } 

# save dictionary with pickle
with open(os.path.join(model_dir, "metrics.pth"), 'wb') as f: 
    pickle.dump(metrics_dict, f)


