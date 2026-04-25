import os

def guardar_usuario(user_id, nombre):
    with open("usuarios.txt", "a") as f:
        f.write(f"{user_id},{nombre}\n")

def cargar_usuarios():
    usuarios = {}
    if not os.path.exists("usuarios.txt"):
        return usuarios

    with open("usuarios.txt", "r") as f:
        for linea in f:
            user_id, nombre = linea.strip().split(",")
            usuarios[int(user_id)] = nombre

    return usuarios