"""Contenido configurable del ejercicio (Tablas 1 y 3 del informe).

Los mensajes son ejemplos de trabajo: ajústalos aquí cuando el docente y el
coordinador los aprueben. No uses nombres, logotipos ni firmas oficiales.
"""

VARIANTS = {
    "curiosidad": {
        "nombre": "Curiosidad",
        "slug": "curiosidad",
        "color": "#4f7cff",
        "mensaje": "Escanea. No vas a creer lo que hay detrás.",
        "palabras": "escanea, descubre, lo que hay detrás",
        "mecanismo": "Crea un vacío de información que la persona quiere cerrar",
    },
    "utilidad": {
        "nombre": "Utilidad académica",
        "slug": "utilidad",
        "color": "#ff6b3d",
        "mensaje": "Internet para estudiantes. Escanea y conéctate.",
        "palabras": "internet gratis, WiFi, acceso libre, para estudiantes",
        "mecanismo": "Ofrece un recurso diario, sin costo y de forma inmediata",
    },
    "urgencia": {
        "nombre": "Urgencia",
        "slug": "urgencia",
        "color": "#8a3ffc",
        "mensaje": "Últimas horas: cupo limitado. Escanea ahora.",
        "palabras": "últimas horas, cupo limitado, ahora",
        "mecanismo": "La presión de tiempo reduce la reflexión y la verificación",
    },
    "informativa": {
        "nombre": "Apariencia informativa",
        "slug": "informativa",
        "color": "#12b5a0",
        "mensaje": "Aviso: nuevo servicio de información estudiantil.",
        "palabras": "aviso, nuevo servicio, información estudiantil",
        "mecanismo": "Imita el tono de una comunicación oficial para generar confianza",
    },
}

# Formulario (Tabla 3). Las claves de las opciones son las que se guardan.
QUESTIONS = [
    {
        "id": "q1",
        "texto": "¿Qué te llevó a escanear el código?",
        "corto": "Motivación para escanear",
        "opciones": {
            "curiosidad": "Curiosidad",
            "util": "Me pareció útil",
            "oficial": "Parecía información oficial",
            "otra": "Otra razón",
        },
    },
    {
        "id": "q2",
        "texto": "Antes de escanear, ¿verificaste quién lo publicó o a dónde llevaba?",
        "corto": "Verificación previa",
        "opciones": {
            "ambas": "Sí, ambas cosas",
            "una": "Solo una",
            "ninguna": "No verifiqué nada",
        },
    },
    {
        "id": "q3",
        "texto": "¿Notaste alguna señal de riesgo antes de escanear?",
        "corto": "Señales de riesgo",
        "opciones": {"si": "Sí", "no": "No", "nose": "No estoy seguro"},
    },
    {
        "id": "q4",
        "texto": "Después de esta explicación, ¿cambiarás la forma en que escaneas códigos QR?",
        "corto": "Cambio de hábito",
        "opciones": {"si": "Sí", "tal_vez": "Tal vez", "no": "No"},
    },
]

EVENT_TYPES = {
    "scan": "Escaneo",
    "read": "Lectura",
    "response": "Respuesta",
}
