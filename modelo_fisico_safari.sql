-- ==============================================================================
-- PROYECTO INTEGRADO: SISTEMA GASTRONÓMICO PARQUE SAFARI
-- EVIDENCIA: MODELO FÍSICO DE BASE DE DATOS (SCRIPT DDL)
-- Motor Compatible: PostgreSQL / MySQL / SQLite (Sintaxis ANSI SQL Estándar)
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 0. LIMPIEZA PREVENTIVA DE TABLAS (ORDEN INVERSO DE DEPENDENCIAS)
-- ------------------------------------------------------------------------------
DROP TABLE IF EXISTS detalle_consumo_interno CASCADE;
DROP TABLE IF EXISTS consumo_interno CASCADE;
DROP TABLE IF EXISTS entrega CASCADE;
DROP TABLE IF EXISTS ticket CASCADE;
DROP TABLE IF EXISTS detalle_pedido CASCADE;
DROP TABLE IF EXISTS pedido CASCADE;
DROP TABLE IF EXISTS detalle_venta CASCADE;
DROP TABLE IF EXISTS venta CASCADE;
DROP TABLE IF EXISTS mesa CASCADE;
DROP TABLE IF EXISTS precio_especial CASCADE;
DROP TABLE IF EXISTS menu_productos CASCADE;
DROP TABLE IF EXISTS menu CASCADE;
DROP TABLE IF EXISTS producto_puntos_venta CASCADE;
DROP TABLE IF EXISTS producto CASCADE;
DROP TABLE IF EXISTS categoria CASCADE;
DROP TABLE IF EXISTS caja CASCADE;
DROP TABLE IF EXISTS jornada CASCADE;
DROP TABLE IF EXISTS alerta_traslado CASCADE;
DROP TABLE IF EXISTS perfil_empleado CASCADE;
DROP TABLE IF EXISTS auth_user CASCADE;
DROP TABLE IF EXISTS punto_venta CASCADE;

-- ==============================================================================
-- 1. MÓDULO DE LOCALES / PUNTOS DE VENTA (RF03 / RF04)
-- ==============================================================================
CREATE TABLE punto_venta (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    tipo VARCHAR(50),                         -- Ej: 'Restaurante', 'Cafetería', 'Kiosco'
    descripcion TEXT,
    icono VARCHAR(50) DEFAULT 'bi-shop',      -- Icono Bootstrap
    color VARCHAR(20) DEFAULT '#c62828',      -- Color hex distintivo
    activo BOOLEAN DEFAULT TRUE,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- 2. MÓDULO DE USUARIOS, ROLES Y AUDITORÍA DE TRABAJADORES (RF01)
-- ==============================================================================
-- Tabla base de usuarios (representa el modelo auth_user de Django)
CREATE TABLE auth_user (
    id SERIAL PRIMARY KEY,
    username VARCHAR(150) NOT NULL UNIQUE,
    first_name VARCHAR(150),
    last_name VARCHAR(150),
    email VARCHAR(254),
    password VARCHAR(128) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_staff BOOLEAN DEFAULT FALSE,
    is_superuser BOOLEAN DEFAULT FALSE,
    date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Extensión de perfil del empleado con rol y puesto único de trabajo
CREATE TABLE perfil_empleado (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL UNIQUE,
    rol VARCHAR(20) NOT NULL DEFAULT 'CAJERO',
    rut VARCHAR(12),
    telefono VARCHAR(20),
    punto_venta_actual_id INT,
    activo BOOLEAN DEFAULT TRUE,
    CONSTRAINT fk_perfil_usuario FOREIGN KEY (usuario_id) REFERENCES auth_user(id) ON DELETE CASCADE,
    CONSTRAINT fk_perfil_puntoventa FOREIGN KEY (punto_venta_actual_id) REFERENCES punto_venta(id) ON DELETE SET NULL,
    CONSTRAINT chk_rol_valido CHECK (rol IN ('ADMINISTRADOR', 'CAJERO', 'MESERO'))
);

-- Registro y auditoría de reasignación / traslado de personal entre locales
CREATE TABLE alerta_traslado (
    id SERIAL PRIMARY KEY,
    empleado_id INT NOT NULL,
    punto_venta_origen_id INT,
    punto_venta_destino_id INT NOT NULL,
    autorizado_por_id INT,
    motivo VARCHAR(255) DEFAULT 'Reasignación operativa de personal',
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    leida BOOLEAN DEFAULT FALSE,
    CONSTRAINT fk_traslado_empleado FOREIGN KEY (empleado_id) REFERENCES auth_user(id) ON DELETE CASCADE,
    CONSTRAINT fk_traslado_origen FOREIGN KEY (punto_venta_origen_id) REFERENCES punto_venta(id) ON DELETE SET NULL,
    CONSTRAINT fk_traslado_destino FOREIGN KEY (punto_venta_destino_id) REFERENCES punto_venta(id) ON DELETE CASCADE,
    CONSTRAINT fk_traslado_autorizado FOREIGN KEY (autorizado_por_id) REFERENCES auth_user(id) ON DELETE SET NULL
);

-- ==============================================================================
-- 3. MÓDULO DE OPERACIÓN DIARIA: JORNADA Y CAJAS (RF02 / RF03)
-- ==============================================================================
-- Ciclo de jornada diaria único y global de Parque Safari
CREATE TABLE jornada (
    id SERIAL PRIMARY KEY,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    fecha_hora_apertura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_hora_cierre TIMESTAMP NULL,
    estado VARCHAR(15) DEFAULT 'ABIERTA',
    usuario_apertura_id INT NOT NULL,
    usuario_cierre_id INT NULL,
    observaciones TEXT,
    CONSTRAINT fk_jornada_user_apertura FOREIGN KEY (usuario_apertura_id) REFERENCES auth_user(id) ON DELETE RESTRICT,
    CONSTRAINT fk_jornada_user_cierre FOREIGN KEY (usuario_cierre_id) REFERENCES auth_user(id) ON DELETE RESTRICT,
    CONSTRAINT chk_jornada_estado CHECK (estado IN ('ABIERTA', 'CERRADA'))
);

-- Cajas individuales por cajero, punto de venta y jornada
CREATE TABLE caja (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    punto_venta_id INT NOT NULL,
    jornada_id INT NOT NULL,
    cajero_id INT NOT NULL,
    monto_apertura DECIMAL(10,2) DEFAULT 0.00,
    monto_cierre DECIMAL(10,2) NULL,
    fecha_hora_apertura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_hora_cierre TIMESTAMP NULL,
    estado VARCHAR(15) DEFAULT 'ABIERTA',
    observaciones TEXT,
    CONSTRAINT fk_caja_puntoventa FOREIGN KEY (punto_venta_id) REFERENCES punto_venta(id) ON DELETE RESTRICT,
    CONSTRAINT fk_caja_jornada FOREIGN KEY (jornada_id) REFERENCES jornada(id) ON DELETE RESTRICT,
    CONSTRAINT fk_caja_cajero FOREIGN KEY (cajero_id) REFERENCES auth_user(id) ON DELETE RESTRICT,
    CONSTRAINT chk_caja_estado CHECK (estado IN ('ABIERTA', 'CERRADA')),
    CONSTRAINT uq_caja_cajero_jornada UNIQUE (jornada_id, cajero_id)
);

-- ==============================================================================
-- 4. MÓDULO DE MESAS Y ESPACIOS OPERATIVOS (RF06)
-- ==============================================================================
CREATE TABLE mesa (
    id SERIAL PRIMARY KEY,
    identificador VARCHAR(20) NOT NULL,        -- Ej: 'Mesa 1', 'Terraza 4'
    punto_venta_id INT NOT NULL,
    capacidad INT DEFAULT 4,
    estado VARCHAR(20) DEFAULT 'HABILITADA',
    CONSTRAINT fk_mesa_puntoventa FOREIGN KEY (punto_venta_id) REFERENCES punto_venta(id) ON DELETE RESTRICT,
    CONSTRAINT chk_mesa_estado CHECK (estado IN ('HABILITADA', 'OCUPADA', 'RESERVADA', 'INACTIVA')),
    CONSTRAINT uq_mesa_identificador_local UNIQUE (identificador, punto_venta_id)
);

-- ==============================================================================
-- 5. MÓDULO DE CATÁLOGO GASTRONÓMICO Y MENÚS (RF05)
-- ==============================================================================
CREATE TABLE categoria (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT,
    activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE producto (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL,
    categoria_id INT NOT NULL,
    precio_base DECIMAL(10,2) NOT NULL,
    descripcion TEXT,
    activo BOOLEAN DEFAULT TRUE,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_producto_categoria FOREIGN KEY (categoria_id) REFERENCES categoria(id) ON DELETE RESTRICT
);

-- Relación N:M entre Productos y Puntos de Venta (disponibilidad)
CREATE TABLE producto_puntos_venta (
    id SERIAL PRIMARY KEY,
    producto_id INT NOT NULL,
    puntoventa_id INT NOT NULL,
    CONSTRAINT fk_ppv_producto FOREIGN KEY (producto_id) REFERENCES producto(id) ON DELETE CASCADE,
    CONSTRAINT fk_ppv_puntoventa FOREIGN KEY (puntoventa_id) REFERENCES punto_venta(id) ON DELETE CASCADE,
    CONSTRAINT uq_producto_puntoventa UNIQUE (producto_id, puntoventa_id)
);

-- Menú específico por local
CREATE TABLE menu (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    punto_venta_id INT NOT NULL,
    activo BOOLEAN DEFAULT TRUE,
    CONSTRAINT fk_menu_puntoventa FOREIGN KEY (punto_venta_id) REFERENCES punto_venta(id) ON DELETE CASCADE
);

-- Relación N:M entre Menús y Productos de la carta
CREATE TABLE menu_productos (
    id SERIAL PRIMARY KEY,
    menu_id INT NOT NULL,
    producto_id INT NOT NULL,
    CONSTRAINT fk_mp_menu FOREIGN KEY (menu_id) REFERENCES menu(id) ON DELETE CASCADE,
    CONSTRAINT fk_mp_producto FOREIGN KEY (producto_id) REFERENCES producto(id) ON DELETE CASCADE,
    CONSTRAINT uq_menu_producto UNIQUE (menu_id, producto_id)
);

-- Precios especiales o convenios institucionales
CREATE TABLE precio_especial (
    id SERIAL PRIMARY KEY,
    producto_id INT NOT NULL,
    nombre_condicion VARCHAR(100) NOT NULL,
    precio DECIMAL(10,2) NOT NULL,
    fecha_inicio DATE NULL,
    fecha_fin DATE NULL,
    activo BOOLEAN DEFAULT TRUE,
    CONSTRAINT fk_precioesp_producto FOREIGN KEY (producto_id) REFERENCES producto(id) ON DELETE CASCADE
);

-- ==============================================================================
-- 6. MÓDULO DE VENTAS Y TRANSACCIONES (RF07 / RF08)
-- ==============================================================================
CREATE TABLE venta (
    id SERIAL PRIMARY KEY,
    caja_id INT NOT NULL,
    cajero_id INT NOT NULL,
    punto_venta_id INT NOT NULL,
    modalidad VARCHAR(20) DEFAULT 'VENTA_RAPIDA',
    mesa_id INT NULL,
    metodo_pago VARCHAR(20) DEFAULT 'EFECTIVO',
    total DECIMAL(12,2) DEFAULT 0.00,
    estado VARCHAR(20) DEFAULT 'PAGADA',
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_venta_caja FOREIGN KEY (caja_id) REFERENCES caja(id) ON DELETE RESTRICT,
    CONSTRAINT fk_venta_cajero FOREIGN KEY (cajero_id) REFERENCES auth_user(id) ON DELETE RESTRICT,
    CONSTRAINT fk_venta_puntoventa FOREIGN KEY (punto_venta_id) REFERENCES punto_venta(id) ON DELETE RESTRICT,
    CONSTRAINT fk_venta_mesa FOREIGN KEY (mesa_id) REFERENCES mesa(id) ON DELETE SET NULL,
    CONSTRAINT chk_venta_modalidad CHECK (modalidad IN ('VENTA_RAPIDA', 'MESA')),
    CONSTRAINT chk_venta_metodopago CHECK (metodo_pago IN ('EFECTIVO', 'DEBITO', 'CREDITO', 'TRANSFERENCIA')),
    CONSTRAINT chk_venta_estado CHECK (estado IN ('PAGADA', 'ANULADA'))
);

CREATE TABLE detalle_venta (
    id SERIAL PRIMARY KEY,
    venta_id INT NOT NULL,
    producto_id INT NOT NULL,
    cantidad INT NOT NULL DEFAULT 1,
    precio_aplicado DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_detventa_venta FOREIGN KEY (venta_id) REFERENCES venta(id) ON DELETE CASCADE,
    CONSTRAINT fk_detventa_producto FOREIGN KEY (producto_id) REFERENCES producto(id) ON DELETE RESTRICT
);

-- ==============================================================================
-- 7. MÓDULO DE COMANDAS, PRODUCCIÓN Y TICKETS TÉRMICOS (RF09 / RF10)
-- ==============================================================================
CREATE TABLE pedido (
    id SERIAL PRIMARY KEY,
    venta_id INT NOT NULL,
    estado VARCHAR(20) DEFAULT 'PENDIENTE',
    observaciones TEXT,                       -- Instrucciones generales de la comanda
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pedido_venta FOREIGN KEY (venta_id) REFERENCES venta(id) ON DELETE CASCADE,
    CONSTRAINT chk_pedido_estado CHECK (estado IN ('PENDIENTE', 'EN_PREPARACION', 'LISTO', 'ENTREGADO', 'CANCELADO'))
);

CREATE TABLE detalle_pedido (
    id SERIAL PRIMARY KEY,
    pedido_id INT NOT NULL,
    producto_id INT NOT NULL,
    cantidad INT NOT NULL DEFAULT 1,
    observaciones VARCHAR(200),               -- NOTA LIBRE (Ej: 'sin queso cheddar', 'sin sal')
    CONSTRAINT fk_detpedido_pedido FOREIGN KEY (pedido_id) REFERENCES pedido(id) ON DELETE CASCADE,
    CONSTRAINT fk_detpedido_producto FOREIGN KEY (producto_id) REFERENCES producto(id) ON DELETE RESTRICT
);

CREATE TABLE ticket (
    id SERIAL PRIMARY KEY,
    pedido_id INT NOT NULL,
    codigo VARCHAR(30) NOT NULL UNIQUE,       -- Ej: 'COM-COC-0001', 'COM-BAR-0001'
    tipo_destino VARCHAR(20) DEFAULT 'COCINA',
    estado VARCHAR(20) DEFAULT 'EMITIDO',
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    contenido_impresion TEXT,
    CONSTRAINT fk_ticket_pedido FOREIGN KEY (pedido_id) REFERENCES pedido(id) ON DELETE CASCADE,
    CONSTRAINT chk_ticket_destino CHECK (tipo_destino IN ('COCINA', 'BARRA', 'COMPROBANTE')),
    CONSTRAINT chk_ticket_estado CHECK (estado IN ('EMITIDO', 'EN_PROCESO', 'FINALIZADO'))
);

CREATE TABLE entrega (
    id SERIAL PRIMARY KEY,
    pedido_id INT NOT NULL,
    ticket_id INT NULL,
    usuario_entrega_id INT NULL,
    fecha_hora_entrega TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    observaciones VARCHAR(200),
    CONSTRAINT fk_entrega_pedido FOREIGN KEY (pedido_id) REFERENCES pedido(id) ON DELETE CASCADE,
    CONSTRAINT fk_entrega_ticket FOREIGN KEY (ticket_id) REFERENCES ticket(id) ON DELETE SET NULL,
    CONSTRAINT fk_entrega_usuario FOREIGN KEY (usuario_entrega_id) REFERENCES auth_user(id) ON DELETE RESTRICT
);

-- ==============================================================================
-- 8. MÓDULO DE CONSUMO INTERNO DE TRABAJADORES (RF12)
-- ==============================================================================
CREATE TABLE consumo_interno (
    id SERIAL PRIMARY KEY,
    empleado_id INT NOT NULL,
    punto_venta_id INT NOT NULL,
    total DECIMAL(10,2) DEFAULT 0.00,
    estado VARCHAR(20) DEFAULT 'REGISTRADO',
    fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    observaciones TEXT,
    CONSTRAINT fk_consumo_empleado FOREIGN KEY (empleado_id) REFERENCES auth_user(id) ON DELETE RESTRICT,
    CONSTRAINT fk_consumo_puntoventa FOREIGN KEY (punto_venta_id) REFERENCES punto_venta(id) ON DELETE RESTRICT,
    CONSTRAINT chk_consumo_estado CHECK (estado IN ('REGISTRADO', 'DESCONTADO', 'ANULADO'))
);

CREATE TABLE detalle_consumo_interno (
    id SERIAL PRIMARY KEY,
    consumo_id INT NOT NULL,
    producto_id INT NOT NULL,
    cantidad INT NOT NULL DEFAULT 1,
    precio_unitario DECIMAL(10,2) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_detconsumo_consumo FOREIGN KEY (consumo_id) REFERENCES consumo_interno(id) ON DELETE CASCADE,
    CONSTRAINT fk_detconsumo_producto FOREIGN KEY (producto_id) REFERENCES producto(id) ON DELETE RESTRICT
);

-- ==============================================================================
-- 9. DATOS SEMILLA INICIALES (DEMO / VERIFICACIÓN DE EVIDENCIA)
-- ==============================================================================
-- Puntos de Venta
INSERT INTO punto_venta (id, nombre, tipo, descripcion, icono, color, activo) VALUES
(1, 'Restaurante Central Safari', 'Restaurante & Buffet Caliente', 'Comida por cocinar, platos calientes y hamburguesas.', 'bi-building-fill', '#c62828', TRUE),
(2, 'Cafetería & Pastelería La Selva', 'Cafetería & Pastelería', 'Bebidas calientes, pastelería y repostería artesanal.', 'bi-cup-hot-fill', '#b45309', TRUE),
(3, 'Barra Rápida & Kiosco Oasis', 'Kiosco & Al Paso', 'Bebidas frías, jugos y snacks rápidos en zonas de recorrido.', 'bi-shop-window', '#0284c7', TRUE);

-- Categorías
INSERT INTO categoria (id, nombre, descripcion) VALUES
(1, 'Comida por Cocinar', 'Platos preparados al momento con requerimiento de cocina caliente.'),
(2, 'Comida Preparada', 'Alimentos listos para despacho inmediato en salón o mostrador.'),
(3, 'Bebidas Envasadas', 'Bebidas frías, gaseosas, aguas y jugos sellados.'),
(4, 'Cafetería y Jugos', 'Café de grano, infusiones calientes y jugos naturales.');

-- Mesas del Local 1 (Muestra representativa)
INSERT INTO mesa (identificador, punto_venta_id, capacidad, estado) VALUES
('Mesa 1', 1, 4, 'HABILITADA'),
('Mesa 2', 1, 4, 'HABILITADA'),
('Mesa 3', 1, 2, 'HABILITADA'),
('Mesa 4', 1, 6, 'HABILITADA');
