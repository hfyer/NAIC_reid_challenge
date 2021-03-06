# encoding: utf-8
"""
@author:  zhoumi
@contact: zhoumi281571814@126.com
"""
import os
import sys
from os import path as osp
from pprint import pprint

import numpy as np
import torch
from tensorboardX import SummaryWriter
from torch import nn
from torch.backends import cudnn
from torch.utils.data import DataLoader

from config import opt
from datasets.init_dataset import Tx_dataset
from datasets.dataset_loader import ImageDataset
from datasets.samplers import RandomIdentitySampler, RandomIdentitySampler_new
from models import build_model
from trainer import cls_tripletTrainer
from loss import CrossEntropyLabelSmooth, TripletLoss, CenterLoss
from logger import Logger, save_checkpoint
from transformer import build_transforms
from lr_schedule import adjust_lr
from datasets.collate_batch import val_collate_fn, train_collate_fn
from config import opt
from evaluator import Evaluator
from loss import make_loss_with_center, make_loss

def train(**kwargs):
    opt._parse(kwargs)

    # set random seed and cudnn benchmark
    torch.manual_seed(opt.seed)
    os.makedirs(opt.save_dir, exist_ok=True)
    use_gpu = torch.cuda.is_available()
    sys.stdout = Logger(osp.join(opt.save_dir, 'log_train.txt'))

    print('=========user config==========')
    pprint(opt._state_dict())
    print('============end===============')

    if use_gpu:
        print('currently using GPU')
        cudnn.benchmark = True
        torch.cuda.manual_seed_all(opt.seed)
    else:
        print('currently using cpu')

    print('initializing tx_chanllege dataset')
    dataset = Tx_dataset(file_list='train_list_new.txt').dataset
    query_dataset = Tx_dataset(set='train_set', file_list='val_query_list.txt').dataset
    gallery_dataset = Tx_dataset(set='train_set', file_list='val_gallery_list.txt').dataset

    train_set = ImageDataset(dataset, transform=build_transforms(opt, is_train=True))

    pin_memory = True if use_gpu else False

    summary_writer = SummaryWriter(osp.join(opt.save_dir, 'tensorboard_log'))
    if opt.sampler_new:
        trainloader = DataLoader(
            train_set,
            sampler=RandomIdentitySampler_new(train_set, opt.train_batch, opt.num_instances),
            # sampler=RandomIdentitySampler(train_set, opt.num_instances),
            batch_size=opt.train_batch, num_workers=opt.workers,
            pin_memory=pin_memory, drop_last=True
        )
    else:
        trainloader = DataLoader(
            train_set,
            # sampler=RandomIdentitySampler_new(train_set, opt.train_batch, opt.num_instances),
            sampler=RandomIdentitySampler(train_set, opt.num_instances),
            batch_size=opt.train_batch, num_workers=opt.workers,
            pin_memory=pin_memory, drop_last=True
        )

    queryloader = DataLoader(
        ImageDataset(query_dataset, transform=build_transforms(opt, is_train=False)),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory)

    galleryloader = DataLoader(
        ImageDataset(gallery_dataset, transform=build_transforms(opt, is_train=False)),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory)

    queryFliploader = DataLoader(
        ImageDataset(query_dataset, transform=build_transforms(opt, is_train=False, flip=True)),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory
    )

    galleryFliploader = DataLoader(
        ImageDataset(gallery_dataset, transform=build_transforms(opt, is_train=False, flip=True)),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory
    )

    queryCenterloader = DataLoader(
        ImageDataset(query_dataset, transform=build_transforms(opt, is_train=False, crop='center')),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory
    )

    galleryCenterloader = DataLoader(
        ImageDataset(gallery_dataset, transform=build_transforms(opt, is_train=False, crop='center')),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory
    )

    queryLtloader = DataLoader(
        ImageDataset(query_dataset, transform=build_transforms(opt, is_train=False, crop='lt')),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory
    )

    galleryLtloader = DataLoader(
        ImageDataset(gallery_dataset, transform=build_transforms(opt, is_train=False, crop='lt')),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory
    )

    queryRtloader = DataLoader(
        ImageDataset(query_dataset, transform=build_transforms(opt, is_train=False, crop='rt')),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory
    )

    galleryRtloader = DataLoader(
        ImageDataset(gallery_dataset, transform=build_transforms(opt, is_train=False, crop='rt')),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory
    )

    queryRbloader = DataLoader(
        ImageDataset(query_dataset, transform=build_transforms(opt, is_train=False, crop='rb')),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory
    )

    galleryRbloader = DataLoader(
        ImageDataset(gallery_dataset, transform=build_transforms(opt, is_train=False, crop='rb')),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory
    )

    queryLbloader = DataLoader(
        ImageDataset(query_dataset, transform=build_transforms(opt, is_train=False, crop='lb')),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory
    )

    galleryLbloader = DataLoader(
        ImageDataset(gallery_dataset, transform=build_transforms(opt, is_train=False, crop='lb')),
        batch_size=opt.test_batch, num_workers=opt.workers,
        pin_memory=pin_memory
    )

    print('initializing model ...')

    model = build_model(opt)

    optim_policy = model.get_optim_policy()

    if opt.pretrained_choice == 'self':
        state_dict = torch.load(opt.pretrained_model)['state_dict']
        # state_dict = {k: v for k, v in state_dict.items() \
        #        if not ('reduction' in k or 'softmax' in k)}
        model.load_state_dict(state_dict, False)
        print('load pretrained model ' + opt.pretrained_model)
    print('model size: {:.5f}M'.format(sum(p.numel() for p in model.parameters()) / 1e6))

    if use_gpu:
        model = nn.DataParallel(model).cuda()
    reid_evaluator = Evaluator(model, norm=opt.norm, eval_flip=opt.eval_flip, re_ranking=opt.re_ranking)

    if opt.use_center:
        criterion = make_loss_with_center(opt)
    else:
        criterion = make_loss(opt)

    # get optimizer
    if opt.optim == "sgd":
        optimizer = torch.optim.SGD(optim_policy, lr=opt.lr, momentum=0.9, weight_decay=opt.weight_decay)
    else:
        optimizer = torch.optim.Adam(optim_policy, lr=opt.lr, weight_decay=opt.weight_decay)

    start_epoch = opt.start_epoch
    # get trainer and evaluator
    reid_trainer = cls_tripletTrainer(opt, model, optimizer, criterion, summary_writer)

    # start training
    best_rank1 = opt.best_rank
    best_epoch = 0
    for epoch in range(start_epoch, opt.max_epoch):
        if opt.adjust_lr:
            adjust_lr(optimizer, opt.lr, opt.model_name, epoch + 1)
        reid_trainer.train(epoch, trainloader)

        # skip if not save model
        if opt.eval_step > 0 and (epoch + 1) % opt.eval_step == 0 or (epoch + 1) == opt.max_epoch:
            rank1 = reid_evaluator.validation(queryloader, galleryloader, queryFliploader, galleryFliploader,
                                              queryCenterloader, galleryCenterloader,
                                              queryLtloader, galleryLtloader,
                                              queryRtloader, galleryRtloader,
                                              queryLbloader, galleryLbloader,
                                              queryRbloader, galleryRbloader)
            print('start re_ranking......')
            _ = reid_evaluator.validation(queryloader, galleryloader,
                                          queryFliploader, galleryFliploader,
                                          queryCenterloader, galleryCenterloader,
                                          queryLtloader, galleryLtloader,
                                          queryRtloader, galleryRtloader,
                                          queryLbloader, galleryLbloader,
                                          queryRbloader, galleryRbloader,
                                          re_ranking=True)
            is_best = rank1 > best_rank1
            if is_best:
                best_rank1 = rank1
                best_epoch = epoch + 1

            if use_gpu:
                state_dict = model.module.state_dict()
            else:
                state_dict = model.state_dict()
            save_checkpoint({'state_dict': state_dict, 'epoch': epoch + 1},
                            is_best=is_best, save_dir=opt.save_dir,
                            filename='checkpoint_ep' + str(epoch + 1) + '.pth.tar')

    print('Best rank-1 {:.1%}, achived at epoch {}'.format(best_rank1, best_epoch))


if __name__ == '__main__':
    import fire
    fire.Fire()
