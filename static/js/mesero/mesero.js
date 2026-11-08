const meseroConfig = (() => {
    const el = document.getElementById('meseroConfigData');
    if (!el) return {};
    try { return JSON.parse(el.textContent || '{}'); } catch (e) { return {}; }
})();

function obtenerCsrfTokenMesero() {
    return document.getElementById('csrfTokenMeseroGlobal')?.value
        || document.querySelector('[name=csrfmiddlewaretoken]')?.value
        || '';
}

// ==========================================================================
// Aloy - Ergonomía Táctil y Auditiva para Salón
// ==========================================================================
function reproducirChimeMesero(tipo = 'exito') {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        
        const now = ctx.currentTime;
        if (tipo === 'exito') {
            osc.frequency.setValueAtTime(523.25, now);
            osc.frequency.exponentialRampToValueAtTime(659.25, now + 0.08);
            osc.frequency.exponentialRampToValueAtTime(783.99, now + 0.16);
            gain.gain.setValueAtTime(0.12, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
            osc.start(now);
            osc.stop(now + 0.35);
        } else if (tipo === 'alerta') {
            osc.frequency.setValueAtTime(880, now);
            osc.frequency.setValueAtTime(440, now + 0.12);
            gain.gain.setValueAtTime(0.15, now);
            gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
            osc.start(now);
            osc.stop(now + 0.3);
        }
    } catch (e) {}
}

function vibrarTactil(patron = [40, 60, 40]) {
    try {
        if ('vibrate' in navigator) {
            navigator.vibrate(patron);
        }
    } catch (e) {}
}

function inicializarModoSol() {
    const btn = document.getElementById('btnToggleModoSol');
    if (!btn) return;
    const guardado = localStorage.getItem('safari_mesero_modo_sol');
    if (guardado === 'true') {
        document.body.classList.add('safari-modo-sol');
    }
    btn.addEventListener('click', () => {
        document.body.classList.toggle('safari-modo-sol');
        const activo = document.body.classList.contains('safari-modo-sol');
        localStorage.setItem('safari_mesero_modo_sol', activo ? 'true' : 'false');
        vibrarTactil([30]);
    });
}

function leerJsonScriptMesero(docRef, scriptId) {
    const root = docRef || document;
    const el = root.getElementById(scriptId);
    if (!el) return {};
    try {
        return JSON.parse(el.textContent || '{}');
    } catch (e) {
        return {};
    }
}

// Cuentas abiertas y pedidos activos en el local (sincronizados en vivo cada 1 segundo)
let cuentasAbiertas = leerJsonScriptMesero(document, 'cuentasAbiertasData');
let pedidosMesaActivos = leerJsonScriptMesero(document, 'pedidosMesaActivosData');

// Estado del Mesero inicializado con la primera mesa real del local
let mesaSeleccionada = meseroConfig.mesaInicial || { id: 1, identificador: 'Mesa 1', capacidad: 4, estado: 'HABILITADA' };
let comensales = 1;
let carrito = {}; // id -> { id, nombre, precio, destino, cantidad, nota }
let notasProductos = {}; // id -> string

// Seleccionar Mesa en el Mapa
function seleccionarMesa(id, identificador, capacidad, estado) {
    mesaSeleccionada = { id, identificador, capacidad, estado };

    // Marcar visualmente la tarjeta seleccionada
    document.querySelectorAll('.mesa-card').forEach(c => c.classList.remove('mesa-seleccionada'));
    const card = document.getElementById(`cardMesa_${id}`);
    if (card) card.classList.add('mesa-seleccionada');

    // Actualizar textos en la interfaz
    document.getElementById('mesaActivaBadge').innerHTML = `<i class="bi bi-geo-alt-fill me-1"></i> ${identificador}`;
    const estadoSpan = document.getElementById('mesaActivaEstado');
    if (estado === 'HABILITADA') {
        estadoSpan.innerText = 'Libre / Habilitada';
        estadoSpan.className = 'text-success';
    } else if (estado === 'OCUPADA') {
        estadoSpan.innerText = 'Ocupada por Comensales';
        estadoSpan.className = 'text-danger';
    } else if (estado === 'INACTIVA') {
        estadoSpan.innerText = 'Inactiva';
        estadoSpan.className = 'text-secondary';
    } else {
        estadoSpan.innerText = 'Reservada';
        estadoSpan.className = 'text-warning';
    }

    const comandaMesaEl = document.getElementById('comandaMesaNombre');
    if (comandaMesaEl) comandaMesaEl.innerText = identificador;

    // Actualizar vista de cuenta abierta, botones rápidos y comandas activas para esta mesa
    actualizarEstadoCuentaMesa(id);
}

function ejecutarAccionMesaRapida(accion) {
    if (!mesaSeleccionada || !mesaSeleccionada.id) return;
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = window.location.href;

    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrfmiddlewaretoken';
    csrfInput.value = obtenerCsrfTokenMesero();
    form.appendChild(csrfInput);

    const accionInput = document.createElement('input');
    accionInput.type = 'hidden';
    accionInput.name = 'accion';
    accionInput.value = accion;
    form.appendChild(accionInput);

    const mesaInput = document.createElement('input');
    mesaInput.type = 'hidden';
    mesaInput.name = 'mesa_id';
    mesaInput.value = mesaSeleccionada.id;
    form.appendChild(mesaInput);

    document.body.appendChild(form);
    form.submit();
}

async function marcarPedidoServidoMesero(pedidoId) {
    try {
        const formData = new FormData();
        formData.append('pedido_id', pedidoId);
        formData.append('nuevo_estado', 'ENTREGADO');
        formData.append('csrfmiddlewaretoken', obtenerCsrfTokenMesero());

        const resp = await fetch((meseroConfig.urlCambiarEstadoPedido || '/pedido/estado/'), {
            method: 'POST',
            body: formData,
            headers: { 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json' }
        });
        const data = await resp.json();
        if (data.ok) {
            await autoSincronizarMesasMesero(true);
            if (typeof swalToast !== 'undefined') {
                swalToast.fire({ icon: 'success', title: `Comanda #COM-${String(pedidoId).padStart(4, '0')} marcada como servida en mesa.` });
            }
        }
    } catch (e) {
        console.error(e);
    }
}

// Seleccionar Comensales
function setComensales(num, btn) {
    comensales = num;
    document.querySelectorAll('.btn-comensal').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('comandaComensales').innerText = `${num} ${num === 1 ? 'Persona' : 'Personas'}`;
}

// Helper para sanitizar texto
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

// Modificar Cantidad (+ / -)
function modificarCantidad(id, nombre, precio, destino, delta) {
    if (!carrito[id]) {
        carrito[id] = { id, nombre, precio, destino, cantidad: 0, nota: notasProductos[id] || '' };
    }

    carrito[id].cantidad += delta;
    if (delta > 0) {
        vibrarTactil([20]);
    }
    if (carrito[id].cantidad <= 0) {
        delete carrito[id];
        document.getElementById(`qty_${id}`).innerText = '0';
    } else {
        document.getElementById(`qty_${id}`).innerText = carrito[id].cantidad;
    }

    renderizarComanda();
}

// Renderizar Lista de Comanda
function renderizarComanda() {
    const container = document.getElementById('listaComandaItems');
    const items = Object.values(carrito);
    const btnDespachar = document.getElementById('btnDespacharComanda');

    let total = 0;
    let totalItems = 0;
    let countCocina = 0;
    let countBarra = 0;
    let countSalon = 0;

    const boxVerTickets = document.getElementById('boxVerTicketsPreview');
    if (items.length === 0) {
        container.innerHTML = `
            <div class="text-center py-4 text-muted" id="comandaVaciaMsg">
                <i class="bi bi-bag-plus display-5 d-block mb-2 text-warning"></i>
                Selecciona alimentos o bebidas con los botones <strong>(+)</strong> para armar la comanda de la mesa.
            </div>`;
        btnDespachar.disabled = true;
        if (boxVerTickets) boxVerTickets.style.display = 'none';
    } else {
        let html = '';
        items.forEach(item => {
            const subtotal = item.precio * item.cantidad;
            total += subtotal;
            totalItems += item.cantidad;

            if (item.destino === 'COCINA') countCocina += item.cantidad;
            else if (item.destino === 'BARRA') countBarra += item.cantidad;
            else countSalon += item.cantidad;

            html += `
                <div class="d-flex justify-content-between align-items-center p-2 mb-2 rounded-3 border bg-white shadow-sm">
                    <div style="max-width: 68%;">
                        <div class="fw-bold small text-dark">${item.cantidad}x ${item.nombre}</div>
                        ${item.nota ? `
                            <div class="comanda-item-nota">
                                <strong class="text-danger">* NOTA:</strong> ${escapeHtml(item.nota)}
                            </div>
                        ` : ''}
                        <small class="text-muted">$${item.precio.toLocaleString('es-CL')} c/u</small>
                    </div>
                    <div class="text-end">
                        <span class="fw-bold text-danger d-block">$${subtotal.toLocaleString('es-CL')}</span>
                        <button type="button" class="btn btn-sm btn-link text-danger p-0 ms-2 text-decoration-none" onclick="modificarCantidad(${item.id}, '${escapeHtml(item.nombre)}', ${item.precio}, '${item.destino}', -${item.cantidad})" title="Eliminar ítem">
                            <i class="bi bi-x-circle fs-5"></i>
                        </button>
                    </div>
                </div>`;
        });
        container.innerHTML = html;
        btnDespachar.disabled = false;
        if (boxVerTickets) boxVerTickets.style.display = 'block';

        const tieneCocina = items.some(it => it.destino === 'COCINA');
        const tieneBarra = items.some(it => it.destino === 'BARRA');
        let destinoLabel = 'Cocina y Barra';
        if (tieneCocina && !tieneBarra) destinoLabel = 'Cocina';
        else if (!tieneCocina && tieneBarra) destinoLabel = 'Barra';

        const esCuentaAbierta = !!(cuentasAbiertas[mesaSeleccionada.id] || cuentasAbiertas[String(mesaSeleccionada.id)]);
        if (esCuentaAbierta) {
            btnDespachar.innerHTML = `<i class="bi bi-send-check-fill me-2 fs-4"></i> Enviar Ronda a ${destinoLabel}`;
        } else {
            btnDespachar.innerHTML = `<i class="bi bi-send-check-fill me-2 fs-4"></i> Enviar a ${destinoLabel}`;
        }
    }

    // Actualizar contadores por zona de impresión
    document.getElementById('contadorCocina').innerText = `${countCocina} ítems`;
    document.getElementById('contadorBarra').innerText = `${countBarra} ítems`;
    document.getElementById('contadorSalon').innerText = `${countSalon} ítems`;

    // Actualizar Total Desktop
    document.getElementById('totalComandaTexto').innerText = `$${total.toLocaleString('es-CL')}`;

    // Actualizar Barra Flotante de Celular
    const mobileMesa = document.getElementById('mobileComandaMesa');
    const mobileTotal = document.getElementById('mobileComandaTotal');
    if (mobileMesa && mobileTotal) {
        mobileMesa.innerText = `${mesaSeleccionada.identificador} • ${totalItems} ${totalItems === 1 ? 'ítem' : 'ítems'}`;
        mobileTotal.innerText = `$${total.toLocaleString('es-CL')}`;
    }
}

// Desplazamiento fluido hacia la comanda en móvil
function scrollHaciaComanda() {
    const panel = document.getElementById('panelComanda');
    if (panel) {
        panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// Vaciar Comanda
function vaciarComanda() {
    carrito = {};
    notasProductos = {};
    document.querySelectorAll('.qty-display').forEach(d => d.innerText = '0');
    document.querySelectorAll('.btn-nota-plato').forEach(b => {
        b.classList.remove('tiene-nota');
        const span = b.querySelector('span');
        if (span) span.innerText = 'Nota';
    });
    renderizarComanda();
}

// Modal de Notas Libres
function abrirNotaModal(id, nombre) {
    document.getElementById('notaProductoId').value = id;
    document.getElementById('modalNotaTitulo').innerHTML = `<i class="bi bi-pencil-square text-warning me-2"></i>Nota para: ${escapeHtml(nombre)}`;
    const notaActual = notasProductos[id] || (carrito[id] ? carrito[id].nota : '');
    document.getElementById('notaTextoInput').value = notaActual;

    const btnQuitar = document.getElementById('btnQuitarNota');
    if (btnQuitar) {
        btnQuitar.style.display = notaActual ? 'inline-block' : 'none';
    }

    const modalEl = document.getElementById('modalNota');
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    setTimeout(() => {
        const input = document.getElementById('notaTextoInput');
        if (input) {
            input.focus();
            input.select();
        }
    }, 350);
}

function quitarNota() {
    const id = document.getElementById('notaProductoId').value;
    document.getElementById('notaTextoInput').value = '';
    guardarNota();
}

function guardarNota() {
    const id = document.getElementById('notaProductoId').value;
    const nota = document.getElementById('notaTextoInput').value.trim();
    notasProductos[id] = nota;

    if (carrito[id]) {
        carrito[id].nota = nota;
    } else if (nota) {
        // Si el producto no estaba en el pedido, agregarlo con cantidad 1 automáticamente
        const card = document.getElementById(`btnNota_${id}`)?.closest('.product-mesero-card');
        if (card) {
            const btnMas = card.querySelector('.qty-control-btn[onclick*=", 1)"]');
            if (btnMas) {
                btnMas.click();
                if (carrito[id]) carrito[id].nota = nota;
            }
        }
    }

    // Actualizar estilo visual del botón
    actualizarBotonNota(id, nota);

    renderizarComanda();
    const modalEl = document.getElementById('modalNota');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
}

function actualizarBotonNota(id, nota) {
    const btn = document.getElementById(`btnNota_${id}`);
    const textSpan = document.getElementById(`btnNotaText_${id}`);
    if (btn && textSpan) {
        if (nota) {
            btn.classList.add('tiene-nota');
            const preview = nota.length > 14 ? nota.substring(0, 12) + '...' : nota;
            textSpan.innerHTML = `<i class="bi bi-check2 me-1"></i>${escapeHtml(preview)}`;
            btn.title = `Nota activa: ${nota}`;
        } else {
            btn.classList.remove('tiene-nota');
            textSpan.innerText = 'Nota';
            btn.title = 'Agregar nota libre para cocina o barra';
        }
    }
}

// Abrir Modal de Impresión Inteligente
function abrirModalTickets() {
    const items = Object.values(carrito);
    if (items.length === 0) {
        if (typeof swalToast !== 'undefined') {
            swalToast.fire({
                icon: 'warning',
                title: 'La comanda está vacía. Selecciona productos antes de ver los tickets.'
            });
        }
        return;
    }

    const itemsCocina = items.filter(i => i.destino === 'COCINA');
    const itemsBarra = items.filter(i => i.destino === 'BARRA');

    const ahora = new Date();
    const fechaStr = ahora.toLocaleDateString('es-CL', { day: '2-digit', month: '2-digit', year: 'numeric' });
    const horaStr = ahora.toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const numeroComanda = Math.floor(1000 + Math.random() * 9000);

    const colCocina = document.getElementById('colTicketCocina');
    const colBarra = document.getElementById('colTicketBarra');
    const bannerMsg = document.getElementById('modalTicketsBannerMsg');

    // Poblar y Gestionar Visibilidad Ticket Cocina (Cero Desperdicio de Papel)
    let totalItemsCocina = 0;
    if (itemsCocina.length > 0) {
        if (colCocina) colCocina.style.display = 'flex';
        document.getElementById('tikCocinaCodigo').innerText = `#COC-${numeroComanda}`;
        document.getElementById('tikCocinaFecha').innerText = fechaStr;
        document.getElementById('tikCocinaHora').innerText = horaStr;
        document.getElementById('tikCocinaMesa').innerText = `${mesaSeleccionada.identificador.toUpperCase()} (${comensales} PERS.)`;

        let htmlC = '';
        itemsCocina.forEach(it => {
            totalItemsCocina += it.cantidad;
            htmlC += `
                <div class="thermal-ticket-item">
                    <span class="thermal-ticket-qty">${it.cantidad}</span>
                    <span class="thermal-ticket-name">${escapeHtml(it.nombre).toUpperCase()}</span>
                </div>
                ${it.nota ? `
                    <div class="thermal-ticket-note">
                        * NOTA: ${escapeHtml(it.nota).toUpperCase()}
                    </div>
                ` : ''}
            `;
        });
        document.getElementById('tikCocinaItems').innerHTML = htmlC;
    } else {
        if (colCocina) colCocina.style.display = 'none';
        document.getElementById('tikCocinaItems').innerHTML = '';
    }
    document.getElementById('tikCocinaTotalItems').innerText = totalItemsCocina;

    // Poblar y Gestionar Visibilidad Ticket Barra (Cero Desperdicio de Papel)
    let totalItemsBarra = 0;
    if (itemsBarra.length > 0) {
        if (colBarra) colBarra.style.display = 'flex';
        document.getElementById('tikBarraCodigo').innerText = `#BAR-${numeroComanda}`;
        document.getElementById('tikBarraFecha').innerText = fechaStr;
        document.getElementById('tikBarraHora').innerText = horaStr;
        document.getElementById('tikBarraMesa').innerText = `${mesaSeleccionada.identificador.toUpperCase()} (${comensales} PERS.)`;

        let htmlB = '';
        itemsBarra.forEach(it => {
            totalItemsBarra += it.cantidad;
            htmlB += `
                <div class="thermal-ticket-item">
                    <span class="thermal-ticket-qty">${it.cantidad}</span>
                    <span class="thermal-ticket-name">${escapeHtml(it.nombre).toUpperCase()}</span>
                </div>
                ${it.nota ? `
                    <div class="thermal-ticket-note">
                        * NOTA: ${escapeHtml(it.nota).toUpperCase()}
                    </div>
                ` : ''}
            `;
        });
        document.getElementById('tikBarraItems').innerHTML = htmlB;
    } else {
        if (colBarra) colBarra.style.display = 'none';
        document.getElementById('tikBarraItems').innerHTML = '';
    }
    document.getElementById('tikBarraTotalItems').innerText = totalItemsBarra;

    // Actualizar Mensaje Informativo en Encabezado del Modal
    if (bannerMsg) {
        if (itemsCocina.length > 0 && itemsBarra.length > 0) {
            bannerMsg.innerText = 'Se emitirán 2 tickets independientes (Cocina y Barra) según destino:';
        } else if (itemsCocina.length > 0) {
            bannerMsg.innerText = 'Comanda destinada únicamente a Cocina Caliente (sin desperdicio de papel en Barra).';
        } else {
            bannerMsg.innerText = 'Comanda destinada únicamente a Barra / Bebidas (sin desperdicio de papel en Cocina).';
        }
    }

    const modal = new bootstrap.Modal(document.getElementById('modalTickets'));
    modal.show();
}

// Despacho Directo e Instantáneo con Alerta Rápida para Hora Pico
function enviarComandaDirecta() {
    const items = Object.values(carrito);
    if (items.length === 0) {
        if (typeof swalToast !== 'undefined') {
            swalToast.fire({
                icon: 'warning',
                title: 'La comanda está vacía. Selecciona productos antes de enviar.'
            });
        }
        return;
    }

    // Ocultar modal de vista previa si estaba abierto
    const modalTicketsEl = document.getElementById('modalTickets');
    const modalTicketsInstance = bootstrap.Modal.getInstance(modalTicketsEl);
    if (modalTicketsInstance) {
        modalTicketsInstance.hide();
    }

    const tieneCocina = items.some(i => i.destino === 'COCINA');
    const tieneBarra = items.some(i => i.destino === 'BARRA');
    let destinoTexto = 'Cocina y Barra';
    if (tieneCocina && !tieneBarra) destinoTexto = 'Cocina';
    else if (!tieneCocina && tieneBarra) destinoTexto = 'Barra';

    const btnDespachar = document.getElementById('btnDespacharComanda');
    if (btnDespachar) {
        btnDespachar.disabled = true;
        btnDespachar.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Enviando a preparar...';
    }

    // Notificación rápida Toast para no detener el ritmo en salón
    if (typeof swalToast !== 'undefined') {
        swalToast.fire({
            icon: 'success',
            title: `¡Pedido enviado a preparar a ${destinoTexto}!`
        });
    }

    reproducirChimeMesero('exito');
    vibrarTactil([50, 70, 50]);

    // Disparar envío formal de comanda
    ejecutarEnvioComandaForm();
}

function confirmarYAtenderOtra() {
    enviarComandaDirecta();
}

// Cola Local Offline Resiliente de Comandas para Meseros (Pérdidas de Wi-Fi en Terreno)
const CLAVE_COLA_OFFLINE = 'safari_mesero_offline_queue';

function guardarComandaOffline(mesaId, mesaNombre, itemsArray) {
    let cola = [];
    try {
        cola = JSON.parse(localStorage.getItem(CLAVE_COLA_OFFLINE) || '[]');
    } catch (e) {
        cola = [];
    }
    const comandaOffline = {
        id_temp: 'OFF-' + Date.now(),
        mesa_id: mesaId,
        mesa_nombre: mesaNombre,
        items: itemsArray,
        fecha_hora: new Date().toISOString()
    };
    cola.push(comandaOffline);
    localStorage.setItem(CLAVE_COLA_OFFLINE, JSON.stringify(cola));
    return comandaOffline;
}

async function sincronizarColaOfflineMesero() {
    let cola = [];
    try {
        cola = JSON.parse(localStorage.getItem(CLAVE_COLA_OFFLINE) || '[]');
    } catch (e) {
        cola = [];
    }
    if (!cola || cola.length === 0) return;

    console.log(`[Safari Mesero] Sincronizando ${cola.length} comandas guardadas offline...`);
    const csrfToken = obtenerCsrfTokenMesero();
    const fallidas = [];

    for (const comanda of cola) {
        try {
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', csrfToken);
            formData.append('accion', 'enviar_comanda');
            formData.append('mesa_id', comanda.mesa_id);
            formData.append('items_json', JSON.stringify(comanda.items));

            const resp = await fetch(window.location.href, {
                method: 'POST',
                body: formData,
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });

            if (!resp.ok) {
                fallidas.push(comanda);
            }
        } catch (err) {
            fallidas.push(comanda);
        }
    }

    if (fallidas.length === 0) {
        localStorage.removeItem(CLAVE_COLA_OFFLINE);
        swalToast.fire({
            icon: 'success',
            title: `¡Conexión restaurada! Se sincronizaron ${cola.length} comanda(s) guardadas offline.`
        });
        autoSincronizarMesasMesero(true);
    } else {
        localStorage.setItem(CLAVE_COLA_OFFLINE, JSON.stringify(fallidas));
    }
}

window.addEventListener('online', () => {
    sincronizarColaOfflineMesero();
});
document.addEventListener('DOMContentLoaded', () => {
    if (navigator.onLine) sincronizarColaOfflineMesero();
});

function ejecutarEnvioComandaForm() {
    const itemsArray = Object.values(carrito).map(it => ({
        id: it.id,
        nombre: it.nombre,
        cantidad: it.cantidad,
        precio: it.precio,
        destino: it.destino,
        nota: it.nota || ''
    }));

    // Si el mesero está sin conexión en el parque Safari, guardar en cola local resiliente
    if (!navigator.onLine) {
        const guardada = guardarComandaOffline(mesaSeleccionada.id, mesaSeleccionada.identificador, itemsArray);
        swalToast.fire({
            icon: 'warning',
            title: `⚠️ Sin conexión a la red local. Comanda guardada en tu tableta. Se enviará automáticamente al reconectar.`
        });
        vaciarComanda();
        return;
    }

    // Enviar datos al backend para persistir la comanda y tickets
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = window.location.href;

    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrfmiddlewaretoken';
    csrfInput.value = obtenerCsrfTokenMesero();
    form.appendChild(csrfInput);

    const accionInput = document.createElement('input');
    accionInput.type = 'hidden';
    accionInput.name = 'accion';
    accionInput.value = 'enviar_comanda';
    form.appendChild(accionInput);

    const mesaInput = document.createElement('input');
    mesaInput.type = 'hidden';
    mesaInput.name = 'mesa_id';
    mesaInput.value = mesaSeleccionada.id;
    form.appendChild(mesaInput);

    const itemsInput = document.createElement('input');
    itemsInput.type = 'hidden';
    itemsInput.name = 'items_json';
    itemsInput.value = JSON.stringify(itemsArray);
    form.appendChild(itemsInput);

    document.body.appendChild(form);
    form.submit();
}

// Filtro por Categoría
function filtrarCategoria(cat, btn) {
    document.querySelectorAll('.filter-cat-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    document.querySelectorAll('.item-plato').forEach(card => {
        const itemCat = card.getAttribute('data-cat');
        if (cat === 'todos' || itemCat === cat) {
            card.classList.remove('d-none');
        } else {
            card.classList.add('d-none');
        }
    });
}

// Filtro por Texto
function filtrarTextoPlatos() {
    const query = document.getElementById('buscadorPlatos').value.toLowerCase().trim();
    document.querySelectorAll('.item-plato').forEach(card => {
        const nombre = card.getAttribute('data-nombre') || '';
        if (!query || nombre.includes(query)) {
            card.classList.remove('d-none');
        } else {
            card.classList.add('d-none');
        }
    });
}

function refrescarBadgesMesasSalon() {
    document.querySelectorAll('[id^="cuentaCardInfo_"]').forEach(cardInfo => {
        const mId = cardInfo.id.replace('cuentaCardInfo_', '');
        const cuenta = cuentasAbiertas[mId] || cuentasAbiertas[String(mId)];
        const pedidosActivos = pedidosMesaActivos[mId] || pedidosMesaActivos[String(mId)] || [];
        const totalEl = document.getElementById(`cuentaCardTotal_${mId}`);

        if (cuenta) {
            cardInfo.style.display = 'block';
            if (totalEl) totalEl.innerText = `$${Number(cuenta.total || 0).toLocaleString('es-CL')}`;
        } else if (pedidosActivos.length > 0) {
            cardInfo.style.display = 'block';
            const tieneListo = pedidosActivos.some(p => p.estado === 'LISTO');
            if (totalEl) totalEl.innerText = tieneListo ? '¡Listo p/ Servir!' : `${pedidosActivos.length} comanda(s)`;
        } else {
            cardInfo.style.display = 'none';
        }
    });
}

// Funciones de Gestión de Cuenta Abierta, Botones Rápidos y Comandas Activas de Mesa
function actualizarEstadoCuentaMesa(mesaId) {
    const cuenta = cuentasAbiertas[mesaId] || cuentasAbiertas[String(mesaId)];
    const pedidosActivos = pedidosMesaActivos[mesaId] || pedidosMesaActivos[String(mesaId)] || [];
    const banner = document.getElementById('bannerCuentaAbierta');
    const bannerPedidos = document.getElementById('bannerPedidosActivosMesa');
    const lateralBox = document.getElementById('lateralCuentaAbiertaBox');
    const btnCerrarLateral = document.getElementById('btnCerrarCuentaLateral');
    const btnDespachar = document.getElementById('btnDespacharComanda');
    const labelTotalComanda = document.getElementById('labelTotalComanda');
    const btnOcupar = document.getElementById('btnOcuparMesaRapido');
    const btnLiberar = document.getElementById('btnLiberarMesaRapido');

    // Botones rápidos de ocupación / liberación sincronizados con Caja
    if (btnOcupar) {
        btnOcupar.style.display = (mesaSeleccionada && mesaSeleccionada.estado === 'HABILITADA') ? 'inline-block' : 'none';
    }
    if (btnLiberar) {
        btnLiberar.style.display = (mesaSeleccionada && mesaSeleccionada.estado === 'OCUPADA' && !cuenta) ? 'inline-block' : 'none';
    }

    if (cuenta) {
        if (banner) {
            banner.style.display = 'block';
            document.getElementById('cuentaRondasBadge').innerText = `Ronda #${cuenta.rondas}`;
            document.getElementById('cuentaHoraTexto').innerText = cuenta.hora_apertura;
            document.getElementById('cuentaTotalTexto').innerText = `$${cuenta.total.toLocaleString('es-CL')}`;
            const totalConsumos = cuenta.items.reduce((acc, it) => acc + it.cantidad, 0);
            document.getElementById('cuentaItemsResumen').innerText = `(${totalConsumos} ${totalConsumos === 1 ? 'consumo previo' : 'consumos previos'})`;
        }

        if (lateralBox) {
            lateralBox.style.display = 'block';
            document.getElementById('lateralRondasBadge').innerText = `${cuenta.rondas} ${cuenta.rondas === 1 ? 'Ronda' : 'Rondas'}`;
            document.getElementById('lateralTotalAcumulado').innerText = `$${cuenta.total.toLocaleString('es-CL')}`;
        }

        if (btnCerrarLateral) btnCerrarLateral.style.display = 'block';
        if (labelTotalComanda) labelTotalComanda.innerText = 'Nueva Ronda:';

        if (btnDespachar && Object.keys(carrito).length === 0) {
            btnDespachar.innerHTML = '<i class="bi bi-send-check-fill me-2 fs-4"></i> Enviar Ronda Adicional';
        }
    } else {
        if (banner) banner.style.display = 'none';
        if (lateralBox) lateralBox.style.display = 'none';
        if (btnCerrarLateral) btnCerrarLateral.style.display = 'none';
        if (labelTotalComanda) labelTotalComanda.innerText = 'Total Comanda:';
        if (btnDespachar && Object.keys(carrito).length === 0) {
            btnDespachar.innerHTML = '<i class="bi bi-send-check-fill me-2 fs-4"></i> Enviar a Cocina y Barra';
        }
    }

    // Mostrar comandas activas de la mesa (incluyendo las enviadas y pagadas desde Caja)
    if (bannerPedidos) {
        if (pedidosActivos.length > 0) {
            let htmlPed = `
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <span class="fw-bold small text-dark">
                        <i class="bi bi-broadcast text-primary me-1"></i>COMANDAS ACTIVAS EN PRODUCCIÓN (${pedidosActivos.length})
                    </span>
                    <small class="text-muted">Sincronizado con Caja, Cocina y Barra</small>
                </div>
                <div class="d-flex flex-column gap-2">
            `;
            pedidosActivos.forEach(pa => {
                let estadoBadge = '';
                let btnServir = '';
                if (pa.estado === 'LISTO') {
                    estadoBadge = '<span class="badge bg-success text-white">¡LISTO PARA SERVIR!</span>';
                    btnServir = `<button type="button" class="btn btn-sm btn-success rounded-pill fw-bold px-3" onclick="marcarPedidoServidoMesero(${pa.pedido_id})"><i class="bi bi-check2-all me-1"></i>Servir en Mesa</button>`;
                } else if (pa.estado === 'EN_PREPARACION') {
                    estadoBadge = '<span class="badge bg-primary text-white">En Preparación</span>';
                } else {
                    estadoBadge = '<span class="badge bg-warning text-dark">Pendiente en Cola</span>';
                }
                const pagadoTag = pa.venta_estado === 'PAGADA'
                    ? '<span class="badge bg-success-subtle text-success border border-success-subtle ms-1">Pagado en Caja</span>'
                    : '<span class="badge bg-warning-subtle text-dark border ms-1">En Cuenta</span>';
                const resumenItems = (pa.items || []).map(i => `${i.cantidad}x ${escapeHtml(i.nombre)}`).join(', ');
                htmlPed += `
                    <div class="p-2 rounded-3 bg-white border d-flex justify-content-between align-items-center flex-wrap gap-2">
                        <div>
                            <div class="fw-bold small text-dark">#${escapeHtml(pa.codigo)} • ${escapeHtml(pa.hora)} hrs ${estadoBadge} ${pagadoTag}</div>
                            <div class="small text-muted">${resumenItems}</div>
                        </div>
                        <div>${btnServir}</div>
                    </div>
                `;
            });
            htmlPed += '</div>';
            bannerPedidos.innerHTML = htmlPed;
            bannerPedidos.style.display = 'block';
        } else {
            bannerPedidos.innerHTML = '';
            bannerPedidos.style.display = 'none';
        }
    }
}

function abrirModalDetalleCuenta() {
    const cuenta = cuentasAbiertas[mesaSeleccionada.id] || cuentasAbiertas[String(mesaSeleccionada.id)];
    if (!cuenta) return;

    document.getElementById('modalDetalleMesaNom').innerText = mesaSeleccionada.identificador;
    document.getElementById('modalDetalleMeseroNom').innerText = cuenta.cajero_nombre;
    document.getElementById('modalDetalleRondasCount').innerText = `${cuenta.rondas} ${cuenta.rondas === 1 ? 'Ronda' : 'Rondas'}`;

    const tbody = document.getElementById('modalDetalleItemsBody');
    let rowsHtml = '';
    cuenta.items.forEach(it => {
        const notaHtml = it.nota ? `<div class="text-danger small fst-italic mt-1"><i class="bi bi-chat-left-dots me-1"></i>Nota: ${escapeHtml(it.nota)}</div>` : '';
        rowsHtml += `
            <tr>
                <td class="fw-bold text-primary py-3" style="font-size: 1.1rem;">${it.cantidad}x</td>
                <td class="py-3">
                    <span class="fw-semibold text-dark fs-6">${escapeHtml(it.nombre)}</span>
                    ${notaHtml}
                </td>
                <td class="text-end text-muted py-3 fs-6">$${it.precio.toLocaleString('es-CL')}</td>
                <td class="text-end fw-bold text-dark py-3" style="font-size: 1.15rem;">$${it.subtotal.toLocaleString('es-CL')}</td>
            </tr>
        `;
    });
    tbody.innerHTML = rowsHtml;
    document.getElementById('modalDetalleTotal').innerText = `$${cuenta.total.toLocaleString('es-CL')}`;

    const modal = new bootstrap.Modal(document.getElementById('modalDetalleCuenta'));
    modal.show();
}

function pasarDeDetalleACobro() {
    const modalDetalleEl = document.getElementById('modalDetalleCuenta');
    const modalDetalle = bootstrap.Modal.getInstance(modalDetalleEl);
    if (modalDetalle) modalDetalle.hide();
    abrirModalCerrarCuenta();
}

function actualizarTotalConRedondeo() {
    if (!mesaSeleccionada) return;
    const cuenta = cuentasAbiertas[mesaSeleccionada.id] || cuentasAbiertas[String(mesaSeleccionada.id)];
    if (!cuenta) return;

    const metodo = document.querySelector('input[name="metodo_pago"]:checked')?.value || 'EFECTIVO';
    const totalOriginal = Math.round(Number(cuenta.total) || 0);
    const boxRedondeo = document.getElementById('boxRedondeoLey');
    const txtDetalle = document.getElementById('txtDetalleRedondeo');
    const badgeMonto = document.getElementById('badgeRedondeoMonto');
    const displayTotal = document.getElementById('modalCerrarTotal');

    if (metodo === 'EFECTIVO') {
        const resto = totalOriginal % 10;
        let ajuste = 0;
        if (resto === 0) {
            ajuste = 0;
        } else if (resto <= 4) {
            ajuste = -resto;
        } else {
            ajuste = 10 - resto;
        }
        const totalRedondeado = totalOriginal + ajuste;
        displayTotal.innerText = `$${totalRedondeado.toLocaleString('es-CL')}`;

        if (boxRedondeo) boxRedondeo.classList.remove('d-none');
        if (ajuste !== 0) {
            txtDetalle.innerText = `Total base $${totalOriginal.toLocaleString('es-CL')} -> Redondeo Ley 20.956: ${ajuste > 0 ? '+' : ''}$${ajuste} CLP`;
            badgeMonto.innerText = `${ajuste > 0 ? '+' : ''}$${ajuste} CLP`;
            badgeMonto.className = ajuste > 0 ? 'badge bg-warning-subtle text-warning-emphasis border border-warning-subtle rounded-pill fw-bold' : 'badge bg-info-subtle text-info-emphasis border border-info-subtle rounded-pill fw-bold';
        } else {
            txtDetalle.innerText = 'Monto exacto a la decena (sin redondeo).';
            badgeMonto.innerText = '$0 CLP';
            badgeMonto.className = 'badge bg-success-subtle text-success border border-success-subtle rounded-pill fw-bold';
        }
    } else {
        displayTotal.innerText = `$${totalOriginal.toLocaleString('es-CL')}`;
        if (boxRedondeo) boxRedondeo.classList.add('d-none');
    }
}

function abrirModalCerrarCuenta() {
    const cuenta = cuentasAbiertas[mesaSeleccionada.id] || cuentasAbiertas[String(mesaSeleccionada.id)];
    if (!cuenta) return;

    document.getElementById('modalCerrarMesaNom').innerText = mesaSeleccionada.identificador;
    document.getElementById('modalCerrarMesaId').value = mesaSeleccionada.id;
    document.getElementById('modalCerrarTotal').innerText = `$${cuenta.total.toLocaleString('es-CL')}`;
    document.getElementById('modalCerrarResumen').innerText = `En ${cuenta.rondas} ${cuenta.rondas === 1 ? 'ronda acumulada' : 'rondas acumuladas'} (${cuenta.items.length} productos)`;

    const modal = new bootstrap.Modal(document.getElementById('modalCerrarCuenta'));
    actualizarTotalConRedondeo();
    modal.show();
}

function abrirModalReasignarMesa() {
    const cuenta = cuentasAbiertas[mesaSeleccionada.id] || cuentasAbiertas[String(mesaSeleccionada.id)];
    if (!cuenta) {
        if (typeof swalToast !== 'undefined') {
            swalToast.fire({
                icon: 'warning',
                title: 'La mesa seleccionada no tiene una cuenta abierta para reasignar.'
            });
        }
        return;
    }

    document.getElementById('modalReasignarOrigenId').value = mesaSeleccionada.id;
    document.getElementById('modalReasignarOrigenNom').innerText = mesaSeleccionada.identificador;
    document.getElementById('modalReasignarRondasBadge').innerText = `${cuenta.rondas} ${cuenta.rondas === 1 ? 'Ronda' : 'Rondas'}`;
    document.getElementById('modalReasignarTotalTexto').innerText = `$${cuenta.total.toLocaleString('es-CL')}`;

    const selectDestino = document.getElementById('modalReasignarDestinoSelect');
    if (selectDestino) {
        Array.from(selectDestino.options).forEach(opt => {
            opt.disabled = (Number(opt.value) === Number(mesaSeleccionada.id));
        });
        selectDestino.value = '';
    }

    const modal = new bootstrap.Modal(document.getElementById('modalReasignarMesa'));
    modal.show();
}

function pasarDeDetalleAReasignar() {
    const modalDetalleEl = document.getElementById('modalDetalleCuenta');
    const modalDetalle = bootstrap.Modal.getInstance(modalDetalleEl);
    if (modalDetalle) modalDetalle.hide();
    abrirModalReasignarMesa();
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('input[name="metodo_pago"]').forEach(r => {
        r.addEventListener('change', actualizarTotalConRedondeo);
    });

    if (Array.isArray(meseroConfig.mensajes) && typeof swalToast !== 'undefined') {
        meseroConfig.mensajes.forEach(msg => {
            swalToast.fire({ icon: msg.icon || 'success', title: msg.title || '' });
        });
    }

    const inputNota = document.getElementById('notaTextoInput');
    if (inputNota) {
        inputNota.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                guardarNota();
            }
        });
    }

    refrescarBadgesMesasSalon();
    if (mesaSeleccionada && mesaSeleccionada.id) {
        seleccionarMesa(mesaSeleccionada.id, mesaSeleccionada.identificador, mesaSeleccionada.capacidad, mesaSeleccionada.estado);
    }
});

// Auto-sincronización fluida en tiempo real cada 1 segundo (Cajero <-> Mesero <-> Cocina <-> Barra)
let sincronizandoMesas = false;
let ultimaVersionDeltaMesero = null;

async function autoSincronizarMesasMesero(forzar = false) {
    if (sincronizandoMesas) return;
    if (!forzar && (document.querySelector('.modal.show') || document.querySelector('.swal2-container'))) {
        return;
    }
    sincronizandoMesas = true;

    try {
        // 1. Paso Delta Liviano (~150 bytes): Verificar si cambió el estado general
        const deltaUrl = '/api/sincronizacion/estado/' + window.location.search;
        let debeActualizar = forzar;

        try {
            const deltaResp = await fetch(deltaUrl, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            if (deltaResp.ok) {
                const delta = await deltaResp.json();
                if (delta.ok) {
                    if (!forzar && ultimaVersionDeltaMesero && ultimaVersionDeltaMesero === delta.version) {
                        sincronizandoMesas = false;
                        return; // Estado idéntico, ahorra 100KB de DOM
                    }
                    ultimaVersionDeltaMesero = delta.version;
                    debeActualizar = true;
                }
            }
        } catch (e) {
            debeActualizar = true;
        }

        if (!debeActualizar) {
            sincronizandoMesas = false;
            return;
        }

        const resp = await fetch(window.location.href, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!resp.ok) return;

        const textoHtml = await resp.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(textoHtml, 'text/html');

        // 1. Actualizar datos vivos de cuentas abiertas y comandas activas por mesa
        cuentasAbiertas = leerJsonScriptMesero(doc, 'cuentasAbiertasData');
        pedidosMesaActivos = leerJsonScriptMesero(doc, 'pedidosMesaActivosData');

        // 2. Actualizar KPIs superiores de mesas libres / ocupadas
        const nuevoKpiBox = doc.getElementById('kpiMesasSalonBox');
        const actualKpiBox = document.getElementById('kpiMesasSalonBox');
        if (nuevoKpiBox && actualKpiBox && nuevoKpiBox.innerHTML.trim() !== actualKpiBox.innerHTML.trim()) {
            actualKpiBox.innerHTML = nuevoKpiBox.innerHTML;
        }

        // 3. Actualizar campana de pedidos listos en Cocina/Barra (si el menú no está desplegado)
        const nuevaCampana = doc.getElementById('contenedorCampanaListos');
        const actualCampana = document.getElementById('contenedorCampanaListos');
        if (nuevaCampana && actualCampana && !actualCampana.querySelector('.dropdown-menu.show')) {
            if (nuevaCampana.innerHTML.trim() !== actualCampana.innerHTML.trim()) {
                actualCampana.innerHTML = nuevaCampana.innerHTML;
            }
        }

        // 4. Actualizar grilla visual de mesas del salón (#contenedorMesas) solo si hubo cambios reales
        const nuevoMapa = doc.getElementById('contenedorMesas');
        const actualMapa = document.getElementById('contenedorMesas');
        if (nuevoMapa && actualMapa && nuevoMapa.innerHTML.trim() !== actualMapa.innerHTML.trim()) {
            actualMapa.innerHTML = nuevoMapa.innerHTML;
            document.querySelectorAll('.mesa-card').forEach(c => c.classList.remove('mesa-seleccionada'));
            refrescarBadgesMesasSalon();
        }

        // 5. Refrescar estado en vivo de la mesa actualmente seleccionada por el mesero
        if (mesaSeleccionada && mesaSeleccionada.id) {
            const cardSel = document.getElementById(`cardMesa_${mesaSeleccionada.id}`);
            if (cardSel) {
                cardSel.classList.add('mesa-seleccionada');
                const nuevoEstado = cardSel.getAttribute('data-estado') || mesaSeleccionada.estado;
                mesaSeleccionada.estado = nuevoEstado;
                const estadoSpan = document.getElementById('mesaActivaEstado');
                if (estadoSpan) {
                    if (nuevoEstado === 'HABILITADA') {
                        estadoSpan.innerText = 'Libre / Habilitada';
                        estadoSpan.className = 'text-success';
                    } else if (nuevoEstado === 'OCUPADA') {
                        estadoSpan.innerText = 'Ocupada por Comensales';
                        estadoSpan.className = 'text-danger';
                    } else if (nuevoEstado === 'INACTIVA') {
                        estadoSpan.innerText = 'Inactiva';
                        estadoSpan.className = 'text-secondary';
                    } else {
                        estadoSpan.innerText = 'Reservada';
                        estadoSpan.className = 'text-warning';
                    }
                }
            }
            actualizarEstadoCuentaMesa(mesaSeleccionada.id);
        }
    } catch (err) {
        // Silencioso ante contingencias de red
    } finally {
        sincronizandoMesas = false;
    }
}
// Sincronización ultra-rápida a 1 segundo (1000 ms)
let meseroInterval = setInterval(() => autoSincronizarMesasMesero(false), 1000);

document.addEventListener('visibilitychange', () => {
    clearInterval(meseroInterval);
    if (document.visibilityState === 'visible') {
        autoSincronizarMesasMesero(false);
        meseroInterval = setInterval(() => autoSincronizarMesasMesero(false), 1000);
    } else {
        meseroInterval = setInterval(() => autoSincronizarMesasMesero(false), 5000);
    }
});

// Inicialización de Modo Sol y Ergonomía
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarModoSol);
} else {
    inicializarModoSol();
}
