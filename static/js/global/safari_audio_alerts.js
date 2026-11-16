/**
 * Parque Safari - Motor Unificado de Alertas Sonoras (Web Audio API),
 * Notificaciones Persistentes (Popover API + ARIA Live) y Bus Inter-Pestañas (BroadcastChannel).
 *
 * Soluciona:
 * - Políticas de Autoplay sin condición de carrera captura/burbuja y sin bloqueo de audioCtx.resume().
 * - Alerta sonora instantánea de Cocina/Barra -> Cajero (Monitor y Crear Ticket) y Mesero.
 * - Sincronización en < 5 ms entre pestañas del mismo navegador vía BroadcastChannel.
 */
(function (global) {
    'use strict';

    // Carga condicional del polyfill de Popover API solo si el navegador carece de soporte nativo
    if (typeof HTMLElement !== 'undefined' && !Object.hasOwn(HTMLElement.prototype, 'popover')) {
        const scriptPolyfill = document.createElement('script');
        scriptPolyfill.src = 'https://cdn.jsdelivr.net/npm/@oddbird/popover-polyfill@latest/dist/popover.min.js';
        scriptPolyfill.async = true;
        document.head.appendChild(scriptPolyfill);
    }

    const SafariAudioAlerts = (() => {
        let audioCtx = null;
        let unlocked = false;
        let listenersBound = false;
        let pendingProfile = null;
        let pendingTimestamp = 0;
        const boundButtons = [];

        function getAudioContextClass() {
            return global.AudioContext || global.webkitAudioContext || null;
        }

        function isEnabled(storageKey) {
            try {
                return localStorage.getItem(storageKey) !== 'false';
            } catch (_err) {
                return true;
            }
        }

        function setEnabled(storageKey, val) {
            try {
                localStorage.setItem(storageKey, val ? 'true' : 'false');
            } catch (_err) {
                // Ignorar si localStorage está restringido
            }
        }

        function notifyButtonsState() {
            boundButtons.forEach((cfg) => refreshButtonUI(cfg));
        }

        function probeInitialState() {
            if (audioCtx) {
                unlocked = audioCtx.state === 'running';
                return unlocked;
            }
            const Ctx = getAudioContextClass();
            if (!Ctx) return false;
            try {
                audioCtx = new Ctx();
                unlocked = audioCtx.state === 'running';
                if (unlocked) {
                    removeUnlockListeners();
                } else if (typeof audioCtx.addEventListener === 'function') {
                    audioCtx.addEventListener('statechange', () => {
                        if (audioCtx && audioCtx.state === 'running' && !unlocked) {
                            unlocked = true;
                            removeUnlockListeners();
                            notifyButtonsState();
                            flushPendingAlert();
                        }
                    });
                }
            } catch (_err) {
                unlocked = false;
            }
            return unlocked;
        }

        function ensureContextFromGesture() {
            const Ctx = getAudioContextClass();
            if (!Ctx) return null;
            if (!audioCtx) {
                try {
                    audioCtx = new Ctx();
                } catch (_err) {
                    return null;
                }
            }

            if (audioCtx.state === 'running') {
                unlocked = true;
                removeUnlockListeners();
                notifyButtonsState();
                flushPendingAlert();
            } else if (audioCtx.state === 'suspended') {
                audioCtx.resume().then(() => {
                    if (audioCtx && audioCtx.state === 'running') {
                        unlocked = true;
                        removeUnlockListeners();
                        notifyButtonsState();
                        flushPendingAlert();
                    }
                }).catch(() => {});
            }

            // Pulso silencioso para desbloquear WebKit / Safari iOS dentro del gesto del usuario
            try {
                if (audioCtx) {
                    const buf = audioCtx.createBuffer(1, 1, 22050);
                    const src = audioCtx.createBufferSource();
                    src.buffer = buf;
                    src.connect(audioCtx.destination);
                    src.start(0);
                    if (audioCtx.state === 'running') {
                        unlocked = true;
                    }
                }
            } catch (_err) {}
            return audioCtx;
        }

        function handleUserUnlockGesture(ev) {
            // Si el usuario hizo clic en el botón de toggle de sonido, dejamos que su listener maneje
            // el desbloqueo sin alterar el estado antes de verificar wasLocked (evita silenciarlo por error).
            if (ev && ev.target && typeof ev.target.closest === 'function') {
                if (ev.target.closest('[data-safari-audio-toggle="1"]')) {
                    return;
                }
            }
            ensureContextFromGesture();
        }

        function bindUnlockListeners() {
            if (listenersBound || unlocked) return;
            listenersBound = true;
            ['pointerdown', 'touchstart', 'click', 'keydown'].forEach((evt) => {
                document.addEventListener(evt, handleUserUnlockGesture, { capture: true, passive: true });
            });
        }

        function removeUnlockListeners() {
            if (!listenersBound) return;
            listenersBound = false;
            ['pointerdown', 'touchstart', 'click', 'keydown'].forEach((evt) => {
                document.removeEventListener(evt, handleUserUnlockGesture, { capture: true });
            });
        }

        async function getRunningContext() {
            const Ctx = getAudioContextClass();
            if (!Ctx) return null;
            if (!audioCtx) {
                try {
                    audioCtx = new Ctx();
                } catch (_err) {
                    return null;
                }
            }
            if (audioCtx.state === 'running') {
                unlocked = true;
                removeUnlockListeners();
                notifyButtonsState();
                return audioCtx;
            }
            if (audioCtx.state === 'suspended') {
                try {
                    // Timeout breve de 60ms para no colgar jamás si autoplay está bloqueado
                    await Promise.race([
                        audioCtx.resume().catch(() => {}),
                        new Promise((resolve) => setTimeout(resolve, 60)),
                    ]);
                } catch (_err) {}
            }
            if (audioCtx && audioCtx.state === 'running') {
                unlocked = true;
                removeUnlockListeners();
                notifyButtonsState();
                return audioCtx;
            }
            unlocked = false;
            return null;
        }

        function scheduleTone(ctx, freq, startTime, duration, vol = 0.3, wave = 'triangle') {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();

            osc.type = wave;
            osc.frequency.setValueAtTime(freq, startTime);

            gain.gain.setValueAtTime(0.0001, startTime);
            gain.gain.exponentialRampToValueAtTime(Math.max(0.001, vol), startTime + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);

            osc.connect(gain);
            gain.connect(ctx.destination);

            osc.start(startTime);
            osc.stop(startTime + duration + 0.06);
        }

        function playOnContext(ctx, profile) {
            const t = ctx.currentTime + 0.02;
            if (profile === 'cocina') {
                // Campana de pase de cocina caliente (E5 -> A5 + armónico)
                scheduleTone(ctx, 659.25, t, 0.28, 0.34, 'triangle');
                scheduleTone(ctx, 880.00, t + 0.17, 0.55, 0.40, 'triangle');
                scheduleTone(ctx, 1760.00, t + 0.17, 0.35, 0.12, 'sine');
            } else if (profile === 'barra') {
                // Campana cristalina de barista / barra (G5 -> C6 + armónico)
                scheduleTone(ctx, 783.99, t, 0.26, 0.32, 'triangle');
                scheduleTone(ctx, 1046.50, t + 0.16, 0.50, 0.38, 'triangle');
                scheduleTone(ctx, 2093.00, t + 0.16, 0.30, 0.10, 'sine');
            } else if (profile === 'pedido_listo') {
                // Timbre triple de servicio listo para Cajero y Mesero (G5 -> B5 -> D6 -> G6)
                scheduleTone(ctx, 783.99, t, 0.18, 0.34, 'triangle');
                scheduleTone(ctx, 987.77, t + 0.12, 0.18, 0.36, 'triangle');
                scheduleTone(ctx, 1174.66, t + 0.24, 0.28, 0.40, 'triangle');
                scheduleTone(ctx, 1567.98, t + 0.44, 0.58, 0.42, 'sine');
                scheduleTone(ctx, 783.99, t + 0.44, 0.45, 0.18, 'triangle');
            } else if (profile === 'alerta') {
                scheduleTone(ctx, 880.00, t, 0.14, 0.24, 'triangle');
                scheduleTone(ctx, 440.00, t + 0.14, 0.24, 0.24, 'triangle');
            } else {
                // Éxito / Confirmación rápida (C5 -> E5 -> G5)
                scheduleTone(ctx, 523.25, t, 0.12, 0.22, 'sine');
                scheduleTone(ctx, 659.25, t + 0.08, 0.14, 0.24, 'sine');
                scheduleTone(ctx, 783.99, t + 0.16, 0.28, 0.26, 'sine');
            }
        }

        function flushPendingAlert() {
            if (!pendingProfile) return;
            const age = Date.now() - pendingTimestamp;
            const prof = pendingProfile;
            pendingProfile = null;
            if (age <= 30000 && audioCtx && audioCtx.state === 'running') {
                playOnContext(audioCtx, prof);
            }
        }

        async function play(profile = 'pedido_listo', storageKey = null) {
            if (storageKey && !isEnabled(storageKey)) return false;

            const ctx = await getRunningContext();
            if (!ctx) {
                pendingProfile = profile;
                pendingTimestamp = Date.now();
                bindUnlockListeners();
                notifyButtonsState();
                return false;
            }
            try {
                playOnContext(ctx, profile);
                return true;
            } catch (_err) {
                return false;
            }
        }

        function refreshButtonUI(cfg) {
            const btn = document.getElementById(cfg.buttonId);
            if (!btn) return;
            const enabled = isEnabled(cfg.storageKey);
            const isDark = cfg.variant === 'dark-header';

            btn.setAttribute('data-safari-audio-toggle', '1');

            if (!enabled) {
                btn.setAttribute('data-audio-locked', '0');
                btn.className = isDark
                    ? 'btn btn-sm btn-outline-light text-on-brand-muted rounded-pill px-3 d-flex align-items-center gap-1 shadow-sm'
                    : 'btn btn-sm btn-outline-secondary bg-white text-muted rounded-pill px-3 d-flex align-items-center gap-1 shadow-xs';
                btn.innerHTML = '<i class="bi bi-volume-mute-fill" aria-hidden="true"></i> <span class="d-none d-md-inline small fw-bold">Sonido OFF</span>';
                btn.setAttribute('aria-pressed', 'false');
                btn.title = 'Alertas sonoras silenciadas. Clic para activar.';
                return;
            }

            if (!unlocked) {
                btn.setAttribute('data-audio-locked', '1');
                btn.className = 'btn btn-sm btn-warning text-dark rounded-pill px-3 d-flex align-items-center gap-1 shadow-sm fw-bold';
                btn.innerHTML = '<i class="bi bi-volume-up-fill" aria-hidden="true"></i> <span class="d-none d-md-inline small fw-bold">Activar Sonido</span>';
                btn.setAttribute('aria-pressed', 'true');
                btn.title = 'Haz clic aquí (o toca la pantalla) para habilitar las alertas de sonido del navegador.';
                return;
            }

            btn.setAttribute('data-audio-locked', '0');
            btn.className = isDark
                ? 'btn btn-sm btn-outline-light rounded-pill px-3 d-flex align-items-center gap-1 shadow-sm'
                : 'btn btn-sm btn-success text-white rounded-pill px-3 d-flex align-items-center gap-1 shadow-xs fw-bold';
            btn.innerHTML = '<i class="bi bi-volume-up-fill" aria-hidden="true"></i> <span class="d-none d-md-inline small fw-bold">Sonido ON</span>';
            btn.setAttribute('aria-pressed', 'true');
            btn.title = 'Alerta sonora activa y desbloqueada. Clic para silenciar.';
        }

        function bindToggleButton(options) {
            const cfg = {
                buttonId: options.buttonId,
                storageKey: options.storageKey,
                testProfile: options.testProfile || 'pedido_listo',
                variant: options.variant || 'light-header',
            };
            if (!boundButtons.some((b) => b.buttonId === cfg.buttonId)) {
                boundButtons.push(cfg);
            }

            probeInitialState();
            bindUnlockListeners();

            const btn = document.getElementById(cfg.buttonId);
            if (btn && btn.dataset.safariAudioBound !== '1') {
                btn.dataset.safariAudioBound = '1';
                btn.addEventListener('click', async () => {
                    const wasLocked = btn.getAttribute('data-audio-locked') === '1';
                    const currentlyEnabled = isEnabled(cfg.storageKey);

                    if (currentlyEnabled && wasLocked) {
                        pendingProfile = null;
                    }
                    ensureContextFromGesture();

                    // Si estaba pendiente de primer gesto, este clic desbloquea y prueba el timbre sin apagarlo
                    if (currentlyEnabled && wasLocked) {
                        const ctx = await getRunningContext();
                        if (ctx) {
                            playOnContext(ctx, cfg.testProfile);
                        }
                        refreshButtonUI(cfg);
                        return;
                    }

                    const nextState = !currentlyEnabled;
                    setEnabled(cfg.storageKey, nextState);
                    if (nextState) {
                        const ctx = await getRunningContext();
                        if (ctx) {
                            playOnContext(ctx, cfg.testProfile);
                        }
                    }
                    refreshButtonUI(cfg);
                });
            }
            refreshButtonUI(cfg);
        }

        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible' && audioCtx && audioCtx.state === 'suspended' && unlocked) {
                audioCtx.resume().catch(() => {});
            }
        });

        probeInitialState();
        bindUnlockListeners();

        return {
            play,
            isEnabled,
            setEnabled,
            bindToggleButton,
            isUnlocked: () => unlocked,
            unlock: ensureContextFromGesture,
        };
    })();

    const SafariReadyNotifier = (() => {
        const deferredQueue = [];
        let modalObserverBound = false;

        function hasOpenModal() {
            return Boolean(document.querySelector('.modal.show, dialog[open], .swal2-container'));
        }

        function announceText(text) {
            if (!text) return;
            if (typeof document.body.ariaNotify === 'function') {
                try {
                    document.body.ariaNotify(text);
                    return;
                } catch (_err) {}
            }
            const liveRegion = document.getElementById('safariReadyAriaLive');
            if (liveRegion) {
                liveRegion.textContent = '';
                global.requestAnimationFrame(() => {
                    liveRegion.textContent = text;
                });
            }
        }

        function showToastElement(item) {
            const region = document.getElementById('safariReadyToastRegion');
            if (!region) return;

            const toastEl = document.createElement('div');
            const toastId = 'safariReadyToast_' + String(item.key || Date.now()).replace(/[^a-zA-Z0-9_-]/g, '_');
            const existing = document.getElementById(toastId);
            if (existing) {
                try {
                    if (typeof existing.hidePopover === 'function') existing.hidePopover();
                } catch (_err) {}
                existing.remove();
            }

            toastEl.id = toastId;
            toastEl.className = 'safari-ready-toast rounded-4';
            toastEl.setAttribute('popover', 'manual');
            toastEl.setAttribute('role', 'status');

            const header = document.createElement('div');
            header.className = 'safari-ready-toast-header';

            const titleWrap = document.createElement('div');
            const title = document.createElement('div');
            title.className = 'safari-ready-toast-title';
            title.innerHTML = '<i class="bi bi-bell-fill text-success me-1" aria-hidden="true"></i>';
            const titleSpan = document.createElement('span');
            titleSpan.textContent = `¡Pedido Listo en ${item.estacion || 'Cocina'}!`;
            title.appendChild(titleSpan);

            const meta = document.createElement('div');
            meta.className = 'safari-ready-toast-meta';
            const strongCode = document.createElement('strong');
            strongCode.textContent = `#${item.codigo || ('COM-' + String(item.pedido_id || '').padStart(4, '0'))}`;
            meta.appendChild(strongCode);
            meta.appendChild(document.createTextNode(` • ${item.mesa || 'Mostrador'}`));

            titleWrap.appendChild(title);
            titleWrap.appendChild(meta);

            const closeBtn = document.createElement('button');
            closeBtn.type = 'button';
            closeBtn.className = 'btn-close safari-toast-close-btn';
            closeBtn.setAttribute('aria-label', 'Cerrar aviso de pedido listo');
            closeBtn.setAttribute('popovertarget', toastId);
            closeBtn.setAttribute('popovertargetaction', 'hide');

            header.appendChild(titleWrap);
            header.appendChild(closeBtn);
            toastEl.appendChild(header);

            const priorFocus = document.activeElement;
            let hideTimer = null;

            function dismissToast(restoreFocusIfFocused) {
                clearTimeout(hideTimer);
                const wasFocusedInside = toastEl.contains(document.activeElement);
                try {
                    if (typeof toastEl.hidePopover === 'function') {
                        toastEl.hidePopover();
                    }
                } catch (_err) {}
                toastEl.classList.remove('safari-toast-open');
                toastEl.remove();
                if (restoreFocusIfFocused && wasFocusedInside && priorFocus && typeof priorFocus.focus === 'function') {
                    priorFocus.focus();
                }
            }

            function scheduleAutoHide() {
                clearTimeout(hideTimer);
                hideTimer = setTimeout(() => {
                    if (toastEl.matches(':hover') || toastEl.contains(document.activeElement)) {
                        scheduleAutoHide();
                        return;
                    }
                    dismissToast(false);
                }, 12000);
            }

            closeBtn.addEventListener('click', () => dismissToast(true));
            toastEl.addEventListener('mouseenter', () => clearTimeout(hideTimer));
            toastEl.addEventListener('mouseleave', scheduleAutoHide);
            toastEl.addEventListener('focusin', () => clearTimeout(hideTimer));
            toastEl.addEventListener('focusout', scheduleAutoHide);

            const visibleCount = region.querySelectorAll('.safari-ready-toast').length;
            if (visibleCount > 0) {
                toastEl.style.top = `${1 + visibleCount * 5.2}rem`;
            }

            region.appendChild(toastEl);
            try {
                if (typeof toastEl.showPopover === 'function') {
                    toastEl.showPopover();
                } else {
                    toastEl.classList.add('safari-toast-open');
                }
            } catch (_err) {
                toastEl.classList.add('safari-toast-open');
            }

            announceText(`Pedido ${item.codigo} listo en ${item.estacion || 'Cocina'} para ${item.mesa || 'Mostrador'}`);
            scheduleAutoHide();
        }

        function bindModalCloseReplay() {
            if (modalObserverBound) return;
            modalObserverBound = true;
            document.addEventListener('hidden.bs.modal', () => {
                if (hasOpenModal()) return;
                while (deferredQueue.length > 0) {
                    const nextItem = deferredQueue.shift();
                    showToastElement(nextItem);
                }
            });
        }

        function notifyReady(item) {
            if (!item) return;
            bindModalCloseReplay();
            if (hasOpenModal()) {
                deferredQueue.push(item);
                return;
            }
            showToastElement(item);
        }

        return { notifyReady };
    })();

    const SafariSyncBus = (() => {
        let channel = null;
        if (typeof BroadcastChannel !== 'undefined') {
            try {
                channel = new BroadcastChannel('safari_pos_sync_v1');
            } catch (_err) {
                channel = null;
            }
        }

        function publish(payload) {
            if (!channel) return;
            try {
                channel.postMessage({ ...payload, ts: Date.now() });
            } catch (_err) {}
        }

        function subscribe(handler) {
            if (!channel || typeof handler !== 'function') return;
            channel.addEventListener('message', (ev) => {
                if (ev && ev.data) handler(ev.data);
            });
        }

        return { publish, subscribe };
    })();

    /**
     * Monitor liviano reutilizable para pantallas POS secundarias (/vendedor/crear-ticket/)
     * que solo necesitan escuchar alertas sonoras y toasts de pedidos listos sin descargar HTML completo.
     */
    const SafariReadyMonitor = (() => {
        function start(options) {
            const storageKey = options.storageKey || 'safari_audio_v2_cajero';
            const visibleMs = options.visibleMs || 2000;
            const hiddenMs = options.hiddenMs || 5000;
            let seenKeys = null;
            let inFlight = false;
            let pendingRun = false;
            let timerId = null;

            function schedule(customDelay) {
                clearTimeout(timerId);
                const delay = typeof customDelay === 'number'
                    ? customDelay
                    : (document.visibilityState === 'visible' ? visibleMs : hiddenMs);
                timerId = setTimeout(tick, delay);
            }

            async function tick() {
                if (inFlight) {
                    pendingRun = true;
                    return;
                }
                inFlight = true;
                try {
                    const resp = await fetch('/api/sincronizacion/estado/', {
                        headers: { 'X-Requested-With': 'XMLHttpRequest' },
                        priority: 'low',
                    });
                    if (resp.ok) {
                        const delta = await resp.json();
                        if (delta.ok && Array.isArray(delta.listos_detalle)) {
                            const actuales = new Set(delta.listos_detalle.map((i) => i.key));
                            if (seenKeys === null) {
                                // Primera lectura establece línea base sin sonar pedidos históricos
                                seenKeys = actuales;
                            } else {
                                const nuevos = delta.listos_detalle.filter((i) => i.key && !seenKeys.has(i.key));
                                seenKeys = actuales;
                                if (nuevos.length > 0) {
                                    SafariAudioAlerts.play('pedido_listo', storageKey);
                                    nuevos.slice(0, 3).forEach((i) => SafariReadyNotifier.notifyReady(i));
                                }
                            }
                        }
                    }
                } catch (_err) {
                } finally {
                    inFlight = false;
                    if (pendingRun) {
                        pendingRun = false;
                        schedule(80);
                    } else {
                        schedule();
                    }
                }
            }

            document.addEventListener('visibilitychange', () => {
                if (document.visibilityState === 'visible') {
                    tick();
                } else {
                    schedule(hiddenMs);
                }
            });

            SafariSyncBus.subscribe((ev) => {
                if (ev && ev.type === 'pedido_estado') {
                    tick();
                }
            });

            tick();
        }

        return { start };
    })();

    global.SafariAudioAlerts = SafariAudioAlerts;
    global.SafariReadyNotifier = SafariReadyNotifier;
    global.SafariSyncBus = SafariSyncBus;
    global.SafariReadyMonitor = SafariReadyMonitor;
})(window);
