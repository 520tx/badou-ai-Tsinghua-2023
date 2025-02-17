import cv2
import numpy as np

def nearest_interpolation(img, out_dim):
    src_h, src_w, channel = img.shape
    dst_h, dst_w = out_dim
    if dst_h == src_h and dst_w == src_w:
        return img
    dst_img = np.zeros((dst_h, dst_w, channel), img.dtype)
    scale_x, scale_y = src_w / dst_w, src_h / dst_h
    for i in range(channel):
        for dst_y in range(dst_h):
            for dst_x in range(dst_w):
                src_x, src_y = min(int(dst_x * scale_x + 0.5), src_w - 1), min(int(dst_y * scale_y + 0.5), src_h - 1)
                dst_img[dst_y, dst_x, i] = img[src_y, src_x, i]
    return dst_img

img = cv2.imread('./img/lenna.png')
res_img = nearest_interpolation(img, (800, 800))
test_img = cv2.resize(img, (800, 800), interpolation=cv2.INTER_NEAREST)
cv2.imshow("pre_img", img)
cv2.imshow("res_img", res_img)
cv2.imshow("test_img", test_img)
cv2.waitKey(0)