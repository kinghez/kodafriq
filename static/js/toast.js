/**
 * Kodafriq Floating Toast & Notification Engine
 */
(() => {
    // 1. Toast Notification System
    function ensureToastContainer() {
        let container = document.getElementById('kfToastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'kfToastContainer';
            container.className = 'kf-toast-container';
            container.setAttribute('aria-live', 'polite');
            document.body.appendChild(container);
        }
        return container;
    }

    const ICONS = {
        success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`,
        error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>`,
        warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>`,
        info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`
    };

    const TITLES = {
        success: 'Success',
        error: 'Attention Needed',
        warning: 'Notice',
        info: 'Information'
    };

    window.showToast = function(message, type = 'info', title = '', duration = 4500) {
        if (!message) return;

        // Map Django tags to valid toast types
        type = type.toLowerCase();
        if (type.includes('error') || type.includes('danger')) type = 'error';
        else if (type.includes('success')) type = 'success';
        else if (type.includes('warning')) type = 'warning';
        else type = 'info';

        const toastTitle = title || TITLES[type] || 'Notification';
        const container = ensureToastContainer();

        const toast = document.createElement('div');
        toast.className = `kf-toast toast-${type}`;
        toast.innerHTML = `
            <div class="kf-toast-inner">
                <div class="kf-toast-icon-wrap">
                    ${ICONS[type]}
                </div>
                <div class="kf-toast-body">
                    <div class="kf-toast-title">${toastTitle}</div>
                    <div class="kf-toast-message">${message}</div>
                </div>
                <button type="button" class="kf-toast-close" aria-label="Close Notification">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>
            <div class="kf-toast-progress">
                <div class="kf-toast-progress-bar"></div>
            </div>
        `;

        container.appendChild(toast);

        // Entrance animation
        requestAnimationFrame(() => {
            toast.classList.add('show');
            const pBar = toast.querySelector('.kf-toast-progress-bar');
            if (pBar) {
                pBar.style.transition = `transform ${duration}ms linear`;
                pBar.style.transform = 'scaleX(0)';
            }
        });

        // Close logic
        let dismissed = false;
        const dismissToast = () => {
            if (dismissed) return;
            dismissed = true;
            toast.classList.remove('show');
            toast.classList.add('hide');
            setTimeout(() => {
                if (toast.parentElement) toast.parentElement.removeChild(toast);
            }, 400);
        };

        const closeBtn = toast.querySelector('.kf-toast-close');
        if (closeBtn) closeBtn.addEventListener('click', dismissToast);

        // Auto-dismiss timeout
        setTimeout(dismissToast, duration);
    };

    // 2. Notification Dropdown Engine
    document.addEventListener('DOMContentLoaded', () => {
        const bellWrap = document.getElementById('kfNotifBellWrap');
        const notifDropdown = document.getElementById('kfNotifDropdown');
        const markAllBtn = document.getElementById('kfMarkAllReadBtn');
        const notifBadge = document.getElementById('kfNotifBadge');
        const sidebarCounter = document.getElementById('kfSidebarNotifCounter');

        if (bellWrap && notifDropdown) {
            // Toggle dropdown on bell click
            bellWrap.addEventListener('click', (e) => {
                if (e.target.closest('#kfNotifDropdown') && !e.target.closest('#kfMarkAllReadBtn')) {
                    return; // Allow clicks inside dropdown
                }
                e.stopPropagation();
                notifDropdown.classList.toggle('open');
            });

            // Close on click outside
            document.addEventListener('click', (e) => {
                if (!bellWrap.contains(e.target)) {
                    notifDropdown.classList.remove('open');
                }
            });

            // Close on ESC
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    notifDropdown.classList.remove('open');
                }
            });
        }

        // Mark All Read via AJAX
        if (markAllBtn) {
            markAllBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();

                const csrfToken = getCookie('csrftoken');
                fetch('/dashboard/notifications/mark-all-read/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'ok') {
                        if (notifBadge) notifBadge.style.display = 'none';
                        if (sidebarCounter) sidebarCounter.style.display = 'none';
                        markAllBtn.style.display = 'none';
                        const pillCount = document.querySelector('.kf-notif-pill-count');
                        if (pillCount) pillCount.style.display = 'none';
                        document.querySelectorAll('.kf-notif-drop-item.unread').forEach(item => {
                            item.classList.remove('unread');
                            const dot = item.querySelector('.kf-notif-unread-dot');
                            if (dot) dot.remove();
                        });
                        window.showToast('All notifications marked as read', 'success');
                    }
                })
                .catch(() => {
                    window.location.href = '/dashboard/notifications/';
                });
            });
        }

        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }
    });
})();
