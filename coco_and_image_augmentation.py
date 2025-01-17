import os
import json
import cv2
import math
import numpy as np

def spinImage(image, angle, keep_size):
    H, W, _ = image.shape
    M = cv2.getRotationMatrix2D((W / 2, H / 2), angle, 1)
    if keep_size:
        # 根據旋轉矩陣進行仿射變換
        img_arr = cv2.warpAffine(image, M, (W, H))
    else:
        new_H = int(
            W * math.fabs(math.sin(math.radians(angle))) + H * math.fabs(
                math.cos(math.radians(angle))))
        new_W = int(
            H * math.fabs(math.sin(math.radians(angle))) + W * math.fabs(
                math.cos(math.radians(angle))))
        M[0, 2] += (new_W - W) / 2
        M[1, 2] += (new_H - H) / 2
        img_arr = cv2.warpAffine(image, M, (new_W, new_H))
    return img_arr

def rotate_point(origin, point, angle):
    ox, oy = origin
    px, py = point

    qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
    qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)

    return abs(int(qx)), abs(int(qy))

def update_rotate_bbox(updated_segmentations):
    # return [ltx, lty, width, height]
    segmentation_pairs = np.array(updated_segmentations).reshape(-1, 2).tolist()
    minX = 100000000
    minY = 100000000
    maxX = 0
    maxY = 0
    for segmentation_pair in segmentation_pairs:
        x, y = segmentation_pair
        if x < minX:
            minX = x
        if x > maxX:
            maxX = x
        if y < minY:
            minY = y
        if y > maxY:
            maxY = y
    return [minX, minY, (maxX - minX), (maxY - minY)]

# styles = [[angle, flip], [angle, flip] ...]
def coco_data_augmentation(img_path, json_path, img_save_path, json_save_path, styles, keep_size=True, json_encoding='utf-8', save_image=True):
    img_file_names = []
    for img_file_name in os.listdir(img_path):
        
        img_file_names.append(os.path.basename(img_file_name))

    result_json = {}
    result_images = []
    result_annotations = []
    result_annotations_id = 0  # 從0遞增

    image_shape_cache = {}

    with open(json_path, encoding=json_encoding) as json_f:
        coco_json = json.load(json_f)
        coco_info = coco_json['info']
        coco_licenses = coco_json['licenses']
        coco_categories = coco_json['categories']
        coco_images = coco_json['images']
        coco_annotations = coco_json['annotations']

        for style in styles:
            angle = style[0]
            flip = style[1]
            histo = style[2]

            #對圖檔擴增
            for img_file_name in img_file_names:
                image = cv2.imread(os.path.join(img_path, img_file_name))
                augmented_image = spinImage(image, angle, keep_size)

                if flip:
                    augmented_image = cv2.flip(augmented_image, 1)

                augmented_image = cv2.cvtColor(augmented_image, cv2.COLOR_BGR2GRAY)
                height, width, = augmented_image.shape

                if histo:
                    augmented_image = cv2.equalizeHist(augmented_image)

                if angle < 0:
                    angle_name = f"1{-angle}"
                else:
                    angle_name = f"{angle}"
                img_file_name = f"1{int(histo)}{int(flip)}{angle_name}{img_file_name}"
                image_shape_cache[os.path.splitext(img_file_name)[0]] = {
                    'width': width,
                    'height': height
                }
                if save_image:
                    cv2.imwrite(os.path.join(img_save_path, img_file_name), augmented_image)
                    print(f"{img_file_name} saved")

            #對json["images"]擴增
            for image_dict in coco_images:
                original_file_name = image_dict['file_name']
                if angle < 0:
                    angle_name = f"1{-angle}"
                else:
                    angle_name = f"{angle}"
                augmented_file_name = f"1{int(histo)}{int(flip)}{angle_name}{original_file_name}"
                augmented_id = int(os.path.splitext(augmented_file_name)[0])
                W = image_dict['width']
                H = image_dict['height']
                if not keep_size:
                    W = int(
                        W * math.fabs(math.sin(math.radians(angle))) + H * math.fabs(
                            math.cos(math.radians(angle))))
                    H = int(
                        H * math.fabs(math.sin(math.radians(angle))) + W * math.fabs(
                            math.cos(math.radians(angle))))
                augmented_image_dict = image_dict.copy()
                augmented_image_dict['id'] = augmented_id
                augmented_image_dict['file_name'] = augmented_file_name
                augmented_image_dict['width'] = W
                augmented_image_dict['height'] = H
                result_images.append(augmented_image_dict)
                print(f"{augmented_image_dict} add to images part")

            #對json["annotations"]擴增
            for annotation_dict in coco_annotations:
                augmented_annotation_dict = annotation_dict.copy()
                augmented_annotation_dict['id'] = result_annotations_id
                result_annotations_id += 1

                original_image_id = annotation_dict['image_id']
                if angle < 0:
                    angle_name = f"1{-angle}"
                else:
                    angle_name = f"{angle}"
                augmented_image_id = int(f'1{int(histo)}{int(flip)}{angle_name}{original_image_id}')
                augmented_annotation_dict['image_id'] = augmented_image_id
                image_width = image_shape_cache[f'{augmented_id}']['width']
                image_height = image_shape_cache[f'{augmented_id}']['height']
                origin = (round(image_width / 2), round(image_height / 2))
                # if flip:
                #     flip_x = image_width - original_bbox[0] - width
                #     flip_y = original_bbox[1]
                #     original_bbox = [flip_x, flip_y, width, height]


                original_segmentation = annotation_dict['segmentation']
                # 將segmentation變成[[x, y], [x, y] ...]
                original_segmentation_reshape = np.reshape(original_segmentation, (-1, 2))
                augmented_segmentation = [[]]
                for x, y in original_segmentation_reshape:
                    # if flip:
                    #     image_width = image_shape_cache[f'{augmented_id}']['width']
                    #     x = image_width - x
                    rad_angle = math.radians(angle)
                    new_x, new_y = rotate_point(origin, (x, y), -rad_angle)
                    if flip:
                        image_width = image_shape_cache[f'{augmented_image_id}']['width']
                        new_x = image_width - new_x
                    if new_x < 0:
                        print("error")
                    augmented_segmentation[0].append(new_x)
                    augmented_segmentation[0].append(new_y)
                augmented_annotation_dict['segmentation'] = augmented_segmentation

                # 轉換 bbox
                augmented_bbox = update_rotate_bbox(augmented_segmentation[0])
                augmented_annotation_dict['bbox'] = augmented_bbox

                result_annotations.append(augmented_annotation_dict)
                print(f'add {augmented_annotation_dict} to annotation part')

        result_json['info'] = coco_info
        result_json['licenses'] = coco_licenses
        result_json['categories'] = coco_categories
        result_json['images'] = result_images
        result_json['annotations'] = result_annotations

        with open(json_save_path, 'w', encoding='utf-8') as f:
            json.dump(result_json, f, ensure_ascii=False, indent=4)
            print(f'saved result_json in {json_save_path}')

if __name__ == '__main__':
    image_path = os.path.join(os.getcwd(), '../Datasets/chimei+ChestX_48times_augmentation/brightness_contrast/images')
    json_path = os.path.join(os.getcwd(), '../Datasets/chimei+ChestX_48times_augmentation/brightness_contrast/labels/4times_labels.json')
    image_save_path = os.path.join(os.getcwd(), '../Datasets/chimei+ChestX_48times_augmentation/images')
    json_save_path = os.path.join(os.getcwd(), '../Datasets/chimei+ChestX_48times_augmentation/labels/all.json')
    # styles = [[0, False, False], [5, False, False], [10, False, False], [-5, False, False], [-10, False, False], [0, True, False], [5, True, False], [10, True, False], [-5, True, False], [-10, True, False],
    #           [0, False, True], [5, False, True], [10, False, True], [-5, False, True], [-10, False, True], [0, True, True], [5, True, True], [10, True, True], [-5, True, True], [-10, True, True]]
    styles = [[0, False, False], [10, False, False], [-10, False, False],
              [0, False, True], [10, False, True], [-10, False, True],
              [0, True, False], [10, True, False], [-10, True, False],
              [0, True, True], [10, True, True], [-10, True, True]]  # 12 times
    coco_data_augmentation(image_path, json_path, image_save_path, json_save_path, styles)
