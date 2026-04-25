import tkinter as tk
import threading
import queue
import os
import shutil
import cv2
import numpy as np
from PIL import Image, ImageTk

from entrenamiento import entrenar_modelo
from login import iniciar_sesion_thread
from registro import registrar_usuario_thread
from usuarios import cargar_usuarios

CONTRASENA_ADMIN = "123"

# ─── Paleta ────────────────────────────────────────────────────────────
BG      = "#0D0D0D"
CARD    = "#1A1A1A"
BORDER  = "#2A2A2A"
ACCENT  = "#C8FF00"
ACCENT2 = "#00CFFF"
TEXT    = "#F0F0F0"
SUBTEXT = "#666666"
DANGER  = "#FF4040"
SUCCESS = "#00FF88"
WARN    = "#FFAA00"

# ─── Escala automática ─────────────────────────────────────────────────
# Se crea root primero solo para leer la resolución real de la pantalla
root = tk.Tk()
root.withdraw()   # ocultar mientras calculamos

SCREEN_W = root.winfo_screenwidth()
SCREEN_H = root.winfo_screenheight()

# Diseño base: 420 x 660  (resolución de referencia)
BASE_W, BASE_H = 420, 660
S = min(SCREEN_W / BASE_W, SCREEN_H / BASE_H)   # factor de escala
S = max(0.5, min(S, 2.0))                        # límites: 50% – 200%

def sc(n):
    """Escala un valor numérico (px, padding, tamaño de fuente)."""
    return max(1, int(round(n * S)))

# ─── Fuentes escaladas ─────────────────────────────────────────────────
FONT_TITLE = ("Courier New", sc(30), "bold")
FONT_LABEL = ("Courier New", sc(11))
FONT_SMALL = ("Courier New", sc(9))
FONT_BTN   = ("Courier New", sc(11), "bold")
FONT_MONO  = ("Courier New", sc(10))

# ─── Visor de cámara escalado ──────────────────────────────────────────
CAM_W = sc(320)
CAM_H = sc(200)

# ─── Tamaños de ventana escalados ──────────────────────────────────────
WIN_W = sc(BASE_W)
WIN_H = sc(BASE_H)


# ─── Botón neon (usa S internamente) ──────────────────────────────────
class NeonButton(tk.Canvas):
    def __init__(self, parent, text, command=None,
                 color=ACCENT, btn_width=240, btn_height=46, **kwargs):
        bw = sc(btn_width)
        bh = sc(btn_height)
        super().__init__(parent, width=bw, height=bh,
                         bg=BG, highlightthickness=0, cursor="hand2", **kwargs)
        self._cmd, self._color, self._text = command, color, text
        self._bw, self._bh = bw, bh
        self._enabled = True
        self._draw(False)
        self.bind("<Enter>",    lambda _: self._draw(True)  if self._enabled else None)
        self.bind("<Leave>",    lambda _: self._draw(False) if self._enabled else None)
        self.bind("<Button-1>", lambda _: self._cmd()       if self._cmd and self._enabled else None)

    def _draw(self, hover):
        self.delete("all")
        color = self._color if self._enabled else BORDER
        fill  = color if hover and self._enabled else BG
        tfill = BG if hover and self._enabled else color
        w, h, r = self._bw, self._bh, sc(4)
        self.create_rectangle(r, r, w-r, h-r, outline=color, fill=fill, width=2)
        d = sc(2)
        for cx, cy in [(r,r),(w-r,r),(r,h-r),(w-r,h-r)]:
            self.create_rectangle(cx-d, cy-d, cx+d, cy+d, fill=color, outline="")
        self.create_text(w//2, h//2, text=self._text, font=FONT_BTN, fill=tfill)

    def habilitar(self, v=True):
        self._enabled = v
        self._draw(False)


# ─── Utilidades ────────────────────────────────────────────────────────
def centrar(win, w, h):
    px = root.winfo_x() + (root.winfo_width()  - w) // 2
    py = root.winfo_y() + (root.winfo_height() - h) // 2
    win.geometry(f"{w}x{h}+{px}+{py}")


def frame_a_tk(frame_bgr, tw, th):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    res = cv2.resize(rgb, (tw, th))
    return ImageTk.PhotoImage(Image.fromarray(res))


def placeholder_tk(tw, th, msg1="SIN SENAL", msg2=""):
    img = np.zeros((th, tw, 3), dtype=np.uint8)
    fs  = max(0.3, 0.65 * S)
    x1  = max(5, tw//2 - int(65 * S))
    cv2.putText(img, msg1, (x1, th//2 - sc(8)),
                cv2.FONT_HERSHEY_SIMPLEX, fs, (50, 50, 50), 2)
    if msg2:
        fs2 = max(0.25, 0.42 * S)
        cv2.putText(img, msg2, (sc(10), th//2 + sc(20)),
                    cv2.FONT_HERSHEY_SIMPLEX, fs2, (50, 50, 50), 1)
    return ImageTk.PhotoImage(Image.fromarray(img))


def mostrar_notif(titulo, mensaje, color=ACCENT, parent=None):
    p = parent or root
    dlg = tk.Toplevel(p)
    dlg.title("")
    dlg.configure(bg=BG)
    dlg.resizable(False, False)
    dlg.transient(p)
    dlg.focus()
    w, h = sc(360), sc(180)
    px = p.winfo_x() + (p.winfo_width()  - w) // 2
    py = p.winfo_y() + (p.winfo_height() - h) // 2
    dlg.geometry(f"{w}x{h}+{px}+{py}")
    outer = tk.Frame(dlg, bg=color, padx=1, pady=1)
    outer.pack(fill="both", expand=True, padx=sc(8), pady=sc(8))
    inner = tk.Frame(outer, bg=BG, padx=sc(20), pady=sc(16))
    inner.pack(fill="both", expand=True)
    tk.Label(inner, text=f"// {titulo}", font=FONT_LABEL, bg=BG, fg=color).pack(anchor="w")
    tk.Label(inner, text=mensaje, font=FONT_SMALL, bg=BG, fg=TEXT,
             wraplength=sc(300), justify="left").pack(anchor="w", pady=(sc(8), sc(12)))
    NeonButton(inner, "OK", dlg.destroy, color=color,
               btn_width=290, btn_height=38).pack()
    dlg.wait_window()


def confirmar_dialogo(titulo, mensaje, parent=None):
    p = parent or root
    dlg = tk.Toplevel(p)
    dlg.title("")
    dlg.configure(bg=BG)
    dlg.resizable(False, False)
    dlg.transient(p)
    dlg.focus()
    w, h = sc(380), sc(210)
    px = p.winfo_x() + (p.winfo_width()  - w) // 2
    py = p.winfo_y() + (p.winfo_height() - h) // 2
    dlg.geometry(f"{w}x{h}+{px}+{py}")
    outer = tk.Frame(dlg, bg=DANGER, padx=1, pady=1)
    outer.pack(fill="both", expand=True, padx=sc(8), pady=sc(8))
    inner = tk.Frame(outer, bg=BG, padx=sc(20), pady=sc(16))
    inner.pack(fill="both", expand=True)
    tk.Label(inner, text=f"// {titulo}", font=FONT_LABEL, bg=BG, fg=DANGER).pack(anchor="w")
    tk.Label(inner, text=mensaje, font=FONT_SMALL, bg=BG, fg=TEXT,
             wraplength=sc(320), justify="left").pack(anchor="w", pady=(sc(8), sc(14)))
    result = [False]
    def si(): result[0] = True; dlg.destroy()
    def no(): dlg.destroy()
    bf = tk.Frame(inner, bg=BG)
    bf.pack(fill="x")
    NeonButton(bf, "ELIMINAR", si, color=DANGER,  btn_width=160, btn_height=38).pack(side="left")
    NeonButton(bf, "CANCELAR", no, color=SUBTEXT, btn_width=160, btn_height=38).pack(side="right")
    dlg.wait_window()
    return result[0]


def pedir_contrasena():
    dlg = tk.Toplevel(root)
    dlg.title("")
    dlg.configure(bg=BG)
    dlg.resizable(False, False)
    dlg.transient(root)
    dlg.focus()
    centrar(dlg, sc(340), sc(210))
    outer = tk.Frame(dlg, bg=ACCENT, padx=1, pady=1)
    outer.pack(fill="both", expand=True, padx=sc(8), pady=sc(8))
    inner = tk.Frame(outer, bg=BG, padx=sc(20), pady=sc(20))
    inner.pack(fill="both", expand=True)
    tk.Label(inner, text="// ACCESO ADMIN", font=FONT_LABEL, bg=BG, fg=ACCENT).pack(anchor="w")
    tk.Label(inner, text="Contrasena:", font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack(anchor="w", pady=(sc(10), sc(2)))
    var = tk.StringVar()
    entry = tk.Entry(inner, textvariable=var, show="*", bg=CARD, fg=TEXT,
                     insertbackground=ACCENT, relief="flat", font=FONT_MONO,
                     bd=0, highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
    entry.pack(fill="x", ipady=sc(6))
    entry.focus()
    result = [None]
    def confirmar(e=None): result[0] = var.get(); dlg.destroy()
    def cancelar(): dlg.destroy()
    bf = tk.Frame(inner, bg=BG)
    bf.pack(pady=(sc(14), 0), fill="x")
    NeonButton(bf, "CONFIRMAR", confirmar, color=ACCENT, btn_width=130, btn_height=36).pack(side="left")
    NeonButton(bf, "CANCELAR",  cancelar,  color=DANGER, btn_width=130, btn_height=36).pack(side="right")
    entry.bind("<Return>", confirmar)
    dlg.wait_window()
    return result[0]


# ─── Gestión de usuarios ───────────────────────────────────────────────
def eliminar_usuario_archivos(user_id):
    ruta = f"rostros/{user_id}"
    if os.path.exists(ruta):
        shutil.rmtree(ruta)
    usuarios = cargar_usuarios()
    usuarios.pop(int(user_id), None)
    with open("usuarios.txt", "w") as f:
        for uid, nombre in usuarios.items():
            f.write(f"{uid},{nombre}\n")
    for arch in ["modelo.yml", "label_map.npy"]:
        if os.path.exists(arch):
            os.remove(arch)
    if usuarios:
        entrenar_modelo()


def ventana_usuarios():
    contrasena = pedir_contrasena()
    if contrasena != CONTRASENA_ADMIN:
        mostrar_notif("ERROR", "Contrasena incorrecta", DANGER)
        return

    win = tk.Toplevel(root)
    win.title("Gestion de Usuarios")
    win.configure(bg=BG)
    win.resizable(False, False)
    win.focus()
    w, h = sc(420), sc(500)
    centrar(win, w, h)

    outer = tk.Frame(win, bg=WARN, padx=1, pady=1)
    outer.pack(fill="both", expand=True, padx=sc(8), pady=sc(8))
    inner = tk.Frame(outer, bg=BG, padx=sc(16), pady=sc(14))
    inner.pack(fill="both", expand=True)

    tk.Label(inner, text="// USUARIOS REGISTRADOS", font=FONT_LABEL,
             bg=BG, fg=WARN).pack(anchor="w")
    tk.Frame(inner, bg=WARN, height=1).pack(fill="x", pady=(sc(4), sc(10)))

    list_frame = tk.Frame(inner, bg=BORDER, padx=1, pady=1)
    list_frame.pack(fill="both", expand=True)

    scrollbar = tk.Scrollbar(list_frame, orient="vertical",
                              bg=CARD, troughcolor=BG,
                              activebackground=WARN, width=sc(12))
    scrollbar.pack(side="right", fill="y")

    listbox = tk.Listbox(list_frame,
                          bg=CARD, fg=TEXT,
                          selectbackground=WARN,
                          selectforeground=BG,
                          font=FONT_MONO,
                          relief="flat", bd=0,
                          highlightthickness=0,
                          activestyle="none",
                          yscrollcommand=scrollbar.set,
                          cursor="hand2")
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=listbox.yview)

    info_frame = tk.Frame(inner, bg=CARD, height=sc(36))
    info_frame.pack(fill="x", pady=(sc(8), 0))
    info_frame.pack_propagate(False)
    info_lbl = tk.Label(info_frame, text="Selecciona un usuario",
                         font=FONT_SMALL, bg=CARD, fg=SUBTEXT, anchor="w")
    info_lbl.pack(side="left", padx=sc(10), fill="y")
    fotos_lbl = tk.Label(info_frame, text="",
                          font=FONT_SMALL, bg=CARD, fg=ACCENT2, anchor="e")
    fotos_lbl.pack(side="right", padx=sc(10), fill="y")

    btn_row = tk.Frame(inner, bg=BG)
    btn_row.pack(fill="x", pady=(sc(10), 0))

    usuarios_data = {}

    def cargar_lista():
        listbox.delete(0, tk.END)
        usuarios_data.clear()
        usuarios = cargar_usuarios()
        if not usuarios:
            listbox.insert(tk.END, "  (Sin usuarios registrados)")
            btn_eliminar.habilitar(False)
            return
        for i, (uid, nombre) in enumerate(sorted(usuarios.items())):
            fotos = len(os.listdir(f"rostros/{uid}")) if os.path.exists(f"rostros/{uid}") else 0
            listbox.insert(tk.END, f"  ID: {uid:>4}   {nombre}")
            usuarios_data[i] = (uid, nombre, fotos)
        btn_eliminar.habilitar(False)

    def on_select(event):
        sel = listbox.curselection()
        if not sel or sel[0] not in usuarios_data: return
        uid, nombre, fotos = usuarios_data[sel[0]]
        info_lbl.config(text=f"ID {uid}  —  {nombre}", fg=TEXT)
        fotos_lbl.config(text=f"{fotos} fotos")
        btn_eliminar.habilitar(True)

    listbox.bind("<<ListboxSelect>>", on_select)

    def eliminar_seleccionado():
        sel = listbox.curselection()
        if not sel or sel[0] not in usuarios_data: return
        uid, nombre, fotos = usuarios_data[sel[0]]
        ok = confirmar_dialogo(
            "CONFIRMAR ELIMINACION",
            f"Vas a eliminar a {nombre} (ID {uid}).\n"
            f"Se borran {fotos} fotos y se reentrena el modelo.\n"
            f"Esta accion no se puede deshacer.",
            parent=win
        )
        if not ok: return
        info_lbl.config(text="Eliminando...", fg=WARN)
        win.update()
        eliminar_usuario_archivos(uid)
        cargar_lista()
        info_lbl.config(text="Usuario eliminado correctamente", fg=SUCCESS)
        fotos_lbl.config(text="")

    btn_eliminar = NeonButton(btn_row, "ELIMINAR USUARIO", eliminar_seleccionado,
                               color=DANGER, btn_width=220, btn_height=44)
    btn_eliminar.pack(side="left")
    NeonButton(btn_row, "CERRAR", win.destroy,
               color=SUBTEXT, btn_width=120, btn_height=44).pack(side="right")

    cargar_lista()


# ─── Registro con cámara ───────────────────────────────────────────────
def ventana_registro():
    contrasena = pedir_contrasena()
    if contrasena != CONTRASENA_ADMIN:
        mostrar_notif("ERROR", "Contrasena incorrecta", DANGER)
        return

    win = tk.Toplevel(root)
    win.title("Registro de Usuario")
    win.configure(bg=BG)
    win.resizable(False, False)
    win.focus()
    w, h = sc(420), sc(600)
    centrar(win, w, h)

    outer = tk.Frame(win, bg=ACCENT2, padx=1, pady=1)
    outer.pack(fill="both", expand=True, padx=sc(8), pady=sc(8))
    inner = tk.Frame(outer, bg=BG, padx=sc(16), pady=sc(14))
    inner.pack(fill="both", expand=True)

    tk.Label(inner, text="// NUEVO USUARIO", font=FONT_LABEL,
             bg=BG, fg=ACCENT2).pack(anchor="w")
    tk.Frame(inner, bg=ACCENT2, height=1).pack(fill="x", pady=(sc(4), sc(10)))

    cam_outer_reg = tk.Frame(inner, bg=ACCENT2, padx=1, pady=1)
    cam_outer_reg.pack()
    reg_cam_lbl = tk.Label(cam_outer_reg, bg="black", width=CAM_W, height=CAM_H)
    reg_cam_lbl.pack()
    win.update_idletasks()
    ph = placeholder_tk(CAM_W, CAM_H, "CAMARA LISTA", "Completa los datos y presiona INICIAR")
    reg_cam_lbl.config(image=ph); reg_cam_lbl.image = ph

    prog_bar_frame = tk.Frame(inner, bg=CARD, height=sc(28))
    prog_bar_frame.pack(fill="x", pady=(sc(6), 0))
    prog_bar_frame.pack_propagate(False)
    prog_lbl = tk.Label(prog_bar_frame, text="EN ESPERA",
                         font=FONT_SMALL, bg=CARD, fg=SUBTEXT, anchor="w")
    prog_lbl.pack(side="left", padx=sc(8), fill="y")
    prog_count = tk.Label(prog_bar_frame, text="0/30",
                           font=FONT_SMALL, bg=CARD, fg=ACCENT2, anchor="e")
    prog_count.pack(side="right", padx=sc(8), fill="y")

    bar_canvas = tk.Canvas(inner, bg=CARD, height=sc(6), highlightthickness=0)
    bar_canvas.pack(fill="x", pady=(sc(2), sc(8)))

    def actualizar_barra(n, total=30):
        bar_canvas.delete("all")
        bw = bar_canvas.winfo_width()
        if bw < 2: return
        filled = int((n / total) * bw)
        bar_canvas.create_rectangle(0, 0, bw, sc(6), fill=BORDER, outline="")
        bar_canvas.create_rectangle(0, 0, filled, sc(6), fill=ACCENT2, outline="")

    def campo(lbl_txt):
        tk.Label(inner, text=lbl_txt, font=FONT_SMALL,
                 bg=BG, fg=SUBTEXT).pack(anchor="w", pady=(sc(8), sc(2)))
        e = tk.Entry(inner, bg=CARD, fg=TEXT, insertbackground=ACCENT2,
                     relief="flat", font=FONT_MONO, bd=0,
                     highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT2)
        e.pack(fill="x", ipady=sc(6))
        return e

    e_nombre = campo("Nombre completo")
    e_id     = campo("ID de usuario (numero)")

    reg_frame_q    = queue.Queue(maxsize=2)
    reg_progreso_q = queue.Queue()
    reg_stop_evt   = [None]
    reg_poll_id    = [None]
    reg_activa     = [False]

    def actualizar_visor_reg():
        ultimo = None
        while True:
            try:   ultimo = reg_frame_q.get_nowait()
            except queue.Empty: break
        if ultimo is not None:
            foto = frame_a_tk(ultimo, CAM_W, CAM_H)
            reg_cam_lbl.config(image=foto); reg_cam_lbl.image = foto
        while True:
            try:
                msg = reg_progreso_q.get_nowait()
                if msg.startswith("ERROR:"):
                    prog_lbl.config(text=msg[6:], fg=DANGER)
                    terminar_registro(exito=False); return
                elif msg == "CANCELADO":
                    prog_lbl.config(text="Cancelado", fg=DANGER)
                    terminar_registro(exito=False); return
                elif msg == "ENTRENANDO":
                    prog_lbl.config(text="Entrenando modelo...", fg=ACCENT)
                    prog_count.config(text="30/30")
                    actualizar_barra(30)
                    win.update()
                    entrenar_modelo()
                    terminar_registro(exito=True); return
                else:
                    n = int(msg.split("/")[0])
                    prog_lbl.config(text="Capturando rostro...", fg=ACCENT2)
                    prog_count.config(text=msg)
                    actualizar_barra(n)
            except queue.Empty: break
        if reg_activa[0]:
            reg_poll_id[0] = win.after(30, actualizar_visor_reg)

    def iniciar_captura():
        nombre  = e_nombre.get().strip()
        user_id = e_id.get().strip()
        if not nombre or not user_id:
            prog_lbl.config(text="[!] Completa todos los campos", fg=DANGER); return
        if not user_id.isdigit():
            prog_lbl.config(text="[!] El ID debe ser numerico", fg=DANGER); return
        reg_activa[0]   = True
        reg_stop_evt[0] = threading.Event()
        btn_iniciar.habilitar(False)
        btn_cancelar_reg.habilitar(True)
        prog_lbl.config(text="Iniciando camara...", fg=ACCENT2)
        threading.Thread(target=registrar_usuario_thread,
                         args=(nombre, user_id, reg_frame_q,
                               reg_progreso_q, reg_stop_evt[0]),
                         daemon=True).start()
        reg_poll_id[0] = win.after(30, actualizar_visor_reg)

    def cancelar_captura():
        if reg_activa[0] and reg_stop_evt[0]:
            reg_stop_evt[0].set()

    def terminar_registro(exito=True):
        reg_activa[0] = False
        if reg_poll_id[0]:
            win.after_cancel(reg_poll_id[0]); reg_poll_id[0] = None
        btn_iniciar.habilitar(True)
        btn_cancelar_reg.habilitar(False)
        if exito:
            nombre = e_nombre.get().strip()
            prog_lbl.config(text=f"[OK] {nombre} registrado", fg=SUCCESS)
            ph2 = placeholder_tk(CAM_W, CAM_H, "REGISTRO OK", nombre)
            reg_cam_lbl.config(image=ph2); reg_cam_lbl.image = ph2
            win.after(2000, win.destroy)
        else:
            ph3 = placeholder_tk(CAM_W, CAM_H, "CAMARA LISTA",
                                  "Completa los datos y presiona INICIAR")
            reg_cam_lbl.config(image=ph3); reg_cam_lbl.image = ph3

    btn_row = tk.Frame(inner, bg=BG)
    btn_row.pack(fill="x", pady=(sc(10), 0))
    btn_iniciar = NeonButton(btn_row, "INICIAR CAPTURA", iniciar_captura,
                              color=ACCENT2, btn_width=220, btn_height=44)
    btn_iniciar.pack(side="left")
    btn_cancelar_reg = NeonButton(btn_row, "CANCELAR", cancelar_captura,
                                   color=DANGER, btn_width=120, btn_height=44)
    btn_cancelar_reg.pack(side="right")
    btn_cancelar_reg.habilitar(False)

    def on_close():
        if reg_activa[0] and reg_stop_evt[0]:
            reg_stop_evt[0].set()
        win.destroy()
    win.protocol("WM_DELETE_WINDOW", on_close)


# ─── Login con cámara en vivo ──────────────────────────────────────────
_frame_q    = queue.Queue(maxsize=2)
_result_q   = queue.Queue()
_stop_evt   = None
_poll_id    = None
_cam_activa = False


def _actualizar_visor():
    global _poll_id
    ultimo = None
    while True:
        try:   ultimo = _frame_q.get_nowait()
        except queue.Empty: break
    if ultimo is not None:
        foto = frame_a_tk(ultimo, CAM_W, CAM_H)
        cam_label.config(image=foto); cam_label.image = foto
    try:
        resultado = _result_q.get_nowait()
        _on_resultado(resultado); return
    except queue.Empty: pass
    if _cam_activa:
        _poll_id = root.after(30, _actualizar_visor)


def iniciar_login():
    global _stop_evt, _poll_id, _cam_activa
    if _cam_activa: return
    if not os.path.exists("modelo.yml"):
        mostrar_notif("SIN MODELO", "Registra un usuario primero.", DANGER); return
    while not _frame_q.empty():
        try: _frame_q.get_nowait()
        except: pass
    while not _result_q.empty():
        try: _result_q.get_nowait()
        except: pass
    _stop_evt   = threading.Event()
    _cam_activa = True
    btn_login.habilitar(False)
    status_lbl.config(text="ESCANEANDO...", fg=ACCENT)
    threading.Thread(target=iniciar_sesion_thread,
                     args=(_frame_q, _result_q, _stop_evt),
                     daemon=True).start()
    _poll_id = root.after(30, _actualizar_visor)


def cancelar_camara():
    """Detiene la cámara y cierra la aplicación."""
    global _cam_activa, _poll_id
    # Detener hilo de cámara si está activo
    if _stop_evt: _stop_evt.set()
    if _poll_id: root.after_cancel(_poll_id); _poll_id = None
    _cam_activa = False
    root.destroy()   # cierra la app completamente


def _on_resultado(resultado):
    global _cam_activa, _poll_id
    _cam_activa = False
    if _poll_id: root.after_cancel(_poll_id); _poll_id = None
    btn_login.habilitar(True)
    if resultado and "Bienvenido" in resultado:
        status_lbl.config(text="ACCESO OK", fg=SUCCESS)
        mostrar_notif("ACCESO CONCEDIDO", resultado, SUCCESS)
    elif resultado == "Acceso denegado":
        status_lbl.config(text="DENEGADO", fg=DANGER)
        mostrar_notif("ACCESO DENEGADO", "Usuario no autorizado", DANGER)
    else:
        status_lbl.config(text="EN ESPERA", fg=SUBTEXT)
        mostrar_notif("INFO", resultado or "Cancelado", SUBTEXT)
    ph = placeholder_tk(CAM_W, CAM_H, "SIN SENAL", "Presiona  INICIAR SESION")
    cam_label.config(image=ph); cam_label.image = ph


# ─── Ventana principal ─────────────────────────────────────────────────
root.deiconify()   # mostrar ahora que todo está listo
root.title("Sistema Moto Inteligente")
root.configure(bg=BG)
root.resizable(False, False)

sx = (SCREEN_W - WIN_W) // 2
sy = (SCREEN_H - WIN_H) // 2
root.geometry(f"{WIN_W}x{WIN_H}+{sx}+{sy}")

# ── Header ──
header = tk.Frame(root, bg=BG)
header.pack(fill="x", padx=sc(30), pady=(sc(18), 0))
tk.Label(header, text="MOTO", font=FONT_TITLE, bg=BG, fg=ACCENT).pack(side="left")
tk.Label(header, text="ID",   font=FONT_TITLE, bg=BG, fg=TEXT).pack(side="left")
tk.Frame(root, bg=ACCENT, height=1).pack(fill="x", padx=sc(30), pady=(sc(4), 0))
tk.Label(root, text="Sistema de encendido por reconocimiento facial",
         font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack(pady=(sc(3), 0))

# ── Visor login ──
cam_outer = tk.Frame(root, bg=ACCENT, padx=1, pady=1)
cam_outer.pack(padx=sc(30), pady=(sc(10), 0))
cam_label = tk.Label(cam_outer, bg="black", width=CAM_W, height=CAM_H)
cam_label.pack()
root.update_idletasks()
ph_init = placeholder_tk(CAM_W, CAM_H, "SIN SENAL", "Presiona  INICIAR SESION")
cam_label.config(image=ph_init); cam_label.image = ph_init

# ── Barra de estado ──
cam_bar = tk.Frame(root, bg=CARD)
cam_bar.pack(fill="x", padx=sc(30))
status_lbl = tk.Label(cam_bar, text="EN ESPERA", font=FONT_SMALL,
                       bg=CARD, fg=SUBTEXT, anchor="w")
status_lbl.pack(side="left", padx=sc(8), pady=sc(4))
NeonButton(cam_bar, "CANCELAR", cancelar_camara,
           color=DANGER, btn_width=90, btn_height=26).pack(side="right", padx=sc(6), pady=sc(3))

tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=sc(30), pady=(sc(10), 0))

# ── Botones principales ──
btn_area = tk.Frame(root, bg=BG)
btn_area.pack(pady=sc(10))

btn_login = NeonButton(btn_area, "> INICIAR SESION", iniciar_login,
                        color=ACCENT, btn_width=320, btn_height=48)
btn_login.pack(pady=sc(5))

NeonButton(btn_area, "+ REGISTRAR USUARIO", ventana_registro,
           color=ACCENT2, btn_width=320, btn_height=48).pack(pady=sc(5))

NeonButton(btn_area, "  GESTIONAR USUARIOS", ventana_usuarios,
           color=WARN, btn_width=320, btn_height=48).pack(pady=sc(5))

# ── Footer ──
tk.Frame(root, bg=BORDER, height=1).pack(fill="x", padx=sc(30))
footer = tk.Frame(root, bg=BG)
footer.pack(fill="x", padx=sc(30), pady=sc(8))
tk.Label(footer, text=f"v3.0  //  {SCREEN_W}x{SCREEN_H}  //  escala {S:.2f}x",
         font=FONT_SMALL, bg=BG, fg=SUBTEXT).pack(side="left")
tk.Label(footer, text="[*] ONLINE",
         font=FONT_SMALL, bg=BG, fg=SUCCESS).pack(side="right")

root.mainloop()
