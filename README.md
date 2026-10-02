# Venta Safari - Sistema Gastronómico Parque Safari 🦁🍴

Sistema web modular para la gestión gastronómica, control de cajas, comandas en tiempo real, asignación de personal y auditoría de locales en Parque Safari. Desarrollado en **Python & Django**.

---

## 🚀 Requisitos Previos

- **Python 3.10 o superior** instalado (verificar con `python --version`).
- `pip` (gestor de paquetes de Python).

---

## 🛠️ Guía Rápida de Instalación y Ejecución

Sigue estos sencillos pasos para importar y correr el proyecto en tu computadora:

### 1. Abrir una terminal en la carpeta del proyecto
Abre la consola (CMD, PowerShell o Terminal de VS Code) dentro de la carpeta raíz del proyecto.

### 2. (Recomendado) Crear y activar un entorno virtual

- En **Windows (PowerShell)**:
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
  *(Si PowerShell bloquea scripts, ejecuta una vez: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

- En **Windows (CMD)**:
  ```cmd
  python -m venv venv
  venv\Scripts\activate.bat
  ```

- En **Linux / macOS**:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Instalar las dependencias
Ejecuta el siguiente comando para instalar Django y las librerías necesarias:
```bash
pip install -r requirements.txt
```

### 4. Base de Datos Lista para Usar
El proyecto **ya incluye la base de datos `db.sqlite3` completamente configurada** con todos los locales, mesas, productos y usuarios de prueba.

> **Nota:** Si en algún momento deseas reiniciar la base de datos desde cero, puedes borrar el archivo `db.sqlite3` y ejecutar:
> ```bash
> python manage.py migrate
> python manage.py poblar_safari
> ```

### 5. Iniciar el Servidor de Desarrollo
Inicia el servidor local de Django:
```bash
python manage.py runserver
```

¡Listo! Abre tu navegador web en:
👉 **http://127.0.0.1:8000/**

---

## 👥 Cuentas de Acceso Demo Preconfiguradas

Todos los usuarios tienen la misma contraseña predeterminada: `safari123`

| Rol | Usuario | Contraseña | Punto de Venta Asignado |
| :--- | :--- | :--- | :--- |
| **Administrador General** | `rgomez` | `safari123` | Supervisión Global de Todos los Locales |
| **Administrador General** | `admin_safari` | `safari123` | Supervisión Global de Todos los Locales |
| **Cajero / Vendedor** | `cvalenzuela` | `safari123` | Restaurante Central Safari (ID 1) |
| **Cajero / Vendedor** | `dsilva` | `safari123` | Cafetería & Pastelería La Selva (ID 2) |
| **Cajero / Vendedor** | `csoto` | `safari123` | Barra Rápida & Kiosco Oasis (ID 3) |
| **Mesero** | `mmorales` | `safari123` | Restaurante Central Safari (ID 1) |
| **Mesero** | `eparedes` | `safari123` | Cafetería & Pastelería La Selva (ID 2) |
| **Mesero** | `rfuentes` | `safari123` | Barra Rápida & Kiosco Oasis (ID 3) |

---

## 📁 Estructura del Proyecto

```text
├── Venta_safari/             # Configuración central (settings, urls, asgi, wsgi)
├── ventas/                   # Aplicación principal
│   ├── management/commands/  # Comando administrativo `poblar_safari`
│   ├── migrations/           # Migraciones de base de datos
│   ├── templates/ventas/     # Plantillas HTML con Bootstrap 5
│   ├── models.py             # Modelos de datos (PuntoVenta, Jornada, Caja, Ticket, etc.)
│   ├── views.py              # Vistas y controladores de lógica de negocio
│   ├── urls.py               # Enrutamiento de URLs
│   └── tests.py              # Suite oficial de 15 pruebas automatizadas
├── static/                   # Recursos estáticos
│   ├── css/                  # Hojas de estilo modulares (base, admin, vendedor, etc.)
│   ├── js/                   # JavaScript (SweetAlert2, anti-doble envío, modales)
│   └── img/                  # Logos e imágenes del Parque Safari
├── db.sqlite3                # Base de datos SQLite pre-poblada
├── manage.py                 # Gestor de comandos de Django
├── requirements.txt          # Lista de dependencias de Python
├── AI_CONTEXT.md             # Memoria técnica y documentación de arquitectura
└── README.md                 # Esta guía de uso e importación
```

---

## 🧪 Ejecutar Pruebas Automatizadas

El proyecto incluye 15 pruebas unitarias y de integración que verifican la integridad de roles, aislamiento por punto de venta, control de caja y concurrencia:
```bash
python manage.py test ventas
```
*(Todas las 15 pruebas deben ejecutarse y aprobar con resultado `OK`)*.
