# -*- coding: utf-8 -*-
# @Time    : 2023/7/7 15:28
# @Author  : zgh
# @FileName: network_kears.py
# @Software: PyCharm

from tensorflow.keras.datasets import mnist
import matplotlib.pyplot as plt
from tensorflow.keras import models
from tensorflow.keras import layers
from tensorflow.keras.utils import to_categorical


# 导入数据集
(train_images, train_labels), (test_images, test_labels) = mnist.load_data()
print('train_images.shape = ', train_images.shape)
print('tran_labels = ', train_labels)
print('test_images.shape = ', test_images.shape)
print('test_labels', test_labels)
#展示数据
digit = test_images[0]
plt.imshow(digit, cmap=plt.cm.binary)
plt.show()
# 构建网络
network = models.Sequential()
# in -> 512 -> 10
network.add(layers.Dense(512, activation='relu', input_shape=(28 * 28,)))
network.add(layers.Dense(10, activation='softmax'))

network.compile(optimizer='rmsprop', loss='categorical_crossentropy',
                metrics=['accuracy'])

# 图形拉伸成一维
train_images = train_images.reshape((60000, 28 * 28))
train_images = train_images.astype('float32') / 255

test_images = test_images.reshape((10000, 28 * 28))
test_images = test_images.astype('float32') / 255

print("before change:", test_labels[0])
train_labels = to_categorical(train_labels)
test_labels = to_categorical(test_labels)
print("after change: ", test_labels[0])

# 训练
network.fit(train_images, train_labels, epochs=5, batch_size=128)

# 测试
test_loss, test_acc = network.evaluate(test_images, test_labels, verbose=1)
print(test_loss)
print('test_acc', test_acc)

(train_images, train_labels), (test_images, test_labels) = mnist.load_data()
digit = test_images[1]
plt.imshow(digit, cmap=plt.cm.binary)
plt.show()
test_images = test_images.reshape((10000, 28 * 28))
res = network.predict(test_images)

for i in range(res[1].shape[0]):
	if (res[1][i] == 1):
		print("the number for the picture is : ", i)
		break

