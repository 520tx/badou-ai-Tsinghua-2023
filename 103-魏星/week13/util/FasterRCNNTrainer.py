# _*_ coding : utf-8 _*_
# @Time : 2023/8/8 11:44
# @Author : weixing
# @FileName : FasterRCNNTrainer
# @Project : cv

import torch
import torch.nn as nn
import torch.nn.functional as F
from util.bboxutil import AnchorTargetCreator, ProposalTargetCreator
from collections import namedtuple

'''
1. 首先使用backbone网络提取输入图片的特征
2. 使用RPN网络来提取rois
3. 如果是训练，得到proposal_target，即分类和回归的ground truth，后续计算faster rcnn(6, 7)的loss时需要用到(8, 9)
4. 使用roi_pooling得到rois的feature map
5. 使用classifier提取特征
6. 使用faster_rcnn_cls得到分类结果
7. 使用faster_rcnn_reg得到回归结果
8. 如果是训练，计算分类loss
9. 如果是训练，计算回归loss
'''

LossTuple = namedtuple('LossTuple', ['rpn_loc_loss', 'rpn_cls_loss', 'roi_loc_loss', 'roi_cls_loss', 'total_loss'])


class FasterRCNNTrainer(nn.Module):
    def __init__(self, faster_rcnn, optimizer):
        super(FasterRCNNTrainer, self).__init__()

        self.faster_rcnn = faster_rcnn
        self.rpn_sigma = 1
        self.roi_sigma = 1

        # 编码anchor与RPN
        self.anchor_target_creator = AnchorTargetCreator()
        self.proposal_target_creator = ProposalTargetCreator()

        self.loc_normalize_mean = [0, 0, 0, 0]
        self.loc_normalize_std = [0.1, 0.1, 0.2, 0.2]

        self.optimizer = optimizer

    def forward(self, imgs, bboxes, labels, scale):
        n = imgs.shape[0]
        img_size = imgs.shape[2:]

        # 1. 获取公用特征层
        base_feature = self.faster_rcnn.extractor(imgs)

        # 2. 利用rpn网络获得先验框的得分与调整参数
        rpn_locs, rpn_scores, rois, roi_indices, anchor = self.faster_rcnn.rpn(base_feature, img_size, scale)

        # 将所有loss值都赋值为0
        rpn_loc_loss_all, rpn_cls_loss_all, roi_loc_loss_all, roi_cls_loss_all = 0, 0, 0, 0
        for i in range(n):
            bbox = bboxes[i]
            label = labels[i]
            rpn_loc = rpn_locs[i]
            rpn_score = rpn_scores[i]
            roi = rois[roi_indices == i]
            feature = base_feature[i]

            # 3. 利用真实框和先验框获得建议框网络应该有的预测结果
            # 给每个先验框都打上标签
            # gt_rpn_loc      [num_anchors, 4]
            # gt_rpn_label    [num_anchors, ]
            gt_rpn_loc, gt_rpn_label = self.anchor_target_creator(bbox, anchor, img_size)
            gt_rpn_loc = torch.Tensor(gt_rpn_loc)
            gt_rpn_label = torch.Tensor(gt_rpn_label).long()

            if rpn_loc.is_cuda:
                gt_rpn_loc = gt_rpn_loc.cuda()
                gt_rpn_label = gt_rpn_label.cuda()

            # 4. 分别计算建议框网络的回归损失和分类损失
            rpn_loc_loss = _fast_rcnn_loc_loss(rpn_loc, gt_rpn_loc, gt_rpn_label, self.rpn_sigma)
            rpn_cls_loss = F.cross_entropy(rpn_score, gt_rpn_label, ignore_index=-1)

            # 5. 利用真实框和建议框获得classifier网络应该有的预测结果
            # 获得三个变量，分别是sample_roi, gt_roi_loc, gt_roi_label
            # sample_roi      [n_sample, ]
            # gt_roi_loc      [n_sample, 4]
            # gt_roi_label    [n_sample, ]
            sample_roi, gt_roi_loc, gt_roi_label = self.proposal_target_creator(roi, bbox, label,
                                                                                self.loc_normalize_mean,
                                                                                self.loc_normalize_std)

            sample_roi = torch.Tensor(sample_roi)
            gt_roi_loc = torch.Tensor(gt_roi_loc)
            gt_roi_label = torch.Tensor(gt_roi_label).long()
            sample_roi_index = torch.zeros(len(sample_roi))

            if feature.is_cuda:
                sample_roi = sample_roi.cuda()
                sample_roi_index = sample_roi_index.cuda()
                gt_roi_loc = gt_roi_loc.cuda()
                gt_roi_label = gt_roi_label.cuda()

            # 6. 获得classifier网络预测结果
            roi_cls_loc, roi_score = self.faster_rcnn.head(torch.unsqueeze(feature, 0), sample_roi, sample_roi_index,
                                                           img_size)

            # 根据建议框的种类，取出对应的回归预测结果
            n_sample = roi_cls_loc.size()[1]
            roi_cls_loc = roi_cls_loc.view(n_sample, -1, 4)
            roi_loc = roi_cls_loc[torch.arange(0, n_sample), gt_roi_label]

            # 7. 分别计算Classifier网络的回归损失和分类损失
            roi_loc_loss = _fast_rcnn_loc_loss(roi_loc, gt_roi_loc, gt_roi_label.data, self.roi_sigma)
            roi_cls_loss = nn.CrossEntropyLoss()(roi_score[0], gt_roi_label)

            rpn_loc_loss_all += rpn_loc_loss
            rpn_cls_loss_all += rpn_cls_loss
            roi_loc_loss_all += roi_loc_loss
            roi_cls_loss_all += roi_cls_loss

        losses = [rpn_loc_loss_all / n, rpn_cls_loss_all / n, roi_loc_loss_all / n, roi_cls_loss_all / n]
        losses = losses + [sum(losses)]
        return LossTuple(*losses)

    def train_step(self, imgs, bboxes, labels, scale):
        self.optimizer.zero_grad()
        losses = self.forward(imgs, bboxes, labels, scale)
        losses.total_loss.backward()
        self.optimizer.step()
        return losses


def _smooth_l1_loss(x, t, sigma):
    sigma_squared = sigma ** 2
    regression_diff = (x - t)
    regression_diff = regression_diff.abs()
    regression_loss = torch.where(
        regression_diff < (1. / sigma_squared),
        0.5 * sigma_squared * regression_diff ** 2,
        regression_diff - 0.5 / sigma_squared
    )
    return regression_loss.sum()


def _fast_rcnn_loc_loss(pred_loc, gt_loc, gt_label, sigma):
    pred_loc = pred_loc[gt_label > 0]
    gt_loc = gt_loc[gt_label > 0]

    loc_loss = _smooth_l1_loss(pred_loc, gt_loc, sigma)
    num_pos = (gt_label > 0).sum().float()
    loc_loss /= torch.max(num_pos, torch.ones_like(num_pos))
    return loc_loss
