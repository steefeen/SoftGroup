# Copyright (c) Gorilla-Lab. All rights reserved.
import argparse
import glob
import os
os.environ['KMP_DUPLICATE_LIB_OK']='True'

import os.path as osp

import numpy as np
import pandas as pd
import torch
from sklearn.neighbors import NearestNeighbors

ROOM_TYPES = {
    'conferenceRoom': 0,
    'copyRoom': 1,
    'hallway': 2,
    'office': 3,
    'pantry': 4,
    'WC': 5,
    'auditorium': 6,
    'storage': 7,
    'lounge': 8,
    'lobby': 9,
    'openspace': 10,
}

INV_OBJECT_LABEL = {
    0: 'ceiling',
    1: 'floor',
    2: 'wall',
    3: 'beam',
    4: 'column',
    5: 'window',
    6: 'door',
    7: 'chair',
    8: 'table',
    9: 'bookcase',
    10: 'sofa',
    11: 'board',
    12: 'clutter',
}

OBJECT_LABEL = {name: i for i, name in INV_OBJECT_LABEL.items()}


def object_name_to_label(object_class):
    r"""convert from object name in S3DIS to an int"""
    object_label = OBJECT_LABEL.get(object_class, OBJECT_LABEL['clutter'])
    return object_label


# modify from https://github.com/nicolas-chaulet/torch-points3d/blob/master/torch_points3d/datasets/segmentation/s3dis.py  # noqa
def read_s3dis_format(area_id: str,
                      room_name: str,
                      data_root: str = './',
                      label_out: bool = True,
                      verbose: bool = False):
    r"""
    extract data from a room folder
    """
    room_type = room_name.split('_')[0]
    room_label = ROOM_TYPES[room_type]
    room_dir = osp.join(data_root, area_id, room_name)
    raw_path = osp.join(room_dir, f'{room_name}.txt')
#hallway_2.txt
    print(raw_path)
    # room_ver = pd.read_csv(raw_path, sep=' ',
    #                       # dtype={0: 'float64', 1: 'float64', 2: 'float64', 3: 'float64', 4: 'float64', 5: 'float64'},
    #                        header=None, error_bad_lines=False)
    # print(room_ver.dtypes)
    # print(len(room_ver))
    # room_ver = room_ver.values

    room_ver = pd.read_csv(raw_path, sep=',', header=None).values
    xyz = np.ascontiguousarray(room_ver[:, 0:3], dtype='float32')
    rgb = np.ascontiguousarray(room_ver[:, 3:6], dtype='uint8')
    if not label_out:
        return xyz, rgb
    n_ver = len(room_ver)
    del room_ver
    nn = NearestNeighbors(n_neighbors=1, algorithm='kd_tree').fit(xyz)
    semantic_labels = np.zeros((n_ver, ), dtype='int64')
    room_label = np.asarray([room_label])
    instance_labels = np.ones((n_ver, ), dtype='int64') * -100
    objects = glob.glob(osp.join(room_dir, 'Annotations', '*.txt'))
    i_object = 1
    for single_object in objects:
        object_name = os.path.splitext(os.path.basename(single_object))[0]
        if verbose:
            print(f'adding object {i_object} : {object_name}')
        object_class = object_name.split('_')[0]
        object_label = object_name_to_label(object_class)
        obj_ver = pd.read_csv(single_object, sep=' ', header=None).values
        _, obj_ind = nn.kneighbors(obj_ver[:, 0:3])
        semantic_labels[obj_ind] = object_label
        # if object_label < 3: # background object
        #     continue
        instance_labels[obj_ind] = i_object
        i_object = i_object + 1

    return (
        xyz,
        rgb,
        semantic_labels,
        instance_labels,
        room_label,
    )


def get_parser():
    parser = argparse.ArgumentParser(description='s3dis data prepare')
    parser.add_argument(
        '--data-root', type=str, default='./raw', help='root dir save data')
    parser.add_argument(
        '--save-dir', type=str, default='./preprocess', help='directory save processed data')
    parser.add_argument(
        '--patch', action='store_true', help='patch data or not (just patch at first time running)')
    parser.add_argument('--align', action='store_true', help='processing aligned dataset or not')
    parser.add_argument('--verbose', action='store_true', help='show processing room name or not')

    args_cfg = parser.parse_args()

    return args_cfg


# patch -ruN -p0 -d  raw < s3dis.patch
if __name__ == '__main__':
    args = get_parser()
    data_root = args.data_root
    # processed data output dir
    save_dir = args.save_dir
    os.makedirs(save_dir, exist_ok=True)

    area_id = "Area_1"
    print(f'Processing: {area_id}')
    area_dir = osp.join(data_root, area_id)
    # get the room name list for each area
    room_name_list = os.listdir(area_dir)
    try:
        room_name_list.remove(f'{area_id}_alignmentAngle.txt')
        room_name_list.remove('.DS_Store')
    except:  # noqa
        pass
    for room_name in room_name_list:
        scene = f'{area_id}_{room_name}'
        if args.verbose:
            print(f'processing: {scene}')
        save_path = osp.join(save_dir, scene + '_inst_nostuff.pth')
        if osp.exists(save_path):
            continue
        (xyz, rgb, semantic_labels, instance_labels,
         room_label) = read_s3dis_format(area_id, room_name, data_root)
        rgb = (rgb / 127.5) - 1
        torch.save((xyz, rgb, semantic_labels, instance_labels, room_label, scene), save_path)
