// Carga de datos 100% reales desde el servidor Django (RF18 - Cero Mocks)
const chartDataRaw = document.getElementById('chartDataJson');
const chartDataServer = chartDataRaw ? JSON.parse(chartDataRaw.textContent) : { meses: {}, dias: {}, horas: {} };

const data15Meses = {
    labels: (chartDataServer.meses && chartDataServer.meses.labels && chartDataServer.meses.labels.length) ? chartDataServer.meses.labels : ["Sin datos"],
    ventas: (chartDataServer.meses && chartDataServer.meses.ventas && chartDataServer.meses.ventas.length) ? chartDataServer.meses.ventas : [0],
    ganancias: (chartDataServer.meses && chartDataServer.meses.ganancias && chartDataServer.meses.ganancias.length) ? chartDataServer.meses.ganancias : [0],
    unidad: "CLP"
};

const dataPorDia = {
    labels: (chartDataServer.dias && chartDataServer.dias.labels && chartDataServer.dias.labels.length) ? chartDataServer.dias.labels : ["Sin datos"],
    ventas: (chartDataServer.dias && chartDataServer.dias.ventas && chartDataServer.dias.ventas.length) ? chartDataServer.dias.ventas : [0],
    ganancias: (chartDataServer.dias && chartDataServer.dias.ganancias && chartDataServer.dias.ganancias.length) ? chartDataServer.dias.ganancias : [0],
    unidad: "CLP"
};

const dataPorHora = {
    labels: (chartDataServer.horas && chartDataServer.horas.labels && chartDataServer.horas.labels.length) ? chartDataServer.horas.labels : ["Sin datos"],
    ventas: (chartDataServer.horas && chartDataServer.horas.ventas && chartDataServer.horas.ventas.length) ? chartDataServer.horas.ventas : [0],
    ganancias: (chartDataServer.horas && chartDataServer.horas.ganancias && chartDataServer.horas.ganancias.length) ? chartDataServer.horas.ganancias : [0],
    unidad: "CLP"
};

let currentChart = null;

function formatearMoneda(val, unidad) {
    return '$' + Math.round(val).toLocaleString('es-CL');
}

function renderizarChart(tipo) {
    const ctx = document.getElementById('mixedChart').getContext('2d');
    let dataSelected, labelVentas, labelGanancias, tituloText, subtituloText;

    if (tipo === 'hora') {
        dataSelected = dataPorHora;
        labelVentas = 'Ventas por Hora ($ CLP)';
        labelGanancias = 'Ganancia por Hora ($ CLP)';
        tituloText = 'DISTRIBUCIÓN HORARIA REAL: VENTAS Y GANANCIAS EN VIVO';
        subtituloText = 'Curva de flujo por hora según transacciones reales registradas en Parque Safari';
    } else if (tipo === 'dia') {
        dataSelected = dataPorDia;
        labelVentas = 'Ventas Diarias ($ CLP)';
        labelGanancias = 'Ganancia Diaria ($ CLP)';
        tituloText = 'EVOLUCIÓN DIARIA DEL PERÍODO: VENTAS Y GANANCIAS REALES';
        subtituloText = 'Registro diario de ingresos reales en la base de datos oficial';
    } else {
        dataSelected = data15Meses;
        labelVentas = 'Ventas Mensuales ($ CLP)';
        labelGanancias = 'Ganancia Mensual ($ CLP)';
        tituloText = 'EVOLUCIÓN MENSUAL HISTÓRICA: VENTAS TOTALES Y COMPARATIVA REAL';
        subtituloText = 'Historial de meses registrados en base de datos • Auditoría 100% verificada';
    }

    document.getElementById('chartTitulo').innerText = tituloText;
    document.getElementById('chartSubtitulo').innerText = subtituloText;

    if (currentChart) {
        currentChart.destroy();
    }

    currentChart = new Chart(ctx, {
        data: {
            labels: dataSelected.labels,
            datasets: [
                // BARRAS: Ventas
                {
                    type: 'bar',
                    label: labelVentas,
                    data: dataSelected.ventas,
                    backgroundColor: 'rgba(198, 40, 40, 0.75)',
                    hoverBackgroundColor: 'rgba(198, 40, 40, 0.95)',
                    borderColor: '#c62828',
                    borderWidth: 1.5,
                    borderRadius: 6,
                    barPercentage: 0.65,
                    order: 2
                },
                // LÍNEA: Ganancias (Requisito clave: diagrama de barras con línea de ganancia)
                {
                    type: 'line',
                    label: labelGanancias,
                    data: dataSelected.ganancias,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.2)',
                    pointBackgroundColor: '#b45309',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    pointHoverRadius: 8,
                    tension: 0.35,
                    borderWidth: 3,
                    fill: false,
                    order: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        font: {
                            family: "'Nunito', sans-serif",
                            size: 13,
                            weight: 'bold'
                        },
                        usePointStyle: true
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(45, 33, 24, 0.92)',
                    titleFont: { family: "'Oswald', sans-serif", size: 14 },
                    bodyFont: { family: "'Nunito', sans-serif", size: 13 },
                    padding: 12,
                    callbacks: {
                        label: function(context) {
                            const val = context.parsed.y;
                            return `${context.dataset.label}: ${formatearMoneda(val, dataSelected.unidad)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        font: {
                            family: "'Nunito', sans-serif",
                            size: 11,
                            weight: 'bold'
                        }
                    }
                },
                y: {
                    beginAtZero: true,
                    grid: {
                        color: '#f0ede6'
                    },
                    ticks: {
                        font: {
                            family: "'Nunito', sans-serif",
                            size: 11
                        },
                        callback: function(value) {
                            return formatearMoneda(value, dataSelected.unidad);
                        }
                    }
                }
            }
        }
    });
}

// Alternar temporalidad
function cambiarTemporalidad(tipo) {
    document.querySelectorAll('.btn-timeframe').forEach(b => b.classList.remove('active'));
    if (tipo === 'hora') {
        document.getElementById('btnHora').classList.add('active');
        document.getElementById('seccionTablaMeses').classList.add('d-none');
    } else if (tipo === 'dia') {
        document.getElementById('btnDia').classList.add('active');
        document.getElementById('seccionTablaMeses').classList.add('d-none');
    } else {
        document.getElementById('btnMes').classList.add('active');
        document.getElementById('seccionTablaMeses').classList.remove('d-none');
    }
    renderizarChart(tipo);
}


// Control dinámico de campos en el modal de exportación
function actualizarControlesRango() {
    const r15 = document.getElementById('rango15Meses');
    const rMes = document.getElementById('rangoMes');
    const rSem = document.getElementById('rangoSemana');
    const rDia = document.getElementById('rangoDia');

    const contDia = document.getElementById('contenedorDiaSelector');
    const contMes = document.getElementById('contenedorMesSelector');

    if (rDia && rDia.checked) {
        contDia.classList.remove('d-none');
        contMes.classList.add('d-none');
    } else if (rSem && rSem.checked) {
        contDia.classList.remove('d-none');
        contMes.classList.add('d-none');
    } else if (rMes && rMes.checked) {
        contDia.classList.add('d-none');
        contMes.classList.remove('d-none');
    } else {
        contDia.classList.add('d-none');
        contMes.classList.add('d-none');
    }
}

// Inicializar gráfico al cargar la página

function renderizarDonutMediosPago() {
    const canvas = document.getElementById('mediosPagoDonutChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const mpData = (chartDataServer && chartDataServer.medios_pago) ? chartDataServer.medios_pago : null;

    if (!mpData || !mpData.labels || mpData.labels.length === 0 || (mpData.totales.length === 1 && mpData.totales[0] === 0)) {
        ctx.font = '13px Nunito, sans-serif';
        ctx.fillStyle = '#9ca3af';
        ctx.textAlign = 'center';
        ctx.fillText('Sin datos de pago en el período', canvas.width / 2, 90);
        return;
    }

    const paletaColores = [
        '#16a34a', // Efectivo (Verde)
        '#2563eb', // Débito (Azul)
        '#8b5cf6', // Crédito (Púrpura)
        '#f59e0b', // Transferencia (Ámbar)
        '#ef4444'  // Otro
    ];

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: mpData.labels,
            datasets: [{
                data: mpData.totales,
                backgroundColor: paletaColores.slice(0, mpData.labels.length),
                hoverOffset: 6,
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        boxWidth: 12,
                        padding: 10,
                        font: { family: 'Nunito, sans-serif', size: 11, weight: 'bold' }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const val = context.parsed;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                            return ` ${context.label}: $${Math.round(val).toLocaleString('es-CL')} (${pct}%)`;
                        }
                    }
                }
            },
            cutout: '62%'
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    renderizarChart('mes');
    renderizarDonutMediosPago();

// Tarea 1: Auto-sincronización fluida en tiempo real del dashboard analítico sin F5 y con Scroll Lock
let sincDashboard = false;
async function autoSincronizarDashboard() {
    if (sincDashboard) return;
    if (document.querySelector('.modal.show')) return;
    sincDashboard = true;
    const scrollPos = window.scrollY;

    try {
        const resp = await fetch(window.location.href, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!resp.ok) { sincDashboard = false; return; }
        const html = await resp.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        const nuevoKPI = doc.getElementById('contenedorDashboardKPIs');
        const actualKPI = document.getElementById('contenedorDashboardKPIs');
        if (nuevoKPI && actualKPI && nuevoKPI.innerHTML.trim() !== actualKPI.innerHTML.trim()) {
            actualKPI.innerHTML = nuevoKPI.innerHTML;
        }
        window.scrollTo(0, scrollPos);
    } catch(e) {}
    finally { sincDashboard = false; }
}
// Sincronizar KPIs en vivo cada 1.5 segundos (1500 ms) con gestion inteligente de recursos
let dashInterval = setInterval(autoSincronizarDashboard, 1500);

document.addEventListener('visibilitychange', () => {
    clearInterval(dashInterval);
    if (document.visibilityState === 'visible') {
        autoSincronizarDashboard();
        dashInterval = setInterval(autoSincronizarDashboard, 1500);
    } else {
        dashInterval = setInterval(autoSincronizarDashboard, 6000);
    }
});

});
