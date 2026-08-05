import math
import json
import numpy as np
import matplotlib
import cv2
from comfy.utils import ProgressBar
from typing import List, Dict

eps = 0.01

def extend_scalelist(scalelist_behavior, pose_json, hands_scale, body_scale, head_scale, overall_scale, match_scalelist_method, only_scale_pose_index) -> List[list]:
    if pose_json.startswith('{'):
        pose_json = '[{}]'.format(pose_json)
    poses = json.loads(pose_json)
    # initialize scale lists
    hands_scalelist, body_scalelist, head_scalelist, overall_scalelist = [], [], [], []
    num_imgs = 0
    num_poses = 0
    scale_values = [hands_scale, body_scale, head_scale, overall_scale]
    scale_lists = [hands_scalelist, body_scalelist, head_scalelist, overall_scalelist]
    for img in poses:
        default_scale = 0.0
        default_num_person = 1
        if 'people' in img:
            default_scale = 1.0
            default_num_person = len(img['people'])
            subscales = [default_scale]*default_num_person
            if scalelist_behavior == 'poses':
                for i, scales in enumerate(scale_values):
                    if isinstance(scales, (list, tuple)):
                        if len(scales) >= num_poses + default_num_person:
                            if only_scale_pose_index<default_num_person and only_scale_pose_index >= -default_num_person:
                                subscales[only_scale_pose_index] = scales[num_poses + only_scale_pose_index]
                            else:
                                subscales = scales[num_poses:num_poses + default_num_person]
                        else:
                            if match_scalelist_method == 'no extend':
                                subscales = [default_scale]*default_num_person
                            elif match_scalelist_method == 'loop extend':
                                extend_scaleslist = scales*math.ceil((num_poses+default_num_person) / len(scales))
                                if only_scale_pose_index<default_num_person and only_scale_pose_index >= -default_num_person:
                                    subscales[only_scale_pose_index] = extend_scaleslist[num_poses + only_scale_pose_index]
                                else:
                                    subscales = extend_scaleslist[num_poses:num_poses + default_num_person]
                            elif match_scalelist_method == 'clamp extend':
                                if only_scale_pose_index<default_num_person and only_scale_pose_index >= -default_num_person:
                                    subscales[only_scale_pose_index] = scales[-1]
                                else:
                                    subscales = [scales[-1]] * default_num_person
                    else:
                        if only_scale_pose_index<default_num_person and only_scale_pose_index >= -default_num_person:
                            subscales[only_scale_pose_index] = scales
                        else:
                            subscales = [scales] * default_num_person

                    scale_lists[i].append(subscales.copy())
            else:
                for i, scales in enumerate(scale_values):
                    if isinstance(scales, (list, tuple)):
                        if len(scales) >= num_imgs + 1:
                            if only_scale_pose_index<default_num_person and only_scale_pose_index >= -default_num_person:
                                subscales[only_scale_pose_index] = scales[num_imgs]
                            else:
                                subscales = scales[num_poses]*default_num_person
                        else:
                            if match_scalelist_method == 'no extend':
                                subscales = [default_scale]*default_num_person
                            elif match_scalelist_method == 'loop extend':
                                extend_scaleslist = scales*math.ceil((num_imgs+1) / len(scales))
                                if only_scale_pose_index<default_num_person and only_scale_pose_index >= -default_num_person:
                                    subscales[only_scale_pose_index] = extend_scaleslist[num_imgs]
                                else:
                                    subscales = extend_scaleslist[num_imgs]*default_num_person
                            elif match_scalelist_method == 'clamp extend':
                                if only_scale_pose_index<default_num_person and only_scale_pose_index >= -default_num_person:
                                    subscales[only_scale_pose_index] = scales[-1]
                                else:
                                    subscales = [scales[-1]] * default_num_person
                    else:
                        if only_scale_pose_index<default_num_person and only_scale_pose_index >= -default_num_person:
                            subscales[only_scale_pose_index] = scales
                        else:
                            subscales = [scales] * default_num_person

                    scale_lists[i].append(subscales.copy())

            num_poses += default_num_person
            num_imgs += 1
        else:
            # if no people in image
            for i in range(len(scale_values)):
                scale_lists[i].append([default_scale])

    return scale_lists

def pose_normalized(pose_json):
    if pose_json.startswith('{'):
        pose_json = '[{}]'.format(pose_json)
    images = json.loads(pose_json)
    for image in images:
        if 'people' not in image:
            continue
        figures = image['people']
        H = image['canvas_height']
        W = image['canvas_width']
        for figure in figures:
            for key, dim_x, dim_y in [
                ('pose_keypoints_2d', W, H),
                ('face_keypoints_2d', W, H),
                ('hand_left_keypoints_2d', W, H),
                ('hand_right_keypoints_2d', W, H),
            ]:
                kpts = figure.get(key)
                if not kpts:
                    continue
                if max(kpts) > 2.0:
                    for i in range(0, len(kpts), 3):
                        kpts[i] = kpts[i] / float(dim_x)
                        kpts[i+1] = kpts[i+1] / float(dim_y)
                # Clamp x,y to [0,1] so the editor's normalization detection
                # (bn.every(v => Math.abs(v) <= 1)) always passes. Without this,
                # keypoints outside the canvas boundary (e.g. y > canvas_height)
                # produce normalized values > 1.0 which cause the editor to
                # misidentify the array as pixel-space, placing all body points
                # at sub-pixel coordinates in the upper-left corner.
                for i in range(0, len(kpts), 3):
                    kpts[i] = max(0.0, min(1.0, kpts[i]))
                    kpts[i+1] = max(0.0, min(1.0, kpts[i+1]))
    return json.dumps(images)

def scale(point, scale_factor, pivot):
    return [(point[i] - pivot[i])*scale_factor + pivot[i] for i in range(len(point))]

def draw_pose_json(pose_json, resolution_x, show_body, show_face, show_hands, pose_marker_size, face_marker_size, hand_marker_size, hands_scalelist, body_scalelist, head_scalelist, overall_scalelist):
    pose_imgs = []
    pose_scaled = []

    if pose_json:
        if pose_json.startswith('{'):
            pose_json = '[{}]'.format(pose_json)
        images = json.loads(pose_json)
        pbar = ProgressBar(len(images))
        for img_idx, image in enumerate(images):
            if 'people' not in image:
                pbar.update(len(images))
                return pose_imgs
            figures = image['people']
            H = image['canvas_height']
            W = image['canvas_width']

            bodies = []
            candidate = []
            subset = [[]]
            faces = []
            hands = []

            openpose_json = []
            for pose_idx, figure in enumerate(figures):
                body_scale = body_scalelist[img_idx][pose_idx]
                hands_scale = hands_scalelist[img_idx][pose_idx]
                head_scale = head_scalelist[img_idx][pose_idx]
                overall_scale = overall_scalelist[img_idx][pose_idx]
                body = []
                face = []
                lhand = []
                rhand = []
                if 'pose_keypoints_2d' in figure:
                    body = figure['pose_keypoints_2d']
                    if body is None:
                        body = []
                if 'face_keypoints_2d' in figure:
                    face = figure['face_keypoints_2d']
                    if face is None:
                        face = []
                if 'hand_left_keypoints_2d' in figure:
                    lhand = figure['hand_left_keypoints_2d']
                    if lhand is None:
                        lhand = []
                if 'hand_right_keypoints_2d' in figure:
                    rhand = figure['hand_right_keypoints_2d']
                    if rhand is None:
                        rhand = []

                body_scaled = body.copy()
                face_scaled = face.copy()
                lhand_scaled = lhand.copy()
                rhand_scaled = rhand.copy()

                face_offset = [0, 0]
                lhand_offset = [0, 0]
                rhand_offset = [0, 0]

                overall_pivot = [0.5, 0.5]
                lhand_pivot = [0.25, 0.5]
                rhand_pivot = [0.75, 0.5]
                face_pivot = [0.5, 0.5]

                if body:
                    candidate_start_idx = len(candidate)

                    for i in range(0,len(body),3):
                        p_scaled = scale(body[i:i+2], body_scale, overall_pivot)
                        p_scaled = scale(p_scaled, overall_scale, overall_pivot)
                        body_scaled[i:i+2] = p_scaled
                        candidate.append(p_scaled)

                    figure_head_idx = candidate_start_idx
                    if figure_head_idx < len(candidate):
                        factor = 0.8
                        face_offset = [(candidate[figure_head_idx][0] - body[0])*factor, (candidate[figure_head_idx][1] - body[1])*factor]
                        face_pivot = candidate[figure_head_idx]

                    wrist_left_idx = candidate_start_idx + 7
                    wrist_right_idx = candidate_start_idx + 4

                    if wrist_left_idx < len(candidate) and len(body) > 22:
                        lhand_offset = [candidate[wrist_left_idx][0] - body[21], candidate[wrist_left_idx][1] - body[22]]
                        lhand_pivot = candidate[wrist_left_idx]

                    if wrist_right_idx < len(candidate) and len(body) > 13:
                        rhand_offset = [candidate[wrist_right_idx][0] - body[12], candidate[wrist_right_idx][1] - body[13]]
                        rhand_pivot = candidate[wrist_right_idx]

                    if not subset[0]:
                        subset[0].extend([candidate_start_idx+(i//3) if body[i+2]>0 else -1 for i in range(0,len(body),3)])
                    else:
                        new_subset = [candidate_start_idx+(i//3) if body[i+2]>0 else -1 for i in range(0,len(body),3)]
                        subset.append(new_subset)

                if face:
                    f = []
                    for i in range(0,len(face),3):
                        p = face[i:i+2]
                        p_offset = [p[0] + face_offset[0], p[1] + face_offset[1]]
                        p_scaled = scale(p_offset, head_scale, face_pivot)
                        p_scaled = scale(p_scaled, overall_scale, overall_pivot)
                        face_scaled[i:i+2] = p_scaled
                        f.append(p_scaled)
                    faces.append(f)

                if lhand:
                    lh = []
                    for i in range(0, len(lhand), 3):
                        p = lhand[i:i+2]
                        p_offset = [p[0] + lhand_offset[0], p[1] + lhand_offset[1]]
                        p_scaled = scale(p_offset, hands_scale, lhand_pivot)
                        p_scaled = scale(p_scaled, overall_scale, overall_pivot)
                        lhand_scaled[i:i+2] = p_scaled
                        lh.append(p_scaled)
                    hands.append(lh)

                if rhand:
                    rh = []
                    for i in range(0, len(rhand), 3):
                        p = rhand[i:i+2]
                        p_offset = [p[0] + rhand_offset[0], p[1] + rhand_offset[1]]
                        p_scaled = scale(p_offset, hands_scale, rhand_pivot)
                        p_scaled = scale(p_scaled, overall_scale, overall_pivot)
                        rhand_scaled[i:i+2] = p_scaled
                        rh.append(p_scaled)
                    hands.append(rh)
                openpose_json.append(dict(pose_keypoints_2d=body_scaled, face_keypoints_2d=face_scaled, hand_left_keypoints_2d=lhand_scaled, hand_right_keypoints_2d=rhand_scaled))

            bodies = dict(candidate=candidate, subset=subset)
            pose = dict(bodies=bodies, faces=faces, hands=hands)
            pose = dict(bodies=bodies if show_body else {'candidate':[], 'subset':[]}, faces=faces if show_face else [], hands=hands if show_hands else [])

            W_scaled = resolution_x
            if resolution_x < 64:
                W_scaled = W
            H_scaled = int(H*(W_scaled*1.0/W))
            openpose_json = {
                            'people': openpose_json,
                            'canvas_height': H_scaled,
                            'canvas_width': W_scaled,
                            }

            pose_img = draw_pose(pose, H_scaled, W_scaled, pose_marker_size, face_marker_size, hand_marker_size)
            pose_imgs.append(pose_img)
            pose_scaled.append(openpose_json)
            pbar.update(1)

    return pose_imgs, pose_scaled

def draw_pose(pose, H, W, pose_marker_size, face_marker_size, hand_marker_size):
    bodies = pose['bodies']
    faces = pose['faces']
    hands = pose['hands']
    candidate = bodies['candidate']
    subset = bodies['subset']
    canvas = np.zeros(shape=(H, W, 3), dtype=np.uint8)

    if len(candidate) > 0:
        canvas = draw_bodypose(canvas, candidate, subset, pose_marker_size)

    if len(hands) > 0:
        canvas = draw_handpose(canvas, hands, hand_marker_size)

    if len(faces) > 0:
        canvas = draw_facepose(canvas, faces, face_marker_size)

    return canvas

def draw_bodypose(canvas, candidate, subset, pose_marker_size):
    H, W, C = canvas.shape
    candidate = np.array(candidate)
    subset = np.array(subset)

    # stickwidth = 4

    limbSeq = [[2, 3], [2, 6], [3, 4], [4, 5], [6, 7], [7, 8], [2, 9], [9, 10], \
               [10, 11], [2, 12], [12, 13], [13, 14], [2, 1], [1, 15], [15, 17], \
               [1, 16], [16, 18], [3, 17], [6, 18]]

    colors = [[255, 0, 0], [255, 85, 0], [255, 170, 0], [255, 255, 0], [170, 255, 0], [85, 255, 0], [0, 255, 0], \
              [0, 255, 85], [0, 255, 170], [0, 255, 255], [0, 170, 255], [0, 85, 255], [0, 0, 255], [85, 0, 255], \
              [170, 0, 255], [255, 0, 255], [255, 0, 170], [255, 0, 85]]

    for i in range(17):
        for n in range(len(subset)):
            index = subset[n][np.array(limbSeq[i]) - 1]
            if -1 in index:
                continue
            Y = candidate[index.astype(int), 0] * float(W)
            X = candidate[index.astype(int), 1] * float(H)
            mX = np.mean(X)
            mY = np.mean(Y)
            length = ((X[0] - X[1]) ** 2 + (Y[0] - Y[1]) ** 2) ** 0.5
            angle = math.degrees(math.atan2(X[0] - X[1], Y[0] - Y[1]))
            polygon = cv2.ellipse2Poly((int(mY), int(mX)), (int(length / 2), pose_marker_size), int(angle), 0, 360, 1)
            cv2.fillConvexPoly(canvas, polygon, colors[i])

    canvas = (canvas * 0.6).astype(np.uint8)

    for i in range(18):
        for n in range(len(subset)):
            index = int(subset[n][i])
            if index == -1:
                continue
            x, y = candidate[index][0:2]
            x = int(x * W)
            y = int(y * H)
            cv2.circle(canvas, (int(x), int(y)), pose_marker_size, colors[i], thickness=-1)

    return canvas


def draw_handpose(canvas, all_hand_peaks, hand_marker_size):
    H, W, C = canvas.shape

    edges = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [5, 6], [6, 7], [7, 8], [0, 9], [9, 10], \
             [10, 11], [11, 12], [0, 13], [13, 14], [14, 15], [15, 16], [0, 17], [17, 18], [18, 19], [19, 20]]

    for peaks in all_hand_peaks:
        peaks = np.array(peaks)

        for ie, e in enumerate(edges):
            x1, y1 = peaks[e[0]]
            x2, y2 = peaks[e[1]]
            x1 = int(x1 * W)
            y1 = int(y1 * H)
            x2 = int(x2 * W)
            y2 = int(y2 * H)
            if x1 > eps and y1 > eps and x2 > eps and y2 > eps:
                cv2.line(canvas, (x1, y1), (x2, y2), matplotlib.colors.hsv_to_rgb([ie / float(len(edges)), 1.0, 1.0]) * 255, thickness=1 if hand_marker_size == 0 else hand_marker_size)

        joint_size=0
        if hand_marker_size < 2:
            joint_size = hand_marker_size + 1
        else:
            joint_size = hand_marker_size + 2
        for i, keyponit in enumerate(peaks):
            x, y = keyponit
            x = int(x * W)
            y = int(y * H)
            if x > eps and y > eps:
                cv2.circle(canvas, (x, y), joint_size, (0, 0, 255), thickness=-1)
    return canvas


def draw_facepose(canvas, all_lmks, face_marker_size):
    H, W, C = canvas.shape
    for lmks in all_lmks:
        lmks = np.array(lmks)
        for lmk in lmks:
            x, y = lmk
            x = int(x * W)
            y = int(y * H)
            if x > eps and y > eps:
                cv2.circle(canvas, (x, y), face_marker_size, (255, 255, 255), thickness=-1)
    return canvas
