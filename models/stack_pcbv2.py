#!/usr/bin/env python
# -*- coding:utf-8 -*-
# @Time    : 2019/11/19 10:31 下午
# @author  : wuh-xmu
# @FileName: stack_pcb.py
# @Software: PyCharm
import torch
import torch.nn as nn
import copy
import gc

from .backbones.resnet_ibn_a import ResNet_IBN as ResNet
from .backbones.resnet_ibn_a import Bottleneck_IBN as Bottleneck

def weights_init_kaiming(m):
    classname = m.__class__.__name__
    if classname.find('Linear') != -1:
        nn.init.kaiming_normal_(m.weight, a=0, mode='fan_out')
        nn.init.constant_(m.bias, 0.0)
    elif classname.find('Conv') != -1:
        nn.init.kaiming_normal_(m.weight, a=0, mode='fan_in')
        if m.bias is not None:
            nn.init.constant_(m.bias, 0.0)
    elif classname.find('BatchNorm') != -1:
        if m.affine:
            nn.init.constant_(m.weight, 1.0)
            nn.init.constant_(m.bias, 0.0)


def weights_init_classifier(m):
    classname = m.__class__.__name__
    if classname.find('Linear') != -1:
        nn.init.normal_(m.weight, std=0.001)
        if m.bias is not None:
            nn.init.constant_(m.bias, 0.0)


class Flatten(nn.Module):
    def __init__(self, dim):
        super(Flatten, self).__init__()
        self.dim = dim

    def forward(self, x):
        return x.flatten(self.dim)


class StackPCBv2(nn.ModuleList):
    def __init__(self, num_classes, pretrain_choice, model_path, neck, neck_feat, local_dim=256, last_stride = 2):
        super(StackPCBv2, self).__init__()

        resnet = ResNet(last_stride=last_stride, block=Bottleneck, layers=[3, 4, 6, 3])

        if pretrain_choice == 'imagenet':
            resnet.load_param(model_path)
            print('Loading pretrained ImageNet model......')

        self.neck = neck
        self.neck_feat = neck_feat

        self.backbone = nn.Sequential(
            resnet.conv1,
            resnet.bn1,
            resnet.relu,
            resnet.maxpool,
            resnet.layer1,
            resnet.layer2,
            resnet.layer3[0],
        )

        self.local_part_1 = nn.Sequential(copy.deepcopy(resnet.layer3[1:]), copy.deepcopy(resnet.layer4))
        self.local_part_2 = nn.Sequential(copy.deepcopy(resnet.layer3[1:]), copy.deepcopy(resnet.layer4))
        self.local_part_3 = nn.Sequential(copy.deepcopy(resnet.layer3[1:]), copy.deepcopy(resnet.layer4))
        self.local_part_4 = nn.Sequential(copy.deepcopy(resnet.layer3[1:]), copy.deepcopy(resnet.layer4))
        self.local_part_5 = nn.Sequential(copy.deepcopy(resnet.layer3[1:]), copy.deepcopy(resnet.layer4))

        self.global_pool = nn.AvgPool2d((24, 8))
        self.local_pool_1 = nn.MaxPool2d((4, 8), stride=(4, 8))
        self.local_pool_2 = nn.MaxPool2d((8, 8), stride=(4, 8))
        self.local_pool_3 = nn.MaxPool2d((12, 8), stride=(4, 8))
        self.local_pool_4 = nn.MaxPool2d((16, 8), stride=(4, 8))
        self.local_pool_5 = nn.MaxPool2d((20, 8), stride=(4, 8))

        self.bottleneck = nn.BatchNorm1d(local_dim)
        self.bottleneck.bias.requires_grad_(False)  # no shift

        self.global_bottleneck = nn.BatchNorm1d(2048)
        self.global_bottleneck.bias.requires_grad_(False)  # no shift

        local_embedding = nn.Sequential(
            nn.Conv2d(2048, local_dim, 1, bias=False),
            nn.BatchNorm2d(local_dim),
            nn.ReLU(),
            Flatten(1)
        )

        self.p1_f1_embedding = copy.deepcopy(local_embedding)
        self.p1_f2_embedding = copy.deepcopy(local_embedding)
        self.p1_f3_embedding = copy.deepcopy(local_embedding)
        self.p1_f4_embedding = copy.deepcopy(local_embedding)
        self.p1_f5_embedding = copy.deepcopy(local_embedding)
        self.p1_f6_embedding = copy.deepcopy(local_embedding)

        self.p2_f1_embedding = copy.deepcopy(local_embedding)
        self.p2_f2_embedding = copy.deepcopy(local_embedding)
        self.p2_f3_embedding = copy.deepcopy(local_embedding)
        self.p2_f4_embedding = copy.deepcopy(local_embedding)
        self.p2_f5_embedding = copy.deepcopy(local_embedding)

        self.p3_f1_embedding = copy.deepcopy(local_embedding)
        self.p3_f2_embedding = copy.deepcopy(local_embedding)
        self.p3_f3_embedding = copy.deepcopy(local_embedding)
        self.p3_f4_embedding = copy.deepcopy(local_embedding)

        self.p4_f1_embedding = copy.deepcopy(local_embedding)
        self.p4_f2_embedding = copy.deepcopy(local_embedding)
        self.p4_f3_embedding = copy.deepcopy(local_embedding)

        self.p5_f1_embedding = copy.deepcopy(local_embedding)
        self.p5_f2_embedding = copy.deepcopy(local_embedding)

        local_classifier = nn.Linear(local_dim, num_classes, bias=False)
        local_classifier.apply(weights_init_classifier)

        global_classifier = nn.Linear(2048, num_classes, bias=False)
        global_classifier.apply(weights_init_classifier)

        self.p1_f1_classifier = copy.deepcopy(local_classifier)
        self.p1_f2_classifier = copy.deepcopy(local_classifier)
        self.p1_f3_classifier = copy.deepcopy(local_classifier)
        self.p1_f4_classifier = copy.deepcopy(local_classifier)
        self.p1_f5_classifier = copy.deepcopy(local_classifier)
        self.p1_f6_classifier = copy.deepcopy(local_classifier)

        self.p2_f1_classifier = copy.deepcopy(local_classifier)
        self.p2_f2_classifier = copy.deepcopy(local_classifier)
        self.p2_f3_classifier = copy.deepcopy(local_classifier)
        self.p2_f4_classifier = copy.deepcopy(local_classifier)
        self.p2_f5_classifier = copy.deepcopy(local_classifier)

        self.p3_f1_classifier = copy.deepcopy(local_classifier)
        self.p3_f2_classifier = copy.deepcopy(local_classifier)
        self.p3_f3_classifier = copy.deepcopy(local_classifier)
        self.p3_f4_classifier = copy.deepcopy(local_classifier)

        self.p4_f1_classifier = copy.deepcopy(local_classifier)
        self.p4_f2_classifier = copy.deepcopy(local_classifier)
        self.p4_f3_classifier = copy.deepcopy(local_classifier)

        self.p5_f1_classifier = copy.deepcopy(local_classifier)
        self.p5_f2_classifier = copy.deepcopy(local_classifier)

        self.p1_global_classifier = copy.deepcopy(global_classifier)
        self.p2_global_classifier = copy.deepcopy(global_classifier)
        self.p3_global_classifier = copy.deepcopy(global_classifier)
        self.p4_global_classifier = copy.deepcopy(global_classifier)
        self.p5_global_classifier = copy.deepcopy(global_classifier)

        # del resnet
        # del global_classifier, local_classifier
        # del global_bn, local_bn, local_embedding
        # gc.collect()

    @staticmethod
    def _init_reduction(reduction):
        # conv
        nn.init.kaiming_normal_(reduction[0].weight, mode='fan_in')
        # nn.init.constant_(reduction[0].bias, 0.)

        # bn
        nn.init.normal_(reduction[1].weight, mean=1., std=0.02)
        nn.init.constant_(reduction[1].bias, 0.)

    def forward(self, x):
        x = self.backbone(x)

        p1 = self.local_part_1(x)
        p2 = self.local_part_2(x)
        p3 = self.local_part_3(x)
        p4 = self.local_part_4(x)
        p5 = self.local_part_5(x)

        p1_global_feature = self.global_pool(p1).flatten(1)
        p2_global_feature = self.global_pool(p2).flatten(1)
        p3_global_feature = self.global_pool(p3).flatten(1)
        p4_global_feature = self.global_pool(p4).flatten(1)
        p5_global_feature = self.global_pool(p5).flatten(1)

        p1 = self.local_pool_1(p1)
        p2 = self.local_pool_2(p2)
        p3 = self.local_pool_3(p3)
        p4 = self.local_pool_4(p4)
        p5 = self.local_pool_5(p5)

        p1_f1 = self.p1_f1_embedding(p1[:, :, 0:1, :])
        p1_f2 = self.p1_f2_embedding(p1[:, :, 1:2, :])
        p1_f3 = self.p1_f3_embedding(p1[:, :, 2:3, :])
        p1_f4 = self.p1_f4_embedding(p1[:, :, 3:4, :])
        p1_f5 = self.p1_f5_embedding(p1[:, :, 4:5, :])
        p1_f6 = self.p1_f6_embedding(p1[:, :, 5:6, :])

        p2_f1 = self.p2_f1_embedding(p2[:, :, 0:1, :])
        p2_f2 = self.p2_f2_embedding(p2[:, :, 1:2, :])
        p2_f3 = self.p2_f3_embedding(p2[:, :, 2:3, :])
        p2_f4 = self.p2_f4_embedding(p2[:, :, 3:4, :])
        p2_f5 = self.p2_f5_embedding(p2[:, :, 4:5, :])

        p3_f1 = self.p3_f1_embedding(p3[:, :, 0:1, :])
        p3_f2 = self.p3_f2_embedding(p3[:, :, 1:2, :])
        p3_f3 = self.p3_f3_embedding(p3[:, :, 2:3, :])
        p3_f4 = self.p3_f4_embedding(p3[:, :, 3:4, :])

        p4_f1 = self.p4_f1_embedding(p4[:, :, 0:1, :])
        p4_f2 = self.p4_f2_embedding(p4[:, :, 1:2, :])
        p4_f3 = self.p4_f3_embedding(p4[:, :, 2:3, :])

        p5_f1 = self.p5_f1_embedding(p5[:, :, 0:1, :])
        p5_f2 = self.p5_f2_embedding(p5[:, :, 1:2, :])

        if self.neck == 'no':
            p1_global_feature_bn = p1_global_feature
            p2_global_feature_bn = p2_global_feature
            p3_global_feature_bn = p3_global_feature
            p4_global_feature_bn = p4_global_feature
            p5_global_feature_bn = p5_global_feature
            p1_f1_bn = p1_f1
            p1_f2_bn = p1_f2
            p1_f3_bn = p1_f3
            p1_f4_bn = p1_f4
            p1_f5_bn = p1_f5
            p1_f6_bn = p1_f6
            p2_f1_bn = p2_f1
            p2_f2_bn = p2_f2
            p2_f3_bn = p2_f3
            p2_f4_bn = p2_f4
            p2_f5_bn = p2_f5
            p3_f1_bn = p3_f1
            p3_f2_bn = p3_f2
            p3_f3_bn = p3_f3
            p3_f4_bn = p3_f4

            p4_f1_bn = p4_f1
            p4_f2_bn = p4_f2
            p4_f3_bn = p4_f3
            p5_f1_bn = p5_f1
            p5_f2_bn = p5_f2
            global_features = [p1_global_feature_bn, p2_global_feature_bn,
                           p3_global_feature_bn, p4_global_feature_bn, p5_global_feature_bn]

            p1_features = [p1_f1_bn, p1_f2_bn, p1_f3_bn, p1_f4_bn, p1_f5_bn, p1_f6_bn]
            p2_features = [p2_f1_bn, p2_f2_bn, p2_f3_bn, p2_f4_bn, p2_f5_bn]
            p3_features = [p3_f1_bn, p3_f2_bn, p3_f3_bn, p3_f4_bn]
            p4_features = [p4_f1_bn, p4_f2_bn, p4_f3_bn]
            p5_features = [p5_f1_bn, p5_f2_bn]

            local_features = []
            local_features += p1_features
            local_features += p2_features
            local_features += p3_features
            local_features += p4_features
            local_features += p5_features
        elif self.neck == 'bnneck':
            p1_global_feature_bn = self.global_bottleneck(p1_global_feature)
            p2_global_feature_bn = self.global_bottleneck(p2_global_feature)
            p3_global_feature_bn = self.global_bottleneck(p3_global_feature)
            p4_global_feature_bn = self.global_bottleneck(p4_global_feature)
            p5_global_feature_bn = self.global_bottleneck(p5_global_feature)
            p1_f1_bn = self.bottleneck(p1_f1)
            p1_f2_bn = self.bottleneck(p1_f2)
            p1_f3_bn = self.bottleneck(p1_f3)
            p1_f4_bn = self.bottleneck(p1_f4)
            p1_f5_bn = self.bottleneck(p1_f5)
            p1_f6_bn = self.bottleneck(p1_f6)
            p2_f1_bn = self.bottleneck(p2_f1)
            p2_f2_bn = self.bottleneck(p2_f2)
            p2_f3_bn = self.bottleneck(p2_f3)
            p2_f4_bn = self.bottleneck(p2_f4)
            p2_f5_bn = self.bottleneck(p2_f5)
            p3_f1_bn = self.bottleneck(p3_f1)
            p3_f2_bn = self.bottleneck(p3_f2)
            p3_f3_bn = self.bottleneck(p3_f3)
            p3_f4_bn = self.bottleneck(p3_f4)

            p4_f1_bn = self.bottleneck(p4_f1)
            p4_f2_bn = self.bottleneck(p4_f2)
            p4_f3_bn = self.bottleneck(p4_f3)
            p5_f1_bn = self.bottleneck(p5_f1)
            p5_f2_bn = self.bottleneck(p5_f2)

            global_features = [p1_global_feature_bn, p2_global_feature_bn,
                           p3_global_feature_bn, p4_global_feature_bn, p5_global_feature_bn]

            p1_features = [p1_f1_bn, p1_f2_bn, p1_f3_bn, p1_f4_bn, p1_f5_bn, p1_f6_bn]
            p2_features = [p2_f1_bn, p2_f2_bn, p2_f3_bn, p2_f4_bn, p2_f5_bn]
            p3_features = [p3_f1_bn, p3_f2_bn, p3_f3_bn, p3_f4_bn]
            p4_features = [p4_f1_bn, p4_f2_bn, p4_f3_bn]
            p5_features = [p5_f1_bn, p5_f2_bn]

            local_features = []
            local_features += p1_features
            local_features += p2_features
            local_features += p3_features
            local_features += p4_features
            local_features += p5_features

        f = global_features + local_features

        if not self.training:
            if self.neck_feat == 'after':
                return torch.cat(f, 1)
            else:
                return

        p1_f1_y = self.p1_f1_classifier(p1_f1_bn)
        p1_f2_y = self.p1_f2_classifier(p1_f2_bn)
        p1_f3_y = self.p1_f3_classifier(p1_f3_bn)
        p1_f4_y = self.p1_f4_classifier(p1_f4_bn)
        p1_f5_y = self.p1_f5_classifier(p1_f5_bn)
        p1_f6_y = self.p1_f6_classifier(p1_f6_bn)

        p2_f1_y = self.p2_f1_classifier(p2_f1_bn)
        p2_f2_y = self.p2_f2_classifier(p2_f2_bn)
        p2_f3_y = self.p2_f3_classifier(p2_f3_bn)
        p2_f4_y = self.p2_f4_classifier(p2_f4_bn)
        p2_f5_y = self.p2_f5_classifier(p2_f5_bn)

        p3_f1_y = self.p3_f1_classifier(p3_f1_bn)
        p3_f2_y = self.p3_f2_classifier(p3_f2_bn)
        p3_f3_y = self.p3_f3_classifier(p3_f3_bn)
        p3_f4_y = self.p3_f4_classifier(p3_f4_bn)

        p4_f1_y = self.p4_f1_classifier(p4_f1_bn)
        p4_f2_y = self.p4_f2_classifier(p4_f2_bn)
        p4_f3_y = self.p4_f3_classifier(p4_f3_bn)

        p5_f1_y = self.p5_f1_classifier(p5_f1_bn)
        p5_f2_y = self.p5_f2_classifier(p5_f2_bn)

        p1_global_y = self.p1_global_classifier(p1_global_feature_bn)
        p2_global_y = self.p2_global_classifier(p2_global_feature_bn)
        p3_global_y = self.p3_global_classifier(p3_global_feature_bn)
        p4_global_y = self.p4_global_classifier(p4_global_feature_bn)
        p5_global_y = self.p5_global_classifier(p5_global_feature_bn)

        y = [p1_global_y, p2_global_y, p3_global_y, p4_global_y, p5_global_y,
             p1_f1_y, p1_f2_y, p1_f3_y, p1_f4_y, p1_f5_y, p1_f6_y,
             p2_f1_y, p2_f2_y, p2_f3_y, p2_f4_y, p2_f5_y,
             p3_f1_y, p3_f2_y, p3_f3_y, p3_f4_y,
             p4_f1_y, p4_f2_y, p4_f3_y,
             p5_f1_y, p5_f2_y]

        return y, [p1_global_feature, p2_global_feature, p3_global_feature, p4_global_feature, p5_global_feature]

    def load_param(self, trained_path):
        param_dict = torch.load(trained_path)
        for i in param_dict:
            if 'classifier' in i:
                continue
            self.state_dict()[i].copy_(param_dict[i])

    def get_optim_policy(self):
        return self.parameters()


# def spcbv2_resnet50(num_classes, loss='softmax', **kwargs):
#     resnet = resnet50_ibn_a(num_classes, loss=loss, **kwargs)
#     model = StackPCBv2(resnet, num_classes)
#     return model
