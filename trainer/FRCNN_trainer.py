'''
quick and dirty test, need to change later
'''
import torch
import torch.nn as nn
import numpy as np
import torchvision
import os
import cv2
from collections import OrderedDict
from torch.nn.parallel import DataParallel, DistributedDataParallel
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torch.utils.data import Dataset, DataLoader
from torchvision import utils
from detection.engine import train_one_epoch, evaluate_base
from detection.utils import collate_fn
from scripts_for_datasets import COWCFRCNNDataset
from detection.transforms import ToTensor, RandomHorizontalFlip, Compose
from matplotlib import pyplot as plt

class COWCFRCNNTrainer:
    """
    Trainer class
    """
    def __init__(self, config):
        self.config = config

        n_gpu = torch.cuda.device_count()
        self.device = torch.device('cuda:1' if n_gpu > 0 else 'cpu')

    def get_transform(self, train):
        transforms = []
        # converts the image, a PIL image, into a PyTorch Tensor
        transforms.append(ToTensor())
        if train:
            # during training, randomly flip the training images
            # and ground-truth for data augmentation
            transforms.append(RandomHorizontalFlip(0.5))
        return Compose(transforms)

    def data_loaders(self):
        # use our dataset and defined transformations
        dataset = COWCFRCNNDataset(root=self.config['path']['data_dir_LR_train'],
                    transforms=self.get_transform(train=True))
        dataset_test = COWCFRCNNDataset(root=self.config['path']['data_dir_Valid'],
                         transforms=self.get_transform(train=False))
        dataset_test_SR = COWCFRCNNDataset(root=self.config['path']['data_dir_SR'],
                         transforms=self.get_transform(train=False))
        dataset_test_SR_combined = COWCFRCNNDataset(root=self.config['path']['data_dir_SR_combined'],
                         transforms=self.get_transform(train=False))
        dataset_test_E_SR_1 = COWCFRCNNDataset(root=self.config['path']['data_dir_E_SR_1'],
                         transforms=self.get_transform(train=False))
        dataset_test_E_SR_2 = COWCFRCNNDataset(root=self.config['path']['data_dir_E_SR_2'],
                         transforms=self.get_transform(train=False))
        dataset_test_E_SR_3 = COWCFRCNNDataset(root=self.config['path']['data_dir_E_SR_3'],
                         transforms=self.get_transform(train=False))
        dataset_test_F_SR = COWCFRCNNDataset(root=self.config['path']['data_dir_F_SR'],
                         transforms=self.get_transform(train=False))
        dataset_test_Bic = COWCFRCNNDataset(root=self.config['path']['data_dir_Bic'],
                         transforms=self.get_transform(train=False))

        # define training and validation data loaders
        data_loader = torch.utils.data.DataLoader(
            dataset, batch_size=2, shuffle=True, num_workers=4,
            collate_fn=collate_fn)

        data_loader_test = torch.utils.data.DataLoader(
            dataset_test, batch_size=1, shuffle=False, num_workers=4,
            collate_fn=collate_fn)

        data_loader_test_SR = torch.utils.data.DataLoader(
            dataset_test_SR, batch_size=1, shuffle=False, num_workers=4,
            collate_fn=collate_fn)

        data_loader_test_SR_combined = torch.utils.data.DataLoader(
            dataset_test_SR_combined, batch_size=1, shuffle=False, num_workers=4,
            collate_fn=collate_fn)

        data_loader_test_E_SR_1 = torch.utils.data.DataLoader(
            dataset_test_E_SR_1, batch_size=1, shuffle=False, num_workers=4,
            collate_fn=collate_fn)

        data_loader_test_E_SR_2 = torch.utils.data.DataLoader(
            dataset_test_E_SR_2, batch_size=1, shuffle=False, num_workers=4,
            collate_fn=collate_fn)

        data_loader_test_E_SR_3 = torch.utils.data.DataLoader(
            dataset_test_E_SR_3, batch_size=1, shuffle=False, num_workers=4,
            collate_fn=collate_fn)

        data_loader_test_F_SR = torch.utils.data.DataLoader(
            dataset_test_F_SR, batch_size=1, shuffle=False, num_workers=4,
            collate_fn=collate_fn)

        data_loader_test_Bic = torch.utils.data.DataLoader(
            dataset_test_Bic, batch_size=1, shuffle=False, num_workers=4,
            collate_fn=collate_fn)

        return data_loader, data_loader_test, data_loader_test_SR, data_loader_test_SR_combined, \
                data_loader_test_E_SR_1, data_loader_test_E_SR_2, data_loader_test_E_SR_3, \
                data_loader_test_F_SR, data_loader_test_Bic

    def save_model(self, network, network_label, iter_label):
        save_filename = '{}_{}.pth'.format(iter_label, network_label)
        save_path = os.path.join(self.config['path']['FRCNN_model'], save_filename)

        state_dict = network.state_dict()
        for key, param in state_dict.items():
            state_dict[key] = param.cpu()
        torch.save(state_dict, save_path)

    def load_model(self, load_path, network, strict=True):
        if isinstance(network, nn.DataParallel) or isinstance(network, DistributedDataParallel):
            network = network.module
        load_net = torch.load(load_path)
        load_net_clean = OrderedDict()  # remove unnecessary 'module.'
        for k, v in load_net.items():
            if k.startswith('module.'):
                load_net_clean[k[7:]] = v
            else:
                load_net_clean[k] = v
        network.load_state_dict(load_net_clean, strict=strict)
        print("model_loaded")

    def get_prediction(self, model, img, annotation_path, threshold):
        new_class_conf_box = list()
        annotation_path = ''.join(annotation_path)
        pred = model(img) # Pass the image to the model
        print(pred)
        pred_class = [i for i in list(pred[0]['labels'].detach().cpu().numpy())] # Get the Prediction Score
        pred_boxes = [[(i[0], i[1]), (i[2], i[3])] for i in list(pred[0]['boxes'].detach().cpu().numpy())] # Bounding boxes
        text_boxes = [i for i in list(pred[0]['boxes'].detach().cpu().numpy())] # Bounding boxes
        pred_score = list(pred[0]['scores'].detach().cpu().numpy())

        for i in range(len(text_boxes)):
            new_class_conf_box.append([int(pred_class[i]), int(pred_score[i][0]), int(text_boxes[i][0]), int(text_boxes[i][1]), int(text_boxes[i][2]), int(text_boxes[i][3])])
        new_class_conf_box = np.matrix(new_class_conf_box)

        #np.savetxt(annotation_path, new_class_conf_box, fmt='%i')
        '''
        pred_t = [pred_score.index(x) for x in pred_score if x > threshold][-1] # Get list of index with score greater than threshold.
        pred_boxes = pred_boxes[:pred_t+1]
        pred_class = pred_class[:pred_t+1]
        return pred_boxes, pred_class
        '''

    def object_detection_api(self, model, img, annotation_path, img_path, threshold=0.5, rect_th=3, text_size=3, text_th=3):
        img_path = ''.join(img_path)

        #boxes, pred_cls =
        self.get_prediction(model, img, annotation_path, threshold) # Get predictions
        '''
        img = cv2.imread(img_path) # Read image with cv2
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) # Convert to RGB
        for i in range(len(boxes)):
            cv2.rectangle(img, boxes[i][0], boxes[i][1],color=(0, 255, 0), thickness=rect_th) # Draw Rectangle with the coordinates
            plt.figure(figsize=(20,30)) # display the output image
            plt.xticks([])
            plt.yticks([])
            plt.savefig(img_path)
        '''

    def test(self):

        # load a model pre-trained pre-trained on COCO
        model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)

        # replace the classifier with a new one, that has
        # num_classes which is user-defined
        num_classes = 2  # 1 class (car) + background
        # get number of input features for the classifier
        in_features = model.roi_heads.box_predictor.cls_score.in_features
        # replace the pre-trained head with a new one
        model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)

        model.to(self.device)

        self.load_model(self.config['path']['pretrain_model_FRCNN'], model)

        _, data_loader_test, data_loader_test_SR, data_loader_test_SR_combined, \
                data_loader_test_E_SR_1, data_loader_test_E_SR_2, data_loader_test_E_SR_3, \
                 data_loader_test_F_SR, data_loader_test_Bic = self.data_loaders()

        print("test lenghts of the data loaders.............")
        print(len(data_loader_test_SR))
        model.eval()
        for image, targets, annotation_path, img_path in data_loader_test_SR:
            evaluate_base(model, data_loader_test_SR, device=self.device)
            #image = list(img.to(self.device) for img in image)
            #self.object_detection_api(model, image, annotation_path, img_path)

        '''
        print(len(data_loader_test_SR))
        print(len(data_loader_test_SR_combined))
        print(len(data_loader_test_E_SR_1))
        print(len(data_loader_test_E_SR_2))
        print(len(data_loader_test_E_SR_3))
        print(len(data_loader_test_F_SR))
        print(len(data_loader_test_Bic))
        print("test HR images..............................")
        evaluate_base(model, data_loader_test, device=self.device)
        print("test SR images..............................")
        evaluate_base(model, data_loader_test_SR, device=self.device)
        print("test SR combined images..............................")
        evaluate_base(model, data_loader_test_SR_combined, device=self.device)
        print("test Enhanced SR 1 images.....................")
        evaluate_base(model, data_loader_test_E_SR_1, device=self.device)
        print("test Enhanced SR 2 images.....................")
        evaluate_base(model, data_loader_test_E_SR_2, device=self.device)
        print("test Enhanced SR 3 images.....................")
        evaluate_base(model, data_loader_test_E_SR_3, device=self.device)
        print("test Final SR images.........................")
        evaluate_base(model, data_loader_test_F_SR, device=self.device)
        print("test Bicubic images..........................")
        evaluate_base(model, data_loader_test_Bic, device=self.device)
        '''
    def train(self):
        # load a model pre-trained pre-trained on COCO
        model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)

        # replace the classifier with a new one, that has
        # num_classes which is user-defined
        num_classes = 2  # 1 class (car) + background
        # get number of input features for the classifier
        in_features = model.roi_heads.box_predictor.cls_score.in_features
        # replace the pre-trained head with a new one
        model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)

        model.to(self.device)
        self.load_model(self.config['path']['pretrain_model_FRCNN'], model)

        # construct an optimizer
        params = [p for p in model.parameters() if p.requires_grad]
        optimizer = torch.optim.SGD(params, lr=0.005,
                                    momentum=0.9, weight_decay=0.0005)

        # and a learning rate scheduler which decreases the learning rate by
        # 10x every 3 epochs
        lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer,
                                                       step_size=3,
                                                       gamma=0.1)

        data_loader, _, _, _, _, _, _, _, data_loader_test_Bic = self.data_loaders()
        # let's train it for 10 epochs
        num_epochs = 1000

        for epoch in range(num_epochs):
            # train for one epoch, printing every 10 iterations
            train_one_epoch(model, optimizer, data_loader, self.device, epoch, print_freq=10)
            # update the learning rate
            lr_scheduler.step()
            # evaluate on the test dataset
            evaluate_base(model, data_loader_test_Bic, device=self.device)
            if epoch % 10 == 0:
                self.save_model(model, 'FRCNN_Bic', epoch)
