import cv2
import os
import numpy as np

def entrenar_modelo():
    data_path = "rostros"

    if not os.path.exists(data_path):
        print("No hay datos para entrenar")
        return

    people = os.listdir(data_path)

    labels = []
    faces_data = []
    label = 0
    label_map = {}

    for person in people:
        person_path = os.path.join(data_path, person)

        if not os.path.isdir(person_path):
            continue

        label_map[label] = int(person)

        for file in os.listdir(person_path):
            img_path = os.path.join(person_path, file)
            img = cv2.imread(img_path, 0)

            if img is None:
                continue

            faces_data.append(img)
            labels.append(label)

        label += 1

    if len(faces_data) == 0:
        print("No hay imágenes válidas")
        return

    recognizer = cv2.face.LBPHFaceRecognizer_create()
    recognizer.train(faces_data, np.array(labels))
    recognizer.write("modelo.yml")

    np.save("label_map.npy", label_map)

    print("Modelo entrenado correctamente")