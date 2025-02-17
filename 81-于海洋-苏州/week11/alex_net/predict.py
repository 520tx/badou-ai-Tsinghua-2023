import numpy as np
import utils
import cv2
from tensorflow.keras import backend as K
from model.AlexNet import AlexNet

K.set_image_data_format('channels_last')

if __name__ == "__main__":
    model = AlexNet()
    model.load_weights("./logs/ep039-loss0.004-val_loss0.652.h5")
    img = cv2.imread("./Test.jpg")
    img_RGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_nor = img_RGB / 255
    img_nor = np.expand_dims(img_nor, axis=0)
    print("shape1", img_nor.shape)
    img_resize = utils.resize_image(img_nor, (224, 224))
    print("shape2", img_resize.shape)
    # utils.print_answer(np.argmax(model.predict(img)))
    print(utils.print_answer(np.argmax(model.predict(img_resize))))
    cv2.imshow("ooo", img)
    cv2.waitKey(0)
